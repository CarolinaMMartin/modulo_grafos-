# -*- coding: utf-8 -*-
"""
Generador de reportes sinteticos con la estructura del JSON de NCMEC.

Sirven para validar la logica del grafo sin usar datos reales (contexto.md 14.13).
El contenido de los chats es un marcador de posicion: solo se conservan los
identificadores estructurados de perfil, que son lo unico que el extractor lee.

Cada reporte esta construido para ejercitar un caso de la logica:

  900000101  misma cuenta y mismo dispositivo, fuera de la ventana de IP
  900000102  archivado por NAT no atribuible, solo telefono
  900000103  aporta el telefono que le faltaba a 102, con ubicacion CABA
  900000104  solo alias y ciudad coincidentes: NO debe generar vinculo
  900000105  mismo dispositivo, cuenta distinta, otra zona
  900000106  duplicado casi exacto de 255553607 + viaje imposible
  900000107  archivado sin datos de ubicacion, solo dispositivo
  900000108  aporta la ubicacion que le faltaba a 107, mismo dispositivo
  900000109  geolocalizacion fuera de Argentina
"""

import json
import os

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "reportes_sinteticos")

AGENCIA = "Argentina Judicial Investigation Center (CIJ)"
TEXTO_PLACEHOLDER = "[contenido sintetico omitido]"


def chat(id_ev, servicio, fecha, perfiles):
    lineas = []
    for i, (rol, perfil) in enumerate(perfiles):
        lineas.append("[%s UTC] %s (Profile %s): %s"
                      % (fecha, rol, perfil, TEXTO_PLACEHOLDER))
    return dict(id=id_ev, chatServiceOrClient=servicio, screenName=None,
                chatRoomName=None, webcamInvolved=None, urls=None,
                notes=[dict(value=" \n".join(lineas))],
                additonalInformations=[dict(value="Reporte sintetico de prueba")],
                thirdPartyContent=None, links=None,
                associationsEntityType="Incident Location")


def captura_ip(valor, evento, fecha, puerto=None, proxy=None):
    return dict(captureType="IP Address", valueType=None, value=valor,
                eventName=evento, dateTime=fecha, possibleProxy=proxy, port=puerto)


def captura_device(valor, subtipo="IDFA", evento="LOGIN", fecha=None):
    return dict(captureType="Device ID", valueType=subtipo, value=valor,
                eventName=evento, dateTime=fecha, possibleProxy=None, port=None)


def geolookup(ip, ciudad, region, isp, lat=None, lon=None, pais="AR", cp=None):
    return dict(ipAddress=ip, country=pais, region=region, city=ciudad,
                postalCode=cp, latitude=lat, longitude=lon,
                metropolitanCode=None, areaCode=None, esp=isp, organization=isp,
                types=["residential"])


def persona(pid, esp_user_id=None, alias=None, telefonos=None, emails=None,
            capturas=None, ubicaciones=None, bio=None):
    return dict(
        id=pid, firstName=None, lastName=None, middleName=None,
        espUserId=esp_user_id, espService=None, screenName=None, screenNames=None,
        displayNames=(dict(displayNames=[dict(value=a) for a in (alias or [])])
                      if alias else None),
        emails=(dict(emails=[dict(value=e) for e in emails]) if emails else None),
        phones=(dict(phones=[dict(value=t) for t in telefonos]) if telefonos else None),
        profileBio=bio,
        sourceInformation=dict(sourceCaptures=capturas or []),
        espEstimatedLocations=(dict(espEstimatedLocations=ubicaciones)
                               if ubicaciones else None),
        ipAddress=None, accountTemporarilyDisabled=None,
        accountPermanentlyDisabled=None, additionalInformations=None,
        priorCybertipReports=None, associationsEntityType="Reported Person")


def ubicacion_esp(ciudad, region, fecha, pais="AR", verificada=False):
    return dict(city=ciudad, region=region, countryCode=pais,
                verified=verificada, timestamp=fecha)


def reporte(rid, esp, plataforma, fecha_hecho, fecha_recepcion, clasificacion,
            prioridad, personas, incidentes=None, geolookups=None, archivos=None,
            pais="Argentina"):
    return {
        "reportId": rid,
        "informational": False,
        "dateReceived": fecha_recepcion,
        "dateMadeAvailable": fecha_recepcion,
        "reportedInformation": {
            "reportingEsp": {"espName": esp, "addresses": None, "phones": None,
                             "emails": None, "id": None,
                             "associationsEntityType": "Reporter"},
            "incidentSummary": {
                "incidentType": clasificacion, "platform": plataforma,
                "incidentDateTime": fecha_hecho, "incidentDateRange": None,
                "espEscalation": "Reporte sintetico generado para pruebas",
                "additionalIncidentTypes": None},
            "incidentDetails": {
                "chatIncident": incidentes or [], "emailIncident": [],
                "webpageIncident": [], "peerToPeerIncident": [],
                "gamingIncident": [], "cellPhoneIncident": [],
                "newsgroupIncident": [], "otherInternetIncident": [],
                "internetIncident": [], "nonInternetIncident": []},
            "childVictims": None,
            "reportedPeople": {"reportedPersons": personas},
            "intendedRecipients": None,
            "uploadedFiles": archivos or [],
            "additionalInformations": [{"value": "DATO SINTETICO - no corresponde "
                                                 "a un hecho real"}],
        },
        "automatedInformation": {
            "autoGeneratedNotes": {
                "geoLookups": {"reportedPersonGeoLookups": geolookups or [],
                               "childVictimGeoLookups": [], "imageGeoLookups": [],
                               "internetGeoLookups": []},
                "phoneGeoLookups": None, "autoCloses": [], "autoRefers": []},
        },
        "additionalNcmecInformation": {
            "priority": {"priorityId": prioridad, "value": "Sintetico"},
            "ncmecClassification": clasificacion,
            "internationalCountry": pais,
            "sentToLawEnforcement": True,
            "dateTimeProcessed": fecha_recepcion,
        },
        "lawEnforcementContactInformation": {
            "lawEnforcementContacts": [
                {"agency": AGENCIA, "dateTimeMadeAvailable": fecha_recepcion,
                 "referralType": "NCMEC_ANALYST"}]},
    }


IP_TELECENTRO = "181.46.66.242"
DEVICE_A = "b534375433e0e502"
DEVICE_B = "d99aa17c40b1ee83"
CUENTA_A = "888658825"
TEL_COMPARTIDO_CRUDO = "+54 9 11 6888-9999"
TEL_COMPARTIDO_ALT = "011 15 6888 9999"


def construir():
    reportes = []

    # --- 101: misma cuenta y dispositivo, IP fuera de ventana --------------
    reportes.append(reporte(
        900000101, "Grindr", "Grindr App", "2026-06-02T09:05:00Z",
        "2026-06-03T10:00:00Z", "Child Sexual Molestation", "E",
        [persona("p101", CUENTA_A, alias=["lechero"],
                 capturas=[captura_ip(IP_TELECENTRO, "LOGIN", "2026-06-02T09:20:00Z"),
                           captura_device(DEVICE_A, fecha="2026-06-02T09:20:00Z")],
                 ubicaciones=[ubicacion_esp("Monte Grande", "B", "2026-06-02T09:20:00Z")],
                 bio="Bio sintetica de prueba")],
        incidentes=[chat(214000101, "Grindr", "2026-06-02 09:05:00",
                         [("Reported User", CUENTA_A), ("Other User", "555000101")])],
        geolookups=[geolookup(IP_TELECENTRO, "Monte Grande", "B", "TeleCentro",
                              "-34.815", "-58.4693", cp="1842")]))

    # --- 102: archivado por NAT, solo telefono -----------------------------
    reportes.append(reporte(
        900000102, "WhatsApp", "WhatsApp", "2026-03-11T14:00:00Z",
        "2026-03-12T08:00:00Z", "Child Pornography (Unconfirmed)", "E",
        [persona("p102", telefonos=[TEL_COMPARTIDO_ALT],
                 capturas=[captura_ip("100.66.12.45", "LOGIN", "2026-03-11T14:05:00Z")])],
        geolookups=[]))

    # --- 103: aporta el telefono que le faltaba a 102, jurisdiccion CABA ---
    reportes.append(reporte(
        900000103, "Instagram", "Instagram", "2026-08-10T18:30:00Z",
        "2026-08-11T09:00:00Z", "Child Sexual Molestation", "3",
        [persona("p103", "771122334", alias=["nocturno_ba"],
                 telefonos=[TEL_COMPARTIDO_CRUDO],
                 capturas=[captura_ip("190.55.120.14", "LOGIN", "2026-08-10T18:35:00Z",
                                      puerto=44120)],
                 ubicaciones=[ubicacion_esp("Buenos Aires", "C", "2026-08-10T18:35:00Z")])],
        geolookups=[geolookup("190.55.120.14", "Buenos Aires", "C",
                              "Telecom Argentina", "-34.6037", "-58.3816", cp="1000")]))

    # --- 104: solo alias y ciudad: no debe vincular ------------------------
    reportes.append(reporte(
        900000104, "Facebook", "Facebook", "2026-05-20T11:00:00Z",
        "2026-05-21T07:00:00Z", "Child Sexual Molestation", "E",
        [persona("p104", alias=["lechero"],
                 ubicaciones=[ubicacion_esp("Monte Grande", "B", "2026-05-20T11:05:00Z")])],
        geolookups=[]))

    # --- 105: mismo dispositivo, cuenta distinta, otra jurisdiccion --------
    reportes.append(reporte(
        900000105, "Grindr", "Grindr App", "2026-08-19T20:10:00Z",
        "2026-08-20T06:00:00Z", "Child Sexual Molestation", "E",
        [persona("p105", "991234567", alias=["ba_nocturno"],
                 capturas=[captura_ip("200.123.45.6", "LOGIN", "2026-08-19T20:15:00Z"),
                           captura_device(DEVICE_A, fecha="2026-08-19T20:15:00Z")],
                 ubicaciones=[ubicacion_esp("Buenos Aires", "C", "2026-08-19T20:15:00Z")])],
        incidentes=[chat(214000105, "Grindr", "2026-08-19 20:10:00",
                         [("Reported User", "991234567"), ("Other User", "555000105")])],
        geolookups=[geolookup("200.123.45.6", "Buenos Aires", "C",
                              "Telecentro", "-34.6037", "-58.3816", cp="1414")]))

    # --- 106: duplicado casi exacto + viaje imposible ---------------------
    reportes.append(reporte(
        900000106, "Grindr", "Grindr App", "2026-08-18T14:10:00Z",
        "2026-08-19T22:00:00Z", "Child Sexual Molestation", "E",
        [persona("p106", CUENTA_A, alias=["lechero"],
                 capturas=[captura_ip(IP_TELECENTRO, "LOGIN", "2026-08-17T08:52:15Z"),
                           captura_ip("200.63.140.10", "LOGIN", "2026-08-17T09:22:15Z"),
                           captura_device(DEVICE_A, fecha="2026-08-17T08:52:15Z")],
                 ubicaciones=[ubicacion_esp("Monte Grande", "B", "2026-08-17T08:52:15Z")])],
        incidentes=[chat(214000106, "Grindr", "2026-08-18 14:10:00",
                         [("Reported User", CUENTA_A), ("Other User", "555000106")])],
        geolookups=[geolookup(IP_TELECENTRO, "Monte Grande", "B", "TeleCentro",
                              "-34.815", "-58.4693", cp="1842"),
                    geolookup("200.63.140.10", "Salta", "A", "Claro",
                              "-24.7859", "-65.4117", cp="4400")]))

    # --- 107: archivado por jurisdiccion indeterminada --------------------
    reportes.append(reporte(
        900000107, "Skype", "Skype", "2026-01-15T22:00:00Z",
        "2026-01-16T09:00:00Z", "Online Enticement", "E",
        [persona("p107", "sk_88231", alias=["elviajero"],
                 capturas=[captura_device(DEVICE_B, subtipo="GAID",
                                          fecha="2026-01-15T22:05:00Z")])],
        geolookups=[]))

    # --- 108: aporta jurisdiccion a 107 por el mismo dispositivo ----------
    reportes.append(reporte(
        900000108, "Instagram", "Instagram", "2026-08-14T16:00:00Z",
        "2026-08-15T09:00:00Z", "Online Enticement", "3",
        [persona("p108", "552211889", alias=["elviajero"],
                 capturas=[captura_ip("181.14.200.31", "LOGIN", "2026-08-14T16:05:00Z",
                                      puerto=51221),
                           captura_device(DEVICE_B, subtipo="GAID",
                                          fecha="2026-08-14T16:05:00Z")],
                 ubicaciones=[ubicacion_esp("Cordoba", "X", "2026-08-14T16:05:00Z")])],
        geolookups=[geolookup("181.14.200.31", "Cordoba", "X", "Telecom Argentina",
                              "-31.4201", "-64.1888", cp="5000")]))

    # --- 109: fuera de Argentina ------------------------------------------
    reportes.append(reporte(
        900000109, "Facebook", "Facebook", "2026-07-01T03:00:00Z",
        "2026-07-02T09:00:00Z", "Child Sexual Molestation", "E",
        [persona("p109", "fb_9911", alias=["nn_usa"],
                 capturas=[captura_ip("73.15.200.11", "LOGIN", "2026-07-01T03:05:00Z")],
                 ubicaciones=[ubicacion_esp("Miami", "FL", "2026-07-01T03:05:00Z",
                                            pais="US")])],
        geolookups=[geolookup("73.15.200.11", "Miami", "FL", "Comcast",
                              "25.7617", "-80.1918", pais="US", cp="33101")]))

    return reportes


# ---------------------------------------------------------------------------
# Estado institucional: vive en el sistema transaccional (PostgreSQL/SIPAR),
# no en el grafo. Aca se simula como sidecar para poder unirlo.
# ---------------------------------------------------------------------------
ESTADO_INSTITUCIONAL = {
    "255553607": dict(estado="en_analisis", motivo_archivo=None,
                      fecha="2026-08-20", operador="op_04"),
    "900000101": dict(estado="archivado", motivo_archivo="sin_datos_de_usuario",
                      fecha="2026-06-05", operador="op_02"),
    "900000102": dict(estado="archivado", motivo_archivo="no_atribuible_nat",
                      fecha="2026-03-14", operador="op_07"),
    "900000103": dict(estado="en_analisis", motivo_archivo=None,
                      fecha="2026-08-12", operador="op_01"),
    "900000104": dict(estado="archivado", motivo_archivo="material_sin_relevancia",
                      fecha="2026-05-22", operador="op_03"),
    "900000105": dict(estado="en_analisis", motivo_archivo=None,
                      fecha="2026-08-20", operador="op_04"),
    "900000106": dict(estado="en_analisis", motivo_archivo=None,
                      fecha="2026-08-20", operador="op_04"),
    "900000107": dict(estado="archivado", motivo_archivo="sin_ubicacion",
                      fecha="2026-01-20", operador="op_05"),
    "900000108": dict(estado="en_investigacion", motivo_archivo=None,
                      fecha="2026-08-16", operador="op_05"),
    "900000109": dict(estado="archivado", motivo_archivo="sin_ubicacion",
                      fecha="2026-07-03", operador="op_06"),
}


def main():
    if not os.path.isdir(DIR):
        os.makedirs(DIR)
    escritos = []
    for r in construir():
        ruta = os.path.join(DIR, "%s.json" % r["reportId"])
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
        escritos.append(ruta)
    ruta_estado = os.path.join(DIR, "estado_institucional.json")
    with open(ruta_estado, "w", encoding="utf-8") as fh:
        json.dump(ESTADO_INSTITUCIONAL, fh, ensure_ascii=False, indent=1)
    print("reportes sinteticos: %d" % len(escritos))
    print("estado institucional: %s" % ruta_estado)


if __name__ == "__main__":
    main()
