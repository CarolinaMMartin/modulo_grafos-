"""Regresiones del circuito de revision. Solo usa copias temporales de sinteticos.

python grafo/pruebas_revision.py
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import servidor
import construir
import resolucion
import validacion


class DemoAislada:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="revision_grafos_")
        self.root = self.tmp.name
        self.previo = []
        datos = os.path.join(self.root, "reportes")
        os.makedirs(datos)
        # Ambos reportes son sinteticos del proyecto. No se copia el reporte real.
        for rid in ("900000105", "900000106"):
            shutil.copyfile(os.path.join(construir.DIR_DATOS, rid + ".json"),
                            os.path.join(datos, rid + ".json"))
        base = os.path.join(self.root, "grafo")
        os.makedirs(os.path.join(base, "estado"))
        for modulo, clave, valor in (
            (construir, "BASE", base), (construir, "DIR_DATOS", datos),
            (construir, "DIR_ENTRADA", os.path.join(base, "entrada")),
            (servidor, "SALIDA", os.path.join(base, "salida")),
            (servidor, "LIBRO_VALIDACIONES", os.path.join(base, "estado", "validaciones.jsonl")),
            (servidor, "LIBRO_VINCULOS", os.path.join(base, "estado", "vinculos_manuales.jsonl")),
        ):
            self.previo.append((modulo, clave, getattr(modulo, clave)))
            setattr(modulo, clave, valor)
        servidor.reconstruir()
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Handler)
        self.hilo = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.hilo.start()
        self.url = "http://127.0.0.1:%d" % self.http.server_port
        return self

    def __exit__(self, *args):
        self.http.shutdown()
        self.http.server_close()
        self.hilo.join()
        for modulo, clave, valor in reversed(self.previo):
            setattr(modulo, clave, valor)
        self.tmp.cleanup()

    def grafo(self):
        with open(os.path.join(servidor.SALIDA, "grafo.json"), encoding="utf-8") as f:
            return json.load(f)

    def html(self):
        return urlopen(self.url, timeout=10).read().decode("utf-8")

    def decidir(self, aid, decision, usuario="operador-prueba", observacion=""):
        req = Request(self.url + "/api/decidir", data=json.dumps(dict(
            arista=aid, decision=decision, usuario=usuario, observacion=observacion)).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=30) as r:
                return r.status, json.load(r)
        except HTTPError as e:
            return e.code, json.load(e)


class RevisionTest(unittest.TestCase):
    def test_circuito_http_y_persistencia(self):
        with DemoAislada() as demo:
            a = next(a for a in demo.grafo()["aristas"] if a["relation_type"] == "COINCIDE_CON")
            aid = a["arista_id"]
            self.assertAlmostEqual(a["confidence"], .92)
            self.assertIn("mismo identificador de dispositivo", a["explicacion"])
            self.assertNotIn("reglas no calibradas", a["explicacion"])
            self.assertNotIn("No acredita autoría", a["explicacion"])
            for decision, motivo in (("validada", ""), ("rechazada", "Dato incorrecto en prueba"),
                                     ("en_revision", "Volver a verificar")):
                status, res = demo.decidir(aid, decision, observacion=motivo)
                self.assertEqual(status, 200, res)
                actual = next(a for a in demo.grafo()["aristas"] if a["arista_id"] == aid)
                self.assertEqual(actual["validation_status"], decision)
                self.assertEqual(actual.get("vigente", True), decision != "rechazada")
                with open(os.path.join(servidor.SALIDA, "analisis.json"), encoding="utf-8") as f:
                    analisis = json.load(f)
                self.assertEqual(len(analisis["vinculacion"]["vinculos"]), int(decision != "rechazada"))
                if decision == "rechazada":
                    self.assertTrue(all(len(l["reportes"]) == 1 for l in analisis["legajos"]))
                # Una nueva reconstruccion conserva el estado y su historial.
                servidor.reconstruir()
                actual = next(a for a in demo.grafo()["aristas"] if a["arista_id"] == aid)
                self.assertEqual(actual["validation_status"], decision)
            self.assertEqual(len(actual["historial_validacion"]), 3)
            self.assertFalse(validacion.LibroValidaciones(servidor.LIBRO_VALIDACIONES).verificar())
            html = demo.html()
            self.assertIn("Cómo se calculó el puntaje", html)
            self.assertIn('data-accion="decidir"', html)
            self.assertEqual(html.count('<footer id="avisoGeneral">'), 1)
            self.assertNotIn("python validar.py", html)

    def test_pedidos_invalidos_no_escriben(self):
        with DemoAislada() as demo:
            aid = next(a["arista_id"] for a in demo.grafo()["aristas"]
                       if a["relation_type"] == "COINCIDE_CON")
            for ident, decision, usuario, motivo in (
                ("inexistente", "validada", "prueba", ""),
                (aid, "invalida", "prueba", ""),
                (aid, "validada", "", ""),
                (aid, "rechazada", "prueba", ""),
                (aid, "validada", ["no es texto"], ""),
            ):
                self.assertEqual(demo.decidir(ident, decision, usuario, motivo)[0], 400)
            self.assertFalse(validacion.LibroValidaciones(servidor.LIBRO_VALIDACIONES).registros())

    def test_desglose_de_ajustes(self):
        d = dict(regla="R03_TELEFONO", tipo="TELEFONO", peso_base=.9,
                 peso_efectivo=.459, factor_texto_libre=.85, factor_discriminancia=.6,
                 corrobora_solamente=False, valor="telefono-sintetico")
        calc = resolucion.calculo_legible([d], .459)
        self.assertEqual(calc["pasos"][0]["cuenta"], "0,9000 × 0,6000 × 0,8500 = 0,4590")
        self.assertEqual(len(calc["pasos"][0]["ajustes"]), 2)

    def test_observacion_no_inyecta_html(self):
        with DemoAislada() as demo:
            aid = next(a["arista_id"] for a in demo.grafo()["aristas"]
                       if a["relation_type"] == "COINCIDE_CON")
            texto = '</script><script>window.INYECCION=true</script>'
            self.assertEqual(demo.decidir(aid, "validada", observacion=texto)[0], 200)
            self.assertNotIn(texto, demo.html())
            reg = validacion.LibroValidaciones(servidor.LIBRO_VALIDACIONES).registros()[0]
            self.assertEqual(reg["observacion"], texto)


if __name__ == "__main__":
    if "--servir" in sys.argv:
        with DemoAislada() as demo:
            print(demo.url, flush=True)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
    else:
        unittest.main(verbosity=2)
