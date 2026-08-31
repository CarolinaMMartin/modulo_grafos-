# -*- coding: utf-8 -*-
"""
Vinculacion determinista entre reportes y resolucion de identidades.

Este modulo produce SOLO aristas derivadas (reglas reproducibles) e inferidas
(hipotesis de identidad). Nunca fusiona nodos de persona.

Tres decisiones que se apartan de un enfoque ingenuo:

1. BLOCKING por identificador en lugar de comparacion de todos contra todos.
   La procedencia ya dice a que reporte pertenece cada arista observada, asi
   que el indice valor -> reportes se arma sin recorrer el grafo. Solo se
   comparan pares que comparten al menos un identificador. Es lo que permite
   que esto escale mas alla de un puñado de reportes.

2. DISCRIMINANCIA. Un identificador compartido por muchos reportes vale menos
   que uno raro. Sin esta ponderacion, una IP de CGNAT o un alias comun
   generan un cluster gigante de falsos positivos.

3. CORROBORACION OBLIGATORIA. Un vinculo necesita al menos una regla que lo
   sostenga por si sola. Alias, ciudad e IP sin ventana temporal solo refuerzan
   (relevamiento 3.5: una relacion debe apoyarse en datos objetivos
   coincidentes, no en semejanza contextual).
"""

import math
from collections import defaultdict
from datetime import datetime

import normalizacion as nz
import ontologia as ont

METODO = "resolucion_determinista"
VERSION = "1.2"

# Un identificador vinculado a mas reportes que esto se trata como hub: no
# genera pares. Se informa siempre, nunca se descarta en silencio.
MAX_REPORTES_POR_IDENTIFICADOR = ont.DF_HUB_SIN_PARES

# Velocidad implausible entre dos observaciones geolocalizadas (km/h).
VELOCIDAD_IMPOSIBLE_KMH = 900.0
# Por debajo de esta distancia no se evalua desplazamiento: la geolocalizacion
# por IP no tiene esa precision y solo produciria ruido.
DISTANCIA_MINIMA_KM = 50.0
# La contradiccion es un indicio de inconsistencia, no una refutacion: puede ser
# una VPN, una cuenta compartida o una geolocalizacion errada.
CONFIANZA_CONTRADICCION = 0.7
# Dos menciones de persona que comparten cuenta PODRIAN ser la misma. Nunca se
# fusionan solas: es una hipotesis a la espera de una decision humana.
CONFIANZA_MISMA_IDENTIDAD = 0.85

TIPOS_INDEXABLES = sorted({r["tipo_nodo"] for r in ont.REGLAS.values()})


# ---------------------------------------------------------------------------
# Indice invertido: identificador -> reportes (blocking)
# ---------------------------------------------------------------------------
def indexar(g):
    """valor_de_nodo -> {source_evidence_id: [aristas observadas]}"""
    indice = defaultdict(lambda: defaultdict(list))
    for u, v, k, d in g.aristas():
        if d["origin"] not in (ont.OBSERVADA, ont.DERIVADA):
            continue
        sid = d.get("source_evidence_id")
        if not sid or not sid.startswith("ncmec:"):
            continue
        for n in (u, v):
            tipo = g.G.nodes[n].get("tipo")
            if tipo in TIPOS_INDEXABLES:
                indice[n][sid].append(d)
    return indice


def discriminancia(df, total_reportes=None):
    """Cuanto aporta un identificador segun en cuantos reportes aparece.

    df = document frequency: cantidad de reportes distintos que lo contienen.
    Hasta DF_PLENA_DISCRIMINANCIA el identificador conserva todo su peso; por
    encima decae de forma logaritmica. No depende del tamano del corpus: ver la
    nota en ontologia.py sobre por que la fraccion enganaba con pocos reportes.

    total_reportes se acepta por compatibilidad y no se usa en el calculo.
    """
    if df <= ont.DF_PLENA_DISCRIMINANCIA:
        return 1.0
    factor = (math.log(1.0 + ont.DF_PLENA_DISCRIMINANCIA) / math.log(1.0 + df))
    return max(0.15, min(1.0, factor))


def es_baja_discriminancia(df, total_reportes):
    """Un identificador tan repetido que deja de poder sostener un vinculo solo."""
    if df >= ont.DF_HUB_ABSOLUTO:
        return True, (u"aparece en %d reportes distintos, por encima del umbral de "
                      u"%d a partir del cual un identificador deja de individualizar"
                      % (df, ont.DF_HUB_ABSOLUTO))
    if (total_reportes >= ont.CORPUS_MINIMO_PARA_FRACCION
            and float(df) / total_reportes > ont.FRACCION_BAJA_DISCRIMINANCIA):
        return True, (u"aparece en %d de %d reportes, esto es, en el %s %% del "
                      u"universo analizado"
                      % (df, total_reportes,
                         ont.numero(100.0 * df / total_reportes, 0)))
    return False, None


# ---------------------------------------------------------------------------
# Evaluacion de una coincidencia concreta
# ---------------------------------------------------------------------------
def _ventana_para_ip(g, n_ip):
    """Ventana temporal segun el prestador asignado a la IP."""
    for _, dst, _, d in g.G.edges(n_ip, keys=True, data=True):
        if d.get("relation_type") == "ASIGNADA_A":
            isp = (g.G.nodes[dst].get("valor") or "").lower()
            for clave, horas in ont.VENTANA_IP_HORAS.items():
                if clave != "_default" and clave in isp:
                    return horas, g.G.nodes[dst].get("valor")
    return ont.VENTANA_IP_HORAS["_default"], None


def _ts_de(aristas):
    out = []
    for d in aristas:
        if d.get("observed_at"):
            ts, _ = nz.normalizar_ts(d["observed_at"])
            if ts:
                out.append((ts, d))
    return out


def evaluar_coincidencia(g, n_nodo, aristas_a, aristas_b, factor_disc):
    """Devuelve la lista de reglas que disparan para un identificador comun.

    Cada disparo trae una frase redactada, pensada para incrustarse en la
    explicacion que lee el operador. El identificador tecnico de la regla queda
    para la auditoria, no para la pantalla.
    """
    tipo = g.G.nodes[n_nodo].get("tipo")
    datos = g.G.nodes[n_nodo]
    disparos = []

    def agregar(regla_id, peso, frase, corrobora=None):
        meta = ont.REGLAS[regla_id]
        fd = factor_disc if meta["usa_discriminancia"] else 1.0
        disparos.append(dict(
            regla=regla_id, regla_version=meta["version"],
            nodo=n_nodo, tipo=tipo, valor=datos.get("valor"),
            peso_base=meta["peso_base"], peso_efectivo=round(peso * fd, 4),
            factor_discriminancia=round(fd, 4),
            corrobora_solamente=(meta["corrobora_solamente"] if corrobora is None
                                 else corrobora),
            nota=frase))

    if tipo == "CUENTA":
        agregar("R01_CUENTA", ont.REGLAS["R01_CUENTA"]["peso_base"],
                u"ambos reportes involucran la misma cuenta de plataforma (%s)"
                % datos.get("valor"))

    elif tipo == "DISPOSITIVO":
        agregar("R02_DISPOSITIVO", ont.REGLAS["R02_DISPOSITIVO"]["peso_base"],
                u"en los dos aparece el mismo identificador de dispositivo (%s)"
                % datos.get("valor"))

    elif tipo == "TELEFONO":
        agregar("R03_TELEFONO", ont.REGLAS["R03_TELEFONO"]["peso_base"],
                u"ambos consignan el mismo número telefónico, que una vez "
                u"normalizado resulta %s" % datos.get("valor"))

    elif tipo == "EMAIL":
        agregar("R04_EMAIL", ont.REGLAS["R04_EMAIL"]["peso_base"],
                u"ambos consignan la misma dirección de correo (%s)"
                % datos.get("valor"))

    elif tipo == "EVIDENCIA":
        agregar("R05_EVIDENCIA", ont.REGLAS["R05_EVIDENCIA"]["peso_base"],
                u"ambos incluyen un archivo de idéntico hash, es decir, "
                u"exactamente el mismo contenido y no uno parecido")

    elif tipo == "IP":
        horas, isp = _ventana_para_ip(g, n_nodo)
        ts_a, ts_b = _ts_de(aristas_a), _ts_de(aristas_b)
        mejor = None
        for ta, da in ts_a:
            for tb, db in ts_b:
                delta = nz.horas_entre(ta, tb)
                if mejor is None or delta < mejor[0]:
                    mejor = (delta, da, db)
        if mejor is None:
            agregar("R07_IP_SUELTA", ont.REGLAS["R07_IP_SUELTA"]["peso_base"],
                    u"ambos registran la misma dirección IP, pero al menos una de "
                    u"las capturas no informa fecha ni hora, de modo que no "
                    u"permite atribuir la conexión a nadie en particular")
        else:
            delta, da, db = mejor
            if delta <= horas:
                peso = ont.REGLAS["R06_IP_VENTANA"]["peso_base"]
                frase = (u"ambos registran la dirección IP %s con %s horas de "
                         u"diferencia, dentro de la ventana de %d horas que se "
                         u"asume para %s"
                         % (datos.get("valor"), ont.numero(delta, 1), horas,
                            isp or u"el prestador"))
                corrobora = None
                if datos.get("cgnat") or datos.get("privada") \
                        or da.get("posible_proxy") or db.get("posible_proxy"):
                    if da.get("puerto") and db.get("puerto"):
                        peso *= ont.FACTOR_NAT_CON_PUERTO
                        frase += (u"; la dirección está bajo CGNAT, pero ambas "
                                  u"capturas informan el puerto de origen, de modo "
                                  u"que el prestador está en condiciones de "
                                  u"identificar al abonado")
                    else:
                        peso *= ont.FACTOR_NAT_SIN_PUERTO
                        corrobora = True
                        frase += (u"; la dirección está bajo CGNAT y ninguna captura "
                                  u"informa el puerto de origen, por lo que no "
                                  u"permite atribuir la conexión a un abonado "
                                  u"determinado y queda como mero indicio")
                agregar("R06_IP_VENTANA", peso, frase, corrobora=corrobora)
            else:
                agregar("R07_IP_SUELTA", ont.REGLAS["R07_IP_SUELTA"]["peso_base"],
                        u"ambos registran la dirección IP %s, aunque separadas por "
                        u"%s horas, muy por fuera de la ventana de %d horas que se "
                        u"asume para %s, de modo que probablemente correspondan a "
                        u"abonados distintos"
                        % (datos.get("valor"), ont.numero(delta, 0), horas,
                           isp or u"el prestador"))

    elif tipo == "ALIAS":
        agregar("R08_ALIAS", ont.REGLAS["R08_ALIAS"]["peso_base"],
                u"en ambos figura el mismo nombre visible, «%s»" % datos.get("valor"))

    elif tipo == "UBICACION":
        agregar("R09_UBICACION", ont.REGLAS["R09_UBICACION"]["peso_base"],
                u"ambos ubican los hechos en la misma zona estimada (%s)"
                % datos.get("valor"))

    return disparos


def combinar(disparos):
    """Noisy-OR sobre las reglas que dispararon.

    Solo se acumula si al menos una regla sostiene el vinculo por si sola.
    Las reglas corroborantes suman, pero nunca crean el vinculo.
    """
    sostienen = [d for d in disparos if not d["corrobora_solamente"]]
    if not sostienen:
        return 0.0, False
    prod = 1.0
    for d in disparos:
        prod *= (1.0 - min(d["peso_efectivo"], ont.CONFIANZA_MAXIMA))
    return round(min(1.0 - prod, ont.CONFIANZA_MAXIMA), 4), True


# ---------------------------------------------------------------------------
# Proceso principal
# ---------------------------------------------------------------------------
def vincular_reportes(g):
    """Crea aristas COINCIDE_CON / POSIBLE_DUPLICADO_DE entre reportes."""
    indice = indexar(g)
    reportes = {("ncmec:%s" % g.G.nodes[n]["valor"]): n for n in g.nodos_tipo("REPORTE")}
    total = max(len(reportes), 1)

    hubs = []
    pares = defaultdict(dict)   # (sid_a, sid_b) -> {nodo: (aristas_a, aristas_b)}
    df_por_nodo = {}

    for n_nodo, por_reporte in indice.items():
        sids = sorted(por_reporte)
        df_por_nodo[n_nodo] = len(sids)
        if len(sids) < 2:
            continue
        if len(sids) > MAX_REPORTES_POR_IDENTIFICADOR:
            hubs.append(dict(nodo=n_nodo, tipo=g.G.nodes[n_nodo].get("tipo"),
                             valor=g.G.nodes[n_nodo].get("valor"), reportes=len(sids),
                             accion="no se generaron pares: identificador de tipo hub, "
                                    "requiere revision manual o segmentacion temporal"))
            continue
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                pares[(sids[i], sids[j])][n_nodo] = (por_reporte[sids[i]],
                                                     por_reporte[sids[j]])

    creadas, descartadas = [], []
    for (sid_a, sid_b), compartidos in sorted(pares.items()):
        if sid_a not in reportes or sid_b not in reportes:
            continue
        disparos = []
        for n_nodo, (ar_a, ar_b) in compartidos.items():
            df = df_por_nodo[n_nodo]
            fd = discriminancia(df)
            baja, razon = es_baja_discriminancia(df, total)
            for disp in evaluar_coincidencia(g, n_nodo, ar_a, ar_b, fd):
                # Un identificador de baja discriminancia deja de sostener solo.
                # La cuenta se exceptua: si el espUserId se repite tanto, el
                # problema es de los datos, no de la regla, y conviene verlo.
                if baja and disp["regla"] != "R01_CUENTA":
                    disp["corrobora_solamente"] = True
                    disp["nota"] += (u", si bien ese dato %s, de modo que por sí "
                                     u"solo ya no individualiza" % razon)
                disparos.append(disp)

        confianza, sostenido = combinar(disparos)
        n_a, n_b = reportes[sid_a], reportes[sid_b]

        if not sostenido or confianza < ont.UMBRAL_PROPONER:
            descartadas.append(dict(
                reporte_a=g.G.nodes[n_a]["valor"], reporte_b=g.G.nodes[n_b]["valor"],
                confianza=confianza, sostenido=sostenido,
                motivo=(u"Los reportes comparten elementos, pero ninguno de ellos "
                        u"individualiza lo suficiente como para sostener la "
                        u"vinculación por sí solo." if not sostenido
                        else u"La confianza resultante no alcanza el umbral mínimo "
                             u"para proponer la vinculación."),
                disparos=disparos))
            continue

        locators = sorted({d["source_locator"] for grupo in compartidos.values()
                           for lista in grupo for d in lista})
        sid_deriv = "derivacion:%s+%s" % (sid_a, sid_b)
        g.registrar_fuente(sid_deriv, tipo="vinculacion_derivada",
                           extra=dict(fuentes=[sid_a, sid_b], locators=locators))

        relacion = "COINCIDE_CON"
        dup = _indicios_de_duplicado(g, n_a, n_b, disparos)
        if dup:
            relacion = "POSIBLE_DUPLICADO_DE"

        explic = _explicar(g, n_a, n_b, disparos, confianza, dup)
        aid = g.arista(
            n_a, n_b, relacion, sid_deriv, " | ".join(locators[:12]),
            explic, METODO, VERSION, confianza=confianza,
            atributos=dict(
                simetrica=True,
                reglas=[d["regla"] for d in disparos],
                detalle_reglas=disparos,
                franja=ont.franja_confianza(confianza),
                indicios_duplicado=dup or None,
            ))
        creadas.append(dict(arista_id=aid, relacion=relacion, confianza=confianza,
                            reporte_a=g.G.nodes[n_a]["valor"],
                            reporte_b=g.G.nodes[n_b]["valor"],
                            reglas=[d["regla"] for d in disparos]))

    return dict(vinculos=creadas, descartados=descartadas, hubs=hubs,
                pares_evaluados=len(pares), reportes=len(reportes))


def _indicios_de_duplicado(g, n_a, n_b, disparos):
    """Duplicado != recurrencia. Se exige misma cuenta, misma plataforma y
    hechos con fechas practicamente iguales."""
    if not any(d["regla"] == "R01_CUENTA" for d in disparos):
        return None
    a, b = g.G.nodes[n_a], g.G.nodes[n_b]
    if (a.get("plataforma") or "?") != (b.get("plataforma") or "??"):
        return None
    ta, _ = nz.normalizar_ts(a.get("fecha_incidente"))
    tb, _ = nz.normalizar_ts(b.get("fecha_incidente"))
    if not ta or not tb:
        return None
    horas = nz.horas_entre(ta, tb)
    if horas is None or horas > 1.0:
        return None
    return dict(misma_cuenta=True, misma_plataforma=a.get("plataforma"),
                horas_entre_hechos=round(horas, 3))


def _enumerar(frases, separador=u", ", conector=u" y "):
    """Une frases en una enumeracion legible: a, b y c.

    Cuando las frases ya contienen comas, conviene separarlas con punto y coma:
    de lo contrario la enumeracion se vuelve ilegible.
    """
    frases = [f for f in frases if f]
    if not frases:
        return u""
    if len(frases) == 1:
        return frases[0]
    return u"%s%s%s" % (separador.join(frases[:-1]), conector, frases[-1])


def _explicar(g, n_a, n_b, disparos, confianza, dup):
    ra, rb = g.G.nodes[n_a]["valor"], g.G.nodes[n_b]["valor"]
    franja = ont.franja_confianza(confianza)
    sostienen = sorted([d for d in disparos if not d["corrobora_solamente"]],
                       key=lambda x: -x["peso_efectivo"])
    corroboran = sorted([d for d in disparos if d["corrobora_solamente"]],
                        key=lambda x: -x["peso_efectivo"])

    parrafos = []
    parrafos.append(
        u"Los reportes %s y %s quedan vinculados con una confianza de %s, que el "
        u"sistema califica como %s." % (ra, rb, ont.numero(confianza), franja))

    if sostienen:
        cierre = (u"Se trata de datos objetivos que individualizan y que, por esa "
                  u"razón, alcanzan para proponer la relación."
                  if len(sostienen) > 1 else
                  u"Se trata de un dato objetivo que individualiza y que, por esa "
                  u"razón, alcanza para proponer la relación.")
        parrafos.append(
            u"La vinculación se sostiene en que %s. %s"
            % (_enumerar([d["nota"] for d in sostienen], separador=u"; "), cierre))

    if corroboran:
        parrafos.append(
            u"A ello se suman los siguientes elementos, que refuerzan la hipótesis "
            u"pero no alcanzarían por sí solos para sostenerla: %s. Conforme al "
            u"criterio de trabajo vigente, una relación no puede apoyarse "
            u"únicamente en semejanzas de contexto."
            % _enumerar([d["nota"] for d in corroboran],
                        separador=u"; ", conector=u"; y, por último, "))

    if dup:
        parrafos.append(
            u"Además, hay indicios de que se trate del mismo hecho reportado dos "
            u"veces: coinciden la cuenta y la plataforma, y los hechos están "
            u"separados por apenas %s horas. Corresponde verificar si se trata de "
            u"una duplicación antes de tramitarlos como actuaciones independientes."
            % ont.numero(dup["horas_entre_hechos"]))

    parrafos.append(
        u"Lo anterior es una propuesta del sistema. No acredita autoría ni "
        u"responsabilidad alguna, y requiere la validación de un operador antes de "
        u"incorporarse a una actuación.")
    return u"\n\n".join(parrafos)


# ---------------------------------------------------------------------------
# Identidades: hipotesis, nunca fusion
# ---------------------------------------------------------------------------
def proponer_identidades(g):
    """POSIBLE_MISMA_IDENTIDAD entre menciones de persona de reportes distintos.

    No se fusionan nodos. Se propone la hipotesis con su explicacion para que
    una persona la confirme o la rechace (CLAUDE.md 11.2).
    """
    propuestas = []
    por_cuenta = defaultdict(set)
    for u, v, k, d in g.aristas(relacion="USA_CUENTA"):
        por_cuenta[v].add(u)

    for n_cta, menciones in por_cuenta.items():
        menciones = sorted(menciones)
        if len(menciones) < 2:
            continue
        for i in range(len(menciones)):
            for j in range(i + 1, len(menciones)):
                a, b = menciones[i], menciones[j]
                sid = "derivacion:identidad:%s" % n_cta
                g.registrar_fuente(sid, tipo="hipotesis_identidad",
                                   extra=dict(cuenta=g.G.nodes[n_cta]["valor"]))
                aid = g.arista(
                    a, b, "POSIBLE_MISMA_IDENTIDAD", sid,
                    "USA_CUENTA -> %s" % n_cta,
                    (u"Las dos personas mencionadas operan con la misma cuenta, %s. "
                     u"Es la señal más fuerte de que podría tratarse de la misma "
                     u"persona, pero no lo prueba: una cuenta puede estar "
                     u"compartida, haber sido vendida o encontrarse comprometida.\n\n"
                     u"Por eso el sistema no unifica las menciones. Deja planteada "
                     u"la hipótesis para que un operador la confirme o la descarte."
                     % g.G.nodes[n_cta]["valor"]),
                    METODO, VERSION, confianza=CONFIANZA_MISMA_IDENTIDAD,
                    atributos=dict(senal="cuenta_compartida", fusion_automatica=False))
                propuestas.append(dict(arista_id=aid, a=a, b=b,
                                       cuenta=g.G.nodes[n_cta]["valor"]))
    return propuestas


# ---------------------------------------------------------------------------
# Contra-evidencia
# ---------------------------------------------------------------------------
def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def detectar_contradicciones(g):
    """Viaje imposible: una misma cuenta o dispositivo observada desde IPs que
    geolocalizan demasiado lejos en muy poco tiempo.

    No invalida nada por si sola. Puede indicar cuenta compartida, VPN o un
    geolookup erroneo, y por eso importa: debilita la atribucion a una persona.
    """
    hallazgos = []
    coords = {}
    for u, v, k, d in g.aristas(relacion="GEOLOCALIZA_EN"):
        lat, lon = g.G.nodes[v].get("lat"), g.G.nodes[v].get("lon")
        if lat and lon:
            try:
                coords[u] = (float(lat), float(lon), g.G.nodes[v].get("valor"))
            except (TypeError, ValueError):
                pass

    observaciones = defaultdict(list)
    for u, v, k, d in g.aristas(relacion="OBSERVADO_DESDE_IP"):
        if v not in coords or not d.get("observed_at"):
            continue
        ts, _ = nz.normalizar_ts(d["observed_at"])
        if ts:
            observaciones[u].append((ts, v, d))

    for n_ancla, obs in observaciones.items():
        obs.sort(key=lambda x: x[0])
        for i in range(len(obs) - 1):
            (t1, ip1, d1), (t2, ip2, d2) = obs[i], obs[i + 1]
            if ip1 == ip2:
                continue
            lat1, lon1, u1 = coords[ip1]
            lat2, lon2, u2 = coords[ip2]
            km = _haversine(lat1, lon1, lat2, lon2)
            horas = nz.horas_entre(t1, t2) or 0.0
            if horas <= 0 or km < DISTANCIA_MINIMA_KM:
                continue
            kmh = km / horas
            if kmh <= VELOCIDAD_IMPOSIBLE_KMH:
                continue
            sid = "derivacion:contradiccion:%s" % n_ancla
            g.registrar_fuente(sid, tipo="contradiccion_espaciotemporal")
            aid = g.arista(
                ip1, ip2, "CONTRADICE", sid,
                "%s | %s" % (d1["source_locator"], d2["source_locator"]),
                (u"%s aparece observado desde %s y, %s horas después, desde %s. "
                 u"Entre ambos puntos median unos %s kilómetros, lo que supondría "
                 u"un desplazamiento de %s km/h.\n\n"
                 u"El traslado es materialmente implausible. Puede tratarse del uso "
                 u"de una VPN, de una cuenta compartida entre varias personas o de "
                 u"un error en la geolocalización automática. Cualquiera sea el "
                 u"caso, debilita la atribución de ambas conexiones a una misma "
                 u"persona y conviene tenerlo presente antes de sostener esa "
                 u"hipótesis."
                 % (g.G.nodes[n_ancla].get("etiqueta"), u1, ont.numero(horas, 1),
                    u2, ont.numero(km, 0), ont.numero(kmh, 0))),
                METODO, VERSION, confianza=CONFIANZA_CONTRADICCION,
                atributos=dict(km=round(km, 1), horas=round(horas, 2),
                               kmh=round(kmh, 1), ancla=n_ancla))
            hallazgos.append(dict(arista_id=aid, ancla=n_ancla, km=round(km, 1),
                                  horas=round(horas, 2), kmh=round(kmh, 1)))
    return hallazgos
