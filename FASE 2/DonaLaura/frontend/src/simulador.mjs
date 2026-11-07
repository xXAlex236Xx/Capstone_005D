// Todos los importes son supuestos netos en CLP. No registra cobros ni pagos.
export const EJEMPLO = Object.freeze({ kilos: 50000, precio: 115, tarifa: 48, dias: 15, transporte: 90000, supervision: 65000, otros: 250000, contingencia: 8, objetivo: 20 });
const limites = { kilos: [1, 1e8], precio: [0, 1e6], tarifa: [0, 1e6], dias: [1, 365], transporte: [0, 1e10], supervision: [0, 1e10], otros: [0, 1e11], contingencia: [0, 100], objetivo: [0, 90] };
export function validarSupuestos(valores) {
  return Object.entries(limites).every(([k, [min, max]]) => valores[k] !== "" && valores[k] != null && Number.isFinite(Number(valores[k])) && Number(valores[k]) >= min && Number(valores[k]) <= max && (k !== "dias" || Number.isInteger(Number(valores[k]))));
}
export function evaluarContrato(valores, factor = 1) {
  if (!validarSupuestos(valores) || !Number.isFinite(factor) || factor <= 0) return null;
  const s = Object.fromEntries(Object.keys(limites).map(k => [k, Number(valores[k])]));
  const kilos = s.kilos * factor;
  const manoObra = kilos * s.tarifa;
  const transporte = s.transporte * s.dias;
  const supervision = s.supervision * s.dias;
  const reserva = (manoObra + transporte + supervision + s.otros) * s.contingencia / 100;
  const costos = manoObra + transporte + supervision + s.otros + reserva;
  const ingreso = kilos * s.precio;
  const margen = ingreso - costos;
  const contribucionKg = s.precio - s.tarifa * (1 + s.contingencia / 100);
  const fijos = (transporte + supervision + s.otros) * (1 + s.contingencia / 100);
  return { kilos, manoObra, transporte, supervision, otros: s.otros, reserva, costos, ingreso, margen,
    porcentaje: ingreso > 0 ? margen / ingreso * 100 : null,
    precioEquilibrio: costos / kilos,
    precioObjetivo: costos / (kilos * (1 - s.objetivo / 100)),
    kilosEquilibrio: contribucionKg > 0 ? fijos / contribucionKg : contribucionKg === 0 && fijos === 0 ? 0 : null };
}
