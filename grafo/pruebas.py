# -*- coding: utf-8 -*-
"""
Pruebas de invariantes del modulo de grafos.

No prueban "que el resultado sea lindo": prueban las reglas que el proyecto
declara no negociables. Si alguna falla, hay un problema de diseno, no de
presentacion.

    python pruebas.py
"""

import json
import os
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import construir                        # noqa: E402
import dossier as mod_dossier          # noqa: E402
import normalizacion as nz              # noqa: E402
import redaccion                        # noqa: E402
import render_html                      # noqa: E402
import ontologia as ont                 # noqa: E402
import resolucion                       # noqa: E402
import validacion                       # noqa: E402

FALLAS = []


def check(nombre, condicion, detalle=""):
    if condicion:
        print("  ok    %s" % nombre)
    else:
        print("  FALLA %s %s" % (nombre, detalle))
        FALLAS.append(nombre)


def _corrida(tmp):
    return construir.construir(construir.DIR_DATOS, tmp,
                               ts_corrida="2026-01-01T00:00:00+00:00")


def main():
    tmp = tempfile.mkdtemp(prefix="grafo_pruebas_")
    try:
        g, res = _corrida(tmp)

        print("\n== Ontologia ==")
        check("la ontologia es coherente", not ont.validar_ontologia(),
              str(ont.validar_ontologia()))
        check("toda relacion declara un origen valido",
              all(m["origen"] in ont.ORIGENES for m in ont.RELACIONES.values()))

        print("\n== Procedencia (CLAUDE.md 14.3) ==")
        sin_fuente = [d["arista_id"] for _, _, _, d in g.aristas(vigentes=False)
                      if not d.get("source_evidence_id") or not d.get("source_locator")]
        check("ninguna arista sin fuente ni locator", not sin_fuente, str(sin_fuente[:3]))
        sin_explic = [d["arista_id"] for _, _, _, d in g.aristas(vigentes=False)
                      if not d.get("explicacion")]
        check("toda arista tiene explicacion legible", not sin_explic, str(sin_explic[:3]))
        sin_metodo = [d["arista_id"] for _, _, _, d in g.aristas(vigentes=False)
                      if not d.get("method") or not d.get("method_version")]
        check("toda arista declara metodo y version", not sin_metodo)
        check("no hay incumplimientos registrados", not g.incumplimientos,
              str(g.incumplimientos[:2]))

        print("\n== Separacion epistemologica (CLAUDE.md 10.1) ==")
        inferidas_validadas = [d["arista_id"] for _, _, _, d in g.aristas(vigentes=False)
                               if d["origin"] == ont.INFERIDA
                               and d["validation_status"] == "validada"
                               and not d.get("validated_by")]
        check("ninguna inferencia nace validada", not inferidas_validadas,
              str(inferidas_validadas[:3]))
        derivadas_sin_conf = [d["arista_id"] for _, _, _, d in g.aristas(vigentes=False)
                              if d["origin"] in (ont.DERIVADA, ont.INFERIDA)
                              and d.get("confidence") is None]
        check("toda derivada e inferida tiene confianza", not derivadas_sin_conf)
        # Una afirmacion humana no lleva confianza: no hay nada calculado que
        # ponderar, y un numero ahi seria precision inventada.
        check("ninguna afirmada lleva confianza",
              all(d.get("confidence") is None
                  for _, _, _, d in g.aristas(origen=ont.AFIRMADA, vigentes=False)))
        check("ninguna confianza llega a 1.0",
              all((d.get("confidence") or 0) <= ont.CONFIANZA_MAXIMA
                  for _, _, _, d in g.aristas(vigentes=False)))

        print("\n== Regla 3.5: no se vincula por semejanza contextual ==")
        vinculos = {frozenset((v["reporte_a"], v["reporte_b"]))
                    for v in res["vinculacion"]["vinculos"]}
        # 900000104 solo comparte alias 'lechero' y ciudad con la familia de 255553607
        check("un reporte con solo alias y ciudad NO se vincula",
              frozenset(("255553607", "900000104")) not in vinculos)
        descartado = [d for d in res["vinculacion"]["descartados"]
                      if {d["reporte_a"], d["reporte_b"]} == {"255553607", "900000104"}]
        check("ese descarte queda registrado y explicado",
              bool(descartado) and not descartado[0]["sostenido"])
        for v in res["vinculacion"]["vinculos"]:
            detalle = None
            for u, w, k, d in g.aristas(origen=ont.DERIVADA):
                if d["arista_id"] == v["arista_id"]:
                    detalle = d.get("detalle_reglas")
            if detalle is not None:
                check("vinculo %s-%s sostenido por regla fuerte"
                      % (v["reporte_a"], v["reporte_b"]),
                      any(not x["corrobora_solamente"] for x in detalle))

        print("\n== Identidades: nunca fusion automatica (CLAUDE.md 11.2) ==")
        menciones = g.nodos_tipo("PERSONA_MENCION")
        check("cada mencion de persona es local a su reporte",
              len(menciones) == len({g.G.nodes[n]["reporte"] + "/" + n for n in menciones}))
        # Una hipotesis solo puede dejar de estar pendiente si una persona la
        # decidio: nunca por obra del sistema.
        check("toda hipotesis de identidad es inferida",
              all(d["origin"] == ont.INFERIDA
                  for _, _, _, d in g.aristas(relacion="POSIBLE_MISMA_IDENTIDAD",
                                              vigentes=False)))
        check("una hipotesis solo sale de pendiente por decision humana",
              all(d["validation_status"] == "pendiente" or d.get("validated_by")
                  for _, _, _, d in g.aristas(relacion="POSIBLE_MISMA_IDENTIDAD",
                                              vigentes=False)))

        print("\n== IP: solo vale con fecha, hora y puerto cuando hay NAT ==")
        e164, _ = nz.normalizar_telefono("011 15 6888 9999")
        e164b, _ = nz.normalizar_telefono("+54 9 11 6888-9999")
        check("dos formatos del mismo telefono normalizan igual", e164 == e164b,
              "%s vs %s" % (e164, e164b))
        _, _, rasgos = nz.normalizar_ip("100.66.12.45")
        check("una IP CGNAT se marca como no atribuible sin dato extra",
              rasgos["cgnat"] and not rasgos["atribuible_sin_dato_extra"])
        cgnat = [d for _, _, _, d in g.aristas(relacion="OBSERVADO_DESDE_IP")
                 if d.get("source_evidence_id") == "ncmec:900000102"]
        check("la captura CGNAT sin puerto queda marcada como tal",
              any("CGNAT" in (d.get("explicacion") or "") for d in cgnat))

        print("\n== Alcance de esta etapa ==")
        check("no se produce ninguna clasificacion jurisdiccional",
              "jurisdiccion" not in res)
        check("no hay nodos de jurisdiccion en el grafo",
              not g.nodos_tipo("JURISDICCION"))
        check("no hay aristas de competencia",
              not list(g.aristas(relacion="PERTENECE_A_JURISDICCION")))

        print("\n== Discriminancia estable frente al tamano del corpus ==")
        check("df bajo conserva peso pleno con 10 y con 100000 reportes",
              resolucion.discriminancia(4, 10) == resolucion.discriminancia(4, 100000) == 1.0)
        baja_chico, _ = resolucion.es_baja_discriminancia(4, 10)
        check("un dispositivo en 4 de 10 reportes NO se degrada", not baja_chico)
        baja_hub, _ = resolucion.es_baja_discriminancia(80, 100000)
        check("un identificador en 80 reportes si se degrada", baja_hub)

        print("\n== Contra-evidencia ==")
        check("se detecta al menos un desplazamiento implausible",
              len(res["contradicciones"]) >= 1)

        print("\n== Alertas tipadas ==")
        al = res["alertas"]["alertas"]
        por_arch = {a["reporte_archivado"] for a in al}
        check("el archivado por NAT se reactiva con el telefono",
              any(a["reporte_archivado"] == "900000102"
                  and a["reporte_disparador"] == "900000103" for a in al))
        check("el archivado sin ubicacion se reactiva con una ubicacion",
              any(a["reporte_archivado"] == "900000107"
                  and "ubicacion_determinable" in a["aportes"] for a in al))
        check("un reporte no archivado nunca genera alerta como archivado",
              all(g.G.nodes[ont.nid("REPORTE", r)].get("estado_sipar")
                  in ("archivado", "archivado_latente", "pendiente") for r in por_arch))

        print("\n== Unificacion de identidades ==")
        unif = res["identidades_unificadas"]
        check("hay al menos una identidad unificada en el dataset de prueba",
              len(unif) >= 1, "aprobar con: validar.py unificar <arista>")
        if unif:
            ident = unif[0]
            check("la identidad agrupa menciones de reportes distintos",
                  len(ident["reportes"]) >= 2)
            check("la unificacion registra quien la aprobo", bool(ident["validada_por"]))
            check("las menciones originales siguen existiendo",
                  all(m in g.G for m in ident["menciones"]))
            check("cada mencion conserva su reporte de origen",
                  all(g.G.nodes[m].get("reporte") for m in ident["menciones"]))
            check("las aristas de identidad quedan validadas por una persona",
                  all(d["validation_status"] == "validada" and d.get("validated_by")
                      for _, _, _, d in g.aristas(relacion="IDENTIFICADO_COMO",
                                                  vigentes=False)))
        sin_validar = [d for _, _, _, d in g.aristas(relacion="POSIBLE_MISMA_IDENTIDAD",
                                                     vigentes=False)
                       if d["validation_status"] == "pendiente"]
        check("las hipotesis no aprobadas siguen sin unificar", bool(sin_validar))

        print("\n== Dossier e informe ==")
        d = mod_dossier.construir(g, res)
        check("el dossier registra el peso de cada vinculacion",
              all(v["peso_total"] is not None for v in d["vinculaciones"]))
        check("cada vinculacion detalla el aporte de cada regla",
              all(all("peso_aportado" in r for r in v["sostienen"] + v["corroboran"])
                  for v in d["vinculaciones"]))
        check("toda vinculacion del dossier tiene una regla que la sostiene",
              all(v["sostienen"] for v in d["vinculaciones"]))
        check("el dossier resume los pesos del conjunto",
              d["pesos"].get("cantidad") == len(d["vinculaciones"])
              and d["pesos"].get("peso_promedio") is not None)
        anon, mapa = mod_dossier.seudonimizar(g, d)
        crudo_anon = json.dumps(anon, ensure_ascii=False, default=str)
        filtrados = [v for v in mapa if v in crudo_anon]
        check("ningun identificador real sobrevive en el dossier seudonimizado",
              not filtrados, str(filtrados[:3]))
        check("se seudonimizan IP, cuentas y dispositivos",
              any(e.startswith("IP-") for e in mapa.values())
              and any(e.startswith("CUENTA-") for e in mapa.values())
              and any(e.startswith("DISPOSITIVO-") for e in mapa.values()))
        muestra = u"Se vincula por %s y %s." % (mapa.get("181.46.66.242", "IP-1"),
                                                mapa.get("b534375433e0e502", "DISPOSITIVO-1"))
        check("los identificadores se restituyen sobre el texto devuelto",
              "181.46.66.242" in mod_dossier.restituir(muestra, mapa))

        print("\n== Reproducibilidad e ids estables ==")
        tmp2 = tempfile.mkdtemp(prefix="grafo_pruebas2_")
        try:
            g2, res2 = _corrida(tmp2)
            ids1 = sorted(d["arista_id"] for _, _, _, d in g.aristas(vigentes=False))
            ids2 = sorted(d["arista_id"] for _, _, _, d in g2.aristas(vigentes=False))
            check("dos corridas producen exactamente los mismos ids de arista",
                  ids1 == ids2, "%d vs %d" % (len(ids1), len(ids2)))
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)

        print("\n== Libro de validaciones ==")
        libro = validacion.LibroValidaciones(
            os.path.join(BASE, "estado", "validaciones.jsonl"))
        check("la cadena de hashes del libro es integra", not libro.verificar(),
              str(libro.verificar()))
        check("las validaciones registradas se re-aplican tras reconstruir",
              res["validaciones"]["aplicadas"] == len(libro.registros()))

        print("\n== Minimizacion: el texto sensible no entra al grafo ==")
        with open(os.path.join(tmp, "grafo.json"), "r", encoding="utf-8") as fh:
            crudo = fh.read()
        with open(os.path.join(construir.DIR_DATOS, "255553607.json"), "r",
                  encoding="utf-8") as fh:
            original = json.load(fh)
        bio = (original["reportedInformation"]["reportedPeople"]["reportedPersons"][0]
               .get("profileBio") or "")
        fragmento = bio.strip().split("\n")[0][:30]
        check("la bio del perfil no aparece en grafo.json",
              bool(fragmento) and fragmento not in crudo)
        chat = (original["reportedInformation"]["incidentDetails"]["chatIncident"][0]
                ["notes"][0]["value"])
        check("la transcripcion del chat no aparece en grafo.json",
              chat[:60] not in crudo)
        check("el texto restringido si queda accesible por hash aparte",
              os.path.exists(os.path.join(tmp, "textos_restringidos.json")))

        # ------------------------------------------------------------------
        print("\n== El informe es del caso, no del archivo ==")
        d_total = mod_dossier.construir(g, res)
        casos = render_html.casos_de(g, res)
        # El identificador de legajo es posicional: al vincular dos reportes a
        # mano se renumeran todos. Ninguna prueba puede depender de el, ni de
        # cuantas vinculaciones manuales haya en el libro en un momento dado:
        # un operador usando la aplicacion no puede poner en rojo la suite.
        agrupados = {r for l in res["legajos"] for r in l["reportes"]}
        sueltos = len(g.nodos_tipo("REPORTE")) - len(agrupados)
        check("hay un caso por legajo y uno por reporte suelto",
              len(casos) == len(res["legajos"]) + sueltos,
              str([c["id"] for c in casos]))
        check("ningun reporte queda fuera de todo caso",
              sorted(r for c in casos for r in c["reportes"])
              == sorted(g.G.nodes[n]["valor"] for n in g.nodos_tipo("REPORTE")))

        caso = [c for c in casos if "255553607" in c["reportes"]][0]
        recorte = mod_dossier.recortar(d_total, caso["reportes"])
        check("el dossier del caso solo trae sus reportes",
              sorted(r["reporte"] for r in recorte["reportes"])
              == sorted(caso["reportes"]))
        check("toda vinculacion del caso toca un reporte del caso",
              all(v["reporte_a"] in caso["reportes"] or v["reporte_b"] in caso["reportes"]
                  for v in recorte["vinculaciones"]))
        check("el recorte no arrastra vinculaciones ajenas",
              len(recorte["vinculaciones"]) < len(d_total["vinculaciones"]))
        check("los pesos se recalculan sobre el caso",
              recorte["pesos"]["cantidad"] == len(recorte["vinculaciones"]))

        texto = redaccion.redactar(recorte, caso=caso)
        check("el informe del caso lo dice en el titulo", caso["etiqueta"] in texto)
        check("el informe remite a la carpeta de archivo provisorio",
              u"carpeta de archivo provisorio" in texto)
        ajenos = [c["reportes"][0] for c in casos if c["id"] != caso["id"]]
        check("el informe no detalla reportes de otros casos",
              not any(u"**Reporte %s**" % r in texto for r in ajenos))

        # ------------------------------------------------------------------
        print("\n== El visor no confunde una conclusion con un dato ==")
        check("la identidad unificada no se dibuja como dato del reporte",
              "IDENTIDAD" not in render_html.TIPOS_EN_TARJETA)
        check("todo tipo que se dibuja tiene color de pantalla",
              all(t in render_html.COLOR_VISOR
                  for t in render_html.TIPOS_EN_TARJETA))
        datos_visor = render_html._datos(g, res)
        check("las coincidencias descartadas llegan al visor",
              len(datos_visor["descartados"])
              == len(res["vinculacion"]["descartados"]))
        check("cada descartada dice con que elementos se la evaluo",
              all(x["compartido"] for x in datos_visor["descartados"]))

        # El color del lienzo significa una sola cosa: de que tipo de dato se
        # trata. Si una linea ENTRE reportes toma uno de esos colores, deja de
        # poder distinguirse de la linea de un dato. Paso con el ambar del
        # "posible duplicado", que era el mismo ambar de UBICACION.
        import re as _re
        colores_dato = set(render_html.COLOR_VISOR[t]
                           for t in render_html.TIPOS_EN_TARJETA)
        de_conector = set(_re.findall(r"\.con\.\w+\{[^}]*stroke:(#[0-9a-fA-F]{6})",
                                      render_html.PLANTILLA))
        check("ninguna linea entre reportes usa un color de tipo de dato",
              not (de_conector & colores_dato),
              str(sorted(de_conector & colores_dato)))
        check("cada tipo de dato tiene un color distinto",
              len(colores_dato) == len(render_html.TIPOS_EN_TARJETA))

        # ------------------------------------------------------------------
        print(chr(10)+"== Vinculaciones que dispone una persona ==")
        vm = res["vinculos_manuales"]
        check("el libro de vinculos manuales es integro", not vm["integridad"],
              str(vm["integridad"]))
        libro_vm = validacion.LibroVinculos(
            os.path.join(BASE, "estado", "vinculos_manuales.jsonl"))
        check("se materializan todas las vinculaciones vigentes, y solo esas",
              len(vm["creadas"]) == len(libro_vm.vigentes()) and vm["creadas"],
              "%d creadas / %d vigentes" % (len(vm["creadas"]),
                                            len(libro_vm.vigentes())))
        afirmadas = list(g.aristas(origen=ont.AFIRMADA, vigentes=False))
        check("la vinculacion manual no se confunde con una derivada",
              all(d["relation_type"] == "VINCULADO_POR_OPERADOR"
                  for _, _, _, d in afirmadas))
        check("registra quien la dispuso y cuando",
              all(d.get("validated_by") and d.get("validated_at")
                  for _, _, _, d in afirmadas))
        check("registra el fundamento del operador",
              all(d.get("motivo_operador") for _, _, _, d in afirmadas))
        check("nace validada, porque la validacion es el acto que la crea",
              all(d["validation_status"] == "validada" for _, _, _, d in afirmadas))
        check("conserva la procedencia completa igual que cualquier otra",
              all(d.get("source_evidence_id") and d.get("source_locator")
                  and d.get("explicacion") for _, _, _, d in afirmadas))
        # Lo que el operador espera al vincular: que queden en el mismo caso.
        juntos = [c for c in casos
                  if "900000104" in c["reportes"] and "900000109" in c["reportes"]]
        check("los reportes vinculados a mano quedan en el mismo caso",
              len(juntos) == 1, str([c["reportes"] for c in casos]))
        # Y que sobreviva a reconstruir el grafo desde cero.
        g2, res2 = _corrida(tmp)
        ids1 = sorted(d["arista_id"] for _, _, _, d in afirmadas)
        ids2 = sorted(d["arista_id"]
                      for _, _, _, d in g2.aristas(origen=ont.AFIRMADA, vigentes=False))
        check("la vinculacion manual persiste y conserva su id al reconstruir",
              ids1 == ids2 and ids1, str((ids1, ids2)))

        # ------------------------------------------------------------------
        print(chr(10)+"== La decision se toma en pantalla, no en la consola ==")
        with open(os.path.join(BASE, "servidor.py"), "r", encoding="utf-8") as fh:
            srv = fh.read()
        check("el servidor escucha solo en esta computadora",
              '("127.0.0.1"' in srv and "0.0.0.0" not in srv)
        check("toda escritura pasa por un libro encadenado",
              "LibroVinculos" in srv and "LibroValidaciones" in srv)
        check("despues de escribir se reconstruye el grafo entero",
              "reconstruir()" in srv)
        check("el servidor no sirve archivos arbitrarios",
              "SimpleHTTPRequestHandler" not in srv and "translate_path" not in srv)
        check("el visor pide el fundamento antes de registrar",
              "motivoObligatorio" in render_html.PLANTILLA
              and "dlgMotivo" in render_html.PLANTILLA)
        check("el visor ya no le pide a nadie que copie un comando",
              "Copiar el comando" not in render_html.PLANTILLA)
        check("abierto como archivo suelto, el boton explica en vez de fallar",
              "Hay que abrir la aplicación" in render_html.PLANTILLA)
        # Una coincidencia descartada se muestra en tres fichas -la del caso, la
        # del reporte y la del dato- y en las tres el operador tiene que poder
        # discrepar. El boton falto una vez justamente en la del dato.
        check("las tres fichas que muestran una descartada ofrecen vincular",
              render_html.PLANTILLA.count("botonVincular(") == 4)
        check("la tarjeta de descartada trae el boton adentro",
              "botonVincular(x.a, x.b)" in render_html.PLANTILLA)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("-" * 60))
    if FALLAS:
        print("FALLARON %d invariantes: %s" % (len(FALLAS), ", ".join(FALLAS)))
        sys.exit(1)
    print("Todos los invariantes se cumplen.")


if __name__ == "__main__":
    main()
