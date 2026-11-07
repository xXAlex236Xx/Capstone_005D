import { useEffect, useState } from "react";
import { API, solicitar } from "./api";
import Icon from "./Icon";
import "./Semana.css";

const numero = n => new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 }).format(Number(n || 0));
const pesos = n => n == null ? "Por definir" : new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(Number(n));
const fechaTexto = f => new Intl.DateTimeFormat("es-CL", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${f}T12:00:00Z`));
function anterior() {
  const f = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const d = new Date(`${f}T12:00:00Z`); d.setUTCDate(d.getUTCDate() - ((d.getUTCDay()+6)%7) - 7); return d.toISOString().slice(0,10);
}
export default function Semana({ usuario }) {
  const [fecha, setFecha] = useState(() => { const f = new URLSearchParams(window.location.hash.split("?")[1] || "").get("fecha"); return /^\d{4}-\d{2}-\d{2}$/.test(f || "") ? f : anterior(); });
  const [respuesta, setRespuesta] = useState(null), [error, setError] = useState(null), [version, setVersion] = useState(0);
  useEffect(() => {
    if (!fecha) return;
    let vivo = true;
    solicitar(`/preparar-semana?fecha=${encodeURIComponent(fecha)}`).then(d => { if (vivo) { setRespuesta({ fecha, datos:d }); setError(null); } }).catch(e => vivo && setError({ fecha, mensaje:e.message }));
    return () => { vivo = false; };
  }, [fecha, version]);
  const datos = respuesta?.fecha === fecha ? respuesta.datos : null;
  const admin = usuario.rol === "administrador";
  const pagos = datos ? `#pagos?fecha=${datos.desde}` : "#pagos";
  const erroresProduccion = datos?.alertas.filter(a => ["datos","duplicados","horas","futuro"].includes(a.clave)) || [];
  return <section className="semana-vista">
    <div className="page-heading"><div><span className="eyebrow">TU RUTINA DE FIN DE SEMANA</span><h1>Preparar la semana</h1><p>Revisa lo registrado, resuelve pendientes y llévate un resumen para compartir.</p></div><button className="boton-secundario" onClick={() => setVersion(v => v + 1)}><Icon nombre="actualizar" size={16}/> Actualizar revisión</button></div>
    <div className="panel semana-selector"><label className="campo">Semana que contiene el día<input type="date" value={fecha} onInput={e => setFecha(e.target.value)}/></label>{datos && <><div><strong>{fechaTexto(datos.desde)} — {fechaTexto(datos.hasta)}</strong><span>{datos.cerrada ? "Cierre de pagos confirmado" : datos.hasta >= datos.fecha_consulta ? "Semana en curso o futura" : "Cierre de pagos pendiente"}</span></div><a className="boton-enlace" href={`${API}/preparar-semana/pdf?fecha=${datos.desde}`}><Icon nombre="reportes" size={17}/> Descargar resumen PDF</a></>}</div>
    {!fecha && <p className="aviso-perfil">Elige un día para revisar su semana de lunes a domingo.</p>}
    {error?.fecha === fecha && <p className="error" role="alert">{error.mensaje}</p>}
    {fecha && !datos && error?.fecha !== fecha && <p>Cargando revisión semanal…</p>}
    {datos && <>
      <div className="semana-kpis">{[["Producción registrada",`${numero(datos.kilos)} kg`,`${datos.personas} personas · ${datos.dias_con_registros} días con registros`], [datos.cerrada ? "Pagos de esa semana" : "Pagos estimados, sin cierre",pesos(datos.cerrada ? datos.pago_confirmado : datos.pago_estimado),datos.cerrada ? "Cierre original más ajustes registrados" : "Sobre kilos originales y tarifa semanal"], ["Recibido de clientes en el período",pesos(datos.recibido_clientes_periodo),"Según fecha anotada del abono"], ["Abonado a trabajadores en el período",pesos(datos.abonado_trabajadores_periodo),"Puede corresponder a cierres de otras semanas"]].map(([t,v,n]) => <article key={t}><span>{t}</span><strong>{v}</strong><small>{n}</small></article>)}</div>
      <div className="semana-pasos">
        <article className="panel semana-paso"><span className="semana-numero">01</span><div><div className="semana-titulo"><h2>Revisa las cosechas</h2><span>{!datos.registros ? "Sin registros" : erroresProduccion.length ? "Revisar datos" : "Controles sin alertas"}</span></div><p>{datos.registros ? `${datos.registros} registros · ${numero(datos.kilos_originales)} kg originales y ${numero(datos.ajustes_kg)} kg de ajustes. Revisa fechas, asistencia y pesajes.` : "No hay cosechas registradas en esta semana. Confirma si hubo trabajo antes de registrar jornadas."}</p></div></article>
        <article className="panel semana-paso"><span className="semana-numero">02</span><div><div className="semana-titulo"><h2>Confirma la tarifa</h2><span>{datos.cerrada ? "Congelada en el cierre" : datos.precio_kg == null ? "Por definir" : "Tarifa registrada"}</span></div><p>{datos.precio_kg == null ? datos.cerrada ? "Los pagos conservan la tarifa del cierre." : "Sin tarifa no se puede estimar cuánto corresponde a cada trabajador." : `Tarifa semanal: $${numero(datos.precio_kg)} por kilo. Es distinta del precio que paga el cliente.`}</p><a href={pagos}>{admin ? "Revisar tarifa en Pagos" : "Ver tarifa y pagos"} <Icon nombre="flecha" size={15}/></a></div></article>
        <article className="panel semana-paso"><span className="semana-numero">03</span><div><div className="semana-titulo"><h2>Revisa y confirma los pagos</h2><span>{datos.cerrada ? "Cierre confirmado" : datos.listo_para_revisar_cierre ? "Disponible para revisar" : "Revisión pendiente"}</span></div><p>{datos.cerrada ? `Saldo actual de los cierres de esa semana: ${pesos(datos.saldo_cierres_semana)}. Cerrar no significa haber pagado; los abonos se registran por separado.` : "El cierre se realiza en Pagos después de revisar el detalle. Esta guía no cierra ni aprueba automáticamente."}</p><a href={datos.cerrada ? "#seguimiento-pagos" : pagos}>{datos.cerrada ? "Revisar saldos y comprobantes" : admin ? "Ir al detalle antes de cerrar" : "Consultar detalle de pagos"} <Icon nombre="flecha" size={15}/></a></div></article>
        <article className="panel semana-paso"><span className="semana-numero">04</span><div><div className="semana-titulo"><h2>Da seguimiento a los cobros</h2><span>{datos.cartera_actual.pendientes ? "Con saldos actuales" : "Sin saldos actuales"}</span></div><p>{datos.acuerdos_periodo} acuerdos vigentes con fecha de acuerdo en esta semana, por {pesos(datos.monto_acuerdos_periodo)}. Hoy quedan {pesos(datos.cartera_actual.saldo)} por recibir en toda la cartera.</p><a href="#cobros">Revisar clientes que deben <Icon nombre="flecha" size={15}/></a></div></article>
      </div>
      {datos.alertas.length > 0 && <div className="panel semana-alertas"><h2>Antes de continuar, revisa esto</h2>{datos.alertas.map(a => <div key={a.clave}><span className={a.bloquea ? "importante" : ""}>{a.cantidad === true ? 1 : a.cantidad}</span><p>{a.mensaje}</p></div>)}</div>}
      <div className="panel semana-jornadas"><div className="panel-heading"><div><h2>Las jornadas, una por una</h2><p>Una fecha sin registros no demuestra ausencia ni trabajo pendiente.</p></div></div><div className="tabla-contenedor"><table><thead><tr><th>Fecha</th><th>Registros</th><th>Personas</th><th>Kilos con ajustes</th><th>Revisión</th></tr></thead><tbody>{Array.from({ length:7 },(_,i) => { const d = new Date(`${datos.desde}T12:00:00Z`); d.setUTCDate(d.getUTCDate()+i); const f=d.toISOString().slice(0,10); const dia=datos.dias.find(d => d.fecha===f); return <tr key={f}><td>{fechaTexto(f)}</td><td>{dia?.registros || "—"}</td><td>{dia?.personas || "—"}</td><td>{dia ? `${numero(Number(dia.kilos_originales)+Number(dia.ajustes_kg))} kg` : "Sin registros"}</td><td><a href={`#cosechas?vista=historial&fecha=${f}`}>Ver jornada →</a></td></tr>; })}</tbody></table></div></div>
      <div className="semana-descarga"><div><span className="eyebrow">UN RESUMEN PARA TU CONTADOR O SOCIO</span><h2>Toda la semana, en una página.</h2><p>Producción, pagos, movimientos registrados y pendientes actuales. El PDF se genera con los datos vigentes al descargar.</p></div><a className="boton-enlace" href={`${API}/preparar-semana/pdf?fecha=${datos.desde}`}><Icon nombre="reportes" size={18}/> Descargar resumen PDF</a></div>
      <p className="dashboard-footnote">Los controles ayudan a revisar; no verifican bancos, asistencia real ni todos los errores posibles. Producción por fecha de jornada; dinero por fecha anotada de cada abono. Los saldos actuales no reconstruyen la deuda que existía al finalizar una semana pasada. No se calcula utilidad ni se emiten facturas.</p>
    </>}
  </section>;
}
