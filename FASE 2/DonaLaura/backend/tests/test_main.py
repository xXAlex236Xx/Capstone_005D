from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_inicio_devuelve_mensaje_de_bienvenida():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "mensaje": "Bienvenido al sistema Dona Laura"
    }


def test_crear_trabajador_rechaza_nombre_vacio():
    response = client.post(
        "/trabajadores",
        json={"nombre": "", "apellido": "Nuñez"},
    )

    assert response.status_code == 422