# -*- coding: utf-8 -*-
"""
Orquestador del corte vertical de grafos (contexto.md 21).

  1. ingesta de reportes con preservacion y hash de la fuente
  2. extraccion de entidades y relaciones OBSERVADAS con locator
  3. aplicacion temprana de decisiones sobre datos fuente
  4. vinculacion DERIVADA entre reportes + contradicciones
  5. hipotesis INFERIDAS de identidad
  6. vinculaciones AFIRMADAS que dispuso un operador
  7. aplicacion final de decisiones e invalidacion de consecuencias rechazadas
  8. alertas y algoritmos clasicos sobre el grafo ya revisado
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
import contexto_lugar                  # noqa: E402
import docs_modelo                     # noqa: E402
import docs_tecnicos                   # noqa: E402
import dossier as mod_dossier          # noqa: E402
import redaccion                       # noqa: E402
import extractor_ncmec                 # noqa: E402
import identidades                     # noqa: E402
import informe as mod_informe          # noqa: E402
import multimedia                      # noqa: E402
import nucleo                          # noqa: E402
import ontologia as ont                # noqa: E402
import render_html                     # noqa: E402
import resolucion                      # noqa: E402
import validacion                      # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
# Los reportes viven en la carpeta de trabajo, no dentro del modulo:
# son material del proyecto, no un recurso interno del codigo.
DIR_DATOS = os.path.join(os.path.dirname(BASE), "reportes_sinteticos")
# Banco de pruebas: lo que se deje aca se ingiere junto con el dataset, sin
# mezclarse con el. Queda fuera del repositorio porque puede contener un
# reporte real.
DIR_ENTRADA = os.path.join(BASE, "entrada")


def carpetas(dir_datos):
    """Admite una carpeta o varias. Las ultimas pisan a las primeras si dos
    traen el mismo reporte, que es lo que permite probar una variante sin
    tocar el dataset."""
    if isinstance(dir_datos, (list, tuple)):
        return [d for d in dir_datos if d and os.path.isdir(d)]
    return [dir_datos] if dir_datos and os.path.isdir(dir_datos) else []


def _separar_por_vigencia(items, indice):
    """Separa resultados activos de los que rechazo una persona.

    El grafo conserva ambos para auditoria. Las salidas operativas, en cambio,
    no pueden contar como vigente algo que ya fue rechazado.
    """
    activos, rechazados = [], []
    for original in items:
        item = dict(original)
        d = indice.get(item.get("arista_id"))
        if d:
            item["estado_revision"] = d.get("validation_status")
            item["vigente"] = d.get("vigente", True)
        if d and (not d.get("vigente", True)
                  or d.get("validation_status") == "rechazada"):
            rechazados.append(item)
        else:
            activos.append(item)
    return activos, rechazados


def _sincronizar_resultados_revision(g, resultado):
    """Propaga la ultima decision humana a todas las listas derivadas."""
    indice = {d["arista_id"]: d
              for _, _, _, d in g.aristas(vigentes=False)}

    vinculacion = resultado.get("vinculacion", {})
    generados = vinculacion.get("vinculos", [])
    vigentes, rechazados = _separar_por_vigencia(generados, indice)
    vinculacion["propuestas_generadas"] = len(generados)
    vinculacion["vinculos"] = vigentes
    vinculacion["rechazados_por_operador"] = rechazados

    for clave, clave_rechazadas in (
            ("contradicciones", "contradicciones_rechazadas"),
            ("identidades", "identidades_rechazadas")):
        activos, no_vigentes = _separar_por_vigencia(
            resultado.get(clave, []), indice)
        resultado[clave] = activos
        resultado[clave_rechazadas] = no_vigentes


def _disparos_vigentes(g, disparos):
    """No reutiliza una comparacion que el operador ya rechazo.

    Las coincidencias exactas se indexan desde sus aristas vigentes. Las
    similitudes por pares (pHash cercano y contexto de lugar) llegan como
    disparos adicionales y por eso declaran la arista que las sustenta.
    """
    indice = {d["arista_id"]: d for _, _, _, d in g.aristas(vigentes=False)}
    salida = []
    for disparo in disparos or []:
        soporte = disparo.get("arista_soporte")
        datos = indice.get(soporte) if soporte else None
        if soporte and (not datos or not datos.get("vigente", True)
                        or datos.get("validation_status") == "rechazada"):
            continue
        salida.append(disparo)
    return salida


def construir(dir_datos, dir_salida, ts_corrida=None,
              manifiestos_multimedia=None):
    problemas = ont.validar_ontologia()
    if problemas:
        raise SystemExit("Ontologia inconsistente: %s" % problemas)

    if not os.path.isdir(dir_salida):
        os.makedirs(dir_salida)

    dirs = carpetas(dir_datos)
    estados = {}
    for d in dirs:
        estado_path = os.path.join(d, "estado_institucional.json")
        if os.path.exists(estado_path):
            with open(estado_path, "r", encoding="utf-8") as fh:
                estados.update(json.load(fh))

    g = nucleo.Grafo(ts_corrida=ts_corrida, estricto=True)
    ext = extractor_ncmec.ExtractorNCMEC(g)

    # Un reporte que aparece en dos carpetas se ingiere una sola vez: gana el
    # de la ultima, que es la de entrada.
    por_reporte = {}
    for d in dirs:
        for r in sorted(glob.glob(os.path.join(d, "*.json"))):
            if os.path.basename(r) == "estado_institucional.json":
                continue
            por_reporte[os.path.splitext(os.path.basename(r))[0]] = r
    rutas = [por_reporte[k] for k in sorted(por_reporte)]
    # Cuales vinieron del banco de pruebas: el visor los distingue del dataset
    # del proyecto, para que nadie confunda un reporte que trajo alguien a
    # probar con uno que forma parte del material.
    raiz_entrada = os.path.abspath(DIR_ENTRADA)
    importados = sorted(rid for rid, r in por_reporte.items()
                        if os.path.abspath(os.path.dirname(r)) == raiz_entrada)
    for ruta in rutas:
        rid = os.path.splitext(os.path.basename(ruta))[0]
        ext.ingerir(ruta, estados.get(rid))

    # Los adjuntos llegan por un flujo separado del JSON principal. Se leen
    # solo cuando el llamador pasa manifiestos: la mejora algoritmica no exige
    # cambiar ni elegir ahora ningun almacenamiento.
    carga_multimedia = multimedia.ingerir(g, manifiestos_multimedia or [])
    analisis_multimedia = multimedia.analizar(g, carga_multimedia)

    # Baseline deliberadamente interpretable para contexto de lugar. Solo
    # corrobora otras senales y nunca fusiona dos lugares automaticamente.
    analisis_lugar = contexto_lugar.analizar(g, ext.textos)

    # Las decisiones sobre datos observados o menciones ya existen antes de
    # calcular conexiones. Aplicarlas ahora evita que una arista rechazada
    # vuelva a alimentar una vinculacion, una identidad o una contradiccion.
    libro = validacion.LibroValidaciones(
        os.path.join(BASE, "estado", "validaciones.jsonl"))
    libro.aplicar(g)

    disparos_adicionales = _disparos_vigentes(
        g, (analisis_multimedia.get("disparos", [])
            + analisis_lugar.get("disparos", [])))

    resultado = dict(
        corrida=g.ts_corrida,
        ontologia_version=ont.ONTOLOGIA_VERSION,
        reportes_ingeridos=len(rutas),
        importados=importados,
        avisos_extraccion=ext.avisos,
        multimedia=dict(
            manifiestos=carga_multimedia["manifiestos"],
            archivos=carga_multimedia["archivos"],
            avisos=carga_multimedia["avisos"],
            comparaciones_phash=analisis_multimedia["comparaciones_phash"],
            coincidencias_audio=analisis_multimedia["coincidencias_audio"],
            metodo=analisis_multimedia["metodo"],
            version=analisis_multimedia["version"],
            max_distancia_hamming=analisis_multimedia[
                "max_distancia_hamming"],
            archivos_con_phash=analisis_multimedia["archivos_con_phash"],
            candidatos_phash_evaluados=analisis_multimedia[
                "candidatos_phash_evaluados"],
        ),
        contexto_lugar={k: v for k, v in analisis_lugar.items()
                        if k != "disparos"},
    )

    # 4-5. vinculacion e hipotesis
    resultado["vinculacion"] = resolucion.vincular_reportes(
        g, disparos_adicionales=disparos_adicionales)
    resultado["contradicciones"] = resolucion.detectar_contradicciones(g)
    resultado["identidades"] = resolucion.proponer_identidades(g)

    # 6. vinculaciones que dispuso una persona.
    # Van antes de agrupar en legajos: si un operador vinculo dos reportes, el
    # sistema tiene que tratarlos como un mismo caso, que es exactamente lo que
    # esa persona esta afirmando.
    libro_vinculos = validacion.LibroVinculos(
        os.path.join(BASE, "estado", "vinculos_manuales.jsonl"))
    resultado["vinculos_manuales"] = libro_vinculos.aplicar(g)

    # 7. Las aristas calculadas no existian durante la aplicacion temprana. Se
    # aplica otra vez el mismo libro y se sincronizan las listas de resultados.
    # Desde este punto ningun calculo operativo ve una relacion rechazada.
    resultado["validaciones"] = libro.aplicar(g)
    _sincronizar_resultados_revision(g, resultado)

    # Una identidad se consolida solamente despues de conocer la decision
    # humana vigente sobre cada hipotesis.
    resultado["identidades_unificadas"] = identidades.consolidar(g)

    # 8. Alertas y algoritmos clasicos sobre el grafo ya revisado.
    resultado["alertas"] = mod_alertas.generar(g)
    resultado["legajos"] = analisis.legajos_logicos(g)
    resultado["comunidades"] = analisis.comunidades(g)
    resultado["centralidades"] = analisis.centralidades(g)
    resultado["candidatos_enlace"] = analisis.candidatos_de_enlace(g)
    resultado["cobertura"] = analisis.cobertura_de_datos(g)
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

    # MODELO_DATOS.md y DOCUMENTACION_TECNICA.md estan versionados y publican
    # numeros de la ultima corrida. Si la corrida incluyo reportes del banco de
    # pruebas no se regeneran: esos reportes no estan en el repositorio, asi
    # que nadie podria reproducir esos numeros clonandolo, y ademas cada
    # importacion dejaria el arbol de trabajo sucio sin que nadie haya tocado
    # nada. El grafo, el visor y los informes si se regeneran siempre.
    importados = resultado.get("importados") or []
    if importados:
        print("Documentacion generada: sin cambios, porque la corrida incluye "
              "%d reporte(s) del banco de pruebas (%s)."
              % (len(importados), ", ".join(importados)))
    else:
        docs_modelo.generar(os.path.join(BASE, "MODELO_DATOS.md"), g.resumen())
        docs_tecnicos.generar(os.path.join(os.path.dirname(BASE),
                                           "DOCUMENTACION_TECNICA.md"), g, resultado)
    render_html.render(g, resultado, os.path.join(dir_salida, "grafo.html"),
                       dossier=dossier, texto_informe=texto_informe,
                       informes_por_caso=informes_por_caso)
    mod_informe.escribir(g, resultado, os.path.join(dir_salida, "informe.md"))
    return g, resultado


def main():
    ap = argparse.ArgumentParser(description="Construye el grafo de la boveda CIJ")
    ap.add_argument("--datos", default=[DIR_DATOS, DIR_ENTRADA], nargs="*")
    ap.add_argument(
        "--multimedia", default=[], nargs="*",
        help="uno o mas manifiestos JSON de fileDetails (metadatos, no binarios)")
    ap.add_argument("--salida", default=os.path.join(BASE, "salida"))
    args = ap.parse_args()

    g, res = construir(args.datos, args.salida,
                       manifiestos_multimedia=args.multimedia)
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
