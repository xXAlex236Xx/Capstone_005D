"""Amplía SOLO la demostración identificada con cobros y abonos ficticios."""
from datetime import date, timedelta
from decimal import Decimal
import os
from types import SimpleNamespace
from uuid import UUID, uuid5

from database import conectar_bd
from demo import leer_estado, verificar_marca
from faenas import listar_faenas
from cobros import Cobro, AbonoCliente, confirmar_cobro, registrar_abono, hoy


def preparar():
    estado = leer_estado()
    if os.environ["DB_NAME"] != estado["demo"]:
        raise RuntimeError("Selecciona la demostración antes de agregar sus cobros ficticios")
    verificar_marca(estado)
    with conectar_bd() as c:
        actor = c.execute("SELECT id_usuario FROM usuarios WHERE usuario='demo.admin' AND rol='administrador'").fetchone()
        existentes = {f[0] for f in c.execute("SELECT id_faena FROM cobros_cliente").fetchall()}
    if not actor: raise RuntimeError("No se encontró el administrador de demostración")
    request = SimpleNamespace(state=SimpleNamespace(usuario={"id":actor[0]}))
    faenas = [f for f in listar_faenas() if f["registros"] and f["fecha_inicio"] <= hoy()][:18]
    cantidad = 0
    for i, f in enumerate(faenas):
        if f["id"] in existentes: continue
        acuerdo = min(f["fecha_fin"] or hoy(),hoy())
        vence = hoy() if i % 5 == 0 else acuerdo+timedelta(days=15)
        monto = Decimal(str(f["cobro_estimado"]))
        if monto <= 0: continue
        clave = uuid5(UUID(estado["identificador"]),f"cobro-faena-{f['id']}")
        r = confirmar_cobro(Cobro(clave=clave,id_faena=f["id"],fecha_acuerdo=acuerdo,vencimiento=vence,
            monto=monto,concepto="SIMULADO · Acuerdo de cobro por cosecha [DEMO]"),request)
        if i % 4 in (0,1):
            recibido = monto if i % 4 == 0 else (monto / 2).quantize(Decimal(1))
            registrar_abono(r["id"],AbonoCliente(clave=uuid5(clave,"abono"),monto=recibido,
                fecha=max(acuerdo,hoy()-timedelta(days=3)),referencia=f"DEMO-CLIENTE-{f['id']}"),request)
        cantidad += 1
    print(f"Demostración ampliada: {cantidad} cobros ficticios. No se modificó la base original.")


if __name__ == "__main__":
    preparar()
