"""Importación inteligente: reconocimiento de nombres y orden de dependencias."""
from datetime import date

import pytest
from fastapi import HTTPException

import main
from importacion_inteligente import (
    analizar_trabajadores, clave_nombre, partir_nombre, resolver_trabajador, son_parecidos,
)


def test_clave_ignora_tildes_mayusculas_y_parentesis():
    assert clave_nombre("  Manuel  VÁSQUEZ (Ferddy) ") == "manuel vasquez"


def test_partir_nombre():
    assert partir_nombre("Manuel Vasquez (Ferddy)") == ("Manuel", "Vasquez")
    assert partir_nombre("Marcial") == ("Marcial", "")
    assert partir_nombre("Lucien Dorne Dit Milicien") == ("Lucien", "Dorne Dit Milicien")


@pytest.mark.parametrize("a,b", [
    ("Christopher", "Christpher"),
    ("Marcial", "Marcial Costana"),
    ("Lucien Dorme", "Lucien Dorne Dit Milicien"),
    ("Nelson Rui", "Nelson Ruiz"),
])
def test_nombres_que_podrian_ser_la_misma_persona(a, b):
    assert son_parecidos(a, b)


@pytest.mark.parametrize("a,b", [
    ("Raul Balceras", "Samuel Balceras"),
    ("Elio Mendez", "Martha Mendez"),
    ("Nelson Paye", "Nelson Ruiz"),
    ("Jose Aguilar", "Jose Aguilar"),
])
def test_nombres_de_personas_distintas_no_se_confunden(a, b):
    assert not son_parecidos(a, b)


def test_analisis_clasifica_nombres():
    bd = [(1, "Jhonny", "Torrejon", "Activo")]
    nombres = {"Jhonny Torrejon": 9, "Christopher": 1, "Christpher": 3, "Ana Soto": 2}
    por_nombre = {r["nombre"]: r for r in analizar_trabajadores(nombres, bd, {})}
    assert por_nombre["Jhonny Torrejon"]["estado"] == "reconocido"
    assert por_nombre["Ana Soto"]["estado"] == "nuevo"
    # Solo se pregunta por el nombre menos usado; el más usado queda como referencia.
    assert por_nombre["Christopher"]["estado"] == "pregunta"
    assert por_nombre["Christopher"]["candidatos"] == [{"tipo": "planilla", "nombre": "Christpher"}]
    assert por_nombre["Christpher"]["estado"] == "nuevo"


def test_analisis_pregunta_por_parecidos_de_la_base():
    bd = [(7, "Marcial", "Costana", "Activo")]
    lista = analizar_trabajadores({"Marcial": 1}, bd, {})
    assert lista[0]["estado"] == "pregunta"
    assert lista[0]["candidatos"] == [{"tipo": "base", "id_trabajador": 7, "nombre": "Marcial Costana"}]


def test_equivalencia_guardada_evita_volver_a_preguntar():
    bd = [(7, "Marcial", "Costana", "Activo")]
    lista = analizar_trabajadores({"Marcial": 1}, bd, {"marcial": 7})
    assert lista[0]["estado"] == "reconocido" and lista[0]["id_trabajador"] == 7


def test_resolver_prioriza_la_decision_del_usuario():
    por_clave = {"marcial costana": [7], "marcial": [3]}
    assert resolver_trabajador("Marcial", por_clave, {}, {}) == ("id", 3)
    assert resolver_trabajador("Marcial", por_clave, {}, {"marcial": {"id_trabajador": 7}}) == ("id", 7)
    assert resolver_trabajador("Christpher", {}, {}, {"christpher": {"igual_a": "Christopher"},
                                                      "christopher": {"crear": True}}) == ("crear", "christopher")
    assert resolver_trabajador("Nadie", {}, {}, {}) is None


def test_resolver_no_se_cuelga_con_ciclos():
    decisiones = {"a": {"igual_a": "b"}, "b": {"igual_a": "a"}}
    assert resolver_trabajador("a", {}, {}, decisiones) is None


def test_lote_sin_decisiones_sigue_siendo_valido():
    lote = main.LoteImportacion(registros=[main.CosechaImportada(
        trabajador="Persona", fecha=date(2026, 10, 14), kilos=10,
        sectores=[main.SectorImportado(id_sector=1, kilos=10, horas=1)])])
    assert lote.decisiones == {} and lote.crear_faltantes is False
