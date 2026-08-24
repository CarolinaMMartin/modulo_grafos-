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


class LibroVinculos(object):
    """Vinculaciones que establece una persona, no el sistema.

    Existe porque el circuito real las necesita: dos reportes se archivaron por
    falta de prueba y un operador, con el expediente delante, concluye que
    tienen que ver. El sistema no lo dedujo y no puede deducirlo; la decision es
    de la persona y el sistema tiene que poder conservarla.

    Mismo mecanismo que el libro de validaciones: append-only, encadenado por
    hash y con las mismas limitaciones (ver el encabezado del modulo). Lo que
    cambia es que aca no se decide sobre una arista existente sino que se crea
    una, y por eso el registro guarda el par de reportes y no un arista_id: el
    identificador se calcula despues, al materializarla, y sale igual en cada
    corrida.

    Una vinculacion manual se revierte con otro registro, nunca borrando el
    anterior. La historia de la decision se conserva.
    """

    ACCIONES = ("vincular", "desvincular")
    METODO = "vinculacion_manual"
    METODO_VERSION = "1.0"

    def __init__(self, ruta):
        self.ruta = ruta
        self._registros = None

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

    def registrar(self, reporte_a, reporte_b, accion, usuario, motivo="", ts=None):
        if accion not in self.ACCIONES:
            raise ValueError("accion invalida: %s" % accion)
        if not usuario:
            raise ValueError("toda vinculacion manual debe identificar al usuario")
        if accion == "vincular" and not motivo:
            raise ValueError("una vinculacion manual debe declarar su fundamento")
        a, b = sorted((str(reporte_a), str(reporte_b)))
        if a == b:
            raise ValueError("no se puede vincular un reporte consigo mismo")
        reg = dict(
            secuencia=len(self.registros()) + 1,
            reporte_a=a, reporte_b=b,
            accion=accion, usuario=usuario, motivo=motivo,
            ts=ts or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            prev_hash=self._ultimo_hash(),
        )
        reg["hash"] = _hash_registro(reg)
        with open(self.ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(reg, ensure_ascii=False) + "\n")
        self._registros.append(reg)
        return reg

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

    def vigentes(self):
        """Ultimo estado de cada par. Un par revertido no vuelve a aparecer."""
        estado = {}
        for reg in self.registros(recargar=True):
            estado[(reg["reporte_a"], reg["reporte_b"])] = reg
        return [r for r in estado.values() if r["accion"] == "vincular"]

    def aplicar(self, g):
        """Materializa en el grafo las vinculaciones vigentes.

        Se corre antes de agrupar en legajos: una vinculacion manual tiene que
        poner los dos reportes en el mismo caso, que es lo que el operador
        espera al establecerla.
        """
        creadas, huerfanas = [], []
        historial = {}
        for reg in self.registros(recargar=True):
            historial.setdefault((reg["reporte_a"], reg["reporte_b"]), []).append(reg)

        for reg in self.vigentes():
            na = ont.nid("REPORTE", reg["reporte_a"])
            nb = ont.nid("REPORTE", reg["reporte_b"])
            if na not in g.G or nb not in g.G:
                huerfanas.append(reg)
                continue
            aid = g.arista(
                na, nb, "VINCULADO_POR_OPERADOR",
                source_evidence_id="operador:%s" % reg["usuario"],
                source_locator="libro:vinculos_manuales#%d" % reg["secuencia"],
                explicacion=(
                    u"Los reportes %s y %s quedaron vinculados por decisión de "
                    u"%s, el %s. No la propuso el sistema: no consta en la "
                    u"fuente ni surge de una regla. El fundamento registrado es: "
                    u"«%s». La vinculación se conserva hasta que se revierta "
                    u"desde el libro, y la reversión también queda asentada."
                    % (reg["reporte_a"], reg["reporte_b"], reg["usuario"],
                       reg["ts"][:10], reg["motivo"])),
                metodo=self.METODO, metodo_version=self.METODO_VERSION,
                atributos=dict(
                    dispuesta_por=reg["usuario"],
                    motivo_operador=reg["motivo"],
                    historial_vinculo=historial[(reg["reporte_a"], reg["reporte_b"])],
                ))
            if aid:
                d = g.G.edges[na, nb, aid]
                d["validated_by"] = reg["usuario"]
                d["validated_at"] = reg["ts"]
                creadas.append(dict(reporte_a=reg["reporte_a"],
                                    reporte_b=reg["reporte_b"],
                                    arista_id=aid, usuario=reg["usuario"],
                                    motivo=reg["motivo"], ts=reg["ts"]))
        return dict(creadas=creadas, huerfanas=huerfanas,
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
