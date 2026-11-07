export const API = import.meta.env.VITE_API_URL || "/api";

export async function apiFetch(url, opciones = {}) {
  const respuesta = await window.fetch(url, { ...opciones, credentials: "include" });
  if (respuesta.status === 401 && !String(url).includes("/auth/")) {
    window.dispatchEvent(new Event("sesion-vencida"));
  }
  return respuesta;
}

export async function solicitar(ruta, opciones = {}) {
  let respuesta;
  try { respuesta = await apiFetch(`${API}${ruta}`, opciones); }
  catch { throw new Error("No se pudo conectar con el sistema. Comprueba que esté iniciado."); }
  const datos = await respuesta.json().catch(() => null);
  if (!datos) throw new Error("El servicio no está disponible en este momento. Intenta nuevamente.");
  if (!respuesta.ok) throw new Error(typeof datos.detail === "string" ? datos.detail : "No se pudo completar la operación");
  return datos;
}

export function enviarJSON(metodo, datos) {
  return { method: metodo, headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) };
}
