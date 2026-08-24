# -*- coding: utf-8 -*-
"""
Informe discursivo de vinculaciones, redactado por un modelo de lenguaje.

El circuito es: los algoritmos producen un dossier crudo con las vinculaciones y
su peso; ese dossier se seudonimiza; el modelo lo convierte en prosa jurídica; y
los identificadores reales se restituyen sobre el texto devuelto.

    dossier crudo  ->  seudonimizar  ->  modelo  ->  restituir  ->  informe

El modelo no ve ninguna IP, cuenta, teléfono ni dispositivo real: trabaja sobre
etiquetas (IP-1, CUENTA-2). Eso permite usar un modelo aunque no corra dentro
del entorno controlado, sin que la evidencia salga de él.

Uso:

    python informe_ia.py --sin-modelo
        Genera el dossier y un borrador discursivo determinista, sin modelo.
        Sirve para ver el circuito completo sin infraestructura.

    python informe_ia.py
        Usa un modelo local compatible con la API de OpenAI. Por defecto
        http://localhost:11434/v1 (Ollama). Configurable por variables de
        entorno GRAFO_LLM_URL, GRAFO_LLM_MODELO y GRAFO_LLM_API_KEY.

    python informe_ia.py --url http://localhost:8000/v1 --modelo qwen2.5:14b

Salidas en salida/:
    informe_crudo.json        dossier estructurado con los pesos
    informe_crudo_anonimo.json  el mismo, seudonimizado (lo que ve el modelo)
    prompt_informe.txt        instrucciones exactas enviadas
    informe_vinculaciones.md  el informe discursivo
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import construir                        # noqa: E402
import dossier as mod_dossier           # noqa: E402
import redaccion                       # noqa: E402
import ontologia as ont                 # noqa: E402

URL_POR_DEFECTO = os.environ.get("GRAFO_LLM_URL", "http://localhost:11434/v1")
MODELO_POR_DEFECTO = os.environ.get("GRAFO_LLM_MODELO", "qwen2.5:14b-instruct")


# ---------------------------------------------------------------------------
def llamar_modelo(url, modelo, sistema, usuario, api_key=None, timeout=600):
    cuerpo = json.dumps(dict(
        model=modelo,
        temperature=0.2,
        messages=[dict(role="system", content=sistema),
                  dict(role="user", content=usuario)],
    ), ensure_ascii=False).encode("utf-8")

    destino = url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(destino, data=cuerpo, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if api_key:
        req.add_header("Authorization", "Bearer %s" % api_key)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        datos = json.loads(r.read().decode("utf-8"))
    return datos["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=URL_POR_DEFECTO,
                    help="endpoint compatible con la API de OpenAI")
    ap.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    ap.add_argument("--sin-modelo", action="store_true",
                    help="redacta con plantillas, sin llamar a ningun modelo")
    ap.add_argument("--sin-seudonimizar", action="store_true",
                    help="envia los identificadores reales al modelo (desaconsejado)")
    ap.add_argument("--salida", default=os.path.join(BASE, "salida"))
    args = ap.parse_args()

    print("Construyendo el grafo...")
    g, res = construir.construir(construir.DIR_DATOS, args.salida)
    d = mod_dossier.construir(g, res)

    ruta_crudo = os.path.join(args.salida, "informe_crudo.json")
    with open(ruta_crudo, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1, default=str)
    print("Dossier crudo    : %s" % ruta_crudo)
    print("Vinculaciones    : %d (peso promedio %s)"
          % (d["pesos"].get("cantidad", 0),
             ont.numero(d["pesos"].get("peso_promedio"))))

    if args.sin_seudonimizar:
        d_envio, mapa = d, {}
        print("ATENCION: se enviarian los identificadores reales al modelo.")
    else:
        d_envio, mapa = mod_dossier.seudonimizar(g, d)
        ruta_anon = os.path.join(args.salida, "informe_crudo_anonimo.json")
        with open(ruta_anon, "w", encoding="utf-8") as fh:
            json.dump(d_envio, fh, ensure_ascii=False, indent=1, default=str)
        print("Seudonimizado    : %s (%d identificadores enmascarados)"
              % (ruta_anon, len(mapa)))

    usuario = mod_dossier.prompt_usuario(d_envio)
    ruta_prompt = os.path.join(args.salida, "prompt_informe.txt")
    with open(ruta_prompt, "w", encoding="utf-8") as fh:
        fh.write(mod_dossier.SISTEMA + "\n\n" + ("=" * 70) + "\n\n" + usuario)
    print("Prompt           : %s" % ruta_prompt)

    if args.sin_modelo:
        texto = redaccion.redactar(d)
        origen = "plantillas deterministas, sin modelo"
    else:
        anfitrion = args.url.split("//")[-1].split("/")[0].split(":")[0]
        if anfitrion not in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            print("\nATENCION: %s no es un endpoint local. La evidencia sensible "
                  "no debe salir del entorno sin autorizacion institucional "
                  "expresa.\n" % args.url)
        print("Consultando al modelo %s en %s ..." % (args.modelo, args.url))
        try:
            texto = llamar_modelo(args.url, args.modelo, mod_dossier.SISTEMA,
                                  usuario, os.environ.get("GRAFO_LLM_API_KEY"))
            origen = "%s vía %s" % (args.modelo, args.url)
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
            print("\nNo se pudo consultar al modelo: %s" % e)
            print("Se genera el borrador con plantillas. El prompt quedo en %s "
                  "para usarlo manualmente." % ruta_prompt)
            texto = redaccion.redactar(d)
            origen = "plantillas deterministas (el modelo no respondio)"

    if mapa:
        texto = mod_dossier.restituir(texto, mapa)

    encabezado = (u"<!-- Informe generado el %s a partir del dossier de la corrida "
                  u"%s. Redaccion: %s. Los identificadores fueron restituidos "
                  u"localmente. -->\n\n" % (res["corrida"], res["corrida"], origen))
    ruta_informe = os.path.join(args.salida, "informe_vinculaciones.md")
    with open(ruta_informe, "w", encoding="utf-8") as fh:
        fh.write(encabezado + texto)
    print("\nInforme          : %s" % ruta_informe)
    print("Redaccion        : %s" % origen)


if __name__ == "__main__":
    main()
