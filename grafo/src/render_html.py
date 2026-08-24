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
#
# Quedan afuera la mencion de persona y el chat, que son estructura interna del
# reporte y no son aquello que el operador esta buscando.
#
# Tambien queda afuera IDENTIDAD. Una identidad unificada no es un dato del
# reporte sino una conclusion sobre una persona, que un operador aprobo *porque*
# dos reportes comparten una cuenta. Dibujarla en la fila de datos la haria
# competir con la cuenta que la origino y se leeria como si fuera una segunda
# coincidencia independiente. Se muestra como distintivo sobre los reportes que
# agrupa y se explica en la ficha.
TIPOS_EN_TARJETA = ("CUENTA", "ALIAS", "TELEFONO", "EMAIL", "IP",
                    "DISPOSITIVO", "EVIDENCIA", "UBICACION")

# Color de cada tipo de dato en el lienzo. La ontologia declara un color
# institucional pensado para papel; sobre fondo oscuro varios de esos tonos no
# se distinguen. Esta es la variante de pantalla, y es el unico criterio de
# color del visor: un tipo de dato, un color, en la barra de la caja y en la
# linea que lo vincula con los otros reportes.
COLOR_VISOR = {
    "CUENTA": "#fb923c",
    "ALIAS": "#fdba74",
    "EMAIL": "#38bdf8",
    "TELEFONO": "#2dd4bf",
    "IP": "#4ade80",
    "DISPOSITIVO": "#c084fc",
    "EVIDENCIA": "#cbd5e1",
    "UBICACION": "#fbbf24",
    "IDENTIDAD": "#818cf8",
    "PERSONA_MENCION": "#818cf8",
    "ORGANIZACION": "#94a3b8",
    "REPORTE": "#38bdf8",
    "EVENTO": "#7dd3fc",
}

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


def casos_de(g, res):
    """Los casos del visor, expuestos para que construir.py pueda redactar un
    informe por cada uno. Es la misma lista que ve el operador en el selector."""
    return _casos(g, res, {})


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
            colorVisor=COLOR_VISOR.get(d.get("tipo"), "#8fa1bb"),
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
        if d["relation_type"] == "VINCULADO_POR_OPERADOR":
            # No hay dato compartido que mostrar: la vinculacion es la decision.
            motivo = u"lo vinculó un operador"
        else:
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
                                                 "POSIBLE_DUPLICADO_DE",
                                                 "VINCULADO_POR_OPERADOR"),
            dispuestaPor=d.get("dispuesta_por"),
            motivoOperador=d.get("motivo_operador"),
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
                       colorVisor=COLOR_VISOR.get(t, "#8fa1bb"),
                       enTarjeta=(t in TIPOS_EN_TARJETA),
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
        # Coincidencias que NO alcanzaron para vincular. Sin esto el visor no
        # puede explicar por que dos reportes que comparten un dato aparecen
        # separados, y la ausencia de linea se lee como una falla del sistema.
        descartados=[dict(
            a=x["reporte_a"], b=x["reporte_b"],
            confianza=x.get("confianza"), motivo=x.get("motivo"),
            compartido=[dict(
                nodo=d.get("nodo"),
                tipo=ont.ETIQUETA_TIPO.get(d.get("tipo"), d.get("tipo")),
                valor=d.get("valor"),
                sostiene=not d.get("corrobora_solamente"),
                texto=d.get("nota"))
                for d in (x.get("disparos") or [])])
            for x in res.get("vinculacion", {}).get("descartados", [])],
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

#izq{flex:0 0 300px;background:var(--panel);border:1px solid var(--borde);
  border-radius:14px;margin:10px 0 10px 10px;overflow-y:auto;position:relative;
  transition:flex-basis .3s cubic-bezier(.4,0,.2,1)}
#izq.plegado{flex-basis:44px}
#izq.plegado .contenido{display:none}
#izq .contenido{padding:42px 18px 26px 18px}
#izq .plegar{left:auto;right:10px}
#izq.plegado .plegar{right:9px}
#izq label{display:flex;align-items:center;gap:7px;font-size:12px;
  color:var(--suave);margin:5px 0;cursor:pointer;line-height:1.35}
#izq label:hover{color:var(--texto)}
#izq input[type=checkbox]{accent-color:#22d3ee;margin:0;flex:0 0 auto}
#izq input[type=range]{accent-color:#22d3ee}
.sw{width:11px;height:11px;border-radius:3px;flex:0 0 auto;display:inline-block}
.rotuloGrupo{font-size:10.5px;color:var(--tenue);margin:14px 0 4px;
  text-transform:uppercase;letter-spacing:.1em}
.trazo{display:inline-block;width:26px;height:0;vertical-align:middle;
  margin-right:8px;border-top-width:2px;flex:0 0 auto}
#centro{flex:1;min-width:280px;position:relative;margin:10px 0;
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
.caja{cursor:grab}
.caja.moviendo{cursor:grabbing}
.caja.movida rect.cuerpo{filter:drop-shadow(0 3px 7px rgba(0,0,0,.55))}
.caja rect.cuerpo{fill:#0e1728;stroke:#3a4f70;stroke-width:1.5;rx:7;
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
/* El orden importa: realzada gana sobre raiz, y apagada gana sobre todo. Con
   la misma especificidad manda la última, y una caja filtrada que se siga
   viendo encendida es exactamente el error de §5.4 del traspaso. */
.caja.realzada rect.cuerpo{stroke:#fff;stroke-width:2.2}
.caja.apagada{opacity:.16}
.caja.apagada rect.cuerpo{stroke:#22314c;stroke-width:1.4}

.mas{cursor:pointer}
.mas.apagada{opacity:.16}
.mas circle{fill:#0d1626;stroke:var(--ambar);stroke-width:1.4;transition:fill .18s}
.mas:hover circle{fill:rgba(251,191,36,.25)}
.mas path{stroke:var(--ambar);stroke-width:1.6;stroke-linecap:round}

/* --- conectores --------------------------------------------------------
   Criterio unico, y no se mezcla:
     el TRAZO dice como se obtuvo la relacion  -> lleno: consta en la fuente;
       rayado: derivada por una regla; punteado: hipotesis a validar.
     el COLOR dice de que tipo de dato se trata (COLOR_VISOR).
     el GROSOR de una vinculacion acompana su peso.
   Ver la leyenda del panel izquierdo. */
.con{fill:none;stroke:#3d5070;stroke-width:1.5;
  transition:stroke .18s,stroke-width .18s,opacity .18s}
.con.vinculo{stroke:#22d3ee;stroke-width:2;stroke-dasharray:11 5}
/* El duplicado NO va en ámbar: el ámbar es el color del tipo de dato
   "ubicación", y una línea entre reportes con color de dato rompe el criterio
   -se contaba como una línea de Monte Grande-. Queda en el cian de las
   vinculaciones, con la raya más corta, y lo dice el rótulo con todas las
   letras. */
.con.duplicado{stroke-dasharray:4 4}
.con.inferida{stroke:#a78bfa;stroke-width:1.8;stroke-dasharray:2 4}
/* La afirmada por una persona: raya y punto, el trazo con el que se marca a
   mano un plano. No lleva peso porque no hay nada calculado. */
.con.afirmada{stroke:#7dd3fc;stroke-width:2.6;stroke-dasharray:14 4 3 4}
.con.cruce{stroke-width:1.7;opacity:.72}
.con.realzada{opacity:1;stroke-width:2.8;filter:drop-shadow(0 0 4px currentColor)}
.con.origen{stroke-width:0}
.con.origen.realzada{stroke-width:0}
.con.apagada{opacity:.08}
.con.sel{stroke:#fff;stroke-width:3;opacity:1}
.zona{stroke:transparent;stroke-width:16;fill:none;cursor:pointer}
.rotulo{font-size:10px;font-family:var(--mono);fill:#8fa1bb;text-anchor:middle;
  pointer-events:none;paint-order:stroke;stroke:#080d17;stroke-width:4;
  stroke-linejoin:round}
.rotulo.vinculo{fill:#a5d8e8}
.rotulo.peso{fill:#6ee7b7}
.rotulo.apagado{opacity:.2}

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

<aside id="izq">
  <button class="plegar" id="plegIzq" title="Plegar los filtros">‹</button>
  <div class="contenido">
    <h1>Vinculaciones</h1>
    <div class="sub" id="meta"></div>

    <h2>Buscar en el caso</h2>
    <input type="text" id="buscar" placeholder="cuenta, IP, dispositivo, alias...">

    <h2>Antecedentes a revisar</h2>
    <div id="alertas"></div>

    <h2>Qué se muestra</h2>
    <div class="rotuloGrupo">Peso mínimo de la vinculación</div>
    <div class="fila">
      <input type="range" id="peso" min="0" max="100" value="0" style="flex:1">
      <span class="sub" id="pesov" style="min-width:34px;text-align:right">0,00</span>
    </div>
    <label><input type="checkbox" id="verPesos">
      Escribir el peso sobre la línea</label>
    <label><input type="checkbox" id="soloComp">
      Solo los datos que comparte con otro reporte</label>

    <div class="rotuloGrupo">Tipos de dato</div>
    <div id="tipos"></div>

    <h2>Cómo leer el lienzo</h2>
    <div class="rotuloGrupo" style="margin-top:4px">El trazo dice de dónde sale</div>
    <div id="leyenda"></div>

    <div class="tarjeta cyan" style="margin-top:18px">
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
    <select id="selCaso" title="Caso en curso"></select>
    <button class="solo" id="contraer">Contraer</button>
    <button class="solo" id="ordenar" title="Devolver las cajas que moviste a su lugar">Ordenar</button>
    <button class="solo" id="ajustar" title="Encuadrar">Encuadrar</button>
    <button class="solo primario" id="btnInforme">Informe</button>
    <button class="solo" id="centrado" style="display:none"
            title="Volver al reporte en análisis"></button>
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
/* En la caja el estado va corto. La frase entera está en la ficha y en el
   globo de ayuda: dentro del recuadro solo entra una línea. */
const BREVE = {
  sin_datos_de_usuario:"archivado · sin datos de usuario",
  no_atribuible_nat:"archivado · IP no atribuible",
  sin_archivos:"archivado · sin archivos",
  sin_ubicacion:"archivado · sin ubicación",
  material_sin_relevancia:"archivado · sin relevancia",
  archivado_latente:"archivado de forma latente"};
const breve = v => v ? (BREVE[v] || legible(v)) : v;
const attr = n => Object.fromEntries((n.atributos||[]));

/* Tipos de dato que pueden aparecer en la fila de datos, en el orden en que se
   ofrecen en el panel. Sale de la ontologia, no de una lista escrita a mano. */
const TIPOS_DATO = Object.keys(D.tipos||{}).filter(t=>D.tipos[t].enTarjeta);
const COLOR_TIPO = t => (D.tipos[t]||{}).colorVisor || "#8fa1bb";
const NOMBRE_TIPO = t => (D.tipos[t]||{}).legible || t;

const estado = {caso:null, raiz:null, abiertos:new Set(), sel:null,
                texto:"", pesoMin:0, verPesos:false, soloCompartidos:false,
                tipos:new Set(TIPOS_DATO), mov:new Map(), centro:null};

/* =============================================================== caso ===== */
function caso(){ return CASOS.find(c=>c.id===estado.caso) || CASOS[0]; }
function reportesCaso(){ return new Set(caso() ? caso().reportes : []); }
function nodoReporte(valor){ return NODOS.get("REPORTE::"+String(valor).toLowerCase()); }
function vinculosDe(idReporte){
  return VINCULOS.filter(a=>a.a===idReporte||a.b===idReporte)
    .filter(a=>{ const rs=reportesCaso();
      return rs.has((NODOS.get(a.a)||{}).valor) && rs.has((NODOS.get(a.b)||{}).valor); })
    .filter(a=>(a.confianza==null || a.confianza>=estado.pesoMin));
}
/* Datos por los que un reporte puede vincularse. Se dejan afuera la mención de
   persona y el chat: son estructura interna del reporte, no aquello que el
   operador está buscando. Tampoco entra la identidad unificada, que es una
   conclusión sobre una persona y no un dato del reporte. */
function datosDe(valorReporte){
  return D.nodos.filter(n => n.enTarjeta
                          && (n.reportes||[]).includes(valorReporte)
                          && RE(n.id) === n.id)
                .filter(n => estado.tipos.has(n.tipo))
                .filter(n => !estado.soloCompartidos || otrosReportesDe(n).length>1);
}
function otrosReportesDe(nodo){
  const rs = reportesCaso();
  return (nodo.reportes||[]).filter(r=>rs.has(r));
}
/* El mismo dato en reportes de otros casos. Que no haya línea significa que la
   coincidencia no alcanzó para vincular, no que el sistema no la haya visto:
   sin decirlo, la ausencia de línea se lee como un error. */
function fueraDelCaso(nodo){
  const rs = reportesCaso();
  return (nodo.reportes||[]).filter(r=>!rs.has(r));
}
const DESCARTADOS = D.descartados || [];
function descartadosDelDato(id){
  return DESCARTADOS.filter(x=>(x.compartido||[]).some(c=>c.nodo && RE(c.nodo)===id));
}
function descartadosDelReporte(valor){
  return DESCARTADOS.filter(x=>x.a===valor || x.b===valor);
}
function casoDe(valorReporte){
  return CASOS.find(c=>c.reportes.includes(valorReporte));
}
/* El visor es un archivo suelto: no tiene con quién hablar ni sesión de
   usuario, así que no puede escribir en el libro. Lo que sí puede es dejar el
   comando exacto listo para copiar, con los dos reportes ya puestos. */
function copiable(cmd){
  return '<div class="cita" style="margin-top:6px">'+esc(cmd)+'</div>'+
    '<div class="fila"><button data-accion="copiar" data-cmd="'+esc(cmd)+
    '">Copiar el comando</button></div>';
}

/* Tarjeta de una coincidencia que se evaluó y no prosperó. */
function tarjetaDescartada(x, idDato){
  const c = (x.compartido||[]).find(y=>y.nodo && RE(y.nodo)===idDato);
  const cuales = (x.compartido||[]).map(y=>y.valor).filter(Boolean);
  return '<div class="tarjeta">'+
    '<div style="font-size:12.5px"><b>Reporte '+esc(x.a)+'</b> y <b>Reporte '+
    esc(x.b)+'</b></div>'+
    '<div style="font-size:12px;color:var(--suave);margin-top:5px">'+
    esc(c ? c.texto : ("Comparten "+cuales.join(", ")+"."))+'</div>'+
    '<div style="font-size:12px;color:var(--tenue);margin-top:6px">'+
    esc(x.motivo||"")+'</div></div>';
}
/* Identidad que un operador confirmó, si alcanza a este reporte. No se dibuja
   como dato: se muestra como distintivo sobre los reportes que agrupa. */
const IDENTIDADES = D.nodos.filter(n=>n.tipo==="IDENTIDAD");
function identidadDe(valorReporte){
  return IDENTIDADES.find(n=>(n.reportes||[]).includes(valorReporte)) || null;
}
/* La búsqueda no oculta: apaga. Lo que no coincide se atenúa y sigue en su
   lugar, para no perder la forma del caso mientras se busca. */
function coincide(nodo){
  const t = estado.texto.trim().toLowerCase();
  if(!t) return true;
  const blob = (nodo.etiqueta+" "+nodo.tipoLegible+" "+
    (nodo.atributos||[]).map(x=>x[1]).join(" ")).toLowerCase();
  return blob.includes(t);
}

/* ========================================================== navegación ==== */
const HIST = {pila:[], pos:-1};
/* Volver a tocar lo que ya estaba elegido suelta el realce y devuelve el caso
   completo. Sin esto, la única forma de recuperar la vista era cambiar de caso:
   el clic apagaba todo y no había cómo volver a encenderlo. */
function alternarFoco(v){
  const a = estado.sel;
  if(a && a.tipo===v.tipo && a.id===v.id) ir({tipo:"inicio"});
  else ir(v);
}
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
const ANCHO_CAJA = 250, ALTO_CAJA = 64, SEP_X = 34;
const Y_RAIZ = 90, Y_REL = 290, Y_ENT = 500;
/* Altura a la que corre el tramo horizontal del que cuelgan los reportes
   vinculados. Deja libre la franja donde se escribe el motivo de cada rama. */
const CARRIL_VINC = Y_RAIZ + ALTO_CAJA + 36;

let VP = {x:0,y:0,k:1};
function pintarVP(){ document.getElementById("vista")
  .setAttribute("transform","translate("+VP.x+","+VP.y+") scale("+VP.k+")"); }

/* Recorta un texto al ancho que efectivamente queda libre, midiendo lo que
   ocupa dibujado. Truncar por cantidad de caracteres no alcanza: con la misma
   cantidad de letras "181.46.66.242" y "Identidad unificada" no ocupan lo
   mismo, y el recorte fijo dejaba el título pisando la marca de la derecha.

   Medir obliga al navegador a recalcular la disposición, y el lienzo se
   redibuja entero en cada paso de un arrastre. Por eso lo medido se guarda:
   la misma letra, del mismo tamaño, mide siempre lo mismo. */
const MEDIDAS = new Map();
function medir(el, texto){
  const k = el.getAttribute("class")+"|"+texto;
  if(MEDIDAS.has(k)) return MEDIDAS.get(k);
  el.textContent = texto;
  const w = el.getComputedTextLength();
  MEDIDAS.set(k, w);
  return w;
}
function ajustar(el, texto, ancho){
  const s = String(texto == null ? "" : texto);
  if(ancho <= 0){ el.textContent = "…"; return; }
  if(medir(el, s) <= ancho){ el.textContent = s; return; }
  let lo = 0, hi = s.length;
  while(lo < hi){
    const m = Math.ceil((lo+hi)/2);
    if(medir(el, s.slice(0,m)+"…") <= ancho) lo = m; else hi = m-1;
  }
  el.textContent = lo ? s.slice(0,lo)+"…" : "…";
}

/* Una caja tiene tres textos y ninguno puede pisar a otro:
     título  arriba a la izquierda; es lo que identifica la caja y manda.
     marca   arriba a la derecha, con lo que sobre después del título. Si no
             entra escrita, se reduce a un punto del color que le corresponde
             y el texto queda en el globo de ayuda: preferible perder la marca
             antes que recortar el número de reporte.
     sub     abajo, a lo ancho de la caja. */
function caja(g, x, y, {titulo, sub, marca, marcaColor, color, clases, alClic}){
  const el = document.createElementNS(SVGNS,"g");
  el.setAttribute("class","caja "+(clases||""));
  el.setAttribute("transform","translate("+x+","+y+")");
  g.appendChild(el);                 // medir exige estar en el documento
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
  t.setAttribute("y", sub ? 24 : ALTO_CAJA/2);
  el.appendChild(t);
  const libre = ANCHO_CAJA - 26 - medir(t, String(titulo)) - 12;
  if(marca){
    const m = document.createElementNS(SVGNS,"text");
    m.setAttribute("class","marca"); m.setAttribute("x",ANCHO_CAJA-12);
    m.setAttribute("y",24);
    if(marcaColor) m.setAttribute("fill",marcaColor);
    el.appendChild(m);
    const anchoMarca = medir(m, marca);
    if(anchoMarca > libre){
      el.removeChild(m);
      const pt = document.createElementNS(SVGNS,"circle");
      pt.setAttribute("cx",ANCHO_CAJA-14); pt.setAttribute("cy",21);
      pt.setAttribute("r",4);
      pt.setAttribute("fill",marcaColor||"#fbbf24"); el.appendChild(pt);
      ajustar(t, titulo, ANCHO_CAJA - 26 - 16);
    } else {
      ajustar(t, titulo, ANCHO_CAJA - 26 - anchoMarca - 12);
    }
  } else {
    ajustar(t, titulo, ANCHO_CAJA - 26);
  }
  if(sub){
    const s2 = document.createElementNS(SVGNS,"text");
    s2.setAttribute("class","sub"); s2.setAttribute("x",13);
    s2.setAttribute("y",45);
    el.appendChild(s2);
    ajustar(s2, sub, ANCHO_CAJA - 26);
  }
  const ti = document.createElementNS(SVGNS,"title");
  ti.textContent = titulo + (sub? "  ·  "+sub : "") + (marca? "  ·  "+marca : "");
  el.appendChild(ti);
  if(alClic) el.addEventListener("click", e=>{
    e.stopPropagation();
    if(SEARRASTRO){ SEARRASTRO = false; return; }   // soltar no es hacer clic
    alClic();
  });
  return el;
}

/* Cada caja se puede correr a mano. La disposición automática ordena el caso,
   pero cuando dos ramas se cruzan el operador necesita poder separarlas para
   entender qué está mirando. Los conectores se recalculan solos porque salen
   de la posición, no de un dibujo guardado. */
let SEARRASTRO = false;
function arrastrable(el, id){
  el.addEventListener("pointerdown", e=>{
    if(e.button!==0) return;
    e.stopPropagation();                       // no arrastra el lienzo entero
    SEARRASTRO = false;                        // cada gesto arranca limpio
    const p0 = {x:e.clientX, y:e.clientY};
    const m0 = estado.mov.get(id) || {dx:0, dy:0};
    let movido = false;
    const mover = ev=>{
      const dx = (ev.clientX-p0.x)/VP.k, dy = (ev.clientY-p0.y)/VP.k;
      if(!movido && Math.abs(dx)+Math.abs(dy) < 3) return;
      movido = true; SEARRASTRO = true;
      document.body.style.userSelect = "none";
      estado.mov.set(id, {dx:m0.dx+dx, dy:m0.dy+dy});
      dibujar();
    };
    const soltar = ()=>{
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
      document.body.style.userSelect = "";
      document.getElementById("ordenar").disabled = estado.mov.size===0;
    };
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
  });
}
function botonMas(g, x, y, abierto, alClic, ayuda, apagado){
  const el = document.createElementNS(SVGNS,"g");
  el.setAttribute("class","mas"+(apagado?" apagada":""));
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
/* Corta el motivo en renglones por sus comas. "misma cuenta, misma IP, mismo
   dispositivo" en una sola línea mide más que la caja y se monta sobre el
   motivo de la rama de al lado. */
function envolver(txt, max){
  const out = [];
  String(txt).split(", ").forEach(p=>{
    const u = out.length-1;
    if(u>=0 && (out[u]+", "+p).length<=max) out[u] += ", "+p;
    else out.push(p);
  });
  return out;
}
/* Punta de flecha del color de la línea. Con una sola punta gris para todas no
   se sabe cuál flecha es de cuál línea, que es justamente lo que hay que poder
   ver cuando hay diez líneas corriendo en paralelo. */
const MARCADORES = new Map();
function marcador(color){
  if(MARCADORES.has(color)) return MARCADORES.get(color);
  const id = "fl"+MARCADORES.size;
  const m = document.createElementNS(SVGNS,"marker");
  m.setAttribute("id",id); m.setAttribute("viewBox","0 0 8 8");
  m.setAttribute("refX","7"); m.setAttribute("refY","4");
  m.setAttribute("markerWidth","6"); m.setAttribute("markerHeight","6");
  m.setAttribute("orient","auto");
  const p = document.createElementNS(SVGNS,"path");
  p.setAttribute("d","M0,0 L8,4 L0,8 z"); p.setAttribute("fill",color);
  m.appendChild(p);
  document.querySelector("#lienzo defs").appendChild(m);
  MARCADORES.set(color,"url(#"+id+")");
  return MARCADORES.get(color);
}
/* Esquinas redondeadas: con el ángulo vivo, dos líneas que doblan en el mismo
   lugar se ven como una sola en cruz. Redondeadas, cada una sigue siendo un
   trazo continuo que se puede seguir con la vista. */
function ruta(x1, y1, x2, y2, ym){
  if(Math.abs(x2-x1) < 1) return "M"+x1+","+y1+" V"+y2;
  const r = Math.min(9, Math.abs(x2-x1)/2, Math.abs(ym-y1), Math.abs(y2-ym));
  if(r < 2) return "M"+x1+","+y1+" V"+ym+" H"+x2+" V"+y2;
  const sx = x2>x1 ? 1 : -1, s1 = ym>y1 ? 1 : -1, s2 = y2>ym ? 1 : -1;
  return "M"+x1+","+y1+
    " V"+(ym-r*s1)+" Q"+x1+","+ym+" "+(x1+r*sx)+","+ym+
    " H"+(x2-r*sx)+" Q"+x2+","+ym+" "+x2+","+(ym+r*s2)+
    " V"+y2;
}
function conector(desde, hasta, {clase, rotulo, peso, alClic, color, carril,
                                 dato, punto, apagado, realzado}){
  const x1 = desde.x, y1 = desde.y, x2 = hasta.x, y2 = hasta.y;
  const ym = carril!=null ? carril : (y1 + (y2-y1)/2);
  const d = ruta(x1,y1,x2,y2,ym);
  const cl = "con "+(clase||"")+(apagado?" apagada":"")+(realzado?" realzada":"");
  const p = document.createElementNS(SVGNS,"path");
  p.setAttribute("class",cl);
  p.setAttribute("d",d);
  // style y no setAttribute: el atributo de presentación pierde contra
  // cualquier regla de la hoja de estilos, y .con ya define un stroke.
  if(color) p.style.stroke = color;
  if(dato) p.setAttribute("data-dato",dato);
  p.setAttribute("marker-end", color ? marcador(color)
    : ((clase||"").indexOf("vinculo")===0 ? "url(#flechaCyan)" : "url(#flecha)"));
  gCon.appendChild(p);
  /* Un punto en el arranque: dice de dónde sale la línea sin tener que
     seguirla hasta el final para descubrirlo. Solo en los cruces, que corren
     por carriles paralelos; en el resto sería ruido. */
  if(punto){
    const o = document.createElementNS(SVGNS,"circle");
    o.setAttribute("class",cl+" origen");
    o.setAttribute("cx",x1); o.setAttribute("cy",y1); o.setAttribute("r",3.2);
    if(color){ o.style.fill = color; o.style.stroke = "none"; }
    o.setAttribute("data-dato",dato);
    gCon.appendChild(o);
  }
  if(alClic){
    const z = document.createElementNS(SVGNS,"path");
    z.setAttribute("class","zona"); z.setAttribute("d",d);
    z.addEventListener("click", e=>{ e.stopPropagation(); alClic(); });
    const ti = document.createElementNS(SVGNS,"title");
    ti.textContent = rotulo||""; z.appendChild(ti);
    gCon.appendChild(z);
  }
  /* El rótulo va sobre la rama que describe -no en el medio del recorrido, que
     es el mismo punto para todas- y colgando del tramo horizontal, no pegado a
     la caja: contra la punta de flecha no se llegaba a leer. */
  if(rotulo){
    const lineas = envolver(rotulo, 28);
    if(peso!=null && estado.verPesos) lineas.push("peso "+num(peso));
    // 14 y no 12: con 12 el alto real de un renglón de 10px -acentos y colas
    // incluidos- llega a tocar el de abajo. La auditoría lo detecta.
    const base = ym + 24, alto = 14;
    lineas.forEach((ln,i)=>{
      const esPeso = (peso!=null && estado.verPesos && i===lineas.length-1);
      const t = document.createElementNS(SVGNS,"text");
      t.setAttribute("class","rotulo "+(esPeso ? "peso" : "vinculo")+
                              (apagado?" apagado":""));
      t.setAttribute("x",x2); t.setAttribute("y",base+i*alto);
      t.textContent = ln; gRot.appendChild(t);
    });
  }
  return p;
}
/* Al pasar el puntero por un dato se realzan las líneas que lo llevan a los
   otros reportes. Es la pregunta que el operador se hace mirando la fila de
   abajo: "¿este dato de dónde más sale?". */
function marcarCruces(id, on){
  gCon.querySelectorAll('[data-dato="'+id+'"]')
      .forEach(p=>p.classList.toggle("realzada",on));
}

function dibujar(){
  gCon.textContent = ""; gRot.textContent = ""; gCaj.textContent = "";
  const c = caso(); if(!c) return;

  /* El árbol se puede colgar de dos cosas distintas:
       del reporte en análisis -lo habitual-, y entonces la fila de abajo son
       los reportes con los que se vinculó;
       de un dato puesto en el centro, y entonces la fila de abajo son los
       reportes en los que ese dato consta. Es la vista para investigar un
       identificador en particular: se ve su alcance de una. */
  const nCentro = estado.centro ? NODOS.get(estado.centro) : null;
  const modoDato = !!(nCentro && otrosReportesDe(nCentro).length);

  let nRaiz, relacionados;
  if(modoDato){
    nRaiz = nCentro;
    relacionados = otrosReportesDe(nCentro)
      .map(rv=>({arista:null, nodo:nodoReporte(rv)}))
      .filter(r=>r.nodo);
  } else {
    const raizVal = estado.raiz || c.reportes[0];
    nRaiz = nodoReporte(raizVal); if(!nRaiz) return;
    const vinc = vinculosDe(nRaiz.id).sort((a,b)=>(b.confianza||0)-(a.confianza||0));
    relacionados = vinc.map(a=>({arista:a, nodo:NODOS.get(a.a===nRaiz.id?a.b:a.a)}));
  }

  // --- fila de abajo: los datos de los reportes abiertos
  const abiertos = relacionados.filter(r=>estado.abiertos.has(r.nodo.id));
  if(!modoDato && estado.abiertos.has(nRaiz.id))
    abiertos.unshift({nodo:nRaiz, arista:null});
  const entidades = [];
  const yaEnt = new Set();
  if(modoDato) yaEnt.add(nCentro.id);      // ya está arriba, no se repite
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

  // Posición efectiva: la que calcula la disposición, más lo que el operador
  // haya corrido esa caja a mano.
  const P = id => { const p = pos.get(id), m = estado.mov.get(id);
                    return m ? {x:p.x+m.dx, y:p.y+m.dy} : p; };
  const abajo = p => ({x:p.x+ANCHO_CAJA/2, y:p.y+ALTO_CAJA});
  const arriba = p => ({x:p.x+ANCHO_CAJA/2, y:p.y});

  /* Realce. Al elegir un dato, el lienzo responde la pregunta que se hizo el
     operador al tocarlo: a qué reportes llega ese dato. Todo lo demás se
     apaga, que es lo único que vuelve legible una fila de diez líneas.
     Al elegir una vinculación, se realzan sus dos reportes y los datos que la
     sostienen. */
  let focoDato = null;
  const focoReps = new Set(), focoDatos = new Set();
  if(estado.sel && estado.sel.tipo==="entidad" && NODOS.has(estado.sel.id)){
    focoDato = estado.sel.id;
    focoDatos.add(focoDato);
    otrosReportesDe(NODOS.get(focoDato)).forEach(rv=>{
      const nr = nodoReporte(rv); if(nr) focoReps.add(nr.id); });
  } else if(estado.sel && estado.sel.tipo==="vinculo" && ARISTAS.has(estado.sel.id)){
    const a = ARISTAS.get(estado.sel.id);
    focoReps.add(a.a); focoReps.add(a.b);
    (a.puente||[]).forEach(x=>{ if(x.nodo) focoDatos.add(RE(x.nodo)); });
  }
  const hayFoco = focoReps.size>0;
  const repApagado = id => hayFoco && !focoReps.has(id);
  const datoApagado = id => hayFoco && !focoDatos.has(id);

  // --- conectores: la raíz -> la fila de abajo
  relacionados.forEach(r=>{
    const a = r.arista;
    if(!a){
      // Modo dato: el dato consta en ese reporte. Es una relación observada,
      // así que va llena y del color del dato, sin peso ni motivo.
      conector(abajo(P(nRaiz.id)), arriba(P(r.nodo.id)), {
        color: COLOR_TIPO(nRaiz.tipo), carril: CARRIL_VINC,
        apagado: !coincide(r.nodo) || repApagado(r.nodo.id),
        alClic: ()=>alternarFoco({tipo:"reporte", id:r.nodo.id})});
      return;
    }
    const apagado = !coincide(r.nodo) ||
      (hayFoco && !(focoReps.has(a.a) && focoReps.has(a.b)));
    conector(abajo(P(nRaiz.id)), arriba(P(r.nodo.id)), {
      clase: "vinculo"+(a.relacion==="POSIBLE_DUPLICADO_DE" ? " duplicado" : "")
             +(a.origen==="inferida" ? " inferida" : "")
             +(a.origen==="afirmada" ? " afirmada" : ""),
      carril: CARRIL_VINC,
      rotulo: (a.relacion==="POSIBLE_DUPLICADO_DE" ? "posible duplicado, " : "")
              + a.motivo,
      peso: a.confianza, apagado: apagado,
      realzado: hayFoco && !apagado,
      alClic: ()=>alternarFoco({tipo:"vinculo", id:a.id})});
  });

  // --- conectores: reporte abierto -> sus datos.
  // Va del color del dato, igual que los cruces. Antes era una línea gris de
  // estructura, y al elegir un dato el reporte del que cuelga quedaba
  // encendido pero sin ninguna línea de su color: se leía como un reporte
  // suelto en medio de la selección.
  entidades.forEach(e=>{
    conector(abajo(P(e.padre.id)), arriba(P(e.nodo.id)), {
      rotulo: null, color: COLOR_TIPO(e.nodo.tipo), dato: e.nodo.id,
      apagado: !coincide(e.nodo) || datoApagado(e.nodo.id),
      realzado: focoDato===e.nodo.id,
      alClic: ()=>alternarFoco({tipo:"entidad", id:e.nodo.id})});
  });

  // --- cruces: el mismo dato en otros reportes de la fila.
  // El color es el del tipo de dato, no un color de turno: así la línea que
  // sube, la barra de la caja de la que sale y su punta de flecha son el mismo
  // color, y dos IP distintas se leen como dos IP y no como dos cosas sueltas.
  let carril = Y_ENT + ALTO_CAJA + 40;
  entidades.forEach(e=>{
    const color = COLOR_TIPO(e.nodo.tipo);
    otrosReportesDe(e.nodo).forEach(rv=>{
      const nr = nodoReporte(rv);
      if(!nr || nr.id===e.padre.id || !pos.has(nr.id)) return;
      const apagado = !coincide(e.nodo) || datoApagado(e.nodo.id);
      conector(abajo(P(e.nodo.id)), abajo(P(nr.id)),
        {clase:"cruce", color, carril, dato:e.nodo.id, punto:true, apagado: apagado,
         realzado: focoDato===e.nodo.id,
         alClic: ()=>alternarFoco({tipo:"entidad", id:e.nodo.id})});
      carril += 13;
    });
  });

  // --- cajas
  // Un reporte que quedó bajo una identidad ya confirmada por un operador lo
  // dice en su propia caja. No se dibuja la identidad como si fuera un dato
  // más: es una conclusión sobre la persona, no algo que el reporte informe.
  const distintivoIdentidad = valor => {
    const idn = identidadDe(valor);
    return idn && otrosReportesDe(idn).length>1
      ? {marca:"misma persona", marcaColor:COLOR_TIPO("IDENTIDAD"), idn:idn} : {};
  };
  // El ⊕ va sobre el borde de abajo, en el punto exacto del que cuelgan los
  // datos: es el mismo lugar donde después aparece la rama que abre.
  const extra = id => (estado.mov.has(id)?" movida":"")+
                      (estado.sel && estado.sel.id===id?" sel":"");
  const cajaReporte = (nodo, sub, clases) => {
    const p = P(nodo.id);
    const dist = distintivoIdentidad(nodo.valor);
    const n = datosDe(nodo.valor).length;
    const apagada = !coincide(nodo) || repApagado(nodo.id);
    const el = caja(gCaj, p.x, p.y, {
      titulo:"Reporte "+nodo.valor, sub:sub,
      marca:dist.marca, marcaColor:dist.marcaColor,
      reservaDer: n ? 28 : 0,
      clases: clases+extra(nodo.id)+(apagada?" apagada":"")
              +(hayFoco && !apagada ? " realzada":""),
      alClic:()=>ir({tipo:"reporte", id:nodo.id})});
    arrastrable(el, nodo.id);
    if(n) botonMas(gCaj, p.x+ANCHO_CAJA-19, p.y+45,
      estado.abiertos.has(nodo.id), ()=>alternar(nodo.id),
      (estado.abiertos.has(nodo.id)?"Cerrar":"Abrir")+" los "+n+
      " dato(s) de este reporte", apagada);
    return el;
  };

  if(modoDato){
    const p = P(nRaiz.id);
    const el = caja(gCaj, p.x, p.y, {
      titulo:nRaiz.etiqueta, sub:nRaiz.tipoLegible+" · en el centro",
      marca:"en "+relacionados.length+" reportes",
      color: COLOR_TIPO(nRaiz.tipo),
      clases:"raiz"+extra(nRaiz.id),
      alClic:()=>ir({tipo:"entidad", id:nRaiz.id})});
    arrastrable(el, nRaiz.id);
  } else {
    const at = attr(nRaiz);
    cajaReporte(nRaiz,
      at["Plataforma"] ? at["Plataforma"]+" · en análisis" : "en análisis", "raiz");
  }

  relacionados.forEach(r=>{
    const a2 = attr(r.nodo);
    cajaReporte(r.nodo, a2["Motivo del archivo"] ? breve(a2["Motivo del archivo"])
                                                 : breve(a2["Estado en SIPAR"]), "");
  });

  entidades.forEach(e=>{
    const p = P(e.nodo.id);
    const enN = otrosReportesDe(e.nodo).length;
    const afuera = fueraDelCaso(e.nodo).length;
    const apagada = !coincide(e.nodo) || datoApagado(e.nodo.id);
    // Si el dato no se repite dentro del caso pero sí en otros, se dice: la
    // caja sin marca ni líneas parecía un dato que a nadie más le figura.
    const el = caja(gCaj, p.x, p.y, {
      titulo:e.nodo.etiqueta, sub:e.nodo.tipoLegible,
      marca: enN>1 ? "en "+enN+" reportes" : (afuera ? "en otros casos" : null),
      marcaColor: enN>1 ? null : "#8fa1bb",
      color: COLOR_TIPO(e.nodo.tipo),
      clases: extra(e.nodo.id)+(apagada?" apagada":"")
              +(focoDato===e.nodo.id ? " realzada":""),
      alClic:()=>alternarFoco({tipo:"entidad", id:e.nodo.id})});
    arrastrable(el, e.nodo.id);
    el.addEventListener("mouseenter",()=>marcarCruces(e.nodo.id,true));
    el.addEventListener("mouseleave",()=>marcarCruces(e.nodo.id,false));
  });

  document.getElementById("pie").textContent = modoDato
    ? nRaiz.etiqueta+" consta en "+relacionados.length+" reporte(s) del caso · "+
      entidades.length+" dato(s) a la vista"
    : relacionados.length+" reporte(s) vinculado(s) · "+entidades.length+" dato(s) a la vista";
  const chip = document.getElementById("centrado");
  chip.style.display = modoDato ? "" : "none";
  if(modoDato) chip.textContent = "◎ "+nRaiz.etiqueta+"  ✕";
  document.getElementById("contraer").disabled = estado.abiertos.size===0;
  document.getElementById("ordenar").disabled = estado.mov.size===0;
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
document.getElementById("ordenar").onclick = ()=>{
  estado.mov.clear(); VP.encuadrado = false; dibujar(); };

/* Poner un dato en el centro: el árbol se cuelga de él y la fila de abajo pasa
   a ser la de los reportes en los que consta. Es la vista para investigar un
   identificador -una cuenta, un dispositivo- en lugar de un reporte. */
function centrarEn(id){
  estado.centro = id || null;
  estado.abiertos.clear(); estado.mov.clear();
  VP.encuadrado = false;
  ir(id ? {tipo:"entidad", id:id} : {tipo:"inicio"});
}
document.getElementById("centrado").onclick = ()=>centrarEn(null);

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
    estado.raiz = acc.dataset.valor; estado.abiertos.clear(); estado.mov.clear();
    VP.encuadrado = false; ir({tipo:"inicio"});
  }
  if(acc.dataset.accion==="abrir"){ estado.abiertos.add(acc.dataset.valor); dibujar(); }
  if(acc.dataset.accion==="centrar"){ centrarEn(acc.dataset.valor); }
  if(acc.dataset.accion==="descentrar"){ centrarEn(null); }
  if(acc.dataset.accion==="copiar"){
    navigator.clipboard.writeText(acc.dataset.cmd).then(
      ()=>{ acc.textContent = "Copiado"; setTimeout(()=>{ acc.textContent = "Copiar el comando"; },1600); },
      ()=>{ acc.textContent = "No se pudo copiar"; });
  }
  if(acc.dataset.accion==="otroCaso"){
    const rv = acc.dataset.valor, c = casoDe(rv);
    if(c){
      cambiarCaso(c.id);
      const nr = nodoReporte(rv); if(nr) ir({tipo:"reporte", id:nr.id});
    }
  }
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
  /* Un reporte que quedó solo tiene que poder decir por qué. Sin esto, "no
     quedó vinculado" no se distingue de "nunca se lo comparó con nada". */
  const desc = descartadosDelReporte(raizVal);
  if(desc.length){
    h += '<h2>Se evaluó y no alcanzó ('+desc.length+')</h2>';
    desc.forEach(x=>{
      const otro = x.a===raizVal ? x.b : x.a, oc = casoDe(otro);
      h += '<div class="tarjeta click" data-accion="otroCaso" data-valor="'+esc(otro)+'">'+
        '<div style="font-size:12.5px"><b>Reporte '+esc(otro)+'</b>'+
        (oc && oc.id!==c.id ? ' <span class="sub">· '+esc(oc.etiqueta)+'</span>':'')+
        '</div><div style="font-size:12px;color:var(--suave);margin-top:5px">'+
        'Comparten '+esc((x.compartido||[]).map(y=>y.valor).filter(Boolean).join(", "))+
        '.</div><div style="font-size:12px;color:var(--tenue);margin-top:6px">'+
        esc(x.motivo||"")+'</div></div>'+
        copiable("python grafo/validar.py vincular "+raizVal+" "+otro+
                 " --usuario TU_USUARIO --motivo \"...\"");
    });
    h += '<div class="prosa"><p style="font-size:11.5px;color:var(--tenue)">'+
      'Si a su criterio estos reportes sí tienen que ver, la vinculación se '+
      'establece a mano con el comando de arriba y queda registrada con su '+
      'nombre y su fundamento. El sistema la conserva y agrupa los dos reportes '+
      'en el mismo caso.</p></div>';
  }

  h += '<h2>Otros reportes del caso</h2>';
  const otros = c.reportes.filter(r=>r!==raizVal);
  h += otros.length
    ? otros.map(r=>'<span class="chip boton" data-accion="raiz" data-valor="'+r+
        '">analizar '+esc(r)+'</span>').join("")
    : '<div class="vacio">Ninguno: el caso es este solo reporte.</div>';
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

  /* La identidad unificada no se dibuja en el lienzo: no es un dato que el
     reporte informe, sino una conclusión que un operador aprobó a partir de
     esos datos. Se explica acá, con los reportes que quedaron agrupados. */
  const idn = identidadDe(n.valor);
  if(idn && otrosReportesDe(idn).length>1){
    h += '<h2>Identidad unificada</h2>'+
      '<div class="tarjeta" style="border-color:rgba(129,140,248,.4)">'+
      '<div style="font-size:12.5px;color:var(--suave);line-height:1.6">'+
      'Un operador confirmó que las menciones de persona de '+
      otrosReportesDe(idn).map(r=>'<b>'+esc(r)+'</b>').join(', ')+
      ' corresponden a la misma persona. No es un dato del reporte: es una '+
      'decisión humana registrada, y se revierte desde el libro de validaciones.'+
      '</div></div>';
  }

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

  /* Sin esto, un reporte que quedó solo no se distingue de uno que el sistema
     nunca comparó. Acá se ve que sí se lo comparó, con qué, y por qué no
     prosperó. Es lo que permite discutir la regla. */
  const desc = descartadosDelReporte(n.valor);
  if(desc.length){
    h += '<h2>Coincidencias que no alcanzaron ('+desc.length+')</h2>'+prosa(
      'Estos reportes comparten algún dato con éste y fueron evaluados, pero la '+
      'coincidencia no alcanzó para proponer una vinculación. Quedan registradas '+
      'para poder revisar el criterio.');
    desc.forEach(x=>{
      const otro = x.a===n.valor ? x.b : x.a;
      const c = casoDe(otro);
      h += '<div class="tarjeta click" data-accion="otroCaso" data-valor="'+esc(otro)+'">'+
        '<div style="font-size:12.5px"><b>Reporte '+esc(otro)+'</b>'+
        (c? ' <span class="sub">· '+esc(c.etiqueta)+'</span>':'')+'</div>'+
        '<div style="font-size:12px;color:var(--suave);margin-top:5px">Comparten '+
        esc((x.compartido||[]).map(y=>y.valor).filter(Boolean).join(", "))+'.</div>'+
        '<div style="font-size:12px;color:var(--tenue);margin-top:6px">'+
        esc(x.motivo||"")+'</div></div>'+
        copiable("python grafo/validar.py vincular "+n.valor+" "+otro+
                 " --usuario TU_USUARIO --motivo \"...\"");
    });
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
  const col = COLOR_TIPO(n.tipo);
  let h = '<span class="chip cy" style="border-color:'+col+'55;color:'+col+
    '"><span class="pt"></span>'+esc(n.tipoLegible)+'</span><h3>'+esc(n.etiqueta)+'</h3>';
  /* Investigar el dato en vez del reporte: el árbol se cuelga de él. Solo tiene
     sentido si consta en más de un reporte del caso. */
  if(estado.centro===id){
    h += '<div class="fila"><button data-accion="descentrar">'+
      'Volver al reporte en análisis</button></div>';
  } else if(enR.length>1){
    h += '<div class="fila"><button class="primario" data-accion="centrar" '+
      'data-valor="'+id+'">Poner este dato en el centro</button></div>'+
      '<div class="sub" style="margin-bottom:4px">El árbol se arma alrededor de '+
      'este dato y muestra los reportes en los que consta.</div>';
  }

  /* Lo primero que hay que contestar cuando alguien toca un dato en el lienzo
     es qué vinculaciones sostiene, no en qué reportes está: para eso ya se ven
     las líneas. Acá va el porqué. */
  const sostiene = VINCULOS.filter(a=>{
    const rs = reportesCaso();
    if(!(rs.has((NODOS.get(a.a)||{}).valor) && rs.has((NODOS.get(a.b)||{}).valor)))
      return false;
    return (a.puente||[]).some(x=>x.nodo && RE(x.nodo)===id);
  });
  if(sostiene.length){
    h += '<h2>Vinculaciones que sostiene ('+sostiene.length+')</h2>';
    sostiene.forEach(a=>{
      const tramo = (a.puente||[]).find(x=>x.nodo && RE(x.nodo)===id) || {};
      h += '<div class="tarjeta click" data-ir="vinculo|'+a.id+'">'+
        chipPeso(a.confianza)+
        '<div style="margin-top:4px;font-size:12.5px"><b>Reporte '+
        esc((NODOS.get(a.a)||{}).valor)+'</b> con <b>Reporte '+
        esc((NODOS.get(a.b)||{}).valor)+'</b></div>'+
        '<div style="font-size:12px;color:var(--suave);margin-top:4px">'+
        esc(tramo.texto || (tramo.sostiene===false
          ? "Corrobora la vinculación sin sostenerla por sí solo."
          : "Es uno de los datos objetivos en que se apoya la vinculación."))+
        '</div></div>';
    });
  } else if(enR.length>1){
    h += '<h2>Vinculaciones que sostiene</h2>'+prosa(
      'Este dato aparece en más de un reporte del caso, pero la vinculación '+
      'entre ellos no se apoya en él. Puede estar corroborando otra relación, '+
      'o no alcanzar por sí solo para individualizar.');
  }

  h += '<h2>Aparece en '+enR.length+' reporte(s) del caso</h2>';
  enR.forEach(r=>{
    const nr = nodoReporte(r);
    h += '<div class="tarjeta click" data-ir="reporte|'+(nr?nr.id:"")+'">'+
      '<div style="font-size:12.5px"><b>Reporte '+esc(r)+'</b></div></div>';
  });

  const fuera = fueraDelCaso(n);
  if(fuera.length){
    h += '<h2>También en otros casos ('+fuera.length+')</h2>'+prosa(
      'Este mismo dato aparece en reportes que no forman parte de este caso. '+
      'Que no haya una línea hacia ellos no significa que el sistema no lo '+
      'haya visto: significa que la coincidencia no alcanzó para sostener una '+
      'vinculación.');
    fuera.forEach(r=>{
      const c = casoDe(r);
      h += '<div class="tarjeta click" data-accion="otroCaso" data-valor="'+esc(r)+'">'+
        '<div style="font-size:12.5px"><b>Reporte '+esc(r)+'</b></div>'+
        '<div class="sub" style="margin-top:3px">'+esc(c?c.etiqueta:"otro caso")+
        '</div></div>';
    });
  }

  const desc = descartadosDelDato(id);
  if(desc.length){
    h += '<h2>Coincidencias que no alcanzaron ('+desc.length+')</h2>';
    desc.forEach(x=>{ h += tarjetaDescartada(x, id); });
  }

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
  const manual = a.origen==="afirmada";
  let h = '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.14em;'+
    'color:var(--cyan)">'+(manual?"Vinculación establecida":"Por qué se vinculan")+'</div>'+
    '<h3>Reporte '+esc(NODOS.get(a.a).valor)+' y Reporte '+esc(NODOS.get(a.b).valor)+'</h3>'+
    chipPeso(a.confianza)+'<span class="chip">'+esc(a.origenLegible)+'</span>'+
    '<span class="chip'+(a.estado==="validada"?" ok":a.estado==="rechazada"?" al":"")+'">'+
    esc(a.estadoLegible)+'</span>';

  /* Una vinculación manual no tiene "lo que la sostiene": lo que la sostiene es
     el criterio de quien la dispuso, y eso es lo que hay que mostrar. */
  if(manual){
    h += '<h2>Quién la dispuso</h2>'+prosa(
      'La estableció '+(a.dispuestaPor||"un operador")+
      (a.validado_en ? ' el '+String(a.validado_en).slice(0,10) : '')+
      '. No la propuso el sistema: no consta en la fuente ni surge de una regla, '+
      'y por eso no lleva peso — no hay nada calculado que ponderar.');
    if(a.motivoOperador){
      h += '<h2>Fundamento registrado</h2><div class="tarjeta cyan">'+
        '<div style="font-size:12.5px;color:var(--texto);line-height:1.6">'+
        esc(a.motivoOperador)+'</div></div>';
    }
    h += '<h2>Cómo se revierte</h2>'+prosa(
      'Desde el mismo libro, con otro registro. El anterior no se borra: la '+
      'historia de la decisión se conserva.')+
      copiable("python grafo/validar.py desvincular "+NODOS.get(a.a).valor+" "+
               NODOS.get(a.b).valor+" --usuario TU_USUARIO");
  }
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
/* El informe es del caso en curso. El general -de toda la corrida- existe como
   archivo aparte, pero no es lo que el operador firma. */
function textoInforme(){
  const c = caso(), i = D.informe||{};
  return (c && (i.porCaso||{})[c.id]) || i.texto || "";
}
function fichaInforme(){
  const t = textoInforme();
  ficha('<div class="fila"><button data-accion="descargar">Descargar .md</button>'+
    '<button data-ir="inicio|">Volver</button></div>'+
    (t? markdown(t) : '<div class="vacio">Sin informe.</div>'));
}
function descargarInforme(){
  const c = caso();
  const b = new Blob([textoInforme()],{type:"text/markdown;charset=utf-8"});
  const u = URL.createObjectURL(b), a = document.createElement("a");
  a.href = u; a.download = "informe_"+(c?c.id:"vinculaciones")+".md"; a.click();
  setTimeout(()=>URL.revokeObjectURL(u),1000);
}
document.getElementById("btnInforme").onclick = ()=>ir({tipo:"informe"});

/* ============================================================ paneles ===== */
function plegable(idPanel, idBoton, abierto, cerrado){
  const b = document.getElementById(idBoton), p = document.getElementById(idPanel);
  b.onclick = ()=>{
    /* Al redimensionar a mano queda un flex-basis en línea, y el estilo en
       línea gana sobre la regla de plegado: el panel se vaciaba pero seguía
       ocupando el ancho al que lo habían llevado. Se guarda ese ancho, se
       suelta el estilo mientras está plegado y se devuelve al abrirlo. */
    const cerrando = !p.classList.contains("plegado");
    if(cerrando){
      p.dataset.ancho = p.style.flexBasis || "";
      p.style.flexBasis = "";
    } else if(p.dataset.ancho){
      p.style.flexBasis = p.dataset.ancho;
    }
    p.classList.toggle("plegado");
    b.textContent = p.classList.contains("plegado") ? cerrado : abierto;
    VP.encuadrado = false; dibujar();
  };
}
plegable("der","plegDer","›","‹");
plegable("izq","plegIzq","‹","☰");

function redimensionable(idAsa, idPanel, lado){
  const asa = document.getElementById(idAsa), panel = document.getElementById(idPanel);
  let act = null;
  asa.addEventListener("pointerdown",e=>{
    act = {x:e.clientX, w:panel.getBoundingClientRect().width};
    asa.setPointerCapture(e.pointerId); panel.style.transition="none";
    document.body.style.userSelect="none"; });
  asa.addEventListener("pointermove",e=>{
    if(!act) return; panel.classList.remove("plegado");
    const delta = lado==="izq" ? (e.clientX-act.x) : (act.x-e.clientX);
    panel.style.flexBasis = Math.max(260,Math.min(760,act.w+delta))+"px"; });
  asa.addEventListener("pointerup",e=>{
    act=null; asa.releasePointerCapture(e.pointerId);
    panel.style.transition=""; document.body.style.userSelect="";
    VP.encuadrado = false; dibujar(); });
}
redimensionable("asa","der","der");
redimensionable("asaIzq","izq","izq");

/* ------------------------------------------------------------- filtros --- */
function refrescar(reencuadrar){
  if(reencuadrar) VP.encuadrado = false;
  dibujar();
}
function pintarTipos(){
  const cont = document.getElementById("tipos");
  cont.innerHTML = "";
  TIPOS_DATO.forEach(t=>{
    const l = document.createElement("label");
    l.innerHTML = '<input type="checkbox"'+(estado.tipos.has(t)?" checked":"")+'>'+
      '<span class="sw" style="background:'+COLOR_TIPO(t)+'"></span>'+
      esc(NOMBRE_TIPO(t));
    l.title = (D.tipos[t]||{}).desc || "";
    l.querySelector("input").onchange = ev=>{
      if(ev.target.checked) estado.tipos.add(t); else estado.tipos.delete(t);
      refrescar(true);
    };
    cont.appendChild(l);
  });
}
/* Leyenda del único criterio de color y trazo del lienzo. Si hay que mirar el
   dibujo y adivinar qué significa una línea, la línea no sirve. */
function pintarLeyenda(){
  const trazos = [
    ["solid",  "#6b7f9e", "Consta en la fuente del reporte"],
    ["dashed", "#22d3ee", "Derivada por una regla del sistema"],
    ["dotted", "#a78bfa", "Hipótesis todavía sin validar"],
    ["dashed", "#7dd3fc", "Establecida por un operador"],
  ];
  document.getElementById("leyenda").innerHTML =
    trazos.map(([e,c,t])=>
      '<div style="display:flex;align-items:center;font-size:11.5px;'+
      'color:var(--suave);margin:6px 0"><span class="trazo" style="border-top-style:'+
      e+';border-top-color:'+c+'"></span>'+esc(t)+'</div>').join("")+
    '<div class="rotuloGrupo">Y el color, de qué dato se trata</div>'+
    '<div style="font-size:11.5px;color:var(--suave);line-height:1.6">'+
    'Cada tipo de dato tiene su color, el mismo en la barra de la caja y en la '+
    'línea que la lleva a los otros reportes donde ese dato aparece. '+
    'El número en ámbar dice en cuántos reportes del caso aparece.</div>';
}
function pintarAlertas(){
  const rs = reportesCaso();
  const al = (D.alertas||[]).filter(a=>rs.has(a.reporte_archivado));
  const cont = document.getElementById("alertas");
  if(!al.length){
    cont.innerHTML = '<div class="vacio">Ninguno en este caso.</div>'; return;
  }
  /* Un archivado puede recibir el dato que le faltaba desde varios reportes a
     la vez. Es un antecedente a revisar, no tres: se agrupa por el reporte
     archivado y se enumeran los que lo reactivan. */
  const porArchivado = new Map();
  al.forEach(a=>{
    if(!porArchivado.has(a.reporte_archivado))
      porArchivado.set(a.reporte_archivado, {motivo:a.motivo_archivo, quienes:[]});
    porArchivado.get(a.reporte_archivado).quienes.push(a.reporte_disparador);
  });
  cont.innerHTML = [...porArchivado.entries()].map(([rid,g])=>
    '<div class="tarjeta alarma click" data-rep="'+esc(rid)+'">'+
    '<div style="font-size:12.5px"><b>Reporte '+esc(rid)+'</b></div>'+
    '<div class="sub" style="margin-top:3px">'+esc(legible(g.motivo))+'</div>'+
    '<div style="font-size:11.5px;color:var(--suave);margin-top:6px">'+
    (g.quienes.length===1
      ? 'Lo reactiva el reporte '+esc(g.quienes[0])+'.'
      : 'Lo reactivan los reportes '+esc(g.quienes.slice(0,-1).join(", "))+
        ' y '+esc(g.quienes[g.quienes.length-1])+'.')+
    '</div></div>').join("");
  cont.querySelectorAll("[data-rep]").forEach(el=>el.onclick=()=>{
    const n = nodoReporte(el.dataset.rep); if(n) ir({tipo:"reporte", id:n.id});
  });
}
document.getElementById("buscar").addEventListener("input", e=>{
  estado.texto = e.target.value; refrescar(false); });
document.getElementById("peso").addEventListener("input", e=>{
  estado.pesoMin = Number(e.target.value)/100;
  document.getElementById("pesov").textContent = num(estado.pesoMin);
  refrescar(true); });
document.getElementById("verPesos").onchange = e=>{
  estado.verPesos = e.target.checked; refrescar(false); };
document.getElementById("soloComp").onchange = e=>{
  estado.soloCompartidos = e.target.checked; estado.abiertos.clear(); refrescar(true); };
document.getElementById("meta").textContent =
  (D.meta.reportes||0)+" reportes ingresados · ontología "+(D.meta.ontologia||"");
/* Al recargar, el navegador devuelve los controles como estaban antes y no
   como los declara el documento. Si el estado no se lee del control, el panel
   dice una cosa y el lienzo muestra otra. */
function sincronizarControles(){
  estado.verPesos = document.getElementById("verPesos").checked;
  estado.soloCompartidos = document.getElementById("soloComp").checked;
  estado.pesoMin = Number(document.getElementById("peso").value)/100;
  estado.texto = document.getElementById("buscar").value;
  document.getElementById("pesov").textContent = num(estado.pesoMin);
}
sincronizarControles();
pintarTipos();
pintarLeyenda();

/* ============================================================ arranque ==== */
const sel = document.getElementById("selCaso");
CASOS.forEach(c=>{
  const o = document.createElement("option");
  o.value = c.id; o.textContent = c.etiqueta; sel.appendChild(o);
});
function cambiarCaso(id){
  estado.caso = id; estado.raiz = null; estado.centro = null;
  estado.abiertos.clear(); estado.mov.clear();
  VP.encuadrado = false;
  HIST.pila = []; HIST.pos = -1;
  sel.value = id;
  pintarAlertas();
  ir({tipo:"inicio"});
}
sel.onchange = e=>cambiarCaso(e.target.value);
window.addEventListener("resize", ()=>{ VP.encuadrado = false; dibujar(); });
if(CASOS.length) cambiarCaso(CASOS[0].id); else ficha('<div class="vacio">Sin casos.</div>');
</script></body></html>
"""


def render(g, res, ruta, dossier=None, texto_informe=None,
           informes_por_caso=None):
    datos = _datos(g, res, dossier, texto_informe)
    if datos.get("informe") is not None:
        datos["informe"]["porCaso"] = informes_por_caso or {}
    html = PLANTILLA.replace("__DATOS__",
                             json.dumps(datos, ensure_ascii=False, default=str))
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(html)
    return ruta
