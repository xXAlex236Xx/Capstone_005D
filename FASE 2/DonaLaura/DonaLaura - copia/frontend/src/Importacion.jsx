import { useEffect, useState } from "react";
import "./Importacion.css";

const API = "http://127.0.0.1:8000";
const nuevaFila = () => ({ id: crypto.randomUUID(), id_sector: "", kilos: "", horas: "" });
const numero = (valor) => Number(valor);
const formato = (valor) => Number(valor).toLocaleString("es-CL", { maximumFractionDigits: 2 });

export default function Importacion() {
  const [archivo1, setArchivo1] = useState(null);
  const [archivo2, setArchivo2] = useState(null);
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
    if (!archivo1) {
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
    const formulario = new FormData();
    formulario.append("archivo_1", archivo1);
    if (archivo2) formulario.append("archivo_2", archivo2);
    try {
      const respuesta = await fetch(`${API}/importacion/vista-previa`, {
        method: "POST",
        body: formulario
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        throw new Error(typeof datos.detail === "string" ? datos.detail : "No se pudieron leer las planillas.");
      }
      setResultado(datos);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
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
        }))
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
      }) };
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
          <label htmlFor="archivo1">Primera planilla</label>
          <input id="archivo1" type="file" accept=".xlsx" onChange={(e) => setArchivo1(e.target.files[0] ?? null)} required />
        </div>
        <div className="importacion-campo">
          <label htmlFor="archivo2">Segunda planilla (opcional)</label>
          <input id="archivo2" type="file" accept=".xlsx" onChange={(e) => setArchivo2(e.target.files[0] ?? null)} />
        </div>
        <button type="submit" disabled={cargando || guardando}>{cargando ? "Leyendo planillas..." : "Mostrar vista previa"}</button>
      </form>
      {error && <p className="importacion-error" role="alert">{error}</p>}
      {errorSectores && <p className="importacion-error" role="alert">{errorSectores}</p>}

      {resultado && (
        <>
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
              disabled={validando || registros.length === 0 || completos !== registros.length}
              onClick={validarCosechas}>
              {validando ? "Validando cosechas..." : "Validar cosechas"}
            </button>
            {completos !== registros.length && <p className="importacion-aviso">Completa todas las distribuciones para habilitar la validación.</p>}
            {errorValidacion && <p className="importacion-error" role="alert">{errorValidacion}</p>}
            {validacion && <div className="importacion-resumen" role="status" style={{ width: "100%" }}>
              <div className="importacion-indicador"><span>Validados</span><strong>{validacion.listos}</strong></div>
              <div className="importacion-indicador"><span>Para revisión</span><strong>{validacion.para_revision}</strong></div>
              <div className="importacion-indicador"><span>Con errores</span><strong>{validacion.con_errores}</strong></div>
            </div>}
            {validacion?.listos > 0 && !guardado && (
              <button type="button" className="importacion-agregar-sector"
                disabled={guardando || validando} onClick={guardarCosechas}>
                {guardando ? "Guardando..." : `Guardar ${validacion.listos} cosechas validadas`}
              </button>
            )}
            {guardado && <div className="importacion-indicador" role="status" style={{ width: "100%" }}>
              <strong>¡Guardado confirmado!</strong>
              <span>{guardado.registros_excel} registros, {guardado.filas_produccion} filas por sector y {formato(guardado.total_kilos)} kg.</span>
              <span>Vuelve a cargar las planillas para realizar otra importación.</span>
            </div>}
          </div>
          <p className="importacion-aviso">Solo se guardan los registros validados sin advertencias. Los demás quedan pendientes de revisión. El servidor vuelve a comprobar todo antes de guardar.</p>
        </>
      )}
    </section>
  );
}
