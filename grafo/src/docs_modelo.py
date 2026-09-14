# -*- coding: utf-8 -*-
"""
Genera MODELO_DATOS.md a partir de ontologia.py.

Se genera en vez de escribirse a mano para que la documentacion no se
desincronice de las reglas que realmente corren.
"""

import ontologia as ont


def generar(ruta, resumen=None):
    L = []
    a = L.append
    a("<!-- GENERADO POR src/docs_modelo.py A PARTIR DE src/ontologia.py.")
    a("     No editar a mano: los cambios se pisan en la proxima construccion. -->\n")
    a("# Modelo de datos del grafo — Bóveda CIJ\n")
    a("Versión de ontología: **`%s`**\n" % ont.ONTOLOGIA_VERSION)
    a("Ontología preliminar. Debe validarse con los equipos jurídicos e "
      "institucionales antes de considerarse estable (contexto.md 10.2).\n")

    a("## 1. Clases de relación\n")
    a("Las %d clases nunca se mezclan, ni en la persistencia ni en la interfaz.\n"
      % len(ont.ORIGENES))
    a("| Clase | Qué significa | Estado inicial de validación |")
    a("|---|---|---|")
    for origen in ont.ORIGENES:
        a("| `%s` | %s | `%s` |"
          % (origen, ont.DESCRIPCION_ORIGEN[origen],
             ont.ESTADO_INICIAL[origen]))

    a("\n## 2. Tipos de nodo\n")
    a("`identificador`: el valor es un dato objetivo apto para sostener un vínculo "
      "entre reportes. `fusionable`: dos menciones del mismo valor son el mismo "
      "objeto — las personas **no** lo son.\n")
    a("| Tipo | Identificador | Fusionable | Descripción |")
    a("|---|---|---|---|")
    for t, m in ont.TIPOS_NODO.items():
        a("| `%s` | %s | %s | %s |"
          % (t, "sí" if m["identificador"] else "no",
             "sí" if m["fusionable"] else "**no**", m["desc"]))

    a("\n## 3. Vocabulario de relaciones\n")
    titulos = {
        ont.OBSERVADA: "Observadas",
        ont.DERIVADA: "Derivadas",
        ont.INFERIDA: "Inferidas",
        ont.AFIRMADA: "Afirmadas por una persona",
    }
    for clase in ont.ORIGENES:
        titulo = titulos[clase]
        a("\n### %s\n" % titulo)
        a("| Relación | Descripción |")
        a("|---|---|")
        for r, m in ont.RELACIONES.items():
            if m["origen"] == clase:
                a("| `%s` | %s |" % (r, m["desc"]))

    a("\n## 4. Metadatos obligatorios de cada arista\n")
    a("Si falta la fuente, el locator o la explicación, la arista **no se crea**: "
      "se registra un incumplimiento. Es preferible perder un vínculo a tener uno "
      "que no se pueda explicar.\n")
    a("| Campo | Para qué |")
    a("|---|---|")
    for campo, para in [
        ("`arista_id`", "identificador determinista: (extremos, relación, método, locator, fuente)"),
        ("`relation_type`", "relación del vocabulario controlado"),
        ("`origin`", "una de las clases declaradas en `ORIGENES`"),
        ("`source_evidence_id`", "qué evidencia la sostiene"),
        ("`source_locator`", "ubicación exacta dentro de esa evidencia: campo JSON, página, timestamp, frame"),
        ("`method` / `method_version`", "qué produjo la arista y con qué versión"),
        ("`ontologia_version`", "con qué vocabulario y pesos se calculó"),
        ("`confidence`", "nombre técnico heredado del puntaje no calibrado; obligatorio para derivadas e inferidas, no equivale a una probabilidad"),
        ("`confidence_calibrated`", "`false` para todo puntaje calculado en esta demo"),
        ("`observed_at`", "cuándo ocurrió el hecho, distinto de cuándo se calculó"),
        ("`created_at`", "cuándo se produjo la arista"),
        ("`validation_status` / `validated_by` / `validated_at`", "revisión humana"),
        ("`case_scope`", "alcance y permisos"),
        ("`explicacion`", "por qué existe, en lenguaje legible"),
        ("`vigente`", "una arista rechazada se marca, no se borra"),
    ]:
        a("| %s | %s |" % (campo, para))

    a("\n## 5. Reglas deterministas de vinculación\n")
    a("`corrobora solamente`: nunca sostiene un vínculo por sí sola, solo refuerza "
      "otro sostenido por un dato objetivo fuerte. Es la traducción de la regla del "
      "relevamiento 3.5.\n")
    a("| Regla | Ver. | Tipo | Peso base | Corrobora solamente | Pondera por rareza | Qué detecta |")
    a("|---|---|---|---|---|---|---|")
    for r, m in ont.REGLAS.items():
        a("| `%s` | %s | `%s` | %.2f | %s | %s | %s |"
          % (r, m["version"], m["tipo_nodo"], m["peso_base"],
             "sí" if m["corrobora_solamente"] else "no",
             "sí" if m["usa_discriminancia"] else "no", m["desc"]))

    a("\n### Combinación\n")
    a("Noisy-OR sobre las reglas que disparan, **solo si al menos una sostiene el "
      "vínculo por sí sola**. El resultado es un puntaje de priorización no "
      "calibrado, aunque por compatibilidad el campo se llame `confidence`; no "
      "es una probabilidad. Puntaje máximo `%.2f`.\n" % ont.CONFIANZA_MAXIMA)

    a("\n### Discriminancia\n")
    a("- Hasta `df = %d` reportes, el identificador conserva su peso completo.\n"
      "- Por encima, el peso decae logarítmicamente.\n"
      "- Desde `df = %d` deja de poder sostener un vínculo solo.\n"
      "- La expansión combinatoria se limita por cantidad de pares y por tipo; "
      "si supera el límite, se conserva como grupo compacto con todos sus reportes.\n"
      "- La fracción sobre el corpus (`%.0f %%`) recién se aplica con al menos %d "
      "reportes: con un corpus chico engaña."
      % (ont.DF_PLENA_DISCRIMINANCIA, ont.DF_HUB_ABSOLUTO,
         ont.FRACCION_BAJA_DISCRIMINANCIA * 100, ont.CORPUS_MINIMO_PARA_FRACCION))
    a("\n| Tipo | Máximo de pares antes de compactar |")
    a("|---|---:|")
    for tipo, limite in sorted(ont.MAX_PARES_POR_TIPO.items()):
        a("| `%s` | %d |" % (tipo, limite))

    a("\n## 6. Política de IP\n")
    a("Una IP aislada no identifica a una persona. Se valora junto con fecha, hora, "
      "prestador y puerto.\n")
    a("| Prestador | Ventana temporal asumida |")
    a("|---|---|")
    for k, v in ont.VENTANA_IP_HORAS.items():
        a("| %s | %d h |" % ("*(default)*" if k == "_default" else k, v))
    a("\n- Rango CGNAT: `%s`." % ont.CGNAT_RED)
    a("- CGNAT **sin** puerto de origen: el peso se multiplica por `%.2f` y la regla "
      "pasa a corroborar solamente. El prestador no puede identificar al abonado."
      % ont.FACTOR_NAT_SIN_PUERTO)
    a("- CGNAT **con** puerto y timestamp: factor `%.2f`, la atribución vuelve a ser "
      "posible." % ont.FACTOR_NAT_CON_PUERTO)
    a("- Las fechas se manejan en UTC. Un valor sin zona horaria se marca como "
      "supuesto: tres horas de corrimiento alcanzan para atribuir una conexión al "
      "abonado equivocado.")

    a("\n## 7. Umbrales\n")
    a("| Umbral | Valor | Qué controla |")
    a("|---|---|---|")
    a("| `UMBRAL_PROPONER` | %.2f | debajo de esto no se materializa la arista |"
      % ont.UMBRAL_PROPONER)
    a("| `UMBRAL_PROBABLE` | %.2f | franja media del puntaje interno |" % ont.UMBRAL_PROBABLE)
    a("| `UMBRAL_ALTA` | %.2f | franja alta del puntaje interno |" % ont.UMBRAL_ALTA)
    a("| `UMBRAL_CLUSTER` | %.2f | mínimo para agrupar en un legajo lógico y para "
      "emitir alertas |" % ont.UMBRAL_CLUSTER)

    if resumen:
        a("\n## 8. Estado de la última construcción\n")
        a("- Nodos: **%d** · Aristas: **%d**" % (resumen["nodos"], resumen["aristas"]))
        a("- Por origen: %s"
          % ", ".join("%s %d" % (k, v) for k, v in sorted(resumen["aristas_por_origen"].items())))
        a("- Incumplimientos de procedencia: **%d**" % resumen["incumplimientos"])
        a("\n| Tipo de nodo | Cantidad |")
        a("|---|---|")
        for t, c in sorted(resumen["nodos_por_tipo"].items(), key=lambda x: -x[1]):
            a("| `%s` | %d |" % (t, c))

    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return ruta
