import ReactMarkdown from "react-markdown";
import { useEffect, useRef, useState } from "react";
import "./AsistenteIA.css";

const API_URL = "http://127.0.0.1:8000";

function AsistenteIA() {
  const [mensajes, setMensajes] = useState([
    {
      autor: "ia",
      texto:
        "Hola 👋 Soy el Asistente Inteligente de Doña Laura.\n\n" +
        "Puedo analizar producción, comparar trabajadores, revisar tendencias, " +
        "buscar anomalías, consultar información de la empresa y darte recomendaciones basadas en los datos.\n\n" +
        "¿Qué quieres revisar?"
    }
  ]);

  const [pregunta, setPregunta] = useState("");
  const [cargando, setCargando] = useState(false);
  const [herramientas, setHerramientas] = useState([]);

  const finalChatRef = useRef(null);

  const preguntasRapidas = [
    "Analiza la empresa y dime qué te preocupa",
    "¿Quiénes tienen mejor rendimiento?",
    "¿Qué trabajadores vienen a la baja?",
    "¿Hay registros extraños?",
    "¿Qué tan confiable es el modelo de IA?"
  ];

  useEffect(() => {
    finalChatRef.current?.scrollIntoView({
      behavior: "smooth"
    });
  }, [mensajes, cargando]);

  const enviarPregunta = async (textoPregunta = pregunta) => {
    const texto = textoPregunta.trim();

    if (!texto || cargando) {
      return;
    }

    const nuevoMensaje = {
      autor: "usuario",
      texto
    };

    const historialAnterior = mensajes
      .filter((mensaje) => mensaje.texto)
      .slice(-12)
      .map((mensaje) => ({
        autor: mensaje.autor,
        texto: mensaje.texto
      }));

    setMensajes((anteriores) => [
      ...anteriores,
      nuevoMensaje
    ]);

    setPregunta("");
    setCargando(true);
    setHerramientas([]);

    try {
      const respuesta = await fetch(
        `${API_URL}/ia/agente`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            pregunta: texto,
            historial: historialAnterior
          })
        }
      );

      if (!respuesta.ok) {
        throw new Error(
          `Error HTTP ${respuesta.status}`
        );
      }

      const datos = await respuesta.json();

      setMensajes((anteriores) => [
        ...anteriores,
        {
          autor: "ia",
          texto:
            datos.respuesta ||
            "No pude generar una respuesta."
        }
      ]);

      setHerramientas(
        datos.herramientas_usadas || []
      );

    } catch (error) {
      console.error(
        "Error comunicándose con la IA:",
        error
      );

      setMensajes((anteriores) => [
        ...anteriores,
        {
          autor: "ia",
          texto:
            "⚠️ No pude comunicarme con el asistente inteligente. " +
            "Verifica que el backend esté funcionando."
        }
      ]);

    } finally {
      setCargando(false);
    }
  };

  const manejarTecla = (evento) => {
    if (
      evento.key === "Enter" &&
      !evento.shiftKey
    ) {
      evento.preventDefault();
      enviarPregunta();
    }
  };

  const limpiarConversacion = () => {
    setMensajes([
      {
        autor: "ia",
        texto:
          "Conversación nueva 👋\n\n" +
          "¿Qué quieres analizar de Doña Laura?"
      }
    ]);

    setHerramientas([]);
  };

  return (
    <div className="asistente-page">
      <div className="asistente-contenedor">

        <div className="asistente-header">
          <div>
            <div className="asistente-titulo">
              🤖 Asistente Inteligente
            </div>

            <div className="asistente-subtitulo">
              IA de gestión agrícola · Doña Laura
            </div>
          </div>

          <button
            className="boton-limpiar"
            onClick={limpiarConversacion}
          >
            Nueva conversación
          </button>
        </div>

        <div className="estado-ia">
          <span className="estado-punto"></span>
          IA conectada a datos de Doña Laura
        </div>

        <div className="preguntas-rapidas">
          {preguntasRapidas.map(
            (preguntaRapida, indice) => (
              <button
                key={indice}
                onClick={() =>
                  enviarPregunta(
                    preguntaRapida
                  )
                }
                disabled={cargando}
              >
                {preguntaRapida}
              </button>
            )
          )}
        </div>

        <div className="chat-contenedor">

          {mensajes.map(
            (mensaje, indice) => (
              <div
                key={indice}
                className={
                  mensaje.autor === "usuario"
                    ? "fila-mensaje usuario"
                    : "fila-mensaje ia"
                }
              >
                <div
                  className={
                    mensaje.autor === "usuario"
                      ? "mensaje mensaje-usuario"
                      : "mensaje mensaje-ia"
                  }
                >
                  {mensaje.autor === "ia" && (
                    <div className="nombre-ia">
                      🤖 Asistente Doña Laura
                    </div>
                  )}

                  <div className="texto-mensaje">
  {mensaje.autor === "ia" ? (
    <ReactMarkdown>
      {mensaje.texto}
    </ReactMarkdown>
  ) : (
    mensaje.texto
  )}
</div>
                </div>
              </div>
            )
          )}

          {cargando && (
            <div className="fila-mensaje ia">
              <div className="mensaje mensaje-ia">
                <div className="nombre-ia">
                  🤖 Asistente Doña Laura
                </div>

                <div className="pensando">
                  <span></span>
                  <span></span>
                  <span></span>

                  <small>
                    Analizando información...
                  </small>
                </div>
              </div>
            </div>
          )}

          <div ref={finalChatRef}></div>
        </div>

        {herramientas.length > 0 && (
          <div className="herramientas-usadas">
            <span>
              🔎 Fuentes consultadas por la IA:
            </span>

            {herramientas.map(
              (herramienta, indice) => (
                <span
                  className="herramienta-chip"
                  key={`${herramienta}-${indice}`}
                >
                  {herramienta}
                </span>
              )
            )}
          </div>
        )}

        <div className="entrada-chat">
          <textarea
            value={pregunta}
            onChange={(evento) =>
              setPregunta(
                evento.target.value
              )
            }
            onKeyDown={manejarTecla}
            placeholder="Pregúntame cualquier cosa sobre Doña Laura..."
            disabled={cargando}
            rows={1}
          />

          <button
            onClick={() =>
              enviarPregunta()
            }
            disabled={
              cargando ||
              !pregunta.trim()
            }
          >
            {cargando
              ? "..."
              : "➤"}
          </button>
        </div>

        <div className="aviso-ia">
          La IA entrega análisis y recomendaciones
          basadas en los datos disponibles. Sus
          predicciones son orientativas.
        </div>

      </div>
    </div>
  );
}

export default AsistenteIA;