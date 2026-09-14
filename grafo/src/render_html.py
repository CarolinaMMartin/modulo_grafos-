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


import ontologia as ont
import resolucion

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
    "ALIAS_PAGO": u"misma vía de cobro",
    "UBICACION": u"misma zona",
    "HASH_PERCEPTUAL": u"imágenes similares",
    "HUELLA_AUDIO": u"misma huella de audio",
    "LUGAR_MENCION": u"descripciones de lugar similares",
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
TIPOS_EN_TARJETA = ("CUENTA", "ALIAS", "ALIAS_PAGO", "TELEFONO", "EMAIL",
                    "IP", "DISPOSITIVO", "EVIDENCIA", "UBICACION")

# Color de cada tipo de dato en el lienzo. La ontologia declara un color
# institucional pensado para papel; sobre fondo oscuro varios de esos tonos no
# se distinguen. Esta es la variante de pantalla, y es el unico criterio de
# color del visor: un tipo de dato, un color, en la barra de la caja y en la
# linea que lo vincula con los otros reportes.
COLOR_VISOR = {
    "CUENTA": "#fb923c",
    "ALIAS": "#fdba74",
    "ALIAS_PAGO": "#facc15",
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
    "ALIAS": 3, "ALIAS_PAGO": 3, "EMAIL": 3, "TELEFONO": 3, "IP": 3,
    "DISPOSITIVO": 3,
    "EVIDENCIA": 3, "SEGMENTO": 3,
    "UBICACION": 4, "ORGANIZACION": 4, "DOCUMENTO": 4, "JURISDICCION": 4,
}



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
        if g.reporte_de_fuente(d.get("source_evidence_id")) != sid:
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
        sid = g.reporte_de_fuente(d.get("source_evidence_id")) or ""
        if not sid:
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
            fuentes = []
            for nu, nv, nk, nd in g.aristas(vigentes=False):
                if n_dato and n_dato in (nu, nv):
                    sid = g.reporte_de_fuente(nd.get("source_evidence_id"))
                    if sid in ("ncmec:%s" % g.G.nodes[u].get("valor"),
                               "ncmec:%s" % g.G.nodes[v].get("valor")):
                        dato_fuente = dict(reporte=sid.split(":", 1)[1],
                                           ruta=nd.get("source_locator"), arista=nd["arista_id"])
                        if dato_fuente not in fuentes:
                            fuentes.append(dato_fuente)
            puente.append(dict(
                nodo=n_dato,
                tipo=ont.ETIQUETA_TIPO.get(x.get("tipo"), x.get("tipo")),
                valor=x.get("valor"),
                peso=x.get("peso_efectivo"),
                sostiene=not x.get("corrobora_solamente"),
                texto=x.get("nota"),
                fuentes=fuentes,
                locators=x.get("source_locators") or [],
                camino_a=_camino(g, u, n_dato) if n_dato in g.G else [],
                camino_b=_camino(g, v, n_dato) if n_dato in g.G else []))
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
            calculo=(resolucion.calculo_legible(d["detalle_reglas"], d["confidence"])
                     if d.get("detalle_reglas") else None),
            resumen=(d.get("explicacion") or "").split("\n\n")[0],
            duplicado=d.get("indicios_duplicado"),
            historial=[{k: r.get(k) for k in ("decision", "usuario", "observacion", "ts")}
                       for r in d.get("historial_validacion", [])],
            reportes=([g.reporte_de_fuente(d.get("source_evidence_id")).split(":", 1)[1]]
                      if g.reporte_de_fuente(d.get("source_evidence_id")) else
                      sorted(set(por_nodo.get(u, [])) | set(por_nodo.get(v, [])))),
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
        importados=res.get("importados", []),
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
<script>
/* Aplicar antes de pintar evita el destello al recuperar el tema elegido. */
try { document.documentElement.dataset.tema = localStorage.getItem("bcij_tema")==="oscuro" ? "oscuro" : "claro"; }
catch(e) { document.documentElement.dataset.tema = "claro"; }
</script>
<style>
:root{
  color-scheme:light;
  --fuente:"Segoe UI","Public Sans",Arial,system-ui,-apple-system,sans-serif;
  --mono:var(--fuente);
  --fondo:#f5f6f7;--lienzo:#f5f6f7;--panel:#fff;--panel2:#f8f9fa;
  --borde:#dce0e4;--borde-fuerte:#b9c1c9;--texto:#15202b;--tenue:#65717c;--suave:#4f5d68;
  --cyan:#2b5f8f;--cyan-tenue:#e6eef6;--cyan-borde:#9db6cd;
  --verde:#1b7146;--verde-bg:#e3f2e9;--ambar:#8a5300;--ambar-bg:#fbf1dc;
  --alarma:#b42318;--alarma-bg:#fbeae8;--hover:#edf0f2;
  --inverso:#15202b;--inverso-texto:#fff;--sombra:0 16px 60px #15202b30;
  --vinculo:#2b5f8f;--duplicado:#92516e;--inferida:#766099;--afirmada:#56616b;
  --tipo-cuenta:#91633d;--tipo-alias:#967353;--tipo-alias-pago:#8c732b;
  --tipo-email:#447b98;--tipo-telefono:#337b72;--tipo-ip:#4b8058;
  --tipo-dispositivo:#83689b;--tipo-evidencia:#697580;--tipo-ubicacion:#967539;
  --tipo-identidad:#696999;--tipo-organizacion:#647383;--tipo-reporte:#447797;
}
:root[data-tema="oscuro"]{
  color-scheme:dark;
  --fondo:#0d1217;--lienzo:#0d1217;--panel:#141b22;--panel2:#19222b;
  --borde:#2a333c;--borde-fuerte:#4b5966;--texto:#e8ecef;--tenue:#96a2ad;--suave:#b1bbc4;
  --cyan:#8fb8dc;--cyan-tenue:#1d2e3e;--cyan-borde:#4b6b87;
  --verde:#7ccf9d;--verde-bg:#1c352a;--ambar:#e6b862;--ambar-bg:#372f22;
  --alarma:#f19a92;--alarma-bg:#382624;--hover:#202a33;
  --inverso:#e8ecef;--inverso-texto:#0d1217;--sombra:0 16px 60px #0007;
  --vinculo:#8fb8dc;--duplicado:#d3a0b6;--inferida:#b5a0d0;--afirmada:#bac5cf;
  --tipo-cuenta:#c59d7b;--tipo-alias:#c8ac92;--tipo-alias-pago:#c9b379;
  --tipo-email:#8ab8d0;--tipo-telefono:#88beb4;--tipo-ip:#93bb9b;
  --tipo-dispositivo:#bda6d2;--tipo-evidencia:#aebbc5;--tipo-ubicacion:#c6b082;
  --tipo-identidad:#aaaad2;--tipo-organizacion:#a1b0bf;--tipo-reporte:#95b8d1;
}
*{box-sizing:border-box}
html,body{height:100%;width:100%}
body{margin:0;background:var(--fondo);color:var(--texto);display:flex;
  font:13px/1.5 var(--fuente);overflow:hidden;padding-top:58px;padding-bottom:45px}
button,input,select,textarea,svg,svg text,code,pre{font-family:var(--fuente)}
svg text{font-variant-numeric:tabular-nums}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-thumb{background:var(--borde-fuerte);border-radius:3px}
::-webkit-scrollbar-track{background:transparent}
a{color:var(--cyan)}
#cabecera{position:fixed;inset:0 0 auto 0;height:58px;z-index:10;display:flex;align-items:center;
  gap:12px;padding:0 20px;border-bottom:1px solid var(--borde);background:var(--panel)}
#cabecera .emblema{width:28px;height:28px;background:var(--inverso);color:var(--inverso-texto);
  display:grid;place-items:center;border-radius:4px;font-size:16px;font-weight:600}
#cabecera strong{font-size:14px;font-weight:600;letter-spacing:-.015em}
#cabecera .contexto{color:var(--tenue);font-size:12px;border-left:1px solid var(--borde);padding-left:12px}
#cabecera .acciones{margin-left:auto;display:flex;align-items:center;gap:8px}
#cabecera label{color:var(--tenue);font-size:12px}
#tema{max-width:100px;padding:6px 9px}
#izq{flex:0 0 260px;min-width:0;background:var(--panel);border-right:1px solid var(--borde);
  overflow-y:auto;position:relative;transition:flex-basis .2s}
#izq.plegado{flex-basis:48px;overflow:hidden}
#izq.plegado .contenido{display:none}
#izq .contenido{padding:57px 18px 24px}
#izq .plegar{left:auto;right:10px}
#izq.plegado .plegar{right:9px}
#izq label{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--suave);margin:8px 0;cursor:pointer;line-height:1.4}
#izq label:hover{color:var(--texto)}
#izq input[type=checkbox]{accent-color:var(--cyan);margin:0;flex:0 0 auto}
#izq input[type=range]{accent-color:var(--cyan)}
.sw{width:9px;height:9px;border-radius:2px;flex:0 0 auto;display:inline-block}
.rotuloGrupo{font-size:10px;color:var(--tenue);margin:16px 0 7px;text-transform:uppercase;letter-spacing:.1em;font-weight:600}
.trazo{display:inline-block;width:26px;height:0;vertical-align:middle;margin-right:8px;border-top-width:2px;flex:0 0 auto}
#centro{flex:1;min-width:0;position:relative;background:var(--lienzo);overflow:hidden;display:flex;flex-direction:column}
.asa{flex:0 0 4px;cursor:col-resize;position:relative;background:var(--panel)}
.asa::after{content:"";position:absolute;top:50%;left:0;width:3px;height:38px;margin-top:-19px;border-radius:2px;background:var(--borde)}
.asa:hover::after{background:var(--cyan)}
#der{flex:0 0 360px;min-width:0;background:var(--panel);border-left:1px solid var(--borde);
  overflow-y:auto;position:relative;transition:flex-basis .2s}
#der.plegado{flex-basis:44px}
#der.plegado .contenido{display:none}
#der .contenido{padding:18px 22px 26px}
#navDetalle{position:sticky;top:0;z-index:4;display:flex;align-items:center;gap:8px;
  padding:12px;background:var(--panel);border-bottom:1px solid var(--borde)}
#navDetalle .plegar{position:static;margin-left:auto;flex:0 0 28px}
#der.plegado #navDetalle{padding:8px}
#der.plegado #navDetalle .historia{display:none}
.plegar{position:absolute;top:12px;left:12px;width:28px;height:28px;padding:0;
  z-index:3;display:flex;align-items:center;justify-content:center;font-size:16px}
h1{font-size:16px;margin:0 0 3px;font-weight:600}
h2{font-size:10.5px;text-transform:uppercase;letter-spacing:.09em;color:var(--tenue);margin:23px 0 10px;font-weight:600}
h3{font-size:16px;margin:8px 0 8px;font-weight:600;line-height:1.35;overflow-wrap:anywhere}
p{margin:0 0 10px}.sub{font-size:11.5px;color:var(--tenue)}
.tarjeta{background:transparent;border:0;border-bottom:1px solid var(--borde);padding:12px 0;margin:5px 0}
.tarjeta.cyan{border-left:2px solid var(--cyan-borde);padding-left:12px}
.tarjeta.alarma{border-left:2px solid var(--alarma);padding-left:12px;background:var(--alarma-bg)}
.tarjeta.click{cursor:pointer}.tarjeta.click:hover{background:var(--hover)}
.chip{display:inline-flex;align-items:center;gap:5px;padding:3px 7px;border-radius:3px;font-size:10.5px;
  border:1px solid var(--borde);background:var(--panel2);color:var(--suave);margin:0 5px 5px 0;white-space:normal;overflow-wrap:anywhere}
.chip.cy{border-color:var(--cyan-borde);background:var(--cyan-tenue);color:var(--cyan)}
.chip.ok,.chip.coincide{border-color:var(--verde);background:var(--verde-bg);color:var(--verde)}
.chip.am{border-color:var(--ambar);background:var(--ambar-bg);color:var(--ambar)}
.chip.al{border-color:var(--alarma);background:var(--alarma-bg);color:var(--alarma)}
.chip .pt{width:6px;height:6px;border-radius:50%;background:currentColor}
.chip.boton{cursor:pointer;max-width:100%}.chip.boton:hover{border-color:var(--cyan);color:var(--cyan)}
button{font:inherit;font-size:12px;padding:7px 11px;border:1px solid var(--borde);background:var(--panel);
  color:var(--suave);border-radius:4px;cursor:pointer;transition:background .15s,color .15s;white-space:nowrap}
button:hover:not(:disabled){color:var(--texto);background:var(--hover);border-color:var(--borde-fuerte)}
button.primario{border-color:var(--inverso);background:var(--inverso);color:var(--inverso-texto);font-weight:600}
button.primario:hover:not(:disabled){opacity:.88;background:var(--inverso);color:var(--inverso-texto)}
button:disabled{opacity:.35;cursor:default}
select{border:1px solid var(--borde);border-radius:4px;color:var(--texto);background:var(--panel);
  padding:7px 10px;font:inherit;font-size:12px;cursor:pointer;max-width:240px;min-width:0}
select:hover{border-color:var(--borde-fuerte)}
input[type=text]{width:100%;padding:9px 10px;border:1px solid var(--borde);border-radius:4px;
  font:inherit;font-size:12px;background:var(--panel);color:var(--texto)}
input[type=text]:focus{border-color:var(--cyan)}
.fila{display:flex;gap:7px;align-items:center;margin:9px 0;flex-wrap:wrap}
#barra{position:relative;flex:0 0 auto;display:flex;gap:6px;align-items:center;flex-wrap:wrap;
  padding:10px 14px;z-index:5;border-bottom:1px solid var(--borde);background:var(--panel)}
.grupo{display:flex;overflow:hidden}.grupo button{border:0;background:transparent;padding:7px 8px}
.grupo button+button{border-left:1px solid var(--borde);border-radius:0}
.solo{background:transparent;border-color:transparent}
#ruta{font-size:11px;color:var(--tenue);margin-left:auto;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
svg#lienzo{width:100%;flex:1;min-height:0;display:block;cursor:grab;touch-action:none}
svg.arrastrando{cursor:grabbing}
.caja{cursor:grab}.caja.moviendo{cursor:grabbing}
.caja.movida rect.cuerpo{filter:drop-shadow(0 2px 3px #0002)}
.caja rect.cuerpo{fill:var(--panel);stroke:var(--borde-fuerte);stroke-width:1;rx:5;transition:stroke .15s,fill .15s}
.caja:hover rect.cuerpo{stroke:var(--cyan);fill:var(--panel2)}
.caja.sel rect.cuerpo,.caja.realzada rect.cuerpo{stroke:var(--cyan);stroke-width:2}
.caja.raiz rect.cuerpo{fill:var(--inverso);stroke:var(--inverso);stroke-width:1}
.caja .barra{rx:2}.caja .titulo{fill:var(--texto);font-size:13px;font-weight:600;dominant-baseline:middle;pointer-events:none}
.caja .sub{fill:var(--tenue);font-size:11px;dominant-baseline:middle;pointer-events:none}
.caja.raiz .titulo{fill:var(--inverso-texto)}.caja.raiz .sub{fill:var(--inverso-texto);opacity:.78}
.caja .marca{fill:var(--ambar);font-size:10px;text-anchor:end;dominant-baseline:middle;pointer-events:none}
.caja.raiz .marca{fill:var(--inverso-texto)}
.caja.apagada{opacity:.2}.caja.apagada rect.cuerpo{stroke:var(--borde);stroke-width:1}
.caja .marca.accion{pointer-events:auto;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px}
.caja .marca.accion:hover,.caja .marca.accion:focus{fill:var(--cyan)}
.caja circle.accion{cursor:pointer}
.caja .accion:focus-visible{outline:2px solid var(--cyan);outline-offset:3px}
.caja.fuera{opacity:.3}
.caja.alcance{opacity:1}
.caja.alcance rect.cuerpo{stroke:var(--cyan);stroke-width:2}
.mas{cursor:pointer}.mas.apagada{opacity:.2}.mas circle{fill:var(--panel);stroke:var(--borde-fuerte);stroke-width:1}
.mas:hover circle{fill:var(--hover);stroke:var(--cyan)}.mas path{stroke:var(--suave);stroke-width:1.4;stroke-linecap:round}
.con{fill:none;stroke:var(--borde-fuerte);stroke-width:1.5;transition:opacity .15s}
.con.vinculo{stroke:var(--vinculo)}.con.duplicado{stroke:var(--duplicado)}
.con.inferida{stroke:var(--inferida);stroke-dasharray:5 4}.con.afirmada{stroke:var(--afirmada);stroke-width:2.4}
.con.cruce{stroke-width:1.5;opacity:.62}.con.realzada{opacity:1;stroke-width:2.8}
.con.origen,.con.origen.realzada{stroke-width:0}.con.apagada{opacity:.08}.con.sel{stroke:var(--texto);stroke-width:3;opacity:1}
.zona{stroke:transparent;stroke-width:16;fill:none;cursor:pointer}
.rotulo{font-size:10.5px;fill:var(--suave);text-anchor:middle;pointer-events:none;paint-order:stroke;
  stroke:var(--lienzo);stroke-width:4;stroke-linejoin:round}
.rotulo.vinculo{fill:var(--cyan)}.rotulo.peso{fill:var(--verde)}.rotulo.apagado{opacity:.2}
#flecha path{fill:var(--borde-fuerte)}#flechaCyan path{fill:var(--vinculo)}
table{width:100%;border-collapse:collapse;font-size:12px}
td{padding:8px 2px;vertical-align:top;border-bottom:1px solid var(--borde);overflow-wrap:anywhere}
td:first-child{color:var(--tenue);width:44%;padding-right:10px}td.mono{font-size:11.5px;word-break:break-all}
.prosa{font-size:13px;line-height:1.7;color:var(--suave)}.prosa p{margin:0 0 11px}
.prosa h1{font-size:17px;margin:16px 0 8px;color:var(--texto)}.prosa h2{color:var(--tenue);font-size:11px;margin:18px 0 8px}
.prosa h3{font-size:14px;margin:14px 0 6px;color:var(--texto)}.prosa li{margin:0 0 5px}
.cadena{font-size:11.5px;color:var(--suave);line-height:2}.cadena .fl{color:var(--tenue);padding:0 3px}
.cita{font-size:11px;color:var(--tenue);word-break:break-all;background:var(--panel2);
  border:1px solid var(--borde);border-radius:3px;padding:9px 11px}
.vacio{color:var(--tenue);font-size:12px}
details.sec{border:0;border-bottom:1px solid var(--borde);margin:5px 0;background:transparent;overflow:hidden}
details.sec>summary{cursor:pointer;list-style:none;padding:12px 0;font-size:12.5px;color:var(--suave);
  display:flex;align-items:center;gap:8px}
details.sec>summary::-webkit-details-marker{display:none}
details.sec>summary::before{content:"\25B8";color:var(--tenue);font-size:11px;display:inline-block;transition:transform .15s}
details.sec[open]>summary::before{transform:rotate(90deg)}details.sec>summary:hover{color:var(--texto)}
details.sec>summary b{color:var(--texto);font-weight:600}details.sec>summary .cuenta{margin-left:auto;font-size:11px;color:var(--tenue)}
details.sec .interior{padding:0 0 14px 16px}details.sub2{border-top:1px solid var(--borde);margin:0}
details.sub2>summary{padding:9px 0}details.sub2 .interior{padding:0 0 12px 12px}
.rotulo-grupo{margin:14px 0 5px;font-size:10.5px;color:var(--tenue);text-transform:uppercase;letter-spacing:.08em}
.nota-chica{font-size:11.5px;color:var(--tenue);margin:8px 0 0}
#velo{position:fixed;inset:0;background:#0d121770;display:none;align-items:center;justify-content:center;z-index:50}
#velo.visible{display:flex}.modal{width:min(580px,92vw);max-height:88vh;overflow-y:auto;background:var(--panel);
  border:1px solid var(--borde);border-radius:5px;padding:24px;box-shadow:var(--sombra)}
.modal h3{margin:0 0 8px;font-size:18px}.modal .intro{font-size:12.5px;color:var(--suave);line-height:1.65;margin-bottom:4px}
.modal label{display:block;font-size:11px;color:var(--tenue);margin:16px 0 6px;font-weight:600}
.modal textarea{width:100%;min-height:104px;padding:10px 12px;border:1px solid var(--borde);border-radius:4px;
  font:inherit;background:var(--panel);color:var(--texto);resize:vertical}
.modal .ayuda{font-size:11.5px;color:var(--tenue);margin-top:6px;line-height:1.55}
.modal .mal{font-size:12px;color:var(--alarma);min-height:17px;margin-top:10px}
.modal .pie{display:flex;gap:9px;justify-content:flex-end;margin-top:16px}
#aviso{position:fixed;left:50%;bottom:64px;transform:translateX(-50%);z-index:60;background:var(--verde-bg);
  border:1px solid var(--verde);color:var(--verde);padding:11px 18px;border-radius:4px;font-size:12.5px;display:none;max-width:80vw;box-shadow:var(--sombra)}
#aviso.visible{display:block}
#pie{position:absolute;left:16px;bottom:12px;font-size:11px;color:var(--tenue);pointer-events:none;
  background:var(--lienzo);padding:6px 0;max-width:calc(100% - 32px)}
#avisoGeneral{position:fixed;bottom:0;left:0;right:0;height:45px;padding:9px 18px;background:var(--panel);
  border-top:1px solid var(--borde);font-size:11px;color:var(--tenue);z-index:5;display:flex;align-items:center}
.revision{border-top:1px solid var(--borde);border-bottom:1px solid var(--borde);padding:15px 0;margin:18px 0}
.revision .fila{flex-wrap:wrap}.hallazgo{font-size:14px;line-height:1.65;margin:15px 0;color:var(--texto)}
.registro{border-bottom:1px solid var(--borde);padding:10px 0;font-size:12px;overflow-wrap:anywhere}
.calculo-paso{padding:12px 0;border-bottom:1px solid var(--borde);font-size:12.5px}.calculo-paso p{margin:5px 0}
.valor-evidencia{overflow-wrap:anywhere}:focus-visible{outline:2px solid var(--cyan);outline-offset:3px}
@media(max-width:1100px){#der{flex-basis:310px}#cabecera .contexto{display:none}#barra{gap:3px;padding:8px}#barra button{padding:6px 8px}#ruta{display:none}}
@media(max-width:760px){#der{flex-basis:270px}#izq:not(.plegado){position:absolute;top:58px;bottom:58px;left:0;width:260px;z-index:12;box-shadow:var(--sombra)}
  #cabecera{padding:0 12px;gap:8px}#cabecera strong{font-size:12px}#cabecera label{display:none}#cabecera .acciones{gap:4px}
  #cabecera .acciones button{padding:6px}#avisoGeneral{height:58px;font-size:10px}body{padding-bottom:58px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body>

<header id="cabecera">
  <span class="emblema" aria-hidden="true">⋈</span>
  <strong>Módulo de grafos</strong><span class="contexto">Bóveda CIJ · Vinculaciones</span>
  <div class="acciones">
    <button id="abrirFiltros" title="Buscar, importar y filtrar reportes">Filtros y reportes</button>
    <button id="abrirHistorial">Revisiones</button>
    <label for="tema">Apariencia</label>
    <select id="tema" aria-label="Apariencia"><option value="claro">Claro</option><option value="oscuro">Oscuro</option></select>
  </div>
</header>
<aside id="izq" class="plegado" aria-label="Filtros y reportes">
  <button class="plegar" id="plegIzq" title="Abrir o plegar filtros" aria-label="Abrir o plegar filtros">☰</button>
  <div class="contenido">
    <h1>Vinculaciones</h1>
    <div class="sub" id="meta"></div>

    <h2>Incorporar reportes</h2>
    <div style="font-size:11.5px;color:var(--tenue);line-height:1.55;margin-bottom:8px">
      Incorporá reportes JSON para analizar sus conexiones con los reportes cargados. El procesamiento es local.</div>
    <input type="file" id="archivos" multiple accept=".json,application/json"
           style="display:none">
    <div class="fila"><button id="btnImportar">Elegir archivos...</button></div>
    <div id="importados"></div>

    <h2>Buscar en el caso</h2>
    <input type="text" id="buscar" aria-label="Buscar en el caso" placeholder="cuenta, IP, dispositivo, alias...">

    <h2>Antecedentes a revisar</h2>
    <div id="alertas"></div>
    <h2>Revisión del reporte</h2>
    <button id="btnRevisiones">Ver pendientes e historial</button>

    <h2>Qué se muestra</h2>
    <div class="rotuloGrupo">Peso mínimo de la vinculación</div>
    <div class="fila">
      <input type="range" id="peso" min="0" max="100" value="0" style="flex:1">
      <span class="sub" id="pesov" style="min-width:34px;text-align:right">0,00</span>
    </div>
    <label><input type="checkbox" id="verPesos">
      Escribir el peso sobre la línea</label>
    <label><input type="checkbox" id="verCruces">
      Dibujar las líneas de un dato hacia los otros reportes donde consta</label>
    <label><input type="checkbox" id="soloComp">
      Solo los datos que comparte con otro reporte</label>

    <div class="rotuloGrupo">Tipos de dato</div>
    <div id="tipos"></div>

    <h2>Cómo leer el lienzo</h2>
    <div id="leyenda"></div>

  </div>
</aside>

<div class="asa" id="asaIzq"></div>

<main id="centro">
  <div id="barra">
    <div class="grupo">
      <button id="atras" title="Volver (Alt + ←)">‹ Volver</button>
      <button id="adelante" title="Siguiente (Alt + →)">Siguiente ›</button>
    </div>
    <select id="selCaso" title="Caso en curso" aria-label="Caso en curso"></select>
    <button class="solo" id="contraer">Contraer todo</button>
    <button class="solo" id="desplegar">Desplegar todo</button>
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
  <nav id="navDetalle" aria-label="Navegación del detalle">
    <button class="historia" id="atrasDetalle" title="Volver a la ficha y vista anteriores (Alt + ←)" disabled>‹ Volver</button>
    <button class="historia" id="adelanteDetalle" title="Recuperar la ficha siguiente (Alt + →)" disabled>Siguiente ›</button>
    <button class="plegar" id="plegDer" title="Abrir o plegar detalle" aria-label="Abrir o plegar detalle">›</button>
  </nav>
  <div class="contenido" id="cuerpo"></div>
</aside>

<div id="velo"><div class="modal" id="modal" role="dialog" aria-modal="true" aria-label="Registrar decisión"></div></div>
<div id="aviso" role="status" aria-live="polite"></div>
<footer id="avisoGeneral">El módulo detecta conexiones entre reportes; no determina autoría ni responsabilidad.
  La incorporación a una actuación requiere revisión humana. Los puntajes ordenan las vinculaciones: no son porcentajes de acierto.</footer>

<script>
const D = __DATOS__;
const NODOS = new Map(D.nodos.map(n=>[n.id,n]));
const ARISTAS = new Map(D.aristas.map(a=>[a.id,a]));
const CASOS = D.casos || [];
// El lienzo representa relaciones vigentes; el índice completo conserva la revisión.
const VINCULOS = D.aristas.filter(a=>a.entreReportes && a.vigente!==false && a.estado!=="rechazada");
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

/* Ubicación dentro del JSON recibido, expresada para lectura humana.
   Los índices técnicos empiezan en cero; al operador se muestran desde uno.
   Un índice vacío no identifica una posición y no se inventa una. */
const CAMPOS_FUENTE = {
  reportedInformation:["Información reportada"],
  reportingEsp:["Proveedor que envió el reporte"], espName:["Nombre del proveedor"],
  reportedPeople:["Personas reportadas"], reportedPersons:["Personas reportadas","Persona"],
  childVictims:["Víctimas menores de edad","Persona"],
  intendedRecipients:["Destinatarios previstos","Persona"],
  sourceInformation:["Registros capturados por la plataforma"], sourceCaptures:["Registros técnicos","Registro"],
  captureType:["Tipo de registro"], valueType:["Tipo de identificador"],
  value:["Valor informado"], eventName:["Evento informado"], dateTime:["Fecha y hora"], port:["Puerto de origen"],
  espUserId:["Identificador de cuenta"], profileBio:["Biografía del perfil"],
  displayNames:["Nombres visibles","Nombre visible"], screenNames:["Nombres de usuario","Nombre de usuario"],
  screenName:["Nombre de usuario"], phones:["Teléfonos","Teléfono"], emails:["Correos electrónicos","Correo electrónico"],
  espEstimatedLocations:["Ubicaciones estimadas por la plataforma","Ubicación estimada"],
  incidentDetails:["Detalles del incidente"], chatIncident:["Chats","Chat"], notes:["Notas","Nota"],
  automatedInformation:["Información automática"], autoGeneratedNotes:["Resultados generados automáticamente"],
  geoLookups:["Consultas de geolocalización"],
  reportedPersonGeoLookups:["Resultados sobre personas reportadas","Resultado sobre personas reportadas"],
  childVictimGeoLookups:["Resultados sobre víctimas menores de edad","Resultado sobre víctimas menores de edad"],
  intendedRecipientGeoLookups:["Resultados sobre destinatarios","Resultado sobre destinatarios"],
  esp:["Prestador informado"], ip:["Dirección IP"], ipAddress:["Dirección IP"],
  country:["País"], city:["Ciudad"], region:["Región"],
  lawEnforcementContactInformation:["Autoridades destinatarias"],
  lawEnforcementContacts:["Organismos destinatarios","Organismo destinatario"], agency:["Nombre del organismo"],
  uploadedFiles:["Archivos adjuntos","Archivo adjunto"], fileDetails:["Detalles de archivos","Archivo"],
  fileName:["Nombre del archivo"], hash:["Huella del archivo"], md5:["Huella MD5"], sha1:["Huella SHA-1"], sha256:["Huella SHA-256"]
};
function ubicacionFuente(ruta){
  const original = String(ruta||"").trim();
  if(!original) return "La fuente no informa una ubicación específica.";
  if(original.includes(" | ")) return [...new Set(original.split(" | ").map(ubicacionFuente))].join("; ");
  const libro = original.match(/^libro:vinculos_manuales#(\d+)$/);
  if(libro) return "Registro de decisiones → Vinculación manual "+libro[1];
  if(/^e_[a-f0-9]+$/i.test(original)) return "Relación utilizada como antecedente (identificador en auditoría)";
  if(original.startsWith("USA_CUENTA -> ")) return "Antecedente de asociación con una cuenta";
  const partes = original.split("#"), etiquetas = [];
  let desconocido = false;
  for(const segmento of partes[0].split(".")){
    const m = segmento.match(/^([A-Za-z][A-Za-z0-9_]*)(?:\[(\d*)\])?$/);
    const meta = m && CAMPOS_FUENTE[m[1]];
    if(!meta){ desconocido = true; break; }
    const indice = m[2];
    const texto = indice!==undefined && indice!==""
      ? (meta[1]||meta[0])+" "+(Number(indice)+1) : meta[0];
    if(etiquetas[etiquetas.length-1]!==texto) etiquetas.push(texto);
  }
  if(desconocido) return "Referencia de origen sin traducción disponible; consulte el detalle técnico de auditoría.";
  if(partes.length>1){
    const perfil = partes.slice(1).join("#").match(/^Profile=(.+)$/);
    etiquetas.push(perfil ? "Identificador de perfil extraído: "+perfil[1] : "Fragmento identificado en auditoría");
  }
  return etiquetas.join(" → ");
}

/* Tipos de dato que pueden aparecer en la fila de datos, en el orden en que se
   ofrecen en el panel. Sale de la ontologia, no de una lista escrita a mano. */
const TIPOS_DATO = Object.keys(D.tipos||{}).filter(t=>D.tipos[t].enTarjeta);
const VARIABLES_TIPO = {
  CUENTA:"cuenta",ALIAS:"alias",ALIAS_PAGO:"alias-pago",EMAIL:"email",TELEFONO:"telefono",IP:"ip",
  DISPOSITIVO:"dispositivo",EVIDENCIA:"evidencia",UBICACION:"ubicacion",IDENTIDAD:"identidad",
  PERSONA_MENCION:"identidad",ORGANIZACION:"organizacion",REPORTE:"reporte",EVENTO:"reporte"
};
const COLOR_TIPO = t => VARIABLES_TIPO[t] ? "var(--tipo-"+VARIABLES_TIPO[t]+")" : "var(--suave)";
const NOMBRE_TIPO = t => (D.tipos[t]||{}).legible || t;

const estado = {caso:null, raiz:null, abiertos:new Set(), sel:null,
                texto:"", pesoMin:0, verPesos:false, verCruces:false, soloCompartidos:false,
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
/* Relaciones cuyo destino aporta un detalle del dato, sin sumar otra caja.
   El prestador de una IP no es su titular ni identifica a quien la utilizó. */
const RELACIONES_EN_TARJETA = {ASIGNADA_A: true};
function detallesDe(id){
  return [...new Set(D.aristas
    .filter(a=>a.a===id && RELACIONES_EN_TARJETA[a.relacion]
               && a.vigente!==false && a.estado!=="rechazada")
    .map(a=>NODOS.get(a.b))
    .filter(n=>n && n.etiqueta)
    .map(n=>n.etiqueta))];
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
/* ================================================== decisiones del operador ==
   Servido por `servidor.py`, el botón escribe de verdad: el servidor registra
   en el libro, reconstruye el grafo y la pantalla se actualiza. Abierto como
   archivo suelto no hay a quién pedirle nada, y ahí el botón explica cómo
   abrir la aplicación en lugar de fingir que funciona.

   Quien usa esto no entra a una consola. Todo lo que haya que declarar —quién
   dispone la decisión y con qué fundamento— se pide en pantalla. */
const EN_APP = location.protocol === "http:" || location.protocol === "https:";
let focoAnterior = null;

function operadorGuardado(){
  try { return localStorage.getItem("bcij_operador") || ""; } catch(e){ return ""; }
}
function recordarOperador(v){
  try { localStorage.setItem("bcij_operador", v); } catch(e){}
}
function avisar(texto){
  if(!texto) return;
  const a = document.getElementById("aviso");
  a.textContent = texto; a.classList.add("visible");
  setTimeout(()=>a.classList.remove("visible"), 7000);
}
function cerrarDialogo(){
  document.getElementById("velo").classList.remove("visible");
  document.getElementById("modal").innerHTML = "";
  if(focoAnterior && focoAnterior.isConnected) focoAnterior.focus();
}
function dialogo(cfg){
  focoAnterior = document.activeElement;
  const velo = document.getElementById("velo"), m = document.getElementById("modal");
  m.innerHTML =
    '<h3 id="dlgTitulo">'+esc(cfg.titulo)+'</h3>'+
    '<div class="intro">'+cfg.intro+'</div>'+
    '<label for="dlgOperador">Operador que registra la decisión</label>'+
    '<input type="text" id="dlgOperador" placeholder="su identificación de operador" value="'+
      esc(operadorGuardado())+'">'+
    '<label for="dlgMotivo">'+esc(cfg.etiquetaMotivo)+'</label>'+
    '<textarea id="dlgMotivo" placeholder="'+esc(cfg.motivoObligatorio ?
      'Explique el motivo de la decisión.' : 'Observación opcional.')+'"></textarea>'+
    '<div class="ayuda">'+cfg.ayuda+'</div>'+
    '<div class="mal" id="dlgMal"></div>'+
    '<div class="pie"><button id="dlgCancelar">Cancelar</button>'+
    '<button class="primario" id="dlgAceptar">'+esc(cfg.aceptar)+'</button></div>';
  velo.classList.add("visible");
  const inpU = document.getElementById("dlgOperador");
  const inpM = document.getElementById("dlgMotivo");
  const mal = document.getElementById("dlgMal");
  const btn = document.getElementById("dlgAceptar");
  (operadorGuardado() ? inpM : inpU).focus();
  document.getElementById("dlgCancelar").onclick = cerrarDialogo;
  btn.onclick = ()=>{
    const usuario = inpU.value.trim(), motivo = inpM.value.trim();
    if(!usuario){ mal.textContent = "Falta indicar quién dispone la decisión."; return; }
    if(cfg.motivoObligatorio && !motivo){
      mal.textContent = "Escriba el motivo para registrar esta decisión.";
      return;
    }
    recordarOperador(usuario);
    mal.textContent = ""; btn.disabled = true; btn.textContent = "Registrando...";
    cfg.alAceptar(usuario, motivo).then(
      msg=>recargarCon(msg),
      err=>{ btn.disabled = false; btn.textContent = cfg.aceptar;
             mal.textContent = String(err && err.message ? err.message : err); });
  };
}
/* El servidor reconstruye el grafo entero después de escribir, de modo que lo
   que se ve sale siempre de una corrida completa y nunca de un parche en
   memoria. Se recarga conservando el caso en el que estaba el operador. */
function recargarCon(mensaje){
  /* Se guarda el REPORTE en análisis, no el legajo. El identificador de legajo
     es posicional: al vincular dos reportes los legajos se renumeran, y volver
     a "L003" deja al operador en un caso que no tiene nada que ver con el que
     estaba mirando. El reporte, en cambio, sigue siendo el mismo. */
  try {
    sessionStorage.setItem("bcij_aviso", mensaje || "");
    const c = caso();
    const r = estado.raiz || (c && c.reportes[0]);
    if(r) sessionStorage.setItem("bcij_reporte", r);
  } catch(e){}
  location.reload();
}
function pedir(ruta, cuerpo){
  return fetch(ruta, {method:"POST", headers:{"Content-Type":"application/json"},
                      body: JSON.stringify(cuerpo)})
    .then(r=>r.json().then(j=>({ok:r.ok, j})))
    .then(function(res){
      if(!res.ok || !res.j.ok) throw new Error(res.j.error || "no se pudo registrar");
      return res.j;
    });
}
function sinApp(que){
  const velo = document.getElementById("velo"), m = document.getElementById("modal");
  m.innerHTML =
    '<h3>Hay que abrir la aplicación</h3>'+
    '<div class="intro">Está viendo el archivo del grafo, que sirve para mirar: '+
    'no puede guardar nada. Para '+esc(que)+' hay que abrir la aplicación, que es '+
    'la que registra las decisiones.</div>'+
    '<div class="ayuda">Vuelva a la pestaña de la aplicación local que abrió '+
    'al iniciar el módulo. En este archivo descargado las revisiones no se guardan.</div>'+
    '<div class="pie"><button class="primario" id="dlgCerrar">Entendido</button></div>';
  velo.classList.add("visible");
  document.getElementById("dlgCerrar").onclick = cerrarDialogo;
}

/* Banco de pruebas: subir reportes y sacarlos, sin salir de la pantalla.
   El servidor los valida, los guarda y reconstruye el grafo entero; aca solo
   se leen los archivos y se informa que paso con cada uno. */
function pintarImportados(){
  const lista = D.importados || [];
  const cont = document.getElementById("importados");
  if(!cont) return;
  if(!lista.length){
    cont.innerHTML = '<div style="font-size:11.5px;color:var(--tenue);'+
      'font-style:italic">Ningún reporte importado. El caso se arma solo con '+
      'el dataset del proyecto.</div>';
    return;
  }
  cont.innerHTML =
    '<div class="rotuloGrupo">Importados (' + lista.length + ')</div>' +
    lista.map(r=>
      '<div style="display:flex;align-items:center;gap:6px;margin:4px 0">'+
      '<span class="chip boton" data-ir="reporte|REPORTE::'+esc(String(r).toLowerCase())+
      '" style="flex:1">'+esc(r)+'</span>'+
      '<button data-accion="quitarImportado" data-valor="'+esc(r)+
      '" title="Sacarlo del banco de pruebas" style="padding:4px 9px">Quitar</button>'+
      '</div>').join("");
}

function importarArchivos(archivos){
  if(!EN_APP) return sinApp("importar reportes");
  if(!archivos || !archivos.length) return;
  const lector = f => new Promise((ok,mal)=>{
    const fr = new FileReader();
    fr.onload = ()=>ok({nombre:f.name, contenido:String(fr.result)});
    fr.onerror = ()=>mal(new Error("no se pudo leer "+f.name));
    fr.readAsText(f, "utf-8");
  });
  const btn = document.getElementById("btnImportar");
  btn.disabled = true; btn.textContent = "Importando...";
  Promise.all([...archivos].map(lector))
    .then(lista=>pedir("/api/importar", {archivos:lista}))
    .then(function(j){
      const r = j.resultados || [];
      const bien = r.filter(x=>x.ok), mal = r.filter(x=>!x.ok);
      let msg = bien.length===1 ? "Se importó el reporte "+bien[0].reporte
              : "Se importaron "+bien.length+" reportes";
      const reemplazados = bien.filter(x=>x.reemplaza).length;
      if(reemplazados) msg += " ("+reemplazados+" reemplazó a uno que ya estaba)";
      msg += ".";
      if(mal.length) msg += " Quedaron afuera "+mal.length+": "+
        mal.map(x=>x.nombre+" — "+x.motivo).join("; ")+".";
      recargarCon(msg);
    })
    .catch(function(e){
      btn.disabled = false; btn.textContent = "Elegir archivos...";
      avisar("No se pudo importar: "+e.message);
    });
}

/* Confirmacion sin campos. No pide operador ni fundamento a proposito: sacar
   un archivo del banco de pruebas no es una decision sobre un caso y no entra
   en ningun libro. Pedir una identificacion ahi haria pensar que si. */
function confirmar(cfg){
  const velo = document.getElementById("velo"), m = document.getElementById("modal");
  m.innerHTML =
    '<h3>'+esc(cfg.titulo)+'</h3>'+
    '<div class="intro">'+cfg.intro+'</div>'+
    '<div class="mal" id="dlgMal"></div>'+
    '<div class="pie"><button id="dlgCancelar">Cancelar</button>'+
    '<button class="primario" id="dlgAceptar">'+esc(cfg.aceptar)+'</button></div>';
  velo.classList.add("visible");
  const mal = document.getElementById("dlgMal");
  const btn = document.getElementById("dlgAceptar");
  btn.focus();
  document.getElementById("dlgCancelar").onclick = cerrarDialogo;
  btn.onclick = ()=>{
    mal.textContent = ""; btn.disabled = true; btn.textContent = "Un momento...";
    cfg.alAceptar().then(
      msg=>recargarCon(msg),
      err=>{ btn.disabled = false; btn.textContent = cfg.aceptar;
             mal.textContent = String(err && err.message ? err.message : err); });
  };
}

function accionQuitarImportado(reporte){
  if(!EN_APP) return sinApp("quitar este reporte");
  confirmar({
    titulo: "Quitar el reporte "+reporte+" del banco de pruebas",
    intro: 'Sale de la carpeta de entrada y deja de procesarse. No toca el '+
      'dataset del proyecto ni los libros de decisiones: si alguien había '+
      'vinculado o validado algo sobre este reporte, ese registro se conserva '+
      'y vuelve a aplicarse si el reporte se importa de nuevo.',
    aceptar: "Quitar",
    alAceptar: function(){
      return pedir("/api/quitar", {reporte:reporte})
        .then(()=>"Reporte "+reporte+" quitado del banco de pruebas.");
    }
  });
}

function accionVincular(a, b){
  const actual = vinculoVigenteEntre(a, b);
  if(actual){ ir({tipo:"vinculo", id:actual.id}); return; }
  if(!EN_APP) return sinApp("vincular estos reportes");
  dialogo({
    titulo: "Vincular los reportes "+a+" y "+b,
    intro: 'Estos reportes no tienen una vinculación directa vigente. '+
      'Las coincidencias evaluadas no alcanzaron para proponerla automáticamente. '+
      'Puede registrar una vinculación directa por su propio criterio, con su nombre '+
      'y fundamento. Se agruparán en el mismo caso si todavía no lo estaban.',
    etiquetaMotivo: "Fundamento de la vinculación",
    ayuda: 'Queda asentado en el informe del caso y en el libro de '+
      'vinculaciones. La vinculación se conserva hasta que alguien la revierta, '+
      'y la reversión también queda asentada.',
    motivoObligatorio: true,
    aceptar: "Vincular",
    alAceptar: function(usuario, motivo){
      return pedir("/api/vincular", {reporte_a:a, reporte_b:b,
                                     usuario:usuario, motivo:motivo})
        .then(()=>"Reportes "+a+" y "+b+" vinculados. Quedaron en el mismo caso.");
    }
  });
}
function accionDesvincular(a, b){
  if(!EN_APP) return sinApp("revertir esta vinculación");
  dialogo({
    titulo: "Revertir la vinculación entre "+a+" y "+b,
    intro: 'La vinculación deja de aplicarse, pero el registro anterior no se '+
      'borra: la historia de la decisión se conserva completa.',
    etiquetaMotivo: "Motivo de la reversión",
    ayuda: 'Puede dejarlo vacío, aunque conviene asentar por qué se revierte.',
    motivoObligatorio: false,
    aceptar: "Revertir",
    alAceptar: function(usuario, motivo){
      return pedir("/api/desvincular", {reporte_a:a, reporte_b:b,
                                        usuario:usuario, motivo:motivo})
        .then(()=>"Vinculación entre "+a+" y "+b+" revertida.");
    }
  });
}

const ESTADOS_REVISION = {pendiente:"Pendiente de revisión", validada:"Validada",
  rechazada:"Rechazada", en_revision:"En revisión"};
function revisable(a){
  return a.origen!=="afirmada" && a.relacion!=="IDENTIFICADO_COMO";
}
function accionDecidir(id, decision){
  const a = ARISTAS.get(id);
  if(!a || !revisable(a)) return;
  if(!EN_APP) return sinApp("registrar la revisión");
  const identidad = a.relacion==="POSIBLE_MISMA_IDENTIDAD";
  const titulos = {validada:identidad?"Confirmar que es la misma persona":"Validar la vinculación",
    rechazada:"Rechazar la vinculación", en_revision:"Dejar en revisión"};
  const intro = decision==="rechazada"
    ? "Esta relación dejará de usarse en el análisis. Podrá recuperarla desde el historial de revisiones."
    : decision==="en_revision"
    ? "Queda en revisión y se incluye en el análisis. Si estaba rechazada, vuelve a estar activa."
    : identidad
    ? "Confirma que ambas menciones corresponden a la misma persona. El módulo agrupará esas menciones bajo una identidad."
    : "Confirma que revisó los datos que sostienen esta relación. La decisión quedará registrada.";
  dialogo({titulo:titulos[decision], intro:esc(intro),
    etiquetaMotivo:decision==="rechazada"?"Motivo del rechazo":"Observación (opcional)",
    ayuda:"La decisión se guarda con operador y fecha. Las revisiones anteriores se conservan.",
    motivoObligatorio:decision==="rechazada", aceptar:"Guardar decisión",
    alAceptar:function(usuario, observacion){
      return pedir("/api/decidir", {arista:id, decision, usuario, observacion}).then(()=>{
        try { sessionStorage.setItem("bcij_relacion", id); } catch(e){}
        return "Decisión guardada: "+ESTADOS_REVISION[decision]+".";
      });
    }});
}
function bloqueRevision(a){
  if(!revisable(a)) return "";
  const etiqueta = ESTADOS_REVISION[a.estado] || a.estadoLegible;
  let h = '<section class="revision" aria-label="Revisión"><b>'+esc(etiqueta)+'</b>';
  if(a.validado_por) h += '<div class="nota-chica">Registrado por '+esc(a.validado_por)+
    (a.validado_en?' · '+esc(a.validado_en.replace("T", " ")):'')+'</div>';
  if(a.estado==="rechazada") h += '<p class="nota-chica">Excluida del análisis. Puede cambiar esta decisión.</p>';
  h += '<div class="fila">';
  for(const [decision, etiquetaBoton] of [["validada",a.relacion==="POSIBLE_MISMA_IDENTIDAD"?
      "Confirmar identidad":"Validar"],["rechazada","Rechazar"],["en_revision","Dejar en revisión"]]){
    h += '<button '+(decision==="validada"?'class="primario" ':'')+
      'data-accion="decidir" data-arista="'+esc(a.id)+'" data-decision="'+decision+'"'+
      (a.estado===decision?' disabled':'')+'>'+etiquetaBoton+'</button>';
  }
  h += '</div></section>';
  if((a.historial||[]).length) h += seccion("Historial de revisiones", a.historial.length,
    a.historial.slice().reverse().map(r=>'<div class="registro"><b>'+esc(ESTADOS_REVISION[r.decision]||r.decision)+
      '</b> · '+esc(r.usuario)+'<div>'+esc((r.ts||"").replace("T"," "))+'</div>'+
      (r.observacion?'<div>'+esc(r.observacion)+'</div>':'')+'</div>').join(""));
  return h;
}

function fichaRevisiones(){
  const c = caso(), reporte = estado.raiz || (c && c.reportes[0]);
  const lista = D.aristas.filter(a=>revisable(a) && (a.reportes||[]).includes(reporte));
  let h = '<h3>Revisiones del reporte '+esc(reporte||"")+'</h3>';
  for(const [titulo, filtro] of [
    ["Vinculaciones", a=>a.entreReportes && a.estado!=="rechazada"],
    ["Hipótesis de identidad", a=>a.relacion==="POSIBLE_MISMA_IDENTIDAD" && a.estado!=="rechazada"],
    ["Rechazadas", a=>a.estado==="rechazada"],
    ["Otras relaciones", a=>!a.entreReportes && a.relacion!=="POSIBLE_MISMA_IDENTIDAD" && a.estado!=="rechazada"]]){
    const grupo = lista.filter(filtro);
    if(!grupo.length) continue;
    h += seccion(titulo, grupo.length, grupo.map(a=>'<button class="tarjeta" style="display:block;width:100%;text-align:left" '+
      'data-ir="'+(a.entreReportes?'vinculo':'relacion')+'|'+esc(a.id)+'">'+
      esc(etq(a.a))+' — '+esc(etq(a.b))+'<div class="nota-chica">'+esc(a.relacionLegible)+
      ' · '+esc(ESTADOS_REVISION[a.estado]||a.estadoLegible)+'</div></button>').join(""));
  }
  if(!lista.length) h += '<p>No hay relaciones para revisar.</p>';
  ficha(h);
}
/* La evaluación automática y la decisión humana son hechos diferentes.
   Consultar el estado vigente sin aplicar filtros visuales evita proponer
   otra vez una decisión que ya está registrada. */
function vinculoVigenteEntre(a, b){
  const par = VINCULOS.filter(v=>{
    const ra = (NODOS.get(v.a)||{}).valor, rb = (NODOS.get(v.b)||{}).valor;
    return (ra===a && rb===b) || (ra===b && rb===a);
  });
  return par.find(v=>v.origen==="afirmada") || par[0] || null;
}
function botonVincular(a, b){
  const vigente = vinculoVigenteEntre(a, b);
  if(vigente){
    const manual = vigente.origen==="afirmada";
    let h = '<div class="registro"><b>'+(manual
      ? 'Vinculación vigente por decisión de una persona'
      : 'Vinculación automática vigente')+'</b>';
    if(manual){
      h += '<p class="nota-chica">La registró '+esc(vigente.dispuestaPor||"un operador")+
        (vigente.validado_en?' · '+esc(vigente.validado_en.replace("T"," ")):'')+'.</p>';
      if(vigente.motivoOperador) h += '<p>Fundamento: '+esc(vigente.motivoOperador)+'</p>';
      h += '<p class="nota-chica">La línea del lienzo representa esta decisión. '+
        'No cambia el resultado de la evaluación automática anterior.</p>';
    }
    return h+'<div class="fila"><button data-ir="vinculo|'+esc(vigente.id)+
      '">Ver vinculación y decisión</button></div></div>';
  }
  const ca = casoDe(a), cb = casoDe(b), indirecta = ca && cb && ca.id===cb.id;
  const nota = indirecta
    ? '<p class="nota-chica">Pertenecen al mismo caso a través de otras vinculaciones. '+
      'Esta coincidencia no establece una relación directa entre ellos.</p>' : '';
  return nota+'<div class="fila"><button class="primario" data-accion="vincular" '+
    'data-a="'+esc(a)+'" data-b="'+esc(b)+'">'+
    (indirecta?'Registrar vínculo manual directo':'Vincular estos reportes')+'</button></div>';
}

/* Tarjeta de una coincidencia que se evaluó y no prosperó.
   Lleva el botón adentro: donde se dice que no alcanzó es donde el operador
   puede discrepar, y esta tarjeta aparece en la ficha del caso, en la del
   reporte y en la del dato. Si el botón vive afuera, en alguna de las tres
   falta —que fue justamente lo que pasó con la ficha del dato—. */
function tarjetaDescartada(x, idDato){
  const c = (x.compartido||[]).find(y=>y.nodo && RE(y.nodo)===idDato);
  const cuales = (x.compartido||[]).map(y=>y.valor).filter(Boolean);
  return '<div class="tarjeta">'+
    '<div style="font-size:12.5px"><b>Reporte '+esc(x.a)+'</b> y <b>Reporte '+
    esc(x.b)+'</b></div>'+
    '<div style="font-size:12px;color:var(--suave);margin-top:5px">'+
    esc(c ? c.texto : ("Comparten "+cuales.join(", ")+"."))+'</div>'+
    '<div style="font-size:12px;color:var(--tenue);margin-top:6px">'+
    esc(x.motivo||"")+'</div>'+
    botonVincular(x.a, x.b)+'</div>';
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
/* El historial guarda tambien COMO estaba el lienzo: que reporte en la cima y
   que cajas abiertas. Guardar solo la seleccion devolvia la ficha pero no el
   dibujo, y volver no recuperaba lo que se estaba mirando. */
/* La instantanea tiene que cubrir TODO lo que dibujar() lee del estado. Si se
   agrega un campo nuevo que cambie el dibujo, va tambien aca: guardar solo una
   parte hace que Volver devuelva la ficha anterior sobre un lienzo que ya es
   otro. Hay una prueba que compara ambas listas y falla si se desincronizan. */
function instantanea(){
  return {caso: estado.caso, raiz: estado.raiz, centro: estado.centro,
          abiertos: [...estado.abiertos], mov: [...estado.mov], verCruces: estado.verCruces,
          camara: {...VP}};
}
function anotarVista(){
  if(HIST.pos>=0) HIST.pila[HIST.pos].lienzo = instantanea();
}
/* Guardar la lectura antes de reemplazar la ficha. No guarda HTML ni decisiones:
   al volver se renderizan los datos vigentes y se repone la posición de lectura. */
function anotarDetalle(){
  const v = HIST.pila[HIST.pos];
  if(!v) return;
  // Si una acción ya pidió otro encuadre, su cámara aún pertenece a la vista
  // anterior. Las acciones de centrado guardan esa vista antes de cambiarla.
  if(VP.encuadrado && v.lienzo) v.lienzo.camara = {...VP};
  v.detalle = {
    scroll: document.getElementById("der").scrollTop,
    secciones: [...document.getElementById("cuerpo").querySelectorAll("details")]
      .map(d=>({titulo:d.querySelector("summary")?.textContent, abierta:d.open}))
  };
}
function restaurarDetalle(v){
  if(!v.detalle) return;
  const secciones = document.getElementById("cuerpo").querySelectorAll("details");
  secciones.forEach((d,i)=>{
    const anterior = v.detalle.secciones[i];
    if(anterior && anterior.titulo===d.querySelector("summary")?.textContent)
      d.open = anterior.abierta;
  });
  document.getElementById("der").scrollTop = v.detalle.scroll;
}
function restaurarVista(v){
  if(!v.lienzo) return;
  const f = v.lienzo;
  if(f.caso && f.caso!==estado.caso) aplicarCaso(f.caso);
  estado.raiz = f.raiz;
  estado.centro = f.centro;
  estado.abiertos = new Set(f.abiertos);
  estado.mov = new Map(f.mov);
  estado.verCruces = !!f.verCruces;
  document.getElementById("verCruces").checked = estado.verCruces;
  if(f.camara?.encuadrado){ Object.assign(VP, f.camara); pintarVP(); }
  else VP.encuadrado = false;
}
function ir(v, nuevaVista=false){
  const act = HIST.pila[HIST.pos];
  anotarDetalle();
  if(nuevaVista || !(act && act.tipo===v.tipo && act.id===v.id)){
    HIST.pila = HIST.pila.slice(0,HIST.pos+1); HIST.pila.push(v); HIST.pos++;
  }
  /* Solo se anota la entrada NUEVA. Anotar tambien la anterior la pisaria con
     el estado que la accion acaba de dejar -"Analizar este reporte" cambia la
     cima del arbol antes de navegar-, y volver traia ese estado en vez del que
     el operador tenia. Las acciones que cambian el lienzo sin navegar anotan
     por su cuenta. */
  anotarVista();
  mostrar(HIST.pila[HIST.pos]);
}
function atras(){
  if(HIST.pos<=0) return;
  anotarDetalle(); anotarVista(); HIST.pos--;
  restaurarVista(HIST.pila[HIST.pos]); mostrar(HIST.pila[HIST.pos]);
}
function adelante(){
  if(HIST.pos>=HIST.pila.length-1) return;
  anotarDetalle(); anotarVista(); HIST.pos++;
  restaurarVista(HIST.pila[HIST.pos]); mostrar(HIST.pila[HIST.pos]);
}
function mostrar(v){
  estado.sel = v;
  if(v.tipo==="reporte"){ fichaReporte(v.id); }
  else if(v.tipo==="entidad"){ fichaEntidad(v.id); }
  else if(v.tipo==="vinculo"){ fichaVinculo(v.id); }
  else if(v.tipo==="relacion"){ fichaRelacion(v.id); }
  else if(v.tipo==="revisiones"){ fichaRevisiones(); }
  else if(v.tipo==="informe"){ fichaInforme(); }
  else fichaCaso();
  document.getElementById("atras").disabled = HIST.pos<=0;
  document.getElementById("adelante").disabled = HIST.pos>=HIST.pila.length-1;
  document.getElementById("atrasDetalle").disabled = HIST.pos<=0;
  document.getElementById("adelanteDetalle").disabled = HIST.pos>=HIST.pila.length-1;
  const nombre = v.tipo==="inicio" ? "Caso"
    : v.tipo==="revisiones" ? "Revisiones"
    : v.tipo==="informe" ? "Informe"
    : v.tipo==="vinculo" ? "Vinculación"
    : v.tipo==="relacion" ? "Relación" : etq(v.id);
  document.getElementById("ruta").textContent = (HIST.pos>0?"◂ ":"")+nombre;
  dibujar();
  restaurarDetalle(v);
}
window.addEventListener("keydown",e=>{
  if(e.altKey && e.key==="ArrowLeft"){ e.preventDefault(); atras(); }
  if(e.altKey && e.key==="ArrowRight"){ e.preventDefault(); adelante(); }
});
document.getElementById("atras").onclick = atras;
document.getElementById("adelante").onclick = adelante;
document.getElementById("atrasDetalle").onclick = atras;
document.getElementById("adelanteDetalle").onclick = adelante;

/* ============================================================== lienzo ==== */
const SVGNS = "http://www.w3.org/2000/svg";
const gCon = document.getElementById("gcon"), gRot = document.getElementById("grot"),
      gCaj = document.getElementById("gcajas"), svg = document.getElementById("lienzo");
const ANCHO_CAJA = 250, ALTO_CAJA = 64, SEP_X = 34;
const X_RAIZ = 40, X_REL = 470, X_ENT = 880;
const PASO_Y = ALTO_CAJA + 34;
/* Franja entre la raíz y los reportes para los conectores y sus motivos. */
const CARRIL_VINC = X_RAIZ + ANCHO_CAJA + 76;

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
function caja(g, x, y, {titulo, sub, marca, marcaColor, color, clases, alClic,
                         alClicMarca, ayudaMarca}){
  const el = document.createElementNS(SVGNS,"g");
  el.setAttribute("class","caja "+(clases||""));
  el.setAttribute("transform","translate("+x+","+y+")");
  g.appendChild(el);                 // medir exige estar en el documento
  const r = document.createElementNS(SVGNS,"rect");
  r.setAttribute("class","cuerpo"); r.setAttribute("width",ANCHO_CAJA);
  r.setAttribute("height",ALTO_CAJA); r.setAttribute("rx",5);
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
    let marcaEl = m;
    if(anchoMarca > libre){
      el.removeChild(m);
      const pt = document.createElementNS(SVGNS,"circle");
      pt.setAttribute("cx",ANCHO_CAJA-14); pt.setAttribute("cy",21);
      pt.setAttribute("r",4);
      pt.setAttribute("fill",marcaColor||"var(--ambar)"); el.appendChild(pt);
      marcaEl = pt;
      ajustar(t, titulo, ANCHO_CAJA - 26 - 16);
    } else {
      ajustar(t, titulo, ANCHO_CAJA - 26 - anchoMarca - 12);
    }
    if(alClicMarca){
      marcaEl.classList.add("accion");
      marcaEl.setAttribute("role","button");
      marcaEl.setAttribute("tabindex","0");
      marcaEl.setAttribute("aria-label",ayudaMarca || marca);
      marcaEl.style.pointerEvents = "auto";
      const ayuda = document.createElementNS(SVGNS,"title");
      ayuda.textContent = ayudaMarca || marca; marcaEl.appendChild(ayuda);
      // El gesto pertenece a la marca, no a la selección ni al arrastre de la caja.
      marcaEl.addEventListener("pointerdown",e=>{ e.stopPropagation(); SEARRASTRO = false; });
      marcaEl.addEventListener("click",e=>{
        e.preventDefault(); e.stopPropagation(); alClicMarca();
      });
      marcaEl.addEventListener("keydown",e=>{
        if(e.key==="Enter" || e.key===" "){
          e.preventDefault(); e.stopPropagation(); alClicMarca();
        }
      });
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
/* Los conectores avanzan desde la raíz hacia los reportes y sus datos. */
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
/* Curvas continuas para seguir cada rama del mapa horizontal. */
function ruta(x1, y1, x2, y2, xm){
  // Una curva horizontal conserva la lectura raíz → reporte → dato.
  if(x2>=x1){
    const medio = (x1+x2)/2;
    return "M"+x1+","+y1+" C"+medio+","+y1+" "+medio+","+y2+" "+x2+","+y2;
  }
  // Los cruces de un dato hacia otros reportes usan carriles exteriores.
  const carr = Math.max(x1,x2)+32+(xm||0)%78;
  return "M"+x1+","+y1+" C"+carr+","+y1+" "+carr+","+y2+" "+x2+","+y2;
}

/* Grosor de una linea segun el peso de la vinculacion.

   La escala es absoluta -de 0,5 a 1- y no relativa al caso que se este
   mirando: si dependiera del maximo del caso, la misma vinculacion se veria
   distinta segun con quien la comparta la pantalla, y dejaria de poder
   compararse entre casos. */
const PESO_MINIMO_ESCALA = 0.5, GRUESO_MIN = 1.3, GRUESO_MAX = 4.4;
function grosorPorPeso(peso){
  if(peso==null) return null;
  const t = Math.max(0, Math.min(1, (peso-PESO_MINIMO_ESCALA)/(1-PESO_MINIMO_ESCALA)));
  return (GRUESO_MIN + t*(GRUESO_MAX-GRUESO_MIN)).toFixed(2);
}

function conector(desde, hasta, {clase, rotulo, peso, alClic, color, carril,
                                 dato, punto, apagado, realzado}){
  const x1 = desde.x, y1 = desde.y, x2 = hasta.x, y2 = hasta.y;
  const ym = carril!=null ? carril : (x1 + (x2-x1)/2);
  const d = ruta(x1,y1,x2,y2,ym);
  const cl = "con "+(clase||"")+(apagado?" apagada":"")+(realzado?" realzada":"");
  const p = document.createElementNS(SVGNS,"path");
  p.setAttribute("class",cl);
  p.setAttribute("d",d);
  // style y no setAttribute: el atributo de presentación pierde contra
  // cualquier regla de la hoja de estilos, y .con ya define un stroke.
  if(color) p.style.stroke = color;
  // El grosor lo fija el peso, no la hoja de estilos: es el unico lugar donde
  // se conoce el valor de esta vinculacion en particular.
  const grueso = grosorPorPeso(peso);
  if(grueso) p.style.strokeWidth = grueso;
  if(dato) p.setAttribute("data-dato",dato);
  const colorPunta = color || ((clase||"").includes("afirmada") ? "var(--afirmada)"
    : (clase||"").includes("inferida") ? "var(--inferida)"
    : (clase||"").includes("duplicado") ? "var(--duplicado)"
    : (clase||"").includes("vinculo") ? "var(--vinculo)" : "var(--borde-fuerte)");
  p.setAttribute("marker-end",marcador(colorPunta));
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
    const lineas = envolver(rotulo, 23).slice(0,3);
    if(peso!=null && estado.verPesos) lineas.push("peso "+num(peso));
    // 14 y no 12: con 12 el alto real de un renglón de 10px -acentos y colas
    // incluidos- llega a tocar el de abajo. La auditoría lo detecta.
    const alto = 14, base = y2 - 12 - (lineas.length-1)*alto;
    lineas.forEach((ln,i)=>{
      const esPeso = (peso!=null && estado.verPesos && i===lineas.length-1);
      const t = document.createElementNS(SVGNS,"text");
      t.setAttribute("class","rotulo "+(esPeso ? "peso" : "vinculo")+
                              (apagado?" apagado":""));
      t.setAttribute("x",x2-95); t.setAttribute("y",base+i*alto);
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
/* El alcance se realza sobre las cajas existentes: no cambia la disposición,
   la selección ni el historial, y no vuelve a dibujar el grafo. */
function marcarAlcance(nodo, on){
  const reportes = new Set(otrosReportesDe(nodo));
  gCaj.querySelectorAll("[data-reporte]").forEach(el=>{
    const contiene = reportes.has(el.getAttribute("data-reporte"));
    el.classList.toggle("alcance", on && contiene);
    el.classList.toggle("fuera", on && !contiene);
  });
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

  // Cada reporte ocupa el alto de sus datos abiertos: no se pisan ramas.
  const pos = new Map();
  let cursor = 65;
  const propios = entidades.filter(e=>e.padre.id===nRaiz.id);
  propios.forEach((e,i)=>pos.set(e.nodo.id,{x:X_ENT,y:cursor+i*PASO_Y}));
  if(propios.length) cursor += propios.length*PASO_Y+35;
  relacionados.forEach(r=>{
    const hijos = entidades.filter(e=>e.padre.id===r.nodo.id);
    const alto = Math.max(PASO_Y,hijos.length*PASO_Y);
    pos.set(r.nodo.id,{x:X_REL,y:cursor+(alto-PASO_Y)/2});
    hijos.forEach((e,i)=>pos.set(e.nodo.id,{x:X_ENT,y:cursor+i*PASO_Y}));
    cursor += alto+28;
  });
  const ys = relacionados.map(r=>pos.get(r.nodo.id).y);
  pos.set(nRaiz.id,{x:X_RAIZ,y:ys.length ? (ys[0]+ys[ys.length-1])/2 : 95});

  // Posición efectiva: la que calcula la disposición, más lo que el operador
  // haya corrido esa caja a mano.
  const P = id => { const p = pos.get(id), m = estado.mov.get(id);
                    return m ? {x:p.x+m.dx, y:p.y+m.dy} : p; };
  const abajo = p => ({x:p.x+ANCHO_CAJA, y:p.y+ALTO_CAJA/2});
  const arriba = p => ({x:p.x, y:p.y+ALTO_CAJA/2});

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
  if(estado.verCruces){
    let carril = X_ENT + ANCHO_CAJA + 40;
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
  }

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
    el.setAttribute("data-reporte",nodo.valor);
    arrastrable(el, nodo.id);
    if(n) botonMas(gCaj, p.x+ANCHO_CAJA+15, p.y+ALTO_CAJA/2,
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
      titulo:e.nodo.etiqueta, sub:[e.nodo.tipoLegible,...detallesDe(e.nodo.id)].join(" · "),
      marca: enN>1 ? "en "+enN+" reportes ›" : (afuera ? "en otros casos" : null),
      alClicMarca: enN>1 ? ()=>centrarEn(e.nodo.id) : null,
      ayudaMarca: enN>1 ? "Poner este dato en el centro y ver los "+enN+" reportes en los que consta" : null,
      marcaColor: enN>1 ? null : "var(--tenue)",
      color: COLOR_TIPO(e.nodo.tipo),
      clases: extra(e.nodo.id)+(apagada?" apagada":"")
              +(focoDato===e.nodo.id ? " realzada":""),
      alClic:()=>alternarFoco({tipo:"entidad", id:e.nodo.id})});
    arrastrable(el, e.nodo.id);
    el.addEventListener("mouseenter",()=>{
      marcarCruces(e.nodo.id,true); marcarAlcance(e.nodo,true);
    });
    el.addEventListener("mouseleave",()=>{
      marcarCruces(e.nodo.id,false); marcarAlcance(e.nodo,false);
    });
    el.addEventListener("focusin",()=>marcarAlcance(e.nodo,true));
    el.addEventListener("focusout",()=>marcarAlcance(e.nodo,false));
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
  anotarVista();
  VP.encuadrado = false;
  dibujar();
}
function encuadrar(){
  const b = document.getElementById("vista").getBBox();
  const r = svg.getBoundingClientRect();
  if(!b.width || !r.width) return;
  const k = Math.max(.08,Math.min((r.width-64)/b.width, (r.height-70)/b.height, 1.15));
  VP.k = k;
  VP.x = (r.width-b.width*k)/2-b.x*k;
  VP.y = (r.height-b.height*k)/2-b.y*k-8;
  pintarVP();
}
document.getElementById("ajustar").onclick = ()=>{ encuadrar(); };
document.getElementById("contraer").onclick = ()=>{
  estado.abiertos.clear(); anotarVista(); VP.encuadrado = false; dibujar();
};
document.getElementById("desplegar").onclick = ()=>{
  const c=caso(); if(!c) return;
  c.reportes.forEach(r=>{const n=nodoReporte(r);if(n) estado.abiertos.add(n.id);});
  anotarVista(); VP.encuadrado = false; dibujar();
};
document.getElementById("ordenar").onclick = ()=>{
  estado.mov.clear(); anotarVista(); VP.encuadrado = false; dibujar(); };

/* Poner un dato en el centro: el árbol se cuelga de él y la fila de abajo pasa
   a ser la de los reportes en los que consta. Es la vista para investigar un
   identificador -una cuenta, un dispositivo- en lugar de un reporte. */
function centrarEn(id){
  const centro = id || null, cambio = estado.centro!==centro;
  // La caja puede estar seleccionada antes de tocar su marca. Cambiar el
  // centro es otra vista aunque la ficha sea la misma: Volver debe conservarla.
  anotarVista();
  estado.centro = centro;
  if(cambio){
    estado.abiertos.clear(); estado.mov.clear();
    VP.encuadrado = false;
  }
  ir(id ? {tipo:"entidad", id:id} : {tipo:"inicio"}, cambio);
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
    anotarVista();
    estado.raiz = acc.dataset.valor; estado.abiertos.clear(); estado.mov.clear();
    VP.encuadrado = false; ir({tipo:"inicio"});
  }
  if(acc.dataset.accion==="abrir"){ estado.abiertos.add(acc.dataset.valor); anotarVista(); dibujar(); }
  if(acc.dataset.accion==="quitarImportado"){ accionQuitarImportado(acc.dataset.valor); }
  if(acc.dataset.accion==="centrar"){ centrarEn(acc.dataset.valor); }
  if(acc.dataset.accion==="descentrar"){ centrarEn(null); }
  if(acc.dataset.accion==="vincular"){ accionVincular(acc.dataset.a, acc.dataset.b); }
  if(acc.dataset.accion==="desvincular"){ accionDesvincular(acc.dataset.a, acc.dataset.b); }
  if(acc.dataset.accion==="decidir"){ accionDecidir(acc.dataset.arista, acc.dataset.decision); }
  if(acc.dataset.accion==="revisiones"){ ir({tipo:"revisiones"}); }
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
    return id===destacado ? "<b style='color:var(--cyan)'>"+t+"</b>"
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
    h += '<h2>Evaluación automática de coincidencias ('+desc.length+')</h2>';
    desc.forEach(x=>{
      const otro = x.a===raizVal ? x.b : x.a, oc = casoDe(otro);
      h += '<div class="tarjeta click" data-accion="otroCaso" data-valor="'+esc(otro)+'">'+
        '<div style="font-size:12.5px"><b>Reporte '+esc(otro)+'</b>'+
        (oc && oc.id!==c.id ? ' <span class="sub">· '+esc(oc.etiqueta)+'</span>':'')+
        '</div><div style="font-size:12px;color:var(--suave);margin-top:5px">'+
        'Comparten '+esc((x.compartido||[]).map(y=>y.valor).filter(Boolean).join(", "))+
        '.</div><div style="font-size:12px;color:var(--tenue);margin-top:6px">'+
        esc(x.motivo||"")+'</div></div>'+
        botonVincular(raizVal, otro);
    });
    h += '<div class="prosa"><p style="font-size:11.5px;color:var(--tenue)">'+
      'La evaluación automática se conserva aunque una persona decida vincular los reportes. '+
      'La decisión vigente, su operador y su fundamento se consultan en la ficha de vinculación.</p></div>';
  }

  h += '<h2>Otros reportes del caso</h2>';
  const otros = c.reportes.filter(r=>r!==raizVal);
  h += otros.length
    ? otros.map(r=>'<span class="chip boton" data-accion="raiz" data-valor="'+r+
        '">analizar '+esc(r)+'</span>').join("")
    : '<div class="vacio">Ninguno: el caso es este solo reporte.</div>';
  ficha(h);
}

/* Resumen brevisimo de por que dos reportes quedaron vinculados. Sale de la
   propia arista, asi que sirve igual para una vinculacion derivada por regla,
   una que dispuso un operador o cualquier otra que se agregue despues. */
function porQueEnUnaLinea(a){
  if(a.origen==="afirmada"){
    const quien = a.dispuestaPor ? esc(a.dispuestaPor) : "un operador";
    const fundamento = (a.motivoOperador||"").trim();
    return "La dispuso "+quien+"."+(fundamento? " "+esc(fundamento) : "");
  }
  const m = (a.motivo||"").trim();
  const frase = m ? m.charAt(0).toUpperCase()+m.slice(1)+"." : "Comparten un dato objetivo.";
  return frase;
}

/* Lista las entidades de un reporte marcando las que tambien estan en otro.
   La comparacion es por identidad de nodo, no por texto: vale para cualquier
   par de reportes y para cualquier tipo de dato que se agregue a la ontologia. */
function listaEntidades(valorReporte, valorContra){
  const propias = datosDe(valorReporte);
  if(!propias.length) return '<div class="vacio">Sin datos registrados.</div>';
  const contra = valorContra
    ? new Set(datosDe(valorContra).map(m=>m.id)) : new Set();
  const ordenadas = propias.slice().sort((x,y)=>{
    const cx = contra.has(x.id)?0:1, cy = contra.has(y.id)?0:1;
    if(cx!==cy) return cx-cy;
    if(x.tipoLegible!==y.tipoLegible) return x.tipoLegible.localeCompare(y.tipoLegible);
    return String(x.etiqueta).localeCompare(String(y.etiqueta));
  });
  let h = "";
  let grupo = null;
  ordenadas.forEach(m=>{
    const coincide = contra.has(m.id);
    const g = coincide ? "\u2713 también en este reporte" : m.tipoLegible;
    if(g!==grupo){ grupo = g; h += '<div class="rotulo-grupo">'+esc(g)+'</div>'; }
    const otros = otrosReportesDe(m).length;
    h += '<span class="chip boton'+(coincide?" coincide":"")+
      '" data-ir="entidad|'+m.id+'">'+esc(m.etiqueta)+
      (otros>1? ' <b style="color:var(--ambar)">\u00b7'+otros+'</b>':'')+'</span>';
  });
  return h;
}

function fichaReporte(id){
  const n = NODOS.get(id); if(!n){ fichaCaso(); return; }
  const at = attr(n);
  const vinc = vinculosDe(id).sort((a,b)=>(b.confianza||0)-(a.confianza||0));
  const datos = datosDe(n.valor);
  const desc = descartadosDelReporte(n.valor);
  const idn = identidadDe(n.valor);
  const esRaiz = (estado.raiz || caso().reportes[0]) === n.valor;

  // Encabezado: lo minimo para saber que reporte es y en que estado esta.
  let h = '<span class="chip cy">Reporte</span>'+
    (esRaiz?'<span class="chip">en análisis</span>':'')+
    '<h3>Reporte '+esc(n.valor)+'</h3>'+
    '<div class="sub" style="font-family:inherit;font-size:12px">'+
    esc([at["Plataforma"], legible(at["Motivo del archivo"]) ||
         legible(at["Estado en SIPAR"])].filter(Boolean).join(" \u00b7 "))+
    '</div>';
  if(!esRaiz){
    h += '<div class="fila"><button data-accion="raiz" data-valor="'+
      esc(n.valor)+'">Analizar este reporte</button></div>';
  }

  // --- vinculaciones: es la pregunta que el operador vino a responder -------
  let cuerpo = vinc.length ? "" :
    '<div class="vacio">Este reporte no quedó vinculado con ningún otro.</div>';
  vinc.forEach(a=>{
    const otro = NODOS.get(a.a===id?a.b:a.a);
    cuerpo += '<details class="sec sub2"><summary><b>Reporte '+esc(otro.valor)+'</b>'+
      '<span class="cuenta">'+(a.confianza!=null? "peso "+num(a.confianza)
                                                : "por un operador")+
      '</span></summary><div class="interior">'+
      '<div style="font-size:12.5px;color:var(--suave);margin:2px 0 6px">'+
      porQueEnUnaLinea(a)+'</div>'+
      listaEntidades(otro.valor, n.valor)+
      '<div class="fila"><button data-ir="vinculo|'+a.id+
      '">Ver coincidencia y revisar</button></div>'+
      '</div></details>';
  });
  h += seccion("Vinculaciones", vinc.length, cuerpo);

  // --- entidades del propio reporte ----------------------------------------
  h += seccion("Entidades", datos.length,
    listaEntidades(n.valor, null)+
    '<div class="nota-chica">El número en ámbar indica en cuántos reportes del '+
    'caso aparece ese dato.</div>'+
    '<div class="fila"><button data-accion="abrir" data-valor="'+id+
    '">Mostrarlas en el gráfico</button></div>');

  // --- coincidencias evaluadas que no prosperaron --------------------------
  if(desc.length){
    let cuerpoDesc =
      '<div class="nota-chica" style="margin:0 0 8px">Comparten algún dato con '+
      'éste, pero esos datos no bastaron para proponer una vinculación automática. '+
      'Debajo de cada evaluación se indica si una persona registró una vinculación.</div>';
    desc.forEach(x=>{
      const otro = x.a===n.valor ? x.b : x.a;
      const c = casoDe(otro);
      cuerpoDesc += '<div class="tarjeta click" data-accion="otroCaso" data-valor="'+esc(otro)+'">'+
        '<div style="font-size:12.5px"><b>Reporte '+esc(otro)+'</b>'+
        (c? ' <span class="sub">· '+esc(c.etiqueta)+'</span>':'')+'</div>'+
        '<div style="font-size:12px;color:var(--suave);margin-top:5px">Comparten '+
        esc((x.compartido||[]).map(y=>y.valor).filter(Boolean).join(", "))+'.</div>'+
        '<div style="font-size:12px;color:var(--tenue);margin-top:6px">'+
        esc(x.motivo||"")+'</div></div>'+
        botonVincular(n.valor, otro);
    });
    h += seccion("Evaluación automática de coincidencias", desc.length, cuerpoDesc);
  }

  // --- identidad unificada, solo si un operador la confirmo ----------------
  if(idn && otrosReportesDe(idn).length>1){
    h += seccion("Identidad unificada", otrosReportesDe(idn).length+" reportes",
      '<div style="font-size:12.5px;color:var(--suave);line-height:1.6">'+
      'Un operador confirmó que las menciones de persona de '+
      otrosReportesDe(idn).map(r=>'<b>'+esc(r)+'</b>').join(", ")+
      ' corresponden a la misma persona. No es un dato del reporte: es una '+
      'decisión humana registrada.'+
      '</div><div class="fila"><button data-accion="revisiones">Revisar las decisiones de identidad</button></div>');
  }

  // --- la ficha tecnica, al final y cerrada -------------------------------
  h += seccion("Datos del reporte", null, tabla(n.atributos));

  ficha(h);
}

/* Una seccion plegada de la ficha. Todas arrancan cerradas: el panel deja leer
   una cosa por vez en vez de volcar el expediente entero. */
function seccion(titulo, cuenta, cuerpo){
  if(!cuerpo) return "";
  return '<details class="sec"><summary><b>'+esc(titulo)+'</b>'+
    (cuenta!=null ? '<span class="cuenta">'+esc(cuenta)+'</span>' : '')+
    '</summary><div class="interior">'+cuerpo+'</div></details>';
}

function fichaEntidad(id){
  const n = NODOS.get(id); if(!n){ fichaCaso(); return; }
  const enR = otrosReportesDe(n);
  const col = COLOR_TIPO(n.tipo);
  let h = '<span class="chip cy" style="border-color:'+col+'55;color:'+col+
    '"><span class="pt"></span>'+esc(n.tipoLegible)+'</span><h3>'+esc(n.etiqueta)+'</h3>';

  /* Investigar el dato en vez del reporte: el arbol se cuelga de el. Solo tiene
     sentido si consta en mas de un reporte del caso. */
  if(estado.centro===id){
    h += '<div class="fila"><button data-accion="descentrar">'+
      'Volver al reporte en análisis</button></div>';
  } else if(enR.length>1){
    h += '<div class="fila"><button class="primario" data-accion="centrar" '+
      'data-valor="'+id+'">Poner este dato en el centro</button></div>';
  }

  /* Lo primero que hay que contestar cuando alguien toca un dato es que
     vinculaciones sostiene, no en que reportes esta: para eso ya estan las
     lineas del lienzo. */
  const sostiene = VINCULOS.filter(a=>{
    const rs = reportesCaso();
    if(!(rs.has((NODOS.get(a.a)||{}).valor) && rs.has((NODOS.get(a.b)||{}).valor)))
      return false;
    return (a.puente||[]).some(x=>x.nodo && RE(x.nodo)===id);
  });
  let cuerpo = "";
  if(sostiene.length){
    sostiene.forEach(a=>{
      const tramo = (a.puente||[]).find(x=>x.nodo && RE(x.nodo)===id) || {};
      cuerpo += '<div class="tarjeta click" data-ir="vinculo|'+a.id+'">'+
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
    h += seccion("Vinculaciones que sostiene", sostiene.length, cuerpo);
  } else if(enR.length>1){
    h += seccion("Vinculaciones que sostiene", 0,
      '<div class="nota-chica" style="margin:0">Este dato aparece en más de un '+
      'reporte del caso, pero la vinculación entre ellos no se apoya en él. '+
      'Puede estar corroborando otra relación, o no alcanzar por sí solo para '+
      'individualizar.</div>');
  }

  cuerpo = "";
  enR.forEach(r=>{
    const nr = nodoReporte(r);
    cuerpo += '<div class="tarjeta click" data-ir="reporte|'+(nr?nr.id:"")+'">'+
      '<div style="font-size:12.5px"><b>Reporte '+esc(r)+'</b></div></div>';
  });
  h += seccion("Aparece en el caso", enR.length+" reportes", cuerpo);

  const fuera = fueraDelCaso(n);
  if(fuera.length){
    cuerpo = '<div class="nota-chica" style="margin:0 0 8px">Este mismo dato '+
      'aparece en reportes que no forman parte de este caso. Que no haya una '+
      'línea hacia ellos no significa que el sistema no lo haya visto: '+
      'no existe una vinculación vigente que los agrupe en este caso.'+
      '</div>';
    fuera.forEach(r=>{
      const c = casoDe(r);
      cuerpo += '<div class="tarjeta click" data-accion="otroCaso" data-valor="'+
        esc(r)+'"><div style="font-size:12.5px"><b>Reporte '+esc(r)+'</b></div>'+
        '<div class="sub" style="margin-top:3px">'+esc(c?c.etiqueta:"otro caso")+
        '</div></div>';
    });
    h += seccion("También en otros casos", fuera.length, cuerpo);
  }

  const desc = descartadosDelDato(id);
  if(desc.length){
    cuerpo = "";
    desc.forEach(x=>{ cuerpo += tarjetaDescartada(x, id); });
    h += seccion("Evaluación automática de coincidencias", desc.length, cuerpo);
  }

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
    cuerpo = "";
    lista.forEach(([a,m,inv])=>{
      cuerpo += '<div class="tarjeta click'+(a.relacion==="CONTRADICE"?" alarma":"")+
        '" data-ir="relacion|'+a.id+'"><span class="chip">'+esc(a.origenLegible)+'</span>'+
        '<div style="margin-top:4px;font-size:12.5px">'+
        (inv? esc(m.etiqueta)+' '+esc(a.relacionLegible)+' <b>esta entidad</b>'
            : '<b>Esta entidad</b> '+esc(a.relacionLegible)+' '+esc(m.etiqueta))+
        '</div></div>';
    });
    h += seccion("Cómo se conecta", lista.length, cuerpo);
  }

  h += seccion("Datos", null, tabla(n.atributos));
  ficha(h);
}

function detalleCalculo(a){
  const c = a.calculo;
  if(!c) return "";
  let h = "";
  c.pasos.forEach((p,i)=>{
    h += '<div class="calculo-paso"><b>'+(i+1)+'. '+esc(p.nombre)+'</b>'+
      '<p>Peso configurado: <b>'+num(p.peso_base)+'</b>. '+esc(p.motivo)+'</p>'+
      p.ajustes.map(t=>'<p>'+esc(t)+'</p>').join("")+
      (p.cuenta.includes("×")?'<p class="valor-evidencia">Cálculo del aporte: '+esc(p.cuenta)+'</p>':'')+'</div>';
  });
  h += '<p style="margin-top:12px">'+esc(c.combinacion)+'</p>';
  if(c.pasos.length>1) h += '<p class="cita">'+esc(c.formula)+'</p>'+
    '<p>Se aplica el límite configurado de '+num(c.limite)+'. Resultado: <b>'+num(c.puntaje)+'</b>.</p>';
  return seccion("Cómo se calculó el puntaje", num(c.puntaje), h);
}

function detalleTecnico(a){
  const rutas = [...new Set([a.locator].concat((a.puente||[]).flatMap(p=>
    (p.fuentes||[]).map(f=>f.ruta).concat(p.locators||[]))).filter(Boolean))];
  return seccion("Detalle técnico de auditoría", null,
    '<p class="nota-chica">Método = procedimiento que produjo la relación. Versión = edición de ese procedimiento.</p>'+
    '<p class="nota-chica">Las rutas siguientes son referencias exactas del JSON o del registro de decisiones. '+
    'Los índices del JSON empiezan en 0; las ubicaciones legibles se numeran desde 1. No son páginas de un documento.</p>'+
    tabla([["Procedimiento y versión",a.metodo],["Referencia interna de evidencia",a.fuente],
      ["Identificador de la relación",a.id]])+
    rutas.map(r=>'<p class="cita">'+esc(r)+'</p>').join(""));
}

function fuentesVinculo(a){
  return seccion("Ver datos de origen", null, (a.puente||[]).map(p=>{
    let h = '<div class="registro"><b>'+esc(p.tipo)+'</b><div class="valor-evidencia">'+esc(p.valor)+'</div>';
    if(p.nodo) h += '<button data-ir="entidad|'+esc(p.nodo)+'">Explorar este dato</button>';
    if(p.fuentes.length) h += '<table>'+p.fuentes.map(f=>
      '<tr><td>Reporte '+esc(f.reporte)+'</td><td class="valor-evidencia">'+esc(ubicacionFuente(f.ruta))+
      '<br><button data-ir="relacion|'+esc(f.arista)+'">Revisar dato de origen</button></td></tr>').join("")+'</table>';
    if(p.locators.length) h += p.locators.map(l=>'<p class="nota-chica">'+esc(ubicacionFuente(l))+'</p>').join("");
    return h+'</div>';
  }).join(""));
}

function fichaVinculo(id){
  const a = ARISTAS.get(id); if(!a){ fichaCaso(); return; }
  const sost = (a.puente||[]).filter(x=>x.sostiene);
  const corr = (a.puente||[]).filter(x=>!x.sostiene);
  const manual = a.origen==="afirmada";
  let h = '<div class="sub">Vinculación entre reportes</div>'+
    '<h3>'+esc(NODOS.get(a.a).valor)+' y '+esc(NODOS.get(a.b).valor)+'</h3>';
  if(manual){
    h += '<p class="nota-chica">Registrada por '+esc(a.dispuestaPor||"un operador")+
      (a.validado_en?' · '+esc(a.validado_en.replace("T"," ")):'')+'</p>'+
      '<div class="hallazgo">'+esc(a.motivoOperador||"Vinculación manual.")+'</div>'+
      '<div class="fila"><button data-accion="desvincular" data-a="'+
      esc(NODOS.get(a.a).valor)+'" data-b="'+esc(NODOS.get(a.b).valor)+
      '">Revertir esta vinculación</button></div>';
  } else {
    // Cada coincidencia se lee una vez. Sus fuentes y su peso se abren a pedido.
    h += '<h2>Por qué se vinculan</h2>';
    h += sost.length ? sost.map(p=>'<div class="hallazgo valor-evidencia">'+
      esc(p.texto.charAt(0).toUpperCase()+p.texto.slice(1))+'.</div>').join("")
      : '<div class="hallazgo">'+esc(a.resumen)+'</div>';
    if(a.duplicado) h += '<p class="nota-chica">Posible reporte duplicado: coinciden cuenta y plataforma, con '+
      num(a.duplicado.horas_entre_hechos)+' horas entre hechos.</p>';
    h += bloqueRevision(a);
    h += detalleCalculo(a);
    if(corr.length) h += seccion("Otros datos que refuerzan", corr.length,
      '<p class="nota-chica">Se agregan al cálculo, pero no vinculan por sí solos.</p>'+
      corr.map(p=>'<p class="valor-evidencia">'+esc(p.texto)+'.</p>').join(""));
    h += fuentesVinculo(a);
  }
  h += detalleTecnico(a);
  ficha(h);
}

function fichaRelacion(id){
  const a = ARISTAS.get(id); if(!a){ fichaCaso(); return; }
  let h = '<h3>'+esc(etq(a.a))+' <span style="font-weight:400">'+
    esc(a.relacionLegible)+'</span> '+esc(etq(a.b))+'</h3>';
  if(a.explicacion) h += prosa(a.explicacion);
  h += bloqueRevision(a);
  if(a.relacion==="IDENTIFICADO_COMO") h += '<button data-accion="revisiones">Revisar la decisión de identidad que la originó</button>';
  h += seccion("Ver datos de origen", null, tabla([
    ["Reporte(s) de origen",(a.reportes||[]).join(", ")],
    ["Dónde se encuentra en el reporte",ubicacionFuente(a.locator)],
    ["Fecha del dato",a.observado||"no informada"],["Puerto de origen",a.puerto||""]]));
  h += detalleTecnico(a);
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
  const origenes = [
    ["var(--borde-fuerte)", "Consta en la fuente del reporte"],
    ["var(--vinculo)", "Derivada por una regla del sistema"],
    ["var(--duplicado)", "Posible duplicado del mismo hecho"],
    ["var(--inferida)", "Hipótesis todavía sin validar"],
    ["var(--afirmada)", "Establecida por un operador"],
  ];
  /* Muestra la escala con las lineas de verdad, no con una descripcion: el
     grosor se entiende viendolo. */
  const escala = [0.55, 0.75, 0.99].map(p=>
    '<div style="display:flex;align-items:center;gap:8px;margin:5px 0">'+
    '<span style="display:inline-block;width:34px;height:0;'+
    'border-top:'+grosorPorPeso(p)+'px solid var(--vinculo)"></span>'+
    '<span style="font-family:var(--mono);font-size:11px;color:var(--tenue)">'+
    'peso '+num(p)+'</span></div>').join("");
  document.getElementById("leyenda").innerHTML =
    '<div class="rotuloGrupo" style="margin-top:0">El grosor es el peso</div>'+
    escala+
    '<div style="font-size:11.5px;color:var(--suave);line-height:1.6;margin-top:6px">'+
    'Cuanto más gruesa la línea, más pesa la vinculación. La escala es la misma '+
    'en todos los casos, así que dos líneas iguales pesan igual aunque estén en '+
    'pantallas distintas.</div>'+
    '<div class="rotuloGrupo">El color, cómo se obtuvo</div>'+
    origenes.map(([c,t])=>
      '<div style="display:flex;align-items:center;font-size:11.5px;'+
      'color:var(--suave);margin:6px 0"><span class="trazo" style="border-top-style:'+
      'solid;border-top-color:'+c+'"></span>'+esc(t)+'</div>').join("")+
    '<div class="rotuloGrupo">En cuántos reportes consta cada dato</div>'+
    '<div style="font-size:11.5px;color:var(--suave);line-height:1.6">'+
    'Cada tipo de dato tiene su color. La marca «en N reportes ›» cuenta los reportes '+
    'distintos del caso donde consta ese dato. Al pasar el puntero por la caja se '+
    'resaltan esos reportes y se atenúan los demás. Al tocar la marca, el dato pasa '+
    'al centro con esos reportes debajo; «Volver» recupera la vista anterior. '+
    'Si la marca no entra, aparece como un punto con la misma acción. Las líneas '+
    'de cruce solo aparecen al activarlas en «Qué se muestra».</div>';
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
document.getElementById("verCruces").onchange = e=>{
  estado.verCruces = e.target.checked; anotarVista(); refrescar(false); };
document.getElementById("soloComp").onchange = e=>{
  estado.soloCompartidos = e.target.checked; estado.abiertos.clear(); refrescar(true); };
document.getElementById("meta").textContent =
  (D.meta.reportes||0)+" reportes ingresados · ontología "+(D.meta.ontologia||"");
/* Al recargar, el navegador devuelve los controles como estaban antes y no
   como los declara el documento. Si el estado no se lee del control, el panel
   dice una cosa y el lienzo muestra otra. */
function sincronizarControles(){
  estado.verPesos = document.getElementById("verPesos").checked;
  estado.verCruces = document.getElementById("verCruces").checked;
  estado.soloCompartidos = document.getElementById("soloComp").checked;
  estado.pesoMin = Number(document.getElementById("peso").value)/100;
  estado.texto = document.getElementById("buscar").value;
  document.getElementById("pesov").textContent = num(estado.pesoMin);
}
sincronizarControles();
pintarTipos();
pintarLeyenda();
pintarImportados();
document.getElementById("btnImportar").onclick = ()=>{
  if(!EN_APP) return sinApp("importar reportes");
  document.getElementById("archivos").click();
};
document.getElementById("btnRevisiones").onclick = ()=>ir({tipo:"revisiones"});
document.getElementById("archivos").addEventListener("change", function(e){
  importarArchivos(e.target.files);
  e.target.value = "";        // permite volver a elegir el mismo archivo
});

/* El tema se conserva entre aperturas y no toca decisiones ni historial. */
const selectorTema = document.getElementById("tema");
selectorTema.value = document.documentElement.dataset.tema || "claro";
selectorTema.onchange = ()=>{
  document.documentElement.dataset.tema = selectorTema.value;
  try { localStorage.setItem("bcij_tema",selectorTema.value); } catch(e){}
};
document.getElementById("abrirFiltros").onclick = ()=>document.getElementById("plegIzq").click();
document.getElementById("abrirHistorial").onclick = ()=>{
  if(document.getElementById("der").classList.contains("plegado")) document.getElementById("plegDer").click();
  ir({tipo:"revisiones"});
};
/* ============================================================ arranque ==== */
const sel = document.getElementById("selCaso");
CASOS.forEach(c=>{
  const o = document.createElement("option");
  o.value = c.id; o.textContent = c.etiqueta; sel.appendChild(o);
});
/* Poner el caso en pantalla, sin tocar el historial. Lo usan tanto el selector
   como la restauracion de una entrada anterior. */
function aplicarCaso(id){
  estado.caso = id;
  sel.value = id;
  pintarAlertas();
}
function cambiarCaso(id){
  anotarVista();
  aplicarCaso(id);
  estado.raiz = null; estado.centro = null;
  estado.abiertos.clear(); estado.mov.clear();
  VP.encuadrado = false;
  /* Antes esto vaciaba la pila. Saltar a un reporte de otro caso era entonces
     un viaje de ida: no habia forma de volver a lo que se estaba mirando.
     Cambiar de caso es una navegacion mas. */
  ir({tipo:"inicio"});
}
sel.onchange = e=>cambiarCaso(e.target.value);
window.addEventListener("resize", ()=>{ VP.encuadrado = false; dibujar(); });
document.getElementById("velo").addEventListener("click", e=>{
  if(e.target.id==="velo") cerrarDialogo(); });
window.addEventListener("keydown", e=>{
  if(e.key==="Escape" &&
     document.getElementById("velo").classList.contains("visible")) cerrarDialogo();
  if(e.key==="Tab" && document.getElementById("velo").classList.contains("visible")){
    const campos = [...document.getElementById("modal").querySelectorAll("input,textarea,button:not(:disabled)")];
    const primero = campos[0], ultimo = campos[campos.length-1];
    if(e.shiftKey && document.activeElement===primero){ e.preventDefault(); ultimo.focus(); }
    else if(!e.shiftKey && document.activeElement===ultimo){ e.preventDefault(); primero.focus(); }
  }
});

/* Después de registrar una decisión el servidor reconstruye y la página se
   recarga. Se vuelve al caso donde estaba el operador y se le dice qué pasó:
   sin eso, la pantalla parpadea y no queda claro si quedó registrado. */
let casoInicial = CASOS.length ? CASOS[0].id : null;
let reporteInicial = null, avisoPendiente = "", relacionInicial = null;
try {
  const r = sessionStorage.getItem("bcij_reporte");
  const c = r && CASOS.find(x=>x.reportes.includes(r));
  if(c){ casoInicial = c.id; reporteInicial = r; }
  avisoPendiente = sessionStorage.getItem("bcij_aviso") || "";
  relacionInicial = sessionStorage.getItem("bcij_relacion");
  sessionStorage.removeItem("bcij_reporte");
  sessionStorage.removeItem("bcij_aviso");
  sessionStorage.removeItem("bcij_relacion");
} catch(e){}

if(casoInicial){
  cambiarCaso(casoInicial);
  if(reporteInicial){ estado.raiz = reporteInicial; VP.encuadrado = false; ir({tipo:"inicio"}); }
} else {
  ficha('<div class="vacio">Sin casos.</div>');
}
if(relacionInicial && ARISTAS.has(relacionInicial)){
  const a = ARISTAS.get(relacionInicial);
  ir({tipo:a.entreReportes?"vinculo":"relacion", id:a.id});
}
avisar(avisoPendiente);
</script></body></html>
"""


def render(g, res, ruta, dossier=None, texto_informe=None,
           informes_por_caso=None):
    datos = _datos(g, res, dossier, texto_informe)
    if datos.get("informe") is not None:
        datos["informe"]["porCaso"] = informes_por_caso or {}
    # Un comentario humano puede contener </script>. Debe conservarse como
    # dato, nunca cerrar el bloque de JavaScript ni ejecutar HTML al recargar.
    serializado = json.dumps(datos, ensure_ascii=False, default=str)
    serializado = serializado.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = PLANTILLA.replace("__DATOS__", serializado)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(html)
    return ruta
