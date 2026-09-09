# -*- coding: utf-8 -*-
u"""
Identificadores mencionados en texto libre.

Por que existe este modulo. El extractor lee campos estructurados, y hay
reportes donde el dato que los conecta con otro no esta en ningun campo sino
escrito en la conversacion o en la biografia del perfil: "agenda 11-6000-0147",
"buscame como Puente_Azul47", "el anticipo sale desde LUNA-RIO-47". Sin esto,
dos reportes de una misma red que no comparten ni cuenta ni IP ni dispositivo
-porque quien opera sabe no repetirlos- quedan sueltos, que es justo el caso
que hay que detectar.

Lo que sale de aca NO es observado: es DERIVADO por una regla a partir de un
texto observado, y va con confianza explicita y pendiente de validacion. Un
numero escrito en un chat puede ser de otra persona, puede estar mal tipeado o
puede ser una fanfarroneada. Por eso la relacion se llama MENCIONA_ y no
ASOCIADO_A: el texto lo menciona, no consta que le pertenezca a nadie.

El texto en si no entra al grafo (contexto.md 14.9). Entra el identificador
normalizado, con el locator del texto del que salio.

Que se admite y que no
----------------------
Telefonos, correos y arrobas se reconocen por su forma y son de bajo riesgo.
El caso dificil es el alias suelto -una palabra en el medio de una frase-, y
ahi la regla es: se admite si lleva un digito, o si una frase lo introduce
expresamente ("buscame como", "el anticipo sale desde"). Sin eso, cualquier
palabra escrita raro entraria al grafo como identificador. Es una regla
conservadora: prefiere perderse un alias antes que llenar el grafo de ruido
que despues nadie puede descartar de a uno.
"""

import re

import normalizacion as nz

MINERIA_VERSION = "1.0"

VENTANA_CUE = 48        # caracteres antes del hallazgo donde se busca la frase

# --------------------------------------------------------------------------
# Lo que se tapa antes de buscar
# --------------------------------------------------------------------------
# Las marcas de tiempo de las transcripciones son tiras de digitos y se leerian
# como numeros de telefono.
RE_TIEMPO = re.compile(r"\d{4}-\d{2}-\d{2}([ T]\d{1,2}:\d{2}(:\d{2})?)?(\s*(UTC|Z))?")
RE_HORA = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")
# Los perfiles que la plataforma agrega a la transcripcion ya los toma el
# extractor como cuentas; no se vuelven a leer como alias sueltos.
RE_PERFIL = re.compile(r"\(\s*Profile\s+[\w.\-]+\s*\)", re.I)

RE_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+\.[\w.-]*[\w](?![\w.-])")
RE_URL = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.I)
# Un telefono tiene que traer un + o algun separador: sin eso, cualquier numero
# de expediente de nueve digitos se leeria como un telefono.
RE_TELEFONO = re.compile(r"(?<![\w])(\+?\d[\d\s().\-]{5,18}\d)(?![\w])")
RE_ARROBA = re.compile(r"(?<![\w@.\-])@([A-Za-z][\w.\-]{2,29})(?![\w.\-])")
RE_TOKEN = re.compile(r"(?<![\w@.\-])([A-Za-z][A-Za-z0-9]*(?:[._\-][A-Za-z0-9]+)*)(?![\w@])")


def _cue(patrones):
    return re.compile(u"(?:%s)\\s*[:,]?\\s*$" % u"|".join(patrones), re.I)


# Frases que introducen un identificador. Las "fuertes" alcanzan para admitir
# un alias que no lleva ningun digito; el resto solo sube la confianza.
CUE_CONTACTO = _cue([
    u"busca(?:me|lo|la|nos)?(?: a| en| como| por)?", u"escrib[ií](?:me|le)?(?: a)?",
    u"agend[aá](?:me|lo|la)?", u"agrega(?:me|lo|la)?(?: como)?",
    u"a[nñ]ad[ií](?:me|lo|la)?(?: como)?", u"suma(?:te|me)(?: a)?",
    u"mi (?:usuario|alias|cuenta|perfil|contacto) es", u"el (?:usuario|alias) es",
    u"usuario", u"alias", u"perfil", u"contacto(?: alternativo)?",
    u"contactar?(?:me|lo|la)?(?: a| por)?", u"habla(?:me|le)?(?: a| por)?",
    u"whatsapp", u"telegram", u"instagram", u"tel[eé]fono", u"cel(?:ular)?",
])
CUE_PAGO = _cue([
    u"transferencias?", u"transfer[ií](?:me)?(?: a)?", u"el anticipo sale desde",
    u"sale desde", u"pag[aá](?:me)?(?: a| por)?", u"pagos?", u"cobros?",
    u"cobr[aá](?:me)?(?: a| por)?", u"se[nñ]a", u"anticipo", u"dep[oó]sito",
    u"deposit[aá](?:me)?(?: a| en)?", u"cvu", u"cbu", u"alias de pago",
    u"mercado ?pago", u"cr[eé]dito", u"canje", u"billetera",
])
# Solo estas admiten por si solas un alias sin digitos: son imperativas y no
# se confunden con prosa comun. "usuario" o "pago" a secas no entran aca.
CUE_FUERTE = _cue([
    u"busca(?:me|lo|la|nos)?(?: a| en| como| por)", u"escrib[ií](?:me|le)?(?: a)",
    u"agend[aá](?:me|lo|la)?", u"agrega(?:me|lo|la)?(?: como)?",
    u"a[nñ]ad[ií](?:me|lo|la)?(?: como)?",
    u"mi (?:usuario|alias|cuenta|perfil|contacto) es", u"el (?:usuario|alias) es",
    u"contacto alternativo", u"alias de pago", u"el anticipo sale desde",
    u"sale desde", u"transferencias?", u"transfer[ií](?:me)?(?: a)?",
])


# Palabras que nunca son un alias. Hacen falta porque una frase como "agregame
# como Zorro.Gris_88" tiene la frase introductoria pegada a "como", y sin esta
# lista "como" entraba al grafo como identificador. Solo se aplica a lo que no
# lleva ningun digito: una palabra con numeros no es una palabra corriente.
PALABRAS_QUE_NO_SON_ALIAS = frozenset(u"""
como que para por con sin desde hasta donde cuando cuanto ahi alli aca aqui
este esta esto estos estas ese esa eso esos esas aquel aquella
mio mia tuyo tuya suyo suya nuestro nuestra
pero porque entonces tambien tampoco siempre nunca ahora luego antes despues
todo toda todos todas nada nadie alguien algo otro otra otros otras
mismo misma mucho mucha poco poca mejor peor
hola chau gracias favor bueno buena claro dale listo obvio igual
usuario alias perfil cuenta cuentas contacto contactos telefono celular
numero numeros nombre apodo direccion mail correo whatsapp telegram instagram
user profile account phone name email chat
""".split())


def _tapar(texto, expresiones):
    """Reemplaza por espacios lo que no debe volver a mirarse.

    Se conservan las posiciones para que el contexto de cada hallazgo -la frase
    que lo introduce- se lea sobre el texto original.
    """
    s = texto
    for rex in expresiones:
        s = rex.sub(lambda m: " " * (m.end() - m.start()), s)
    return s


def _contexto(texto, inicio):
    previo = texto[max(0, inicio - VENTANA_CUE):inicio]
    return nz.sin_diacriticos(previo).lower()


def _clasificar_cue(texto, inicio):
    """(familia, fuerte). La familia decide si el alias es de pago o de contacto."""
    ctx = _contexto(texto, inicio)
    fuerte = bool(CUE_FUERTE.search(ctx))
    if CUE_PAGO.search(ctx):
        return "pago", fuerte
    if CUE_CONTACTO.search(ctx):
        return "contacto", fuerte
    return None, fuerte


def clave_alias(valor):
    """Clave con la que dos alias se comparan entre si.

    Se van mayusculas, acentos y separadores: `Puente_Azul47`, `puenteazul47` y
    `puente-azul-47` son el mismo alias escrito de tres maneras. La forma con la
    que aparecio se conserva aparte, porque es lo que el operador va a buscar
    en el expediente.
    """
    base, notas = nz.normalizar_alias(valor)
    if not base:
        return None, notas
    clave = re.sub(r"[\s._\-]+", "", base)
    if len(clave) < 4 or not re.search(r"[a-z]{2}", clave):
        return None, notas + [u"descartado: demasiado corto para individualizar"]
    if clave != base:
        notas.append(u"se compara sin mayúsculas, acentos ni separadores")
    return clave, notas


def _agregar(salida, vistos, hallazgo):
    if not hallazgo["clave"]:
        return
    firma = (hallazgo["tipo"], hallazgo["clave"])
    if firma in vistos:
        # Mismo identificador dos veces en el mismo texto: queda la lectura de
        # mayor confianza, que es la que trae la frase que lo introduce.
        previo = vistos[firma]
        if hallazgo["confianza"] > previo["confianza"]:
            previo.update(hallazgo)
        return
    vistos[firma] = hallazgo
    salida.append(hallazgo)


def identificadores(texto, pais_default="AR"):
    u"""Identificadores que menciona un texto libre.

    Devuelve una lista de hallazgos, cada uno con su tipo de nodo, la clave con
    la que se compara, la forma en que estaba escrito, la confianza y las notas
    de normalizacion que van a la explicacion de la arista.
    """
    if not texto or not str(texto).strip():
        return []
    texto = str(texto)
    salida, vistos = [], {}

    libre = _tapar(texto, [RE_TIEMPO, RE_HORA, RE_PERFIL, RE_URL])

    # -- correo ------------------------------------------------------------
    for m in RE_EMAIL.finditer(libre):
        email, notas = nz.normalizar_email(m.group(0))
        if not email:
            continue
        familia, _ = _clasificar_cue(texto, m.start())
        _agregar(salida, vistos, dict(
            tipo="EMAIL", clave=email, escrito=m.group(0), notas=notas,
            cue=familia, confianza=0.86,
            como=u"dirección de correo escrita en el texto"))
    libre = _tapar(libre, [RE_EMAIL])

    # -- telefono ----------------------------------------------------------
    for m in RE_TELEFONO.finditer(libre):
        crudo = m.group(1)
        if "+" not in crudo and not re.search(r"[\s().\-]", crudo):
            # Numero corrido y sin prefijo: puede ser cualquier cosa, un numero
            # de expediente o un identificador interno. No se toma.
            continue
        e164, notas = nz.normalizar_telefono(crudo, pais_default=pais_default)
        if not e164:
            continue
        familia, _ = _clasificar_cue(texto, m.start())
        _agregar(salida, vistos, dict(
            tipo="TELEFONO", clave=e164, escrito=crudo.strip(), notas=notas,
            cue=familia, confianza=0.88 if familia else 0.80,
            como=u"número telefónico escrito en el texto"))
    libre = _tapar(libre, [RE_TELEFONO])

    # -- arroba ------------------------------------------------------------
    for m in RE_ARROBA.finditer(libre):
        clave, notas = clave_alias(m.group(1))
        familia, _ = _clasificar_cue(texto, m.start())
        _agregar(salida, vistos, dict(
            tipo=("ALIAS_PAGO" if familia == "pago" else "ALIAS"),
            clave=clave, escrito="@" + m.group(1), notas=notas,
            cue=familia, confianza=0.80,
            como=u"nombre de usuario escrito con arroba"))
    libre = _tapar(libre, [RE_ARROBA])

    # -- alias suelto ------------------------------------------------------
    for m in RE_TOKEN.finditer(libre):
        crudo = m.group(1)
        familia, fuerte = _clasificar_cue(texto, m.start())
        tiene_digito = bool(re.search(r"\d", crudo))
        if not tiene_digito and not fuerte:
            continue
        clave, notas = clave_alias(crudo)
        if not clave:
            continue
        if not tiene_digito and clave in PALABRAS_QUE_NO_SON_ALIAS:
            continue
        if fuerte:
            conf = 0.74 if tiene_digito else 0.58
        else:
            conf = 0.55
        _agregar(salida, vistos, dict(
            tipo=("ALIAS_PAGO" if familia == "pago" else "ALIAS"),
            clave=clave, escrito=crudo, notas=notas,
            cue=familia, confianza=conf,
            como=(u"alias que el texto introduce expresamente" if fuerte
                  else u"alias escrito en el texto")))
    return salida
