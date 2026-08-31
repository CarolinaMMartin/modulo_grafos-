# Tecnologías y algoritmos

Inventario de todo lo que efectivamente corre en este módulo. Para cada
elemento: qué es, cómo funciona y qué papel cumple acá.

Al final hay una lista de lo que la arquitectura preliminar del proyecto propone
pero **todavía no se usa**, con el motivo.

---

> Este documento explica **qué tecnología se usa para cada cosa y por qué
> esa y no otra**. Los valores concretos —cada peso, cada umbral, cada
> parámetro de cada algoritmo— están en
> [`DOCUMENTACION_TECNICA.md`](DOCUMENTACION_TECNICA.md), que se genera
> desde el código en cada corrida y por eso no puede desactualizarse.

## 1. Base de ejecución

### Python 3.11

Todo el procesamiento. Se eligió por ser el lenguaje de la arquitectura
preliminar del proyecto y por la disponibilidad de librerías de grafos y de
machine learning para las etapas siguientes.

No hay servidor, no hay base de datos, no hay contenedor. El módulo es un
conjunto de scripts que leen archivos y escriben archivos. Es deliberado: en
esta etapa lo que hay que validar es la lógica, no el despliegue.

### Biblioteca estándar

| Módulo | Para qué se usa acá |
|---|---|
| `json` | Lectura de los reportes de NCMEC y escritura de todas las salidas estructuradas. |
| `hashlib` | SHA-256 para el hash de las fuentes y para el encadenado del libro de validaciones. SHA-1 truncado para los identificadores de arista (ver la pregunta abierta más abajo). |
| `ipaddress` | Validación de direcciones IP y detección de rangos privados y CGNAT. |
| `re` | Normalización de teléfonos y alias; extracción de los identificadores de perfil de las transcripciones. |
| `unicodedata` | Descomposición NFD para quitar diacríticos al normalizar nombres visibles. |
| `datetime` | Manejo de fechas con zona horaria explícita. Todo se normaliza a UTC. |
| `math` | Decaimiento logarítmico de la discriminancia y fórmula de Haversine. |
| `collections` | `defaultdict` y `OrderedDict` para los índices invertidos y el dossier. |
| `itertools` | Generación de pares candidatos. |
| `urllib` | Única salida de red del proyecto, y solo si se usa `informe_ia.py` contra un modelo local. |
| `argparse` | Interfaz de línea de comandos de los tres ejecutables. |

### networkx 3.5

Única dependencia externa. Es una librería de grafos en Python puro, sin
compilación ni servicios.

Se usa como **estructura de datos en memoria** y como **caja de herramientas de
algoritmos clásicos**. No es la base de grafos definitiva: es lo que permite
validar la ontología y las reglas antes de decidir si hace falta una base
distribuida.

---

## 2. Estructura del grafo

### MultiDiGraph

Grafo dirigido que admite **varias aristas distintas entre el mismo par de
nodos**. No es un detalle: dos reportes pueden afirmar lo mismo, y cada
afirmación es una pieza de evidencia separada, con su propia fuente y su propio
locator. Un grafo simple las colapsaría en una y se perdería evidencia.

El identificador de cada arista se calcula sobre `(origen, destino, relación,
método, locator, fuente)`. Al incluir la fuente, dos reportes que dicen lo mismo
producen dos aristas. Al ser determinista, reconstruir el grafo produce los
mismos identificadores, y las validaciones humanas registradas antes siguen
aplicando.

### Pregunta abierta: el identificador de arista

Hoy el identificador de cada arista es un SHA-1 truncado calculado sobre
`(origen, destino, relación, método, locator, fuente)`. Es un identificador
**propio de este módulo**, elegido porque cumple lo único que el diseño exige:
ser determinista, para que reconstruir el grafo devuelva los mismos
identificadores y las validaciones humanas registradas antes sigan aplicando.

Queda pendiente definir si debería usar el esquema de identificadores del resto
del sistema —el de la Bóveda, SIPAR o el contenedor `.qaif`— en lugar de uno
propio. Para decidirlo hace falta saber:

- qué esquema usa hoy cada sistema y si es estable en el tiempo;
- si ese identificador puede calcularse localmente o requiere pedirlo a un
  servicio, porque el grafo se reconstruye entero en cada corrida y no puede
  depender de un servicio externo para volver a producir los mismos ids;
- si hay un requisito de trazabilidad que obligue a que el mismo objeto tenga
  el mismo identificador en todos los sistemas.

Mientras no esté resuelto conviene no acoplarse: el identificador actual está
aislado en una sola función (`nucleo.Grafo._id_arista`) y cambiarlo es un
reemplazo local, siempre que el nuevo esquema también sea determinista. Lo que
**no** puede cambiarse sin costo es esa propiedad: un identificador aleatorio o
asignado por un servicio rompería la re-aplicación de las decisiones humanas.

Está anotado también en las preguntas abiertas de `CLAUDE.md` §19.

### Modelo de procedencia

Cada arista lleva obligatoriamente: fuente, ubicación exacta dentro de esa
fuente, método y versión, versión de ontología, confianza, momento del hecho,
momento del cálculo, estado de validación y explicación en prosa. Si falta
alguno de los campos esenciales, la arista no se crea y se registra un
incumplimiento.

---

## 3. Normalización de identificadores

Primer nivel de la resolución de entidades: llevar cada dato a una forma
canónica para que dos escrituras distintas del mismo valor coincidan.

| Técnica | Qué hace | Por qué importa acá |
|---|---|---|
| **E.164** | Normaliza teléfonos al formato internacional. Para Argentina: quita el `0` de larga distancia, el `9` de móvil y el `15`. | `011 15 6888 9999` y `+54 9 11 6888-9999` son el mismo número. Sin esto, dos reportes del mismo abonado no se vinculan. Es el caso que ejercita el par 900000102 / 900000103. |
| **Canonicalización de correo** | Minúsculas; en Gmail, además, ignora puntos y sufijos `+etiqueta`. | Solo se aplica en dominios donde esa equivalencia está documentada. Aplicarla en cualquier dominio produciría falsos positivos. |
| **RFC 6598 (CGNAT)** | Detecta si una IP cae en `100.64.0.0/10`. | Una IP bajo CGNAT la comparten miles de abonados. Sin el puerto de origen, el prestador no puede identificar a ninguno. La regla se degrada automáticamente. |
| **Normalización Unicode NFD** | Descompone caracteres acentuados y descarta las marcas diacríticas. | `Martín` y `Martin` son el mismo alias escrito distinto. |
| **ISO 8601 con zona horaria** | Toda fecha se lleva a UTC; si llega sin zona, se marca como supuesto. | NCMEC informa en UTC y los prestadores argentinos responden en hora local. Tres horas de corrimiento alcanzan para atribuir una conexión al abonado equivocado. |

---

## 4. Vinculación entre reportes

### Blocking por índice invertido

Comparar todos los reportes contra todos es `O(n²)`: con cien mil reportes son
cinco mil millones de comparaciones. El *blocking* construye un índice
`identificador → reportes que lo contienen` y solo compara pares que ya
comparten algo.

Acá el índice se arma sin recorrer el grafo, porque la procedencia de cada
arista ya dice a qué reporte pertenece. El costo pasa a ser proporcional a la
cantidad de coincidencias reales, no al cuadrado del corpus.

Los identificadores que aparecen en demasiados reportes se tratan como *hub*: no
generan pares y se informan aparte para revisión manual. Un descarte silencioso
se leería como "no había nada".

### Ponderación por discriminancia

Emparentada con el `IDF` de recuperación de información: cuanto más raro es un
término, más informa.

Acá el peso de una coincidencia decae logarítmicamente según en cuántos reportes
aparece ese identificador. Hasta cierto umbral conserva su peso completo; por
encima decae; y a partir de otro umbral deja de poder sostener un vínculo por sí
solo.

**Es a propósito que no se mide como fracción del corpus.** Un dispositivo
presente en 4 de 10 reportes de prueba sería el 40 % y quedaría degradado, pero
ese mismo dispositivo en 100.000 reportes es altamente discriminante. La rareza
de un identificador es una propiedad suya, no del tamaño de la base.

### Combinación noisy-OR

Cuando varias reglas coinciden sobre el mismo par de reportes, hay que combinar
sus pesos. La noisy-OR asume que cada evidencia es una oportunidad independiente
de que la hipótesis sea cierta:

```
confianza = 1 - Π (1 - peso_i)
```

Suma evidencia sin superar nunca 1, y no premia la repetición del mismo tipo de
señal tanto como la aparición de señales distintas.

**Restricción propia del proyecto:** la combinación solo se acumula si al menos
una regla sostiene el vínculo por sí sola. Alias, zona estimada e IP fuera de su
ventana temporal únicamente refuerzan. Es la traducción de la regla del
relevamiento: una relación debe apoyarse en datos objetivos coincidentes, no en
semejanza de contexto.

### Ventana temporal de IP

Una dirección IP no identifica a nadie por sí sola: identifica a quien la tenía
asignada en un momento dado. Dos capturas de la misma IP separadas por más de la
ventana de reasignación del prestador probablemente correspondan a abonados
distintos.

La ventana se declara por prestador, con un valor por defecto, y el supuesto
viaja escrito en la explicación de cada arista. Son valores estimados: hay que
confirmarlos con cada prestador.

---

## 5. Resolución e identidades

### Modelo mención / identidad

Cada reporte aporta su propia mención de persona. Las menciones **no se
fusionan** por cálculo. Cuando dos comparten una cuenta, el sistema propone una
hipótesis `POSIBLE_MISMA_IDENTIDAD` y espera.

El motivo es concreto: una cuenta puede estar compartida, vendida o
comprometida. Fusionar por esa señal propaga un error de atribución sin dejar
rastro.

### Union-Find (conjuntos disjuntos)

Estructura que mantiene grupos y responde rápido si dos elementos están en el
mismo grupo. Con compresión de caminos, cada operación es prácticamente
constante.

Se usa para la **clausura transitiva de las validaciones humanas**: si alguien
aprobó A=B y otro aprobó B=C, las tres menciones quedan bajo la misma identidad.
Se recalcula entero en cada construcción, así que revertir una validación
deshace la identidad sin dejar estado sucio.

### BFS de camino mínimo

Recorrido en anchura sobre el subgrafo de un reporte, para encontrar la cadena
que va del reporte hasta el dato compartido.

Es lo que responde **"cómo llegaron ahí"**. El reporte no toca la cuenta
directamente: la toca a través del chat. Sin ese tramo intermedio, la
vinculación aparece como un salto sin explicación.

---

## 6. Contra-evidencia

### Fórmula de Haversine

Distancia entre dos puntos sobre una esfera a partir de latitud y longitud.

Se combina con la diferencia de tiempo entre dos observaciones de la misma
cuenta o dispositivo. Si la velocidad implícita supera un umbral, el
desplazamiento es materialmente implausible y se registra una relación
`CONTRADICE`.

No invalida nada por sí sola: puede ser una VPN, una cuenta compartida o un
error de geolocalización. Importa porque **debilita** la atribución, y un grafo
que solo acumula coincidencias tiende a confirmar la hipótesis inicial.

---

## 7. Algoritmos clásicos de grafos

Todos explicables, todos previos a cualquier modelo. Corresponden a la fase G3
de la hoja de ruta.

| Algoritmo | Qué calcula | Para qué se usa acá |
|---|---|---|
| **Componentes conexas** | Grupos de nodos alcanzables entre sí. | Definen el **caso**: un reporte y todos aquellos con los que quedó vinculado. Es la unidad de trabajo del operador. |
| **Louvain** | Detección de comunidades por optimización de modularidad, en tiempo casi lineal. | Subgrupos dentro de un conjunto de reportes vinculados. Con pocos reportes coincide con las componentes conexas; recién aporta con densidad suficiente. |
| **Centralidad de grado** | Cantidad de conexiones de un nodo. | Qué entidades concentran relaciones. |
| **Centralidad de intermediación** | Con qué frecuencia un nodo está en el camino más corto entre otros dos. | Qué entidad actúa de puente entre grupos que de otro modo estarían separados. |
| **PageRank** | Importancia por caminata aleatoria: un nodo importa si lo señalan nodos importantes. | Ordenamiento estructural alternativo, menos sensible a nodos con muchas conexiones triviales. |
| **Detección de puentes** | Aristas cuya eliminación desconecta el grafo. | Vinculaciones de las que depende toda la conexión de un grupo. Si una de esas se rechaza, el caso se parte. |
| **Adamic-Adar** | Predicción de enlaces: suma `1/log(grado)` sobre los vecinos comunes. Los vecinos poco conectados pesan más. | **Baseline** contra el cual comparar una GNN más adelante. Produce una lista de pares a revisar; no escribe aristas. |

**Advertencia que acompaña toda salida de este módulo:** una centralidad alta no
indica peligrosidad, responsabilidad ni jerarquía. Describe una posición
estructural en el grafo disponible, que está sesgado por lo que cada plataforma
informa.

---

## 8. Visualización

### Disposición en árbol

El lienzo **no** usa un grafo de fuerzas. Un layout físico acomoda los nodos
donde el equilibrio los deja: produce dibujos distintos en cada corrida y sin
jerarquía visible. Para lo que el operador necesita -ver si un reporte tiene
vinculaciones y por qué- sirve un árbol de arriba hacia abajo, calculado de
forma determinista:

- fila 0: el reporte en análisis, centrado;
- fila 1: los reportes con los que se vincula, distribuidos;
- fila 2: los datos de los reportes que el operador abrió.

Los conectores son **ortogonales**: bajan del origen, corren horizontal y entran
al destino por arriba. Es la convención de los diagramas de flujo y se lee sin
esfuerzo. Cada conector lleva escrito el motivo de la vinculación y su peso.

Cuando un dato aparece además en otro de los reportes de la fila, se traza una
línea de color desde el dato hasta ese reporte, por un carril horizontal propio
para que no se superpongan. Es lo que hace visible, de un vistazo, qué dato
sostiene qué vinculación.

### Etiquetas de vínculo

Cada arista lleva escrito qué relación representa, en castellano: *opera con la
cuenta*, *fue observada desde la IP*, *coincide con · 0,99*. Una línea entre dos
nodos sin etiqueta no comunica nada.

Por encima de cierta cantidad de aristas a la vista, las etiquetas se ocultan y
queda solo el peso de las vinculaciones entre reportes, para que no se pisen.

### SVG y JavaScript sin librerías

El visor es un único archivo HTML autocontenido. No carga nada de internet: ni
fuentes, ni scripts, ni hojas de estilo. Es un requisito del proyecto, que
contempla operar en una red aislada.

---

## 9. Auditoría y trazabilidad

### Libro append-only encadenado por hash

Cada decisión humana se escribe como una línea de JSON que incluye el hash del
registro anterior. Modificar o borrar un registro pasado rompe la cadena y se
detecta.

**Alcance real, que conviene no exagerar:** detecta modificación de registros
previos. No impide que alguien con acceso de escritura reescriba el archivo
entero, ni sella el tiempo. Para eso hace falta almacenamiento append-only del
lado del servidor o anclaje externo, que todavía no está definido.

### Separación entre proyección y decisión

El grafo es una proyección reconstruible: se puede borrar y regenerar desde los
reportes. Las decisiones humanas viven aparte y se re-aplican sobre el grafo
reconstruido, apoyándose en que los identificadores de arista son deterministas.

### Seudonimización reversible

Sustitución de identificadores por etiquetas estables (`IP-1`, `CUENTA-2`),
reemplazando primero las cadenas más largas para que una subcadena no rompa un
valor que la contiene. El mapa inverso no sale del entorno.

Se usa antes de enviar el dossier a un modelo de lenguaje, y también para
publicar el dataset sin el texto libre del reporte real.

---

## 10. Formatos de salida

| Formato | Para qué |
|---|---|
| **JSON** | Grafo completo con procedencia, resultado de todos los módulos, dossier de vinculaciones. |
| **GraphML** | Estándar XML para grafos. Permite abrir el resultado en Gephi, yEd o Cytoscape sin depender de este código. |
| **JSONL** | Libro de validaciones. Un registro por línea, apto para agregar sin reescribir el archivo. |
| **Markdown** | Informes y documentación. El modelo de datos se genera desde la ontología para que no se desincronice. |
| **HTML + SVG** | Visor autocontenido. |

---

## 11. Lo que todavía no se usa

La arquitectura preliminar del proyecto propone estas piezas. Ninguna está
integrada, y conviene no presentarlas como disponibles.

| Tecnología | Qué aportaría | Por qué todavía no |
|---|---|---|
| **JanusGraph** | Base de grafos distribuida para recorridos sobre volúmenes grandes. | No hay medición de volumen real. Adoptarla ahora sería infraestructura sin requisito que la justifique. La escalabilidad no se evalúa solo por cantidad de nodos: también por aristas, profundidad de recorrido, latencia, permisos y capacidad operativa del equipo. |
| **Apache Cassandra** | Persistencia horizontal para JanusGraph. | Depende de la decisión anterior. |
| **Apache Solr** | Índice de búsqueda mixta sobre el grafo. | Depende de la decisión anterior. |
| **TinkerPop / Gremlin** | Lenguaje de recorridos sobre grafos de propiedad. | Solo tiene sentido con una base de grafos detrás. |
| **Apache Spark / GraphX** | Cálculo distribuido sobre grafos grandes. | Los algoritmos clásicos corren en segundos sobre el volumen actual. |
| **PyTorch Geometric / DGL** | Entrenamiento de redes neuronales sobre grafos. | Falta lo que la hoja de ruta exige antes: ontología estable, identidades resueltas, criterios de evaluación y un conjunto de vínculos validados por especialistas. El baseline determinista contra el cual comparar ya existe; el modelo no. |
| **pgvector** | Búsqueda semántica por embeddings. | Requiere la capa de extracción de texto e imagen, que no está. |
| **PostgreSQL** | Registro oficial de casos, estados y validaciones. | Hoy el estado institucional se simula con un archivo lateral. Es la primera pieza a integrar cuando el módulo salga del banco de pruebas. |
| **Cytoscape.js** | Visualización de grafos para producción, con dibujo por capas y ruteo de aristas. | El árbol calculado a mano alcanza para un caso. Corresponde revisarlo si aparecen casos con decenas de reportes vinculados. |
| **FFmpeg, Whisper, Qwen** | Procesamiento multimodal de audio y video. | Es la línea del analizador de video, todavía sin integrar con el grafo. |
| **Docker** | Despliegue reproducible. | El módulo no tiene servicios que orquestar. Corresponde cuando haya API. |

---

## 12. Resumen

Lo que efectivamente corre hoy son **reglas deterministas y algoritmos clásicos
de grafos**, sin ningún modelo estadístico en el camino crítico. Es una decisión
de diseño, no una limitación temporal: cada vinculación que el sistema propone
tiene que poder explicarse paso a paso ante quien la va a usar en una actuación.

El único punto donde puede intervenir un modelo de lenguaje es la redacción del
informe, y está aislado: recibe un dossier ya calculado, no participa de la
decisión de vincular, y el informe se genera igual si el modelo no está.
