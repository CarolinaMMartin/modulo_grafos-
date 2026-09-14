# -*- coding: utf-8 -*-
"""
Redaccion del informe de vinculaciones a partir del dossier crudo.

Produce prosa juridica de forma determinista, sin ningun modelo. El informe
queda disponible en cada corrida y en el visor, sin depender de que haya
infraestructura de IA levantada.
"""

import ontologia as ont


def _enumerar(xs):
    """Enumeracion en castellano: "A, B y C". Se escribe para que lo lea una
    persona, no para que lo parsee un programa."""
    xs = [u"el reporte %s" % x for x in xs]
    if not xs:
        return u"ningún reporte"
    if len(xs) == 1:
        return xs[0]
    return u", ".join(xs[:-1]) + u" y " + xs[-1]


def redactar(d, caso=None):
    """Redaccion determinista del informe de vinculaciones.

    Es la que se genera siempre, en cada construccion, para que el operador
    tenga el informe a mano sin depender de nada. Cuando haya un modelo local
    disponible, informe_ia.py usa este mismo dossier para producir una version
    mas fluida.

    Con `caso` -{"etiqueta": ..., "reporte_en_analisis": ...}- el informe es del
    caso y no del archivo entero. Es como se firma: un informe por actuacion.
    """
    n = ont.numero
    L = []
    a = L.append
    reportes = [r["reporte"] for r in d["reportes"]]

    if caso:
        a(u"# Informe de vinculaciones — %s\n" % caso["etiqueta"])
        a(u"## I. Objeto y alcance\n")
        a(u"El presente informe se refiere exclusivamente al caso en análisis, "
          u"integrado por %s. Reúne las vinculaciones que el sistema propone "
          u"entre esos reportes y los antecedentes que corresponde revisar a "
          u"partir de ellos.\n" % _enumerar(reportes))
        a(u"El análisis se ejecutó sobre la totalidad del archivo en la corrida "
          u"del %s, en la que se evaluaron %s pares de reportes que compartían "
          u"al menos un identificador. De ese análisis se extrae aquí únicamente "
          u"lo que alcanza a este caso.\n"
          % (d["meta"]["corrida"], d["meta"]["pares_evaluados"]))
    else:
        a(u"# Informe de vinculaciones\n")
        a(u"## I. Objeto y alcance\n")
        a(u"El presente informe reúne las vinculaciones que el sistema detectó "
          u"entre los %s reportes analizados en la corrida del %s. Se evaluaron "
          u"%s pares de reportes que compartían al menos un identificador.\n"
          % (d["meta"]["reportes_analizados"], d["meta"]["corrida"],
             d["meta"]["pares_evaluados"]))

    a(u"Todas las vinculaciones que siguen son propuestas del sistema. Ninguna "
      u"acredita autoría ni responsabilidad, y todas requieren validación de un "
      u"operador antes de incorporarse a una actuación.\n")

    a(u"## II. Material analizado\n")
    a(u"El material examinado es el que integra este caso: %s. El detalle de "
      u"cada uno figura a continuación.\n" % _enumerar(reportes))
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
    a(u"El resto del material sobre el que se ejecutó el análisis permanece en "
      u"la **carpeta de archivo provisorio** y no se enumera en este informe. "
      u"Esa carpeta reúne los reportes que en su momento se archivaron por "
      u"insuficiencia de evidencia y los que continúan en trámite en otras "
      u"actuaciones. Se conserva íntegra y consultable, y es la que el sistema "
      u"recorre en cada corrida para detectar antecedentes: por eso un reporte "
      u"archivado puede reactivarse cuando aparece el dato que le faltaba. "
      u"Enumerarla aquí no aportaría nada al caso e incorporaría al informe "
      u"material ajeno a él.\n")

    a(u"## III. Vinculaciones detectadas\n")
    if not d["vinculaciones"]:
        a(u"El sistema no detectó vinculaciones que superaran el umbral mínimo.\n")
    for v in d["vinculaciones"]:
        a(u"### Reportes %s y %s\n" % (v["reporte_a"], v["reporte_b"]))
        a(v["fundamento"] + u"\n")

    a(u"## III bis. Vinculaciones establecidas por un operador\n")
    manuales = d.get("vinculaciones_manuales") or []
    if not manuales:
        a(u"No se estableció ninguna vinculación por decisión de un operador.\n")
    else:
        a(u"Las siguientes vinculaciones no las propuso el sistema. Las dispuso "
          u"una persona por su propio criterio, y por eso no llevan peso: no hay "
          u"un cálculo que ponderar, hay una decisión y su fundamento.\n")
        for m in manuales:
            a(u"### Reportes %s y %s\n" % (m["reporte_a"], m["reporte_b"]))
            a(u"Vinculación establecida por %s%s.\n"
              % (m.get("dispuesta_por") or u"un operador",
                 u" el %s" % m["fecha"][:10] if m.get("fecha") else u""))
            if m.get("motivo"):
                a(u"Fundamento registrado: «%s»\n" % m["motivo"])
            a(u"Se conserva hasta que se revierta desde el libro de "
              u"vinculaciones, y la reversión también queda asentada.\n")

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
        a(u"Por franja de puntaje: %s.\n"
          % u", ".join(u"%d con puntaje %s" % (c, f)
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
        if caso:
            a(u"Algunos de los reportes que se nombran a continuación no "
              u"integran este caso y pertenecen a otras actuaciones o a la "
              u"carpeta de archivo provisorio. Figuran únicamente porque se los "
              u"comparó con los de este caso y la comparación no prosperó.\n")
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
