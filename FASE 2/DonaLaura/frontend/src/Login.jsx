import { useState } from "react";
import Icon from "./Icon";
import { enviarJSON, solicitar } from "./api";

export default function Login({ onLogin }) {
  const [datos, setDatos] = useState({ usuario: "", password: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  async function entrar(evento) {
    evento.preventDefault(); setEnviando(true); setError("");
    try { onLogin(await solicitar("/auth/login", enviarJSON("POST", datos))); }
    catch (e) { setError(e.message); }
    finally { setEnviando(false); }
  }
  return <div className="login-page">
    <aside className="login-presentacion">
      <div className="login-marca"><span className="logo"><Icon nombre="cosechas" size={27} /></span>agricolix<span className="marca-punto">.</span></div>
      <div className="login-discurso"><span className="eyebrow">GESTIÓN AGRÍCOLA</span><h1>Tu operación,<br />con una visión<br /><em>más clara.</em></h1><p>Producción, personas y pagos.<br />La información que necesitas para gestionar cada jornada.</p></div>
      <div className="login-pie">Doña Laura SpA <span>Plataforma de gestión</span></div>
    </aside>
    <main className="login-panel"><div className="login-formulario">
      <span className="eyebrow">BIENVENIDO A TU ESPACIO DE TRABAJO</span>
      <h2>Iniciar sesión</h2><p className="muted">Ingresa con la cuenta asignada por tu administrador.</p>
      <form onSubmit={entrar}>
        <label className="campo">Usuario<input name="username" autoComplete="username" autoFocus required value={datos.usuario} onChange={e => setDatos({ ...datos, usuario: e.target.value })} /></label>
        <label className="campo">Contraseña<input name="password" type="password" autoComplete="current-password" required value={datos.password} onChange={e => setDatos({ ...datos, password: e.target.value })} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="login-boton" disabled={enviando}>{enviando ? "Validando acceso…" : "Entrar al sistema"}<Icon nombre="flecha" /></button>
      </form>
      <p className="login-ayuda">¿Necesitas acceso? Contacta al administrador de tu empresa.</p>
    </div><span className="login-nota">Acceso privado · Doña Laura SpA</span></main>
  </div>;
}
