"""Seguridad con PostgreSQL real (base temporal, igual que test_postgres.py).

Cubre lo que la prueba de rutas no puede ver sin base de datos:
  1. Cada perfil SÍ puede hacer lo que le corresponde (y nada más).
  2. Ninguna respuesta filtra contraseñas, hashes ni claves.
  3. Los parámetros con SQL malicioso no rompen ni alteran nada.
  4. La sesión: cookie, vencimiento, cierre, cambio de clave y usuarios desactivados.

Se ejecutan con RUN_POSTGRES_TESTS=1, igual que el resto de pruebas de integración.
"""
import json
import os
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import main
import seguridad
from database import conectar_bd

# Misma base temporal y mismos datos de ejemplo que las demás pruebas de integración.
from test_postgres import base_temporal, bd  # noqa: F401

pytestmark = pytest.mark.integration

CLAVE = "Clave-de-prueba-1234"
PERFILES = ("administrador", "encargado", "consulta")
INYECCIONES = ["' OR '1'='1", "'; DROP TABLE trabajadores; --", "1; DELETE FROM usuarios --",
               "\" OR 1=1 --", "%' UNION SELECT usuario,password_hash FROM usuarios --"]


# ==========================================================
# AYUDAS
# ==========================================================
@pytest.fixture
def usuarios(bd):
    with conectar_bd() as c:
        for rol in PERFILES:
            c.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES (%s,%s,%s,%s)",
                      (rol, f"Cuenta {rol}", seguridad.hash_password(CLAVE), rol))
    return PERFILES


def entrar(rol, usuario=None, clave=CLAVE):
    cliente = TestClient(main.app, raise_server_exceptions=False)
    r = cliente.post("/auth/login", json={"usuario": usuario or rol, "password": clave})
    return cliente, r


@pytest.fixture
def clientes(usuarios):
    resultado = {}
    for rol in PERFILES:
        cliente, r = entrar(rol)
        assert r.status_code == 200, r.text
        resultado[rol] = cliente
    return resultado


def contar(tabla):
    with conectar_bd() as c:
        return c.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


def rutas(metodo, con_parametros=False):
    """Rutas del esquema OpenAPI: (ruta, [parametros de consulta])."""
    salida = []
    for ruta, ops in main.app.openapi()["paths"].items():
        op = ops.get(metodo.lower())
        if not op:
            continue
        hay_ruta = "{" in ruta
        if hay_ruta != con_parametros:
            continue
        consulta = [p["name"] for p in op.get("parameters", []) if p["in"] == "query"]
        salida.append((ruta, consulta))
    return sorted(salida)


GET_SIN_PARAMETROS = rutas("GET")
SOLO_ADMIN = {"/usuarios", "/auditoria"}
# Rutas que llaman a servicios externos o generan archivos pesados: se prueban aparte.
EXCLUIDAS = {"/ia/analisis", "/docs", "/redoc", "/openapi.json"}


# ==========================================================
# 1. CADA PERFIL PUEDE HACER LO QUE LE CORRESPONDE
# ==========================================================
@pytest.mark.parametrize("ruta", [r for r, _ in GET_SIN_PARAMETROS if r not in EXCLUIDAS])
@pytest.mark.parametrize("rol", PERFILES)
def test_lectura_por_perfil_nunca_da_401_ni_500(clientes, rol, ruta):
    r = clientes[rol].get(ruta)
    assert r.status_code != 401, "con sesión válida no debe pedir iniciar sesión"
    assert r.status_code < 500, f"{ruta} falló con {r.status_code}: {r.text[:200]}"
    if ruta in SOLO_ADMIN and rol != "administrador":
        assert r.status_code == 403
    else:
        assert r.status_code in (200, 422), f"{rol} no pudo leer {ruta}: {r.status_code}"


def test_administrador_puede_gestionar_usuarios(clientes):
    nuevo = {"usuario": "nueva.cuenta", "nombre": "Nueva", "password": "otra-clave-larga-1", "rol": "consulta"}
    r = clientes["administrador"].post("/usuarios", json=nuevo)
    assert r.status_code == 201
    lista = clientes["administrador"].get("/usuarios").json()
    assert "nueva.cuenta" in [u["usuario"] for u in lista]
    id_nuevo = r.json()["id"]
    assert clientes["administrador"].patch(f"/usuarios/{id_nuevo}", json={"rol": "encargado", "activo": True}).status_code == 200
    # No se puede dejar el sistema sin administrador ni cambiarse el propio perfil
    propio = next(u["id"] for u in lista if u["usuario"] == "administrador")
    assert clientes["administrador"].patch(f"/usuarios/{propio}", json={"rol": "consulta", "activo": True}).status_code == 409


def test_nadie_mas_puede_crear_usuarios_ni_cambiar_perfiles(clientes):
    antes = contar("usuarios")
    nuevo = {"usuario": "intruso", "nombre": "X", "password": "otra-clave-larga-1", "rol": "administrador"}
    for rol in ("encargado", "consulta"):
        assert clientes[rol].post("/usuarios", json=nuevo).status_code == 403
        assert clientes[rol].patch("/usuarios/1", json={"rol": "administrador", "activo": True}).status_code == 403
    assert contar("usuarios") == antes


def test_encargado_registra_pero_consulta_no(clientes):
    antes = contar("trabajadores")
    cuerpo = {"nombre": "Ana", "apellido": "Rojas"}
    assert clientes["consulta"].post("/trabajadores", json=cuerpo).status_code == 403
    assert contar("trabajadores") == antes                      # lo rechazado no dejó rastro
    assert clientes["encargado"].post("/trabajadores", json=cuerpo).status_code == 201
    assert clientes["administrador"].post("/trabajadores", json={"nombre": "Luis", "apellido": "Soto"}).status_code == 201
    assert contar("trabajadores") == antes + 2


def test_cierre_de_pagos_y_tarifas_solo_administrador(clientes):
    with conectar_bd() as c:
        antes = c.execute("SELECT COUNT(*) FROM pagos").fetchone()[0]
    for rol in ("encargado", "consulta"):
        assert clientes[rol].post("/pagos/cerrar", json={"fecha": "2026-10-14"}).status_code == 403
        assert clientes[rol].put("/tarifas/2026-10-12", json={"precio_kg": 1}).status_code == 403
    with conectar_bd() as c:
        assert c.execute("SELECT COUNT(*) FROM pagos").fetchone()[0] == antes
        assert float(c.execute("SELECT precio_kg FROM tarifas WHERE semana_inicio='2026-10-12'").fetchone()[0]) == 12.5
    assert clientes["administrador"].post("/pagos/cerrar", json={"fecha": "2026-10-14"}).status_code in (200, 201)


def test_operaciones_permitidas_quedan_en_la_auditoria(clientes):
    clientes["encargado"].post("/trabajadores", json={"nombre": "Ana", "apellido": "Rojas"})
    clientes["consulta"].post("/trabajadores", json={"nombre": "Zeta", "apellido": "Zeta"})   # rechazada
    with conectar_bd() as c:
        acciones = [f[0] for f in c.execute("SELECT accion FROM auditoria").fetchall()]
    assert "Registro de trabajador" in acciones
    assert acciones.count("Registro de trabajador") == 1          # la rechazada no se registra como hecha


# ==========================================================
# 2. FUGAS DE DATOS
# ==========================================================
PROHIBIDO = [r"pbkdf2_sha256", r"password_hash", r"\"password\"\s*:", r"token_hash", r"sk-[A-Za-z0-9]{10,}",
             r"Traceback \(most recent call last\)", r"psycopg\.", r"File \".*\.py\""]


def _sin_fugas(texto, extras=(), eco=None):
    """`eco` es el texto que la propia prueba envió: la API puede devolverlo en un error de validación."""
    if eco:
        for forma in (eco, json.dumps(eco)[1:-1], eco.replace("'", "\u0027")):
            texto = texto.replace(forma, "")
    for patron in PROHIBIDO:
        assert not re.search(patron, texto), f"posible fuga: {patron}"
    for secreto in extras:
        if secreto:
            assert secreto not in texto


def _secretos():
    return [os.getenv("DB_PASSWORD"), os.getenv("OPENAI_API_KEY"), CLAVE]


@pytest.mark.parametrize("ruta", [r for r, _ in GET_SIN_PARAMETROS if r not in EXCLUIDAS])
def test_ninguna_lectura_filtra_secretos(clientes, ruta):
    r = clientes["administrador"].get(ruta)
    _sin_fugas(r.text, _secretos())


def test_login_y_listado_de_usuarios_no_devuelven_hash_ni_clave(usuarios):
    cliente, r = entrar("administrador")
    assert set(r.json()) == {"id", "usuario", "nombre", "rol"}
    _sin_fugas(r.text, _secretos())
    lista = cliente.get("/usuarios")
    assert all(set(u) == {"id", "usuario", "nombre", "rol", "activo"} for u in lista.json())
    _sin_fugas(lista.text, _secretos())
    _sin_fugas(cliente.get("/auditoria").text, _secretos())


def test_errores_de_validacion_y_rutas_inexistentes_no_muestran_detalles_internos(clientes):
    c = clientes["administrador"]
    for r in (c.post("/trabajadores", json={"nombre": 5}), c.get("/ruta-que-no-existe"),
              c.get("/trabajadores/abc"), c.post("/produccion", content=b"{no es json"),
              c.get("/preparar-semana?fecha=invalida")):
        assert r.status_code in (404, 405, 422)
        _sin_fugas(r.text, _secretos())


def test_clave_nunca_se_guarda_en_claro_en_la_base(usuarios):
    with conectar_bd() as c:
        hashes = [f[0] for f in c.execute("SELECT password_hash FROM usuarios").fetchall()]
    assert hashes and all(CLAVE not in h and h.startswith("pbkdf2_sha256$") for h in hashes)


def test_auditoria_no_registra_claves_ni_cuerpos(clientes):
    clientes["administrador"].post("/usuarios", json={"usuario": "otra", "nombre": "O", "password": "secreta-muy-larga-9", "rol": "consulta"})
    clientes["administrador"].post("/auth/password", json={"actual": CLAVE, "nueva": "nueva-secreta-larga-9"})
    with conectar_bd() as c:
        texto = " ".join(f"{a} {d}" for a, d in c.execute("SELECT accion,COALESCE(detalle,'') FROM auditoria").fetchall())
    assert "secreta" not in texto and CLAVE not in texto


# ==========================================================
# 3. INYECCIÓN SQL
# ==========================================================
TABLAS = ["trabajadores", "usuarios", "produccion", "jornadas", "sesiones", "auditoria"]


def _estado():
    return {t: contar(t) for t in TABLAS}


@pytest.mark.parametrize("carga", INYECCIONES)
def test_parametros_de_consulta_con_sql_no_rompen_ni_alteran_nada(clientes, carga):
    antes = _estado()
    for ruta, parametros in rutas("GET"):
        if ruta in EXCLUIDAS or not parametros:
            continue
        r = clientes["administrador"].get(ruta, params={p: carga for p in parametros})
        assert r.status_code < 500, f"{ruta} con {carga!r}: {r.status_code} {r.text[:150]}"
        _sin_fugas(r.text, _secretos(), eco=carga)
    despues = _estado()
    # La auditoría puede crecer por las propias consultas; nada más debe cambiar.
    despues.pop("auditoria"), antes.pop("auditoria")
    assert despues == antes


@pytest.mark.parametrize("carga", INYECCIONES)
def test_rutas_con_identificador_texto_malicioso_no_rompen(clientes, carga):
    antes = _estado()
    for ruta, _ in rutas("GET", con_parametros=True):
        url = re.sub(r"\{[^}]+\}", requests_quote(carga), ruta)
        r = clientes["administrador"].get(url)
        assert r.status_code < 500, f"{url}: {r.status_code}"
    assert {k: v for k, v in _estado().items() if k != "auditoria"} == {k: v for k, v in antes.items() if k != "auditoria"}


def requests_quote(texto):
    from urllib.parse import quote
    return quote(texto, safe="")


@pytest.mark.parametrize("carga", INYECCIONES)
def test_login_con_inyeccion_no_entra(usuarios, carga):
    cliente, r = entrar("administrador", usuario=carga, clave=carga)
    assert r.status_code in (401, 422)
    assert contar("sesiones") == 0
    cliente, r = entrar("administrador", usuario="administrador", clave=carga)
    assert r.status_code in (401, 422)
    assert cliente.get("/usuarios").status_code == 401


def test_texto_malicioso_en_cuerpo_se_guarda_literal_sin_ejecutarse(clientes):
    nombre = "Robert'); DROP TABLE trabajadores;--"
    r = clientes["encargado"].post("/trabajadores", json={"nombre": nombre, "apellido": "Tabla"})
    assert r.status_code == 201
    assert contar("trabajadores") >= 2                          # la tabla sigue existiendo
    with conectar_bd() as c:
        assert c.execute("SELECT 1 FROM trabajadores WHERE nombre=%s", (nombre,)).fetchone()


# ==========================================================
# 4. SESIÓN Y COOKIE
# ==========================================================
def test_cookie_tiene_los_atributos_de_seguridad(usuarios):
    _, r = entrar("administrador")
    cookie = r.headers["set-cookie"].lower()
    assert seguridad.COOKIE in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=28800" in cookie
    assert "secure" not in cookie.replace("samesite", "")        # local por http: sin Secure por defecto


def test_cookie_secure_se_activa_por_configuracion(usuarios, monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "true")
    _, r = entrar("administrador")
    assert re.search(r";\s*secure", r.headers["set-cookie"].lower())


def test_el_token_se_guarda_con_hash_y_no_en_claro(usuarios):
    cliente, _ = entrar("administrador")
    token = cliente.cookies.get(seguridad.COOKIE)
    assert len(token) >= 48
    with conectar_bd() as c:
        guardados = [f[0] for f in c.execute("SELECT token_hash FROM sesiones").fetchall()]
    assert token not in guardados and len(guardados) == 1 and len(guardados[0]) == 64


def test_cada_inicio_de_sesion_genera_un_token_distinto(usuarios):
    a, _ = entrar("administrador")
    b, _ = entrar("administrador")
    assert a.cookies.get(seguridad.COOKIE) != b.cookies.get(seguridad.COOKIE)


def test_sesion_vencida_deja_de_servir(clientes):
    assert clientes["administrador"].get("/usuarios").status_code == 200
    with conectar_bd() as c:
        c.execute("UPDATE sesiones SET vence_en = NOW() - INTERVAL '1 second'")
    assert clientes["administrador"].get("/usuarios").status_code == 401


def test_token_robado_no_sirve_despues_de_cerrar_sesion(usuarios):
    cliente, _ = entrar("administrador")
    token = cliente.cookies.get(seguridad.COOKIE)
    assert cliente.post("/auth/logout").status_code == 200
    otro = TestClient(main.app, raise_server_exceptions=False)
    otro.cookies.set(seguridad.COOKIE, token)                     # alguien reutiliza el token viejo
    assert otro.get("/usuarios").status_code == 401


def test_usuario_desactivado_pierde_el_acceso_al_instante(clientes):
    antes = clientes["consulta"].get("/trabajadores").status_code
    assert antes == 200
    lista = clientes["administrador"].get("/usuarios").json()
    id_consulta = next(u["id"] for u in lista if u["usuario"] == "consulta")
    assert clientes["administrador"].patch(f"/usuarios/{id_consulta}", json={"rol": "consulta", "activo": False}).status_code == 200
    assert clientes["consulta"].get("/trabajadores").status_code == 401
    _, r = entrar("consulta")
    assert r.status_code == 401                                   # tampoco puede volver a entrar


def test_sesion_abierta_no_sirve_si_la_cuenta_se_desactiva_directo_en_la_base(clientes):
    """Tercera defensa: aunque nadie borre la sesión, una cuenta inactiva no pasa."""
    assert clientes["consulta"].get("/trabajadores").status_code == 200
    with conectar_bd() as c:
        c.execute("UPDATE usuarios SET activo = FALSE WHERE usuario = 'consulta'")
    assert clientes["consulta"].get("/trabajadores").status_code == 401


def test_cambio_de_perfil_corta_las_sesiones_abiertas(clientes):
    lista = clientes["administrador"].get("/usuarios").json()
    id_enc = next(u["id"] for u in lista if u["usuario"] == "encargado")
    clientes["administrador"].patch(f"/usuarios/{id_enc}", json={"rol": "consulta", "activo": True})
    assert clientes["encargado"].get("/trabajadores").status_code == 401


def test_cambiar_la_contrasena_cierra_las_otras_sesiones_y_exige_la_actual(usuarios):
    a, _ = entrar("administrador")
    b, _ = entrar("administrador")
    assert a.post("/auth/password", json={"actual": "incorrecta-larga-1", "nueva": "nueva-clave-larga-1"}).status_code == 400
    assert b.get("/usuarios").status_code == 200                  # no pasó nada
    assert a.post("/auth/password", json={"actual": CLAVE, "nueva": "nueva-clave-larga-1"}).status_code == 200
    assert a.get("/usuarios").status_code == 200                  # la sesión actual sigue
    assert b.get("/usuarios").status_code == 401                  # la otra se cerró
    assert entrar("administrador")[1].status_code == 401          # la vieja contraseña ya no entra
    assert entrar("administrador", clave="nueva-clave-larga-1")[1].status_code == 200


def test_contrasena_nueva_corta_se_rechaza(usuarios):
    a, _ = entrar("administrador")
    assert a.post("/auth/password", json={"actual": CLAVE, "nueva": "corta"}).status_code == 422
    assert entrar("administrador")[1].status_code == 200


def test_mensaje_de_login_no_revela_si_el_usuario_existe(usuarios):
    _, mal_usuario = entrar("administrador", usuario="no-existe")
    _, mala_clave = entrar("administrador", clave="incorrecta-larga-1")
    assert mal_usuario.status_code == mala_clave.status_code == 401
    assert mal_usuario.json() == mala_clave.json()


def test_el_bloqueo_por_intentos_es_por_usuario_y_no_deja_entrar_ni_con_la_clave_buena(usuarios):
    for _ in range(5):
        assert entrar("administrador", clave="incorrecta-larga-1")[1].status_code == 401
    assert entrar("administrador", clave="incorrecta-larga-1")[1].status_code == 429
    assert entrar("administrador")[1].status_code == 429          # ni con la clave correcta
    assert entrar("consulta")[1].status_code == 200               # otro usuario no se ve afectado


def test_sesiones_vencidas_se_limpian_al_iniciar_otra(usuarios):
    entrar("administrador")
    with conectar_bd() as c:
        c.execute("UPDATE sesiones SET vence_en = NOW() - INTERVAL '1 day'")
    entrar("consulta")
    assert contar("sesiones") == 1


def test_sin_cookie_y_con_cookie_basura_no_hay_acceso(usuarios):
    anonimo = TestClient(main.app, raise_server_exceptions=False)
    assert anonimo.get("/usuarios").status_code == 401
    for basura in ("", "x", "a" * 5000, "' OR 1=1 --", "../../etc/passwd"):
        anonimo.cookies.set(seguridad.COOKIE, basura)
        assert anonimo.get("/usuarios").status_code == 401


def test_origen_ajeno_no_puede_escribir_aunque_tenga_sesion_valida(clientes):
    antes = contar("trabajadores")
    r = clientes["administrador"].post("/trabajadores", json={"nombre": "Ana", "apellido": "Rojas"},
                                       headers={"Origin": "https://sitio-malo.invalid"})
    assert r.status_code == 403 and contar("trabajadores") == antes
    ok = clientes["administrador"].post("/trabajadores", json={"nombre": "Ana", "apellido": "Rojas"},
                                        headers={"Origin": "http://127.0.0.1:5173"})
    assert ok.status_code == 201
