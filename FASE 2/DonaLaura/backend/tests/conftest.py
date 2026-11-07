import os

import pytest

import seguridad


@pytest.fixture(autouse=True)
def acceso_unitario(request, monkeypatch):
    # Las pruebas unitarias no abren conexiones. Las de seguridad e integración
    # verifican la autenticación explícitamente.
    if request.node.get_closest_marker("seguridad") or request.node.get_closest_marker("integration"):
        return
    monkeypatch.setattr(seguridad, "usuario_de_sesion", lambda token: {
        "id": 1, "usuario": "prueba", "nombre": "Prueba", "rol": "administrador"
    })
    monkeypatch.setattr(seguridad, "registrar_evento", lambda *args: None)


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Usa RUN_POSTGRES_TESTS=1 para PostgreSQL real"))
