"""Crea el primer administrador, sin modificar usuarios existentes.

Uso: python crear_admin.py. Guarda un acceso inicial aleatorio en .local/primer-acceso.txt.
"""
import os
import re
import secrets
import sys
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
        destino = Path(os.getenv("AGRICOLIX_LOCAL") or Path(__file__).resolve().parents[3] / ".local") / "primer-acceso.txt"
        destino.parent.mkdir(exist_ok=True)
        destino.write_text(f"AGRICOLIX · Acceso inicial\n\nUsuario: admin\nContraseña: {password}\n\nAbre http://127.0.0.1:5173 y cambia esta contraseña desde Mi cuenta.\nEste archivo es local y está excluido de Git.\n", encoding="utf-8")
    print("Administrador creado. Consulta .local/primer-acceso.txt en la raíz del proyecto.")


def preparar_base():
    """Crea las tablas y aplica las migraciones, sin crear ningún usuario."""
    from pagos import crear_tablas_pagos
    crear_tablas_pagos()
    inicializar_seguridad()


def hay_usuarios():
    with conectar_bd() as conexion:
        return conexion.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone() is not None


def crear_con_datos(reemplazar=False):
    """Crea el primer administrador con el usuario y la contraseña que eligió la persona.

    Los datos llegan por variables de entorno (AGRICOLIX_ADMIN_USUARIO y AGRICOLIX_ADMIN_PASSWORD)
    para que la contraseña no aparezca en la línea de comandos.

    Con reemplazar=True las cuentas anteriores se desactivan (no se borran, porque el historial de
    pagos y la auditoría se refieren a ellas), se cierran sus sesiones y queda solo la cuenta nueva.
    """
    usuario = os.getenv("AGRICOLIX_ADMIN_USUARIO", "").strip().lower()
    password = os.getenv("AGRICOLIX_ADMIN_PASSWORD", "")
    if not re.fullmatch(r"[a-z0-9._-]{3,80}", usuario):
        print("El usuario debe tener entre 3 y 80 caracteres: letras, números, punto, guion o guion bajo.")
        sys.exit(3)
    if not 12 <= len(password) <= 256:
        print("La contraseña debe tener al menos 12 caracteres.")
        sys.exit(3)
    with conectar_bd() as conexion:
        conexion.execute("LOCK TABLE usuarios IN EXCLUSIVE MODE")
        if reemplazar:
            conexion.execute("UPDATE usuarios SET activo=FALSE WHERE usuario<>%s", (usuario,))
            conexion.execute("DELETE FROM sesiones")
            existente = conexion.execute("UPDATE usuarios SET password_hash=%s, rol='administrador', activo=TRUE "
                                         "WHERE usuario=%s RETURNING 1", (hash_password(password), usuario)).fetchone()
            if existente:
                print("Cuenta reemplazada.")
                return
        elif conexion.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            print("Ya existen usuarios; no se modificó ninguna cuenta.")
            sys.exit(2)
        conexion.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol) VALUES (%s,%s,%s,%s)",
                         (usuario, usuario, hash_password(password), "administrador"))
    print("Cuenta reemplazada." if reemplazar else "Administrador creado.")


if __name__ == "__main__":
    if "--preparar" in sys.argv:
        preparar_base()
    elif "--hay-usuarios" in sys.argv:
        print("si" if hay_usuarios() else "no")
    elif "--crear" in sys.argv:
        crear_con_datos()
    elif "--reemplazar" in sys.argv:
        crear_con_datos(reemplazar=True)
    else:
        crear_primero()
