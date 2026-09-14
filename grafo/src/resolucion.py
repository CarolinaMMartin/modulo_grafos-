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
VERSION = "1.3"

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

# Un identificador que los dos reportes traen escrito en un texto libre pesa
# menos que el mismo identificador declarado en un campo. No porque la
# extraccion falle, sino por lo que significa: que el prestador informe un
# telefono es un dato de la cuenta, que alguien lo escriba en una conversacion
# es una afirmacion de esa persona, que puede estar equivocada, ser de un
# tercero o ser mentira. El descuento es unico y explicito para que se pueda
# discutir; como todos los pesos, esta sin calibrar.
FACTOR_TEXTO_LIBRE = 0.85


def _solo_de_texto(aristas):
    """True si todo lo que sostiene este identificador salio de un texto libre."""
    return bool(aristas) and all(
        str(a.get("relation_type", "")).startswith("MENCIONA_") for a in aristas)


def _procedencia_lado(aristas):
    """Procedencia semantica del dato en uno de los reportes.

    Si el mismo valor aparece tanto en un campo como en texto, el campo basta
    para sostener ese lado. Solo se lo considera dependiente de texto cuando
    todas las aristas disponibles son menciones extraidas de texto libre.
    """
    if not aristas:
        return "sin_evidencia"
    if _solo_de_texto(aristas):
        return "texto_libre"
    if any(str(a.get("relation_type", "")).startswith("MENCIONA_")
           for a in aristas):
        return "campo_y_texto"
    return "campo_estructurado"


# ---------------------------------------------------------------------------
# Indice invertido: identificador -> reportes (blocking)
# ---------------------------------------------------------------------------
def indexar(g):
    """valor_de_nodo -> {reporte_canonico: [aristas de sus fuentes]}"""
    indice = defaultdict(lambda: defaultdict(list))
    for u, v, k, d in g.aristas():
        if d["origin"] not in (ont.OBSERVADA, ont.DERIVADA):
            continue
        sid = g.reporte_de_fuente(d.get("source_evidence_id"))
        if not sid:
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
        if not d.get("vigente", True) or d.get("validation_status") == "rechazada":
            continue
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
    procedencia_a = _procedencia_lado(aristas_a)
    procedencia_b = _procedencia_lado(aristas_b)
    lados_desde_texto = sum(
        p == "texto_libre" for p in (procedencia_a, procedencia_b))
    desde_texto = lados_desde_texto > 0

    def agregar(regla_id, peso, frase, corrobora=None):
        meta = ont.REGLAS[regla_id]
        fd = factor_disc if meta["usa_discriminancia"] else 1.0
        # Cada lado que depende exclusivamente de texto introduce su propia
        # salvedad. Campo↔texto se descuenta una vez; texto↔texto, dos veces.
        ft = FACTOR_TEXTO_LIBRE ** lados_desde_texto
        disparos.append(dict(
            regla=regla_id, regla_version=meta["version"],
            nodo=n_nodo, tipo=tipo, valor=datos.get("valor"),
            peso_base=meta["peso_base"], peso_efectivo=round(peso * fd * ft, 4),
            factor_contexto=round(peso / meta["peso_base"], 8),
            factor_discriminancia=round(fd, 4),
            factor_texto_libre=round(ft, 4),
            desde_texto=desde_texto,
            lados_desde_texto=lados_desde_texto,
            procedencia_lado_a=procedencia_a,
            procedencia_lado_b=procedencia_b,
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
        if lados_desde_texto == 0:
            forma = u"en ambos se consigna"
        elif lados_desde_texto == 1:
            forma = (u"un reporte consigna en un campo y el otro menciona en "
                     u"texto libre")
        else:
            forma = u"ambos mencionan en texto libre"
        agregar("R03_TELEFONO", ont.REGLAS["R03_TELEFONO"]["peso_base"],
                u"%s el mismo número telefónico, que una vez "
                u"normalizado resulta %s"
                % (forma, datos.get("valor")))

    elif tipo == "EMAIL":
        if lados_desde_texto == 0:
            forma = u"en ambos se consigna"
        elif lados_desde_texto == 1:
            forma = (u"un reporte consigna en un campo y el otro menciona en "
                     u"texto libre")
        else:
            forma = u"ambos mencionan en texto libre"
        agregar("R04_EMAIL", ont.REGLAS["R04_EMAIL"]["peso_base"],
                u"%s la misma dirección de correo (%s)"
                % (forma, datos.get("valor")))

    elif tipo == "EVIDENCIA":
        agregar("R05_EVIDENCIA", ont.REGLAS["R05_EVIDENCIA"]["peso_base"],
                u"ambos incluyen un archivo de idéntico hash, es decir, "
                u"exactamente el mismo contenido y no uno parecido")

    elif tipo == "HASH_PERCEPTUAL":
        agregar("R11_PHASH_SIMILAR",
                ont.REGLAS["R11_PHASH_SIMILAR"]["peso_base"],
                u"ambas imágenes tienen la misma huella perceptual (%s); esto "
                u"indica similitud visual, no igualdad criptográfica"
                % datos.get("valor"))

    elif tipo == "HUELLA_AUDIO":
        agregar("R12_HUELLA_AUDIO",
                ont.REGLAS["R12_HUELLA_AUDIO"]["peso_base"],
                u"los dos archivos de audio comparten la misma huella "
                u"algorítmica (%s)" % datos.get("valor"))

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
                u"en ambos figura el mismo %s, «%s»"
                % (u"alias mencionado" if desde_texto else u"nombre visible",
                   datos.get("valor")))

    elif tipo == "ALIAS_PAGO":
        agregar("R10_ALIAS_PAGO", ont.REGLAS["R10_ALIAS_PAGO"]["peso_base"],
                u"los dos apuntan a la misma vía de cobro, el alias de pago "
                u"«%s»" % datos.get("valor"))

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
def vincular_reportes(g, disparos_adicionales=None):
    """Crea aristas COINCIDE_CON / POSIBLE_DUPLICADO_DE entre reportes.

    ``disparos_adicionales`` permite sumar señales por par que no se expresan
    como igualdad de un nodo: por ejemplo dos pHash cercanos o dos
    descripciones de lugar semejantes. Deben traer la misma estructura
    auditable que una regla normal y nunca eluden la corroboración obligatoria.
    """
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
        tipo = g.G.nodes[n_nodo].get("tipo")
        pares_posibles = len(sids) * (len(sids) - 1) // 2
        limite_pares = ont.MAX_PARES_POR_TIPO.get(
            tipo, ont.MAX_PARES_POR_TIPO["_default"])
        if pares_posibles > limite_pares:
            if tipo == "IP":
                politica = "segmentar_temporalmente"
                accion = ("grupo compacto conservado; requiere segmentacion por "
                          "fecha, hora, puerto y prestador antes de abrir pares")
            elif tipo in ("ALIAS", "UBICACION"):
                politica = "contexto_masivo"
                accion = ("grupo compacto conservado; no abre pares por si solo "
                          "porque es una señal contextual de baja discriminancia")
            else:
                politica = "grupo_compacto"
                accion = ("grupo compacto conservado; no se enumeran todos los "
                          "pares para evitar expansion combinatoria")
            hubs.append(dict(
                nodo=n_nodo, tipo=tipo,
                valor=g.G.nodes[n_nodo].get("valor"), reportes=len(sids),
                ids_reportes=[sid.split(":", 1)[1] for sid in sids],
                pares_posibles=pares_posibles, limite_pares=limite_pares,
                politica=politica, oculto=False, accion=accion))
            continue
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                pares[(sids[i], sids[j])][n_nodo] = (por_reporte[sids[i]],
                                                     por_reporte[sids[j]])

    extras_por_par = defaultdict(list)
    for original in (disparos_adicionales or []):
        disp = dict(original)
        rid_a = str(disp.pop("reporte_a", ""))
        rid_b = str(disp.pop("reporte_b", ""))
        sid_a, sid_b = sorted(("ncmec:%s" % rid_a, "ncmec:%s" % rid_b))
        if not rid_a or not rid_b or sid_a == sid_b:
            continue
        par = (sid_a, sid_b)
        extras_por_par[par].append(disp)
        pares.setdefault(par, {})

    creadas, descartadas = [], []
    for (sid_a, sid_b), compartidos in sorted(pares.items()):
        if sid_a not in reportes or sid_b not in reportes:
            continue
        disparos = list(extras_por_par.get((sid_a, sid_b), []))
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
                        else u"El puntaje resultante no alcanza el umbral mínimo "
                             u"para proponer la vinculación."),
                disparos=disparos))
            continue

        locators = {d["source_locator"] for grupo in compartidos.values()
                    for lista in grupo for d in lista}
        for disp in disparos:
            locators.update(x for x in (disp.get("source_locators") or []) if x)
        locators = sorted(locators)
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
                formula_puntaje="noisy_or_pesos_efectivos",
                puntaje_calibrado=False,
                indicios_duplicado=dup or None,
            ))
        creadas.append(dict(arista_id=aid, relacion=relacion, confianza=confianza,
                            reporte_a=g.G.nodes[n_a]["valor"],
                            reporte_b=g.G.nodes[n_b]["valor"],
                            reglas=[d["regla"] for d in disparos],
                            formula_puntaje="noisy_or_pesos_efectivos",
                            puntaje_calibrado=False))

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


RAZON_PESO = {
    "R01_CUENTA": u"Coinciden la plataforma y el ID de usuario: es la misma cuenta registrada.",
    "R02_DISPOSITIVO": u"La coincidencia exacta del ID de dispositivo vincula los reportes por ese identificador.",
    "R03_TELEFONO": u"El número coincide después de unificar su formato.",
    "R04_EMAIL": u"La dirección de correo coincide después de unificar su formato.",
    "R05_EVIDENCIA": u"El hash coincide: los reportes referencian el mismo contenido de archivo.",
    "R06_IP_VENTANA": u"La IP coincide dentro del intervalo de tiempo configurado para el prestador.",
    "R07_IP_SUELTA": u"La IP coincide, pero falta proximidad temporal comprobable; solo refuerza otra coincidencia.",
    "R08_ALIAS": u"Un nombre visible puede repetirse entre cuentas: solo refuerza otra coincidencia.",
    "R09_UBICACION": u"Una zona puede ser compartida por muchas personas: solo refuerza otra coincidencia.",
    "R10_ALIAS_PAGO": u"El alias de pago coincide y conecta los reportes por esa vía de cobro.",
    "R11_PHASH_SIMILAR": u"Las huellas perceptuales indican semejanza visual; se comparan los metadatos declarados.",
    "R12_HUELLA_AUDIO": u"Coinciden las huellas de audio declaradas en los metadatos.",
    "R13_CONTEXTO_LUGAR": u"Coinciden rasgos de la descripción; solo refuerzan otras coincidencias.",
}


def calculo_legible(disparos, confianza):
    """Explica los pesos efectivamente usados, sin cambiar la ponderacion.

    Los numeros son parametros de trabajo, no porcentajes de acierto. El
    desglose se muestra a pedido; el hallazgo ocupa el primer plano del visor.
    """
    pasos = []
    for d in disparos:
        base = d["peso_base"]
        ajustes = []
        factores = [base]
        for clave, texto in (
            ("factor_contexto", u"Ajuste por las condiciones de la conexión (NAT/proxy)"),
            ("factor_discriminancia", u"Reducción porque el dato aparece en muchos reportes"),
            ("factor_texto_libre", u"Reducción porque el dato se menciona en texto libre"),
            ("factor_similitud", u"Ajuste por el grado de similitud"),
        ):
            factor = d.get(clave, 1.0)
            if factor != 1.0:
                factores.append(factor)
                ajustes.append(u"%s: multiplicar por %s."
                               % (texto, ont.numero(factor, 4)))
        if not ajustes:
            ajustes.append(u"Se usa el peso completo, sin reducciones.")
        pasos.append(dict(
            regla=d["regla"],
            nombre=ont.ETIQUETA_TIPO.get(d.get("tipo"), d.get("tipo")),
            valor=d.get("valor"),
            peso_base=base, peso_final=d["peso_efectivo"],
            motivo=RAZON_PESO.get(d["regla"], ont.REGLAS[d["regla"]]["desc"]),
            ajustes=ajustes,
            cuenta=u" × ".join(ont.numero(x, 4) for x in factores)
                   + u" = " + ont.numero(d["peso_efectivo"], 4),
        ))
    if len(disparos) == 1:
        combinacion = (u"Hay una sola coincidencia: el puntaje final es su peso, %s."
                       % ont.numero(confianza, 2 if round(confianza, 2) == confianza else 4))
    else:
        combinacion = (u"Se combinan los aportes, no se suman directamente. "
                       u"Cada coincidencia adicional aumenta el puntaje usando "
                       u"la parte que falta para llegar a 1.")
    formula = u"1 − (" + u" × ".join(
        u"(1 − %s)" % ont.numero(min(d["peso_efectivo"], ont.CONFIANZA_MAXIMA), 4)
        for d in disparos) + u")"
    return dict(pasos=pasos, combinacion=combinacion, formula=formula,
                puntaje=confianza, limite=ont.CONFIANZA_MAXIMA,
                criterio=u"Los pesos están configurados según el tipo de coincidencia. "
                u"Sirven para ordenar las vinculaciones; no son porcentajes de acierto.")


def _explicar(g, n_a, n_b, disparos, confianza, dup):
    ra, rb = g.G.nodes[n_a]["valor"], g.G.nodes[n_b]["valor"]
    sostienen = sorted([d for d in disparos if not d["corrobora_solamente"]],
                       key=lambda x: -x["peso_efectivo"])
    corroboran = sorted([d for d in disparos if d["corrobora_solamente"]],
                        key=lambda x: -x["peso_efectivo"])

    # La salvedad distingue campo↔texto de texto↔texto. En ambos casos consta
    # la coincidencia del valor, pero no la atribucion de ese valor a la cuenta
    # o persona mencionada. Repetirla dentro de cada regla volveria ilegible la
    # explicacion, por eso se resume una sola vez y con los valores afectados.
    un_lado_texto = [d for d in disparos if d.get("lados_desde_texto") == 1]
    dos_lados_texto = [d for d in disparos if d.get("lados_desde_texto") == 2]
    salvedades = []
    if un_lado_texto:
        salvedades.append(
            u"En %s, uno de los reportes declara el dato en un campo y el otro "
            u"solamente lo menciona en la conversación o en la biografía. La "
            u"coincidencia del valor es verificable, pero esa mención no prueba "
            u"que el dato pertenezca a la persona reportada; por eso se aplica "
            u"un descuento explícito y debe revisarse en su contexto."
            % _enumerar([u"«%s»" % d["valor"] for d in un_lado_texto]))
    if dos_lados_texto:
        salvedades.append(
            u"En %s, ninguno de los dos reportes declara el dato en un campo: "
            u"ambos solamente lo mencionan en texto libre. Que dos textos "
            u"contengan el mismo valor permite proponer una pista, pero no "
            u"atribuírselo a las personas reportadas; por eso el descuento se "
            u"aplica en cada lado y la coincidencia requiere revisión."
            % _enumerar([u"«%s»" % d["valor"] for d in dos_lados_texto]))
    salvedad = u"\n\n".join(salvedades)

    parrafos = []
    if sostienen:
        parrafos.append(
            u"Los reportes %s y %s están vinculados porque %s."
            % (ra, rb, _enumerar([d["nota"] for d in sostienen], separador=u"; ")))

    if corroboran:
        parrafos.append(
            u"También coinciden estos datos, que solo refuerzan la vinculación: %s."
            % _enumerar([d["nota"] for d in corroboran],
                        separador=u"; ", conector=u"; y, por último, "))

    if salvedad:
        parrafos.append(salvedad)

    if dup:
        parrafos.append(
            u"Además, hay indicios de que se trate del mismo hecho reportado dos "
            u"veces: coinciden la cuenta y la plataforma, y los hechos están "
            u"separados por apenas %s horas. Corresponde verificar si se trata de "
            u"una duplicación antes de tramitarlos como actuaciones independientes."
            % ont.numero(dup["horas_entre_hechos"]))

    calculo = calculo_legible(disparos, confianza)
    parrafos.append(u"Puntaje: %s. %s" % (ont.numero(confianza), calculo["combinacion"]))
    for paso in calculo["pasos"]:
        parrafos.append(u"%s: peso configurado %s. %s %s Aporte final: %s."
                        % (paso["nombre"], ont.numero(paso["peso_base"]),
                           paso["motivo"], u" ".join(paso["ajustes"]),
                           ont.numero(paso["peso_final"], 4)))
    return u"\n\n".join(parrafos)


# ---------------------------------------------------------------------------
# Identidades: hipotesis, nunca fusion
# ---------------------------------------------------------------------------
def proponer_identidades(g):
    """POSIBLE_MISMA_IDENTIDAD entre menciones de persona de reportes distintos.

    No se fusionan nodos. Se propone la hipotesis con su explicacion para que
    una persona la confirme o la rechace (contexto.md 11.2).
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
