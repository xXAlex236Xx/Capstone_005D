"""Crea el primer administrador, sin modificar usuarios existentes.

Uso: python crear_admin.py. Guarda un acceso inicial aleatorio en .local/primer-acceso.txt.
"""
import secrets
from pathlib import Path

from database import conectar_bd
from seguridad import hash_password, inicializar_seguridad


def crear_primero():
    from pagos import crear_tablas_pagos
    crear_tablas_pagos()
    inicializar_seguridad()
    with conectar_bd() as conexion:
        conexion.execute("LOCK TABLE usuarios IN EXCLUSIVE MODE")
        if conexion.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            print("Ya existen usuarios; no se modificó ninguna cuenta.")
            return
        password = secrets.token_urlsafe(18)
        conexion.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES (%s,%s,%s,%s)",
                         ("admin", "Administrador", hash_password(password), "administrador"))
        destino = Path(__file__).resolve().parents[3] / ".local" / "primer-acceso.txt"
        destino.parent.mkdir(exist_ok=True)
        destino.write_text(f"AGRICOLIX · Acceso inicial\n\nUsuario: admin\nContraseña: {password}\n\nAbre http://127.0.0.1:5173 y cambia esta contraseña desde Mi cuenta.\nEste archivo es local y está excluido de Git.\n", encoding="utf-8")
    print("Administrador creado. Consulta .local/primer-acceso.txt en la raíz del proyecto.")


if __name__ == "__main__":
    crear_primero()
