"""Pruebas del lanzador de Agricolix (agricolix.py, servidor_web.py y crear_admin.py).

No abren la ventana, no descargan nada de internet ni tocan la carpeta real del proyecto:
todo ocurre en carpetas temporales y con servidores locales de prueba.
Uso (desde la carpeta launcher):  python -m pytest tests -q
"""
import http.client
import importlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAUNCHER))

import agricolix  # noqa: E402
from agricolix import ErrorAgricolix, FaltaCuenta, Sistema  # noqa: E402


# ==========================================================
# AYUDAS
# ==========================================================
def servir(manejador):
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


@pytest.fixture
def servidores():
    abiertos = []

    def abrir(manejador):
        s = servir(manejador)
        abiertos.append(s)
        return s
    yield abrir
    for s in abiertos:
        s.shutdown()
        s.server_close()


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pedir(puerto, metodo, ruta, cuerpo=None, cabeceras=None):
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
    try:
        c.request(metodo, ruta, cuerpo, cabeceras or {})
        r = c.getresponse()
        return r.status, r.read(), dict((k.lower(), v) for k, v in r.getheaders())
    finally:
        c.close()


# ==========================================================
# VALIDACIONES
# ==========================================================
@pytest.mark.parametrize("usuario,password,valido", [
    ("ana", "una-clave-larga-1", True),
    ("ana.perez-2_x", "123456789012", True),
    ("ab", "una-clave-larga-1", False),          # usuario muy corto
    ("Ana", "una-clave-larga-1", False),         # mayúscula
    ("ana perez", "una-clave-larga-1", False),   # espacio
    ("ana;drop", "una-clave-larga-1", False),
    ("", "una-clave-larga-1", False),
    ("ana", "corta", False),
    ("ana", "12345678901", False),               # 11 caracteres
])
def test_validar_cuenta(usuario, password, valido):
    assert (agricolix.validar_cuenta(usuario, password) is None) == valido


@pytest.mark.parametrize("clave,valido", [
    ("", True),                       # vacía = omitir
    ("sk-" + "a" * 40, True),
    ("sk-corta", False),
    ("sk-" + "a" * 20 + " b" * 5, False),
])
def test_validar_clave_openai(clave, valido):
    assert (agricolix.validar_clave_openai(clave) is None) == valido


# ==========================================================
# .env y clave de OpenAI
# ==========================================================
@pytest.fixture
def sistema(tmp_path):
    s = Sistema(tmp_path)
    s.backend.mkdir(parents=True)
    return s


def test_guardar_env_reemplaza_solo_esa_variable(sistema):
    (sistema.backend / ".env").write_text("# nota\nA=1\nOPENAI_API_KEY=\nB=dos\n", encoding="utf-8")
    sistema.guardar_env("OPENAI_API_KEY", "sk-nueva")
    texto = (sistema.backend / ".env").read_text(encoding="utf-8")
    assert texto == "# nota\nA=1\nOPENAI_API_KEY=sk-nueva\nB=dos\n"


def test_guardar_env_agrega_si_no_existe_y_crea_archivo(sistema):
    sistema.guardar_env("X", "1")
    assert sistema.leer_env() == {"X": "1"}
    sistema.guardar_env("Y", "2")
    assert sistema.leer_env() == {"X": "1", "Y": "2"}


def test_guardar_env_ignora_variables_comentadas(sistema):
    (sistema.backend / ".env").write_text("# OPENAI_API_KEY=vieja\n", encoding="utf-8")
    sistema.guardar_env("OPENAI_API_KEY", "nueva")
    assert sistema.leer_env()["OPENAI_API_KEY"] == "nueva"
    assert "# OPENAI_API_KEY=vieja" in (sistema.backend / ".env").read_text(encoding="utf-8")


def test_preparar_env_genera_clave_aleatoria_y_no_pisa_uno_existente(sistema):
    sistema.preparar_env()
    primero = sistema.leer_env()
    assert primero["DB_PORT"] == str(agricolix.PUERTO_BD)
    assert primero["DB_HOST"] == "127.0.0.1"
    assert len(primero["DB_PASSWORD"]) >= 24
    assert (sistema.backend / ".env").read_text(encoding="utf-8").startswith("# Generado por Agricolix")
    sistema.preparar_env()
    assert sistema.leer_env() == primero


def test_dos_instalaciones_no_comparten_clave_de_base(tmp_path):
    claves = []
    for nombre in ("a", "b"):
        s = Sistema(tmp_path / nombre)
        s.backend.mkdir(parents=True)
        s.preparar_env()
        claves.append(s.leer_env()["DB_PASSWORD"])
    assert claves[0] != claves[1]


def test_bd_propia_distingue_la_base_incluida_de_la_del_desarrollador(sistema):
    sistema.preparar_env()
    assert sistema.bd_propia()
    (sistema.backend / ".env").write_text("DB_HOST=127.0.0.1\nDB_PORT=5432\n", encoding="utf-8")
    assert not sistema.bd_propia()


def test_clave_openai_pendiente_configurada_y_omitida(sistema):
    sistema.preparar_env()
    assert sistema.clave_pendiente() and not sistema.clave_configurada()
    sistema.guardar_clave("")                      # omitir por ahora
    assert not sistema.clave_pendiente()
    sistema.guardar_clave("sk-" + "a" * 40)
    assert sistema.clave_configurada() and not sistema.clave_pendiente()
    assert not (sistema.local / "clave-omitida").exists()


def test_clave_de_ejemplo_no_cuenta_como_configurada(sistema):
    (sistema.backend / ".env").write_text("OPENAI_API_KEY=escribir_tu_clave_aqui\n", encoding="utf-8")
    assert not sistema.clave_configurada()


# ==========================================================
# ORDENAR LA CARPETA
# ==========================================================
def crear_proyecto(raiz):
    """Imita el repositorio: documentos, el sistema en FASE 2/DonaLaura y archivos ajenos."""
    (raiz / "FASE 1").mkdir()
    (raiz / "FASE 1" / "informe.docx").write_text("doc1")
    (raiz / "FASE 3").mkdir()
    (raiz / "FASE 3" / "presentacion.pptx").write_text("ppt")
    (raiz / "scripts").mkdir()
    (raiz / "scripts" / "iniciar.ps1").write_text("x")
    for nombre in agricolix.ELIMINAR + agricolix.CONSERVAR:
        if nombre.endswith((".md", ".cmd")):
            (raiz / nombre).write_text(nombre)
    sistema = raiz / "FASE 2" / "DonaLaura"
    (sistema / "backend").mkdir(parents=True)
    (sistema / "backend" / "main.py").write_text("app = None")
    (sistema / "frontend" / "dist").mkdir(parents=True)
    (sistema / "frontend" / "dist" / "index.html").write_text("<html></html>")
    (raiz / "FASE 2" / "informe_final.docx").write_text("doc2")
    # Cosas de la persona que no deben tocarse
    (raiz / "Agricolix.exe").write_text("exe")
    (raiz / "mis_planillas.xlsx").write_text("datos de la persona")
    (raiz / ".git").mkdir()
    (raiz / ".git" / "HEAD").write_text("ref: refs/heads/main")


def test_necesita_ordenar(tmp_path):
    s = Sistema(tmp_path)
    assert not s.necesita_ordenar()              # carpeta vacía
    crear_proyecto(tmp_path)
    assert s.necesita_ordenar()


def test_ordenar_mueve_el_sistema_y_elimina_solo_lo_previsto(tmp_path, monkeypatch):
    crear_proyecto(tmp_path)
    s = Sistema(tmp_path)
    monkeypatch.setattr(s, "instalar_componentes", lambda base=None: None)
    fallos = s.ordenar()
    assert fallos == []
    assert (tmp_path / "agricolix data" / "backend" / "main.py").is_file()
    assert (tmp_path / "agricolix data" / "frontend" / "dist" / "index.html").is_file()
    for nombre in agricolix.ELIMINAR:
        assert not (tmp_path / nombre).exists(), nombre
    # Los accesos .cmd y sus scripts no se borran: pasan a 'agricolix data'
    for nombre in agricolix.CONSERVAR:
        assert not (tmp_path / nombre).exists(), nombre
        assert (tmp_path / "agricolix data" / nombre).exists(), nombre
    assert (tmp_path / "agricolix data" / "Iniciar Agricolix.cmd").read_text() == "Iniciar Agricolix.cmd"
    assert (tmp_path / "agricolix data" / "scripts" / "iniciar.ps1").read_text() == "x"
    # Lo que no está en la lista se respeta
    assert (tmp_path / "Agricolix.exe").is_file()
    assert (tmp_path / "mis_planillas.xlsx").read_text() == "datos de la persona"
    assert (tmp_path / ".git" / "HEAD").is_file()
    assert not s.necesita_ordenar()


def test_ordenar_no_borra_nada_si_falla_la_descarga(tmp_path, monkeypatch):
    crear_proyecto(tmp_path)
    s = Sistema(tmp_path)

    def sin_internet(base=None):
        raise ErrorAgricolix("No se pudieron descargar los componentes")
    monkeypatch.setattr(s, "instalar_componentes", sin_internet)
    with pytest.raises(ErrorAgricolix):
        s.ordenar()
    assert (tmp_path / "FASE 2" / "DonaLaura" / "backend" / "main.py").is_file()
    assert (tmp_path / "FASE 1" / "informe.docx").is_file()
    assert (tmp_path / "README.md").is_file()
    assert not (tmp_path / "agricolix data").exists()


def test_ordenar_no_borra_nada_si_no_puede_mover_la_carpeta(tmp_path, monkeypatch):
    crear_proyecto(tmp_path)
    s = Sistema(tmp_path)
    monkeypatch.setattr(s, "instalar_componentes", lambda base=None: None)

    def bloqueado(self, destino):
        raise PermissionError("archivo en uso")
    monkeypatch.setattr(Path, "rename", bloqueado)
    with pytest.raises(ErrorAgricolix, match="Cierra los programas"):
        s.ordenar()
    assert (tmp_path / "FASE 1" / "informe.docx").is_file()
    assert (tmp_path / "FASE 2" / "DonaLaura" / "backend" / "main.py").is_file()


def test_ordenar_elimina_archivos_de_solo_lectura(tmp_path, monkeypatch):
    crear_proyecto(tmp_path)
    protegido = tmp_path / "FASE 1" / "informe.docx"
    os.chmod(protegido, 0o444)
    s = Sistema(tmp_path)
    monkeypatch.setattr(s, "instalar_componentes", lambda base=None: None)
    assert s.ordenar() == []
    assert not (tmp_path / "FASE 1").exists()


def test_ordenar_no_sigue_enlaces_hacia_fuera(tmp_path, monkeypatch):
    """Si 'scripts' fuera un enlace a otra carpeta, se mueve el enlace pero no se toca su contenido."""
    ajena = tmp_path / "ajena"
    ajena.mkdir()
    (ajena / "importante.txt").write_text("no borrar")
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    crear_proyecto(raiz)
    shutil.rmtree(raiz / "scripts")
    try:
        os.symlink(ajena, raiz / "scripts", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Windows sin permiso para crear enlaces simbólicos")
    s = Sistema(raiz)
    monkeypatch.setattr(s, "instalar_componentes", lambda base=None: None)
    s.ordenar()
    assert (ajena / "importante.txt").read_text() == "no borrar"


# ==========================================================
# DESCARGAS
# ==========================================================
CONTENIDO = bytes(range(256)) * 4096   # 1 MiB


def manejador_archivo(cortes=0, admite_rango=True, siempre_falla=False, rango_invalido=False):
    estado = {"cortes": cortes, "pedidos": []}

    class M(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_GET(self):
            estado["pedidos"].append(self.headers.get("Range"))
            if siempre_falla:
                self.send_error(503)
                return
            inicio = 0
            rango = self.headers.get("Range")
            if rango and rango_invalido:
                self.send_response(416)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if rango and admite_rango:
                inicio = int(rango.split("=")[1].split("-")[0])
            parte = CONTENIDO[inicio:]
            self.send_response(206 if inicio else 200)
            self.send_header("Content-Length", str(len(parte)))
            self.end_headers()
            if estado["cortes"] > 0:
                estado["cortes"] -= 1
                self.wfile.write(parte[: len(parte) // 3])   # se corta a la mitad del camino
                self.wfile.flush()
                self.close_connection = True
                return
            self.wfile.write(parte)
    return M, estado


@pytest.fixture
def descargador(tmp_path, monkeypatch):
    monkeypatch.setattr(agricolix, "ESPERAS_DESCARGA", (0, 0, 0, 0))
    s = Sistema(tmp_path)
    s.mensajes = []
    s.avisar = s.mensajes.append
    return s


def test_descarga_completa(descargador, servidores, tmp_path):
    M, estado = manejador_archivo()
    srv = servidores(M)
    destino = tmp_path / "bajada" / "a.zip"
    descargador.descargar(f"http://127.0.0.1:{srv.server_port}/a.zip", destino, "prueba")
    assert destino.read_bytes() == CONTENIDO
    assert not destino.with_name("a.zip.parte").exists()


def test_descarga_se_reanuda_si_la_conexion_se_corta(descargador, servidores, tmp_path):
    M, estado = manejador_archivo(cortes=2)
    srv = servidores(M)
    destino = tmp_path / "a.zip"
    descargador.descargar(f"http://127.0.0.1:{srv.server_port}/a.zip", destino, "prueba")
    assert destino.read_bytes() == CONTENIDO        # sin bytes repetidos ni faltantes
    assert any(p and p.startswith("bytes=") and p != "bytes=0-" for p in estado["pedidos"])
    assert any("Reintentando" in m for m in descargador.mensajes)


def test_descarga_continua_desde_un_parcial_de_una_apertura_anterior(descargador, servidores, tmp_path):
    M, estado = manejador_archivo()
    srv = servidores(M)
    destino = tmp_path / "a.zip"
    destino.with_name("a.zip.parte").write_bytes(CONTENIDO[:300_000])
    descargador.descargar(f"http://127.0.0.1:{srv.server_port}/a.zip", destino, "prueba")
    assert destino.read_bytes() == CONTENIDO
    assert estado["pedidos"][0] == "bytes=300000-"


def test_descarga_empieza_de_cero_si_el_servidor_no_permite_reanudar(descargador, servidores, tmp_path):
    M, estado = manejador_archivo(admite_rango=False)
    srv = servidores(M)
    destino = tmp_path / "a.zip"
    destino.with_name("a.zip.parte").write_bytes(b"basura-vieja" * 1000)
    descargador.descargar(f"http://127.0.0.1:{srv.server_port}/a.zip", destino, "prueba")
    assert destino.read_bytes() == CONTENIDO


def test_descarga_se_recupera_de_un_parcial_que_el_servidor_rechaza(descargador, servidores, tmp_path):
    M, estado = manejador_archivo(rango_invalido=True)
    srv = servidores(M)
    destino = tmp_path / "a.zip"
    destino.with_name("a.zip.parte").write_bytes(b"x" * 10)
    descargador.descargar(f"http://127.0.0.1:{srv.server_port}/a.zip", destino, "prueba")
    assert destino.read_bytes() == CONTENIDO


def test_descarga_que_siempre_falla_da_error_claro_y_conserva_el_parcial(descargador, servidores, tmp_path):
    M, estado = manejador_archivo(siempre_falla=True)
    srv = servidores(M)
    destino = tmp_path / "a.zip"
    parcial = destino.with_name("a.zip.parte")
    parcial.write_bytes(b"abc")
    with pytest.raises(ErrorAgricolix, match="contacta con soporte"):
        descargador.descargar(f"http://127.0.0.1:{srv.server_port}/a.zip", destino, "prueba")
    assert len(estado["pedidos"]) == agricolix.INTENTOS_DESCARGA
    assert parcial.read_bytes() == b"abc"
    assert not destino.exists()


def test_descarga_sin_servidor_da_error_claro(descargador, tmp_path, monkeypatch):
    monkeypatch.setattr(agricolix, "INTENTOS_DESCARGA", 2)    # Windows tarda ~2 s por cada conexión rechazada
    with pytest.raises(ErrorAgricolix, match="conexión a internet"):
        descargador.descargar(f"http://127.0.0.1:{puerto_libre()}/a.zip", tmp_path / "a.zip", "prueba")


def test_descarga_no_repite_si_el_archivo_ya_existe(descargador, tmp_path):
    destino = tmp_path / "a.zip"
    destino.write_bytes(b"ya estaba")
    descargador.descargar("http://127.0.0.1:1/no-se-usa", destino, "prueba")
    assert destino.read_bytes() == b"ya estaba"


def test_zip_danado_se_borra_y_pide_reabrir(descargador, tmp_path):
    malo = tmp_path / "malo.zip"
    malo.write_bytes(b"esto no es un zip")
    with pytest.raises(ErrorAgricolix, match="dañado"):
        descargador.abrir_zip(malo)
    assert not malo.exists()


# ==========================================================
# PUERTOS Y ESTADO
# ==========================================================
def test_puerto_ocupado_avisa_cual(sistema):
    with socket.socket() as ocupante:
        ocupante.bind(("127.0.0.1", 0))
        ocupante.listen()
        puerto = ocupante.getsockname()[1]
        assert agricolix.puerto_abierto(puerto)
        with pytest.raises(ErrorAgricolix, match=str(puerto)):
            sistema.revisar_puerto(puerto, propio=False)
        sistema.revisar_puerto(puerto, propio=True)      # es nuestro: no molesta


def test_puerto_libre_no_da_error(sistema):
    p = puerto_libre()
    assert not agricolix.puerto_abierto(p)
    sistema.revisar_puerto(p, propio=False)


def test_responde_distingue_sano_de_caido(servidores):
    class Sano(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            self.send_response(200 if self.path == "/health" else 500)
            self.send_header("Content-Length", "0")
            self.end_headers()
    srv = servidores(Sano)
    base = f"http://127.0.0.1:{srv.server_port}"
    assert agricolix.responde(base + "/health")
    assert not agricolix.responde(base + "/otra")
    assert not agricolix.responde(f"http://127.0.0.1:{puerto_libre()}/health")


def test_iniciar_no_enciende_nada_si_el_puerto_esta_ocupado(sistema, monkeypatch):
    monkeypatch.setattr(sistema, "instalar_componentes", lambda base=None: None)
    monkeypatch.setattr(sistema, "encendido", lambda: False)
    monkeypatch.setattr(agricolix, "responde", lambda url: False)
    monkeypatch.setattr(agricolix, "puerto_abierto", lambda p: p == agricolix.PUERTO_API)
    lanzados = []
    monkeypatch.setattr(sistema, "lanzar", lambda *a: lanzados.append(a))
    with pytest.raises(ErrorAgricolix, match=str(agricolix.PUERTO_API)):
        sistema.iniciar()
    assert lanzados == []


def test_iniciar_pide_crear_cuenta_si_no_hay_usuarios(sistema, monkeypatch):
    for nombre in ("instalar_componentes",):
        monkeypatch.setattr(sistema, nombre, lambda base=None: None)
    monkeypatch.setattr(sistema, "encendido", lambda: False)
    monkeypatch.setattr(agricolix, "responde", lambda url: False)
    monkeypatch.setattr(agricolix, "puerto_abierto", lambda p: False)
    monkeypatch.setattr(sistema, "preparar_env", lambda: None)
    monkeypatch.setattr(sistema, "preparar_postgres", lambda: None)
    monkeypatch.setattr(sistema, "preparar_base", lambda: None)
    monkeypatch.setattr(sistema, "consultar_sin_usuarios", lambda: True)
    lanzados = []
    monkeypatch.setattr(sistema, "lanzar", lambda *a: lanzados.append(a))
    with pytest.raises(agricolix.FaltaCuenta):
        sistema.iniciar()
    assert lanzados == []


def test_faltan_componentes_lo_dice_con_nombre(sistema):
    with pytest.raises(ErrorAgricolix, match="Python.*PostgreSQL.*interfaz"):
        sistema.revisar_componentes()


# ==========================================================
# CUENTA DE ACCESO
# ==========================================================
def test_crear_cuenta_rechaza_datos_invalidos_antes_de_tocar_la_base(sistema, monkeypatch):
    monkeypatch.setattr(sistema, "usar_base", lambda f: pytest.fail("no debía abrir la base"))
    with pytest.raises(ErrorAgricolix, match="12 caracteres"):
        sistema.crear_cuenta("ana", "corta")
    with pytest.raises(ErrorAgricolix, match="usuario"):
        sistema.crear_cuenta("a", "una-clave-larga-1")


def test_la_contrasena_viaja_por_variable_de_entorno_y_no_por_argumentos(sistema, monkeypatch):
    llamadas = []

    class Resultado:
        returncode, stdout, stderr = 0, "", ""

    def falso(args, **kw):
        llamadas.append((args, kw))
        return Resultado()
    monkeypatch.setattr(agricolix.subprocess, "run", falso)
    monkeypatch.setattr(sistema, "usar_base", lambda f: f())
    monkeypatch.setattr(sistema, "preparar_base", lambda: None)
    secreta = "contrasena-muy-secreta-123"
    sistema.crear_cuenta(" Ana ", secreta)
    args, kw = llamadas[-1]
    assert secreta not in " ".join(map(str, args))
    assert kw["env"]["AGRICOLIX_ADMIN_PASSWORD"] == secreta
    assert kw["env"]["AGRICOLIX_ADMIN_USUARIO"] == "ana"      # normalizado


@pytest.mark.parametrize("codigo,salida,esperado", [
    (2, "Ya existen usuarios; no se modificó ninguna cuenta.", "Ya existen usuarios"),
    (3, "La contraseña debe tener al menos 12 caracteres.", "12 caracteres"),
    (1, "Traceback con detalles internos", "contacta con soporte"),
])
def test_crear_cuenta_traduce_los_codigos_de_salida(sistema, monkeypatch, codigo, salida, esperado):
    class Resultado:
        returncode, stdout, stderr = codigo, salida, ""
    monkeypatch.setattr(sistema, "usar_base", lambda f: Resultado())
    with pytest.raises(ErrorAgricolix, match=esperado) as e:
        sistema.crear_cuenta("ana", "una-clave-larga-1")
    if codigo == 1:
        assert "Traceback" not in str(e.value)     # no se muestran detalles internos


@pytest.mark.parametrize("usuario,password", [
    ("", "una-clave-larga-1"),
    ("a", "una-clave-larga-1"),
    ("ana perez", "una-clave-larga-1"),
    ("ana", "corta"),
    ("ana", "x" * 257),
])
def test_crear_admin_rechaza_datos_malos_antes_de_conectar(usuario, password):
    """El script del backend valida por su cuenta aunque el lanzador no lo hubiera hecho."""
    backend = LAUNCHER.parent / "backend"
    if not (backend / "crear_admin.py").is_file():
        pytest.skip("no está el backend junto al lanzador")
    env = {**os.environ, "AGRICOLIX_ADMIN_USUARIO": usuario, "AGRICOLIX_ADMIN_PASSWORD": password,
           "DB_HOST": "127.0.0.1", "DB_PORT": str(puerto_libre()), "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, "crear_admin.py", "--crear"], cwd=backend, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    if "ModuleNotFoundError" in r.stderr:
        pytest.skip("faltan dependencias del backend en este Python")
    assert r.returncode == 3, r.stderr
    assert password not in r.stdout + r.stderr or password == ""


# ==========================================================
# APAGAR
# ==========================================================
def test_apagar_cierra_los_procesos_registrados_en_orden_inverso(sistema, monkeypatch):
    sistema.local.mkdir(parents=True)
    sistema.registro.write_text(json.dumps([{"nombre": "backend", "pid": 111}, {"nombre": "web", "pid": 222}]))
    monkeypatch.setattr(sistema, "proceso_vivo", lambda pid: pid != 111)    # el 111 ya no existe
    cerrados = []

    class R:
        returncode, stdout, stderr = 0, "", ""
    monkeypatch.setattr(agricolix.subprocess, "run", lambda args, **kw: cerrados.append(args) or R())
    sistema.apagar()
    assert len(cerrados) == 1 and cerrados[0][:3] == ["taskkill", "/PID", "222"]
    assert not sistema.registro.exists()


def test_apagar_sin_registro_no_falla(sistema):
    sistema.apagar()


# ==========================================================
# RESTAURAR (con Git de verdad, en una carpeta temporal)
# ==========================================================
def git(raiz, *args):
    return subprocess.run(["git", "-C", str(raiz), "-c", "user.name=prueba", "-c", "user.email=p@p.p",
                           *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture(scope="session")
def repo_base(tmp_path_factory):
    """Repositorio de ejemplo creado UNA sola vez; cada prueba trabaja con su propia copia."""
    if not shutil.which("git"):
        pytest.skip("Git no está instalado")
    raiz = tmp_path_factory.mktemp("base") / "repo"
    raiz.mkdir()
    crear_proyecto(raiz)
    shutil.rmtree(raiz / ".git")
    (raiz / ".gitignore").write_text(".env\n.local/\nagricolix data/datos/\nFASE 2/DonaLaura/datos/\n")
    git(raiz, "init", "-q")
    git(raiz, "add", "-A")
    git(raiz, "commit", "-q", "-m", "inicial")
    assert git(raiz, "status", "--porcelain") == ""
    return raiz


@pytest.fixture
def repo(repo_base, tmp_path, monkeypatch):
    raiz = tmp_path / "repo"
    shutil.copytree(repo_base, raiz)
    s = Sistema(raiz)
    monkeypatch.setattr(s, "instalar_componentes", lambda base=None: None)
    return s


def test_restaurar_deja_el_repositorio_identico(repo):
    repo.ordenar()
    assert git(repo.raiz, "status", "--porcelain") != ""       # el orden sí cambió cosas
    repo.restaurar()
    assert git(repo.raiz, "status", "--porcelain") == ""
    assert (repo.raiz / "FASE 1" / "informe.docx").read_text() == "doc1"
    assert (repo.raiz / "FASE 2" / "DonaLaura" / "backend" / "main.py").is_file()
    assert not (repo.raiz / "agricolix data").exists()


def test_restaurar_dos_veces_seguidas_funciona(repo):
    for _ in range(2):
        repo.ordenar()
        repo.restaurar()
        assert git(repo.raiz, "status", "--porcelain") == ""


def test_restaurar_conserva_la_base_y_la_cuenta_que_genero_agricolix(repo):
    repo.ordenar()
    repo.preparar_env()
    (repo.datos / "datos" / "postgres").mkdir(parents=True)
    (repo.datos / "datos" / "postgres" / "PG_VERSION").write_text("18")
    env_antes = (repo.backend / ".env").read_text(encoding="utf-8")
    repo.restaurar()
    base = repo.raiz / "FASE 2" / "DonaLaura"
    assert (base / "datos" / "postgres" / "PG_VERSION").is_file()
    assert (base / "backend" / ".env").read_text(encoding="utf-8") == env_antes
    assert (base / ".local" / "restaurado").is_file()
    assert git(repo.raiz, "status", "--porcelain") == ""      # nada de eso ensucia Git


def test_despues_de_restaurar_se_pregunta_por_la_cuenta_y_una_vez(repo):
    repo.ordenar()
    repo.preparar_env()
    repo.restaurar()
    repo.ordenar()
    assert repo.cuenta_anterior_pendiente()
    repo.decidir_cuenta_anterior()
    assert not repo.cuenta_anterior_pendiente()


def test_no_se_pregunta_si_la_base_es_del_desarrollador(repo):
    repo.ordenar()
    (repo.backend / ".env").write_text("DB_HOST=127.0.0.1\nDB_PORT=5432\nDB_PASSWORD=mia\n")
    repo.local.mkdir(exist_ok=True)
    (repo.local / "restaurado").write_text("1")
    assert not repo.cuenta_anterior_pendiente()


def test_reemplazar_cuenta_usa_el_modo_reemplazar(sistema, monkeypatch):
    pedidos = []

    class R:
        returncode, stdout = 0, ""
    monkeypatch.setattr(sistema, "usar_base", lambda f: f())
    monkeypatch.setattr(sistema, "preparar_base", lambda: None)
    monkeypatch.setattr(sistema, "script_admin", lambda arg, extra=None: pedidos.append((arg, extra["AGRICOLIX_ADMIN_USUARIO"])) or R())
    sistema.crear_cuenta("nueva.cuenta", "una-clave-larga-1", reemplazar=True)
    sistema.crear_cuenta("otra.cuenta", "una-clave-larga-1")
    assert pedidos == [("--reemplazar", "nueva.cuenta"), ("--crear", "otra.cuenta")]


def test_restaurar_conserva_el_env_y_los_respaldos_del_desarrollador(repo):
    repo.ordenar()
    (repo.backend / ".env").write_text("DB_HOST=127.0.0.1\nDB_PORT=5432\nDB_PASSWORD=mia\n")
    (repo.local / "backups").mkdir(parents=True)
    (repo.local / "backups" / "respaldo.sql").write_text("mis datos reales")
    repo.restaurar()
    base = repo.raiz / "FASE 2" / "DonaLaura"
    assert (base / "backend" / ".env").read_text().endswith("DB_PASSWORD=mia\n")
    assert (repo.raiz / ".local" / "backups" / "respaldo.sql").read_text() == "mis datos reales"


def test_restaurar_no_pisa_cambios_sin_guardar_del_sistema(repo):
    repo.ordenar()
    (repo.backend / "main.py").write_text("app = 'editado por el desarrollador'")
    repo.restaurar()
    assert (repo.raiz / "FASE 2" / "DonaLaura" / "backend" / "main.py").read_text() == "app = 'editado por el desarrollador'"


def test_restaurar_sin_git_da_error_y_no_mueve_nada(tmp_path, monkeypatch):
    crear_proyecto(tmp_path)
    shutil.rmtree(tmp_path / ".git")
    s = Sistema(tmp_path)
    monkeypatch.setattr(s, "instalar_componentes", lambda base=None: None)
    s.ordenar()
    with pytest.raises(ErrorAgricolix, match="Git"):
        s.restaurar()
    assert (tmp_path / "agricolix data" / "backend" / "main.py").is_file()


def test_restaurar_sin_haber_ordenado_no_hace_nada(repo):
    with pytest.raises(ErrorAgricolix, match="nada que restaurar"):
        repo.restaurar()
    assert git(repo.raiz, "status", "--porcelain") == ""


# ==========================================================
# SERVIDOR WEB (servidor_web.py)
# ==========================================================
@pytest.fixture
def web(tmp_path, servidores, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>INDEX</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "assets" / "estilo.css").write_text("body{}", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("CONTRASEÑA-DEL-SISTEMA", encoding="utf-8")
    (tmp_path / "dist2").mkdir()
    (tmp_path / "dist2" / "otro.txt").write_text("VECINO", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["servidor_web.py", str(dist)])
    sys.modules.pop("servidor_web", None)
    modulo = importlib.import_module("servidor_web")

    visto = {}

    class Falso(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a): pass

        def atender(self):
            largo = int(self.headers.get("Content-Length") or 0)
            visto.update(metodo=self.command, ruta=self.path, cuerpo=self.rfile.read(largo),
                         cabeceras={k.lower(): v for k, v in self.headers.items()})
            if self.path == "/falla":
                cuerpo = b'{"detail":"no existe"}'
                self.send_response(404)
            else:
                cuerpo = b'{"ok":true}'
                self.send_response(201)
                self.send_header("Set-Cookie", "agricolix_session=abc; HttpOnly")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        do_GET = do_POST = do_PUT = do_PATCH = atender

    falso = servidores(Falso)
    modulo.BACKEND = ("127.0.0.1", falso.server_port)
    srv = servidores(modulo.Manejador)

    class Web:
        puerto = srv.server_port
        backend = visto
        modulo_web = modulo
        carpeta = dist
    yield Web
    sys.modules.pop("servidor_web", None)


def test_web_sirve_index_y_archivos_con_su_tipo(web):
    estado, cuerpo, cab = pedir(web.puerto, "GET", "/")
    assert estado == 200 and b"INDEX" in cuerpo and cab["cache-control"] == "no-cache"
    estado, cuerpo, cab = pedir(web.puerto, "GET", "/assets/app.js")
    assert estado == 200 and cuerpo == b"console.log(1)" and "javascript" in cab["content-type"]
    assert "max-age" in cab["cache-control"]
    assert pedir(web.puerto, "GET", "/assets/estilo.css")[2]["content-type"].startswith("text/css")


def test_web_ruta_desconocida_vuelve_al_index(web):
    estado, cuerpo, _ = pedir(web.puerto, "GET", "/trabajadores/5?x=1#y")
    assert estado == 200 and b"INDEX" in cuerpo


@pytest.mark.parametrize("ruta", [
    "/../secreto.txt", "/assets/../../secreto.txt", "/..%2fsecreto.txt", "/%2e%2e/secreto.txt",
    "/../dist2/otro.txt", "/..\\secreto.txt", "/assets/..\\..\\secreto.txt",
    "//secreto.txt", "/C:/Windows/win.ini",
])
def test_web_no_permite_salir_de_la_carpeta_dist(web, ruta):
    estado, cuerpo, _ = pedir(web.puerto, "GET", ruta)
    assert b"CONTRASE" not in cuerpo and b"VECINO" not in cuerpo and b"[fonts]" not in cuerpo.lower()
    assert b"INDEX" in cuerpo


def test_web_no_acepta_escrituras_en_archivos_estaticos(web):
    for metodo in ("POST", "PUT", "DELETE"):
        assert pedir(web.puerto, metodo, "/", b"x")[0] == 405
    assert (web.carpeta / "index.html").read_text(encoding="utf-8") == "<html>INDEX</html>"


def test_web_head_no_devuelve_cuerpo(web):
    estado, cuerpo, cab = pedir(web.puerto, "HEAD", "/")
    assert estado == 200 and cuerpo == b"" and int(cab["content-length"]) > 0


def test_web_reenvia_api_quitando_el_prefijo_y_conserva_cookie_y_cuerpo(web):
    estado, cuerpo, cab = pedir(web.puerto, "POST", "/api/produccion?semana=1", b'{"kg": 5}',
                                {"Content-Type": "application/json", "Cookie": "agricolix_session=zzz",
                                 "Origin": "http://127.0.0.1:5173"})
    assert estado == 201 and json.loads(cuerpo) == {"ok": True}
    assert web.backend["metodo"] == "POST" and web.backend["ruta"] == "/produccion?semana=1"
    assert web.backend["cuerpo"] == b'{"kg": 5}'
    assert web.backend["cabeceras"]["cookie"] == "agricolix_session=zzz"
    assert web.backend["cabeceras"]["origin"] == "http://127.0.0.1:5173"
    assert "agricolix_session=abc" in cab["set-cookie"]          # la sesión vuelve al navegador


def test_web_pasa_tal_cual_los_errores_del_backend(web):
    estado, cuerpo, _ = pedir(web.puerto, "GET", "/api/falla")
    assert estado == 404 and json.loads(cuerpo) == {"detail": "no existe"}


@pytest.mark.parametrize("metodo", ["GET", "PUT", "PATCH"])
def test_web_reenvia_distintos_metodos(web, metodo):
    pedir(web.puerto, metodo, "/api/algo", b"{}" if metodo != "GET" else None)
    assert web.backend["metodo"] == metodo


def test_web_con_backend_apagado_responde_502_claro(web):
    web.modulo_web.BACKEND = ("127.0.0.1", puerto_libre())
    estado, cuerpo, _ = pedir(web.puerto, "GET", "/api/health")
    assert estado == 502
    assert "no esta disponible" in json.loads(cuerpo)["detail"]


def test_web_api_no_se_confunde_con_rutas_parecidas(web):
    """/apiario o /apis son páginas de la interfaz, no del backend."""
    estado, cuerpo, _ = pedir(web.puerto, "GET", "/apiario")
    assert b"INDEX" in cuerpo
    assert web.backend == {}


# ==========================================================
# DEMOSTRACIÓN Y RESPALDO (accesos .cmd)
# ==========================================================
@pytest.fixture
def sistema_demo(sistema, monkeypatch):
    """Sistema con todo simulado: registra qué scripts del backend y qué pasos se ejecutan."""
    pasos = []
    sistema.local.mkdir(parents=True)
    monkeypatch.setattr(sistema, "instalar_componentes", lambda base=None: None)
    monkeypatch.setattr(sistema, "preparar_env", lambda: None)
    monkeypatch.setattr(sistema, "apagar", lambda: pasos.append("apagar"))
    monkeypatch.setattr(sistema, "preparar_postgres", lambda: pasos.append("postgres"))
    monkeypatch.setattr(sistema, "preparar_base", lambda: pasos.append("base"))
    monkeypatch.setattr(sistema, "consultar_sin_usuarios", lambda: False)
    monkeypatch.setattr(sistema, "iniciar", lambda: pasos.append("iniciar"))
    monkeypatch.setattr(sistema, "script_backend", lambda *a: pasos.append(a))
    sistema.pasos = pasos
    return sistema


def test_demostracion_la_crea_si_no_existe_y_la_activa(sistema_demo):
    sistema_demo.cambiar_datos(True)
    assert sistema_demo.pasos == ["apagar", "postgres", "base", ("demo.py", "--crear"),
                                  ("demo.py", "--activar"), "iniciar"]


def test_demostracion_no_la_regenera_si_ya_existe(sistema_demo):
    (sistema_demo.local / "demostracion.json").write_text("{}")
    sistema_demo.cambiar_datos(True)
    assert ("demo.py", "--crear") not in sistema_demo.pasos
    assert ("demo.py", "--activar") in sistema_demo.pasos


def test_volver_a_datos_reales(sistema_demo):
    (sistema_demo.local / "demostracion.json").write_text("{}")
    sistema_demo.cambiar_datos(False)
    assert ("demo.py", "--original") in sistema_demo.pasos
    assert sistema_demo.pasos[-1] == "iniciar"


def test_volver_a_datos_reales_sin_demostracion_no_cambia_nada(sistema_demo):
    sistema_demo.cambiar_datos(False)
    assert not any(isinstance(p, tuple) for p in sistema_demo.pasos)


def test_demostracion_sin_cuenta_pide_crearla_y_no_enciende(sistema_demo, monkeypatch):
    monkeypatch.setattr(sistema_demo, "consultar_sin_usuarios", lambda: True)
    monkeypatch.setattr(sistema_demo, "detener_postgres", lambda: sistema_demo.pasos.append("detener_pg"))
    with pytest.raises(FaltaCuenta):
        sistema_demo.cambiar_datos(True)
    assert "iniciar" not in sistema_demo.pasos and "detener_pg" in sistema_demo.pasos


def test_respaldar_ejecuta_el_script_con_la_base_encendida(sistema_demo, monkeypatch):
    monkeypatch.setattr(sistema_demo, "usar_base", lambda funcion: funcion())
    sistema_demo.respaldar()
    assert sistema_demo.pasos == [("respaldo.py",)]


# ==========================================================
# APERTURA EN EDGE (modo aplicación) CON RESPALDO AL NAVEGADOR
# ==========================================================
def test_abrir_web_usa_edge_en_modo_aplicacion(monkeypatch, tmp_path):
    edge = tmp_path / "msedge.exe"
    llamadas, web = [], []
    monkeypatch.setattr(agricolix, "buscar_edge", lambda: edge)
    monkeypatch.setattr(agricolix.subprocess, "Popen", lambda args, **kw: llamadas.append(args))
    monkeypatch.setattr(agricolix.webbrowser, "open", lambda url: web.append(url))
    agricolix.abrir_web()
    assert llamadas == [[str(edge), f"--app={agricolix.URL_WEB}"]]
    assert web == []


def test_abrir_web_sin_edge_usa_el_navegador_predeterminado(monkeypatch):
    web = []
    monkeypatch.setattr(agricolix, "buscar_edge", lambda: None)
    monkeypatch.setattr(agricolix.webbrowser, "open", lambda url: web.append(url))
    agricolix.abrir_web()
    assert web == [agricolix.URL_WEB]


def test_abrir_web_si_edge_no_se_puede_abrir_usa_el_navegador(monkeypatch, tmp_path):
    web = []

    def falla(args, **kw):
        raise OSError("no se pudo abrir")
    monkeypatch.setattr(agricolix, "buscar_edge", lambda: tmp_path / "msedge.exe")
    monkeypatch.setattr(agricolix.subprocess, "Popen", falla)
    monkeypatch.setattr(agricolix.webbrowser, "open", lambda url: web.append(url))
    agricolix.abrir_web()
    assert web == [agricolix.URL_WEB]


def test_buscar_edge_encuentra_la_instalacion_o_devuelve_none(monkeypatch, tmp_path):
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        monkeypatch.setenv(variable, str(tmp_path / "vacio"))
    monkeypatch.setattr(agricolix.shutil, "which", lambda nombre: None)
    assert agricolix.buscar_edge() is None
    ruta = tmp_path / "pf" / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    ruta.parent.mkdir(parents=True)
    ruta.write_text("x")
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    assert agricolix.buscar_edge() == ruta


# ==========================================================
# VISUAL C++ (lo necesita PostgreSQL; en un PC limpio puede faltar)
# ==========================================================
def preparar_windows(monkeypatch, tmp_path, con_dll):
    sistema32 = tmp_path / "Windows" / "System32"
    sistema32.mkdir(parents=True)
    if con_dll:
        for dll in agricolix.DLL_VISUAL_CPP:
            (sistema32 / dll).write_text("x")
    monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))


def test_visual_cpp_se_detecta(sistema, monkeypatch, tmp_path):
    preparar_windows(monkeypatch, tmp_path, True)
    assert sistema.visual_cpp_instalado()
    (tmp_path / "Windows" / "System32" / "msvcp140.dll").unlink()
    assert not sistema.visual_cpp_instalado()


def test_si_visual_cpp_esta_no_descarga_nada(sistema, monkeypatch, tmp_path):
    preparar_windows(monkeypatch, tmp_path, True)
    monkeypatch.setattr(sistema, "descargar", lambda *a: pytest.fail("no debía descargar"))
    sistema.asegurar_visual_cpp(sistema.datos)


def test_si_falta_visual_cpp_lo_descarga_y_lo_instala(sistema, monkeypatch, tmp_path):
    preparar_windows(monkeypatch, tmp_path, False)
    pasos = []

    class R:
        returncode, stdout, stderr = 3010, "", ""   # instalado, pide reiniciar
    monkeypatch.setattr(sistema, "descargar", lambda url, destino, etiqueta: pasos.append(url))
    monkeypatch.setattr(sistema, "powershell", lambda script, **v: pasos.append(v) or R())
    sistema.asegurar_visual_cpp(sistema.datos)
    assert pasos[0] == agricolix.URL_VISUAL_CPP
    assert pasos[1]["AGX_INSTALADOR"].endswith("vc_redist.x64.exe")


def test_si_el_usuario_rechaza_el_permiso_da_un_error_claro(sistema, monkeypatch, tmp_path):
    preparar_windows(monkeypatch, tmp_path, False)

    class R:
        returncode, stdout, stderr = 1, "", ""
    monkeypatch.setattr(sistema, "descargar", lambda *a: None)
    monkeypatch.setattr(sistema, "powershell", lambda script, **v: R())
    with pytest.raises(ErrorAgricolix, match="Visual C"):
        sistema.asegurar_visual_cpp(sistema.datos)


def test_sin_internet_para_visual_cpp_no_se_toca_la_carpeta(tmp_path, monkeypatch):
    crear_proyecto(tmp_path)
    s = Sistema(tmp_path)
    preparar_windows(monkeypatch, tmp_path, False)

    def sin_internet(*a):
        raise ErrorAgricolix("No se pudieron descargar los componentes")
    monkeypatch.setattr(s, "descargar", sin_internet)
    with pytest.raises(ErrorAgricolix):
        s.ordenar()
    assert (tmp_path / "FASE 1" / "informe.docx").is_file()
    assert (tmp_path / "FASE 2" / "DonaLaura" / "backend" / "main.py").is_file()
