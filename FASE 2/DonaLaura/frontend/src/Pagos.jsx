import { useEffect, useState } from "react";
import "./Pagos.css";

const API_URL = "http://127.0.0.1:8000";

function hoyISO() {
  const hoy = new Date();
  const mes = String(hoy.getMonth() + 1).padStart(2, "0");
  const dia = String(hoy.getDate()).padStart(2, "0");
  return `${hoy.getFullYear()}-${mes}-${dia}`;
}

function formatoPesos(valor) {
  return Number(valor || 0).toLocaleString("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0
  });
}

function formatoFecha(iso) {
  const [anio, mes, dia] = iso.split("-");
  return `${dia}-${mes}-${anio}`;
}

async function leerError(respuesta, mensajePorDefecto) {
  try {
    const datos = await respuesta.json();
    return typeof datos.detail === "string" ? datos.detail : mensajePorDefecto;
  } catch {
    return mensajePorDefecto;
  }
}

function Pagos() {
  const [fecha, setFecha] = useState(hoyISO());
  const [detalle, setDetalle] = useState(null);
  const [historial, setHistorial] = useState([]);
  const [precio, setPrecio] = useState("");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  async function cargarHistorial() {
    try {
      const respuesta = await fetch(`${API_URL}/pagos/historial`);

      if (!respuesta.ok) {
        throw new Error("No se pudo cargar el historial de pagos.");
      }

      setHistorial(await respuesta.json());
    } catch (errorCapturado) {
      setError(errorCapturado.message);
    }
  }

  async function cargarSemana(fechaConsulta) {
    setCargando(true);
    setError("");

    try {
      const respuesta = await fetch(
        `${API_URL}/pagos/semana?fecha=${fechaConsulta}`
      );

      if (!respuesta.ok) {
        throw new Error(
          await leerError(respuesta, "No se pudieron consultar los pagos.")
        );
      }

      const datos = await respuesta.json();
      setDetalle(datos);
      setPrecio(datos.precio_kg !== null ? String(datos.precio_kg) : "");
    } catch (errorCapturado) {
      setError(errorCapturado.message);
      setDetalle(null);
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    cargarHistorial();
  }, []);

  useEffect(() => {
    if (fecha) {
      setMensaje("");
      cargarSemana(fecha);
    }
  }, [fecha]);

  async function guardarTarifa(evento) {
    evento.preventDefault();

    if (guardando) return;

    if (!fecha) {
      setError("Selecciona una fecha válida (por ejemplo, el 30 de septiembre).");
      return;
    }

    const valor = Number(precio);

    if (!valor || valor <= 0) {
      setError("Ingresa un precio por kilo mayor que 0.");
      return;
    }

    setGuardando(true);
    setError("");
    setMensaje("");

    try {
      const respuesta = await fetch(`${API_URL}/tarifas/${fecha}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ precio_kg: valor })
      });

      if (!respuesta.ok) {
        throw new Error(
          await leerError(respuesta, "No se pudo guardar la tarifa.")
        );
      }

      setMensaje("Tarifa de la semana guardada correctamente.");
      await cargarSemana(fecha);
    } catch (errorCapturado) {
      setError(errorCapturado.message);
    } finally {
      setGuardando(false);
    }
  }

  async function cerrarSemana() {
    if (guardando || !detalle || !fecha) return;

    const confirmado = window.confirm(
      `¿Cerrar la semana del ${formatoFecha(detalle.semana_inicio)} al ` +
      `${formatoFecha(detalle.semana_fin)}?\n\n` +
      `Total a pagar: ${formatoPesos(detalle.total_pagar)}\n` +
      "Después de cerrarla no se podrá modificar."
    );

    if (!confirmado) return;

    setGuardando(true);
    setError("");
    setMensaje("");

    try {
      const respuesta = await fetch(`${API_URL}/pagos/cerrar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fecha })
      });

      if (!respuesta.ok) {
        throw new Error(
          await leerError(respuesta, "No se pudo cerrar la semana.")
        );
      }

      setMensaje("Semana cerrada correctamente.");
      await Promise.all([cargarSemana(fecha), cargarHistorial()]);
    } catch (errorCapturado) {
      setError(errorCapturado.message);
    } finally {
      setGuardando(false);
    }
  }

  const sinTarifa = detalle && detalle.precio_kg === null;
  const sinProduccion = detalle && detalle.trabajadores.length === 0;

  return (
    <section className="pagos-seccion">
      <div className="pagos-encabezado">
        <h2>💰 Pagos semanales</h2>
        <p>
          Define el precio por kilo de la semana (lunes a domingo), revisa
          cuánto corresponde pagar a cada trabajador y cierra la semana.
        </p>
      </div>

      <div className="pagos-controles">
        <div className="campo">
          <label htmlFor="pagos-fecha">Semana que contiene el día</label>
          <input
            id="pagos-fecha"
            type="date"
            value={fecha}
            onChange={(evento) => setFecha(evento.target.value)}
          />
        </div>

        <form className="pagos-tarifa" onSubmit={guardarTarifa}>
          <div className="campo">
            <label htmlFor="pagos-precio">Precio por kilo (CLP)</label>
            <input
              id="pagos-precio"
              type="number"
              min="1"
              step="0.01"
              value={precio}
              onChange={(evento) => setPrecio(evento.target.value)}
              disabled={guardando || (detalle && detalle.cerrada)}
              placeholder="Ej.: 80"
            />
          </div>

          <button
            type="submit"
            disabled={guardando || !detalle || detalle.cerrada}
          >
            Guardar tarifa
          </button>
        </form>
      </div>

      {mensaje && <p className="mensaje">{mensaje}</p>}
      {error && <p className="error">{error}</p>}

      {cargando && <p>Cargando pagos...</p>}

      {!cargando && detalle && (
        <>
          <div className="pagos-estado">
            <span>
              Semana del {formatoFecha(detalle.semana_inicio)} al{" "}
              {formatoFecha(detalle.semana_fin)}
            </span>

            <span
              className={detalle.cerrada ? "pagos-cerrada" : "pagos-abierta"}
            >
              {detalle.cerrada ? "Cerrada" : "Sin cerrar"}
            </span>
          </div>

          <div className="pagos-tarjetas">
            <div className="pagos-tarjeta">
              <span>Precio por kilo</span>
              <strong>
                {detalle.precio_kg !== null
                  ? formatoPesos(detalle.precio_kg)
                  : "Sin definir"}
              </strong>
            </div>

            <div className="pagos-tarjeta">
              <span>Kilos de la semana</span>
              <strong>{detalle.total_kilos.toFixed(2)} kg</strong>
            </div>

            <div className="pagos-tarjeta">
              <span>Trabajadores a pagar</span>
              <strong>{detalle.trabajadores.length}</strong>
            </div>

            <div className="pagos-tarjeta">
              <span>Total a pagar</span>
              <strong>
                {sinTarifa ? "—" : formatoPesos(detalle.total_pagar)}
              </strong>
            </div>
          </div>

          {sinTarifa && (
            <p className="pagos-aviso">
              Esta semana no tiene tarifa. Guárdala arriba para calcular los
              montos.
            </p>
          )}

          {sinProduccion ? (
            <p>No hay producción registrada en esta semana.</p>
          ) : (
            <div className="tabla-contenedor">
              <table>
                <thead>
                  <tr>
                    <th>Trabajador</th>
                    <th>RUT</th>
                    <th>Kilos</th>
                    <th>Total a pagar</th>
                  </tr>
                </thead>

                <tbody>
                  {detalle.trabajadores.map((trabajador) => (
                    <tr key={trabajador.id_trabajador}>
                      <td>
                        {trabajador.nombre} {trabajador.apellido}
                      </td>
                      <td>{trabajador.rut || "Sin registrar"}</td>
                      <td>{trabajador.kilos.toFixed(2)} kg</td>
                      <td>
                        {trabajador.total !== null
                          ? formatoPesos(trabajador.total)
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="pagos-acciones">
            {!detalle.cerrada && (
              <button
                type="button"
                onClick={cerrarSemana}
                disabled={guardando || sinTarifa || sinProduccion}
              >
                Cerrar semana
              </button>
            )}

            <a
              className="pagos-descarga"
              href={`${API_URL}/pagos/semana/exportar?fecha=${fecha}`}
            >
              Descargar Excel (CSV)
            </a>
          </div>
        </>
      )}

      <h3>Semanas cerradas</h3>

      {historial.length === 0 ? (
        <p>Aún no hay semanas cerradas.</p>
      ) : (
        <div className="tabla-contenedor">
          <table>
            <thead>
              <tr>
                <th>Semana</th>
                <th>Precio por kilo</th>
                <th>Trabajadores</th>
                <th>Kilos</th>
                <th>Total pagado</th>
                <th></th>
              </tr>
            </thead>

            <tbody>
              {historial.map((semana) => (
                <tr key={semana.semana_inicio}>
                  <td>
                    {formatoFecha(semana.semana_inicio)} al{" "}
                    {formatoFecha(semana.semana_fin)}
                  </td>
                  <td>{formatoPesos(semana.precio_kg)}</td>
                  <td>{semana.trabajadores}</td>
                  <td>{semana.total_kilos.toFixed(2)} kg</td>
                  <td>{formatoPesos(semana.total_pagar)}</td>
                  <td>
                    <button
                      type="button"
                      className="boton-editar"
                      onClick={() => setFecha(semana.semana_inicio)}
                    >
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default Pagos;
