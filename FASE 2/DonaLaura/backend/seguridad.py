"""Acceso por sesión, permisos y trazabilidad. No almacena contraseñas en claro."""
import hashlib
import hmac
import logging
import os
import secrets
from pathlib import Path

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from database import conectar_bd

router = APIRouter(tags=["Acceso y usuarios"])
COOKIE = "agricolix_session"
ITERACIONES = 600_000
ROLES = {"administrador", "encargado", "consulta"}
ORIGENES = {"http://127.0.0.1:5173", "http://localhost:5173"}
logger = logging.getLogger("agricolix.acceso")


def hash_password(password: str) -> str:
    sal = secrets.token_hex(16)
    derivada = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${sal}${derivada.hex()}"


def verificar_password(password: str, valor: str) -> bool:
    try:
        algoritmo, iteraciones, sal, esperado = valor.split("$")
        if algoritmo != "pbkdf2_sha256" or not 100_000 <= int(iteraciones) <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), int(iteraciones))
        return hmac.compare_digest(actual.hex(), esperado)
    except (ValueError, TypeError):
        return False


HASH_FICTICIO = hash_password(secrets.token_urlsafe(24))


def inicializar_seguridad():
    carpeta = Path(__file__).parent / "migrations"
    with conectar_bd() as conexion:
        conexion.execute("SELECT pg_advisory_xact_lock(20261102, 1)")
        conexion.execute("CREATE TABLE IF NOT EXISTS migraciones (version TEXT PRIMARY KEY, aplicado_en TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        for archivo in sorted(carpeta.glob("*.sql")):
            if not conexion.execute("SELECT 1 FROM migraciones WHERE version = %s", (archivo.name,)).fetchone():
                conexion.execute(archivo.read_text(encoding="utf-8"))
                conexion.execute("INSERT INTO migraciones(version) VALUES (%s)", (archivo.name,))


def usuario_de_sesion(token):
    if not token:
        return None
    with conectar_bd() as conexion:
        fila = conexion.execute("""
            SELECT u.id_usuario, u.usuario, u.nombre, u.rol
            FROM sesiones s JOIN usuarios u USING(id_usuario)
            WHERE s.token_hash = %s AND s.vence_en > NOW() AND u.activo
        """, (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    return dict(zip(("id", "usuario", "nombre", "rol"), fila)) if fila else None


def registrar_evento(id_usuario, accion, detalle=""):
    with conectar_bd() as conexion:
        conexion.execute("INSERT INTO auditoria(id_usuario, accion, detalle) VALUES (%s,%s,%s)",
                         (id_usuario, accion[:180], detalle[:250]))


def puede_acceder(rol, metodo, ruta):
    if metodo not in {"GET", "HEAD", "OPTIONS"} and (ruta == "/cobros" or ruta.startswith("/cobros/")):
        return rol == "administrador"
    if metodo not in {"GET", "HEAD", "OPTIONS"} and (ruta == "/clientes" or ruta.startswith("/clientes/") or ruta == "/faenas" or ruta.startswith("/faenas/")):
        return rol == "administrador"
    if metodo not in {"GET","HEAD","OPTIONS"} and (ruta.startswith("/seguimiento-pagos/") or ruta.endswith("/ajustes")):
        return rol == "administrador"
    if ruta.startswith("/usuarios") or ruta == "/auditoria":
        return rol == "administrador"
    if metodo in {"GET", "HEAD", "OPTIONS"} or ruta.startswith("/auth/"):
        return True
    if ruta.startswith("/ia/") or ruta in {"/importacion/validar", "/importacion/vista-previa"}:
        return True
    if ruta.startswith("/tarifas") or ruta == "/pagos/cerrar":
        return rol == "administrador"
    return rol in {"administrador", "encargado"}


def nombre_operacion(metodo, ruta):
    if ruta == "/clientes": return "Creación de cliente"
    if ruta.startswith("/clientes/"): return "Actualización de cliente"
    if ruta == "/faenas": return "Creación de faena"
    if ruta.startswith("/faenas/"): return "Actualización de faena"
    if ruta == "/produccion/jornada": return "Registro de jornada"
    if ruta.endswith("/ajustes"): return "Ajuste de cosecha cerrada"
    if ruta.startswith("/produccion/") and metodo == "PATCH": return "Corrección de cosecha"
    if ruta.startswith("/seguimiento-pagos/"): return "Aprobación de pago" if ruta.endswith("/aprobar") else "Registro de abono"
    nombres = {
        "/produccion": "Registro de cosecha", "/trabajadores": "Registro de trabajador",
        "/jornadas": "Creación de jornada", "/sectores": "Creación de sector",
        "/labores": "Creación de labor", "/pagos/cerrar": "Cierre de semana de pagos",
        "/usuarios": "Creación de usuario", "/auth/logout": "Cierre de sesión",
        "/auth/password": "Cambio de contraseña", "/importacion/guardar": "Importación de cosechas",
        "/importacion/validar": "Validación de planilla", "/importacion/vista-previa": "Vista previa de planilla",
        "/ia/agente": "Consulta al asistente", "/ia/chat": "Consulta al análisis local",
    }
    if ruta.startswith("/tarifas/"):
        return "Actualización de tarifa semanal"
    if ruta.startswith("/usuarios/"):
        return "Actualización de acceso de usuario"
    if ruta.startswith("/trabajadores/"):
        return "Desactivación de trabajador" if ruta.endswith("/desactivar") else "Actualización de trabajador"
    return nombres.get(ruta, "Operación registrada")


class ControlAcceso(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ruta = request.url.path
        if request.method == "OPTIONS" or ruta in {"/", "/health", "/auth/login", "/entorno"}:
            if request.method != "OPTIONS" and request.method not in {"GET", "HEAD"}:
                origen = request.headers.get("origin")
                if origen and origen not in ORIGENES:
                    return JSONResponse({"detail": "Origen de solicitud no permitido"}, status_code=403)
            return await call_next(request)
        try:
            # Las operaciones síncronas de PostgreSQL se ejecutan fuera del event loop.
            from starlette.concurrency import run_in_threadpool
            usuario = await run_in_threadpool(usuario_de_sesion, request.cookies.get(COOKIE))
        except psycopg.Error:
            return JSONResponse({"detail": "La base de datos no está disponible"}, status_code=503)
        if not usuario:
            return JSONResponse({"detail": "Inicia sesión para continuar"}, status_code=401)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origen = request.headers.get("origin")
            if origen and origen not in ORIGENES:
                return JSONResponse({"detail": "Origen de solicitud no permitido"}, status_code=403)
        if not puede_acceder(usuario["rol"], request.method, ruta):
            return JSONResponse({"detail": "Tu perfil no tiene permiso para esta operación"}, status_code=403)
        request.state.usuario = usuario
        respuesta = await call_next(request)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and respuesta.status_code < 400:
            try:
                await run_in_threadpool(registrar_evento, usuario["id"], nombre_operacion(request.method, ruta))
            except psycopg.Error:
                logger.exception("No se pudo registrar la auditoría de %s", ruta)
        return respuesta


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class UsuarioNuevo(BaseModel):
    usuario: str = Field(pattern=r"^[a-zA-Z0-9._-]{3,80}$")
    nombre: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    rol: str


class UsuarioEditar(BaseModel):
    rol: str
    activo: bool


class CambioPassword(BaseModel):
    actual: str = Field(min_length=1, max_length=256)
    nueva: str = Field(min_length=12, max_length=256)


@router.post("/auth/login")
def login(datos: Credenciales, request: Request, response: Response):
    nombre = datos.usuario.strip().lower()
    origen = request.client.host if request.client else "local"
    with conectar_bd() as conexion:
        conexion.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"login:{nombre}:{origen}",))
        conexion.execute("DELETE FROM intentos_login WHERE creado_en < NOW() - INTERVAL '15 minutes'")
        fallos = conexion.execute("SELECT COUNT(*) FROM intentos_login WHERE usuario=%s AND origen=%s", (nombre, origen)).fetchone()[0]
        if fallos >= 5:
            raise HTTPException(429, "Demasiados intentos. Espera 15 minutos antes de volver a intentar.")
        fila = conexion.execute("SELECT id_usuario, usuario, nombre, rol, password_hash, activo FROM usuarios WHERE usuario=%s", (nombre,)).fetchone()
        valido = verificar_password(datos.password, fila[4] if fila else HASH_FICTICIO)
        if not fila or not valido or not fila[5]:
            conexion.execute("INSERT INTO intentos_login(usuario, origen) VALUES (%s,%s)", (nombre, origen))
            # Confirmar el intento fallido antes de devolver el error HTTP.
            conexion.commit()
            raise HTTPException(401, "Usuario o contraseña incorrectos")
        token = secrets.token_urlsafe(48)
        conexion.execute("DELETE FROM sesiones WHERE vence_en <= NOW()")
        conexion.execute("DELETE FROM intentos_login WHERE usuario=%s AND origen=%s", (nombre, origen))
        conexion.execute("INSERT INTO sesiones(token_hash,id_usuario,vence_en) VALUES (%s,%s,NOW()+INTERVAL '8 hours')", (hashlib.sha256(token.encode()).hexdigest(), fila[0]))
        conexion.execute("INSERT INTO auditoria(id_usuario,accion) VALUES (%s,'Inicio de sesión')", (fila[0],))
    response.set_cookie(COOKIE, token, max_age=8 * 3600, httponly=True,
                        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", samesite="strict")
    return dict(zip(("id", "usuario", "nombre", "rol"), fila[:4]))


@router.get("/auth/session")
def sesion(request: Request):
    return request.state.usuario


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    with conectar_bd() as conexion:
        conexion.execute("DELETE FROM sesiones WHERE token_hash=%s", (hashlib.sha256(request.cookies[COOKIE].encode()).hexdigest(),))
    response.delete_cookie(COOKIE, httponly=True, samesite="strict")
    return {"mensaje": "Sesión cerrada"}


@router.post("/auth/password")
def cambiar_password(datos: CambioPassword, request: Request):
    with conectar_bd() as conexion:
        actual = conexion.execute("SELECT password_hash FROM usuarios WHERE id_usuario=%s FOR UPDATE", (request.state.usuario["id"],)).fetchone()[0]
        if not verificar_password(datos.actual, actual):
            raise HTTPException(400, "La contraseña actual no es correcta")
        conexion.execute("UPDATE usuarios SET password_hash=%s WHERE id_usuario=%s", (hash_password(datos.nueva), request.state.usuario["id"]))
        conexion.execute("DELETE FROM sesiones WHERE id_usuario=%s AND token_hash<>%s", (request.state.usuario["id"], hashlib.sha256(request.cookies[COOKIE].encode()).hexdigest()))
    return {"mensaje": "Contraseña actualizada. Las otras sesiones se han cerrado."}


@router.get("/usuarios")
def listar_usuarios():
    with conectar_bd() as conexion:
        filas = conexion.execute("SELECT id_usuario,usuario,nombre,rol,activo FROM usuarios ORDER BY id_usuario").fetchall()
    return [dict(zip(("id", "usuario", "nombre", "rol", "activo"), fila)) for fila in filas]


@router.post("/usuarios", status_code=201)
def crear_usuario(datos: UsuarioNuevo):
    if datos.rol not in ROLES or not datos.nombre.strip():
        raise HTTPException(422, "Nombre o perfil inválido")
    try:
        with conectar_bd() as conexion:
            fila = conexion.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES (%s,%s,%s,%s) RETURNING id_usuario", (datos.usuario.lower(), datos.nombre.strip(), hash_password(datos.password), datos.rol)).fetchone()
        return {"id": fila[0], "mensaje": "Usuario creado"}
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409, "Ese nombre de usuario ya existe") from error


@router.patch("/usuarios/{id_usuario}")
def editar_usuario(id_usuario: int, datos: UsuarioEditar, request: Request):
    if datos.rol not in ROLES:
        raise HTTPException(422, "Perfil inválido")
    if id_usuario == request.state.usuario["id"]:
        raise HTTPException(409, "No puedes cambiar tu propio perfil ni desactivar tu cuenta")
    with conectar_bd() as conexion:
        conexion.execute("SELECT pg_advisory_xact_lock(20261102, 2)")
        fila = conexion.execute("UPDATE usuarios SET rol=%s,activo=%s WHERE id_usuario=%s RETURNING id_usuario", (datos.rol, datos.activo, id_usuario)).fetchone()
        if not fila:
            raise HTTPException(404, "Usuario no encontrado")
        if not conexion.execute("SELECT 1 FROM usuarios WHERE rol='administrador' AND activo LIMIT 1").fetchone():
            raise HTTPException(409, "Debe quedar al menos un administrador activo")
        conexion.execute("DELETE FROM sesiones WHERE id_usuario=%s", (id_usuario,))
    return {"mensaje": "Acceso actualizado"}


@router.get("/auditoria")
def auditoria():
    with conectar_bd() as conexion:
        filas = conexion.execute("""SELECT a.id_evento,COALESCE(u.nombre,'Sistema'),a.accion,a.detalle,a.creado_en
            FROM auditoria a LEFT JOIN usuarios u USING(id_usuario)
            ORDER BY a.id_evento DESC LIMIT 200""").fetchall()
    return [dict(zip(("id", "nombre", "accion", "detalle", "fecha"), fila)) for fila in filas]
