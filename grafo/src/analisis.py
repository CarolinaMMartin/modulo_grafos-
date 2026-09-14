# -*- coding: utf-8 -*-
"""
Algoritmos clasicos de grafos (fase G3), explicables y sin modelos.

Advertencia que debe acompanar cualquier salida de este modulo, y que se
incluye en el informe: una centralidad alta no indica culpabilidad ni
liderazgo. Describe una posicion estructural dentro del grafo construido con
los datos disponibles, que estan sesgados por lo que cada plataforma reporta.
"""

import math
from collections import defaultdict
from itertools import combinations

import networkx as nx

import ontologia as ont

METODO = "analisis_clasico"
VERSION = "1.2"

# Solo entidades con significado investigativo pueden originar candidatos.
# Plataforma informante, organismo receptor y otros nodos administrativos se
# conservan en el grafo, pero compartirlos no acerca dos reportes entre si.
TIPOS_VECINO_INVESTIGATIVO = {
    "CUENTA", "DISPOSITIVO", "TELEFONO", "EMAIL", "EVIDENCIA", "IP",
    "ALIAS", "ALIAS_PAGO", "UBICACION", "HASH_PERCEPTUAL", "HUELLA_AUDIO",
}

ADVERTENCIA_CENTRALIDAD = (
    "Las metricas describen la posicion de un nodo en el grafo disponible. No "
    "miden peligrosidad, responsabilidad ni jerarquia. Un nodo puede ser central "
    "solo porque su plataforma informa mas datos que las demas."
)


def proyeccion_reportes(g, umbral=None):
    """Grafo no dirigido reporte-reporte: lo que el sistema derivo, mas lo que
    un operador afirmo.

    Una vinculacion manual entra sin pasar por el umbral y con el peso maximo
    posible. No es que el sistema este seguro: es que ahi no hay calculo. La
    dispuso una persona, y por eso los dos reportes tienen que caer en el mismo
    legajo -que es lo que esa persona esta afirmando-.
    """
    umbral = ont.UMBRAL_CLUSTER if umbral is None else umbral
    P = nx.Graph()
    for n in g.nodos_tipo("REPORTE"):
        P.add_node(n, **{k: v for k, v in g.G.nodes[n].items()
                         if not isinstance(v, (dict, list))})
    for u, v, k, d in g.aristas(origen=ont.AFIRMADA):
        if d["relation_type"] != "VINCULADO_POR_OPERADOR":
            continue
        P.add_edge(u, v, peso=ont.CONFIANZA_MAXIMA,
                   distancia=1.0 / ont.CONFIANZA_MAXIMA,
                   relacion=d["relation_type"], arista_id=d["arista_id"])
    for u, v, k, d in g.aristas(origen=ont.DERIVADA):
        if d["relation_type"] not in ("COINCIDE_CON", "POSIBLE_DUPLICADO_DE"):
            continue
        if d.get("validation_status") == "rechazada":
            continue
        if (d.get("confidence") or 0) < umbral:
            continue
        if P.has_edge(u, v):
            # Una vinculacion manual no la pisa ninguna derivada.
            if P[u][v]["relacion"] == "VINCULADO_POR_OPERADOR":
                continue
            if P[u][v]["peso"] >= d["confidence"]:
                continue
        P.add_edge(u, v, peso=d["confidence"],
                   distancia=1.0 / max(d["confidence"], 0.0001),
                   relacion=d["relation_type"],
                   arista_id=d["arista_id"])
    return P


def legajos_logicos(g, umbral=None):
    """Componentes conexas de la proyeccion: casos que deberian mirarse juntos."""
    P = proyeccion_reportes(g, umbral)
    grupos = []
    for i, comp in enumerate(sorted(nx.connected_components(P), key=lambda c: -len(c))):
        if len(comp) < 2:
            continue
        sub = P.subgraph(comp)
        pesos = [d["peso"] for _, _, d in sub.edges(data=True)]
        grupos.append(dict(
            legajo="L%03d" % (i + 1),
            reportes=sorted(g.G.nodes[n]["valor"] for n in comp),
            nodos=sorted(comp),
            vinculos=sub.number_of_edges(),
            confianza_min=round(min(pesos), 3),
            confianza_max=round(max(pesos), 3),
            duplicados=[(g.G.nodes[u]["valor"], g.G.nodes[v]["valor"])
                        for u, v, d in sub.edges(data=True)
                        if d["relacion"] == "POSIBLE_DUPLICADO_DE"],
        ))
    return grupos


def comunidades(g, umbral=None):
    """Louvain sobre la proyeccion de reportes.

    Con pocos reportes coincide con las componentes conexas; recien aporta
    valor cuando el grafo tiene densidad suficiente.
    """
    P = proyeccion_reportes(g, umbral)
    if P.number_of_edges() == 0:
        return []
    algoritmo = "louvain"
    aviso = None
    try:
        parts = nx.community.louvain_communities(P, weight="peso", seed=7)
    except Exception as exc:
        algoritmo = "greedy_modularity_fallback"
        aviso = "%s: %s" % (type(exc).__name__, str(exc))
        parts = nx.community.greedy_modularity_communities(P, weight="peso")
    salida = []
    for i, c in enumerate(parts):
        if len(c) < 2:
            continue
        salida.append(dict(comunidad="C%03d" % (i + 1),
                           reportes=sorted(g.G.nodes[n]["valor"] for n in c),
                           tamano=len(c), algoritmo=algoritmo,
                           peso="peso", semilla=7 if algoritmo == "louvain" else None,
                           aviso_fallback=aviso))
    return salida


def centralidades(g, top=10):
    """Centralidades sobre la proyeccion reporte-reporte ya revisada.

    Plataforma, organismo receptor y otros nodos administrativos no compiten
    con los reportes. Para intermediacion, el puntaje de vinculacion se
    convierte en distancia inversa: una relacion mas fuerte representa un
    camino mas corto. PageRank usa el puntaje como peso de afinidad.
    """
    H = proyeccion_reportes(g)
    if H.number_of_nodes() == 0:
        return dict(advertencia=ADVERTENCIA_CENTRALIDAD,
                    proyeccion="reporte-reporte")

    grado = nx.degree_centrality(H)
    intermediacion = (nx.betweenness_centrality(H, weight="distancia")
                      if H.number_of_nodes() <= 3000 else {})
    pagerank = (nx.pagerank(H, weight="peso")
                if H.number_of_nodes() <= 20000 else {})

    def top_n(d, n):
        return [dict(nodo=k, etiqueta=g.G.nodes[k].get("etiqueta"),
                     tipo=g.G.nodes[k].get("tipo"), valor=round(v, 4))
                for k, v in sorted(d.items(), key=lambda x: -x[1])[:n]]

    puentes = [dict(a=u, b=v,
                    a_etiqueta=g.G.nodes[u].get("etiqueta"),
                    b_etiqueta=g.G.nodes[v].get("etiqueta"))
               for u, v in nx.bridges(H)]

    return dict(
        advertencia=ADVERTENCIA_CENTRALIDAD,
        proyeccion="reporte-reporte",
        nodos=H.number_of_nodes(), aristas=H.number_of_edges(),
        grado=top_n(grado, top),
        intermediacion=top_n(intermediacion, top) if intermediacion else [],
        pagerank=top_n(pagerank, top) if pagerank else [],
        puentes=puentes[:top],
    )


def candidatos_de_enlace(g, top=15):
    """Baseline explicable de link prediction (fase previa a cualquier GNN).

    Adamic-Adar sobre una proyeccion bipartita reporte-identificador. NO se
    escriben aristas: es una lista de pares para revision. Los pares se generan
    desde vecindarios compartidos, no combinando todos los reportes entre si;
    por eso el costo depende de las coincidencias reales y no de N al cuadrado.

    Los nodos administrativos quedan excluidos. Cada propuesta conserva, para
    ambos reportes, las relaciones y locators que explican el vecino comun.
    """
    reportes_por_sid = {
        "ncmec:%s" % g.G.nodes[n]["valor"]: n
        for n in g.nodos_tipo("REPORTE")
    }

    # identificador -> reporte fuente -> aristas que muestran de donde salio.
    indice = defaultdict(lambda: defaultdict(list))
    for u, v, k, d in g.aristas():
        if d.get("origin") not in (ont.OBSERVADA, ont.DERIVADA):
            continue
        sid = g.reporte_de_fuente(d.get("source_evidence_id")) or ""
        if sid not in reportes_por_sid:
            continue
        for n in (u, v):
            if g.G.nodes[n].get("tipo") in TIPOS_VECINO_INVESTIGATIVO:
                indice[n][sid].append(d)

    # Un par ya evaluado no reaparece como una sugerencia estructural, incluso
    # si su vinculacion fue rechazada: la decision humana no puede volver por
    # una puerta lateral con otro nombre.
    ya = set()
    for u, v, k, d in g.aristas(vigentes=False):
        if d.get("relation_type") in (
                "COINCIDE_CON", "POSIBLE_DUPLICADO_DE",
                "VINCULADO_POR_OPERADOR"):
            ya.add(frozenset((u, v)))

    vecinos_por_par = defaultdict(set)
    for n, por_reporte in indice.items():
        sids = sorted(por_reporte)
        if len(sids) < 2:
            continue
        tipo = g.G.nodes[n].get("tipo")
        pares_posibles = len(sids) * (len(sids) - 1) // 2
        limite = ont.MAX_PARES_POR_TIPO.get(
            tipo, ont.MAX_PARES_POR_TIPO["_default"])
        if pares_posibles > limite:
            # El grupo masivo ya queda inventariado por vincular_reportes. No
            # se expande aca con un limite distinto y oculto.
            continue
        for sid_a, sid_b in combinations(sids, 2):
            a, b = reportes_por_sid[sid_a], reportes_por_sid[sid_b]
            par = frozenset((a, b))
            if par not in ya:
                vecinos_por_par[tuple(sorted((a, b)))].add(n)

    salida = []
    for (a, b), comunes in vecinos_por_par.items():
        score = 0.0
        detalle = []
        sid_a = "ncmec:%s" % g.G.nodes[a]["valor"]
        sid_b = "ncmec:%s" % g.G.nodes[b]["valor"]
        for n in sorted(comunes):
            df = max(len(indice[n]), 2)
            aporte = 1.0 / math.log(df)
            score += aporte

            def soportes(sid):
                unicos = []
                vistos = set()
                for d in indice[n][sid]:
                    clave = (d.get("relation_type"), d.get("source_locator"))
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    unicos.append(dict(
                        relacion=d.get("relation_type"),
                        locator=d.get("source_locator"),
                        metodo="%s@%s" % (d.get("method"),
                                           d.get("method_version"))))
                return unicos

            detalle.append(dict(
                nodo=n, tipo=g.G.nodes[n].get("tipo"),
                etiqueta=g.G.nodes[n].get("etiqueta"),
                frecuencia_reportes=len(indice[n]),
                aporte_adamic_adar=round(aporte, 4),
                soporte_a=soportes(sid_a), soporte_b=soportes(sid_b)))

        if score <= 0:
            continue
        salida.append(dict(
            reporte_a=g.G.nodes[a]["valor"], reporte_b=g.G.nodes[b]["valor"],
            adamic_adar=round(score, 4),
            vecinos_comunes=detalle,
            metodo="%s@%s" % (METODO, VERSION),
            estado="candidato_no_materializado",
            nota="Par sugerido por identificadores investigativos compartidos. "
                 "Ninguna regla determinista lo sostiene todavia: sirve para "
                 "priorizar revision, no para afirmar un vinculo."))
    salida.sort(key=lambda x: (-x["adamic_adar"], x["reporte_a"], x["reporte_b"]))
    return salida[:top]


def cobertura_de_datos(g):
    """Que tan informado esta cada reporte. Explica por que un reporte queda
    aislado: normalmente por falta de datos, no por ausencia de relaciones."""
    filas = []
    for n_rep in sorted(g.nodos_tipo("REPORTE")):
        rid = g.G.nodes[n_rep]["valor"]
        sid = "ncmec:%s" % rid
        # Se cuentan nodos distintos, no aristas: una IP mencionada en tres
        # capturas del mismo reporte sigue siendo un solo identificador.
        vistos = defaultdict(set)
        for u, v, k, d in g.aristas():
            if g.reporte_de_fuente(d.get("source_evidence_id")) != sid:
                continue
            for n in (u, v):
                t = g.G.nodes[n].get("tipo")
                if t in ("CUENTA", "ALIAS", "IP", "DISPOSITIVO", "TELEFONO",
                         "EMAIL", "EVIDENCIA", "HASH_PERCEPTUAL",
                         "HUELLA_AUDIO"):
                    vistos[t].add(n)
        conteo = {t: len(s) for t, s in vistos.items()}
        identificadores = sum(conteo.values())
        filas.append(dict(
            reporte=rid,
            plataforma=g.G.nodes[n_rep].get("plataforma"),
            estado=g.G.nodes[n_rep].get("estado_sipar"),
            motivo_archivo=g.G.nodes[n_rep].get("motivo_archivo"),
            identificadores=identificadores,
            detalle=conteo,
            vinculable=identificadores > 0,
        ))
    return filas
