import { useEffect, useRef, useState } from "react";
import { enviarJSON, solicitar } from "./api";
import Icon from "./Icon";
import "./Faenas.css";

const numero = n => new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 }).format(Number(n || 0));
const pesos = n => n == null ? "Por completar" : new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(Number(n));
const hoy = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const fecha = valor => valor ? new Intl.DateTimeFormat("es-CL", { timeZone: "UTC" }).format(new Date(`${valor}T12:00:00Z`)) : "Sin fecha final";
const clienteVacio = () => ({ nombre: "", contacto: "", email: "", telefono: "", notas: "", activo: true });
const faenaVacia = () => ({ id_cliente: "", nombre: "", predio: "", cultivo: "", fecha_inicio: hoy(), fecha_fin: "", precio_kg: "", estado: "Planificada", notas: "" });
const camposCliente = ["nombre", "contacto", "email", "telefono", "notas", "activo"];
const camposFaena = ["id_cliente", "nombre", "predio", "cultivo", "fecha_inicio", "fecha_fin", "precio_kg", "estado", "notas"];

export default function Faenas({ usuario }) {
  const [datos, setDatos] = useState({ clientes: [], faenas: [] });
  const [vista, setVista] = useState("faenas");
  const [busqueda, setBusqueda] = useState("");
  const [estado, setEstado] = useState("");
  const [cargando, setCargando] = useState(true);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [formulario, setFormulario] = useState(null);
  const [detalleId, setDetalleId] = useState(null);
  const [registros, setRegistros] = useState(null);
  const solicitud = useRef(0);
  const admin = usuario.rol === "administrador";
  const detalle = datos.faenas.find(f => f.id === detalleId);

  useEffect(() => {
    let vigente = true;
    const cola = solicitud;
    Promise.all([solicitar("/clientes"), solicitar("/faenas")])
      .then(([clientes, faenas]) => vigente && setDatos({ clientes, faenas }))
      .catch(e => vigente && setError(e.message)).finally(() => vigente && setCargando(false));
    return () => { vigente = false; cola.current++; };
  }, []);
  async function cargar() {
    const [clientes, faenas] = await Promise.all([solicitar("/clientes"), solicitar("/faenas")]);
    setDatos({ clientes, faenas });
  }
  function abrir(tipo, registro) {
    setError(""); setAviso("");
    const campos = tipo === "clientes" ? camposCliente : camposFaena;
    const valores = registro ? Object.fromEntries(campos.map(c => [c, registro[c] ?? ""])) : tipo === "clientes" ? clienteVacio() : faenaVacia();
    setFormulario({ tipo, id: registro?.id, version: registro?.version, conProduccion: Boolean(registro?.registros), valores });
  }
  function campo(nombre, valor) { setFormulario(f => ({ ...f, valores: { ...f.valores, [nombre]: valor } })); }
  async function guardar(evento) {
    evento.preventDefault(); setOcupado(true); setError(""); setAviso("");
    try {
      const { tipo, id, valores, version } = formulario;
      const cuerpo = { ...valores, ...(id ? { version } : {}) };
      if (tipo === "faenas") { cuerpo.id_cliente = Number(cuerpo.id_cliente); cuerpo.fecha_fin ||= null; }
      const r = await solicitar(`/${tipo}${id ? `/${id}` : ""}`, enviarJSON(id ? "PATCH" : "POST", cuerpo));
      setFormulario(null); setAviso(r.mensaje);
      await cargar();
      if (detalleId) { solicitud.current++; setDetalleId(null); setRegistros(null); }
    } catch (e) { setError(e.message); } finally { setOcupado(false); }
  }
  async function abrirDetalle(faena) {
    const turno = ++solicitud.current;
    setDetalleId(faena.id); setRegistros(null); setError("");
    try { const filas = await solicitar(`/faenas/${faena.id}/produccion`); if (turno === solicitud.current) setRegistros(filas); }
    catch (e) { if (turno === solicitud.current) { setError(e.message); setRegistros([]); } }
  }
  const texto = busqueda.trim().toLocaleLowerCase("es-CL");
  const faenas = datos.faenas.filter(f => (!estado || f.estado === estado) && [f.nombre, f.cliente, f.predio, f.cultivo].join(" ").toLocaleLowerCase("es-CL").includes(texto));
  const clientes = datos.clientes.filter(c => [c.nombre, c.contacto, c.email].join(" ").toLocaleLowerCase("es-CL").includes(texto));
  const totalKg = faenas.reduce((a, f) => a + Number(f.kilos), 0);
  const cobro = faenas.reduce((a, f) => a + Number(f.cobro_estimado), 0);
  const sinTarifa = faenas.some(f => f.sin_tarifa > 0);
  const pago = sinTarifa ? null : faenas.reduce((a, f) => a + Number(f.pago_estimado), 0);

  return <section className="faenas-vista">
    <div className="page-heading"><div><span className="eyebrow">CLIENTES Y SERVICIOS</span><h1>Faenas agrícolas</h1><p>Relaciona cada cosecha con su cliente, predio y acuerdo de cobro por kilo.</p></div>{admin && <button disabled={ocupado} onClick={() => abrir(vista)}><Icon nombre="faenas" size={17} />{vista === "clientes" ? "Nuevo cliente" : "Nueva faena"}</button>}</div>
    <div className="operation-tabs">{["faenas", "clientes"].map(v => <button key={v} className={vista === v ? "selected" : ""} onClick={() => { setVista(v); setBusqueda(""); setEstado(""); }}>{v === "faenas" ? "Faenas y producción" : "Clientes"}</button>)}</div>
    {error && <p className="error" role="alert">{error}</p>}{aviso && <p className="mensaje" role="status">{aviso}</p>}

    {formulario && <form className="panel faena-formulario" onSubmit={guardar}><fieldset disabled={ocupado} className="campos-sin-borde">
      <div className="panel-heading sin-padding"><div><h2>{formulario.id ? "Editar" : "Crear"} {formulario.tipo === "clientes" ? "cliente" : "faena"}</h2><p>{formulario.tipo === "clientes" ? "Datos de contacto y estado del cliente." : "El precio de venta es independiente de la tarifa del trabajador."}</p></div><button type="button" className="boton-secundario" onClick={() => setFormulario(null)}>Cancelar</button></div>
      {formulario.tipo === "clientes" ? <div className="campos">
        <label className="campo">Nombre del cliente<input autoFocus required minLength={2} maxLength={160} value={formulario.valores.nombre} onChange={e => campo("nombre", e.target.value)} /></label>
        <label className="campo">Persona de contacto<input maxLength={120} value={formulario.valores.contacto} onChange={e => campo("contacto", e.target.value)} /></label>
        <label className="campo">Correo electrónico<input type="email" maxLength={180} value={formulario.valores.email} onChange={e => campo("email", e.target.value)} /></label>
        <label className="campo">Teléfono<input type="tel" maxLength={40} value={formulario.valores.telefono} onChange={e => campo("telefono", e.target.value)} /></label>
        <label className="campo">Estado<select value={String(formulario.valores.activo)} onChange={e => campo("activo", e.target.value === "true")}><option value="true">Activo</option><option value="false">Inactivo</option></select></label>
      </div> : <>
        {formulario.conProduccion && <p className="aviso-perfil">Esta faena ya tiene producción. Su cliente, identificación, inicio y precio se conservan. Para cambiar el acuerdo comercial, crea otra faena.</p>}
        {!datos.clientes.some(c => c.activo) && <p className="aviso-perfil">Crea primero un cliente activo en la pestaña Clientes.</p>}
        <div className="campos">
          <label className="campo">Cliente<select required disabled={formulario.conProduccion} value={formulario.valores.id_cliente} onChange={e => campo("id_cliente", e.target.value)}><option value="">Seleccionar cliente…</option>{datos.clientes.filter(c => c.activo || c.id === Number(formulario.valores.id_cliente)).map(c => <option value={c.id} key={c.id}>{c.nombre}{!c.activo ? " (inactivo)" : ""}</option>)}</select></label>
          <label className="campo">Nombre de la faena<input autoFocus required readOnly={formulario.conProduccion} minLength={2} maxLength={160} value={formulario.valores.nombre} onChange={e => campo("nombre", e.target.value)} /></label>
          <label className="campo">Predio o lugar del servicio<input required readOnly={formulario.conProduccion} minLength={2} maxLength={160} value={formulario.valores.predio} onChange={e => campo("predio", e.target.value)} /></label>
          <label className="campo">Cultivo<input readOnly={formulario.conProduccion} maxLength={100} placeholder="Ej.: palta" value={formulario.valores.cultivo} onChange={e => campo("cultivo", e.target.value)} /></label>
          <label className="campo">Fecha de inicio<input required readOnly={formulario.conProduccion} type="date" value={formulario.valores.fecha_inicio} onChange={e => campo("fecha_inicio", e.target.value)} /></label>
          <label className="campo">Fecha final (opcional)<input type="date" min={formulario.valores.fecha_inicio} value={formulario.valores.fecha_fin || ""} onChange={e => campo("fecha_fin", e.target.value)} /></label>
          <label className="campo">Precio a cobrar al cliente · CLP/kg<input required readOnly={formulario.conProduccion} type="number" step="0.01" min="0.01" max="9999999999.99" value={formulario.valores.precio_kg} onChange={e => campo("precio_kg", e.target.value)} /><small>Monto base por kilo. No agrega impuestos ni descuentos.</small></label>
          <label className="campo">Estado<select value={formulario.valores.estado} onChange={e => campo("estado", e.target.value)}>{["Planificada", "Activa", "Finalizada"].map(v => <option key={v}>{v}</option>)}</select><small>Solo las faenas activas reciben cosechas nuevas.</small></label>
        </div>
      </>}
      <label className="campo">Notas<textarea maxLength={1000} rows={2} value={formulario.valores.notas} onChange={e => campo("notas", e.target.value)} /></label>
      <div className="faena-form-acciones"><button disabled={ocupado || (formulario.tipo === "faenas" && !formulario.id && !datos.clientes.some(c => c.activo))}>{ocupado ? "Guardando…" : "Guardar cambios"}</button></div>
    </fieldset></form>}

    {cargando ? <div className="panel estado-vacio"><p>Cargando clientes y faenas…</p></div> : <>
      {vista === "faenas" && <><div className="faenas-indicadores"><div><span>Faenas mostradas</span><strong>{faenas.length}</strong></div><div><span>Producción vinculada</span><strong>{numero(totalKg)} <small>kg</small></strong></div><div><span>Cobro estimado al cliente</span><strong>{pesos(cobro)}</strong></div><div><span>Pago bruto estimado por producción</span><strong>{pesos(pago)}</strong></div></div><p className="faena-aclaracion">Estimaciones de las faenas filtradas, incluidos ajustes de kilos. El cobro no es una factura ni confirma dinero recibido. El pago bruto no incluye transporte, insumos ni otros costos; puede diferir del cierre por redondeo.</p>{sinTarifa && <p className="aviso-perfil">Faltan tarifas semanales de trabajadores en alguna faena. Completa esas tarifas para estimar el pago bruto. El precio al cliente sí está definido.</p>}</>}
      <div className="panel"><div className="tabla-toolbar"><label className="campo faena-buscador">Buscar {vista === "faenas" ? "faena, cliente o predio" : "cliente o contacto"}<input type="search" value={busqueda} onChange={e => setBusqueda(e.target.value)} placeholder="Escribe para filtrar…" /></label>{vista === "faenas" && <label className="campo">Estado<select value={estado} onChange={e => setEstado(e.target.value)}><option value="">Todos</option>{["Planificada", "Activa", "Finalizada"].map(e => <option key={e}>{e}</option>)}</select></label>}<button className="boton-secundario" onClick={() => cargar().catch(e => setError(e.message))}>Actualizar</button></div>
        <div className="tabla-contenedor"><table><thead>{vista === "faenas" ? <tr><th>Faena / cliente</th><th>Predio / período</th><th>Precio cliente</th><th>Producción</th><th>Cobro estimado</th><th>Estado</th><th>Acciones</th></tr> : <tr><th>Cliente</th><th>Contacto</th><th>Faenas</th><th>Estado</th>{admin && <th>Acciones</th>}</tr>}</thead><tbody>
          {vista === "faenas" ? faenas.map(f => <tr key={f.id}><td><strong>{f.nombre}</strong><small className="block-muted">{f.cliente}</small></td><td>{f.predio}<small className="block-muted">{fecha(f.fecha_inicio)} · {fecha(f.fecha_fin)}</small></td><td>{numero(f.precio_kg)} CLP/kg</td><td>{numero(f.kilos)} kg<small className="block-muted">{f.trabajadores} personas · {f.jornadas} jornadas</small></td><td>{pesos(f.cobro_estimado)}</td><td><span className={`faena-estado ${f.estado.toLowerCase()}`}>{f.estado}</span></td><td><div className="acciones"><button className="boton-secundario" onClick={() => abrirDetalle(f)}>Ver producción</button>{admin && <button className="boton-editar" onClick={() => abrir("faenas", f)}>Editar</button>}</div></td></tr>) : clientes.map(c => <tr key={c.id}><td><strong>{c.nombre}</strong>{c.notas && <small className="block-muted">{c.notas}</small>}</td><td>{c.contacto || "Sin contacto"}<small className="block-muted">{c.email || "Sin correo"}{c.telefono && ` · ${c.telefono}`}</small></td><td>{c.faenas}<small className="block-muted">{c.faenas_activas} activas</small></td><td><span className={`faena-estado ${c.activo ? "activa" : "finalizada"}`}>{c.activo ? "Activo" : "Inactivo"}</span></td>{admin && <td><button className="boton-editar" onClick={() => abrir("clientes", c)}>Editar</button></td>}</tr>)}
        </tbody></table></div>
        {!(vista === "faenas" ? faenas : clientes).length && <div className="estado-vacio"><Icon nombre="faenas" size={32} /><h2>{busqueda || estado ? "No hay coincidencias" : vista === "faenas" ? "Conecta tu primera faena" : "Registra tu primer cliente"}</h2><p>{busqueda || estado ? "Prueba con otros filtros." : vista === "faenas" ? "Crea un cliente, define la faena y selecciona ese servicio al registrar una cosecha." : "Agrega la empresa a la que Doña Laura presta el servicio."}</p></div>}
      </div>
      {detalle && <div className="panel faena-detalle"><div className="panel-heading sin-padding"><div><h2>{detalle.nombre}</h2><p>{detalle.cliente} · {detalle.predio} · {detalle.cultivo || "Cultivo sin especificar"}</p></div><button className="boton-secundario" onClick={() => { solicitud.current++; setDetalleId(null); setRegistros(null); }}>Cerrar detalle</button></div><div className="faena-resumen"><span>{numero(detalle.kilos)} kg</span><span>{numero(detalle.horas)} h</span><span>{pesos(detalle.cobro_estimado)} de cobro estimado</span><span>{pesos(detalle.pago_estimado)} de pago bruto estimado</span></div><p className="faena-aclaracion">El resumen incluye todos los registros de la faena. La tabla muestra hasta 200 registros recientes. Los kilos ajustados se muestran separados del original.</p>
        {registros === null ? <p>Cargando producción…</p> : <div className="tabla-contenedor"><table><thead><tr><th>Fecha / trabajador</th><th>Sector / labor</th><th>Kg originales</th><th>Ajuste kg</th><th>Kg vigentes</th><th>Horas</th></tr></thead><tbody>{registros.map(r => <tr key={r.id}><td><strong>{r.trabajador}</strong><small className="block-muted">{fecha(r.fecha)}</small></td><td>{r.sector}<small className="block-muted">{r.labor}</small></td><td>{numero(r.kilos_originales)}</td><td>{numero(r.ajuste_kg)}</td><td>{numero(r.kilos)}</td><td>{numero(r.horas)}</td></tr>)}</tbody></table>{!registros.length && <p className="empty-table">Esta faena todavía no tiene cosechas vinculadas.</p>}</div>}
      </div>}
    </>}
  </section>;
}
