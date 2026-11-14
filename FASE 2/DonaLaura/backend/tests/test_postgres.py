"""Pruebas contra una base temporal. Nunca truncan ni modifican la base operativa."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import uuid4
from types import SimpleNamespace

import psycopg
from psycopg import sql
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
import pagos
import seguridad
import operacion
import seguimiento
import faenas
import entorno
import resumen
import cobros
import semana
from ia.gestion import consultar_gestion
from database import conectar_bd

pytestmark = pytest.mark.integration


def test_guia_semanal_normaliza_lunes_y_no_realiza_cierre(bd):
    d=semana.consultar_semana(date(2026,10,14))
    assert d["desde"]==date(2026,10,12) and d["hasta"]==date(2026,10,18)
    assert d["kilos"]==100 and d["pago_estimado"]==1250
    assert not d["cerrada"] and d["listo_para_revisar_cierre"]
    assert any(a["clave"]=="faenas" and not a["bloquea"] for a in d["alertas"])
    with conectar_bd() as c: assert c.execute("SELECT COUNT(*) FROM pagos").fetchone()[0]==0


def test_guia_separa_movimientos_por_fecha_de_la_semana_producida(actor):
    identificador,_=cuenta_prueba(actor)
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    seguimiento.aprobar(1,actor)
    seguimiento.abonar(1,seguimiento.Abono(clave=uuid4(),monto=500,fecha=date(2026,10,23),comprobante="SEMANA-PAGO"),actor)
    cobros.registrar_abono(identificador,cobros.AbonoCliente(clave=uuid4(),monto=4000,fecha=date(2026,10,20),referencia="SEMANA-COBRO"),actor)
    produccion=semana.consultar_semana(date(2026,10,14))
    movimientos=semana.consultar_semana(date(2026,10,20))
    assert produccion["pago_confirmado"]==2375 and produccion["saldo_cierres_semana"]==1875
    assert produccion["recibido_clientes_periodo"]==0 and produccion["abonado_trabajadores_periodo"]==0
    assert movimientos["registros"]==0
    assert movimientos["recibido_clientes_periodo"]==4000 and movimientos["abonado_trabajadores_periodo"]==500
    assert movimientos["cartera_actual"]==produccion["cartera_actual"]
    assert movimientos["cartera_actual"]["saldo"]==5000


def test_guia_cerrada_conserva_monto_con_ajustes(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    operacion.ajustar(1,operacion.Ajuste(clave=uuid4(),diferencia_kg=8,motivo="Revisión de pesaje"),actor)
    d=semana.consultar_semana(date(2026,10,14))
    assert d["kilos_originales"]==100 and d["ajustes_kg"]==8 and d["kilos"]==108
    assert d["pago_confirmado"]==1350 and d["cerrada"]
    assert not d["listo_para_revisar_cierre"]


def test_guia_no_inventa_pago_sin_tarifa_ni_dias_trabajados(bd):
    with conectar_bd() as c: c.execute("DELETE FROM tarifas")
    d=semana.consultar_semana(date(2026,10,14))
    assert d["pago_estimado"] is None and not d["listo_para_revisar_cierre"]
    assert d["dias_con_registros"]==1 and len(d["dias"])==1
    assert any(a["clave"]=="tarifa" and a["bloquea"] for a in d["alertas"])


def test_guia_detecta_duplicados_horas_nulas_y_exceso_diario(bd):
    with conectar_bd() as c:
        c.execute("""INSERT INTO produccion(id_trabajador,id_jornada,id_sector,id_labor,cantidad_kg,horas_trabajadas)
            VALUES (1,1,1,1,10,20),(1,1,1,1,20,NULL)""")
    d=semana.consultar_semana(date(2026,10,14))
    assert {a["clave"] for a in d["alertas"]}>={"datos","duplicados","horas"}
    assert not d["listo_para_revisar_cierre"]


def test_guia_pdf_autenticado_disponible_para_consulta_sin_mutar(actor):
    cliente=TestClient(main.app)
    assert cliente.get("/preparar-semana/pdf").status_code==401
    with conectar_bd() as c: c.execute("UPDATE usuarios SET rol='consulta' WHERE usuario='admin'")
    assert cliente.post("/auth/login",json={"usuario":"admin","password":"Clave-de-prueba-1234"}).status_code==200
    assert cliente.get("/preparar-semana?fecha=2026-10-14").status_code==200
    pdf=cliente.get("/preparar-semana/pdf?fecha=2026-10-14")
    assert pdf.status_code==200 and pdf.headers["content-type"]=="application/pdf"
    assert pdf.content.startswith(b"%PDF-") and b"/Count 1" in pdf.content
    assert "2026-10-12" in pdf.headers["content-disposition"]
    assert cliente.get("/preparar-semana?fecha=invalida").status_code==422
    with conectar_bd() as c:
        assert c.execute("SELECT COUNT(*) FROM pagos").fetchone()[0]==0


def cuenta_prueba(actor, **cambios):
    identificador,_ = acuerdo_prueba(actor)
    operacion.guardar_jornada(lote_prueba(id_faena=identificador),actor)
    datos = dict(clave=uuid4(),id_faena=identificador,fecha_acuerdo=date(2026,10,15),vencimiento=date(2026,10,30),monto=9000,concepto="Acuerdo de cosecha revisado")
    datos.update(cambios)
    objeto = cobros.Cobro(**datos)
    return cobros.confirmar_cobro(objeto,actor)["id"],objeto


def test_cobros_separan_estimado_confirmado_recibido_y_saldo(actor):
    identificador,_ = cuenta_prueba(actor,monto=9500)
    cobros.registrar_abono(identificador,cobros.AbonoCliente(clave=uuid4(),monto=5000,fecha=date(2026,10,20),referencia="CLIENTE-001"),actor)
    cartera = cobros.listar_cobros()
    assert cartera["totales"]["confirmado"] == 9500
    assert cartera["totales"]["recibido"] == 5000
    assert cartera["totales"]["saldo"] == 4500
    assert cartera["cobros"][0]["estimado_referencia"] == 9000
    assert cobros.listar_abonos(identificador)[0]["referencia"] == "CLIENTE-001"
    assert resumen.mi_dia(date(2026,10,30))["cobros_clientes"]["vencen_hoy"] == 1
    assert resumen.mi_dia(date(2026,10,31))["cobros_clientes"]["vencidos"] == 1
    gestion = consultar_gestion()
    assert gestion["cartera_actual_por_cliente"][0]["saldo_clp"] == 4500


def test_cobro_confirmado_no_cambia_con_correccion_posterior(actor):
    identificador,_ = cuenta_prueba(actor)
    operacion.corregir(2,operacion.Correccion(cantidad_kg=80,horas_trabajadas=4,version=1,motivo="Corrección de pesaje"),actor)
    c = cobros.listar_cobros()["cobros"][0]
    assert c["id"] == identificador and c["monto"] == 9000 and c["kilos_referencia"] == 90


def test_cobro_idempotente_y_no_se_confirma_dos_veces_la_faena(actor):
    identificador,datos = cuenta_prueba(actor)
    assert cobros.confirmar_cobro(datos,actor)["id"] == identificador
    for cambio in ({"clave":uuid4()},{"monto":Decimal(10000)}):
        with pytest.raises(HTTPException) as error:
            cobros.confirmar_cobro(datos.model_copy(update=cambio),actor)
        assert error.value.status_code == 409


def test_abonos_cliente_idempotentes_referencia_y_sobrepago(actor):
    identificador,_ = cuenta_prueba(actor)
    a = cobros.AbonoCliente(clave=uuid4(),monto=4000,fecha=date(2026,10,20),referencia="COMPROBANTE-UNO")
    cobros.registrar_abono(identificador,a,actor)
    cobros.registrar_abono(identificador,a,actor)
    assert len(cobros.listar_abonos(identificador)) == 1
    for cambio in ({"clave":uuid4(),"referencia":"comprobante-uno"},{"monto":4001},{"clave":uuid4(),"monto":6000,"referencia":"OTRO"}):
        with pytest.raises(HTTPException) as error:
            cobros.registrar_abono(identificador,a.model_copy(update=cambio),actor)
        assert error.value.status_code == 409


def test_abono_cliente_no_admite_fechas_fuera_del_acuerdo(actor):
    identificador,_ = cuenta_prueba(actor)
    for dia in (date(2026,10,14),date(2099,1,1)):
        with pytest.raises(HTTPException) as error:
            cobros.registrar_abono(identificador,cobros.AbonoCliente(clave=uuid4(),monto=1,fecha=dia,referencia="FECHA-PRUEBA"),actor)
        assert error.value.status_code == 422


def test_abonos_cliente_simultaneos_no_sobrepagan(actor):
    identificador,_ = cuenta_prueba(actor)
    barrera = Barrier(2)
    def pagar(i):
        barrera.wait(timeout=10)
        try:
            cobros.registrar_abono(identificador,cobros.AbonoCliente(clave=uuid4(),monto=6000,fecha=date(2026,10,20),referencia=f"CONCURRENTE-{i}"),actor)
            return 201
        except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as e:
        assert sorted(e.map(pagar,range(2))) == [201,409]
    assert cobros.listar_cobros()["totales"]["saldo"] == 3000


def test_anular_sin_abonos_conserva_historial_y_permite_nuevo_acuerdo(actor):
    identificador,datos = cuenta_prueba(actor)
    cobros.anular_cobro(identificador,cobros.Anulacion(motivo="Acuerdo reemplazado por revisión"),actor)
    nuevo = cobros.confirmar_cobro(datos.model_copy(update={"clave":uuid4(),"monto":Decimal(8000)}),actor)
    assert nuevo["id"] != identificador
    cartera = cobros.listar_cobros()
    assert len(cartera["cobros"]) == 2 and cartera["totales"]["saldo"] == 8000
    with pytest.raises(HTTPException):
        cobros.registrar_abono(identificador,cobros.AbonoCliente(clave=uuid4(),monto=1,fecha=date(2026,10,20),referencia="ANULADO"),actor)


def test_no_se_anula_cobro_con_dinero_registrado(actor):
    identificador,_ = cuenta_prueba(actor)
    cobros.registrar_abono(identificador,cobros.AbonoCliente(clave=uuid4(),monto=1,fecha=date(2026,10,20),referencia="RECIBIDO"),actor)
    with pytest.raises(HTTPException) as error:
        cobros.anular_cobro(identificador,cobros.Anulacion(motivo="No debe perder comprobantes"),actor)
    assert error.value.status_code == 409


@pytest.mark.parametrize("rol", ["consulta","encargado"])
def test_cobros_solo_dueno_confirma_abona_y_anula(actor,rol):
    cliente = TestClient(main.app)
    assert cliente.get("/cobros").status_code == 401
    with conectar_bd() as c: c.execute("UPDATE usuarios SET rol=%s WHERE usuario='admin'",(rol,))
    assert cliente.post("/auth/login",json={"usuario":"admin","password":"Clave-de-prueba-1234"}).status_code == 200
    assert cliente.get("/cobros").status_code == 200
    for ruta in ("/cobros","/cobros/1/abonos","/cobros/1/anular"):
        assert cliente.post(ruta,json={}).status_code == 403


def test_mi_dia_distingue_hoy_de_semana_actual_y_ultima_fecha(bd):
    dia = resumen.mi_dia(date(2026,10,14))
    assert dia["registros_hoy"] == 1 and dia["kilos_hoy"] == 100
    assert dia["personas_hoy"] == 1
    assert dia["semanas_por_cerrar"] == 0
    siguiente = resumen.mi_dia(date(2026,10,19))
    assert siguiente["registros_hoy"] == 0
    assert siguiente["ultima_produccion"] == date(2026,10,14)
    assert siguiente["primeras_semanas"] == [date(2026,10,12)]
    assert resumen.mi_dia(date(2026,10,1))["ultima_produccion"] is None


def test_mi_dia_saldo_incluye_ajuste_y_abono_sin_contar_produccion_abierta(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    operacion.ajustar(1,operacion.Ajuste(clave=uuid4(),diferencia_kg=8,motivo="Revisión de pesaje"),actor)
    dia = resumen.mi_dia(date(2026,10,19))
    assert dia["saldo_trabajadores"] == 1350 and dia["pagos_por_aprobar"] == 1
    seguimiento.aprobar(1,actor)
    seguimiento.abonar(1,seguimiento.Abono(clave=uuid4(),monto=500,fecha=date(2026,10,16),comprobante="DIA-ABONO"),actor)
    dia = resumen.mi_dia(date(2026,10,19))
    assert dia["saldo_trabajadores"] == 850
    assert dia["pagos_con_saldo"] == 1 and dia["pagos_por_aprobar"] == 0
    assert dia["semanas_por_cerrar"] == 0


def test_mi_dia_faenas_solo_vigentes_y_proximas(actor):
    identificador,_ = acuerdo_prueba(actor,fecha_fin=date(2026,10,16))
    operacion.guardar_jornada(lote_prueba(id_faena=identificador),actor)
    with conectar_bd() as c:
        c.execute("""INSERT INTO faenas(id_cliente,nombre,predio,cultivo,fecha_inicio,precio_kg,estado)
            VALUES (1,'Próxima','Predio','Palta','2026-10-20',100,'Planificada'),
            (1,'Finalizada','Predio','Palta','2026-10-01',100,'Finalizada')""")
    dia = resumen.mi_dia(date(2026,10,15))
    assert len(dia["faenas"]) == 1 and dia["faenas"][0]["registros_hoy"] == 2
    assert [f["nombre"] for f in dia["proximas"]] == ["Próxima"]
    assert resumen.mi_dia(date(2026,10,17))["faenas"] == []


def test_repetir_usa_ultima_produccion_no_jornada_vacia_y_no_copia_kilos(bd):
    with conectar_bd() as c:
        c.execute("INSERT INTO jornadas(fecha) VALUES ('2026-10-15')")
    plantilla = operacion.plantilla_jornada(date(2026,10,16))
    assert plantilla["origen"] == date(2026,10,14)
    grupo = plantilla["grupos"][0]
    assert grupo["trabajadores"] == [{"id":1,"nombre":"Persona Prueba"}]
    assert "cantidad_kg" not in grupo and "horas_trabajadas" not in grupo
    with conectar_bd() as c:
        assert c.execute("SELECT COUNT(*) FROM produccion").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM jornadas WHERE fecha='2026-10-16'").fetchone()[0] == 0


def test_repetir_excluye_inactivos_y_ya_registrados(actor):
    operacion.guardar_jornada(lote_prueba(),actor)
    operacion.guardar_jornada(lote_prueba(id_jornada=None,fecha=date(2026,10,16),filas=[dict(id_trabajador=1,cantidad_kg=10,horas_trabajadas=1)]),actor)
    with conectar_bd() as c: c.execute("UPDATE trabajadores SET estado='Inactivo' WHERE id_trabajador=2")
    grupo = operacion.plantilla_jornada(date(2026,10,16))["grupos"][0]
    assert grupo["trabajadores"] == []
    assert grupo["inactivos"] == 1 and grupo["ya_registrados"] == 1


def test_repetir_avisa_faena_fuera_de_fecha_y_semana_destino_cerrada(actor):
    identificador,_ = acuerdo_prueba(actor,fecha_fin=date(2026,10,15))
    operacion.guardar_jornada(lote_prueba(id_faena=identificador),actor)
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,15)))
    plantilla = operacion.plantilla_jornada(date(2026,10,16))
    assert plantilla["cerrada"]
    assert not plantilla["grupos"][0]["faena_valida"]
    assert not operacion.plantilla_jornada(date(2026,10,21))["cerrada"]
    assert operacion.plantilla_jornada(date(2026,10,1))["grupos"] == []
    with pytest.raises(HTTPException) as error:
        operacion.plantilla_jornada(date(2026,10,15),date(2026,10,15))
    assert error.value.status_code == 422


def test_mi_dia_y_plantilla_requieren_sesion_y_permiten_consulta(actor):
    cliente = TestClient(main.app)
    assert cliente.get("/mi-dia").status_code == 401
    assert cliente.get("/produccion/plantilla?destino=2026-10-16").status_code == 401
    with conectar_bd() as c:
        c.execute("UPDATE usuarios SET rol='consulta' WHERE usuario='admin'")
    assert cliente.post("/auth/login",json={"usuario":"admin","password":"Clave-de-prueba-1234"}).status_code == 200
    assert cliente.get("/mi-dia?fecha=2026-10-14").status_code == 200
    assert cliente.get("/produccion/plantilla?destino=2026-10-16").status_code == 200


@pytest.fixture(scope="module")
def base_temporal():
    if os.getenv("DATABASE_URL"):
        pytest.fail("Quita DATABASE_URL antes de ejecutar las pruebas locales de PostgreSQL.")
    nombre = "agricolix_test_" + uuid4().hex[:12]
    original = os.environ.get("DB_NAME")
    parametros = dict(host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"), dbname="postgres",
                      user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"))
    with psycopg.connect(**parametros, autocommit=True) as administrador:
        administrador.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nombre)))
    os.environ["DB_NAME"] = nombre
    try:
        with conectar_bd() as conexion:
            conexion.execute((Path(__file__).parents[1] / "esquema.sql").read_text(encoding="utf-8-sig"))
        seguridad.inicializar_seguridad()
        yield nombre
    finally:
        if original is None:
            os.environ.pop("DB_NAME", None)
        else:
            os.environ["DB_NAME"] = original
        assert nombre.startswith("agricolix_test_")
        with psycopg.connect(**parametros, autocommit=True) as administrador:
            administrador.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(nombre)))


@pytest.fixture
def bd(base_temporal):
    assert os.environ["DB_NAME"] == base_temporal
    with conectar_bd() as conexion:
        conexion.execute("TRUNCATE usuarios,trabajadores,jornadas,sectores,labores,tarifas,pagos,intentos_login,auditoria,lotes_cosecha,clientes RESTART IDENTITY CASCADE")
        conexion.execute("INSERT INTO trabajadores(nombre,apellido) VALUES ('Persona','Prueba')")
        conexion.execute("INSERT INTO jornadas(fecha) VALUES ('2026-10-14')")
        conexion.execute("INSERT INTO sectores(nombre) VALUES ('Sector de prueba')")
        conexion.execute("INSERT INTO labores(nombre) VALUES ('Cosecha')")
        conexion.execute("INSERT INTO produccion(id_trabajador,id_jornada,id_sector,id_labor,cantidad_kg,horas_trabajadas) VALUES (1,1,1,1,100,8)")
        conexion.execute("INSERT INTO tarifas(semana_inicio,precio_kg) VALUES ('2026-10-12',12.50)")
    yield


def test_cierre_y_bloqueo_de_cosechas_reales(bd):
    cerrado = pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    assert cerrado["total_pagar"] == 1250
    assert cerrado["cerrada"]
    with pytest.raises(HTTPException) as error:
        main.registrar_produccion(main.ProduccionCrear(id_trabajador=1,id_jornada=1,id_sector=1,id_labor=1,cantidad_kg=20,horas_trabajadas=2))
    assert error.value.status_code == 409
    with conectar_bd() as conexion:
        assert conexion.execute("SELECT SUM(cantidad_kg) FROM produccion").fetchone()[0] == 100


def test_dos_cierres_simultaneos_solo_uno_se_confirma(bd):
    barrera = Barrier(2)
    def cerrar():
        barrera.wait(timeout=10)
        try:
            pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
            return 201
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(lambda _: cerrar(), range(2)))
    assert sorted(resultados) == [201,409]
    with conectar_bd() as conexion:
        assert conexion.execute("SELECT COUNT(*) FROM pagos").fetchone()[0] == 1


def test_cosecha_y_cierre_simultaneos_no_desajustan_pagos(bd):
    barrera = Barrier(2)
    def registrar():
        barrera.wait(timeout=10)
        try:
            main.registrar_produccion(main.ProduccionCrear(id_trabajador=1,id_jornada=1,id_sector=1,id_labor=1,cantidad_kg=20,horas_trabajadas=2))
            return 201
        except HTTPException as error:
            return error.status_code
    def cerrar():
        barrera.wait(timeout=10)
        return pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    with ThreadPoolExecutor(max_workers=2) as executor:
        a = executor.submit(registrar)
        b = executor.submit(cerrar)
        assert a.result(timeout=15) in {201,409}
        assert b.result(timeout=15)["cerrada"]
    with conectar_bd() as conexion:
        produccion = conexion.execute("SELECT SUM(cantidad_kg) FROM produccion").fetchone()[0]
        kilos = conexion.execute("SELECT SUM(kilos) FROM pagos").fetchone()[0]
        assert produccion == kilos


def test_importacion_repetida_no_duplica_produccion(bd):
    with conectar_bd() as conexion:
        conexion.execute("INSERT INTO jornadas(fecha) VALUES ('2026-10-15')")
    lote = main.LoteImportacion(registros=[main.CosechaImportada(trabajador="Persona Prueba",fecha=date(2026,10,15),kilos=40,
        sectores=[main.SectorImportado(id_sector=1,kilos=40,horas=4)])])
    assert main.guardar_importacion(lote)["filas_produccion"] == 1
    with pytest.raises(HTTPException) as error:
        main.guardar_importacion(lote)
    assert error.value.status_code == 409
    with conectar_bd() as conexion:
        assert conexion.execute("SELECT SUM(cantidad_kg) FROM produccion").fetchone()[0] == 140


def test_lote_con_semana_cerrada_se_rechaza_completo(bd):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    with conectar_bd() as conexion:
        conexion.execute("INSERT INTO jornadas(fecha) VALUES ('2026-10-21')")
    lote = main.LoteImportacion(registros=[main.CosechaImportada(trabajador="Persona Prueba",fecha=d,kilos=40,
        sectores=[main.SectorImportado(id_sector=1,kilos=40,horas=4)]) for d in [date(2026,10,14),date(2026,10,21)]])
    with pytest.raises(HTTPException):
        main.guardar_importacion(lote)
    with conectar_bd() as conexion:
        assert conexion.execute("SELECT COUNT(*) FROM produccion").fetchone()[0] == 1


def test_login_permisos_auditoria_y_logout_reales(bd):
    with conectar_bd() as conexion:
        conexion.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES ('prueba','Cuenta de prueba',%s,'consulta')", (seguridad.hash_password("Password-de-prueba-123"),))
    cliente = TestClient(main.app)
    assert cliente.get("/resumen").status_code == 401
    acceso = cliente.post("/auth/login",json={"usuario":"prueba","password":"Password-de-prueba-123"})
    assert acceso.status_code == 200
    assert "HttpOnly" in acceso.headers["set-cookie"]
    assert cliente.get("/resumen").status_code == 200
    assert cliente.post("/produccion",json={}).status_code == 403
    assert cliente.get("/usuarios").status_code == 403
    assert cliente.post("/auth/logout").status_code == 200
    assert cliente.get("/resumen").status_code == 401
    with conectar_bd() as conexion:
        assert conexion.execute("SELECT COUNT(*) FROM sesiones").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0] >= 2


def test_login_limita_intentos_fallidos(bd):
    cliente = TestClient(main.app)
    for _ in range(5):
        assert cliente.post("/auth/login",json={"usuario":"inexistente","password":"incorrecta"}).status_code == 401
    assert cliente.post("/auth/login",json={"usuario":"inexistente","password":"incorrecta"}).status_code == 429


def test_ia_operativa_incluye_nueva_produccion(bd):
    from ia.modelo_productividad import generar_analisis
    antes = generar_analisis("operacion")
    main.registrar_produccion(main.ProduccionCrear(id_trabajador=1,id_jornada=1,id_sector=1,id_labor=1,cantidad_kg=20,horas_trabajadas=2))
    despues = generar_analisis("operacion")
    assert antes["trabajadores"][0]["total_kg"] == 100
    assert despues["trabajadores"][0]["total_kg"] == 120
    assert despues["fuente"] == "operacion"
    assert despues["trabajadores"][0]["tendencia"] == "Datos insuficientes"


def test_migraciones_son_idempotentes(bd):
    seguridad.inicializar_seguridad()
    seguridad.inicializar_seguridad()
    with conectar_bd() as conexion:
        assert conexion.execute("SELECT COUNT(*) FROM migraciones").fetchone()[0] == len(list((Path(__file__).parents[1]/"migrations").glob("*.sql")))


def test_sesion_vencida_no_permite_consultar(bd):
    with conectar_bd() as conexion:
        conexion.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES ('prueba','Cuenta de prueba',%s,'consulta')", (seguridad.hash_password("Password-de-prueba-123"),))
    cliente = TestClient(main.app)
    assert cliente.post("/auth/login",json={"usuario":"prueba","password":"Password-de-prueba-123"}).status_code == 200
    with conectar_bd() as conexion:
        conexion.execute("UPDATE sesiones SET vence_en=NOW()-INTERVAL '1 second'")
    assert cliente.get("/resumen").status_code == 401


def test_cambio_de_perfil_invalida_sesion_y_protege_administrador(bd):
    with conectar_bd() as conexion:
        conexion.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES ('admin','Admin de prueba',%s,'administrador')", (seguridad.hash_password("Password-de-prueba-123"),))
    admin = TestClient(main.app)
    admin.post("/auth/login",json={"usuario":"admin","password":"Password-de-prueba-123"})
    creado = admin.post("/usuarios",json={"usuario":"encargado","nombre":"Encargado de prueba","password":"Password-de-prueba-123","rol":"encargado"})
    assert creado.status_code == 201
    persona = TestClient(main.app)
    assert persona.post("/auth/login",json={"usuario":"encargado","password":"Password-de-prueba-123"}).status_code == 200
    assert admin.patch(f'/usuarios/{creado.json()["id"]}',json={"rol":"consulta","activo":True}).status_code == 200
    assert persona.get("/resumen").status_code == 401
    assert admin.patch("/usuarios/1",json={"rol":"consulta","activo":False}).status_code == 409


def test_cambio_de_tarifa_y_cierre_simultaneos_conservan_precio(bd):
    barrera = Barrier(2)
    def tarifa():
        barrera.wait(timeout=10)
        try:
            pagos.guardar_tarifa(date(2026,10,14),pagos.TarifaGuardar(precio_kg=Decimal("20")))
            return 200
        except HTTPException as error:
            return error.status_code
    def cerrar():
        barrera.wait(timeout=10)
        return pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    with ThreadPoolExecutor(max_workers=2) as executor:
        a = executor.submit(tarifa)
        b = executor.submit(cerrar)
        assert a.result(timeout=15) in {200,409}
        b.result(timeout=15)
    with conectar_bd() as conexion:
        precio_pago = conexion.execute("SELECT precio_kg FROM pagos").fetchone()[0]
        precio_tarifa = conexion.execute("SELECT precio_kg FROM tarifas").fetchone()[0]
        assert precio_pago == precio_tarifa


@pytest.fixture
def actor(bd):
    with conectar_bd() as c:
        id_usuario=c.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES ('admin','Prueba',%s,'administrador') RETURNING id_usuario",(seguridad.hash_password("Clave-de-prueba-1234"),)).fetchone()[0]
        c.execute("INSERT INTO jornadas(fecha) VALUES ('2026-10-15')")
        c.execute("INSERT INTO trabajadores(nombre,apellido) VALUES ('Segunda','Persona')")
    return SimpleNamespace(state=SimpleNamespace(usuario={"id":id_usuario,"rol":"administrador"}))


def lote_prueba(**cambios):
    datos=dict(clave=uuid4(),id_jornada=2,id_sector=1,id_labor=1,filas=[dict(id_trabajador=1,cantidad_kg=40,horas_trabajadas=4),dict(id_trabajador=2,cantidad_kg=50,horas_trabajadas=5)])
    datos.update(cambios)
    return operacion.LoteJornada(**datos)


def acuerdo_prueba(actor, **cambios):
    cliente = faenas.crear_cliente(faenas.Cliente(nombre="Cliente de prueba"), actor)["id"]
    datos = dict(id_cliente=cliente,nombre="Cosecha de prueba",predio="Predio de prueba",cultivo="Palta",
                 fecha_inicio=date(2026,10,1),precio_kg=Decimal("100"),estado="Activa")
    datos.update(cambios)
    identificador = faenas.crear_faena(faenas.Faena(**datos), actor)["id"]
    return identificador, datos


def test_faena_separa_cobro_cliente_y_pago_trabajador(actor):
    identificador, _ = acuerdo_prueba(actor)
    lote = lote_prueba(id_faena=identificador)
    resultado = operacion.guardar_jornada(lote, actor)
    assert operacion.guardar_jornada(lote, actor) == resultado
    resumen = faenas.listar_faenas()[0]
    assert resumen["kilos"] == 90 and resumen["horas"] == 9
    assert resumen["cobro_estimado"] == 9000
    assert resumen["pago_estimado"] == 1125
    assert resumen["trabajadores"] == 2 and resumen["jornadas"] == 1
    assert len(faenas.produccion_faena(identificador)) == 2
    assert operacion.registros()[0]["faena"] == "Cosecha de prueba"
    with conectar_bd() as c:
        assert c.execute("SELECT id_faena FROM produccion WHERE id_produccion=1").fetchone()[0] is None


def test_flujo_http_cliente_faena_cosecha_y_resumen(actor):
    cliente = TestClient(main.app)
    assert cliente.post("/auth/login",json={"usuario":"admin","password":"Clave-de-prueba-1234"}).status_code == 200
    respuesta = cliente.post("/clientes",json={"nombre":"Empresa HTTP"})
    assert respuesta.status_code == 201
    acuerdo = cliente.post("/faenas",json={"id_cliente":respuesta.json()["id"],"nombre":"Servicio HTTP",
        "predio":"Predio HTTP","fecha_inicio":"2026-10-01","precio_kg":"100.50","estado":"Activa"})
    assert acuerdo.status_code == 201
    lote = lote_prueba(id_faena=acuerdo.json()["id"])
    assert cliente.post("/produccion/jornada",json=lote.model_dump(mode="json")).status_code == 201
    resumen = cliente.get("/faenas")
    assert resumen.status_code == 200
    assert resumen.json()[0]["cobro_estimado"] == 9045
    assert resumen.json()[0]["pago_estimado"] == 1125
    assert cliente.get(f"/faenas/{acuerdo.json()['id']}/produccion").status_code == 200


def test_gestion_ia_respeta_periodos_y_separa_cobro_de_abonos(actor):
    identificador, _ = acuerdo_prueba(actor)
    operacion.guardar_jornada(lote_prueba(id_faena=identificador),actor)
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,15)))
    seguimiento.aprobar(1,actor)
    seguimiento.abonar(1,seguimiento.Abono(clave=uuid4(),monto=500,fecha=date(2026,10,20),comprobante="GESTION-PRUEBA"),actor)
    gestion=consultar_gestion("2026-10-15","2026-10-15")
    assert gestion["resumen"]["kilos_incluidos_ajustes"] == 90
    assert gestion["resumen"]["cobro_estimado_faenas_clp"] == 9000
    assert gestion["pagos_trabajadores"]["total_bruto_clp"] == 2375
    assert gestion["pagos_trabajadores"]["abonado_clp"] == 500
    assert gestion["pagos_trabajadores"]["saldo_clp"] == 1875
    assert gestion["entorno"]["demostracion"] is False


def test_entorno_demostracion_se_identifica_sin_exponer_conexion(bd):
    try:
        with conectar_bd() as c:
            c.execute("CREATE TABLE entorno_demostracion(id INT PRIMARY KEY,desde DATE,hasta DATE)")
            c.execute("INSERT INTO entorno_demostracion VALUES (1,'2024-11-06','2026-11-05')")
        info=entorno.describir_entorno()
        assert info["demostracion"] is True and info["desde"] == "2024-11-06"
        assert "DB_NAME" not in info and "password" not in info
    finally:
        with conectar_bd() as c: c.execute("DROP TABLE IF EXISTS entorno_demostracion")


@pytest.mark.parametrize("estado", ["Planificada", "Finalizada"])
def test_faena_no_activa_rechaza_lote_sin_crear_jornada(actor, estado):
    identificador, _ = acuerdo_prueba(actor, estado=estado)
    with pytest.raises(HTTPException) as error:
        operacion.guardar_jornada(lote_prueba(id_jornada=None, fecha=date(2026,10,17), id_faena=identificador), actor)
    assert error.value.status_code == 409
    with conectar_bd() as c:
        assert c.execute("SELECT 1 FROM jornadas WHERE fecha='2026-10-17'").fetchone() is None
        assert c.execute("SELECT COUNT(*) FROM produccion WHERE id_faena=%s", (identificador,)).fetchone()[0] == 0


@pytest.mark.parametrize("fecha", [date(2026,9,30), date(2026,10,16)])
def test_faena_rechaza_fecha_fuera_del_acuerdo(actor, fecha):
    identificador, _ = acuerdo_prueba(actor, fecha_fin=date(2026,10,15))
    with pytest.raises(HTTPException) as error:
        operacion.guardar_jornada(lote_prueba(id_jornada=None, fecha=fecha, id_faena=identificador), actor)
    assert error.value.status_code == 422


def test_precio_y_cliente_se_conservan_despues_de_registrar(actor):
    identificador, datos = acuerdo_prueba(actor)
    operacion.guardar_jornada(lote_prueba(id_faena=identificador), actor)
    with pytest.raises(HTTPException) as error:
        faenas.editar_faena(identificador, faenas.FaenaEditar(**{**datos,"precio_kg":200}, version=1), actor)
    assert error.value.status_code == 409
    assert faenas.listar_faenas()[0]["precio_kg"] == 100
    faenas.editar_faena(identificador, faenas.FaenaEditar(**{**datos,"estado":"Finalizada","fecha_fin":date(2026,10,15)}, version=1), actor)
    with pytest.raises(HTTPException):
        faenas.editar_faena(identificador, faenas.FaenaEditar(**datos, version=1), actor)
    # Reintentar un envío ya confirmado sigue sin duplicar producción aunque haya finalizado.
    assert faenas.listar_faenas()[0]["registros"] == 2


def test_no_se_desactiva_cliente_con_faenas_pendientes(actor):
    identificador, datos = acuerdo_prueba(actor)
    with pytest.raises(HTTPException) as error:
        faenas.editar_cliente(datos["id_cliente"], faenas.ClienteEditar(nombre="Cliente de prueba",activo=False,version=1),actor)
    assert error.value.status_code == 409
    faenas.editar_faena(identificador,faenas.FaenaEditar(**{**datos,"estado":"Finalizada"},version=1),actor)
    faenas.editar_cliente(datos["id_cliente"],faenas.ClienteEditar(nombre="Cliente de prueba",activo=False,version=1),actor)
    with pytest.raises(HTTPException):
        faenas.crear_faena(faenas.Faena(**{**datos,"nombre":"Otra faena"}),actor)
    with pytest.raises(HTTPException):
        faenas.editar_faena(identificador,faenas.FaenaEditar(**datos,version=2),actor)


def test_pago_estimado_no_inventa_cero_si_falta_tarifa(actor):
    identificador, _ = acuerdo_prueba(actor)
    operacion.guardar_jornada(lote_prueba(id_faena=identificador),actor)
    with conectar_bd() as c:
        c.execute("DELETE FROM tarifas")
    resumen = faenas.listar_faenas()[0]
    assert resumen["cobro_estimado"] == 9000
    assert resumen["sin_tarifa"] == 2 and resumen["pago_estimado"] is None


def test_resumen_faena_incluye_ajustes_y_tarifa_congelada(actor):
    identificador, _ = acuerdo_prueba(actor)
    registro = operacion.guardar_jornada(lote_prueba(id_faena=identificador),actor)["ids"][0]
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,15)))
    operacion.ajustar(registro,operacion.Ajuste(clave=uuid4(),diferencia_kg=2,motivo="Revisión de pesaje"),actor)
    with conectar_bd() as c:
        c.execute("UPDATE tarifas SET precio_kg=999")
    resumen = faenas.listar_faenas()[0]
    assert resumen["kilos"] == 92 and resumen["cobro_estimado"] == 9200
    assert resumen["pago_estimado"] == 1150
    assert faenas.produccion_faena(identificador)[1]["ajuste_kg"] == 2


def test_cliente_y_faena_no_se_duplican_y_auditan(actor):
    identificador, datos = acuerdo_prueba(actor)
    with pytest.raises(HTTPException) as error:
        faenas.crear_cliente(faenas.Cliente(nombre=" cliente DE PRUEBA "),actor)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException):
        faenas.crear_faena(faenas.Faena(**datos),actor)
    with conectar_bd() as c:
        assert c.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM faenas").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM auditoria WHERE accion='Creación de faena'").fetchone()[0] == 1


def test_cambio_precio_y_registro_simultaneo_respetan_el_acuerdo(actor):
    identificador, datos = acuerdo_prueba(actor)
    barrera = Barrier(2)
    def cambiar():
        barrera.wait(timeout=10)
        try:
            faenas.editar_faena(identificador,faenas.FaenaEditar(**{**datos,"precio_kg":200},version=1),actor)
            return 200
        except HTTPException as e:
            return e.status_code
    def guardar():
        barrera.wait(timeout=10)
        return operacion.guardar_jornada(lote_prueba(id_faena=identificador),actor)
    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        cambio = ejecutor.submit(cambiar)
        registro = ejecutor.submit(guardar)
        assert cambio.result(timeout=15) in {200,409}
        assert registro.result(timeout=15)["registros"] == 2
    resumen = faenas.listar_faenas()[0]
    assert resumen["cobro_estimado"] == 90 * resumen["precio_kg"]


def test_jornada_es_idempotente_y_atomica(actor):
    lote=lote_prueba()
    a=operacion.guardar_jornada(lote,actor)
    b=operacion.guardar_jornada(lote,actor)
    assert a==b
    with conectar_bd() as c:
        assert c.execute("SELECT COUNT(*) FROM produccion WHERE id_jornada=2").fetchone()[0]==2


def test_lote_invalido_no_deja_filas_parciales(actor):
    with pytest.raises(HTTPException):
        operacion.guardar_jornada(lote_prueba(id_sector=999),actor)
    with conectar_bd() as c:
        assert c.execute("SELECT COUNT(*) FROM produccion WHERE id_jornada=2").fetchone()[0]==0
        assert c.execute("SELECT COUNT(*) FROM lotes_cosecha").fetchone()[0]==0


def test_lote_repetido_con_otra_clave_tambien_se_rechaza(actor):
    operacion.guardar_jornada(lote_prueba(),actor)
    with pytest.raises(HTTPException) as error: operacion.guardar_jornada(lote_prueba(),actor)
    assert error.value.status_code==409


def test_correccion_guarda_historia_y_rechaza_version_antigua(actor):
    datos=operacion.Correccion(cantidad_kg=120,horas_trabajadas=9,version=1,motivo="Revisión de planilla")
    operacion.corregir(1,datos,actor)
    historia=operacion.historial(1)["correcciones"]
    assert historia[0]["antes"]["cantidad_kg"]=="100.00"
    assert Decimal(historia[0]["despues"]["cantidad_kg"])==120
    with pytest.raises(HTTPException) as error: operacion.corregir(1,datos,actor)
    assert error.value.status_code==409


def test_correccion_no_modifica_semana_cerrada(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    with pytest.raises(HTTPException) as error:
        operacion.corregir(1,operacion.Correccion(cantidad_kg=120,horas_trabajadas=8,version=1,motivo="Corrección tardía"),actor)
    assert error.value.status_code==409


def test_ajuste_conserva_original_y_requiere_reaprobar(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    seguimiento.aprobar(1,actor)
    datos=operacion.Ajuste(clave=uuid4(),diferencia_kg=2,diferencia_horas=0,motivo="Diferencia de pesaje")
    assert operacion.ajustar(1,datos,actor)["diferencia_monto"]==25
    operacion.ajustar(1,datos,actor)
    fila=seguimiento.listar()[0]
    assert fila["total"]==1275 and fila["saldo"]==1275 and not fila["aprobado"]
    with conectar_bd() as c:
        assert c.execute("SELECT cantidad_kg FROM produccion WHERE id_produccion=1").fetchone()[0]==100
        assert c.execute("SELECT total FROM pagos WHERE id_pago=1").fetchone()[0]==1250
        assert c.execute("SELECT COUNT(*) FROM ajustes_cosecha").fetchone()[0]==1


def test_abonos_exigen_aprobacion_son_idempotentes_y_no_superan_saldo(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    datos=seguimiento.Abono(clave=uuid4(),monto=500,fecha=date(2026,10,15),comprobante="REF-123")
    with pytest.raises(HTTPException): seguimiento.abonar(1,datos,actor)
    seguimiento.aprobar(1,actor)
    seguimiento.abonar(1,datos,actor); seguimiento.abonar(1,datos,actor)
    assert seguimiento.listar()[0]["saldo"]==750
    assert len(seguimiento.abonos(1))==1
    with pytest.raises(HTTPException): seguimiento.abonar(1,seguimiento.Abono(clave=uuid4(),monto=751,fecha=date(2026,10,15),comprobante="REF-456"),actor)
    seguimiento.abonar(1,seguimiento.Abono(clave=uuid4(),monto=750,fecha=date(2026,10,15),comprobante="REF-789"),actor)
    assert seguimiento.listar()[0]["estado"]=="Pagado"


def test_ajuste_no_puede_reducir_total_bajo_lo_abonado(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14))); seguimiento.aprobar(1,actor)
    seguimiento.abonar(1,seguimiento.Abono(clave=uuid4(),monto=500,fecha=date(2026,10,15),comprobante="REF-123"),actor)
    with pytest.raises(HTTPException) as error:
        operacion.ajustar(1,operacion.Ajuste(clave=uuid4(),diferencia_kg=-80,diferencia_horas=0,motivo="Revisión de pesaje"),actor)
    assert error.value.status_code==409


def test_abonos_simultaneos_no_sobrepagan(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14))); seguimiento.aprobar(1,actor)
    barrera=Barrier(2)
    def abonar():
        barrera.wait(timeout=10)
        try:
            seguimiento.abonar(1,seguimiento.Abono(clave=uuid4(),monto=800,fecha=date(2026,10,15),comprobante="REF-CONCURRENTE"),actor)
            return 201
        except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as e:
        assert sorted(e.map(lambda _:abonar(),range(2)))==[201,409]
    assert seguimiento.listar()[0]["saldo"]==450


def test_horas_acumuladas_se_validan_por_jornada(actor):
    with conectar_bd() as c: c.execute("INSERT INTO sectores(nombre) VALUES ('Otro sector')")
    lote=lote_prueba(id_jornada=1,id_sector=2,filas=[dict(id_trabajador=1,cantidad_kg=30,horas_trabajadas=20)])
    with pytest.raises(HTTPException) as error: operacion.guardar_jornada(lote,actor)
    assert error.value.status_code==422


def test_jornada_nueva_se_crea_con_el_lote(actor):
    lote=lote_prueba(id_jornada=None,fecha=date(2026,10,16))
    operacion.guardar_jornada(lote,actor)
    with conectar_bd() as c:
        assert c.execute("SELECT COUNT(*) FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha='2026-10-16'").fetchone()[0]==2


def test_fecha_nueva_no_se_crea_si_falla_el_lote(actor):
    lote=lote_prueba(id_jornada=None,fecha=date(2026,10,16),id_sector=999)
    with pytest.raises(HTTPException): operacion.guardar_jornada(lote,actor)
    with conectar_bd() as c:
        assert c.execute("SELECT COUNT(*) FROM jornadas WHERE fecha='2026-10-16'").fetchone()[0]==0


def test_ajustes_pequenos_redondean_el_total_no_cada_diferencia(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14)))
    for _ in range(2):
        operacion.ajustar(1,operacion.Ajuste(clave=uuid4(),diferencia_kg=Decimal("0.04"),motivo="Ajuste fino de pesaje"),actor)
    assert seguimiento.listar()[0]["total"]==1251


def test_referencia_repetida_con_clave_distinta_no_duplica_abonos(actor):
    pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026,10,14))); seguimiento.aprobar(1,actor)
    for i in range(2):
        datos=seguimiento.Abono(clave=uuid4(),monto=100,fecha=date(2026,10,15),comprobante="MISMA-REFERENCIA")
        if i==0: seguimiento.abonar(1,datos,actor)
        else:
            with pytest.raises(HTTPException) as error: seguimiento.abonar(1,datos,actor)
            assert error.value.status_code==409
    assert seguimiento.listar()[0]["abonado"]==100
