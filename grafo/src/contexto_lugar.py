# -*- coding: utf-8 -*-
"""Baseline local y explicable para descripciones de lugares.

No intenta resolver domicilios ni afirmar que dos frases nombran el mismo
sitio. Extrae categorias de un vocabulario controlado, compara perfiles por
reporte y produce una hipotesis que SOLO corrobora otras señales.

El texto sensible no entra al grafo. Quedan su hash, locator, categorias,
version del vocabulario y formula del puntaje. Esto permite revisar el pasaje
exacto en el almacen restringido sin copiarlo a todas las salidas.
"""

import hashlib
import re
from collections import defaultdict
from itertools import combinations

import normalizacion as nz
import ontologia as ont

METODO = "contexto_lugar_controlado"
VERSION = "1.0"
LEXICO_VERSION = "1.0"
UMBRAL_SIMILITUD = 0.45
CONFIANZA_EXTRACCION = 0.72

# Las equivalencias son visibles y discutibles. No se aprende nada en secreto.
LEXICO = {
    "estructura:deposito": {
        "dimension": "estructura",
        "formas": ("galpon", "deposito", "almacen", "bodega", "tinglado"),
    },
    "estructura:vivienda": {
        "dimension": "estructura",
        "formas": ("casa", "vivienda", "departamento", "depto"),
    },
    "rasgo:mural": {
        "dimension": "rasgo",
        "formas": ("mural", "pared pintada", "grafiti", "graffiti"),
    },
    "color:azul": {
        "dimension": "color",
        "formas": ("azul", "celeste"),
    },
    "color:rojo": {
        "dimension": "color",
        "formas": ("rojo", "bordo", "colorado"),
    },
    "referencia:estacion": {
        "dimension": "referencia",
        "formas": ("estacion", "terminal de tren", "terminal ferroviaria"),
    },
    "referencia:plaza": {
        "dimension": "referencia",
        "formas": ("plaza", "parque", "plazoleta"),
    },
    "acceso:lateral": {
        "dimension": "acceso",
        "formas": ("entrada lateral", "puerta lateral", "acceso lateral"),
    },
    "acceso:trasero": {
        "dimension": "acceso",
        "formas": ("entrada trasera", "puerta trasera", "por atras"),
    },
}

PESO_DIMENSION = {
    "estructura": 0.30,
    "rasgo": 0.25,
    "referencia": 0.25,
    "color": 0.12,
    "acceso": 0.08,
}
DIMENSIONES_ANCLA = {"estructura", "rasgo", "referencia"}

RE_LINEA_CHAT = re.compile(
    r"^\s*\[[^\]]+\]\s*(Reported\s+User|Other\s+User)\s*"
    r"\([^)]*\)\s*:\s*(.*)$", re.I)


def _normal(texto):
    texto = nz.sin_diacriticos(str(texto or "")).lower()
    return re.sub(r"\s+", " ", texto).strip()


def _contiene(texto, forma):
    patron = r"(?<!\w)%s(?!\w)" % re.escape(forma).replace(r"\ ", r"\s+")
    return bool(re.search(patron, texto))


def categorizar(texto):
    """Categorias canonicas presentes, sin devolver ni almacenar la frase."""
    normal = _normal(texto)
    salida = []
    for etiqueta, meta in sorted(LEXICO.items()):
        formas = [_normal(x) for x in meta["formas"]]
        if any(_contiene(normal, forma) for forma in formas):
            salida.append(dict(etiqueta=etiqueta,
                                dimension=meta["dimension"]))
    return salida


def _fragmentos_habilitados(meta):
    """Devuelve solo fragmentos atribuibles a la cuenta reportada.

    Las notas de chat contienen a ambos participantes en un unico bloque. No
    alcanza con comprobar que el bloque diga ``Reported User``: eso haria que
    tambien se atribuyera al reportado una descripcion escrita por la
    contraparte. Las lineas que el exportador no permite asignar con claridad
    se omiten de manera conservadora.
    """
    texto = str(meta.get("texto") or "")
    locator = str(meta.get("locator") or "")
    if meta.get("tipo") != "transcripcion_chat":
        return [(texto, locator)] if texto else []

    salida = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        m = RE_LINEA_CHAT.match(linea)
        if not m or m.group(1).lower().replace(" ", "") != "reporteduser":
            continue
        salida.append((m.group(2), "%s#linea=%d" % (locator, numero)))
    return salida


def _peso_dimensiones(dimensiones):
    return sum(PESO_DIMENSION.get(d, 0.0) for d in dimensiones)


def analizar(g, textos):
    """Extrae perfiles por reporte y propone similitudes auditables."""
    acumulado = defaultdict(lambda: dict(tags=defaultdict(set), hashes=set()))
    for h, meta in sorted((textos or {}).items()):
        sid = g.reporte_de_fuente(meta.get("source_evidence_id"))
        if not sid:
            continue
        rid = sid.split(":", 1)[1]
        encontro = False
        for fragmento, locator in _fragmentos_habilitados(meta):
            categorias = categorizar(fragmento)
            if not categorias:
                continue
            encontro = True
            for categoria in categorias:
                acumulado[rid]["tags"][categoria["etiqueta"]].add(locator)
        if encontro:
            acumulado[rid]["hashes"].add(h)

    perfiles = {}
    for rid, datos in sorted(acumulado.items()):
        tags = sorted(datos["tags"])
        dimensiones = sorted({LEXICO[t]["dimension"] for t in tags})
        if len(dimensiones) < 2 or not (set(dimensiones) & DIMENSIONES_ANCLA):
            continue
        locators = sorted({loc for valores in datos["tags"].values()
                           for loc in valores if loc})
        firma = hashlib.sha256(
            (rid + "|" + "|".join(tags) + "|" + "|".join(locators))
            .encode("utf-8")).hexdigest()
        n_rep = ont.nid("REPORTE", rid)
        if n_rep not in g.G:
            continue
        n_lugar = g.nodo(
            "LUGAR_MENCION", "%s/%s" % (rid, firma[:16]),
            etiqueta=u"Descripción de lugar (reporte %s)" % rid,
            categorias=tags, dimensiones=dimensiones,
            hashes_texto=sorted(datos["hashes"]), texto_restringido=True,
            lexico_version=LEXICO_VERSION)
        g.arista(
            n_rep, n_lugar, "MENCIONA_LUGAR", "ncmec:%s" % rid,
            " | ".join(locators),
            (u"El texto restringido del reporte contiene categorías compatibles "
             u"con una descripción de lugar: %s. El texto no se copia al grafo "
             u"y la extracción no resuelve un domicilio."
             % u", ".join(tags)),
            METODO, VERSION, confianza=CONFIANZA_EXTRACCION,
            atributos=dict(lexico_version=LEXICO_VERSION,
                           categorias=tags, texto_restringido=True))
        perfiles[rid] = dict(
            reporte=rid, nodo=n_lugar, tags=set(tags),
            dimensiones=set(dimensiones), locators=locators,
            hashes=sorted(datos["hashes"]))

    # Blocking por categoria compartida: no se forman todos los pares globales.
    por_tag = defaultdict(list)
    for rid, perfil in perfiles.items():
        for tag in perfil["tags"]:
            por_tag[tag].append(rid)
    pares = set()
    for reportes in por_tag.values():
        for a, b in combinations(sorted(set(reportes)), 2):
            pares.add((a, b))

    similitudes, disparos = [], []
    for rid_a, rid_b in sorted(pares):
        a, b = perfiles[rid_a], perfiles[rid_b]
        comunes = sorted(a["tags"] & b["tags"])
        dims_comunes = {LEXICO[t]["dimension"] for t in comunes}
        dims_union = a["dimensiones"] | b["dimensiones"]
        if len(dims_comunes) < 2 or not (dims_comunes & DIMENSIONES_ANCLA):
            continue
        score = (_peso_dimensiones(dims_comunes) /
                 max(_peso_dimensiones(dims_union), 0.0001))
        if score < UMBRAL_SIMILITUD:
            continue

        sid = "derivacion:lugar:%s:%s" % (rid_a, rid_b)
        locators = a["locators"] + b["locators"]
        g.registrar_fuente(
            sid, tipo="similitud_contextual_lugar",
            extra=dict(fuentes=["ncmec:%s" % rid_a, "ncmec:%s" % rid_b],
                       locators=locators, categorias_comunes=comunes,
                       lexico_version=LEXICO_VERSION,
                       formula="peso_dimensiones_comunes/peso_dimensiones_union"))
        aid = g.arista(
            a["nodo"], b["nodo"], "SIMILAR_A", sid,
            " | ".join(locators),
            (u"Las descripciones restringidas comparten %d dimensiones del "
             u"vocabulario controlado (%s), con puntaje %s. Es una hipótesis "
             u"contextual: no afirma que sea el mismo lugar y nunca sostiene "
             u"por sí sola una vinculación entre reportes."
             % (len(dims_comunes), u", ".join(sorted(dims_comunes)),
                ont.numero(score, 4))),
            METODO, VERSION, confianza=score,
            atributos=dict(
                categorias_comunes=comunes,
                dimensiones_comunes=sorted(dims_comunes),
                formula="peso_dimensiones_comunes/peso_dimensiones_union",
                puntaje_contextual=round(score, 4),
                lexico_version=LEXICO_VERSION,
                fusion_automatica=False, texto_restringido=True))

        meta_regla = ont.REGLAS["R13_CONTEXTO_LUGAR"]
        peso = round(meta_regla["peso_base"] * score, 4)
        disparos.append(dict(
            reporte_a=rid_a, reporte_b=rid_b,
            regla="R13_CONTEXTO_LUGAR",
            regla_version=meta_regla["version"],
            nodo=None, tipo="LUGAR_MENCION",
            valor=u", ".join(comunes),
            peso_base=meta_regla["peso_base"], peso_efectivo=peso,
            factor_discriminancia=1.0, factor_texto_libre=1.0,
            factor_similitud=round(score, 4), desde_texto=True,
            lados_desde_texto=2,
            procedencia_lado_a="texto_restringido",
            procedencia_lado_b="texto_restringido",
            corrobora_solamente=True, origen_senal=ont.INFERIDA,
            arista_soporte=aid,
            source_locators=locators,
            nota=(u"las descripciones de lugar comparten las categorías %s; "
                  u"es una semejanza contextual y no prueba que se trate del "
                  u"mismo sitio" % u", ".join(comunes))))
        similitudes.append(dict(
            arista_id=aid, reporte_a=rid_a, reporte_b=rid_b,
            categorias_comunes=comunes,
            dimensiones_comunes=sorted(dims_comunes),
            puntaje=round(score, 4), fusion_automatica=False))

    perfiles_salida = [dict(
        reporte=p["reporte"], nodo=p["nodo"], tags=sorted(p["tags"]),
        dimensiones=sorted(p["dimensiones"]), locators=p["locators"],
        hashes=p["hashes"])
        for p in perfiles.values()]
    return dict(
        perfiles=perfiles_salida, similitudes=similitudes, disparos=disparos,
        metodo=METODO, version=VERSION, lexico_version=LEXICO_VERSION,
        formula="peso_dimensiones_comunes/peso_dimensiones_union",
        umbral=UMBRAL_SIMILITUD)
