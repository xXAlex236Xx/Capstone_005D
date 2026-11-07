import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


@pytest.mark.parametrize("clave", ["", "   ", "escribir_la_clave_de_openai"])
def test_asistente_sin_clave_informa_configuracion(monkeypatch, clave):
    monkeypatch.setattr(main, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("OPENAI_API_KEY", clave)
    respuesta = client.post("/ia/agente", json={"pregunta": "Hola"})
    assert respuesta.status_code == 503
    assert "OPENAI_API_KEY" in respuesta.json()["detail"]


def test_asistente_configurado_conserva_respuesta(monkeypatch):
    monkeypatch.setattr(main, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("OPENAI_API_KEY", "clave-simulada-sin-acceso-a-red")
    monkeypatch.setitem(sys.modules, "ia.agente_llm", SimpleNamespace(
        responder_agente=lambda pregunta, historial: {
            "respuesta": "Respuesta de prueba", "herramientas_usadas": []
        }
    ))
    respuesta = client.post("/ia/agente", json={"pregunta": "Hola"})
    assert respuesta.status_code == 200
    assert respuesta.json()["respuesta"] == "Respuesta de prueba"
