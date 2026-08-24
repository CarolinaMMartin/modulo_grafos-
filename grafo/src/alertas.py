# -*- coding: utf-8 -*-
"""
Alertas de reapertura tipadas por motivo de archivo.

Idea central: un reporte archivado no se reabre porque "aparecio una conexion".
Se reabre porque aparecio EL DATO QUE LE FALTABA. El motivo de archivo define
que aporte lo reactiva, y esa correspondencia es lo que evita inundar al
operador con alertas irrelevantes.

Una alerta requiere DOS condiciones independientes:

  1. que el vinculo entre reportes este sostenido por una regla determinista
     fuerte (no alcanza una corroboracion contextual), y
  2. que el reporte disparador APORTE efectivamente lo que le faltaba al
     archivado.

Sin la segunda condicion, cualquier coincidencia genera ruido: un vinculo por
dispositivo no resuelve un archivo por falta de datos de ubicacion, y un vinculo
por telefono no resuelve un archivo por ausencia de archivos.

El archivo describe insuficiencia actual de evidencia, no falsedad del hecho
(CLAUDE.md 3 y 14.14). El archivado nunca se trata como caso negativo.
"""

from collections import defaultdict

import ontologia as ont

METODO = "alertas_reapertura"
VERSION = "2.0"

ESTADOS_ARCHIVADOS = {"archivado", "archivado_latente", "pendiente"}
ESTADOS_ACTIVOS = {"en_analisis", "en_investigacion", "derivado", "judicializado"}

TIPOS_ATRIBUIBLES = {"CUENTA", "DISPOSITIVO", "TELEFONO", "EMAIL"}


# ---------------------------------------------------------------------------
# Que aporta un reporte (se evalua sobre el reporte disparador)
# ---------------------------------------------------------------------------
def _aportes_de(g, n_rep):
    """Inventario de lo que un reporte puede ofrecerle a otro."""
    rid = g.G.nodes[n_rep]["valor"]
    sid = "ncmec:%s" % rid
    aportes = defaultdict(list)

    for u, v, k, d in g.aristas():
        if d.get("source_evidence_id") != sid:
            continue
        for n in (u, v):
            nodo = g.G.nodes[n]
            tipo = nodo.get("tipo")
            if tipo in TIPOS_ATRIBUIBLES:
                aportes["identificador_atribuible"].append(
                    dict(tipo=tipo, valor=nodo.get("etiqueta"), locator=d["source_locator"]))
            elif tipo == "EVIDENCIA":
                aportes["evidencia_con_hash"].append(
                    dict(tipo=tipo, valor=nodo.get("etiqueta"), locator=d["source_locator"]))
            elif tipo == "IP" and d["relation_type"] == "OBSERVADO_DESDE_IP":
                atribuible = (nodo.get("atribuible_sin_dato_extra")
                              or bool(d.get("puerto")))
                if atribuible and d.get("observed_at"):
                    aportes["ip_atribuible"].append(
                        dict(tipo=tipo, valor=nodo.get("valor"),
                             fecha=d.get("observed_at"), puerto=d.get("puerto"),
                             locator=d["source_locator"]))

    # Nota: la clasificacion jurisdiccional quedo fuera de esta etapa. Lo que se
    # evalua ahora es si el reporte aporta una ubicacion utilizable, que es el
    # dato en si; que se haga con el es una decision posterior.
    for u, v, k, d in g.aristas():
        if d.get("source_evidence_id") != sid:
            continue
        if g.G.nodes[v].get("tipo") != "UBICACION":
            continue
        if d["relation_type"] not in ("GEOLOCALIZA_EN", "UBICADO_EN"):
            continue
        aportes["ubicacion_determinable"].append(
            dict(tipo="UBICACION", valor=g.G.nodes[v].get("valor"),
                 origen=(u"geolocalización de la IP"
                         if d["relation_type"] == "GEOLOCALIZA_EN"
                         else u"declarada por la plataforma"),
                 locator=d["source_locator"]))

    estado = (g.G.nodes[n_rep].get("estado_sipar") or "").lower()
    prioridad = (g.G.nodes[n_rep].get("prioridad") or "").upper()
    if estado in ESTADOS_ACTIVOS or prioridad in ("1", "2"):
        aportes["caso_con_merito"].append(
            dict(tipo="REPORTE", valor=rid,
                 detalle="estado %s, prioridad %s" % (estado or "s/d", prioridad or "s/d"),
                 locator="estado_institucional"))

    # Un mismo identificador alcanzado por varias aristas del reporte se cuenta
    # una sola vez: lo que importa es que el dato exista, no cuantas veces.
    for clave, items in aportes.items():
        unicos, claves = [], set()
        for x in items:
            ck = (x.get("tipo"), x.get("valor"))
            if ck in claves:
                continue
            claves.add(ck)
            unicos.append(x)
        aportes[clave] = unicos
    return aportes


# motivo_archivo -> que aporte lo reactiva y con que prioridad
DISPARADORES = {
    "sin_datos_de_usuario": dict(
        aportes=("identificador_atribuible",), prioridad="alta",
        texto=u"porque no contaba con datos de usuario que permitieran "
              u"individualizar a nadie"),
    "no_atribuible_nat": dict(
        aportes=("identificador_atribuible", "ip_atribuible"), prioridad="alta",
        texto=u"porque la dirección IP registrada se encontraba bajo NAT y no "
              u"permitía atribuir la conexión a un abonado determinado"),
    "sin_archivos": dict(
        aportes=("evidencia_con_hash",), prioridad="alta",
        texto=u"porque no se acompañó ningún archivo que pudiera analizarse"),
    "sin_ubicacion": dict(
        aportes=("ubicacion_determinable", "ip_atribuible"), prioridad="media",
        texto=u"porque no contaba con ningún dato de ubicación utilizable"),
    "material_sin_relevancia": dict(
        aportes=("caso_con_merito", "evidencia_con_hash"), prioridad="media",
        texto=u"porque, considerado de forma aislada, el material no presentaba "
              u"relevancia suficiente"),
    "_default": dict(
        aportes=("identificador_atribuible", "evidencia_con_hash",
                 "ip_atribuible", "caso_con_merito"), prioridad="media",
        texto=u"por insuficiencia de elementos"),
}

ESTADO_LEGIBLE = {
    "en_analisis": u"en análisis",
    "en_investigacion": u"en investigación",
    "derivado": u"derivado a otra jurisdicción",
    "judicializado": u"judicializado",
    "archivado": u"archivado",
    "archivado_latente": u"archivado de forma latente",
    "pendiente": u"pendiente",
}


def _fecha(iso):
    """Fecha en formato local: 14/03/2026."""
    if not iso:
        return u""
    partes = str(iso)[:10].split("-")
    if len(partes) != 3:
        return str(iso)
    return u"%s/%s/%s" % (partes[2], partes[1], partes[0])


def _enumerar(frases, separador=u", ", conector=u" y "):
    frases = [f for f in frases if f]
    if not frases:
        return u""
    if len(frases) == 1:
        return frases[0]
    return u"%s%s%s" % (separador.join(frases[:-1]), conector, frases[-1])


NOMBRE_APORTE = {
    "identificador_atribuible": u"un identificador que permite individualizar",
    "ip_atribuible": u"una dirección IP atribuible, con fecha y hora",
    "evidencia_con_hash": u"un archivo identificado por su hash",
    "ubicacion_determinable": u"un dato de ubicación utilizable",
    "caso_con_merito": u"su condición de actuación con mérito para avanzar",
}


def generar(g, umbral=None):
    umbral = ont.UMBRAL_CLUSTER if umbral is None else umbral
    alertas = []
    cache_aportes = {}
    silenciadas = []

    for u, v, k, d in g.aristas(origen=ont.DERIVADA):
        if d["relation_type"] not in ("COINCIDE_CON", "POSIBLE_DUPLICADO_DE"):
            continue
        if (d.get("confidence") or 0) < umbral:
            continue
        if d.get("validation_status") == "rechazada":
            continue

        sostenes = [x for x in (d.get("detalle_reglas") or [])
                    if not x.get("corrobora_solamente")]
        if not sostenes:
            continue

        for archivado, otro in ((u, v), (v, u)):
            a, b = g.G.nodes[archivado], g.G.nodes[otro]
            if (a.get("estado_sipar") or "").lower() not in ESTADOS_ARCHIVADOS:
                continue

            motivo = a.get("motivo_archivo") or "_default"
            regla = DISPARADORES.get(motivo, DISPARADORES["_default"])

            if otro not in cache_aportes:
                cache_aportes[otro] = _aportes_de(g, otro)
            aportes = cache_aportes[otro]

            coincidentes = {clave: aportes[clave] for clave in regla["aportes"]
                            if aportes.get(clave)}
            if not coincidentes:
                silenciadas.append(dict(
                    reporte_archivado=a["valor"], reporte_disparador=b["valor"],
                    motivo_archivo=motivo,
                    razon=(u"La vinculación existe, pero el reporte %s no aporta lo "
                           u"que le faltaba al archivado. Para reactivarlo haría "
                           u"falta %s."
                           % (b["valor"],
                              u" o ".join(NOMBRE_APORTE.get(x, x)
                                          for x in regla["aportes"])))))
                continue

            prioridad = regla["prioridad"]
            if (b.get("estado_sipar") or "").lower() in ESTADOS_ARCHIVADOS:
                # Dos archivados vinculados importan, pero no hay un caso activo
                # que traccione la revision.
                prioridad = "media" if prioridad == "alta" else "baja"

            detalle = []
            for clave, items in coincidentes.items():
                muestras = ", ".join(str(x.get("valor")) for x in items[:3])
                detalle.append(u"%s (%s)"
                               % (NOMBRE_APORTE.get(clave, clave), muestras))

            estado_b = ESTADO_LEGIBLE.get((b.get("estado_sipar") or u"").lower(),
                                          (b.get("estado_sipar") or u"").replace("_", " "))
            alertas.append(dict(
                reporte_archivado=a["valor"],
                motivo_archivo=motivo,
                reporte_disparador=b["valor"],
                estado_disparador=b.get("estado_sipar"),
                prioridad=prioridad,
                confianza_vinculo=d.get("confidence"),
                arista_id=d["arista_id"],
                sostenido_por=[x["regla"] for x in sostenes],
                aportes=coincidentes,
                explicacion=(
                    u"El reporte %s fue archivado%s %s.\n\n"
                    u"El reporte %s, %s, aporta precisamente aquello que faltaba: "
                    u"%s.\n\n"
                    u"La vinculación entre ambos se apoya en que %s, con una "
                    u"confianza de %s.\n\n"
                    u"Corresponde evaluar si procede reabrir la actuación. La "
                    u"decisión es del operador: el sistema no reabre nada por sí "
                    u"mismo."
                    % (a["valor"],
                       u" el %s" % _fecha(a.get("fecha_estado"))
                       if a.get("fecha_estado") else u"",
                       regla["texto"],
                       b["valor"],
                       u"actualmente %s" % estado_b if estado_b else u"vinculado",
                       _enumerar(detalle),
                       _enumerar([x.get("nota", u"comparten un dato objetivo")
                                  for x in sostenes], separador=u"; "),
                       ont.numero(d.get("confidence")))),
                locator=d.get("source_locator"),
            ))

    orden = {"alta": 0, "media": 1, "baja": 2}
    alertas.sort(key=lambda x: (orden.get(x["prioridad"], 9),
                                -(x["confianza_vinculo"] or 0)))
    return dict(alertas=alertas, silenciadas=silenciadas)


def resumen_por_motivo(alertas):
    agrupado = defaultdict(list)
    for a in alertas:
        agrupado[a["motivo_archivo"]].append(a["reporte_archivado"])
    return {k: sorted(set(v)) for k, v in agrupado.items()}
