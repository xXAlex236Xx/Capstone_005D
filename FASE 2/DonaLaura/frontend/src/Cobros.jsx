import { useEffect, useRef, useState } from "react";
import { enviarJSON, solicitar } from "./api";
import Icon from "./Icon";
import "./Cobros.css";

const pesos = n => new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(Number(n || 0));
const numero = n => new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 }).format(Number(n));
const hoy = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const fecha = f => new Intl.DateTimeFormat("es-CL", { timeZone: "UTC", day: "numeric", month: "short", year: "numeric" }).format(new Date(`${f}T12:00:00Z`));
const en15dias = () => { const d = new Date(`${hoy()}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + 15); return d.toISOString().slice(0, 10); };
const estado = (c, dia) => c.estado === "Anulado" ? "Anulado" : Number(c.saldo) === 0 ? "Pagado" : c.vencimiento < dia ? "Vencido" : c.vencimiento === dia ? "Vence hoy" : Number(c.abonado) > 0 ? "Pago parcial" : "Pendiente";
const datosNuevos = () => ({ clave: crypto.randomUUID(), id_faena: "", monto: "", fecha_acuerdo: hoy(), vencimiento: en15dias(), concepto: "Servicio de cosecha según acuerdo con el cliente" });

export default function Cobros({ usuario }) {
  const [datos, setDatos] = useState(null), [faenas, setFaenas] = useState([]);
  const [form, setForm] = useState(null), [revisado, setRevisado] = useState(false);
  const [filtro, setFiltro] = useState("Pendientes"), [busqueda, setBusqueda] = useState("");
  const [seleccion, setSeleccion] = useState(null), [abonos, setAbonos] = useState(null);
  const [abono, setAbono] = useState(null), [motivo, setMotivo] = useState(null);
  const [error, setError] = useState(""), [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const solicitud = useRef(0);
  const carga = useRef(0);
  const panelDetalle = useRef(null);
  const admin = usuario.rol === "administrador";
  useEffect(() => { if (seleccion !== null) panelDetalle.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [seleccion]);
  useEffect(() => {
    let vivo = true;
    const cola = solicitud;
    Promise.all([solicitar("/cobros"), solicitar("/faenas")]).then(([d, f]) => { if (vivo) { setDatos(d); setFaenas(f); } }).catch(e => vivo && setError(e.message));
    return () => { vivo = false; cola.current++; };
  }, []);
  async function cargar() { const turno = ++carga.current; const [d, f] = await Promise.all([solicitar("/cobros"), solicitar("/faenas")]); if (turno === carga.current) { setDatos(d); setFaenas(f); } }
  function campo(k, v) { setRevisado(false); setForm(s => ({ ...s, [k]: v, clave: crypto.randomUUID() })); }
  async function guardar(e) {
    e.preventDefault(); if (!revisado) return;
    setOcupado(true); setError(""); setAviso("");
    try { const r = await solicitar("/cobros", enviarJSON("POST", { ...form, id_faena: Number(form.id_faena) })); setForm(null); await cargar(); setAviso(r.mensaje); }
    catch (e) { setError(e.message); } finally { setOcupado(false); }
  }
  async function abrir(c) {
    const turno = ++solicitud.current;
    setForm(null); setSeleccion(c.id); setAbonos(null); setAbono(null); setMotivo(null); setError(""); setAviso("");
    try { const a = await solicitar(`/cobros/${c.id}/abonos`); if (turno === solicitud.current) setAbonos(a); }
    catch (e) { if (turno === solicitud.current) setError(e.message); }
  }
  async function guardarAbono(e) {
    e.preventDefault(); setOcupado(true); setError(""); setAviso("");
    try { const r = await solicitar(`/cobros/${seleccion}/abonos`, enviarJSON("POST", abono)); setAbono(null); await cargar(); setAbonos(await solicitar(`/cobros/${seleccion}/abonos`)); setAviso(r.mensaje); }
    catch (e) { setError(e.message); } finally { setOcupado(false); }
  }
  async function anular(e) {
    e.preventDefault(); setOcupado(true); setError(""); setAviso("");
    try { const r = await solicitar(`/cobros/${seleccion}/anular`, enviarJSON("POST", { motivo })); setMotivo(null); await cargar(); setAviso(r.mensaje); }
    catch (e) { setError(e.message); } finally { setOcupado(false); }
  }
  if (!datos) return <p className={error ? "error" : "cargando"} role={error ? "alert" : undefined}>{error || "Preparando tu cartera de clientes…"}</p>;
  const detalle = datos.cobros.find(c => c.id === seleccion);
  const disponibles = faenas.filter(f => Number(f.registros) > 0 && !datos.cobros.some(c => c.id_faena === f.id && c.estado === "Vigente"));
  const referencia = faenas.find(f => f.id === Number(form?.id_faena));
  const texto = busqueda.trim().toLocaleLowerCase("es-CL");
  const filas = datos.cobros.filter(c => {
    const e = estado(c, datos.fecha);
    const coincide = filtro === "Todos" || (filtro === "Pendientes" ? c.estado === "Vigente" && Number(c.saldo) > 0 : filtro === "Vencidos" ? e === "Vencido" : filtro === "Vencen hoy" ? e === "Vence hoy" : filtro === "Pagados" ? e === "Pagado" : e === "Anulado");
    return coincide && `${c.cliente} ${c.faena} ${c.concepto}`.toLocaleLowerCase("es-CL").includes(texto);
  });
  const mensaje = detalle && `${detalle.cliente.includes("[DEMO]") ? "[DEMOSTRACIÓN · DATOS FICTICIOS]\n" : ""}Hola, ${detalle.cliente}. Les escribo por el servicio de cosecha «${detalle.faena}». El monto acordado es ${pesos(detalle.monto)}; tenemos registrados abonos por ${pesos(detalle.abonado)} y queda un saldo de ${pesos(detalle.saldo)}. El vencimiento es el ${fecha(detalle.vencimiento)}. ¿Nos confirman la fecha de pago? Si ya pagaron, por favor envíennos el comprobante para revisarlo. Gracias, Doña Laura SpA.`;
  async function copiar() { try { await navigator.clipboard.writeText(mensaje); setAviso("Mensaje copiado. Revísalo antes de enviarlo; la aplicación no envió ningún WhatsApp."); } catch { setAviso("Selecciona y copia el texto del mensaje. No se envió ningún WhatsApp."); } }
  return <section className="cobros-vista">
    <div className="page-heading"><div><span className="eyebrow">CUENTAS POR COBRAR</span><h1>Clientes que me deben</h1><p>Del acuerdo de cobro al abono recibido. Cada saldo, con su respaldo.</p></div><div className="cobros-botones"><button className="boton-secundario" disabled={ocupado} onClick={() => cargar().catch(e => setError(e.message))}><Icon nombre="actualizar" size={16}/> Actualizar</button>{admin && <button disabled={ocupado} onClick={() => { solicitud.current++; setSeleccion(null); setAbono(null); setMotivo(null); setForm(datosNuevos()); setRevisado(false); setError(""); setAviso(""); }}>+ Confirmar cobro</button>}</div></div>
    <div className="cobros-kpis">{[["Pendiente de recibir", datos.totales.saldo, `${datos.totales.pendientes} cobros con saldo`], ["Saldo vencido", datos.totales.saldo_vencido, `${datos.totales.vencidos} cobros fuera de plazo`], ["Recibido registrado", datos.totales.recibido, "Abonos anotados · no verificación bancaria"], ["Total confirmado", datos.totales.confirmado, "Acuerdos vigentes · incluye los pagados"]].map(([t,v,n]) => <article key={t}><span>{t}</span><strong>{pesos(v)}</strong><small>{n}</small></article>)}</div>
    <p className="cobros-aclaracion">El estimado por kilos es una referencia. El monto confirmado es el acuerdo revisado por ti y no cambia automáticamente si se corrige la cosecha. Una cuenta vigente por faena. No se emiten facturas ni se realizan transferencias.</p>
    {error && <p className="error" role="alert">{error}</p>}{aviso && <p className="mensaje" role="status">{aviso}</p>}
    {form && <form className="panel cobro-form" onSubmit={guardar}><fieldset className="campos-sin-borde" disabled={ocupado}><div className="panel-heading sin-padding"><div><h2>Confirmar un acuerdo de cobro</h2><p>Elige una faena con producción, revisa su estimado y confirma el monto acordado.</p></div><button type="button" className="boton-secundario" onClick={() => setForm(null)}>Cancelar</button></div>
      {!disponibles.length ? <p>No hay faenas con producción sin un cobro vigente. Revisa <a href="#faenas">Clientes y faenas</a>.</p> : <><div className="campos"><label className="campo">Faena a cobrar<select required value={form.id_faena} onChange={e => { const f = disponibles.find(f => f.id === Number(e.target.value)); setForm(s => ({ ...s, id_faena: e.target.value, monto: f ? String(f.cobro_estimado) : "", clave: crypto.randomUUID() })); setRevisado(false); }}><option value="">Seleccionar faena…</option>{disponibles.map(f => <option key={f.id} value={f.id}>{f.cliente} · {f.nombre}</option>)}</select></label><label className="campo">Monto confirmado (CLP)<input type="number" min="1" max="99999999999999" step="1" required value={form.monto} onChange={e => campo("monto", e.target.value)}/></label><label className="campo">Fecha del acuerdo<input type="date" required max={hoy()} value={form.fecha_acuerdo} onInput={e => campo("fecha_acuerdo", e.target.value)}/></label><label className="campo">Vencimiento<input type="date" required min={form.fecha_acuerdo} value={form.vencimiento} onInput={e => campo("vencimiento", e.target.value)}/></label></div>
      {referencia && <div className="cobro-referencia"><strong>Estimado de referencia: {pesos(referencia.cobro_estimado)}</strong>{referencia.estado !== "Finalizada" && <span>Esta faena todavía no está finalizada. Confirma solo el acuerdo revisado: más producción no aumentará automáticamente esta cuenta.</span>}<span>{numero(referencia.kilos)} kg × ${numero(referencia.precio_kg)} por kilo · incluye ajustes registrados.</span>{Number(form.monto) !== Number(referencia.cobro_estimado) && <span>El monto acordado difiere del estimado. Explica el acuerdo en el concepto.</span>}</div>}
      <label className="campo">Concepto y detalle del acuerdo<input required minLength={5} maxLength={500} value={form.concepto} onChange={e => campo("concepto", e.target.value)}/></label><label className="cobro-confirmacion"><input type="checkbox" required checked={revisado} onChange={e => setRevisado(e.target.checked)}/> Revisé el monto y vencimiento del acuerdo con este cliente.</label><button disabled={!revisado}>{ocupado ? "Confirmando…" : "Confirmar cuenta por cobrar"}</button></>}
    </fieldset></form>}
    <div className="panel"><div className="tabla-toolbar cobros-toolbar"><input aria-label="Buscar cliente o faena" type="search" placeholder="Buscar cliente o faena…" value={busqueda} onChange={e => setBusqueda(e.target.value)}/><label className="campo">Mostrar<select value={filtro} onChange={e => setFiltro(e.target.value)}>{["Pendientes", "Vencidos", "Vencen hoy", "Pagados", "Anulados", "Todos"].map(f => <option key={f}>{f}</option>)}</select></label><span>{filas.length} cobros · {datos.totales.vencen_hoy} vencen hoy</span></div><div className="tabla-contenedor"><table><thead><tr><th>Cliente / faena</th><th>Vencimiento</th><th>Confirmado</th><th>Recibido</th><th>Saldo</th><th>Estado</th><th></th></tr></thead><tbody>{filas.map(c => <tr key={c.id}><td><strong>{c.cliente}</strong><small className="block-muted">{c.faena}</small></td><td>{fecha(c.vencimiento)}</td><td>{pesos(c.monto)}</td><td>{pesos(c.abonado)}</td><td><strong>{pesos(c.saldo)}</strong></td><td><span className={`cobro-estado ${estado(c, datos.fecha) === "Vencido" ? "vencido" : ""}`}>{estado(c, datos.fecha)}</span></td><td><button className="boton-secundario" disabled={ocupado} onClick={() => abrir(c)}>Ver cobro</button></td></tr>)}</tbody></table>{!filas.length && <p className="empty-table">No hay cobros que coincidan con esta vista.</p>}</div></div>
    {detalle && <div ref={panelDetalle} className="panel cobro-detalle"><div className="panel-heading sin-padding"><div><span className="eyebrow">COBRO #{detalle.id}</span><h2>{detalle.cliente}</h2><p>{detalle.faena} · {detalle.concepto}</p></div><button className="boton-secundario" disabled={ocupado} onClick={() => { solicitud.current++; setSeleccion(null); }}>Cerrar detalle</button></div><div className="cobro-detalle-resumen"><span>Acordado <strong>{pesos(detalle.monto)}</strong></span><span>Recibido <strong>{pesos(detalle.abonado)}</strong></span><span>Saldo <strong>{pesos(detalle.saldo)}</strong></span><span>Vence <strong>{fecha(detalle.vencimiento)}</strong></span></div><p className="cobros-aclaracion">Referencia al confirmar: {numero(detalle.kilos_referencia)} kg × ${numero(detalle.precio_referencia)} = {pesos(detalle.estimado_referencia)} estimados. Acuerdo del {fecha(detalle.fecha_acuerdo)}.</p>
      {detalle.estado === "Anulado" ? <p className="aviso-perfil">Cobro anulado: {detalle.motivo_anulacion}. Su historial se conserva.</p> : <><div className="cobros-botones">{admin && Number(detalle.saldo) > 0 && <button disabled={ocupado} onClick={() => { setAbono({ clave: crypto.randomUUID(), monto: "", fecha: hoy(), referencia: "" }); setMotivo(null); }}>Registrar abono recibido</button>}{admin && Number(detalle.abonado) === 0 && <button disabled={ocupado} className="boton-secundario" onClick={() => { setMotivo(""); setAbono(null); }}>Anular cobro sin abonos</button>}</div>
      {abono && <form className="cobro-abono" onSubmit={guardarAbono}><fieldset className="campos-sin-borde" disabled={ocupado}><h3>Registrar dinero ya recibido</h3><div className="campos">{[["monto","Monto recibido (CLP)","number"],["fecha","Fecha de recepción","date"],["referencia","Referencia o comprobante","text"]].map(([k,l,t]) => <label className="campo" key={k}>{l}<input required type={t} min={k === "monto" ? 1 : k === "fecha" ? detalle.fecha_acuerdo : undefined} max={k === "monto" ? Number(detalle.saldo) : k === "fecha" ? hoy() : undefined} step={k === "monto" ? 1 : undefined} minLength={k === "referencia" ? 3 : undefined} maxLength={k === "referencia" ? 180 : undefined} value={abono[k]} onInput={e => setAbono(a => ({ ...a, [k]: e.target.value, clave: crypto.randomUUID() }))}/></label>)}</div><p>Registra únicamente dinero recibido y conserva su comprobante. Esto no solicita ni ejecuta un pago.</p><button>{ocupado ? "Registrando…" : "Guardar abono recibido"}</button><button type="button" className="boton-secundario" onClick={() => setAbono(null)}>Cancelar abono</button></fieldset></form>}
      {motivo !== null && <form className="cobro-abono" onSubmit={anular}><fieldset className="campos-sin-borde" disabled={ocupado}><label className="campo">Motivo de anulación<input required minLength={5} maxLength={500} value={motivo} onChange={e => setMotivo(e.target.value)}/></label><p>Se conservará el cobro anulado y podrás confirmar un nuevo acuerdo para la faena.</p><button>Confirmar anulación</button><button type="button" className="boton-secundario" onClick={() => setMotivo(null)}>Cancelar anulación</button></fieldset></form>}
      {Number(detalle.saldo) > 0 && <div className="cobro-mensaje"><h3>Mensaje para copiar a WhatsApp</h3><textarea aria-label="Mensaje de cobro para copiar" readOnly value={mensaje} rows={5}/><button className="boton-secundario" disabled={ocupado} onClick={copiar}>Copiar mensaje</button><small>Revísalo antes de enviarlo. No se envía automáticamente.</small></div>}</>}
      <h3>Historial de abonos</h3>{abonos === null ? <p>Cargando comprobantes…</p> : abonos.length ? <div className="tabla-contenedor"><table><thead><tr><th>Fecha</th><th>Monto</th><th>Referencia</th><th>Registrado por</th></tr></thead><tbody>{abonos.map(a => <tr key={a.id}><td>{fecha(a.fecha)}</td><td>{pesos(a.monto)}</td><td>{a.referencia}</td><td>{a.usuario}</td></tr>)}</tbody></table></div> : <p className="muted">Todavía no hay abonos registrados para este cobro.</p>}
    </div>}
  </section>;
}
