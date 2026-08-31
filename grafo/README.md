# Módulo de grafos — Bóveda CIJ

Corte vertical funcional del grafo de conocimiento, ejecutable de punta a punta
sin infraestructura. Implementa el primer objetivo recomendado en `contexto.md`
§21: ingreso de reportes → extracción con procedencia → vínculo con un caso
archivado → hipótesis separada → visualización → validación humana → informe.

Todo corre local, sin dependencias externas ni servicios de red.
Única dependencia: `networkx`.

## Ejecutar

```bash
python servidor.py
```

Abre el visor en el navegador. **Es la forma de usarlo**: los botones que
registran decisiones —vincular, revertir— solo funcionan acá, porque son los que
escriben en el libro. Escucha solo en esta computadora y no autentica a nadie:
el campo "quién lo dispone" sirve para saber quién dijo qué, no para acreditar
identidad.

Para generar las salidas sin levantar nada:

```bash
python construir.py
```

Eso deja `salida/grafo.html`, que se abre con doble clic pero sirve solo para
mirar: un archivo suelto no puede guardar nada. Si se toca un botón de decisión,
el visor lo dice en lugar de fingir que anduvo.

```bash
python pruebas.py
```

Los reportes de entrada viven en `../reportes_sinteticos/`. Para regenerar los
sintéticos (el reporte real no se toca):

```bash
python generar_sinteticos.py
```

## Cómo se usa el visor

**La pregunta que responde es una sola: este reporte, ¿tiene vinculaciones que
justifiquen reabrirlo?** Todo lo demás está subordinado a eso.

El lienzo es un árbol de arriba hacia abajo, no una nube de nodos:

```
                    +---------------------+
                    | Reporte en análisis |
                    +----------+----------+
        misma cuenta,          |          mismo
        mismo dispositivo      |          dispositivo
    +--------------+-----------+-----------+--------------+
    v              v                       v
+--------+   +--------+              +--------+
| Rep. 1 | + | Rep. 2 | +            | Rep. 3 | -
+--------+   +--------+              +---+----+
                                         |
              +----------+--------------+----------+
              v          v              v          v
          +-------+ +--------+   +-----------+ +----------+
          |lechero| |IP 5556.|   |cuenta@esp | |Monte Gr. |
          +-------+ +--------+   +-----------+ +----------+
```

- Arriba, el **reporte en análisis**.
- Debajo, los reportes con los que se vincula. Sobre cada conector está escrito
  **por qué**: *misma cuenta, mismo dispositivo · peso 0,99*.
- El botón **+** de cada reporte abre sus datos en la fila siguiente. **−** los
  cierra.
- Cuando uno de esos datos aparece además en otro de los reportes, una línea de
  color vuelve hacia arriba y lo conecta. Es lo que muestra, de un vistazo, qué
  dato sostiene qué vinculación.
- La caja de un dato compartido lleva escrito *en N reportes*.

### El panel derecho

Acompaña siempre a lo que se toca en el lienzo:

| Al hacer clic en... | El panel muestra |
|---|---|
| El fondo, o al abrir | Resumen del caso: cuántas vinculaciones tiene el reporte en análisis y con quién |
| Un **conector** entre reportes | Por qué se vinculan: qué dato lo sostiene, la cadena completa desde cada reporte, el fundamento redactado y de dónde surge |
| Un **reporte** | Resumen del reporte, con quién se vincula y por qué, y sus entidades agrupadas por tipo |
| Un **dato** | En qué reportes del caso aparece y cómo se conecta |

Desde la ficha de cualquier reporte, **Analizar este reporte** lo lleva a la
cima del árbol y reconstruye la vista alrededor de él.

### Otras acciones

- **Volver / Siguiente** recorren el historial. También `Alt + izquierda` y
  `Alt + derecha`.
- **Encuadrar** ajusta el zoom al contenido. Rueda para acercar, arrastrar para
  desplazar.
- **Contraer** cierra todo lo abierto.
- El selector de arriba cambia de caso. El visor nunca muestra dos a la vez.
- Al hacer clic en un dato se apaga todo lo que no lo involucra, y el panel
  derecho dice qué vinculaciones sostiene. El segundo clic devuelve la vista.
  Lo mismo al hacer clic sobre el conector de una vinculación.
- Las cajas se arrastran de a una para separar ramas que se cruzan.
  **Ordenar** las devuelve a su lugar.
- Desde la ficha de un dato, **Poner este dato en el centro** vuelve a colgar el
  árbol de él: arriba el dato, abajo los reportes en los que consta.
- El panel izquierdo trae la búsqueda dentro del caso, los antecedentes a
  revisar, el peso mínimo, los tipos de dato y la leyenda.

### Vincular a mano

Si el sistema no vinculó dos reportes y a criterio del operador sí tienen que
ver, en la ficha de cada coincidencia que no alcanzó hay un botón **Vincular
estos reportes**. Se abre un cuadro que pide quién lo dispone y el fundamento
—obligatorio, y va al informe—, se registra en el libro, se reconstruye el grafo
y la pantalla vuelve al mismo reporte con el aviso de lo que quedó asentado.

La vinculación se dibuja con su propio trazo, entra en el informe del caso y
agrupa los dos reportes en el mismo legajo. No lleva peso: no hay nada calculado
que ponderar. Se revierte desde su ficha, y el registro anterior no se borra.

Los mismos actos por consola, para quien esté trabajando en el código:

```bash
python validar.py vincular 900000104 900000109 --usuario op_04 --motivo "..."
python validar.py vinculos
python validar.py desvincular 900000104 900000109 --usuario op_04
```

### Cómo leer las líneas

Un solo criterio, y está en la leyenda del panel izquierdo:

- el **trazo** dice de dónde sale la relación — lleno: consta en la fuente;
  rayado: derivada por una regla; punteado: hipótesis sin validar; raya y punto:
  la estableció un operador;
- el **color** dice de qué tipo de dato se trata, y es el mismo en la barra de
  la caja, en la línea y en su punta de flecha.

### Lo que no se dibuja

- **Las plataformas y los prestadores.** Todos los reportes de Grindr comparten
  Grindr: no distingue nada. Se informan en la ficha del reporte.
- **La mención de persona y el chat.** Son estructura interna del reporte, no
  aquello por lo que un reporte se vincula con otro. Aparecen en la cadena
  completa cuando se abre una vinculación.
- **Entidades de otros casos.** Pero si un dato aparece además en reportes de
  otro caso, la caja lo dice —*«en otros casos»*— y la ficha explica que la
  coincidencia se evaluó y no alcanzó para vincular.
- **La identidad unificada.** No es un dato del reporte sino una conclusión
  sobre una persona. Los reportes que agrupa llevan la marca *«misma persona»*.

## Informe

El botón **Informe** abre el informe **del caso en curso**, ya redactado, con el
peso de cada vínculo y el aporte de cada regla. Se genera uno por caso en cada
corrida, sin depender de ninguna infraestructura, y se puede descargar en
Markdown.

No enumera el archivo completo: lista los reportes del caso y remite al resto
como *carpeta de archivo provisorio*, explicando qué reúne y por qué el sistema
la recorre. Enumerarla deja de ser posible apenas hay unos miles de reportes.

Cuando haya un modelo local disponible, `informe_ia.py` toma el mismo dossier y
produce una redacción más fluida:

```bash
python informe_ia.py
```

Por defecto apunta a `http://localhost:11434/v1`; se configura con `--url` y
`--modelo`. El dossier se seudonimiza antes de enviarlo y los identificadores se
restituyen localmente sobre el texto devuelto.

## Unificar identidades

El sistema propone `POSIBLE_MISMA_IDENTIDAD` pero nunca fusiona por su cuenta.
La aprobación es un comando:

```bash
python validar.py identidades
```

```bash
python validar.py unificar e_95a74f9390f1562c --usuario op_04
```

Al aprobarla se crea un nodo de identidad que agrupa las menciones. Las
menciones **no se borran**: cada reporte conserva la suya con su fuente. Si se
aprueban A=B y B=C, las tres quedan bajo la misma identidad. En el visor, la
casilla *Unificar las identidades ya validadas* colapsa las menciones en el nodo
de identidad y redibuja sus relaciones desde ahí, que es lo que deja el grafo
limpio. Revertir la validación en el libro hace desaparecer la identidad sola en
la próxima construcción.

## Ciclo de revisión humana

```bash
python validar.py cola --origen inferida
```

```bash
python validar.py ver e_7e301ea5c99cbc0f
```

```bash
python validar.py e_7e301ea5c99cbc0f validada --usuario op_04 --nota "confirmado"
```

```bash
python validar.py auditar
```

Las decisiones se guardan en `estado/validaciones.jsonl`, un libro append-only
encadenado por hash, y se re-aplican en cada reconstrucción del grafo. Rechazar
no borra: marca la arista como no vigente y conserva la historia.

## Estructura

```
grafo/
  construir.py             orquestador: ingesta -> análisis -> salidas
  validar.py               CLI de validación humana
  pruebas.py               invariantes no negociables (103 chequeos)
  generar_sinteticos.py    dataset sintético de prueba
  MODELO_DATOS.md          generado desde la ontología, no editar a mano
  ESTADO.md                qué está implementado y qué no
  src/
    ontologia.py           tipos, vocabulario, reglas, umbrales, versión
    nucleo.py              contenedor del grafo y procedencia obligatoria
    normalizacion.py       teléfonos, correos, IP, alias, tiempo
    extractor_ncmec.py     JSON de NCMEC -> relaciones OBSERVADAS con locator
    jurisdiccion.py        SIN CONECTAR: clasificación territorial, Etapa 2
    resolucion.py          vínculos DERIVADOS, identidades, contra-evidencia
    alertas.py             reapertura tipada por motivo de archivo
    analisis.py            componentes, comunidades, centralidades, baseline
    identidades.py         consolida las unificaciones aprobadas
    dossier.py             dossier crudo, seudonimización y prompt
    validacion.py          libro append-only y re-aplicación
    render_html.py         visor autocontenido
    informe.py             informe en Markdown
    docs_modelo.py         genera MODELO_DATOS.md desde la ontología
  estado/                  libro de validaciones
  salida/                  resultados de la última corrida
```

## Salidas

| Archivo | Qué es |
|---|---|
| `salida/informe.md` | Informe legible. Cada hallazgo enlaza a su evidencia. |
| `salida/grafo.html` | Visor interactivo autocontenido. Abrir en el navegador. |
| `salida/grafo.json` | Grafo completo con procedencia de cada arista. |
| `salida/grafo.graphml` | Para Gephi, yEd o Cytoscape. |
| `salida/analisis.json` | Resultado estructurado de todos los módulos. |
| `salida/textos_restringidos.json` | Texto sensible, **fuera** del grafo, indexado por hash. |
| `salida/informe_crudo.json` | Dossier con el peso de cada vinculación y el aporte de cada regla. |
| `salida/informe_crudo_anonimo.json` | El mismo, seudonimizado: es lo único que ve el modelo. |
| `salida/informe_vinculaciones.md` | El informe discursivo de toda la corrida. |
| `salida/informes_por_caso/` | Un informe por caso: es el que el visor muestra y el que se firma. |

## Decisiones de diseño que conviene conocer antes de tocar el código

1. **El grafo es una proyección reconstruible, no el registro oficial.** Se
   puede borrar `salida/` y volver a generarlo desde los reportes. Por eso las
   decisiones humanas viven aparte, en `estado/`.

2. **El identificador de arista es determinista** — se calcula sobre extremos,
   relación, método, locator y fuente. Eso permite que una validación registrada
   hoy siga aplicando sobre el grafo reconstruido mañana.

3. **Sin procedencia no hay arista.** Si falta fuente, locator o explicación, se
   registra un incumplimiento en lugar de crear el vínculo.

4. **Las personas no se fusionan solas.** Cada reporte aporta su propia
   `PERSONA_MENCION`. Dos menciones se relacionan con `POSIBLE_MISMA_IDENTIDAD`,
   que es una hipótesis pendiente. La unificación existe, pero la aprueba una
   persona (`validar.py unificar`) y no borra las menciones: agrega una capa de
   identidad por encima, reversible.

5. **El texto sensible no entra al grafo.** Transcripciones y bios quedan en un
   almacén aparte referenciado por hash. Del chat solo se leen los
   identificadores de perfil que la plataforma agrega de forma estructurada.

6. **Nada se decide automáticamente.** El sistema propone vínculos, duplicados,
   unificaciones de identidad y reaperturas. La decisión es siempre del operador.

7. **El visor no necesita nada levantado.** El informe viaja embebido y el
   grafo es un único archivo HTML. Si más adelante se usa un modelo, se le
   envía el dossier seudonimizado y la restitución ocurre localmente.

## Datos de entrada

Están en `../reportes_sinteticos/`, con su propio README. `255553607.json` es el
reporte real que estaba en la carpeta; el resto son sintéticos, cada uno
construido para ejercitar una rama distinta de la lógica.

`estado_institucional.json` simula lo que en producción vive en SIPAR o en la
base transaccional: estado del reporte, motivo de archivo, operador. El grafo lo
lee, no lo posee.

## Fuera del alcance de esta etapa

La clasificación jurisdiccional y la derivación territorial se sacaron del
circuito por decisión del proyecto. `src/jurisdiccion.py` quedó en el
repositorio sin conectar, para cuando se retome la Etapa 2.
