# -*- coding: utf-8 -*-
"""
Redacta el texto libre y los datos de contacto de un reporte real de NCMEC.

Que hace y que NO hace:

- REEMPLAZA la transcripcion del chat, la bio del perfil y los datos de contacto
  de las personas que intervinieron en el tramite (nombres, correos, telefonos
  institucionales). Es el material que no deberia salir de la maquina.
- CONSERVA los identificadores tecnicos: IP, dispositivo, cuenta, alias,
  geolocalizacion, fechas. Son los que hacen funcionar la logica de vinculacion,
  y sin ellos el dataset deja de servir para probar nada.

De la transcripcion se preservan las marcas "(Profile NNN)", que es lo unico que
el extractor lee de ella.

    python redactar_reporte.py reportes_sinteticos/255553607.json

Guarda el original intacto en _privado/ antes de tocar nada.
"""

import json
import os
import re
import shutil
import sys

# La cabecera llega hasta el "(Profile NNN)" inclusive. No alcanza con cortar en
# el primer ":": la marca de tiempo tiene dos puntos y se perderia el perfil.
CABECERA = re.compile(r"^(.*?\(Profile\s+\w+\))\s*:", re.I)
PLACEHOLDER = "[texto original removido para publicacion]"


def redactar_transcripcion(texto):
    """Deja la estructura de la conversacion y borra el contenido."""
    lineas = []
    for linea in texto.split("\n"):
        m = CABECERA.match(linea.strip())
        if m:
            lineas.append("%s: %s" % (m.group(1).strip(), PLACEHOLDER))
        elif linea.strip():
            lineas.append(PLACEHOLDER)
    return " \n".join(lineas)


def redactar(r):
    cambios = []

    ri = r.get("reportedInformation") or {}

    # 1. transcripciones de chat
    detalles = ri.get("incidentDetails") or {}
    for clave, lista in detalles.items():
        if not isinstance(lista, list):
            continue
        for inc in lista:
            for nota in (inc.get("notes") or []):
                if nota.get("value"):
                    nota["value"] = redactar_transcripcion(nota["value"])
                    cambios.append("transcripcion en %s" % clave)

    # 2. bios de perfil y descripciones libres de las personas
    for cont, clave in (("reportedPeople", "reportedPersons"),
                        ("childVictims", "childVictims"),
                        ("intendedRecipients", "intendedRecipients")):
        grupo = ri.get(cont) or {}
        if not isinstance(grupo, dict):
            continue
        for p in (grupo.get(clave) or []):
            for campo in ("profileBio", "physicalDescription", "vehicleDescription"):
                if p.get(campo):
                    p[campo] = PLACEHOLDER
                    cambios.append("%s de una persona reportada" % campo)

    # 3. datos de contacto de quienes intervinieron en el tramite
    esp = ri.get("reportingEsp") or {}
    contacto = (esp.get("contactForLawEnforcement") or {}).get("contactPerson")
    if contacto:
        contacto["firstName"] = "NOMBRE"
        contacto["lastName"] = "REMOVIDO"
        if contacto.get("emails", {}).get("emails"):
            for e in contacto["emails"]["emails"]:
                e["value"] = "contacto@esp.example"
        cambios.append("contacto del proveedor")

    for c in ((r.get("lawEnforcementContactInformation") or {})
              .get("lawEnforcementContacts") or []):
        of = c.get("officer") or {}
        of["firstName"] = "NOMBRE"
        of["lastName"] = "REMOVIDO"
        of["title"] = "REMOVIDO"
        for e in (of.get("emails") or {}).get("emails", []):
            e["value"] = "contacto@organismo.example"
        for t in (of.get("phones") or {}).get("phones", []):
            t["value"] = "+540000000000"
        cambios.append("contacto del organismo receptor")

    # 4. resumenes y notas redactadas por analistas
    ncmec = r.get("additionalNcmecInformation") or {}
    if (ncmec.get("executiveSummary") or {}).get("value"):
        ncmec["executiveSummary"]["value"] = PLACEHOLDER
        cambios.append("resumen ejecutivo")
    for nota in (ncmec.get("notes") or {}).get("notes", []):
        if nota.get("value"):
            nota["value"] = PLACEHOLDER
            cambios.append("nota de analista")

    r.setdefault("reportedInformation", {})["additionalInformations"] = [
        {"value": "REPORTE REDACTADO: el texto libre y los datos de contacto "
                  "fueron removidos. Los identificadores tecnicos se conservan "
                  "para que la logica de vinculacion siga siendo verificable."}]
    return cambios


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ruta = sys.argv[1]
    base = os.path.dirname(os.path.dirname(os.path.abspath(ruta)))
    privado = os.path.join(base, "_privado")
    if not os.path.isdir(privado):
        os.makedirs(privado)

    resguardo = os.path.join(privado, os.path.basename(ruta).replace(
        ".json", ".original.json"))
    if not os.path.exists(resguardo):
        shutil.copy2(ruta, resguardo)
        print("Original resguardado en %s" % resguardo)
    else:
        print("Ya existia un resguardo en %s (no se pisa)" % resguardo)

    with open(ruta, "r", encoding="utf-8") as fh:
        r = json.load(fh)
    cambios = redactar(r)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=1)

    print("Redactado %s" % ruta)
    for c in sorted(set(cambios)):
        print("  - %s" % c)


if __name__ == "__main__":
    main()
