"""Regresiones de instalacion, identidad de entrada, salidas y proteccion HTTP."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pruebas_revision import DemoAislada
from pruebas_importacion import archivo, pedir
import construir
import analisis
import nucleo
import resolucion
import servidor
import validacion

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import iniciar


class MantenimientoTest(unittest.TestCase):
    def test_contador_visible_tras_varios_redibujados(self):
        subprocess.run(['node', str(RAIZ/'grafo/pruebas_lienzo.js')], check=True)

    def test_python_y_versiones_requeridas(self):
        self.assertFalse(iniciar.python_admitido((3,8,20)))
        self.assertFalse(iniciar.python_admitido((3,14,1)))
        self.assertTrue(iniciar.python_admitido((3,12,14)))
        self.assertTrue(iniciar.python_admitido((3,14,2)))
        self.assertEqual(set(iniciar.requisitos_fijados()), {'networkx','numpy','scipy'})
        with patch.object(iniciar, 'PYTHON', Path(sys.executable)):
            self.assertTrue(iniciar.dependencias_correctas())
            with patch.object(iniciar,'requisitos_fijados',return_value={'networkx':'0.0.0'}):
                self.assertFalse(iniciar.dependencias_correctas())

    def test_reportes_no_colisionan_ni_sobrescriben_por_sanitizacion(self):
        with DemoAislada() as demo:
            self.assertEqual(pedir(demo,'/api/importar',{'archivos':[archivo({'reportId':'QA_AB'})]})[0],200)
            p=Path(construir.DIR_ENTRADA)/'QA_AB.json'
            anterior=p.read_bytes()
            for rid in ['QA_ AB','QA_/AB','qa_ab','CON','NUL','COM1','A'*61]:
                status,_=pedir(demo,'/api/importar',{'archivos':[archivo({'reportId':rid})]})
                self.assertEqual(status,400,rid)
                self.assertEqual(p.read_bytes(),anterior)
                self.assertEqual(len(list(Path(construir.DIR_ENTRADA).glob('*.json'))),1)

    def test_vinculo_con_reporte_inexistente_no_se_guarda(self):
        with DemoAislada() as demo:
            status,_=pedir(demo,'/api/vincular',dict(reporte_a='900000105',reporte_b='NO_EXISTE',usuario='prueba',motivo='prueba'))
            self.assertEqual(status,400)
            self.assertFalse(Path(servidor.LIBRO_VINCULOS).exists())

    def test_reconstruccion_fallida_declara_operacion_guardada(self):
        with DemoAislada() as demo:
            with patch.object(servidor,'reconstruir',side_effect=RuntimeError('prueba')):
                status,res=pedir(demo,'/api/importar',{'archivos':[archivo({'reportId':'QA_PERSISTE'})]})
            self.assertEqual(status,500)
            self.assertTrue(res['operacion_guardada'])
            self.assertTrue((Path(construir.DIR_ENTRADA)/'QA_PERSISTE.json').is_file())
            servidor.reconstruir()

    def test_post_externo_y_formulario_no_escriben(self):
        with DemoAislada() as demo:
            datos=json.dumps({'archivos':[archivo({'reportId':'QA_RECHAZADO'})]}).encode()
            for headers,codigo in [({'Content-Type':'text/plain'},415),
                                   ({'Content-Type':'application/json','Origin':'https://otro.example'},403),
                                   ({'Content-Type':'application/json','Host':'otro.example'},403)]:
                req=Request(demo.url+'/api/importar',data=datos,headers=headers)
                with self.assertRaises(HTTPError) as cm:urlopen(req,timeout=10)
                self.assertEqual(cm.exception.code,codigo)
                cm.exception.close()
            self.assertFalse(Path(construir.DIR_ENTRADA).exists())

    def test_reaplicar_validacion_reactiva_la_arista_y_crea_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            g=nucleo.Grafo();a=g.nodo('REPORTE','QA_A');b=g.nodo('REPORTE','QA_B')
            aid=g.arista(a,b,'COINCIDE_CON','qa','qa','prueba','prueba',confianza=.9)
            libro=validacion.LibroValidaciones(str(Path(tmp)/'estado'/'validaciones.jsonl'))
            libro.registrar(aid,'rechazada','prueba');libro.aplicar(g)
            self.assertFalse(g.G.edges[a,b,aid]['vigente'])
            libro.registrar(aid,'validada','prueba');libro.aplicar(g)
            self.assertTrue(g.G.edges[a,b,aid]['vigente']);self.assertFalse(libro.verificar())

    def test_identidad_del_reporte_no_depende_del_nombre_de_archivo(self):
        with DemoAislada():
            entrada=Path(construir.DIR_ENTRADA);entrada.mkdir()
            (entrada/'nombre_libre.json').write_text(json.dumps({'reportId':'900000105'}))
            g,res=construir.construir([construir.DIR_DATOS,str(entrada)],servidor.SALIDA)
            self.assertEqual(res['reportes_ingeridos'],2)
            self.assertIn('900000105',res['importados'])
            (entrada/'otro.json').write_text(json.dumps({'reportId':'900000105'}))
            with self.assertRaisesRegex(ValueError,'duplicado'):
                construir.construir(str(entrada),servidor.SALIDA)

    def test_construir_no_modifica_documentacion_versionada(self):
        paths=[RAIZ/'DOCUMENTACION_TECNICA.md',RAIZ/'grafo/MODELO_DATOS.md']
        antes=[p.read_bytes() for p in paths]
        with DemoAislada():pass
        self.assertEqual(antes,[p.read_bytes() for p in paths])

    def test_informe_declara_fallback_y_puentes(self):
        with DemoAislada():
            with patch.object(analisis.nx.community,'louvain_communities',side_effect=RuntimeError('fallback de prueba')):
                _,res=construir.construir(construir.DIR_DATOS,servidor.SALIDA)
            self.assertEqual(res['comunidades'][0]['algoritmo'],'greedy_modularity_fallback')
            texto=(Path(servidor.SALIDA)/'informe.md').read_text()
            self.assertIn('greedy_modularity_fallback',texto)
            self.assertIn('### Puentes',texto)
            self.assertNotIn('Comunidades (Louvain)',texto)

    def test_contradiccion_admite_coordenadas_cero(self):
        g=nucleo.Grafo();cuenta=g.nodo('CUENTA','prueba')
        for i,lon in enumerate([2,8]):
            ip=g.nodo('IP','192.0.2.'+str(i+1))
            lugar=g.nodo('UBICACION',str(i),lat=0,lon=lon)
            g.arista(ip,lugar,'GEOLOCALIZA_EN','qa','lugar'+str(i),'prueba','prueba',confianza=.8)
            g.arista(cuenta,ip,'OBSERVADO_DESDE_IP','qa','captura'+str(i),'prueba','prueba',observed_at='2026-09-01T00:%s:00Z' % ('00' if i==0 else '30'))
        self.assertEqual(len(resolucion.detectar_contradicciones(g)),1)

    def test_metricas_omitidas_tienen_motivo(self):
        g=nucleo.Grafo();a=g.nodo('REPORTE','QA_A');b=g.nodo('REPORTE','QA_B')
        g.arista(a,b,'COINCIDE_CON','qa','qa','prueba','prueba',confianza=.9)
        with patch.object(analisis,'MAX_NODOS_INTERMEDIACION',1),patch.object(analisis,'MAX_NODOS_PAGERANK',1):
            r=analisis.centralidades(g)
        self.assertEqual(set(r['omitidas']),{'intermediacion','pagerank'})
        self.assertEqual(r['intermediacion'],[]);self.assertEqual(r['pagerank'],[])


if __name__=='__main__':unittest.main(verbosity=2)
