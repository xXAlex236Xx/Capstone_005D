import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from ia.herramientas import ejecutar_herramienta


# =====================================================
# CONFIGURACIÓN
# =====================================================

BACKEND_DIR = Path(__file__).resolve().parent.parent

load_dotenv(
    BACKEND_DIR / ".env",
    override=False
)

MODELO = os.getenv(
    "OPENAI_MODEL",
    "gpt-6-luna"
)

# =====================================================
# PERSONALIDAD / REGLAS DEL AGENTE
# =====================================================

INSTRUCCIONES = """
Eres el Asistente Inteligente de Gestión Agrícola de la empresa Doña Laura.

Tu objetivo es ayudar al encargado a comprender la empresa, analizar datos,
resolver dudas y apoyar decisiones administrativas y productivas.

REGLAS IMPORTANTES:

1. Habla en español chileno natural, profesional pero cercano.

2. Cuando una pregunta dependa de información real de Doña Laura,
   DEBES consultar las herramientas disponibles antes de responder.

3. Nunca inventes kilos, trabajadores, fechas, pagos, tendencias,
   producción, predicciones ni información de la empresa.

4. Diferencia claramente dos fuentes:
   - PostgreSQL: información operativa registrada en el sistema.
   - Histórico Excel + IA: información histórica usada por los modelos.

5. Puedes dar opiniones, conclusiones y recomendaciones, pero siempre
   explica brevemente qué datos sustentan esa opinión.

6. Si los datos no son suficientes, dilo directamente.

7. Las predicciones son estimaciones, no resultados garantizados.

8. No recomiendes despedir, contratar o sancionar automáticamente
   a una persona usando solo productividad o predicciones.
   Puedes señalar tendencias y aspectos que merecen revisión.

9. Si el usuario pide una acción que modifique datos importantes
   (borrar, desactivar, registrar o modificar información),
   NO la ejecutes todavía. Explica qué acción se realizaría y solicita
   confirmación. Las herramientas de escritura se incorporarán después
   con confirmaciones explícitas.

10. Puedes razonar sobre los resultados. Por ejemplo:
    - detectar qué trabajador merece revisión,
    - comparar tendencias,
    - explicar anomalías,
    - señalar riesgos,
    - sugerir qué datos sería útil registrar,
    - interpretar el desempeño del modelo,
    - dar una opinión administrativa basada en evidencia.

11. No muestres claves API, contraseñas, variables .env
    ni credenciales de base de datos.

12. Responde de forma útil y directa. No entregues tablas gigantes
    si no son necesarias.

13. La tabla de jornadas puede contener fechas creadas automáticamente
    por el sistema y no necesariamente representa días realmente trabajados.
    No interpretes el número total de jornadas como actividad real de la empresa.
    Para evaluar trabajo o producción, prioriza los registros de producción
    asociados a trabajadores y los datos históricos disponibles.

Eres un asistente de gestión, no solamente un buscador de datos.
Usa las herramientas y luego interpreta los resultados.
"""


# =====================================================
# HERRAMIENTAS DISPONIBLES PARA EL MODELO
# =====================================================

TOOLS = [
    {
        "type": "function",
        "name": "resumen_empresa",
        "description": (
            "Obtiene un panorama general de Doña Laura: "
            "trabajadores, producción, jornadas, histórico IA "
            "y estado del modelo predictivo."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "listar_trabajadores",
        "description": (
            "Lista trabajadores registrados actualmente "
            "en PostgreSQL."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "estado": {
                    "type": "string",
                    "description": (
                        "Todos, Activo o Inactivo."
                    )
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "analizar_trabajador",
        "description": (
            "Obtiene análisis histórico completo de un trabajador: "
            "kilos, promedio, tendencia, perfil IA y predicción."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nombre": {
                    "type": "string",
                    "description": (
                        "Nombre o parte del nombre del trabajador."
                    )
                }
            },
            "required": ["nombre"]
        }
    },
    {
        "type": "function",
        "name": "comparar_trabajadores",
        "description": (
            "Compara los indicadores históricos de entre "
            "dos y cinco trabajadores."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nombres": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": (
                        "Lista de nombres de trabajadores."
                    )
                }
            },
            "required": ["nombres"]
        }
    },
    {
        "type": "function",
        "name": "ranking_trabajadores",
        "description": (
            "Obtiene rankings históricos por promedio, total, "
            "predicción, tendencia al alza o tendencia a la baja."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "criterio": {
                    "type": "string",
                    "description": (
                        "promedio, total, prediccion, "
                        "tendencia alza o tendencia baja."
                    )
                },
                "limite": {
                    "type": "integer",
                    "description": (
                        "Cantidad de trabajadores a devolver."
                    )
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "registros_atipicos",
        "description": (
            "Busca registros de producción considerados atípicos "
            "por la IA. Puede filtrar por trabajador."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nombre": {
                    "type": ["string", "null"],
                    "description": (
                        "Nombre del trabajador o null "
                        "para revisar toda la empresa."
                    )
                },
                "limite": {
                    "type": "integer",
                    "description": (
                        "Máximo de registros a devolver."
                    )
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "consultar_produccion_bd",
        "description": (
            "Consulta producción realmente guardada en PostgreSQL. "
            "Permite filtrar por fechas y trabajador."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fecha_inicio": {
                    "type": ["string", "null"],
                    "description": (
                        "Fecha inicial YYYY-MM-DD o null."
                    )
                },
                "fecha_fin": {
                    "type": ["string", "null"],
                    "description": (
                        "Fecha final YYYY-MM-DD o null."
                    )
                },
                "nombre": {
                    "type": ["string", "null"],
                    "description": (
                        "Nombre del trabajador o null."
                    )
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "simular_pago_historico",
        "description": (
            "Simula un pago usando kilos históricos y un precio "
            "por kilo indicado por el usuario. No registra pagos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "precio_kilo": {
                    "type": "number",
                    "description": (
                        "Precio en pesos chilenos por kilogramo."
                    )
                },
                "nombre": {
                    "type": ["string", "null"],
                    "description": (
                        "Trabajador específico o null "
                        "para toda la empresa."
                    )
                }
            },
            "required": ["precio_kilo"]
        }
    },
    {
        "type": "function",
        "name": "estado_modelo_ia",
        "description": (
            "Obtiene métricas, limitaciones y advertencias "
            "del modelo predictivo actual."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    }
]


# =====================================================
# CONVERSACIÓN
# =====================================================

def preparar_historial(
    pregunta: str,
    historial: list[dict] | None
):
    mensajes = []

    historial = historial or []

    # Solo usamos mensajes recientes para controlar costo.
    for mensaje in historial[-12:]:
        texto = str(
            mensaje.get("texto", "")
        ).strip()

        if not texto:
            continue

        autor = mensaje.get(
            "autor",
            "usuario"
        )

        rol = (
            "assistant"
            if autor in ["ia", "assistant"]
            else "user"
        )

        mensajes.append({
            "role": rol,
            "content": texto
        })

    mensajes.append({
        "role": "user",
        "content": pregunta
    })

    return mensajes


# =====================================================
# AGENTE LLM
# =====================================================

def responder_agente(
    pregunta: str,
    historial: list[dict] | None = None
):
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "No existe OPENAI_API_KEY en el archivo .env."
        )

    cliente = OpenAI(
        api_key=api_key
    )

    input_items = preparar_historial(
        pregunta,
        historial
    )

    herramientas_usadas = []

    try:
        respuesta = cliente.responses.create(
            model=MODELO,
            instructions=INSTRUCCIONES,
            tools=TOOLS,
            tool_choice="auto",
            input=input_items,
            max_output_tokens=3000,
            store=False
        )

        # Permitimos varias rondas de herramientas.
        for _ in range(6):
            llamadas = [
                item
                for item in respuesta.output
                if item.type == "function_call"
            ]

            if not llamadas:
                texto = respuesta.output_text

                if not texto:
                    texto = (
                        "No pude generar una respuesta "
                        "con los datos disponibles."
                    )

                return {
                    "respuesta": texto,
                    "modo": "llm",
                    "modelo": MODELO,
                    "herramientas_usadas":
                        herramientas_usadas
                }

            # La documentación de Responses API recomienda
            # conservar la salida del modelo en la entrada
            # antes de agregar los resultados de las funciones.
            input_items += respuesta.output

            for llamada in llamadas:
                herramientas_usadas.append(
                    llamada.name
                )

                try:
                    argumentos = json.loads(
                        llamada.arguments or "{}"
                    )

                except json.JSONDecodeError:
                    argumentos = {}

                resultado = ejecutar_herramienta(
                    llamada.name,
                    argumentos
                )

                input_items.append({
                    "type": "function_call_output",
                    "call_id": llamada.call_id,
                    "output": json.dumps(
                        resultado,
                        ensure_ascii=False,
                        default=str
                    )
                })

            respuesta = cliente.responses.create(
                model=MODELO,
                instructions=INSTRUCCIONES,
                tools=TOOLS,
                tool_choice="auto",
                input=input_items,
                max_output_tokens=1400,
                store=False
            )

        return {
            "respuesta": (
                "El análisis requirió demasiadas consultas "
                "internas. Intenta formular la pregunta "
                "de una manera más específica."
            ),
            "modo": "llm",
            "modelo": MODELO,
            "herramientas_usadas":
                herramientas_usadas
        }

    except Exception as error:
        print(
            "ERROR OPENAI AGENTE:",
            type(error).__name__,
            error
        )

        # Si falla la API, mantenemos vivo el chatbot antiguo.
        try:
            from ia.asistente import responder_chat

            respuesta_local = responder_chat(
                pregunta
            )

            return {
                "respuesta": (
                    "⚠️ El asistente avanzado no pudo "
                    "conectarse al modelo de lenguaje.\n\n"
                    + respuesta_local.get(
                        "respuesta",
                        ""
                    )
                ),
                "modo": "fallback_local",
                "modelo": MODELO,
                "herramientas_usadas": [],
                "error_tipo":
                    type(error).__name__
            }

        except Exception:
            raise error