import { useEffect, useState } from "react";

import { API as API_URL, apiFetch as fetch } from "./api";

const formularioVacio = {
  nombre: "",
  apellido: "",
  rut: ""
};

function Trabajadores({ usuario }) {
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [estado, setEstado] = useState("Todos");
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
      setError("No se pudo cargar la lista. Comprueba la conexión con el sistema.");
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
    setMostrarFormulario(true);
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
    setMostrarFormulario(false);
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
      setMostrarFormulario(false);

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

  const filtrados = trabajadores.filter(t =>
    (estado === "Todos" || t.estado === estado) &&
    `${t.nombre} ${t.apellido} ${t.rut || ""}`.toLocaleLowerCase("es").includes(busqueda.toLocaleLowerCase("es"))
  );
  return (
    <>
      <div className="page-heading"><div><span className="eyebrow">EQUIPO DE TRABAJO</span><h1>Trabajadores</h1><p>Administra el personal y mantén sus datos al día.</p></div>{usuario?.rol !== "consulta" && !mostrarFormulario && <button onClick={() => { cancelarEdicion(); setMostrarFormulario(true); }}>+ Agregar trabajador</button>}</div>
      {mensaje && <p className="mensaje" role="status">{mensaje}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {/* FORMULARIO */}
      {mostrarFormulario && <section className="formulario-seccion">
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

            {mostrarFormulario && (
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

      </section>}

      {/* TABLA DE TRABAJADORES */}
      <section className="trabajadores-seccion panel">
        <div className="tabla-toolbar"><label className="campo">Buscar trabajador<input type="search" placeholder="Nombre, apellido o RUT" value={busqueda} onChange={e => setBusqueda(e.target.value)} /></label><label className="campo">Estado<select value={estado} onChange={e => setEstado(e.target.value)}><option>Todos</option><option>Activo</option><option>Inactivo</option></select></label><span>{filtrados.length} de {trabajadores.length} trabajadores</span></div>

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
                {filtrados.map((trabajador) => (
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

            {filtrados.length === 0 && (
              <p className="empty-table">No hay trabajadores que coincidan con esta búsqueda.</p>
            )}
          </div>
        )}
      </section>
    </>
  );
}

export default Trabajadores;
