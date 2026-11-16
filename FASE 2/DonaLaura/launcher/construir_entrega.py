# ==========================================================
# AGRICOLIX - CONSTRUCCIÓN DEL EJECUTABLE
# Herramienta de desarrollo (no la usa el usuario final).
# Cuando cambie el frontend o el lanzador, ejecutar:
#   python construir_entrega.py
# Hace dos cosas:
#   - Compila la interfaz (frontend/dist). Esa carpeta SÍ se sube a Git,
#     porque el usuario no tiene Node para compilarla.
#   - Genera Agricolix.exe en la carpeta raíz del proyecto.
# Python, PostgreSQL y las librerías NO se preparan aquí: el propio
# Agricolix.exe los descarga solo la primera vez que se abre.
# Requiere Node.js y Python 3.13.
# ==========================================================
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NOMBRE_DATOS = "agricolix data"
DATOS = Path(__file__).resolve().parent.parent
RAIZ = DATOS.parent if DATOS.name == NOMBRE_DATOS else DATOS.parents[1]


def construir_interfaz():
    frontend = DATOS / "frontend"
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not (frontend / "node_modules").is_dir():
        subprocess.run([npm, "install"], cwd=frontend, check=True)
    subprocess.run([npm, "run", "build"], cwd=frontend, check=True)


def construir_exe():
    icono = Path(__file__).with_name("agricolix.ico")
    with tempfile.TemporaryDirectory() as temporal:
        entorno = Path(temporal) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(entorno)], check=True)
        python = entorno / "Scripts" / "python.exe"
        subprocess.run([str(python), "-m", "pip", "install", "pyinstaller"], check=True)
        # El ícono va en el exe y también dentro, para la ventana (ver poner_icono en agricolix.py).
        subprocess.run([str(python), "-m", "PyInstaller", "--onefile", "--noconsole", "--name", "Agricolix",
                        "--icon", str(icono), "--add-data", f"{icono};.", "--distpath", str(RAIZ), "--workpath", str(Path(temporal) / "work"),
                        "--specpath", temporal, str(Path(__file__).with_name("agricolix.py"))], check=True)


if __name__ == "__main__":
    construir_interfaz()
    construir_exe()
    print("Listo. Agricolix.exe está en:", RAIZ)
