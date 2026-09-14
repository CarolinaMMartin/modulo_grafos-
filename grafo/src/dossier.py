# -*- coding: utf-8 -*-
"""
Dossier crudo de vinculaciones: la salida estructurada de los algoritmos.

Es el insumo del informe discursivo. Contiene, para cada vinculacion, su peso
total y el aporte de cada regla por separado, de modo que el informe pueda
decir no solo QUE dos reportes estan vinculados, sino CUANTO pesa cada elemento
en esa conclusion.

Incluye ademas un seudonimizador. Antes de enviar el dossier a cualquier modelo
de lenguaje, los identificadores reales -IP, cuentas, telefonos, dispositivos,
correos, hashes- se reemplazan por etiquetas estables (IP-1, CUENTA-2). El
modelo redacta sobre las etiquetas y los valores reales se restituyen despues,
sobre el texto devuelto. Asi el texto sensible nunca sale del entorno, aun
cuando el modelo corra fuera de el.
"""

import json
import re
from collections import OrderedDict, defaultdict

import ontologia as ont

VERSION = "1.0"

TIPOS_SENSIBLES = ("IP", "CUENTA", "TELEFONO", "EMAIL", "DISPOSITIVO",
                   "ALIAS", "ALIAS_PAGO", "EVIDENCIA", "HASH_PERCEPTUAL",
                   "HUELLA_AUDIO")


# ---------------------------------------------------------------------------
# Construccion
# ---------------------------------------------------------------------------
def construir(g, res):
    reportes = OrderedDict()
    for n in sorted(g.nodos_tipo("REPORTE"), key=lambda x: g.G.nodes[x]["valor"]):
        d = g.G.nodes[n]
        reportes[d["valor"]] = dict(
            reporte=d["valor"],
            plataforma=d.get("plataforma"),
            clasificacion=d.get("clasificacion"),
            prioridad=d.get("prioridad"),
            fecha_del_hecho=d.get("fecha_incidente"),
            fecha_de_recepcion=d.get("fecha_recepcion"),
            estado=d.get("estado_sipar"),
            motivo_de_archivo=d.get("motivo_archivo"),
            fecha_del_estado=d.get("fecha_estado"),
            identificadores=_identificadores(g, n),
        )

    vinculaciones = []
    for u, v, k, d in g.aristas(origen=ont.DERIVADA):
        if d["relation_type"] not in ("COINCIDE_CON", "POSIBLE_DUPLICADO_DE"):
            continue
        detalle = d.get("detalle_reglas") or []
        vinculaciones.append(dict(
            id=d["arista_id"],
            reporte_a=g.G.nodes[u]["valor"], reporte_b=g.G.nodes[v]["valor"],
            tipo_de_relacion=d["relation_type"],
            peso_total=d.get("confidence"),
            franja=ont.franja_confianza(d.get("confidence") or 0),
            estado_de_revision=d.get("validation_status"),
            revisada_por=d.get("validated_by"),
            sostienen=[_regla(x) for x in detalle if not x["corrobora_solamente"]],
            corroboran=[_regla(x) for x in detalle if x["corrobora_solamente"]],
            indicios_de_duplicado=d.get("indicios_duplicado"),
            evidencia=str(d.get("source_locator") or "").split(" | "),
            metodo="%s v%s" % (d.get("method"), d.get("method_version")),
            fundamento=d.get("explicacion"),
        ))
    vinculaciones.sort(key=lambda x: -(x["peso_total"] or 0))

    alertas = res.get("alertas", {})
    dossier = OrderedDict()
    dossier["meta"] = dict(
        version_dossier=VERSION,
        corrida=res.get("corrida"),
        version_ontologia=res.get("ontologia_version"),
        reportes_analizados=res.get("reportes_ingeridos"),
        pares_evaluados=res.get("vinculacion", {}).get("pares_evaluados"),
        advertencias=[
            u"Todas las vinculaciones son propuestas del sistema y ninguna "
            u"acredita autoría ni responsabilidad.",
            u"Las relaciones derivadas surgen de reglas deterministas; las "
            u"inferidas son hipótesis y requieren validación humana.",
            u"Un reporte archivado no es un caso negativo: describe "
            u"insuficiencia de evidencia en el momento del archivo.",
            u"En esta etapa no se clasifica jurisdicción ni se preparan "
            u"derivaciones territoriales.",
        ])
    dossier["glosario_de_reglas"] = {
        r: dict(descripcion=m["desc"], peso_maximo=m["peso_base"],
                solo_corrobora=m["corrobora_solamente"])
        for r, m in ont.REGLAS.items()}
    dossier["reportes"] = list(reportes.values())
    dossier["vinculaciones"] = vinculaciones
    dossier["pesos"] = _resumen_pesos(vinculaciones)
    dossier["vinculaciones_descartadas"] = [
        dict(reporte_a=x["reporte_a"], reporte_b=x["reporte_b"],
             peso_total=x["confianza"], motivo=x["motivo"],
             elementos=[_regla(y) for y in x["disparos"]])
        for x in res.get("vinculacion", {}).get("descartados", [])]
    # Vinculaciones que dispuso una persona. Van en el dossier -y por lo tanto
    # en el informe- separadas de las que propuso el sistema: es una afirmacion
    # de quien firma, no un hallazgo del analisis.
    dossier["vinculaciones_manuales"] = [
        dict(reporte_a=g.G.nodes[u]["valor"], reporte_b=g.G.nodes[v]["valor"],
             dispuesta_por=d.get("dispuesta_por") or d.get("validated_by"),
             fecha=d.get("validated_at"),
             motivo=d.get("motivo_operador"),
             fundamento=d.get("explicacion"))
        for u, v, k, d in g.aristas(origen=ont.AFIRMADA)
        if d["relation_type"] == "VINCULADO_POR_OPERADOR"]
    dossier["antecedentes_reactivados"] = [
        dict(reporte_archivado=a["reporte_archivado"],
             motivo_de_archivo=a["motivo_archivo"],
             reporte_que_lo_reactiva=a["reporte_disparador"],
             estado_de_ese_reporte=a["estado_disparador"],
             prioridad=a["prioridad"],
             peso_del_vinculo=a["confianza_vinculo"],
             que_aporta=list(a["aportes"].keys()),
             fundamento=a["explicacion"])
        for a in alertas.get("alertas", [])]
    # El campo `reportes` es lo que permite despues acotar el dossier a un caso.
    dossier["contra_evidencia"] = [
        dict(entidad=g.G.nodes[c["ancla"]].get("etiqueta") if c["ancla"] in g.G else c["ancla"],
             kilometros=c["km"], horas=c["horas"], km_por_hora=c["kmh"],
             reportes=_reportes_de(g, c["ancla"]),
             fundamento=_explic(g, c["arista_id"]))
        for c in res.get("contradicciones", [])]
    dossier["hipotesis_de_identidad"] = [
        dict(mencion_a=g.G.nodes[h["a"]].get("etiqueta") if h["a"] in g.G else h["a"],
             mencion_b=g.G.nodes[h["b"]].get("etiqueta") if h["b"] in g.G else h["b"],
             cuenta_compartida=h["cuenta"],
             reportes=sorted(set(_reportes_de(g, h["a"])) | set(_reportes_de(g, h["b"]))),
             fundamento=_explic(g, h["arista_id"]))
        for h in res.get("identidades", [])]
    dossier["agrupamientos"] = res.get("legajos", [])
    dossier["pendientes_de_revision"] = len(res.get("cola_revision", []))
    return dossier


def _reportes_de(g, n):
    """Reportes que mencionan un nodo. Sale de la procedencia de sus aristas."""
    if n not in g.G:
        return []
    if g.G.nodes[n].get("tipo") == "REPORTE":
        return [g.G.nodes[n]["valor"]]
    rs = set()
    for u, v, k, d in g.aristas(vigentes=False):
        if u != n and v != n:
            continue
        sid = g.reporte_de_fuente(d.get("source_evidence_id")) or ""
        if sid:
            rs.add(sid.split(":", 1)[1])
    return sorted(rs)


def recortar(d, reportes):
    """Dossier acotado a un caso.

    El grafo se construye sobre todo el archivo -de ahi salen los antecedentes-,
    pero el informe que firma un operador es del caso que tiene entre manos.
    Enumerar el archivo entero deja de ser posible apenas hay unos miles de
    reportes, y ademas pone en el informe material ajeno al caso.
    """
    rs = set(reportes)
    toca = lambda x: x.get("reporte_a") in rs or x.get("reporte_b") in rs
    alcanza = lambda x: bool(set(x.get("reportes") or []) & rs)

    e = OrderedDict()
    e["meta"] = dict(d["meta"])
    e["meta"]["reportes_del_caso"] = sorted(rs)
    e["glosario_de_reglas"] = d["glosario_de_reglas"]
    e["reportes"] = [r for r in d["reportes"] if r["reporte"] in rs]
    e["vinculaciones"] = [v for v in d["vinculaciones"] if toca(v)]
    e["pesos"] = _resumen_pesos(e["vinculaciones"])
    e["vinculaciones_descartadas"] = [x for x in d["vinculaciones_descartadas"]
                                      if toca(x)]
    e["vinculaciones_manuales"] = [x for x in d.get("vinculaciones_manuales", [])
                                   if toca(x)]
    e["antecedentes_reactivados"] = [
        a for a in d["antecedentes_reactivados"]
        if a["reporte_archivado"] in rs or a["reporte_que_lo_reactiva"] in rs]
    e["contra_evidencia"] = [c for c in d["contra_evidencia"] if alcanza(c)]
    e["hipotesis_de_identidad"] = [h for h in d["hipotesis_de_identidad"]
                                   if alcanza(h)]
    e["agrupamientos"] = [l for l in d["agrupamientos"]
                          if set(l.get("reportes") or []) & rs]
    e["pendientes_de_revision"] = d["pendientes_de_revision"]
    return e


def _regla(x):
    meta = ont.REGLAS.get(x["regla"], {})
    return dict(
        regla=x["regla"],
        elemento=ont.ETIQUETA_TIPO.get(x.get("tipo"), x.get("tipo")),
        valor=x.get("valor"),
        peso_aportado=x.get("peso_efectivo"),
        peso_maximo_de_la_regla=meta.get("peso_base"),
        ajuste_por_frecuencia=x.get("factor_discriminancia"),
        solo_corrobora=x.get("corrobora_solamente"),
        redaccion=x.get("nota"))


def _identificadores(g, n_rep):
    sid = "ncmec:%s" % g.G.nodes[n_rep]["valor"]
    por_tipo = defaultdict(set)
    for u, v, k, d in g.aristas():
        if g.reporte_de_fuente(d.get("source_evidence_id")) != sid:
            continue
        for n in (u, v):
            t = g.G.nodes[n].get("tipo")
            if t in TIPOS_SENSIBLES:
                por_tipo[t].add(g.G.nodes[n].get("valor"))
    return {ont.ETIQUETA_TIPO.get(t, t): sorted(vs) for t, vs in por_tipo.items()}


def _resumen_pesos(vinculaciones):
    if not vinculaciones:
        return dict(cantidad=0)
    pesos = [v["peso_total"] for v in vinculaciones if v["peso_total"] is not None]
    por_regla = defaultdict(list)
    for v in vinculaciones:
        for r in v["sostienen"] + v["corroboran"]:
            por_regla[r["regla"]].append(r["peso_aportado"])
    return dict(
        cantidad=len(vinculaciones),
        peso_maximo=max(pesos), peso_minimo=min(pesos),
        peso_promedio=round(sum(pesos) / len(pesos), 4),
        por_franja={f: sum(1 for v in vinculaciones if v["franja"] == f)
                    for f in ("alta", "media", "baja")},
        aporte_por_regla={r: dict(veces=len(v), aporte_promedio=round(sum(v) / len(v), 4))
                          for r, v in sorted(por_regla.items())},
        umbral_para_proponer=ont.UMBRAL_PROPONER,
        peso_maximo_posible=ont.CONFIANZA_MAXIMA)


def _explic(g, arista_id):
    for u, v, k, d in g.aristas(vigentes=False):
        if d["arista_id"] == arista_id:
            return d.get("explicacion")
    return None


# ---------------------------------------------------------------------------
# Seudonimizacion
# ---------------------------------------------------------------------------
def seudonimizar(g, dossier):
    """Reemplaza identificadores reales por etiquetas estables.

    Devuelve (dossier_seudonimizado, mapa). El mapa NO debe salir del entorno:
    sirve para restituir los valores sobre el texto que devuelve el modelo.
    """
    contadores = defaultdict(int)
    mapa = OrderedDict()
    for n, d in g.G.nodes(data=True):
        t = d.get("tipo")
        if t not in TIPOS_SENSIBLES:
            continue
        valor = d.get("valor")
        if not valor or len(str(valor)) < 4 or valor in mapa:
            continue
        contadores[t] += 1
        mapa[str(valor)] = "%s-%d" % (t, contadores[t])

    # Se reemplaza primero lo mas largo: evita que una subcadena rompa un valor
    # mas extenso que la contiene.
    claves = sorted(mapa, key=len, reverse=True)
    crudo = json.dumps(dossier, ensure_ascii=False, indent=1, default=str)
    for real in claves:
        crudo = crudo.replace(real, mapa[real])
    return json.loads(crudo), mapa


def restituir(texto, mapa):
    """Devuelve los valores reales al texto redactado por el modelo."""
    inverso = sorted(((v, k) for k, v in mapa.items()), key=lambda x: len(x[0]),
                     reverse=True)
    for etiqueta, real in inverso:
        texto = re.sub(r"\b" + re.escape(etiqueta) + r"\b", real, texto)
    return texto


# ---------------------------------------------------------------------------
# Instrucciones para el modelo
# ---------------------------------------------------------------------------
SISTEMA = u"""Sos un asistente de redacción jurídica de un ministerio público. Tu \
tarea es convertir la salida estructurada de un sistema de análisis de \
vinculaciones en un informe discursivo dirigido a abogados y abogadas.

REGLAS QUE NO PODÉS QUEBRAR:

1. No inventes ningún dato. Si algo no está en el material, no existe. No \
completes con conocimiento general ni con suposiciones verosímiles.
2. Nunca afirmes autoría, responsabilidad ni culpabilidad de nadie. El sistema \
detecta coincidencias entre reportes, no atribuye conductas.
3. Mantené la distinción entre lo que consta en la fuente, lo que se derivó por \
una regla determinista y lo que es una hipótesis pendiente de validación. No las \
mezcles ni las presentes con el mismo grado de certeza.
4. Cada vez que menciones una vinculación, indicá su peso y qué elementos lo \
sostienen. Distinguí siempre entre los elementos que sostienen la vinculación por \
sí mismos y los que solamente la refuerzan.
5. Un reporte archivado no es un caso falso ni descartado: describe \
insuficiencia de evidencia al momento del archivo.
6. No propongas medidas procesales concretas ni califiques jurídicamente los \
hechos. Describí hallazgos y su fuerza probatoria aparente.
7. Los identificadores aparecen etiquetados (IP-1, CUENTA-2, DISPOSITIVO-1). \
Usalos tal cual, sin modificarlos y sin intentar adivinar el valor real.

REGISTRO Y FORMA:

- Castellano rioplatense, formal, en tercera persona.
- Prosa corrida. Evitá las viñetas salvo en el inventario de reportes.
- Frases completas. Nada de estilo telegráfico ni de jerga técnica sin explicar.
- Números decimales con coma.
- Markdown, con estos apartados y en este orden:

# Informe de vinculaciones
## I. Objeto y alcance
## II. Material analizado
## III. Vinculaciones detectadas
## IV. Peso de las vinculaciones
## V. Antecedentes archivados que corresponde revisar
## VI. Elementos que debilitan las vinculaciones
## VII. Coincidencias descartadas
## VIII. Limitaciones y advertencias

En el apartado IV explicá cómo se compone el peso: qué regla aportó cuánto y por \
qué algunos elementos solo refuerzan. En el VIII dejá constancia de que todo \
requiere validación humana y de que el sistema no clasifica jurisdicción."""


def prompt_usuario(dossier_seudo):
    return (u"A continuación, la salida estructurada del sistema de "
            u"vinculaciones. Redactá el informe siguiendo las instrucciones.\n\n"
            u"```json\n%s\n```"
            % json.dumps(dossier_seudo, ensure_ascii=False, indent=1, default=str))
