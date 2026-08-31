# -*- coding: utf-8 -*-
"""
Normalizacion de identificadores (contexto.md 11.1, primer nivel determinista).

Toda normalizacion devuelve (valor_normalizado, notas). Las notas explican que
transformacion se aplico y quedan en la explicacion de la arista, para que un
operador pueda auditar por que dos menciones distintas quedaron unificadas.
"""

import ipaddress
import re
import unicodedata
from datetime import datetime, timedelta, timezone

NORMALIZACION_VERSION = "1.0"

# --------------------------------------------------------------------------
# Texto y alias
# --------------------------------------------------------------------------
def sin_diacriticos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def normalizar_alias(valor):
    if not valor:
        return None, []
    notas = []
    v = str(valor).strip()
    original = v
    v = sin_diacriticos(v).lower()
    v = re.sub(r"\s+", " ", v)
    v = re.sub(r"[^\w\s@._-]", "", v)
    if v != original.lower():
        notas.append("alias normalizado desde %r" % original)
    return (v or None), notas


# --------------------------------------------------------------------------
# Correo
# --------------------------------------------------------------------------
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalizar_email(valor):
    if not valor:
        return None, []
    notas = []
    v = str(valor).strip().lower()
    if not RE_EMAIL.match(v):
        return None, ["descartado: no tiene forma de correo (%r)" % valor]
    local, dominio = v.split("@", 1)
    # Solo se normaliza el punto en dominios que lo ignoran explicitamente.
    if dominio in ("gmail.com", "googlemail.com"):
        local_sin = local.split("+", 1)[0].replace(".", "")
        if local_sin != local:
            notas.append("gmail: se ignoran puntos y sufijo +etiqueta")
            local = local_sin
        dominio = "gmail.com"
    return "%s@%s" % (local, dominio), notas


# --------------------------------------------------------------------------
# Telefono (E.164, foco Argentina)
# --------------------------------------------------------------------------
def normalizar_telefono(valor, pais_default="AR"):
    if not valor:
        return None, []
    notas = []
    crudo = str(valor).strip()
    tiene_mas = crudo.startswith("+")
    d = re.sub(r"\D", "", crudo)
    if not d:
        return None, ["descartado: sin digitos"]

    if tiene_mas or d.startswith("54"):
        if d.startswith("54"):
            nacional = d[2:]
        else:
            return "+" + d, ["numero internacional no argentino, se deja como esta"]
    elif pais_default == "AR":
        nacional = d
        notas.append("se asumio pais AR por defecto")
    else:
        return "+" + d, notas

    # Argentina: 0 de larga distancia y 15 de celular no forman parte del E.164.
    if nacional.startswith("0"):
        nacional = nacional[1:]
        notas.append("se quito el 0 de larga distancia")
    if nacional.startswith("9"):
        nacional = nacional[1:]
        notas.append("se quito el 9 de movil para normalizar")
    m = re.match(r"^(11|2\d{2}|3\d{2})15(\d+)$", nacional)
    if m:
        nacional = m.group(1) + m.group(2)
        notas.append("se quito el 15 de movil")

    if not 8 <= len(nacional) <= 11:
        return None, notas + ["descartado: longitud nacional inverosimil (%s)" % nacional]
    return "+54" + nacional, notas


def prefijo_ar(e164):
    """Devuelve el codigo de area argentino, util para jurisdiccion."""
    if not e164 or not e164.startswith("+54"):
        return None
    n = e164[3:]
    for largo in (4, 3, 2):
        if len(n) > largo:
            return n[:largo]
    return None


# --------------------------------------------------------------------------
# IP
# --------------------------------------------------------------------------
CGNAT = ipaddress.ip_network("100.64.0.0/10")


def normalizar_ip(valor):
    if not valor:
        return None, [], {}
    try:
        ip = ipaddress.ip_address(str(valor).strip())
    except ValueError:
        return None, ["descartado: no es una IP valida (%r)" % valor], {}
    rasgos = dict(
        version=ip.version,
        privada=bool(ip.is_private),
        cgnat=bool(ip.version == 4 and ip in CGNAT),
    )
    # Una IP privada o CGNAT no identifica a un abonado por si sola.
    rasgos["atribuible_sin_dato_extra"] = not (rasgos["privada"] or rasgos["cgnat"])
    return str(ip), [], rasgos


# --------------------------------------------------------------------------
# Tiempo
# --------------------------------------------------------------------------
def normalizar_ts(valor):
    """Devuelve datetime timezone-aware en UTC.

    Las capturas de NCMEC vienen en UTC. Las respuestas de prestadores
    argentinos suelen venir en hora local (UTC-3): si un valor llega sin zona
    horaria se lo marca como supuesto, porque tres horas de corrimiento
    alcanzan para atribuir una conexion al abonado equivocado.
    """
    if not valor:
        return None, []
    v = str(valor).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                dt = datetime.strptime(v, fmt)
                break
            except ValueError:
                continue
        else:
            return None, ["descartado: fecha no interpretable (%r)" % valor]
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc), [
            "SUPUESTO: la fecha llego sin zona horaria y se la trato como UTC"]
    return dt.astimezone(timezone.utc), []


def dentro_de_ventana(ts_a, ts_b, horas):
    if not ts_a or not ts_b:
        return False, None
    delta = abs(ts_a - ts_b)
    return delta <= timedelta(hours=horas), delta


def horas_entre(ts_a, ts_b):
    if not ts_a or not ts_b:
        return None
    return abs((ts_a - ts_b).total_seconds()) / 3600.0


# --------------------------------------------------------------------------
# Cuenta de plataforma
# --------------------------------------------------------------------------
def clave_cuenta(esp, esp_user_id):
    """Una cuenta es unica dentro de su plataforma, no globalmente."""
    if not esp or not esp_user_id:
        return None
    esp_n, _ = normalizar_alias(esp)
    return "%s/%s" % (esp_n, str(esp_user_id).strip())
