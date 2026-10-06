import re
import unicodedata
from difflib import SequenceMatcher

from ia.modelo_productividad import generar_analisis


def normalizar(texto):
    texto = str(texto).lower().strip()

    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )

    texto = re.sub(r"\s+", " ", texto)

    return texto


def formato_numero(numero, decimales=1):
    if numero is None:
        return "sin datos"

    return f"{numero:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def buscar_trabajador(pregunta, trabajadores):
    pregunta_normalizada = normalizar(pregunta)

    # Primero intentamos encontrar el nombre directamente.
    candidatos = []

    for trabajador in trabajadores:
        nombre = trabajador["trabajador"]
        nombre_normalizado = normalizar(nombre)

        if nombre_normalizado in pregunta_normalizada:
            return trabajador

        partes = [
            parte
            for parte in nombre_normalizado.split()
            if len(parte) >= 4
        ]

        coincidencias = sum(
            1
            for parte in partes
            if parte in pregunta_normalizada
        )

        if coincidencias > 0:
            candidatos.append(
                (
                    coincidencias,
                    len(nombre_normalizado),
                    trabajador
                )
            )

    if candidatos:
        candidatos.sort(
            key=lambda elemento: (elemento[0], elemento[1]),
            reverse=True
        )

        return candidatos[0][2]

    # Si hay un error de escritura pequeño, hacemos búsqueda aproximada.
    mejor = None
    mejor_puntaje = 0

    palabras_pregunta = pregunta_normalizada.split()

    for trabajador in trabajadores:
        nombre = normalizar(trabajador["trabajador"])

        for palabra in palabras_pregunta:
            if len(palabra) < 4:
                continue

            for parte_nombre in nombre.split():
                puntaje = SequenceMatcher(
                    None,
                    palabra,
                    parte_nombre
                ).ratio()

                if puntaje > mejor_puntaje:
                    mejor_puntaje = puntaje
                    mejor = trabajador

    if mejor_puntaje >= 0.78:
        return mejor

    return None


def resumen_trabajador(trabajador):
    prediccion = trabajador.get(
        "prediccion_proxima_jornada_kg"
    )

    if prediccion is None:
        texto_prediccion = (
            "Todavía no tiene suficientes registros "
            "para generar una predicción."
        )
    else:
        texto_prediccion = (
            f"La IA estima aproximadamente "
            f"{formato_numero(prediccion)} kg "
            f"para su próxima jornada."
        )

    return (
        f"📊 {trabajador['trabajador']}\n\n"
        f"Ha trabajado {trabajador['dias_trabajados']} jornadas registradas "
        f"y acumula {formato_numero(trabajador['total_kg'])} kg.\n\n"
        f"Su promedio es de "
        f"{formato_numero(trabajador['promedio_kg_dia'])} kg por jornada.\n\n"
        f"Su tendencia actual es: "
        f"{trabajador['tendencia']} "
        f"({formato_numero(trabajador['tendencia_pct'])}%).\n\n"
        f"Perfil detectado por IA: "
        f"{trabajador['perfil_ia']}.\n\n"
        f"{texto_prediccion}\n\n"
        f"💡 {trabajador['recomendacion']}"
    )


def respuesta_ranking(trabajadores, tipo="promedio"):
    validos = [
        trabajador
        for trabajador in trabajadores
        if trabajador["dias_trabajados"] >= 4
    ]

    if tipo == "total":
        ordenados = sorted(
            validos,
            key=lambda trabajador: trabajador["total_kg"],
            reverse=True
        )

        titulo = "🏆 Mayor producción acumulada"

        lineas = [
            (
                f"{indice}. {trabajador['trabajador']}: "
                f"{formato_numero(trabajador['total_kg'])} kg"
            )
            for indice, trabajador in enumerate(
                ordenados[:5],
                start=1
            )
        ]

    else:
        ordenados = sorted(
            validos,
            key=lambda trabajador: trabajador["promedio_kg_dia"],
            reverse=True
        )

        titulo = "🏆 Mejores promedios de producción"

        lineas = [
            (
                f"{indice}. {trabajador['trabajador']}: "
                f"{formato_numero(trabajador['promedio_kg_dia'])} "
                f"kg por jornada"
            )
            for indice, trabajador in enumerate(
                ordenados[:5],
                start=1
            )
        ]

    return titulo + "\n\n" + "\n".join(lineas)


def respuesta_tendencias(trabajadores, tendencia):
    encontrados = [
        trabajador
        for trabajador in trabajadores
        if trabajador["tendencia"] == tendencia
        and trabajador["dias_trabajados"] >= 4
    ]

    encontrados = sorted(
        encontrados,
        key=lambda trabajador: abs(
            trabajador["tendencia_pct"]
        ),
        reverse=True
    )

    if not encontrados:
        return (
            f"No encontré trabajadores con tendencia "
            f"'{tendencia}' usando los datos actuales."
        )

    titulo = (
        "📉 Trabajadores con tendencia a la baja"
        if tendencia == "A la baja"
        else "📈 Trabajadores con tendencia al alza"
    )

    lineas = []

    for trabajador in encontrados[:8]:
        signo = "+" if trabajador["tendencia_pct"] > 0 else ""

        lineas.append(
            f"• {trabajador['trabajador']}: "
            f"{signo}{formato_numero(trabajador['tendencia_pct'])}%"
        )

    return titulo + "\n\n" + "\n".join(lineas)


def respuesta_atipicos(analisis, trabajador=None):
    registros = analisis.get("registros_atipicos", [])

    if trabajador:
        nombre = trabajador["trabajador"]

        registros = [
            registro
            for registro in registros
            if registro["trabajador"] == nombre
        ]

    if not registros:
        if trabajador:
            return (
                f"No encontré registros atípicos recientes "
                f"para {trabajador['trabajador']}."
            )

        return "No encontré registros atípicos en el análisis actual."

    lineas = []

    for registro in registros[:8]:
        lineas.append(
            f"• {registro['trabajador']} — "
            f"{registro['fecha']}: "
            f"{formato_numero(registro['kilos'])} kg "
            f"({registro['tipo']}). "
            f"Promedio: "
            f"{formato_numero(registro['promedio_trabajador'])} kg."
        )

    return (
        "⚠️ Registros que la IA recomienda revisar\n\n"
        + "\n".join(lineas)
        + "\n\nUn valor atípico no significa automáticamente que exista un error."
    )


def respuesta_modelo(analisis):
    modelo = analisis.get("modelo_predictivo", {})

    if not modelo.get("entrenado"):
        return "El modelo predictivo todavía no está entrenado."

    mae = modelo.get("mae_kg")
    r2 = modelo.get("r2")

    return (
        "🧠 Estado del modelo predictivo\n\n"
        f"Modelo: Random Forest\n"
        f"Registros de entrenamiento: "
        f"{modelo.get('registros_entrenamiento', 0)}\n"
        f"Registros de prueba: "
        f"{modelo.get('registros_prueba', 0)}\n"
        f"Error medio absoluto: "
        f"{formato_numero(mae)} kg\n"
        f"R²: {formato_numero(r2, 3)}\n\n"
        f"{modelo.get('descripcion', '')}\n\n"
        "El modelo es una herramienta de apoyo y sus predicciones "
        "no deben interpretarse como valores exactos."
    )


def extraer_precio(pregunta):
    pregunta_normalizada = normalizar(pregunta)

    patrones = [
        r"\$\s*([0-9]+(?:[.,][0-9]+)?)",
        r"([0-9]+(?:[.,][0-9]+)?)\s*(?:pesos)?\s*(?:por|el)?\s*kilo",
        r"kilo\s*(?:vale|a|en)?\s*\$?\s*([0-9]+(?:[.,][0-9]+)?)"
    ]

    for patron in patrones:
        coincidencia = re.search(
            patron,
            pregunta_normalizada
        )

        if coincidencia:
            valor = coincidencia.group(1)
            valor = valor.replace(".", "").replace(",", ".")

            try:
                return float(valor)
            except ValueError:
                pass

    return None


def responder_chat(pregunta):
    analisis = generar_analisis()

    trabajadores = analisis.get("trabajadores", [])
    pregunta_normalizada = normalizar(pregunta)

    trabajador = buscar_trabajador(
        pregunta,
        trabajadores
    )

    # -------------------------------------------------
    # AYUDA
    # -------------------------------------------------

    if any(
        palabra in pregunta_normalizada
        for palabra in [
            "que puedes hacer",
            "que sabes hacer",
            "ayuda",
            "como funcionas"
        ]
    ):
        return {
            "respuesta": (
                "🤖 Puedo analizar los datos históricos de Doña Laura.\n\n"
                "Puedes preguntarme, por ejemplo:\n\n"
                "• ¿Cómo va Rubén Fabrica?\n"
                "• ¿Quién produce más?\n"
                "• ¿Quién viene a la baja?\n"
                "• ¿Qué predice la IA para Manuel?\n"
                "• ¿Qué registros son atípicos?\n"
                "• ¿Qué tan preciso es el modelo?\n"
                "• Si el kilo vale $80, ¿cuánto habría ganado Rubén?"
            ),
            "tipo": "ayuda"
        }

    # -------------------------------------------------
    # MODELO IA
    # -------------------------------------------------

    if any(
        palabra in pregunta_normalizada
        for palabra in [
            "precision",
            "modelo",
            "mae",
            "r2",
            "error",
            "confiable"
        ]
    ):
        return {
            "respuesta": respuesta_modelo(analisis),
            "tipo": "modelo"
        }

    # -------------------------------------------------
    # REGISTROS ATÍPICOS
    # -------------------------------------------------

    if any(
        palabra in pregunta_normalizada
        for palabra in [
            "atipico",
            "anomalo",
            "anomalia",
            "raro",
            "inusual"
        ]
    ):
        return {
            "respuesta": respuesta_atipicos(
                analisis,
                trabajador
            ),
            "tipo": "atipicos"
        }

    # -------------------------------------------------
    # PAGOS SIMULADOS
    # -------------------------------------------------

    if any(
        palabra in pregunta_normalizada
        for palabra in [
            "pago",
            "pagaria",
            "ganaria",
            "gano",
            "ganado",
            "precio"
        ]
    ):
        precio = extraer_precio(pregunta)

        if precio is None:
            return {
                "respuesta": (
                    "💰 Puedo hacer una simulación de pago, "
                    "pero necesito que me indiques el precio por kilo.\n\n"
                    "Por ejemplo: "
                    "\"Si el kilo vale $80, ¿cuánto habría ganado Rubén?\""
                ),
                "tipo": "pago"
            }

        if trabajador is None:
            return {
                "respuesta": (
                    "Encontré el precio por kilo, pero necesito que "
                    "me indiques el trabajador.\n\n"
                    "Ejemplo: "
                    "\"Si el kilo vale $80, ¿cuánto habría ganado Rubén?\""
                ),
                "tipo": "pago"
            }

        total = trabajador["total_kg"] * precio

        return {
            "respuesta": (
                f"💰 Simulación para {trabajador['trabajador']}\n\n"
                f"Producción histórica considerada: "
                f"{formato_numero(trabajador['total_kg'])} kg\n"
                f"Precio indicado: ${formato_numero(precio, 0)} por kg\n\n"
                f"Pago estimado sobre ese histórico: "
                f"${formato_numero(total, 0)} CLP.\n\n"
                "⚠️ Esto es una simulación sobre todo el período "
                "histórico cargado, no un pago semanal."
            ),
            "tipo": "pago"
        }

    # -------------------------------------------------
    # PREDICCIÓN
    # -------------------------------------------------

    if any(
        palabra in pregunta_normalizada
        for palabra in [
            "prediccion",
            "predecir",
            "estima",
            "estimacion",
            "proxima jornada",
            "proximo dia"
        ]
    ):
        if trabajador:
            prediccion = trabajador.get(
                "prediccion_proxima_jornada_kg"
            )

            if prediccion is None:
                respuesta = (
                    f"{trabajador['trabajador']} todavía no tiene "
                    f"suficientes datos para generar una predicción."
                )
            else:
                respuesta = (
                    f"🔮 Predicción para "
                    f"{trabajador['trabajador']}\n\n"
                    f"El modelo estima aproximadamente "
                    f"{formato_numero(prediccion)} kg "
                    f"para su próxima jornada.\n\n"
                    f"Su promedio histórico es de "
                    f"{formato_numero(trabajador['promedio_kg_dia'])} "
                    f"kg por jornada.\n\n"
                    "Esta estimación es orientativa y puede cambiar "
                    "al incorporar nuevas jornadas."
                )

            return {
                "respuesta": respuesta,
                "tipo": "prediccion"
            }

        con_prediccion = [
            t
            for t in trabajadores
            if t.get("prediccion_proxima_jornada_kg")
            is not None
        ]

        con_prediccion = sorted(
            con_prediccion,
            key=lambda t: t[
                "prediccion_proxima_jornada_kg"
            ],
            reverse=True
        )

        lineas = [
            (
                f"• {t['trabajador']}: "
                f"≈ {formato_numero(t['prediccion_proxima_jornada_kg'])} kg"
            )
            for t in con_prediccion[:5]
        ]

        return {
            "respuesta": (
                "🔮 Mayores predicciones para la próxima jornada\n\n"
                + "\n".join(lineas)
            ),
            "tipo": "prediccion"
        }

    # -------------------------------------------------
    # TENDENCIAS
    # -------------------------------------------------

    if any(
        palabra in pregunta_normalizada
        for palabra in [
            "a la baja",
            "bajando",
            "disminuyendo",
            "descenso",
            "cayeron"
        ]
    ):
        return {
            "respuesta": respuesta_tendencias(
                trabajadores,
                "A la baja"
            ),
            "tipo": "tendencias"
        }

    if any(
        palabra in pregunta_normalizada
        for palabra in [
            "al alza",
            "subiendo",
            "mejorando",
            "creciendo"
        ]
    ):
        return {
            "respuesta": respuesta_tendencias(
                trabajadores,
                "Al alza"
            ),
            "tipo": "tendencias"
        }

    # -------------------------------------------------
    # RANKING
    # -------------------------------------------------

    if any(
        palabra in pregunta_normalizada
        for palabra in [
            "quien produce mas",
            "quien produjo mas",
            "mejor trabajador",
            "mejores trabajadores",
            "ranking",
            "mayor produccion",
            "top"
        ]
    ):
        tipo = (
            "total"
            if any(
                palabra in pregunta_normalizada
                for palabra in [
                    "total",
                    "acumulado",
                    "acumula"
                ]
            )
            else "promedio"
        )

        return {
            "respuesta": respuesta_ranking(
                trabajadores,
                tipo
            ),
            "tipo": "ranking"
        }

    # -------------------------------------------------
    # CONSULTA DE UN TRABAJADOR
    # -------------------------------------------------

    if trabajador:
        return {
            "respuesta": resumen_trabajador(
                trabajador
            ),
            "tipo": "trabajador",
            "trabajador": trabajador["trabajador"]
        }

    # -------------------------------------------------
    # RESPUESTA GENERAL
    # -------------------------------------------------

    return {
        "respuesta": (
            "🤖 No entendí completamente esa consulta todavía.\n\n"
            "Puedes preguntarme cosas como:\n"
            "• ¿Cómo va Rubén Fabrica?\n"
            "• ¿Quién produce más?\n"
            "• ¿Quién viene a la baja?\n"
            "• ¿Qué predice la IA para Manuel?\n"
            "• ¿Qué datos son atípicos?\n"
            "• ¿Qué tan preciso es el modelo?"
        ),
        "tipo": "desconocido"
    }
  