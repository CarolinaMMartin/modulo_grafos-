# -*- coding: utf-8 -*-
"""
Libro de validaciones humanas: append-only y encadenado por hash.

Por que un libro separado y no un campo mutable en el grafo: el grafo es una
proyeccion reconstruible. Si se vuelve a construir desde los reportes, todo lo
calculado se pisa. Las decisiones de las personas no pueden perderse en ese
proceso, asi que viven aparte y se re-aplican sobre el grafo reconstruido.

Eso funciona porque el identificador de arista es determinista: la misma
evidencia con el mismo metodo produce el mismo arista_id en cada corrida.

Alcance real de la cadena de hashes: detecta modificacion o borrado de
registros anteriores. No es un sello de tiempo confiable ni impide que alguien
con acceso de escritura reescriba el archivo completo. Para esas garantias hace
falta almacenamiento append-only del lado del servidor o anclaje externo, que
todavia no esta definido en el proyecto.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

import ontologia as ont

DECISIONES = ("validada", "rechazada", "en_revision")


class LibroValidaciones(object):

    def __init__(self, ruta):
        self.ruta = ruta
        self._registros = None

    # -- lectura -----------------------------------------------------------
    def registros(self, recargar=False):
        if self._registros is None or recargar:
            self._registros = []
            if os.path.exists(self.ruta):
                with open(self.ruta, "r", encoding="utf-8") as fh:
                    for linea in fh:
                        linea = linea.strip()
                        if linea:
                            self._registros.append(json.loads(linea))
        return self._registros

    def _ultimo_hash(self):
        regs = self.registros()
        return regs[-1]["hash"] if regs else "genesis"

    # -- escritura ---------------------------------------------------------
    def registrar(self, arista_id, decision, usuario, observacion="", ts=None):
        if decision not in DECISIONES:
            raise ValueError("decision invalida: %s" % decision)
        if not usuario:
            raise ValueError("toda validacion debe identificar al usuario")
        reg = dict(
            secuencia=len(self.registros()) + 1,
            arista_id=arista_id,
            decision=decision,
            usuario=usuario,
            observacion=observacion,
            ts=ts or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            prev_hash=self._ultimo_hash(),
        )
        reg["hash"] = _hash_registro(reg)
        with open(self.ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(reg, ensure_ascii=False) + "\n")
        self._registros.append(reg)
        return reg

    # -- integridad --------------------------------------------------------
    def verificar(self):
        problemas = []
        prev = "genesis"
        for i, reg in enumerate(self.registros(recargar=True), start=1):
            esperado = dict(reg)
            h = esperado.pop("hash", None)
            if reg.get("prev_hash") != prev:
                problemas.append("registro %d: prev_hash no encadena" % i)
            if _hash_registro(esperado) != h:
                problemas.append("registro %d: hash no coincide con el contenido" % i)
            prev = h
        return problemas

    # -- aplicacion sobre el grafo ----------------------------------------
    def aplicar(self, g):
        """Re-aplica las decisiones humanas sobre un grafo recien construido."""
        por_arista = {}
        historial = {}
        for reg in self.registros(recargar=True):
            por_arista[reg["arista_id"]] = reg
            historial.setdefault(reg["arista_id"], []).append(reg)

        aplicadas, huerfanas = 0, []
        indice = {d["arista_id"]: (u, v, k) for u, v, k, d in g.aristas(vigentes=False)}
        for aid, reg in por_arista.items():
            if aid not in indice:
                huerfanas.append(reg)
                continue
            u, v, k = indice[aid]
            d = g.G.edges[u, v, k]
            d["validation_status"] = reg["decision"]
            d["validated_by"] = reg["usuario"]
            d["validated_at"] = reg["ts"]
            d["historial_validacion"] = historial[aid]
            if reg["decision"] == "rechazada":
                # No se borra: se marca. La historia de la decision se conserva.
                d["vigente"] = False
            aplicadas += 1
        return dict(aplicadas=aplicadas, huerfanas=huerfanas,
                    integridad=self.verificar())


def _hash_registro(reg):
    crudo = json.dumps(reg, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(crudo.encode("utf-8")).hexdigest()


def pendientes(g, solo_origen=None):
    """Cola de revision humana, priorizada."""
    filas = []
    for u, v, k, d in g.aristas():
        if d.get("validation_status") != "pendiente":
            continue
        if solo_origen and d["origin"] != solo_origen:
            continue
        filas.append(dict(
            arista_id=d["arista_id"], relacion=d["relation_type"], origen=d["origin"],
            confianza=d.get("confidence"),
            franja=ont.franja_confianza(d.get("confidence") or 0),
            a=g.G.nodes[u].get("etiqueta"), b=g.G.nodes[v].get("etiqueta"),
            explicacion=d.get("explicacion"), locator=d.get("source_locator"),
            metodo="%s@%s" % (d.get("method"), d.get("method_version")),
        ))
    # Primero lo inferido (mas riesgoso) y dentro de eso lo mas confiable.
    filas.sort(key=lambda x: (x["origen"] != ont.INFERIDA, -(x["confianza"] or 0)))
    return filas
