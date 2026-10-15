import { useEffect, useState } from "react";
import "./Reportes.css";

const API_URL = "http://127.0.0.1:8000";

const FAMILIAS = {
  produccion: {
    nombre: "Producción",
    descripcion: "Kilos y horas trabajadas según los registros de cosecha.",
    tipos: {
      detalle: "Detalle de cada registro",
      trabajador: "Resumen por trabajador",
      sector: "Resumen por sector",
      labor: "Resumen por labor",
      dia: "Resumen por día"
    }
  },
  pagos: {
    nombre: "Pagos",
    descripcion: "Pagos de las semanas ya cerradas.",
    tipos: {
      detalle: "Detalle de cada pago",
      trabajador: "Resumen por trabajador",
      semana: "Resumen por semana"
    }
  }
};

const filtrosIniciales = {
  fecha_inicio: "",
  fecha_fin: "",
  id_sector: "",
  id_labor: "",
  id_trabajador: ""
};

function formatoFecha(iso) {
  const [anio, mes, dia] = iso.split("-");
  return `${dia}-${mes}-${anio}`;
}

function formatoValor(valor, formato) {
  if (valor === null || valor === undefined || valor === "") return "—";

  if (formato === "fecha") return formatoFecha(valor);

  if (formato === "pesos") {
    return Number(valor).toLocaleString("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0
    });
  }

  if (formato === "numero") {
    return Number(valor).toLocaleString("es-CL", {
      maximumFractionDigits: 2
    });
  }

  return valor;
}

function describirFiltros(filtros) {
  const partes = [
    filtros.fecha_inicio && `desde ${formatoFecha(filtros.fecha_inicio)}`,
    filtros.fecha_fin && `hasta ${formatoFecha(filtros.fecha_fin)}`,
    filtros.trabajador && `trabajador ${filtros.trabajador}`,
    filtros.sector && `sector ${filtros.sector}`,
    filtros.labor && `labor ${filtros.labor}`
  ].filter(Boolean);

  return partes.length > 0 ? partes.join(" · ") : "ninguno (todos los datos)";
}

function Reportes() {
  const [familia, setFamilia] = useState("produccion");
  const [tipo, setTipo] = useState("detalle");
  const [filtros, setFiltros] = useState(filtrosIniciales);
  const [reporte, setReporte] = useState(null);
  const [consulta, setConsulta] = useState("");
  const [generadoEl, setGeneradoEl] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  const [sectores, setSectores] = useState([]);
  const [labores, setLabores] = useState([]);
  const [trabajadores, setTrabajadores] = useState([]);

  // Opciones de los filtros
  useEffect(() => {
    async function cargarOpciones() {
      try {
        const [rSectores, rLabores, rTrabajadores] = await Promise.all([
          fetch(`${API_URL}/sectores`),
          fetch(`${API_URL}/labores`),
          fetch(`${API_URL}/trabajadores`)
        ]);

        if (!rSectores.ok || !rLabores.ok || !rTrabajadores.ok) {
          throw new Error("No se pudieron cargar los filtros.");
        }

        setSectores(await rSectores.json());
        setLabores(await rLabores.json());
        setTrabajadores(await rTrabajadores.json());
      } catch (errorCapturado) {
        setError(errorCapturado.message);
      }
    }

    cargarOpciones();
  }, []);

  function armarConsulta(familiaActual, tipoActual, filtrosActuales) {
    const parametros = new URLSearchParams({ tipo: tipoActual });

    Object.entries(filtrosActuales).forEach(([clave, valor]) => {
      const aplica =
        familiaActual === "produccion" ||
        clave === "fecha_inicio" ||
        clave === "fecha_fin" ||
        clave === "id_trabajador";

      if (valor !== "" && aplica) {
        parametros.append(clave, valor);
      }
    });

    return parametros.toString();
  }

  async function generarReporte(evento) {
    if (evento) evento.preventDefault();

    if (
      filtros.fecha_inicio &&
      filtros.fecha_fin &&
      filtros.fecha_inicio > filtros.fecha_fin
    ) {
      setError("La fecha de inicio no puede ser posterior a la fecha de fin.");
      return;
    }

    setCargando(true);
    setError("");

    const parametros = armarConsulta(familia, tipo, filtros);

    try {
      const respuesta = await fetch(
        `${API_URL}/reportes/${familia}?${parametros}`
      );

      if (!respuesta.ok) {
        let mensaje = "No se pudo generar el reporte.";

        try {
          const datos = await respuesta.json();
          if (typeof datos.detail === "string") mensaje = datos.detail;
        } catch {
          // Se conserva el mensaje por defecto.
        }

        throw new Error(mensaje);
      }

      setReporte(await respuesta.json());
      setConsulta(`${familia}/exportar?${parametros}`);
      setGeneradoEl(new Date().toLocaleString("es-CL"));
    } catch (errorCapturado) {
      setError(errorCapturado.message);
      setReporte(null);
    } finally {
      setCargando(false);
    }
  }

  function cambiarFamilia(nuevaFamilia) {
    setFamilia(nuevaFamilia);
    setTipo("detalle");
    setReporte(null);
    setError("");
  }

  function actualizarFiltro(evento) {
    const { name, value } = evento.target;
    setFiltros((anteriores) => ({ ...anteriores, [name]: value }));
  }

  function limpiarFiltros() {
    setFiltros(filtrosIniciales);
    setReporte(null);
    setError("");
  }

  const esProduccion = familia === "produccion";

  return (
    <section className="reportes-seccion">
      <div className="reportes-encabezado">
        <h2>📄 Reportes</h2>
        <p>
          Genera reportes de producción y pagos, descárgalos en Excel (CSV) o
          imprímelos / guárdalos como PDF.
        </p>
      </div>

      <div className="reportes-familias">
        {Object.entries(FAMILIAS).map(([clave, datos]) => (
          <button
            key={clave}
            type="button"
            className={
              familia === clave ? "reportes-familia activa" : "reportes-familia"
            }
            onClick={() => cambiarFamilia(clave)}
          >
            <strong>{datos.nombre}</strong>
            <span>{datos.descripcion}</span>
          </button>
        ))}
      </div>

      <form className="reportes-filtros" onSubmit={generarReporte}>
        <div className="campo">
          <label htmlFor="rep-tipo">Tipo de reporte</label>
          <select
            id="rep-tipo"
            value={tipo}
            onChange={(evento) => {
              setTipo(evento.target.value);
              setReporte(null);
            }}
          >
            {Object.entries(FAMILIAS[familia].tipos).map(([clave, nombre]) => (
              <option key={clave} value={clave}>
                {nombre}
              </option>
            ))}
          </select>
        </div>

        <div className="campo">
          <label htmlFor="rep-desde">Desde</label>
          <input
            id="rep-desde"
            name="fecha_inicio"
            type="date"
            value={filtros.fecha_inicio}
            onChange={actualizarFiltro}
          />
        </div>

        <div className="campo">
          <label htmlFor="rep-hasta">Hasta</label>
          <input
            id="rep-hasta"
            name="fecha_fin"
            type="date"
            value={filtros.fecha_fin}
            onChange={actualizarFiltro}
          />
        </div>

        <div className="campo">
          <label htmlFor="rep-trabajador">Trabajador</label>
          <select
            id="rep-trabajador"
            name="id_trabajador"
            value={filtros.id_trabajador}
            onChange={actualizarFiltro}
          >
            <option value="">Todos</option>
            {trabajadores.map((trabajador) => (
              <option key={trabajador.id} value={trabajador.id}>
                {trabajador.nombre} {trabajador.apellido}
              </option>
            ))}
          </select>
        </div>

        {esProduccion && (
          <>
            <div className="campo">
              <label htmlFor="rep-sector">Sector</label>
              <select
                id="rep-sector"
                name="id_sector"
                value={filtros.id_sector}
                onChange={actualizarFiltro}
              >
                <option value="">Todos</option>
                {sectores.map((sector) => (
                  <option key={sector.id} value={sector.id}>
                    {sector.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div className="campo">
              <label htmlFor="rep-labor">Labor</label>
              <select
                id="rep-labor"
                name="id_labor"
                value={filtros.id_labor}
                onChange={actualizarFiltro}
              >
                <option value="">Todas</option>
                {labores.map((labor) => (
                  <option key={labor.id} value={labor.id}>
                    {labor.nombre}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        <div className="reportes-botones">
          <button type="submit" disabled={cargando}>
            {cargando ? "Generando..." : "Generar reporte"}
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

      {reporte && (
        <div className="reportes-resultado">
          <div className="reportes-cabecera-impresion">
            <p className="reportes-marca">Doña Laura · Gestión agrícola</p>
            <h3>{reporte.titulo}</h3>
            <p>Generado el {generadoEl}</p>
            <p>Filtros: {describirFiltros(reporte.filtros)}</p>
          </div>

          <div className="reportes-acciones">
            <span>
              {reporte.total_filas}{" "}
              {reporte.total_filas === 1 ? "fila" : "filas"}
            </span>

            <div>
              <a
                className="reportes-descarga"
                href={`${API_URL}/reportes/${consulta}`}
              >
                Descargar Excel (CSV)
              </a>

              <button type="button" onClick={() => window.print()}>
                Imprimir / guardar PDF
              </button>
            </div>
          </div>

          {reporte.truncado && (
            <p className="reportes-aviso">
              Se muestran solo las primeras filas. Acota las fechas para ver el
              resto.
            </p>
          )}

          {reporte.filas.length === 0 ? (
            <p>No hay datos para los filtros seleccionados.</p>
          ) : (
            <div className="tabla-contenedor">
              <table>
                <thead>
                  <tr>
                    {reporte.columnas.map((columna) => (
                      <th
                        key={columna.clave}
                        className={
                          columna.formato === "numero" ||
                          columna.formato === "pesos"
                            ? "reportes-numero"
                            : ""
                        }
                      >
                        {columna.titulo}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {reporte.filas.map((fila, indice) => (
                    <tr key={indice}>
                      {reporte.columnas.map((columna) => (
                        <td
                          key={columna.clave}
                          className={
                            columna.formato === "numero" ||
                            columna.formato === "pesos"
                              ? "reportes-numero"
                              : ""
                          }
                        >
                          {formatoValor(fila[columna.clave], columna.formato)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>

                <tfoot>
                  <tr>
                    {reporte.columnas.map((columna, indice) => (
                      <td
                        key={columna.clave}
                        className={
                          columna.formato === "numero" ||
                          columna.formato === "pesos"
                            ? "reportes-numero"
                            : ""
                        }
                      >
                        {indice === 0
                          ? "TOTAL"
                          : formatoValor(
                              reporte.totales[columna.clave],
                              columna.formato
                            )}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default Reportes;
