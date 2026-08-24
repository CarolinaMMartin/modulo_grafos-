# -*- coding: utf-8 -*-
"""
Algoritmos clasicos de grafos (fase G3), explicables y sin modelos.

Advertencia que debe acompanar cualquier salida de este modulo, y que se
incluye en el informe: una centralidad alta no indica culpabilidad ni
liderazgo. Describe una posicion estructural dentro del grafo construido con
los datos disponibles, que estan sesgados por lo que cada plataforma reporta.
"""

from collections import defaultdict
from itertools import combinations

import networkx as nx

import ontologia as ont

METODO = "analisis_clasico"
VERSION = "1.1"

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
        P.add_edge(u, v, peso=d["confidence"], relacion=d["relation_type"],
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
    try:
        parts = nx.community.louvain_communities(P, weight="peso", seed=7)
    except Exception:
        parts = nx.community.greedy_modularity_communities(P, weight="peso")
    salida = []
    for i, c in enumerate(parts):
        if len(c) < 2:
            continue
        salida.append(dict(comunidad="C%03d" % (i + 1),
                           reportes=sorted(g.G.nodes[n]["valor"] for n in c),
                           tamano=len(c)))
    return salida


def centralidades(g, top=10):
    """Centralidades sobre el grafo completo, no solo sobre reportes."""
    H = nx.Graph()
    for u, v, k, d in g.aristas():
        if d.get("validation_status") == "rechazada":
            continue
        H.add_edge(u, v)
    if H.number_of_nodes() == 0:
        return dict(advertencia=ADVERTENCIA_CENTRALIDAD)

    grado = nx.degree_centrality(H)
    intermediacion = nx.betweenness_centrality(H) if H.number_of_nodes() <= 3000 else {}
    pagerank = nx.pagerank(H) if H.number_of_nodes() <= 20000 else {}

    def top_n(d, n):
        return [dict(nodo=k, etiqueta=g.G.nodes[k].get("etiqueta"),
                     tipo=g.G.nodes[k].get("tipo"), valor=round(v, 4))
                for k, v in sorted(d.items(), key=lambda x: -x[1])[:n]]

    puentes = [dict(a=u, b=v,
                    a_etiqueta=g.G.nodes[u].get("etiqueta"),
                    b_etiqueta=g.G.nodes[v].get("etiqueta"))
               for u, v in nx.bridges(H)] if nx.is_connected(H) or True else []

    return dict(
        advertencia=ADVERTENCIA_CENTRALIDAD,
        grado=top_n(grado, top),
        intermediacion=top_n(intermediacion, top) if intermediacion else [],
        pagerank=top_n(pagerank, top) if pagerank else [],
        puentes=puentes[:top],
    )


def candidatos_de_enlace(g, top=15):
    """Baseline explicable de link prediction (fase previa a cualquier GNN).

    Adamic-Adar y vecinos comunes sobre el grafo de entidades. NO se escriben
    aristas: es una lista de pares para revision. Sirve como referencia contra
    la cual comparar despues un modelo, tal como pide la hoja de ruta.
    """
    H = nx.Graph()
    for u, v, k, d in g.aristas(origen=ont.OBSERVADA):
        H.add_edge(u, v)
    reportes = [n for n in g.nodos_tipo("REPORTE") if n in H]
    ya = set()
    for u, v, k, d in g.aristas(origen=ont.DERIVADA):
        if d["relation_type"] in ("COINCIDE_CON", "POSIBLE_DUPLICADO_DE"):
            ya.add(frozenset((u, v)))

    pares = [(a, b) for a, b in combinations(sorted(reportes), 2)
             if frozenset((a, b)) not in ya]
    if not pares:
        return []
    salida = []
    for a, b, score in nx.adamic_adar_index(H, pares):
        if score <= 0:
            continue
        comunes = sorted(nx.common_neighbors(H, a, b))
        salida.append(dict(
            reporte_a=g.G.nodes[a]["valor"], reporte_b=g.G.nodes[b]["valor"],
            adamic_adar=round(score, 4),
            vecinos_comunes=[dict(nodo=n, tipo=g.G.nodes[n].get("tipo"),
                                  etiqueta=g.G.nodes[n].get("etiqueta"))
                             for n in comunes],
            estado="candidato_no_materializado",
            nota="Par sugerido por similitud estructural. Ninguna regla "
                 "determinista lo sostiene todavia: sirve para priorizar "
                 "revision, no para afirmar un vinculo."))
    salida.sort(key=lambda x: -x["adamic_adar"])
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
            if d.get("source_evidence_id") != sid:
                continue
            for n in (u, v):
                t = g.G.nodes[n].get("tipo")
                if t in ("CUENTA", "ALIAS", "IP", "DISPOSITIVO", "TELEFONO",
                         "EMAIL", "EVIDENCIA"):
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
