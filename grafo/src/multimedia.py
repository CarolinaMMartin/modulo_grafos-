# -*- coding: utf-8 -*-
"""Ingesta y comparacion explicable de metadatos multimedia.

El modulo no abre imagenes ni audios. Lee un manifiesto ``fileDetails`` y
conserva exactamente que caracteristica declaro esa fuente. Un SHA-256 igual
significa contenido binario igual; un pHash cercano solo significa similitud
visual; una huella de audio igual significa coincidencia segun el algoritmo
que la produjo, no identidad criptografica del archivo.

Para pHash no se comparan todos los archivos contra todos. Se divide la huella
de 64 bits en ``MAX_DISTANCIA_HAMMING + 1`` bloques. Dos huellas que difieren
en, como maximo, ese numero de bits tienen que compartir al menos un bloque
exacto (principio del palomar). Solo esos candidatos pasan al calculo exacto.
"""

import json
import os
import re
from collections import defaultdict
from itertools import combinations

import nucleo
import ontologia as ont

METODO = "analisis_multimedia"
VERSION = "1.0"
MAX_DISTANCIA_HAMMING = 8


def _lista(valor):
    return valor if isinstance(valor, list) else []


def _sha256(detalle):
    for h in _lista(detalle.get("originalFileHash")):
        if str(h.get("hashType") or "").upper().replace("-", "") != "SHA256":
            continue
        valor = str(h.get("value") or "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", valor):
            return valor
    return None


def _caracteristicas(detalle):
    salida = defaultdict(list)
    for bloque in _lista(detalle.get("details")):
        for par in _lista((bloque or {}).get("nameValuePair")):
            nombre = str((par or {}).get("name") or "").strip().lower()
            valor = str((par or {}).get("value") or "").strip()
            if nombre and valor:
                salida[nombre].append(valor)
    return salida


def _phash(valor):
    limpio = str(valor or "").strip().lower()
    if limpio.startswith("0x"):
        limpio = limpio[2:]
    # La primera version se limita a la huella de 64 bits presente en el lote.
    return limpio if re.fullmatch(r"[0-9a-f]{16}", limpio) else None


def _huella_audio(caracteristicas):
    for nombre, valores in caracteristicas.items():
        if "audio" in nombre and ("fingerprint" in nombre or "huella" in nombre):
            return valores[0]
    return None


def ingerir(g, rutas):
    """Incorpora manifiestos sin confundirlos con el JSON principal del reporte."""
    if isinstance(rutas, (str, os.PathLike)):
        rutas = [rutas]
    archivos, avisos, manifiestos = [], [], []

    for ruta in (rutas or []):
        if not ruta or not os.path.exists(ruta):
            avisos.append(dict(ruta=str(ruta), motivo="manifiesto inexistente"))
            continue
        with open(ruta, "r", encoding="utf-8") as fh:
            doc = json.load(fh)

        huella_fuente = nucleo.hash_archivo(ruta)
        sid_manifest = "multimedia:%s" % huella_fuente.split(":", 1)[1][:16]
        g.registrar_fuente(sid_manifest, ruta=ruta, tipo="manifiesto_multimedia",
                           extra=dict(metadatos_solamente=True))
        manifiestos.append(dict(id=sid_manifest, ruta=str(ruta), hash=huella_fuente))

        for i, detalle in enumerate(_lista(doc.get("fileDetails"))):
            rid = str((detalle or {}).get("reportId") or "")
            n_rep = ont.nid("REPORTE", rid)
            locator = "fileDetails[%d]" % i
            if not rid or n_rep not in g.G:
                avisos.append(dict(ruta=str(ruta), locator=locator,
                                   motivo="reportId ausente o no ingerido: %s" % rid))
                continue

            file_id = str(detalle.get("fileId") or "%s-%d" % (rid, i))
            sid_archivo = "%s:%d" % (sid_manifest, i)
            g.registrar_fuente(
                sid_archivo, ruta=ruta, tipo="detalle_multimedia",
                extra=dict(report_id=rid, manifest_id=sid_manifest,
                           file_id=file_id, indice=i, metadatos_solamente=True))

            sha = _sha256(detalle)
            clave_evidencia = ("sha256:%s" % sha if sha
                               else "archivo:%s:%s" % (rid, file_id))
            nombre = str(detalle.get("originalFileName") or file_id)
            caracteristicas = _caracteristicas(detalle)
            mime = (caracteristicas.get("media_type") or [None])[0]
            n_ev = g.nodo(
                "EVIDENCIA", clave_evidencia, etiqueta=nombre[:80],
                nombre=nombre, tipo_mime=mime, sha256=sha,
                file_id=file_id, metadatos_solamente=True)
            g.arista(
                n_rep, n_ev, "ADJUNTA", sid_archivo, locator,
                (u"El manifiesto asocia al reporte el archivo %s. En esta corrida "
                 u"solo se leyeron sus metadatos declarados; el módulo no abrió "
                 u"ni analizó el binario." % nombre),
                METODO, VERSION,
                observed_at=detalle.get("uploadedToEspTimestamp"),
                atributos=dict(file_id=file_id, metadatos_solamente=True))

            ph = None
            for candidato in (caracteristicas.get("perceptual_hash") or
                              caracteristicas.get("phash") or []):
                ph = _phash(candidato)
                if ph:
                    break
            n_ph = None
            if ph:
                n_ph = g.nodo("HASH_PERCEPTUAL", ph, etiqueta=ph, bits=64)
                g.arista(
                    n_ev, n_ph, "TIENE_HASH_PERCEPTUAL", sid_archivo,
                    locator + ".details.perceptual_hash",
                    (u"El manifiesto declara esta huella perceptual de 64 bits. "
                     u"Sirve para medir similitud visual; no demuestra que dos "
                     u"archivos sean binariamente iguales."),
                    METODO, VERSION)

            audio = _huella_audio(caracteristicas)
            n_audio = None
            if audio:
                n_audio = g.nodo("HUELLA_AUDIO", audio, etiqueta=audio)
                g.arista(
                    n_ev, n_audio, "TIENE_HUELLA_AUDIO", sid_archivo,
                    locator + ".details.audio_fingerprint",
                    (u"El manifiesto declara esta huella algorítmica de audio. "
                     u"Su coincidencia depende del método que la produjo y no "
                     u"equivale a un hash criptográfico del archivo."),
                    METODO, VERSION)

            archivos.append(dict(
                reporte=rid, evidencia=n_ev, file_id=file_id, nombre=nombre,
                source_evidence_id=sid_archivo, locator=locator,
                sha256=sha, phash=ph, nodo_phash=n_ph,
                huella_audio=audio, nodo_audio=n_audio))

    return dict(manifiestos=manifiestos, archivos=archivos, avisos=avisos)


def _bloques_phash(valor, partes=None):
    partes = partes or (MAX_DISTANCIA_HAMMING + 1)
    bits = bin(int(valor, 16))[2:].zfill(len(valor) * 4)
    base, resto = divmod(len(bits), partes)
    salida, inicio = [], 0
    for i in range(partes):
        largo = base + (1 if i < resto else 0)
        salida.append((i, bits[inicio:inicio + largo]))
        inicio += largo
    return salida


def distancia_hamming(a, b):
    """Cantidad exacta de bits diferentes entre dos hashes hexadecimales."""
    if len(a) != len(b):
        raise ValueError("los pHash deben tener la misma longitud")
    return (int(a, 16) ^ int(b, 16)).bit_count()


def _disparo_phash(a, b, distancia, similitud, arista_soporte):
    meta = ont.REGLAS["R11_PHASH_SIMILAR"]
    peso = round(meta["peso_base"] * similitud, 4)
    return dict(
        reporte_a=a["reporte"], reporte_b=b["reporte"],
        regla="R11_PHASH_SIMILAR", regla_version=meta["version"],
        nodo=None, tipo="HASH_PERCEPTUAL",
        valor="%s ~ %s" % (a["phash"], b["phash"]),
        peso_base=meta["peso_base"], peso_efectivo=peso,
        factor_discriminancia=1.0, factor_texto_libre=1.0,
        factor_similitud=round(similitud, 4), desde_texto=False,
        lados_desde_texto=0,
        procedencia_lado_a="manifiesto_multimedia",
        procedencia_lado_b="manifiesto_multimedia",
        corrobora_solamente=meta["corrobora_solamente"],
        origen_senal=ont.DERIVADA,
        arista_soporte=arista_soporte,
        source_locators=[a["locator"] + ".details.perceptual_hash",
                         b["locator"] + ".details.perceptual_hash"],
        nota=(u"las imágenes tienen hashes perceptuales separados por %d bit%s "
              u"de 64 (similitud de bits %s); esto indica parecido visual y no "
              u"identidad criptográfica"
              % (distancia, "" if distancia == 1 else "s",
                 ont.numero(similitud, 4))))


def analizar(g, carga):
    """Compara pHash y huellas de audio; devuelve señales para reportes."""
    archivos = carga.get("archivos", []) if carga else []
    con_phash = [x for x in archivos if x.get("phash")]

    # Multi-index hashing: genera candidatos por al menos un bloque identico.
    cubetas = defaultdict(list)
    for i, archivo in enumerate(con_phash):
        for bloque in _bloques_phash(archivo["phash"]):
            cubetas[bloque].append(i)
    candidatos = set()
    for indices in cubetas.values():
        for i, j in combinations(sorted(set(indices)), 2):
            candidatos.add((i, j))

    comparaciones_phash, disparos = [], []
    for i, j in sorted(candidatos):
        a, b = con_phash[i], con_phash[j]
        if a["reporte"] == b["reporte"] or a["evidencia"] == b["evidencia"]:
            continue
        distancia = distancia_hamming(a["phash"], b["phash"])
        if distancia > MAX_DISTANCIA_HAMMING:
            continue
        similitud = 1.0 - float(distancia) / (len(a["phash"]) * 4)
        sid = "derivacion:phash:%s:%s" % tuple(sorted((a["evidencia"], b["evidencia"])))
        locators = [a["locator"] + ".details.perceptual_hash",
                    b["locator"] + ".details.perceptual_hash"]
        g.registrar_fuente(
            sid, tipo="comparacion_phash",
            extra=dict(fuentes=[a["source_evidence_id"], b["source_evidence_id"]],
                       locators=locators, distancia_hamming=distancia,
                       umbral=MAX_DISTANCIA_HAMMING))
        aid = g.arista(
            a["evidencia"], b["evidencia"], "SIMILITUD_PERCEPTUAL", sid,
            " | ".join(locators),
            (u"Las huellas perceptuales difieren en %d bit%s de 64, dentro del "
             u"umbral operativo de %d. Es una similitud calculada sobre los "
             u"metadatos declarados: no se compararon los binarios y no se "
             u"afirma que sean el mismo archivo."
             % (distancia, "" if distancia == 1 else "s",
                MAX_DISTANCIA_HAMMING)),
            METODO, VERSION, confianza=similitud,
            atributos=dict(distancia_hamming=distancia, bits=64,
                           umbral_hamming=MAX_DISTANCIA_HAMMING,
                           similitud_bits=round(similitud, 4),
                           binarios_analizados=False))
        comparaciones_phash.append(dict(
            arista_id=aid, reporte_a=a["reporte"], reporte_b=b["reporte"],
            evidencia_a=a["evidencia"], evidencia_b=b["evidencia"],
            distancia_hamming=distancia, similitud_bits=round(similitud, 4)))
        # Con pHash identico la regla normal se activa por el nodo compartido.
        # Solo las huellas cercanas necesitan una señal de par adicional.
        if distancia > 0:
            disparos.append(_disparo_phash(
                a, b, distancia, similitud, arista_soporte=aid))

    por_audio = defaultdict(list)
    for archivo in archivos:
        if archivo.get("huella_audio"):
            por_audio[archivo["huella_audio"]].append(archivo)
    coincidencias_audio = []
    for huella, grupo in sorted(por_audio.items()):
        for a, b in combinations(grupo, 2):
            if a["reporte"] == b["reporte"] or a["evidencia"] == b["evidencia"]:
                continue
            sid = "derivacion:audio:%s:%s" % tuple(
                sorted((a["evidencia"], b["evidencia"])))
            locators = [a["locator"] + ".details.audio_fingerprint",
                        b["locator"] + ".details.audio_fingerprint"]
            g.registrar_fuente(
                sid, tipo="comparacion_huella_audio",
                extra=dict(fuentes=[a["source_evidence_id"],
                                    b["source_evidence_id"]],
                           locators=locators, huella=huella))
            aid = g.arista(
                a["evidencia"], b["evidencia"], "COINCIDE_HUELLA_AUDIO", sid,
                " | ".join(locators),
                (u"Los dos manifiestos declaran la misma huella algorítmica de "
                 u"audio. La coincidencia vincula los archivos según ese método, "
                 u"pero no equivale a un hash criptográfico ni demuestra quién "
                 u"los creó o compartió."),
                METODO, VERSION,
                confianza=ont.REGLAS["R12_HUELLA_AUDIO"]["peso_base"],
                atributos=dict(huella_audio=huella, binarios_analizados=False))
            coincidencias_audio.append(dict(
                arista_id=aid, reporte_a=a["reporte"], reporte_b=b["reporte"],
                evidencia_a=a["evidencia"], evidencia_b=b["evidencia"],
                huella=huella))

    return dict(
        comparaciones_phash=comparaciones_phash,
        coincidencias_audio=coincidencias_audio,
        disparos=disparos,
        metodo=METODO, version=VERSION,
        max_distancia_hamming=MAX_DISTANCIA_HAMMING,
        archivos_con_phash=len(con_phash),
        candidatos_phash_evaluados=len(candidatos))
