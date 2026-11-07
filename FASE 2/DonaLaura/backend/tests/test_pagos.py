from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import main
import pagos


def conexion_simulada(monkeypatch, modulo):
    conexion = MagicMock()
    cursor = conexion.__enter__.return_value.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(modulo, "conectar_bd", lambda: conexion)
    return cursor


@pytest.mark.parametrize("kilos,precio,total", [
    ("1.25", "10", "13"),
    ("1.24", "10", "12"),
    ("0", "123.45", "0"),
    ("123.45", "78.90", "9740"),
])
def test_total_redondea_al_peso(kilos, precio, total):
    assert pagos.calcular_total(Decimal(kilos), Decimal(precio)) == Decimal(total)


def test_cosecha_en_semana_cerrada_no_inserta(monkeypatch):
    cursor = conexion_simulada(monkeypatch, main)
    cursor.fetchone.side_effect = [
        ("Activo",), (date(2026, 10, 14),), (datetime(2026, 10, 19),)
    ]
    with pytest.raises(HTTPException) as error:
        main.registrar_produccion(main.ProduccionCrear(
            id_trabajador=1, id_jornada=1, id_sector=1, id_labor=1,
            cantidad_kg=100, horas_trabajadas=8,
        ))
    assert error.value.status_code == 409
    assert not any("INSERT" in llamada.args[0] for llamada in cursor.execute.call_args_list)


def test_cosecha_en_semana_abierta_se_registra(monkeypatch):
    cursor = conexion_simulada(monkeypatch, main)
    cursor.fetchone.side_effect = [("Activo",), (date(2026, 10, 14),), (None,), (42,)]
    resultado = main.registrar_produccion(main.ProduccionCrear(
        id_trabajador=1, id_jornada=1, id_sector=1, id_labor=1,
        cantidad_kg=100, horas_trabajadas=8,
    ))
    assert resultado["id_produccion"] == 42
    assert resultado["productividad_kg_hora"] == 12.5


def test_jornada_inexistente_no_inserta(monkeypatch):
    cursor = conexion_simulada(monkeypatch, main)
    cursor.fetchone.side_effect = [("Activo",), None]
    with pytest.raises(HTTPException) as error:
        main.registrar_produccion(main.ProduccionCrear(
            id_trabajador=1, id_jornada=999, id_sector=1, id_labor=1,
            cantidad_kg=100, horas_trabajadas=8,
        ))
    assert error.value.status_code == 404
    assert not any("INSERT" in llamada.args[0] for llamada in cursor.execute.call_args_list)


def test_importacion_de_semana_cerrada_rechaza_lote(monkeypatch):
    cursor = conexion_simulada(monkeypatch, main)
    cursor.fetchone.return_value = (datetime(2026, 10, 19),)
    lote = main.LoteImportacion(registros=[main.CosechaImportada(
        trabajador="Persona Ejemplo", fecha=date(2026, 10, 14), kilos=100,
        sectores=[main.SectorImportado(id_sector=1, kilos=100, horas=8)],
    )])
    with pytest.raises(HTTPException) as error:
        main.guardar_importacion(lote)
    assert error.value.status_code == 409
    assert not any("INSERT" in llamada.args[0] for llamada in cursor.execute.call_args_list)


def test_tarifa_de_semana_cerrada_no_cambia(monkeypatch):
    cursor = conexion_simulada(monkeypatch, pagos)
    cursor.fetchone.return_value = (datetime(2026, 10, 19),)
    with pytest.raises(HTTPException) as error:
        pagos.guardar_tarifa(date(2026, 10, 14), pagos.TarifaGuardar(precio_kg=100))
    assert error.value.status_code == 409
    assert not any("INSERT" in llamada.args[0] for llamada in cursor.execute.call_args_list)


def test_cierre_duplicado_no_inserta(monkeypatch):
    cursor = conexion_simulada(monkeypatch, pagos)
    cursor.fetchone.return_value = (datetime(2026, 10, 19),)
    with pytest.raises(HTTPException) as error:
        pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026, 10, 14)))
    assert error.value.status_code == 409
    assert not any("INSERT" in llamada.args[0] for llamada in cursor.execute.call_args_list)


@pytest.mark.parametrize("respuestas", [[(None,), None], [(None,), (Decimal("100"),)]])
def test_cierre_sin_tarifa_o_produccion_no_inserta(monkeypatch, respuestas):
    cursor = conexion_simulada(monkeypatch, pagos)
    cursor.fetchone.side_effect = respuestas
    cursor.fetchall.return_value = []
    with pytest.raises(HTTPException) as error:
        pagos.cerrar_semana(pagos.CierreSemana(fecha=date(2026, 10, 14)))
    assert error.value.status_code == 400
    assert not any("INSERT" in llamada.args[0] for llamada in cursor.execute.call_args_list)


def test_semana_abierta_bloquea_antes_de_comprobar():
    cursor = MagicMock()
    cursor.fetchone.return_value = (None,)
    pagos.exigir_semana_abierta(cursor, date(2026, 10, 18))
    llamadas = cursor.execute.call_args_list
    assert "pg_advisory_xact_lock" in llamadas[0].args[0]
    assert llamadas[0].args[1] == (date(2026, 10, 12).toordinal(),)
    assert "FROM pagos" in llamadas[1].args[0]
