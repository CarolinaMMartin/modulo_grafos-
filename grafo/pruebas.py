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
                              if d["origin"] != ont.OBSERVADA and d.get("confidence") is None]
        check("toda derivada e inferida tiene confianza", not derivadas_sin_conf)
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

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("-" * 60))
    if FALLAS:
        print("FALLARON %d invariantes: %s" % (len(FALLAS), ", ".join(FALLAS)))
        sys.exit(1)
    print("Todos los invariantes se cumplen.")


if __name__ == "__main__":
    main()
