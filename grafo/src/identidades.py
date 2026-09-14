# -*- coding: utf-8 -*-
"""
Consolidacion de identidades: la unificacion que decide una persona.

El sistema nunca fusiona personas por su cuenta. Propone la hipotesis
POSIBLE_MISMA_IDENTIDAD y espera. Cuando un operador la valida, este modulo
crea un nodo IDENTIDAD que agrupa las menciones validadas y las conecta con
IDENTIFICADO_COMO.

Tres propiedades que hacen que esto sea reversible y auditable:

1. Las menciones NO se borran. Cada reporte sigue teniendo la suya, con su
   locator. La identidad es una capa por encima, no un reemplazo.
2. La agrupacion es la clausura transitiva de las validaciones humanas: si
   alguien valido A=B y otro valido B=C, las tres menciones quedan bajo la
   misma identidad. Eso es deliberado, y por eso la explicacion de cada arista
   dice quien valido que par.
3. Si una validacion se revierte en el libro, la identidad se recalcula sola en
   la proxima construccion. No hay estado que limpiar a mano.
"""

import hashlib
from collections import defaultdict

import ontologia as ont

METODO = "consolidacion_identidad"
VERSION = "1.1"


def _raiz(padre, x):
    while padre[x] != x:
        padre[x] = padre[padre[x]]
        x = padre[x]
    return x


def consolidar(g):
    """Crea nodos IDENTIDAD a partir de las hipotesis ya validadas.

    Debe llamarse DESPUES de re-aplicar el libro de validaciones, porque lee el
    estado de validacion de cada arista.
    """
    padre, decisiones = {}, defaultdict(list)

    for u, v, k, d in g.aristas(relacion="POSIBLE_MISMA_IDENTIDAD", vigentes=False):
        if d.get("validation_status") != "validada":
            continue
        for n in (u, v):
            padre.setdefault(n, n)
        ru, rv = _raiz(padre, u), _raiz(padre, v)
        if ru != rv:
            padre[rv] = ru
        decisiones[u].append(d)
        decisiones[v].append(d)

    if not padre:
        return []

    grupos = defaultdict(list)
    for n in padre:
        grupos[_raiz(padre, n)].append(n)

    consolidadas = []
    for raiz, menciones in sorted(grupos.items()):
        menciones = sorted(menciones)
        if len(menciones) < 2:
            continue

        reportes = sorted({g.G.nodes[m].get("reporte") for m in menciones
                           if g.G.nodes[m].get("reporte")})
        # Dos personas diferentes pueden aparecer en exactamente los mismos
        # reportes. La clave anterior usaba solo esos numeros y colapsaba ambos
        # grupos en un unico nodo IDENTIDAD. La composicion concreta de
        # menciones es la identidad logica de este agrupamiento.
        huella_menciones = hashlib.sha256(
            "|".join(menciones).encode("utf-8")).hexdigest()
        clave = "id-" + huella_menciones[:16]
        quienes = sorted({x.get("validated_by") for m in menciones
                          for x in decisiones[m] if x.get("validated_by")})
        cuando = sorted({x.get("validated_at") for m in menciones
                         for x in decisiones[m] if x.get("validated_at")})

        n_id = g.nodo(
            "IDENTIDAD", clave,
            etiqueta=u"Identidad unificada (%s)" % u", ".join(reportes),
            reportes=", ".join(reportes),
            huella_menciones="sha256:" + huella_menciones,
            menciones_unificadas=len(menciones),
            validada_por=", ".join(quienes) or None,
            validada_en=cuando[-1] if cuando else None)

        sid = "validacion:identidad:%s" % clave
        g.registrar_fuente(sid, tipo="decision_humana_de_unificacion",
                           extra=dict(menciones=menciones, validada_por=quienes))

        for m in menciones:
            pares = decisiones[m]
            aid = g.arista(
                m, n_id, "IDENTIFICADO_COMO", sid,
                " | ".join(sorted({x["arista_id"] for x in pares})),
                (u"Esta mención quedó unificada bajo una misma identidad por "
                 u"decisión de %s.\n\n"
                 u"La unificación agrupa las menciones de los reportes %s. No "
                 u"reemplaza a ninguna de ellas: cada reporte conserva la suya, "
                 u"con su fuente. Si la validación se revierte, la identidad "
                 u"desaparece sola en la próxima construcción del grafo."
                 % (u" y ".join(quienes) or u"un operador", u", ".join(reportes))),
                METODO, VERSION, confianza=ont.CONFIANZA_MAXIMA)
            # Nace validada porque no es una propuesta del sistema: es el
            # registro de una decision que una persona ya tomo.
            for uu, vv, kk, dd in g.aristas(vigentes=False):
                if dd["arista_id"] == aid:
                    dd["validation_status"] = "validada"
                    dd["validated_by"] = ", ".join(quienes) or None
                    dd["validated_at"] = cuando[-1] if cuando else None

        consolidadas.append(dict(
            identidad=n_id, clave=clave, menciones=menciones,
            reportes=reportes, validada_por=quienes))
    return consolidadas
