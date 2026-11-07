import test from "node:test";
import assert from "node:assert/strict";
import { EJEMPLO, evaluarContrato } from "./simulador.mjs";

test("contrato incluye costos diarios, variables y reserva", () => {
  const r = evaluarContrato(EJEMPLO);
  assert.equal(r.ingreso, 5750000);
  assert.equal(r.costos, 5373000);
  assert.equal(r.margen, 377000);
  assert.equal(r.precioObjetivo, 134.325);
});
test("menor volumen mantiene costos fijos y cambia pago variable", () => {
  const r = evaluarContrato(EJEMPLO, .8);
  assert.equal(r.manoObra, 1920000);
  assert.equal(r.transporte, 1350000);
  assert.equal(r.costos, 4854600);
  assert.equal(r.margen, -254600);
});
test("precio objetivo alcanza margen sobre ventas, no recargo sobre costos", () => {
  const r = evaluarContrato(EJEMPLO, .8);
  const ajustado = evaluarContrato({ ...EJEMPLO, precio: r.precioObjetivo }, .8);
  assert.ok(Math.abs(ajustado.porcentaje - 20) < 1e-9);
});
test("volumen de equilibrio deja margen cero", () => {
  const r = evaluarContrato(EJEMPLO);
  const equilibrio = evaluarContrato(EJEMPLO, r.kilosEquilibrio / EJEMPLO.kilos);
  assert.ok(Math.abs(equilibrio.margen) < 1e-7);
});
test("precio menor al costo variable no tiene volumen de equilibrio", () => {
  const r = evaluarContrato({ ...EJEMPLO, precio: 10 });
  assert.equal(r.kilosEquilibrio, null);
});
test("sin ventas no inventa porcentaje de margen", () => {
  assert.equal(evaluarContrato({ ...EJEMPLO, precio: 0 }).porcentaje, null);
});
test("sin ingresos ni costos el equilibrio es cero, sin inventar margen porcentual", () => {
  const r = evaluarContrato({ ...EJEMPLO, precio: 0, tarifa: 0, transporte: 0, supervision: 0, otros: 0 });
  assert.equal(r.kilosEquilibrio, 0);
  assert.equal(r.porcentaje, null);
  assert.equal(r.margen, 0);
});
test("entradas incompletas o fuera de rango no producen estimaciones", () => {
  for (const cambio of [{ kilos: "" }, { kilos: 0 }, { transporte: -1 }, { dias: 1.5 }, { objetivo: 100 }, { precio: Infinity }, { tarifa: null }]) {
    assert.equal(evaluarContrato({ ...EJEMPLO, ...cambio }), null);
  }
});
