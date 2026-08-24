# -*- coding: utf-8 -*-
"""
Clasificacion jurisdiccional determinista (Etapa 2 del proyecto).

Criterio del documento: cuando las reglas alcanzan, se resuelve por reglas y no
se usa un modelo de IA. Esta etapa corre ANTES del analisis sustantivo, para
que los casos de otras jurisdicciones se deriven sin consumir procesamiento
pesado ni ingresar a la boveda.

Salidas posibles para un reporte:
  CIJ_CABA               competencia propia, continua en el circuito
  DERIVAR                otra jurisdiccion argentina identificada
  DILIGENCIA_PREVIA      hace falta oficiar para determinar la jurisdiccion
  PENDIENTE_NAT          IP no atribuible sin puerto de origen
  FUERA_DE_ARGENTINA     el pais informado no es Argentina
  INDETERMINADA          no hay datos suficientes

Nada se deriva automaticamente: el sistema propone y una persona aprueba.
"""

import normalizacion as nz
import ontologia as ont

METODO = "clasificador_jurisdiccional"
VERSION = "1.1"

# ISO 3166-2:AR
PROVINCIAS = {
    "C": u"Ciudad Autónoma de Buenos Aires", "B": "Buenos Aires",
    "K": u"Catamarca", "H": "Chaco", "U": "Chubut", "X": u"Córdoba",
    "W": "Corrientes", "E": u"Entre Ríos", "P": "Formosa", "Y": u"Jujuy",
    "L": "La Pampa", "F": u"La Rioja", "M": "Mendoza", "N": "Misiones",
    "Q": u"Neuquén", "R": u"Río Negro", "A": "Salta", "J": u"San Juan",
    "D": u"San Luis", "Z": "Santa Cruz", "S": u"Santa Fe",
    "G": "Santiago del Estero", "V": "Tierra del Fuego", "T": u"Tucumán",
}

CIUDADES_CABA = {
    "buenos aires", "ciudad autonoma de buenos aires", "caba",
    "capital federal", "ciudad de buenos aires",
}

# Localidades del conurbano que suelen confundirse con CABA por cercania o por
# compartir el codigo de area 11. La lista es parcial y debe validarse.
LOCALIDADES_GBA = {
    "monte grande": u"Esteban Echeverría", "lomas de zamora": "Lomas de Zamora",
    "avellaneda": "Avellaneda", "quilmes": "Quilmes", "lanus": u"Lanús",
    "san isidro": "San Isidro", "vicente lopez": u"Vicente López",
    "moron": u"Morón", "la matanza": "La Matanza", "san martin": u"General San Martín",
    "tigre": "Tigre", "berazategui": "Berazategui", "ezeiza": "Ezeiza",
    "la plata": "La Plata", "moreno": "Moreno", "pilar": "Pilar",
}

# El codigo 11 cubre CABA y gran parte del conurbano: no alcanza para decidir.
AREAS_AMBIGUAS = {"11"}

# SIPAR cubre todas las provincias excepto Tucuman (segun el relevamiento).
SIN_COBERTURA_SIPAR = {u"Tucumán"}


def _texto(nodo):
    return (nodo.get("valor") or "").lower()


def _senales(g, n_rep):
    """Junta las senales de ubicacion disponibles para un reporte, con su
    locator, para que la decision sea auditable."""
    senales = dict(geolookup=[], esp=[], telefonos=[], ips=[], pais=None)
    senales["pais"] = g.G.nodes[n_rep].get("pais")
    sid = "ncmec:%s" % g.G.nodes[n_rep]["valor"]

    for u, v, k, d in g.aristas():
        if d.get("source_evidence_id") != sid:
            continue
        rel = d["relation_type"]
        if rel == "GEOLOCALIZA_EN":
            nub = g.G.nodes[v]
            senales["geolookup"].append(dict(
                ciudad=nub.get("ciudad"), region=nub.get("region"),
                pais=nub.get("pais"), locator=d["source_locator"],
                ip=g.G.nodes[u].get("valor")))
        elif rel == "UBICADO_EN" and g.G.nodes[v].get("tipo") == "UBICACION":
            nub = g.G.nodes[v]
            senales["esp"].append(dict(
                ciudad=nub.get("ciudad"), region=nub.get("region"),
                pais=nub.get("pais"), locator=d["source_locator"]))
        elif rel == "ASOCIADO_A_TELEFONO":
            senales["telefonos"].append(dict(
                valor=g.G.nodes[v].get("valor"), area=g.G.nodes[v].get("area"),
                locator=d["source_locator"]))
        elif rel == "OBSERVADO_DESDE_IP":
            nip = g.G.nodes[v]
            senales["ips"].append(dict(
                valor=nip.get("valor"), cgnat=bool(nip.get("cgnat")),
                privada=bool(nip.get("privada")), puerto=d.get("puerto"),
                observed_at=d.get("observed_at"), locator=d["source_locator"]))
    return senales


ORIGEN_SENAL = {
    "geolookup": u"la geolocalización automática de la dirección IP",
    "esp": u"la ubicación que declara la propia plataforma",
}


def clasificar(g, n_rep):
    s = _senales(g, n_rep)
    motivos = []

    pais = (s["pais"] or "").strip().lower()
    paises_geo = {(x.get("pais") or "").strip().upper()
                  for x in s["geolookup"] + s["esp"] if x.get("pais")}
    if paises_geo and not ({"AR", "ARGENTINA"} & paises_geo):
        return _resultado("FUERA_DE_ARGENTINA", None, 0.9,
                          [u"Todas las señales de ubicación disponibles apuntan "
                           u"fuera del país (%s), de modo que el hecho no parece "
                           u"corresponder a jurisdicción argentina."
                           % ", ".join(sorted(paises_geo))], s)
    if pais and pais not in ("argentina", "ar"):
        motivos.append(u"NCMEC informa como país de destino %s." % s["pais"])

    # 1) Region explicita (la senal mas fuerte y determinista)
    for clave, lista in (("geolookup", s["geolookup"]), ("esp", s["esp"])):
        origen = ORIGEN_SENAL[clave]
        for x in lista:
            region = (x.get("region") or "").strip().upper()
            ciudad = (x.get("ciudad") or "").strip().lower()
            if ciudad in CIUDADES_CABA and region in ("C", ""):
                return _resultado(
                    "CIJ_CABA", u"Ciudad Autónoma de Buenos Aires", 0.85,
                    motivos + [u"Según %s, la conexión se ubica en %s, que "
                               u"corresponde a la Ciudad Autónoma de Buenos Aires."
                               % (origen, x.get("ciudad"))],
                    s, locator=x.get("locator"))
            if region in PROVINCIAS:
                prov = PROVINCIAS[region]
                if region == "C":
                    return _resultado(
                        "CIJ_CABA", prov, 0.85,
                        motivos + [u"Según %s, la conexión se ubica en la región C, "
                                   u"que corresponde a la Ciudad Autónoma de Buenos "
                                   u"Aires." % origen],
                        s, locator=x.get("locator"))
                extra = []
                if ciudad in LOCALIDADES_GBA:
                    extra.append(u"La localidad de %s integra el partido de %s."
                                 % (x.get("ciudad"), LOCALIDADES_GBA[ciudad]))
                if prov in SIN_COBERTURA_SIPAR:
                    extra.append(u"Debe tenerse presente que, según el relevamiento, "
                                 u"SIPAR no cubre %s, por lo que la derivación "
                                 u"requiere una vía alternativa." % prov)
                return _resultado(
                    "DERIVAR", prov, 0.8,
                    motivos + [u"Según %s, la conexión se ubica en %s, región %s, "
                               u"que corresponde a la provincia de %s."
                               % (origen, x.get("ciudad") or u"una localidad no "
                                  u"informada", region, prov)] + extra,
                    s, locator=x.get("locator"))

    # 2) Sin region: la IP no atribuible bloquea antes que el telefono
    ips_no_atribuibles = [ip for ip in s["ips"]
                          if (ip["cgnat"] or ip["privada"]) and not ip["puerto"]]
    if ips_no_atribuibles and not s["geolookup"]:
        return _resultado(
            "PENDIENTE_NAT", None, 0.6,
            motivos + [u"Las direcciones IP disponibles (%s) se encuentran bajo "
                       u"NAT o CGNAT y el reporte no informa el puerto de origen. "
                       u"En esas condiciones el prestador no está en condiciones de "
                       u"identificar al abonado, de modo que corresponde requerir "
                       u"el puerto u otros datos técnicos antes de decidir la "
                       u"competencia."
                       % ", ".join(ip["valor"] for ip in ips_no_atribuibles)],
            s, locator=ips_no_atribuibles[0]["locator"])

    # 3) Prefijo telefonico
    for t in s["telefonos"]:
        area = t.get("area")
        if not area:
            continue
        if area in AREAS_AMBIGUAS:
            return _resultado(
                "DILIGENCIA_PREVIA", None, 0.4,
                motivos + [u"El teléfono %s tiene código de área %s, que abarca "
                           u"tanto la Ciudad Autónoma como buena parte del "
                           u"conurbano bonaerense, por lo que no alcanza para "
                           u"determinar la competencia." % (t["valor"], area)],
                s, locator=t.get("locator"))

    # 4) Hay IP publica pero sin geolookup: se puede oficiar
    ips_utiles = [ip for ip in s["ips"] if not ip["cgnat"] and not ip["privada"]
                  and ip.get("observed_at")]
    if ips_utiles:
        return _resultado(
            "DILIGENCIA_PREVIA", None, 0.5,
            motivos + [u"El reporte informa una dirección IP con fecha y hora (%s), "
                       u"pero no cuenta con geolocalización utilizable. Corresponde "
                       u"consultar LACNIC, ENACOM o CABASE para identificar al "
                       u"prestador y librar el oficio pertinente."
                       % ips_utiles[0]["valor"]],
            s, locator=ips_utiles[0]["locator"])

    return _resultado("INDETERMINADA", None, 0.2,
                      motivos + [u"El reporte no aporta ubicación, prefijo "
                                 u"telefónico ni dirección IP con fecha y hora que "
                                 u"permitan establecer la competencia."], s)


def _resultado(decision, jurisdiccion, confianza, motivos, senales, locator=None):
    return dict(decision=decision, jurisdiccion=jurisdiccion, confianza=confianza,
                motivos=motivos, locator=locator, senales=senales)


ACCION = {
    "CIJ_CABA": u"Retener la actuación en el CIJ CABA y continuar el circuito",
    "DERIVAR": u"Preparar la derivación territorial para su aprobación",
    "DILIGENCIA_PREVIA": u"Confeccionar el oficio al prestador y suspender la "
                         u"decisión hasta contar con la respuesta",
    "PENDIENTE_NAT": u"Requerir el puerto de origen u otros datos técnicos; la "
                     u"actuación queda latente",
    "FUERA_DE_ARGENTINA": u"Revisar la asignación de país en la herramienta de NCMEC",
    "INDETERMINADA": u"Elevar a revisión manual",
}

ETIQUETA_DECISION = {
    "CIJ_CABA": u"Competencia del CIJ CABA",
    "DERIVAR": u"Derivar a otra jurisdicción",
    "DILIGENCIA_PREVIA": u"Requiere diligencia previa",
    "PENDIENTE_NAT": u"Pendiente por NAT",
    "FUERA_DE_ARGENTINA": u"Fuera de la Argentina",
    "INDETERMINADA": u"Competencia indeterminada",
}


def clasificar_todos(g):
    """Aplica la clasificacion y materializa la propuesta en el grafo."""
    resultados = []
    for n_rep in sorted(g.nodos_tipo("REPORTE")):
        rid = g.G.nodes[n_rep]["valor"]
        res = clasificar(g, n_rep)
        res["reporte"] = rid
        res["accion"] = ACCION[res["decision"]]
        res["decision_legible"] = ETIQUETA_DECISION[res["decision"]]

        etiqueta = res["jurisdiccion"] or ETIQUETA_DECISION[res["decision"]]
        n_jur = g.nodo("JURISDICCION", etiqueta, etiqueta=etiqueta,
                       decision=res["decision"])
        sid = "derivacion:jurisdiccion:%s" % rid
        g.registrar_fuente(sid, tipo="clasificacion_jurisdiccional",
                           extra=dict(reporte=rid, decision=res["decision"]))
        explic = (u"Competencia propuesta para el reporte %s: %s.\n\n%s\n\n"
                  u"La determinación surge de reglas deterministas, sin "
                  u"intervención de modelos de inteligencia artificial, y puede "
                  u"reproducirse paso a paso. Se sugiere %s. El sistema no deriva "
                  u"ni retiene nada por sí mismo."
                  % (rid, ETIQUETA_DECISION[res["decision"]].lower(),
                     " ".join(res["motivos"]),
                     res["accion"][0].lower() + res["accion"][1:]))
        res["arista_id"] = g.arista(
            n_rep, n_jur, "PERTENECE_A_JURISDICCION", sid,
            res["locator"] or "reportedInformation (sin locator especifico)",
            explic, METODO, VERSION, confianza=res["confianza"],
            atributos=dict(decision=res["decision"], accion=res["accion"]))
        g.G.nodes[n_rep]["jurisdiccion_propuesta"] = res["decision"]
        resultados.append(res)
    return resultados


# ---------------------------------------------------------------------------
# Insumos para el oficio (Etapa 2: confeccion asistida)
# ---------------------------------------------------------------------------
def datos_para_oficio(g, n_rep):
    """Extrae los campos que el oficio necesita. No redacta el documento:
    entrega el payload para el template de SIPAR."""
    rid = g.G.nodes[n_rep]["valor"]
    s = _senales(g, n_rep)
    prestador = None
    conexiones = []
    for ip in s["ips"]:
        n_ip = ont.nid("IP", ip["valor"])
        for _, dst, _, d in g.G.edges(n_ip, keys=True, data=True):
            if d.get("relation_type") == "ASIGNADA_A":
                prestador = g.G.nodes[dst].get("valor")
        conexiones.append(dict(ip=ip["valor"], fecha_hora_utc=ip["observed_at"],
                               puerto=ip["puerto"], cgnat=ip["cgnat"],
                               locator=ip["locator"]))
    faltantes = []
    if not prestador:
        faltantes.append("prestador: debe confirmarse en LACNIC/ENACOM/CABASE")
    for c in conexiones:
        if not c["fecha_hora_utc"]:
            faltantes.append("fecha y hora de la conexion %s" % c["ip"])
        if c["cgnat"] and not c["puerto"]:
            faltantes.append("puerto de origen de la conexion %s (CGNAT)" % c["ip"])
    return dict(
        numero_reporte=rid,
        prestador_sugerido=prestador,
        conexiones=conexiones,
        zona_horaria="Las fechas se informan en UTC. Al oficiar debe aclararse la "
                     "zona horaria: un corrimiento de 3 h puede atribuir la "
                     "conexion a otro abonado.",
        campos_faltantes=faltantes,
        listo_para_enviar=not faltantes,
    )
