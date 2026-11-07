import { useEffect, useState } from "react";
import { enviarJSON, solicitar } from "./api";
import { roles } from "./roles";

export function Cuenta({ usuario }) {
  const [datos, setDatos] = useState({ actual: "", nueva: "" });
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function guardar(e) {
    e.preventDefault(); setOcupado(true); setAviso(""); setError("");
    try { const r = await solicitar("/auth/password", enviarJSON("POST", datos)); setAviso(r.mensaje); setDatos({ actual: "", nueva: "" }); }
    catch (err) { setError(err.message); }
    finally { setOcupado(false); }
  }
  return <section><div className="page-heading"><div><span className="eyebrow">PERFIL Y SEGURIDAD</span><h1>Mi cuenta</h1><p>{usuario.nombre} · {roles[usuario.rol]}</p></div></div><form className="panel cuenta-form" onSubmit={guardar}><h2>Cambiar contraseña</h2><p className="muted">Usa al menos 12 caracteres. Se cerrarán las otras sesiones de tu cuenta.</p><label className="campo">Contraseña actual<input type="password" autoComplete="current-password" required value={datos.actual} onChange={e => setDatos({ ...datos, actual: e.target.value })} /></label><label className="campo">Nueva contraseña<input type="password" autoComplete="new-password" minLength={12} required value={datos.nueva} onChange={e => setDatos({ ...datos, nueva: e.target.value })} /></label>{error && <p className="error" role="alert">{error}</p>}{aviso && <p className="mensaje" role="status">{aviso}</p>}<button disabled={ocupado}>Actualizar contraseña</button></form></section>;
}

export default function Accesos({ usuario }) {
  const [usuarios, setUsuarios] = useState([]);
  const [eventos, setEventos] = useState([]);
  const [datos, setDatos] = useState({ usuario: "", nombre: "", password: "", rol: "consulta" });
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function cargar() {
    const [u,a] = await Promise.all([solicitar("/usuarios"),solicitar("/auditoria")]);
    setUsuarios(u); setEventos(a);
  }
  useEffect(() => { cargar().catch(e => setError(e.message)); }, []);
  async function crear(e) {
    e.preventDefault(); setOcupado(true); setError(""); setAviso("");
    try { await solicitar("/usuarios", enviarJSON("POST", datos)); setDatos({ usuario: "", nombre: "", password: "", rol: "consulta" }); await cargar(); setAviso("Usuario creado correctamente."); }
    catch (err) { setError(err.message); }
    finally { setOcupado(false); }
  }
  async function actualizar(persona, cambios) {
    setOcupado(true); setError(""); setAviso("");
    try { await solicitar(`/usuarios/${persona.id}`, enviarJSON("PATCH", { rol: persona.rol, activo: persona.activo, ...cambios })); await cargar(); setAviso("Permisos actualizados. Se cerraron las sesiones de esa cuenta."); }
    catch (e) { setError(e.message); }
    finally { setOcupado(false); }
  }
  return <section><div className="page-heading"><div><span className="eyebrow">CONTROL DE ACCESO</span><h1>Usuarios y actividad</h1><p>Administra quién puede operar y consulta los últimos movimientos.</p></div></div>
    <div className="perfiles-grid">{[["Administrador","Usuarios, configuración, tarifas y cierre de pagos."],["Encargado","Trabajadores, jornadas, cosechas e importaciones."],["Solo consulta","Indicadores, reportes y consultas al asistente."]].map(([t,d]) => <article className="panel" key={t}><h3>{t}</h3><p className="muted">{d}</p></article>)}</div>
    {error && <p className="error" role="alert">{error}</p>}{aviso && <p className="mensaje" role="status">{aviso}</p>}
    <form className="panel usuario-form" onSubmit={crear}><h2>Agregar usuario</h2><div className="campos"><label className="campo">Nombre completo<input required maxLength={120} value={datos.nombre} onChange={e => setDatos({ ...datos, nombre: e.target.value })} /></label><label className="campo">Usuario<input required pattern="[a-zA-Z0-9._-]{3,80}" autoComplete="off" value={datos.usuario} onChange={e => setDatos({ ...datos, usuario: e.target.value })} /></label><label className="campo">Perfil<select value={datos.rol} onChange={e => setDatos({ ...datos, rol: e.target.value })}>{Object.entries(roles).map(([id,t]) => <option value={id} key={id}>{t}</option>)}</select></label><label className="campo">Contraseña inicial<input required type="password" minLength={12} autoComplete="new-password" value={datos.password} onChange={e => setDatos({ ...datos, password: e.target.value })} /><small>Mínimo 12 caracteres</small></label></div><button disabled={ocupado}>Crear usuario</button></form>
    <div className="panel"><div className="panel-heading"><h2>Accesos del equipo</h2><span className="muted">{usuarios.length} cuentas</span></div><div className="tabla-contenedor"><table><thead><tr><th>Persona</th><th>Usuario</th><th>Perfil</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{usuarios.map(u => <tr key={u.id}><td><strong>{u.nombre}</strong></td><td>{u.usuario}</td><td><select aria-label={`Perfil de ${u.nombre}`} disabled={ocupado || u.id === usuario.id} value={u.rol} onChange={e => actualizar(u,{rol:e.target.value})}>{Object.entries(roles).map(([id,t]) => <option value={id} key={id}>{t}</option>)}</select></td><td><span className={u.activo ? "activo" : "inactivo"}>{u.activo ? "Activo" : "Inactivo"}</span></td><td><button className="boton-secundario" disabled={ocupado || u.id === usuario.id} onClick={() => actualizar(u,{activo:!u.activo})}>{u.activo ? "Desactivar" : "Activar"}</button></td></tr>)}</tbody></table></div></div>
    <div className="panel auditoria-panel"><div className="panel-heading"><div><h2>Registro de actividad</h2><p>Últimas 200 operaciones exitosas · hora local de Chile</p></div><button className="boton-secundario" disabled={ocupado} onClick={() => cargar().catch(e => setError(e.message))}>Actualizar</button></div><div className="tabla-contenedor"><table><thead><tr><th>Fecha</th><th>Usuario</th><th>Operación</th></tr></thead><tbody>{eventos.map(a => <tr key={a.id}><td>{new Intl.DateTimeFormat("es-CL",{dateStyle:"short",timeStyle:"short",timeZone:"America/Santiago"}).format(new Date(a.fecha))}</td><td>{a.nombre}</td><td>{a.accion}</td></tr>)}</tbody></table></div></div>
  </section>;
}
