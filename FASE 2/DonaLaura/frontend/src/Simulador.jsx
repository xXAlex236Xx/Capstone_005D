import { useState } from "react";
import Icon from "./Icon";
import { EJEMPLO, evaluarContrato } from "./simulador.mjs";
import "./Simulador.css";

const pesos = n => new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(n);
const numero = (n, dec = 0) => new Intl.NumberFormat("es-CL", { maximumFractionDigits: dec }).format(n);
const campos = [
  ["kilos", "Kilos esperados", "kg", 1, 1e8, 1], ["precio", "Precio ofrecido por el cliente", "$/kg", 0, 1e6, .01],
  ["tarifa", "Pago variable a trabajadores", "$/kg", 0, 1e6, .01], ["dias", "Duración de la faena", "días", 1, 365, 1],
  ["transporte", "Transporte del equipo por día", "$/día", 0, 1e10, 1], ["supervision", "Supervisión por día", "$/día", 0, 1e10, 1],
  ["otros", "Otros costos del contrato", "$", 0, 1e11, 1], ["contingencia", "Reserva sobre costos", "%", 0, 100, .1],
  ["objetivo", "Margen objetivo sobre ventas", "%", 0, 90, .1],
];

function Sensibilidad({ valores, factor }) {
  const puntos = Array.from({ length: 21 }, (_, i) => ({ factor: .5 + i * .05, ...evaluarContrato(valores, .5 + i * .05) }));
  const actual = evaluarContrato(valores, factor);
  const min = Math.min(0, ...puntos.map(p => p.margen)), max = Math.max(1, ...puntos.map(p => p.margen));
  const y = valor => 150 - (valor - min) / (max - min) * 115;
  const x = f => 62 + (f - .5) * 565;
  return <svg viewBox="0 0 690 205" role="img" aria-label={`Sensibilidad del margen al volumen entre 50 y 150 por ciento de lo esperado. Con ${numero(actual.kilos)} kilos el margen es ${pesos(actual.margen)}.`}>
    <defs><linearGradient id="margen-relleno" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#5c9675" stopOpacity=".22"/><stop offset="100%" stopColor="#5c9675" stopOpacity=".02"/></linearGradient></defs>
    <path d={`M${x(.5)},${y(0)} ${puntos.map(p => `L${x(p.factor)},${y(p.margen)}`).join(" ")} L${x(1.5)},${y(0)}Z`} fill="url(#margen-relleno)"/>
    <line x1="62" x2="627" y1={y(0)} y2={y(0)} stroke="#b9c8ba" strokeDasharray="5 5"/><text x="62" y={y(0) - 7} fill="#738171" fontSize="10">Sin ganancia ni pérdida</text>
    <polyline points={puntos.map(p => `${x(p.factor)},${y(p.margen)}`).join(" ")} fill="none" stroke="#337052" strokeWidth="3"/>
    <line x1={x(factor)} x2={x(factor)} y1="25" y2="160" stroke="#acbbab" strokeDasharray="3 4"/>
    <circle cx={x(factor)} cy={y(actual.margen)} r="6" fill={actual.margen < 0 ? "#b85b44" : "#24583e"} stroke="white" strokeWidth="3"/>
    {[.5, .75, 1, 1.25, 1.5].map(f => <text key={f} x={x(f)} y="182" textAnchor="middle" fill="#738171" fontSize="11">{numero(f * 100)}%</text>)}
    <text x="345" y="202" textAnchor="middle" fill="#738171" fontSize="10">Volumen respecto a los kilos esperados · costos diarios constantes</text>
  </svg>;
}

export default function Simulador({ entorno }) {
  const mostrarEjemplos = entorno?.ejemplos_disponibles === true;
  const [valores, setValores] = useState(() =>
    mostrarEjemplos ? { ...EJEMPLO } : Object.fromEntries(campos.map(([clave]) => [clave, ""]))
  );
  const [volumen, setVolumen] = useState(100);
  const [nombre, setNombre] = useState("Nueva oportunidad de cosecha");
  const [ejemplo, setEjemplo] = useState(mostrarEjemplos);
  const resultado = evaluarContrato(valores, volumen / 100);
  const bajo = evaluarContrato(valores, .8);
  const decision = !resultado ? "Completa los supuestos" : resultado.ingreso === 0 ? "El escenario no genera ingresos" : resultado.margen < 0 ? "El escenario proyecta una pérdida" : resultado.porcentaje < Number(valores.objetivo) ? "Hay margen, pero falta llegar a tu objetivo" : "El escenario alcanza tu margen objetivo";
  function cambiar(k, v) { setValores(s => ({ ...s, [k]: v })); setEjemplo(false); }
  function reiniciar() { setValores({ ...EJEMPLO }); setVolumen(100); setEjemplo(true); setNombre("Nueva oportunidad de cosecha"); }
  return <section className="simulador-vista">
    <div className="page-heading"><div><span className="eyebrow">DECISIONES ANTES DEL CONTRATO</span><h1>¿Conviene aceptar esta faena?</h1><p>Prueba una oferta, anticipa el riesgo y encuentra el precio que necesitas negociar.</p></div>{mostrarEjemplos && <button className="boton-secundario" onClick={reiniciar}><Icon nombre="actualizar" size={16}/> Cargar ejemplo</button>}</div>
    <div className="sim-aviso"><Icon nombre="simulador" size={18}/><span><strong>{ejemplo ? "Ejemplo hipotético para explorar" : "Simulación con tus supuestos"}</strong> · No modifica faenas, tarifas ni pagos. Valores netos en CLP, antes de impuestos.</span></div>
    <div className="sim-layout">
      <div className="sim-form panel"><div className="sim-panel-title"><span className="sim-step">01</span><div><h2>Construye la oferta</h2><p>Estos valores son editables; no se toman del historial.</p></div></div>
        <label className="sim-campo sim-nombre">Nombre del escenario<input value={nombre} maxLength={100} onChange={e => setNombre(e.target.value)}/></label>
        <div className="sim-campos">{campos.map(([k, etiqueta, unidad, min, max, step]) => <label className="sim-campo" key={k}>{etiqueta}<div><input type="number" min={min} max={max} step={step} value={valores[k]} onChange={e => cambiar(k, e.target.value)} /><span>{unidad}</span></div></label>)}</div>
        <p className="sim-ayuda">Incluye en “otros costos” los gastos adicionales que correspondan. La reserva se aplica a todos los costos ingresados. El pago por kilo no incluye automáticamente otros costos laborales.</p>
      </div>
      <div className="sim-resultados">
        <div className={`sim-veredicto ${resultado?.margen < 0 ? "riesgo" : resultado?.porcentaje >= Number(valores.objetivo) ? "favorable" : "revisar"}`} aria-live="polite">
          <span className="eyebrow">{nombre || "Tu escenario"}</span><h2>{decision}</h2>
          {resultado && <p>{resultado.margen < 0 ? "El ingreso no cubre los costos que ingresaste. Revisa precio, volumen y costos antes de decidir." : `Para un margen de ${numero(Number(valores.objetivo), 1)}%, prueba un precio de al menos $${numero(Math.ceil(resultado.precioObjetivo * 100) / 100, 2)} por kilo en este escenario.`}</p>}
        </div>
        {!resultado ? <p className="error" role="alert">Completa todos los campos con números válidos. Kilos desde 1, días enteros entre 1 y 365, costos desde 0, reserva de 0 a 100% y objetivo de 0 a 90%.</p> : <>
          <div className="sim-kpis"><article><span>Ingreso estimado</span><strong>{pesos(resultado.ingreso)}</strong><small>{numero(resultado.kilos)} kg × ${numero(Number(valores.precio), 2)}</small></article><article><span>Costo total + reserva</span><strong>{pesos(resultado.costos)}</strong><small>Según los supuestos ingresados</small></article><article className={resultado.margen < 0 ? "negativo" : "positivo"}><span>Margen estimado</span><strong>{pesos(resultado.margen)}</strong><small>{resultado.porcentaje == null ? "Sin ventas para calcular porcentaje" : `${numero(resultado.porcentaje, 1)}% sobre ventas`}</small></article></div>
          <div className="sim-grafico panel"><div className="sim-panel-title"><span className="sim-step">02</span><div><h2>¿Y si cosechamos menos?</h2><p>Mueve el volumen. Mantendremos los mismos días y costos fijos.</p></div></div>
            <div className="sim-range-label"><label htmlFor="sim-volumen">Volumen simulado</label><strong>{numero(volumen)}% <small>· {numero(resultado.kilos)} kg</small></strong></div>
            <input id="sim-volumen" type="range" min="50" max="150" step="1" value={volumen} onChange={e => setVolumen(Number(e.target.value))}/>
            <Sensibilidad valores={valores} factor={volumen / 100}/>
            <div className="sim-riesgo"><strong>Con 20% menos de cosecha</strong><span>El margen sería {pesos(bajo.margen)}{bajo.porcentaje == null ? "" : ` (${numero(bajo.porcentaje, 1)}%)`}. El pago por kilo baja con el volumen; los costos diarios se mantienen.</span></div>
          </div>
          <div className="sim-objetivos"><article><span>Precio para no perder</span><strong>${numero(Math.ceil(resultado.precioEquilibrio * 100) / 100, 2)} <small>/ kg</small></strong><p>Cubre costos y reserva con el volumen simulado.</p></article><article><span>Precio para tu objetivo</span><strong>${numero(Math.ceil(resultado.precioObjetivo * 100) / 100, 2)} <small>/ kg</small></strong><button className="sim-probar" onClick={() => cambiar("precio", Math.ceil(resultado.precioObjetivo * 100) / 100)}>Probar este precio <Icon nombre="flecha" size={15}/></button></article><article><span>Kilos para no perder</span><strong>{resultado.kilosEquilibrio == null ? "No se alcanza" : numero(Math.ceil(resultado.kilosEquilibrio))} <small>{resultado.kilosEquilibrio == null ? "" : "kg"}</small></strong><p>{resultado.kilosEquilibrio == null ? "El precio no cubre el costo variable y su reserva por kilo." : "Al precio ofrecido, manteniendo días y costos fijos."}</p></article></div>
        </>}
      </div>
    </div>
    {resultado && <div className="sim-comparacion panel"><div className="sim-panel-title"><span className="sim-step">03</span><div><h2>Tres escenarios, una decisión informada</h2><p>Comparación sobre los kilos esperados del formulario, independiente del deslizador.</p></div></div><div className="tabla-contenedor"><table><thead><tr><th>Escenario</th><th>Volumen</th><th>Ingresos</th><th>Costos + reserva</th><th>Margen estimado</th><th>% sobre ventas</th></tr></thead><tbody>{[["Conservador", .8], ["Esperado", 1], ["Mayor cosecha", 1.2]].map(([etiqueta, f]) => { const r = evaluarContrato(valores, f); return <tr key={etiqueta}><td><strong>{etiqueta}</strong></td><td>{numero(r.kilos)} kg</td><td>{pesos(r.ingreso)}</td><td>{pesos(r.costos)}</td><td className={r.margen < 0 ? "sim-perdida" : "sim-ganancia"}>{pesos(r.margen)}</td><td>{r.porcentaje == null ? "—" : `${numero(r.porcentaje, 1)}%`}</td></tr>; })}</tbody></table></div></div>}
    <p className="sim-nota">Herramienta de planificación con cálculos deterministas. No es una predicción de la IA ni una garantía de rentabilidad. El margen solo considera los costos ingresados; no acredita cobros recibidos, impuestos ni todos los gastos de la empresa. Los supuestos se conservan al navegar en esta sesión, pero se reinician al recargar o cerrar la página.</p>
  </section>;
}
