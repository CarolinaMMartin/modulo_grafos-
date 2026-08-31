# -*- coding: utf-8 -*-
"""
Servidor local del visor: lo que convierte el archivo suelto en una aplicacion.


    python grafo/servidor.py

Abre el navegador solo. El operador trabaja ahi.

Alcance y limites, para no confundirlo con lo que no es:

  - Escucha SOLO en 127.0.0.1. No queda expuesto a la red.
  - No hay autenticacion. El campo "operador" es ATRIBUCION, no identidad
    verificada: sirve para saber quien dijo que, no para probar que fue esa
    persona. En la Boveda esto lo reemplaza la sesion institucional.
  - No hay permisos por rol, caso ni jurisdiccion. Quien lo corre ve todo.
  - Es un servidor de piloto, sin hardening. No se despliega asi.

Lo que si hace bien, porque es lo que no se puede perder:

  - Toda escritura pasa por el libro append-only encadenado por hash.
  - Despues de cada escritura reconstruye el grafo entero desde los reportes,
    de modo que lo que se ve en pantalla siempre sale de una corrida completa
    y nunca de un parche en memoria.
"""

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import construir                        # noqa: E402
import validacion                       # noqa: E402

SALIDA = os.path.join(BASE, "salida")
LIBRO_VALIDACIONES = os.path.join(BASE, "estado", "validaciones.jsonl")
LIBRO_VINCULOS = os.path.join(BASE, "estado", "vinculos_manuales.jsonl")

CUERPO_MAXIMO = 64 * 1024          # ningun motivo legitimo pesa mas que esto
_candado = threading.Lock()        # una escritura por vez: el libro es un archivo


def reconstruir():
    construir.construir(construir.DIR_DATOS, SALIDA)


class Handler(BaseHTTPRequestHandler):

    server_version = "BovedaCIJ/piloto"

    def log_message(self, formato, *args):
        sys.stderr.write("  %s\n" % (formato % args))

    # -- respuestas --------------------------------------------------------
    def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8",
                   solo_encabezados=False):
        datos = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode("utf-8")
        try:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            # El visor no pide nada afuera y nadie deberia poder embeberlo.
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not solo_encabezados:
                self.wfile.write(datos)
        except (ConnectionError, BrokenPipeError):
            # El navegador corto la descarga -recargo, cerro la pestana-. Es
            # normal y no es un error del sistema: quien mira esta consola es un
            # operador, y un stack trace ahi parece que algo se rompio.
            self.log_message("el navegador corto la conexion")

    def _json(self, codigo, obj):
        self._responder(codigo, json.dumps(obj, ensure_ascii=False))

    def _error(self, codigo, mensaje):
        self._json(codigo, dict(ok=False, error=mensaje))

    # -- GET / HEAD --------------------------------------------------------
    def do_GET(self):
        self._servir(solo_encabezados=False)

    def do_HEAD(self):
        # Los que comprueban si el servidor esta vivo mandan HEAD antes que GET.
        # Sin esto contestaba 501 y parecia caido estando levantado.
        self._servir(solo_encabezados=True)

    def _servir(self, solo_encabezados):
        ruta = self.path.split("?")[0]
        if ruta in ("/", "/index.html", "/grafo.html"):
            archivo = os.path.join(SALIDA, "grafo.html")
            if not os.path.exists(archivo):
                reconstruir()
            with open(archivo, "rb") as fh:
                self._responder(200, fh.read(), "text/html; charset=utf-8",
                                solo_encabezados=solo_encabezados)
            return
        if ruta == "/api/estado":
            self._responder(200, json.dumps(dict(ok=True, app=True)),
                            solo_encabezados=solo_encabezados)
            return
        self._responder(404, json.dumps(dict(ok=False, error="no existe")),
                        solo_encabezados=solo_encabezados)

    # -- POST --------------------------------------------------------------
    def do_POST(self):
        ruta = self.path.split("?")[0]
        acciones = {
            "/api/vincular": self._vincular,
            "/api/desvincular": self._desvincular,
            "/api/decidir": self._decidir,
        }
        if ruta not in acciones:
            self._error(404, "no existe")
            return
        try:
            largo = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._error(400, "cuerpo invalido")
            return
        if largo <= 0 or largo > CUERPO_MAXIMO:
            self._error(400, "cuerpo invalido o demasiado grande")
            return
        try:
            datos = json.loads(self.rfile.read(largo).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._error(400, "no se pudo interpretar el pedido")
            return
        if not isinstance(datos, dict):
            self._error(400, "no se pudo interpretar el pedido")
            return

        with _candado:
            try:
                respuesta = acciones[ruta](datos)
            except ValueError as e:
                self._error(400, str(e))
                return
            except Exception as e:                      # noqa: BLE001
                self.log_message("error interno: %s", e)
                self._error(500, "no se pudo completar la operacion")
                return
            reconstruir()
        self._json(200, respuesta)

    # -- operaciones -------------------------------------------------------
    @staticmethod
    def _texto(datos, clave, obligatorio=True, maximo=2000):
        valor = (datos.get(clave) or "").strip()
        if obligatorio and not valor:
            raise ValueError("falta %s" % clave)
        if len(valor) > maximo:
            raise ValueError("%s es demasiado largo" % clave)
        return valor

    def _vincular(self, datos):
        a = self._texto(datos, "reporte_a")
        b = self._texto(datos, "reporte_b")
        usuario = self._texto(datos, "usuario")
        motivo = self._texto(datos, "motivo")
        libro = validacion.LibroVinculos(LIBRO_VINCULOS)
        reg = libro.registrar(a, b, "vincular", usuario, motivo)
        return dict(ok=True, accion="vincular", registro=reg)

    def _desvincular(self, datos):
        a = self._texto(datos, "reporte_a")
        b = self._texto(datos, "reporte_b")
        usuario = self._texto(datos, "usuario")
        motivo = self._texto(datos, "motivo", obligatorio=False)
        libro = validacion.LibroVinculos(LIBRO_VINCULOS)
        reg = libro.registrar(a, b, "desvincular", usuario, motivo)
        return dict(ok=True, accion="desvincular", registro=reg)

    def _decidir(self, datos):
        arista = self._texto(datos, "arista")
        decision = self._texto(datos, "decision")
        if decision not in validacion.DECISIONES:
            raise ValueError("decision invalida")
        usuario = self._texto(datos, "usuario")
        observacion = self._texto(datos, "observacion", obligatorio=False)
        libro = validacion.LibroValidaciones(LIBRO_VALIDACIONES)
        reg = libro.registrar(arista, decision, usuario, observacion)
        return dict(ok=True, accion="decidir", registro=reg)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Servidor local del visor")
    ap.add_argument("--puerto", type=int, default=8731)
    ap.add_argument("--sin-navegador", action="store_true")
    args = ap.parse_args()

    print("Construyendo el grafo...")
    reconstruir()

    url = "http://127.0.0.1:%d/" % args.puerto
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Handler)
    print("")
    print("  Visor de vinculaciones: %s" % url)
    print("")
    print("  Escucha solo en esta computadora. Sin autenticacion: el campo")
    print("  'operador' sirve para saber quien dispuso cada cosa, no para")
    print("  acreditar identidad. Ctrl+C para salir.")
    print("")
    if not args.sin_navegador:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        servidor.server_close()


if __name__ == "__main__":
    main()
