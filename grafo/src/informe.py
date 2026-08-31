# -*- coding: utf-8 -*-
"""
Informe en Markdown de una corrida del grafo.

Criterio rector (contexto.md 22): cada hallazgo debe poder responder que conecta,
de donde surge, cuando ocurrio, que metodo lo produjo, con que confianza, quien
lo reviso y que evidencia permite comprobarlo. El informe no repite contenido
sensible: enlaza al locator dentro de la fuente.
"""

import analisis
import ontologia as ont

ENCABEZADO_ADVERTENCIA = """> **Cómo leer este informe.** Todo lo que aparece acá es una *propuesta* del
> sistema. Ninguna relación acredita autoría ni responsabilidad. Las relaciones
> están separadas en tres clases que nunca se mezclan:
>
> - **observada**: consta en un campo del reporte de origen;
> - **derivada**: producto de una regla determinista y reproducible;
> - **inferida**: hipótesis por similitud o modelo, siempre pendiente de validación.
>
> Un reporte archivado no es un caso negativo: describe insuficiencia de
> evidencia en ese momento.
"""


def escribir(g, res, ruta):
    L = []
    a = L.append

    a("# Informe de la corrida del grafo — Bóveda CIJ\n")
    a("- Corrida: `%s`" % res["corrida"])
    a("- Versión de ontología: `%s`" % res["ontologia_version"])
    a("- Reportes ingeridos: **%d**" % res["reportes_ingeridos"])
    r = res["resumen_grafo"]
    a("- Nodos: **%d** · Aristas: **%d** (%s)"
      % (r["nodos"], r["aristas"],
         ", ".join("%s %d" % (k, v) for k, v in sorted(r["aristas_por_origen"].items()))))
    a("- Incumplimientos de procedencia: **%d**\n" % r["incumplimientos"])
    a(ENCABEZADO_ADVERTENCIA)

    # ---------------------------------------------------------------- datos
    a("\n## 1. Qué entró y con cuánto dato\n")
    a("Un reporte sin identificadores no puede vincularse con nada. Esta tabla "
      "explica por qué algunos quedan aislados.\n")
    a("| Reporte | Plataforma | Estado | Motivo de archivo | Identificadores | Vinculable |")
    a("|---|---|---|---|---|---|")
    for c in res["cobertura"]:
        a("| %s | %s | %s | %s | %d %s | %s |"
          % (c["reporte"], c["plataforma"] or "—", c["estado"] or "—",
             c["motivo_archivo"] or "—", c["identificadores"],
             _detalle(c["detalle"]), "sí" if c["vinculable"] else "**no**"))

    # ---------------------------------------------------------- vinculacion
    v = res["vinculacion"]
    a("\n## 2. Vínculos propuestos entre reportes\n")
    a("Pares evaluados por blocking: **%d** sobre %d reportes. "
      "Vínculos materializados: **%d**. Descartados: **%d**.\n"
      % (v["pares_evaluados"], v["reportes"], len(v["vinculos"]), len(v["descartados"])))
    if v["hubs"]:
        a("> Identificadores tipo *hub* que no generaron pares (requieren revisión "
          "manual): %s\n"
          % ", ".join("%s `%s` en %d reportes" % (h["tipo"], h["valor"], h["reportes"])
                      for h in v["hubs"]))
    if v["vinculos"]:
        a("| A | B | Relación | Confianza | Reglas |")
        a("|---|---|---|---|---|")
        for x in sorted(v["vinculos"], key=lambda y: -y["confianza"]):
            a("| %s | %s | %s | **%.2f** (%s) | %s |"
              % (x["reporte_a"], x["reporte_b"], x["relacion"], x["confianza"],
                 ont.franja_confianza(x["confianza"]), ", ".join(sorted(set(x["reglas"])))))
        a("\n<details><summary>Explicación completa de cada vínculo</summary>\n")
        for u, w, k, d in g.aristas(origen=ont.DERIVADA):
            if d["relation_type"] not in ("COINCIDE_CON", "POSIBLE_DUPLICADO_DE"):
                continue
            a("\n**`%s`** — %s" % (d["arista_id"], d["relation_type"]))
            a("```\n%s\n```" % d["explicacion"])
            a("- Método: `%s@%s` · ontología `%s`"
              % (d["method"], d["method_version"], d["ontologia_version"]))
            a("- Evidencia: `%s`" % d["source_locator"])
            a("- Estado de validación: **%s**" % d["validation_status"])
        a("\n</details>\n")

    a("\n### Vínculos descartados y por qué\n")
    a("Se listan explícitamente: un descarte silencioso se lee como *no había nada*.\n")
    if not v["descartados"]:
        a("_Ninguno._")
    else:
        a("| A | B | Confianza | Motivo |")
        a("|---|---|---|---|")
        for x in v["descartados"]:
            a("| %s | %s | %.2f | %s |"
              % (x["reporte_a"], x["reporte_b"], x["confianza"], x["motivo"]))
        a("\n<details><summary>Detalle de las coincidencias descartadas</summary>\n")
        for x in v["descartados"]:
            a("\n**%s ↔ %s**" % (x["reporte_a"], x["reporte_b"]))
            for d in x["disparos"]:
                a(u"- %s — aporte %s, regla `%s`%s"
                  % (_mayus(d["nota"]), ont.numero(d["peso_efectivo"]), d["regla"],
                     u" *(solo corrobora)*" if d["corrobora_solamente"] else u""))
        a("\n</details>\n")

    # ------------------------------------------------------------- alertas
    al = res["alertas"]
    a("\n## 3. Antecedentes que corresponde revisar\n")
    a("Una alerta se emite solo si el vínculo está sostenido por una regla fuerte "
      "**y** el reporte disparador aporta exactamente lo que le faltaba al "
      "archivado.\n")
    if not al["alertas"]:
        a("_Sin alertas._")
    else:
        a("| Prioridad | Archivado | Motivo de archivo | Disparador | Confianza |")
        a("|---|---|---|---|---|")
        for x in al["alertas"]:
            a("| **%s** | %s | %s | %s (%s) | %.2f |"
              % (x["prioridad"].upper(), x["reporte_archivado"], x["motivo_archivo"],
                 x["reporte_disparador"], x["estado_disparador"] or "—",
                 x["confianza_vinculo"] or 0))
        a("")
        for x in al["alertas"]:
            a("\n**%s ← %s** (%s)" % (x["reporte_archivado"], x["reporte_disparador"],
                                      x["prioridad"]))
            a("```\n%s\n```" % x["explicacion"])
            a("- Arista: `%s` · Evidencia: `%s`" % (x["arista_id"], x["locator"]))
    if al["silenciadas"]:
        a("\n<details><summary>Vínculos que NO generaron alerta (%d)</summary>\n"
          % len(al["silenciadas"]))
        for s in al["silenciadas"]:
            a("- %s ← %s: %s" % (s["reporte_archivado"], s["reporte_disparador"],
                                 s["razon"]))
        a("\n</details>\n")

    # ------------------------------------------------------ contradicciones
    a("\n## 4. Contra-evidencia\n")
    a("Vínculos que *debilitan* una atribución. Se modelan explícitamente porque "
      "un grafo que solo acumula coincidencias tiende a confirmar la hipótesis "
      "inicial.\n")
    if not res["contradicciones"]:
        a("_Sin contradicciones detectadas._")
    else:
        for c in res["contradicciones"]:
            a("- `%s`: %.0f km en %.1f h (%.0f km/h) — arista `%s`"
              % (c["ancla"], c["km"], c["horas"], c["kmh"], c["arista_id"]))
        a("")
        for u, w, k, d in g.aristas(relacion="CONTRADICE"):
            a("```\n%s\n```" % d["explicacion"])

    # --------------------------------------------------------- identidades
    a("\n## 5. Hipótesis de identidad\n")
    a("Nunca se fusionan nodos de persona de forma automática. Se propone la "
      "hipótesis con su explicación para que una persona la confirme.\n")
    if not res["identidades"]:
        a("_Sin hipótesis._")
    else:
        for x in res["identidades"]:
            a("- `%s` ↔ `%s` por la cuenta `%s` — arista `%s`"
              % (x["a"], x["b"], x["cuenta"], x["arista_id"]))

    # ----------------------------------------------------------- algoritmos
    a("\n## 6. Estructura del grafo\n")
    a("### Legajos lógicos (componentes conexas)\n")
    if not res["legajos"]:
        a("_Sin agrupamientos._")
    else:
        for l in res["legajos"]:
            a("- **%s**: %s — %d vínculos, confianza %.2f–%.2f%s"
              % (l["legajo"], ", ".join(l["reportes"]), l["vinculos"],
                 l["confianza_min"], l["confianza_max"],
                 " · posibles duplicados: %s" % l["duplicados"] if l["duplicados"] else ""))

    a("\n### Comunidades (Louvain)\n")
    if not res["comunidades"]:
        a("_El grafo todavía no tiene densidad suficiente para que aporte algo "
          "distinto de las componentes conexas._")
    else:
        for c in res["comunidades"]:
            a("- **%s**: %s" % (c["comunidad"], ", ".join(c["reportes"])))

    cen = res["centralidades"]
    a("\n### Centralidades\n")
    a("> %s\n" % analisis.ADVERTENCIA_CENTRALIDAD)
    if cen.get("grado"):
        a("| Métrica | Nodo | Tipo | Valor |")
        a("|---|---|---|---|")
        for metrica in ("grado", "intermediacion", "pagerank"):
            for x in (cen.get(metrica) or [])[:5]:
                a("| %s | %s | %s | %.4f |" % (metrica, x["etiqueta"], x["tipo"], x["valor"]))

    a("\n### Candidatos de enlace (baseline sin modelo)\n")
    a("Pares que ninguna regla determinista sostiene todavía, ordenados por "
      "Adamic-Adar. Sirven para priorizar revisión y como referencia contra la "
      "cual comparar una GNN más adelante. **No se materializan como aristas.**\n")
    if not res["candidatos_enlace"]:
        a("_Sin candidatos._")
    else:
        a("| A | B | Adamic-Adar | Vecinos comunes |")
        a("|---|---|---|---|")
        for c in res["candidatos_enlace"]:
            a("| %s | %s | %.3f | %s |"
              % (c["reporte_a"], c["reporte_b"], c["adamic_adar"],
                 ", ".join("%s:%s" % (x["tipo"], x["etiqueta"])
                           for x in c["vecinos_comunes"][:4])))

    # ------------------------------------------------------------ revision
    a("\n## 7. Cola de revisión humana\n")
    val = res["validaciones"]
    a("Validaciones ya registradas y re-aplicadas: **%d**. "
      "Integridad del libro: %s.\n"
      % (val["aplicadas"],
         "correcta" if not val["integridad"] else "**%s**" % val["integridad"]))
    if val["huerfanas"]:
        a("> %d validaciones quedaron huérfanas: la arista que decidían ya no "
          "existe en esta corrida. Puede indicar un cambio de reglas o de datos.\n"
          % len(val["huerfanas"]))
    cola = res["cola_revision"]
    a("Pendientes: **%d**\n" % len(cola))
    if cola:
        a("| Origen | Relación | A | B | Confianza | Arista |")
        a("|---|---|---|---|---|---|")
        for x in cola[:40]:
            a("| %s | %s | %s | %s | %s | `%s` |"
              % (x["origen"], x["relacion"], x["a"], x["b"],
                 "%.2f" % x["confianza"] if x["confianza"] is not None else "—",
                 x["arista_id"]))

    # --------------------------------------------------------- limitaciones
    a("\n## 8. Qué este módulo NO hace\n")
    a("- No decide reaperturas ni archivos: propone y espera aprobación.")
    a("- No clasifica jurisdicción ni prepara derivaciones territoriales: quedó "
      "fuera de esta etapa por decisión del proyecto.")
    a("- No fusiona identidades automáticamente.")
    a("- No usa reportes archivados como ejemplos negativos.")
    a("- No aplica modelos de lenguaje ni GNN: todo lo derivado es regla explícita.")
    a("- No reemplaza el expediente ni la bóveda de objetos: es una proyección "
      "analítica reconstruible.")
    a("- Las geolocalizaciones son aproximadas y no reemplazan la respuesta del "
      "prestador.")
    if res["avisos_extraccion"]:
        a("\n### Avisos de extracción\n")
        for av in res["avisos_extraccion"]:
            a("- `%s`: %s" % (av["locator"], "; ".join(av["motivo"])))

    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return ruta


def _mayus(texto):
    """Primera letra en mayuscula, sin tocar el resto."""
    if not texto:
        return texto
    return texto[0].upper() + texto[1:]


def _detalle(d):
    if not d:
        return ""
    return "(" + ", ".join("%s×%d" % (k.lower(), v) for k, v in sorted(d.items())) + ")"
