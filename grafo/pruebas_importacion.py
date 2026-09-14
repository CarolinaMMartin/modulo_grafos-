"""Regresiones HTTP de importacion. Solo usa copias temporales sinteticas.

python grafo/pruebas_importacion.py
"""
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pruebas_revision import DemoAislada
import construir
import servidor


def pedir(demo, ruta, datos):
    req = Request(demo.url + ruta, data=json.dumps(datos).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=60) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def archivo(reporte, nombre="prueba.json"):
    return dict(nombre=nombre, contenido=json.dumps(reporte))


class ImportacionHTTPTest(unittest.TestCase):
    def test_mixta_minimo_y_quitar_sin_alterar_dataset(self):
        with DemoAislada() as demo:
            antes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in Path(construir.DIR_DATOS).glob("*.json")}
            validos = [archivo({"reportId": "QA_MINIMO"}, "../../fuera.json")]
            invalidos = [dict(nombre="invalido.json", contenido="{sin JSON}"),
                         archivo({"sin_reportId": True}), "no es objeto"]
            status, res = pedir(demo, "/api/importar", {"archivos": validos + invalidos})
            self.assertEqual(status, 200, res)
            self.assertEqual([r["ok"] for r in res["resultados"]], [True, False, False, False])
            ruta = Path(construir.DIR_ENTRADA) / "QA_MINIMO.json"
            self.assertTrue(ruta.is_file())
            self.assertEqual(os.listdir(construir.DIR_ENTRADA), ["QA_MINIMO.json"])
            self.assertEqual(pedir(demo, "/api/quitar", {"reporte": "900000105"})[0], 400)
            self.assertEqual(pedir(demo, "/api/quitar", {"reporte": "QA_MINIMO"})[0], 200)
            self.assertFalse(ruta.exists())
            despues = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in Path(construir.DIR_DATOS).glob("*.json")}
            self.assertEqual(antes, despues)

    def test_estructura_invalida_no_persiste_ni_reemplaza(self):
        with DemoAislada() as demo:
            valido = {"reportId": "QA_EXISTENTE"}
            self.assertEqual(pedir(demo, "/api/importar", {"archivos": [archivo(valido)]})[0], 200)
            ruta = Path(construir.DIR_ENTRADA) / "QA_EXISTENTE.json"
            original = ruta.read_bytes()
            for cuerpo in (
                {"reportId": "QA_EXISTENTE", "reportedInformation": "no es objeto"},
                {"reportId": "QA_NUEVO", "reportedInformation": {"incidentDetails": {"chatIncident": ["no es objeto"]}}},
                {"reportId": ["no es identificador"]},
                {"reportId": True},
            ):
                status, res = pedir(demo, "/api/importar", {"archivos": [archivo(cuerpo)]})
                self.assertEqual(status, 400, res)
                self.assertEqual(ruta.read_bytes(), original)
                self.assertEqual(os.listdir(construir.DIR_ENTRADA), ["QA_EXISTENTE.json"])
                servidor.reconstruir()

    def test_elemento_no_objeto_devuelve_error_cliente(self):
        with DemoAislada() as demo:
            status, res = pedir(demo, "/api/importar", {"archivos": ["no es objeto"]})
            self.assertEqual(status, 400, res)
            self.assertFalse(res["ok"])
            self.assertFalse(os.listdir(construir.DIR_ENTRADA))

    def test_fallo_de_reconstruccion_devuelve_json_y_registra_error(self):
        with DemoAislada() as demo:
            with patch.object(servidor, "reconstruir", side_effect=RuntimeError("fallo simulado")):
                status, res = pedir(demo, "/api/importar", {
                    "archivos": [archivo({"reportId": "QA_VALIDO"})]})
            self.assertEqual(status, 500, res)
            self.assertFalse(res["ok"])
            # El archivo de esta prueba es valido; al restablecerse el
            # constructor vuelve a poder procesarse normalmente.
            servidor.reconstruir()


if __name__ == "__main__":
    unittest.main(verbosity=2)
