# -*- coding: utf-8 -*-
"""
Visualizador autocontenido del grafo (HTML + SVG, sin dependencias externas).

Restricciones del proyecto que este visor respeta:

- procesamiento local: no carga nada de internet, ni fuentes ni librerias;
- el estilo de la arista distingue observada / derivada / inferida;
- el color y el tamano no expresan sospecha: son de identificacion. El unico
  color de alarma esta reservado para la contra-evidencia;
- el detalle de cada relacion muestra su fundamento redactado, la fuente, el
  locator, el metodo y el estado de validacion;
- el texto sensible no se incluye: solo se referencia su hash y su locator;
- al generar el informe con un modelo, se envia el dossier seudonimizado y los
  identificadores se restituyen localmente sobre el texto devuelto.

Vistas:

- Solo vinculaciones : unicamente los reportes y las relaciones entre reportes.
                       Es la vista por defecto, la que responde "que se conecta
                       con que" sin la marana de entidades intermedias.
- Entorno directo    : agrega las entidades que cuelgan del reporte elegido.
- Todo               : el grafo completo.

Disposiciones: fuerzas (organica), jerarquica (por tipo de entidad) y por
legajo (agrupada por conjunto de reportes vinculados).
"""

import json

import networkx as nx

import ontologia as ont

ATRIBUTOS_LEGIBLES = {
    "valor": u"Valor", "clasificacion": u"Clasificación NCMEC",
    "prioridad": u"Prioridad", "plataforma": u"Plataforma", "pais": u"País",
    "fecha_incidente": u"Fecha del hecho", "fecha_recepcion": u"Fecha de recepción",
    "estado_sipar": u"Estado en SIPAR", "motivo_archivo": u"Motivo del archivo",
    "fecha_estado": u"Fecha del estado", "operador": u"Operador asignado",
    "esp": u"Plataforma", "esp_user_id": u"Identificador de usuario",
    "area": u"Código de área", "subtipo": u"Subtipo", "servicio": u"Servicio",
    "ciudad": u"Ciudad", "region": u"Región", "cp": u"Código postal",
    "lat": u"Latitud", "lon": u"Longitud", "forma_original": u"Forma original",
    "cgnat": u"Bajo CGNAT", "privada": u"Dirección privada",
    "atribuible_sin_dato_extra": u"Atribuible sin datos adicionales",
    "version": u"Versión IP", "cuenta_suspendida": u"Cuenta dada de baja",
    "genero": u"Género", "edad_aprox": u"Edad aproximada",
    "reporte": u"Reporte de origen", "nombre": u"Nombre del archivo",
    "tipo_mime": u"Tipo de archivo", "enviado_a_le": u"Remitido a autoridad",
    "prioridad_desc": u"Detalle de prioridad",
}

OCULTAR = {"tipo", "etiqueta", "identificador", "fusionable", "bio_hash",
           "decision", "transcripciones", "_variantes"}

# Escalones de la disposicion jerarquica: de la actuacion hacia el dato tecnico.
# Frase corta que explica por que dos reportes quedaron vinculados. Es lo que
# se escribe sobre el conector, como el "motivo vinculacion" del boceto.
MOTIVO_CORTO = {
    "CUENTA": u"misma cuenta",
    "DISPOSITIVO": u"mismo dispositivo",
    "TELEFONO": u"mismo teléfono",
    "EMAIL": u"mismo correo",
    "EVIDENCIA": u"mismo archivo",
    "IP": u"misma IP",
    "ALIAS": u"mismo nombre visible",
    "UBICACION": u"misma zona",
}

# Lo que se muestra al abrir un reporte: los datos por los que se vincula.
# Quedan afuera la mencion de persona y el chat, que son estructura interna del
# reporte y no son aquello que el operador esta buscando.
TIPOS_EN_TARJETA = ("IDENTIDAD", "CUENTA", "ALIAS", "TELEFONO", "EMAIL", "IP",
                    "DISPOSITIVO", "EVIDENCIA", "UBICACION")

ATRIBUTOS_LEGIBLES = {
    "valor": u"Valor", "clasificacion": u"Clasificación NCMEC",
    "prioridad": u"Prioridad", "plataforma": u"Plataforma", "pais": u"País",
    "fecha_incidente": u"Fecha del hecho", "fecha_recepcion": u"Fecha de recepción",
    "estado_sipar": u"Estado en SIPAR", "motivo_archivo": u"Motivo del archivo",
    "fecha_estado": u"Fecha del estado", "operador": u"Operador asignado",
    "esp": u"Plataforma", "esp_user_id": u"Identificador de usuario",
    "area": u"Código de área", "subtipo": u"Subtipo", "servicio": u"Servicio",
    "ciudad": u"Ciudad", "region": u"Región", "cp": u"Código postal",
    "lat": u"Latitud", "lon": u"Longitud", "forma_original": u"Forma original",
    "cgnat": u"Bajo CGNAT", "privada": u"Dirección privada",
    "atribuible_sin_dato_extra": u"Atribuible sin datos adicionales",
    "version": u"Versión IP", "cuenta_suspendida": u"Cuenta dada de baja",
    "genero": u"Género", "edad_aprox": u"Edad aproximada",
    "reporte": u"Reporte de origen", "nombre": u"Nombre del archivo",
    "tipo_mime": u"Tipo de archivo", "enviado_a_le": u"Remitido a autoridad",
    "prioridad_desc": u"Detalle de prioridad",
}

OCULTAR = {"tipo", "etiqueta", "identificador", "fusionable", "bio_hash",
           "decision", "transcripciones", "_variantes"}

# Escalones de la disposicion jerarquica: de la actuacion hacia el dato tecnico.
# Frase corta que explica por que dos reportes quedaron vinculados. Es lo que
# se escribe sobre el conector, como el "motivo vinculacion" del boceto.
MOTIVO_CORTO = {
    "CUENTA": u"misma cuenta",
    "DISPOSITIVO": u"mismo dispositivo",
    "TELEFONO": u"mismo teléfono",
    "EMAIL": u"mismo correo",
    "EVIDENCIA": u"mismo archivo",
    "IP": u"misma IP",
    "ALIAS": u"mismo nombre visible",
    "UBICACION": u"misma zona",
}

# Lo que se muestra al abrir un reporte: los datos por los que se vincula.
# Quedan afuera la mencion de persona y el chat, que son estructura interna del
# reporte y no son aquello que el operador esta buscando.
TIPOS_EN_TARJETA = ("IDENTIDAD", "CUENTA", "ALIAS", "TELEFONO", "EMAIL", "IP",
                    "DISPOSITIVO", "EVIDENCIA", "UBICACION")

NIVEL_JERARQUICO = {
    "REPORTE": 0,
    "EVENTO": 1, "PERSONA_MENCION": 1, "IDENTIDAD": 1,
    "CUENTA": 2,
    "ALIAS": 3, "EMAIL": 3, "TELEFONO": 3, "IP": 3, "DISPOSITIVO": 3,
    "EVIDENCIA": 3, "SEGMENTO": 3,
    "UBICACION": 4, "ORGANIZACION": 4, "DOCUMENTO": 4, "JURISDICCION": 4,
}


ATRIBUTOS_LEGIBLES = {
    "valor": u"Valor", "clasificacion": u"Clasificación NCMEC",
    "prioridad": u"Prioridad", "plataforma": u"Plataforma", "pais": u"País",
    "fecha_incidente": u"Fecha del hecho", "fecha_recepcion": u"Fecha de recepción",
    "estado_sipar": u"Estado en SIPAR", "motivo_archivo": u"Motivo del archivo",
    "fecha_estado": u"Fecha del estado", "operador": u"Operador asignado",
    "esp": u"Plataforma", "esp_user_id": u"Identificador de usuario",
    "area": u"Código de área", "subtipo": u"Subtipo", "servicio": u"Servicio",
    "ciudad": u"Ciudad", "region": u"Región", "cp": u"Código postal",
    "lat": u"Latitud", "lon": u"Longitud", "forma_original": u"Forma original",
    "cgnat": u"Bajo CGNAT", "privada": u"Dirección privada",
    "atribuible_sin_dato_extra": u"Atribuible sin datos adicionales",
    "version": u"Versión IP", "cuenta_suspendida": u"Cuenta dada de baja",
    "genero": u"Género", "edad_aprox": u"Edad aproximada",
    "reporte": u"Reporte de origen", "nombre": u"Nombre del archivo",
    "tipo_mime": u"Tipo de archivo", "enviado_a_le": u"Remitido a autoridad",
    "prioridad_desc": u"Detalle de prioridad",
}

OCULTAR = {"tipo", "etiqueta", "identificador", "fusionable", "bio_hash",
           "decision", "transcripciones", "_variantes"}

# Escalones de la disposicion jerarquica: de la actuacion hacia el dato tecnico.
# Frase corta que explica por que dos reportes quedaron vinculados. Es lo que
# se escribe sobre el conector, como el "motivo vinculacion" del boceto.
MOTIVO_CORTO = {
    "CUENTA": u"misma cuenta",
    "DISPOSITIVO": u"mismo dispositivo",
    "TELEFONO": u"mismo teléfono",
    "EMAIL": u"mismo correo",
    "EVIDENCIA": u"mismo archivo",
    "IP": u"misma IP",
    "ALIAS": u"mismo nombre visible",
    "UBICACION": u"misma zona",
}

# Lo que se muestra al abrir un reporte: los datos por los que se vincula.
# Quedan afuera la mencion de persona y el chat, que son estructura interna del
# reporte y no son aquello que el operador esta buscando.
TIPOS_EN_TARJETA = ("IDENTIDAD", "CUENTA", "ALIAS", "TELEFONO", "EMAIL", "IP",
                    "DISPOSITIVO", "EVIDENCIA", "UBICACION")

NIVEL_JERARQUICO = {
    "REPORTE": 0,
    "EVENTO": 1, "PERSONA_MENCION": 1, "IDENTIDAD": 1,
    "CUENTA": 2,
    "ALIAS": 3, "EMAIL": 3, "TELEFONO": 3, "IP": 3, "DISPOSITIVO": 3,
    "EVIDENCIA": 3, "SEGMENTO": 3,
    "UBICACION": 4, "ORGANIZACION": 4, "DOCUMENTO": 4, "JURISDICCION": 4,
}


def _layout(g):
    """Posiciones iniciales. La simulacion del navegador las refina."""
    H = nx.Graph()
    H.add_nodes_from(g.G.nodes())
    for u, v, k, d in g.aristas():
        H.add_edge(u, v, weight=2.0 if d["origin"] == ont.OBSERVADA else 1.0)
    if H.number_of_nodes() == 0:
        return {}
    pos = nx.spring_layout(H, seed=17, k=1.5 / max(1, H.number_of_nodes() ** 0.4),
                           iterations=300, weight="weight")
    xs = [p[0] for p in pos.values()] or [0]
    ys = [p[1] for p in pos.values()] or [0]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    dx = (maxx - minx) or 1.0
    dy = (maxy - miny) or 1.0
    m = 90
    return {n: ((p[0] - minx) / dx * (ANCHO - 2 * m) + m,
                (p[1] - miny) / dy * (ALTO - 2 * m) + m)
            for n, p in pos.items()}


PREFERENCIA_CAMINO = {"PERSONA_MENCION": 0, "IDENTIDAD": 0, "CUENTA": 1,
                      "EVENTO": 3, "ORGANIZACION": 4}


def _camino(g, n_rep, n_destino):
    """Cadena de nodos que va del reporte al dato compartido, dentro de ese reporte.

    Es lo que responde "como llegaron ahi": el reporte no toca la cuenta
    directamente, la toca a traves de la persona mencionada. Sin mostrar ese
    tramo, el vinculo aparece como un salto sin explicacion.
    """
    sid = "ncmec:%s" % g.G.nodes[n_rep]["valor"]
    vecinos = {}
    for u, v, k, d in g.aristas():
        if d.get("source_evidence_id") != sid:
            continue
        vecinos.setdefault(u, set()).add(v)
        vecinos.setdefault(v, set()).add(u)
    if n_rep not in vecinos or n_destino not in vecinos:
        return []

    def _preferencia(n):
        return (PREFERENCIA_CAMINO.get(g.G.nodes[n].get("tipo"), 2), n)

    previo, cola, vistos = {n_rep: None}, [n_rep], {n_rep}
    while cola:
        actual = cola.pop(0)
        if actual == n_destino:
            camino = []
            while actual is not None:
                camino.append(actual)
                actual = previo[actual]
            return list(reversed(camino))
        # A igual longitud hay varios caminos posibles: por la persona
        # mencionada o por el chat. Se prefiere la persona, que es la entidad
        # que el operador esta buscando; "el reporte, a traves de esta persona,
        # opera con esta cuenta" se lee solo.
        for sig in sorted(vecinos.get(actual, ()), key=_preferencia):
            if sig not in vistos:
                vistos.add(sig)
                previo[sig] = actual
                cola.append(sig)
    return []


def _reportes_por_nodo(g):
    """Que reportes menciona cada entidad.

    Es lo que permite recortar el grafo a un caso: una entidad pertenece al caso
    si alguno de los reportes del caso la menciona.
    """
    from collections import defaultdict
    mapa = defaultdict(set)
    for u, v, k, d in g.aristas(vigentes=False):
        sid = d.get("source_evidence_id") or ""
        if not sid.startswith("ncmec:"):
            continue
        rid = sid.split(":", 1)[1]
        mapa[u].add(rid)
        mapa[v].add(rid)
    for n, d in g.G.nodes(data=True):
        if d.get("tipo") == "REPORTE":
            mapa[n].add(d["valor"])
    # Una identidad unificada no proviene de un reporte sino de una decision
    # humana. Hereda los reportes de las menciones que agrupa, para que quede
    # dentro del caso cuando se la colapsa.
    for u, v, k, d in g.aristas(relacion="IDENTIFICADO_COMO", vigentes=False):
        mapa[v] |= mapa.get(u, set())
    return {n: sorted(v) for n, v in mapa.items()}


def _casos(g, res, legajo_de):
    """Un caso es un legajo: el reporte y todos aquellos con los que quedo
    vinculado. Un reporte sin vinculaciones es un caso de uno solo.

    El operador trabaja de a un caso. El visor nunca muestra dos a la vez.
    """
    casos, vistos = [], set()
    for l in res.get("legajos", []):
        reportes = sorted(l["reportes"])
        casos.append(dict(
            id=l["legajo"],
            etiqueta=u"Legajo %s · %d reportes" % (l["legajo"], len(reportes)),
            reportes=reportes,
            vinculos=l["vinculos"],
            confianza_max=l["confianza_max"]))
        vistos.update(reportes)
    sueltos = sorted(g.G.nodes[n]["valor"] for n in g.nodos_tipo("REPORTE")
                     if g.G.nodes[n]["valor"] not in vistos)
    for rid in sueltos:
        casos.append(dict(id=u"R" + rid, etiqueta=u"Reporte %s · sin vinculaciones" % rid,
                          reportes=[rid], vinculos=0, confianza_max=None))
    casos.sort(key=lambda c: (-len(c["reportes"]), c["reportes"][0]))
    return casos


def _tipo_crudo(x):
    return x.get("tipo")


def _datos(g, res, dossier=None, texto_informe=None):
    por_nodo = _reportes_por_nodo(g)

    # legajo al que pertenece cada reporte, para la disposicion agrupada
    legajo_de = {}
    for l in res.get("legajos", []):
        for n in l.get("nodos", []):
            legajo_de[n] = l["legajo"]

    nodos = []
    for n, d in g.G.nodes(data=True):
        atributos = []
        for k, v in d.items():
            if k in OCULTAR or v is None or v == "" or isinstance(v, (dict, list)):
                continue
            if isinstance(v, bool):
                v = u"sí" if v else u"no"
            atributos.append([ATRIBUTOS_LEGIBLES.get(k, k.replace("_", " ").capitalize()),
                              str(v)])
        nodos.append(dict(
            id=n, tipo=d.get("tipo"),
            tipoLegible=ont.ETIQUETA_TIPO.get(d.get("tipo"), d.get("tipo")),
            etiqueta=d.get("etiqueta") or d.get("valor"), valor=d.get("valor"),
            legajo=legajo_de.get(n),
            reportes=por_nodo.get(n, []),
            enTarjeta=(d.get("tipo") in TIPOS_EN_TARJETA),
            color=ont.TIPOS_NODO.get(d.get("tipo"), {}).get("color", "#8a94a6"),
            atributos=atributos,
            transcripciones=d.get("transcripciones") or [],
        ))

    aristas = []
    for u, v, k, d in g.aristas(vigentes=False):
        puente = []
        for x in (d.get("detalle_reglas") or []):
            n_dato = x.get("nodo")
            if not n_dato or n_dato not in g.G:
                continue
            puente.append(dict(
                nodo=n_dato,
                tipo=ont.ETIQUETA_TIPO.get(x.get("tipo"), x.get("tipo")),
                valor=x.get("valor"),
                peso=x.get("peso_efectivo"),
                sostiene=not x.get("corrobora_solamente"),
                texto=x.get("nota"),
                camino_a=_camino(g, u, n_dato),
                camino_b=_camino(g, v, n_dato)))
        puente.sort(key=lambda z: (not z["sostiene"], -(z["peso"] or 0)))
        motivo = u", ".join(
            MOTIVO_CORTO.get(_tipo_crudo(x), u"dato compartido")
            for x in (d.get("detalle_reglas") or [])
            if not x.get("corrobora_solamente")) or u"dato compartido"
        aristas.append(dict(
            puente=puente,
            motivo=motivo,
            id=d["arista_id"], a=u, b=v,
            relacion=d["relation_type"],
            relacionLegible=ont.ETIQUETA_RELACION.get(d["relation_type"],
                                                      d["relation_type"]),
            entreReportes=d["relation_type"] in ("COINCIDE_CON",
                                                 "POSIBLE_DUPLICADO_DE"),
            origen=d["origin"],
            origenLegible=ont.ETIQUETA_ORIGEN[d["origin"]],
            origenDesc=ont.DESCRIPCION_ORIGEN[d["origin"]],
            confianza=d.get("confidence"),
            estado=d.get("validation_status"),
            estadoLegible=ont.ETIQUETA_ESTADO.get(d.get("validation_status"),
                                                  d.get("validation_status")),
            vigente=d.get("vigente", True),
            metodo="%s v%s" % (d.get("method"), d.get("method_version")),
            locator=d.get("source_locator"), fuente=d.get("source_evidence_id"),
            observado=d.get("observed_at"), explicacion=d.get("explicacion"),
            validado_por=d.get("validated_by"), validado_en=d.get("validated_at"),
            rol=d.get("rol"), puerto=d.get("puerto"),
        ))

    # Menciones que un operador ya unifico bajo una misma identidad.
    identidades = {}
    for u, v, k, d in g.aristas(relacion="IDENTIFICADO_COMO", vigentes=False):
        identidades[u] = v

    salida = dict(
        nodos=nodos, aristas=aristas, identidades=identidades,
        tipos={t: dict(color=m["color"],
                       legible=ont.ETIQUETA_TIPO.get(t, t), desc=m["desc"],
                       # Las organizaciones -plataforma que reporta, prestador
                       # de internet- no aportan a la vinculacion: todos los
                       # reportes de Grindr comparten Grindr. Se informan en la
                       # ficha y no compiten por atencion en el lienzo.
                       informativo=(t == "ORGANIZACION"))
               for t, m in ont.TIPOS_NODO.items()},
        meta=dict(corrida=res.get("corrida"),
                  ontologia=res.get("ontologia_version"),
                  reportes=res.get("reportes_ingeridos")),
        alertas=res.get("alertas", {}).get("alertas", []),
        legajos=res.get("legajos", []),
        casos=_casos(g, res, legajo_de),
    )
    if dossier is not None:
        salida["informe"] = dict(
            texto=texto_informe or "",
            pesos=dossier.get("pesos", {}),
            vinculaciones=len(dossier.get("vinculaciones", [])),
        )
    return salida


PLANTILLA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vinculaciones — Bóveda CIJ</title>
<style>
:root{
  --fondo:#060a12; --lienzo:#080d17; --panel:#0b1220; --panel2:#0e1728;
  --borde:#1a2740; --texto:#dbe4f0; --tenue:#7d8ba3; --suave:#9fb0c9;
  --cyan:#22d3ee; --cyan-tenue:rgba(34,211,238,.10); --cyan-borde:rgba(34,211,238,.32);
  --verde:#34d399; --ambar:#fbbf24; --alarma:#f87171;
  --mono:"Cascadia Mono","JetBrains Mono",Consolas,"DejaVu Sans Mono",monospace;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--fondo);color:var(--texto);display:flex;
  font:13.5px/1.6 "Segoe UI",system-ui,-apple-system,sans-serif;overflow:hidden}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:#1c2942;border-radius:5px}
::-webkit-scrollbar-track{background:transparent}

#centro{flex:1;min-width:280px;position:relative;margin:10px 0 10px 10px;
  border:1px solid var(--borde);border-radius:14px;background:
    radial-gradient(1200px 700px at 30% 15%,rgba(34,211,238,.04),transparent 60%),
    var(--lienzo);overflow:hidden}
.asa{flex:0 0 7px;cursor:col-resize;position:relative}
.asa::after{content:"";position:absolute;top:50%;left:2px;width:3px;height:46px;
  margin-top:-23px;border-radius:3px;background:#1e2c46;transition:background .2s}
.asa:hover::after{background:var(--cyan)}
#der{flex:0 0 440px;background:var(--panel);border:1px solid var(--borde);
  border-radius:14px;margin:10px 10px 10px 0;overflow-y:auto;position:relative;
  transition:flex-basis .3s cubic-bezier(.4,0,.2,1)}
#der.plegado{flex-basis:44px}
#der.plegado .contenido{display:none}
.contenido{padding:16px 18px 26px 44px}
.plegar{position:absolute;top:10px;left:10px;width:26px;height:26px;padding:0;
  z-index:3;display:flex;align-items:center;justify-content:center;font-size:13px}

h1{font-size:15px;margin:0 0 2px;font-weight:600}
h2{font-size:10.5px;text-transform:uppercase;letter-spacing:.14em;color:var(--cyan);
  margin:20px 0 8px;font-weight:600;opacity:.85}
h3{font-size:14.5px;margin:8px 0 4px;font-weight:600;line-height:1.35}
p{margin:0 0 10px}
.sub{font-size:11.5px;color:var(--tenue);font-family:var(--mono)}

.tarjeta{background:var(--panel2);border:1px solid var(--borde);border-radius:10px;
  padding:11px 12px;margin:8px 0}
.tarjeta.cyan{border-color:var(--cyan-borde);background:linear-gradient(180deg,
  rgba(34,211,238,.05),rgba(34,211,238,.01))}
.tarjeta.alarma{border-color:rgba(248,113,113,.35);background:rgba(248,113,113,.05)}
.tarjeta.click{cursor:pointer;transition:border-color .18s,transform .18s}
.tarjeta.click:hover{border-color:var(--cyan-borde);transform:translateX(2px)}

.chip{display:inline-flex;align-items:center;gap:5px;padding:2.5px 9px;border-radius:999px;
  font-size:10.5px;font-family:var(--mono);border:1px solid var(--borde);
  background:#0d1626;color:var(--suave);margin:0 5px 5px 0;white-space:nowrap}
.chip.cy{border-color:var(--cyan-borde);background:var(--cyan-tenue);color:#67e8f9}
.chip.ok{border-color:rgba(52,211,153,.35);background:rgba(52,211,153,.08);color:#6ee7b7}
.chip.am{border-color:rgba(251,191,36,.35);background:rgba(251,191,36,.08);color:#fcd34d}
.chip.al{border-color:rgba(248,113,113,.4);background:rgba(248,113,113,.08);color:#fca5a5}
.chip .pt{width:6px;height:6px;border-radius:50%;background:currentColor}
.chip.boton{cursor:pointer;max-width:100%}
.chip.boton:hover{border-color:var(--cyan-borde);color:#67e8f9}

button{font:inherit;font-size:12px;padding:7px 12px;border:1px solid var(--borde);
  background:#0d1626;color:var(--suave);border-radius:8px;cursor:pointer;
  transition:border-color .18s,color .18s,background .18s;white-space:nowrap}
button:hover:not(:disabled){border-color:var(--cyan-borde);color:#67e8f9;background:var(--cyan-tenue)}
button.primario{border-color:var(--cyan-borde);background:rgba(34,211,238,.14);color:#a5f3fc;font-weight:600}
button:disabled{opacity:.35;cursor:default}
select{border:1px solid var(--borde);border-radius:9px;color:#a5f3fc;
  background:rgba(8,13,23,.94);padding:7px 11px;font:inherit;font-size:12px;
  cursor:pointer;outline:none;max-width:260px}
select:hover{border-color:var(--cyan-borde)}
input[type=text]{width:100%;padding:8px 11px;border:1px solid var(--borde);
  border-radius:8px;font:inherit;font-size:12.5px;background:#0a1120;
  color:var(--texto);outline:none}
input[type=text]:focus{border-color:var(--cyan-borde)}
.fila{display:flex;gap:8px;align-items:center;margin:9px 0;flex-wrap:wrap}

#barra{position:absolute;top:12px;left:14px;right:14px;display:flex;gap:8px;
  align-items:center;flex-wrap:wrap;z-index:5;pointer-events:none}
#barra>*{pointer-events:auto}
.grupo{display:flex;background:rgba(8,13,23,.94);border:1px solid var(--borde);
  border-radius:9px;overflow:hidden}
.grupo button{border:0;border-radius:0;background:transparent;padding:7px 13px}
.grupo button+button{border-left:1px solid var(--borde)}
.solo{background:rgba(8,13,23,.94)}
#ruta{margin-left:auto;font-size:11px;color:var(--tenue);font-family:var(--mono);
  background:rgba(8,13,23,.94);border-radius:8px;padding:6px 11px;
  max-width:44%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

svg{width:100%;height:100%;display:block;cursor:grab}
svg.arrastrando{cursor:grabbing}

/* --- cajas ------------------------------------------------------------- */
.caja{cursor:pointer}
.caja rect.cuerpo{fill:#0e1728;stroke:#2b3a55;stroke-width:1.4;rx:7;
  transition:stroke .18s,fill .18s}
.caja:hover rect.cuerpo{stroke:var(--cyan)}
.caja.sel rect.cuerpo{stroke:#fff;stroke-width:2}
.caja.raiz rect.cuerpo{fill:#10243a;stroke:var(--cyan);stroke-width:1.8}
.caja .barra{rx:2}
.caja .titulo{fill:#e6eefb;font-size:12.5px;font-family:var(--mono);
  dominant-baseline:middle;pointer-events:none}
.caja .sub{fill:#7d8ba3;font-size:10px;dominant-baseline:middle;pointer-events:none}
.caja .marca{fill:var(--ambar);font-size:9.5px;font-family:var(--mono);
  text-anchor:end;dominant-baseline:middle;pointer-events:none}

.mas{cursor:pointer}
.mas circle{fill:#0d1626;stroke:var(--ambar);stroke-width:1.4;transition:fill .18s}
.mas:hover circle{fill:rgba(251,191,36,.25)}
.mas path{stroke:var(--ambar);stroke-width:1.6;stroke-linecap:round}

/* --- conectores -------------------------------------------------------- */
.con{fill:none;stroke:#3d5070;stroke-width:1.6;transition:stroke .18s,stroke-width .18s}
.con.vinculo{stroke:#22d3ee;stroke-width:2}
.con.duplicado{stroke:var(--ambar);stroke-width:2;stroke-dasharray:9 4}
.con.cruce{stroke-width:1.5;stroke-dasharray:5 4}
.con.sel{stroke:#fff;stroke-width:3}
.zona{stroke:transparent;stroke-width:16;fill:none;cursor:pointer}
.rotulo{font-size:10px;font-family:var(--mono);fill:#8fa1bb;text-anchor:middle;
  pointer-events:none;paint-order:stroke;stroke:#080d17;stroke-width:4;
  stroke-linejoin:round}
.rotulo.vinculo{fill:#67e8f9}
.rotulo.peso{fill:#6ee7b7}

table{width:100%;border-collapse:collapse;font-size:12px}
td{padding:5px 2px;vertical-align:top;border-bottom:1px solid rgba(26,39,64,.7)}
td:first-child{color:var(--tenue);width:44%;padding-right:10px}
td.mono{font-family:var(--mono);font-size:11.5px;word-break:break-all}
.prosa{font-size:13px;line-height:1.7;color:#c8d4e4}
.prosa p{margin:0 0 11px}
.prosa h1{font-size:16px;margin:16px 0 8px}
.prosa h2{color:var(--cyan);font-size:11px;margin:18px 0 8px}
.prosa h3{font-size:13.5px;margin:14px 0 6px;color:#e2e8f0}
.prosa li{margin:0 0 5px}
.cadena{font-family:var(--mono);font-size:11.5px;color:var(--suave);line-height:2}
.cadena .fl{color:var(--tenue);padding:0 3px}
.cita{font-family:var(--mono);font-size:11px;color:var(--tenue);word-break:break-all;
  background:#0a1120;border:1px solid var(--borde);border-radius:8px;padding:9px 11px}
.vacio{color:var(--tenue);font-size:12.5px;font-style:italic}
#pie{position:absolute;left:14px;bottom:12px;font-size:11px;color:var(--tenue);
  font-family:var(--mono);pointer-events:none;background:rgba(6,10,18,.85);
  border-radius:8px;padding:6px 10px}
</style></head><body>

<main id="centro">
  <div id="barra">
    <div class="grupo">
      <button id="atras" title="Volver (Alt + ←)">‹ Volver</button>
      <button id="adelante" title="Siguiente (Alt + →)">Siguiente ›</button>
    </div>
    <select id="selCaso" title="Caso en curso"></select>
    <button class="solo" id="contraer">Contraer</button>
    <button class="solo" id="ajustar" title="Encuadrar">Encuadrar</button>
    <button class="solo primario" id="btnInforme">Informe</button>
    <div id="ruta"></div>
  </div>
  <svg id="lienzo">
    <defs>
      <marker id="flecha" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7"
              markerHeight="7" orient="auto-start-reverse">
        <path d="M0,0 L8,4 L0,8 z" fill="#3d5070"/>
      </marker>
      <marker id="flechaCyan" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7"
              markerHeight="7" orient="auto-start-reverse">
        <path d="M0,0 L8,4 L0,8 z" fill="#22d3ee"/>
      </marker>
    </defs>
    <g id="vista">
      <g id="gcon"></g><g id="grot"></g><g id="gcajas"></g>
    </g>
  </svg>
  <div id="pie"></div>
</main>

<div class="asa" id="asa"></div>

<aside id="der">
  <button class="plegar" id="plegDer" title="Plegar la ficha">›</button>
  <div class="contenido" id="cuerpo"></div>
</aside>

<script>
const D = __DATOS__;
const NODOS = new Map(D.nodos.map(n=>[n.id,n]));
const ARISTAS = new Map(D.aristas.map(a=>[a.id,a]));
const CASOS = D.casos || [];
const VINCULOS = D.aristas.filter(a=>a.entreReportes);
const UNIF = new Map(Object.entries(D.identidades||{}));
const RE = id => UNIF.get(id) || id;

const esc = s => String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const num = v => (v==null? "—" : v.toFixed(2).replace(".",","));
const etq = id => (NODOS.get(id)||{}).etiqueta || id;
const LEGIBLE = {
  en_analisis:"en análisis", en_investigacion:"en investigación",
  archivado:"archivado", archivado_latente:"archivado de forma latente",
  judicializado:"judicializado", derivado:"derivado", pendiente:"pendiente",
  sin_datos_de_usuario:"archivado por falta de datos de usuario",
  no_atribuible_nat:"archivado por IP no atribuible bajo NAT",
  sin_archivos:"archivado por ausencia de archivos",
  sin_ubicacion:"archivado sin datos de ubicación",
  material_sin_relevancia:"archivado por material sin relevancia"};
const legible = v => v ? (LEGIBLE[v] || String(v).replace(/_/g," ")) : v;
const attr = n => Object.fromEntries((n.atributos||[]));

const estado = {caso:null, raiz:null, abiertos:new Set(), sel:null};

/* =============================================================== caso ===== */
function caso(){ return CASOS.find(c=>c.id===estado.caso) || CASOS[0]; }
function reportesCaso(){ return new Set(caso() ? caso().reportes : []); }
function nodoReporte(valor){ return NODOS.get("REPORTE::"+String(valor).toLowerCase()); }
function vinculosDe(idReporte){
  return VINCULOS.filter(a=>a.a===idReporte||a.b===idReporte)
    .filter(a=>{ const rs=reportesCaso();
      return rs.has((NODOS.get(a.a)||{}).valor) && rs.has((NODOS.get(a.b)||{}).valor); });
}
/* Datos por los que un reporte puede vincularse. Se dejan afuera la mención de
   persona y el chat: son estructura interna del reporte, no aquello que el
   operador está buscando. */
function datosDe(valorReporte){
  return D.nodos.filter(n => n.enTarjeta
                          && (n.reportes||[]).includes(valorReporte)
                          && RE(n.id) === n.id);
}
function otrosReportesDe(nodo){
  const rs = reportesCaso();
  return (nodo.reportes||[]).filter(r=>rs.has(r));
}

/* ========================================================== navegación ==== */
const HIST = {pila:[], pos:-1};
function ir(v){
  const act = HIST.pila[HIST.pos];
  if(!(act && act.tipo===v.tipo && act.id===v.id)){
    HIST.pila = HIST.pila.slice(0,HIST.pos+1); HIST.pila.push(v); HIST.pos++;
  }
  mostrar(v);
}
function atras(){ if(HIST.pos>0){ HIST.pos--; mostrar(HIST.pila[HIST.pos]); } }
function adelante(){ if(HIST.pos<HIST.pila.length-1){ HIST.pos++; mostrar(HIST.pila[HIST.pos]); } }
function mostrar(v){
  estado.sel = v;
  if(v.tipo==="reporte"){ fichaReporte(v.id); }
  else if(v.tipo==="entidad"){ fichaEntidad(v.id); }
  else if(v.tipo==="vinculo"){ fichaVinculo(v.id); }
  else if(v.tipo==="relacion"){ fichaRelacion(v.id); }
  else if(v.tipo==="informe"){ fichaInforme(); }
  else fichaCaso();
  document.getElementById("atras").disabled = HIST.pos<=0;
  document.getElementById("adelante").disabled = HIST.pos>=HIST.pila.length-1;
  const nombre = v.tipo==="inicio" ? "Caso"
    : v.tipo==="informe" ? "Informe"
    : v.tipo==="vinculo" ? "Vinculación"
    : v.tipo==="relacion" ? "Relación" : etq(v.id);
  document.getElementById("ruta").textContent = (HIST.pos>0?"◂ ":"")+nombre;
  dibujar();
}
window.addEventListener("keydown",e=>{
  if(e.altKey && e.key==="ArrowLeft"){ e.preventDefault(); atras(); }
  if(e.altKey && e.key==="ArrowRight"){ e.preventDefault(); adelante(); }
});
document.getElementById("atras").onclick = atras;
document.getElementById("adelante").onclick = adelante;

/* ============================================================== lienzo ==== */
const SVGNS = "http://www.w3.org/2000/svg";
const gCon = document.getElementById("gcon"), gRot = document.getElementById("grot"),
      gCaj = document.getElementById("gcajas"), svg = document.getElementById("lienzo");
const ANCHO_CAJA = 200, ALTO_CAJA = 52, SEP_X = 34;
const Y_RAIZ = 90, Y_REL = 280, Y_ENT = 480;
const PALETA = ["#34d399","#a78bfa","#f472b6","#fbbf24","#38bdf8","#fb7185",
                "#4ade80","#c084fc"];

let VP = {x:0,y:0,k:1};
function pintarVP(){ document.getElementById("vista")
  .setAttribute("transform","translate("+VP.x+","+VP.y+") scale("+VP.k+")"); }

function caja(g, x, y, {titulo, sub, marca, color, clases, alClic}){
  const el = document.createElementNS(SVGNS,"g");
  el.setAttribute("class","caja "+(clases||""));
  el.setAttribute("transform","translate("+x+","+y+")");
  const r = document.createElementNS(SVGNS,"rect");
  r.setAttribute("class","cuerpo"); r.setAttribute("width",ANCHO_CAJA);
  r.setAttribute("height",ALTO_CAJA); r.setAttribute("rx",7);
  el.appendChild(r);
  if(color){
    const b = document.createElementNS(SVGNS,"rect");
    b.setAttribute("class","barra"); b.setAttribute("x",0); b.setAttribute("y",0);
    b.setAttribute("width",4); b.setAttribute("height",ALTO_CAJA);
    b.setAttribute("fill",color); el.appendChild(b);
  }
  const t = document.createElementNS(SVGNS,"text");
  t.setAttribute("class","titulo"); t.setAttribute("x",13);
  t.setAttribute("y", sub? ALTO_CAJA/2-8 : ALTO_CAJA/2);
  t.textContent = String(titulo).slice(0,24); el.appendChild(t);
  if(sub){
    const s2 = document.createElementNS(SVGNS,"text");
    s2.setAttribute("class","sub"); s2.setAttribute("x",13);
    s2.setAttribute("y",ALTO_CAJA/2+10);
    s2.textContent = String(sub).slice(0,32); el.appendChild(s2);
  }
  if(marca){
    const m = document.createElementNS(SVGNS,"text");
    m.setAttribute("class","marca"); m.setAttribute("x",ANCHO_CAJA-12);
    m.setAttribute("y",13); m.textContent = marca; el.appendChild(m);
  }
  const ti = document.createElementNS(SVGNS,"title");
  ti.textContent = titulo + (sub? "  ·  "+sub : ""); el.appendChild(ti);
  if(alClic) el.addEventListener("click", e=>{ e.stopPropagation(); alClic(); });
  g.appendChild(el);
  return el;
}
function botonMas(g, x, y, abierto, alClic, ayuda){
  const el = document.createElementNS(SVGNS,"g");
  el.setAttribute("class","mas");
  el.setAttribute("transform","translate("+x+","+y+")");
  const c = document.createElementNS(SVGNS,"circle");
  c.setAttribute("r",9); el.appendChild(c);
  const p = document.createElementNS(SVGNS,"path");
  p.setAttribute("d", abierto ? "M-4.5,0 H4.5" : "M-4.5,0 H4.5 M0,-4.5 V4.5");
  p.setAttribute("fill","none"); el.appendChild(p);
  const ti = document.createElementNS(SVGNS,"title");
  ti.textContent = ayuda; el.appendChild(ti);
  el.addEventListener("click", e=>{ e.stopPropagation(); alClic(); });
  g.appendChild(el);
}
/* Conector en ángulo recto: baja del origen, corre horizontal y entra al
   destino por arriba. Es la forma en que se lee un árbol. */
function conector(desde, hasta, {clase, rotulo, peso, alClic, color, carril}){
  const x1 = desde.x, y1 = desde.y, x2 = hasta.x, y2 = hasta.y;
  const ym = carril!=null ? carril : (y1 + (y2-y1)/2);
  const d = "M"+x1+","+y1+" V"+ym+" H"+x2+" V"+y2;
  const p = document.createElementNS(SVGNS,"path");
  p.setAttribute("class","con "+(clase||""));
  p.setAttribute("d",d);
  if(color) p.setAttribute("stroke",color);
  p.setAttribute("marker-end", clase==="vinculo" ? "url(#flechaCyan)" : "url(#flecha)");
  gCon.appendChild(p);
  if(alClic){
    const z = document.createElementNS(SVGNS,"path");
    z.setAttribute("class","zona"); z.setAttribute("d",d);
    z.addEventListener("click", e=>{ e.stopPropagation(); alClic(); });
    const ti = document.createElementNS(SVGNS,"title");
    ti.textContent = rotulo||""; z.appendChild(ti);
    gCon.appendChild(z);
  }
  if(rotulo){
    const t = document.createElementNS(SVGNS,"text");
    t.setAttribute("class","rotulo "+(clase==="vinculo"?"vinculo":""));
    t.setAttribute("x",(x1+x2)/2); t.setAttribute("y",ym-7);
    t.textContent = rotulo; gRot.appendChild(t);
    if(peso!=null){
      const w = document.createElementNS(SVGNS,"text");
      w.setAttribute("class","rotulo peso");
      w.setAttribute("x",(x1+x2)/2); w.setAttribute("y",ym+13);
      w.textContent = "peso "+num(peso); gRot.appendChild(w);
    }
  }
  return p;
}

function dibujar(){
  gCon.textContent = ""; gRot.textContent = ""; gCaj.textContent = "";
  const c = caso(); if(!c) return;
  const raizVal = estado.raiz || c.reportes[0];
  const nRaiz = nodoReporte(raizVal); if(!nRaiz) return;

  // --- fila 1: los reportes con los que se vincula el que está en análisis
  const vinc = vinculosDe(nRaiz.id).sort((a,b)=>(b.confianza||0)-(a.confianza||0));
  const relacionados = vinc.map(a=>{
    const otro = a.a===nRaiz.id ? a.b : a.a;
    return {arista:a, nodo:NODOS.get(otro)};
  });

  // --- fila 2: los datos de los reportes abiertos
  const abiertos = relacionados.filter(r=>estado.abiertos.has(r.nodo.id));
  if(estado.abiertos.has(nRaiz.id)) abiertos.unshift({nodo:nRaiz, arista:null});
  const entidades = [];
  const yaEnt = new Set();
  abiertos.forEach(r=>{
    datosDe(r.nodo.valor).forEach(m=>{
      if(yaEnt.has(m.id)) return;
      yaEnt.add(m.id); entidades.push({nodo:m, padre:r.nodo});
    });
  });

  // --- posiciones
  const anchoFila = arr => arr.length*ANCHO_CAJA + Math.max(0,arr.length-1)*SEP_X;
  const anchoTotal = Math.max(anchoFila(relacionados), anchoFila(entidades), ANCHO_CAJA);
  const x0 = 60;
  const pos = new Map();
  pos.set(nRaiz.id, {x: x0 + anchoTotal/2 - ANCHO_CAJA/2, y: Y_RAIZ});
  const xRel = x0 + (anchoTotal - anchoFila(relacionados))/2;
  relacionados.forEach((r,i)=>pos.set(r.nodo.id,
    {x: xRel + i*(ANCHO_CAJA+SEP_X), y: Y_REL}));
  const xEnt = x0 + (anchoTotal - anchoFila(entidades))/2;
  entidades.forEach((e,i)=>pos.set(e.nodo.id,
    {x: xEnt + i*(ANCHO_CAJA+SEP_X), y: Y_ENT}));

  const abajo = p => ({x:p.x+ANCHO_CAJA/2, y:p.y+ALTO_CAJA});
  const arriba = p => ({x:p.x+ANCHO_CAJA/2, y:p.y});

  // --- conectores: reporte en análisis -> relacionados
  relacionados.forEach(r=>{
    const a = r.arista;
    conector(abajo(pos.get(nRaiz.id)), arriba(pos.get(r.nodo.id)), {
      clase: a.relacion==="POSIBLE_DUPLICADO_DE" ? "vinculo duplicado" : "vinculo",
      rotulo: a.motivo, peso: a.confianza,
      alClic: ()=>ir({tipo:"vinculo", id:a.id})});
  });

  // --- conectores: reporte abierto -> sus datos
  entidades.forEach(e=>{
    conector(abajo(pos.get(e.padre.id)), arriba(pos.get(e.nodo.id)), {
      rotulo: null, alClic: ()=>ir({tipo:"entidad", id:e.nodo.id})});
  });

  // --- cruces: el mismo dato en otros reportes de la fila
  let carril = Y_ENT + ALTO_CAJA + 40;
  entidades.forEach((e,i)=>{
    const color = PALETA[i % PALETA.length];
    otrosReportesDe(e.nodo).forEach(rv=>{
      const nr = nodoReporte(rv);
      if(!nr || nr.id===e.padre.id || !pos.has(nr.id)) return;
      conector(abajo(pos.get(e.nodo.id)), abajo(pos.get(nr.id)),
        {clase:"cruce", color, carril, alClic: ()=>ir({tipo:"entidad", id:e.nodo.id})});
      carril += 13;
    });
  });

  // --- cajas
  const at = attr(nRaiz);
  caja(gCaj, pos.get(nRaiz.id).x, pos.get(nRaiz.id).y, {
    titulo:"Reporte "+nRaiz.valor,
    sub: at["Plataforma"] ? at["Plataforma"]+" · en análisis" : "en análisis",
    clases:"raiz"+(estado.sel && estado.sel.id===nRaiz.id?" sel":""),
    alClic:()=>ir({tipo:"reporte", id:nRaiz.id})});
  const dRaiz = datosDe(nRaiz.valor).length;
  if(dRaiz) botonMas(gCaj, pos.get(nRaiz.id).x+ANCHO_CAJA-16,
    pos.get(nRaiz.id).y+ALTO_CAJA-14, estado.abiertos.has(nRaiz.id),
    ()=>{ alternar(nRaiz.id); },
    (estado.abiertos.has(nRaiz.id)?"Cerrar":"Abrir")+" los "+dRaiz+" datos de este reporte");

  relacionados.forEach(r=>{
    const p = pos.get(r.nodo.id), a2 = attr(r.nodo);
    const est = a2["Motivo del archivo"] ? legible(a2["Motivo del archivo"])
                                         : legible(a2["Estado en SIPAR"]);
    caja(gCaj, p.x, p.y, {
      titulo:"Reporte "+r.nodo.valor, sub:est,
      clases: (estado.sel && estado.sel.id===r.nodo.id?"sel":""),
      alClic:()=>ir({tipo:"reporte", id:r.nodo.id})});
    const n = datosDe(r.nodo.valor).length;
    if(n) botonMas(gCaj, p.x+ANCHO_CAJA-16, p.y+ALTO_CAJA-14,
      estado.abiertos.has(r.nodo.id), ()=>alternar(r.nodo.id),
      (estado.abiertos.has(r.nodo.id)?"Cerrar":"Abrir")+" los "+n+" datos de este reporte");
  });

  entidades.forEach((e,i)=>{
    const p = pos.get(e.nodo.id);
    const enN = otrosReportesDe(e.nodo).length;
    caja(gCaj, p.x, p.y, {
      titulo:e.nodo.etiqueta, sub:e.nodo.tipoLegible,
      marca: enN>1 ? "en "+enN+" reportes" : null,
      color: PALETA[i % PALETA.length],
      clases: (estado.sel && estado.sel.id===e.nodo.id?"sel":""),
      alClic:()=>ir({tipo:"entidad", id:e.nodo.id})});
  });

  document.getElementById("pie").textContent =
    relacionados.length+" reporte(s) vinculado(s) · "+entidades.length+" dato(s) a la vista";
  document.getElementById("contraer").disabled = estado.abiertos.size===0;
  if(!VP.encuadrado){ encuadrar(); VP.encuadrado = true; }
}
function alternar(id){
  if(estado.abiertos.has(id)) estado.abiertos.delete(id); else estado.abiertos.add(id);
  dibujar();
}
function encuadrar(){
  const b = document.getElementById("vista").getBBox();
  const r = svg.getBoundingClientRect();
  if(!b.width || !r.width) return;
  const k = Math.min((r.width-60)/b.width, (r.height-120)/b.height, 1.3);
  VP.k = k;
  VP.x = (r.width - b.width*k)/2 - b.x*k;
  VP.y = 70 - b.y*k;
  pintarVP();
}
document.getElementById("ajustar").onclick = ()=>{ encuadrar(); };
document.getElementById("contraer").onclick = ()=>{ estado.abiertos.clear(); dibujar(); };

svg.addEventListener("wheel",e=>{
  e.preventDefault();
  const r = svg.getBoundingClientRect();
  const sx = e.clientX-r.left, sy = e.clientY-r.top;
  const f = e.deltaY<0 ? 1.12 : 1/1.12, k2 = Math.max(0.2,Math.min(3,VP.k*f));
  VP.x = sx-(sx-VP.x)*(k2/VP.k); VP.y = sy-(sy-VP.y)*(k2/VP.k); VP.k = k2; pintarVP();
},{passive:false});
let arr = null;
svg.addEventListener("pointerdown",e=>{
  arr = {x:e.clientX,y:e.clientY,vx:VP.x,vy:VP.y}; svg.classList.add("arrastrando"); });
window.addEventListener("pointermove",e=>{
  if(!arr) return; VP.x = arr.vx+(e.clientX-arr.x); VP.y = arr.vy+(e.clientY-arr.y); pintarVP(); });
window.addEventListener("pointerup",()=>{ arr = null; svg.classList.remove("arrastrando"); });

/* =============================================================== ficha ==== */
document.getElementById("cuerpo").addEventListener("click", e=>{
  const nav = e.target.closest("[data-ir]");
  if(nav){ const [tipo,id] = nav.dataset.ir.split("|"); ir(id?{tipo,id}:{tipo}); return; }
  const acc = e.target.closest("[data-accion]");
  if(!acc) return;
  if(acc.dataset.accion==="descargar") descargarInforme();
  if(acc.dataset.accion==="raiz"){
    estado.raiz = acc.dataset.valor; estado.abiertos.clear();
    VP.encuadrado = false; ir({tipo:"inicio"});
  }
  if(acc.dataset.accion==="abrir"){ estado.abiertos.add(acc.dataset.valor); dibujar(); }
});
function ficha(html){
  document.getElementById("cuerpo").innerHTML = html;
  document.getElementById("der").classList.remove("plegado");
  document.getElementById("der").scrollTop = 0;
}
function tabla(pares){
  const f = pares.filter(x=>x[1]!==""&&x[1]!=null);
  if(!f.length) return "";
  return "<table>"+f.map(([k,v])=>"<tr><td>"+esc(k)+"</td><td class='mono'>"+
    esc(v)+"</td></tr>").join("")+"</table>";
}
function prosa(t){
  return '<div class="prosa">'+String(t||"").split(/\n\s*\n/)
    .map(p=>"<p>"+esc(p).replace(/\n/g,"<br>")+"</p>").join("")+"</div>";
}
function chipPeso(c){
  if(c==null) return "";
  const cl = c>=0.9?"ok":c>=0.7?"cy":"am", t = c>=0.9?"alto":c>=0.7?"medio":"bajo";
  return '<span class="chip '+cl+'"><span class="pt"></span>peso '+num(c)+' · '+t+'</span>';
}
function cadena(ids, destacado){
  return '<div class="cadena">'+ids.map(id=>{
    const t = esc(etq(id));
    return id===destacado ? "<b style='color:#67e8f9'>"+t+"</b>"
      : '<span class="chip boton" data-ir="entidad|'+id+'">'+t+'</span>';
  }).join('<span class="fl">→</span>')+'</div>';
}

function fichaCaso(){
  const c = caso(); if(!c){ ficha('<div class="vacio">Sin casos.</div>'); return; }
  const raizVal = estado.raiz || c.reportes[0];
  const nRaiz = nodoReporte(raizVal);
  const vinc = vinculosDe(nRaiz.id).sort((a,b)=>(b.confianza||0)-(a.confianza||0));
  let h = '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.14em;'+
    'color:var(--cyan)">Reporte en análisis</div><h1>Reporte '+esc(raizVal)+'</h1>'+
    '<div class="prosa"><p>'+
    (vinc.length
      ? 'Tiene <b>'+vinc.length+'</b> vinculación(es) con otros reportes del archivo. '+
        'Es lo que habilita evaluar una reapertura.'
      : 'No quedó vinculado con ningún otro reporte.')+
    '</p></div>';
  if(vinc.length){
    h += '<h2>Se vincula con</h2>';
    vinc.forEach(a=>{
      const otro = a.a===nRaiz.id?a.b:a.a, m = NODOS.get(otro), at = attr(m);
      h += '<div class="tarjeta click" data-ir="vinculo|'+a.id+'">'+
        chipPeso(a.confianza)+
        (a.relacion==="POSIBLE_DUPLICADO_DE"?'<span class="chip am">posible duplicado</span>':'')+
        '<div style="margin-top:4px;font-size:12.5px"><b>Reporte '+esc(m.valor)+'</b></div>'+
        '<div style="color:var(--cyan);font-size:12px;margin-top:2px">'+esc(a.motivo)+'</div>'+
        '<div style="color:var(--tenue);font-size:11.5px;margin-top:2px">'+
        esc(legible(at["Motivo del archivo"]) || legible(at["Estado en SIPAR"]) || "")+
        '</div></div>';
    });
  }
  h += '<h2>Otros reportes del caso</h2>';
  c.reportes.forEach(r=>{
    if(r===raizVal) return;
    h += '<span class="chip boton" data-accion="raiz" data-valor="'+r+'">analizar '+esc(r)+'</span>';
  });
  ficha(h);
}

function fichaReporte(id){
  const n = NODOS.get(id); if(!n){ fichaCaso(); return; }
  const at = attr(n);
  const vinc = vinculosDe(id).sort((a,b)=>(b.confianza||0)-(a.confianza||0));
  const datos = datosDe(n.valor);
  const esRaiz = (estado.raiz || caso().reportes[0]) === n.valor;
  let h = '<span class="chip cy">Reporte</span>'+
    (esRaiz?'<span class="chip">en análisis</span>':'')+
    '<h3>Reporte '+esc(n.valor)+'</h3>';

  h += '<h2>Resumen</h2>'+prosa(
    'Reporte de '+(at["Plataforma"]||"plataforma no informada")+
    ', clasificado como '+(at["Clasificación NCMEC"]||"sin clasificar")+
    '. El hecho es del '+String(at["Fecha del hecho"]||"—").slice(0,10)+
    ' y se recibió el '+String(at["Fecha de recepción"]||"—").slice(0,10)+'.'+
    ' Actualmente '+(legible(at["Motivo del archivo"]) || legible(at["Estado en SIPAR"]) || "sin estado")+'.');

  if(vinc.length){
    h += '<h2>Se vincula con ('+vinc.length+')</h2>';
    vinc.forEach(a=>{
      const otro = a.a===id?a.b:a.a;
      h += '<div class="tarjeta click" data-ir="vinculo|'+a.id+'">'+chipPeso(a.confianza)+
        '<div style="margin-top:4px;font-size:12.5px"><b>Reporte '+esc(NODOS.get(otro).valor)+'</b></div>'+
        '<div style="color:var(--cyan);font-size:12px">'+esc(a.motivo)+'</div></div>';
    });
  } else {
    h += '<h2>Vinculaciones</h2><div class="vacio">Ninguna.</div>';
  }

  if(datos.length){
    h += '<h2>Entidades ('+datos.length+')</h2>'+
      '<div class="fila"><button data-accion="abrir" data-valor="'+id+'">Mostrarlas en el gráfico</button></div>';
    const porTipo = new Map();
    datos.forEach(m=>{ if(!porTipo.has(m.tipoLegible)) porTipo.set(m.tipoLegible,[]);
                       porTipo.get(m.tipoLegible).push(m); });
    porTipo.forEach((lista,t)=>{
      h += '<div style="margin:10px 0 4px;font-size:11px;color:var(--tenue);'+
        'text-transform:uppercase;letter-spacing:.1em">'+esc(t)+'</div>';
      lista.forEach(m=>{
        const o = otrosReportesDe(m).length;
        h += '<span class="chip boton" data-ir="entidad|'+m.id+'">'+esc(m.etiqueta)+
          (o>1? ' <b style="color:var(--ambar)">·'+o+'</b>':'')+'</span>';
      });
    });
    h += '<div class="prosa"><p style="font-size:11.5px;color:var(--tenue);margin-top:8px">'+
      'El número en ámbar indica en cuántos reportes del caso aparece ese dato.</p></div>';
  }
  if(!esRaiz){
    h += '<div class="fila"><button data-accion="raiz" data-valor="'+n.valor+'">'+
      'Analizar este reporte</button></div>';
  }
  h += '<h2>Datos del reporte</h2>'+tabla(n.atributos);
  ficha(h);
}

function fichaEntidad(id){
  const n = NODOS.get(id); if(!n){ fichaCaso(); return; }
  const enR = otrosReportesDe(n);
  let h = '<span class="chip cy">'+esc(n.tipoLegible)+'</span><h3>'+esc(n.etiqueta)+'</h3>';
  h += '<h2>Aparece en '+enR.length+' reporte(s) del caso</h2>';
  enR.forEach(r=>{
    const nr = nodoReporte(r);
    h += '<div class="tarjeta click" data-ir="reporte|'+(nr?nr.id:"")+'">'+
      '<div style="font-size:12.5px"><b>Reporte '+esc(r)+'</b></div></div>';
  });
  if(enR.length>1) h += '<div class="prosa"><p style="font-size:12px;color:var(--tenue)">'+
    'Este dato se repite: es de los que sostienen las vinculaciones del caso.</p></div>';
  h += '<h2>Datos</h2>'+tabla(n.atributos);
  const rel = D.aristas.filter(a=>!a.entreReportes && (RE(a.a)===id||RE(a.b)===id));
  const vistos = new Set();
  const lista = [];
  rel.forEach(a=>{
    const otro = RE(a.a)===id?RE(a.b):RE(a.a), m = NODOS.get(otro);
    if(!m || m.tipo==="ORGANIZACION") return;
    const k = otro+"|"+a.relacion; if(vistos.has(k)) return; vistos.add(k);
    lista.push([a,m,RE(a.a)!==id]);
  });
  if(lista.length){
    h += '<h2>Cómo se conecta</h2>';
    lista.forEach(([a,m,inv])=>{
      h += '<div class="tarjeta click'+(a.relacion==="CONTRADICE"?" alarma":"")+
        '" data-ir="relacion|'+a.id+'"><span class="chip">'+esc(a.origenLegible)+'</span>'+
        '<div style="margin-top:4px;font-size:12.5px">'+
        (inv? esc(m.etiqueta)+' '+esc(a.relacionLegible)+' <b>esta entidad</b>'
            : '<b>Esta entidad</b> '+esc(a.relacionLegible)+' '+esc(m.etiqueta))+
        '</div></div>';
    });
  }
  ficha(h);
}

function fichaVinculo(id){
  const a = ARISTAS.get(id); if(!a){ fichaCaso(); return; }
  const sost = (a.puente||[]).filter(x=>x.sostiene);
  const corr = (a.puente||[]).filter(x=>!x.sostiene);
  let h = '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.14em;'+
    'color:var(--cyan)">Por qué se vinculan</div>'+
    '<h3>Reporte '+esc(NODOS.get(a.a).valor)+' y Reporte '+esc(NODOS.get(a.b).valor)+'</h3>'+
    chipPeso(a.confianza)+'<span class="chip">'+esc(a.origenLegible)+'</span>'+
    '<span class="chip'+(a.estado==="validada"?" ok":a.estado==="rechazada"?" al":"")+'">'+
    esc(a.estadoLegible)+'</span>';
  if(sost.length){
    h += '<h2>Lo que sostiene la vinculación</h2>';
    sost.forEach(p=>{
      h += '<div class="tarjeta cyan">'+chipPeso(p.peso)+
        '<div style="font-size:12.5px;margin:2px 0 8px"><b>'+esc(p.tipo)+'</b> '+
        '<span class="chip boton" data-ir="entidad|'+p.nodo+'">'+esc(p.valor)+'</span></div>'+
        '<div style="font-size:11px;color:var(--tenue)">Desde el reporte '+
        esc(NODOS.get(a.a).valor)+'</div>'+cadena(p.camino_a,p.nodo)+
        '<div style="font-size:11px;color:var(--tenue);margin-top:6px">Desde el reporte '+
        esc(NODOS.get(a.b).valor)+'</div>'+cadena(p.camino_b,p.nodo)+'</div>';
    });
  }
  if(corr.length){
    h += '<h2>Lo que solo refuerza</h2><div class="prosa"><p style="font-size:12px;'+
      'color:var(--tenue)">Coinciden, pero no alcanzan por sí solos para vincular.</p></div>';
    corr.forEach(p=>{
      h += '<div class="tarjeta">'+chipPeso(p.peso)+'<div style="font-size:12.5px">'+
        '<b>'+esc(p.tipo)+'</b> <span class="chip boton" data-ir="entidad|'+p.nodo+'">'+
        esc(p.valor)+'</span></div></div>';
    });
  }
  if(a.explicacion) h += '<h2>Fundamento</h2>'+prosa(a.explicacion);
  h += '<h2>De dónde surge</h2>'+tabla([["Método",a.metodo],
    ["Evidencia de origen",a.fuente],["Revisada por",a.validado_por||"sin revisar"],
    ["Identificador",a.id]]);
  h += '<h2>Registrar una decisión</h2><div class="cita">python validar.py '+
    esc(a.id)+' validada --usuario SU_USUARIO</div>';
  ficha(h);
}

function fichaRelacion(id){
  const a = ARISTAS.get(id); if(!a){ fichaCaso(); return; }
  let h = '<span class="chip">'+esc(a.origenLegible)+'</span>'+chipPeso(a.confianza)+
    '<h3>'+esc(etq(a.a))+' <span style="color:var(--cyan);font-weight:400">'+
    esc(a.relacionLegible)+'</span> '+esc(etq(a.b))+'</h3>'+
    '<div style="font-size:11.5px;color:var(--tenue)">'+esc(a.origenDesc)+'</div>';
  if(a.explicacion) h += '<h2>Fundamento</h2>'+prosa(a.explicacion);
  h += '<h2>De dónde surge</h2>'+tabla([
    ["Evidencia de origen",a.fuente],["Ubicación exacta en la fuente",a.locator],
    ["Método",a.metodo],["Fecha del hecho observado",a.observado||"no informada"],
    ["Revisada por",a.validado_por||"sin revisar"],["Puerto de origen",a.puerto||""],
    ["Identificador",a.id]]);
  ficha(h);
}

function markdown(t){
  const L = t.split("\n"); let out=[], enT=false, enL=false;
  const il = s => esc(s).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>")
    .replace(/`(.+?)`/g,'<code style="font-family:var(--mono);font-size:11.5px">$1</code>');
  const cerrar = ()=>{ if(enT){out.push("</table>");enT=false;} if(enL){out.push("</ul>");enL=false;} };
  L.forEach(l=>{
    if(/^\s*\|/.test(l)){
      if(/^\s*\|[\s:|-]+\|\s*$/.test(l)) return;
      const c = l.trim().replace(/^\||\|$/g,"").split("|").map(x=>il(x.trim()));
      if(enL){out.push("</ul>");enL=false;}
      if(!enT){out.push("<table>");enT=true;}
      out.push("<tr>"+c.map(x=>"<td>"+x+"</td>").join("")+"</tr>"); return;
    }
    if(/^\s*[-*]\s/.test(l)){
      if(enT){out.push("</table>");enT=false;}
      if(!enL){out.push("<ul style='margin:6px 0 10px;padding-left:18px'>");enL=true;}
      out.push("<li>"+il(l.replace(/^\s*[-*]\s/,""))+"</li>"); return;
    }
    cerrar();
    if(/^###\s/.test(l)) out.push("<h3>"+il(l.slice(4))+"</h3>");
    else if(/^##\s/.test(l)) out.push("<h2>"+il(l.slice(3))+"</h2>");
    else if(/^#\s/.test(l)) out.push("<h1>"+il(l.slice(2))+"</h1>");
    else if(l.trim()) out.push("<p>"+il(l)+"</p>");
  });
  cerrar();
  return '<div class="prosa">'+out.join("")+"</div>";
}
function fichaInforme(){
  const t = (D.informe||{}).texto||"";
  ficha('<div class="fila"><button data-accion="descargar">Descargar .md</button>'+
    '<button data-ir="inicio|">Volver</button></div>'+
    (t? markdown(t) : '<div class="vacio">Sin informe.</div>'));
}
function descargarInforme(){
  const b = new Blob([(D.informe||{}).texto||""],{type:"text/markdown;charset=utf-8"});
  const u = URL.createObjectURL(b), a = document.createElement("a");
  a.href = u; a.download = "informe_vinculaciones.md"; a.click();
  setTimeout(()=>URL.revokeObjectURL(u),1000);
}
document.getElementById("btnInforme").onclick = ()=>ir({tipo:"informe"});

/* ============================================================ panel ======= */
document.getElementById("plegDer").onclick = ()=>{
  const p = document.getElementById("der");
  p.classList.toggle("plegado");
  document.getElementById("plegDer").textContent = p.classList.contains("plegado")?"‹":"›";
};
(function(){
  const asa = document.getElementById("asa"), panel = document.getElementById("der");
  let act = null;
  asa.addEventListener("pointerdown",e=>{
    act = {x:e.clientX, w:panel.getBoundingClientRect().width};
    asa.setPointerCapture(e.pointerId); panel.style.transition="none";
    document.body.style.userSelect="none"; });
  asa.addEventListener("pointermove",e=>{
    if(!act) return; panel.classList.remove("plegado");
    panel.style.flexBasis = Math.max(280,Math.min(760,act.w+(act.x-e.clientX)))+"px"; });
  asa.addEventListener("pointerup",e=>{
    act=null; asa.releasePointerCapture(e.pointerId);
    panel.style.transition=""; document.body.style.userSelect=""; });
})();

/* ============================================================ arranque ==== */
const sel = document.getElementById("selCaso");
CASOS.forEach(c=>{
  const o = document.createElement("option");
  o.value = c.id; o.textContent = c.etiqueta; sel.appendChild(o);
});
function cambiarCaso(id){
  estado.caso = id; estado.raiz = null; estado.abiertos.clear();
  VP.encuadrado = false;
  HIST.pila = []; HIST.pos = -1;
  sel.value = id;
  ir({tipo:"inicio"});
}
sel.onchange = e=>cambiarCaso(e.target.value);
window.addEventListener("resize", ()=>{ VP.encuadrado = false; dibujar(); });
if(CASOS.length) cambiarCaso(CASOS[0].id); else ficha('<div class="vacio">Sin casos.</div>');
</script></body></html>
"""


def render(g, res, ruta, dossier=None, texto_informe=None):
    datos = _datos(g, res, dossier, texto_informe)
    html = PLANTILLA.replace("__DATOS__",
                             json.dumps(datos, ensure_ascii=False, default=str))
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(html)
    return ruta
