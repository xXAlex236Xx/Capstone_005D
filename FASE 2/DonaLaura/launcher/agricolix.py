# ==========================================================
# AGRICOLIX - LANZADOR
# Ventana con "Iniciar sistema" y "Apagar sistema".
# La primera vez descarga lo que falta, ordena la carpeta del
# proyecto, prepara la base de datos y pide crear la cuenta de
# acceso (y, si se quiere, la clave de OpenAI). Después solo
# enciende o apaga los servicios.
#
# Uso normal: doble clic en Agricolix.exe (sin consola).
# Pruebas:    Agricolix.exe --raiz <carpeta> --abrir | --ordenar
#             | --iniciar | --apagar | --estado | --restaurar
#             | --crear-cuenta (usuario y contraseña por variables
#               AGRICOLIX_ADMIN_USUARIO y AGRICOLIX_ADMIN_PASSWORD)
# ==========================================================
import argparse
import http.client
import json
import os
import platform
import queue
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

NOMBRE_DATOS = "agricolix data"
VERSION_POSTGRES = "18.0-1"
PUERTO_WEB = 5173
PUERTO_API = 8000
PUERTO_BD = 54329
NOMBRE_BD = "dona_laura_db"
URL_WEB = f"http://127.0.0.1:{PUERTO_WEB}"
URL_API = f"http://127.0.0.1:{PUERTO_API}/health"
SOPORTE = "Si el problema continúa, contacta con soporte."
INTENTOS_DESCARGA = 5
ESPERAS_DESCARGA = (2, 5, 10, 15)  # segundos entre reintentos

# Lo único que se elimina al ordenar. Cualquier otra cosa en la carpeta se respeta.
ELIMINAR = [
    "FASE 1", "FASE 2", "FASE 3",
    "README.md", "DEMOSTRACION.md", "PRUEBA_OPERATIVA.md",
    "Iniciar Agricolix.cmd", "Detener Agricolix.cmd", "Respaldar Agricolix.cmd",
    "Usar demostracion.cmd", "Volver a datos reales.cmd",
    "scripts",
]

SIN_VENTANA = subprocess.CREATE_NO_WINDOW
SEPARADO = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP


class ErrorAgricolix(Exception):
    """Error pensado para mostrarse tal cual al usuario."""


class FaltaCuenta(ErrorAgricolix):
    """Todavía no existe ningún usuario: hay que crear la cuenta de acceso."""


# ==========================================================
# UTILIDADES
# ==========================================================
def responde(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as respuesta:
            return respuesta.status == 200
    except OSError:
        return False


def puerto_abierto(puerto):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conexion:
        conexion.settimeout(1)
        return conexion.connect_ex(("127.0.0.1", puerto)) == 0


def borrar(ruta):
    def quitar_solo_lectura(funcion, camino, _error):
        os.chmod(camino, stat.S_IWRITE)
        funcion(camino)

    if ruta.is_dir() and not ruta.is_symlink():
        shutil.rmtree(ruta, onexc=quitar_solo_lectura)
    else:
        ruta.unlink()


def esperar(condicion, segundos):
    fin = time.time() + segundos
    while time.time() < fin:
        if condicion():
            return True
        time.sleep(0.5)
    return False


def validar_cuenta(usuario, password):
    """Devuelve un mensaje de error, o None si el usuario y la contraseña sirven."""
    if not re.fullmatch(r"[a-z0-9._-]{3,80}", usuario):
        return "El usuario debe tener entre 3 y 80 caracteres: letras, números, punto, guion o guion bajo."
    if len(password) < 12:
        return "La contraseña debe tener al menos 12 caracteres."
    return None


def validar_clave_openai(clave):
    if clave and (len(clave) < 20 or any(c.isspace() for c in clave)):
        return "La clave de OpenAI no parece válida. Cópiala completa, sin espacios."
    return None


# ==========================================================
# SISTEMA
# ==========================================================
class Sistema:
    def __init__(self, raiz, avisar=print):
        self.raiz = Path(raiz).resolve()
        self.avisar = avisar
        self.datos = self.raiz / NOMBRE_DATOS
        self.backend = self.datos / "backend"
        self.dist = self.datos / "frontend" / "dist"
        self.local = self.datos / ".local"
        self.python = self.datos / "runtime" / "python" / "python.exe"
        self.pgbin = self.datos / "runtime" / "postgres" / "bin"
        self.pgdatos = self.datos / "datos" / "postgres"
        self.registro = self.local / "procesos.json"
        # Ruta del programa (solo cuando corre como Agricolix.exe); la usa el acceso directo.
        self.exe = Path(sys.executable) if getattr(sys, "frozen", False) else None

    # ---------- orden de la carpeta ----------
    def necesita_ordenar(self):
        origen = self.raiz / "FASE 2" / "DonaLaura" / "backend" / "main.py"
        return origen.is_file() and not self.datos.exists()

    def ordenar(self):
        """Mueve el sistema a 'agricolix data' y elimina los documentos del proyecto."""
        origen = self.raiz / "FASE 2" / "DonaLaura"
        # Antes de eliminar nada: se descarga lo que falte; si algo falla, no se toca la carpeta.
        self.instalar_componentes(origen)
        self.avisar("Ordenando la carpeta del proyecto...")
        try:
            origen.rename(self.datos)
        except OSError:
            raise ErrorAgricolix("No se pudo ordenar la carpeta. Cierra los programas que tengan "
                                 "archivos del proyecto abiertos e inténtalo de nuevo.")
        if not (self.backend / "main.py").is_file():
            raise ErrorAgricolix("El orden de la carpeta quedó incompleto. No se eliminó nada.")
        fallos = []
        for nombre in ELIMINAR:
            destino = self.raiz / nombre
            if destino.parent != self.raiz or not (destino.exists() or destino.is_symlink()):
                continue
            try:
                borrar(destino)
            except OSError:
                fallos.append(nombre)
        return fallos

    # ---------- configuración ----------
    def leer_env(self):
        valores = {}
        archivo = self.backend / ".env"
        if archivo.is_file():
            for linea in archivo.read_text(encoding="utf-8").splitlines():
                if "=" in linea and not linea.lstrip().startswith("#"):
                    clave, _, valor = linea.partition("=")
                    valores[clave.strip()] = valor.strip()
        return valores

    def guardar_env(self, clave, valor):
        """Escribe o reemplaza una variable en backend/.env, sin tocar las demás."""
        archivo = self.backend / ".env"
        lineas = archivo.read_text(encoding="utf-8").splitlines() if archivo.is_file() else []
        nueva = f"{clave}={valor}"
        for i, linea in enumerate(lineas):
            if not linea.lstrip().startswith("#") and linea.partition("=")[0].strip() == clave:
                lineas[i] = nueva
                break
        else:
            lineas.append(nueva)
        archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    def preparar_env(self):
        archivo = self.backend / ".env"
        if archivo.is_file():
            return
        archivo.write_text(
            "# Generado por Agricolix. No se sube a Git.\n"
            f"DB_HOST=127.0.0.1\nDB_PORT={PUERTO_BD}\nDB_NAME={NOMBRE_BD}\nDB_USER=postgres\n"
            f"DB_PASSWORD={secrets.token_urlsafe(24)}\n"
            "COOKIE_SECURE=false\n"
            "# Clave del asistente de IA (OpenAI). Sin ella, el resto del sistema funciona igual.\n"
            "OPENAI_API_KEY=\n", encoding="utf-8")

    def bd_propia(self):
        """True si el sistema usa el PostgreSQL incluido; False si .env apunta a otra base."""
        env = self.leer_env()
        return env.get("DB_HOST", "127.0.0.1") == "127.0.0.1" and env.get("DB_PORT") == str(PUERTO_BD)

    def entorno(self):
        variables = os.environ.copy()
        variables.update(AGRICOLIX_LOCAL=str(self.local), PG_BIN=str(self.pgbin),
                         PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PGCLIENTENCODING="UTF8")
        return variables

    # ---------- clave de OpenAI ----------
    def clave_configurada(self):
        valor = self.leer_env().get("OPENAI_API_KEY", "")
        return bool(valor) and not valor.startswith("escribir_")

    def clave_pendiente(self):
        """True si falta la clave y la persona todavía no eligió omitirla."""
        return not self.clave_configurada() and not (self.local / "clave-omitida").exists()

    def guardar_clave(self, clave):
        """Guarda la clave en .env. Una clave vacía significa 'omitir por ahora'."""
        self.local.mkdir(parents=True, exist_ok=True)
        if clave:
            self.guardar_env("OPENAI_API_KEY", clave)
            (self.local / "clave-omitida").unlink(missing_ok=True)
        else:
            (self.local / "clave-omitida").write_text("1", encoding="utf-8")

    # ---------- componentes ----------
    def revisar_componentes(self, base=None):
        """Comprueba que estén Python, PostgreSQL y la interfaz compilada (en 'base' o en agricolix data)."""
        base = base or self.datos
        faltan = [n for n, r in (("Python", base / "runtime" / "python" / ".listo"),
                                 ("PostgreSQL", base / "runtime" / "postgres" / ".listo"),
                                 ("la interfaz", base / "frontend" / "dist" / "index.html")) if not r.is_file()]
        if faltan:
            raise ErrorAgricolix("Faltan componentes de Agricolix (" + ", ".join(faltan) + "). " + SOPORTE)

    def descargar(self, url, destino, etiqueta):
        """Descarga con reintentos. Si la conexión se corta, sigue desde donde quedó (también al reabrir)."""
        if destino.is_file():
            return
        destino.parent.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_name(destino.name + ".parte")
        for intento in range(1, INTENTOS_DESCARGA + 1):
            try:
                self.descargar_tramo(url, parcial, etiqueta)
                parcial.replace(destino)
                return
            except (OSError, http.client.HTTPException):
                if intento == INTENTOS_DESCARGA:
                    break
                self.avisar(f"Se cortó la conexión. Reintentando ({intento} de {INTENTOS_DESCARGA - 1})...")
                time.sleep(ESPERAS_DESCARGA[min(intento, len(ESPERAS_DESCARGA)) - 1])
        # El archivo parcial se conserva: al volver a abrir Agricolix la descarga continúa.
        raise ErrorAgricolix("No se pudieron descargar los componentes de Agricolix. "
                             "Comprueba la conexión a internet y vuelve a abrirlo: la descarga continúa "
                             "donde quedó. " + SOPORTE)

    def descargar_tramo(self, url, parcial, etiqueta):
        tengo = parcial.stat().st_size if parcial.is_file() else 0
        pedido = urllib.request.Request(url, headers={"Range": f"bytes={tengo}-"} if tengo else {})
        try:
            respuesta = urllib.request.urlopen(pedido, timeout=60)
        except urllib.error.HTTPError as e:
            if e.code == 416:  # el rango ya no sirve: se empieza de cero
                parcial.unlink(missing_ok=True)
            raise
        with respuesta:
            if tengo and respuesta.status != 206:  # el servidor no permite reanudar: de cero
                tengo = 0
            largo = int(respuesta.headers.get("Content-Length") or 0)
            total = tengo + largo if largo else 0
            leido = ultimo = tengo
            with open(parcial, "ab" if tengo else "wb") as salida:
                while bloque := respuesta.read(1 << 20):
                    salida.write(bloque)
                    leido += len(bloque)
                    if leido - ultimo >= 8 << 20:
                        ultimo = leido
                        self.avisar(f"Descargando {etiqueta}... {leido >> 20} de {total >> 20} MB" if total
                                    else f"Descargando {etiqueta}... {leido >> 20} MB")
            if total and leido != total:
                raise OSError("descarga incompleta")

    def abrir_zip(self, archivo):
        try:
            return zipfile.ZipFile(archivo)
        except zipfile.BadZipFile:
            archivo.unlink(missing_ok=True)
            raise ErrorAgricolix("Un archivo descargado quedó dañado. Vuelve a abrir Agricolix para "
                                 "descargarlo de nuevo. " + SOPORTE)

    def instalar_python(self, base):
        runtime = base / "runtime"
        destino = runtime / "python"
        version = platform.python_version()
        archivo = runtime / "_descargas" / f"python-{version}-embed-amd64.zip"
        self.descargar(f"https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip",
                       archivo, "Python")
        shutil.rmtree(destino, ignore_errors=True)
        with self.abrir_zip(archivo) as z:
            z.extractall(destino)
        corto = "".join(version.split(".")[:2])
        # ..\..\backend: el Python portable no agrega solo la carpeta del script a sus rutas.
        (destino / f"python{corto}._pth").write_text(
            f"python{corto}.zip\n.\nLib\\site-packages\n..\\..\\backend\nimport site\n", encoding="utf-8")
        instalador = runtime / "_descargas" / "get-pip.py"
        self.descargar("https://bootstrap.pypa.io/get-pip.py", instalador, "el instalador de librerías")
        self.avisar("Instalando las librerías de Python (puede tardar varios minutos)...")
        python = destino / "python.exe"
        comunes = ["--no-warn-script-location", "--disable-pip-version-check"]
        registro = runtime / "instalacion.log"
        for orden in ([python, instalador, *comunes],
                      [python, "-m", "pip", "install", *comunes, "--no-compile",
                       "-r", base / "backend" / "requirements.txt", "-r", base / "backend" / "requirements_ia.txt"]):
            r = subprocess.run([str(a) for a in orden], capture_output=True, text=True, env=self.entorno(),
                               creationflags=SIN_VENTANA, timeout=3600)
            with open(registro, "a", encoding="utf-8") as f:
                f.write((r.stdout or "") + (r.stderr or ""))
            if r.returncode:
                shutil.rmtree(destino, ignore_errors=True)
                raise ErrorAgricolix("No se pudieron instalar las librerías de Python. "
                                     "Comprueba la conexión a internet e inténtalo de nuevo. " + SOPORTE)
        (destino / ".listo").write_text("1", encoding="utf-8")

    def instalar_postgres(self, base):
        runtime = base / "runtime"
        destino = runtime / "postgres"
        archivo = runtime / "_descargas" / f"postgresql-{VERSION_POSTGRES}-windows-x64-binaries.zip"
        self.descargar(f"https://get.enterprisedb.com/postgresql/postgresql-{VERSION_POSTGRES}-windows-x64-binaries.zip",
                       archivo, "la base de datos")
        self.avisar("Instalando la base de datos...")
        shutil.rmtree(destino, ignore_errors=True)
        # Solo lo necesario para correr el servidor: se omiten pgAdmin, StackBuilder, documentación, etc.
        with self.abrir_zip(archivo) as z:
            for entrada in z.infolist():
                partes = Path(entrada.filename).parts
                if len(partes) > 2 and partes[0] == "pgsql" and partes[1] in ("bin", "lib", "share") \
                        and not entrada.is_dir():
                    salida = destino.joinpath(*partes[1:])
                    salida.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(entrada) as origen, open(salida, "wb") as f:
                        shutil.copyfileobj(origen, f)
        (destino / ".listo").write_text("1", encoding="utf-8")

    def instalar_componentes(self, base=None):
        """Descarga e instala lo que falte. Se hace antes de eliminar o mover cualquier cosa."""
        base = base or self.datos
        runtime = base / "runtime"
        if not (runtime / "python" / ".listo").is_file():
            self.instalar_python(base)
        if not (runtime / "postgres" / ".listo").is_file():
            self.instalar_postgres(base)
        # Las descargas se conservan si algo falla, para poder continuar; aquí ya no hacen falta.
        shutil.rmtree(runtime / "_descargas", ignore_errors=True)
        self.revisar_componentes(base)

    # ---------- base de datos ----------
    def ejecutar(self, args, env=None, registro=None):
        salida = open(registro, "ab") if registro else subprocess.PIPE
        try:
            return subprocess.run([str(a) for a in args], env=env or self.entorno(), text=True,
                                  encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, stdout=salida,
                                  stderr=subprocess.STDOUT if registro else subprocess.PIPE,
                                  creationflags=SIN_VENTANA, timeout=300)
        finally:
            if registro:
                salida.close()

    def postgres_propio_activo(self):
        """True si el PostgreSQL incluido en Agricolix está encendido."""
        if not (self.pgdatos / "PG_VERSION").is_file():
            return False
        return self.ejecutar([self.pgbin / "pg_ctl.exe", "status", "-D", self.pgdatos]).returncode == 0

    def revisar_puerto(self, puerto, propio):
        """Avisa con claridad si otro programa ocupa un puerto que Agricolix necesita."""
        if puerto_abierto(puerto) and not propio:
            raise ErrorAgricolix(f"El puerto {puerto} está ocupado por otro programa. "
                                 "Ciérralo e inténtalo de nuevo. " + SOPORTE)

    def preparar_postgres(self):
        if not self.bd_propia():
            return
        env = self.entorno()
        env["PGPASSWORD"] = self.leer_env()["DB_PASSWORD"]
        log = self.local / "postgres-sistema.log"
        if not (self.pgdatos / "PG_VERSION").is_file():
            self.revisar_puerto(PUERTO_BD, False)
            self.avisar("Creando la base de datos (solo la primera vez)...")
            self.pgdatos.parent.mkdir(parents=True, exist_ok=True)
            clave = self.local / "pg.tmp"
            clave.write_text(env["PGPASSWORD"], encoding="utf-8")
            try:
                r = self.ejecutar([self.pgbin / "initdb.exe", "-D", self.pgdatos, "-U", "postgres",
                                   "-A", "scram-sha-256", "-E", "UTF8", f"--pwfile={clave}"], env, log)
            finally:
                clave.unlink(missing_ok=True)
            if r.returncode:
                shutil.rmtree(self.pgdatos, ignore_errors=True)
                raise ErrorAgricolix("No se pudo crear la base de datos. " + SOPORTE)
            with open(self.pgdatos / "postgresql.conf", "a", encoding="utf-8") as conf:
                conf.write(f"\nport = {PUERTO_BD}\nlisten_addresses = '127.0.0.1'\nmax_connections = 50\n")
        if not self.postgres_propio_activo():
            self.revisar_puerto(PUERTO_BD, False)
            self.avisar("Encendiendo la base de datos...")
            r = self.ejecutar([self.pgbin / "pg_ctl.exe", "start", "-D", self.pgdatos, "-w", "-t", "60",
                               "-l", self.local / "postgres.log"], env, log)
            if r.returncode or not puerto_abierto(PUERTO_BD):
                raise ErrorAgricolix("No se pudo encender la base de datos. " + SOPORTE)
        conexion = ["-h", "127.0.0.1", "-p", PUERTO_BD, "-U", "postgres"]
        r = self.ejecutar([self.pgbin / "psql.exe", *conexion, "-d", "postgres", "-tAc",
                           f"SELECT 1 FROM pg_database WHERE datname='{NOMBRE_BD}'"], env)
        if (r.stdout or "").strip() != "1":
            self.avisar("Preparando las tablas del sistema...")
            if self.ejecutar([self.pgbin / "createdb.exe", *conexion, NOMBRE_BD], env, log).returncode or \
               self.ejecutar([self.pgbin / "psql.exe", *conexion, "-d", NOMBRE_BD, "-v", "ON_ERROR_STOP=1",
                              "-f", self.backend / "esquema.sql"], env, log).returncode:
                raise ErrorAgricolix("No se pudieron crear las tablas. " + SOPORTE)

    def detener_postgres(self):
        if self.bd_propia() and (self.pgdatos / "PG_VERSION").is_file() and puerto_abierto(PUERTO_BD):
            self.ejecutar([self.pgbin / "pg_ctl.exe", "stop", "-D", self.pgdatos, "-m", "fast", "-w"],
                          registro=self.local / "postgres-sistema.log")

    def usar_base(self, funcion):
        """Ejecuta 'funcion' con la base encendida; si se encendió solo para esto, la deja apagada."""
        estaba_encendida = puerto_abierto(PUERTO_BD) or not self.bd_propia()
        self.preparar_postgres()
        try:
            return funcion()
        finally:
            if not estaba_encendida and not self.encendido():
                self.detener_postgres()

    # ---------- cuenta de acceso ----------
    def script_admin(self, argumento, extra=None):
        env = self.entorno()
        env.update(extra or {})
        return subprocess.run([str(self.python), "crear_admin.py", argumento], cwd=self.backend, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              creationflags=SIN_VENTANA, timeout=300)

    def preparar_base(self):
        """Crea las tablas y migraciones del sistema (la base debe estar encendida)."""
        self.avisar("Preparando el sistema...")
        r = self.script_admin("--preparar")
        (self.local / "preparacion.log").write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
        if r.returncode:
            raise ErrorAgricolix("No se pudo preparar el sistema. Comprueba la base de datos. " + SOPORTE)

    def consultar_sin_usuarios(self):
        r = self.script_admin("--hay-usuarios")
        if r.returncode:
            raise ErrorAgricolix("No se pudo revisar la cuenta de acceso. " + SOPORTE)
        return (r.stdout or "").strip() == "no"

    def sin_usuarios(self):
        def consulta():
            self.preparar_base()
            return self.consultar_sin_usuarios()
        return self.usar_base(consulta)

    def crear_cuenta(self, usuario, password):
        """Crea el primer administrador con el usuario y la contraseña que eligió la persona."""
        usuario = usuario.strip().lower()
        problema = validar_cuenta(usuario, password)
        if problema:
            raise ErrorAgricolix(problema)

        def crear():
            self.preparar_base()
            return self.script_admin("--crear", {"AGRICOLIX_ADMIN_USUARIO": usuario,
                                                 "AGRICOLIX_ADMIN_PASSWORD": password})
        r = self.usar_base(crear)
        if r.returncode in (2, 3):
            # Mensajes pensados para la persona (contraseña corta, ya existe una cuenta...).
            raise ErrorAgricolix((r.stdout or "").strip())
        if r.returncode:
            raise ErrorAgricolix("No se pudo crear la cuenta. " + SOPORTE)

    # ---------- primera apertura ----------
    def preparar(self):
        """Primera apertura: ordena la carpeta y deja lista la base de datos, sin encender el sistema."""
        fallos = []
        if self.necesita_ordenar():
            fallos = self.ordenar()
        else:
            self.instalar_componentes()
        self.local.mkdir(parents=True, exist_ok=True)
        self.preparar_env()
        self.usar_base(self.preparar_base)
        return fallos

    # ---------- encendido y apagado ----------
    def encendido(self):
        return responde(URL_API) and responde(URL_WEB)

    def lanzar(self, nombre, args, cwd):
        salida = open(self.local / f"{nombre}.log", "ab")
        error = open(self.local / f"{nombre}-error.log", "ab")
        proceso = subprocess.Popen([str(a) for a in args], cwd=cwd, env=self.entorno(),
                                   stdin=subprocess.DEVNULL, stdout=salida, stderr=error,
                                   creationflags=SEPARADO)
        return {"nombre": nombre, "pid": proceso.pid}

    def iniciar(self):
        self.instalar_componentes()
        self.local.mkdir(parents=True, exist_ok=True)
        if self.encendido():
            self.avisar("El sistema ya estaba encendido.")
            return
        self.revisar_puerto(PUERTO_API, responde(URL_API))
        self.revisar_puerto(PUERTO_WEB, responde(URL_WEB))
        self.preparar_env()
        self.preparar_postgres()
        self.preparar_base()
        if self.consultar_sin_usuarios():
            raise FaltaCuenta("Falta crear la cuenta de acceso.")
        self.avisar("Encendiendo Agricolix...")
        procesos = []
        if not responde(URL_API):
            procesos.append(self.lanzar("backend", [self.python, "-m", "uvicorn", "main:app", "--host",
                                                    "127.0.0.1", "--port", PUERTO_API], self.backend))
        if not responde(URL_WEB):
            procesos.append(self.lanzar("web", [self.python, "servidor_web.py", self.dist],
                                        self.datos / "launcher"))
        self.registro.write_text(json.dumps(procesos), encoding="utf-8")
        if not esperar(self.encendido, 120):
            raise ErrorAgricolix("El sistema no respondió a tiempo. " + SOPORTE)

    def proceso_vivo(self, pid):
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True,
                           text=True, creationflags=SIN_VENTANA)
        return "python" in r.stdout.lower()

    def apagar(self):
        self.avisar("Apagando Agricolix...")
        if self.registro.is_file():
            for reg in reversed(json.loads(self.registro.read_text(encoding="utf-8") or "[]")):
                if self.proceso_vivo(reg["pid"]):
                    subprocess.run(["taskkill", "/PID", str(reg["pid"]), "/T", "/F"],
                                   capture_output=True, creationflags=SIN_VENTANA)
            self.registro.unlink(missing_ok=True)
        self.detener_postgres()

    def reiniciar(self):
        self.apagar()
        self.iniciar()

    # ---------- acceso directo en el escritorio ----------
    def powershell(self, script):
        env = os.environ.copy()
        env["AGX_EXE"] = str(self.exe or "")
        return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              creationflags=SIN_VENTANA, timeout=60)

    def crear_acceso_directo(self):
        """Crea 'Agricolix' en el escritorio de la persona, con el ícono del programa."""
        if not self.exe:
            raise ErrorAgricolix("El acceso directo solo se puede crear desde Agricolix.exe.")
        r = self.powershell(
            "$d=[Environment]::GetFolderPath('Desktop'); $a=Join-Path $d 'Agricolix.lnk'; "
            "$l=(New-Object -ComObject WScript.Shell).CreateShortcut($a); $l.TargetPath=$env:AGX_EXE; "
            "$l.WorkingDirectory=Split-Path $env:AGX_EXE; $l.IconLocation=$env:AGX_EXE; "
            "$l.Description='Agricolix'; $l.Save(); Write-Output $a")
        if r.returncode:
            raise ErrorAgricolix("No se pudo crear el acceso directo. " + SOPORTE)
        return (r.stdout or "").strip()

    def quitar_acceso_directo(self):
        """Borra el acceso directo del escritorio, solo si apunta a este Agricolix.exe."""
        if self.exe:
            self.powershell(
                "$d=[Environment]::GetFolderPath('Desktop'); $a=Join-Path $d 'Agricolix.lnk'; "
                "if (Test-Path $a) { $t=(New-Object -ComObject WScript.Shell).CreateShortcut($a).TargetPath; "
                "if ($t -eq $env:AGX_EXE) { Remove-Item $a -Force } }")

    # ---------- restaurar (solo desarrolladores) ----------
    def puede_restaurar(self):
        return self.datos.is_dir() and not (self.raiz / "FASE 2" / "DonaLaura").exists()

    def hay_git(self):
        return bool(shutil.which("git")) and (self.raiz / ".git").is_dir()

    def restaurar(self):
        """Deja la carpeta como estaba antes de abrir Agricolix por primera vez.

        Devuelve 'agricolix data' a FASE 2/DonaLaura y recupera desde Git lo que el orden eliminó.
        Solo se borra lo que Agricolix generó con su propia base; si .env apunta a otra base,
        sus datos y respaldos se conservan.
        """
        git = shutil.which("git")
        if not git or not (self.raiz / ".git").is_dir():
            raise ErrorAgricolix("Restaurar necesita Git instalado y la carpeta .git del proyecto.")
        if not self.puede_restaurar():
            raise ErrorAgricolix("No hay nada que restaurar: la carpeta ya está en su estado original.")
        self.apagar()
        self.quitar_acceso_directo()
        self.avisar("Restaurando la carpeta del proyecto...")
        env = self.backend / ".env"
        generado = env.is_file() and env.read_text(encoding="utf-8").startswith("# Generado por Agricolix")
        if generado or not env.is_file():
            shutil.rmtree(self.datos / "datos", ignore_errors=True)
            shutil.rmtree(self.local, ignore_errors=True)
            if generado:
                env.unlink()
        elif self.local.is_dir() and not (self.raiz / ".local").exists():
            shutil.move(str(self.local), str(self.raiz / ".local"))
        destino = self.raiz / "FASE 2" / "DonaLaura"
        destino.parent.mkdir(exist_ok=True)
        try:
            self.datos.rename(destino)
        except OSError:
            raise ErrorAgricolix("No se pudo restaurar la carpeta. Cierra los programas que tengan "
                                 "archivos del proyecto abiertos e inténtalo de nuevo.")
        # Solo se recuperan los archivos que faltan; los cambios sin guardar en Git no se tocan.
        faltantes = subprocess.run([git, "-C", str(self.raiz), "ls-files", "-z", "--deleted"],
                                   capture_output=True, creationflags=SIN_VENTANA).stdout
        if faltantes:
            r = subprocess.run([git, "-C", str(self.raiz), "restore", "--pathspec-from-file=-",
                                "--pathspec-file-nul"], input=faltantes, capture_output=True,
                               creationflags=SIN_VENTANA)
            if r.returncode:
                raise ErrorAgricolix("La carpeta volvió a su lugar, pero Git no pudo recuperar los documentos. "
                                     "Ejecuta «git restore .» en la carpeta del proyecto.")


# ==========================================================
# VENTANA
# ==========================================================
VERDE = "#2f6b3a"
VERDE_OSCURO = "#25552e"
FONDO = "#f4f7f2"


def instancia_unica():
    """Evita abrir dos ventanas de Agricolix. Devuelve el candado, o None si ya había otra abierta."""
    import ctypes
    kernel, usuario = ctypes.windll.kernel32, ctypes.windll.user32
    candado = kernel.CreateMutexW(None, False, "Local\\Agricolix.Lanzador")
    if kernel.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        existente = usuario.FindWindowW(None, "Agricolix")
        if existente:
            usuario.ShowWindow(existente, 9)
            usuario.SetForegroundWindow(existente)
        return None
    return candado


def poner_icono(ventana_tk):
    try:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        ventana_tk.iconbitmap(str(base / "agricolix.ico"))
    except Exception:
        pass  # sin ícono la ventana funciona igual


def ventana(sistema):
    import tkinter as tk
    from tkinter import messagebox, ttk

    candado = instancia_unica()
    if candado is None:
        return
    raiz = tk.Tk()
    raiz.title("Agricolix")
    poner_icono(raiz)
    raiz.resizable(False, False)
    raiz.configure(bg=FONDO)
    mensajes = queue.Queue()
    texto = tk.StringVar(value="")
    ocupado = {"valor": False}

    def centrar(ventana_tk, ancho=None, alto=None):
        ventana_tk.update_idletasks()
        # Sin medidas explícitas, la ventana se ajusta a su contenido (ya dibujado).
        ancho = ancho or ventana_tk.winfo_reqwidth()
        alto = alto or ventana_tk.winfo_reqheight()
        x = (ventana_tk.winfo_screenwidth() - ancho) // 2
        y = (ventana_tk.winfo_screenheight() - alto) // 3
        ventana_tk.geometry(f"{ancho}x{alto}+{x}+{y}")

    centrar(raiz, 460, 490 if sistema.hay_git() else 460)

    tk.Label(raiz, text="Agricolix", font=("Segoe UI", 26, "bold"), fg=VERDE, bg=FONDO).pack(pady=(24, 0))
    tk.Label(raiz, text="Gestión agrícola de Doña Laura", font=("Segoe UI", 10), fg="#555", bg=FONDO).pack()
    indicador = tk.Label(raiz, text="", font=("Segoe UI", 11, "bold"), bg=FONDO)
    indicador.pack(pady=(20, 2))
    tk.Label(raiz, textvariable=texto, font=("Segoe UI", 9), fg="#444", bg=FONDO, wraplength=400,
             justify="center", height=3).pack()
    zona_barra = tk.Frame(raiz, height=24, bg=FONDO)
    zona_barra.pack(pady=(0, 10))
    zona_barra.pack_propagate(False)
    barra = ttk.Progressbar(zona_barra, mode="indeterminate", length=320)
    boton_iniciar = tk.Button(raiz, text="Iniciar sistema", font=("Segoe UI", 12, "bold"), bg=VERDE, fg="white",
                              activebackground=VERDE_OSCURO, activeforeground="white", relief="flat",
                              width=30, height=2, cursor="hand2")
    boton_abrir = tk.Button(raiz, text="Abrir Agricolix en el navegador", font=("Segoe UI", 11), bg="#dfe9db",
                            relief="flat", width=30, height=1, cursor="hand2", state="disabled")
    boton_apagar = tk.Button(raiz, text="Apagar sistema", font=("Segoe UI", 11), bg="#e4ded8", relief="flat",
                             width=30, height=1, cursor="hand2")
    boton_clave = tk.Button(raiz, text="Clave de OpenAI (asistente de IA)", font=("Segoe UI", 9), relief="flat",
                            bg=FONDO, fg=VERDE, cursor="hand2")
    boton_restaurar = tk.Button(raiz, text="Restaurar (solo desarrolladores)", font=("Segoe UI", 8), relief="flat",
                                bg=FONDO, fg="#8a4b2f", cursor="hand2")
    boton_iniciar.pack(pady=(4, 8))
    boton_abrir.pack(pady=4)
    boton_apagar.pack(pady=4)
    boton_clave.pack(pady=(12, 0))
    if sistema.hay_git():
        boton_restaurar.pack(pady=(8, 0))
    sistema.avisar = mensajes.put

    def aplicar_estado(encendido):
        if encendido:
            indicador.config(text="● Sistema encendido", fg=VERDE)
        else:
            indicador.config(text="● Sistema apagado", fg="#9a5b2f")
        boton_abrir.config(state="normal" if encendido and not ocupado["valor"] else "disabled")

    def estado_inicial():
        # La consulta va en otro hilo: si el sistema tarda en responder, la ventana no se congela.
        threading.Thread(target=lambda: mensajes.put(("estado", sistema.encendido())), daemon=True).start()

    def refrescar():
        if not ocupado["valor"]:
            estado_inicial()
        raiz.after(5000, refrescar)

    def bloquear(si):
        ocupado["valor"] = si
        for b in (boton_iniciar, boton_abrir, boton_apagar, boton_clave, boton_restaurar):
            b.config(state="disabled" if si else "normal")
        if si:
            barra.pack(pady=3)
            barra.start(12)
        else:
            barra.stop()
            barra.pack_forget()

    def trabajo(accion):
        def correr():
            try:
                accion()
                mensajes.put(("fin", None))
            except FaltaCuenta:
                mensajes.put(("cuenta", True))
            except ErrorAgricolix as e:
                mensajes.put(("error", str(e)))
            except Exception as e:
                mensajes.put(("error", f"Ocurrió un problema inesperado: {e}\n\n{SOPORTE}"))
        bloquear(True)
        threading.Thread(target=correr, daemon=True).start()

    # ---------- formulario de configuración ----------
    def formulario(pedir_cuenta, pedir_clave, al_enviar):
        d = tk.Toplevel(raiz)
        poner_icono(d)
        d.title("Agricolix - Configuración inicial" if pedir_cuenta else "Agricolix - Clave de OpenAI")
        d.configure(bg=FONDO, padx=26, pady=18)
        d.resizable(False, False)
        d.transient(raiz)
        d.grab_set()
        error = tk.StringVar()
        campos = {}

        def campo(titulo, secreto=False):
            tk.Label(d, text=titulo, font=("Segoe UI", 9, "bold"), bg=FONDO, anchor="w").pack(fill="x", pady=(8, 0))
            entrada = tk.Entry(d, font=("Segoe UI", 11), width=34, show="•" if secreto else "")
            entrada.pack(fill="x")
            return entrada

        if pedir_cuenta:
            tk.Label(d, text="Crea tu cuenta de acceso", font=("Segoe UI", 14, "bold"), fg=VERDE, bg=FONDO).pack(anchor="w")
            tk.Label(d, text="Elige el usuario y la contraseña con los que vas a entrar al sistema.\n"
                             "Guárdalos en un lugar seguro: Agricolix no puede recuperarlos.",
                     font=("Segoe UI", 9), fg="#555", bg=FONDO, justify="left").pack(anchor="w")
            campos["usuario"] = campo("Usuario (letras, números, punto o guion; mínimo 3)")
            campos["clave1"] = campo("Contraseña (mínimo 12 caracteres)", True)
            campos["clave2"] = campo("Repite la contraseña", True)

            def mostrar():
                for k in ("clave1", "clave2"):
                    campos[k].config(show="" if ver.get() else "•")
            ver = tk.BooleanVar()
            tk.Checkbutton(d, text="Mostrar contraseña", variable=ver, command=mostrar, bg=FONDO,
                           font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
            campos["usuario"].focus_set()
        else:
            tk.Label(d, text="Clave de OpenAI", font=("Segoe UI", 14, "bold"), fg=VERDE, bg=FONDO).pack(anchor="w")
        if pedir_clave:
            if pedir_cuenta:
                tk.Frame(d, height=1, bg="#cfd8cb").pack(fill="x", pady=(14, 0))
            tk.Label(d, text="El asistente de IA necesita una clave de OpenAI. Es opcional: sin ella el resto del "
                             "sistema funciona igual y puedes agregarla después con el botón «Clave de OpenAI».",
                     font=("Segoe UI", 9), fg="#555", bg=FONDO, justify="left", wraplength=360).pack(anchor="w", pady=(8, 0))
            campos["openai"] = campo("Clave de OpenAI (empieza con sk-)", True)
            if not pedir_cuenta:
                campos["openai"].focus_set()
        tk.Label(d, textvariable=error, font=("Segoe UI", 9), fg="#b03a2e", bg=FONDO, wraplength=360,
                 justify="left").pack(anchor="w", pady=(8, 0))

        def enviar(_evento=None):
            datos = {}
            if pedir_cuenta:
                usuario, clave = campos["usuario"].get().strip().lower(), campos["clave1"].get()
                problema = validar_cuenta(usuario, clave)
                if not problema and clave != campos["clave2"].get():
                    problema = "Las contraseñas no coinciden."
                if problema:
                    error.set(problema)
                    return
                datos.update(usuario=usuario, password=clave)
            if pedir_clave:
                clave_ia = campos["openai"].get().strip()
                problema = validar_clave_openai(clave_ia)
                if problema:
                    error.set(problema)
                    return
                datos["clave_openai"] = clave_ia
            d.destroy()
            al_enviar(datos)

        botones = tk.Frame(d, bg=FONDO)
        botones.pack(fill="x", pady=(10, 0))
        tk.Button(botones, text="Crear cuenta y continuar" if pedir_cuenta else "Guardar", command=enviar,
                  font=("Segoe UI", 10, "bold"), bg=VERDE, fg="white", activebackground=VERDE_OSCURO,
                  activeforeground="white", relief="flat", padx=14, pady=5, cursor="hand2").pack(side="right")
        tk.Button(botones, text="Cancelar", command=d.destroy, font=("Segoe UI", 10), bg="#e4ded8", relief="flat",
                  padx=14, pady=5, cursor="hand2").pack(side="right", padx=(0, 8))
        d.bind("<Return>", enviar)
        centrar(d)

    # ---------- acciones ----------
    def encender():
        if sistema.necesita_ordenar():
            sistema.preparar()
        sistema.iniciar()
        webbrowser.open(URL_WEB)

    def aplicar_configuracion(datos):
        if "usuario" in datos:
            sistema.crear_cuenta(datos["usuario"], datos["password"])
        if "clave_openai" in datos:
            sistema.guardar_clave(datos["clave_openai"])
        sistema.iniciar()
        webbrowser.open(URL_WEB)

    def guardar_solo_clave(datos):
        if not datos["clave_openai"]:
            return
        sistema.guardar_clave(datos["clave_openai"])
        if sistema.encendido():
            sistema.avisar("Aplicando la clave: se reinicia el sistema...")
            sistema.reiniciar()

    def pedir_clave():
        if not sistema.datos.is_dir():
            messagebox.showinfo("Agricolix", "Primero se prepara el sistema. Presiona «Iniciar sistema».")
            return
        sistema.preparar_env()
        if sistema.clave_configurada() and not messagebox.askyesno(
                "Clave de OpenAI", "Ya hay una clave guardada. ¿Quieres reemplazarla por otra?"):
            return
        formulario(False, True, lambda datos: trabajo(lambda: guardar_solo_clave(datos)))

    def primera_apertura():
        fallos = sistema.preparar()
        if fallos:
            mensajes.put("No se pudieron eliminar: " + ", ".join(fallos))
        mensajes.put(("primera", sistema.sin_usuarios()))

    def primera_configuracion(sin_cuenta):
        if sistema.exe and messagebox.askyesno(
                "Acceso directo", "¿Quieres un acceso directo a Agricolix en el escritorio?"):
            try:
                sistema.crear_acceso_directo()
            except ErrorAgricolix as e:
                messagebox.showwarning("Agricolix", str(e))
        # Si la cuenta ya existe y solo falta la clave, el formulario pide únicamente la clave.
        if sin_cuenta or sistema.clave_pendiente():
            formulario(sin_cuenta, sistema.clave_pendiente(),
                       lambda datos: trabajo(lambda: aplicar_configuracion(datos)))

    def pedir_restauracion():
        if not sistema.puede_restaurar():
            messagebox.showinfo("Restaurar", "No hay nada que restaurar: la carpeta ya está en su estado original.")
            return
        if messagebox.askyesno(
                "Restaurar (solo desarrolladores)",
                "Esto deja la carpeta como estaba antes de abrir Agricolix por primera vez.\n\n"
                "Se apaga el sistema, se elimina la base de datos de prueba y los accesos que Agricolix "
                "generó, y se recuperan desde Git los documentos que se habían eliminado. "
                "Si tu .env usa otra base de datos, esa no se toca.\n\n¿Continuar?"):
            trabajo(sistema.restaurar)

    def revisar():
        while not mensajes.empty():
            m = mensajes.get()
            if isinstance(m, tuple) and m[0] == "estado":
                aplicar_estado(m[1])
            elif isinstance(m, tuple):
                bloquear(False)
                texto.set("")
                estado_inicial()
                if m[0] == "error":
                    messagebox.showerror("Agricolix", m[1])
                elif m[0] == "primera":
                    primera_configuracion(m[1])
                elif m[0] == "cuenta":
                    formulario(m[1], sistema.clave_pendiente(),
                               lambda datos: trabajo(lambda: aplicar_configuracion(datos)))
            else:
                texto.set(m)
        raiz.after(300, revisar)

    def cerrar():
        if ocupado["valor"] and not messagebox.askyesno(
                "Agricolix", "Hay una tarea en curso. Si cierras ahora puede quedar incompleta "
                             "y tendrás que repetirla.\n\n¿Cerrar de todos modos?"):
            return
        raiz.destroy()

    boton_iniciar.config(command=lambda: trabajo(encender))
    boton_abrir.config(command=lambda: webbrowser.open(URL_WEB))
    boton_apagar.config(command=lambda: trabajo(sistema.apagar))
    boton_clave.config(command=pedir_clave)
    boton_restaurar.config(command=pedir_restauracion)
    raiz.protocol("WM_DELETE_WINDOW", cerrar)
    estado_inicial()
    # Primera vez: descarga, ordena la carpeta y prepara todo solo, sin preguntar ni pedir ningún clic.
    if sistema.necesita_ordenar():
        raiz.after(500, lambda: trabajo(primera_apertura))
    raiz.after(300, revisar)
    raiz.after(5000, refrescar)
    raiz.mainloop()


# ==========================================================
# ENTRADA
# ==========================================================
def main():
    analizador = argparse.ArgumentParser()
    analizador.add_argument("--raiz", help="Carpeta que contiene el proyecto (por defecto, la del programa)")
    grupo = analizador.add_mutually_exclusive_group()
    grupo.add_argument("--abrir", action="store_true", help="Simula la primera apertura (ordena y prepara)")
    grupo.add_argument("--ordenar", action="store_true", help="Ordena la carpeta sin ventana ni preguntas")
    grupo.add_argument("--iniciar", action="store_true")
    grupo.add_argument("--apagar", action="store_true")
    grupo.add_argument("--estado", action="store_true")
    grupo.add_argument("--crear-cuenta", action="store_true", help="Crea la cuenta con AGRICOLIX_ADMIN_USUARIO/PASSWORD")
    grupo.add_argument("--acceso-directo", action="store_true", help="Crea el acceso directo en el escritorio")
    grupo.add_argument("--restaurar", action="store_true", help="Solo desarrolladores: deshace el orden")
    argumentos = analizador.parse_args()
    raiz = argumentos.raiz or (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd())
    sistema = Sistema(raiz)
    try:
        if argumentos.ordenar:
            print("No se pudieron eliminar:", sistema.ordenar() or "nada")
        elif argumentos.abrir:
            print("No se pudieron eliminar:", sistema.preparar() or "nada")
            print("Cuenta pendiente:", "sí" if sistema.sin_usuarios() else "no")
        elif argumentos.iniciar:
            if sistema.necesita_ordenar():
                sistema.preparar()
            sistema.iniciar()
        elif argumentos.apagar:
            sistema.apagar()
        elif argumentos.estado:
            print("encendido" if sistema.encendido() else "apagado")
        elif argumentos.crear_cuenta:
            sistema.crear_cuenta(os.getenv("AGRICOLIX_ADMIN_USUARIO", ""), os.getenv("AGRICOLIX_ADMIN_PASSWORD", ""))
            print("Cuenta creada.")
        elif argumentos.acceso_directo:
            print("Acceso directo creado en:", sistema.crear_acceso_directo())
        elif argumentos.restaurar:
            sistema.restaurar()
        else:
            ventana(sistema)
    except ErrorAgricolix as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
