# -*- coding: utf-8 -*-
"""
Ontologia controlada del grafo - Boveda CIJ.

Fuente: CLAUDE.md secciones 10.1 a 10.4 y 11.1.
Este modulo no infiere culpabilidad ni fusiona identidades: solo define el
vocabulario, los origenes epistemologicos y los pesos de reglas deterministas.

VERSIONADO: cualquier cambio de pesos, umbrales o vocabulario debe subir
ONTOLOGIA_VERSION. Cada arista persistida guarda la version con la que fue
producida, para que el grafo sea reconstruible y comparable entre corridas.
"""

ONTOLOGIA_VERSION = "0.3.0"

# ---------------------------------------------------------------------------
# 1. SEPARACION EPISTEMOLOGICA (CLAUDE.md 10.1) - nunca se mezclan
# ---------------------------------------------------------------------------
OBSERVADA = "observada"   # surge directamente de un campo de la fuente
DERIVADA = "derivada"     # regla determinista reproducible sobre datos observados
INFERIDA = "inferida"     # similitud / modelo / LLM / GNN -> hipotesis

ORIGENES = (OBSERVADA, DERIVADA, INFERIDA)

ESTADOS_VALIDACION = (
    "pendiente",      # propuesta por el sistema, sin revision humana
    "en_revision",
    "validada",       # una persona la acepto
    "rechazada",      # una persona la descarto
)

# Una arista inferida NUNCA nace validada. Una observada no requiere validacion
# para existir (consta en la fuente), pero puede impugnarse despues.
ESTADO_INICIAL = {
    OBSERVADA: "validada",
    DERIVADA: "pendiente",
    INFERIDA: "pendiente",
}

# ---------------------------------------------------------------------------
# 2. TIPOS DE NODO (CLAUDE.md 10.2)
# ---------------------------------------------------------------------------
# Los colores son de identificacion, no de valoracion. Ningun tipo de
# entidad se pinta de rojo: el rojo queda reservado para la contra-evidencia
# (CLAUDE.md 13: el color no debe leerse como equivalente de culpabilidad).
# identificador : el valor es un dato objetivo apto para sostener un vinculo
#                 entre reportes (regla 3.5 del relevamiento).
# fusionable    : dos menciones del mismo valor son el mismo objeto (una IP es
#                 una IP). Las PERSONAS no son fusionables: se relacionan con
#                 POSIBLE_MISMA_IDENTIDAD, no se unifican automaticamente.
TIPOS_NODO = {
    "REPORTE": dict(color="#1f4e79", identificador=False, fusionable=True,
                    desc="Reporte NCMEC/CyberTipline ingresado a SIPAR"),
    "EVENTO": dict(color="#2e75b6", identificador=False, fusionable=True,
                   desc="Hecho reportado: chat, email, webpage, p2p, gaming"),
    "PERSONA_MENCION": dict(color="#5c6bc0", identificador=False, fusionable=False,
                            desc="Mencion de persona dentro de UN reporte. El rol "
                                 "procesal vive en la arista, no en el nodo"),
    "IDENTIDAD": dict(color="#3949ab", identificador=False, fusionable=False,
                      desc="Agrupamiento de menciones confirmado por una persona"),
    "CUENTA": dict(color="#e36c0a", identificador=True, fusionable=True,
                   desc="Cuenta de plataforma: ESP + espUserId"),
    "ALIAS": dict(color="#f4b183", identificador=True, fusionable=True,
                  desc="Nombre visible / screen name (identificador debil)"),
    "EMAIL": dict(color="#00b0f0", identificador=True, fusionable=True,
                  desc="Direccion de correo normalizada"),
    "TELEFONO": dict(color="#008080", identificador=True, fusionable=True,
                     desc="Numero telefonico en formato E.164"),
    "IP": dict(color="#548235", identificador=True, fusionable=True,
               desc="Direccion IP. Solo tiene valor junto a fecha, hora, "
                    "prestador y puerto cuando exista"),
    "DISPOSITIVO": dict(color="#7030a0", identificador=True, fusionable=True,
                        desc="Device ID / IDFA / GAID"),
    "EVIDENCIA": dict(color="#7f7f7f", identificador=True, fusionable=True,
                      desc="Archivo reportado, identificado por hash"),
    "SEGMENTO": dict(color="#bfbfbf", identificador=False, fusionable=True,
                     desc="Fragmento de una evidencia: frame, clip, pagina"),
    "UBICACION": dict(color="#bf8f00", identificador=False, fusionable=True,
                      desc="Ciudad / region estimada o declarada"),
    "JURISDICCION": dict(color="#833c00", identificador=False, fusionable=True,
                         desc="Jurisdiccion competente propuesta"),
    "ORGANIZACION": dict(color="#404040", identificador=False, fusionable=True,
                         desc="ESP, prestador de internet, organismo, fiscalia"),
    "DOCUMENTO": dict(color="#375623", identificador=False, fusionable=True,
                      desc="Oficio, respuesta de prestador, informe"),
}

# ---------------------------------------------------------------------------
# 3. VOCABULARIO DE RELACIONES (CLAUDE.md 10.3)
# ---------------------------------------------------------------------------
# Se evitan aristas genericas cuando existe una relacion especifica.
RELACIONES = {
    # -- observadas: se leen de un campo concreto de la fuente ---------------
    "REPORTADO_EN": dict(origen=OBSERVADA,
                         desc="Mencion de persona -> reporte. El rol procesal va en la arista"),
    "CONTIENE_EVENTO": dict(origen=OBSERVADA, desc="Reporte -> evento o incidente"),
    "EMITIDO_POR": dict(origen=OBSERVADA, desc="Reporte -> organizacion que lo genero"),
    "USA_CUENTA": dict(origen=OBSERVADA, desc="Mencion de persona -> cuenta"),
    "ALIAS_DE": dict(origen=OBSERVADA, desc="Cuenta -> alias o nombre visible"),
    "ASOCIADO_A_TELEFONO": dict(origen=OBSERVADA, desc="Cuenta o mencion -> telefono"),
    "ASOCIADO_A_EMAIL": dict(origen=OBSERVADA, desc="Cuenta o mencion -> email"),
    "OBSERVADO_DESDE_IP": dict(origen=OBSERVADA,
                               desc="Cuenta -> IP, con fecha, hora, evento y puerto"),
    "USA_DISPOSITIVO": dict(origen=OBSERVADA, desc="Cuenta -> dispositivo"),
    "PARTICIPA_EN": dict(origen=OBSERVADA, desc="Cuenta -> evento"),
    "ADJUNTA": dict(origen=OBSERVADA, desc="Reporte o evento -> evidencia"),
    "UBICADO_EN": dict(origen=OBSERVADA, desc="Entidad -> ubicacion declarada por la fuente"),
    "PUESTO_A_DISPOSICION_DE": dict(origen=OBSERVADA,
                                    desc="Reporte -> organismo al que NCMEC lo puso a disposicion"),

    # -- derivadas: regla determinista y reproducible ------------------------
    "GEOLOCALIZA_EN": dict(origen=DERIVADA, desc="IP -> ubicacion por geolookup (aproximada)"),
    "ASIGNADA_A": dict(origen=DERIVADA, desc="IP -> prestador de acceso"),
    "PERTENECE_A_JURISDICCION": dict(origen=DERIVADA,
                                     desc="Ubicacion o reporte -> jurisdiccion competente"),
    "COINCIDE_CON": dict(origen=DERIVADA,
                         desc="Reporte <-> reporte por identificador objetivo compartido"),
    "POSIBLE_DUPLICADO_DE": dict(origen=DERIVADA,
                                 desc="Reporte <-> reporte con indicios de duplicacion"),
    "CONTRADICE": dict(origen=DERIVADA,
                       desc="Vinculo que debilita otro, por ejemplo un viaje imposible"),
    "RESPONDE_A": dict(origen=DERIVADA, desc="Respuesta de prestador -> oficio"),
    "IDENTIFICADO_COMO": dict(origen=DERIVADA,
                              desc="Mencion -> identidad unificada por decision humana"),

    # -- inferidas: hipotesis, siempre pendientes de validacion --------------
    "POSIBLE_MISMA_IDENTIDAD": dict(origen=INFERIDA,
                                    desc="Dos menciones podrian ser la misma persona"),
    "SIMILAR_A": dict(origen=INFERIDA, desc="Similitud textual, semantica o multimodal"),
}

# ---------------------------------------------------------------------------
# 4. REGLAS DETERMINISTAS DE VINCULACION (CLAUDE.md 11.1)
# ---------------------------------------------------------------------------
# peso_base           : confianza maxima que aporta la coincidencia.
# corrobora_solamente : True -> nunca sostiene sola un vinculo; solo refuerza
#                       otro sostenido por un dato objetivo fuerte (regla 3.5).
# usa_discriminancia  : True -> el peso se pondera segun que tan raro sea el
#                       valor. Un alias comun o una IP compartida por miles de
#                       reportes no puede valer lo mismo que un dato unico.
REGLAS = {
    "R01_CUENTA": dict(
        version="1.0", tipo_nodo="CUENTA", peso_base=0.98,
        corrobora_solamente=False, usa_discriminancia=False,
        desc="Misma cuenta: mismo ESP y mismo espUserId"),
    "R02_DISPOSITIVO": dict(
        version="1.0", tipo_nodo="DISPOSITIVO", peso_base=0.92,
        corrobora_solamente=False, usa_discriminancia=True,
        desc="Mismo identificador de dispositivo"),
    "R03_TELEFONO": dict(
        version="1.0", tipo_nodo="TELEFONO", peso_base=0.90,
        corrobora_solamente=False, usa_discriminancia=True,
        desc="Mismo telefono normalizado a E.164"),
    "R04_EMAIL": dict(
        version="1.0", tipo_nodo="EMAIL", peso_base=0.90,
        corrobora_solamente=False, usa_discriminancia=True,
        desc="Mismo correo normalizado"),
    "R05_EVIDENCIA": dict(
        version="1.0", tipo_nodo="EVIDENCIA", peso_base=0.88,
        corrobora_solamente=False, usa_discriminancia=True,
        desc="Mismo hash de archivo"),
    "R06_IP_VENTANA": dict(
        version="1.0", tipo_nodo="IP", peso_base=0.72,
        corrobora_solamente=False, usa_discriminancia=True,
        desc="Misma IP dentro de la ventana temporal del prestador. La IP se "
             "valora siempre junto con su fecha y hora"),
    "R07_IP_SUELTA": dict(
        version="1.0", tipo_nodo="IP", peso_base=0.28,
        corrobora_solamente=True, usa_discriminancia=True,
        desc="Misma IP fuera de la ventana temporal: indicio, no atribucion"),
    "R08_ALIAS": dict(
        version="1.0", tipo_nodo="ALIAS", peso_base=0.22,
        corrobora_solamente=True, usa_discriminancia=True,
        desc="Mismo nombre visible: refuerza, nunca sostiene solo"),
    "R09_UBICACION": dict(
        version="1.0", tipo_nodo="UBICACION", peso_base=0.08,
        corrobora_solamente=True, usa_discriminancia=True,
        desc="Misma ciudad estimada: contexto, nunca sostiene solo"),
}

# ---------------------------------------------------------------------------
# 5. POLITICA DE IP (relevamiento 3.2, 4.2 y 4.5)
# ---------------------------------------------------------------------------
# La ventana temporal no es una constante universal: depende del prestador y
# del tipo de asignacion. Se declara por prestador con un default explicito, y
# el supuesto queda escrito en la explicacion de cada arista.
VENTANA_IP_HORAS = {
    "_default": 24,
    "telecentro": 24,
    "telecom argentina": 24,
    "telefonica de argentina": 24,
    "claro": 12,      # movil: reasignacion mas frecuente
    "personal": 12,
    "movistar": 12,
}

# Rango CGNAT (RFC 6598: 100.64.0.0/10). Con CGNAT el PUERTO DE ORIGEN es
# imprescindible: sin puerto y timestamp exacto el prestador no puede
# identificar al abonado (relevamiento 4.5, IP NAT).
CGNAT_RED = "100.64.0.0/10"

# Factor aplicado a R06 cuando la IP es NAT/CGNAT/proxy y no hay puerto.
FACTOR_NAT_SIN_PUERTO = 0.35
# Con puerto de origen y timestamp la atribucion vuelve a ser posible.
FACTOR_NAT_CON_PUERTO = 0.85

# ---------------------------------------------------------------------------
# 6. UMBRALES
# ---------------------------------------------------------------------------
UMBRAL_PROPONER = 0.55    # debajo de esto no se materializa la arista
UMBRAL_PROBABLE = 0.70
UMBRAL_ALTA = 0.90
CONFIANZA_MAXIMA = 0.99   # ninguna regla determinista produce certeza absoluta

# Discriminancia de un identificador segun en cuantos reportes aparece (df).
#
# Deliberadamente NO se mide como fraccion del corpus. Con 10 reportes de
# prueba, un dispositivo presente en 4 seria el 40 % y quedaria degradado, pero
# ese mismo dispositivo en un corpus de 100.000 reportes es altisimamente
# discriminante. La rareza de un identificador es una propiedad suya, no del
# tamano de la base.
DF_PLENA_DISCRIMINANCIA = 10    # hasta aca el identificador vale su peso completo
DF_HUB_ABSOLUTO = 50            # desde aca deja de sostener solo y pasa a corroborar
DF_HUB_SIN_PARES = 100          # desde aca ni siquiera se generan pares

# La fraccion solo se aplica cuando el corpus ya es grande: recien ahi dice algo.
FRACCION_BAJA_DISCRIMINANCIA = 0.20
CORPUS_MINIMO_PARA_FRACCION = 200

# Umbral para agrupar reportes en un mismo cluster o legajo logico.
UMBRAL_CLUSTER = 0.70


# ---------------------------------------------------------------------------
# 7. ETIQUETAS PARA PERSONAS, NO PARA MAQUINAS
# ---------------------------------------------------------------------------
# El vocabulario tecnico (REPORTADO_EN, R06_IP_VENTANA) es necesario para la
# persistencia y la auditoria, pero quien lee la pantalla es un operador o un
# fiscal. Estas etiquetas son las que se muestran.
ETIQUETA_TIPO = {
    "REPORTE": u"Reporte",
    "EVENTO": u"Hecho reportado",
    "PERSONA_MENCION": u"Persona mencionada",
    "IDENTIDAD": u"Identidad confirmada",
    "CUENTA": u"Cuenta de plataforma",
    "ALIAS": u"Nombre visible",
    "EMAIL": u"Correo electrónico",
    "TELEFONO": u"Teléfono",
    "IP": u"Dirección IP",
    "DISPOSITIVO": u"Dispositivo",
    "EVIDENCIA": u"Archivo",
    "SEGMENTO": u"Segmento de archivo",
    "UBICACION": u"Ubicación",
    "JURISDICCION": u"Jurisdicción",
    "ORGANIZACION": u"Organización",
    "DOCUMENTO": u"Documento",
}

ETIQUETA_RELACION = {
    "REPORTADO_EN": u"figura en el reporte",
    "CONTIENE_EVENTO": u"registra el hecho",
    "EMITIDO_POR": u"fue generado por",
    "USA_CUENTA": u"opera con la cuenta",
    "ALIAS_DE": u"se presenta con el nombre",
    "ASOCIADO_A_TELEFONO": u"está asociada al teléfono",
    "ASOCIADO_A_EMAIL": u"está asociada al correo",
    "OBSERVADO_DESDE_IP": u"fue observada desde la IP",
    "USA_DISPOSITIVO": u"se usó desde el dispositivo",
    "PARTICIPA_EN": u"interviene en",
    "ADJUNTA": u"adjunta el archivo",
    "UBICADO_EN": u"se ubica en",
    "PUESTO_A_DISPOSICION_DE": u"fue puesto a disposición de",
    "GEOLOCALIZA_EN": u"geolocaliza, de modo aproximado, en",
    "ASIGNADA_A": u"está asignada al prestador",
    "PERTENECE_A_JURISDICCION": u"competencia propuesta",
    "COINCIDE_CON": u"coincide con",
    "POSIBLE_DUPLICADO_DE": u"sería un duplicado de",
    "CONTRADICE": u"contradice",
    "RESPONDE_A": u"responde a",
    "POSIBLE_MISMA_IDENTIDAD": u"podría ser la misma persona que",
    "SIMILAR_A": u"guarda similitud con",
    "IDENTIFICADO_COMO": u"fue unificada bajo la identidad",
}

ETIQUETA_ORIGEN = {
    OBSERVADA: u"Consta en la fuente",
    DERIVADA: u"Derivada por regla",
    INFERIDA: u"Hipótesis a validar",
}

DESCRIPCION_ORIGEN = {
    OBSERVADA: u"El dato figura textualmente en un campo del reporte de origen. "
               u"No fue calculado ni supuesto por el sistema.",
    DERIVADA: u"Resulta de aplicar una regla determinista y reproducible sobre "
              u"datos que constan en la fuente. Puede volver a calcularse y "
              u"debe ser revisada por una persona.",
    INFERIDA: u"Es una hipótesis producida por similitud o por un modelo. No "
              u"acredita nada por sí sola y requiere validación humana.",
}

ETIQUETA_ESTADO = {
    "pendiente": u"Pendiente de revisión",
    "en_revision": u"En revisión",
    "validada": u"Validada",
    "rechazada": u"Rechazada",
}


def numero(valor, decimales=2):
    """Formato numérico en castellano: coma decimal y punto de miles."""
    if valor is None:
        return u"—"
    txt = "{:,.{d}f}".format(float(valor), d=decimales)
    return txt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def franja_confianza(c):
    if c >= UMBRAL_ALTA:
        return "alta"
    if c >= UMBRAL_PROBABLE:
        return "media"
    return "baja"


def nid(tipo, valor):
    """Identificador canonico y estable de nodo."""
    return "%s::%s" % (tipo, str(valor).strip().lower())


def validar_ontologia():
    """Chequeos de coherencia. Se ejecuta en cada construccion del grafo."""
    problemas = []
    for rel, meta in RELACIONES.items():
        if meta["origen"] not in ORIGENES:
            problemas.append("relacion %s: origen invalido" % rel)
    for regla, meta in REGLAS.items():
        if meta["tipo_nodo"] not in TIPOS_NODO:
            problemas.append("regla %s: tipo_nodo desconocido" % regla)
        if not 0 < meta["peso_base"] <= CONFIANZA_MAXIMA:
            problemas.append("regla %s: peso_base fuera de rango" % regla)
        if meta["corrobora_solamente"] and meta["peso_base"] >= UMBRAL_PROPONER:
            problemas.append("regla %s: corrobora sola pero supera el umbral" % regla)
    return problemas
