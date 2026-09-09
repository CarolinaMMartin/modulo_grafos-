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
# Los reportes se suben de a varios y un JSON de NCMEC con transcripciones pesa.
CUERPO_MAXIMO_IMPORTAR = 12 * 1024 * 1024
_candado = threading.Lock()        # una escritura por vez: el libro es un archivo


def reconstruir():
    construir.construir([construir.DIR_DATOS, construir.DIR_ENTRADA], SALIDA)


def _nombre_seguro(valor):
    """Nombre de archivo a partir del numero de reporte.

    Se arma con el reportId y no con el nombre que trae el archivo subido: un
    nombre de archivo es entrada no confiable y no tiene por que decidir donde
    se escribe.
    """
    limpio = "".join(c for c in str(valor) if c.isalnum() or c in "-_")
    if not limpio:
        raise ValueError("el numero de reporte no sirve como nombre de archivo")
    return limpio[:60] + ".json"


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
            "/api/importar": self._importar,
            "/api/quitar": self._quitar,
        }
        if ruta not in acciones:
            self._error(404, "no existe")
            return
        try:
            largo = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._error(400, "cuerpo invalido")
            return
        tope = CUERPO_MAXIMO_IMPORTAR if ruta == "/api/importar" else CUERPO_MAXIMO
        if largo <= 0 or largo > tope:
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

    def _importar(self, datos):
        """Guarda reportes en la carpeta de entrada.

        Valida lo minimo que el extractor necesita para no fallar despues: que
        sea un JSON, que sea un objeto y que traiga numero de reporte. Lo que
        falte adentro lo tolera el extractor, y el visor lo muestra como lo que
        es -un reporte con pocos datos-, que tambien es un caso a probar.
        """
        archivos = datos.get("archivos")
        if not isinstance(archivos, list) or not archivos:
            raise ValueError("no llego ningun archivo")
        if len(archivos) > 200:
            raise ValueError("demasiados archivos de una vez")
        if not os.path.isdir(construir.DIR_ENTRADA):
            os.makedirs(construir.DIR_ENTRADA)

        resultados = []
        for a in archivos:
            nombre = str((a or {}).get("nombre") or "sin nombre")[:120]
            try:
                r = json.loads((a or {}).get("contenido") or "")
            except (ValueError, TypeError):
                resultados.append(dict(nombre=nombre, ok=False,
                                       motivo="no es un JSON valido"))
                continue
            if not isinstance(r, dict):
                resultados.append(dict(nombre=nombre, ok=False,
                                       motivo="el JSON no es un objeto"))
                continue
            rid = r.get("reportId")
            if rid in (None, ""):
                resultados.append(dict(nombre=nombre, ok=False,
                                       motivo="no trae reportId"))
                continue
            try:
                destino = os.path.join(construir.DIR_ENTRADA, _nombre_seguro(rid))
            except ValueError as e:
                resultados.append(dict(nombre=nombre, ok=False, motivo=str(e)))
                continue
            reemplaza = os.path.exists(destino)
            with open(destino, "w", encoding="utf-8") as fh:
                json.dump(r, fh, ensure_ascii=False, indent=1)
            resultados.append(dict(nombre=nombre, ok=True, reporte=str(rid),
                                   reemplaza=reemplaza))
        if not any(x["ok"] for x in resultados):
            raise ValueError("ningun archivo se pudo importar")
        return dict(ok=True, accion="importar", resultados=resultados)

    def _quitar(self, datos):
        """Saca un reporte del banco de pruebas. Solo toca la carpeta de
        entrada: el dataset del proyecto no se borra desde la pantalla."""
        rid = self._texto(datos, "reporte", maximo=60)
        destino = os.path.join(construir.DIR_ENTRADA, _nombre_seguro(rid))
        if not os.path.exists(destino):
            raise ValueError("ese reporte no esta en la carpeta de entrada")
        os.remove(destino)
        return dict(ok=True, accion="quitar", reporte=rid)

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


PUERTO_POR_DEFECTO = 8731


def _puerto_inicial():
    """Puerto: la variable PORT del entorno gana sobre el valor por defecto.

    Esta aplicacion no necesita un puerto en particular -no recibe callbacks ni
    webhooks, y el visor se sirve desde el mismo origen, asi que tampoco hay
    CORS de por medio-. Respetar PORT permite que quien la levante le asigne
    uno libre y evita el choque cuando ya hay una instancia corriendo.
    """
    crudo = os.environ.get("PORT")
    if not crudo:
        return PUERTO_POR_DEFECTO
    try:
        return int(crudo)
    except ValueError:
        print("PORT=%r no es un numero; se usa %d" % (crudo, PUERTO_POR_DEFECTO))
        return PUERTO_POR_DEFECTO


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Servidor local del visor")
    ap.add_argument("--puerto", type=int, default=_puerto_inicial())
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
