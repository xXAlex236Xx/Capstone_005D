import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

import psycopg
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from database import conectar_bd


router = APIRouter(tags=["Reportes"])

LIMITE_FILAS = 5000


# =====================================================
# UTILIDADES
# =====================================================

def numero(valor):
    if valor is None:
        return None
    return float(valor) if isinstance(valor, Decimal) else valor


def columna(clave, titulo, formato="texto", suma=False):
    return {
        "clave": clave,
        "titulo": titulo,
        "formato": formato,
        "suma": suma
    }


def kilos_por_hora(kilos, horas):
    if not horas:
        return None
    return round(kilos / horas, 2)


def armar_reporte(titulo, filtros, columnas, filas, truncado=False):
    totales = {}

    for col in columnas:
        if col["suma"]:
            totales[col["clave"]] = round(
                sum(fila[col["clave"]] or 0 for fila in filas), 2
            )

    # kg/h total = kilos totales / horas totales (no el promedio de promedios)
    if "kg_hora" in {c["clave"] for c in columnas}:
        totales["kg_hora"] = kilos_por_hora(
            totales.get("kilos", 0), totales.get("horas", 0)
        )

    return {
        "titulo": titulo,
        "filtros": filtros,
        "columnas": columnas,
        "filas": filas,
        "totales": totales,
        "total_filas": len(filas),
        "truncado": truncado
    }


def formato_csv(valor, formato):
    if valor is None:
        return ""
    if formato == "fecha":
        anio, mes, dia = str(valor).split("-")
        return f"{dia}-{mes}-{anio}"
    if formato == "pesos":
        return str(int(round(valor)))
    if formato == "numero":
        return str(valor).replace(".", ",")
    return valor


def respuesta_csv(reporte, nombre_archivo):
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")
    columnas = reporte["columnas"]

    escritor.writerow([c["titulo"] for c in columnas])

    for fila in reporte["filas"]:
        escritor.writerow([
            formato_csv(fila[c["clave"]], c["formato"]) for c in columnas
        ])

    if reporte["filas"]:
        escritor.writerow([
            "TOTAL" if i == 0
            else formato_csv(reporte["totales"].get(c["clave"]), c["formato"])
            for i, c in enumerate(columnas)
        ])

    return Response(
        content="﻿" + salida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nombre_archivo}.csv"'
        }
    )


def lunes_de(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())


# =====================================================
# REPORTE DE PRODUCCIÓN
# =====================================================

TIPOS_PRODUCCION = {
    "detalle": "Detalle de producción",
    "trabajador": "Producción por trabajador",
    "sector": "Producción por sector",
    "labor": "Producción por labor",
    "dia": "Producción por día"
}

AGRUPACIONES_PRODUCCION = {
    "trabajador": (
        "t.id_trabajador, t.nombre, t.apellido, t.rut",
        "CONCAT_WS(' ', t.nombre, t.apellido)",
        "grupo",
        "Trabajador"
    ),
    "sector": ("s.id_sector, s.nombre", "s.nombre", "grupo", "Sector"),
    "labor": ("l.id_labor, l.nombre", "l.nombre", "grupo", "Labor"),
    "dia": ("j.fecha", "j.fecha", "fecha", "Fecha")
}


def consultar_produccion(
    tipo, fecha_inicio, fecha_fin, id_sector, id_labor, id_trabajador
):
    condiciones = ["1 = 1"]
    parametros = []

    if fecha_inicio:
        condiciones.append("j.fecha >= %s")
        parametros.append(fecha_inicio)

    if fecha_fin:
        condiciones.append("j.fecha <= %s")
        parametros.append(fecha_fin)

    if id_sector is not None:
        condiciones.append("p.id_sector = %s")
        parametros.append(id_sector)

    if id_labor is not None:
        condiciones.append("p.id_labor = %s")
        parametros.append(id_labor)

    if id_trabajador is not None:
        condiciones.append("p.id_trabajador = %s")
        parametros.append(id_trabajador)

    where_sql = " AND ".join(condiciones)

    desde_sql = """
        FROM produccion p
        JOIN jornadas j ON j.id_jornada = p.id_jornada
        JOIN trabajadores t ON t.id_trabajador = p.id_trabajador
        JOIN sectores s ON s.id_sector = p.id_sector
        JOIN labores l ON l.id_labor = p.id_labor
        WHERE
    """ + where_sql

    filtros = {
        "fecha_inicio": fecha_inicio.isoformat() if fecha_inicio else None,
        "fecha_fin": fecha_fin.isoformat() if fecha_fin else None
    }

    with conectar_bd() as conexion:
        with conexion.cursor() as cursor:
            if id_sector is not None:
                cursor.execute(
                    "SELECT nombre FROM sectores WHERE id_sector = %s",
                    (id_sector,)
                )
                fila = cursor.fetchone()
                filtros["sector"] = fila[0] if fila else str(id_sector)

            if id_labor is not None:
                cursor.execute(
                    "SELECT nombre FROM labores WHERE id_labor = %s",
                    (id_labor,)
                )
                fila = cursor.fetchone()
                filtros["labor"] = fila[0] if fila else str(id_labor)

            if id_trabajador is not None:
                cursor.execute(
                    """
                    SELECT CONCAT_WS(' ', nombre, apellido)
                    FROM trabajadores WHERE id_trabajador = %s
                    """,
                    (id_trabajador,)
                )
                fila = cursor.fetchone()
                filtros["trabajador"] = fila[0] if fila else str(id_trabajador)

            if tipo == "detalle":
                cursor.execute(
                    f"""
                    SELECT
                        j.fecha,
                        CONCAT_WS(' ', t.nombre, t.apellido),
                        s.nombre,
                        l.nombre,
                        p.cantidad_kg,
                        p.horas_trabajadas
                    {desde_sql}
                    ORDER BY j.fecha DESC, t.nombre, t.apellido
                    LIMIT {LIMITE_FILAS + 1}
                    """,
                    parametros
                )

                registros = cursor.fetchall()
                truncado = len(registros) > LIMITE_FILAS
                registros = registros[:LIMITE_FILAS]

                filas = [
                    {
                        "fecha": r[0].isoformat(),
                        "trabajador": r[1],
                        "sector": r[2],
                        "labor": r[3],
                        "kilos": numero(r[4]),
                        "horas": numero(r[5]),
                        "kg_hora": kilos_por_hora(
                            float(r[4]), float(r[5]) if r[5] else None
                        )
                    }
                    for r in registros
                ]

                columnas = [
                    columna("fecha", "Fecha", "fecha"),
                    columna("trabajador", "Trabajador"),
                    columna("sector", "Sector"),
                    columna("labor", "Labor"),
                    columna("kilos", "Kilos", "numero", True),
                    columna("horas", "Horas", "numero", True),
                    columna("kg_hora", "Kg por hora", "numero")
                ]

                return armar_reporte(
                    TIPOS_PRODUCCION[tipo], filtros, columnas, filas, truncado
                )

            agrupar, etiqueta, clave, titulo_grupo = AGRUPACIONES_PRODUCCION[tipo]

            cursor.execute(
                f"""
                SELECT
                    {etiqueta},
                    COUNT(DISTINCT j.fecha),
                    COUNT(*),
                    SUM(p.cantidad_kg),
                    SUM(p.horas_trabajadas)
                {desde_sql}
                GROUP BY {agrupar}
                ORDER BY SUM(p.cantidad_kg) DESC
                """,
                parametros
            )

            filas = []

            for r in cursor.fetchall():
                kilos = float(r[3])
                horas = float(r[4]) if r[4] is not None else None

                valor = r[0].isoformat() if tipo == "dia" else r[0]

                filas.append({
                    clave: valor,
                    "dias": r[1],
                    "registros": r[2],
                    "kilos": kilos,
                    "horas": horas,
                    "kg_hora": kilos_por_hora(kilos, horas)
                })

            if tipo == "dia":
                filas.sort(key=lambda f: f["fecha"], reverse=True)

            columnas = [
                columna(
                    clave,
                    titulo_grupo,
                    "fecha" if tipo == "dia" else "texto"
                )
            ]

            if tipo != "dia":
                columnas.append(columna("dias", "Días trabajados", "numero"))

            columnas += [
                columna("registros", "Registros", "numero", True),
                columna("kilos", "Kilos", "numero", True),
                columna("horas", "Horas", "numero", True),
                columna("kg_hora", "Kg por hora", "numero")
            ]

            return armar_reporte(
                TIPOS_PRODUCCION[tipo], filtros, columnas, filas
            )


def producir_reporte_produccion(
    tipo, fecha_inicio, fecha_fin, id_sector, id_labor, id_trabajador
):
    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
        raise HTTPException(
            status_code=400,
            detail="La fecha de inicio no puede ser posterior a la fecha de fin"
        )

    try:
        return consultar_produccion(
            tipo, fecha_inicio, fecha_fin, id_sector, id_labor, id_trabajador
        )

    except psycopg.Error as error:
        print(f"ERROR EN REPORTE DE PRODUCCIÓN: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudo generar el reporte de producción"
        )


@router.get("/reportes/produccion")
def reporte_produccion(
    tipo: Literal["detalle", "trabajador", "sector", "labor", "dia"] = "detalle",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    id_sector: int | None = None,
    id_labor: int | None = None,
    id_trabajador: int | None = None
):
    return producir_reporte_produccion(
        tipo, fecha_inicio, fecha_fin, id_sector, id_labor, id_trabajador
    )


@router.get("/reportes/produccion/exportar")
def exportar_reporte_produccion(
    tipo: Literal["detalle", "trabajador", "sector", "labor", "dia"] = "detalle",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    id_sector: int | None = None,
    id_labor: int | None = None,
    id_trabajador: int | None = None
):
    reporte = producir_reporte_produccion(
        tipo, fecha_inicio, fecha_fin, id_sector, id_labor, id_trabajador
    )
    return respuesta_csv(reporte, f"reporte_produccion_{tipo}")


# =====================================================
# REPORTE DE PAGOS (semanas cerradas)
# =====================================================

TIPOS_PAGOS = {
    "detalle": "Detalle de pagos",
    "trabajador": "Pagos por trabajador",
    "semana": "Pagos por semana"
}


def consultar_pagos(tipo, fecha_inicio, fecha_fin, id_trabajador):
    condiciones = ["1 = 1"]
    parametros = []

    if fecha_inicio:
        condiciones.append("g.semana_inicio >= %s")
        parametros.append(lunes_de(fecha_inicio))

    if fecha_fin:
        condiciones.append("g.semana_inicio <= %s")
        parametros.append(fecha_fin)

    if id_trabajador is not None:
        condiciones.append("g.id_trabajador = %s")
        parametros.append(id_trabajador)

    desde_sql = """
        FROM pagos g
        JOIN trabajadores t ON t.id_trabajador = g.id_trabajador
        WHERE
    """ + " AND ".join(condiciones)

    filtros = {
        "fecha_inicio": fecha_inicio.isoformat() if fecha_inicio else None,
        "fecha_fin": fecha_fin.isoformat() if fecha_fin else None
    }

    with conectar_bd() as conexion:
        with conexion.cursor() as cursor:
            if id_trabajador is not None:
                cursor.execute(
                    """
                    SELECT CONCAT_WS(' ', nombre, apellido)
                    FROM trabajadores WHERE id_trabajador = %s
                    """,
                    (id_trabajador,)
                )
                fila = cursor.fetchone()
                filtros["trabajador"] = fila[0] if fila else str(id_trabajador)

            if tipo == "detalle":
                cursor.execute(
                    f"""
                    SELECT
                        g.semana_inicio,
                        CONCAT_WS(' ', t.nombre, t.apellido),
                        t.rut,
                        g.kilos,
                        g.precio_kg,
                        g.total
                    {desde_sql}
                    ORDER BY g.semana_inicio DESC, t.nombre, t.apellido
                    LIMIT {LIMITE_FILAS + 1}
                    """,
                    parametros
                )

                registros = cursor.fetchall()
                truncado = len(registros) > LIMITE_FILAS

                filas = [
                    {
                        "semana": r[0].isoformat(),
                        "trabajador": r[1],
                        "rut": r[2] or "",
                        "kilos": numero(r[3]),
                        "precio_kg": numero(r[4]),
                        "total": numero(r[5])
                    }
                    for r in registros[:LIMITE_FILAS]
                ]

                columnas = [
                    columna("semana", "Semana desde", "fecha"),
                    columna("trabajador", "Trabajador"),
                    columna("rut", "RUT"),
                    columna("kilos", "Kilos", "numero", True),
                    columna("precio_kg", "Precio por kg", "pesos"),
                    columna("total", "Total pagado", "pesos", True)
                ]

                return armar_reporte(
                    TIPOS_PAGOS[tipo], filtros, columnas, filas, truncado
                )

            if tipo == "trabajador":
                cursor.execute(
                    f"""
                    SELECT
                        CONCAT_WS(' ', t.nombre, t.apellido),
                        t.rut,
                        COUNT(*),
                        SUM(g.kilos),
                        SUM(g.total)
                    {desde_sql}
                    GROUP BY t.id_trabajador, t.nombre, t.apellido, t.rut
                    ORDER BY SUM(g.total) DESC
                    """,
                    parametros
                )

                filas = [
                    {
                        "trabajador": r[0],
                        "rut": r[1] or "",
                        "semanas": r[2],
                        "kilos": numero(r[3]),
                        "total": numero(r[4])
                    }
                    for r in cursor.fetchall()
                ]

                columnas = [
                    columna("trabajador", "Trabajador"),
                    columna("rut", "RUT"),
                    columna("semanas", "Semanas pagadas", "numero"),
                    columna("kilos", "Kilos", "numero", True),
                    columna("total", "Total pagado", "pesos", True)
                ]

                return armar_reporte(TIPOS_PAGOS[tipo], filtros, columnas, filas)

            cursor.execute(
                f"""
                SELECT
                    g.semana_inicio,
                    COUNT(*),
                    SUM(g.kilos),
                    MAX(g.precio_kg),
                    SUM(g.total)
                {desde_sql}
                GROUP BY g.semana_inicio
                ORDER BY g.semana_inicio DESC
                """,
                parametros
            )

            filas = [
                {
                    "semana": r[0].isoformat(),
                    "trabajadores": r[1],
                    "kilos": numero(r[2]),
                    "precio_kg": numero(r[3]),
                    "total": numero(r[4])
                }
                for r in cursor.fetchall()
            ]

            columnas = [
                columna("semana", "Semana desde", "fecha"),
                columna("trabajadores", "Trabajadores", "numero"),
                columna("kilos", "Kilos", "numero", True),
                columna("precio_kg", "Precio por kg", "pesos"),
                columna("total", "Total pagado", "pesos", True)
            ]

            return armar_reporte(TIPOS_PAGOS[tipo], filtros, columnas, filas)


def producir_reporte_pagos(tipo, fecha_inicio, fecha_fin, id_trabajador):
    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
        raise HTTPException(
            status_code=400,
            detail="La fecha de inicio no puede ser posterior a la fecha de fin"
        )

    try:
        return consultar_pagos(tipo, fecha_inicio, fecha_fin, id_trabajador)

    except psycopg.Error as error:
        print(f"ERROR EN REPORTE DE PAGOS: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudo generar el reporte de pagos"
        )


@router.get("/reportes/pagos")
def reporte_pagos(
    tipo: Literal["detalle", "trabajador", "semana"] = "detalle",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    id_trabajador: int | None = None
):
    return producir_reporte_pagos(tipo, fecha_inicio, fecha_fin, id_trabajador)


@router.get("/reportes/pagos/exportar")
def exportar_reporte_pagos(
    tipo: Literal["detalle", "trabajador", "semana"] = "detalle",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    id_trabajador: int | None = None
):
    reporte = producir_reporte_pagos(tipo, fecha_inicio, fecha_fin, id_trabajador)
    return respuesta_csv(reporte, f"reporte_pagos_{tipo}")
