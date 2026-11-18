

import os
import psycopg
from dotenv import load_dotenv



from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field
from typing import Literal

from collections import Counter

from datetime import date

from fastapi import File, UploadFile

from importador import leer_planilla
from importacion_inteligente import (
    analizar_trabajadores, clave_nombre, partir_nombre, resolver_trabajador,
)



from database import conectar_bd, BASE_DIR
from seguridad import ControlAcceso, router as router_acceso
from resumen import router as router_resumen
from operacion import router as router_operacion
from seguimiento import router as router_seguimiento
from faenas import router as router_faenas
from entorno import router as router_entorno
from cobros import router as router_cobros
from semana import router as router_semana

from pagos import router as router_pagos, ciclo_de_vida
from pagos import exigir_semana_abierta, lunes_de

from reportes import router as router_reportes





# =====================================================

# CONFIGURACIÓN DE FASTAPI

# =====================================================



app = FastAPI(

    title="Sistema de Gestion Dona Laura",

    description="API de gestion administrativa agricola",

    version="0.1.0",

    lifespan=ciclo_de_vida

)



# Permitir la conexión desde nuestro frontend React

app.add_middleware(ControlAcceso)
app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        "http://localhost:5173",

        "http://127.0.0.1:5173"

    ],

    allow_credentials=True,

    allow_methods=["GET", "POST", "PUT", "PATCH"

],

    allow_headers=["*"],

)





app.include_router(router_pagos)

app.include_router(router_reportes)
app.include_router(router_acceso)
app.include_router(router_faenas)
app.include_router(router_entorno)
app.include_router(router_cobros)
app.include_router(router_semana)
app.include_router(router_resumen)
app.include_router(router_operacion)
app.include_router(router_seguimiento)


@app.get("/health")
def salud():
    try:
        with conectar_bd() as conexion:
            conexion.execute("SELECT 1")
        return {"estado": "ok", "base_datos": "disponible"}
    except psycopg.Error as error:
        raise HTTPException(503, "No se pudo conectar con la base de datos") from error





# =====================================================

# MODELOS DE TRABAJADORES

# =====================================================



class TrabajadorCrear(BaseModel):

    nombre: str = Field(min_length=1, max_length=100)

    apellido: str = Field(min_length=1, max_length=100)

    rut: str | None = Field(default=None, max_length=12)





class TrabajadorActualizar(BaseModel):

    nombre: str = Field(min_length=1, max_length=100)

    apellido: str = Field(min_length=1, max_length=100)

    rut: str | None = Field(default=None, max_length=12)





# =====================================================

# MODELO DE PRODUCCIÓN

# =====================================================



class ProduccionCrear(BaseModel):

    id_trabajador: int = Field(gt=0)

    id_jornada: int = Field(gt=0)

    id_sector: int = Field(gt=0)

    id_labor: int = Field(gt=0)

    cantidad_kg: float = Field(ge=0)

    horas_trabajadas: float = Field(gt=0, le=24)





# =====================================================

# INICIO

# =====================================================



@app.get("/")

def inicio():

    return {

        "mensaje": "Bienvenido al sistema Dona Laura"

    }





# =====================================================

# CONSULTAR TRABAJADORES

# =====================================================



@app.get("/trabajadores")

def obtener_trabajadores():

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute("""

                    SELECT

                        id_trabajador,

                        nombre,

                        apellido,

                        rut,

                        estado

                    FROM trabajadores

                    ORDER BY id_trabajador

                """)



                registros = cursor.fetchall()



                return [

                    {

                        "id": fila[0],

                        "nombre": fila[1],

                        "apellido": fila[2],

                        "rut": fila[3],

                        "estado": fila[4]

                    }

                    for fila in registros

                ]



    except psycopg.Error as error:

        print(

            f"ERROR AL CONSULTAR TRABAJADORES: "

            f"{type(error).__name__}: {error}"

        )



        raise HTTPException(

            status_code=500,

            detail="Error al consultar los trabajadores"

        )





# =====================================================

# REGISTRAR TRABAJADORES

# =====================================================



@app.post("/trabajadores", status_code=201)

def crear_trabajador(trabajador: TrabajadorCrear):

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute(

                    """

                    INSERT INTO trabajadores (

                        nombre,

                        apellido,

                        rut

                    )

                    VALUES (%s, %s, %s)

                    RETURNING

                        id_trabajador,

                        nombre,

                        apellido,

                        rut,

                        estado

                    """,

                    (

                        trabajador.nombre.strip(),

                        trabajador.apellido.strip(),

                        trabajador.rut

                    )

                )



                fila = cursor.fetchone()



                return {

                    "id": fila[0],

                    "nombre": fila[1],

                    "apellido": fila[2],

                    "rut": fila[3],

                    "estado": fila[4]

                }



    except psycopg.errors.UniqueViolation:

        raise HTTPException(

            status_code=409,

            detail="Ya existe un trabajador con ese RUT"

        )



    except psycopg.Error as error:

        print(

            f"ERROR AL REGISTRAR TRABAJADOR: "

            f"{type(error).__name__}: {error}"

        )



        raise HTTPException(

            status_code=500,

            detail="No se pudo registrar el trabajador"

        )





# =====================================================

# ACTUALIZAR TRABAJADORES

# =====================================================



@app.put("/trabajadores/{id_trabajador}")

def actualizar_trabajador(

    id_trabajador: int,

    trabajador: TrabajadorActualizar

):

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute(

                    """

                    UPDATE trabajadores

                    SET

                        nombre = %s,

                        apellido = %s,

                        rut = %s

                    WHERE id_trabajador = %s

                    RETURNING

                        id_trabajador,

                        nombre,

                        apellido,

                        rut,

                        estado

                    """,

                    (

                        trabajador.nombre.strip(),

                        trabajador.apellido.strip(),

                        trabajador.rut,

                        id_trabajador

                    )

                )



                fila = cursor.fetchone()



                if fila is None:

                    raise HTTPException(

                        status_code=404,

                        detail="Trabajador no encontrado"

                    )



                return {

                    "id": fila[0],

                    "nombre": fila[1],

                    "apellido": fila[2],

                    "rut": fila[3],

                    "estado": fila[4]

                }



    except psycopg.errors.UniqueViolation:

        raise HTTPException(

            status_code=409,

            detail="Ya existe otro trabajador con ese RUT"

        )



    except psycopg.Error as error:

        print(

            f"ERROR AL ACTUALIZAR TRABAJADOR: "

            f"{type(error).__name__}: {error}"

        )



        raise HTTPException(

            status_code=500,

            detail="No se pudo actualizar el trabajador"

        )





# =====================================================

# DESACTIVAR TRABAJADORES

# =====================================================



@app.patch("/trabajadores/{id_trabajador}/desactivar")

def desactivar_trabajador(id_trabajador: int):

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute(

                    """

                    UPDATE trabajadores

                    SET estado = 'Inactivo'

                    WHERE id_trabajador = %s

                    RETURNING

                        id_trabajador,

                        nombre,

                        estado

                    """,

                    (id_trabajador,)

                )



                fila = cursor.fetchone()



                if fila is None:

                    raise HTTPException(

                        status_code=404,

                        detail="Trabajador no encontrado"

                    )



                return {

                    "id": fila[0],

                    "nombre": fila[1],

                    "estado": fila[2]

                }



    except psycopg.Error as error:

        print(

            f"ERROR AL DESACTIVAR TRABAJADOR: "

            f"{type(error).__name__}: {error}"

        )



        raise HTTPException(

            status_code=500,

            detail="No se pudo desactivar el trabajador"

        )





# =====================================================

# REGISTRAR COSECHAS

# =====================================================



@app.post("/produccion", status_code=201)

def registrar_produccion(produccion: ProduccionCrear):

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:



                # Verificar que el trabajador exista y esté activo

                cursor.execute(

                    """

                    SELECT estado

                    FROM trabajadores

                    WHERE id_trabajador = %s

                    """,

                    (produccion.id_trabajador,)

                )



                trabajador = cursor.fetchone()



                if trabajador is None:

                    raise HTTPException(

                        status_code=404,

                        detail="Trabajador no encontrado"

                    )



                if trabajador[0] != "Activo":

                    raise HTTPException(

                        status_code=400,

                        detail="El trabajador está inactivo"

                    )



                # La producción y el cierre comparten el bloqueo de la semana.
                cursor.execute(
                    "SELECT fecha FROM jornadas WHERE id_jornada = %s",
                    (produccion.id_jornada,)
                )
                jornada = cursor.fetchone()
                if jornada is None:
                    raise HTTPException(status_code=404, detail="Jornada no encontrada")
                exigir_semana_abierta(cursor, jornada[0])

                # Registrar la cosecha

                cursor.execute(

                    """

                    INSERT INTO produccion (

                        id_trabajador,

                        id_jornada,

                        id_sector,

                        id_labor,

                        cantidad_kg,

                        horas_trabajadas

                    )

                    VALUES (%s, %s, %s, %s, %s, %s)

                    RETURNING id_produccion

                    """,

                    (

                        produccion.id_trabajador,

                        produccion.id_jornada,

                        produccion.id_sector,

                        produccion.id_labor,

                        produccion.cantidad_kg,

                        produccion.horas_trabajadas

                    )

                )



                nuevo_id = cursor.fetchone()[0]



                productividad = round(

                    produccion.cantidad_kg

                    / produccion.horas_trabajadas,

                    2

                )



                return {

                    "mensaje": "Cosecha registrada correctamente",

                    "id_produccion": nuevo_id,

                    "cantidad_kg": produccion.cantidad_kg,

                    "horas_trabajadas": produccion.horas_trabajadas,

                    "productividad_kg_hora": productividad

                }



    except psycopg.errors.ForeignKeyViolation:

        raise HTTPException(

            status_code=400,

            detail="La jornada, el sector o la labor no existen"

        )



    except psycopg.Error as error:

        print(

            f"ERROR AL REGISTRAR COSECHA: "

            f"{type(error).__name__}: {error}"

        )



        raise HTTPException(

            status_code=500,

            detail="No se pudo registrar la cosecha"

        )





# =====================================================

# CONSULTAR PRODUCTIVIDAD

# =====================================================





@app.get("/productividad")

def consultar_productividad(

    fecha_inicio: str | None = None,

    fecha_fin: str | None = None,

    id_sector: int | None = None,

    id_labor: int | None = None

):

    try:

        condiciones = [

            "p.horas_trabajadas IS NOT NULL"

        ]

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



        where_sql = " AND ".join(condiciones)



        consulta = f"""

            SELECT

                t.id_trabajador,

                t.nombre,

                t.apellido,

                SUM(p.cantidad_kg) AS total_kg,

                SUM(p.horas_trabajadas) AS total_horas,

                ROUND(

                    SUM(p.cantidad_kg) /

                    NULLIF(SUM(p.horas_trabajadas), 0),

                    2

                ) AS kg_por_hora

            FROM produccion p

            JOIN trabajadores t

                ON p.id_trabajador = t.id_trabajador

            JOIN jornadas j

                ON p.id_jornada = j.id_jornada

            WHERE {where_sql}

            GROUP BY

                t.id_trabajador,

                t.nombre,

                t.apellido

            ORDER BY t.id_trabajador

        """



        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute(consulta, parametros)

                registros = cursor.fetchall()



                return [

                    {

                        "id_trabajador": registro[0],

                        "nombre": registro[1],

                        "apellido": registro[2],

                        "total_kg": float(registro[3]),

                        "total_horas": float(registro[4]),

                        "kg_por_hora": (

                            float(registro[5])

                            if registro[5] is not None

                            else None

                        )

                    }

                    for registro in registros

                ]



    except psycopg.Error as error:

        print(f"ERROR AL CONSULTAR PRODUCTIVIDAD: {error}")

        raise HTTPException(

            status_code=500,

            detail="No se pudo consultar la productividad"

        )







# OBTENER JORNADAS

@app.get("/jornadas")

def obtener_jornadas():

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute("""

                    SELECT id_jornada, fecha

                    FROM jornadas

                    ORDER BY fecha DESC

                """)



                registros = cursor.fetchall()



                return [

                    {

                        "id": registro[0],

                        "fecha": registro[1].isoformat()

                    }

                    for registro in registros

                ]



    except psycopg.Error as error:

        print(f"ERROR AL CONSULTAR JORNADAS: {error}")

        raise HTTPException(

            status_code=500,

            detail="No se pudieron consultar las jornadas"

        )





# OBTENER SECTORES

@app.get("/sectores")

def obtener_sectores():

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute("""

                    SELECT id_sector, nombre

                    FROM sectores

                    ORDER BY nombre

                """)



                registros = cursor.fetchall()



                return [

                    {

                        "id": registro[0],

                        "nombre": registro[1]

                    }

                    for registro in registros

                ]



    except psycopg.Error as error:

        print(f"ERROR AL CONSULTAR SECTORES: {error}")

        raise HTTPException(

            status_code=500,

            detail="No se pudieron consultar los sectores"

        )





# OBTENER LABORES

@app.get("/labores")

def obtener_labores():

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute("""

                    SELECT id_labor, nombre

                    FROM labores

                    ORDER BY nombre

                """)



                registros = cursor.fetchall()



                return [

                    {

                        "id": registro[0],

                        "nombre": registro[1]

                    }

                    for registro in registros

                ]



    except psycopg.Error as error:

        print(f"ERROR AL CONSULTAR LABORES: {error}")

        raise HTTPException(

            status_code=500,

            detail="No se pudieron consultar las labores"

        )



# MODELOS PARA REGISTRAR DATOS



class JornadaCrear(BaseModel):

    fecha: date

    observaciones: str | None = None





class SectorCrear(BaseModel):

    nombre: str = Field(min_length=1, max_length=100)

    descripcion: str | None = None





class LaborCrear(BaseModel):

    nombre: str = Field(min_length=1, max_length=100)

    descripcion: str | None = None





# CREAR JORNADA



@app.post("/jornadas", status_code=201)

def crear_jornada(jornada: JornadaCrear):

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute(

                    """

                    INSERT INTO jornadas (fecha, observaciones)

                    VALUES (%s, %s)

                    RETURNING id_jornada, fecha

                    """,

                    (jornada.fecha, jornada.observaciones)

                )



                registro = cursor.fetchone()



                return {

                    "id": registro[0],

                    "fecha": registro[1].isoformat()

                }



    except psycopg.errors.UniqueViolation:

        raise HTTPException(

            status_code=409,

            detail="Ya existe una jornada para esa fecha"

        )



    except psycopg.Error as error:

        print(f"ERROR AL CREAR JORNADA: {error}")

        raise HTTPException(

            status_code=500,

            detail="No se pudo crear la jornada"

        )





# CREAR SECTOR



@app.post("/sectores", status_code=201)

def crear_sector(sector: SectorCrear):

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute(

                    """

                    INSERT INTO sectores (nombre, descripcion)

                    VALUES (%s, %s)

                    RETURNING id_sector, nombre

                    """,

                    (sector.nombre.strip(), sector.descripcion)

                )



                registro = cursor.fetchone()



                return {

                    "id": registro[0],

                    "nombre": registro[1]

                }



    except psycopg.errors.UniqueViolation:

        raise HTTPException(

            status_code=409,

            detail="Ya existe un sector con ese nombre"

        )



    except psycopg.Error as error:

        print(f"ERROR AL CREAR SECTOR: {error}")

        raise HTTPException(

            status_code=500,

            detail="No se pudo crear el sector"

        )





# CREAR LABOR



@app.post("/labores", status_code=201)

def crear_labor(labor: LaborCrear):

    try:

        with conectar_bd() as conexion:

            with conexion.cursor() as cursor:

                cursor.execute(

                    """

                    INSERT INTO labores (nombre, descripcion)

                    VALUES (%s, %s)

                    RETURNING id_labor, nombre

                    """,

                    (labor.nombre.strip(), labor.descripcion)

                )



                registro = cursor.fetchone()



                return {

                    "id": registro[0],

                    "nombre": registro[1]

                }



    except psycopg.errors.UniqueViolation:

        raise HTTPException(

            status_code=409,

            detail="Ya existe una labor con ese nombre"

        )



    except psycopg.Error as error:

        print(f"ERROR AL CREAR LABOR: {error}")

        raise HTTPException(

            status_code=500,

            detail="No se pudo crear la labor"

        )



@app.post("/importacion/vista-previa")
async def vista_previa_excel(
    archivos: list[UploadFile] = File(..., description="Planillas Excel (todas las que se quieran)"),
):
    """Lee todas las planillas y devuelve una vista previa, sin guardar en BD.
    Las planillas que no se pueden leer se informan aparte y no frenan a las demás."""
    if not archivos or len(archivos) > 40:
        raise HTTPException(status_code=400, detail="Sube entre 1 y 40 planillas.")
    registros = []
    omitidos = []
    for archivo in archivos:
        nombre = archivo.filename or "archivo sin nombre"
        if not nombre.lower().endswith((".xlsx", ".xlsm")):
            omitidos.append({"archivo": nombre, "motivo": "No es un archivo Excel .xlsx."})
            continue
        # Leer como máximo 5 MB + 1 byte para rechazar archivos demasiado grandes.
        contenido = await archivo.read(5 * 1024 * 1024 + 1)
        await archivo.close()
        if len(contenido) > 5 * 1024 * 1024:
            omitidos.append({"archivo": nombre, "motivo": "Supera el límite de 5 MB."})
            continue
        try:
            leidos = leer_planilla(contenido, nombre)
        except Exception as error:
            print(f"ERROR AL LEER {nombre}: {type(error).__name__}: {error}")
            omitidos.append({"archivo": nombre, "motivo": "No se reconoció el formato de la planilla."})
            continue
        registros.extend(leidos)
    if not registros:
        detalle = " ".join(f"{o['archivo']}: {o['motivo']}" for o in omitidos[:3])
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo leer ninguna planilla. {detalle}".strip(),
        )
    # Orden cronológico: así las semanas se importan en el orden en que ocurrieron.
    registros.sort(key=lambda r: (r["fecha"], r["archivo"], r["numero_planilla"]))
    conteos = Counter(
        (registro["trabajador"].strip().casefold(), registro["fecha"])
        for registro in registros
    )
    for registro in registros:
        clave = (registro["trabajador"].strip().casefold(), registro["fecha"])
        registro["requiere_revision"] = conteos[clave] > 1
    return {
        "total_registros": len(registros),
        "registros_para_revisar": sum(
            registro["requiere_revision"] for registro in registros
        ),
        "total_kilos": round(sum(registro["kilos"] for registro in registros), 2),
        "archivos_omitidos": omitidos,
        "registros": registros,
    }


# =====================================================
# VALIDACIÓN DE IMPORTACIÓN (NO GUARDA EN LA BASE DE DATOS)
# =====================================================

from decimal import Decimal
import unicodedata


class SectorImportado(BaseModel):
    id_sector: int = Field(gt=0)
    kilos: Decimal = Field(gt=0)
    horas: Decimal = Field(gt=0, le=24)


class CosechaImportada(BaseModel):
    trabajador: str = Field(min_length=1)
    fecha: date
    kilos: Decimal = Field(gt=0)
    labor: str = Field(default="Cosecha", min_length=1)
    requiere_revision: bool = False
    sectores: list[SectorImportado] = Field(min_length=1)


class DecisionTrabajador(BaseModel):
    """Lo que decidió quien importa sobre un nombre de las planillas."""
    id_trabajador: int | None = Field(default=None, gt=0)  # es este trabajador ya registrado
    igual_a: str | None = Field(default=None, max_length=160)  # es el mismo que este otro nombre
    crear: bool = False  # es una persona nueva


class LoteImportacion(BaseModel):
    registros: list[CosechaImportada] = Field(min_length=1, max_length=5000)
    decisiones: dict[str, DecisionTrabajador] = Field(default_factory=dict, max_length=2000)
    crear_faltantes: bool = False  # crear jornadas y labores que aún no existen


class RegistroAnalisis(BaseModel):
    trabajador: str = Field(min_length=1, max_length=160)
    fecha: date
    labor: str = Field(default="Cosecha", min_length=1, max_length=100)


class SolicitudAnalisis(BaseModel):
    registros: list[RegistroAnalisis] = Field(min_length=1, max_length=5000)


def contexto_trabajadores(cursor, lote):
    """Trabajadores, equivalencias guardadas y decisiones del lote, listos para comparar."""
    cursor.execute("SELECT id_trabajador, nombre, apellido, estado FROM trabajadores")
    por_clave, estados, claves_bd = {}, {}, {}
    for id_trabajador, nombre, apellido, estado in cursor.fetchall():
        clave = clave_nombre(f"{nombre} {apellido}")
        por_clave.setdefault(clave, []).append(id_trabajador)
        estados[id_trabajador] = estado
        claves_bd[id_trabajador] = clave
    cursor.execute("SELECT alias, id_trabajador FROM alias_trabajadores")
    alias = {a: i for a, i in cursor.fetchall()}
    decisiones = {clave_nombre(nombre): d.model_dump() for nombre, d in lote.decisiones.items()}
    return por_clave, estados, claves_bd, alias, decisiones


def identidad_de(nombre, por_clave, alias, decisiones):
    """(resolución, identidad) de un nombre. La identidad distingue personas, no escrituras."""
    resolucion = resolver_trabajador(nombre, por_clave, alias, decisiones)
    if resolucion is None:
        return None, ("nombre", clave_nombre(nombre))
    return resolucion, (("id", resolucion[1]) if resolucion[0] == "id" else ("nuevo", resolucion[1]))


@app.post("/importacion/analizar")
def analizar_importacion(solicitud: SolicitudAnalisis):
    """Dice qué hace falta crear antes de guardar y qué nombres hay que confirmar.
    Solo lee; no modifica la base de datos."""
    cantidades = Counter(r.trabajador.strip() for r in solicitud.registros)
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id_trabajador, nombre, apellido, estado FROM trabajadores")
                trabajadores = cursor.fetchall()
                cursor.execute("SELECT alias, id_trabajador FROM alias_trabajadores")
                alias = {a: i for a, i in cursor.fetchall()}
                cursor.execute("SELECT fecha FROM jornadas")
                fechas_existentes = {f[0] for f in cursor.fetchall()}
                cursor.execute("SELECT nombre FROM labores")
                labores_existentes = {normalizar_nombre(f[0]) for f in cursor.fetchall()}
    except psycopg.Error as error:
        print(f"ERROR AL ANALIZAR IMPORTACIÓN: {type(error).__name__}: {error}")
        raise HTTPException(status_code=500, detail="No se pudo analizar la importación.") from error
    lista = analizar_trabajadores(dict(cantidades), trabajadores, alias)
    fechas = sorted({r.fecha for r in solicitud.registros} - fechas_existentes)
    labores = {}
    for r in solicitud.registros:
        if normalizar_nombre(r.labor) not in labores_existentes:
            labores.setdefault(normalizar_nombre(r.labor), r.labor.strip())
    return {
        "trabajadores": lista,
        "jornadas_nuevas": [f.isoformat() for f in fechas],
        "labores_nuevas": sorted(labores.values()),
    }


def normalizar_nombre(valor: str) -> str:
    sin_tildes = "".join(
        caracter for caracter in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(caracter)
    )
    return " ".join(sin_tildes.casefold().split())


@app.post("/importacion/validar")
def validar_importacion(lote: LoteImportacion):
    """Comprueba registros contra PostgreSQL. No realiza INSERT ni UPDATE."""
    resultados = []
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                por_clave, estados, _claves_bd, alias, decisiones = contexto_trabajadores(cursor, lote)
                cursor.execute("SELECT id_sector FROM sectores")
                sectores_validos = {fila[0] for fila in cursor.fetchall()}
                cursor.execute("SELECT id_labor, nombre FROM labores")
                labores = {}
                for id_labor, nombre in cursor.fetchall():
                    labores.setdefault(normalizar_nombre(nombre), []).append(id_labor)
                cursor.execute("SELECT id_jornada, fecha FROM jornadas")
                jornadas = {}
                for id_jornada, fecha in cursor.fetchall():
                    jornadas.setdefault(fecha, []).append(id_jornada)
                identidades = [identidad_de(r.trabajador, por_clave, alias, decisiones) for r in lote.registros]
                claves_lote = Counter(
                    (identidades[i][1], r.fecha, normalizar_nombre(r.labor))
                    for i, r in enumerate(lote.registros)
                )
                for indice, registro in enumerate(lote.registros):
                    errores = []
                    advertencias = []
                    resolucion, identidad = identidades[indice]
                    clave = (identidad, registro.fecha, normalizar_nombre(registro.labor))
                    id_trabajador = None
                    if resolucion is None:
                        candidatos = por_clave.get(clave_nombre(registro.trabajador), [])
                        errores.append(
                            "Nombre ambiguo: varios trabajadores coinciden." if len(candidatos) > 1
                            else "Trabajador no encontrado; indica si es nuevo o el mismo que otro."
                        )
                    elif resolucion[0] == "id":
                        id_trabajador = resolucion[1]
                        if id_trabajador not in estados:
                            errores.append("Trabajador no encontrado.")
                        elif estados[id_trabajador] != "Activo":
                            errores.append("El trabajador está inactivo.")
                    ids_labor = labores.get(clave[2], [])
                    if len(ids_labor) > 1 or (not ids_labor and not lote.crear_faltantes):
                        errores.append("La labor no existe o su nombre es ambiguo.")
                    ids_jornada = jornadas.get(registro.fecha, [])
                    if len(ids_jornada) > 1 or (not ids_jornada and not lote.crear_faltantes):
                        errores.append("Falta la jornada para esa fecha o está duplicada.")
                    ids_sector = [s.id_sector for s in registro.sectores]
                    if len(ids_sector) != len(set(ids_sector)):
                        errores.append("Hay sectores repetidos en la distribución.")
                    if any(id_sector not in sectores_validos for id_sector in ids_sector):
                        errores.append("Uno o más sectores no existen.")
                    if sum((s.kilos for s in registro.sectores), Decimal(0)).quantize(Decimal('0.01')) != registro.kilos.quantize(Decimal('0.01')):
                        errores.append("Los kilos distribuidos no coinciden con el Excel.")
                    if sum((s.horas for s in registro.sectores), Decimal(0)) > 24:
                        errores.append("Las horas totales superan las 24 horas.")
                    if claves_lote[clave] > 1 or registro.requiere_revision:
                        advertencias.append("Posible duplicado entre planillas; revisión manual obligatoria.")
                    if id_trabajador is not None and len(ids_labor) == 1:
                        cursor.execute("""
                            SELECT COUNT(*) FROM produccion p
                            JOIN jornadas j ON j.id_jornada = p.id_jornada
                            WHERE p.id_trabajador = %s AND j.fecha = %s AND p.id_labor = %s
                        """, (id_trabajador, registro.fecha, ids_labor[0]))
                        if cursor.fetchone()[0] > 0:
                            advertencias.append("Ya hay producción registrada para este trabajador, fecha y labor.")
                    resultados.append({
                        "indice": indice,
                        "trabajador": registro.trabajador,
                        "fecha": registro.fecha.isoformat(),
                        "estado": "error" if errores else "revision" if advertencias else "listo",
                        "errores": errores,
                        "advertencias": advertencias,
                        "id_trabajador": id_trabajador,
                        "id_jornada": ids_jornada[0] if len(ids_jornada) == 1 else None,
                        "id_labor": ids_labor[0] if len(ids_labor) == 1 else None,
                    })
    except psycopg.Error as error:
        print(f"ERROR AL VALIDAR IMPORTACIÓN: {type(error).__name__}: {error}")
        raise HTTPException(status_code=500, detail="No se pudo validar la importación.")
    return {
        "total": len(resultados),
        "listos": sum(r["estado"] == "listo" for r in resultados),
        "para_revision": sum(r["estado"] == "revision" for r in resultados),
        "con_errores": sum(r["estado"] == "error" for r in resultados),
        "se_guardo_en_bd": False,
        "resultados": resultados,
    }


# =====================================================
# GUARDADO TRANSACCIONAL DE COSECHAS VALIDADAS
# =====================================================
# Una importación solo acepta registros sin advertencias ni errores.
# Se vuelve a validar en la misma transacción antes de insertar.

@app.post("/importacion/guardar", status_code=201)
def guardar_importacion(lote: LoteImportacion):
    if any(r.requiere_revision for r in lote.registros):
        raise HTTPException(409, "El lote contiene registros marcados para revisión.")
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                # Serializa importaciones simultáneas de este módulo.
                cursor.execute("SELECT pg_advisory_xact_lock(20260925, 1)")
                # Orden estable para evitar interbloqueos entre lotes de varias semanas.
                for semana in sorted({lunes_de(r.fecha) for r in lote.registros}):
                    exigir_semana_abierta(cursor, semana)
                por_clave, estados, claves_bd, alias, decisiones = contexto_trabajadores(cursor, lote)
                identidades = [identidad_de(r.trabajador, por_clave, alias, decisiones) for r in lote.registros]
                claves = [(identidades[i][1], r.fecha, normalizar_nombre(r.labor))
                          for i, r in enumerate(lote.registros)]
                if len(set(claves)) != len(claves):
                    raise HTTPException(409, "El lote contiene al mismo trabajador, fecha y labor más de una vez.")
                cursor.execute("SELECT id_jornada, fecha FROM jornadas")
                jornadas = {}
                for id_jornada, fecha in cursor.fetchall():
                    jornadas.setdefault(fecha, []).append(id_jornada)
                cursor.execute("SELECT id_labor, nombre FROM labores")
                labores = {}
                for id_labor, nombre in cursor.fetchall():
                    labores.setdefault(normalizar_nombre(nombre), []).append(id_labor)
                cursor.execute("SELECT id_sector FROM sectores")
                sectores_validos = {r[0] for r in cursor.fetchall()}

                # Lo que falta se crea dentro de la misma transacción: si algo falla, no queda nada.
                creados = {"trabajadores": 0, "jornadas": 0, "labores": 0}
                if lote.crear_faltantes:
                    for r in lote.registros:
                        if r.fecha not in jornadas:
                            cursor.execute("INSERT INTO jornadas (fecha) VALUES (%s) RETURNING id_jornada", (r.fecha,))
                            jornadas[r.fecha] = [cursor.fetchone()[0]]
                            creados["jornadas"] += 1
                        clave_labor = normalizar_nombre(r.labor)
                        if clave_labor not in labores:
                            cursor.execute("INSERT INTO labores (nombre) VALUES (%s) RETURNING id_labor", (r.labor.strip(),))
                            labores[clave_labor] = [cursor.fetchone()[0]]
                            creados["labores"] += 1
                nombre_de_clave = {}
                for r in lote.registros:
                    nombre_de_clave.setdefault(clave_nombre(r.trabajador), r.trabajador)
                nuevos = {}
                for resolucion, _ in identidades:
                    if resolucion and resolucion[0] == "crear" and resolucion[1] not in nuevos:
                        nombre, apellido = partir_nombre(nombre_de_clave.get(resolucion[1], resolucion[1]))
                        cursor.execute(
                            "INSERT INTO trabajadores (nombre, apellido) VALUES (%s, %s) RETURNING id_trabajador",
                            (nombre, apellido),
                        )
                        nuevos[resolucion[1]] = cursor.fetchone()[0]
                        estados[nuevos[resolucion[1]]] = "Activo"
                        claves_bd[nuevos[resolucion[1]]] = clave_nombre(f"{nombre} {apellido}")
                        creados["trabajadores"] += 1

                preparados = []
                problemas = []
                equivalencias = {}
                for indice, r in enumerate(lote.registros, start=1):
                    fallas = []
                    resolucion = identidades[indice - 1][0]
                    trabajador_id = None
                    if resolucion is None:
                        fallas.append("Trabajador inexistente, ambiguo o inactivo")
                    else:
                        trabajador_id = nuevos[resolucion[1]] if resolucion[0] == "crear" else resolucion[1]
                        if estados.get(trabajador_id) != "Activo":
                            fallas.append("Trabajador inexistente, ambiguo o inactivo")
                    ids_jornada = jornadas.get(r.fecha, [])
                    if len(ids_jornada) != 1:
                        fallas.append("Jornada inexistente o duplicada")
                    ids_labor = labores.get(normalizar_nombre(r.labor), [])
                    if len(ids_labor) != 1:
                        fallas.append("Labor inexistente o ambigua")
                    ids_sector = [s.id_sector for s in r.sectores]
                    if len(set(ids_sector)) != len(ids_sector) or any(s not in sectores_validos for s in ids_sector):
                        fallas.append("Sectores repetidos o inexistentes")
                    if sum((s.kilos for s in r.sectores), Decimal(0)).quantize(Decimal("0.01")) != r.kilos.quantize(Decimal("0.01")):
                        fallas.append("Kilos distribuidos distintos del Excel")
                    if sum((s.horas for s in r.sectores), Decimal(0)) > 24:
                        fallas.append("Más de 24 horas distribuidas")
                    if not fallas:
                        jornada_id = ids_jornada[0]
                        labor_id = ids_labor[0]
                        cursor.execute("""
                            SELECT 1 FROM produccion
                            WHERE id_trabajador = %s AND id_jornada = %s AND id_labor = %s
                            LIMIT 1
                        """, (trabajador_id, jornada_id, labor_id))
                        if cursor.fetchone():
                            fallas.append("Ya existe producción para ese trabajador, jornada y labor")
                    if fallas:
                        problemas.append({"registro": indice, "trabajador": r.trabajador, "motivos": fallas})
                    else:
                        preparados.append((trabajador_id, jornada_id, labor_id, r))
                        escrito = clave_nombre(r.trabajador)
                        if escrito != claves_bd.get(trabajador_id) and alias.get(escrito) != trabajador_id:
                            equivalencias[escrito] = trabajador_id
                if problemas:
                    # Se revierte todo, incluso lo recién creado: lote íntegramente rechazado.
                    raise HTTPException(status_code=409, detail={
                        "mensaje": "No se guardó nada; revisa los registros indicados.",
                        "problemas": problemas[:30],
                    })
                # Recuerda cómo escriben el nombre las planillas para no volver a preguntar.
                for escrito, id_trabajador in equivalencias.items():
                    cursor.execute("""
                        INSERT INTO alias_trabajadores (alias, id_trabajador) VALUES (%s, %s)
                        ON CONFLICT (alias) DO UPDATE SET id_trabajador = EXCLUDED.id_trabajador
                    """, (escrito[:160], id_trabajador))
                ids_creados = []
                for trabajador_id, jornada_id, labor_id, r in preparados:
                    for sector in r.sectores:
                        cursor.execute("""
                            INSERT INTO produccion
                                (id_trabajador, id_jornada, id_sector, id_labor,
                                 cantidad_kg, horas_trabajadas)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id_produccion
                        """, (trabajador_id, jornada_id, sector.id_sector, labor_id,
                              sector.kilos, sector.horas))
                        ids_creados.append(cursor.fetchone()[0])
                # El context manager de psycopg confirma al salir sin errores.
                return {
                    "mensaje": "Cosechas guardadas correctamente",
                    "registros_excel": len(preparados),
                    "filas_produccion": len(ids_creados),
                    "total_kilos": float(sum((r.kilos for _, _, _, r in preparados), Decimal(0))),
                    "ids_produccion": ids_creados,
                    "trabajadores_creados": creados["trabajadores"],
                    "jornadas_creadas": creados["jornadas"],
                    "labores_creadas": creados["labores"],
                }
    except psycopg.Error as error:
        print(f"ERROR AL GUARDAR IMPORTACIÓN: {type(error).__name__}: {error}")
        raise HTTPException(500, "No se pudo guardar la importación; no se confirmó el lote.") from error


# =====================================================
# ANÁLISIS IA DE PRODUCTIVIDAD
# =====================================================

@app.get("/ia/analisis")
def obtener_analisis_ia(fuente: Literal["operacion", "historico"] = "operacion"):
    """Analiza el histórico de cosecha de paltas con modelos de IA.

    Agrupa patrones de producción, detecta registros atípicos y genera una
    estimación orientativa para la próxima jornada. No toma decisiones laborales
    ni modifica registros de producción.
    """
    try:
        from ia.modelo_productividad import generar_analisis
        return generar_analisis(fuente=fuente)
    except ModuleNotFoundError as error:
        print(f"DEPENDENCIA IA FALTANTE: {error}")
        raise HTTPException(
            status_code=503,
            detail=(
                "Faltan dependencias de IA. Ejecuta: "
                ".\\.venv\\Scripts\\python.exe -m pip install -r requirements_ia.txt"
            ),
        ) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        print(f"ERROR EN ANÁLISIS IA: {type(error).__name__}: {error}")
        raise HTTPException(
            status_code=500,
            detail="No se pudo generar el análisis IA.",
        ) from error

# =====================================================
# ASISTENTE AGRÍCOLA IA
# =====================================================

class PreguntaAsistenteIA(BaseModel):
    pregunta: str = Field(min_length=2, max_length=500)


@app.post("/ia/chat")
def chat_asistente_ia(datos: PreguntaAsistenteIA):
    try:
        from ia.asistente import responder_chat

        return responder_chat(datos.pregunta)

    except Exception as error:
        print(
            f"ERROR EN ASISTENTE IA: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="No se pudo procesar la pregunta del asistente IA."
        ) from error
        # =====================================================
# AGENTE INTELIGENTE LLM
# =====================================================

class MensajeAgenteLLM(BaseModel):
    autor: str
    texto: str


class ConsultaAgenteLLM(BaseModel):
    pregunta: str = Field(
        min_length=2,
        max_length=2000
    )

    historial: list[MensajeAgenteLLM] = Field(
        default_factory=list,
        max_length=20
    )


@app.post("/ia/agente")
def agente_inteligente(datos: ConsultaAgenteLLM):
    try:
        # Permite completar la configuración sin reiniciar la aplicación.
        load_dotenv(BASE_DIR / ".env", override=True)
        clave = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not clave or clave == "escribir_la_clave_de_openai":
            raise HTTPException(
                status_code=503,
                detail=(
                    "El asistente avanzado aún no está configurado. "
                    "Falta configurar OPENAI_API_KEY en el archivo .env del backend. "
                    "El resto de la aplicación sigue disponible."
                ),
            )
        from ia.agente_llm import responder_agente

        historial = [
            {
                "autor": mensaje.autor,
                "texto": mensaje.texto
            }
            for mensaje in datos.historial
        ]

        return responder_agente(
            datos.pregunta,
            historial
        )

    except HTTPException:
        raise
    except ModuleNotFoundError as error:
        print(f"DEPENDENCIA DEL ASISTENTE FALTANTE: {error.name}")
        raise HTTPException(
            status_code=503,
            detail="Faltan dependencias del asistente. Instala requirements_ia.txt en el backend.",
        ) from error
    except Exception as error:
        print(
            f"ERROR EN AGENTE LLM: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "No se pudo procesar la consulta "
                "del asistente inteligente."
            )
        ) from error

