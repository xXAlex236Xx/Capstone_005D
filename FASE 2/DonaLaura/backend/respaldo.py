"""Copias PostgreSQL y restauración en bases nuevas. Nunca sobrescribe la operación."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
from database import conectar_bd, BASE_DIR

CARPETA = BASE_DIR.parents[2] / ".local" / "backups"
def ahora():
    return datetime.now(ZoneInfo("America/Santiago"))


def herramientas():
    with conectar_bd() as c:
        version = c.info.server_version // 10000
    base = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PostgreSQL" / str(version) / "bin"
    dump = str(base / "pg_dump.exe") if (base / "pg_dump.exe").exists() else shutil.which("pg_dump")
    restore = str(base / "pg_restore.exe") if (base / "pg_restore.exe").exists() else shutil.which("pg_restore")
    if not dump or not restore:
        raise RuntimeError("No se encontraron pg_dump y pg_restore de PostgreSQL. Instala sus herramientas de línea de comandos.")
    return dump, restore


def entorno():
    variables = os.environ.copy()
    for origen,destino in (("DB_HOST","PGHOST"),("DB_PORT","PGPORT"),("DB_USER","PGUSER"),("DB_PASSWORD","PGPASSWORD")):
        variables[destino] = os.getenv(origen, "")
    return variables


def ejecutar(args):
    resultado = subprocess.run(args, env=entorno(), capture_output=True, text=True, encoding="utf-8", errors="replace",timeout=300)
    if resultado.returncode:
        # No incluir el entorno ni credenciales en la salida de diagnóstico.
        raise RuntimeError("La herramienta PostgreSQL no pudo completar la operación. Comprueba permisos y compatibilidad de versiones.")


def conteos(conexion):
    tablas=[f[0] for f in conexion.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()]
    return {t:conexion.execute(sql.SQL("SELECT COUNT(*) FROM public.{}").format(sql.Identifier(t))).fetchone()[0] for t in tablas}


def huella_archivo(archivo):
    with Path(archivo).open("rb") as entrada:
        return hashlib.file_digest(entrada,"sha256").hexdigest()


def copia_integra(archivo):
    try:
        metadata=json.loads(archivo.with_suffix(".json").read_text(encoding="utf-8"))
        return huella_archivo(archivo)==metadata["sha256"]
    except (OSError,ValueError,KeyError):
        return False


def crear_diario():
    with conectar_bd() as coordinador:
        if not coordinador.execute("SELECT pg_try_advisory_xact_lock(20261102,3)").fetchone()[0]: return
        for archivo in CARPETA.glob(f"agricolix_{ahora():%Y%m%d}_*.dump"):
            if copia_integra(archivo):
                metadata = json.loads(archivo.with_suffix(".json").read_text(encoding="utf-8"))
                if metadata.get("base_datos") == os.getenv("DB_NAME"):
                    return
        crear()


def crear():
    CARPETA.mkdir(parents=True, exist_ok=True)
    dump,_ = herramientas()
    archivo = CARPETA / f"agricolix_{ahora():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}.dump"
    with conectar_bd() as origen:
        origen.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        snapshot = origen.execute("SELECT pg_export_snapshot()").fetchone()[0]
        filas = conteos(origen)
        ejecutar([dump,"--format=custom","--no-owner","--no-privileges","--snapshot",snapshot,"--file",str(archivo),"--dbname",os.environ["DB_NAME"]])
    metadata = {"creado_en":ahora().isoformat(),"base_datos":os.environ["DB_NAME"],"sha256":huella_archivo(archivo),"conteos":filas}
    archivo.with_suffix(".json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Respaldo creado: {archivo}")
    return archivo


def restaurar(archivo, verificar=False, destino=None):
    archivo = Path(archivo).resolve(strict=True)
    metadata = json.loads(archivo.with_suffix(".json").read_text(encoding="utf-8"))
    if huella_archivo(archivo) != metadata["sha256"]:
        raise RuntimeError("La copia no coincide con su verificación de integridad. No se restauró nada.")
    nombre = "agricolix_restore_test_"+uuid4().hex[:12] if verificar else destino
    if not nombre or not nombre.startswith(("agricolix_restore_test_","agricolix_recuperada_")) or nombre==os.getenv("DB_NAME"):
        raise RuntimeError("La restauración exige una base NUEVA con prefijo agricolix_recuperada_. Nunca se sobrescribe la base operativa.")
    _,restore = herramientas()
    parametros=dict(host=os.getenv("DB_HOST"),port=os.getenv("DB_PORT"),user=os.getenv("DB_USER"),password=os.getenv("DB_PASSWORD"))
    creada=False
    try:
        with psycopg.connect(**parametros,dbname="postgres",autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nombre)))
            creada=True
        ejecutar([restore,"--exit-on-error","--no-owner","--no-privileges","--dbname",nombre,str(archivo)])
        with psycopg.connect(**parametros,dbname=nombre) as restaurada:
            if conteos(restaurada) != metadata["conteos"]: raise RuntimeError("Los conteos de la restauración no coinciden con el respaldo")
        print("Restauracion comprobada: integridad y conteos correctos." if verificar else f"Base recuperada: {nombre}. Revisa sus datos antes de cambiar DB_NAME.")
    finally:
        if verificar and creada:
            assert nombre.startswith("agricolix_restore_test_")
            with psycopg.connect(**parametros,dbname="postgres",autocommit=True) as admin:
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(nombre)))


def principal():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diario",action="store_true",help="Una copia por día al iniciar la aplicación")
    p.add_argument("--verificar",type=Path,help="Restaurar una copia en una base temporal y comprobar conteos")
    p.add_argument("--restaurar",type=Path,help="Recuperar una copia en una base nueva")
    p.add_argument("--destino",help="Nombre de base nueva con prefijo agricolix_recuperada_")
    args=p.parse_args()
    if args.verificar: restaurar(args.verificar,verificar=True)
    elif args.restaurar: restaurar(args.restaurar,destino=args.destino)
    else:
        if args.diario: crear_diario()
        else: crear()


if __name__ == "__main__":
    try: principal()
    except Exception as error:
        print(f"No se completo el respaldo o la restauracion: {type(error).__name__}: {error}")
        raise SystemExit(1)
