

import psycopg



from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from collections import Counter

from datetime import date

from fastapi import File, UploadFile

from importador import leer_planilla



from database import conectar_bd





# =====================================================

# CONFIGURACIÓN DE FASTAPI

# =====================================================



app = FastAPI(

    title="Sistema de Gestion Dona Laura",

    description="API de gestion administrativa agricola",

    version="0.1.0"

)



# Permitir la conexión desde nuestro frontend React

app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        "http://localhost:5173",

        "http://127.0.0.1:5173"

    ],

    allow_credentials=False,

    allow_methods=["GET", "POST", "PUT", "PATCH"

],

    allow_headers=["*"],

)





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

    archivo_1: UploadFile = File(..., description="Primera planilla Excel"),

    archivo_2: UploadFile | None = File(None, description="Segunda planilla Excel (opcional)"),

):

    """Lee una o dos planillas y devuelve una vista previa, sin guardar en BD."""

    registros = []

    archivos = [archivo_1]

    if archivo_2 is not None:

        archivos.append(archivo_2)



    for archivo in archivos:

        nombre = archivo.filename or "archivo sin nombre"

        if not nombre.lower().endswith(".xlsx"):

            raise HTTPException(

                status_code=400,

                detail=f"{nombre}: selecciona un archivo Excel .xlsx.",

            )



        # Leer como máximo 5 MB + 1 byte para rechazar archivos demasiado grandes.

        contenido = await archivo.read(5 * 1024 * 1024 + 1)

        await archivo.close()

        if len(contenido) > 5 * 1024 * 1024:

            raise HTTPException(

                status_code=400,

                detail=f"{nombre} supera el límite de 5 MB.",

            )



        try:

            registros.extend(leer_planilla(contenido, nombre))

        except Exception as error:

            print(f"ERROR AL LEER {nombre}: {type(error).__name__}: {error}")

            raise HTTPException(

                status_code=400,

                detail=f"No se pudo leer {nombre}. Revisa el formato de la planilla.",

            ) from error



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


class LoteImportacion(BaseModel):
    registros: list[CosechaImportada] = Field(min_length=1, max_length=2000)


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
    claves_lote = Counter(
        (normalizar_nombre(r.trabajador), r.fecha, normalizar_nombre(r.labor))
        for r in lote.registros
    )

    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT id_trabajador, nombre, apellido, estado FROM trabajadores")
                trabajadores = cursor.fetchall()
                por_nombre = {}
                for id_trabajador, nombre, apellido, estado in trabajadores:
                    clave = normalizar_nombre(f"{nombre} {apellido}")
                    por_nombre.setdefault(clave, []).append((id_trabajador, estado))

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

                for indice, registro in enumerate(lote.registros):
                    errores = []
                    advertencias = []
                    clave = (normalizar_nombre(registro.trabajador), registro.fecha,
                             normalizar_nombre(registro.labor))
                    candidatos = por_nombre.get(clave[0], [])
                    id_trabajador = None
                    if not candidatos:
                        errores.append("Trabajador no encontrado; revisar nombre en Excel.")
                    elif len(candidatos) > 1:
                        errores.append("Nombre ambiguo: varios trabajadores coinciden.")
                    else:
                        id_trabajador, estado = candidatos[0]
                        if estado != "Activo":
                            errores.append("El trabajador está inactivo.")

                    ids_labor = labores.get(clave[2], [])
                    if len(ids_labor) != 1:
                        errores.append("La labor no existe o su nombre es ambiguo.")
                    ids_jornada = jornadas.get(registro.fecha, [])
                    if len(ids_jornada) != 1:
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

    claves = [(normalizar_nombre(r.trabajador), r.fecha, normalizar_nombre(r.labor))
              for r in lote.registros]
    if len(set(claves)) != len(claves):
        raise HTTPException(409, "El lote contiene al mismo trabajador, fecha y labor más de una vez.")

    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                # Serializa importaciones simultáneas de este módulo.
                cursor.execute("SELECT pg_advisory_xact_lock(20260925, 1)")
                cursor.execute("SELECT id_trabajador, nombre, apellido, estado FROM trabajadores")
                por_nombre = {}
                for id_trabajador, nombre, apellido, estado in cursor.fetchall():
                    por_nombre.setdefault(normalizar_nombre(f"{nombre} {apellido}"), []).append((id_trabajador, estado))
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

                preparados = []
                problemas = []
                for indice, r in enumerate(lote.registros, start=1):
                    fallas = []
                    candidatos = por_nombre.get(normalizar_nombre(r.trabajador), [])
                    if len(candidatos) != 1 or candidatos[0][1] != "Activo":
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
                        trabajador_id = candidatos[0][0]
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

                if problemas:
                    # No se ejecutó ningún INSERT: lote íntegramente rechazado.
                    raise HTTPException(status_code=409, detail={
                        "mensaje": "No se guardó nada; revisa los registros indicados.",
                        "problemas": problemas[:30],
                    })

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
                }
    except psycopg.Error as error:
        print(f"ERROR AL GUARDAR IMPORTACIÓN: {type(error).__name__}: {error}")
        raise HTTPException(500, "No se pudo guardar la importación; no se confirmó el lote.") from error


# =====================================================
# ANÁLISIS IA DE PRODUCTIVIDAD
# =====================================================

@app.get("/ia/analisis")
def obtener_analisis_ia():
    """Analiza el histórico de cosecha de paltas con modelos de IA.

    Agrupa patrones de producción, detecta registros atípicos y genera una
    estimación orientativa para la próxima jornada. No toma decisiones laborales
    ni modifica registros de producción.
    """
    try:
        from ia.modelo_productividad import generar_analisis
        return generar_analisis()
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

