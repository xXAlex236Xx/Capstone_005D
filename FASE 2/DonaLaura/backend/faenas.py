"""Clientes y servicios agrícolas por kilo, sin emitir facturas ni registrar cobros."""
from datetime import date
from decimal import Decimal
from typing import Literal

import psycopg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from database import conectar_bd
from pagos import calcular_total

router = APIRouter(tags=["Clientes y faenas"])


class Cliente(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    nombre: str = Field(min_length=2, max_length=160)
    contacto: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=180)
    telefono: str = Field(default="", max_length=40)
    notas: str = Field(default="", max_length=1000)
    activo: bool = True

    @field_validator("email")
    @classmethod
    def correo_valido(cls, valor):
        if valor and (valor.count("@") != 1 or any(c.isspace() for c in valor)
                      or not all(valor.split("@")) or "." not in valor.split("@")[1]):
            raise ValueError("Indica un correo válido o deja el campo vacío")
        return valor


class ClienteEditar(Cliente):
    version: int = Field(gt=0)


class Faena(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    id_cliente: int = Field(gt=0)
    nombre: str = Field(min_length=2, max_length=160)
    predio: str = Field(min_length=2, max_length=160)
    cultivo: str = Field(default="", max_length=100)
    fecha_inicio: date
    fecha_fin: date | None = None
    precio_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    estado: Literal["Planificada", "Activa", "Finalizada"] = "Planificada"
    notas: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def fechas_validas(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha final no puede ser anterior al inicio")
        return self


class FaenaEditar(Faena):
    version: int = Field(gt=0)


def auditar(cursor, request, accion, detalle):
    cursor.execute("INSERT INTO auditoria(id_usuario,accion,detalle) VALUES (%s,%s,%s)",
                   (request.state.usuario["id"], accion, detalle[:250]))


@router.get("/clientes")
def listar_clientes():
    with conectar_bd() as conexion:
        cursor = conexion.execute("""SELECT c.id_cliente AS id,c.nombre,c.contacto,c.email,c.telefono,
            c.notas,c.activo,c.version,COUNT(f.id_faena) AS faenas,
            COUNT(f.id_faena) FILTER(WHERE f.estado='Activa') AS faenas_activas
            FROM clientes c LEFT JOIN faenas f USING(id_cliente)
            GROUP BY c.id_cliente ORDER BY c.activo DESC,c.nombre,c.id_cliente"""
        )
        return [dict(zip([d.name for d in cursor.description], fila)) for fila in cursor.fetchall()]


@router.post("/clientes", status_code=201)
def crear_cliente(datos: Cliente, request: Request):
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("""INSERT INTO clientes(nombre,contacto,email,telefono,notas,activo)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_cliente""",
                    (datos.nombre, datos.contacto, datos.email, datos.telefono, datos.notas, datos.activo))
                id_cliente = cursor.fetchone()[0]
                auditar(cursor, request, "Creación de cliente", f"Cliente {id_cliente}: {datos.nombre}")
        return {"id": id_cliente, "mensaje": "Cliente creado"}
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409, "Ya existe un cliente con ese nombre") from error


@router.patch("/clientes/{id_cliente}")
def editar_cliente(id_cliente: int, datos: ClienteEditar, request: Request):
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT version FROM clientes WHERE id_cliente=%s FOR UPDATE", (id_cliente,))
                fila = cursor.fetchone()
                if not fila:
                    raise HTTPException(404, "Cliente no encontrado")
                if fila[0] != datos.version:
                    raise HTTPException(409, "Otra persona modificó este cliente. Actualiza antes de guardar.")
                if not datos.activo:
                    cursor.execute("SELECT 1 FROM faenas WHERE id_cliente=%s AND estado<>'Finalizada' LIMIT 1", (id_cliente,))
                    if cursor.fetchone():
                        raise HTTPException(409, "Finaliza las faenas pendientes antes de desactivar el cliente")
                cursor.execute("""UPDATE clientes SET nombre=%s,contacto=%s,email=%s,telefono=%s,
                    notas=%s,activo=%s,version=version+1 WHERE id_cliente=%s""",
                    (datos.nombre, datos.contacto, datos.email, datos.telefono, datos.notas, datos.activo, id_cliente))
                auditar(cursor, request, "Actualización de cliente", f"Cliente {id_cliente}; activo={datos.activo}; versión {datos.version+1}")
        return {"mensaje": "Cliente actualizado"}
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409, "Ya existe otro cliente con ese nombre") from error


def exigir_cliente_activo(cursor, id_cliente):
    cursor.execute("SELECT activo FROM clientes WHERE id_cliente=%s FOR SHARE", (id_cliente,))
    fila = cursor.fetchone()
    if not fila:
        raise HTTPException(404, "Cliente no encontrado")
    if not fila[0]:
        raise HTTPException(409, "Activa el cliente antes de crear o reactivar sus faenas")


@router.post("/faenas", status_code=201)
def crear_faena(datos: Faena, request: Request):
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                exigir_cliente_activo(cursor, datos.id_cliente)
                cursor.execute("""INSERT INTO faenas(id_cliente,nombre,predio,cultivo,fecha_inicio,fecha_fin,
                    precio_kg,estado,notas) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_faena""",
                    (datos.id_cliente, datos.nombre, datos.predio, datos.cultivo, datos.fecha_inicio,
                     datos.fecha_fin, datos.precio_kg, datos.estado, datos.notas))
                id_faena = cursor.fetchone()[0]
                auditar(cursor, request, "Creación de faena", f"Faena {id_faena}; cliente {datos.id_cliente}; cobro {datos.precio_kg} CLP/kg")
        return {"id": id_faena, "mensaje": "Faena creada"}
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409, "Ya existe esa faena para el cliente y la fecha de inicio") from error


@router.patch("/faenas/{id_faena}")
def editar_faena(id_faena: int, datos: FaenaEditar, request: Request):
    try:
        with conectar_bd() as conexion:
            with conexion.cursor() as cursor:
                # Cliente primero: mismo orden que creación y desactivación.
                cursor.execute("SELECT id_cliente FROM faenas WHERE id_faena=%s", (id_faena,))
                anterior = cursor.fetchone()
                if not anterior:
                    raise HTTPException(404, "Faena no encontrada")
                for cliente in sorted({anterior[0], datos.id_cliente}):
                    cursor.execute("SELECT activo FROM clientes WHERE id_cliente=%s FOR SHARE", (cliente,))
                    c = cursor.fetchone()
                    if not c:
                        raise HTTPException(404, "Cliente no encontrado")
                    if cliente == datos.id_cliente and datos.estado != "Finalizada" and not c[0]:
                        raise HTTPException(409, "El cliente está inactivo")
                cursor.execute("""SELECT id_cliente,nombre,predio,cultivo,fecha_inicio,precio_kg,version
                    FROM faenas WHERE id_faena=%s FOR UPDATE""", (id_faena,))
                fila = cursor.fetchone()
                if fila[6] != datos.version:
                    raise HTTPException(409, "Otra persona modificó esta faena. Actualiza antes de guardar.")
                cursor.execute("""SELECT COUNT(*),MAX(j.fecha) FROM produccion p
                    JOIN jornadas j USING(id_jornada) WHERE p.id_faena=%s""", (id_faena,))
                cantidad, ultima = cursor.fetchone()
                identidad = (datos.id_cliente, datos.nombre, datos.predio, datos.cultivo, datos.fecha_inicio, datos.precio_kg)
                if cantidad and fila[:6] != identidad:
                    raise HTTPException(409, "Esta faena ya tiene producción: conserva cliente, identificación, inicio y precio. Crea otra faena para un nuevo acuerdo.")
                if ultima and datos.fecha_fin and datos.fecha_fin < ultima:
                    raise HTTPException(409, "La fecha final no puede dejar fuera cosechas ya registradas")
                cursor.execute("""UPDATE faenas SET id_cliente=%s,nombre=%s,predio=%s,cultivo=%s,
                    fecha_inicio=%s,fecha_fin=%s,precio_kg=%s,estado=%s,notas=%s,version=version+1
                    WHERE id_faena=%s""", (datos.id_cliente, datos.nombre, datos.predio, datos.cultivo,
                    datos.fecha_inicio, datos.fecha_fin, datos.precio_kg, datos.estado, datos.notas, id_faena))
                auditar(cursor, request, "Actualización de faena", f"Faena {id_faena}; estado {datos.estado}; versión {datos.version+1}")
        return {"mensaje": "Faena actualizada"}
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409, "Ya existe esa faena para el cliente y la fecha de inicio") from error


@router.get("/faenas")
def listar_faenas():
    with conectar_bd() as conexion:
        cursor = conexion.execute("""SELECT f.id_faena AS id,f.id_cliente,c.nombre AS cliente,c.activo AS cliente_activo,
            f.nombre,f.predio,f.cultivo,f.fecha_inicio,f.fecha_fin,f.precio_kg,f.estado,f.notas,f.version,
            COALESCE(r.registros,0) AS registros,COALESCE(r.kilos,0) AS kilos,
            COALESCE(r.horas,0) AS horas,COALESCE(r.trabajadores,0) AS trabajadores,
            COALESCE(r.jornadas,0) AS jornadas,COALESCE(r.sin_tarifa,0) AS sin_tarifa,
            CASE WHEN COALESCE(r.sin_tarifa,0)=0 THEN COALESCE(r.pago_estimado,0) END AS pago_estimado
            FROM faenas f JOIN clientes c USING(id_cliente)
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS registros,SUM(p.cantidad_kg+COALESCE(a.kilos,0)) AS kilos,
                    SUM(COALESCE(p.horas_trabajadas,0)+COALESCE(a.horas,0)) AS horas,
                    COUNT(DISTINCT p.id_trabajador) AS trabajadores,COUNT(DISTINCT p.id_jornada) AS jornadas,
                    COUNT(*) FILTER(WHERE COALESCE(g.precio_kg,t.precio_kg) IS NULL) AS sin_tarifa,
                    SUM((p.cantidad_kg+COALESCE(a.kilos,0))*COALESCE(g.precio_kg,t.precio_kg)) AS pago_estimado
                FROM produccion p JOIN jornadas j USING(id_jornada)
                LEFT JOIN tarifas t ON t.semana_inicio=date_trunc('week',j.fecha)::date
                LEFT JOIN pagos g ON g.semana_inicio=date_trunc('week',j.fecha)::date AND g.id_trabajador=p.id_trabajador
                LEFT JOIN LATERAL (SELECT SUM(diferencia_kg) AS kilos,SUM(diferencia_horas) AS horas
                    FROM ajustes_cosecha WHERE id_produccion=p.id_produccion) a ON TRUE
                WHERE p.id_faena=f.id_faena
            ) r ON TRUE ORDER BY f.fecha_inicio DESC,f.id_faena DESC"""
        )
        filas = [dict(zip([d.name for d in cursor.description], fila)) for fila in cursor.fetchall()]
    for fila in filas:
        fila["cobro_estimado"] = calcular_total(fila["kilos"], fila["precio_kg"])
        if fila["pago_estimado"] is not None:
            fila["pago_estimado"] = calcular_total(fila["pago_estimado"], Decimal(1))
    return filas


@router.get("/faenas/{id_faena}/produccion")
def produccion_faena(id_faena: int):
    with conectar_bd() as conexion:
        if not conexion.execute("SELECT 1 FROM faenas WHERE id_faena=%s", (id_faena,)).fetchone():
            raise HTTPException(404, "Faena no encontrada")
        cursor = conexion.execute("""SELECT p.id_produccion AS id,j.fecha,CONCAT(t.nombre,' ',t.apellido) AS trabajador,
            s.nombre AS sector,l.nombre AS labor,p.cantidad_kg AS kilos_originales,
            COALESCE(a.kilos,0) AS ajuste_kg,p.cantidad_kg+COALESCE(a.kilos,0) AS kilos,
            COALESCE(p.horas_trabajadas,0)+COALESCE(a.horas,0) AS horas
            FROM produccion p JOIN jornadas j USING(id_jornada) JOIN trabajadores t USING(id_trabajador)
            JOIN sectores s USING(id_sector) JOIN labores l USING(id_labor)
            LEFT JOIN LATERAL (SELECT SUM(diferencia_kg) AS kilos,SUM(diferencia_horas) AS horas
                FROM ajustes_cosecha WHERE id_produccion=p.id_produccion) a ON TRUE
            WHERE p.id_faena=%s ORDER BY j.fecha DESC,p.id_produccion DESC LIMIT 200""", (id_faena,))
        return [dict(zip([d.name for d in cursor.description], fila)) for fila in cursor.fetchall()]


def validar_faena_registro(cursor, id_faena, fecha):
    """Bloquea el acuerdo mientras se guarda el lote; no permite cambiar su precio a la vez."""
    if id_faena is None:
        return
    cursor.execute("SELECT id_cliente FROM faenas WHERE id_faena=%s", (id_faena,))
    referencia = cursor.fetchone()
    if not referencia:
        raise HTTPException(404, "Faena no encontrada; no se guardó el lote")
    exigir_cliente_activo(cursor, referencia[0])
    cursor.execute("SELECT id_cliente,estado,fecha_inicio,fecha_fin FROM faenas WHERE id_faena=%s FOR SHARE", (id_faena,))
    cliente, estado, inicio, fin = cursor.fetchone()
    if cliente != referencia[0]:
        raise HTTPException(409, "La faena cambió mientras guardabas. Actualiza e intenta nuevamente.")
    if estado != "Activa":
        raise HTTPException(409, "Solo se puede registrar producción en faenas activas")
    if fecha < inicio or (fin and fecha > fin):
        raise HTTPException(422, "La fecha de cosecha está fuera del período de la faena")
