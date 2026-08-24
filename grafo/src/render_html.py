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

ANCHO, ALTO = 1700, 1050

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
    previo, cola, vistos = {n_rep: None}, [n_rep], {n_rep}
    while cola:
        actual = cola.pop(0)
        if actual == n_destino:
            camino = []
            while actual is not None:
                camino.append(actual)
                actual = previo[actual]
            return list(reversed(camino))
        for sig in sorted(vecinos.get(actual, ())):
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


def _datos(g, res, dossier=None, texto_informe=None):
    pos = _layout(g)
    por_nodo = _reportes_por_nodo(g)

    # legajo al que pertenece cada reporte, para la disposicion agrupada
    legajo_de = {}
    for l in res.get("legajos", []):
        for n in l.get("nodos", []):
            legajo_de[n] = l["legajo"]

    nodos = []
    for n, d in g.G.nodes(data=True):
        x, y = pos.get(n, (ANCHO / 2, ALTO / 2))
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
            x=round(x, 1), y=round(y, 1),
            nivel=NIVEL_JERARQUICO.get(d.get("tipo"), 3),
            legajo=legajo_de.get(n),
            reportes=por_nodo.get(n, []),
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
        aristas.append(dict(
            puente=puente,
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
                       legible=ont.ETIQUETA_TIPO.get(t, t), desc=m["desc"])
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
  font:13.5px/1.65 "Segoe UI",system-ui,-apple-system,sans-serif;overflow:hidden}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:#1c2942;border-radius:5px}
::-webkit-scrollbar-track{background:transparent}

.panel{background:var(--panel);border:1px solid var(--borde);border-radius:14px;
  overflow-y:auto;overflow-x:hidden;position:relative;
  transition:flex-basis .3s cubic-bezier(.4,0,.2,1)}
#izq{flex:0 0 320px;margin:10px 0 10px 10px}
#der{flex:0 0 430px;margin:10px 10px 10px 0}
.contenido{padding:16px 18px 24px}
/* deja lugar al boton de plegar, que vive dentro del panel */
#izq .contenido{padding-right:44px}
#der .contenido{padding-left:44px}
/* Plegado: queda un riel angosto con su propio boton. Nunca desaparece del todo,
   para que siempre se pueda volver a abrir desde el mismo lugar. */
.panel.plegado{flex-basis:44px!important}
.panel.plegado .contenido{display:none}
.panel.plegado .rotulo{display:block}
.rotulo{display:none;position:absolute;top:52px;left:50%;transform-origin:0 0;
  transform:rotate(90deg) translateX(0);white-space:nowrap;font-size:10.5px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--tenue);
  pointer-events:none}
.plegar{position:absolute;top:10px;width:26px;height:26px;padding:0;z-index:3;
  display:flex;align-items:center;justify-content:center;font-size:13px;line-height:1}
#izq .plegar{right:10px} #izq.plegado .plegar{right:9px;left:9px}
#der .plegar{left:10px} #der.plegado .plegar{left:9px;right:9px}
.asa{flex:0 0 7px;cursor:col-resize;position:relative}
.asa::after{content:"";position:absolute;top:50%;left:2px;width:3px;height:46px;
  margin-top:-23px;border-radius:3px;background:#1e2c46;transition:background .2s}
.asa:hover::after{background:var(--cyan)}
#centro{flex:1;min-width:280px;position:relative;margin:10px 0;
  border:1px solid var(--borde);border-radius:14px;background:
    radial-gradient(1200px 700px at 30% 20%,rgba(34,211,238,.045),transparent 60%),
    var(--lienzo);overflow:hidden}

h1{font-size:15px;margin:0 30px 0 0;letter-spacing:.2px;font-weight:600}
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
  font-size:10.5px;font-family:var(--mono);letter-spacing:.03em;
  border:1px solid var(--borde);background:#0d1626;color:var(--suave);
  margin:0 5px 5px 0;white-space:nowrap}
.chip.cy{border-color:var(--cyan-borde);background:var(--cyan-tenue);color:#67e8f9}
.chip.ok{border-color:rgba(52,211,153,.35);background:rgba(52,211,153,.08);color:#6ee7b7}
.chip.am{border-color:rgba(251,191,36,.35);background:rgba(251,191,36,.08);color:#fcd34d}
.chip.al{border-color:rgba(248,113,113,.4);background:rgba(248,113,113,.08);color:#fca5a5}
.chip .pt{width:6px;height:6px;border-radius:50%;background:currentColor}
.chip.boton{cursor:pointer}
.chip.boton:hover{border-color:var(--cyan-borde);color:#67e8f9}

label{display:flex;align-items:center;gap:8px;padding:3.5px 0;cursor:pointer;
  font-size:12.5px;color:var(--suave)}
label:hover{color:var(--texto)}
label .sw{width:9px;height:9px;border-radius:2.5px;flex:0 0 9px}
input[type=checkbox]{accent-color:var(--cyan);width:13px;height:13px;cursor:pointer}
input[type=text]{width:100%;padding:8px 11px;border:1px solid var(--borde);
  border-radius:8px;font:inherit;font-size:12.5px;background:#0a1120;color:var(--texto);
  outline:none;transition:border-color .18s}
input[type=text]:focus{border-color:var(--cyan-borde)}
input[type=range]{accent-color:var(--cyan);width:100%}
button{font:inherit;font-size:12px;padding:7px 12px;border:1px solid var(--borde);
  background:#0d1626;color:var(--suave);border-radius:8px;cursor:pointer;
  transition:border-color .18s,color .18s,background .18s;white-space:nowrap}
button:hover:not(:disabled){border-color:var(--cyan-borde);color:#67e8f9;background:var(--cyan-tenue)}
button.activo{border-color:var(--cyan-borde);background:var(--cyan-tenue);color:#67e8f9}
button.primario{border-color:var(--cyan-borde);background:rgba(34,211,238,.14);
  color:#a5f3fc;font-weight:600}
button:disabled{opacity:.35;cursor:default}
.fila{display:flex;gap:8px;align-items:center;margin:9px 0;flex-wrap:wrap}
details{margin:14px 0}
details summary{cursor:pointer;font-size:10.5px;text-transform:uppercase;
  letter-spacing:.14em;color:var(--cyan);opacity:.85;font-weight:600;
  list-style:none;padding:4px 0}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"▸ ";font-size:9px}
details[open] summary::before{content:"▾ "}

#barra{position:absolute;top:12px;left:14px;right:14px;display:flex;gap:8px;
  align-items:center;flex-wrap:wrap;z-index:5;pointer-events:none}
#barra>*{pointer-events:auto}
.grupo{display:flex;background:rgba(8,13,23,.92);border:1px solid var(--borde);
  border-radius:9px;overflow:hidden;backdrop-filter:blur(6px)}
.grupo button{border:0;border-radius:0;background:transparent;padding:7px 13px}
.grupo button+button{border-left:1px solid var(--borde)}
.solo{background:rgba(8,13,23,.92);backdrop-filter:blur(6px)}
select.solo{border:1px solid var(--borde);border-radius:9px;color:#a5f3fc;
  padding:7px 11px;font:inherit;font-size:12px;cursor:pointer;outline:none;
  max-width:250px}
select.solo:hover{border-color:var(--cyan-borde)}
.etiquetaArista{font-size:9px;fill:#8fa1bb;font-family:var(--mono);
  pointer-events:none;paint-order:stroke;stroke:#080d17;stroke-width:3.5;
  stroke-linejoin:round;transition:opacity .3s}
#migas{margin-left:auto;font-size:11px;color:var(--tenue);font-family:var(--mono);
  background:rgba(8,13,23,.92);border-radius:8px;padding:6px 11px;
  max-width:46%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

svg{width:100%;height:100%;display:block;cursor:grab;touch-action:none}
svg.arrastrandoLienzo{cursor:grabbing}
.arista{fill:none;stroke:#31435f;stroke-width:1.3;transition:opacity .3s,stroke-width .2s}
.arista.derivada{stroke:#22d3ee;stroke-width:2;stroke-dasharray:8 5;opacity:.85}
.arista.inferida{stroke:#a78bfa;stroke-width:1.8;stroke-dasharray:2 5;opacity:.8}
.arista.contradice{stroke:var(--alarma);stroke-width:2.2;stroke-dasharray:11 3 2 3}
.arista.apagada{opacity:0}
.arista.rechazada{opacity:.18}
.arista.resaltada{stroke-width:3.4}
.arista.sel{stroke:#fff;stroke-width:3.6;opacity:1}
.zonaClic{stroke:transparent;stroke-width:14;fill:none;cursor:pointer}
.pesoArista{font-size:9.5px;fill:#67e8f9;font-family:var(--mono);pointer-events:none;
  paint-order:stroke;stroke:#080d17;stroke-width:3.5;stroke-linejoin:round;
  transition:opacity .3s}

.nodo{cursor:grab;transition:opacity .3s}
.nodo.moviendo{cursor:grabbing}
.nodo .halo{fill:none;stroke:currentColor;stroke-width:1.2;opacity:0;transition:opacity .25s}
.nodo:hover .halo,.nodo.sel .halo{opacity:.55}
.nodo .cuerpo{stroke:#060a12;stroke-width:2;transition:stroke .2s}
.nodo.sel .cuerpo{stroke:#fff;stroke-width:2.4}
.nodo text{font-size:10.5px;fill:#aebbd0;pointer-events:none;font-family:var(--mono);
  paint-order:stroke;stroke:#060a12;stroke-width:3;stroke-linejoin:round}
.nodo.sel text{fill:#fff}
.nodo.apagado{opacity:0;pointer-events:none}
.nodo .pin{fill:var(--ambar);opacity:0;transition:opacity .2s}
.nodo.fijado .pin{opacity:.9}
.etiquetaGrupo{font-size:11px;fill:#4d5f7d;font-family:var(--mono);
  text-transform:uppercase;letter-spacing:.12em;pointer-events:none}

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
.cadena{font-family:var(--mono);font-size:11.5px;color:var(--suave);
  line-height:2;word-break:break-word}
.cadena b{color:#67e8f9;font-weight:600}
.cadena .fl{color:var(--tenue);padding:0 3px}
.cita{font-family:var(--mono);font-size:11px;color:var(--tenue);word-break:break-all;
  background:#0a1120;border:1px solid var(--borde);border-radius:8px;padding:9px 11px}
.vacio{color:var(--tenue);font-size:12.5px;font-style:italic}
#pie{position:absolute;left:14px;bottom:12px;font-size:11px;color:var(--tenue);
  font-family:var(--mono);pointer-events:none;user-select:none;
  background:rgba(6,10,18,.82);border-radius:8px;padding:6px 10px}
#leyenda{position:absolute;right:14px;bottom:12px;font-size:11px;color:var(--tenue);
  text-align:right;pointer-events:none;user-select:none;font-family:var(--mono);
  line-height:1.9;background:rgba(6,10,18,.82);border-radius:8px;padding:6px 10px}
#leyenda i{display:inline-block;width:26px;height:0;vertical-align:middle;
  margin-right:7px;border-top-width:2px;border-top-style:solid}
@media (max-width:1350px){#leyenda{display:none}}
</style></head><body>

<aside class="panel plegado" id="izq">
  <button class="plegar" id="plegIzq" title="Mostrar filtros">☰</button>
  <div class="rotulo">Filtros</div>
  <div class="contenido">
    <h1>Vinculaciones</h1>
    <div class="sub" id="meta"></div>

    <h2>Buscar</h2>
    <input type="text" id="buscar" placeholder="cuenta, IP, alias, reporte...">

    <h2>Antecedentes a revisar</h2>
    <div id="alertas"></div>

    <details id="detFiltros">
      <summary>Filtros</summary>

      <div style="font-size:11.5px;color:var(--tenue);margin:6px 0 4px">
        Cómo se obtuvo cada relación</div>
      <label><input type="checkbox" class="forigen" value="observada" checked>
        <span class="sw" style="background:#4b6182"></span> Consta en la fuente</label>
      <label><input type="checkbox" class="forigen" value="derivada" checked>
        <span class="sw" style="background:#22d3ee"></span> Derivada por regla</label>
      <label><input type="checkbox" class="forigen" value="inferida" checked>
        <span class="sw" style="background:#a78bfa"></span> Hipótesis a validar</label>

      <div style="font-size:11.5px;color:var(--tenue);margin:12px 0 2px">
        Peso mínimo de la vinculación</div>
      <div class="fila">
        <input type="range" id="conf" min="0" max="100" value="0" style="flex:1">
        <span class="sub" id="confv" style="min-width:32px;text-align:right">0,00</span>
      </div>
      <label><input type="checkbox" id="verPesos" checked> Mostrar el peso sobre la línea</label>
      <label><input type="checkbox" id="verRechazadas"> Mostrar las rechazadas</label>
      <label id="filaUnif"><input type="checkbox" id="unificar" checked>
        Unificar las identidades validadas</label>

      <div style="font-size:11.5px;color:var(--tenue);margin:12px 0 2px">
        Tipos de entidad (al ver todo el detalle)</div>
      <div id="tipos"></div>
    </details>

    <div class="tarjeta cyan">
      <div style="font-size:12px;color:var(--suave)">
        Todo lo que se muestra son <b style="color:var(--texto)">propuestas del
        sistema</b>. Ninguna relación acredita autoría ni responsabilidad.
      </div>
    </div>
  </div>
</aside>

<div class="asa" id="asaIzq"></div>

<main id="centro">
  <div id="barra">
    <div class="grupo">
      <button id="atras" title="Volver (Alt + ←)">‹ Volver</button>
      <button id="adelante" title="Siguiente (Alt + →)">Siguiente ›</button>
    </div>
    <select id="selCaso" class="solo" title="Caso en curso"></select>
    <div class="grupo" id="niveles">
      <button data-nivel="0">Vinculaciones</button>
      <button data-nivel="1">Por qué</button>
      <button data-nivel="2">Todo el caso</button>
    </div>
    <button class="solo" id="reorganizar">Reorganizar</button>
    <button class="solo primario" id="btnInforme">Informe</button>
    <div id="migas"></div>
  </div>

  <svg id="lienzo" viewBox="0 0 __ANCHO__ __ALTO__">
    <g id="vista">
      <g id="ggrupos"></g>
      <g id="garistas"></g>
      <g id="gpesos"></g>
      <g id="gnodos"></g>
    </g>
  </svg>
  <div id="pie"></div>
  <div id="leyenda">
    <div><i style="border-color:#4b6182"></i>consta en la fuente</div>
    <div><i style="border-color:#22d3ee;border-top-style:dashed"></i>derivada por regla</div>
    <div><i style="border-color:#a78bfa;border-top-style:dotted"></i>hipótesis a validar</div>
    <div><i style="border-color:#f87171;border-top-style:dashed"></i>contradice</div>
  </div>
</main>

<div class="asa" id="asaDer"></div>

<aside class="panel" id="der">
  <button class="plegar" id="plegDer" title="Plegar la ficha">›</button>
  <div class="rotulo">Ficha</div>
  <div class="contenido" id="cuerpo"></div>
</aside>

<script>
const D = __DATOS__;
const ANCHO = __ANCHO__, ALTO = __ALTO__;
const NODOS = new Map(D.nodos.map(n=>[n.id,n]));
const ARISTAS = new Map(D.aristas.map(a=>[a.id,a]));
const ADY = new Map();
D.aristas.forEach(a=>{
  if(!ADY.has(a.a)) ADY.set(a.a,new Set());
  if(!ADY.has(a.b)) ADY.set(a.b,new Set());
  ADY.get(a.a).add(a.b); ADY.get(a.b).add(a.a);
});
const UNIF = new Map(Object.entries(D.identidades||{}));
const HAY_UNIF = UNIF.size > 0;
const RE = id => (estado.unificar && UNIF.get(id)) || id;
const VINCULOS = D.aristas.filter(a=>a.entreReportes);
const CASOS = D.casos || [];

/* El visor trabaja sobre UN caso por vez. No es un explorador del archivo
   general: mostrar a la vez las relaciones de todos los casos vuelve ilegible
   lo único que le importa al operador, que es el caso que tiene en la mano. */
function casoActual(){ return CASOS.find(c=>c.id===estado.caso) || CASOS[0] || null; }
function reportesDelCaso(){
  const c = casoActual();
  return new Set(c ? c.reportes : []);
}
function enElCaso(id){
  const n = NODOS.get(id); if(!n) return false;
  const rs = reportesDelCaso();
  if(n.tipo==="REPORTE") return rs.has(n.valor);
  return (n.reportes||[]).some(r=>rs.has(r));
}
function vinculosDelCaso(){
  const rs = reportesDelCaso();
  return VINCULOS.filter(a=>rs.has((NODOS.get(a.a)||{}).valor) &&
                            rs.has((NODOS.get(a.b)||{}).valor));
}
function esCompartido(id){
  const n = NODOS.get(id); if(!n || n.tipo==="REPORTE") return false;
  const rs = reportesDelCaso();
  return (n.reportes||[]).filter(r=>rs.has(r)).length >= 2;
}

const estado = {tipos:new Set(Object.keys(D.tipos)),
                origenes:new Set(["observada","derivada","inferida"]),
                conf:0, nivel:0, disposicion:"secuencia", rechazadas:false,
                verPesos:true, verEtiquetas:true, texto:"", unificar:true,
                caso:null, foco:null, vista:{tipo:"inicio"}};

const num = v => (v==null? "—" : v.toFixed(2).replace(".",","));
const esc = s => String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const etq = id => (NODOS.get(id)||{}).etiqueta || id;
// Los estados y motivos vienen del sistema transaccional en formato tecnico.
// En pantalla se leen como frases.
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

document.getElementById("meta").innerHTML =
  D.meta.reportes+" reportes · "+D.nodos.length+" entidades · "+
  VINCULOS.length+" vinculaciones";

/* =========================================================== navegación ==== */
/* Un historial simple: cada vista es {tipo, id}. Volver y Siguiente recorren
   la pila, igual que en un navegador. Sin esto, entrar a una entidad y querer
   regresar obliga a reconstruir el recorrido a mano. */
const HIST = {pila:[], pos:-1};
function ir(vista, reemplazar){
  const actual = HIST.pila[HIST.pos];
  if(actual && actual.tipo===vista.tipo && actual.id===vista.id) { mostrar(vista); return; }
  if(reemplazar && HIST.pos>=0) HIST.pila[HIST.pos] = vista;
  else { HIST.pila = HIST.pila.slice(0,HIST.pos+1); HIST.pila.push(vista); HIST.pos++; }
  mostrar(vista);
}
function atras(){ if(HIST.pos>0){ HIST.pos--; mostrar(HIST.pila[HIST.pos]); } }
function adelante(){ if(HIST.pos<HIST.pila.length-1){ HIST.pos++; mostrar(HIST.pila[HIST.pos]); } }
function botonesHist(){
  document.getElementById("atras").disabled = HIST.pos<=0;
  document.getElementById("adelante").disabled = HIST.pos>=HIST.pila.length-1;
  const v = HIST.pila[HIST.pos] || {tipo:"inicio"};
  const nombre = v.tipo==="inicio" ? "Vista general"
    : v.tipo==="informe" ? "Informe de vinculaciones"
    : v.tipo==="porque" ? "Por qué se vinculan"
    : v.tipo==="arista" ? "Relación"
    : (NODOS.get(v.id)||{}).tipoLegible+" · "+etq(v.id);
  document.getElementById("migas").textContent =
    (HIST.pos>0 ? "◂ " : "") + nombre;
}
function mostrar(v){
  estado.vista = v;
  if(v.tipo==="inicio") pintarInicio();
  else if(v.tipo==="nodo") pintarNodo(v.id);
  else if(v.tipo==="arista") pintarArista(v.id);
  else if(v.tipo==="porque") pintarPorQue(v.id);
  else if(v.tipo==="informe") pintarInforme();
  botonesHist();
  aplicar();
}
document.getElementById("atras").onclick = atras;
document.getElementById("adelante").onclick = adelante;
window.addEventListener("keydown",e=>{
  if(e.altKey && e.key==="ArrowLeft"){ e.preventDefault(); atras(); }
  if(e.altKey && e.key==="ArrowRight"){ e.preventDefault(); adelante(); }
});
window.irANodo = id => ir({tipo:"nodo", id});
window.irAArista = id => ir({tipo:"arista", id});
window.irAPorQue = id => ir({tipo:"porque", id});
window.irAInicio = () => ir({tipo:"inicio"});

/* ============================================================ simulación ==== */
const SIM = new Map();
D.nodos.forEach(n=>SIM.set(n.id,{x:n.x,y:n.y,vx:0,vy:0,fijo:false}));
const CX = ANCHO/2, CY = ALTO/2;
let alpha = 0.9, corriendo = true, animando = false;

function paso(){
  const activos = D.nodos.filter(n=>!elN.get(n.id).classList.contains("apagado"));
  const pocos = activos.length <= 16;
  const dt = 0.85, gravedad = 0.0016;
  const repulsion = pocos ? 26000 : 6200;
  const resorte = pocos ? 0.010 : 0.013;
  const largo = pocos ? 260 : 155;
  for(let i=0;i<activos.length;i++){
    const a = SIM.get(activos[i].id);
    for(let j=i+1;j<activos.length;j++){
      const b = SIM.get(activos[j].id);
      let dx = b.x-a.x, dy = b.y-a.y, d2 = dx*dx+dy*dy;
      if(d2 < 1){ dx = (Math.random()-0.5)*4; dy = (Math.random()-0.5)*4; d2 = dx*dx+dy*dy; }
      if(d2 > 700*700) continue;
      const f = repulsion/d2, d = Math.sqrt(d2);
      const ux = dx/d*f, uy = dy/d*f;
      a.vx -= ux; a.vy -= uy; b.vx += ux; b.vy += uy;
    }
  }
  const vis = new Set(activos.map(n=>n.id));
  D.aristas.forEach(e=>{
    const ea = RE(e.a), eb = RE(e.b);
    if(ea===eb || !vis.has(ea) || !vis.has(eb)) return;
    const a = SIM.get(ea), b = SIM.get(eb);
    const dx = b.x-a.x, dy = b.y-a.y;
    const d = Math.sqrt(dx*dx+dy*dy)||1;
    const f = (d-largo)*resorte;
    const ux = dx/d*f, uy = dy/d*f;
    a.vx += ux; a.vy += uy; b.vx -= ux; b.vy -= uy;
  });
  let mov = 0;
  SIM.forEach(s=>{
    s.vx += (CX-s.x)*gravedad; s.vy += (CY-s.y)*gravedad;
    if(s.fijo){ s.vx = 0; s.vy = 0; return; }
    s.vx *= 0.82; s.vy *= 0.82;
    s.x += s.vx*dt*alpha; s.y += s.vy*dt*alpha;
    s.x = Math.max(60,Math.min(ANCHO-60,s.x));
    s.y = Math.max(70,Math.min(ALTO-50,s.y));
    mov += Math.abs(s.vx)+Math.abs(s.vy);
  });
  alpha *= 0.992;
  if(alpha < 0.02 || mov < 0.6) corriendo = false;
}
function recalentar(a){
  if(estado.disposicion!=="fuerzas" || animando) return;
  alpha = Math.max(alpha,a||0.55);
  if(!corriendo){ corriendo = true; bucle(); }
}
function bucle(){ if(!corriendo||animando) return; paso(); pintarPos(); requestAnimationFrame(bucle); }

function animarA(destino, ms, alTerminar){
  corriendo = false; animando = true;
  const inicio = new Map();
  SIM.forEach((s,id)=>inicio.set(id,{x:s.x,y:s.y}));
  const t0 = performance.now();
  (function cuadro(t){
    const p = Math.min(1,(t-t0)/(ms||700));
    const e = p<0.5 ? 4*p*p*p : 1-Math.pow(-2*p+2,3)/2;
    destino.forEach((d,id)=>{
      const s = SIM.get(id), i = inicio.get(id);
      s.x = i.x+(d.x-i.x)*e; s.y = i.y+(d.y-i.y)*e; s.vx = 0; s.vy = 0;
    });
    pintarPos();
    if(p<1) requestAnimationFrame(cuadro);
    else { animando = false; if(alTerminar) alTerminar(); }
  })(performance.now());
}

/* ========================================================= disposiciones ==== */
const GRUPOS = [];
function visiblesAhora(){ return D.nodos.filter(n=>!elN.get(n.id).classList.contains("apagado")); }
function dispJerarquica(){
  const vis = visiblesAhora(), porNivel = new Map();
  vis.forEach(n=>{ if(!porNivel.has(n.nivel)) porNivel.set(n.nivel,[]); porNivel.get(n.nivel).push(n); });
  const niveles = [...porNivel.keys()].sort((a,b)=>a-b);
  const altoUtil = ALTO-200, pasoY = niveles.length>1 ? altoUtil/(niveles.length-1) : 0;
  const destino = new Map(), orden = new Map();
  niveles.forEach((niv,i)=>{
    let fila = porNivel.get(niv).slice();
    fila = i>0 ? fila.sort((a,b)=>bari(a,orden)-bari(b,orden))
               : fila.sort((a,b)=>String(a.etiqueta).localeCompare(String(b.etiqueta)));
    const pasoX = (ANCHO-220)/Math.max(1,fila.length);
    fila.forEach((n,j)=>{ destino.set(n.id,{x:110+pasoX*(j+0.5), y:120+pasoY*i}); orden.set(n.id,j); });
  });
  return destino;
}
function bari(n,orden){
  const vec = [...(ADY.get(n.id)||[])].filter(v=>orden.has(v)).map(v=>orden.get(v));
  return vec.length ? vec.reduce((a,b)=>a+b,0)/vec.length : 1e9;
}
function dispLegajos(){
  const vis = visiblesAhora(), grupos = new Map();
  vis.forEach(n=>{
    let g = n.legajo;
    if(!g){
      const vecinos = [...(ADY.get(n.id)||[])].map(v=>(NODOS.get(v)||{}).legajo).filter(Boolean);
      g = vecinos.length ? vecinos[0] : "Sin agrupar";
    }
    if(!grupos.has(g)) grupos.set(g,[]);
    grupos.get(g).push(n);
  });
  const claves = [...grupos.keys()].sort();
  const cols = Math.min(claves.length,3)||1, filas = Math.ceil(claves.length/cols);
  const anchoCol = ANCHO/cols, altoFila = (ALTO-140)/filas;
  const destino = new Map(); GRUPOS.length = 0;
  claves.forEach((clave,i)=>{
    const cx = anchoCol*((i%cols)+0.5), cy = 140+altoFila*(Math.floor(i/cols)+0.45);
    const miembros = grupos.get(clave).slice()
      .sort((a,b)=>(a.nivel-b.nivel)||String(a.etiqueta).localeCompare(String(b.etiqueta)));
    GRUPOS.push({clave, x:cx, y:cy-Math.min(altoFila,anchoCol)*0.42-16});
    const r = Math.min(anchoCol,altoFila)*0.36;
    miembros.forEach((n,j)=>{
      if(miembros.length===1){ destino.set(n.id,{x:cx,y:cy}); return; }
      const ang = (j/miembros.length)*Math.PI*2 - Math.PI/2;
      const rr = n.tipo==="REPORTE" ? r*0.45 : r;
      destino.set(n.id,{x:cx+Math.cos(ang)*rr, y:cy+Math.sin(ang)*rr});
    });
  });
  return destino;
}
/* Disposición del "por qué": el reporte A a la izquierda, el B a la derecha, y
   una fila por cada dato compartido, con la cadena que va de un reporte al otro
   pasando por ese dato. Es la forma más directa de leer cómo llegaron ahí. */
function dispPorQue(aristaId){
  const a = ARISTAS.get(aristaId);
  if(!a || !a.puente || !a.puente.length) return null;
  const destino = new Map();
  const izq = 190, der = ANCHO-190;
  const filas = a.puente.length;
  // La cadena principal -la que sostiene el vinculo- queda horizontal, con los
  // dos reportes a la misma altura. Lo que solo refuerza cuelga por debajo.
  const yBase = 250, alto = ALTO-yBase-140;
  const pasoY = filas>1 ? alto/(filas-1) : 0;
  destino.set(RE(a.a), {x:izq, y:yBase});
  destino.set(RE(a.b), {x:der, y:yBase});
  // Un mismo nodo puede estar en varias cadenas (la cuenta suele estar en todas).
  // Se lo ubica en la primera en la que aparece y no se lo vuelve a mover: si no,
  // cada cadena lo arrastra a su fila y el dibujo se desarma.
  a.puente.forEach((p,i)=>{
    const y = yBase+pasoY*i;
    const cadena = p.camino_a.concat(p.camino_b.slice(0,-1).reverse());
    const total = cadena.length;
    cadena.forEach((id,k)=>{
      const e = RE(id);
      if(e===RE(a.a) || e===RE(a.b) || destino.has(e)) return;
      const t = total>1 ? k/(total-1) : 0.5;
      destino.set(e, {x: izq+(der-izq)*t, y});
    });
  });
  return destino;
}
/* Disposición en secuencia: se lee de izquierda a derecha como una frase.
   [reporte en curso] -> [por dónde pasa] -> [dato compartido] -> [reporte vinculado]
   Es la forma más directa de seguir la lógica de una vinculación sin tener que
   interpretar una nube de nodos. */
function dispSecuencia(){
  const vis = visiblesAhora();
  if(!vis.length) return new Map();
  const ids = new Set(vis.map(n=>n.id));
  const rs = reportesDelCaso();
  const reportes = vis.filter(n=>n.tipo==="REPORTE");
  const ancla = (estado.foco && ids.has(estado.foco)) ? estado.foco
              : (reportes[0] ? reportes[0].id : vis[0].id);

  // distancia al reporte en curso, recorriendo solo lo visible
  const dist = new Map([[ancla,0]]);
  let frente = [ancla];
  while(frente.length){
    const sig = [];
    frente.forEach(x=>(ADY.get(x)||new Set()).forEach(y0=>{
      const y = RE(y0);
      if(ids.has(y) && !dist.has(y)){ dist.set(y, dist.get(x)+1); sig.push(y); }
    }));
    frente = sig;
  }

  const COL_COMPARTIDO = 4, COL_OTROS = 5;
  const columnas = new Map();
  vis.forEach(n=>{
    let c;
    if(n.id===ancla) c = 0;
    else if(n.tipo==="REPORTE") c = COL_OTROS;
    else if(esCompartido(n.id)) c = COL_COMPARTIDO;
    else c = Math.min(3, Math.max(1, dist.get(n.id) || 1));
    if(!columnas.has(c)) columnas.set(c,[]);
    columnas.get(c).push(n);
  });

  const usadas = [...columnas.keys()].sort((a,b)=>a-b);
  const destino = new Map(), orden = new Map();
  const pasoX = (ANCHO-260)/Math.max(1, usadas.length-1);
  usadas.forEach((c,i)=>{
    let fila = columnas.get(c).slice();
    fila = i>0 ? fila.sort((a,b)=>bari(a,orden)-bari(b,orden))
               : fila.sort((a,b)=>String(a.etiqueta).localeCompare(String(b.etiqueta)));
    const x = usadas.length>1 ? 130+pasoX*i : ANCHO/2;
    const alto = ALTO-260, pasoY = alto/Math.max(1, fila.length);
    fila.forEach((n,j)=>{
      destino.set(n.id, {x, y: 170+pasoY*(j+0.5)});
      orden.set(n.id, j);
    });
  });
  return destino;
}

function aplicarDisposicion(disp, arg){
  estado.disposicion = disp;
  if(disp==="fuerzas"){
    GRUPOS.length = 0; pintarGrupos();
    SIM.forEach(s=>s.fijo=false);
    elN.forEach(el=>el.classList.remove("fijado"));
    corriendo = false; animando = false; alpha = 0.9; recalentar(0.9);
    return;
  }
  const destino = disp==="jerarquica" ? dispJerarquica()
                : disp==="porque" ? dispPorQue(arg)
                : disp==="secuencia" ? dispSecuencia() : dispLegajos();
  if(!destino){ aplicarDisposicion("fuerzas"); return; }
  if(disp!=="legajos"){ GRUPOS.length = 0; pintarGrupos(); }
  animarA(destino, 700, ()=>{ destino.forEach((_,id)=>{ SIM.get(id).fijo = true; }); pintarGrupos(); });
}
const DISPOSICIONES = [
  ["secuencia", "En secuencia"], ["fuerzas", "Orgánica"],
  ["jerarquica", "Por tipo de dato"]];
document.getElementById("reorganizar").onclick = ()=>{
  const i = DISPOSICIONES.findIndex(d=>d[0]===estado.disposicion);
  const sig = DISPOSICIONES[(i+1)%DISPOSICIONES.length];
  aplicarDisposicion(sig[0]);
  document.getElementById("reorganizar").textContent = "Vista: "+sig[1];
};

/* =============================================================== dibujo ==== */
const SVGNS = "http://www.w3.org/2000/svg";
const gG = document.getElementById("ggrupos"), gA = document.getElementById("garistas");
const gP = document.getElementById("gpesos"), gN = document.getElementById("gnodos");
const elA = new Map(), elZ = new Map(), elN = new Map(), elP = new Map();

D.aristas.forEach(a=>{
  if(!NODOS.has(a.a)||!NODOS.has(a.b)) return;
  const z = document.createElementNS(SVGNS,"path");
  z.setAttribute("class","zonaClic");
  z.onclick = e=>{ e.stopPropagation(); ir(a.entreReportes?{tipo:"porque",id:a.id}:{tipo:"arista",id:a.id}); };
  const t = document.createElementNS(SVGNS,"title");
  t.textContent = etq(a.a)+" "+a.relacionLegible+" "+etq(a.b)+
                  (a.confianza!=null? "  ·  peso "+num(a.confianza) : "");
  z.appendChild(t);
  const p = document.createElementNS(SVGNS,"path");
  p.setAttribute("class","arista "+a.origen+(a.relacion==="CONTRADICE"?" contradice":"")+
                 (a.estado==="rechazada"?" rechazada":""));
  gA.appendChild(p); gA.appendChild(z);
  elA.set(a.id,p); elZ.set(a.id,z);
  // Cada arista lleva escrito QUE la vincula. Sin la etiqueta, una linea entre
  // dos nodos no dice nada: el operador tiene que poder leer la relacion.
  const tx = document.createElementNS(SVGNS,"text");
  tx.setAttribute("class", a.entreReportes ? "pesoArista" : "etiquetaArista");
  tx.setAttribute("text-anchor","middle");
  tx.textContent = a.entreReportes
    ? a.relacionLegible+" · "+num(a.confianza)
    : a.relacionLegible;
  gP.appendChild(tx); elP.set(a.id,tx);
});
function radio(n){
  if(n.tipo==="REPORTE") return 13;
  if(n.tipo==="IDENTIDAD") return 12;
  if(n.tipo==="PERSONA_MENCION"||n.tipo==="EVENTO") return 10;
  return 8;
}
D.nodos.forEach(n=>{
  const g = document.createElementNS(SVGNS,"g");
  g.setAttribute("class","nodo"); g.style.color = n.color;
  const r = radio(n);
  const halo = document.createElementNS(SVGNS,"circle");
  halo.setAttribute("class","halo"); halo.setAttribute("r",r+6); g.appendChild(halo);
  const caja = ["REPORTE","EVIDENCIA","ORGANIZACION","DOCUMENTO"].includes(n.tipo);
  let f;
  if(caja){
    f = document.createElementNS(SVGNS,"rect");
    f.setAttribute("x",-r); f.setAttribute("y",-r);
    f.setAttribute("width",2*r); f.setAttribute("height",2*r); f.setAttribute("rx",3);
  } else { f = document.createElementNS(SVGNS,"circle"); f.setAttribute("r",r); }
  f.setAttribute("class","cuerpo"); f.setAttribute("fill",n.color); g.appendChild(f);
  const pin = document.createElementNS(SVGNS,"circle");
  pin.setAttribute("class","pin"); pin.setAttribute("r",3);
  pin.setAttribute("cx",r-1); pin.setAttribute("cy",-r+1); g.appendChild(pin);
  const tx = document.createElementNS(SVGNS,"text");
  tx.setAttribute("x",r+6); tx.setAttribute("y",4);
  tx.textContent = (n.etiqueta||"").slice(0,28); g.appendChild(tx);
  const ti = document.createElementNS(SVGNS,"title");
  ti.textContent = n.tipoLegible+": "+n.etiqueta; g.appendChild(ti);
  gN.appendChild(g); elN.set(n.id,g);
  arrastrable(g,n);
});
function pintarGrupos(){
  gG.textContent = "";
  GRUPOS.forEach(gr=>{
    const t = document.createElementNS(SVGNS,"text");
    t.setAttribute("class","etiquetaGrupo");
    t.setAttribute("x",gr.x); t.setAttribute("y",gr.y);
    t.setAttribute("text-anchor","middle");
    t.textContent = gr.clave==="Sin agrupar" ? "sin vincular" : "legajo "+gr.clave;
    gG.appendChild(t);
  });
}
function pintarPos(){
  D.aristas.forEach(a=>{
    const p = elA.get(a.id); if(!p) return;
    const s = SIM.get(RE(a.a)), t = SIM.get(RE(a.b));
    if(!s||!t) return;
    const dx = t.x-s.x, dy = t.y-s.y;
    const cx = (s.x+t.x)/2 - dy*0.08, cy = (s.y+t.y)/2 + dx*0.08;
    const d = "M"+s.x+","+s.y+" Q"+cx+","+cy+" "+t.x+","+t.y;
    p.setAttribute("d",d); elZ.get(a.id).setAttribute("d",d);
    const tx = elP.get(a.id);
    if(tx){ tx.setAttribute("x",(s.x+t.x)/2 - dy*0.04); tx.setAttribute("y",(s.y+t.y)/2 + dx*0.04 + 3); }
  });
  SIM.forEach((s,id)=>{
    const el = elN.get(id);
    if(el) el.setAttribute("transform","translate("+s.x.toFixed(1)+","+s.y.toFixed(1)+")");
  });
}

/* ============================================================= arrastre ==== */
function aGrafo(ev){
  const r = svg.getBoundingClientRect();
  const sx = (ev.clientX-r.left)/r.width*ANCHO, sy = (ev.clientY-r.top)/r.height*ALTO;
  return {x:(sx-T.x)/T.k, y:(sy-T.y)/T.k};
}
function arrastrable(el,n){
  let mov = false, movido = false;
  el.addEventListener("pointerdown",ev=>{
    ev.stopPropagation(); ev.preventDefault();
    mov = true; movido = false;
    el.setPointerCapture(ev.pointerId); el.classList.add("moviendo");
    SIM.get(n.id).fijo = true; recalentar(0.75);
  });
  el.addEventListener("pointermove",ev=>{
    if(!mov) return;
    const p = aGrafo(ev), s = SIM.get(n.id);
    if(Math.abs(p.x-s.x)>2||Math.abs(p.y-s.y)>2) movido = true;
    s.x = p.x; s.y = p.y; s.vx = 0; s.vy = 0;
    recalentar(0.6); pintarPos();
  });
  el.addEventListener("pointerup",ev=>{
    if(!mov) return;
    mov = false; el.classList.remove("moviendo"); el.releasePointerCapture(ev.pointerId);
    if(movido){ el.classList.add("fijado"); recalentar(0.5); }
    else { if(estado.disposicion==="fuerzas") SIM.get(n.id).fijo = false; ir({tipo:"nodo", id:n.id}); }
  });
  el.addEventListener("dblclick",ev=>{
    ev.stopPropagation(); SIM.get(n.id).fijo = false;
    el.classList.remove("fijado"); recalentar(0.6);
  });
}

/* ============================================================== filtros ==== */
function nodosDelPuente(a){
  const s = new Set();
  (a.puente||[]).forEach(p=>{
    p.camino_a.forEach(x=>s.add(RE(x)));
    p.camino_b.forEach(x=>s.add(RE(x)));
  });
  return s;
}
/* Pares consecutivos de cada cadena. En la vista "por qué" solo se dibujan
   estos tramos: mostrar todas las relaciones entre los nodos visibles llena la
   pantalla de líneas que no explican nada. */
function tramosDelPuente(a){
  const s = new Set();
  (a.puente||[]).forEach(p=>{
    [p.camino_a, p.camino_b].forEach(cad=>{
      for(let i=0;i<cad.length-1;i++){
        const x = RE(cad[i]), y = RE(cad[i+1]);
        if(x!==y){ s.add(x+"|"+y); s.add(y+"|"+x); }
      }
    });
  });
  return s;
}
function conjuntoVisible(){
  const v = estado.vista;
  const txt = estado.texto.trim().toLowerCase();
  const delCaso = D.nodos.filter(n=>enElCaso(n.id));
  const reportesCaso = delCaso.filter(n=>n.tipo==="REPORTE").map(n=>n.id);
  const vincCaso = vinculosDelCaso();
  let base = new Set();

  if(v.tipo==="porque"){
    // Solo lo que explica ESA vinculación: los dos reportes y las cadenas.
    const a = ARISTAS.get(v.id);
    if(a){ base = nodosDelPuente(a); base.add(RE(a.a)); base.add(RE(a.b)); }
  } else if(estado.nivel===0){
    base = new Set(reportesCaso);
  } else if(estado.nivel===1){
    // "Por qué": los reportes del caso y únicamente las cadenas que sostienen
    // sus vinculaciones. Nada de lo que no explique algo.
    base = new Set(reportesCaso);
    let relevantes = vincCaso;
    if(estado.foco) relevantes = vincCaso.filter(a=>a.a===estado.foco||a.b===estado.foco);
    if(!relevantes.length) relevantes = vincCaso;
    relevantes.forEach(a=>nodosDelPuente(a).forEach(x=>base.add(x)));
    if(v.tipo==="nodo" && (NODOS.get(v.id)||{}).tipo!=="REPORTE"){
      base.add(v.id); (ADY.get(v.id)||new Set()).forEach(x=>base.add(RE(x)));
    }
  } else {
    base = new Set(delCaso.map(n=>n.id));
  }

  const fin = new Set();
  base.forEach(id0=>{
    const id = RE(id0);
    const n = NODOS.get(id); if(!n) return;
    if(!enElCaso(id)) return;                     // nunca se sale del caso
    const colapsada = estado.unificar && UNIF.has(id0) && id!==id0;
    if(!colapsada && estado.nivel>1 && v.tipo!=="porque" && !estado.tipos.has(n.tipo)) return;
    if(txt){
      const blob = (n.etiqueta+" "+n.tipoLegible+" "+n.atributos.map(x=>x[1]).join(" ")).toLowerCase();
      if(!blob.includes(txt)) return;
    }
    fin.add(id);
  });
  return fin;
}
function aplicar(reacomodar){
  const v = estado.vista;
  const vis = conjuntoVisible();
  D.nodos.forEach(n=>elN.get(n.id).classList.toggle("apagado",!vis.has(n.id)));

  const foco = v.tipo==="porque" ? ARISTAS.get(v.id) : null;
  const tramos = foco ? tramosDelPuente(foco) : null;
  let cuenta = 0;
  const visiblesA = [];
  D.aristas.forEach(a=>{
    const p = elA.get(a.id); if(!p) return;
    const ea = RE(a.a), eb = RE(a.b);
    let ok = estado.origenes.has(a.origen) && vis.has(ea) && vis.has(eb) && ea!==eb;
    if(ok && estado.nivel===0 && v.tipo!=="porque" && !a.entreReportes) ok = false;
    if(ok && foco && !a.entreReportes && !tramos.has(ea+"|"+eb)) ok = false;
    if(ok && foco && a.entreReportes && a.id!==foco.id) ok = false;
    if(ok && a.confianza!=null) ok = a.confianza >= estado.conf;
    if(ok && a.estado==="rechazada" && !estado.rechazadas) ok = false;
    p.classList.toggle("apagada",!ok);
    elZ.get(a.id).style.pointerEvents = ok ? "stroke" : "none";
    const tocaSel = v.tipo==="nodo" && (ea===RE(v.id)||eb===RE(v.id));
    p.classList.toggle("resaltada",!!(ok&&tocaSel));
    p.classList.toggle("sel", (v.tipo==="arista"||v.tipo==="porque") && a.id===v.id);
    if(ok) cuenta++;
    visiblesA.push([a, ok]);
  });
  // Con muchas aristas las etiquetas se pisan y estorban: por encima de ese
  // umbral se deja solo el peso de las vinculaciones entre reportes.
  const pocasAristas = cuenta <= 90;
  visiblesA.forEach(([a, ok])=>{
    const tx = elP.get(a.id); if(!tx) return;
    const mostrar = ok && estado.verEtiquetas &&
                    (a.entreReportes ? estado.verPesos : pocasAristas);
    tx.style.opacity = mostrar ? 1 : 0;
  });
  elN.forEach((el,id)=>el.classList.toggle("sel", v.tipo==="nodo" && RE(v.id)===id));

  document.getElementById("pie").textContent =
    vis.size+(vis.size===1?" entidad · ":" entidades · ")+
    cuenta+(cuenta===1?" relación":" relaciones");
  document.querySelectorAll("#niveles button").forEach(b=>
    b.classList.toggle("activo",+b.dataset.nivel===estado.nivel && v.tipo!=="porque"));

  if(reacomodar!==false){
    if(v.tipo==="porque") aplicarDisposicion("porque", v.id);
    else if(estado.disposicion==="fuerzas") recalentar(0.6);
    else aplicarDisposicion(estado.disposicion);
  }
}

/* ======================================================== panel izquierdo ==== */
const cont = document.getElementById("tipos");
Object.entries(D.tipos).forEach(([t,m])=>{
  const usados = D.nodos.filter(n=>n.tipo===t).length;
  if(!usados) return;
  const l = document.createElement("label");
  l.innerHTML = '<input type="checkbox" class="ftipo" value="'+t+'" checked>'+
    '<span class="sw" style="background:'+m.color+'"></span>'+esc(m.legible)+
    ' <span style="color:var(--tenue);font-family:var(--mono);font-size:11px">'+usados+'</span>';
  l.title = m.desc; cont.appendChild(l);
});
const ca = document.getElementById("alertas");
if(!D.alertas.length) ca.innerHTML = '<div class="vacio">Ningún antecedente archivado quedó reactivado.</div>';
D.alertas.forEach(al=>{
  const d = document.createElement("div");
  d.className = "tarjeta click";
  d.innerHTML = '<span class="chip '+(al.prioridad==="alta"?"am":"cy")+'"><span class="pt"></span>'+
    esc(al.prioridad)+'</span>'+
    '<div style="margin-top:4px;font-size:12.5px">Reporte <b>'+esc(al.reporte_archivado)+'</b> archivado</div>'+
    '<div style="color:var(--tenue);font-size:12px;margin-top:4px">Lo reactiva el '+
    esc(al.reporte_disparador)+' · peso '+num(al.confianza_vinculo)+'</div>';
  d.onclick = ()=>ir({tipo:"porque", id:al.arista_id});
  ca.appendChild(d);
});
if(!HAY_UNIF) document.getElementById("filaUnif").style.display = "none";

document.querySelectorAll(".ftipo").forEach(c=>c.onchange=()=>{
  c.checked?estado.tipos.add(c.value):estado.tipos.delete(c.value); aplicar();});
document.querySelectorAll(".forigen").forEach(c=>c.onchange=()=>{
  c.checked?estado.origenes.add(c.value):estado.origenes.delete(c.value); aplicar(false);});
document.getElementById("conf").oninput = e=>{
  estado.conf = e.target.value/100;
  document.getElementById("confv").textContent = num(estado.conf); aplicar(false);};
document.getElementById("verPesos").onchange = e=>{estado.verPesos=e.target.checked;aplicar(false);};
document.getElementById("verRechazadas").onchange = e=>{estado.rechazadas=e.target.checked;aplicar(false);};
document.getElementById("unificar").onchange = e=>{estado.unificar=e.target.checked;aplicar();};
document.getElementById("buscar").oninput = e=>{estado.texto=e.target.value;aplicar();};
const sel = document.getElementById("selCaso");
CASOS.forEach(c=>{
  const o = document.createElement("option");
  o.value = c.id; o.textContent = c.etiqueta;
  sel.appendChild(o);
});
function cambiarCaso(id){
  estado.caso = id;
  const c = casoActual();
  estado.foco = c ? ont_id(c.reportes[0]) : null;
  sel.value = id;
  HIST.pila = []; HIST.pos = -1;
  ir({tipo:"inicio"});
}
function ont_id(valorReporte){ return "REPORTE::"+String(valorReporte).toLowerCase(); }
sel.onchange = e=>cambiarCaso(e.target.value);

document.querySelectorAll("#niveles button").forEach(b=>b.onclick=()=>{
  estado.nivel = +b.dataset.nivel;
  if(estado.vista.tipo==="porque"){
    const a = ARISTAS.get(estado.vista.id);
    ir({tipo:"nodo", id:a? a.a : null});
  } else aplicar();
});

/* ================================================ plegado y redimensionado ==== */
function plegable(idPanel,idBoton,abierto,cerrado){
  const panel = document.getElementById(idPanel), b = document.getElementById(idBoton);
  const pintar = ()=>{
    const p = panel.classList.contains("plegado");
    b.textContent = p ? cerrado : abierto;
    b.title = (p?"Mostrar":"Plegar")+" el panel";
  };
  b.onclick = ()=>{ panel.classList.toggle("plegado"); panel.style.flexBasis=""; pintar(); };
  pintar();
}
plegable("izq","plegIzq","‹","☰");
plegable("der","plegDer","›","‹");
function redimensionable(idAsa,idPanel,lado){
  const asa = document.getElementById(idAsa), panel = document.getElementById(idPanel);
  let act = null;
  asa.addEventListener("pointerdown",e=>{
    act = {x:e.clientX, w:panel.getBoundingClientRect().width};
    asa.setPointerCapture(e.pointerId);
    panel.style.transition = "none"; document.body.style.userSelect = "none";
  });
  asa.addEventListener("pointermove",e=>{
    if(!act) return;
    const delta = lado==="izq" ? (e.clientX-act.x) : (act.x-e.clientX);
    panel.classList.remove("plegado");
    panel.style.flexBasis = Math.max(240,Math.min(720,act.w+delta))+"px";
  });
  asa.addEventListener("pointerup",e=>{
    act = null; asa.releasePointerCapture(e.pointerId);
    panel.style.transition = ""; document.body.style.userSelect = "";
  });
}
redimensionable("asaIzq","izq","izq");
redimensionable("asaDer","der","der");

/* ============================================================ ficha ======== */
function tabla(pares){
  const filas = pares.filter(x=>x[1]!==""&&x[1]!=null);
  if(!filas.length) return "";
  return "<table>"+filas.map(([k,v])=>
    "<tr><td>"+esc(k)+"</td><td class='mono'>"+esc(v)+"</td></tr>").join("")+"</table>";
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
function chipOrigen(a){
  return '<span class="chip '+({observada:"",derivada:"cy",inferida:"am"})[a.origen]+'">'+
    esc(a.origenLegible)+'</span>';
}
function cadenaHTML(ids, destacado){
  return '<div class="cadena">'+ids.map(id=>{
    const n = NODOS.get(id)||{};
    const txt = esc(n.etiqueta||id);
    return id===destacado ? "<b>"+txt+"</b>" :
      '<span class="chip boton" onclick="irANodo(\''+id+'\')">'+txt+'</span>';
  }).join('<span class="fl">→</span>')+'</div>';
}
function ficha(html){
  document.getElementById("cuerpo").innerHTML = html;
  document.getElementById("der").classList.remove("plegado");
  document.getElementById("plegDer").textContent = "›";
  document.getElementById("der").scrollTop = 0;
}

function pintarInicio(){
  const c = casoActual();
  if(!c){ ficha('<div class="vacio">No hay casos para mostrar.</div>'); return; }
  const vinc = vinculosDelCaso().slice().sort((a,b)=>(b.confianza||0)-(a.confianza||0));
  const otros = CASOS.length-1;
  const compartidos = D.nodos.filter(n=>enElCaso(n.id) && esCompartido(n.id));

  let h = '<div class="sub" style="font-family:inherit;font-size:11px;'+
    'text-transform:uppercase;letter-spacing:.14em;color:var(--cyan)">Caso en curso</div>'+
    '<h1 style="margin:2px 0 6px">'+esc(c.etiqueta)+'</h1>'+
    '<div class="prosa"><p>Se muestran únicamente las relaciones de este caso. '+
    'El archivo general tiene '+D.meta.reportes+' reportes en '+CASOS.length+
    ' casos'+(otros>0? '; los otros '+otros+' no se dibujan hasta que se los '+
    'elija en el selector de arriba':'')+'.</p></div>';

  h += '<h2>Reportes del caso</h2>';
  c.reportes.forEach(rid=>{
    const n = NODOS.get("REPORTE::"+rid.toLowerCase());
    if(!n) return;
    const at = Object.fromEntries(n.atributos);
    h += '<div class="tarjeta click" onclick="irANodo(\''+n.id+'\')">'+
      '<div style="font-size:12.5px"><b>Reporte '+esc(rid)+'</b>'+
      (estado.foco===n.id? ' <span class="chip cy">en curso</span>':'')+'</div>'+
      '<div style="color:var(--tenue);font-size:11.5px;margin-top:3px">'+
      esc([at["Plataforma"], legible(at["Estado en SIPAR"]),
           legible(at["Motivo del archivo"])].filter(Boolean).join(" · "))+
      '</div></div>';
  });

  if(vinc.length){
    h += '<h2>Cómo se conectan entre sí</h2>'+
      '<div class="prosa"><p style="font-size:12px;color:var(--tenue)">Clic en '+
      'cualquiera para ver la cadena completa que une a los dos reportes.</p></div>';
    vinc.forEach(a=>{
      h += '<div class="tarjeta click" onclick="irAPorQue(\''+a.id+'\')">'+
        chipPeso(a.confianza)+(a.relacion==="POSIBLE_DUPLICADO_DE"?
          '<span class="chip am">posible duplicado</span>':'')+
        '<div style="margin-top:4px;font-size:12.5px"><b>'+esc(etq(a.a))+'</b>'+
        ' <span style="color:var(--cyan)">'+esc(a.relacionLegible)+'</span> <b>'+
        esc(etq(a.b))+'</b></div>'+
        '<div style="color:var(--tenue);font-size:11.5px;margin-top:3px">por '+
        ((a.puente||[]).filter(x=>x.sostiene).map(x=>esc(x.tipo.toLowerCase()))
          .join(", ")||"—")+'</div></div>';
    });
  } else {
    h += '<h2>Vinculaciones</h2><div class="vacio">Este reporte no quedó '+
      'vinculado con ningún otro.</div>';
  }

  if(compartidos.length){
    h += '<h2>Datos que se repiten en el caso</h2>'+
      '<div class="prosa"><p style="font-size:12px;color:var(--tenue)">Aparecen '+
      'en más de un reporte. Son los que sostienen las vinculaciones.</p></div>';
    compartidos.sort((a,b)=>(b.reportes||[]).length-(a.reportes||[]).length)
      .forEach(n=>{
      h += '<div class="tarjeta click" onclick="irANodo(\''+n.id+'\')">'+
        '<span class="chip">'+esc(n.tipoLegible)+'</span>'+
        '<div style="margin-top:3px;font-size:12.5px"><b>'+esc(n.etiqueta)+'</b></div>'+
        '<div style="color:var(--tenue);font-size:11.5px;margin-top:3px">en los '+
        'reportes '+esc((n.reportes||[]).filter(r=>reportesDelCaso().has(r)).join(", "))+
        '</div></div>';
    });
  }

  const alertasCaso = D.alertas.filter(a=>reportesDelCaso().has(a.reporte_archivado));
  if(alertasCaso.length){
    h += '<h2>Antecedentes a revisar en este caso</h2>';
    alertasCaso.forEach(al=>{
      h += '<div class="tarjeta click" onclick="irAPorQue(\''+al.arista_id+'\')">'+
        '<span class="chip '+(al.prioridad==="alta"?"am":"cy")+'"><span class="pt">'+
        '</span>'+esc(al.prioridad)+'</span>'+
        '<div style="margin-top:4px;font-size:12.5px">Reporte <b>'+
        esc(al.reporte_archivado)+'</b> archivado, lo reactiva el '+
        esc(al.reporte_disparador)+'</div></div>';
    });
  }
  ficha(h);
}

function pintarPorQue(id){
  const a = ARISTAS.get(id);
  if(!a){ pintarInicio(); return; }
  const sost = (a.puente||[]).filter(x=>x.sostiene);
  const corr = (a.puente||[]).filter(x=>!x.sostiene);
  let h = '<h1>Por qué se vinculan</h1>'+
    '<div style="font-size:13px;margin-bottom:8px"><b>'+esc(etq(a.a))+'</b>'+
    ' <span style="color:var(--tenue)">y</span> <b>'+esc(etq(a.b))+'</b></div>'+
    chipPeso(a.confianza)+chipOrigen(a)+
    '<span class="chip'+(a.estado==="validada"?" ok":a.estado==="rechazada"?" al":"")+'">'+
    esc(a.estadoLegible)+'</span>';

  if(sost.length){
    h += '<h2>Lo que sostiene la vinculación</h2>';
    sost.forEach(p=>{
      h += '<div class="tarjeta cyan">'+chipPeso(p.peso)+
        '<div style="font-size:12.5px;margin:2px 0 8px"><b>'+esc(p.tipo)+'</b> '+
        '<span class="chip boton" onclick="irANodo(\''+p.nodo+'\')">'+esc(p.valor)+'</span></div>'+
        '<div style="font-size:11px;color:var(--tenue);margin-bottom:2px">Cómo llega desde '+
        esc(etq(a.a))+'</div>'+cadenaHTML(p.camino_a, p.nodo)+
        '<div style="font-size:11px;color:var(--tenue);margin:6px 0 2px">Cómo llega desde '+
        esc(etq(a.b))+'</div>'+cadenaHTML(p.camino_b, p.nodo)+'</div>';
    });
  }
  if(corr.length){
    h += '<h2>Lo que solo refuerza</h2>'+
      '<div class="prosa"><p style="font-size:12px;color:var(--tenue)">Estos elementos '+
      'coinciden, pero no alcanzan por sí solos para vincular dos reportes.</p></div>';
    corr.forEach(p=>{
      h += '<div class="tarjeta">'+chipPeso(p.peso)+
        '<div style="font-size:12.5px;margin-top:2px"><b>'+esc(p.tipo)+'</b> '+
        '<span class="chip boton" onclick="irANodo(\''+p.nodo+'\')">'+esc(p.valor)+'</span></div>'+
        '</div>';
    });
  }
  if(a.explicacion) h += '<h2>Fundamento</h2>'+prosa(a.explicacion);
  h += '<h2>De dónde surge</h2>'+tabla([
    ["Método",a.metodo], ["Evidencia de origen",a.fuente],
    ["Revisada por",a.validado_por||"sin revisar"],
    ["Identificador",a.id]]);
  h += '<div class="fila"><button onclick="irAArista(\''+a.id+'\')">Ver la relación en detalle</button></div>';
  ficha(h);
}

function pintarNodo(id){
  if(!id || !NODOS.has(id)){ pintarInicio(); return; }
  const n = NODOS.get(id);
  const rel = D.aristas.filter(a=>a.a===id||a.b===id);
  const conRep = rel.filter(a=>a.entreReportes);
  const otras = rel.filter(a=>!a.entreReportes);
  let h = '<span class="chip cy">'+esc(n.tipoLegible)+'</span><h3>'+esc(n.etiqueta||"")+'</h3>';

  if(conRep.length){
    h += '<h2>Se vincula con ('+conRep.length+')</h2>';
    conRep.sort((a,b)=>(b.confianza||0)-(a.confianza||0)).forEach(a=>{
      const otro = a.a===id?a.b:a.a;
      h += '<div class="tarjeta click" onclick="irAPorQue(\''+a.id+'\')">'+
        chipPeso(a.confianza)+
        '<div style="margin-top:4px;font-size:12.5px"><b>'+esc(etq(otro))+'</b></div>'+
        '<div style="color:var(--tenue);font-size:11.5px;margin-top:3px">por '+
        ((a.puente||[]).filter(x=>x.sostiene).map(x=>esc(x.tipo.toLowerCase())).join(", ")||"—")+
        ' · clic para ver por qué</div></div>';
    });
  }
  h += '<h2>Datos</h2>'+tabla(n.atributos);
  if(n.transcripciones&&n.transcripciones.length){
    h += '<h2>Texto restringido</h2><div class="prosa"><p>Este hecho tiene '+
      n.transcripciones.length+' transcripción(es) que no se incorporan al grafo. '+
      'Se conservan aparte, por hash, en <span class="cita">salida/textos_restringidos.json</span>.</p></div>';
  }
  if(otras.length){
    h += '<h2>Otras relaciones ('+otras.length+')</h2>';
    otras.forEach(a=>{
      const otro = a.a===id?a.b:a.a, inv = a.a!==id;
      h += '<div class="tarjeta click'+(a.relacion==="CONTRADICE"?" alarma":"")+
        '" onclick="irAArista(\''+a.id+'\')">'+chipOrigen(a)+
        '<div style="margin-top:4px;font-size:12.5px">'+
        (inv ? '<span style="color:var(--tenue)">'+esc(etq(otro))+'</span> '+esc(a.relacionLegible)+' <b>esta entidad</b>'
             : '<b>Esta entidad</b> '+esc(a.relacionLegible)+' <span style="color:var(--tenue)">'+esc(etq(otro))+'</span>')+
        '</div></div>';
    });
  }
  ficha(h);
}

function pintarArista(id){
  const a = ARISTAS.get(id);
  if(!a){ pintarInicio(); return; }
  let h = chipOrigen(a)+chipPeso(a.confianza)+
    '<span class="chip'+(a.estado==="validada"?" ok":a.estado==="rechazada"?" al":"")+'">'+
    esc(a.estadoLegible)+'</span>'+
    '<h3>'+esc(etq(a.a))+' <span style="color:var(--cyan);font-weight:400">'+
    esc(a.relacionLegible)+'</span> '+esc(etq(a.b))+'</h3>'+
    '<div style="font-size:11.5px;color:var(--tenue)">'+esc(a.origenDesc)+'</div>'+
    '<div class="fila">'+
    '<button onclick="irANodo(\''+a.a+'\')">'+esc(etq(a.a))+'</button>'+
    '<button onclick="irANodo(\''+a.b+'\')">'+esc(etq(a.b))+'</button></div>';
  if(a.entreReportes) h += '<div class="fila"><button onclick="irAPorQue(\''+a.id+'\')">Ver por qué se vinculan</button></div>';
  if(a.explicacion) h += '<h2>Fundamento</h2>'+prosa(a.explicacion);
  h += '<h2>De dónde surge</h2>'+tabla([
    ["Evidencia de origen",a.fuente], ["Ubicación exacta en la fuente",a.locator],
    ["Método",a.metodo], ["Fecha del hecho observado",a.observado||"no informada"],
    ["Revisada por",a.validado_por||"sin revisar"],
    ["Fecha de la revisión",a.validado_en||""], ["Vigente",a.vigente?"sí":"no"],
    ["Rol",a.rol||""], ["Puerto de origen",a.puerto||""], ["Identificador",a.id]]);
  if(a.origen!=="observada"){
    h += '<h2>Registrar una decisión</h2>'+
      '<div class="cita">python validar.py '+esc(a.id)+' validada --usuario SU_USUARIO</div>';
  }
  ficha(h);
}

/* =============================================================== informe ==== */
function markdown(texto){
  const L = texto.split("\n"); let out = [], enTabla = false, enLista = false;
  const inline = s => esc(s)
    .replace(/\*\*(.+?)\*\*/g,"<b>$1</b>")
    .replace(/`(.+?)`/g,'<code style="font-family:var(--mono);font-size:11.5px">$1</code>')
    .replace(/\*(.+?)\*/g,"<i>$1</i>");
  const cerrar = ()=>{ if(enTabla){out.push("</table>");enTabla=false;} if(enLista){out.push("</ul>");enLista=false;} };
  L.forEach(l=>{
    if(/^\s*\|/.test(l)){
      if(/^\s*\|[\s:|-]+\|\s*$/.test(l)) return;
      const c = l.trim().replace(/^\||\|$/g,"").split("|").map(x=>inline(x.trim()));
      if(enLista){out.push("</ul>");enLista=false;}
      if(!enTabla){ out.push("<table>"); enTabla = true; }
      out.push("<tr>"+c.map(x=>"<td>"+x+"</td>").join("")+"</tr>"); return;
    }
    if(/^\s*[-*]\s/.test(l)){
      if(enTabla){out.push("</table>");enTabla=false;}
      if(!enLista){ out.push("<ul style='margin:6px 0 10px;padding-left:18px'>"); enLista = true; }
      out.push("<li>"+inline(l.replace(/^\s*[-*]\s/,""))+"</li>"); return;
    }
    cerrar();
    if(/^###\s/.test(l)) out.push("<h3>"+inline(l.slice(4))+"</h3>");
    else if(/^##\s/.test(l)) out.push("<h2>"+inline(l.slice(3))+"</h2>");
    else if(/^#\s/.test(l)) out.push("<h1>"+inline(l.slice(2))+"</h1>");
    else if(/^>\s?/.test(l)) out.push('<p style="color:var(--tenue)">'+inline(l.replace(/^>\s?/,""))+"</p>");
    else if(l.trim()) out.push("<p>"+inline(l)+"</p>");
  });
  cerrar();
  return '<div class="prosa">'+out.join("")+"</div>";
}
function pintarInforme(){
  const t = (D.informe||{}).texto || "";
  if(!t){ ficha('<h1>Informe</h1><div class="vacio">No se generó el informe en esta corrida.</div>'); return; }
  ficha('<div class="fila"><button onclick="descargarInforme()">Descargar .md</button>'+
    '<button onclick="irAInicio()">Volver</button></div>'+markdown(t)+
    '<h2>Versión redactada por IA</h2><div class="prosa"><p>Este informe se genera '+
    'con plantillas, sin depender de ningún modelo. Para una redacción más fluida, '+
    'cuando haya un modelo local disponible:</p></div>'+
    '<div class="cita">python informe_ia.py</div>');
}
function descargarInforme(){
  const b = new Blob([(D.informe||{}).texto||""],{type:"text/markdown;charset=utf-8"});
  const u = URL.createObjectURL(b), a = document.createElement("a");
  a.href = u; a.download = "informe_vinculaciones.md"; a.click();
  setTimeout(()=>URL.revokeObjectURL(u),1000);
}
window.descargarInforme = descargarInforme;
document.getElementById("btnInforme").onclick = ()=>ir({tipo:"informe"});

/* ============================================================ pan y zoom ==== */
const svg = document.getElementById("lienzo"), vista = document.getElementById("vista");
let T = {x:0,y:0,k:1}, arr = null;
function pintarVista(){ vista.setAttribute("transform","translate("+T.x+","+T.y+") scale("+T.k+")"); }
svg.addEventListener("wheel",e=>{
  e.preventDefault();
  const r = svg.getBoundingClientRect();
  const sx = (e.clientX-r.left)/r.width*ANCHO, sy = (e.clientY-r.top)/r.height*ALTO;
  const f = e.deltaY<0 ? 1.14 : 1/1.14, k2 = Math.max(0.25,Math.min(6,T.k*f));
  T.x = sx-(sx-T.x)*(k2/T.k); T.y = sy-(sy-T.y)*(k2/T.k); T.k = k2; pintarVista();
},{passive:false});
svg.addEventListener("pointerdown",e=>{
  arr = {x:e.clientX,y:e.clientY,tx:T.x,ty:T.y,movido:false};
  svg.classList.add("arrastrandoLienzo");
});
window.addEventListener("pointermove",e=>{
  if(!arr) return;
  const r = svg.getBoundingClientRect();
  T.x = arr.tx+(e.clientX-arr.x)/r.width*ANCHO;
  T.y = arr.ty+(e.clientY-arr.y)/r.height*ALTO;
  if(Math.abs(e.clientX-arr.x)>3||Math.abs(e.clientY-arr.y)>3) arr.movido = true;
  pintarVista();
});
window.addEventListener("pointerup",()=>{
  if(arr && !arr.movido && estado.vista.tipo!=="inicio") ir({tipo:"inicio"});
  arr = null; svg.classList.remove("arrastrandoLienzo");
});

pintarPos();
document.getElementById("reorganizar").textContent = "Vista: En secuencia";
if(CASOS.length) cambiarCaso(CASOS[0].id); else ir({tipo:"inicio"});
bucle();
</script></body></html>
"""


def render(g, res, ruta, dossier=None, texto_informe=None):
    datos = _datos(g, res, dossier, texto_informe)
    html = (PLANTILLA
            .replace("__DATOS__", json.dumps(datos, ensure_ascii=False, default=str))
            .replace("__ANCHO__", str(ANCHO))
            .replace("__ALTO__", str(ALTO)))
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(html)
    return ruta
