import { useEffect, useRef, useState } from "react";
import { solicitar } from "./api";

export default function RepetirJornada({ fecha, onCargar, hayBorrador, disabled }) {
  const [abierto, setAbierto] = useState(false);
  const [origen, setOrigen] = useState("");
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const turno = useRef(0);
  useEffect(() => () => { turno.current++; }, []);
  async function buscar() {
    const actual = ++turno.current;
    setAbierto(true); setCargando(true); setError(""); setDatos(null);
    try {
      const d = await solicitar(`/produccion/plantilla?destino=${encodeURIComponent(fecha)}${origen ? `&origen=${encodeURIComponent(origen)}` : ""}`);
      if (turno.current === actual) setDatos(d);
    } catch (e) { if (turno.current === actual) setError(e.message); }
    finally { if (turno.current === actual) setCargando(false); }
  }
  return <div className="repetir-jornada panel">
    <div className="repetir-encabezado"><div><strong>El mismo equipo, menos digitación</strong><p>Carga una jornada anterior y completa los kilos y horas de la nueva fecha.</p></div><button type="button" className="boton-secundario" disabled={disabled || cargando || !fecha} onClick={buscar}>{cargando ? "Buscando…" : "Repetir jornada anterior"}</button></div>
    {abierto && <div className="repetir-contenido"><div className="repetir-busqueda"><label className="campo">Buscar otra fecha de origen<input type="date" value={origen} disabled={disabled || cargando} onInput={e => { setOrigen(e.target.value); setDatos(null); setError(""); }}/><small>Vacío: última jornada con registros anterior al {fecha}.</small></label><button type="button" className="boton-secundario" disabled={disabled || cargando} onClick={buscar}>Buscar equipo</button><button type="button" className="boton-secundario" disabled={disabled} onClick={() => { turno.current++; setAbierto(false); setCargando(false); }}>Cerrar</button></div>
      {error && <p className="error" role="alert">{error}</p>}
      {datos && <>{datos.cerrada && <p className="error" role="alert">La semana de destino ya está cerrada. Elige otra fecha para registrar una nueva jornada.</p>}
        <p className="repetir-nota">{datos.origen ? `Origen: ${datos.origen} → Destino: ${datos.destino}.` : "No hay jornadas anteriores con producción."} Se cargan solo trabajadores activos sin registros en la misma fecha, sector, labor y faena. No se copia producción ni se guarda nada todavía.</p>
        {hayBorrador && datos.grupos.length > 0 && <p className="aviso-perfil">Al elegir un equipo se reemplazará el borrador de este formulario. Revisa antes de continuar.</p>}
        {datos.origen && !datos.grupos.length && <p>No hay producción registrada en la fecha elegida.</p>}
        <div className="repetir-grupos">{datos.grupos.map((g, i) => <article key={i}><div><strong>{g.sector} · {g.labor}</strong><p>{g.faena ? `${g.cliente} · ${g.faena}` : "Sin faena vinculada"}</p><span>{g.trabajadores.length} personas disponibles{g.inactivos > 0 ? ` · ${g.inactivos} inactivos excluidos` : ""}{g.ya_registrados > 0 ? ` · ${g.ya_registrados} ya registrados excluidos` : ""}</span>{!g.faena_valida && <p className="repetir-advertencia">La faena anterior no está vigente para el destino. Tendrás que elegir una faena válida antes de guardar.</p>}{g.trabajadores.length > 200 && <p>Este equipo supera 200 personas. Divide el registro en equipos más pequeños.</p>}</div><button type="button" disabled={disabled || datos.cerrada || !g.trabajadores.length || g.trabajadores.length > 200} onClick={() => { onCargar(g, datos.origen); setAbierto(false); }}>{hayBorrador ? "Reemplazar borrador con este equipo" : "Cargar este equipo"}</button></article>)}</div>
      </>}
    </div>}
  </div>;
}
