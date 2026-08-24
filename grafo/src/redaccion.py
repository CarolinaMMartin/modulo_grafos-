# -*- coding: utf-8 -*-
"""
Redaccion del informe de vinculaciones a partir del dossier crudo.

Produce prosa juridica de forma determinista, sin ningun modelo. El informe
queda disponible en cada corrida y en el visor, sin depender de que haya
infraestructura de IA levantada.
"""

import ontologia as ont


def redactar(d):
    """Redaccion determinista del informe de vinculaciones.

    Es la que se genera siempre, en cada construccion, para que el operador
    tenga el informe a mano sin depender de nada. Cuando haya un modelo local
    disponible, informe_ia.py usa este mismo dossier para producir una version
    mas fluida.
    """
    n = ont.numero
    L = []
    a = L.append
    a(u"# Informe de vinculaciones\n")
    a(u"## I. Objeto y alcance\n")
    a(u"El presente informe reúne las vinculaciones que el sistema detectó entre "
      u"los %s reportes analizados en la corrida del %s. Se evaluaron %s pares de "
      u"reportes que compartían al menos un identificador.\n"
      % (d["meta"]["reportes_analizados"], d["meta"]["corrida"],
         d["meta"]["pares_evaluados"]))
    a(u"Todas las vinculaciones que siguen son propuestas del sistema. Ninguna "
      u"acredita autoría ni responsabilidad, y todas requieren validación de un "
      u"operador antes de incorporarse a una actuación.\n")

    a(u"## II. Material analizado\n")
    for r in d["reportes"]:
        ident = u"; ".join(u"%s: %s" % (k, u", ".join(v))
                           for k, v in sorted(r["identificadores"].items()))
        a(u"- **Reporte %s** — plataforma %s, clasificado como %s, hecho del %s, "
          u"actualmente %s%s. Identificadores: %s."
          % (r["reporte"], r["plataforma"] or u"no informada",
             r["clasificacion"] or u"sin clasificar",
             (r["fecha_del_hecho"] or u"fecha no informada")[:10],
             (r["estado"] or u"sin estado").replace("_", " "),
             u" (archivado %s)" % r["motivo_de_archivo"].replace("_", " ")
             if r.get("motivo_de_archivo") else u"", ident or u"ninguno"))
    a(u"")

    a(u"## III. Vinculaciones detectadas\n")
    if not d["vinculaciones"]:
        a(u"El sistema no detectó vinculaciones que superaran el umbral mínimo.\n")
    for v in d["vinculaciones"]:
        a(u"### Reportes %s y %s\n" % (v["reporte_a"], v["reporte_b"]))
        a(v["fundamento"] + u"\n")

    a(u"## IV. Peso de las vinculaciones\n")
    p = d["pesos"]
    if p.get("cantidad"):
        a(u"Se propusieron %d vinculaciones. El peso promedio es de %s, con un "
          u"máximo de %s y un mínimo de %s. El umbral por debajo del cual una "
          u"coincidencia no se propone es %s, y ninguna vinculación puede superar "
          u"%s: el sistema no produce certezas absolutas.\n"
          % (p["cantidad"], n(p["peso_promedio"]), n(p["peso_maximo"]),
             n(p["peso_minimo"]), n(p["umbral_para_proponer"]),
             n(p["peso_maximo_posible"])))
        a(u"Por franja de confianza: %s.\n"
          % u", ".join(u"%d de confianza %s" % (c, f)
                       for f, c in p["por_franja"].items() if c))
        a(u"El aporte de cada regla al conjunto fue el siguiente:\n")
        a(u"| Regla | Qué detecta | Veces que operó | Aporte promedio |")
        a(u"|---|---|---|---|")
        for regla, datos in p["aporte_por_regla"].items():
            a(u"| `%s` | %s | %d | %s |"
              % (regla, d["glosario_de_reglas"][regla]["descripcion"],
                 datos["veces"], n(datos["aporte_promedio"])))
        a(u"")
        a(u"Conviene precisar cómo se compone ese peso. Cada elemento coincidente "
          u"aporta un valor propio, que se ajusta según con qué frecuencia ese "
          u"identificador aparece en el conjunto: un dato que se repite en muchos "
          u"reportes individualiza menos y pesa menos. Los elementos que el "
          u"sistema marca como corroborantes —el nombre visible, la zona "
          u"estimada, una dirección IP fuera de su ventana temporal— nunca "
          u"sostienen una vinculación por sí solos: únicamente refuerzan otra que "
          u"ya se apoya en un dato objetivo.\n")

    a(u"## V. Antecedentes archivados que corresponde revisar\n")
    if not d["antecedentes_reactivados"]:
        a(u"Ningún reporte archivado quedó reactivado en esta corrida.\n")
    for x in d["antecedentes_reactivados"]:
        a(u"### Reporte %s (prioridad %s)\n" % (x["reporte_archivado"], x["prioridad"]))
        a(x["fundamento"] + u"\n")

    a(u"## VI. Elementos que debilitan las vinculaciones\n")
    if not d["contra_evidencia"]:
        a(u"El sistema no detectó elementos que contradigan las vinculaciones "
          u"propuestas.\n")
    for c in d["contra_evidencia"]:
        a(c["fundamento"] + u"\n")

    a(u"## VII. Coincidencias descartadas\n")
    if not d["vinculaciones_descartadas"]:
        a(u"No hubo coincidencias descartadas.\n")
    else:
        a(u"Las siguientes coincidencias se evaluaron y no dieron lugar a una "
          u"vinculación. Se dejan asentadas para que su ausencia no se lea como "
          u"falta de análisis.\n")
        for x in d["vinculaciones_descartadas"]:
            elementos = u"; ".join(e["redaccion"] for e in x["elementos"])
            a(u"- **Reportes %s y %s.** %s Elementos considerados: %s.\n"
              % (x["reporte_a"], x["reporte_b"], x["motivo"], elementos))

    a(u"## VIII. Limitaciones y advertencias\n")
    for adv in d["meta"]["advertencias"]:
        a(u"- %s" % adv)
    a(u"- Quedan %d relaciones pendientes de revisión humana."
      % d["pendientes_de_revision"])
    a(u"- Las hipótesis de identidad no unifican personas: solo señalan que dos "
      u"menciones podrían corresponder a la misma, y requieren confirmación.")
    return u"\n".join(L) + u"\n"
