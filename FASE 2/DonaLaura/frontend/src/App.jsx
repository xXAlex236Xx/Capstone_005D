import { useEffect, useState } from "react";
import "./App.css";
import Trabajadores from "./Trabajadores";
import Cosechas from "./Cosechas";
import Productividad from "./Productividad";
import Pagos from "./Pagos";
import Reportes from "./Reportes";
import Administracion from "./Administracion";
import Importacion from "./Importacion";
import AnalisisIA from "./AnalisisIA";
import AsistenteIA from "./AsistenteIA";

// "persistente": la pantalla se mantiene montada al cambiar de sección
// para no perder la conversación o la vista previa en curso.
const GRUPOS = [
  {
    nombre: "Análisis",
    secciones: [
      { id: "productividad", etiqueta: "Productividad", icono: "📊", Vista: Productividad },
      { id: "asistente", etiqueta: "Asistente IA", icono: "💬", Vista: AsistenteIA, persistente: true },
      { id: "analisis-ia", etiqueta: "Análisis IA", icono: "🤖", Vista: AnalisisIA }
    ]
  },
  {
    nombre: "Operación",
    secciones: [
      { id: "trabajadores", etiqueta: "Trabajadores", icono: "👷", Vista: Trabajadores },
      { id: "cosechas", etiqueta: "Cosechas", icono: "🥑", Vista: Cosechas },
      { id: "importacion", etiqueta: "Importación", icono: "📥", Vista: Importacion, persistente: true }
    ]
  },
  {
    nombre: "Finanzas",
    secciones: [
      { id: "pagos", etiqueta: "Pagos", icono: "💰", Vista: Pagos },
      { id: "reportes", etiqueta: "Reportes", icono: "📄", Vista: Reportes }
    ]
  },
  {
    nombre: "Sistema",
    secciones: [
      { id: "administracion", etiqueta: "Administración", icono: "⚙️", Vista: Administracion }
    ]
  }
];

const SECCIONES = GRUPOS.flatMap((grupo) => grupo.secciones);
const SECCION_INICIAL = "productividad";

function seccionDesdeHash() {
  const id = window.location.hash.replace("#", "");
  return SECCIONES.some((seccion) => seccion.id === id) ? id : SECCION_INICIAL;
}

function App() {
  const [activa, setActiva] = useState(seccionDesdeHash);
  const [visitadas, setVisitadas] = useState(() => new Set([seccionDesdeHash()]));
  const [menuAbierto, setMenuAbierto] = useState(false);

  // Mantiene la sección en la URL (#pagos, #reportes...) y responde a atrás/adelante
  useEffect(() => {
    function alCambiarHash() {
      const id = seccionDesdeHash();
      setActiva(id);
      setVisitadas((anteriores) => new Set(anteriores).add(id));
      setMenuAbierto(false);
      window.scrollTo({ top: 0 });
    }

    window.addEventListener("hashchange", alCambiarHash);
    return () => window.removeEventListener("hashchange", alCambiarHash);
  }, []);

  const seccionActual = SECCIONES.find((seccion) => seccion.id === activa);

  return (
    <div className="aplicacion">
      <aside className={menuAbierto ? "barra-lateral abierta" : "barra-lateral"}>
        <div className="marca">
          <span className="marca-icono">🌱</span>
          <div>
            <strong>Doña Laura</strong>
            <span>Gestión agrícola</span>
          </div>
        </div>

        <nav aria-label="Secciones del sistema">
          {GRUPOS.map((grupo) => (
            <div className="menu-grupo" key={grupo.nombre}>
              <p className="menu-grupo-titulo">{grupo.nombre}</p>

              {grupo.secciones.map((seccion) => (
                <a
                  key={seccion.id}
                  href={`#${seccion.id}`}
                  className={
                    seccion.id === activa
                      ? "enlace-menu enlace-actual"
                      : "enlace-menu"
                  }
                  aria-current={seccion.id === activa ? "page" : undefined}
                >
                  <span aria-hidden="true">{seccion.icono}</span>
                  {seccion.etiqueta}
                </a>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      {menuAbierto && (
        <div className="fondo-menu" onClick={() => setMenuAbierto(false)} />
      )}

      <div className="contenido">
        <div className="barra-superior">
          <button
            type="button"
            className="boton-menu"
            onClick={() => setMenuAbierto(true)}
            aria-label="Abrir menú"
          >
            ☰
          </button>
          <strong>{seccionActual.etiqueta}</strong>
        </div>

        <main>
          {SECCIONES.map(({ id, Vista, persistente }) => {
            const esActiva = id === activa;

            if (!esActiva && !(persistente && visitadas.has(id))) return null;

            return (
              <div className="vista-contenido" key={id} hidden={!esActiva}>
                <Vista />
              </div>
            );
          })}
        </main>
      </div>
    </div>
  );
}

export default App;
