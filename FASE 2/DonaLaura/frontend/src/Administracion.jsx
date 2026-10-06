
import { useEffect, useState } from "react";
import "./Administracion.css";

const API = "http://127.0.0.1:8000";
const JORNADAS_POR_PAGINA = 10;

function Administracion() {
  const [jornadas, setJornadas] = useState([]);
  const [sectores, setSectores] = useState([]);
  const [labores, setLabores] = useState([]);

  const [fecha, setFecha] = useState("");
  const [observaciones, setObservaciones] = useState("");

  const [nombreSector, setNombreSector] = useState("");
  const [descripcionSector, setDescripcionSector] = useState("");

  const [nombreLabor, setNombreLabor] = useState("");
  const [descripcionLabor, setDescripcionLabor] = useState("");

  const [buscarFecha, setBuscarFecha] = useState("");
  const [pagina, setPagina] = useState(1);

  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function cargarDatos() {
    try {
      const respuestas = await Promise.all([
        fetch(`${API}/jornadas`),
        fetch(`${API}/sectores`),
        fetch(`${API}/labores`)
      ]);

      if (respuestas.some((respuesta) => !respuesta.ok)) {
        throw new Error("No se pudieron cargar los registros.");
      }

      const [datosJornadas, datosSectores, datosLabores] =
        await Promise.all(
          respuestas.map((respuesta) => respuesta.json())
        );

      setJornadas(datosJornadas);
      setSectores(datosSectores);
      setLabores(datosLabores);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    cargarDatos();
  }, []);

  async function guardar(ruta, datos, limpiarFormulario) {
    setMensaje("");
    setError("");
    setGuardando(true);

    try {
      const respuesta = await fetch(`${API}/${ruta}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(datos)
      });

      const resultado = await respuesta.json();

      if (!respuesta.ok) {
        throw new Error(
          typeof resultado.detail === "string"
            ? resultado.detail
            : "No se pudo guardar el registro."
        );
      }

      setMensaje("Registro creado correctamente.");
      limpiarFormulario();
      await cargarDatos();
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  }

  function crearJornada(evento) {
    evento.preventDefault();

    guardar(
      "jornadas",
      {
        fecha,
        observaciones: observaciones.trim() || null
      },
      () => {
        setFecha("");
        setObservaciones("");
        setBuscarFecha("");
        setPagina(1);
      }
    );
  }

  function crearSector(evento) {
    evento.preventDefault();

    guardar(
      "sectores",
      {
        nombre: nombreSector.trim(),
        descripcion: descripcionSector.trim() || null
      },
      () => {
        setNombreSector("");
        setDescripcionSector("");
      }
    );
  }

  function crearLabor(evento) {
    evento.preventDefault();

    guardar(
      "labores",
      {
        nombre: nombreLabor.trim(),
        descripcion: descripcionLabor.trim() || null
      },
      () => {
        setNombreLabor("");
        setDescripcionLabor("");
      }
    );
  }

  // Buscar por fecha y ordenar de más reciente a más antigua.
  const jornadasFiltradas = jornadas
    .filter((jornada) =>
      !buscarFecha || jornada.fecha === buscarFecha
    )
    .sort((a, b) => b.fecha.localeCompare(a.fecha));

  const totalPaginas = Math.max(
    1,
    Math.ceil(jornadasFiltradas.length / JORNADAS_POR_PAGINA)
  );

  const paginaActual = Math.min(pagina, totalPaginas);

  const jornadasVisibles = jornadasFiltradas.slice(
    (paginaActual - 1) * JORNADAS_POR_PAGINA,
    paginaActual * JORNADAS_POR_PAGINA
  );

  return (
    <section className="administracion">
      <div className="administracion-titulo">
        <h2>Administración agrícola</h2>
        <p>
          Gestiona las jornadas, sectores y labores de Doña Laura.
        </p>
      </div>

      {mensaje && (
        <p className="administracion-exito">{mensaje}</p>
      )}

      {error && (
        <p className="administracion-error">{error}</p>
      )}

      <div className="administracion-grid">
        {/* JORNADAS */}
        <article className="administracion-tarjeta">
          <h3>📅 Jornadas</h3>

          <form onSubmit={crearJornada}>
            <label htmlFor="nueva-fecha">Fecha</label>
            <input
              id="nueva-fecha"
              type="date"
              value={fecha}
              onChange={(e) => setFecha(e.target.value)}
              required
            />

            <label htmlFor="nueva-observacion">
              Observaciones
            </label>
            <textarea
              id="nueva-observacion"
              value={observaciones}
              onChange={(e) =>
                setObservaciones(e.target.value)
              }
              placeholder="Opcional"
              rows={3}
            />

            <button type="submit" disabled={guardando}>
              Crear jornada
            </button>
          </form>

          <h4>
            Jornadas registradas ({jornadas.length})
          </h4>

          <div className="administracion-buscador">
            <label htmlFor="buscar-jornada">
              Buscar por fecha
            </label>

            <div className="administracion-buscador-fila">
              <input
                id="buscar-jornada"
                type="date"
                value={buscarFecha}
                onChange={(e) => {
                  setBuscarFecha(e.target.value);
                  setPagina(1);
                }}
              />

              {buscarFecha && (
                <button
                  type="button"
                  className="administracion-limpiar"
                  onClick={() => {
                    setBuscarFecha("");
                    setPagina(1);
                  }}
                >
                  Limpiar
                </button>
              )}
            </div>
          </div>

          <p className="administracion-contador">
            {jornadasFiltradas.length} jornadas encontradas
          </p>

          <div className="administracion-lista">
            {jornadasVisibles.map((jornada) => (
              <div
                key={jornada.id}
                className="administracion-item"
              >
                📅 {jornada.fecha}
              </div>
            ))}

            {jornadasVisibles.length === 0 && (
              <p className="administracion-vacio">
                No hay jornadas para esa fecha.
              </p>
            )}
          </div>

          {totalPaginas > 1 && (
            <div className="administracion-paginacion">
              <button
                type="button"
                disabled={paginaActual === 1}
                onClick={() =>
                  setPagina(paginaActual - 1)
                }
              >
                Anterior
              </button>

              <span>
                Página {paginaActual} de {totalPaginas}
              </span>

              <button
                type="button"
                disabled={paginaActual === totalPaginas}
                onClick={() =>
                  setPagina(paginaActual + 1)
                }
              >
                Siguiente
              </button>
            </div>
          )}
        </article>

        {/* SECTORES */}
        <article className="administracion-tarjeta">
          <h3>🌱 Sectores</h3>

          <form onSubmit={crearSector}>
            <label htmlFor="nuevo-sector">
              Nombre del sector
            </label>
            <input
              id="nuevo-sector"
              value={nombreSector}
              onChange={(e) =>
                setNombreSector(e.target.value)
              }
              placeholder="Ej.: Sector Norte"
              maxLength={100}
              required
            />

            <label htmlFor="descripcion-sector">
              Descripción
            </label>
            <textarea
              id="descripcion-sector"
              value={descripcionSector}
              onChange={(e) =>
                setDescripcionSector(e.target.value)
              }
              placeholder="Opcional"
              rows={3}
            />

            <button type="submit" disabled={guardando}>
              Crear sector
            </button>
          </form>

          <h4>
            Sectores registrados ({sectores.length})
          </h4>

          <div className="administracion-lista">
            {sectores.map((sector) => (
              <div
                key={sector.id}
                className="administracion-item"
              >
                {sector.nombre}
              </div>
            ))}
          </div>
        </article>

        {/* LABORES */}
        <article className="administracion-tarjeta">
          <h3>🧑‍🌾 Labores</h3>

          <form onSubmit={crearLabor}>
            <label htmlFor="nueva-labor">
              Nombre de la labor
            </label>
            <input
              id="nueva-labor"
              value={nombreLabor}
              onChange={(e) =>
                setNombreLabor(e.target.value)
              }
              placeholder="Ej.: Cosecha"
              maxLength={100}
              required
            />

            <label htmlFor="descripcion-labor">
              Descripción
            </label>
            <textarea
              id="descripcion-labor"
              value={descripcionLabor}
              onChange={(e) =>
                setDescripcionLabor(e.target.value)
              }
              placeholder="Opcional"
              rows={3}
            />

            <button type="submit" disabled={guardando}>
              Crear labor
            </button>
          </form>

          <h4>
            Labores registradas ({labores.length})
          </h4>

          <div className="administracion-lista">
            {labores.map((labor) => (
              <div
                key={labor.id}
                className="administracion-item"
              >
                {labor.nombre}
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

export default Administracion;
