"""Registro por jornada y correcciones con trazabilidad transaccional."""
import hashlib
from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from database import conectar_bd
from faenas import validar_faena_registro
from pagos import exigir_semana_abierta, lunes_de, bloquear_semana, calcular_total, semana_cerrada

router = APIRouter(tags=["Operación diaria"])


class FilaJornada(BaseModel):
    id_trabajador: int = Field(gt=0)
    cantidad_kg: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    horas_trabajadas: Decimal = Field(gt=0, le=24, max_digits=5, decimal_places=2)


class LoteJornada(BaseModel):
    clave: UUID
    id_jornada: int | None = Field(default=None,gt=0)
    fecha: date | None = None
    id_sector: int = Field(gt=0)
    id_labor: int = Field(gt=0)
    id_faena: int | None = Field(default=None, gt=0)
    filas: list[FilaJornada] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def una_jornada(self):
        if (self.id_jornada is None) == (self.fecha is None):
            raise ValueError("Indica una fecha o una jornada existente, no ambas")
        return self


class Correccion(BaseModel):
    cantidad_kg: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    horas_trabajadas: Decimal = Field(gt=0, le=24, max_digits=5, decimal_places=2)
    version: int = Field(gt=0)
    motivo: str = Field(min_length=5, max_length=500)


class Ajuste(BaseModel):
    clave: UUID
    diferencia_kg: Decimal = Field(max_digits=10, decimal_places=2)
    diferencia_horas: Decimal = Field(default=0, max_digits=5, decimal_places=2)
    motivo: str = Field(min_length=5, max_length=500)


def motivo_valido(motivo):
    if len(motivo.strip()) < 5:
        raise HTTPException(422, "Explica el motivo con al menos cinco caracteres")


@router.post("/produccion/jornada", status_code=201)
def guardar_jornada(lote: LoteJornada, request: Request):
    ids = [f.id_trabajador for f in lote.filas]
    if len(ids) != len(set(ids)):
        raise HTTPException(409, "Un trabajador aparece más de una vez en este lote")
    excluidos = {"clave"} if lote.id_faena is not None else {"clave", "id_faena"}
    huella = hashlib.sha256(lote.model_dump_json(exclude=excluidos).encode()).hexdigest()
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(lote.clave),))
                cursor.execute("SELECT contenido_hash,resultado FROM lotes_cosecha WHERE clave=%s", (lote.clave,))
                previo = cursor.fetchone()
                if previo:
                    if previo[0] != huella:
                        raise HTTPException(409, "La clave de envío ya se usó para otro contenido")
                    return previo[1]
                if lote.fecha is not None:
                    fecha_jornada = lote.fecha
                    exigir_semana_abierta(cursor,lote.fecha)
                    cursor.execute("INSERT INTO jornadas(fecha) VALUES (%s) ON CONFLICT(fecha) DO UPDATE SET fecha=EXCLUDED.fecha RETURNING id_jornada", (lote.fecha,))
                    id_jornada=cursor.fetchone()[0]
                else:
                    id_jornada=lote.id_jornada
                    cursor.execute("SELECT fecha FROM jornadas WHERE id_jornada=%s", (id_jornada,))
                    jornada = cursor.fetchone()
                    if not jornada:
                        raise HTTPException(404, "Jornada no encontrada")
                    exigir_semana_abierta(cursor, jornada[0])
                    fecha_jornada = jornada[0]
                validar_faena_registro(cursor, lote.id_faena, fecha_jornada)
                cursor.execute("SELECT id_trabajador FROM trabajadores WHERE id_trabajador=ANY(%s) AND estado='Activo' FOR SHARE", (ids,))
                if {f[0] for f in cursor.fetchall()} != set(ids):
                    raise HTTPException(409, "El lote contiene trabajadores inexistentes o inactivos")
                cursor.execute("SELECT 1 FROM produccion WHERE id_jornada=%s AND id_sector=%s AND id_labor=%s AND id_trabajador=ANY(%s) AND id_faena IS NOT DISTINCT FROM %s",
                               (id_jornada,lote.id_sector,lote.id_labor,ids,lote.id_faena))
                if cursor.fetchone():
                    raise HTTPException(409, "Ya hay registros para un trabajador en esta jornada, sector y labor. Revisa el historial para corregirlos.")
                creados = []
                for fila in lote.filas:
                    cursor.execute("SELECT COALESCE(SUM(horas_trabajadas),0) FROM produccion WHERE id_trabajador=%s AND id_jornada=%s", (fila.id_trabajador,id_jornada))
                    if cursor.fetchone()[0]+fila.horas_trabajadas>24: raise HTTPException(422,"Un trabajador superaría las 24 horas en la jornada; no se guardó el lote")
                    cursor.execute("INSERT INTO produccion(id_trabajador,id_jornada,id_sector,id_labor,cantidad_kg,horas_trabajadas,id_faena) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id_produccion",
                                   (fila.id_trabajador,id_jornada,lote.id_sector,lote.id_labor,fila.cantidad_kg,fila.horas_trabajadas,lote.id_faena))
                    creados.append(cursor.fetchone()[0])
                resultado = {"mensaje": "Jornada guardada completa", "registros": len(creados), "ids": creados}
                cursor.execute("INSERT INTO lotes_cosecha(clave,contenido_hash,resultado) VALUES (%s,%s,%s)", (lote.clave,huella,Jsonb(resultado)))
                cursor.execute("INSERT INTO auditoria(id_usuario,accion,detalle) VALUES (%s,'Registro de jornada',%s)", (request.state.usuario["id"],f"{len(creados)} registros · jornada {id_jornada}"))
                return resultado
    except psycopg.errors.ForeignKeyViolation as error:
        raise HTTPException(422, "El sector o la labor no existe; no se guardó ningún registro") from error


@router.get("/produccion/registros")
def registros(fecha: date | None = None):
    with conectar_bd() as conexion:
        filas = conexion.execute("""SELECT p.id_produccion,j.fecha,CONCAT(t.nombre,' ',t.apellido),s.nombre,l.nombre,
            p.cantidad_kg,p.horas_trabajadas,p.version,
            EXISTS(SELECT 1 FROM pagos g WHERE g.semana_inicio=date_trunc('week',j.fecha)::date),
            f.nombre,c.nombre,f.id_faena
            FROM produccion p JOIN jornadas j USING(id_jornada) JOIN trabajadores t USING(id_trabajador)
            JOIN sectores s USING(id_sector) JOIN labores l USING(id_labor)
            LEFT JOIN faenas f USING(id_faena) LEFT JOIN clientes c ON c.id_cliente=f.id_cliente
            WHERE (%s::date IS NULL OR j.fecha=%s) ORDER BY j.fecha DESC,p.id_produccion DESC LIMIT 200""", (fecha,fecha)).fetchall()
    claves = ("id","fecha","trabajador","sector","labor","cantidad_kg","horas_trabajadas","version","cerrada","faena","cliente","id_faena")
    return [dict(zip(claves,f)) for f in filas]


@router.get("/produccion/plantilla")
def plantilla_jornada(destino: date, origen: date | None = None):
    if origen is not None and origen >= destino:
        raise HTTPException(422, "La jornada de origen debe ser anterior a la fecha de destino")
    with conectar_bd() as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        if origen is None:
            origen = c.execute("SELECT MAX(j.fecha) FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha<%s", (destino,)).fetchone()[0]
        cerrada = c.execute("SELECT EXISTS(SELECT 1 FROM pagos WHERE semana_inicio=%s)", (lunes_de(destino),)).fetchone()[0]
        filas = c.execute("""SELECT p.id_sector,s.nombre,p.id_labor,l.nombre,p.id_faena,f.nombre,cl.nombre,
            (f.estado='Activa' AND cl.activo AND f.fecha_inicio<=%s AND (f.fecha_fin IS NULL OR f.fecha_fin>=%s)),
            t.id_trabajador,CONCAT(t.nombre,' ',t.apellido),t.estado,
            EXISTS(SELECT 1 FROM produccion pd JOIN jornadas jd USING(id_jornada) WHERE jd.fecha=%s
                AND pd.id_trabajador=p.id_trabajador AND pd.id_sector=p.id_sector AND pd.id_labor=p.id_labor
                AND pd.id_faena IS NOT DISTINCT FROM p.id_faena)
            FROM produccion p JOIN jornadas j USING(id_jornada) JOIN trabajadores t USING(id_trabajador)
            JOIN sectores s USING(id_sector) JOIN labores l USING(id_labor) LEFT JOIN faenas f USING(id_faena)
            LEFT JOIN clientes cl ON cl.id_cliente=f.id_cliente WHERE j.fecha=%s ORDER BY s.nombre,l.nombre,p.id_faena,t.nombre,t.id_trabajador""", (destino,destino,destino,origen)).fetchall()
    grupos = {}
    for sector, nombre_sector, labor, nombre_labor, faena, nombre_faena, cliente, valida, trabajador, nombre, estado, ya_registrado in filas:
        clave=(sector,labor,faena)
        if clave not in grupos:
            grupos[clave]={"id_sector":sector,"sector":nombre_sector,"id_labor":labor,"labor":nombre_labor,
                "id_faena":faena,"faena":nombre_faena,"cliente":cliente,"faena_valida":bool(valida) if faena else True,
                "trabajadores":[],"inactivos":0,"ya_registrados":0}
        grupo=grupos[clave]
        if estado != "Activo": grupo["inactivos"]+=1
        elif ya_registrado: grupo["ya_registrados"]+=1
        elif not any(t["id"]==trabajador for t in grupo["trabajadores"]): grupo["trabajadores"].append({"id":trabajador,"nombre":nombre})
    return {"origen":origen,"destino":destino,"cerrada":cerrada,"grupos":list(grupos.values())}


@router.get("/produccion/{id_produccion}/historial")
def historial(id_produccion: int):
    with conectar_bd() as conexion:
        correcciones = conexion.execute("SELECT c.id,u.nombre,c.motivo,c.antes,c.despues,c.creado_en FROM correcciones_cosecha c JOIN usuarios u USING(id_usuario) WHERE c.id_produccion=%s ORDER BY c.id DESC", (id_produccion,)).fetchall()
        ajustes = conexion.execute("SELECT a.id,u.nombre,a.motivo,a.diferencia_kg,a.diferencia_horas,a.monto,a.creado_en FROM ajustes_cosecha a JOIN usuarios u USING(id_usuario) WHERE a.id_produccion=%s ORDER BY a.id DESC", (id_produccion,)).fetchall()
    return {"correcciones": [dict(zip(("id","usuario","motivo","antes","despues","fecha"),f)) for f in correcciones],
            "ajustes": [dict(zip(("id","usuario","motivo","kilos","horas","monto","fecha"),f)) for f in ajustes]}


@router.patch("/produccion/{id_produccion}")
def corregir(id_produccion: int, datos: Correccion, request: Request):
    motivo_valido(datos.motivo)
    with conectar_bd() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT j.fecha,p.id_trabajador,p.id_jornada FROM produccion p JOIN jornadas j USING(id_jornada) WHERE p.id_produccion=%s", (id_produccion,))
            fila = cursor.fetchone()
            if not fila: raise HTTPException(404,"Registro no encontrado")
            exigir_semana_abierta(cursor, fila[0])
            cursor.execute("SELECT cantidad_kg,horas_trabajadas,version FROM produccion WHERE id_produccion=%s FOR UPDATE", (id_produccion,))
            kilos,horas,version = cursor.fetchone()
            if version != datos.version: raise HTTPException(409,"Otra persona modificó este registro. Actualiza antes de corregirlo.")
            if kilos == datos.cantidad_kg and horas == datos.horas_trabajadas: raise HTTPException(422,"No hay cambios para guardar")
            cursor.execute("SELECT COALESCE(SUM(horas_trabajadas),0) FROM produccion WHERE id_trabajador=%s AND id_jornada=%s AND id_produccion<>%s", (fila[1],fila[2],id_produccion))
            if cursor.fetchone()[0]+datos.horas_trabajadas>24: raise HTTPException(422,"La corrección superaría las 24 horas acumuladas de esa jornada")
            antes = {"cantidad_kg": str(kilos),"horas_trabajadas": str(horas),"version":version}
            despues = {"cantidad_kg": str(datos.cantidad_kg),"horas_trabajadas":str(datos.horas_trabajadas),"version":version+1}
            cursor.execute("UPDATE produccion SET cantidad_kg=%s,horas_trabajadas=%s,version=version+1 WHERE id_produccion=%s", (datos.cantidad_kg,datos.horas_trabajadas,id_produccion))
            cursor.execute("INSERT INTO correcciones_cosecha(id_produccion,id_usuario,motivo,antes,despues) VALUES (%s,%s,%s,%s,%s)", (id_produccion,request.state.usuario["id"],datos.motivo.strip(),Jsonb(antes),Jsonb(despues)))
    return {"mensaje":"Corrección guardada con historial"}


@router.post("/produccion/{id_produccion}/ajustes", status_code=201)
def ajustar(id_produccion: int, datos: Ajuste, request: Request):
    motivo_valido(datos.motivo)
    if not datos.diferencia_kg and not datos.diferencia_horas: raise HTTPException(422,"El ajuste debe cambiar kilos u horas")
    with conectar_bd() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT j.fecha,p.id_trabajador,p.cantidad_kg,p.horas_trabajadas,p.id_jornada FROM produccion p JOIN jornadas j USING(id_jornada) WHERE p.id_produccion=%s", (id_produccion,))
            fila = cursor.fetchone()
            if not fila: raise HTTPException(404,"Registro no encontrado")
            semana = lunes_de(fila[0]); bloquear_semana(cursor, semana)
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(datos.clave),))
            cursor.execute("SELECT id_produccion,diferencia_kg,diferencia_horas,motivo,monto FROM ajustes_cosecha WHERE clave=%s", (datos.clave,))
            previo=cursor.fetchone()
            if previo:
                if previo[:4] != (id_produccion,datos.diferencia_kg,datos.diferencia_horas,datos.motivo.strip()): raise HTTPException(409,"La clave de envío ya se utilizó para otro ajuste")
                return {"mensaje":"Ajuste ya registrado; no se duplicó","diferencia_monto":previo[4]}
            cursor.execute("SELECT id_pago,precio_kg,total FROM pagos WHERE semana_inicio=%s AND id_trabajador=%s FOR UPDATE", (semana,fila[1]))
            pago = cursor.fetchone()
            if not pago: raise HTTPException(409,"Los ajustes corresponden a semanas cerradas con pago registrado. En semanas abiertas utiliza Corregir.")
            cursor.execute("SELECT COALESCE(SUM(diferencia_kg),0),COALESCE(SUM(diferencia_horas),0) FROM ajustes_cosecha WHERE id_produccion=%s", (id_produccion,))
            dk,dh = cursor.fetchone()
            if fila[2]+dk+datos.diferencia_kg < 0 or not 0 < (fila[3] or 0)+dh+datos.diferencia_horas <= 24:
                raise HTTPException(422,"El ajuste dejaría kilos negativos u horas fuera del rango permitido")
            cursor.execute("""SELECT COALESCE(SUM(COALESCE(p.horas_trabajadas,0)+COALESCE(
                (SELECT SUM(a.diferencia_horas) FROM ajustes_cosecha a WHERE a.id_produccion=p.id_produccion),0)),0)
                FROM produccion p WHERE p.id_trabajador=%s AND p.id_jornada=%s""", (fila[1],fila[4]))
            if not 0 < cursor.fetchone()[0]+datos.diferencia_horas <= 24:
                raise HTTPException(422,"El ajuste superaría el rango de horas acumuladas de la jornada")
            # Redondear el total revisado, no cada diferencia por separado.
            cursor.execute("SELECT kilos FROM pagos WHERE id_pago=%s", (pago[0],)); kilos_pago=cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(SUM(diferencia_kg),0),COALESCE(SUM(monto),0) FROM ajustes_cosecha WHERE id_pago=%s", (pago[0],)); kilos_previos,monto_previo=cursor.fetchone()
            monto = calcular_total(kilos_pago+kilos_previos+datos.diferencia_kg,pago[1])-pago[2]-monto_previo
            cursor.execute("SELECT COALESCE(SUM(monto),0) FROM abonos_pago WHERE id_pago=%s", (pago[0],)); abonado=cursor.fetchone()[0]
            if pago[2]+monto_previo+monto < abonado: raise HTTPException(409,"El ajuste reduciría el total por debajo de lo ya pagado. Revisa la diferencia antes de continuar.")
            cursor.execute("INSERT INTO ajustes_cosecha(clave,id_produccion,id_pago,diferencia_kg,diferencia_horas,monto,motivo,id_usuario) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                           (datos.clave,id_produccion,pago[0],datos.diferencia_kg,datos.diferencia_horas,monto,datos.motivo.strip(),request.state.usuario["id"]))
            cursor.execute("DELETE FROM aprobaciones_pago WHERE id_pago=%s", (pago[0],))
    return {"mensaje":"Ajuste registrado por separado. Revisa y aprueba nuevamente el pago.","diferencia_monto":monto}
