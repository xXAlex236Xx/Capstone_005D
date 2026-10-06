
import { useEffect, useState } from "react";
import "./App.css";
import Cosechas from "./Cosechas";
import Productividad from "./Productividad";
import Administracion from "./Administracion";
import Importacion from "./Importacion";
import AnalisisIA from "./AnalisisIA";
import AsistenteIA from "./AsistenteIA";
const API_URL = "http://127.0.0.1:8000";

const formularioVacio = {
  nombre: "",
  apellido: "",
  rut: ""
};

function App() {
  const [trabajadores, setTrabajadores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [desactivandoId, setDesactivandoId] = useState(null);
  const [editandoId, setEditandoId] = useState(null);

  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [formulario, setFormulario] = useState(formularioVacio);

  // CONSULTAR TRABAJADORES
  async function cargarTrabajadores() {
    try {
      const respuesta = await fetch(`${API_URL}/trabajadores`);

      if (!respuesta.ok) {
        throw new Error("No se pudieron obtener los trabajadores");
      }

      const datos = await respuesta.json();
      setTrabajadores(datos);
      return true;
    } catch {
      setError("No se pudo cargar la lista. Comprueba que FastAPI esté funcionando.");
      return false;
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    cargarTrabajadores();
  }, []);

  // ACTUALIZAR LOS CAMPOS DEL FORMULARIO
  function actualizarFormulario(evento) {
    const { name, value } = evento.target;

    setFormulario((anterior) => ({
      ...anterior,
      [name]: value
    }));
  }

  // PREPARAR EL FORMULARIO PARA EDITAR
  function editarTrabajador(trabajador) {
    setEditandoId(trabajador.id);

    setFormulario({
      nombre: trabajador.nombre,
      apellido: trabajador.apellido,
      rut: trabajador.rut || ""
    });

    setError("");
    setMensaje("");

    window.scrollTo({
      top: 0,
      behavior: "smooth"
    });
  }

  // CANCELAR LA EDICIÓN
  function cancelarEdicion() {
    setEditandoId(null);
    setFormulario(formularioVacio);
    setError("");
    setMensaje("");
  }

  // REGISTRAR O ACTUALIZAR UN TRABAJADOR
  async function guardarTrabajador(evento) {
    evento.preventDefault();

    if (guardando) return;

    setGuardando(true);
    setError("");
    setMensaje("");

    const esEdicion = editandoId !== null;

    const url = esEdicion
      ? `${API_URL}/trabajadores/${editandoId}`
      : `${API_URL}/trabajadores`;

    try {
      const respuesta = await fetch(url, {
        method: esEdicion ? "PUT" : "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          nombre: formulario.nombre.trim(),
          apellido: formulario.apellido.trim(),
          rut: formulario.rut.trim() || null
        })
      });

      if (!respuesta.ok) {
        const datosError = await respuesta.json();

        throw new Error(
          typeof datosError.detail === "string"
            ? datosError.detail
            : "No se pudo guardar el trabajador"
        );
      }

      setFormulario(formularioVacio);
      setEditandoId(null);

      setMensaje(
        esEdicion
          ? "¡Trabajador actualizado correctamente!"
          : "¡Trabajador registrado correctamente!"
      );

      await cargarTrabajadores();

    } catch (errorCapturado) {
      setError(errorCapturado.message);
    } finally {
      setGuardando(false);
    }
  }

  // DESACTIVAR UN TRABAJADOR
  async function desactivarTrabajador(trabajador) {
    if (desactivandoId !== null) return;

    const confirmado = window.confirm(
      `¿Quieres desactivar a ${trabajador.nombre} ${trabajador.apellido}?`
    );

    if (!confirmado) return;

    setDesactivandoId(trabajador.id);
    setError("");
    setMensaje("");

    try {
      const respuesta = await fetch(
        `${API_URL}/trabajadores/${trabajador.id}/desactivar`,
        {
          method: "PATCH"
        }
      );

      if (!respuesta.ok) {
        const datosError = await respuesta.json();

        throw new Error(
          typeof datosError.detail === "string"
            ? datosError.detail
            : "No se pudo desactivar al trabajador"
        );
      }

      setMensaje("¡Trabajador desactivado correctamente!");

      await cargarTrabajadores();

    } catch (errorCapturado) {
      setError(errorCapturado.message);
    } finally {
      setDesactivandoId(null);
    }
  }

  return (
    <div className="contenedor">
      <header>
        <h1>🌱 Doña Laura</h1>
        <p>Sistema de Gestión Administrativa Agrícola</p>
      </header>

      <main>
        {/* FORMULARIO */}
        <section className="formulario-seccion">
          <h2>
            {editandoId !== null
              ? "Editar trabajador"
              : "Registrar trabajador"}
          </h2>

          <p>
            {editandoId !== null
              ? "Modifica los datos y guarda los cambios."
              : "Ingresa los datos del nuevo trabajador."}
          </p>

          <form onSubmit={guardarTrabajador}>
            <div className="campos">
              <div className="campo">
                <label htmlFor="nombre">Nombre</label>
                <input
                  id="nombre"
                  name="nombre"
                  value={formulario.nombre}
                  onChange={actualizarFormulario}
                  maxLength={100}
                  required
                  placeholder="Ej.: Carlos"
                />
              </div>

              <div className="campo">
                <label htmlFor="apellido">Apellido</label>
                <input
                  id="apellido"
                  name="apellido"
                  value={formulario.apellido}
                  onChange={actualizarFormulario}
                  maxLength={100}
                  required
                  placeholder="Ej.: Muñoz"
                />
              </div>

              <div className="campo">
                <label htmlFor="rut">RUT (opcional)</label>
                <input
                  id="rut"
                  name="rut"
                  value={formulario.rut}
                  onChange={actualizarFormulario}
                  maxLength={12}
                  placeholder="Ej.: 12345678-9"
                />
              </div>
            </div>

            <div className="botones-formulario">
              <button type="submit" disabled={guardando}>
                {guardando
                  ? "Guardando..."
                  : editandoId !== null
                    ? "Guardar cambios"
                    : "Registrar trabajador"}
              </button>

              {editandoId !== null && (
                <button
                  type="button"
                  className="boton-cancelar"
                  onClick={cancelarEdicion}
                  disabled={guardando}
                >
                  Cancelar
                </button>
              )}
            </div>
          </form>

          {mensaje && <p className="mensaje">{mensaje}</p>}
          {error && <p className="error">{error}</p>}
        </section>

        {/* TABLA DE TRABAJADORES */}
        <section className="trabajadores-seccion">
          <h2>Gestión de trabajadores</h2>
          <p>Trabajadores registrados en el sistema.</p>

          {cargando ? (
            <p>Cargando trabajadores...</p>
          ) : (
            <div className="tabla-contenedor">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Nombre</th>
                    <th>Apellido</th>
                    <th>RUT</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>

                <tbody>
                  {trabajadores.map((trabajador) => (
                    <tr key={trabajador.id}>
                      <td>{trabajador.id}</td>
                      <td>{trabajador.nombre}</td>
                      <td>{trabajador.apellido}</td>
                      <td>{trabajador.rut || "Sin registrar"}</td>

                      <td>
                        <span
                          className={
                            trabajador.estado === "Activo"
                              ? "activo"
                              : "inactivo"
                          }
                        >
                          {trabajador.estado}
                        </span>
                      </td>

                      <td>
                        <div className="acciones">
                          <button
                            type="button"
                            className="boton-editar"
                            onClick={() => editarTrabajador(trabajador)}
                            disabled={guardando}
                          >
                            Editar
                          </button>

                          <button
                            type="button"
                            className="boton-desactivar"
                            onClick={() => desactivarTrabajador(trabajador)}
                            disabled={
                              trabajador.estado === "Inactivo" ||
                              desactivandoId !== null
                            }
                          >
                            {desactivandoId === trabajador.id
                              ? "Desactivando..."
                              : "Desactivar"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {trabajadores.length === 0 && (
                <p>No hay trabajadores registrados.</p>
              )}
            </div>
          )}
        </section>
        <Cosechas />
        <Productividad />
        <AsistenteIA />
        <AnalisisIA />
        <Administracion />
        <Importacion />
      </main>
    </div>
  );
}

export default App;