import { useEffect, useMemo, useState } from "react";
import "./AnalisisIA.css";

const API = "http://127.0.0.1:8000";

function formatoNumero(valor, decimales = 0) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) {
    return "—";
  }

  return new Intl.NumberFormat("es-CL", {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales
  }).format(Number(valor));
}

function claseTendencia(tendencia) {
  if (tendencia === "Al alza") return "ia-tendencia ia-alza";
  if (tendencia === "A la baja") return "ia-tendencia ia-baja";
  return "ia-tendencia ia-estable";
}

function AnalisisIA() {
  const [analisis, setAnalisis] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [soloAnalizados, setSoloAnalizados] = useState(true);

  async function cargarAnalisis() {
    setCargando(true);
    setError("");

    try {
      const respuesta = await fetch(`${API}/ia/analisis`);
      const datos = await respuesta.json();

      if (!respuesta.ok) {
        throw new Error(
          typeof datos.detail === "string"
            ? datos.detail
            : "No se pudo cargar el análisis IA."
        );
      }

      setAnalisis(datos);
    } catch (err) {
      setError(err.message || "No se pudo conectar con el análisis IA.");
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    cargarAnalisis();
  }, []);

  const trabajadoresFiltrados = useMemo(() => {
    if (!analisis) return [];

    const texto = busqueda.trim().toLowerCase();
    return analisis.trabajadores.filter((trabajador) => {
      const coincideNombre =
        !texto || trabajador.trabajador.toLowerCase().includes(texto);
      const tieneDatos =
        !soloAnalizados || trabajador.perfil_ia !== "Datos insuficientes";
      return coincideNombre && tieneDatos;
    });
  }, [analisis, busqueda, soloAnalizados]);

  return (
    <section className="ia-seccion">
      <div className="ia-encabezado">
        <div>
          <span className="ia-etiqueta">🤖 {analisis?.version || "IA"}</span>
          <h2>Análisis inteligente de productividad</h2>
          <p>
            Analiza patrones históricos de cosecha, detecta valores atípicos y
            estima la producción de una próxima jornada a partir de los datos disponibles.
          </p>
        </div>

        <button type="button" onClick={cargarAnalisis} disabled={cargando}>
          {cargando ? "Analizando..." : "Actualizar análisis"}
        </button>
      </div>

      {error && (
        <div className="ia-error">
          <strong>No se pudo cargar la IA.</strong>
          <span>{error}</span>
        </div>
      )}

      {cargando && !analisis && <p>Procesando datos históricos...</p>}

      {analisis && (
        <>
          <div className="ia-tarjetas">
            <article>
              <span>Registros históricos</span>
              <strong>{formatoNumero(analisis.registros_historicos)}</strong>
            </article>
            <article>
              <span>Trabajadores históricos</span>
              <strong>{formatoNumero(analisis.trabajadores_historicos)}</strong>
            </article>
            <article>
              <span>Analizados por IA</span>
              <strong>{formatoNumero(analisis.trabajadores_analizados_ia)}</strong>
            </article>
            <article>
              <span>Con predicción</span>
              <strong>{formatoNumero(analisis.trabajadores_con_prediccion)}</strong>
            </article>
          </div>

          <div className="ia-modelo">
            <div>
              <strong>{analisis.metodo}</strong>
              <p>{analisis.descripcion}</p>
            </div>
            <span>
              Período: {analisis.periodo.desde} → {analisis.periodo.hasta}
            </span>
          </div>

          {analisis.modelo_predictivo?.entrenado && (
            <div className="ia-prediccion-resumen">
              <div>
                <span>Modelo predictivo</span>
                <strong>Random Forest</strong>
              </div>
              <div>
                <span>Error medio de prueba</span>
                <strong>
                  {formatoNumero(analisis.modelo_predictivo.mae_kg, 1)} kg
                </strong>
              </div>
              <div>
                <span>Registros usados</span>
                <strong>
                  {formatoNumero(analisis.modelo_predictivo.registros_entrenamiento)}
                </strong>
              </div>
              <p>{analisis.modelo_predictivo.descripcion}</p>
            </div>
          )}

          <div className="ia-controles">
            <input
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar trabajador..."
            />

            <label>
              <input
                type="checkbox"
                checked={soloAnalizados}
                onChange={(e) => setSoloAnalizados(e.target.checked)}
              />
              Mostrar solo trabajadores con datos suficientes
            </label>
          </div>

          <div className="ia-tabla-contenedor">
            <table className="ia-tabla">
              <thead>
                <tr>
                  <th>Trabajador</th>
                  <th>Días</th>
                  <th>Promedio</th>
                  <th>Total</th>
                  <th>Tendencia</th>
                  <th>Predicción</th>
                  <th>Perfil IA</th>
                  <th>Apoyo al análisis</th>
                </tr>
              </thead>
              <tbody>
                {trabajadoresFiltrados.map((trabajador) => (
                  <tr key={trabajador.trabajador}>
                    <td>
                      <strong>{trabajador.trabajador}</strong>
                      <small>
                        Último: {formatoNumero(trabajador.ultimo_kg, 1)} kg
                      </small>
                    </td>
                    <td>{trabajador.dias_trabajados}</td>
                    <td>{formatoNumero(trabajador.promedio_kg_dia, 1)} kg/día</td>
                    <td>{formatoNumero(trabajador.total_kg, 1)} kg</td>
                    <td>
                      <span className={claseTendencia(trabajador.tendencia)}>
                        {trabajador.tendencia}
                      </span>
                      <small>
                        {trabajador.tendencia_pct > 0 ? "+" : ""}
                        {formatoNumero(trabajador.tendencia_pct, 1)}%
                      </small>
                    </td>
                    <td>
                      {trabajador.prediccion_proxima_jornada_kg === null ? (
                        <span className="ia-sin-prediccion">Datos insuficientes</span>
                      ) : (
                        <span className="ia-prediccion">
                          ≈ {formatoNumero(trabajador.prediccion_proxima_jornada_kg, 1)} kg
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="ia-perfil">{trabajador.perfil_ia}</span>
                    </td>
                    <td className="ia-recomendacion">
                      {trabajador.recomendacion}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {analisis.registros_atipicos.length > 0 && (
            <div className="ia-atipicos">
              <div className="ia-subtitulo">
                <div>
                  <h3>🔎 Registros atípicos detectados</h3>
                  <p>
                    Son valores que se alejan del patrón habitual del trabajador.
                    Deben revisarse; no significa automáticamente que estén mal.
                  </p>
                </div>
              </div>

              <div className="ia-atipicos-grid">
                {analisis.registros_atipicos.slice(0, 8).map((registro, indice) => (
                  <article key={`${registro.trabajador}-${registro.fecha}-${indice}`}>
                    <strong>{registro.trabajador}</strong>
                    <span>{registro.fecha}</span>
                    <b>
                      {formatoNumero(registro.kilos, 1)} kg · {registro.tipo}
                    </b>
                    <small>
                      Promedio histórico: {formatoNumero(registro.promedio_trabajador, 1)} kg
                    </small>
                  </article>
                ))}
              </div>
            </div>
          )}

          <div className="ia-advertencias">
            <strong>Calidad y uso de los datos</strong>
            <p>
              {analisis.fechas_corregidas} registros usan fechas corregidas a
              partir de la semana y el día indicado en la planilla.
            </p>
            <ul>
              {analisis.advertencias.map((advertencia) => (
                <li key={advertencia}>{advertencia}</li>
              ))}
            </ul>
          </div>
        </>
      )}
    </section>
  );
}

export default AnalisisIA;
