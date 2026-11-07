import pandas as pd
import pytest
from ia.modelo_productividad import _calcular_tendencia


def serie(kilos):
    return pd.DataFrame({"fecha": pd.date_range("2024-01-01", periods=len(kilos)), "kilos": kilos})


def test_historial_largo_no_oculta_caida_reciente():
    reciente = list(range(1000, 600, -20))
    assert _calcular_tendencia(serie([1000] * 400 + reciente)) == pytest.approx(
        _calcular_tendencia(serie(reciente)))
    assert _calcular_tendencia(serie(reciente)) < -30


@pytest.mark.parametrize("kilos", [[1000] * 40, [0] * 20, [500]])
def test_tendencia_sin_cambio_o_sin_base(kilos):
    assert _calcular_tendencia(serie(kilos)) == pytest.approx(0, abs=1e-8)


def test_tendencia_respeta_orden_cronologico():
    datos = serie(list(range(600, 1000, 20)))
    assert _calcular_tendencia(datos.iloc[::-1]) == pytest.approx(_calcular_tendencia(datos))
    assert _calcular_tendencia(datos) > 30
