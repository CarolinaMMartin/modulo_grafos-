# -*- coding: utf-8 -*-
"""
Extractor de entidades y relaciones OBSERVADAS desde un reporte NCMEC.

Regla del modulo: cada arista que se crea aca apunta a un campo concreto del
JSON de origen mediante su locator. Si el campo no esta, no se inventa el
vinculo. Nada de lo que produce este extractor es una inferencia.

El texto libre sensible (transcripciones de chat, bios de perfil) NO se guarda
en el grafo. Queda en un almacen aparte, referenciado por hash, para respetar
minimizacion y exportacion controlada (CLAUDE.md 14.9 y 14.10).
"""

import json
import re

import normalizacion as nz
import nucleo
import ontologia as ont

METODO = "extractor_ncmec"
VERSION = "1.2"

RE_PERFIL_CHAT = re.compile(r"(Reported User|Other User)\s*\(Profile\s+(\w+)\)", re.I)

ROL_CHAT = {"reported user": "reportado", "other user": "contraparte"}

LISTAS_INCIDENTE = [
    ("chatIncident", "chat"),
    ("emailIncident", "email"),
    ("webpageIncident", "webpage"),
    ("peerToPeerIncident", "p2p"),
    ("gamingIncident", "gaming"),
    ("cellPhoneIncident", "telefonia"),
    ("newsgroupIncident", "newsgroup"),
    ("otherInternetIncident", "otro_internet"),
    ("internetIncident", "internet"),
    ("nonInternetIncident", "no_internet"),
]


def _g(dic, *claves):
    """Navegacion segura sobre el JSON."""
    actual = dic
    for c in claves:
        if actual is None:
            return None
        if isinstance(c, int):
            if not isinstance(actual, list) or len(actual) <= c:
                return None
            actual = actual[c]
        else:
            if not isinstance(actual, dict):
                return None
            actual = actual.get(c)
    return actual


def _lista(valor):
    return valor if isinstance(valor, list) else []


class ExtractorNCMEC(object):

    def __init__(self, grafo):
        self.g = grafo
        self.textos = {}        # hash -> {texto, locator, source_evidence_id}
        self.avisos = []
        self._esp_reporte = None

    # ---------------------------------------------------------------- API
    def ingerir(self, ruta_json, estado_institucional=None):
        with open(ruta_json, "r", encoding="utf-8") as fh:
            r = json.load(fh)

        report_id = str(r.get("reportId"))
        sid = "ncmec:%s" % report_id
        self.g.registrar_fuente(sid, ruta=ruta_json, tipo="reporte_ncmec_json",
                                extra=dict(report_id=report_id))

        self._esp_reporte = _g(r, "reportedInformation", "reportingEsp", "espName")
        n_rep = self._nodo_reporte(r, report_id, sid, estado_institucional or {})
        self._esp_emisor(r, n_rep, sid)
        self._eventos(r, n_rep, sid, report_id)
        self._personas(r, n_rep, sid, report_id)
        self._geolookups(r, sid)
        self._archivos(r, n_rep, sid)
        self._destinatario_le(r, n_rep, sid)
        return n_rep

    # ------------------------------------------------------------ reporte
    def _nodo_reporte(self, r, report_id, sid, estado):
        ri = r.get("reportedInformation") or {}
        resumen = ri.get("incidentSummary") or {}
        ncmec = r.get("additionalNcmecInformation") or {}
        ts_inc, _ = nz.normalizar_ts(resumen.get("incidentDateTime"))
        ts_rec, _ = nz.normalizar_ts(r.get("dateReceived"))

        return self.g.nodo(
            "REPORTE", report_id,
            etiqueta="Reporte %s" % report_id,
            clasificacion=ncmec.get("ncmecClassification") or resumen.get("incidentType"),
            prioridad=_g(ncmec, "priority", "priorityId"),
            prioridad_desc=_g(ncmec, "priority", "value"),
            plataforma=resumen.get("platform"),
            pais=ncmec.get("internationalCountry"),
            fecha_incidente=ts_inc.isoformat() if ts_inc else None,
            fecha_recepcion=ts_rec.isoformat() if ts_rec else None,
            enviado_a_le=ncmec.get("sentToLawEnforcement"),
            # Estado institucional: vive en el sistema transaccional, no en el
            # grafo. Se une aca solo como proyeccion de lectura.
            estado_sipar=estado.get("estado"),
            motivo_archivo=estado.get("motivo_archivo"),
            fecha_estado=estado.get("fecha"),
            operador=estado.get("operador"),
        )

    def _esp_emisor(self, r, n_rep, sid):
        esp = _g(r, "reportedInformation", "reportingEsp", "espName")
        if not esp:
            return
        n_esp = self.g.nodo("ORGANIZACION", esp, etiqueta=esp, subtipo="ESP")
        self.g.arista(
            n_rep, n_esp, "EMITIDO_POR", sid,
            "reportedInformation.reportingEsp.espName",
            u"El reporte fue generado y remitido por el proveedor %s." % esp,
            METODO, VERSION)

    # ------------------------------------------------------------- eventos
    def _eventos(self, r, n_rep, sid, report_id):
        detalles = _g(r, "reportedInformation", "incidentDetails") or {}
        for clave, subtipo in LISTAS_INCIDENTE:
            for i, inc in enumerate(_lista(detalles.get(clave))):
                base = "reportedInformation.incidentDetails.%s[%d]" % (clave, i)
                ev_id = inc.get("id") or "%s-%s-%d" % (report_id, subtipo, i)
                n_ev = self.g.nodo(
                    "EVENTO", ev_id,
                    etiqueta="%s %s" % (subtipo, ev_id),
                    subtipo=subtipo,
                    servicio=inc.get("chatServiceOrClient") or inc.get("chatRoomName"),
                )
                self.g.arista(
                    n_rep, n_ev, "CONTIENE_EVENTO", sid, base,
                    u"El reporte comprende un hecho de tipo %s, tal como lo clasifica la "
                    u"propia plataforma." % subtipo,
                    METODO, VERSION)
                self._perfiles_en_notas(inc, base, n_ev, sid, r)

    def _perfiles_en_notas(self, inc, base, n_ev, sid, r):
        """Extrae identificadores de perfil de las transcripciones.

        Solo se toman los identificadores estructurados que la plataforma
        agrega a la transcripcion. El contenido del chat no se copia al grafo.
        """
        esp = _g(r, "reportedInformation", "reportingEsp", "espName") or "desconocido"
        for j, nota in enumerate(_lista(inc.get("notes"))):
            texto = (nota or {}).get("value")
            if not texto:
                continue
            loc_nota = "%s.notes[%d].value" % (base, j)
            h = nucleo.hash_texto(texto)
            self.textos[h] = dict(locator=loc_nota, source_evidence_id=sid,
                                  tipo="transcripcion_chat", caracteres=len(texto),
                                  texto=texto)
            self.g.G.nodes[n_ev].setdefault("transcripciones", []).append(h)

            vistos = {}
            for rol_txt, perfil in RE_PERFIL_CHAT.findall(texto):
                vistos.setdefault(perfil, ROL_CHAT.get(rol_txt.lower(), "participante"))
            for perfil, rol in vistos.items():
                clave = nz.clave_cuenta(esp, perfil)
                n_cta = self.g.nodo("CUENTA", clave, etiqueta="%s@%s" % (perfil, esp),
                                    esp=esp, esp_user_id=perfil)
                self.g.arista(
                    n_cta, n_ev, "PARTICIPA_EN", sid,
                    "%s#Profile=%s" % (loc_nota, perfil),
                    u"La transcripción aportada por la plataforma identifica al perfil "
                    u"%s como %s del intercambio. Del texto solo se toma este "
                    u"identificador: el contenido no se incorpora al grafo."
                    % (perfil, rol),
                    METODO, VERSION, atributos=dict(rol=rol))

    # ------------------------------------------------------------ personas
    def _personas(self, r, n_rep, sid, report_id):
        ri = r.get("reportedInformation") or {}
        grupos = [
            ("reportedPeople", "reportedPersons", "reportado"),
            ("childVictims", "childVictims", "victima"),
            ("intendedRecipients", "intendedRecipients", "destinatario"),
        ]
        for cont, lista_clave, rol in grupos:
            contenedor = ri.get(cont) or {}
            personas = _lista(contenedor.get(lista_clave)) if isinstance(contenedor, dict) else []
            for i, p in enumerate(personas):
                base = "reportedInformation.%s.%s[%d]" % (cont, lista_clave, i)
                self._persona(p, base, rol, n_rep, sid, report_id, i)

    def _persona(self, p, base, rol, n_rep, sid, report_id, idx):
        # El nodo de mencion es local al reporte: no se fusionan personas
        # entre reportes por cuenta propia (CLAUDE.md 11.2).
        mencion_id = "%s/%s" % (report_id, p.get("id") or "%s%d" % (rol, idx))
        n_per = self.g.nodo(
            "PERSONA_MENCION", mencion_id,
            etiqueta="%s (rep. %s)" % (rol, report_id),
            reporte=report_id,
            genero=p.get("gender"),
            edad_aprox=p.get("approximateAge"),
            cuenta_suspendida=bool(p.get("accountPermanentlyDisabled")
                                   or p.get("accountTemporarilyDisabled")),
        )
        self.g.arista(
            n_per, n_rep, "REPORTADO_EN", sid, base,
            u"El reporte menciona a esta persona en calidad de %s. El rol es el "
            u"que corresponde a esta actuación y no una característica "
            u"permanente de la persona." % rol,
            METODO, VERSION, atributos=dict(rol=rol))

        esp = p.get("espService") or getattr(self, "_esp_reporte", None) or "desconocido"
        n_cta = None
        esp_user = p.get("espUserId")
        if esp_user:
            clave = nz.clave_cuenta(esp, esp_user)
            n_cta = self.g.nodo("CUENTA", clave, etiqueta="%s@%s" % (esp_user, esp),
                                esp=esp, esp_user_id=str(esp_user))
            self.g.arista(
                n_per, n_cta, "USA_CUENTA", sid, base + ".espUserId",
                u"La persona figura en el reporte operando con la cuenta %s de %s."
                % (esp_user, esp),
                METODO, VERSION)

        ancla = n_cta or n_per
        self._alias(p, base, ancla, sid)
        self._contactos(p, base, ancla, sid)
        self._capturas(p, base, ancla, sid)
        self._ubicaciones_esp(p, base, ancla, sid)
        self._bio(p, base, n_per, sid)

    def _alias(self, p, base, ancla, sid):
        candidatos = []
        for nom in _lista(_g(p, "displayNames", "displayNames")):
            candidatos.append((nom.get("value"), base + ".displayNames.displayNames[].value",
                               "nombre visible"))
        for nom in _lista(_g(p, "screenNames", "screenNames")):
            candidatos.append((nom.get("value"), base + ".screenNames.screenNames[].value",
                               "screen name"))
        if p.get("screenName"):
            candidatos.append((p["screenName"], base + ".screenName", "screen name"))

        for valor, loc, tipo in candidatos:
            alias, notas = nz.normalizar_alias(valor)
            if not alias:
                continue
            n_al = self.g.nodo("ALIAS", alias, etiqueta=alias, forma_original=valor)
            self.g.arista(
                ancla, n_al, "ALIAS_DE", sid, loc,
                u"%s declarado en el reporte: «%s».%s"
                % (tipo.capitalize(), valor,
                   (u" " + u"; ".join(notas) + u".") if notas else u""),
                METODO, VERSION, atributos=dict(normalizacion=nz.NORMALIZACION_VERSION))

    def _contactos(self, p, base, ancla, sid):
        for i, em in enumerate(_lista(_g(p, "emails", "emails"))):
            email, notas = nz.normalizar_email(em.get("value"))
            if not email:
                continue
            n_em = self.g.nodo("EMAIL", email, etiqueta=email)
            self.g.arista(
                ancla, n_em, "ASOCIADO_A_EMAIL", sid,
                "%s.emails.emails[%d].value" % (base, i),
                u"Dirección de correo informada en el reporte.%s"
                % ((u" " + u"; ".join(notas) + u".") if notas else u""),
                METODO, VERSION)
        for i, tel in enumerate(_lista(_g(p, "phones", "phones"))):
            e164, notas = nz.normalizar_telefono(tel.get("value"))
            if not e164:
                continue
            n_tel = self.g.nodo("TELEFONO", e164, etiqueta=e164,
                                area=nz.prefijo_ar(e164))
            self.g.arista(
                ancla, n_tel, "ASOCIADO_A_TELEFONO", sid,
                "%s.phones.phones[%d].value" % (base, i),
                u"Número telefónico informado en el reporte.%s"
                % ((u" " + u"; ".join(notas) + u".") if notas else u""),
                METODO, VERSION)

    def _capturas(self, p, base, ancla, sid):
        capturas = _lista(_g(p, "sourceInformation", "sourceCaptures"))
        if p.get("ipAddress"):
            capturas = capturas + [dict(captureType="IP Address", value=p["ipAddress"],
                                        eventName=None, dateTime=None, port=None)]
        for i, cap in enumerate(capturas):
            loc = "%s.sourceInformation.sourceCaptures[%d]" % (base, i)
            tipo = (cap.get("captureType") or "").lower()
            valor = cap.get("value")
            if not valor:
                continue
            ts, notas_ts = nz.normalizar_ts(cap.get("dateTime"))
            evento = cap.get("eventName")

            if "ip" in tipo:
                ip, notas, rasgos = nz.normalizar_ip(valor)
                if not ip:
                    self.avisos.append(dict(locator=loc, motivo=notas))
                    continue
                n_ip = self.g.nodo("IP", ip, etiqueta=ip, **rasgos)
                puerto = cap.get("port")
                proxy = cap.get("possibleProxy")
                explic = (u"La plataforma capturó esta dirección IP durante el "
                          u"evento %s%s. Una dirección IP solo permite atribuir una "
                          u"conexión cuando se la considera junto con su fecha y "
                          u"hora."
                          % (evento or u"no informado",
                             u", el %s" % ts.isoformat() if ts else u""))
                if rasgos.get("cgnat"):
                    if cap.get("port"):
                        explic += (u"\n\nLa dirección pertenece al rango CGNAT, de "
                                   u"modo que por sí sola no individualiza a un "
                                   u"abonado. La captura sí informa el puerto de "
                                   u"origen (%s), lo que permite al prestador "
                                   u"identificarlo." % cap.get("port"))
                    else:
                        explic += (u"\n\nLa dirección pertenece al rango CGNAT y la "
                                   u"captura no informa el puerto de origen. Sin ese "
                                   u"dato el prestador no está en condiciones de "
                                   u"identificar al abonado.")
                if not ts:
                    explic += (u"\n\nATENCIÓN: la captura no informa fecha ni hora, "
                               u"por lo que su valor identificatorio es muy "
                               u"limitado.")
                if notas_ts:
                    explic += u"\n\n" + u"; ".join(notas_ts) + u"."
                self.g.arista(
                    ancla, n_ip, "OBSERVADO_DESDE_IP", sid, loc, explic,
                    METODO, VERSION,
                    observed_at=ts.isoformat() if ts else None,
                    atributos=dict(evento=evento, puerto=puerto,
                                   posible_proxy=proxy,
                                   sin_timestamp=ts is None))
            elif "device" in tipo:
                n_dev = self.g.nodo("DISPOSITIVO", valor, etiqueta=valor,
                                    subtipo=cap.get("valueType"))
                self.g.arista(
                    ancla, n_dev, "USA_DISPOSITIVO", sid, loc,
                    u"La plataforma capturó este identificador de dispositivo%s durante "
                    u"el evento %s."
                    % (u" (%s)" % cap.get("valueType") if cap.get("valueType") else u"",
                       evento or u"no informado"),
                    METODO, VERSION,
                    observed_at=ts.isoformat() if ts else None,
                    atributos=dict(evento=evento))
            elif "phone" in tipo:
                e164, _ = nz.normalizar_telefono(valor)
                if e164:
                    n_tel = self.g.nodo("TELEFONO", e164, etiqueta=e164,
                                        area=nz.prefijo_ar(e164))
                    self.g.arista(
                        ancla, n_tel, "ASOCIADO_A_TELEFONO", sid, loc,
                        u"Número telefónico capturado directamente por la plataforma.",
                        METODO, VERSION,
                        observed_at=ts.isoformat() if ts else None)
            elif "email" in tipo:
                email, _ = nz.normalizar_email(valor)
                if email:
                    n_em = self.g.nodo("EMAIL", email, etiqueta=email)
                    self.g.arista(
                        ancla, n_em, "ASOCIADO_A_EMAIL", sid, loc,
                        u"Dirección de correo capturada directamente por la plataforma.",
                        METODO, VERSION,
                        observed_at=ts.isoformat() if ts else None)

    def _ubicaciones_esp(self, p, base, ancla, sid):
        locs = _lista(_g(p, "espEstimatedLocations", "espEstimatedLocations"))
        for i, u in enumerate(locs):
            clave = _clave_ubicacion(u.get("city"), u.get("region"), u.get("countryCode"))
            if not clave:
                continue
            n_ub = self.g.nodo("UBICACION", clave, etiqueta=clave,
                               ciudad=u.get("city"), region=u.get("region"),
                               pais=u.get("countryCode"))
            ts, _ = nz.normalizar_ts(u.get("timestamp"))
            self.g.arista(
                ancla, n_ub, "UBICADO_EN", sid,
                "%s.espEstimatedLocations.espEstimatedLocations[%d]" % (base, i),
                u"Ubicación estimada que informa la propia plataforma%s. Es "
                u"aproximada: indica una zona, no un domicilio, y no reemplaza la "
                u"respuesta del prestador."
                % (u", declarada como verificada" if u.get("verified")
                   else u", sin verificar"),
                METODO, VERSION,
                observed_at=ts.isoformat() if ts else None,
                atributos=dict(verificada=bool(u.get("verified")), aproximada=True))

    def _bio(self, p, base, n_per, sid):
        bio = p.get("profileBio")
        if not bio:
            return
        h = nucleo.hash_texto(bio)
        self.textos[h] = dict(locator=base + ".profileBio", source_evidence_id=sid,
                              tipo="bio_perfil", caracteres=len(bio), texto=bio)
        self.g.G.nodes[n_per]["bio_hash"] = h

    # --------------------------------------------------------- automatico
    def _geolookups(self, r, sid):
        base = ("automatedInformation.autoGeneratedNotes.geoLookups")
        auto = _g(r, "automatedInformation", "autoGeneratedNotes", "geoLookups") or {}
        for clave in ("reportedPersonGeoLookups", "childVictimGeoLookups",
                      "imageGeoLookups", "internetGeoLookups"):
            for i, gl in enumerate(_lista(auto.get(clave))):
                ip, _, rasgos = nz.normalizar_ip(gl.get("ipAddress"))
                if not ip:
                    continue
                loc = "%s.%s[%d]" % (base, clave, i)
                n_ip = self.g.nodo("IP", ip, etiqueta=ip, **rasgos)

                isp = gl.get("esp") or gl.get("organization")
                if isp:
                    n_isp = self.g.nodo("ORGANIZACION", isp, etiqueta=isp,
                                        subtipo="ISP")
                    self.g.arista(
                        n_ip, n_isp, "ASIGNADA_A", sid, loc + ".esp",
                        u"El sistema automático de NCMEC atribuye esta dirección "
                        u"IP al prestador %s. La atribución debe confirmarse con "
                        u"LACNIC, ENACOM o el propio prestador antes de librar un "
                        u"oficio." % isp,
                        "ncmec_geolookup", "reporte", confianza=0.75)

                clave_ub = _clave_ubicacion(gl.get("city"), gl.get("region"),
                                            gl.get("country"))
                if clave_ub:
                    n_ub = self.g.nodo(
                        "UBICACION", clave_ub, etiqueta=clave_ub,
                        ciudad=gl.get("city"), region=gl.get("region"),
                        pais=gl.get("country"), cp=gl.get("postalCode"),
                        lat=gl.get("latitude"), lon=gl.get("longitude"))
                    conf = 0.6 if not rasgos.get("atribuible_sin_dato_extra") else 0.8
                    self.g.arista(
                        n_ip, n_ub, "GEOLOCALIZA_EN", sid, loc, (
                            u"Geolocalización aproximada producida por el sistema "
                            u"automático de NCMEC a partir de consultas públicas. "
                            u"Estima una zona, no un domicilio, y en modo alguno "
                            u"reemplaza la respuesta del prestador."),
                        "ncmec_geolookup", "reporte", confianza=conf,
                        atributos=dict(aproximada=True,
                                       tipos=",".join(gl.get("types") or [])))

    def _archivos(self, r, n_rep, sid):
        archivos = _g(r, "reportedInformation", "uploadedFiles") or []
        for i, f in enumerate(_lista(archivos)):
            h = f.get("md5") or f.get("sha1") or f.get("fileHash") or f.get("hash")
            if not h:
                self.avisos.append(dict(
                    locator="reportedInformation.uploadedFiles[%d]" % i,
                    motivo=["archivo sin hash: no se puede vincular por contenido"]))
                continue
            n_ev = self.g.nodo("EVIDENCIA", h, etiqueta=(f.get("fileName") or h)[:40],
                               nombre=f.get("fileName"), tipo_mime=f.get("fileType"),
                               clasificacion=f.get("industryClassification"))
            self.g.arista(
                n_rep, n_ev, "ADJUNTA", sid,
                "reportedInformation.uploadedFiles[%d]" % i,
                u"Archivo incorporado al reporte e identificado por su hash, lo que "
                u"permite reconocer el mismo contenido en otras actuaciones.",
                METODO, VERSION)

    def _destinatario_le(self, r, n_rep, sid):
        contactos = _g(r, "lawEnforcementContactInformation",
                       "lawEnforcementContacts") or []
        for i, c in enumerate(_lista(contactos)):
            agencia = c.get("agency")
            if not agencia:
                continue
            n_org = self.g.nodo("ORGANIZACION", agencia, etiqueta=agencia,
                                subtipo="fuerza_o_ministerio_publico")
            self.g.arista(
                n_rep, n_org, "PUESTO_A_DISPOSICION_DE", sid,
                "lawEnforcementContactInformation.lawEnforcementContacts[%d].agency" % i,
                u"NCMEC puso el reporte a disposición de %s." % agencia,
                METODO, VERSION,
                observed_at=c.get("dateTimeMadeAvailable"),
                atributos=dict(rol="destinatario"))


def _clave_ubicacion(ciudad, region, pais):
    partes = [p for p in (ciudad, region, pais) if p]
    if not partes:
        return None
    return ", ".join(str(p).strip() for p in partes)
