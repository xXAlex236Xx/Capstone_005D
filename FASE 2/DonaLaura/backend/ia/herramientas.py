from difflib import SequenceMatcher
from functools import lru_cache
import unicodedata

from database import conectar_bd
from ia.modelo_productividad import generar_analisis


# =====================================================
# UTILIDADES
# =====================================================

def normalizar(texto: str) -> str:
    texto = str(texto or "").strip().lower()

    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )


@lru_cache(maxsize=1)
def obtener_analisis_historico():
    return generar_analisis()


def buscar_trabajador_historico(nombre: str):
    analisis = obtener_analisis_historico()
    trabajadores = analisis.get("trabajadores", [])

    objetivo = normalizar(nombre)

    if not objetivo:
        return None

    for trabajador in trabajadores:
        if normalizar(trabajador.get("trabajador")) == objetivo:
            return trabajador

    for trabajador in trabajadores:
        nombre_actual = normalizar(
            trabajador.get("trabajador")
        )

        if (
            objetivo in nombre_actual
            or nombre_actual in objetivo
        ):
            return trabajador

    mejor = None
    mejor_puntaje = 0

    for trabajador in trabajadores:
        nombre_actual = normalizar(
            trabajador.get("trabajador")
        )

        puntaje = SequenceMatcher(
            None,
            objetivo,
            nombre_actual
        ).ratio()

        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor = trabajador

    if mejor_puntaje >= 0.55:
        return mejor

    return None


def trabajador_compacto(trabajador):
    return {
        "trabajador":
            trabajador.get("trabajador"),

        "dias_trabajados":
            trabajador.get("dias_trabajados"),

        "total_kg":
            trabajador.get("total_kg"),

        "promedio_kg_dia":
            trabajador.get("promedio_kg_dia"),

        "mediana_kg":
            trabajador.get("mediana_kg"),

        "variabilidad_pct":
            trabajador.get("variabilidad_pct"),

        "tendencia":
            trabajador.get("tendencia"),

        "tendencia_pct":
            trabajador.get("tendencia_pct"),

        "ultimo_kg":
            trabajador.get("ultimo_kg"),

        "ultimo_registro":
            trabajador.get("ultimo_registro"),

        "perfil_ia":
            trabajador.get("perfil_ia"),

        "prediccion_proxima_jornada_kg":
            trabajador.get(
                "prediccion_proxima_jornada_kg"
            ),

        "recomendacion":
            trabajador.get("recomendacion")
    }


# =====================================================
# RESUMEN EMPRESA
# =====================================================

def resumen_empresa():
    analisis = obtener_analisis_historico()

    resultado_bd = {}

    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        COUNT(*),
                        COUNT(*) FILTER (
                            WHERE LOWER(estado) = 'activo'
                        ),
                        COUNT(*) FILTER (
                            WHERE LOWER(estado) = 'inactivo'
                        )
                    FROM trabajadores
                """)

                fila = cursor.fetchone()

                resultado_bd = {
                    "trabajadores_total":
                        fila[0],

                    "trabajadores_activos":
                        fila[1],

                    "trabajadores_inactivos":
                        fila[2]
                }

                cursor.execute("""
                    SELECT
                        COUNT(*),
                        COALESCE(
                            SUM(cantidad_kg),
                            0
                        ),
                        COUNT(
                            DISTINCT id_trabajador
                        )
                    FROM produccion
                """)

                fila = cursor.fetchone()

                resultado_bd[
                    "registros_produccion"
                ] = fila[0]

                resultado_bd[
                    "kilos_registrados"
                ] = float(fila[1])

                resultado_bd[
                    "trabajadores_con_produccion"
                ] = fila[2]

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM jornadas
                """)

                resultado_bd["jornadas"] = (
                    cursor.fetchone()[0]
                )

    except Exception as error:
        resultado_bd = {
            "error": (
                f"No se pudo consultar PostgreSQL: "
                f"{type(error).__name__}: {error}"
            )
        }

    return {
        "postgreSQL": resultado_bd,

        "historico_ia": {
            "periodo":
                analisis.get("periodo"),

            "registros_historicos":
                analisis.get(
                    "registros_historicos"
                ),

            "trabajadores_historicos":
                analisis.get(
                    "trabajadores_historicos"
                ),

            "trabajadores_analizados_ia":
                analisis.get(
                    "trabajadores_analizados_ia"
                ),

            "trabajadores_con_prediccion":
                analisis.get(
                    "trabajadores_con_prediccion"
                )
        },

        "modelo_predictivo":
            analisis.get("modelo_predictivo"),

        "advertencias":
            analisis.get(
                "advertencias",
                []
            )
    }


# =====================================================
# LISTAR TRABAJADORES
# =====================================================

def listar_trabajadores(
    estado: str = "Todos"
):
    estado_normalizado = normalizar(estado)

    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:

                consulta = """
                    SELECT
                        id_trabajador,
                        nombre,
                        apellido,
                        rut,
                        estado
                    FROM trabajadores
                """

                parametros = []

                if estado_normalizado == "activo":
                    consulta += """
                        WHERE LOWER(estado) = 'activo'
                    """

                elif estado_normalizado == "inactivo":
                    consulta += """
                        WHERE LOWER(estado) = 'inactivo'
                    """

                consulta += """
                    ORDER BY
                        nombre,
                        apellido
                """

                cursor.execute(
                    consulta,
                    parametros
                )

                trabajadores = []

                for fila in cursor.fetchall():

                    trabajadores.append({
                        "id":
                            fila[0],

                        "nombre":
                            fila[1],

                        "apellido":
                            fila[2],

                        "rut":
                            fila[3],

                        "estado":
                            fila[4]
                    })

                return {
                    "fuente":
                        "PostgreSQL",

                    "trabajadores":
                        trabajadores
                }

    except Exception as error:
        return {
            "error": (
                f"No se pudieron consultar "
                f"los trabajadores: "
                f"{type(error).__name__}: "
                f"{error}"
            )
        }


# =====================================================
# ANALIZAR TRABAJADOR
# =====================================================

def analizar_trabajador(nombre: str):
    trabajador = buscar_trabajador_historico(
        nombre
    )

    if trabajador is None:
        return {
            "encontrado": False,

            "mensaje": (
                f"No encontré un trabajador "
                f"que coincida con '{nombre}'."
            )
        }

    return {
        "encontrado": True,
        "fuente": "Histórico Excel + IA",

        "datos":
            trabajador_compacto(
                trabajador
            )
    }


# =====================================================
# COMPARAR TRABAJADORES
# =====================================================

def comparar_trabajadores(
    nombres: list[str]
):
    resultados = []

    for nombre in nombres[:5]:

        trabajador = (
            buscar_trabajador_historico(
                nombre
            )
        )

        if trabajador is None:
            resultados.append({
                "buscado": nombre,
                "encontrado": False
            })

        else:
            resultados.append({
                "buscado": nombre,
                "encontrado": True,

                "datos":
                    trabajador_compacto(
                        trabajador
                    )
            })

    return {
        "fuente":
            "Histórico Excel + IA",

        "comparacion":
            resultados
    }


# =====================================================
# RANKING
# =====================================================

def ranking_trabajadores(
    criterio: str = "promedio",
    limite: int = 5
):
    analisis = obtener_analisis_historico()

    trabajadores = [
        trabajador
        for trabajador
        in analisis.get(
            "trabajadores",
            []
        )
        if trabajador.get(
            "dias_trabajados",
            0
        ) >= 4
    ]

    limite = max(
        1,
        min(
            int(limite),
            10
        )
    )

    criterio_normalizado = (
        normalizar(criterio)
    )

    if criterio_normalizado in [
        "total",
        "kilos",
        "produccion total"
    ]:
        campo = "total_kg"
        reverse = True

    elif criterio_normalizado in [
        "prediccion",
        "estimacion"
    ]:
        trabajadores = [
            trabajador
            for trabajador
            in trabajadores
            if trabajador.get(
                "prediccion_proxima_jornada_kg"
            ) is not None
        ]

        campo = (
            "prediccion_proxima_jornada_kg"
        )

        reverse = True

    elif criterio_normalizado in [
        "baja",
        "tendencia baja",
        "tendencia a la baja"
    ]:
        trabajadores = [
            trabajador
            for trabajador
            in trabajadores
            if normalizar(
                trabajador.get(
                    "tendencia"
                )
            ) == "a la baja"
        ]

        campo = "tendencia_pct"
        reverse = False

    elif criterio_normalizado in [
        "alza",
        "tendencia alza",
        "tendencia al alza"
    ]:
        trabajadores = [
            trabajador
            for trabajador
            in trabajadores
            if normalizar(
                trabajador.get(
                    "tendencia"
                )
            ) == "al alza"
        ]

        campo = "tendencia_pct"
        reverse = True

    else:
        campo = "promedio_kg_dia"
        reverse = True

    ordenados = sorted(
        trabajadores,
        key=lambda trabajador: (
            trabajador.get(campo)
            or 0
        ),
        reverse=reverse
    )

    return {
        "criterio":
            criterio_normalizado,

        "resultados": [
            trabajador_compacto(
                trabajador
            )
            for trabajador
            in ordenados[:limite]
        ]
    }


# =====================================================
# REGISTROS ATIPICOS
# =====================================================

def registros_atipicos(
    nombre: str | None = None,
    limite: int = 10
):
    analisis = obtener_analisis_historico()

    registros = analisis.get(
        "registros_atipicos",
        []
    )

    limite = max(
        1,
        min(
            int(limite),
            20
        )
    )

    if nombre:

        trabajador = (
            buscar_trabajador_historico(
                nombre
            )
        )

        if trabajador:
            nombre_real = (
                trabajador.get(
                    "trabajador"
                )
            )

            registros = [
                registro
                for registro
                in registros
                if registro.get(
                    "trabajador"
                ) == nombre_real
            ]

    return {
        "cantidad":
            len(registros),

        "registros":
            registros[:limite]
    }


# =====================================================
# PRODUCCION POSTGRESQL
# =====================================================

def consultar_produccion_bd(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    nombre: str | None = None
):
    condiciones = ["1 = 1"]
    parametros = []

    if fecha_inicio:
        condiciones.append(
            "j.fecha >= %s"
        )

        parametros.append(
            fecha_inicio
        )

    if fecha_fin:
        condiciones.append(
            "j.fecha <= %s"
        )

        parametros.append(
            fecha_fin
        )

    if nombre:
        condiciones.append("""
            CONCAT_WS(
                ' ',
                t.nombre,
                t.apellido
            ) ILIKE %s
        """)

        parametros.append(
            f"%{nombre}%"
        )

    where_sql = " AND ".join(
        condiciones
    )

    consulta = f"""
        SELECT
            t.id_trabajador,
            t.nombre,
            t.apellido,

            COUNT(
                p.id_produccion
            ),

            COALESCE(
                SUM(
                    p.cantidad_kg
                ),
                0
            ),

            MIN(j.fecha),
            MAX(j.fecha)

        FROM produccion p

        JOIN trabajadores t
            ON t.id_trabajador =
               p.id_trabajador

        JOIN jornadas j
            ON j.id_jornada =
               p.id_jornada

        WHERE {where_sql}

        GROUP BY
            t.id_trabajador,
            t.nombre,
            t.apellido

        ORDER BY
            SUM(
                p.cantidad_kg
            ) DESC
    """

    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:

                cursor.execute(
                    consulta,
                    parametros
                )

                resultados = []

                for fila in cursor.fetchall():

                    resultados.append({
                        "id_trabajador":
                            fila[0],

                        "trabajador":
                            f"{fila[1]} {fila[2]}",

                        "registros":
                            fila[3],

                        "total_kg":
                            float(
                                fila[4]
                            ),

                        "desde":
                            (
                                fila[5].isoformat()
                                if fila[5]
                                else None
                            ),

                        "hasta":
                            (
                                fila[6].isoformat()
                                if fila[6]
                                else None
                            )
                    })

                return {
                    "fuente":
                        "PostgreSQL",

                    "filtros": {
                        "fecha_inicio":
                            fecha_inicio,

                        "fecha_fin":
                            fecha_fin,

                        "nombre":
                            nombre
                    },

                    "total_kg":
                        round(
                            sum(
                                r["total_kg"]
                                for r
                                in resultados
                            ),
                            2
                        ),

                    "trabajadores":
                        resultados
                }

    except Exception as error:
        return {
            "error": (
                f"No se pudo consultar "
                f"la producción: "
                f"{type(error).__name__}: "
                f"{error}"
            )
        }


# =====================================================
# SIMULAR PAGO HISTORICO
# =====================================================

def simular_pago_historico(
    precio_kilo: float,
    nombre: str | None = None
):
    analisis = obtener_analisis_historico()

    if precio_kilo <= 0:
        return {
            "error":
                "El precio por kilo debe "
                "ser mayor que 0."
        }

    if nombre:

        trabajador = (
            buscar_trabajador_historico(
                nombre
            )
        )

        if trabajador is None:
            return {
                "error": (
                    f"No encontré al trabajador "
                    f"'{nombre}'."
                )
            }

        kilos = float(
            trabajador.get(
                "total_kg",
                0
            )
        )

        return {
            "tipo":
                "simulacion_historica",

            "trabajador":
                trabajador.get(
                    "trabajador"
                ),

            "kilos":
                kilos,

            "precio_kilo":
                precio_kilo,

            "pago_estimado":
                round(
                    kilos
                    * precio_kilo
                ),

            "periodo":
                analisis.get(
                    "periodo"
                ),

            "advertencia": (
                "Esta es una simulación sobre "
                "el histórico disponible. "
                "El precio real puede cambiar "
                "cada semana."
            )
        }

    kilos = sum(
        float(
            trabajador.get(
                "total_kg",
                0
            )
        )
        for trabajador
        in analisis.get(
            "trabajadores",
            []
        )
    )

    return {
        "tipo":
            "simulacion_historica_empresa",

        "kilos":
            round(
                kilos,
                2
            ),

        "precio_kilo":
            precio_kilo,

        "pago_estimado":
            round(
                kilos
                * precio_kilo
            ),

        "periodo":
            analisis.get(
                "periodo"
            ),

        "advertencia": (
            "Esta es una simulación del "
            "histórico completo y no "
            "representa necesariamente "
            "una semana específica."
        )
    }


# =====================================================
# ESTADO IA
# =====================================================

def estado_modelo_ia():
    analisis = obtener_analisis_historico()

    return {
        "modelo_predictivo":
            analisis.get(
                "modelo_predictivo"
            ),

        "periodo":
            analisis.get(
                "periodo"
            ),

        "fechas_corregidas":
            analisis.get(
                "fechas_corregidas"
            ),

        "advertencias":
            analisis.get(
                "advertencias",
                []
            )
    }


# =====================================================
# MAPA DE HERRAMIENTAS
# =====================================================

HERRAMIENTAS_PYTHON = {
    "resumen_empresa":
        resumen_empresa,

    "listar_trabajadores":
        listar_trabajadores,

    "analizar_trabajador":
        analizar_trabajador,

    "comparar_trabajadores":
        comparar_trabajadores,

    "ranking_trabajadores":
        ranking_trabajadores,

    "registros_atipicos":
        registros_atipicos,

    "consultar_produccion_bd":
        consultar_produccion_bd,

    "simular_pago_historico":
        simular_pago_historico,

    "estado_modelo_ia":
        estado_modelo_ia
}


def ejecutar_herramienta(
    nombre: str,
    argumentos: dict
):
    funcion = HERRAMIENTAS_PYTHON.get(
        nombre
    )

    if funcion is None:
        return {
            "error":
                f"Herramienta desconocida: {nombre}"
        }

    try:
        return funcion(
            **argumentos
        )

    except Exception as error:
        return {
            "error": (
                f"Error ejecutando "
                f"{nombre}: "
                f"{type(error).__name__}: "
                f"{error}"
            )
        }