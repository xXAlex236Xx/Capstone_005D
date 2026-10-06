
import { useEffect, useState } from "react";
import "./Cosechas.css";

const API_URL = "http://127.0.0.1:8000";

const formularioInicial = {
  id_trabajador: "",
  id_jornada: "",
  id_sector: "",
  id_labor: "",
  cantidad_kg: "",
  horas_trabajadas: ""
};

function Cosechas() {
  const [trabajadores, setTrabajadores] = useState([]);
  const [jornadas, setJornadas] = useState([]);
  const [sectores, setSectores] = useState([]);
  const [labores, setLabores] = useState([]);

  const [formulario, setFormulario] = useState(formularioInicial);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  useEffect(() => {
    async function cargarOpciones() {
      try {
        const rutas = [
          "/trabajadores",
          "/jornadas",
          "/sectores",
          "/labores"
        ];

        const respuestas = await Promise.all(
          rutas.map((ruta) => fetch(`${API_URL}${ruta}`))
        );

        if (respuestas.some((respuesta) => !respuesta.ok)) {
          throw new Error("No se pudieron cargar las opciones.");
        }

        const datos = await Promise.all(
          respuestas.map((respuesta) => respuesta.json())
        );

        setTrabajadores(
          datos[0].filter((trabajador) => trabajador.estado === "Activo")
        );
        setJornadas(datos[1]);
        setSectores(datos[2]);
        setLabores(datos[3]);
      } catch (errorCapturado) {
        setError(errorCapturado.message);
      } finally {
        setCargando(false);
      }
    }

    cargarOpciones();
  }, []);

  function actualizarCampo(evento) {
    const { name, value } = evento.target;

    setFormulario((anterior) => ({
      ...anterior,
      [name]: value
    }));
  }

  async function registrarCosecha(evento) {
    evento.preventDefault();

    if (guardando) return;

    setGuardando(true);
    setError("");
    setMensaje("");

    try {
      const respuesta = await fetch(`${API_URL}/produccion`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          id_trabajador: Number(formulario.id_trabajador),
          id_jornada: Number(formulario.id_jornada),
          id_sector: Number(formulario.id_sector),
          id_labor: Number(formulario.id_labor),
          cantidad_kg: Number(formulario.cantidad_kg),
          horas_trabajadas: Number(formulario.horas_trabajadas)
        })
      });

      const datos = await respuesta.json();

      if (!respuesta.ok) {
        throw new Error(
          typeof datos.detail === "string"
            ? datos.detail
            : "No se pudo registrar la cosecha."
        );
      }

      setMensaje(
        `¡Cosecha registrada! Productividad: ${datos.productividad_kg_hora} kg/h`
      );

      setFormulario(formularioInicial);
    } catch (errorCapturado) {
      setError(errorCapturado.message);
    } finally {
      setGuardando(false);
    }
  }

  const kilos = Number(formulario.cantidad_kg);
  const horas = Number(formulario.horas_trabajadas);

  const productividad =
    formulario.cantidad_kg !== "" &&
    formulario.horas_trabajadas !== "" &&
    horas > 0
      ? (kilos / horas).toFixed(2)
      : null;

  const faltanOpciones =
    trabajadores.length === 0 ||
    jornadas.length === 0 ||
    sectores.length === 0 ||
    labores.length === 0;

  return (
    <section className="cosechas-seccion">
      <h2>🌿 Registro de cosechas</h2>
      <p>Registra la producción diaria de cada trabajador.</p>

      {cargando ? (
        <p>Cargando datos...</p>
      ) : (
        <>
          {faltanOpciones && (
            <p className="aviso-cosechas">
              Faltan trabajadores activos, jornadas, sectores o labores.
              Revisa los datos disponibles en FastAPI.
            </p>
          )}

          <form onSubmit={registrarCosecha}>
            <div className="campos-cosechas">
              <div className="campo">
                <label htmlFor="cosecha-trabajador">Trabajador</label>
                <select
                  id="cosecha-trabajador"
                  name="id_trabajador"
                  value={formulario.id_trabajador}
                  onChange={actualizarCampo}
                  required
                >
                  <option value="">Selecciona un trabajador</option>

                  {trabajadores.map((trabajador) => (
                    <option key={trabajador.id} value={trabajador.id}>
                      {trabajador.nombre} {trabajador.apellido}
                    </option>
                  ))}
                </select>
              </div>

              <div className="campo">
                <label htmlFor="cosecha-jornada">Jornada</label>
                <select
                  id="cosecha-jornada"
                  name="id_jornada"
                  value={formulario.id_jornada}
                  onChange={actualizarCampo}
                  required
                >
                  <option value="">Selecciona una fecha</option>

                  {jornadas.map((jornada) => (
                    <option key={jornada.id} value={jornada.id}>
                      {jornada.fecha}
                    </option>
                  ))}
                </select>
              </div>

              <div className="campo">
                <label htmlFor="cosecha-sector">Sector</label>
                <select
                  id="cosecha-sector"
                  name="id_sector"
                  value={formulario.id_sector}
                  onChange={actualizarCampo}
                  required
                >
                  <option value="">Selecciona un sector</option>

                  {sectores.map((sector) => (
                    <option key={sector.id} value={sector.id}>
                      {sector.nombre}
                    </option>
                  ))}
                </select>
              </div>

              <div className="campo">
                <label htmlFor="cosecha-labor">Labor</label>
                <select
                  id="cosecha-labor"
                  name="id_labor"
                  value={formulario.id_labor}
                  onChange={actualizarCampo}
                  required
                >
                  <option value="">Selecciona una labor</option>

                  {labores.map((labor) => (
                    <option key={labor.id} value={labor.id}>
                      {labor.nombre}
                    </option>
                  ))}
                </select>
              </div>

              <div className="campo">
                <label htmlFor="cosecha-kilos">Kilos cosechados</label>
                <input
                  id="cosecha-kilos"
                  name="cantidad_kg"
                  type="number"
                  min="0"
                  step="0.01"
                  value={formulario.cantidad_kg}
                  onChange={actualizarCampo}
                  placeholder="Ej.: 280"
                  required
                />
              </div>

              <div className="campo">
                <label htmlFor="cosecha-horas">Horas trabajadas</label>
                <input
                  id="cosecha-horas"
                  name="horas_trabajadas"
                  type="number"
                  min="0.01"
                  max="24"
                  step="0.01"
                  value={formulario.horas_trabajadas}
                  onChange={actualizarCampo}
                  placeholder="Ej.: 8"
                  required
                />
              </div>
            </div>

            {productividad !== null && (
              <div className="resultado-cosecha">
                <span>Productividad estimada</span>
                <strong>{productividad} kg/h</strong>
              </div>
            )}

            <button
              type="submit"
              disabled={guardando || faltanOpciones}
            >
              {guardando ? "Guardando..." : "Registrar cosecha"}
            </button>
          </form>

          {mensaje && <p className="mensaje">{mensaje}</p>}
          {error && <p className="error">{error}</p>}
        </>
      )}
    </section>
  );
}

export default Cosechas;