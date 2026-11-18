
from datetime import datetime
from io import BytesIO
import math
import re

import pandas as pd


# Hojas que se prueban primero; las que contienen "sector" nunca se leen.
HOJAS_PREFERIDAS = ("anillado", "cosecha")
FILAS_BUSQUEDA_ENCABEZADO = 30


def _a_fecha(valor):
    """Devuelve la fecha (YYYY-MM-DD) si la celda parece una fecha; si no, None."""
    if valor is None or isinstance(valor, bool):
        return None

    try:
        if isinstance(valor, (datetime, pd.Timestamp)):
            if pd.isna(valor):
                return None
            fecha = pd.Timestamp(valor)
        elif isinstance(valor, (int, float)):
            if not math.isfinite(valor) or not 36526 <= valor <= 73050:
                return None
            fecha = pd.to_datetime(float(valor), unit="D", origin="1899-12-30")
        elif isinstance(valor, str):
            texto = valor.strip()
            if not re.fullmatch(r"\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}", texto):
                return None
            fecha = pd.to_datetime(texto, dayfirst=True)
        else:
            return None
    except (ValueError, TypeError, OverflowError):
        return None

    if pd.isna(fecha) or not 2000 <= fecha.year <= 2100:
        return None
    return fecha.strftime("%Y-%m-%d")


def _es_numero(valor):
    if isinstance(valor, bool) or pd.isna(valor):
        return False
    try:
        float(str(valor).replace(",", "."))
        return True
    except ValueError:
        return False


def _buscar_encabezado(tabla):
    """Fila con más fechas: ahí están los días de la planilla."""
    mejor_fila, mejores = None, []

    for indice in range(min(FILAS_BUSQUEDA_ENCABEZADO, len(tabla))):
        fila = tabla.iloc[indice]
        columnas = []
        for columna in range(len(fila)):
            fecha = _a_fecha(fila.iloc[columna])
            if fecha:
                columnas.append((columna, fecha))
        if len(columnas) > len(mejores):
            mejor_fila, mejores = indice, columnas

    return mejor_fila, mejores


def _leer_hoja(tabla, nombre_archivo):
    fila_fechas, columnas_diarias = _buscar_encabezado(tabla)
    if fila_fechas is None:
        return []

    primera_fecha = columnas_diarias[0][0]
    filas = range(fila_fechas + 1, len(tabla))

    # Columna del nombre: la de más textos (con letras) antes de las fechas.
    puntajes = {}
    for columna in range(primera_fecha):
        puntajes[columna] = sum(
            1
            for i in filas
            if isinstance(tabla.iat[i, columna], str)
            and re.search(r"[^\W\d_]", tabla.iat[i, columna])
        )
    if not puntajes or max(puntajes.values()) == 0:
        return []
    columna_nombre = max(puntajes, key=lambda c: (puntajes[c], -c))

    # Columna del número: la más cercana a la izquierda del nombre con enteros.
    columna_numero = None
    for columna in range(columna_nombre - 1, -1, -1):
        enteros = sum(
            1
            for i in filas
            if _es_numero(tabla.iat[i, columna])
            and float(str(tabla.iat[i, columna]).replace(",", ".")).is_integer()
        )
        if enteros >= 1:
            columna_numero = columna
            break

    registros = []
    secuencia = 0

    for indice in filas:
        nombre = tabla.iat[indice, columna_nombre]
        if pd.isna(nombre) or not isinstance(nombre, str):
            continue

        nombre = nombre.strip()
        if not nombre or not re.search(r"[^\W\d_]", nombre):
            continue
        if re.match(r"(?i)(sub)?\s*total|nombre\b", nombre):
            continue

        if columna_numero is not None:
            numero = tabla.iat[indice, columna_numero]
            if not _es_numero(numero):
                continue
            numero_trabajador = int(float(str(numero).replace(",", ".")))
        else:
            secuencia += 1
            numero_trabajador = secuencia

        for columna, fecha in columnas_diarias:
            valor = tabla.iat[indice, columna]

            if pd.isna(valor):
                continue

            try:
                kilos = float(str(valor).replace(",", "."))
            except (ValueError, TypeError):
                continue

            if not math.isfinite(kilos) or kilos <= 0:
                continue

            registros.append({
                "archivo": nombre_archivo,
                "numero_planilla": numero_trabajador,
                "trabajador": nombre,
                "fecha": fecha,
                "kilos": round(kilos, 2),
                "labor": "Cosecha",
                "sector": None,
                "horas": None,
                "requiere_revision": False
            })

    return registros


def leer_planilla(contenido: bytes, nombre_archivo: str):
    """
    Lee una planilla de cosecha de Doña Laura sin depender del nombre de la hoja
    ni de la posición exacta de las columnas.
    Busca la hoja (Anillado o Cosecha primero, luego cualquier otra menos
    Sectores), la fila de fechas y las columnas de número, nombre y kilos diarios.
    Extrae únicamente trabajador, fecha y kilos diarios.
    No guarda información en la base de datos.
    """

    hojas = pd.read_excel(BytesIO(contenido), sheet_name=None, header=None)

    def prioridad(nombre):
        minuscula = str(nombre).strip().lower()
        for posicion, preferida in enumerate(HOJAS_PREFERIDAS):
            if preferida in minuscula:
                return posicion
        return len(HOJAS_PREFERIDAS)

    nombres = [n for n in hojas if "sector" not in str(n).lower()]
    nombres.sort(key=prioridad)  # estable: respeta el orden original

    for nombre_hoja in nombres:
        registros = _leer_hoja(hojas[nombre_hoja], nombre_archivo)
        if registros:
            return registros

    raise ValueError("No se encontró una hoja con fechas, trabajadores y kilos.")
