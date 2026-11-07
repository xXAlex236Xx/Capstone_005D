"""Genera dos años sintéticos en una base NUEVA y alterna sin borrar la original."""
import argparse
import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import math
import os
from pathlib import Path
import random
import secrets
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from dotenv import set_key

from database import BASE_DIR, conectar_bd
from pagos import calcular_total, lunes_de
from seguridad import hash_password, inicializar_seguridad

LOCAL = BASE_DIR.parents[2] / ".local"
ESTADO = LOCAL / "demostracion.json"
ACCESOS = LOCAL / "accesos-demostracion.txt"
TABLAS_OPERACION = ("trabajadores", "jornadas", "produccion", "clientes", "faenas", "pagos", "tarifas", "abonos_pago")


def parametros():
    return {"host": os.getenv("DB_HOST"), "port": os.getenv("DB_PORT"),
            "user": os.getenv("DB_USER"), "password": os.getenv("DB_PASSWORD"), "connect_timeout": 5}


def contar_operacion(conexion):
    return {t: conexion.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(t))).fetchone()[0]
            for t in TABLAS_OPERACION}


def redondear(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def instante(fecha, hora=18):
    return datetime.combine(fecha, time(hora), ZoneInfo("America/Santiago"))


def leer_estado():
    if not ESTADO.exists():
        raise RuntimeError("No hay demostración preparada. Ejecuta demo.py --crear primero.")
    estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    if not estado["demo"].startswith("agricolix_demo_") or estado["original"] == estado["demo"]:
        raise RuntimeError("La configuración de demostración no es válida")
    return estado


def verificar_marca(estado):
    with psycopg.connect(**parametros(), dbname=estado["demo"]) as conexion:
        marca = conexion.execute("SELECT identificador FROM entorno_demostracion WHERE id=1").fetchone()
        if not marca or str(marca[0]) != estado["identificador"]:
            raise RuntimeError("La base no coincide con la demostración registrada. No se cambió el entorno.")


def cambiar_entorno(demostracion):
    estado = leer_estado()
    if demostracion:
        verificar_marca(estado)
    destino = estado["demo"] if demostracion else estado["original"]
    if not demostracion and destino.startswith(("agricolix_demo_", "agricolix_test_")):
        raise RuntimeError("La referencia original no apunta a una base operativa")
    # Cambia únicamente DB_NAME; las claves y demás configuración permanecen intactas.
    with psycopg.connect(**parametros(), dbname=destino) as conexion:
        conexion.execute("SELECT 1")
    set_key(str(BASE_DIR / ".env"), "DB_NAME", destino)
    print("Entorno de demostración seleccionado. Reinicia Agricolix." if demostracion
          else "Datos originales seleccionados. Reinicia Agricolix. La demostración se conserva por separado.")


def generar(hasta):
    if ESTADO.exists():
        raise RuntimeError("Ya hay una demostración registrada. Puedes activarla o volver a los datos originales sin regenerarla.")
    original = os.environ["DB_NAME"]
    if original.startswith(("agricolix_demo_", "agricolix_test_")):
        raise RuntimeError("La generación debe comenzar desde la base operativa original")
    desde = date(hasta.year - 2, hasta.month, hasta.day) + timedelta(days=1)
    nombre = "agricolix_demo_" + hasta.strftime("%Y%m%d") + "_" + uuid4().hex[:6]
    identificador = uuid4()
    rng = random.Random(20261105)
    LOCAL.mkdir(parents=True, exist_ok=True)
    with conectar_bd() as origen:
        preservado = contar_operacion(origen)
        # Conserva el acceso del administrador actual y su sesión en esta copia local.
        administradores = origen.execute("SELECT id_usuario,usuario,nombre,password_hash,rol,activo,creado_en FROM usuarios WHERE rol='administrador' AND activo").fetchall()
        sesiones = origen.execute("SELECT s.token_hash,s.id_usuario,s.vence_en FROM sesiones s JOIN usuarios u USING(id_usuario) WHERE u.rol='administrador' AND u.activo AND s.vence_en>NOW()").fetchall()
    with psycopg.connect(**parametros(), dbname="postgres", autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nombre)))
    os.environ["DB_NAME"] = nombre
    try:
        with conectar_bd() as conexion:
            if conexion.info.dbname != nombre or not nombre.startswith("agricolix_demo_"):
                raise RuntimeError("La conexión no apunta a la base nueva de demostración")
            conexion.execute((BASE_DIR / "esquema.sql").read_text(encoding="utf-8-sig"))
        inicializar_seguridad()
        with conectar_bd() as conexion:
            with conexion.cursor() as c:
                c.execute("""CREATE TABLE entorno_demostracion (
                    id INTEGER PRIMARY KEY CHECK(id=1),identificador UUID NOT NULL,
                    desde DATE NOT NULL,hasta DATE NOT NULL,creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
                c.execute("INSERT INTO entorno_demostracion(id,identificador,desde,hasta) VALUES (1,%s,%s,%s)", (identificador,desde,hasta))
                if administradores:
                    c.executemany("""INSERT INTO usuarios(id_usuario,usuario,nombre,password_hash,rol,activo,creado_en)
                        OVERRIDING SYSTEM VALUE VALUES (%s,%s,%s,%s,%s,%s,%s)""", administradores)
                    c.execute("SELECT setval(pg_get_serial_sequence('usuarios','id_usuario'),(SELECT MAX(id_usuario) FROM usuarios))")
                if sesiones:
                    c.executemany("INSERT INTO sesiones(token_hash,id_usuario,vence_en) VALUES (%s,%s,%s)", sesiones)
                accesos = []
                cuentas = [("demo.admin","Administración DEMO","administrador"),
                    ("demo.campo","Encargada de campo DEMO","encargado"),
                    ("demo.supervisor","Supervisión DEMO","encargado"),
                    ("demo.operaciones","Operaciones DEMO","encargado"),
                    ("demo.gerencia","Gerencia DEMO","consulta"),
                    ("demo.reportes","Reportes DEMO","consulta")]
                usuarios_demo = []
                for usuario, visible, rol in cuentas:
                    clave = secrets.token_urlsafe(15)
                    c.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol,creado_en) VALUES (%s,%s,%s,%s,%s) RETURNING id_usuario",
                              (usuario,visible,hash_password(clave),rol,instante(desde)))
                    usuarios_demo.append(c.fetchone()[0])
                    accesos.append(f"Usuario: {usuario}\nPerfil: {rol}\nContraseña: {clave}\n")
                administrador_demo, encargado = usuarios_demo[:2]
                nombres = ["Camila","Matías","Valentina","Diego","Javiera","Nicolás","Daniela","Tomás","Francisca",
                    "Sebastián","Antonia","Felipe","Catalina","Benjamín","Paula","Ignacio","Fernanda","Cristóbal",
                    "María José","Vicente","Carolina","Joaquín","Constanza","Gabriel","Sofía","Andrés","Josefa",
                    "Rodrigo","Isidora","Manuel","Claudia","Pablo","Elena","Héctor","Lorena","Luis"]
                apellidos = ["Rojas","Muñoz","Soto","Vargas","Silva","Castro","Torres","Vera","Morales","Fuentes","Araya","Navarro"]
                trabajadores = []
                for i, primer_nombre in enumerate(nombres):
                    c.execute("INSERT INTO trabajadores(nombre,apellido,estado) VALUES (%s,%s,%s) RETURNING id_trabajador",
                              (primer_nombre, apellidos[i % len(apellidos)] + " [DEMO]", "Activo" if i<30 else "Inactivo"))
                    trabajadores.append(c.fetchone()[0])
                for sector in ["Norte A","Norte B","Valle A","Valle B","Ladera A","Ladera B"]:
                    c.execute("INSERT INTO sectores(nombre,descripcion) VALUES (%s,'Sector ficticio de demostración')", (sector,))
                for labor in ["Cosecha de palta","Cosecha de limón","Cosecha de naranja"]:
                    c.execute("INSERT INTO labores(nombre,descripcion) VALUES (%s,'Actividad ficticia de demostración')", (labor,))
                empresas = ["Agrícola Horizonte","Campos del Valle","Huertos Santa Clara","Agrícola Los Aromos",
                    "Frutales Cordillera","Predios El Maitén","Agrícola La Quebrada","Huertos La Ribera"]
                clientes = []
                for i, empresa in enumerate(empresas):
                    c.execute("""INSERT INTO clientes(nombre,contacto,email,notas,activo,creado_en)
                        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_cliente""",
                        (empresa+" [DEMO]","Contacto ficticio "+str(i+1),f"cliente{i+1}@example.invalid",
                         "Empresa completamente ficticia. No contactar ni facturar.",i!=7,instante(desde)))
                    clientes.append(c.fetchone()[0])
                acuerdos = {}
                inicio_mes = desde.replace(day=1)
                indice_mes = 0
                while inicio_mes <= hasta:
                    fin_mes = inicio_mes.replace(day=calendar.monthrange(inicio_mes.year,inicio_mes.month)[1])
                    for grupo in range(3):
                        cliente_idx = (indice_mes*3+grupo) % (8 if indice_mes<12 else 7)
                        cultivo_idx = (indice_mes+grupo) % 3
                        precio = redondear(100+grupo*13+indice_mes*0.45)
                        estado = "Activa" if fin_mes>=hasta else "Finalizada"
                        c.execute("""INSERT INTO faenas(id_cliente,nombre,predio,cultivo,fecha_inicio,fecha_fin,precio_kg,estado,notas,creado_en)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_faena""",
                            (clientes[cliente_idx],f"Cosecha {inicio_mes:%Y-%m} · Equipo {grupo+1} [DEMO]",
                             f"Predio {empresas[cliente_idx]} [DEMO]",["Palta","Limón","Naranja"][cultivo_idx],
                             max(inicio_mes,desde),fin_mes,precio,estado,"Acuerdo sintético; no corresponde a un contrato real.",instante(max(inicio_mes,desde))))
                        acuerdos[(inicio_mes.year,inicio_mes.month,grupo)] = (c.fetchone()[0],cultivo_idx+1)
                    inicio_mes = (fin_mes+timedelta(days=1)); indice_mes += 1
                proximo_mes = (hasta.replace(day=calendar.monthrange(hasta.year,hasta.month)[1])+timedelta(days=1))
                for grupo in range(2):
                    c.execute("""INSERT INTO faenas(id_cliente,nombre,predio,cultivo,fecha_inicio,precio_kg,estado,notas)
                        VALUES (%s,%s,'Predio futuro [DEMO]','Palta',%s,125,'Planificada','Planificación ficticia para probar estados')""",
                        (clientes[grupo],f"Próxima temporada · Equipo {grupo+1} [DEMO]",proximo_mes))
                tarifas = {}
                semana = lunes_de(desde)
                while semana <= hasta:
                    indice = (semana-lunes_de(desde)).days//7
                    tarifa = redondear(40+indice*0.06+1.5*math.sin(indice/8))
                    tarifas[semana] = tarifa
                    c.execute("INSERT INTO tarifas(semana_inicio,precio_kg,creado_en) VALUES (%s,%s,%s)", (semana,tarifa,instante(semana)))
                    semana += timedelta(days=7)
                bases = [rng.uniform(78,138) for _ in trabajadores]
                registros = []
                eventos = []
                dia = desde
                jornadas = 0
                while dia <= hasta:
                    if dia.weekday()<5 and (dia.month,dia.day) not in {(1,1),(12,25)} and rng.random()>.035:
                        c.execute("INSERT INTO jornadas(fecha,observaciones) VALUES (%s,'Jornada sintética de demostración') RETURNING id_jornada", (dia,))
                        jornada = c.fetchone()[0]; jornadas += 1
                        clima = rng.uniform(.83,1.12)
                        temporada = 1+.1*math.sin((dia.timetuple().tm_yday-30)*math.pi/182.5)
                        progreso = 1+.08*(dia-desde).days/max((hasta-desde).days,1)
                        grupos_con_datos = set()
                        for i, trabajador in enumerate(trabajadores):
                            if i>=30 and dia > date(hasta.year,6,1): continue
                            if i>=24 and dia < desde+timedelta(days=120+(i-24)*8): continue
                            if rng.random()<.09: continue
                            grupo = i % 3
                            id_faena, id_labor = acuerdos[(dia.year,dia.month,grupo)]
                            horas = redondear(rng.uniform(6.5,8.5))
                            tendencia = 1
                            dias_finales = (hasta-dia).days
                            if dias_finales<60 and i in (1,7): tendencia = .72+.28*dias_finales/60
                            if dias_finales<60 and i in (0,4): tendencia = 1.16-.16*dias_finales/60
                            kilos = bases[i]*float(horas)*clima*temporada*progreso*tendencia*rng.uniform(.88,1.12)
                            if rng.random()<.008: kilos *= rng.choice([.38,1.75])
                            kilos = redondear(kilos)
                            sector = grupo*2+1+(dia.day%2)
                            registros.append((trabajador,jornada,sector,id_labor,kilos,horas,id_faena))
                            grupos_con_datos.add(grupo)
                        for grupo in grupos_con_datos:
                            eventos.append((encargado,"Registro de jornada","SIMULADO · Equipo "+str(grupo+1)+" · "+dia.isoformat(),instante(dia)))
                    dia += timedelta(days=1)
                c.executemany("""INSERT INTO produccion(id_trabajador,id_jornada,id_sector,id_labor,cantidad_kg,horas_trabajadas,id_faena)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)""", registros)
                # Las dos últimas semanas quedan abiertas para explorar el cierre en la interfaz.
                limite_cierre = lunes_de(hasta)-timedelta(days=14)
                grupos = c.execute("""SELECT date_trunc('week',j.fecha)::date,p.id_trabajador,SUM(p.cantidad_kg)
                    FROM produccion p JOIN jornadas j USING(id_jornada) GROUP BY 1,2 ORDER BY 1,2""").fetchall()
                pagos_creados = []
                for semana, trabajador, kilos in grupos:
                    if semana>limite_cierre: continue
                    precio = tarifas[semana]; total = calcular_total(kilos,precio)
                    c.execute("""INSERT INTO pagos(semana_inicio,id_trabajador,kilos,precio_kg,total,fecha_cierre)
                        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_pago""",(semana,trabajador,kilos,precio,total,instante(semana+timedelta(days=4),19)))
                    pagos_creados.append((c.fetchone()[0],semana,trabajador,kilos,precio,total))
                ajustes = {}
                for indice, (id_pago, semana, trabajador, kilos, precio, total) in enumerate(pagos_creados[-48:]):
                    if indice%3: continue
                    registro = c.execute("""SELECT p.id_produccion,p.cantidad_kg FROM produccion p JOIN jornadas j USING(id_jornada)
                        WHERE p.id_trabajador=%s AND j.fecha BETWEEN %s AND %s ORDER BY p.id_produccion LIMIT 1""",(trabajador,semana,semana+timedelta(days=6))).fetchone()
                    delta = Decimal(rng.choice([-5,8,12,15])); monto = calcular_total(kilos+delta,precio)-total
                    c.execute("""INSERT INTO ajustes_cosecha(clave,id_produccion,id_pago,diferencia_kg,diferencia_horas,monto,motivo,id_usuario,creado_en)
                        VALUES (%s,%s,%s,%s,0,%s,'SIMULADO · Revisión de pesaje',%s,%s)""",
                        (uuid4(),registro[0],id_pago,delta,monto,administrador_demo,instante(semana+timedelta(days=7))))
                    ajustes[id_pago] = monto
                abonos = []
                aprobaciones = []
                for indice, (id_pago, semana, trabajador, kilos, precio, total) in enumerate(pagos_creados):
                    total += ajustes.get(id_pago,0)
                    antiguedad = (hasta-semana).days
                    clase = "completo" if antiguedad>45 else ("calculado" if indice%7==0 else "parcial" if indice%3==0 else "completo")
                    if clase=="calculado": continue
                    aprobaciones.append((id_pago,administrador_demo,instante(semana+timedelta(days=7),9)))
                    pagado = total if clase=="completo" else (total*Decimal("0.55")).quantize(Decimal(1),rounding=ROUND_HALF_UP)
                    if clase=="completo" and indice%5==0:
                        anticipo=(pagado*Decimal("0.4")).quantize(Decimal(1),rounding=ROUND_HALF_UP)
                        abonos.append((uuid4(),id_pago,anticipo,semana+timedelta(days=7),f"DEMO-{id_pago}-A",administrador_demo,instante(semana+timedelta(days=7),10)))
                        pagado-=anticipo
                    abonos.append((uuid4(),id_pago,pagado,semana+timedelta(days=8),f"DEMO-{id_pago}-B",administrador_demo,instante(semana+timedelta(days=8),10)))
                c.executemany("INSERT INTO aprobaciones_pago(id_pago,id_usuario,aprobado_en) VALUES (%s,%s,%s)",aprobaciones)
                c.executemany("INSERT INTO abonos_pago(clave,id_pago,monto,fecha,comprobante,id_usuario,creado_en) VALUES (%s,%s,%s,%s,%s,%s,%s)",abonos)
                recientes = c.execute("""SELECT p.id_produccion,p.cantidad_kg,p.horas_trabajadas,j.fecha FROM produccion p JOIN jornadas j USING(id_jornada)
                    WHERE j.fecha>%s ORDER BY p.id_produccion DESC LIMIT 12""", (limite_cierre+timedelta(days=6),)).fetchall()
                for id_produccion,kilos,horas,fecha_registro in recientes:
                    nuevo=kilos+Decimal(7)
                    antes={"cantidad_kg":str(kilos),"horas_trabajadas":str(horas),"version":1}
                    despues={"cantidad_kg":str(nuevo),"horas_trabajadas":str(horas),"version":2}
                    c.execute("UPDATE produccion SET cantidad_kg=%s,version=2 WHERE id_produccion=%s",(nuevo,id_produccion))
                    c.execute("""INSERT INTO correcciones_cosecha(id_produccion,id_usuario,motivo,antes,despues,creado_en)
                        VALUES (%s,%s,'SIMULADO · Corrección de digitación',%s,%s,%s)""",(id_produccion,encargado,Jsonb(antes),Jsonb(despues),instante(fecha_registro,19)))
                for semana in sorted({p[1] for p in pagos_creados}):
                    eventos.append((administrador_demo,"Cierre de semana de pagos","SIMULADO · "+semana.isoformat(),instante(semana+timedelta(days=4),19)))
                c.executemany("INSERT INTO auditoria(id_usuario,accion,detalle,creado_en) VALUES (%s,%s,%s,%s)",eventos)
                # Controles de integridad independientes de las pantallas.
                assert not c.execute("""SELECT 1 FROM produccion p JOIN jornadas j USING(id_jornada) JOIN faenas f USING(id_faena)
                    WHERE j.fecha<f.fecha_inicio OR j.fecha>f.fecha_fin LIMIT 1""").fetchone()
                assert not c.execute("SELECT 1 FROM produccion GROUP BY id_trabajador,id_jornada HAVING SUM(horas_trabajadas)>24 LIMIT 1").fetchone()
                assert not c.execute("""SELECT 1 FROM pagos g WHERE COALESCE((SELECT SUM(monto) FROM abonos_pago a WHERE a.id_pago=g.id_pago),0)>
                    g.total+COALESCE((SELECT SUM(monto) FROM ajustes_cosecha a WHERE a.id_pago=g.id_pago),0) LIMIT 1""").fetchone()
                resumen = contar_operacion(conexion)
        # Verifica que la operación original no se modificó durante la preparación.
        with psycopg.connect(**parametros(), dbname=original) as origen:
            if contar_operacion(origen) != preservado:
                raise RuntimeError("Los conteos originales cambiaron mientras se preparaba la copia. Revisa antes de activarla.")
        estado={"original":original,"demo":nombre,"identificador":str(identificador),"desde":desde.isoformat(),"hasta":hasta.isoformat(),"conteos_originales":preservado,"conteos_demo":resumen}
        ESTADO.write_text(json.dumps(estado,ensure_ascii=False,indent=2),encoding="utf-8")
        ACCESOS.write_text("CUENTAS EXCLUSIVAS DE DEMOSTRACIÓN\nNo corresponden a personas reales.\n\n"+"\n".join(accesos),encoding="utf-8")
        print(json.dumps({"mensaje":"Demostración creada; la base original está conservada", "desde":desde.isoformat(),"hasta":hasta.isoformat(),"conteos":resumen,"accesos":str(ACCESOS)},ensure_ascii=False))
    finally:
        os.environ["DB_NAME"] = original


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    grupo=p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--crear",action="store_true")
    grupo.add_argument("--activar",action="store_true")
    grupo.add_argument("--original",action="store_true")
    p.add_argument("--hasta",type=date.fromisoformat,default=datetime.now(ZoneInfo("America/Santiago")).date())
    args=p.parse_args()
    if args.crear: generar(args.hasta)
    else: cambiar_entorno(args.activar)
