import json
import pytest
import respaldo
from contextlib import nullcontext


def test_integridad_detecta_copia_alterada(tmp_path):
    archivo=tmp_path/"copia.dump"
    archivo.write_bytes(b"contenido de prueba")
    archivo.with_suffix(".json").write_text(json.dumps({"sha256":respaldo.huella_archivo(archivo)}))
    assert respaldo.copia_integra(archivo)
    archivo.write_bytes(b"contenido alterado")
    assert not respaldo.copia_integra(archivo)


def test_copia_sin_manifiesto_no_cuenta_como_respaldo_diario(tmp_path):
    archivo=tmp_path/"copia.dump"; archivo.write_bytes(b"incompleta")
    assert not respaldo.copia_integra(archivo)


@pytest.mark.parametrize("misma_base", [True, False])
def test_respaldo_diario_distingue_base_original_de_demostracion(tmp_path, monkeypatch, misma_base):
    class Coordinador:
        def execute(self, _): return self
        def fetchone(self): return (True,)

    archivo = tmp_path / f"agricolix_{respaldo.ahora():%Y%m%d}_prueba.dump"
    archivo.write_bytes(b"copia")
    archivo.with_suffix(".json").write_text(json.dumps({
        "sha256": respaldo.huella_archivo(archivo),
        "base_datos": "original" if misma_base else "agricolix_demo_prueba",
    }))
    creaciones = []
    monkeypatch.setenv("DB_NAME", "original")
    monkeypatch.setattr(respaldo, "CARPETA", tmp_path)
    monkeypatch.setattr(respaldo, "conectar_bd", lambda: nullcontext(Coordinador()))
    monkeypatch.setattr(respaldo, "crear", lambda: creaciones.append(True))
    respaldo.crear_diario()
    assert bool(creaciones) == (not misma_base)


def test_restauracion_rechaza_destino_operativo_antes_de_conectar(tmp_path,monkeypatch):
    archivo=tmp_path/"copia.dump"; archivo.write_bytes(b"prueba")
    archivo.with_suffix(".json").write_text(json.dumps({"sha256":respaldo.huella_archivo(archivo)}))
    monkeypatch.setattr(respaldo,"herramientas",lambda:pytest.fail("No debe conectar para un destino inválido"))
    with pytest.raises(RuntimeError,match="NUEVA"):
        respaldo.restaurar(archivo,destino="dona_laura_db")
