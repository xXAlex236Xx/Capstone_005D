from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from database import conectar_bd
from pagos import bloquear_semana

router = APIRouter(tags=["Seguimiento de pagos"])


@router.get("/seguimiento-pagos")
def listar():
    with conectar_bd() as conexion:
        filas = conexion.execute("""SELECT g.id_pago,g.semana_inicio,CONCAT(t.nombre,' ',t.apellido),g.total,
            COALESCE((SELECT SUM(a.monto) FROM ajustes_cosecha a WHERE a.id_pago=g.id_pago),0),
            COALESCE((SELECT SUM(b.monto) FROM abonos_pago b WHERE b.id_pago=g.id_pago),0),
            EXISTS(SELECT 1 FROM aprobaciones_pago ap WHERE ap.id_pago=g.id_pago)
            FROM pagos g JOIN trabajadores t USING(id_trabajador) ORDER BY g.semana_inicio DESC,t.nombre LIMIT 500""").fetchall()
    resultado=[]
    for id_pago,semana,nombre,total,ajustes,abonado,aprobado in filas:
        saldo=total+ajustes-abonado
        resultado.append({"id":id_pago,"semana":semana,"trabajador":nombre,"original":total,"ajustes":ajustes,
                          "total":total+ajustes,"abonado":abonado,"saldo":saldo,
                          "estado":"Pagado" if saldo==0 else "Pago parcial" if abonado else "Aprobado" if aprobado else "Calculado", "aprobado":aprobado})
    return resultado


def bloquear_pago(cursor, id_pago):
    cursor.execute("SELECT semana_inicio FROM pagos WHERE id_pago=%s", (id_pago,)); fila=cursor.fetchone()
    if not fila: raise HTTPException(404,"Pago no encontrado")
    bloquear_semana(cursor,fila[0])
    cursor.execute("SELECT total FROM pagos WHERE id_pago=%s FOR UPDATE", (id_pago,))
    return cursor.fetchone()[0]


@router.post("/seguimiento-pagos/{id_pago}/aprobar")
def aprobar(id_pago:int,request:Request):
    with conectar_bd() as conexion:
        with conexion.cursor() as cursor:
            bloquear_pago(cursor,id_pago)
            cursor.execute("INSERT INTO aprobaciones_pago(id_pago,id_usuario) VALUES (%s,%s) ON CONFLICT(id_pago) DO NOTHING", (id_pago,request.state.usuario["id"]))
    return {"mensaje":"Pago aprobado para registro de abonos"}


class Abono(BaseModel):
    clave: UUID
    monto: Decimal = Field(gt=0,max_digits=14,decimal_places=0)
    fecha: date
    comprobante: str = Field(min_length=3,max_length=180)


@router.post("/seguimiento-pagos/{id_pago}/abonos",status_code=201)
def abonar(id_pago:int,datos:Abono,request:Request):
    if len(datos.comprobante.strip())<3: raise HTTPException(422,"Indica el número o referencia del comprobante")
    if datos.fecha > datetime.now(ZoneInfo("America/Santiago")).date(): raise HTTPException(422,"Un abono informado no puede tener una fecha futura")
    with conectar_bd() as conexion:
        with conexion.cursor() as cursor:
            total=bloquear_pago(cursor,id_pago)
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(datos.clave),))
            cursor.execute("SELECT id_pago,monto,fecha,comprobante FROM abonos_pago WHERE clave=%s", (datos.clave,))
            previo=cursor.fetchone()
            if previo:
                if previo != (id_pago,datos.monto,datos.fecha,datos.comprobante.strip()): raise HTTPException(409,"La clave del comprobante ya se utilizó para otro abono")
                return {"mensaje":"Abono ya registrado; no se duplicó"}
            cursor.execute("SELECT 1 FROM abonos_pago WHERE id_pago=%s AND comprobante=%s", (id_pago,datos.comprobante.strip()))
            if cursor.fetchone(): raise HTTPException(409,"Esa referencia ya está registrada en este pago. Revisa los comprobantes antes de continuar.")
            cursor.execute("SELECT 1 FROM aprobaciones_pago WHERE id_pago=%s", (id_pago,))
            if not cursor.fetchone(): raise HTTPException(409,"Aprueba el pago antes de registrar un abono")
            cursor.execute("SELECT COALESCE(SUM(monto),0) FROM ajustes_cosecha WHERE id_pago=%s", (id_pago,)); total+=cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(SUM(monto),0) FROM abonos_pago WHERE id_pago=%s", (id_pago,)); pagado=cursor.fetchone()[0]
            if datos.monto>total-pagado: raise HTTPException(409,"El abono supera el saldo pendiente")
            cursor.execute("INSERT INTO abonos_pago(clave,id_pago,monto,fecha,comprobante,id_usuario) VALUES (%s,%s,%s,%s,%s,%s)", (datos.clave,id_pago,datos.monto,datos.fecha,datos.comprobante.strip(),request.state.usuario["id"]))
    return {"mensaje":"Abono registrado. No se realizó ninguna transferencia bancaria."}


@router.get("/seguimiento-pagos/{id_pago}/abonos")
def abonos(id_pago:int):
    with conectar_bd() as conexion:
        filas=conexion.execute("SELECT b.id,b.monto,b.fecha,b.comprobante,u.nombre FROM abonos_pago b JOIN usuarios u USING(id_usuario) WHERE id_pago=%s ORDER BY b.id DESC", (id_pago,)).fetchall()
    return [dict(zip(("id","monto","fecha","comprobante","usuario"),f)) for f in filas]
