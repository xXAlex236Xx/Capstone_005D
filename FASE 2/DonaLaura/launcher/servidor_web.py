# ==========================================================
# AGRICOLIX - SERVIDOR WEB LOCAL
# Sirve la interfaz compilada (frontend/dist) y reenvía las
# peticiones /api al backend. Reemplaza a Node en la entrega.
# Uso: python servidor_web.py <carpeta_dist>
# ==========================================================
import http.client
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIST = Path(sys.argv[1]).resolve()
PUERTO = 5173
BACKEND = ("127.0.0.1", 8000)
# Cabeceras propias de cada conexión: no se reenvían.
SALTAR = {"connection", "keep-alive", "transfer-encoding", "te", "trailer",
          "upgrade", "proxy-authorization", "proxy-authenticate", "host", "content-length"}


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def responder(self, estado, cuerpo, tipo="application/json", extra=()):
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        for nombre, valor in extra:
            self.send_header(nombre, valor)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def reenviar(self):
        ruta = self.path[4:] or "/"
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo) if largo else None
        cabeceras = {k: v for k, v in self.headers.items() if k.lower() not in SALTAR}
        conexion = http.client.HTTPConnection(*BACKEND, timeout=300)
        try:
            conexion.request(self.command, ruta, cuerpo, cabeceras)
            respuesta = conexion.getresponse()
            datos = respuesta.read()
        except OSError:
            self.responder(502, b'{"detail":"El sistema no esta disponible en este momento."}')
            return
        finally:
            conexion.close()
        self.send_response(respuesta.status)
        for nombre, valor in respuesta.getheaders():
            if nombre.lower() not in SALTAR:
                self.send_header(nombre, valor)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(datos)

    def estatico(self):
        ruta = self.path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        archivo = (DIST / ruta).resolve()
        # Nunca salir de la carpeta dist; lo desconocido vuelve al index.
        if DIST not in archivo.parents or not archivo.is_file():
            archivo = DIST / "index.html"
        tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
        cache = "no-cache" if archivo.name == "index.html" else "public, max-age=3600"
        self.responder(200, archivo.read_bytes(), tipo, [("Cache-Control", cache)])

    def atender(self):
        if self.path == "/api" or self.path.startswith("/api/") or self.path.startswith("/api?"):
            self.reenviar()
        elif self.command in ("GET", "HEAD"):
            self.estatico()
        else:
            self.responder(405, b'{"detail":"Metodo no permitido."}')

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = atender


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador).serve_forever()
