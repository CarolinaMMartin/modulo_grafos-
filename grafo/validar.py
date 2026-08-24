# -*- coding: utf-8 -*-
"""
Registro de decisiones humanas sobre las relaciones propuestas.

En la version institucional esto es un boton en la interfaz. Aca es una CLI,
para poder ejercitar el ciclo completo -propuesta, revision, decision,
reconstruccion- sin montar la aplicacion.

Uso:
    python validar.py cola                       lista lo pendiente
    python validar.py cola --origen inferida
    python validar.py ver e_1bfbf511c92672ff     muestra una relacion
    python validar.py e_1bfb... validada   --usuario op_04 --nota "confirmado"
    python validar.py e_1bfb... rechazada  --usuario op_04 --nota "cuenta compartida"
    python validar.py auditar                    verifica la cadena del libro

    python validar.py identidades                hipotesis de identidad y unificaciones
    python validar.py unificar e_xxx --usuario op_04
        Aprueba que dos menciones de persona son la misma. Crea un nodo de
        identidad que las agrupa, sin borrar ninguna.

Las decisiones se guardan en estado/validaciones.jsonl y se re-aplican en la
proxima construccion del grafo. Rechazar no borra: marca la arista como no
vigente y conserva la historia.
"""

import argparse
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import construir                        # noqa: E402
import ontologia as ont                 # noqa: E402
import validacion                       # noqa: E402

LIBRO = os.path.join(BASE, "estado", "validaciones.jsonl")
LIBRO_VINCULOS = os.path.join(BASE, "estado", "vinculos_manuales.jsonl")


def _grafo():
    g, res = construir.construir(construir.DIR_DATOS,
                                 os.path.join(BASE, "salida"))
    return g, res


def cmd_cola(args):
    g, res = _grafo()
    filas = validacion.pendientes(g, solo_origen=args.origen)
    if not filas:
        print("No hay relaciones pendientes de revision.")
        return
    print("%d relaciones pendientes\n" % len(filas))
    for f in filas[:args.limite]:
        conf = "%.2f" % f["confianza"] if f["confianza"] is not None else "  - "
        print("%-20s %-9s %-24s conf %s  %s -> %s"
              % (f["arista_id"], f["origen"], f["relacion"], conf, f["a"], f["b"]))
    if len(filas) > args.limite:
        print("\n... y %d mas (usar --limite)" % (len(filas) - args.limite))


def cmd_ver(args):
    g, res = _grafo()
    for u, v, k, d in g.aristas(vigentes=False):
        if d["arista_id"] != args.arista:
            continue
        print("Relacion   : %s (%s)" % (d["relation_type"], d["origin"]))
        print("Entre      : %s  ->  %s" % (g.G.nodes[u].get("etiqueta"),
                                           g.G.nodes[v].get("etiqueta")))
        print("Confianza  : %s" % d.get("confidence"))
        print("Metodo     : %s@%s  (ontologia %s)"
              % (d["method"], d["method_version"], d["ontologia_version"]))
        print("Fuente     : %s" % d["source_evidence_id"])
        print("Locator    : %s" % d["source_locator"])
        print("Observado  : %s" % (d.get("observed_at") or "-"))
        print("Estado     : %s%s" % (d["validation_status"],
                                     "" if not d.get("validated_by")
                                     else " por %s el %s" % (d["validated_by"],
                                                             d["validated_at"])))
        print("\n%s" % d.get("explicacion"))
        return
    print("No existe la arista %s en esta corrida." % args.arista)
    sys.exit(1)


def cmd_decidir(args):
    g, res = _grafo()
    existentes = {d["arista_id"]: (u, v, d)
                  for u, v, k, d in g.aristas(vigentes=False)}
    if args.arista not in existentes:
        print("No existe la arista %s en la corrida actual." % args.arista)
        sys.exit(1)
    u, v, d = existentes[args.arista]
    if d["origin"] == ont.OBSERVADA and args.decision == "rechazada":
        print("AVISO: esta relacion es OBSERVADA, es decir, consta en un campo "
              "del reporte de origen.\nRechazarla significa impugnar el dato de "
              "la fuente, no descartar una hipotesis del sistema.")
        if not args.forzar:
            print("Si es lo que queres hacer, repetir con --forzar.")
            sys.exit(1)

    libro = validacion.LibroValidaciones(LIBRO)
    reg = libro.registrar(args.arista, args.decision, args.usuario, args.nota or "")
    print("Registrado #%d: %s -> %s por %s"
          % (reg["secuencia"], args.arista, args.decision, args.usuario))
    print("Hash: %s" % reg["hash"])
    print("\nReconstruyendo el grafo con la decision aplicada...")
    g2, res2 = _grafo()
    print("Vinculos derivados vigentes: %d | pendientes de revision: %d"
          % (len([x for x in res2["vinculacion"]["vinculos"]]),
             len(res2["cola_revision"])))


def cmd_identidades(args):
    """Muestra las hipotesis de identidad y como quedaron las unificaciones."""
    g, res = _grafo()
    print("HIPOTESIS DE IDENTIDAD")
    print("Dos menciones de persona podrian ser la misma. El sistema no las "
          "unifica solo:\nlas propone y espera la decision de un operador.\n")
    hay = False
    for u, v, k, d in g.aristas(relacion="POSIBLE_MISMA_IDENTIDAD", vigentes=False):
        hay = True
        marca = {"validada": "[UNIFICADA]", "rechazada": "[DESCARTADA]"}.get(
            d["validation_status"], "[pendiente] ")
        print("%s %s" % (marca, d["arista_id"]))
        print("            %s  <->  %s" % (g.G.nodes[u].get("etiqueta"),
                                           g.G.nodes[v].get("etiqueta")))
        print("            cuenta compartida, confianza %s%s"
              % (d.get("confidence"),
                 "" if not d.get("validated_by")
                 else "  ·  por %s el %s" % (d["validated_by"], d["validated_at"])))
    if not hay:
        print("  (ninguna)")

    print("\nIDENTIDADES YA UNIFICADAS")
    if not res["identidades_unificadas"]:
        print("  (ninguna todavia)")
        print("\nPara unificar un par:")
        print("  python validar.py unificar <arista> --usuario TU_USUARIO")
    for x in res["identidades_unificadas"]:
        print("  %s" % g.G.nodes[x["identidad"]].get("etiqueta"))
        print("    reportes    : %s" % ", ".join(x["reportes"]))
        print("    menciones   : %d" % len(x["menciones"]))
        print("    validada por: %s" % ", ".join(x["validada_por"]))


def cmd_unificar(args):
    """Aprueba una hipotesis de identidad. Es azucar sobre 'validada'."""
    g, res = _grafo()
    objetivo = None
    for u, v, k, d in g.aristas(vigentes=False):
        if d["arista_id"] == args.arista:
            objetivo = (u, v, d)
    if not objetivo:
        print("No existe la arista %s en la corrida actual." % args.arista)
        sys.exit(1)
    u, v, d = objetivo
    if d["relation_type"] != "POSIBLE_MISMA_IDENTIDAD":
        print("La arista %s no es una hipotesis de identidad, sino %s.\n"
              "Para validarla usa: python validar.py %s validada --usuario X"
              % (args.arista, d["relation_type"], args.arista))
        sys.exit(1)

    print("Vas a unificar estas dos menciones bajo una misma identidad:\n")
    print("  %s" % g.G.nodes[u].get("etiqueta"))
    print("  %s\n" % g.G.nodes[v].get("etiqueta"))
    print(d.get("explicacion"))
    print("\nLa unificacion NO borra las menciones: cada reporte conserva la suya.")
    print("Si mas adelante se revierte, la identidad desaparece sola.\n")

    libro = validacion.LibroValidaciones(LIBRO)
    reg = libro.registrar(args.arista, "validada", args.usuario,
                          args.nota or "unificacion de identidad aprobada")
    print("Registrado #%d por %s" % (reg["secuencia"], args.usuario))
    print("Reconstruyendo el grafo con la unificacion aplicada...\n")
    g2, res2 = _grafo()
    for x in res2["identidades_unificadas"]:
        print("  %s" % g2.G.nodes[x["identidad"]].get("etiqueta"))
        print("    agrupa %d menciones de los reportes %s"
              % (len(x["menciones"]), ", ".join(x["reportes"])))
    print("\nEn el visor, activa 'Unificar identidades' para verlo colapsado.")


def cmd_vincular(args):
    """Vinculacion que dispone una persona, no el sistema.

    El caso real: dos reportes se archivaron por falta de prueba y el operador,
    con el expediente delante, concluye que tienen que ver. Eso no lo puede
    deducir el sistema. Lo que el sistema tiene que hacer es conservarlo, con
    quien lo dispuso y por que.
    """
    g, res = _grafo()
    faltan = [r for r in (args.reporte_a, args.reporte_b)
              if ont.nid("REPORTE", r) not in g.G]
    if faltan and not args.forzar:
        print("No existe(n) el/los reporte(s): %s" % ", ".join(faltan))
        print("Se cancela. Usar --forzar para registrarlo igual.")
        return

    libro = validacion.LibroVinculos(LIBRO_VINCULOS)
    reg = libro.registrar(args.reporte_a, args.reporte_b, "vincular",
                          args.usuario, args.motivo)
    print("Vinculacion registrada #%d" % reg["secuencia"])
    print("  %s  <->  %s" % (reg["reporte_a"], reg["reporte_b"]))
    print("  por %s el %s" % (reg["usuario"], reg["ts"]))
    print("  fundamento: %s" % reg["motivo"])
    print("")
    print("Se materializa en la proxima construccion, con origen 'afirmada'.")
    print("Los dos reportes van a quedar en el mismo caso.")


def cmd_desvincular(args):
    libro = validacion.LibroVinculos(LIBRO_VINCULOS)
    a, b = sorted((args.reporte_a, args.reporte_b))
    if (a, b) not in {(r["reporte_a"], r["reporte_b"]) for r in libro.vigentes()}:
        print("No hay una vinculacion manual vigente entre %s y %s." % (a, b))
        return
    reg = libro.registrar(a, b, "desvincular", args.usuario, args.motivo)
    print("Vinculacion revertida #%d  %s <-> %s  por %s"
          % (reg["secuencia"], a, b, reg["usuario"]))
    print("El registro anterior no se borra: la historia de la decision queda.")


def cmd_vinculos(args):
    libro = validacion.LibroVinculos(LIBRO_VINCULOS)
    regs = libro.registros()
    problemas = libro.verificar()
    print("VINCULACIONES ESTABLECIDAS POR UN OPERADOR")
    print("No las propuso el sistema: no constan en la fuente ni salen de una")
    print("regla. Se conservan hasta que alguien las revierta.")
    print("")
    print("Registros en el libro: %d" % len(regs))
    print("Integridad de la cadena: %s"
          % ("correcta" if not problemas else "; ".join(problemas)))
    vig = {(r["reporte_a"], r["reporte_b"]) for r in libro.vigentes()}
    for r in regs:
        estado = "[VIGENTE]  " if (r["accion"] == "vincular"
                                   and (r["reporte_a"], r["reporte_b"]) in vig)                  else "[revertida]" if r["accion"] == "desvincular" else "[pisada]   "
        print("  #%d %s %s <-> %s  por %s el %s"
              % (r["secuencia"], estado, r["reporte_a"], r["reporte_b"],
                 r["usuario"], r["ts"]))
        if r["motivo"]:
            print("        %s" % r["motivo"])


def cmd_auditar(args):
    libro = validacion.LibroValidaciones(LIBRO)
    regs = libro.registros()
    problemas = libro.verificar()
    print("Registros en el libro: %d" % len(regs))
    print("Integridad de la cadena: %s"
          % ("correcta" if not problemas else "; ".join(problemas)))
    for r in regs:
        print("  #%d %s %s por %s el %s %s"
              % (r["secuencia"], r["arista_id"], r["decision"], r["usuario"],
                 r["ts"], ("- " + r["observacion"]) if r["observacion"] else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("cola", help="lista relaciones pendientes")
    p.add_argument("--origen", choices=list(ont.ORIGENES))
    p.add_argument("--limite", type=int, default=25)
    p.set_defaults(func=cmd_cola)

    p = sub.add_parser("ver", help="muestra el detalle de una relacion")
    p.add_argument("arista")
    p.set_defaults(func=cmd_ver)

    p = sub.add_parser("identidades", help="hipotesis de identidad y unificaciones")
    p.set_defaults(func=cmd_identidades)

    p = sub.add_parser("unificar", help="aprueba unificar dos menciones de persona")
    p.add_argument("arista")
    p.add_argument("--usuario", required=True)
    p.add_argument("--nota", default="")
    p.set_defaults(func=cmd_unificar)

    p = sub.add_parser("auditar", help="verifica la cadena de hashes del libro")
    p.set_defaults(func=cmd_auditar)

    p = sub.add_parser("vincular",
                       help="establece a mano una vinculacion entre dos reportes")
    p.add_argument("reporte_a")
    p.add_argument("reporte_b")
    p.add_argument("--usuario", required=True)
    p.add_argument("--motivo", required=True,
                   help="fundamento de la decision; queda en el informe")
    p.add_argument("--forzar", action="store_true")
    p.set_defaults(func=cmd_vincular)

    p = sub.add_parser("desvincular", help="revierte una vinculacion manual")
    p.add_argument("reporte_a")
    p.add_argument("reporte_b")
    p.add_argument("--usuario", required=True)
    p.add_argument("--motivo", default="")
    p.set_defaults(func=cmd_desvincular)

    p = sub.add_parser("vinculos", help="lista las vinculaciones manuales")
    p.set_defaults(func=cmd_vinculos)

    p = sub.add_parser("decidir", help="registra una decision")
    p.add_argument("arista")
    p.add_argument("decision", choices=list(validacion.DECISIONES))
    p.add_argument("--usuario", required=True)
    p.add_argument("--nota", default="")
    p.add_argument("--forzar", action="store_true")
    p.set_defaults(func=cmd_decidir)

    # Forma corta: validar.py <arista> <decision> --usuario X
    argv = sys.argv[1:]
    if argv and argv[0] not in ("cola", "ver", "auditar", "decidir",
                                "identidades", "unificar", "vincular",
                                "desvincular", "vinculos", "-h", "--help"):
        argv = ["decidir"] + argv

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
