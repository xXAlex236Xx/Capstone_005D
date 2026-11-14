from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from dotenv import load_dotenv
from database import conectar_bd

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env", override=False)

# Si DATASET_PATH está en el .env se usa ese archivo (datos reales);
# si no, el CSV de ejemplo con trabajadores anonimizados incluido en el repo.
DATASET = Path(os.getenv("DATASET_PATH") or BASE_DIR / "dataset_cosecha_paltas_2026.csv")

MIN_DIAS_CLUSTER = 4
MIN_REGISTROS_PREDICCION = 5
RANDOM_STATE = 42


def _cargar_dataset(fuente="operacion") -> pd.DataFrame:
    if fuente == "operacion":
        with conectar_bd() as conexion:
            filas = conexion.execute("""
                SELECT CONCAT(t.nombre, ' ', t.apellido, ' · #', t.id_trabajador),
                       j.fecha, SUM(p.cantidad_kg)
                FROM produccion p JOIN trabajadores t USING(id_trabajador)
                JOIN jornadas j USING(id_jornada) JOIN labores l USING(id_labor)
                WHERE l.nombre ILIKE 'Cosecha%'
                GROUP BY t.id_trabajador,t.nombre,t.apellido,j.fecha
                ORDER BY j.fecha,t.id_trabajador
            """).fetchall()
        datos = pd.DataFrame(filas, columns=["trabajador", "fecha", "kilos"])
        datos["fecha"] = pd.to_datetime(datos["fecha"])
        datos["kilos"] = pd.to_numeric(datos["kilos"])
        return datos[datos["kilos"] > 0].reset_index(drop=True)
    if fuente != "historico":
        raise ValueError("Fuente de análisis desconocida")
    if not DATASET.exists():
        raise FileNotFoundError(
            "No se encontró el dataset histórico de cosecha de paltas."
        )

    datos = pd.read_csv(DATASET, parse_dates=["fecha"])
    datos = datos.dropna(subset=["trabajador", "fecha", "kilos"]).copy()
    datos["kilos"] = pd.to_numeric(datos["kilos"], errors="coerce")
    datos = datos.dropna(subset=["kilos"])
    datos = datos[(datos["kilos"] > 0) & (datos["kilos"] <= 5000)]
    datos["trabajador"] = (
        datos["trabajador"]
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    # Un trabajador puede tener varias filas por sector en una misma jornada.
    agregaciones = {"kilos": "sum"}
    if "fecha_corregida" in datos.columns:
        agregaciones["fecha_corregida"] = "max"
    datos = datos.groupby(["fecha", "trabajador"], as_index=False).agg(agregaciones)
    return datos.sort_values(["fecha", "trabajador"]).reset_index(drop=True)


def _calcular_tendencia(grupo: pd.DataFrame) -> float:
    # Cambio ajustado en las últimas 20 jornadas observadas, no pendiente
    # diaria sobre dos años (que diluía cambios recientes casi a cero).
    grupo = grupo.sort_values("fecha").tail(20)
    y = grupo["kilos"].to_numpy(dtype=float)
    if len(y) < 2 or float(np.mean(y)) == 0:
        return 0.0

    x = np.arange(len(y), dtype=float)
    pendiente = float(np.polyfit(x, y, 1)[0])
    return (pendiente * (len(y) - 1) / float(np.mean(y))) * 100.0


def _nombre_grupo(centro: pd.Series, centros: pd.DataFrame) -> str:
    promedio = float(centro["promedio_kg_dia"])
    variacion = float(centro["coef_variacion"])
    tendencia = float(centro["tendencia_pct"])

    mediana_promedios = float(centros["promedio_kg_dia"].median())
    mediana_variacion = float(centros["coef_variacion"].median())

    if tendencia >= 5:
        return "En crecimiento / variable"
    if promedio >= mediana_promedios:
        return "Producción consolidada"
    if variacion <= mediana_variacion:
        return "Producción moderada y estable"
    if tendencia <= -3:
        return "Producción moderada en descenso"
    return "Producción moderada / variable"


def _recomendacion(perfil: str, tendencia: float, dias: int) -> str:
    if dias < MIN_DIAS_CLUSTER:
        return "Se necesitan más jornadas antes de comparar este trabajador."
    if tendencia <= -5:
        return "Revisar la tendencia y el contexto de las últimas jornadas."
    if perfil.startswith("En crecimiento"):
        return "Tendencia positiva; continuar seguimiento con nuevas jornadas."
    if "consolidada" in perfil.lower():
        return "Patrón histórico consolidado; continuar seguimiento."
    return "Seguimiento normal; comparar nuevamente al incorporar más datos."


def _resumen_trabajadores(datos: pd.DataFrame) -> pd.DataFrame:
    resumen = (
        datos.groupby("trabajador")
        .agg(
            dias_trabajados=("fecha", "nunique"),
            registros=("kilos", "count"),
            total_kg=("kilos", "sum"),
            promedio_kg_dia=("kilos", "mean"),
            mediana_kg=("kilos", "median"),
            desviacion_kg=("kilos", "std"),
            ultimo_registro=("fecha", "max"),
        )
        .reset_index()
    )

    resumen["desviacion_kg"] = resumen["desviacion_kg"].fillna(0.0)
    resumen["coef_variacion"] = np.where(
        resumen["promedio_kg_dia"] > 0,
        resumen["desviacion_kg"] / resumen["promedio_kg_dia"],
        0.0,
    )

    tendencias = {
        nombre: _calcular_tendencia(grupo)
        for nombre, grupo in datos.groupby("trabajador")
    }
    ultimos = {
        nombre: float(grupo.sort_values("fecha").iloc[-1]["kilos"])
        for nombre, grupo in datos.groupby("trabajador")
    }

    resumen["tendencia_pct"] = resumen["trabajador"].map(tendencias).fillna(0.0)
    resumen["ultimo_kg"] = resumen["trabajador"].map(ultimos).fillna(0.0)
    resumen["perfil_ia"] = "Datos insuficientes"
    resumen["cluster"] = np.nan

    elegibles = resumen[resumen["dias_trabajados"] >= MIN_DIAS_CLUSTER].copy()

    if len(elegibles) >= 6:
        columnas = ["promedio_kg_dia", "coef_variacion", "tendencia_pct"]
        escalador = StandardScaler()
        matriz = escalador.fit_transform(elegibles[columnas])

        cantidad_clusters = 3 if len(elegibles) >= 9 else 2
        modelo = KMeans(
            n_clusters=cantidad_clusters,
            n_init=30,
            random_state=RANDOM_STATE,
        )
        etiquetas = modelo.fit_predict(matriz)
        elegibles["cluster"] = etiquetas

        centros = elegibles.groupby("cluster")[columnas].mean().sort_index()
        nombres = {
            int(cluster): _nombre_grupo(fila, centros)
            for cluster, fila in centros.iterrows()
        }
        elegibles["perfil_ia"] = elegibles["cluster"].map(nombres)

        resumen.loc[elegibles.index, "cluster"] = elegibles["cluster"]
        resumen.loc[elegibles.index, "perfil_ia"] = elegibles["perfil_ia"]

    resumen["tendencia"] = np.select(
        [resumen["tendencia_pct"] >= 3, resumen["tendencia_pct"] <= -3],
        ["Al alza", "A la baja"],
        default="Estable",
    )
    insuficientes = resumen["dias_trabajados"] < MIN_DIAS_CLUSTER
    resumen.loc[insuficientes, "tendencia"] = "Datos insuficientes"
    resumen.loc[insuficientes, "tendencia_pct"] = 0.0

    resumen["recomendacion"] = resumen.apply(
        lambda fila: _recomendacion(
            str(fila["perfil_ia"]),
            float(fila["tendencia_pct"]),
            int(fila["dias_trabajados"]),
        ),
        axis=1,
    )

    return resumen.sort_values(
        ["dias_trabajados", "promedio_kg_dia"], ascending=[False, False]
    ).reset_index(drop=True)


def _detectar_atipicos(datos: pd.DataFrame, limite: int = 15) -> list[dict]:
    estadisticas = datos.groupby("trabajador")["kilos"].agg(["mean", "std", "count"])
    trabajo = datos.join(estadisticas, on="trabajador")
    trabajo = trabajo[trabajo["count"] >= MIN_DIAS_CLUSTER].copy()
    trabajo["std"] = trabajo["std"].replace(0, np.nan)
    trabajo["desviacion_relativa"] = (
        (trabajo["kilos"] - trabajo["mean"]) / trabajo["std"]
    ).fillna(0.0)
    trabajo["dia_semana"] = trabajo["fecha"].dt.dayofweek

    if len(trabajo) < 20:
        return []

    modelo = IsolationForest(
        n_estimators=250,
        contamination=0.05,
        random_state=RANDOM_STATE,
    )
    matriz = trabajo[["desviacion_relativa", "dia_semana"]].to_numpy(dtype=float)
    trabajo["es_atipico"] = modelo.fit_predict(matriz) == -1
    trabajo["puntaje_atipico"] = -modelo.score_samples(matriz)

    atipicos = trabajo[trabajo["es_atipico"]].copy()
    atipicos = atipicos.sort_values("puntaje_atipico", ascending=False).head(limite)

    salida = []
    for _, fila in atipicos.iterrows():
        salida.append(
            {
                "trabajador": str(fila["trabajador"]),
                "fecha": fila["fecha"].date().isoformat(),
                "kilos": round(float(fila["kilos"]), 2),
                "promedio_trabajador": round(float(fila["mean"]), 2),
                "tipo": "Alto" if float(fila["kilos"]) > float(fila["mean"]) else "Bajo",
                "mensaje": "Registro atípico para revisión; no implica un error por sí solo.",
            }
        )
    return salida


def _variables_supervisadas(datos: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for nombre, grupo in datos.groupby("trabajador"):
        grupo = grupo.sort_values("fecha").reset_index(drop=True)
        kilos = grupo["kilos"].astype(float)

        for i in range(3, len(grupo)):
            fecha = pd.Timestamp(grupo.loc[i, "fecha"])
            anteriores = kilos.iloc[i - 3 : i]
            filas.append(
                {
                    "trabajador": nombre,
                    "fecha": fecha,
                    "lag_1": float(kilos.iloc[i - 1]),
                    "lag_2": float(kilos.iloc[i - 2]),
                    "media_3": float(anteriores.mean()),
                    "tendencia_reciente": float(kilos.iloc[i - 1] - kilos.iloc[i - 2]),
                    "dia_semana": int(fecha.dayofweek),
                    "semana": int(fecha.isocalendar().week),
                    "kilos_objetivo": float(kilos.iloc[i]),
                }
            )

    return pd.DataFrame(filas)


def _entrenar_prediccion(datos: pd.DataFrame) -> tuple[dict, dict[str, float | None]]:
    base = _variables_supervisadas(datos)
    vacio = {
        "entrenado": False,
        "descripcion": "Aún no hay suficientes secuencias históricas para entrenar la predicción.",
        "registros_entrenamiento": 0,
        "registros_prueba": 0,
        "mae_kg": None,
        "r2": None,
    }
    if len(base) < 30:
        return vacio, {}

    # Corte global por fecha: ningún trabajador aporta al entrenamiento datos
    # posteriores al inicio de la evaluación.
    fechas = sorted(base["fecha"].unique())
    corte = fechas[max(1, int(len(fechas) * 0.8))] if len(fechas) > 1 else fechas[0]
    prueba = base[base["fecha"] >= corte].copy()
    entrenamiento = base[base["fecha"] < corte].copy()

    if len(entrenamiento) < 20 or len(prueba) < 5:
        return vacio, {}

    columnas_numericas = [
        "lag_1",
        "lag_2",
        "media_3",
        "tendencia_reciente",
        "dia_semana",
        "semana",
    ]
    columnas = ["trabajador", *columnas_numericas]

    preprocesador = ColumnTransformer(
        transformers=[
            ("trabajador", OneHotEncoder(handle_unknown="ignore"), ["trabajador"]),
            ("numericas", "passthrough", columnas_numericas),
        ]
    )
    modelo = Pipeline(
        steps=[
            ("preprocesador", preprocesador),
            (
                "regresor",
                RandomForestRegressor(
                    n_estimators=300,
                    min_samples_leaf=2,
                    max_features="sqrt",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    modelo.fit(entrenamiento[columnas], entrenamiento["kilos_objetivo"])
    pred_prueba = modelo.predict(prueba[columnas])
    mae = float(mean_absolute_error(prueba["kilos_objetivo"], pred_prueba))
    mae_base = float(mean_absolute_error(prueba["kilos_objetivo"], prueba["media_3"]))
    r2 = float(r2_score(prueba["kilos_objetivo"], pred_prueba)) if len(prueba) >= 2 else None

    # Reentrenar con toda la información disponible para estimar la próxima jornada.
    modelo.fit(base[columnas], base["kilos_objetivo"])

    predicciones: dict[str, float | None] = {}
    for nombre, grupo in datos.groupby("trabajador"):
        grupo = grupo.sort_values("fecha").reset_index(drop=True)
        if len(grupo) < MIN_REGISTROS_PREDICCION:
            predicciones[str(nombre)] = None
            continue

        ultimos = grupo["kilos"].astype(float).tail(3).to_numpy()
        proxima_fecha = pd.Timestamp(grupo.iloc[-1]["fecha"]) + pd.Timedelta(days=1)
        entrada = pd.DataFrame(
            [
                {
                    "trabajador": str(nombre),
                    "lag_1": float(ultimos[-1]),
                    "lag_2": float(ultimos[-2]),
                    "media_3": float(np.mean(ultimos)),
                    "tendencia_reciente": float(ultimos[-1] - ultimos[-2]),
                    "dia_semana": int(proxima_fecha.dayofweek),
                    "semana": int(proxima_fecha.isocalendar().week),
                }
            ]
        )
        pred = float(modelo.predict(entrada[columnas])[0])
        predicciones[str(nombre)] = round(max(0.0, pred), 2)

    metricas = {
        "entrenado": True,
        "descripcion": (
            "Random Forest estima los kilos de la próxima jornada usando el historial reciente "
            "del trabajador. La predicción es orientativa y debe mejorar al incorporar más datos."
        ),
        "registros_entrenamiento": int(len(entrenamiento)),
        "registros_prueba": int(len(prueba)),
        "mae_kg": round(mae, 2),
        "r2": round(r2, 3) if r2 is not None else None,
        "mae_referencia_kg": round(mae_base, 2),
        "mejora_referencia": mae < mae_base,
        "evaluacion": "Corte temporal global 80/20; referencia: media de las tres jornadas anteriores",
        "fecha_corte": pd.Timestamp(corte).date().isoformat(),
    }
    return metricas, predicciones


def generar_analisis(fuente="operacion") -> dict:
    datos = _cargar_dataset(fuente)
    if datos.empty:
        return {
            "version": "IA v2", "fuente": fuente,
            "metodo": "K-Means + Isolation Forest + Random Forest",
            "descripcion": "Aún no hay producción de cosecha suficiente en esta fuente.",
            "periodo": {"desde": None, "hasta": None},
            "registros_historicos": 0, "trabajadores_historicos": 0,
            "trabajadores_analizados_ia": 0, "trabajadores_con_prediccion": 0,
            "minimo_dias_para_ia": MIN_DIAS_CLUSTER,
            "minimo_registros_prediccion": MIN_REGISTROS_PREDICCION,
            "modelo_predictivo": {"entrenado": False, "mae_kg": None, "r2": None},
            "fechas_corregidas": 0, "trabajadores": [], "registros_atipicos": [],
            "advertencias": ["Registra cosechas para comenzar a analizar la producción."],
        }
    resumen = _resumen_trabajadores(datos)
    atipicos = _detectar_atipicos(datos)
    modelo_predictivo, predicciones = _entrenar_prediccion(datos)

    corregidas = 0
    if "fecha_corregida" in datos.columns:
        valores = datos["fecha_corregida"].astype(str).str.lower()
        corregidas = int(valores.isin(["true", "1", "si", "sí"]).sum())

    trabajadores = []
    for _, fila in resumen.iterrows():
        nombre = str(fila["trabajador"])
        trabajadores.append(
            {
                "trabajador": nombre,
                "dias_trabajados": int(fila["dias_trabajados"]),
                "registros": int(fila["registros"]),
                "total_kg": round(float(fila["total_kg"]), 2),
                "promedio_kg_dia": round(float(fila["promedio_kg_dia"]), 2),
                "mediana_kg": round(float(fila["mediana_kg"]), 2),
                "variabilidad_pct": round(float(fila["coef_variacion"]) * 100, 1),
                "tendencia_pct": round(float(fila["tendencia_pct"]), 2),
                "tendencia_metodo": "Cambio de la recta ajustada entre inicio y fin de las últimas 20 jornadas disponibles (o menos), dividido por su promedio de kg/día. No ajusta por horas ni condiciones.",
                "tendencia": str(fila["tendencia"]),
                "ultimo_kg": round(float(fila["ultimo_kg"]), 2),
                "ultimo_registro": fila["ultimo_registro"].date().isoformat(),
                "perfil_ia": str(fila["perfil_ia"]),
                "recomendacion": str(fila["recomendacion"]),
                "prediccion_proxima_jornada_kg": predicciones.get(nombre),
            }
        )

    analizados = int((resumen["dias_trabajados"] >= MIN_DIAS_CLUSTER).sum())
    con_prediccion = sum(
        1 for valor in predicciones.values() if valor is not None
    )

    return {
        "version": "IA v2",
        "fuente": fuente,
        "metodo": "K-Means + Isolation Forest + Random Forest",
        "descripcion": (
            "K-Means agrupa patrones de producción, Isolation Forest marca registros inusuales "
            "y Random Forest entrega una estimación orientativa para la próxima jornada."
        ),
        "periodo": {
            "desde": datos["fecha"].min().date().isoformat(),
            "hasta": datos["fecha"].max().date().isoformat(),
        },
        "registros_historicos": int(len(datos)),
        "trabajadores_historicos": int(datos["trabajador"].nunique()),
        "trabajadores_analizados_ia": analizados,
        "trabajadores_con_prediccion": int(con_prediccion),
        "minimo_dias_para_ia": MIN_DIAS_CLUSTER,
        "minimo_registros_prediccion": MIN_REGISTROS_PREDICCION,
        "modelo_predictivo": modelo_predictivo,
        "fechas_corregidas": corregidas,
        "advertencias": [
            ("Fuente: producción registrada en PostgreSQL, agrupada por trabajador y fecha; labores cuyo nombre comienza con Cosecha."
             if fuente == "operacion" else "Fuente: CSV histórico de ejemplo, separado de la operación actual."),
            "Compara jornadas considerando horas, sector, cultivo y condiciones; los kilos diarios no describen por sí solos el desempeño.",
            "La tendencia estima el cambio dentro de las últimas 20 jornadas disponibles de cada trabajador; revisa su última fecha, especialmente en trabajadores inactivos.",
            "Las estimaciones son apoyo para análisis; no deben usarse por sí solas para decisiones laborales.",
            "La fiabilidad depende de la cantidad y representatividad de las jornadas disponibles; el análisis se recalcula al actualizar.",
        ],
        "trabajadores": trabajadores,
        "registros_atipicos": atipicos,
    }
