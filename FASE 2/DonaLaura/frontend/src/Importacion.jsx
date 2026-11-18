import { useEffect, useState } from "react";
import "./Importacion.css";

import { API, apiFetch as fetch } from "./api";
const nuevaFila = () => ({ id: crypto.randomUUID(), id_sector: "", kilos: "", horas: "" });
const numero = (valor) => Number(valor);
const formato = (valor) => Number(valor).toLocaleString("es-CL", { maximumFractionDigits: 2 });

export default function Importacion({ usuario }) {
  const [archivos, setArchivos] = useState([]);
  const [plan, setPlan] = useState(null);
  const [decisiones, setDecisiones] = useState({});
  const [omitidos, setOmitidos] = useState([]);
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [soloRevision, setSoloRevision] = useState(false);
  const [sectores, setSectores] = useState([]);
  const [errorSectores, setErrorSectores] = useState("");
  const [distribuciones, setDistribuciones] = useState({});
  const [validando, setValidando] = useState(false);
  const [validacion, setValidacion] = useState(null);
  const [errorValidacion, setErrorValidacion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [guardado, setGuardado] = useState(null);

  useEffect(() => {
    async function cargarSectores() {
      try {
        const respuesta = await fetch(`${API}/sectores`);
        if (!respuesta.ok) throw new Error("No se pudieron cargar los sectores.");
        const datos = await respuesta.json();
        const lista = Array.isArray(datos) ? datos : datos.sectores ?? [];
        if (!Array.isArray(lista)) throw new Error("El formato de los sectores no es válido.");
        setSectores(lista);
      } catch (err) {
        setErrorSectores(err.message);
      }
    }
    cargarSectores();
  }, []);

  async function procesarArchivos(evento) {
    evento.preventDefault();
    if (!archivos.length) {
      setError("Selecciona al menos una planilla.");
      return;
    }
    setCargando(true);
    setError("");
    setResultado(null);
    setValidacion(null);
    setGuardado(null);
    setErrorValidacion("");
    setDistribuciones({});
    setSoloRevision(false);
    setPlan(null);
    setDecisiones({});
    setOmitidos([]);
    const formulario = new FormData();
    archivos.forEach((archivo) => formulario.append("archivos", archivo));
    try {
      const respuesta = await fetch(`${API}/importacion/vista-previa`, {
        method: "POST",
        body: formulario
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        throw new Error(typeof datos.detail === "string" ? datos.detail : "No se pudieron leer las planillas.");
      }
      setOmitidos(datos.archivos_omitidos ?? []);
      await analizarPlan(datos);
      setResultado(datos);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }

  // Averigua qué hay que crear antes de guardar y qué nombres conviene confirmar.
  async function analizarPlan(datos) {
    const respuesta = await fetch(`${API}/importacion/analizar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        registros: datos.registros.map((r) => ({ trabajador: r.trabajador, fecha: r.fecha, labor: r.labor || "Cosecha" }))
      })
    });
    const analisis = await respuesta.json();
    if (!respuesta.ok) {
      throw new Error(typeof analisis.detail === "string" ? analisis.detail : "No se pudieron analizar las planillas.");
    }
    setPlan(analisis);
    // Los nombres que no se parecen a nadie se crean solos; los dudosos esperan respuesta.
    const iniciales = {};
    analisis.trabajadores.forEach((t) => { if (t.estado === "nuevo") iniciales[t.nombre] = { crear: true }; });
    setDecisiones(iniciales);
  }

  function responder(nombre, valor) {
    setValidacion(null);
    setGuardado(null);
    setErrorValidacion("");
    setDecisiones((previo) => {
      const copia = { ...previo };
      if (valor === "") delete copia[nombre];
      else if (valor === "nuevo") copia[nombre] = { crear: true };
      else if (valor.startsWith("base:")) copia[nombre] = { id_trabajador: Number(valor.slice(5)) };
      else if (valor.startsWith("planilla:")) copia[nombre] = { igual_a: valor.slice(9) };
      return copia;
    });
  }

  function valorDe(nombre) {
    const d = decisiones[nombre];
    if (!d) return "";
    if (d.crear) return "nuevo";
    if (d.id_trabajador) return `base:${d.id_trabajador}`;
    return `planilla:${d.igual_a}`;
  }

  function filasDe(indice) {
    return distribuciones[indice] ?? [];
  }

  function agregarSector(indice) {
    setValidacion(null);
    setGuardado(null);
    setErrorValidacion("");
    setDistribuciones((previo) => ({
      ...previo,
      [indice]: [...(previo[indice] ?? []), nuevaFila()]
    }));
  }

  function modificarSector(indice, idFila, campo, valor) {
    setValidacion(null);
    setGuardado(null);
    setErrorValidacion("");
    setDistribuciones((previo) => ({
      ...previo,
      [indice]: (previo[indice] ?? []).map((fila) =>
        fila.id === idFila ? { ...fila, [campo]: valor } : fila
      )
    }));
  }

  function quitarSector(indice, idFila) {
    setValidacion(null);
    setGuardado(null);
    setErrorValidacion("");
    setDistribuciones((previo) => ({
      ...previo,
      [indice]: (previo[indice] ?? []).filter((fila) => fila.id !== idFila)
    }));
  }

  function estadoDistribucion(registro, filas) {
    if (!filas.length) return { texto: "Pendiente de distribución", valido: false };
    if (filas.some((fila) => !fila.id_sector || fila.kilos === "" || fila.horas === "" || !Number.isFinite(numero(fila.kilos)) || !Number.isFinite(numero(fila.horas)) || numero(fila.kilos) <= 0 || numero(fila.horas) <= 0 || numero(fila.horas) > 24)) {
      return { texto: "Completa los sectores, kilos y horas (máximo 24 h por fila)", valido: false };
    }
    if (new Set(filas.map((fila) => fila.id_sector)).size !== filas.length) {
      return { texto: "Un sector aparece dos veces; reúne sus kilos y horas", valido: false };
    }
    const totalKilos = filas.reduce((suma, fila) => suma + numero(fila.kilos), 0);
    if (Math.abs(totalKilos - numero(registro.kilos)) > 0.005) {
      return { texto: `Diferencia: ${formato(numero(registro.kilos) - totalKilos)} kg`, valido: false };
    }
    const totalHoras = filas.reduce((suma, fila) => suma + numero(fila.horas), 0);
    if (totalHoras > 24) return { texto: "Las horas del día superan 24", valido: false };
    return { texto: "Distribución completa", valido: true };
  }

  async function validarCosechas() {
    if (!resultado?.registros?.length) return;
    const pendientes = resultado.registros.filter(
      (registro, indice) => !estadoDistribucion(registro, filasDe(indice)).valido
    );
    if (pendientes.length) {
      setErrorValidacion(`Completa primero las distribuciones pendientes (${pendientes.length} registros).`);
      setValidacion(null);
    setGuardado(null);
      return;
    }

    setValidando(true);
    setErrorValidacion("");
    setValidacion(null);
    setGuardado(null);
    try {
      const lote = {
        registros: resultado.registros.map((registro, indice) => ({
          trabajador: registro.trabajador,
          fecha: registro.fecha,
          kilos: registro.kilos,
          labor: registro.labor || "Cosecha",
          requiere_revision: Boolean(registro.requiere_revision),
          sectores: filasDe(indice).map((fila) => ({
            id_sector: Number(fila.id_sector),
            kilos: Number(fila.kilos),
            horas: Number(fila.horas)
          }))
        })),
        decisiones,
        crear_faltantes: true
      };
      const respuesta = await fetch(`${API}/importacion/validar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lote)
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        const detalle = datos.detail;
        throw new Error(typeof detalle === "string"
          ? detalle
          : "No se pudo validar el lote. Revisa los datos enviados.");
      }
      setValidacion(datos);
    } catch (err) {
      setErrorValidacion(err.message || "No se pudo conectar con el servidor.");
    } finally {
      setValidando(false);
    }
  }

  async function guardarCosechas() {
    const indicesListos = (validacion?.resultados ?? [])
      .filter((r) => r.estado === "listo")
      .map((r) => r.indice);
    if (!indicesListos.length || guardando || guardado) return;
    const kilos = indicesListos.reduce((suma, i) => suma + Number(resultado.registros[i].kilos), 0);
    if (!window.confirm(`¿Guardar ${indicesListos.length} registros validados (${formato(kilos)} kg)?\nLos registros pendientes o con errores NO se guardarán.`)) return;
    setGuardando(true);
    setErrorValidacion("");
    try {
      const lote = { registros: indicesListos.map((i) => {
        const r = resultado.registros[i];
        return {
          trabajador: r.trabajador, fecha: r.fecha, kilos: r.kilos,
          labor: r.labor || "Cosecha", requiere_revision: Boolean(r.requiere_revision),
          sectores: filasDe(i).map((f) => ({
            id_sector: Number(f.id_sector), kilos: Number(f.kilos), horas: Number(f.horas)
          }))
        };
      }), decisiones, crear_faltantes: true };
      const respuesta = await fetch(`${API}/importacion/guardar`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lote)
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        const detalle = datos.detail;
        const mensaje = typeof detalle === "string" ? detalle :
          `${detalle?.mensaje || "No se pudo guardar."} ${
            (detalle?.problemas ?? []).slice(0, 3).map(p =>
              `Registro ${p.registro} (${p.trabajador}): ${p.motivos.join(", ")}`).join(" | ")}`;
        throw new Error(mensaje);
      }
      setGuardado(datos);
      // La validación anterior ya no representa el estado actual de PostgreSQL.
      setValidacion(null);
    } catch (err) {
      setErrorValidacion(err.message || "No se pudo conectar con el servidor.");
      setValidacion(null); // Volver a validar antes de intentar guardar otra vez.
    } finally {
      setGuardando(false);
    }
  }

  const preguntas = (plan?.trabajadores ?? []).filter((t) => t.estado === "pregunta");
  const sinResponder = preguntas.filter((t) => !decisiones[t.nombre]).length;
  const nuevos = (plan?.trabajadores ?? []).filter((t) => decisiones[t.nombre]?.crear).length;
  const registros = resultado?.registros ?? [];
  const visibles = registros
    .map((registro, indice) => ({ registro, indice }))
    .filter(({ registro }) => !soloRevision || registro.requiere_revision);
  const completos = registros.filter((registro, indice) => estadoDistribucion(registro, filasDe(indice)).valido).length;
  const validacionesPorIndice = new Map((validacion?.resultados ?? []).map((r) => [r.indice, r]));

  return (
    <section className="importacion">
      <div className="importacion-encabezado">
        <h2>Importación de cosechas</h2>
        <p>Carga las planillas Excel y distribuye los kilos y las horas reales entre los sectores donde trabajó cada persona.</p>
      </div>

      <form onSubmit={procesarArchivos} className="importacion-formulario">
        <div className="importacion-campo">
          <label htmlFor="archivos">Planillas Excel (puedes elegir todas las que quieras)</label>
          <input id="archivos" type="file" accept=".xlsx,.xlsm" multiple onChange={(e) => setArchivos(Array.from(e.target.files ?? []))} required />
          {archivos.length > 0 && <small>{archivos.length} {archivos.length === 1 ? "archivo seleccionado" : "archivos seleccionados"}</small>}
        </div>
        <button type="submit" disabled={cargando || guardando}>{cargando ? "Leyendo planillas..." : "Mostrar vista previa"}</button>
      </form>
      {error && <p className="importacion-error" role="alert">{error}</p>}
      {errorSectores && <p className="importacion-error" role="alert">{errorSectores}</p>}

      {resultado && (
        <>
          {omitidos.length > 0 && (
            <div className="importacion-error" role="alert">
              <strong>No se pudieron leer {omitidos.length} {omitidos.length === 1 ? "archivo" : "archivos"} (se siguió con los demás):</strong>
              {omitidos.map((o) => <p key={o.archivo} style={{ margin: "4px 0" }}>{o.archivo}: {o.motivo}</p>)}
            </div>
          )}
          {plan && (
            <div className="importacion-plan">
              <h3>Qué se va a preparar</h3>
              <p>
                Las planillas se ordenan por fecha. Al guardar, el sistema crea primero lo que falta
                (trabajadores, fechas y labores) y después registra las cosechas, todo en un solo paso:
                si algo falla, no se guarda nada.
              </p>
              <div className="importacion-resumen">
                <div className="importacion-indicador"><span>Trabajadores ya registrados</span><strong>{plan.trabajadores.filter((t) => t.estado === "reconocido").length}</strong></div>
                <div className="importacion-indicador"><span>Trabajadores nuevos</span><strong>{nuevos}</strong></div>
                <div className="importacion-indicador"><span>Fechas nuevas</span><strong>{plan.jornadas_nuevas.length}</strong></div>
                <div className="importacion-indicador"><span>Labores nuevas</span><strong>{plan.labores_nuevas.length}</strong></div>
              </div>
              {plan.labores_nuevas.length > 0 && <p>Labores que se crearán: {plan.labores_nuevas.join(", ")}.</p>}
              {preguntas.length > 0 && (
                <>
                  <h4>Confirma estos nombres ({sinResponder === 0 ? "listo" : `faltan ${sinResponder}`})</h4>
                  <p>Estos nombres se parecen a otros. Si son la misma persona, el sistema los unirá y lo recordará para las próximas importaciones.</p>
                  {preguntas.map((t) => (
                    <div className="importacion-pregunta" key={t.nombre} style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", margin: "8px 0" }}>
                      <span><strong>{t.nombre}</strong> ({t.cantidad} {t.cantidad === 1 ? "registro" : "registros"}) ¿es la misma persona que…?</span>
                      <select aria-label={`Confirmar a ${t.nombre}`} value={valorDe(t.nombre)} onChange={(e) => responder(t.nombre, e.target.value)}>
                        <option value="">Elegir…</option>
                        {t.candidatos.map((c) => c.tipo === "base"
                          ? <option key={`b${c.id_trabajador}`} value={`base:${c.id_trabajador}`}>Sí, es {c.nombre} (ya registrado)</option>
                          : <option key={`p${c.nombre}`} value={`planilla:${c.nombre}`}>Sí, es {c.nombre} (de las planillas)</option>)}
                        <option value="nuevo">No, es otra persona (crear como nuevo)</option>
                      </select>
                    </div>
                  ))}
                </>
              )}
              <details>
                <summary>Ver todos los trabajadores ({plan.trabajadores.length})</summary>
                <ul>
                  {plan.trabajadores.map((t) => (
                    <li key={t.nombre}>
                      {t.nombre}: {t.estado === "reconocido"
                        ? `ya registrado${t.coincide_con && t.coincide_con !== t.nombre ? ` como ${t.coincide_con}` : ""}`
                        : decisiones[t.nombre]?.igual_a ? `se une con ${decisiones[t.nombre].igual_a}`
                        : decisiones[t.nombre]?.id_trabajador ? "se une con un trabajador registrado"
                        : decisiones[t.nombre]?.crear ? "se creará como nuevo" : "falta confirmar"}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          )}
          <div className="importacion-resumen">
            <div className="importacion-indicador"><span>Registros encontrados</span><strong>{resultado.total_registros}</strong></div>
            <div className="importacion-indicador"><span>Kilos en las planillas</span><strong>{formato(resultado.total_kilos)} kg</strong></div>
            <div className="importacion-indicador"><span>Registros por revisar</span><strong>{resultado.registros_para_revisar}</strong></div>
            <div className="importacion-indicador"><span>Distribuciones completas</span><strong>{completos} / {registros.length}</strong></div>
          </div>
          <div className="importacion-tabla-encabezado">
            <h3>Vista previa de registros</h3>
            <label className="importacion-filtro">
              <input type="checkbox" checked={soloRevision} onChange={(e) => setSoloRevision(e.target.checked)} />
              Mostrar solo registros por revisar
            </label>
          </div>
          <div className="importacion-tabla-contenedor">
            <table className="importacion-tabla">
              <thead>
                <tr><th>Trabajador</th><th>Fecha</th><th>Kilos Excel</th><th>Labor</th><th>Distribución por sector</th><th>Estado</th><th>Archivo</th></tr>
              </thead>
              <tbody>
                {visibles.map(({ registro, indice }) => {
                  const filas = filasDe(indice);
                  const totalDistribuido = filas.reduce((suma, fila) => suma + (Number.isFinite(numero(fila.kilos)) ? numero(fila.kilos) : 0), 0);
                  const estado = estadoDistribucion(registro, filas);
                  const comprobacion = validacionesPorIndice.get(indice);
                  return (
                    <tr key={indice} className={registro.requiere_revision ? "importacion-revisar" : ""}>
                      <td>{registro.trabajador}</td>
                      <td>{registro.fecha}</td>
                      <td>{formato(registro.kilos)} kg</td>
                      <td>{registro.labor}</td>
                      <td>
                        <div className="importacion-distribuciones">
                          {filas.map((fila, numeroFila) => (
                            <div className="importacion-fila-sector" key={fila.id}>
                              <span className="importacion-numero-sector">Sector {numeroFila + 1}</span>
                              <select aria-label={`Sector ${numeroFila + 1} de ${registro.trabajador}`} value={fila.id_sector} onChange={(e) => modificarSector(indice, fila.id, "id_sector", e.target.value)}>
                                <option value="">Seleccionar sector</option>
                                {sectores.map((sector) => <option key={sector.id} value={String(sector.id)}>{sector.nombre}</option>)}
                              </select>
                              <input aria-label={`Kilos del sector ${numeroFila + 1}`} type="number" min="0.01" step="0.01" placeholder="Kilos" value={fila.kilos} onChange={(e) => modificarSector(indice, fila.id, "kilos", e.target.value)} />
                              <input aria-label={`Horas del sector ${numeroFila + 1}`} type="number" min="0.01" max="24" step="0.01" placeholder="Horas" value={fila.horas} onChange={(e) => modificarSector(indice, fila.id, "horas", e.target.value)} />
                              <button type="button" className="importacion-quitar-sector" onClick={() => quitarSector(indice, fila.id)}>Quitar</button>
                            </div>
                          ))}
                          <button type="button" className="importacion-agregar-sector" onClick={() => agregarSector(indice)}>+ Agregar sector</button>
                          {filas.length > 0 && <small>Distribuidos: {formato(totalDistribuido)} / {formato(registro.kilos)} kg</small>}
                          <small className={estado.valido ? "importacion-valido" : "importacion-pendiente"}>{estado.texto}</small>
                        </div>
                      </td>
                      <td>
                        {comprobacion ? (
                          <div>
                            <span className={`importacion-etiqueta ${comprobacion.estado === "listo" ? "correcto" : "revisar"}`}>
                              {comprobacion.estado === "listo" ? "Validado" : comprobacion.estado === "revision" ? "Revisión necesaria" : "Con errores"}
                            </span>
                            {[...(comprobacion.errores ?? []), ...(comprobacion.advertencias ?? [])].map((mensaje, i) => (
                              <p key={i} style={{ fontSize: 12, margin: "6px 0" }}>{mensaje}</p>
                            ))}
                          </div>
                        ) : registro.requiere_revision
                          ? <span className="importacion-etiqueta revisar">Revisar posible duplicado</span>
                          : <span className="importacion-etiqueta correcto">Sin coincidencias</span>}
                      </td>
                      <td>{registro.archivo}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {visibles.length === 0 && <p className="importacion-sin-registros">No hay registros que coincidan con este filtro.</p>}
          </div>
          <div style={{ marginTop: 20, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 12 }}>
            <button type="button" className="importacion-agregar-sector"
              disabled={validando || registros.length === 0 || completos !== registros.length || sinResponder > 0}
              onClick={validarCosechas}>
              {validando ? "Validando cosechas..." : "Validar cosechas"}
            </button>
            {completos !== registros.length && <p className="importacion-aviso">Completa todas las distribuciones para habilitar la validación.</p>}
            {sinResponder > 0 && <p className="importacion-aviso">Confirma los nombres de trabajadores marcados arriba para habilitar la validación.</p>}
            {errorValidacion && <p className="importacion-error" role="alert">{errorValidacion}</p>}
            {validacion && <div className="importacion-resumen" role="status" style={{ width: "100%" }}>
              <div className="importacion-indicador"><span>Validados</span><strong>{validacion.listos}</strong></div>
              <div className="importacion-indicador"><span>Para revisión</span><strong>{validacion.para_revision}</strong></div>
              <div className="importacion-indicador"><span>Con errores</span><strong>{validacion.con_errores}</strong></div>
            </div>}
            {validacion?.listos > 0 && !guardado && (
              <button type="button" className="importacion-agregar-sector"
                disabled={usuario?.rol === "consulta" || guardando || validando} onClick={guardarCosechas}>
                {guardando ? "Guardando..." : `Guardar ${validacion.listos} cosechas validadas`}
              </button>
            )}
            {guardado && <div className="importacion-indicador" role="status" style={{ width: "100%" }}>
              <strong>¡Guardado confirmado!</strong>
              <span>{guardado.registros_excel} registros, {guardado.filas_produccion} filas por sector y {formato(guardado.total_kilos)} kg.</span>
              {(guardado.trabajadores_creados > 0 || guardado.jornadas_creadas > 0 || guardado.labores_creadas > 0) && (
                <span>También se crearon {guardado.trabajadores_creados} trabajadores, {guardado.jornadas_creadas} fechas y {guardado.labores_creadas} labores.</span>
              )}
              <span>Vuelve a cargar las planillas para realizar otra importación.</span>
            </div>}
          </div>
          <p className="importacion-aviso">Solo se guardan los registros validados sin advertencias. Los demás quedan pendientes de revisión. El servidor vuelve a comprobar todo antes de guardar.</p>
        </>
      )}
    </section>
  );
}
