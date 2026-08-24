# -*- coding: utf-8 -*-
"""
Orquestador del corte vertical de grafos (CLAUDE.md 21).

  1. ingesta de reportes con preservacion y hash de la fuente
  2. extraccion de entidades y relaciones OBSERVADAS con locator
  3. vinculacion DERIVADA entre reportes + contradicciones
  4. hipotesis INFERIDAS de identidad
  5. alertas de reapertura tipadas por motivo de archivo
  6. vinculaciones AFIRMADAS que dispuso un operador
  7. algoritmos clasicos: legajos, comunidades, centralidades, candidatos
  8. re-aplicacion de las validaciones humanas registradas
  9. salidas: grafo.json, grafo.graphml, grafo.html, informe.md, dossier

La clasificacion jurisdiccional y la derivacion territorial quedan FUERA de esta
etapa por decision del proyecto. El modulo src/jurisdiccion.py se conserva sin
conectar, para cuando se retome la Etapa 2.

Uso:
    python construir.py
    python construir.py --datos datos --salida salida
"""

import argparse
import glob
import json
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import alertas as mod_alertas          # noqa: E402
import analisis                        # noqa: E402
import docs_modelo                     # noqa: E402
import dossier as mod_dossier          # noqa: E402
import redaccion                       # noqa: E402
import extractor_ncmec                 # noqa: E402
import identidades                     # noqa: E402
import informe as mod_informe          # noqa: E402
import nucleo                          # noqa: E402
import ontologia as ont                # noqa: E402
import render_html                     # noqa: E402
import resolucion                      # noqa: E402
import validacion                      # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
# Los reportes viven en la carpeta de trabajo, no dentro del modulo:
# son material del proyecto, no un recurso interno del codigo.
DIR_DATOS = os.path.join(os.path.dirname(BASE), "reportes_sinteticos")


def construir(dir_datos, dir_salida, ts_corrida=None):
    problemas = ont.validar_ontologia()
    if problemas:
        raise SystemExit("Ontologia inconsistente: %s" % problemas)

    if not os.path.isdir(dir_salida):
        os.makedirs(dir_salida)

    estado_path = os.path.join(dir_datos, "estado_institucional.json")
    estados = {}
    if os.path.exists(estado_path):
        with open(estado_path, "r", encoding="utf-8") as fh:
            estados = json.load(fh)

    g = nucleo.Grafo(ts_corrida=ts_corrida, estricto=True)
    ext = extractor_ncmec.ExtractorNCMEC(g)

    rutas = sorted(r for r in glob.glob(os.path.join(dir_datos, "*.json"))
                   if os.path.basename(r) != "estado_institucional.json")
    for ruta in rutas:
        rid = os.path.splitext(os.path.basename(ruta))[0]
        ext.ingerir(ruta, estados.get(rid))

    resultado = dict(
        corrida=g.ts_corrida,
        ontologia_version=ont.ONTOLOGIA_VERSION,
        reportes_ingeridos=len(rutas),
        avisos_extraccion=ext.avisos,
    )

    # 3-4. vinculacion e hipotesis
    resultado["vinculacion"] = resolucion.vincular_reportes(g)
    resultado["contradicciones"] = resolucion.detectar_contradicciones(g)
    resultado["identidades"] = resolucion.proponer_identidades(g)

    # 5. alertas
    resultado["alertas"] = mod_alertas.generar(g)

    # 6. vinculaciones que dispuso una persona.
    # Van antes de agrupar en legajos: si un operador vinculo dos reportes, el
    # sistema tiene que tratarlos como un mismo caso, que es exactamente lo que
    # esa persona esta afirmando.
    libro_vinculos = validacion.LibroVinculos(
        os.path.join(BASE, "estado", "vinculos_manuales.jsonl"))
    resultado["vinculos_manuales"] = libro_vinculos.aplicar(g)

    # 7. algoritmos clasicos
    resultado["legajos"] = analisis.legajos_logicos(g)
    resultado["comunidades"] = analisis.comunidades(g)
    resultado["centralidades"] = analisis.centralidades(g)
    resultado["candidatos_enlace"] = analisis.candidatos_de_enlace(g)
    resultado["cobertura"] = analisis.cobertura_de_datos(g)

    # 8. validaciones humanas previas
    libro = validacion.LibroValidaciones(os.path.join(BASE, "estado", "validaciones.jsonl"))
    resultado["validaciones"] = libro.aplicar(g)
    # Recien ahora, con las decisiones humanas aplicadas, se pueden unificar
    # las identidades que un operador aprobo.
    resultado["identidades_unificadas"] = identidades.consolidar(g)
    resultado["cola_revision"] = validacion.pendientes(g)

    resultado["resumen_grafo"] = g.resumen()

    # 9. salidas
    g.guardar_json(os.path.join(dir_salida, "grafo.json"))
    g.guardar_graphml(os.path.join(dir_salida, "grafo.graphml"))
    with open(os.path.join(dir_salida, "analisis.json"), "w", encoding="utf-8") as fh:
        json.dump(resultado, fh, ensure_ascii=False, indent=1, default=str)

    # Los textos sensibles quedan en un archivo aparte del grafo y del informe.
    with open(os.path.join(dir_salida, "textos_restringidos.json"), "w",
              encoding="utf-8") as fh:
        json.dump(ext.textos, fh, ensure_ascii=False, indent=1)

    dossier = mod_dossier.construir(g, resultado)
    with open(os.path.join(dir_salida, "informe_crudo.json"), "w",
              encoding="utf-8") as fh:
        json.dump(dossier, fh, ensure_ascii=False, indent=1, default=str)

    # El informe discursivo se genera siempre, sin depender de ningun modelo,
    # y viaja embebido en el visor para que el operador lo tenga a mano.
    #
    # Se redacta uno por caso: el informe que firma un operador es de la
    # actuacion que tiene entre manos, no del archivo entero. El general queda
    # como resumen de corrida.
    texto_informe = redaccion.redactar(dossier)
    with open(os.path.join(dir_salida, "informe_vinculaciones.md"), "w",
              encoding="utf-8") as fh:
        fh.write(texto_informe)

    informes_por_caso = {}
    for caso in render_html.casos_de(g, resultado):
        recorte = mod_dossier.recortar(dossier, caso["reportes"])
        informes_por_caso[caso["id"]] = redaccion.redactar(recorte, caso=caso)
    # Se vacia antes de escribir. Los casos se renumeran cuando cambian las
    # vinculaciones, y un informe viejo de un caso que ya no existe es peor que
    # no tenerlo: alguien lo abre y lee una composicion que ya no es.
    dir_casos = os.path.join(dir_salida, "informes_por_caso")
    if not os.path.isdir(dir_casos):
        os.makedirs(dir_casos)
    for viejo in os.listdir(dir_casos):
        if viejo.startswith("informe_") and viejo.endswith(".md"):
            os.remove(os.path.join(dir_casos, viejo))
    for cid, texto in informes_por_caso.items():
        with open(os.path.join(dir_casos, "informe_%s.md" % cid), "w",
                  encoding="utf-8") as fh:
            fh.write(texto)

    docs_modelo.generar(os.path.join(BASE, "MODELO_DATOS.md"), g.resumen())
    render_html.render(g, resultado, os.path.join(dir_salida, "grafo.html"),
                       dossier=dossier, texto_informe=texto_informe,
                       informes_por_caso=informes_por_caso)
    mod_informe.escribir(g, resultado, os.path.join(dir_salida, "informe.md"))
    return g, resultado


def main():
    ap = argparse.ArgumentParser(description="Construye el grafo de la boveda CIJ")
    ap.add_argument("--datos", default=DIR_DATOS)
    ap.add_argument("--salida", default=os.path.join(BASE, "salida"))
    args = ap.parse_args()

    g, res = construir(args.datos, args.salida)
    r = res["resumen_grafo"]
    print("Reportes ingeridos      : %d" % res["reportes_ingeridos"])
    print("Nodos / aristas         : %d / %d" % (r["nodos"], r["aristas"]))
    print("Aristas por origen      : %s" % r["aristas_por_origen"])
    print("Vinculos derivados      : %d (descartados %d)"
          % (len(res["vinculacion"]["vinculos"]), len(res["vinculacion"]["descartados"])))
    print("Contradicciones         : %d" % len(res["contradicciones"]))
    print("Hipotesis de identidad  : %d (unificadas por un operador: %d)"
          % (len(res["identidades"]), len(res["identidades_unificadas"])))
    print("Alertas de reapertura   : %d (silenciadas %d)"
          % (len(res["alertas"]["alertas"]), len(res["alertas"]["silenciadas"])))
    print("Vinculos manuales       : %d (revertidos o huerfanos %d)"
          % (len(res["vinculos_manuales"]["creadas"]),
             len(res["vinculos_manuales"]["huerfanas"])))
    print("Legajos logicos         : %d" % len(res["legajos"]))
    print("Cola de revision humana : %d" % len(res["cola_revision"]))
    print("Incumplimientos de proc.: %d" % r["incumplimientos"])
    print("\nSalidas en %s" % args.salida)


if __name__ == "__main__":
    main()
