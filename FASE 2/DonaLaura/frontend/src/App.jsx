import { useEffect, useState } from "react";
import "./App.css";
import Trabajadores from "./Trabajadores";
import Cosechas from "./Cosechas";
import Productividad from "./Productividad";
import Pagos from "./Pagos";
import SeguimientoPagos from "./SeguimientoPagos";
import Faenas from "./Faenas";
import Simulador from "./Simulador.jsx";
import Reportes from "./Reportes";
import Administracion from "./Administracion";
import Importacion from "./Importacion";
import AnalisisIA from "./AnalisisIA";
import AsistenteIA from "./AsistenteIA";
import Inicio from "./Inicio";
import MiDia from "./MiDia";
import Cobros from "./Cobros";
import Semana from "./Semana";
import Login from "./Login";
import Accesos, { Cuenta } from "./Accesos";
import { roles } from "./roles";
import Icon from "./Icon";
import { solicitar, API } from "./api";
import "./enterprise.css";

const GRUPOS = [
  { nombre: "GENERAL", secciones: [{ id: "inicio", etiqueta: "Mi día", Vista: MiDia }, { id: "semana", etiqueta: "Preparar la semana", Vista: Semana }, { id: "resumen", etiqueta: "Vista general", Vista: Inicio }, { id: "productividad", etiqueta: "Productividad", Vista: Productividad }] },
  { nombre: "OPERACIÓN", secciones: [{ id: "faenas", etiqueta: "Clientes y faenas", Vista: Faenas }, { id: "trabajadores", etiqueta: "Trabajadores", Vista: Trabajadores }, { id: "cosechas", etiqueta: "Cosechas", Vista: Cosechas, persistente: true }, { id: "importacion", etiqueta: "Importación", Vista: Importacion, persistente: true }] },
  { nombre: "FINANZAS", secciones: [{ id: "cobros", etiqueta: "Cobros a clientes", Vista: Cobros }, { id: "simulador", etiqueta: "Simulador de contratos", Vista: Simulador, persistente: true }, { id: "pagos", etiqueta: "Pagos semanales", Vista: Pagos }, { id: "seguimiento-pagos", etiqueta: "Seguimiento de pagos", Vista: SeguimientoPagos }, { id: "reportes", etiqueta: "Reportes", Vista: Reportes }] },
  { nombre: "INTELIGENCIA", secciones: [{ id: "analisis-ia", etiqueta: "Análisis de datos", Vista: AnalisisIA }, { id: "asistente", etiqueta: "Asistente IA", Vista: AsistenteIA, persistente: true }] },
  { nombre: "ADMINISTRACIÓN", secciones: [{ id: "administracion", etiqueta: "Configuración", Vista: Administracion }, { id: "usuarios", etiqueta: "Usuarios y actividad", Vista: Accesos, admin: true }] },
];
const SECCIONES = [...GRUPOS.flatMap(g => g.secciones), { id: "cuenta", etiqueta: "Mi cuenta", Vista: Cuenta }];
function desdeHash() { const id = window.location.hash.slice(1).split("?")[0]; return SECCIONES.some(s => s.id === id) ? id : "inicio"; }
function AvisoDemostracion({ entorno }) {
  return entorno?.demostracion ? <div className="aviso-demostracion" role="note"><strong>ENTORNO DE DEMOSTRACIÓN</strong><span>Datos ficticios · {entorno.desde} al {entorno.hasta}. Puedes explorar y hacer pruebas en esta copia.</span></div> : null;
}

export default function App() {
  const [usuario, setUsuario] = useState(null);
  const [iniciando, setIniciando] = useState(true);
  const [activa, setActiva] = useState(desdeHash);
  const [visitadas, setVisitadas] = useState(() => new Set([desdeHash()]));
  const [menu, setMenu] = useState(false);
  const [movil, setMovil] = useState(() => window.matchMedia("(max-width: 900px)").matches);
  const [salud, setSalud] = useState("comprobando");
  const [version, setVersion] = useState(0);
  const [aviso, setAviso] = useState("");
  const [entorno, setEntorno] = useState(null);
  useEffect(() => {
    let vigente = true;
    solicitar("/entorno").then(e => vigente && setEntorno(e)).catch(() => {});
    return () => { vigente = false; };
  }, []);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 900px)");
    const cambiar = e => { setMovil(e.matches); if (!e.matches) setMenu(false); };
    media.addEventListener("change", cambiar);
    return () => media.removeEventListener("change", cambiar);
  }, []);
  useEffect(() => {
    let vivo = true;
    solicitar("/auth/session").then(u => vivo && setUsuario(u)).catch(() => {}).finally(() => vivo && setIniciando(false));
    const vencida = () => { setUsuario(null); setVisitadas(new Set()); };
    window.addEventListener("sesion-vencida", vencida);
    return () => { vivo = false; window.removeEventListener("sesion-vencida", vencida); };
  }, []);
  useEffect(() => {
    const cambiar = () => { const id = desdeHash(); setActiva(id); setVisitadas(v => new Set(v).add(id)); setMenu(false); window.scrollTo({ top: 0 }); };
    const escape = e => { if (e.key === "Escape") setMenu(false); };
    window.addEventListener("hashchange", cambiar); window.addEventListener("keydown", escape);
    return () => { window.removeEventListener("hashchange", cambiar); window.removeEventListener("keydown", escape); };
  }, []);
  useEffect(() => {
    let vivo = true;
    const comprobar = () => window.fetch(`${API}/health`).then(r => vivo && setSalud(r.ok ? "ok" : "error")).catch(() => vivo && setSalud("error"));
    comprobar(); const reloj = setInterval(comprobar, 30000);
    return () => { vivo = false; clearInterval(reloj); };
  }, []);
  async function salir() {
    try { await solicitar("/auth/logout", { method: "POST" }); setUsuario(null); setVisitadas(new Set()); setAviso(""); }
    catch (e) { setAviso(e.message); }
  }
  function entrar(u) { setUsuario(u); setVisitadas(new Set(["inicio"])); setActiva("inicio"); window.location.hash = "inicio"; }
  if (iniciando) return <div className="pantalla-carga"><span className="logo"><Icon nombre="cosechas" /></span><p>Preparando tu espacio de trabajo…</p></div>;
  if (!usuario) return <><AvisoDemostracion entorno={entorno} /><Login onLogin={entrar} /></>;
  const seccion = SECCIONES.find(s => s.id === activa && (!s.admin || usuario.rol === "administrador")) || SECCIONES[0];
  return <div className="aplicacion" data-rol={usuario.rol}>
    <aside className={`barra-lateral ${menu ? "abierta" : ""}`} aria-label="Navegación principal" inert={movil && !menu} aria-hidden={movil && !menu}>
      <a className="marca" href="#inicio"><span className="logo"><Icon nombre="cosechas" size={25} /></span><div><strong>agricolix<span>.</span></strong><small>GESTIÓN AGRÍCOLA</small></div></a>
      <div className="empresa-selector"><span className="empresa-avatar">DL</span><div><strong>Doña Laura SpA</strong><small>Espacio de trabajo</small></div><span>⌄</span></div>
      <nav>{GRUPOS.map(g => <div className="menu-grupo" key={g.nombre}><p className="menu-grupo-titulo">{g.nombre}</p>{g.secciones.filter(s => !s.admin || usuario.rol === "administrador").map(s => <a href={`#${s.id}`} key={s.id} className={`enlace-menu ${seccion.id === s.id ? "enlace-actual" : ""}`} aria-current={seccion.id === s.id ? "page" : undefined}><Icon nombre={s.id} size={18} /><span>{s.etiqueta}</span>{s.id === "asistente" && <small className="ia-badge" aria-hidden="true">IA</small>}</a>)}</div>)}</nav>
      <div className="sidebar-bottom"><div className="entorno-indicador"><span className={`punto-estado ${salud === "error" ? "offline" : ""}`} />{salud === "ok" ? "Sistema disponible" : salud === "error" ? "Revisar conexión" : "Comprobando conexión"}</div><a className="sidebar-cuenta" href="#cuenta"><span className="user-avatar">{usuario.nombre.slice(0,1)}</span><div><strong>{usuario.nombre}</strong><small>{roles[usuario.rol]}</small></div><Icon nombre="cuenta" size={17} /></a><button className="salir-button" onClick={salir}><Icon nombre="salir" size={16} />Cerrar sesión</button></div>
    </aside>
    {menu && <button className="fondo-menu" aria-label="Cerrar menú" onClick={() => setMenu(false)} />}
    <div className="contenido"><header className="barra-superior"><div className="breadcrumb"><button className="boton-menu" aria-label="Abrir menú" aria-expanded={menu} onClick={() => setMenu(true)}><Icon nombre="menu" /></button><span>Espacio de trabajo</span><span className="breadcrumb-separador">/</span><strong>{seccion.etiqueta}</strong></div><div className="topbar-actions"><time>{new Intl.DateTimeFormat("es-CL", { day: "numeric", month: "long", year: "numeric", timeZone: "America/Santiago" }).format(new Date())}</time><button className="icon-button" title="Actualizar vista" aria-label="Actualizar vista" onClick={() => setVersion(v => v+1)}><Icon nombre="actualizar" size={17} /></button><a href="#cuenta" className="user-avatar" aria-label="Mi cuenta">{usuario.nombre.slice(0,1)}</a></div></header>
      <AvisoDemostracion entorno={entorno} /><main>{aviso && <p className="error" role="alert">{aviso}</p>}{salud === "error" && <p className="error" role="alert">El servicio no está disponible. Comprueba el estado del sistema e intenta nuevamente.</p>}{usuario.rol === "consulta" && <div className="aviso-perfil">Perfil de consulta · Puedes revisar información y descargar reportes.</div>}
        {SECCIONES.map(({id,Vista,persistente,admin}) => {
          const visible = id === seccion.id;
          if ((admin && usuario.rol !== "administrador") || (!visible && !(persistente && visitadas.has(id)))) return null;
          return <div className="vista-contenido" key={`${id}:${version}`} hidden={!visible}><Vista usuario={usuario} /></div>;
        })}
      </main><footer className="app-footer"><span>agricolix · Doña Laura SpA</span><span>Gestión basada en tus registros</span></footer>
    </div>
  </div>;
}
