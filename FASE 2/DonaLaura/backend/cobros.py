"""Cuentas por cobrar internas. No emite documentos tributarios ni mueve dinero."""
from datetime import date, datetime
from decimal import Decimal
import hashlib
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from database import conectar_bd
from pagos import calcular_total
from faenas import auditar

router = APIRouter(tags=["Cobros a clientes"])


def hoy():
    return datetime.now(ZoneInfo("America/Santiago")).date()


class Cobro(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    clave: UUID
    id_faena: int = Field(gt=0)
    fecha_acuerdo: date
    vencimiento: date
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=0)
    concepto: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def fechas(self):
        if self.fecha_acuerdo > hoy() or self.vencimiento < self.fecha_acuerdo:
            raise ValueError("El acuerdo no puede ser futuro y el vencimiento debe ser igual o posterior al acuerdo")
        return self


class AbonoCliente(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    clave: UUID
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=0)
    fecha: date
    referencia: str = Field(min_length=3, max_length=180)


class Anulacion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    motivo: str = Field(min_length=5, max_length=500)


SALDOS = """SELECT g.*,COALESCE(a.abonado,0) abonado,g.monto-COALESCE(a.abonado,0) saldo
    FROM cobros_cliente g LEFT JOIN (SELECT id_cobro,SUM(monto) abonado FROM abonos_cliente GROUP BY id_cobro) a USING(id_cobro)"""


def resumen_cobros(conexion, fecha=None):
    fecha = fecha or hoy()
    fila = conexion.execute(f"""WITH saldos AS ({SALDOS}) SELECT
        COALESCE(SUM(monto),0),COALESCE(SUM(abonado),0),COALESCE(SUM(saldo),0),
        COALESCE(SUM(saldo) FILTER(WHERE saldo>0 AND vencimiento<%s),0),
        COUNT(*) FILTER(WHERE saldo>0 AND vencimiento<%s),
        COUNT(*) FILTER(WHERE saldo>0 AND vencimiento=%s),COUNT(*) FILTER(WHERE saldo>0)
        FROM saldos WHERE estado='Vigente'""", (fecha,fecha,fecha)).fetchone()
    return dict(zip(("confirmado","recibido","saldo","saldo_vencido","vencidos","vencen_hoy","pendientes"),fila))


def cartera_por_cliente(conexion):
    filas = conexion.execute(f"""WITH saldos AS ({SALDOS}) SELECT cl.nombre,
        SUM(g.monto),SUM(g.abonado),SUM(g.saldo),MIN(g.vencimiento) FILTER(WHERE g.saldo>0)
        FROM saldos g JOIN faenas f USING(id_faena) JOIN clientes cl USING(id_cliente)
        WHERE g.estado='Vigente' GROUP BY cl.id_cliente,cl.nombre ORDER BY SUM(g.saldo) DESC""").fetchall()
    return [dict(zip(("cliente","confirmado_clp","recibido_clp","saldo_clp","primer_vencimiento_pendiente"),f)) for f in filas]


@router.get("/cobros")
def listar_cobros():
    with conectar_bd() as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        totales = resumen_cobros(c)
        resultado = c.execute(f"""WITH saldos AS ({SALDOS}) SELECT g.id_cobro AS id,g.id_faena,f.nombre AS faena,
            cl.nombre AS cliente,g.fecha_acuerdo,g.vencimiento,g.monto,g.abonado,g.saldo,g.estado,g.concepto,
            g.kilos_referencia,g.precio_referencia,g.estimado_referencia,g.motivo_anulacion
            FROM saldos g JOIN faenas f USING(id_faena) JOIN clientes cl USING(id_cliente)
            ORDER BY (g.estado='Vigente' AND g.saldo>0) DESC,g.vencimiento,g.id_cobro""")
        filas = [dict(zip([d.name for d in resultado.description],f)) for f in resultado.fetchall()]
    return {"fecha":hoy(),"totales":totales,"cobros":filas}


@router.post("/cobros",status_code=201)
def confirmar_cobro(datos: Cobro, request: Request):
    huella = hashlib.sha256(datos.model_dump_json(exclude={"clave"}).encode()).hexdigest()
    try:
        with conectar_bd() as c:
            c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(str(datos.clave),))
            previo = c.execute("SELECT id_cobro,contenido_hash FROM cobros_cliente WHERE clave=%s",(datos.clave,)).fetchone()
            if previo:
                if previo[1] != huella: raise HTTPException(409,"Esta clave de envío ya se usó con otro contenido")
                return {"id":previo[0],"mensaje":"Cobro ya confirmado; no se duplicó"}
            faena = c.execute("SELECT precio_kg FROM faenas WHERE id_faena=%s FOR UPDATE",(datos.id_faena,)).fetchone()
            if not faena: raise HTTPException(404,"Faena no encontrada")
            kilos, registros = c.execute("""SELECT COALESCE(SUM(p.cantidad_kg+COALESCE(a.kilos,0)),0),COUNT(*)
                FROM produccion p LEFT JOIN LATERAL(SELECT SUM(diferencia_kg) kilos FROM ajustes_cosecha
                    WHERE id_produccion=p.id_produccion) a ON TRUE WHERE p.id_faena=%s""",(datos.id_faena,)).fetchone()
            if not registros: raise HTTPException(422,"Registra producción vinculada a la faena antes de confirmar su cobro")
            identificador = c.execute("""INSERT INTO cobros_cliente(clave,contenido_hash,id_faena,fecha_acuerdo,vencimiento,
                monto,kilos_referencia,precio_referencia,estimado_referencia,concepto,id_usuario)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_cobro""",
                (datos.clave,huella,datos.id_faena,datos.fecha_acuerdo,datos.vencimiento,datos.monto,kilos,faena[0],calcular_total(kilos,faena[0]),datos.concepto,request.state.usuario["id"])).fetchone()[0]
            auditar(c,request,"Confirmación de cobro",f"Cobro {identificador} · faena {datos.id_faena} · CLP {datos.monto}")
        return {"id":identificador,"mensaje":"Cobro confirmado. No se emitió una factura ni se registró dinero recibido."}
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409,"Esta faena ya tiene un cobro vigente. Revisa su saldo antes de crear otro.") from error


@router.get("/cobros/{id_cobro}/abonos")
def listar_abonos(id_cobro: int):
    with conectar_bd() as c:
        if not c.execute("SELECT 1 FROM cobros_cliente WHERE id_cobro=%s",(id_cobro,)).fetchone():
            raise HTTPException(404,"Cobro no encontrado")
        filas = c.execute("""SELECT a.id_abono AS id,a.monto,a.fecha,a.referencia,u.nombre AS usuario
            FROM abonos_cliente a JOIN usuarios u USING(id_usuario) WHERE id_cobro=%s ORDER BY a.fecha DESC,a.id_abono DESC""",(id_cobro,))
        return [dict(zip([d.name for d in filas.description],f)) for f in filas.fetchall()]


@router.post("/cobros/{id_cobro}/abonos",status_code=201)
def registrar_abono(id_cobro: int, datos: AbonoCliente, request: Request):
    if datos.fecha > hoy(): raise HTTPException(422,"La fecha del abono no puede ser futura")
    try:
        with conectar_bd() as c:
            c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(str(datos.clave),))
            previo = c.execute("SELECT id_cobro,monto,fecha,referencia FROM abonos_cliente WHERE clave=%s",(datos.clave,)).fetchone()
            if previo:
                if previo != (id_cobro,datos.monto,datos.fecha,datos.referencia): raise HTTPException(409,"La clave del abono ya se utilizó con otro contenido")
                return {"mensaje":"Abono ya registrado; no se duplicó"}
            cobro = c.execute("SELECT monto,estado,fecha_acuerdo FROM cobros_cliente WHERE id_cobro=%s FOR UPDATE",(id_cobro,)).fetchone()
            if not cobro: raise HTTPException(404,"Cobro no encontrado")
            if cobro[1] != "Vigente": raise HTTPException(409,"El cobro está anulado")
            if datos.fecha < cobro[2]: raise HTTPException(422,"El abono no puede ser anterior al acuerdo del cobro")
            abonado = c.execute("SELECT COALESCE(SUM(monto),0) FROM abonos_cliente WHERE id_cobro=%s",(id_cobro,)).fetchone()[0]
            if datos.monto > cobro[0]-abonado: raise HTTPException(409,"El abono supera el saldo pendiente. Actualiza el cobro antes de continuar.")
            c.execute("""INSERT INTO abonos_cliente(clave,id_cobro,monto,fecha,referencia,id_usuario)
                VALUES (%s,%s,%s,%s,%s,%s)""",(datos.clave,id_cobro,datos.monto,datos.fecha,datos.referencia,request.state.usuario["id"]))
            auditar(c,request,"Abono recibido de cliente",f"Cobro {id_cobro} · CLP {datos.monto} · {datos.referencia}")
        return {"mensaje":"Abono registrado como recibido. La aplicación no realiza transferencias."}
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409,"Esa referencia ya está registrada en este cobro") from error


@router.post("/cobros/{id_cobro}/anular")
def anular_cobro(id_cobro: int, datos: Anulacion, request: Request):
    with conectar_bd() as c:
        cobro = c.execute("SELECT estado FROM cobros_cliente WHERE id_cobro=%s FOR UPDATE",(id_cobro,)).fetchone()
        if not cobro: raise HTTPException(404,"Cobro no encontrado")
        if cobro[0] == "Anulado": raise HTTPException(409,"El cobro ya está anulado")
        if c.execute("SELECT 1 FROM abonos_cliente WHERE id_cobro=%s",(id_cobro,)).fetchone():
            raise HTTPException(409,"No se puede anular un cobro que ya tiene abonos. Conserva sus comprobantes y revisa el caso.")
        c.execute("UPDATE cobros_cliente SET estado='Anulado',motivo_anulacion=%s WHERE id_cobro=%s",(datos.motivo,id_cobro))
        auditar(c,request,"Anulación de cobro",f"Cobro {id_cobro} · {datos.motivo}")
    return {"mensaje":"Cobro anulado con historial. No se borró ningún registro."}
