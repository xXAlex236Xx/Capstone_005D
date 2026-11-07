"""Identificación explícita de copias con datos sintéticos."""
from fastapi import APIRouter
from database import conectar_bd

router = APIRouter(tags=["Entorno de trabajo"])


def describir_entorno():
    with conectar_bd() as conexion:
        if not conexion.execute("SELECT to_regclass('public.entorno_demostracion')").fetchone()[0]:
            return {"demostracion": False}
        fila = conexion.execute("SELECT desde,hasta FROM entorno_demostracion WHERE id=1").fetchone()
    if not fila:
        return {"demostracion": False}
    return {"demostracion": True, "desde": fila[0].isoformat(), "hasta": fila[1].isoformat(),
            "aviso": "Datos ficticios para explorar la aplicación. No representan actividad real de Doña Laura."}


@router.get("/entorno")
def entorno_actual():
    return describir_entorno()
