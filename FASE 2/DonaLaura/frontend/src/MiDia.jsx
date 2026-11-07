import { useEffect, useState } from "react";
import { solicitar } from "./api";
import Icon from "./Icon";
import "./MiDia.css";

const numero = n => new Intl.NumberFormat("es-CL", { maximumFractionDigits: 1 }).format(Number(n));
const pesos = n => new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(Number(n));
const fecha = f => f ? new Intl.DateTimeFormat("es-CL", { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(`${f}T12:00:00Z`)) : "Sin registros";

export default function MiDia({ usuario }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let vigente = true;
    solicitar("/mi-dia").then(d => { if (vigente) { setDatos(d); setError(""); } }).catch(e => vigente && setError(e.message));
    return () => { vigente = false; };
  }, [version]);
  if (!datos) return error ? <p className="error" role="alert">{error} <button onClick={() => setVersion(v => v + 1)}>Reintentar</button></p> : <p>Cargando tu día…</p>;
  const puede = usuario.rol !== "consulta";
  const sinRegistro = datos.faenas.filter(f => !f.registros_hoy).length;
  return <section className="mi-dia">
    <div className="page-heading"><div><span className="eyebrow">TU OPERACIÓN, PASO A PASO · {fecha(datos.fecha)}</span><h1>Hola, {usuario.nombre}. Este es tu día.</h1><p>Lo que ya registraste y lo que conviene revisar, en un solo lugar.</p></div><button className="boton-secundario" onClick={() => setVersion(v => v + 1)}><Icon nombre="actualizar" size={16}/> Actualizar pendientes</button></div>
    {error && <p className="error" role="alert">{error} Los datos visibles corresponden a la última carga correcta.</p>}
    <div className="dia-hero"><div><span className="eyebrow">{datos.registros_hoy ? "HOY YA HAY MOVIMIENTO" : "EMPIEZA POR LA JORNADA"}</span><h2>{datos.registros_hoy ? `${numero(datos.kilos_hoy)} kilos registrados hoy` : "¿Hubo cosecha hoy? Déjala registrada."}</h2><p>{datos.registros_hoy ? `${datos.personas_hoy} personas · ${datos.registros_hoy} registros. Puedes agregar otro equipo o revisar lo ingresado.` : "Puedes cargar el equipo de una jornada anterior y completar solo los kilos y horas de esta jornada."}</p><a className="boton-enlace" href="#cosechas?vista=registro"><Icon nombre="cosechas" size={17}/>{puede ? "Registrar o repetir jornada" : "Revisar cosechas"}<Icon nombre="flecha" size={16}/></a></div><div className="dia-hero-fecha"><span>Última producción registrada</span><strong>{fecha(datos.ultima_produccion)}</strong><small>La ausencia de registros no confirma que haya faltado una jornada.</small></div></div>
    <div className="dia-section-title"><h2>Primero, lo importante</h2><span>Pendientes y accesos rápidos</span></div>
    <div className="dia-pendientes">
      <a href="#cobros" className="dia-tarea"><span className="dia-tarea-icon"><Icon nombre="cobros"/></span><strong>{pesos(datos.cobros_clientes.saldo)} por recibir de clientes</strong><p>{datos.cobros_clientes.vencidos} cobros vencidos · {datos.cobros_clientes.vencen_hoy} vencen hoy. Solo acuerdos confirmados, descontando abonos registrados.</p><span>Revisar cobros <Icon nombre="flecha" size={15}/></span></a>
      <a href="#faenas" className="dia-tarea"><span className="dia-tarea-icon"><Icon nombre="faenas"/></span><strong>{sinRegistro ? `${sinRegistro} faenas sin cosecha registrada hoy` : "Faenas del día"}</strong><p>{sinRegistro ? "Confirma si trabajaron hoy. No implica un atraso ni una obligación de cosechar." : `${datos.faenas.length} faenas activas dentro de sus fechas. Revisa su avance.`}</p><span>Revisar faenas <Icon nombre="flecha" size={15}/></span></a>
      <a href="#seguimiento-pagos" className="dia-tarea"><span className="dia-tarea-icon"><Icon nombre="seguimiento-pagos"/></span><strong>{pesos(datos.saldo_trabajadores)} pendientes a trabajadores</strong><p>{datos.pagos_con_saldo} pagos cerrados con saldo · {datos.pagos_por_aprobar} por aprobar. Excluye producción sin cierre.</p><span>Revisar pagos <Icon nombre="flecha" size={15}/></span></a>
      <a href={datos.primeras_semanas[0] ? `#pagos?fecha=${datos.primeras_semanas[0]}` : "#pagos"} className="dia-tarea"><span className="dia-tarea-icon"><Icon nombre="pagos"/></span><strong>{datos.semanas_por_cerrar ? `${datos.semanas_por_cerrar} ${datos.semanas_por_cerrar === 1 ? "semana anterior sin cierre" : "semanas anteriores sin cierre"}` : "Semanas anteriores al día"}</strong><p>{datos.semanas_por_cerrar ? `Semanas desde ${datos.primeras_semanas.map(fecha).join(", ")}${datos.semanas_por_cerrar > 5 ? "…" : ""}. Revisa antes de cerrar.` : "No hay semanas anteriores con producción pendientes de cierre."} La semana actual no se cuenta como pendiente.</p><span>Revisar cierres <Icon nombre="flecha" size={15}/></span></a>
    </div>
    <div className="dia-columnas"><article className="panel"><div className="panel-heading"><div><h2>Faenas vigentes hoy</h2><p>Clientes activos y fechas que incluyen el día de hoy.</p></div><a href="#faenas">Ver todas →</a></div><div className="dia-faenas">{datos.faenas.length ? datos.faenas.map(f => <a href="#faenas" className="dia-faena" key={f.id}><span className={`dia-estado ${f.registros_hoy ? "registrada" : ""}`}/><div><strong>{f.cliente}</strong><span>{f.nombre} · {f.predio}</span><small>{f.fecha_fin ? `Fin previsto: ${fecha(f.fecha_fin)}` : "Sin fecha de término"}</small></div><span className="dia-etiqueta">{f.registros_hoy ? `${f.registros_hoy} registros hoy` : "Sin registro hoy"}</span></a>) : <p className="dia-vacio">No hay faenas vigentes para hoy. Puedes revisar las planificadas o registrar una nueva.</p>}</div></article>
      <article className="panel"><div className="panel-heading"><div><h2>Los próximos 7 días</h2><p>Inicios de faenas según tu planificación.</p></div></div><div className="dia-agenda">{datos.proximas.length ? datos.proximas.map((f, i) => <a href="#faenas" key={i}><time>{fecha(f.fecha_inicio)}</time><div><strong>{f.cliente}</strong><span>{f.nombre}</span><small>{f.estado}</small></div></a>) : <p className="dia-vacio">No hay inicios de faena en los próximos 7 días. Consulta tus acuerdos antes de planificar el equipo.</p>}</div><a className="panel-link" href="#simulador">Evaluar una nueva oferta <Icon nombre="flecha" size={15}/></a></article></div>
    <div className="dia-atajos"><a href="#semana"><Icon nombre="semana"/><div><strong>Preparar y resumir la semana</strong><span>Revisa cosechas, pagos y descarga el resumen PDF</span></div><Icon nombre="flecha" size={17}/></a><a href="#asistente"><Icon nombre="asistente"/><div><strong>Consultar al asistente</strong><span>Pregunta sobre tu producción, clientes y pagos</span></div><Icon nombre="flecha" size={17}/></a></div>
    <p className="dashboard-footnote">Fecha local de Chile. Los kilos de hoy corresponden a registros originales; los ajustes de semanas cerradas se revisan en su historial y en pagos. Los abonos de clientes y trabajadores son registros manuales; no confirman movimientos bancarios.</p>
  </section>;
}
