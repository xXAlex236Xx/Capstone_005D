import { useEffect, useRef, useState } from "react";
import { enviarJSON, solicitar } from "./api";
import "./Cosechas.css";
import RepetirJornada from "./RepetirJornada";

const nuevaFila = () => ({ key: crypto.randomUUID(), id_trabajador: "", cantidad_kg: "", horas_trabajadas: "" });
const numero = n => new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 }).format(Number(n || 0));
const hoy = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const consultaJornada = () => new URLSearchParams(window.location.hash.split("?")[1] || "");

export default function Cosechas({ usuario }) {
  const [opciones, setOpciones] = useState({ trabajadores: [], jornadas: [], sectores: [], labores: [], faenas: [] });
  const [cabecera, setCabecera] = useState({ fecha: hoy(), id_sector: "", id_labor: "", id_faena: "" });
  const [filas, setFilas] = useState([nuevaFila()]);
  const [vista, setVista] = useState(() => usuario.rol === "consulta" || consultaJornada().get("vista") === "historial" ? "historial" : "registro");
  const [registros, setRegistros] = useState([]);
  const [fecha, setFecha] = useState(() => /^\d{4}-\d{2}-\d{2}$/.test(consultaJornada().get("fecha") || "") ? consultaJornada().get("fecha") : "");
  const [seleccion, setSeleccion] = useState(null);
  const [historia, setHistoria] = useState(null);
  const [edicion, setEdicion] = useState({ kilos: "", horas: "", motivo: "" });
  const [ocupado, setOcupado] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [exigeFaena, setExigeFaena] = useState(false);
  const claveLote = useRef(crypto.randomUUID());
  const claveAjuste = useRef(crypto.randomUUID());
  const solicitudHistorial = useRef(0);
  const puede = usuario.rol !== "consulta";
  useEffect(() => {
    const navegar = () => {
      if (window.location.hash.split("?")[0] !== "#cosechas") return;
      const p = consultaJornada();
      if (p.get("vista") === "historial") { setVista("historial"); if (/^\d{4}-\d{2}-\d{2}$/.test(p.get("fecha") || "")) setFecha(p.get("fecha")); }
      if (p.get("vista") === "registro" && puede) setVista("registro");
    };
    window.addEventListener("hashchange", navegar);
    return () => window.removeEventListener("hashchange", navegar);
  }, [puede]);
  useEffect(() => {
    let vivo = true;
    Promise.all(["/trabajadores", "/sectores", "/labores", "/faenas"].map(r => solicitar(r)))
      .then(([trabajadores,sectores,labores,faenas]) => vivo && setOpciones({trabajadores:trabajadores.filter(t=>t.estado==="Activo"),sectores,labores,faenas}))
      .catch(e=>vivo&&setError(e.message)).finally(()=>vivo&&setCargando(false));
    return ()=>{vivo=false;};
  }, []);
  async function cargarRegistros() { setRegistros(await solicitar(`/produccion/registros${fecha?`?fecha=${fecha}`:""}`)); }
  useEffect(() => {
    let vivo = true;
    solicitar(`/produccion/registros${fecha?`?fecha=${fecha}`:""}`).then(r=>vivo&&setRegistros(r)).catch(e=>vivo&&setError(e.message));
    return ()=>{vivo=false;};
  }, [fecha]);
  function cambiarFila(key,campo,valor) { claveLote.current=crypto.randomUUID(); setFilas(v=>v.map(f=>f.key===key?{...f,[campo]:valor}:f)); }
  function repetir(grupo, origen) {
    claveLote.current=crypto.randomUUID();
    setCabecera(v => ({ ...v, id_sector:String(grupo.id_sector), id_labor:String(grupo.id_labor), id_faena:grupo.faena_valida && grupo.id_faena ? String(grupo.id_faena) : "" }));
    setFilas(grupo.trabajadores.map(t => ({ ...nuevaFila(), id_trabajador:String(t.id) })));
    setExigeFaena(Boolean(grupo.id_faena && !grupo.faena_valida));
    setError("");
    setAviso(`Equipo del ${origen} cargado como borrador. Revisa asistencia y completa los kilos y horas de ${cabecera.fecha}.${grupo.faena_valida ? "" : " Elige una faena vigente antes de guardar."}`);
  }
  async function guardar(e) {
    e.preventDefault(); setOcupado(true); setError(""); setAviso("");
    try {
      if (exigeFaena && !cabecera.id_faena) throw new Error("La faena anterior no está vigente. Elige una faena válida antes de guardar.");
      const r = await solicitar("/produccion/jornada",enviarJSON("POST",{fecha:cabecera.fecha,id_sector:Number(cabecera.id_sector),id_labor:Number(cabecera.id_labor),id_faena:cabecera.id_faena?Number(cabecera.id_faena):null,clave:claveLote.current,filas:filas.map(({id_trabajador,cantidad_kg,horas_trabajadas})=>({id_trabajador:Number(id_trabajador),cantidad_kg,horas_trabajadas}))}));
      setAviso(`${r.mensaje}: ${r.registros} trabajadores.`); setFilas([nuevaFila()]); setExigeFaena(false); claveLote.current=crypto.randomUUID(); await cargarRegistros();
    } catch(err) { setError(err.message); } finally { setOcupado(false); }
  }
  async function abrir(r,modo) {
    const solicitud=++solicitudHistorial.current;
    setError(""); setSeleccion({registro:r,modo}); setHistoria(null); claveAjuste.current=crypto.randomUUID();
    setEdicion({kilos:modo==="ajuste"?"":String(r.cantidad_kg),horas:modo==="ajuste"?"0":String(r.horas_trabajadas||""),motivo:""});
    try { const h=await solicitar(`/produccion/${r.id}/historial`); if(solicitud===solicitudHistorial.current) setHistoria(h); } catch(e) { if(solicitud===solicitudHistorial.current) setError(e.message); }
  }
  async function guardarCambio(e) {
    e.preventDefault(); if(!seleccion) return; setOcupado(true); setError(""); setAviso("");
    const ajuste=seleccion.modo==="ajuste";
    try {
      const datos=ajuste?{clave:claveAjuste.current,diferencia_kg:edicion.kilos,diferencia_horas:edicion.horas,motivo:edicion.motivo}:{cantidad_kg:edicion.kilos,horas_trabajadas:edicion.horas,motivo:edicion.motivo,version:seleccion.registro.version};
      const r=await solicitar(`/produccion/${seleccion.registro.id}${ajuste?"/ajustes":""}`,enviarJSON(ajuste?"POST":"PATCH",datos));
      setAviso(r.mensaje); setSeleccion(null); await cargarRegistros();
    } catch(err) { setError(err.message); } finally { setOcupado(false); }
  }
  const kg=filas.reduce((a,f)=>a+Number(f.cantidad_kg||0),0);
  const horas=filas.reduce((a,f)=>a+Number(f.horas_trabajadas||0),0);
  return <section><div className="page-heading"><div><span className="eyebrow">OPERACIÓN DIARIA</span><h1>Cosechas por jornada</h1><p>Una fecha, un sector y una labor para todo el equipo. Cada cambio conserva su historial.</p></div></div>
    <div className="operation-tabs">{puede&&<button className={vista==="registro"?"selected":""} onClick={()=>setVista("registro")}>Registrar jornada</button>}<button className={vista==="historial"?"selected":""} onClick={()=>setVista("historial")}>Registros e historial</button></div>
    {error&&<p className="error" role="alert">{error}</p>}{aviso&&<p className="mensaje" role="status">{aviso}</p>}
    {!cargando && vista === "registro" && puede && <RepetirJornada key={cabecera.fecha} fecha={cabecera.fecha} disabled={ocupado} hayBorrador={Boolean(cabecera.id_sector || cabecera.id_labor || cabecera.id_faena || filas.some(f => f.id_trabajador || f.cantidad_kg || f.horas_trabajadas))} onCargar={repetir}/>}
    {cargando?<p>Cargando opciones…</p>:vista==="registro"&&puede?<form className="panel jornada-panel" onSubmit={guardar}><fieldset disabled={ocupado} className="campos-sin-borde"><div className="campos">
      <label className="campo">Fecha de la jornada<input type="date" required value={cabecera.fecha} onInput={e=>{claveLote.current=crypto.randomUUID();setCabecera({...cabecera,fecha:e.target.value});}}/><small>La jornada se crea al guardar si todavía no existe.</small></label>
      <label className="campo">Faena del cliente {exigeFaena ? "(obligatoria al repetir este equipo)" : "(opcional)"}<select required={exigeFaena} value={cabecera.id_faena} onChange={e=>{claveLote.current=crypto.randomUUID();setCabecera({...cabecera,id_faena:e.target.value});}}><option value="">Sin faena vinculada</option>{opciones.faenas.filter(f=>f.estado==="Activa"&&f.cliente_activo).map(f=><option key={f.id} value={f.id}>{f.nombre} · {f.cliente} · {f.predio}</option>)}</select><small>Vincula los kilos al cobro del servicio. Solo aparecen faenas activas. <a href="#faenas">Administrar faenas</a></small></label>
      {[["id_sector","Sector",opciones.sectores],["id_labor","Labor",opciones.labores]].map(([id,label,lista])=><label className="campo" key={id}>{label}<select required value={cabecera[id]} onChange={e=>{claveLote.current=crypto.randomUUID();setCabecera({...cabecera,[id]:e.target.value});}}><option value="">Seleccionar…</option>{lista.map(o=><option value={o.id} key={o.id}>{o.nombre}</option>)}</select></label>)}</div>
      <div className="panel-heading sin-padding"><div><h2>Producción del equipo</h2><p>Completa kilos y horas. Los trabajadores no pueden repetirse en el lote.</p></div><button type="button" className="boton-secundario" onClick={()=>{claveLote.current=crypto.randomUUID();setFilas(actual=>[...actual.filter(f=>f.id_trabajador),...opciones.trabajadores.filter(t=>!actual.some(f=>Number(f.id_trabajador)===t.id)).map(t=>({...nuevaFila(),id_trabajador:String(t.id)}))]);}}>Agregar todo el equipo</button></div>
      <div className="tabla-contenedor"><table className="tabla-jornada"><thead><tr><th>Trabajador</th><th>Kilos</th><th>Horas</th><th>kg/h</th><th></th></tr></thead><tbody>{filas.map((f,i)=><tr key={f.key}><td><select aria-label={`Trabajador fila ${i+1}`} required value={f.id_trabajador} onChange={e=>cambiarFila(f.key,"id_trabajador",e.target.value)}><option value="">Seleccionar trabajador</option>{opciones.trabajadores.map(t=><option value={t.id} key={t.id}>{t.nombre} {t.apellido}</option>)}</select></td><td><input aria-label={`Kilos fila ${i+1}`} type="number" min="0" max="99999999.99" step="0.01" required value={f.cantidad_kg} onChange={e=>cambiarFila(f.key,"cantidad_kg",e.target.value)}/></td><td><input aria-label={`Horas fila ${i+1}`} type="number" min="0.01" max="24" step="0.01" required value={f.horas_trabajadas} onChange={e=>cambiarFila(f.key,"horas_trabajadas",e.target.value)}/></td><td>{Number(f.horas_trabajadas)>0?numero(Number(f.cantidad_kg)/Number(f.horas_trabajadas)):"—"}</td><td><button type="button" className="boton-secundario" aria-label={`Quitar fila ${i+1}`} disabled={filas.length===1} onClick={()=>{claveLote.current=crypto.randomUUID();setFilas(v=>v.filter(r=>r.key!==f.key));}}>×</button></td></tr>)}</tbody></table></div>
      <div className="jornada-acciones"><button type="button" className="boton-secundario" onClick={()=>{claveLote.current=crypto.randomUUID();setFilas(v=>[...v,nuevaFila()]);}}>+ Agregar fila</button><span>{filas.length} filas · {numero(kg)} kg · {numero(horas)} h</span><button disabled={ocupado||!opciones.trabajadores.length}>{ocupado?"Guardando…":"Guardar jornada completa"}</button></div></fieldset><p className="dashboard-footnote">Si alguna fila no es válida, no se guarda ninguna. Las semanas cerradas no admiten nuevas cosechas.</p></form>:<>
      <div className="panel"><div className="tabla-toolbar"><label className="campo">Filtrar por fecha<input type="date" value={fecha} onChange={e=>setFecha(e.target.value)}/></label><button className="boton-secundario" onClick={()=>cargarRegistros().catch(e=>setError(e.message))}>Actualizar</button><span>Hasta 200 registros recientes</span></div><div className="tabla-contenedor"><table><thead><tr><th>Fecha / trabajador</th><th>Sector / labor</th><th>Faena / cliente</th><th>Kilos</th><th>Horas</th><th>Semana</th><th>Acciones</th></tr></thead><tbody>{registros.map(r=><tr key={r.id}><td><strong>{r.trabajador}</strong><small className="block-muted">{r.fecha}</small></td><td>{r.sector}<small className="block-muted">{r.labor}</small></td><td>{r.faena||"Sin faena"}{r.cliente&&<small className="block-muted">{r.cliente}</small>}</td><td>{numero(r.cantidad_kg)}</td><td>{numero(r.horas_trabajadas)}</td><td><span className={r.cerrada?"pagos-cerrada":"pagos-abierta"}>{r.cerrada?"Cerrada":"Abierta"}</span></td><td><div className="acciones"><button className="boton-secundario" onClick={()=>abrir(r,"historial")}>Historial</button>{puede&&!r.cerrada&&<button className="boton-editar" onClick={()=>abrir(r,"corregir")}>Corregir</button>}{usuario.rol==="administrador"&&r.cerrada&&<button className="boton-secundario" onClick={()=>abrir(r,"ajuste")}>Ajustar</button>}</div></td></tr>)}</tbody></table>{!registros.length&&<p className="empty-table">No hay registros para esta fecha.</p>}</div></div>
      {seleccion&&<div className="panel jornada-panel detalle-correccion"><div className="panel-heading sin-padding"><div><h2>{seleccion.modo==="historial"?"Historial del registro":seleccion.modo==="ajuste"?"Ajuste de semana cerrada":"Corregir registro"}</h2><p>{seleccion.registro.trabajador} · {seleccion.registro.fecha} · {seleccion.registro.sector}</p></div><button disabled={ocupado} className="boton-secundario" onClick={()=>setSeleccion(null)}>Cerrar</button></div>
        {seleccion.modo!=="historial"&&<form onSubmit={guardarCambio}><fieldset disabled={ocupado} className="campos-sin-borde">{seleccion.modo==="ajuste"&&<p className="aviso-perfil">El original y el cierre se conservan. Indica diferencias con signo: por ejemplo, −10 para descontar kilos. El pago requerirá una nueva aprobación. Los reportes de producción conservan el original; el ajuste se consulta aquí y en Seguimiento de pagos.</p>}<div className="campos"><label className="campo">{seleccion.modo==="ajuste"?"Diferencia de kilos":"Kilos corregidos"}<input type="number" step="0.01" min={seleccion.modo==="ajuste"?undefined:0} required value={edicion.kilos} onChange={e=>{claveAjuste.current=crypto.randomUUID();setEdicion({...edicion,kilos:e.target.value});}}/></label><label className="campo">{seleccion.modo==="ajuste"?"Diferencia de horas":"Horas corregidas"}<input type="number" step="0.01" min={seleccion.modo==="ajuste"?undefined:0.01} max={24} required value={edicion.horas} onChange={e=>{claveAjuste.current=crypto.randomUUID();setEdicion({...edicion,horas:e.target.value});}}/></label><label className="campo">Motivo del cambio<input minLength={5} maxLength={500} required value={edicion.motivo} onChange={e=>{claveAjuste.current=crypto.randomUUID();setEdicion({...edicion,motivo:e.target.value});}}/></label></div><button>{ocupado?"Guardando…":"Guardar con historial"}</button></fieldset></form>}
        <div className="timeline-cosecha">{!historia?<p className="muted">Cargando historial…</p>:<>{historia.correcciones.map(c=><article key={`c${c.id}`}><strong>Corrección · {c.usuario}</strong><small>{new Date(c.fecha).toLocaleString("es-CL")}</small><p>{c.antes.cantidad_kg} → {c.despues.cantidad_kg} kg · {c.antes.horas_trabajadas} → {c.despues.horas_trabajadas} h</p><p>{c.motivo}</p></article>)}{historia.ajustes.map(a=><article key={`a${a.id}`}><strong>Ajuste separado · {a.usuario}</strong><small>{new Date(a.fecha).toLocaleString("es-CL")}</small><p>{numero(a.kilos)} kg · {numero(a.horas)} h · ${numero(a.monto)}</p><p>{a.motivo}</p></article>)}{!historia.correcciones.length&&!historia.ajustes.length&&<p className="muted">Este registro no tiene correcciones ni ajustes.</p>}</>}</div>
      </div>}</>}
  </section>;
}
