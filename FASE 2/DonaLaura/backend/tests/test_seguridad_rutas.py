"""Recorre TODAS las rutas registradas en la API y comprueba su protección.

No usa base de datos: el middleware responde 401/403 antes de llegar a la ruta.
Como las rutas se leen de `main.app`, una ruta nueva queda cubierta sola.
"""
import re

import pytest
from fastapi.testclient import TestClient

import main
import seguridad

pytestmark = pytest.mark.seguridad

PUBLICAS = {"/", "/health", "/auth/login", "/entorno"}
LECTURA = {"GET", "HEAD", "OPTIONS"}
# Escrituras que un perfil de solo consulta sí puede usar (análisis, no modifican datos).
ESCRITURA_PERMITIDA_A_CONSULTA = {
    "/ia/chat", "/ia/agente", "/importacion/validar", "/importacion/vista-previa",
    "/auth/logout", "/auth/password",
}
SOLO_ADMIN_LECTURA = {"/usuarios", "/auditoria"}


def _rellenar(ruta):
    """Cambia {parametros} por valores de ejemplo para poder llamar a la ruta."""
    return re.sub(r"\{[^}]+\}", "1", ruta)


def _operaciones():
    # Se leen del esquema OpenAPI: incluye las rutas de todos los módulos,
    # sin depender de cómo FastAPI guarde los routers por dentro.
    vistas = set()
    for ruta, metodos in main.app.openapi()["paths"].items():
        for metodo in metodos:
            if metodo.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                vistas.add((metodo.upper(), _rellenar(ruta)))
    return sorted(vistas)


OPERACIONES = _operaciones()
PROTEGIDAS = [(m, p) for m, p in OPERACIONES if p not in PUBLICAS]
ESCRITURAS = [(m, p) for m, p in PROTEGIDAS if m not in LECTURA]


def _cliente(monkeypatch, rol):
    monkeypatch.setattr(
        seguridad, "usuario_de_sesion",
        lambda token: None if rol is None else {"id": 7, "usuario": "t", "nombre": "T", "rol": rol},
    )
    return TestClient(main.app, raise_server_exceptions=False)


def test_se_encontraron_rutas():
    # Si esto falla, la prueba de abajo estaría recorriendo una lista vacía.
    assert len(PROTEGIDAS) > 40
    assert len(ESCRITURAS) > 20


@pytest.mark.parametrize("metodo,ruta", PROTEGIDAS)
def test_sin_sesion_toda_ruta_protegida_responde_401(monkeypatch, metodo, ruta):
    cliente = _cliente(monkeypatch, None)
    assert cliente.request(metodo, ruta).status_code == 401


@pytest.mark.parametrize("metodo,ruta", PROTEGIDAS)
def test_cookie_falsa_responde_401(monkeypatch, metodo, ruta):
    cliente = _cliente(monkeypatch, None)
    cliente.cookies.set(seguridad.COOKIE, "token-inventado")
    assert cliente.request(metodo, ruta).status_code == 401


@pytest.mark.parametrize("metodo,ruta", [(m, p) for m, p in ESCRITURAS if p not in ESCRITURA_PERMITIDA_A_CONSULTA])
def test_consulta_no_puede_escribir_en_ninguna_ruta(monkeypatch, metodo, ruta):
    cliente = _cliente(monkeypatch, "consulta")
    assert cliente.request(metodo, ruta, json={}).status_code == 403


@pytest.mark.parametrize("ruta", sorted(SOLO_ADMIN_LECTURA))
@pytest.mark.parametrize("rol", ["consulta", "encargado"])
def test_usuarios_y_auditoria_solo_para_administrador(monkeypatch, rol, ruta):
    cliente = _cliente(monkeypatch, rol)
    assert cliente.get(ruta).status_code == 403


def _es_admin(ruta):
    return (
        ruta.startswith(("/usuarios", "/tarifas", "/cobros", "/clientes", "/faenas", "/seguimiento-pagos"))
        or ruta == "/pagos/cerrar"
        or ruta.endswith("/ajustes")
    )


@pytest.mark.parametrize("metodo,ruta", [(m, p) for m, p in ESCRITURAS if _es_admin(p)])
def test_encargado_no_puede_usar_operaciones_de_administrador(monkeypatch, metodo, ruta):
    cliente = _cliente(monkeypatch, "encargado")
    assert cliente.request(metodo, ruta, json={}).status_code == 403


@pytest.mark.parametrize("ruta", ["/", "/health", "/auth/login", "/entorno"])
def test_origen_ajeno_se_rechaza_tambien_en_rutas_publicas(monkeypatch, ruta):
    cliente = _cliente(monkeypatch, None)
    r = cliente.post(ruta, json={}, headers={"Origin": "https://ajeno.invalid"})
    assert r.status_code == 403


@pytest.mark.parametrize("metodo,ruta", ESCRITURAS)
def test_origen_ajeno_no_escribe_ni_con_administrador(monkeypatch, metodo, ruta):
    cliente = _cliente(monkeypatch, "administrador")
    r = cliente.request(metodo, ruta, json={}, headers={"Origin": "https://ajeno.invalid"})
    assert r.status_code == 403


@pytest.mark.parametrize("ruta", ["/pagos/cerrar/", "//usuarios", "/usuarios/../usuarios", "/USUARIOS"])
def test_variantes_de_ruta_no_saltan_el_control(monkeypatch, ruta):
    """Una variante de la ruta nunca debe dar acceso a un perfil sin permiso."""
    cliente = _cliente(monkeypatch, "consulta")
    r = cliente.request("POST", ruta, json={})
    assert r.status_code in {403, 404, 405, 307, 308}
    assert r.status_code != 200
