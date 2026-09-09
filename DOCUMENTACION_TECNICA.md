<!-- Generado por grafo/src/docs_tecnicos.py en cada corrida.
     No editar a mano: los numeros se leen del codigo. -->

# Documentación técnica — módulo de grafos, Bóveda CIJ

Referencia completa de las tecnologías que se usan, de cómo está configurado cada algoritmo y de cada peso, umbral y constante que interviene en una decisión del sistema.

**Este archivo se genera solo, en cada construcción, leyendo los valores de los módulos que los definen.** No es una transcripción: si mañana alguien cambia un peso en `src/ontologia.py`, este documento cambia con él. Por eso no se edita a mano.

Complementa a los otros tres, sin repetirlos:

- `TRASPASO.md` — por qué cada cosa es como es, y qué se descartó.
- `grafo/ESTADO.md` — qué está implementado, simplificado o ausente.
- `grafo/MODELO_DATOS.md` — la ontología: tipos de nodo y vocabulario.

Versión de ontología documentada: **0.3.0**.

---

## 1. Base de ejecución

Todo corre local, sin servicios de red y sin llamadas a terceros. Es un requisito del proyecto, no una preferencia: la evidencia sensible no sale del entorno.

| Componente | Versión verificada | Para qué |
|---|---|---|
| Python | 3.11.1 | todo el procesamiento; mínimo requerido 3.8 |
| networkx | 3.5 | estructura del grafo y algoritmos clásicos |
| Biblioteca estándar | — | servidor HTTP, hashes, JSON, fechas, expresiones regulares |

Corrida de verificación: `3.11.1` sobre `Windows-10-10.0.26200-SP0`.

**Una sola dependencia externa, y es deliberado.** El servidor, el visor, los informes, la seudonimización y los libros de decisiones usan únicamente la biblioteca estándar. Agregar infraestructura pesada antes de justificarla con requisitos medidos está expresamente desaconsejado en el contexto del proyecto.

## 2. Módulos y sus versiones

Cada módulo que produce relaciones declara un método y una versión, y ambos quedan grabados en **cada arista que crea**. Es lo que permite, meses después, saber con qué versión de qué regla se produjo un vínculo determinado.

| Módulo | Método que graba | Versión | Responsabilidad |
|---|---|---|---|
| `src/resolucion.py` | `resolucion_determinista` | 1.2 | vinculación entre reportes, identidades, contra-evidencia |
| `src/analisis.py` | `analisis_clasico` | 1.1 | legajos, comunidades, centralidades, baseline de enlaces |
| `src/alertas.py` | `alertas_reapertura` | 2.0 | alertas de reapertura tipadas por motivo de archivo |
| `src/normalizacion.py` | — | 1.0 | teléfonos, correos, IP, alias, marcas temporales |
| `src/validacion.py` | `vinculacion_manual` | 1.0 | libros de decisiones humanas y vinculación manual |
| `src/ontologia.py` | — | 0.3.0 | tipos, vocabulario, reglas, pesos y umbrales |

Los módulos sin versión propia no crean aristas: transforman valores (`normalizacion`) o declaran vocabulario (`ontologia`), y su versión viaja igual en cada arista como `ontologia_version`.

## 3. Clases de relación

Toda arista pertenece a **una** de estas clases y nunca se mezclan, ni en la base ni en la pantalla. Es la separación epistemológica que ordena todo el sistema.

| Clase | Qué significa | Estado inicial | ¿Lleva peso? |
|---|---|---|---|
| `observada` | El dato figura textualmente en un campo del reporte de origen. No fue calculado ni supuesto por el sistema. | `validada` | no |
| `derivada` | Resulta de aplicar una regla determinista y reproducible sobre datos que constan en la fuente. Puede volver a calcularse y debe ser revisada por una persona. | `pendiente` | sí, obligatorio |
| `inferida` | Es una hipótesis producida por similitud o por un modelo. No acredita nada por sí sola y requiere validación humana. | `pendiente` | sí, obligatorio |
| `afirmada` | La estableció una persona por su propio criterio, no el sistema. No surge de la fuente ni de una regla: queda registrada con quién la dispuso, cuándo y con qué fundamento, y puede revertirse. | `validada` | no |

Dos consecuencias que conviene tener presentes:

- Una **observada** no lleva peso porque no hay nada que ponderar: consta textualmente en un campo de la fuente. Nace validada, pero puede impugnarse.
- Una **afirmada** tampoco lleva peso, y por el motivo contrario: no hay cálculo alguno detrás. La dispuso una persona. Ponerle un número sería inventar una precisión que nadie calculó.

> La clase `afirmada` **no está en el documento rector** (`contexto.md` §10.1, que enumera tres). Se agregó porque una vinculación que dispone una persona no entra en ninguna de las tres sin desdibujarlas. Está fundada en `TRASPASO.md` §4.13 y **pendiente de validar con los especialistas**. No presentarla como ontología aprobada.

### Estados de validación

`pendiente`, `en_revision`, `validada`, `rechazada`

Una arista rechazada **no se borra**: se marca `vigente = false` y queda con su historial. La historia de la decisión se conserva.

## 4. Reglas de vinculación y sus pesos

Estas son las nueve reglas que pueden vincular dos reportes. Todas son deterministas: mismos datos, mismo resultado, siempre.

Cada regla declara cuatro cosas.

- **Peso base** — cuánto aporta si el identificador es plenamente discriminante. Nunca es 1: ninguna coincidencia sola acredita nada.
- **¿Sostiene?** — si puede fundar el vínculo por sí sola, o si únicamente refuerza uno que ya se apoya en un dato objetivo.
- **¿Pondera por rareza?** — si su peso decae cuando el identificador aparece en muchos reportes.
- **Versión** — graba en cada arista que produce.

| Regla | Tipo de dato | Peso base | ¿Sostiene? | ¿Pondera por rareza? | Ver. |
|---|---|---|---|---|---|
| `R01_CUENTA` | `CUENTA` | 0,98 | sí | no | 1.0 |
| `R02_DISPOSITIVO` | `DISPOSITIVO` | 0,92 | sí | sí | 1.0 |
| `R03_TELEFONO` | `TELEFONO` | 0,90 | sí | sí | 1.0 |
| `R04_EMAIL` | `EMAIL` | 0,90 | sí | sí | 1.0 |
| `R05_EVIDENCIA` | `EVIDENCIA` | 0,88 | sí | sí | 1.0 |
| `R06_IP_VENTANA` | `IP` | 0,72 | sí | sí | 1.0 |
| `R07_IP_SUELTA` | `IP` | 0,28 | **no, solo refuerza** | sí | 1.0 |
| `R08_ALIAS` | `ALIAS` | 0,22 | **no, solo refuerza** | sí | 1.0 |
| `R09_UBICACION` | `UBICACION` | 0,08 | **no, solo refuerza** | sí | 1.0 |
| `R10_ALIAS_PAGO` | `ALIAS_PAGO` | 0,62 | sí | sí | 1.0 |

### Qué detecta cada una

- **`R01_CUENTA`** — Misma cuenta: mismo ESP y mismo espUserId.
- **`R02_DISPOSITIVO`** — Mismo identificador de dispositivo.
- **`R03_TELEFONO`** — Mismo telefono normalizado a E.164.
- **`R04_EMAIL`** — Mismo correo normalizado.
- **`R05_EVIDENCIA`** — Mismo hash de archivo.
- **`R06_IP_VENTANA`** — Misma IP dentro de la ventana temporal del prestador. La IP se valora siempre junto con su fecha y hora.
- **`R07_IP_SUELTA`** — Misma IP fuera de la ventana temporal: indicio, no atribucion.
- **`R08_ALIAS`** — Mismo nombre visible: refuerza, nunca sostiene solo.
- **`R09_UBICACION`** — Misma ciudad estimada: contexto, nunca sostiene solo.
- **`R10_ALIAS_PAGO`** — Misma via de cobro: mismo alias de pago normalizado.

### Por qué esos pesos y no otros

El orden no es arbitrario: sigue **cuánto individualiza cada dato**.

La cuenta de plataforma encabeza con **0,98** porque el par `ESP + espUserId` identifica a un titular concreto dentro de una plataforma. El dispositivo la sigue con **0,92**: individualiza casi tan bien, pero un aparato puede prestarse o venderse. Teléfono y correo comparten **0,90**. El hash de archivo baja a **0,88** porque prueba que dos reportes traen el mismo contenido, no que provengan de la misma persona: un material que circula lo comparten muchos.

Debajo del umbral quedan las **3 reglas que solo refuerzan** (`R07_IP_SUELTA`, `R08_ALIAS`, `R09_UBICACION`). Su peso —entre 0,08 y 0,28— está deliberadamente por debajo del umbral de propuesta: aunque dispararan todas juntas, no alcanzan para crear un vínculo. Es la traducción de la regla del relevamiento: *una relación debe apoyarse en datos objetivos coincidentes, no en semejanza contextual*.

Ninguna regla que sostiene baja de **0,62** ni llega a **0,99**.

## 5. Cómo se combinan los pesos

Cuando dos reportes comparten varios datos, cada regla que dispara aporta su peso y se combinan con **noisy-OR**:

```
confianza = 1 - Π (1 - peso_efectivo_i)
```

La lectura es directa: cada coincidencia es una razón independiente para creer que los reportes están relacionados, y la confianza es la probabilidad de que **al menos una** sea válida. Nunca baja al sumar evidencia y nunca supera 1.

**La condición que lo gobierna todo:** el producto solo se acumula si *al menos una* regla que sostiene disparó. Si únicamente dispararon reglas corroborantes, el resultado es `0.0` y el par se descarta, por muchas que sean.

### Umbrales

| Constante | Valor | Qué decide |
|---|---|---|
| `UMBRAL_PROPONER` | 0,55 | por debajo, el vínculo no se propone y queda como descartado con su motivo |
| `UMBRAL_CLUSTER` | 0,70 | peso mínimo para que un vínculo agrupe dos reportes en un mismo legajo |
| `UMBRAL_PROBABLE` | 0,70 | desde acá la confianza se informa como «media» |
| `UMBRAL_ALTA` | 0,90 | desde acá se informa como «alta» |
| `CONFIANZA_MAXIMA` | 0,99 | techo absoluto: ninguna arista puede llegar a 1 |

El techo de 0,99 no es cosmético. Un 1,00 en pantalla se lee como certeza, y el sistema no produce certezas: produce propuestas que una persona tiene que revisar.

### Ejemplo trabajado, calculado sobre esta corrida

Reportes **255553607** y **900000101**. Dispararon 5 reglas:

| Regla | Valor coincidente | Peso base | × rareza | = peso efectivo | Rol |
|---|---|---|---|---|---|
| `R01_CUENTA` | grindr/888658825 | 0,98 | 1,0000 | 0,9800 | **sostiene** |
| `R02_DISPOSITIVO` | b534375433e0e502 | 0,92 | 1,0000 | 0,9200 | **sostiene** |
| `R07_IP_SUELTA` | 181.46.66.242 | 0,28 | 1,0000 | 0,2800 | refuerza |
| `R08_ALIAS` | lechero | 0,22 | 1,0000 | 0,2200 | refuerza |
| `R09_UBICACION` | Monte Grande, B, AR | 0,08 | 1,0000 | 0,0800 | refuerza |

Como al menos una regla sostiene, se acumula:

```
confianza = 1 - (1 - 0,9800) × (1 - 0,9200) × (1 - 0,2800) × (1 - 0,2200) × (1 - 0,0800)
          = 1 - 0,0008
          = 0,9900
```

Confianza registrada en la arista: **0,9900** — franja «alta», por el techo de 0,99.

## 6. Ponderación por rareza (discriminancia)

Un identificador que aparece en muchos reportes individualiza menos. El peso base de cada regla se multiplica por un factor que decae con `df` — la cantidad de reportes distintos en que aparece ese identificador.

```
si df <= 10           factor = 1,00
si df >  10           factor = log(1 + 10) / log(1 + df),  acotado a [0,15 ; 1,00]
```

Curva efectiva, calculada al generar este documento:

| df (reportes en que aparece) | Factor | Peso conservado |
|---|---|---|
| 1 | 1,0000 | 100,0 % |
| 5 | 1,0000 | 100,0 % |
| 10 | 1,0000 | 100,0 % |
| 15 | 0,8649 | 86,5 % |
| 25 | 0,7360 | 73,6 % |
| 50 | 0,6099 | 61,0 % |
| 100 | 0,5196 | 52,0 % |
| 500 | 0,3857 | 38,6 % |
| 5000 | 0,2815 | 28,2 % |

### Cuándo un identificador deja de sostener

Además del decaimiento, hay un corte duro: pasado cierto punto el identificador se degrada a *solo refuerza*, sin importar qué regla sea.

| Constante | Valor | Efecto |
|---|---|---|
| `DF_PLENA_DISCRIMINANCIA` | 10 | hasta acá el identificador conserva todo su peso |
| `DF_HUB_ABSOLUTO` | 50 | desde acá deja de sostener por sí solo, con cualquier corpus |
| `DF_HUB_SIN_PARES` | 100 | desde acá no genera pares para comparar y se informa aparte como *hub* |
| `CORPUS_MINIMO_PARA_FRACCION` | 200 | recién con este volumen se aplica también el criterio de fracción |
| `FRACCION_BAJA_DISCRIMINANCIA` | 0,20 | con corpus grande, aparecer en más de esta fracción degrada |

Hay un segundo descuento, independiente del anterior. Cuando el identificador que comparten los dos reportes no está declarado en ningún campo sino escrito en un texto libre —la conversación, la biografía del perfil—, el peso se multiplica por `FACTOR_TEXTO_LIBRE` = 0,85. No es que la extracción falle: es que cambia lo que el dato significa. Que el prestador informe un teléfono es un dato de la cuenta; que alguien lo escriba en un chat es una afirmación de esa persona, que puede estar equivocada, ser de un tercero o ser mentira.

> **La rareza es una propiedad del identificador, no del tamaño de la base.** El primer diseño medía la fracción del corpus, y con diez reportes un dispositivo compartido por cuatro daba 40 % y quedaba degradado, perdiendo un vínculo legítimo. Ese mismo dispositivo en cien mil reportes es altamente discriminante. Por eso el umbral principal es **absoluto** sobre `df`, y la fracción solo entra a partir de 200 reportes. Hay invariantes que verifican que `discriminancia(4)` da lo mismo con 10 y con 100.000 reportes.

La regla `R01_CUENTA` es la única exceptuada del corte por *hub*: si un `espUserId` se repite en decenas de reportes, el problema es de los datos y conviene verlo, no ocultarlo.

## 7. Política de dirección IP

Una IP aislada no identifica a nadie. Solo vale junto con fecha, hora, prestador y —cuando hay NAT— puerto de origen.

### Ventana temporal por prestador

Dos capturas de la misma IP corresponden probablemente al mismo abonado solo si están dentro de la ventana de reasignación del prestador. Fuera de ella, la regla degrada de `R06_IP_VENTANA` (0,72, sostiene) a `R07_IP_SUELTA` (0,28, solo refuerza).

| Prestador | Ventana asumida |
|---|---|
| *(cualquier otro)* | 24 h |
| claro | 12 h |
| movistar | 12 h |
| personal | 12 h |
| telecentro | 24 h |
| telecom argentina | 24 h |
| telefonica de argentina | 24 h |

> **Estos valores son estimados y no están verificados con los prestadores.** El supuesto viaja escrito en la explicación de cada arista que produce, de modo que quien lee el informe sabe sobre qué base se afirmó. Confirmarlos es una tarea pendiente.

### CGNAT

Bajo *Carrier-Grade NAT* (`100.64.0.0/10`, RFC 6598) muchos abonados comparten una misma IP pública, y sin el puerto de origen el prestador no puede decir cuál.

| Situación | Factor sobre el peso | Efecto |
|---|---|---|
| IP normal, dentro de ventana | 1,00 | `R06_IP_VENTANA` con su peso pleno, **sostiene** |
| CGNAT **con** puerto en ambas capturas | × 0,85 | sigue sosteniendo: el prestador puede identificar al abonado |
| CGNAT **sin** puerto | × 0,35 | **se degrada a solo refuerza**: no permite atribuir a nadie |
| Fuera de ventana | — | pasa a `R07_IP_SUELTA`, que nunca sostiene |
| Sin fecha ni hora en alguna captura | — | pasa a `R07_IP_SUELTA` |

El reporte real del dataset trae `port: 19096`, un campo que suele ignorarse y que acá cambia el resultado.

### Zona horaria

NCMEC informa en UTC; los prestadores argentinos responden en hora local. Tres horas de corrimiento alcanzan para atribuir una conexión al abonado equivocado. Toda fecha sin zona horaria explícita se marca como supuesto en la explicación de la arista.

## 8. Normalización de identificadores

Antes de comparar, cada identificador se lleva a una forma canónica. Sin esto, `011 15 6888-9999` y `+54 9 11 6888 9999` serían dos teléfonos distintos. Versión: **1.0**.

| Tipo | Regla | Entrada | Resultado |
|---|---|---|---|
| Teléfono | E.164 argentino: se saca el `9` de móvil, se descartan longitudes inverosímiles (fuera de 8 a 11 dígitos nacionales) | `011 15 6888 9999` | `+541168889999` |
| Teléfono | misma entrada en formato internacional | `+54 9 11 6888-9999` | `+541168889999` |
| Correo | minúsculas, sin espacios, con validación de forma | `  Lechero@Example.COM ` | `lechero@example.com` |
| Alias | minúsculas y espacios colapsados; identificador **débil** | `  El  Lechero ` | `el lechero` |
| IP | validación de forma y marcado de rasgos | `181.46.66.242` | `181.46.66.242` |
| IP | CGNAT detectada | `100.66.12.45` | `100.66.12.45` |

Cada IP normalizada arrastra los rasgos que condicionan su valor probatorio. Para `100.66.12.45`: `atribuible_sin_dato_extra = False`, `cgnat = True`, `privada = False`, `version = 4`.

Cuando una normalización descarta un valor, deja una nota que explica por qué. Nada se descarta en silencio.

## 9. Hipótesis de identidad

Cada reporte aporta su propia `PERSONA_MENCION`. Dos menciones que comparten cuenta generan una relación `POSIBLE_MISMA_IDENTIDAD` con confianza fija **0,85** (`CONFIANZA_MISMA_IDENTIDAD`), clase `inferida`, estado `pendiente` — **nunca una fusión**.

Una cuenta puede estar compartida, vendida o comprometida. La unificación existe, pero **la aprueba una persona**, y entonces:

- no borra las menciones: cada reporte conserva la suya con su fuente;
- es transitiva, por conjuntos disjuntos (*union-find*): aprobar A=B y B=C agrupa las tres;
- es reversible: revertir la validación deshace la identidad sola en la próxima construcción.

## 10. Contra-evidencia

Un grafo que solo acumula coincidencias tiende a confirmar la hipótesis inicial. Por eso existen aristas que **debilitan**.

`CONTRADICE` se produce cuando la misma cuenta aparece observada desde dos IP geolocalizadas a una distancia que exige una velocidad imposible.

| Parámetro | Valor | Qué hace |
|---|---|---|
| `VELOCIDAD_IMPOSIBLE_KMH` | 900 | por encima de esta velocidad implícita se marca la contradicción |
| `DISTANCIA_MINIMA_KM` | 50 km | por debajo no se evalúa: la geolocalización por IP no tiene esa precisión |
| Distancia | Haversine | sobre las coordenadas informadas por la geolocalización |
| `CONFIANZA_CONTRADICCION` | 0,70 | es un indicio de inconsistencia, no una refutación |

**No invalida nada.** Puede ser una VPN, una cuenta compartida o una geolocalización errónea. Debilita la atribución, y por eso conviene tenerla a la vista.

## 11. Alertas de reapertura

Un archivado **no se reabre porque apareció una conexión**. Se reabre porque apareció *el dato que le faltaba*. Por eso el motivo de archivo es un campo de primera clase y cada motivo declara qué aporte lo reactiva.

| Motivo del archivo | Qué lo reactiva | Prioridad |
|---|---|---|
| `sin_datos_de_usuario` | un identificador que permite individualizar | alta |
| `no_atribuible_nat` | un identificador que permite individualizar; una dirección IP atribuible, con fecha y hora | alta |
| `sin_archivos` | un archivo identificado por su hash | alta |
| `sin_ubicacion` | un dato de ubicación utilizable; una dirección IP atribuible, con fecha y hora | media |
| `material_sin_relevancia` | su condición de actuación con mérito para avanzar; un archivo identificado por su hash | media |
| *(cualquier otro motivo)* | un identificador que permite individualizar; un archivo identificado por su hash; una dirección IP atribuible, con fecha y hora; su condición de actuación con mérito para avanzar | media |

### Las dos condiciones

Una alerta exige **ambas**, no una:

1. que el vínculo entre los dos reportes esté sostenido por una regla fuerte —no solo por reglas que refuerzan—;
2. que el reporte disparador aporte efectivamente aquello que le faltaba al archivado.

Los vínculos que no califican se registran como **silenciados**, con su motivo. No se descartan en silencio.

### Estados institucionales

| Grupo | Estados |
|---|---|
| Se consideran archivados | `archivado`, `archivado_latente`, `pendiente` |
| Se consideran activos (pueden disparar) | `derivado`, `en_analisis`, `en_investigacion`, `judicializado` |
| Tipos de dato que individualizan | `CUENTA`, `DISPOSITIVO`, `EMAIL`, `TELEFONO` |

> Toda esta lógica depende de que el motivo de archivo se registre de forma **estructurada**. Hoy se simula con `reportes_sinteticos/estado_institucional.json`. Si en SIPAR es texto libre, ese es el primer cambio a pedir.

## 12. Algoritmos clásicos de grafos

Corren sobre la **proyección reporte–reporte**: un grafo no dirigido donde cada nodo es un reporte y cada arista un vínculo que superó `UMBRAL_CLUSTER` (0,70), más las vinculaciones manuales, que entran sin umbral.

| Qué | Algoritmo | Configuración | Para qué sirve |
|---|---|---|---|
| Legajos | componentes conexas | — | qué reportes conviene mirar juntos |
| Comunidades | Louvain | `weight="peso"`, `seed=7` | subgrupos dentro de un legajo grande; con pocos reportes coincide con las componentes |
| Centralidad de grado | `degree_centrality` | top 10 | con cuántos se conecta cada reporte |
| Intermediación | `betweenness_centrality` | top 10, solo si el grafo tiene ≤ 3.000 nodos | qué reporte actúa de puente entre grupos |
| PageRank | `pagerank` | top 10, solo si ≤ 20.000 nodos | importancia estructural |
| Puentes | `nx.bridges` | top 10 | aristas cuya caída parte el legajo en dos |
| Enlaces probables | Adamic–Adar | top 15, **no materializa aristas** | baseline determinista contra el cual comparar una futura GNN |

El `seed=7` de Louvain no es decorativo: sin él dos corridas sobre los mismos datos pueden dar comunidades distintas, y un informe que cambia solo porque se volvió a ejecutar no es reproducible.

Adamic–Adar **calcula y ordena, pero no escribe nada en el grafo**. Es un ranking de pares que merecerían revisión, no un conjunto de relaciones. Materializarlo convertiría una sugerencia estadística en algo que se ve igual que un hecho.

> **Una centralidad alta no significa culpabilidad, liderazgo ni peligrosidad.** Describe una posición estructural en el grafo que se pudo construir con los datos disponibles. Un reporte puede ser central solo porque su plataforma informa más campos que las demás. La advertencia viaja en la salida del propio módulo.

## 13. Registro de las decisiones humanas

El grafo es una **proyección reconstruible**: se borra `salida/` y se regenera desde los reportes. Las decisiones de las personas no pueden vivir ahí, así que viven aparte y se re-aplican sobre el grafo reconstruido.

| Libro | Qué registra | Clave |
|---|---|---|
| `estado/validaciones.jsonl` | validar, rechazar o poner en revisión una relación existente; aprobar una unificación de identidad | `arista_id` |
| `estado/vinculos_manuales.jsonl` | vincular o desvincular dos reportes por decisión propia | el par de reportes |

Ambos son **append-only y encadenados por hash**: cada registro lleva `prev_hash` y un `hash` SHA-256 de su propio contenido.

Esto funciona porque **el identificador de arista es determinista**: se calcula con SHA-1 truncado sobre extremos, relación, método, locator y fuente, de modo que la misma evidencia con el mismo método produce el mismo `arista_id` en cada corrida. Es la propiedad que no se puede perder.

> **Alcance real de la cadena de hashes:** detecta la modificación o el borrado de registros anteriores. **No** impide que alguien con acceso de escritura reescriba el archivo entero, ni sella el tiempo. Para eso hace falta almacenamiento append-only del lado del servidor o anclaje externo, que todavía no está definido.

### Seudonimización

Antes de enviar el dossier a cualquier modelo de lenguaje, los identificadores de tipo `IP`, `CUENTA`, `TELEFONO`, `EMAIL`, `DISPOSITIVO`, `ALIAS`, `EVIDENCIA` se reemplazan por etiquetas estables (`IP-1`, `CUENTA-2`). El modelo redacta sobre las etiquetas y los valores reales se restituyen después, localmente, sobre el texto devuelto. Hay invariantes que verifican que ningún identificador real sobrevive en el dossier seudonimizado.

## 14. Formatos de salida

| Archivo | Formato | Para qué |
|---|---|---|
| `grafo.json` | JSON | grafo completo con la procedencia de cada arista |
| `grafo.graphml` | GraphML | para Gephi, yEd o Cytoscape |
| `analisis.json` | JSON | resultado estructurado de cada módulo de la corrida |
| `grafo.html` | HTML autocontenido | el visor, sin dependencias externas |
| `informes_por_caso/` | Markdown | un informe por caso, que es el que se firma |
| `informe_vinculaciones.md` | Markdown | informe general de la corrida |
| `informe.md` | Markdown | informe técnico con trazabilidad a la fuente |
| `informe_crudo.json` | JSON | dossier con el peso de cada vínculo y el aporte de cada regla |
| `informe_crudo_anonimo.json` | JSON | el mismo, seudonimizado: es lo único que ve un modelo |
| `textos_restringidos.json` | JSON | texto sensible **fuera** del grafo, indexado por hash |

Todo lo de `salida/` se regenera en cada corrida y no se versiona. Lo único que no se recalcula es `estado/`.

## 15. Límites de esta configuración

Lo que sigue no son defectos ocultos: son las condiciones bajo las cuales los números de arriba son válidos.

1. **Los pesos no están calibrados contra un conjunto validado.** Salen del criterio del relevamiento —cuánto individualiza cada dato— y no de medir aciertos y errores sobre casos reales ya trabajados. Ese conjunto todavía no existe, y sin él no se puede informar precisión ni recall.
2. **Las ventanas de IP por prestador son estimadas.** Hay que confirmarlas con cada uno.
3. **El corpus de prueba tiene diez reportes.** Los umbrales que dependen del volumen —`CORPUS_MINIMO_PARA_FRACCION` = 200, `DF_HUB_ABSOLUTO` = 50— no se ejercitan con datos reales, solo con pruebas unitarias.
4. **Todo corre en memoria con `networkx`.** No escala más allá de decenas de miles de nodos. Evaluar una base de grafos distribuida recién tiene sentido con volúmenes reales medidos.
5. **El extractor está escrito contra el JSON de NCMEC.** PDF y XML no se procesan.
6. **No hay control de acceso.** Quien corre el sistema ve todo.

---

## Cómo verificar todo esto

```bash
python grafo/construir.py   # regenera este documento y las salidas
python grafo/pruebas.py     # invariantes sobre las reglas no negociables
```

Los invariantes cubren, entre otras cosas: que ninguna arista exista sin fuente ni locator, que ninguna inferencia nazca validada, que una afirmación humana no lleve peso, que la discriminancia no dependa del tamaño del corpus, que una coincidencia de solo alias y ciudad no vincule, que el identificador de arista sea estable entre corridas y que el texto sensible no entre al grafo.
