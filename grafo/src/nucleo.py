# -*- coding: utf-8 -*-
"""
Nucleo del grafo: contenedor, procedencia y metadatos obligatorios de arista.

Decisiones de diseno:

1. MultiDiGraph. Dos nodos pueden estar relacionados por varias vias distintas
   (una comunicacion, un lugar, un archivo, una coincidencia temporal), cada
   una con su propia fuente y fuerza (contexto.md 10.4).

2. Toda arista lleva el bloque de procedencia completo. Si falta la fuente o
   el locator, la arista no se crea: se registra un incumplimiento. Es
   preferible perder un vinculo a tener uno que no se pueda explicar.

3. El identificador de arista es determinista: se calcula a partir de los
   extremos, el tipo de relacion, el metodo y el locator. Asi una reconstruccion
   del grafo vuelve a producir los mismos ids y las validaciones humanas
   registradas antes siguen aplicando.

4. El grafo es una proyeccion analitica reconstruible, no el registro oficial
   (contexto.md 12.2). Nada de lo que vive aca es la fuente de verdad.
"""

import hashlib
import json
from datetime import datetime, timezone

import networkx as nx

import ontologia as ont


def ahora_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hash_archivo(ruta, algoritmo="sha256"):
    h = hashlib.new(algoritmo)
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(65536), b""):
            h.update(bloque)
    return "%s:%s" % (algoritmo, h.hexdigest())


def hash_texto(texto, algoritmo="sha256"):
    h = hashlib.new(algoritmo)
    h.update(texto.encode("utf-8"))
    return "%s:%s" % (algoritmo, h.hexdigest())


class IncumplimientoProcedencia(Exception):
    pass


class Grafo(object):
    """Contenedor del grafo con control de procedencia."""

    def __init__(self, ts_corrida=None, estricto=True):
        self.G = nx.MultiDiGraph()
        # ts_corrida fijo para toda la construccion: hace la corrida reproducible
        # y comparable. No se usa el reloj por arista.
        self.ts_corrida = ts_corrida or ahora_utc()
        self.estricto = estricto
        self.incumplimientos = []
        self.fuentes = {}     # source_evidence_id -> metadatos de la fuente

    # -- fuentes -----------------------------------------------------------
    def registrar_fuente(self, source_evidence_id, ruta=None, tipo=None, extra=None):
        meta = dict(id=source_evidence_id, tipo=tipo, ruta=str(ruta) if ruta else None)
        if ruta:
            meta["hash"] = hash_archivo(ruta)
        if extra:
            meta.update(extra)
        self.fuentes[source_evidence_id] = meta
        return meta

    def reporte_de_fuente(self, source_evidence_id):
        """Devuelve la clave canonica del reporte al que pertenece una fuente.

        Los JSON principales usan ``ncmec:<id>``. Un manifiesto multimedia es
        otra fuente y debe conservar su propio hash, pero cada entrada declara
        a que reporte aporta evidencia. Esta resolucion evita falsificar la
        procedencia solo para que los algoritmos puedan agruparla.
        """
        sid = str(source_evidence_id or "")
        if sid.startswith("ncmec:"):
            return sid
        rid = (self.fuentes.get(sid) or {}).get("report_id")
        return "ncmec:%s" % rid if rid is not None else None

    # -- nodos -------------------------------------------------------------
    def nodo(self, tipo, valor, etiqueta=None, **atributos):
        if tipo not in ont.TIPOS_NODO:
            raise ValueError("tipo de nodo fuera de la ontologia: %s" % tipo)
        node_id = ont.nid(tipo, valor)
        if node_id in self.G:
            datos = self.G.nodes[node_id]
            for k, v in atributos.items():
                if v is None:
                    continue
                if k in datos and datos[k] != v:
                    datos.setdefault("_variantes", {}).setdefault(k, [])
                    if v not in datos["_variantes"][k]:
                        datos["_variantes"][k].append(v)
                else:
                    datos[k] = v
        else:
            self.G.add_node(
                node_id,
                tipo=tipo,
                valor=str(valor),
                etiqueta=etiqueta or str(valor),
                identificador=ont.TIPOS_NODO[tipo]["identificador"],
                fusionable=ont.TIPOS_NODO[tipo]["fusionable"],
                **{k: v for k, v in atributos.items() if v is not None}
            )
        return node_id

    # -- aristas -----------------------------------------------------------
    def arista(self, u, v, relacion, source_evidence_id, source_locator,
               explicacion, metodo, metodo_version="1.0", confianza=None,
               observed_at=None, case_scope=None, atributos=None):
        """Crea una arista con el bloque de procedencia completo.

        source_locator: ubicacion exacta dentro de la fuente. Para un JSON de
        NCMEC es la ruta del campo; para un PDF, pagina; para un video, el
        timestamp o frame.
        """
        if relacion not in ont.RELACIONES:
            raise ValueError("relacion fuera del vocabulario: %s" % relacion)
        origen = ont.RELACIONES[relacion]["origen"]

        faltantes = []
        if not source_evidence_id:
            faltantes.append("source_evidence_id")
        if not source_locator:
            faltantes.append("source_locator")
        if not explicacion:
            faltantes.append("explicacion")
        # Una afirmacion humana no lleva confianza: ponerle un numero seria
        # inventar una precision que nadie calculo. Lo que sí lleva es quien la
        # dispuso y con que fundamento.
        if origen in (ont.DERIVADA, ont.INFERIDA) and confianza is None:
            faltantes.append("confidence")
        if faltantes:
            problema = dict(relacion=relacion, u=u, v=v, faltantes=faltantes)
            self.incumplimientos.append(problema)
            if self.estricto:
                raise IncumplimientoProcedencia(json.dumps(problema, ensure_ascii=False))
            return None

        if confianza is not None:
            confianza = round(min(float(confianza), ont.CONFIANZA_MAXIMA), 4)

        arista_id = self._id_arista(u, v, relacion, metodo, source_locator,
                                    source_evidence_id)

        datos = dict(
            arista_id=arista_id,
            relation_type=relacion,
            origin=origen,
            source_evidence_id=source_evidence_id,
            source_locator=source_locator,
            method=metodo,
            method_version=metodo_version,
            ontologia_version=ont.ONTOLOGIA_VERSION,
            confidence=confianza,
            # El nombre ``confidence`` se conserva por compatibilidad con las
            # salidas existentes. Ninguno de estos valores se entreno ni se
            # calibro contra una muestra validada: son puntajes de reglas.
            confidence_calibrated=(False if origen in (ont.DERIVADA,
                                                        ont.INFERIDA)
                                   else None),
            observed_at=observed_at,
            created_at=self.ts_corrida,
            validation_status=ont.ESTADO_INICIAL[origen],
            validated_by=None,
            validated_at=None,
            case_scope=case_scope,
            explicacion=explicacion,
            vigente=True,
        )
        if atributos:
            datos.update({k: val for k, val in atributos.items() if val is not None})

        self.G.add_edge(u, v, key=arista_id, **datos)
        return arista_id

    @staticmethod
    def _id_arista(u, v, relacion, metodo, locator, source_evidence_id):
        # La fuente forma parte del identificador: dos reportes que afirman lo
        # mismo son dos piezas de evidencia distintas, no una sola. Sin esto,
        # locators identicos entre reportes (todos traen
        # reportedPersons[0].sourceCaptures[0]) colapsan y se pierde evidencia.
        crudo = "|".join([u, v, relacion, str(metodo), str(locator),
                          str(source_evidence_id)])
        return "e_" + hashlib.sha1(crudo.encode("utf-8")).hexdigest()[:16]

    # -- consultas ---------------------------------------------------------
    def aristas(self, origen=None, relacion=None, vigentes=True):
        for u, v, k, d in self.G.edges(keys=True, data=True):
            if vigentes and not d.get("vigente", True):
                continue
            if origen and d.get("origin") != origen:
                continue
            if relacion and d.get("relation_type") != relacion:
                continue
            yield u, v, k, d

    def nodos_tipo(self, tipo):
        return [n for n, d in self.G.nodes(data=True) if d.get("tipo") == tipo]

    def resumen(self):
        por_tipo = {}
        for _, d in self.G.nodes(data=True):
            por_tipo[d["tipo"]] = por_tipo.get(d["tipo"], 0) + 1
        por_origen = {}
        por_relacion = {}
        for _, _, _, d in self.G.edges(keys=True, data=True):
            por_origen[d["origin"]] = por_origen.get(d["origin"], 0) + 1
            por_relacion[d["relation_type"]] = por_relacion.get(d["relation_type"], 0) + 1
        return dict(
            nodos=self.G.number_of_nodes(),
            aristas=self.G.number_of_edges(),
            nodos_por_tipo=por_tipo,
            aristas_por_origen=por_origen,
            aristas_por_relacion=por_relacion,
            incumplimientos=len(self.incumplimientos),
        )

    # -- persistencia ------------------------------------------------------
    def a_dict(self):
        return dict(
            meta=dict(
                ontologia_version=ont.ONTOLOGIA_VERSION,
                ts_corrida=self.ts_corrida,
                resumen=self.resumen(),
            ),
            fuentes=self.fuentes,
            nodos=[dict(id=n, **d) for n, d in self.G.nodes(data=True)],
            aristas=[dict(origen_nodo=u, destino_nodo=v, **d)
                     for u, v, k, d in self.G.edges(keys=True, data=True)],
            incumplimientos=self.incumplimientos,
        )

    def guardar_json(self, ruta):
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(self.a_dict(), fh, ensure_ascii=False, indent=1)
        return ruta

    def guardar_graphml(self, ruta):
        """GraphML para abrir en Gephi, yEd o Cytoscape."""
        H = nx.MultiDiGraph()
        for n, d in self.G.nodes(data=True):
            H.add_node(n, **{k: _plano(v) for k, v in d.items()})
        for u, v, k, d in self.G.edges(keys=True, data=True):
            H.add_edge(u, v, key=k, **{kk: _plano(vv) for kk, vv in d.items()
                                       if vv is not None})
        nx.write_graphml(H, ruta)
        return ruta


def _plano(valor):
    if isinstance(valor, (dict, list, tuple)):
        return json.dumps(valor, ensure_ascii=False)
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return valor
    return valor
