import { useEffect, useState } from "react";
import { solicitar } from "./api";
import Icon from "./Icon";

const numero = (valor, digitos = 0) => new Intl.NumberFormat("es-CL", { maximumFractionDigits: digitos }).format(valor || 0);
const fecha = valor => valor ? new Intl.DateTimeFormat("es-CL", { day: "numeric", month: "short" }).format(new Date(`${valor}T12:00:00`)) : "Sin registros";

function Grafico({ dias }) {
  const maximo = Math.max(...dias.map(d => d.kilos), 1);
  const puntos = dias.map((d, i) => `${48 + i * 86},${190 - d.kilos / maximo * 145}`);
  return <svg className="grafico-jornadas" viewBox="0 0 612 234" role="img" aria-label="Kilos registrados por fecha durante los últimos siete días con actividad">
    <defs><linearGradient id="areaProduccion" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#32866a" stopOpacity=".18" /><stop offset="100%" stopColor="#32866a" stopOpacity="0" /></linearGradient></defs>
    {[0, 1, 2, 3].map(i => <g key={i}><line x1="48" x2="568" y1={45+i*48.3} y2={45+i*48.3} stroke="#e9eeeb" strokeDasharray="4 4" /><text x="36" y={49+i*48.3} textAnchor="end" fill="#8a9690" fontSize="10">{numero(maximo*(1-i/3))}</text></g>)}
    {puntos.length > 0 && <><polygon points={`48,190 ${puntos.join(" ")} 564,190`} fill="url(#areaProduccion)" /><polyline points={puntos.join(" ")} stroke="#2c8061" strokeWidth="2.5" fill="none" strokeLinejoin="round" />
    {dias.map((d, i) => <g key={d.fecha}><circle cx={48+i*86} cy={190-d.kilos/maximo*145} r="4" fill="#fff" stroke="#2c8061" strokeWidth="2"><title>{fecha(d.fecha)}: {numero(d.kilos, 2)} kg</title></circle><text x={48+i*86} y="220" textAnchor="middle" fill="#78857d" fontSize="11">{fecha(d.fecha)}</text></g>)}</>}
  </svg>;
}

export default function Inicio({ usuario }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { let vivo = true; solicitar("/resumen").then(d => vivo && setDatos(d)).catch(e => vivo && setError(e.message)); return () => { vivo = false; }; }, []);
  if (error) return <div className="error" role="alert">{error}</div>;
  if (!datos) return <p className="cargando">Cargando el resumen de tu operación…</p>;
  const rendimiento = datos.horas > 0 ? datos.kilos / datos.horas : 0;
  const maxSector = Math.max(...datos.sectores.map(s => s.kilos), 1);
  return <section className="inicio-page">
    <div className="page-heading"><div><span className="eyebrow">RESUMEN GENERAL</span><h1>Una mirada a tu operación</h1><p>Hola, {usuario.nombre}. Revisa los indicadores de tu última semana registrada.</p></div>{usuario.rol !== "consulta" && <a className="boton-enlace" href="#cosechas"><span>+</span> Registrar cosecha</a>}</div>
    <div className="periodo-resumen"><span className="punto-estado" />Datos de producción <strong>{fecha(datos.desde)} — {fecha(datos.hasta)}</strong><span className="periodo-nota">Últimos 7 días hasta el registro más reciente</span></div>
    <div className="kpi-grid">
      {[
        ["Producción registrada", numero(datos.kilos, 1), "kg", "cosechas", datos.variacion !== null ? `${datos.variacion > 0 ? "+" : ""}${numero(datos.variacion, 1)}% respecto a los 7 días anteriores` : "Sin período anterior para comparar"],
        ["Productividad", numero(rendimiento, 1), "kg/h", "productividad", `${numero(datos.horas, 1)} horas registradas en el período`],
        ["Trabajadores activos", numero(datos.activos), "", "trabajadores", "Personas habilitadas en el sistema"],
        ["Semanas por cerrar", numero(datos.semanas_pendientes), "", "pagos", "Semanas con producción sin cierre de pagos"],
      ].map(([titulo, valor, unidad, icono, nota]) => <article className="kpi-card" key={titulo}><div className="kpi-title">{titulo}<span><Icon nombre={icono} size={18} /></span></div><strong>{valor}<small>{unidad}</small></strong><p>{nota}</p></article>)}
    </div>
    <div className="dashboard-grid"><article className="panel grafico-panel"><div className="panel-heading"><div><h2>Evolución de la producción</h2><p>Kilos por jornada · última semana registrada</p></div><span className="chart-legend"><i />Producción</span></div>{datos.dias.length ? <Grafico dias={datos.dias} /> : <div className="estado-vacio"><Icon nombre="cosechas" size={32} /><h3>Tu primera jornada empieza aquí</h3><p>Registra una cosecha o importa una planilla para ver los indicadores.</p><a href="#importacion">Ir a importación <span>→</span></a></div>}</article>
      <article className="panel"><div className="panel-heading"><div><h2>Producción por sector</h2><p>Distribución del mismo período</p></div></div><div className="sectores-resumen">{datos.sectores.length ? datos.sectores.map((s,i) => <div key={s.nombre}><div><span><i className={`sector-dot sector-${i%3}`} />{s.nombre}</span><strong>{numero(s.kilos)} <small>kg</small></strong></div><div className="sector-bar"><i style={{width:`${s.kilos/maxSector*100}%`}} /></div></div>) : <p className="muted">Aún no hay producción distribuida por sector.</p>}</div><a className="panel-link" href="#productividad">Explorar productividad <Icon nombre="flecha" size={16} /></a></article>
    </div>
    <div className="dashboard-grid inferior"><article className="panel"><div className="panel-heading"><div><h2>Producción por trabajador</h2><p>Los 5 mayores volúmenes del período</p></div><a href="#trabajadores">Ver trabajadores →</a></div><div className="tabla-contenedor"><table><thead><tr><th>Trabajador</th><th>Producción</th><th>Horas</th><th>Rendimiento</th></tr></thead><tbody>{datos.trabajadores.map(t => <tr key={t.id}><td><span className="avatar-pequeno">{t.nombre.split(" ").map(n => n[0]).slice(0,2).join("")}</span><strong>{t.nombre}</strong></td><td>{numero(t.kilos,1)} kg</td><td>{numero(t.horas,1)} h</td><td>{t.horas ? `${numero(t.kilos/t.horas,1)} kg/h` : "—"}</td></tr>)}</tbody></table>{!datos.trabajadores.length && <p className="empty-table">No hay producción registrada.</p>}</div></article>
      <article className="panel accesos-panel"><div className="panel-heading"><div><h2>Continúa tu gestión</h2><p>Herramientas para cada jornada</p></div></div>{[["importacion", "Importar planillas", "Revisa y carga tus registros de Excel"],["pagos", "Revisar pagos", "Consulta tarifas y cierres semanales"],["asistente", "Consultar al asistente", "Explora tus datos con inteligencia artificial"]].map(([id,titulo,nota]) => <a className="acceso-rapido" href={`#${id}`} key={id}><span className="acceso-icon"><Icon nombre={id} /></span><div><strong>{titulo}</strong><small>{nota}</small></div><Icon nombre="flecha" size={17} /></a>)}</article></div>
    <p className="dashboard-footnote">Los indicadores reflejan los registros disponibles. El volumen cosechado debe interpretarse junto con las condiciones de cada jornada.</p>
  </section>;
}
