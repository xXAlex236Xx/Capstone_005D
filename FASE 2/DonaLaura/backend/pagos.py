import csv
import io
from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import psycopg
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from database import conectar_bd


router = APIRouter(tags=["Pagos"])


# =====================================================
# TABLAS DEL MÓDULO (se crean si no existen)
# =====================================================

def crear_tablas_pagos():
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tarifas (
                        id_tarifa SERIAL PRIMARY KEY,
                        semana_inicio DATE NOT NULL UNIQUE,
                        precio_kg NUMERIC(10, 2) NOT NULL CHECK (precio_kg > 0),
                        creado_en TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pagos (
                        id_pago SERIAL PRIMARY KEY,
                        semana_inicio DATE NOT NULL,
                        id_trabajador INTEGER NOT NULL
                            REFERENCES trabajadores (id_trabajador),
                        kilos NUMERIC(12, 2) NOT NULL,
                        precio_kg NUMERIC(10, 2) NOT NULL,
                        total NUMERIC(14, 0) NOT NULL,
                        fecha_cierre TIMESTAMP NOT NULL DEFAULT NOW(),
                        UNIQUE (semana_inicio, id_trabajador)
                    )
                """)
    except psycopg.Error as error:
        print(
            f"ERROR AL CREAR TABLAS DE PAGOS: "
            f"{type(error).__name__}: {error}"
        )


@asynccontextmanager
async def ciclo_de_vida(app):
    crear_tablas_pagos()
    yield


# =====================================================
# MODELOS
# =====================================================

class TarifaGuardar(BaseModel):
    precio_kg: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class CierreSemana(BaseModel):
    fecha: date


# =====================================================
# UTILIDADES
# =====================================================

def lunes_de(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())


def calcular_total(kilos: Decimal, precio_kg: Decimal) -> Decimal:
    return (kilos * precio_kg).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def obtener_precio(cursor, semana_inicio: date):
    cursor.execute(
        "SELECT precio_kg FROM tarifas WHERE semana_inicio = %s",
        (semana_inicio,)
    )
    fila = cursor.fetchone()
    return fila[0] if fila else None


def semana_cerrada(cursor, semana_inicio: date):
    cursor.execute(
        "SELECT MIN(fecha_cierre) FROM pagos WHERE semana_inicio = %s",
        (semana_inicio,)
    )
    return cursor.fetchone()[0]


def kilos_de_la_semana(cursor, semana_inicio: date):
    cursor.execute(
        """
        SELECT
            t.id_trabajador,
            t.nombre,
            t.apellido,
            t.rut,
            SUM(p.cantidad_kg)
        FROM produccion p
        JOIN jornadas j ON j.id_jornada = p.id_jornada
        JOIN trabajadores t ON t.id_trabajador = p.id_trabajador
        WHERE j.fecha >= %s AND j.fecha <= %s
        GROUP BY t.id_trabajador, t.nombre, t.apellido, t.rut
        HAVING SUM(p.cantidad_kg) > 0
        ORDER BY t.nombre, t.apellido
        """,
        (semana_inicio, semana_inicio + timedelta(days=6))
    )
    return cursor.fetchall()


def pagos_guardados(cursor, semana_inicio: date):
    cursor.execute(
        """
        SELECT
            t.id_trabajador,
            t.nombre,
            t.apellido,
            t.rut,
            g.kilos,
            g.precio_kg,
            g.total
        FROM pagos g
        JOIN trabajadores t ON t.id_trabajador = g.id_trabajador
        WHERE g.semana_inicio = %s
        ORDER BY t.nombre, t.apellido
        """,
        (semana_inicio,)
    )
    return cursor.fetchall()


def armar_detalle(semana_inicio: date, cursor):
    """Devuelve el detalle de pagos de la semana, cerrada o calculada."""
    fecha_cierre = semana_cerrada(cursor, semana_inicio)
    trabajadores = []

    if fecha_cierre is not None:
        precio = None
        for fila in pagos_guardados(cursor, semana_inicio):
            precio = fila[5]
            trabajadores.append({
                "id_trabajador": fila[0],
                "nombre": fila[1],
                "apellido": fila[2],
                "rut": fila[3],
                "kilos": float(fila[4]),
                "total": float(fila[6])
            })
    else:
        precio = obtener_precio(cursor, semana_inicio)
        for fila in kilos_de_la_semana(cursor, semana_inicio):
            kilos = Decimal(fila[4])
            trabajadores.append({
                "id_trabajador": fila[0],
                "nombre": fila[1],
                "apellido": fila[2],
                "rut": fila[3],
                "kilos": float(kilos),
                "total": (
                    float(calcular_total(kilos, precio))
                    if precio is not None
                    else None
                )
            })

    return {
        "semana_inicio": semana_inicio.isoformat(),
        "semana_fin": (semana_inicio + timedelta(days=6)).isoformat(),
        "precio_kg": float(precio) if precio is not None else None,
        "cerrada": fecha_cierre is not None,
        "fecha_cierre": (
            fecha_cierre.isoformat() if fecha_cierre is not None else None
        ),
        "total_kilos": round(sum(t["kilos"] for t in trabajadores), 2),
        "total_pagar": sum(t["total"] or 0 for t in trabajadores),
        "trabajadores": trabajadores
    }


# =====================================================
# TARIFAS
# =====================================================

@router.get("/tarifas")
def listar_tarifas():
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT semana_inicio, precio_kg
                    FROM tarifas
                    ORDER BY semana_inicio DESC
                """)

                return [
                    {
                        "semana_inicio": fila[0].isoformat(),
                        "semana_fin": (fila[0] + timedelta(days=6)).isoformat(),
                        "precio_kg": float(fila[1])
                    }
                    for fila in cursor.fetchall()
                ]

    except psycopg.Error as error:
        print(f"ERROR AL CONSULTAR TARIFAS: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudieron consultar las tarifas"
        )


@router.put("/tarifas/{fecha}")
def guardar_tarifa(fecha: date, tarifa: TarifaGuardar):
    """Crea o actualiza la tarifa de la semana (lunes a domingo) de esa fecha."""
    semana_inicio = lunes_de(fecha)

    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                if semana_cerrada(cursor, semana_inicio) is not None:
                    raise HTTPException(
                        status_code=409,
                        detail="La semana ya está cerrada; no se puede cambiar su tarifa"
                    )

                cursor.execute(
                    """
                    INSERT INTO tarifas (semana_inicio, precio_kg)
                    VALUES (%s, %s)
                    ON CONFLICT (semana_inicio)
                    DO UPDATE SET precio_kg = EXCLUDED.precio_kg
                    RETURNING semana_inicio, precio_kg
                    """,
                    (semana_inicio, tarifa.precio_kg)
                )

                fila = cursor.fetchone()

                return {
                    "semana_inicio": fila[0].isoformat(),
                    "semana_fin": (fila[0] + timedelta(days=6)).isoformat(),
                    "precio_kg": float(fila[1])
                }

    except psycopg.Error as error:
        print(f"ERROR AL GUARDAR TARIFA: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar la tarifa"
        )


# =====================================================
# PAGOS SEMANALES
# =====================================================

@router.get("/pagos/semana")
def consultar_pagos_semana(fecha: date):
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                return armar_detalle(lunes_de(fecha), cursor)

    except psycopg.Error as error:
        print(f"ERROR AL CONSULTAR PAGOS: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudieron consultar los pagos"
        )


@router.post("/pagos/cerrar", status_code=201)
def cerrar_semana(cierre: CierreSemana):
    """Guarda los pagos de la semana con la tarifa vigente. No se puede deshacer."""
    semana_inicio = lunes_de(cierre.fecha)

    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                # Evita cierres simultáneos de la misma semana.
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(20261015, %s)",
                    (semana_inicio.toordinal(),)
                )

                if semana_cerrada(cursor, semana_inicio) is not None:
                    raise HTTPException(
                        status_code=409,
                        detail="La semana ya está cerrada"
                    )

                precio = obtener_precio(cursor, semana_inicio)

                if precio is None:
                    raise HTTPException(
                        status_code=400,
                        detail="Define la tarifa de la semana antes de cerrarla"
                    )

                filas = kilos_de_la_semana(cursor, semana_inicio)

                if not filas:
                    raise HTTPException(
                        status_code=400,
                        detail="No hay producción registrada en esa semana"
                    )

                for fila in filas:
                    kilos = Decimal(fila[4])

                    cursor.execute(
                        """
                        INSERT INTO pagos (
                            semana_inicio,
                            id_trabajador,
                            kilos,
                            precio_kg,
                            total
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            semana_inicio,
                            fila[0],
                            kilos,
                            precio,
                            calcular_total(kilos, precio)
                        )
                    )

                return armar_detalle(semana_inicio, cursor)

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="La semana ya está cerrada"
        )

    except psycopg.Error as error:
        print(f"ERROR AL CERRAR SEMANA: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudo cerrar la semana"
        )


@router.get("/pagos/historial")
def historial_pagos():
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        semana_inicio,
                        MAX(precio_kg),
                        COUNT(*),
                        SUM(kilos),
                        SUM(total),
                        MIN(fecha_cierre)
                    FROM pagos
                    GROUP BY semana_inicio
                    ORDER BY semana_inicio DESC
                """)

                return [
                    {
                        "semana_inicio": fila[0].isoformat(),
                        "semana_fin": (fila[0] + timedelta(days=6)).isoformat(),
                        "precio_kg": float(fila[1]),
                        "trabajadores": fila[2],
                        "total_kilos": float(fila[3]),
                        "total_pagar": float(fila[4]),
                        "fecha_cierre": fila[5].isoformat()
                    }
                    for fila in cursor.fetchall()
                ]

    except psycopg.Error as error:
        print(f"ERROR AL CONSULTAR HISTORIAL DE PAGOS: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudo consultar el historial de pagos"
        )


@router.get("/pagos/semana/exportar")
def exportar_pagos_semana(fecha: date):
    """Descarga el detalle de pagos de la semana en CSV (abre en Excel)."""
    semana_inicio = lunes_de(fecha)

    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                detalle = armar_detalle(semana_inicio, cursor)

    except psycopg.Error as error:
        print(f"ERROR AL EXPORTAR PAGOS: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudo exportar el detalle de pagos"
        )

    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow([
        "Semana desde", "Semana hasta", "Estado", "Trabajador",
        "RUT", "Kilos", "Precio por kg", "Total a pagar"
    ])

    for t in detalle["trabajadores"]:
        escritor.writerow([
            detalle["semana_inicio"],
            detalle["semana_fin"],
            "Cerrada" if detalle["cerrada"] else "Sin cerrar",
            f"{t['nombre']} {t['apellido']}",
            t["rut"] or "",
            str(t["kilos"]).replace(".", ","),
            (
                str(detalle["precio_kg"]).replace(".", ",")
                if detalle["precio_kg"] is not None
                else ""
            ),
            int(t["total"]) if t["total"] is not None else ""
        ])

    return Response(
        content="﻿" + salida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="pagos_{detalle["semana_inicio"]}.csv"'
        }
    )
