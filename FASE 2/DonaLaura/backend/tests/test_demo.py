import json
from datetime import date
import pytest
import demo


def test_no_regenera_ni_conecta_si_ya_hay_demostracion(tmp_path,monkeypatch):
    estado=tmp_path/"demostracion.json"; estado.write_text("{}")
    monkeypatch.setattr(demo,"ESTADO",estado)
    monkeypatch.setattr(demo,"conectar_bd",lambda:pytest.fail("No debe conectar ni modificar una base"))
    with pytest.raises(RuntimeError,match="Ya hay"):
        demo.generar(date(2026,11,5))


@pytest.mark.parametrize("original,nombre",[("operacion","operacion"),("operacion","otra_base")])
def test_rechaza_referencias_sin_prefijo_demo(tmp_path,monkeypatch,original,nombre):
    estado=tmp_path/"demostracion.json"
    estado.write_text(json.dumps({"original":original,"demo":nombre}))
    monkeypatch.setattr(demo,"ESTADO",estado)
    with pytest.raises(RuntimeError,match="no es válida"):
        demo.leer_estado()
