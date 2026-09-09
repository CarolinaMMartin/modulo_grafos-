# -*- coding: utf-8 -*-
"""
Generador de DOCUMENTACION_TECNICA.md.

Por que generado y no escrito a mano: es un documento de pesos, umbrales y
parametros. Un documento asi escrito a mano es exacto el dia que se escribe y
deja de serlo en la primera correccion del codigo, sin que nadie se entere. Aca
cada numero se lee del modulo que lo define en el momento de generar, y el
ejemplo trabajado se calcula sobre la corrida real.

La prosa vive aca, los numeros vienen del codigo. Se regenera en cada
construccion, igual que MODELO_DATOS.md.
"""

import platform
import sys

import networkx as nx

import alertas as mod_alertas
import analisis
import normalizacion as nz
import ontologia as ont
import resolucion
import validacion


def _n(v, dec=2):
    return ont.numero(v, dec)


def _tabla(cabeceras, filas):
    L = ["| " + " | ".join(cabeceras) + " |",
         "|" + "|".join("---" for _ in cabeceras) + "|"]
    for f in filas:
        L.append("| " + " | ".join(str(c) for c in f) + " |")
    return L


def generar(ruta, g=None, res=None):
    a = []
    _portada(a)
    _stack(a)
    _modulos(a)
    _ontologia(a)
    _reglas(a)
    _combinacion(a, g, res)
    _discriminancia(a)
    _ip(a)
    _normalizacion(a)
    _identidades(a)
    _contradicciones(a)
    _alertas(a)
    _algoritmos(a, g)
    _libros(a)
    _salidas(a)
    _limites(a)
    texto = "\n".join(a).rstrip() + "\n"
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)
    return ruta


# ---------------------------------------------------------------------------
def _portada(a):
    a.append(u"<!-- Generado por grafo/src/docs_tecnicos.py en cada corrida.")
    a.append(u"     No editar a mano: los numeros se leen del codigo. -->")
    a.append(u"")
    a.append(u"# Documentación técnica — módulo de grafos, Bóveda CIJ")
    a.append(u"")
    a.append(u"Referencia completa de las tecnologías que se usan, de cómo está "
             u"configurado cada algoritmo y de cada peso, umbral y constante que "
             u"interviene en una decisión del sistema.")
    a.append(u"")
    a.append(u"**Este archivo se genera solo, en cada construcción, leyendo los "
             u"valores de los módulos que los definen.** No es una transcripción: "
             u"si mañana alguien cambia un peso en `src/ontologia.py`, este "
             u"documento cambia con él. Por eso no se edita a mano.")
    a.append(u"")
    a.append(u"Complementa a los otros tres, sin repetirlos:")
    a.append(u"")
    a.append(u"- `TRASPASO.md` — por qué cada cosa es como es, y qué se descartó.")
    a.append(u"- `grafo/ESTADO.md` — qué está implementado, simplificado o ausente.")
    a.append(u"- `grafo/MODELO_DATOS.md` — la ontología: tipos de nodo y vocabulario.")
    a.append(u"")
    a.append(u"Versión de ontología documentada: **%s**." % ont.ONTOLOGIA_VERSION)
    a.append(u"")
    a.append(u"---")
    a.append(u"")


def _stack(a):
    a.append(u"## 1. Base de ejecución")
    a.append(u"")
    a.append(u"Todo corre local, sin servicios de red y sin llamadas a terceros. "
             u"Es un requisito del proyecto, no una preferencia: la evidencia "
             u"sensible no sale del entorno.")
    a.append(u"")
    a.extend(_tabla(
        [u"Componente", u"Versión verificada", u"Para qué"],
        [[u"Python", platform.python_version(),
          u"todo el procesamiento; mínimo requerido 3.8"],
         [u"networkx", nx.__version__,
          u"estructura del grafo y algoritmos clásicos"],
         [u"Biblioteca estándar", u"—",
          u"servidor HTTP, hashes, JSON, fechas, expresiones regulares"]]))
    a.append(u"")
    a.append(u"Corrida de verificación: `%s` sobre `%s`."
             % (sys.version.split()[0], platform.platform()))
    a.append(u"")
    a.append(u"**Una sola dependencia externa, y es deliberado.** El servidor, el "
             u"visor, los informes, la seudonimización y los libros de decisiones "
             u"usan únicamente la biblioteca estándar. Agregar infraestructura "
             u"pesada antes de justificarla con requisitos medidos está "
             u"expresamente desaconsejado en el contexto del proyecto.")
    a.append(u"")


def _modulos(a):
    a.append(u"## 2. Módulos y sus versiones")
    a.append(u"")
    a.append(u"Cada módulo que produce relaciones declara un método y una versión, "
             u"y ambos quedan grabados en **cada arista que crea**. Es lo que "
             u"permite, meses después, saber con qué versión de qué regla se "
             u"produjo un vínculo determinado.")
    a.append(u"")
    a.extend(_tabla(
        [u"Módulo", u"Método que graba", u"Versión", u"Responsabilidad"],
        [[u"`src/resolucion.py`", u"`%s`" % resolucion.METODO, resolucion.VERSION,
          u"vinculación entre reportes, identidades, contra-evidencia"],
         [u"`src/analisis.py`", u"`%s`" % analisis.METODO, analisis.VERSION,
          u"legajos, comunidades, centralidades, baseline de enlaces"],
         [u"`src/alertas.py`", u"`%s`" % mod_alertas.METODO, mod_alertas.VERSION,
          u"alertas de reapertura tipadas por motivo de archivo"],
         [u"`src/normalizacion.py`", u"—", nz.NORMALIZACION_VERSION,
          u"teléfonos, correos, IP, alias, marcas temporales"],
         [u"`src/validacion.py`", u"`%s`" % validacion.LibroVinculos.METODO,
          validacion.LibroVinculos.METODO_VERSION,
          u"libros de decisiones humanas y vinculación manual"],
         [u"`src/ontologia.py`", u"—", ont.ONTOLOGIA_VERSION,
          u"tipos, vocabulario, reglas, pesos y umbrales"]]))
    a.append(u"")
    a.append(u"Los módulos sin versión propia no crean aristas: transforman "
             u"valores (`normalizacion`) o declaran vocabulario (`ontologia`), y "
             u"su versión viaja igual en cada arista como "
             u"`ontologia_version`.")
    a.append(u"")


def _ontologia(a):
    a.append(u"## 3. Clases de relación")
    a.append(u"")
    a.append(u"Toda arista pertenece a **una** de estas clases y nunca se mezclan, "
             u"ni en la base ni en la pantalla. Es la separación epistemológica "
             u"que ordena todo el sistema.")
    a.append(u"")
    a.extend(_tabla(
        [u"Clase", u"Qué significa", u"Estado inicial", u"¿Lleva peso?"],
        [[u"`%s`" % o,
          ont.DESCRIPCION_ORIGEN.get(o, u""),
          u"`%s`" % ont.ESTADO_INICIAL[o],
          u"no" if o in (ont.OBSERVADA, ont.AFIRMADA) else u"sí, obligatorio"]
         for o in ont.ORIGENES]))
    a.append(u"")
    a.append(u"Dos consecuencias que conviene tener presentes:")
    a.append(u"")
    a.append(u"- Una **observada** no lleva peso porque no hay nada que ponderar: "
             u"consta textualmente en un campo de la fuente. Nace validada, pero "
             u"puede impugnarse.")
    a.append(u"- Una **afirmada** tampoco lleva peso, y por el motivo contrario: "
             u"no hay cálculo alguno detrás. La dispuso una persona. Ponerle un "
             u"número sería inventar una precisión que nadie calculó.")
    a.append(u"")
    a.append(u"> La clase `afirmada` **no está en el documento rector** "
             u"(`contexto.md` §10.1, que enumera tres). Se agregó porque una "
             u"vinculación que dispone una persona no entra en ninguna de las "
             u"tres sin desdibujarlas. Está fundada en `TRASPASO.md` §4.13 y "
             u"**pendiente de validar con los especialistas**. No presentarla "
             u"como ontología aprobada.")
    a.append(u"")
    a.append(u"### Estados de validación")
    a.append(u"")
    a.append(u"`" + u"`, `".join(ont.ESTADOS_VALIDACION) + u"`")
    a.append(u"")
    a.append(u"Una arista rechazada **no se borra**: se marca `vigente = false` y "
             u"queda con su historial. La historia de la decisión se conserva.")
    a.append(u"")


def _reglas(a):
    a.append(u"## 4. Reglas de vinculación y sus pesos")
    a.append(u"")
    a.append(u"Estas son las nueve reglas que pueden vincular dos reportes. Todas "
             u"son deterministas: mismos datos, mismo resultado, siempre.")
    a.append(u"")
    a.append(u"Cada regla declara cuatro cosas.")
    a.append(u"")
    a.append(u"- **Peso base** — cuánto aporta si el identificador es plenamente "
             u"discriminante. Nunca es 1: ninguna coincidencia sola acredita nada.")
    a.append(u"- **¿Sostiene?** — si puede fundar el vínculo por sí sola, o si "
             u"únicamente refuerza uno que ya se apoya en un dato objetivo.")
    a.append(u"- **¿Pondera por rareza?** — si su peso decae cuando el "
             u"identificador aparece en muchos reportes.")
    a.append(u"- **Versión** — graba en cada arista que produce.")
    a.append(u"")
    filas = []
    for rid in sorted(ont.REGLAS):
        m = ont.REGLAS[rid]
        filas.append([
            u"`%s`" % rid,
            u"`%s`" % m["tipo_nodo"],
            _n(m["peso_base"]),
            u"**no, solo refuerza**" if m["corrobora_solamente"] else u"sí",
            u"sí" if m["usa_discriminancia"] else u"no",
            m["version"],
        ])
    a.extend(_tabla([u"Regla", u"Tipo de dato", u"Peso base", u"¿Sostiene?",
                     u"¿Pondera por rareza?", u"Ver."], filas))
    a.append(u"")
    a.append(u"### Qué detecta cada una")
    a.append(u"")
    for rid in sorted(ont.REGLAS):
        a.append(u"- **`%s`** — %s." % (rid, ont.REGLAS[rid]["desc"]))
    a.append(u"")
    a.append(u"### Por qué esos pesos y no otros")
    a.append(u"")
    a.append(u"El orden no es arbitrario: sigue **cuánto individualiza cada dato**.")
    a.append(u"")
    sostienen = [(r, ont.REGLAS[r]) for r in sorted(ont.REGLAS)
                 if not ont.REGLAS[r]["corrobora_solamente"]]
    corroboran = [(r, ont.REGLAS[r]) for r in sorted(ont.REGLAS)
                  if ont.REGLAS[r]["corrobora_solamente"]]
    a.append(u"La cuenta de plataforma encabeza con **%s** porque el par "
             u"`ESP + espUserId` identifica a un titular concreto dentro de una "
             u"plataforma. El dispositivo la sigue con **%s**: individualiza casi "
             u"tan bien, pero un aparato puede prestarse o venderse. Teléfono y "
             u"correo comparten **%s**. El hash de archivo baja a **%s** porque "
             u"prueba que dos reportes traen el mismo contenido, no que provengan "
             u"de la misma persona: un material que circula lo comparten muchos."
             % (_n(ont.REGLAS["R01_CUENTA"]["peso_base"]),
                _n(ont.REGLAS["R02_DISPOSITIVO"]["peso_base"]),
                _n(ont.REGLAS["R03_TELEFONO"]["peso_base"]),
                _n(ont.REGLAS["R05_EVIDENCIA"]["peso_base"])))
    a.append(u"")
    a.append(u"Debajo del umbral quedan las **%d reglas que solo refuerzan** "
             u"(%s). Su peso —entre %s y %s— está deliberadamente por debajo del "
             u"umbral de propuesta: aunque dispararan todas juntas, no alcanzan "
             u"para crear un vínculo. Es la traducción de la regla del "
             u"relevamiento: *una relación debe apoyarse en datos objetivos "
             u"coincidentes, no en semejanza contextual*."
             % (len(corroboran),
                u", ".join(u"`%s`" % r for r, _ in corroboran),
                _n(min(m["peso_base"] for _, m in corroboran)),
                _n(max(m["peso_base"] for _, m in corroboran))))
    a.append(u"")
    a.append(u"Ninguna regla que sostiene baja de **%s** ni llega a **%s**."
             % (_n(min(m["peso_base"] for _, m in sostienen)),
                _n(ont.CONFIANZA_MAXIMA)))
    a.append(u"")


def _combinacion(a, g, res):
    a.append(u"## 5. Cómo se combinan los pesos")
    a.append(u"")
    a.append(u"Cuando dos reportes comparten varios datos, cada regla que dispara "
             u"aporta su peso y se combinan con **noisy-OR**:")
    a.append(u"")
    a.append(u"```")
    a.append(u"confianza = 1 - Π (1 - peso_efectivo_i)")
    a.append(u"```")
    a.append(u"")
    a.append(u"La lectura es directa: cada coincidencia es una razón "
             u"independiente para creer que los reportes están relacionados, y la "
             u"confianza es la probabilidad de que **al menos una** sea válida. "
             u"Nunca baja al sumar evidencia y nunca supera 1.")
    a.append(u"")
    a.append(u"**La condición que lo gobierna todo:** el producto solo se acumula "
             u"si *al menos una* regla que sostiene disparó. Si únicamente "
             u"dispararon reglas corroborantes, el resultado es `0.0` y el par se "
             u"descarta, por muchas que sean.")
    a.append(u"")
    a.append(u"### Umbrales")
    a.append(u"")
    a.extend(_tabla(
        [u"Constante", u"Valor", u"Qué decide"],
        [[u"`UMBRAL_PROPONER`", _n(ont.UMBRAL_PROPONER),
          u"por debajo, el vínculo no se propone y queda como descartado con su motivo"],
         [u"`UMBRAL_CLUSTER`", _n(ont.UMBRAL_CLUSTER),
          u"peso mínimo para que un vínculo agrupe dos reportes en un mismo legajo"],
         [u"`UMBRAL_PROBABLE`", _n(ont.UMBRAL_PROBABLE),
          u"desde acá la confianza se informa como «media»"],
         [u"`UMBRAL_ALTA`", _n(ont.UMBRAL_ALTA),
          u"desde acá se informa como «alta»"],
         [u"`CONFIANZA_MAXIMA`", _n(ont.CONFIANZA_MAXIMA),
          u"techo absoluto: ninguna arista puede llegar a 1"]]))
    a.append(u"")
    a.append(u"El techo de %s no es cosmético. Un 1,00 en pantalla se lee como "
             u"certeza, y el sistema no produce certezas: produce propuestas que "
             u"una persona tiene que revisar." % _n(ont.CONFIANZA_MAXIMA))
    a.append(u"")
    _ejemplo(a, g, res)


def _ejemplo(a, g, res):
    """Un vinculo real de la corrida, con su aritmetica desarmada."""
    if not (g and res):
        return
    mejor = None
    for u, v, k, d in g.aristas(origen=ont.DERIVADA):
        det = d.get("detalle_reglas") or []
        if len(det) >= 2 and (mejor is None or len(det) > len(mejor[2])):
            mejor = (u, v, det, d)
    if not mejor:
        return
    u, v, det, d = mejor
    a.append(u"### Ejemplo trabajado, calculado sobre esta corrida")
    a.append(u"")
    a.append(u"Reportes **%s** y **%s**. Dispararon %d reglas:"
             % (g.G.nodes[u]["valor"], g.G.nodes[v]["valor"], len(det)))
    a.append(u"")
    filas = []
    for x in sorted(det, key=lambda y: -(y.get("peso_efectivo") or 0)):
        filas.append([
            u"`%s`" % x["regla"],
            x.get("valor") or u"—",
            _n(x.get("peso_base")),
            _n(x.get("factor_discriminancia"), 4),
            _n(x.get("peso_efectivo"), 4),
            u"refuerza" if x.get("corrobora_solamente") else u"**sostiene**",
        ])
    a.extend(_tabla([u"Regla", u"Valor coincidente", u"Peso base",
                     u"× rareza", u"= peso efectivo", u"Rol"], filas))
    a.append(u"")
    a.append(u"Como al menos una regla sostiene, se acumula:")
    a.append(u"")
    a.append(u"```")
    partes = [u"(1 - %s)" % _n(x.get("peso_efectivo"), 4)
              for x in sorted(det, key=lambda y: -(y.get("peso_efectivo") or 0))]
    prod = 1.0
    for x in det:
        prod *= (1.0 - min(x.get("peso_efectivo") or 0.0, ont.CONFIANZA_MAXIMA))
    a.append(u"confianza = 1 - " + u" × ".join(partes))
    a.append(u"          = 1 - %s" % _n(prod, 4))
    a.append(u"          = %s" % _n(min(1.0 - prod, ont.CONFIANZA_MAXIMA), 4))
    a.append(u"```")
    a.append(u"")
    a.append(u"Confianza registrada en la arista: **%s** — franja «%s», por el "
             u"techo de %s."
             % (_n(d.get("confidence"), 4),
                ont.franja_confianza(d.get("confidence") or 0),
                _n(ont.CONFIANZA_MAXIMA)))
    a.append(u"")


def _discriminancia(a):
    a.append(u"## 6. Ponderación por rareza (discriminancia)")
    a.append(u"")
    a.append(u"Un identificador que aparece en muchos reportes individualiza "
             u"menos. El peso base de cada regla se multiplica por un factor que "
             u"decae con `df` — la cantidad de reportes distintos en que aparece "
             u"ese identificador.")
    a.append(u"")
    a.append(u"```")
    a.append(u"si df <= %d           factor = 1,00" % ont.DF_PLENA_DISCRIMINANCIA)
    a.append(u"si df >  %d           factor = log(1 + %d) / log(1 + df),  "
             u"acotado a [0,15 ; 1,00]"
             % (ont.DF_PLENA_DISCRIMINANCIA, ont.DF_PLENA_DISCRIMINANCIA))
    a.append(u"```")
    a.append(u"")
    a.append(u"Curva efectiva, calculada al generar este documento:")
    a.append(u"")
    filas = [[df, _n(resolucion.discriminancia(df), 4),
              u"%s %%" % _n(100 * resolucion.discriminancia(df), 1)]
             for df in (1, 5, 10, 15, 25, 50, 100, 500, 5000)]
    a.extend(_tabla([u"df (reportes en que aparece)", u"Factor", u"Peso conservado"],
                    filas))
    a.append(u"")
    a.append(u"### Cuándo un identificador deja de sostener")
    a.append(u"")
    a.append(u"Además del decaimiento, hay un corte duro: pasado cierto punto el "
             u"identificador se degrada a *solo refuerza*, sin importar qué regla "
             u"sea.")
    a.append(u"")
    a.extend(_tabla(
        [u"Constante", u"Valor", u"Efecto"],
        [[u"`DF_PLENA_DISCRIMINANCIA`", ont.DF_PLENA_DISCRIMINANCIA,
          u"hasta acá el identificador conserva todo su peso"],
         [u"`DF_HUB_ABSOLUTO`", ont.DF_HUB_ABSOLUTO,
          u"desde acá deja de sostener por sí solo, con cualquier corpus"],
         [u"`DF_HUB_SIN_PARES`", ont.DF_HUB_SIN_PARES,
          u"desde acá no genera pares para comparar y se informa aparte como *hub*"],
         [u"`CORPUS_MINIMO_PARA_FRACCION`", ont.CORPUS_MINIMO_PARA_FRACCION,
          u"recién con este volumen se aplica también el criterio de fracción"],
         [u"`FRACCION_BAJA_DISCRIMINANCIA`", _n(ont.FRACCION_BAJA_DISCRIMINANCIA),
          u"con corpus grande, aparecer en más de esta fracción degrada"]]))
    a.append(u"")
    a.append(u"Hay un segundo descuento, independiente del anterior. Cuando el "
             u"identificador que comparten los dos reportes no está declarado en "
             u"ningún campo sino escrito en un texto libre —la conversación, la "
             u"biografía del perfil—, el peso se multiplica por "
             u"`FACTOR_TEXTO_LIBRE` = %s. No es que la extracción falle: es que "
             u"cambia lo que el dato significa. Que el prestador informe un "
             u"teléfono es un dato de la cuenta; que alguien lo escriba en un "
             u"chat es una afirmación de esa persona, que puede estar equivocada, "
             u"ser de un tercero o ser mentira."
             % _n(resolucion.FACTOR_TEXTO_LIBRE))
    a.append(u"")
    a.append(u"> **La rareza es una propiedad del identificador, no del tamaño de "
             u"la base.** El primer diseño medía la fracción del corpus, y con "
             u"diez reportes un dispositivo compartido por cuatro daba 40 %% y "
             u"quedaba degradado, perdiendo un vínculo legítimo. Ese mismo "
             u"dispositivo en cien mil reportes es altamente discriminante. Por "
             u"eso el umbral principal es **absoluto** sobre `df`, y la fracción "
             u"solo entra a partir de %d reportes. Hay invariantes que verifican "
             u"que `discriminancia(4)` da lo mismo con 10 y con 100.000 reportes."
             % ont.CORPUS_MINIMO_PARA_FRACCION)
    a.append(u"")
    a.append(u"La regla `R01_CUENTA` es la única exceptuada del corte por *hub*: "
             u"si un `espUserId` se repite en decenas de reportes, el problema es "
             u"de los datos y conviene verlo, no ocultarlo.")
    a.append(u"")


def _ip(a):
    a.append(u"## 7. Política de dirección IP")
    a.append(u"")
    a.append(u"Una IP aislada no identifica a nadie. Solo vale junto con fecha, "
             u"hora, prestador y —cuando hay NAT— puerto de origen.")
    a.append(u"")
    a.append(u"### Ventana temporal por prestador")
    a.append(u"")
    a.append(u"Dos capturas de la misma IP corresponden probablemente al mismo "
             u"abonado solo si están dentro de la ventana de reasignación del "
             u"prestador. Fuera de ella, la regla degrada de `R06_IP_VENTANA` "
             u"(%s, sostiene) a `R07_IP_SUELTA` (%s, solo refuerza)."
             % (_n(ont.REGLAS["R06_IP_VENTANA"]["peso_base"]),
                _n(ont.REGLAS["R07_IP_SUELTA"]["peso_base"])))
    a.append(u"")
    filas = [[u"*(cualquier otro)*" if k == "_default" else k, u"%d h" % v]
             for k, v in sorted(ont.VENTANA_IP_HORAS.items(),
                                key=lambda x: (x[0] != "_default", x[0]))]
    a.extend(_tabla([u"Prestador", u"Ventana asumida"], filas))
    a.append(u"")
    a.append(u"> **Estos valores son estimados y no están verificados con los "
             u"prestadores.** El supuesto viaja escrito en la explicación de cada "
             u"arista que produce, de modo que quien lee el informe sabe sobre "
             u"qué base se afirmó. Confirmarlos es una tarea pendiente.")
    a.append(u"")
    a.append(u"### CGNAT")
    a.append(u"")
    a.append(u"Bajo *Carrier-Grade NAT* (`%s`, RFC 6598) muchos abonados comparten "
             u"una misma IP pública, y sin el puerto de origen el prestador no "
             u"puede decir cuál." % ont.CGNAT_RED)
    a.append(u"")
    a.extend(_tabla(
        [u"Situación", u"Factor sobre el peso", u"Efecto"],
        [[u"IP normal, dentro de ventana", u"1,00",
          u"`R06_IP_VENTANA` con su peso pleno, **sostiene**"],
         [u"CGNAT **con** puerto en ambas capturas",
          u"× %s" % _n(ont.FACTOR_NAT_CON_PUERTO),
          u"sigue sosteniendo: el prestador puede identificar al abonado"],
         [u"CGNAT **sin** puerto", u"× %s" % _n(ont.FACTOR_NAT_SIN_PUERTO),
          u"**se degrada a solo refuerza**: no permite atribuir a nadie"],
         [u"Fuera de ventana", u"—",
          u"pasa a `R07_IP_SUELTA`, que nunca sostiene"],
         [u"Sin fecha ni hora en alguna captura", u"—",
          u"pasa a `R07_IP_SUELTA`"]]))
    a.append(u"")
    a.append(u"El reporte real del dataset trae `port: 19096`, un campo que suele "
             u"ignorarse y que acá cambia el resultado.")
    a.append(u"")
    a.append(u"### Zona horaria")
    a.append(u"")
    a.append(u"NCMEC informa en UTC; los prestadores argentinos responden en hora "
             u"local. Tres horas de corrimiento alcanzan para atribuir una "
             u"conexión al abonado equivocado. Toda fecha sin zona horaria "
             u"explícita se marca como supuesto en la explicación de la arista.")
    a.append(u"")


def _normalizacion(a):
    a.append(u"## 8. Normalización de identificadores")
    a.append(u"")
    a.append(u"Antes de comparar, cada identificador se lleva a una forma "
             u"canónica. Sin esto, `011 15 6888-9999` y `+54 9 11 6888 9999` "
             u"serían dos teléfonos distintos. Versión: **%s**."
             % nz.NORMALIZACION_VERSION)
    a.append(u"")
    ejemplos = [
        (u"Teléfono", u"E.164 argentino: se saca el `9` de móvil, se descartan "
                      u"longitudes inverosímiles (fuera de 8 a 11 dígitos "
                      u"nacionales)",
         u"011 15 6888 9999", nz.normalizar_telefono(u"011 15 6888 9999")[0]),
        (u"Teléfono", u"misma entrada en formato internacional",
         u"+54 9 11 6888-9999", nz.normalizar_telefono(u"+54 9 11 6888-9999")[0]),
        (u"Correo", u"minúsculas, sin espacios, con validación de forma",
         u"  Lechero@Example.COM ", nz.normalizar_email(u"  Lechero@Example.COM ")[0]),
        (u"Alias", u"minúsculas y espacios colapsados; identificador **débil**",
         u"  El  Lechero ", nz.normalizar_alias(u"  El  Lechero ")[0]),
        (u"IP", u"validación de forma y marcado de rasgos",
         u"181.46.66.242", nz.normalizar_ip(u"181.46.66.242")[0]),
        (u"IP", u"CGNAT detectada",
         u"100.66.12.45", nz.normalizar_ip(u"100.66.12.45")[0]),
    ]
    a.extend(_tabla([u"Tipo", u"Regla", u"Entrada", u"Resultado"],
                    [[t, r, u"`%s`" % e, u"`%s`" % s] for t, r, e, s in ejemplos]))
    a.append(u"")
    _, _, rasgos = nz.normalizar_ip(u"100.66.12.45")
    a.append(u"Cada IP normalizada arrastra los rasgos que condicionan su valor "
             u"probatorio. Para `100.66.12.45`: %s."
             % u", ".join(u"`%s = %s`" % (k, v) for k, v in sorted(rasgos.items())))
    a.append(u"")
    a.append(u"Cuando una normalización descarta un valor, deja una nota que "
             u"explica por qué. Nada se descarta en silencio.")
    a.append(u"")


def _identidades(a):
    a.append(u"## 9. Hipótesis de identidad")
    a.append(u"")
    a.append(u"Cada reporte aporta su propia `PERSONA_MENCION`. Dos menciones que "
             u"comparten cuenta generan una relación `POSIBLE_MISMA_IDENTIDAD` "
             u"con confianza fija **%s** (`CONFIANZA_MISMA_IDENTIDAD`), clase "
             u"`inferida`, estado `pendiente` — **nunca una fusión**."
             % _n(resolucion.CONFIANZA_MISMA_IDENTIDAD))
    a.append(u"")
    a.append(u"Una cuenta puede estar compartida, vendida o comprometida. La "
             u"unificación existe, pero **la aprueba una persona**, y entonces:")
    a.append(u"")
    a.append(u"- no borra las menciones: cada reporte conserva la suya con su fuente;")
    a.append(u"- es transitiva, por conjuntos disjuntos (*union-find*): aprobar "
             u"A=B y B=C agrupa las tres;")
    a.append(u"- es reversible: revertir la validación deshace la identidad sola "
             u"en la próxima construcción.")
    a.append(u"")


def _contradicciones(a):
    a.append(u"## 10. Contra-evidencia")
    a.append(u"")
    a.append(u"Un grafo que solo acumula coincidencias tiende a confirmar la "
             u"hipótesis inicial. Por eso existen aristas que **debilitan**.")
    a.append(u"")
    a.append(u"`CONTRADICE` se produce cuando la misma cuenta aparece observada "
             u"desde dos IP geolocalizadas a una distancia que exige una "
             u"velocidad imposible.")
    a.append(u"")
    a.extend(_tabla(
        [u"Parámetro", u"Valor", u"Qué hace"],
        [[u"`VELOCIDAD_IMPOSIBLE_KMH`", _n(resolucion.VELOCIDAD_IMPOSIBLE_KMH, 0),
          u"por encima de esta velocidad implícita se marca la contradicción"],
         [u"`DISTANCIA_MINIMA_KM`", u"%s km" % _n(resolucion.DISTANCIA_MINIMA_KM, 0),
          u"por debajo no se evalúa: la geolocalización por IP no tiene esa precisión"],
         [u"Distancia", u"Haversine",
          u"sobre las coordenadas informadas por la geolocalización"],
         [u"`CONFIANZA_CONTRADICCION`", _n(resolucion.CONFIANZA_CONTRADICCION),
          u"es un indicio de inconsistencia, no una refutación"]]))
    a.append(u"")
    a.append(u"**No invalida nada.** Puede ser una VPN, una cuenta compartida o "
             u"una geolocalización errónea. Debilita la atribución, y por eso "
             u"conviene tenerla a la vista.")
    a.append(u"")


def _alertas(a):
    a.append(u"## 11. Alertas de reapertura")
    a.append(u"")
    a.append(u"Un archivado **no se reabre porque apareció una conexión**. Se "
             u"reabre porque apareció *el dato que le faltaba*. Por eso el motivo "
             u"de archivo es un campo de primera clase y cada motivo declara qué "
             u"aporte lo reactiva.")
    a.append(u"")
    filas = []
    for motivo, m in mod_alertas.DISPARADORES.items():
        nombre = (u"*(cualquier otro motivo)*" if motivo == "_default"
                  else u"`%s`" % motivo)
        filas.append([
            nombre,
            u"; ".join(mod_alertas.NOMBRE_APORTE.get(x, x) for x in m["aportes"]),
            m["prioridad"],
        ])
    a.extend(_tabla([u"Motivo del archivo", u"Qué lo reactiva", u"Prioridad"], filas))
    a.append(u"")
    a.append(u"### Las dos condiciones")
    a.append(u"")
    a.append(u"Una alerta exige **ambas**, no una:")
    a.append(u"")
    a.append(u"1. que el vínculo entre los dos reportes esté sostenido por una "
             u"regla fuerte —no solo por reglas que refuerzan—;")
    a.append(u"2. que el reporte disparador aporte efectivamente aquello que le "
             u"faltaba al archivado.")
    a.append(u"")
    a.append(u"Los vínculos que no califican se registran como **silenciados**, "
             u"con su motivo. No se descartan en silencio.")
    a.append(u"")
    a.append(u"### Estados institucionales")
    a.append(u"")
    a.extend(_tabla(
        [u"Grupo", u"Estados"],
        [[u"Se consideran archivados",
          u"`" + u"`, `".join(sorted(mod_alertas.ESTADOS_ARCHIVADOS)) + u"`"],
         [u"Se consideran activos (pueden disparar)",
          u"`" + u"`, `".join(sorted(mod_alertas.ESTADOS_ACTIVOS)) + u"`"],
         [u"Tipos de dato que individualizan",
          u"`" + u"`, `".join(sorted(mod_alertas.TIPOS_ATRIBUIBLES)) + u"`"]]))
    a.append(u"")
    a.append(u"> Toda esta lógica depende de que el motivo de archivo se registre "
             u"de forma **estructurada**. Hoy se simula con "
             u"`reportes_sinteticos/estado_institucional.json`. Si en SIPAR es "
             u"texto libre, ese es el primer cambio a pedir.")
    a.append(u"")


def _algoritmos(a, g):
    a.append(u"## 12. Algoritmos clásicos de grafos")
    a.append(u"")
    a.append(u"Corren sobre la **proyección reporte–reporte**: un grafo no "
             u"dirigido donde cada nodo es un reporte y cada arista un vínculo "
             u"que superó `UMBRAL_CLUSTER` (%s), más las vinculaciones manuales, "
             u"que entran sin umbral." % _n(ont.UMBRAL_CLUSTER))
    a.append(u"")
    a.extend(_tabla(
        [u"Qué", u"Algoritmo", u"Configuración", u"Para qué sirve"],
        [[u"Legajos", u"componentes conexas", u"—",
          u"qué reportes conviene mirar juntos"],
         [u"Comunidades", u"Louvain", u"`weight=\"peso\"`, `seed=7`",
          u"subgrupos dentro de un legajo grande; con pocos reportes coincide con las componentes"],
         [u"Centralidad de grado", u"`degree_centrality`", u"top 10",
          u"con cuántos se conecta cada reporte"],
         [u"Intermediación", u"`betweenness_centrality`",
          u"top 10, solo si el grafo tiene ≤ 3.000 nodos",
          u"qué reporte actúa de puente entre grupos"],
         [u"PageRank", u"`pagerank`", u"top 10, solo si ≤ 20.000 nodos",
          u"importancia estructural"],
         [u"Puentes", u"`nx.bridges`", u"top 10",
          u"aristas cuya caída parte el legajo en dos"],
         [u"Enlaces probables", u"Adamic–Adar", u"top 15, **no materializa aristas**",
          u"baseline determinista contra el cual comparar una futura GNN"]]))
    a.append(u"")
    a.append(u"El `seed=7` de Louvain no es decorativo: sin él dos corridas sobre "
             u"los mismos datos pueden dar comunidades distintas, y un informe "
             u"que cambia solo porque se volvió a ejecutar no es reproducible.")
    a.append(u"")
    a.append(u"Adamic–Adar **calcula y ordena, pero no escribe nada en el grafo**. "
             u"Es un ranking de pares que merecerían revisión, no un conjunto de "
             u"relaciones. Materializarlo convertiría una sugerencia estadística "
             u"en algo que se ve igual que un hecho.")
    a.append(u"")
    a.append(u"> **Una centralidad alta no significa culpabilidad, liderazgo ni "
             u"peligrosidad.** Describe una posición estructural en el grafo que "
             u"se pudo construir con los datos disponibles. Un reporte puede ser "
             u"central solo porque su plataforma informa más campos que las "
             u"demás. La advertencia viaja en la salida del propio módulo.")
    a.append(u"")


def _libros(a):
    a.append(u"## 13. Registro de las decisiones humanas")
    a.append(u"")
    a.append(u"El grafo es una **proyección reconstruible**: se borra `salida/` y "
             u"se regenera desde los reportes. Las decisiones de las personas no "
             u"pueden vivir ahí, así que viven aparte y se re-aplican sobre el "
             u"grafo reconstruido.")
    a.append(u"")
    a.extend(_tabla(
        [u"Libro", u"Qué registra", u"Clave"],
        [[u"`estado/validaciones.jsonl`",
          u"validar, rechazar o poner en revisión una relación existente; "
          u"aprobar una unificación de identidad",
          u"`arista_id`"],
         [u"`estado/vinculos_manuales.jsonl`",
          u"vincular o desvincular dos reportes por decisión propia",
          u"el par de reportes"]]))
    a.append(u"")
    a.append(u"Ambos son **append-only y encadenados por hash**: cada registro "
             u"lleva `prev_hash` y un `hash` SHA-256 de su propio contenido.")
    a.append(u"")
    a.append(u"Esto funciona porque **el identificador de arista es "
             u"determinista**: se calcula con SHA-1 truncado sobre extremos, "
             u"relación, método, locator y fuente, de modo que la misma evidencia "
             u"con el mismo método produce el mismo `arista_id` en cada corrida. "
             u"Es la propiedad que no se puede perder.")
    a.append(u"")
    a.append(u"> **Alcance real de la cadena de hashes:** detecta la modificación "
             u"o el borrado de registros anteriores. **No** impide que alguien con "
             u"acceso de escritura reescriba el archivo entero, ni sella el "
             u"tiempo. Para eso hace falta almacenamiento append-only del lado "
             u"del servidor o anclaje externo, que todavía no está definido.")
    a.append(u"")
    a.append(u"### Seudonimización")
    a.append(u"")
    a.append(u"Antes de enviar el dossier a cualquier modelo de lenguaje, los "
             u"identificadores de tipo `%s` se reemplazan por etiquetas estables "
             u"(`IP-1`, `CUENTA-2`). El modelo redacta sobre las etiquetas y los "
             u"valores reales se restituyen después, localmente, sobre el texto "
             u"devuelto. Hay invariantes que verifican que ningún identificador "
             u"real sobrevive en el dossier seudonimizado."
             % u"`, `".join(__import__("dossier").TIPOS_SENSIBLES))
    a.append(u"")


def _salidas(a):
    a.append(u"## 14. Formatos de salida")
    a.append(u"")
    a.extend(_tabla(
        [u"Archivo", u"Formato", u"Para qué"],
        [[u"`grafo.json`", u"JSON",
          u"grafo completo con la procedencia de cada arista"],
         [u"`grafo.graphml`", u"GraphML",
          u"para Gephi, yEd o Cytoscape"],
         [u"`analisis.json`", u"JSON",
          u"resultado estructurado de cada módulo de la corrida"],
         [u"`grafo.html`", u"HTML autocontenido",
          u"el visor, sin dependencias externas"],
         [u"`informes_por_caso/`", u"Markdown",
          u"un informe por caso, que es el que se firma"],
         [u"`informe_vinculaciones.md`", u"Markdown",
          u"informe general de la corrida"],
         [u"`informe.md`", u"Markdown",
          u"informe técnico con trazabilidad a la fuente"],
         [u"`informe_crudo.json`", u"JSON",
          u"dossier con el peso de cada vínculo y el aporte de cada regla"],
         [u"`informe_crudo_anonimo.json`", u"JSON",
          u"el mismo, seudonimizado: es lo único que ve un modelo"],
         [u"`textos_restringidos.json`", u"JSON",
          u"texto sensible **fuera** del grafo, indexado por hash"]]))
    a.append(u"")
    a.append(u"Todo lo de `salida/` se regenera en cada corrida y no se versiona. "
             u"Lo único que no se recalcula es `estado/`.")
    a.append(u"")


def _limites(a):
    a.append(u"## 15. Límites de esta configuración")
    a.append(u"")
    a.append(u"Lo que sigue no son defectos ocultos: son las condiciones bajo las "
             u"cuales los números de arriba son válidos.")
    a.append(u"")
    a.append(u"1. **Los pesos no están calibrados contra un conjunto validado.** "
             u"Salen del criterio del relevamiento —cuánto individualiza cada "
             u"dato— y no de medir aciertos y errores sobre casos reales ya "
             u"trabajados. Ese conjunto todavía no existe, y sin él no se puede "
             u"informar precisión ni recall.")
    a.append(u"2. **Las ventanas de IP por prestador son estimadas.** Hay que "
             u"confirmarlas con cada uno.")
    a.append(u"3. **El corpus de prueba tiene diez reportes.** Los umbrales que "
             u"dependen del volumen —`CORPUS_MINIMO_PARA_FRACCION` = %d, "
             u"`DF_HUB_ABSOLUTO` = %d— no se ejercitan con datos reales, solo con "
             u"pruebas unitarias."
             % (ont.CORPUS_MINIMO_PARA_FRACCION, ont.DF_HUB_ABSOLUTO))
    a.append(u"4. **Todo corre en memoria con `networkx`.** No escala más allá de "
             u"decenas de miles de nodos. Evaluar una base de grafos distribuida "
             u"recién tiene sentido con volúmenes reales medidos.")
    a.append(u"5. **El extractor está escrito contra el JSON de NCMEC.** PDF y "
             u"XML no se procesan.")
    a.append(u"6. **No hay control de acceso.** Quien corre el sistema ve todo.")
    a.append(u"")
    a.append(u"---")
    a.append(u"")
    a.append(u"## Cómo verificar todo esto")
    a.append(u"")
    a.append(u"```bash")
    a.append(u"python grafo/construir.py   # regenera este documento y las salidas")
    a.append(u"python grafo/pruebas.py     # invariantes sobre las reglas no negociables")
    a.append(u"```")
    a.append(u"")
    a.append(u"Los invariantes cubren, entre otras cosas: que ninguna arista "
             u"exista sin fuente ni locator, que ninguna inferencia nazca "
             u"validada, que una afirmación humana no lleve peso, que la "
             u"discriminancia no dependa del tamaño del corpus, que una "
             u"coincidencia de solo alias y ciudad no vincule, que el "
             u"identificador de arista sea estable entre corridas y que el texto "
             u"sensible no entre al grafo.")
    a.append(u"")
