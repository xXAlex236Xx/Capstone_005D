
import { useEffect, useState } from "react";
import "./Productividad.css";

const API_URL = "http://127.0.0.1:8000";

const filtrosIniciales = {
  fecha_inicio: "",
  fecha_fin: "",
  id_sector: "",
  id_labor: ""
};

function Productividad() {
  const [datos, setDatos] = useState([]);
  const [sectores, setSectores] = useState([]);
  const [labores, setLabores] = useState([]);
  const [filtros, setFiltros] = useState(filtrosIniciales);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  // Obtener los sectores y las labores para los filtros
  useEffect(() => {
    async function cargarOpciones() {
      try {
        const [respuestaSectores, respuestaLabores] = await Promise.all([
          fetch(`${API_URL}/sectores`),
          fetch(`${API_URL}/labores`)
        ]);

        if (!respuestaSectores.ok || !respuestaLabores.ok) {
          throw new Error("No se pudieron cargar los filtros.");
        }

        setSectores(await respuestaSectores.json());
        setLabores(await respuestaLabores.json());
      } catch (errorCapturado) {
        setError(errorCapturado.message);
      }
    }

    cargarOpciones();
  }, []);

  async function cargarProductividad(filtrosAplicados = filtrosIniciales) {
    setCargando(true);
    setError("");

    try {
      const parametros = new URLSearchParams();

      Object.entries(filtrosAplicados).forEach(([clave, valor]) => {
        if (valor !== "") {
          parametros.append(clave, valor);
        }
      });

      const url = `${API_URL}/productividad?${parametros.toString()}`;

      const respuesta = await fetch(url);

      if (!respuesta.ok) {
        throw new Error("No se pudo consultar la productividad.");
      }

      const resultado = await respuesta.json();
      setDatos(resultado);
    } catch (errorCapturado) {
      setError(errorCapturado.message);
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    cargarProductividad();
  }, []);

  function actualizarFiltro(evento) {
    const { name, value } = evento.target;

    setFiltros((anteriores) => ({
      ...anteriores,
      [name]: value
    }));
  }

  function aplicarFiltros(evento) {
    evento.preventDefault();

    if (
      filtros.fecha_inicio &&
      filtros.fecha_fin &&
      filtros.fecha_inicio > filtros.fecha_fin
    ) {
      setError("La fecha de inicio no puede ser posterior a la fecha de fin.");
      return;
    }

    cargarProductividad(filtros);
  }

  function limpiarFiltros() {
    setFiltros(filtrosIniciales);
    cargarProductividad(filtrosIniciales);
  }

  const totalKilos = datos.reduce(
    (acumulado, trabajador) =>
      acumulado + Number(trabajador.total_kg),
    0
  );

  const totalHoras = datos.reduce(
    (acumulado, trabajador) =>
      acumulado + Number(trabajador.total_horas),
    0
  );

  const productividadGeneral =
    totalHoras > 0 ? totalKilos / totalHoras : 0;

  const mayorProductividad = Math.max(
    0,
    ...datos.map((trabajador) => Number(trabajador.kg_por_hora) || 0)
  );

  return (
    <section className="productividad-seccion">
      <div className="productividad-encabezado">
        <div>
          <h2>📊 Dashboard de productividad</h2>
          <p>Analiza la producción por fecha, sector y labor.</p>
        </div>
      </div>

      {/* FILTROS */}
      <form className="filtros-productividad" onSubmit={aplicarFiltros}>
        <div className="campo">
          <label htmlFor="fecha-inicio">Desde</label>
          <input
            id="fecha-inicio"
            name="fecha_inicio"
            type="date"
            value={filtros.fecha_inicio}
            onChange={actualizarFiltro}
          />
        </div>

        <div className="campo">
          <label htmlFor="fecha-fin">Hasta</label>
          <input
            id="fecha-fin"
            name="fecha_fin"
            type="date"
            value={filtros.fecha_fin}
            onChange={actualizarFiltro}
          />
        </div>

        <div className="campo">
          <label htmlFor="filtro-sector">Sector</label>
          <select
            id="filtro-sector"
            name="id_sector"
            value={filtros.id_sector}
            onChange={actualizarFiltro}
          >
            <option value="">Todos los sectores</option>

            {sectores.map((sector) => (
              <option key={sector.id} value={sector.id}>
                {sector.nombre}
              </option>
            ))}
          </select>
        </div>

        <div className="campo">
          <label htmlFor="filtro-labor">Labor</label>
          <select
            id="filtro-labor"
            name="id_labor"
            value={filtros.id_labor}
            onChange={actualizarFiltro}
          >
            <option value="">Todas las labores</option>

            {labores.map((labor) => (
              <option key={labor.id} value={labor.id}>
                {labor.nombre}
              </option>
            ))}
          </select>
        </div>

        <div className="botones-filtros">
          <button type="submit" disabled={cargando}>
            Aplicar filtros
          </button>

          <button
            type="button"
            className="boton-limpiar"
            onClick={limpiarFiltros}
            disabled={cargando}
          >
            Limpiar
          </button>
        </div>
      </form>

      {error && <p className="error">{error}</p>}

      {cargando ? (
        <p>Cargando productividad...</p>
      ) : (
        <>
          {/* TARJETAS DE RESUMEN */}
          <div className="tarjetas-productividad">
            <div className="tarjeta-productividad">
              <span>Kilos cosechados</span>
              <strong>{totalKilos.toFixed(2)} kg</strong>
            </div>

            <div className="tarjeta-productividad">
              <span>Horas trabajadas</span>
              <strong>{totalHoras.toFixed(2)} h</strong>
            </div>

            <div className="tarjeta-productividad">
              <span>Productividad general</span>
              <strong>{productividadGeneral.toFixed(2)} kg/h</strong>
            </div>

            <div className="tarjeta-productividad">
              <span>Trabajadores con producción</span>
              <strong>{datos.length}</strong>
            </div>
          </div>

          {/* GRÁFICO */}
          <h3>Productividad por trabajador</h3>

          {datos.length === 0 ? (
            <p>No hay cosechas registradas para los filtros seleccionados.</p>
          ) : (
            <div className="grafico-productividad">
              {datos.map((trabajador) => {
                const rendimiento =
                  Number(trabajador.kg_por_hora) || 0;

                const porcentaje =
                  mayorProductividad > 0
                    ? (rendimiento / mayorProductividad) * 100
                    : 0;

                return (
                  <div
                    className="fila-productividad"
                    key={trabajador.id_trabajador}
                  >
                    <div className="fila-productividad-info">
                      <strong>
                        {trabajador.nombre} {trabajador.apellido}
                      </strong>

                      <span>{rendimiento.toFixed(2)} kg/h</span>
                    </div>

                    <div className="barra-fondo">
                      <div
                        className="barra-valor"
                        style={{ width: `${porcentaje}%` }}
                      />
                    </div>

                    <small>
                      {Number(trabajador.total_kg).toFixed(2)} kg
                      {" · "}
                      {Number(trabajador.total_horas).toFixed(2)} horas
                    </small>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default Productividad;