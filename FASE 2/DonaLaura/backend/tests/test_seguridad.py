import pytest
from fastapi.testclient import TestClient

import main
import seguridad

pytestmark = pytest.mark.seguridad


def test_password_no_se_guarda_en_claro_y_usa_sal():
    a = seguridad.hash_password("Una-clave-de-prueba-larga")
    b = seguridad.hash_password("Una-clave-de-prueba-larga")
    assert a != b
    assert "Una-clave" not in a
    assert seguridad.verificar_password("Una-clave-de-prueba-larga", a)
    assert not seguridad.verificar_password("incorrecta", a)
    assert not seguridad.verificar_password("incorrecta", "hash-corrupto")


@pytest.mark.parametrize("rol,metodo,ruta,permitido", [
    ("consulta", "GET", "/pagos/semana", True),
    ("consulta", "POST", "/produccion", False),
    ("consulta", "POST", "/ia/agente", True),
    ("consulta", "POST", "/importacion/guardar", False),
    ("encargado", "POST", "/produccion", True),
    ("encargado", "POST", "/pagos/cerrar", False),
    ("encargado", "PUT", "/tarifas/2026-11-02", False),
    ("encargado", "GET", "/usuarios", False),
    ("administrador", "PATCH", "/usuarios/2", True),
    ("administrador", "POST", "/pagos/cerrar", True),
    ("encargado", "POST", "/seguimiento-pagos/1/abonos", False),
    ("consulta", "PATCH", "/produccion/1", False),
    ("encargado", "POST", "/produccion/1/ajustes", False),
    ("administrador", "POST", "/produccion/1/ajustes", True),
    ("consulta", "GET", "/faenas", True),
    ("consulta", "POST", "/clientes", False),
    ("encargado", "GET", "/clientes", True),
    ("encargado", "PATCH", "/faenas/1", False),
    ("administrador", "POST", "/faenas", True),
])
def test_matriz_de_permisos(rol, metodo, ruta, permitido):
    assert seguridad.puede_acceder(rol, metodo, ruta) == permitido


def test_sin_sesion_devuelve_401(monkeypatch):
    monkeypatch.setattr(seguridad, "usuario_de_sesion", lambda token: None)
    cliente = TestClient(main.app)
    assert cliente.get("/trabajadores").status_code == 401


def test_consulta_no_puede_cerrar_pagos(monkeypatch):
    monkeypatch.setattr(seguridad, "usuario_de_sesion", lambda token: {"id": 1,"rol": "consulta"})
    cliente = TestClient(main.app)
    assert cliente.post("/pagos/cerrar", json={"fecha": "2026-11-02"}).status_code == 403


def test_origen_ajeno_no_puede_escribir(monkeypatch):
    monkeypatch.setattr(seguridad, "usuario_de_sesion", lambda token: {"id": 1,"rol": "administrador"})
    cliente = TestClient(main.app)
    assert cliente.post("/produccion", json={}, headers={"Origin": "https://ajeno.invalid"}).status_code == 403
