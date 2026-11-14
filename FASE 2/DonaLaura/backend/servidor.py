"""Sirve la app compilada y su API bajo el mismo origen."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import BASE_DIR, conectar_bd
from main import app as api
from pagos import ciclo_de_vida
from seguridad import hash_password


def preparar_base():
    if os.getenv("AGRICOLIX_PRODUCCION") != "1" or not os.getenv("DATABASE_URL"):
        raise RuntimeError("El servidor de entrega requiere AGRICOLIX_PRODUCCION y DATABASE_URL.")
    with conectar_bd() as conexion:
        conexion.execute("SELECT pg_advisory_xact_lock(20261102, 1)")
        if conexion.execute("SELECT to_regclass('public.entorno_demostracion')").fetchone()[0]:
            raise RuntimeError("La versión de entrega requiere una base separada de la demostración.")
        conexion.execute((BASE_DIR / "esquema.sql").read_text(encoding="utf-8-sig"))


def crear_administrador_inicial():
    with conectar_bd() as conexion:
        conexion.execute("LOCK TABLE usuarios IN EXCLUSIVE MODE")
        if conexion.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            return
        clave = os.getenv("AGRICOLIX_CLAVE_INICIAL", "")
        if not 16 <= len(clave) <= 256 or not clave.strip():
            raise RuntimeError("Configura una clave inicial de entre 16 y 256 caracteres.")
        conexion.execute(
            "INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES (%s,%s,%s,%s)",
            ("admin", "Administrador", hash_password(clave), "administrador"),
        )


@asynccontextmanager
async def iniciar(app):
    preparar_base()
    async with ciclo_de_vida(api):
        crear_administrador_inicial()
        yield


app = FastAPI(lifespan=iniciar, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", api)
app.mount("/", StaticFiles(directory=BASE_DIR.parent / "frontend" / "dist", html=True))
