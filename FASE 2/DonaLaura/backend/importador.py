
from datetime import datetime
from io import BytesIO
import math

import pandas as pd


def leer_planilla(contenido: bytes, nombre_archivo: str):
    """
    Lee la hoja Anillado de las planillas de Doña Laura.
    Extrae únicamente trabajador, fecha y kilos diarios.
    No guarda información en la base de datos.
    """

    tabla = pd.read_excel(
        BytesIO(contenido),
        sheet_name="Anillado",
        header=None
    )

    # La segunda fila contiene las fechas de cada día.
    fila_fechas = tabla.iloc[1]

    # Identificamos las columnas con fechas.
    columnas_diarias = []

    for columna in range(4, len(fila_fechas)):
        valor = fila_fechas.iloc[columna]

        if str(valor).strip().lower() == "total kg":
            break

        try:
            if isinstance(valor, (datetime, pd.Timestamp)):
                fecha = valor.strftime("%Y-%m-%d")
            else:
                fecha = pd.to_datetime(
                    float(valor),
                    unit="D",
                    origin="1899-12-30"
                ).strftime("%Y-%m-%d")

            columnas_diarias.append((columna, fecha))

        except (ValueError, TypeError, OverflowError):
            continue

    registros = []

    # Los trabajadores comienzan en la tercera fila.
    for indice_fila in range(2, len(tabla)):
        fila = tabla.iloc[indice_fila]

        numero = fila.iloc[0]
        nombre = fila.iloc[1]

        # Ignoramos encabezados, totales y filas vacías.
        if pd.isna(numero) or pd.isna(nombre):
            continue

        try:
            numero_trabajador = int(numero)
        except (ValueError, TypeError):
            continue

        nombre = str(nombre).strip()

        if not nombre:
            continue

        for columna, fecha in columnas_diarias:
            valor = fila.iloc[columna]

            if pd.isna(valor):
                continue

            try:
                kilos = float(valor)
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