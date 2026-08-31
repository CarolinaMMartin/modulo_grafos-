# Etapa 2 — Vinculación contextual

### Capa semántica, conjunto etiquetado y aprendizaje sobre grafos

Documento de arquitectura e ingeniería. Define qué se construye en la Etapa 2,
en qué orden, con qué tecnologías, bajo qué criterios se acepta cada pieza y
cómo se integra con el circuito de decisión que ya opera.

Versión del documento: 1.0 · Ontología de referencia: 0.3.0

---

## Índice

1. [Objeto](#1-objeto)
2. [El problema](#2-el-problema)
3. [Sustrato disponible](#3-sustrato-disponible)
4. [Arquitectura general](#4-arquitectura-general)
5. [Capa de embeddings](#5-capa-de-embeddings)
6. [Conjunto etiquetado](#6-conjunto-etiquetado)
7. [Baseline semántico](#7-baseline-semántico)
8. [Modelo de grafos](#8-modelo-de-grafos)
9. [Explicabilidad](#9-explicabilidad)
10. [Integración con el circuito de decisión](#10-integración-con-el-circuito-de-decisión)
11. [Infraestructura](#11-infraestructura)
12. [Plan por fases](#12-plan-por-fases)
13. [Riesgos y controles](#13-riesgos-y-controles)
14. [Glosario](#14-glosario)

---

## 1. Objeto

La Etapa 1 vincula reportes cuando **comparten un identificador**: una cuenta,
un dispositivo, un teléfono, un hash de archivo, una dirección IP dentro de la
ventana de reasignación de su prestador. Son reglas deterministas, auditables y
explicables en prosa, y resuelven el caso en que el dato objetivo existe y
coincide.

La Etapa 2 aborda el caso en que **no existe ese dato objetivo y la relación
igual está**: dos reportes que describen la misma forma de operar, el mismo
guion de aproximación, el mismo tipo de material, la misma franja etaria de las
víctimas, la misma secuencia de plataformas. Un operador con experiencia los
relaciona leyéndolos. El sistema, hoy, no.

Esa es la **vinculación contextual**, y este documento define cómo se construye.

El objetivo operativo es concreto y medible: **reducir el trabajo de un
operador para encontrar antecedentes relevantes**, elevando a su atención pares
de reportes que merecen revisión y que ninguna regla determinista habría
propuesto.

El objetivo **no** es reemplazar el criterio humano ni producir conclusiones
automáticas. Toda salida de esta capa entra al circuito con el mismo estatuto
que cualquier otra hipótesis: como propuesta pendiente de validación, con su
fundamento a la vista.

---

## 2. El problema

### 2.1 Formulación técnica

Dado el conjunto de reportes `R` y un reporte en análisis `r ∈ R`, producir un
ranking de los reportes `r' ∈ R \ {r}` por probabilidad de que exista una
relación sustantiva entre ambos, junto con la evidencia que sostiene esa
probabilidad.

Es un problema de **predicción de enlaces sobre un grafo heterogéneo con
atributos textuales**, con tres condiciones que lo separan del caso académico
habitual:

1. **Los negativos no están observados.** Que dos reportes no estén vinculados
   no significa que no se relacionen: significa que nadie encontró el vínculo o
   que la evidencia no alcanzó. Tratar cada par no vinculado como un ejemplo
   negativo produce un modelo que aprende a reproducir las omisiones del
   archivo.
2. **El costo de los errores es asimétrico y no es simétrico entre clases.** Un
   falso negativo cuesta un antecedente que no se revisó. Un falso positivo
   cuesta tiempo de un operador y, si se presenta mal, contamina una actuación
   con una relación que no existe.
3. **Una propuesta sin fundamento no sirve.** Un ranking sin explicación no es
   accionable: quien lo recibe no puede decidir si seguirlo, y menos aún
   incorporarlo a un expediente.

### 2.2 Qué se considera una relación sustantiva

La vinculación contextual amplía el vocabulario de relaciones. Se definen
cuatro tipos, que se etiquetan por separado porque tienen valor probatorio
distinto:

| Tipo | Definición operativa | Ejemplo |
|---|---|---|
| **Mismo autor** | Los reportes describen conductas atribuibles a la misma persona, sin identificador compartido | Mismo guion de aproximación, misma franja horaria, misma zona, mismo perfil de víctima |
| **Misma víctima** | Los reportes refieren a la misma persona menor de edad | Descripciones convergentes en dos plataformas distintas |
| **Mismo material** | Los reportes involucran contenido de origen común sin hash coincidente | Recorte, recodificación o captura de pantalla del mismo material |
| **Mismo modus operandi** | Patrón de conducta compartido sin atribución a la misma persona | Técnica de captación replicada por actores distintos |

El cuarto tipo merece atención particular: **es el más frecuente y el de menor
valor atributivo**. Que dos reportes compartan modus operandi es información
útil para el análisis criminal y no acredita relación entre las personas
involucradas. Se etiqueta y se propone, pero se presenta con esa distinción
explícita.

---

## 3. Sustrato disponible

La Etapa 2 no parte de cero. Construye sobre cinco piezas que ya existen y
funcionan.

### 3.1 El grafo

Un grafo dirigido y multirelacional con **16 tipos de nodo** y **24 tipos de
relación**, donde cada arista lleva su bloque de procedencia completo: fuente,
ubicación exacta dentro de esa fuente, método, versión del método, versión de
ontología, momento del hecho, momento del cálculo y explicación en prosa.

Es el sustrato estructural sobre el que opera la GNN. La heterogeneidad no es
un accidente: es información. Que dos reportes se conecten a través de un
dispositivo no significa lo mismo que a través de una ubicación estimada, y el
modelo tiene que poder distinguirlo.

### 3.2 La separación epistemológica

Cada relación declara cómo se obtuvo, y las clases no se mezclan:

- **observada** — consta textualmente en un campo de la fuente;
- **derivada** — resulta de una regla determinista y reproducible;
- **inferida** — hipótesis por similitud o modelo, siempre pendiente;
- **afirmada** — la estableció una persona por su propio criterio.

Toda salida de la Etapa 2 es **inferida**. Esta separación es la que permite
incorporar un modelo sin contaminar lo que consta en la evidencia, y la que
permite retirarlo sin pérdida si no rinde.

### 3.3 El baseline determinista

El sistema ya produce un ranking de pares de reportes que merecerían revisión,
calculado con **Adamic–Adar** sobre la proyección reporte–reporte. No
materializa aristas: ordena y explica cuáles son los vecinos comunes que
sostienen cada candidato.

Es el punto de comparación obligatorio. **Un modelo que no supera este baseline
sobre la misma partición no se incorpora**, por sofisticado que sea.

### 3.4 El texto retenido

Las transcripciones de chat, las biografías de perfil y las notas de analistas
no entran al grafo: se conservan aparte, indexadas por hash, con su locator y
su reporte de origen. Cada entrada registra el tipo de texto, su tamaño y su
procedencia.

**Ese repositorio es la materia prima de la capa semántica.** Está separado por
diseño desde el primer día, con su trazabilidad intacta, y es exactamente lo
que hay que vectorizar.

### 3.5 Las decisiones humanas registradas

Cada validación, cada rechazo, cada unificación de identidad aprobada y cada
vinculación establecida a mano queda en libros append-only encadenados por
hash, con quién la dispuso, cuándo y con qué fundamento.

**Ese registro es el conjunto etiquetado en formación.** Cada decisión que toma
un operador produce una etiqueta con su justificación en lenguaje natural. El
capítulo 6 define cómo se convierte ese flujo en un conjunto de entrenamiento.

---

## 4. Arquitectura general

```
  Reportes ─┬─► Extracción estructurada ──► Grafo heterogéneo ──┐
            │                                                    │
            └─► Texto retenido ──► Fragmentación ──► Embeddings ─┤
                                                                 │
                                        Atributos de nodo ───────┤
                                                                 ▼
                                                        Features de entrada
                                                                 │
             Decisiones humanas ──► Conjunto etiquetado          │
                        │                                        │
                        ▼                                        ▼
                  Partición temporal ─────────────────► Entrenamiento GNN
                                                                 │
                                                                 ▼
                                            Ranking + subgrafo justificante
                                                                 │
                                                                 ▼
                                    Relación INFERIDA, pendiente de validación
                                                                 │
                                                                 ▼
                                          Decisión del operador ──► etiqueta nueva
```

El circuito **se realimenta**: cada decisión sobre una propuesta del modelo
produce una etiqueta que mejora el modelo siguiente. Esa realimentación es la
razón por la que el conjunto etiquetado no se construye una vez, sino que se
acumula.

Cuatro invariantes gobiernan la arquitectura:

1. **Los embeddings son un índice derivado.** Se reconstruyen desde el texto
   original. No son la fuente de verdad y no se versionan como tal.
2. **El grafo es una proyección reconstruible.** El modelo se entrena sobre él,
   no lo modifica.
3. **Las inferencias viven en tablas separadas y versionadas.** Nunca se
   escriben junto a los hechos.
4. **Nada sale del entorno.** Modelos locales, inferencia local, entrenamiento
   local.

---

## 5. Capa de embeddings

### 5.1 Qué se vectoriza

Tres familias, con tratamiento distinto:

| Familia | Contenido | Unidad de vectorización |
|---|---|---|
| **Texto narrativo** | Transcripciones de chat, biografías de perfil, notas y resúmenes de analistas, descripciones de incidente | Fragmento de 256–512 tokens con solapamiento de 64 |
| **Entidad** | Alias, nombres visibles, nombres de archivo, descripciones de material | Cadena completa, sin fragmentar |
| **Reporte** | Representación agregada del reporte completo | Promedio ponderado de sus fragmentos, más atributos categóricos |

La fragmentación del texto narrativo respeta límites de turno de conversación
cuando existen. Un fragmento que corta un intercambio a la mitad produce un
vector que no representa ninguna interacción completa.

### 5.2 Modelo

Requisitos no negociables: **ejecución local**, **multilingüe con buen
rendimiento en castellano rioplatense** y **licencia compatible con uso
institucional**.

| Candidato | Dimensión | Observaciones |
|---|---|---|
| `multilingual-e5-large` | 1024 | Buen rendimiento en recuperación multilingüe; requiere prefijos `query:` / `passage:` |
| `bge-m3` | 1024 | Denso, disperso y multivector en un mismo modelo; útil si se quiere combinar recuperación léxica y semántica |
| `paraphrase-multilingual-mpnet-base-v2` | 768 | Más liviano, menor calidad en textos largos |

La elección se resuelve **midiendo sobre el corpus propio**, no por
reputación: se arma un conjunto de 200 pares de fragmentos con relación conocida
y se compara recuperación en top-10. El modelo elegido queda registrado con su
identificador exacto y su hash de pesos.

El lenguaje de estos reportes tiene particularidades —jerga, errores de tipeo
deliberados, sustituciones de caracteres, mezcla de idiomas— que degradan a
cualquier modelo entrenado en texto general. **La evaluación sobre corpus propio
es la única forma de saber cuánto.**

### 5.3 Almacenamiento e indexación

PostgreSQL con `pgvector`. La misma base que ya sostiene el registro
transaccional, sin agregar un servicio más.

```sql
CREATE TABLE embedding_fragmento (
    id              bigserial PRIMARY KEY,
    hash_texto      text        NOT NULL,   -- vincula con el texto retenido
    reporte         text        NOT NULL,
    locator         text        NOT NULL,   -- campo exacto dentro de la fuente
    tipo_texto      text        NOT NULL,   -- chat | bio | nota | descripcion
    fragmento_idx   int         NOT NULL,
    texto_len       int         NOT NULL,
    modelo          text        NOT NULL,   -- identificador exacto del modelo
    modelo_version  text        NOT NULL,
    dim             int         NOT NULL,
    generado_en     timestamptz NOT NULL,
    vector          vector(1024) NOT NULL,
    UNIQUE (hash_texto, fragmento_idx, modelo, modelo_version)
);

CREATE INDEX ON embedding_fragmento
    USING hnsw (vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

Cada fila conserva `locator`: **un fragmento siempre puede volver a su campo de
origen en el reporte original**. Un resultado de búsqueda semántica que no puede
citar de dónde salió no entra a un informe.

### 5.4 Versionado

Cambiar de modelo de embeddings **no es una migración: es un índice nuevo**. Se
generan las filas con el nuevo `modelo` / `modelo_version` conviviendo con las
anteriores, se comparan sobre el conjunto de evaluación, y recién entonces se
retira el índice viejo.

Nunca se sobrescribe un vector en su lugar. Un vector sobrescrito hace
irreproducible cualquier resultado anterior que se haya apoyado en él.

### 5.5 Tratamiento del texto sensible

El texto que se vectoriza es, por definición, el más sensible del sistema.

- **El vector no sale del entorno.** El modelo corre local; no hay llamada a
  ningún servicio externo en generación ni en consulta.
- **El vector no es anónimo.** Un embedding de dimensión 1024 sobre un
  fragmento corto permite reconstrucción aproximada del texto con un modelo
  adversario. Se trata con el mismo control de acceso que el texto original, no
  con el del grafo.
- **La seudonimización se aplica antes de cualquier envío a un modelo
  generativo.** Los identificadores se reemplazan por etiquetas estables y se
  restituyen localmente sobre el texto devuelto. Este mecanismo ya existe y se
  extiende a la capa semántica sin cambios.
- **Retención.** Al eliminarse un reporte del sistema, se eliminan sus
  fragmentos y sus vectores en la misma operación. El índice derivado no
  sobrevive a la fuente.

---

## 6. Conjunto etiquetado

Es la pieza que determina si la Etapa 2 rinde. Un modelo sobre un conjunto
etiquetado pobre produce resultados que parecen buenos y no lo son.

### 6.1 Las tres fuentes de etiqueta

**Fuente A — Decisiones ya registradas.** Cada vínculo validado por un operador
es un positivo con fundamento escrito. Cada vínculo rechazado es un negativo
con motivo. Cada vinculación establecida a mano es un positivo especialmente
valioso: es un caso que las reglas no detectaron y una persona sí.

Estas etiquetas **se acumulan solas** mientras el sistema se usa, y traen algo
que ningún conjunto anotado a posteriori tiene: se produjeron en el curso del
trabajo real, sobre casos reales, por quien tenía el expediente delante.

**Fuente B — Anotación dirigida.** Un conjunto construido a propósito sobre
casos ya cerrados, donde se conoce el desenlace. Es lo que permite medir
recuperación: sin él solo se puede medir precisión sobre lo que el sistema ya
propuso.

**Fuente C — Pares descartados.** El sistema registra cada par que evaluó y no
alcanzó el umbral, con qué comparten y por qué no prosperó. Son **negativos
difíciles**: comparten algo, y aun así no se vincularon. Un modelo entrenado
solo con negativos aleatorios aprende a distinguir pares obviamente no
relacionados, que no es el problema.

### 6.2 Unidad etiquetada

La unidad es el **par de reportes**, no el reporte. Cada par lleva:

```json
{
  "reporte_a": "…",
  "reporte_b": "…",
  "relacion": "mismo_autor | misma_victima | mismo_material | mismo_modus | ninguna",
  "confianza_anotador": "cierta | probable | insuficiente",
  "fundamento": "texto libre del anotador",
  "evidencia": ["locator del fragmento o campo en que se apoya", "…"],
  "anotador": "…",
  "fecha": "…",
  "fuente_etiqueta": "decision_operativa | anotacion_dirigida | descarte_del_sistema",
  "version_guia": "…"
}
```

Tres campos merecen atención.

`confianza_anotador` con tres valores, no dos. **«Insuficiente» no es
«ninguna».** Un par sobre el que el anotador no puede pronunciarse se excluye
del entrenamiento en lugar de contarse como negativo. Colapsar ambos es la
forma más común de envenenar un conjunto etiquetado en este dominio.

`evidencia` con los locators. Obliga al anotador a señalar en qué se apoyó, y
habilita después una evaluación de explicabilidad: se puede comparar lo que el
modelo señala con lo que señaló la persona.

`version_guia`. Las guías de anotación cambian. Una etiqueta producida bajo la
guía v1 y otra bajo la v3 no son directamente comparables, y hay que poder
segmentarlas.

### 6.3 Protocolo de anotación

1. **Guía escrita, con casos límite resueltos.** No una definición abstracta:
   diez ejemplos por cada tipo de relación, incluyendo cinco que *parecen*
   entrar y no entran.
2. **Doble anotación ciega** sobre el 20 % de los pares. Los dos anotadores no
   ven la decisión del otro.
3. **Medición de acuerdo** con κ de Cohen sobre ese solapamiento.
4. **Adjudicación** de los desacuerdos por una tercera persona, y actualización
   de la guía con el caso.
5. **Anotación simple** del resto, una vez alcanzado el umbral de acuerdo.

**Criterio de avance: κ ≥ 0,70 antes de escalar la anotación.** Por debajo de
ese valor el desacuerdo no está en los casos difíciles: está en la definición.
Anotar en volumen antes de resolverlo produce un conjunto que mide el ruido
entre anotadores y no el fenómeno.

### 6.4 Los archivados no son negativos

Un reporte archivado por insuficiencia de evidencia describe **una limitación
del momento del archivo**, no la inexistencia del hecho. Usarlo como ejemplo
negativo enseña al modelo a replicar exactamente aquello que el sistema existe
para corregir.

El tratamiento correcto es **aprendizaje positivo–no etiquetado** (PU
learning): se dispone de positivos confirmados y de un conjunto no etiquetado
que contiene positivos desconocidos y negativos. Dos estrategias aplicables:

- **Estimación de la prevalencia** de positivos en el conjunto no etiquetado a
  partir de una muestra anotada exhaustivamente, y corrección del sesgo del
  clasificador con esa estimación.
- **Bagging de negativos confiables**: entrenar múltiples clasificadores sobre
  submuestras del conjunto no etiquetado, y considerar negativos confiables solo
  aquellos pares que todos los clasificadores rechazan consistentemente.

Los negativos que sí se pueden usar con confianza son los de la fuente C —pares
que un operador evaluó y descartó explícitamente— y los pares con
`relacion = "ninguna"` y `confianza_anotador = "cierta"`.

### 6.5 Volumen objetivo

El volumen se dimensiona por tipo de relación, no en total. Para cada uno de
los cuatro tipos:

| Etapa | Positivos por tipo | Para qué alcanza |
|---|---|---|
| Mínimo viable | 150 | Medir si la señal existe; no entrenar |
| Baseline semántico | 400 | Ajustar umbrales de similitud y evaluar recuperación |
| GNN experimental | 1.000 | Entrenar con validación cruzada estable |
| GNN en circuito | 2.500+ | Evaluación por subgrupos, detección de sesgo |

La relación **mismo modus operandi** admite volúmenes menores por tipo porque
es más frecuente; **misma víctima** exigirá el esfuerzo mayor por ser la más
escasa y la más sensible.

Estos números son órdenes de magnitud para planificar, y se ajustan con la
primera medición de curva de aprendizaje: se entrena con el 25 %, 50 %, 75 % y
100 % del conjunto disponible y se observa si la métrica sigue subiendo. Si
sigue subiendo, falta conjunto.

### 6.6 Gobierno del conjunto

- **Particiones congeladas.** Una vez definidas las particiones de
  entrenamiento, validación y prueba, no se re-etiqueta un par que ya está en
  prueba. Se agrega a una partición nueva.
- **Versionado del conjunto**, con hash del contenido. Todo resultado
  reportado cita la versión del conjunto sobre la que se obtuvo.
- **Trazabilidad del anotador.** Permite detectar deriva individual y
  recalibrar.
- **Revisión periódica de una muestra** por una segunda persona, para detectar
  deriva del criterio a lo largo del tiempo.

---

## 7. Baseline semántico

Antes de la GNN se construye un sistema completo **sin ella**. No es un paso
preparatorio: es un producto entregable, y además es la vara contra la cual se
mide la GNN.

### 7.1 Componentes

1. **Recuperación densa.** Para el reporte en análisis, recuperar los `k`
   fragmentos más similares del corpus por coseno sobre los embeddings, y
   agregar por reporte.
2. **Recuperación léxica.** BM25 sobre el mismo corpus. Captura coincidencias
   exactas de jerga, apodos y expresiones que el modelo denso diluye.
3. **Fusión.** Combinación de ambos rankings por *reciprocal rank fusion*, que
   no requiere calibrar escalas entre sistemas heterogéneos.
4. **Señal estructural.** El puntaje Adamic–Adar del par, ya disponible.
5. **Combinación final.** Un modelo lineal o un árbol de decisión de poca
   profundidad sobre estas cuatro señales, entrenado sobre el conjunto
   etiquetado. Se elige un modelo simple deliberadamente: sus coeficientes son
   inspeccionables y su comportamiento, previsible.

### 7.2 Por qué este orden

Un porcentaje sustancial de la vinculación contextual se resuelve con
similitud textual bien hecha. Construir la GNN antes de saber cuánto es ese
porcentaje impide después atribuirle mérito: si la GNN rinde, no se sabe cuánto
de eso venía de los embeddings.

Además, el baseline semántico entrega valor operativo mientras el conjunto
etiquetado todavía se está construyendo, y **su uso genera etiquetas**.

---

## 8. Modelo de grafos

### 8.1 Formulación

Predicción de enlaces sobre grafo heterogéneo, con arquitectura
**codificador–decodificador**:

- **Codificador**: una GNN que produce una representación vectorial por nodo,
  agregando información de sus vecinos a lo largo de `L` saltos, con parámetros
  distintos por tipo de relación.
- **Decodificador**: una función que, dadas las representaciones de dos nodos
  reporte, produce un puntaje por cada tipo de relación contextual.

Formalmente, para cada capa `l` y cada tipo de relación `r`:

```
h_v^(l+1) = σ( W_0^(l) h_v^(l) + Σ_r Σ_{u ∈ N_r(v)}  (1 / c_{v,r}) W_r^(l) h_u^(l) )
```

y para el par de reportes `(a, b)` y el tipo de relación `t`:

```
score_t(a, b) = h_a^T  R_t  h_b
```

con `R_t` diagonal (formulación DistMult), que mantiene la cantidad de
parámetros acotada y admite lectura: cada dimensión pesa distinto según el tipo
de relación que se está prediciendo.

### 8.2 Arquitecturas candidatas

| Arquitectura | Cuándo conviene | Riesgo |
|---|---|---|
| **R-GCN** | 24 tipos de relación con volumen desparejo. Parámetros por relación, con descomposición en bases para las relaciones escasas | Suaviza en exceso con muchas capas |
| **GraphSAGE heterogéneo** | Grafos grandes; muestreo de vecindario acotado | Pierde información de tipo si no se separa la agregación |
| **HGT** | Atención por tipo de nodo y de arista; aprende qué relaciones importan | Requiere más datos etiquetados; menos interpretable |

**Punto de partida: R-GCN con descomposición en bases y dos capas.** Dos capas
significa que un reporte ve a sus vecinos y a los vecinos de sus vecinos —un
reporte a través de una cuenta compartida, o de un dispositivo—. Tres capas ya
alcanzan casi todo el grafo y la representación pierde especificidad.

HGT queda para cuando el conjunto etiquetado supere los umbrales del capítulo
6.5 y se pueda medir si la atención por tipo aporta algo.

### 8.3 Features de entrada

| Nodo | Features iniciales |
|---|---|
| `REPORTE` | Embedding agregado de sus fragmentos · plataforma · clasificación · prioridad · antigüedad normalizada · estado |
| `PERSONA_MENCION` | Embedding del alias · rol procesal · edad aproximada declarada · género declarado |
| `CUENTA` | Embedding del identificador · plataforma · antigüedad · indicador de baja |
| `EVIDENCIA` | Tipo de archivo · indicador de remisión a autoridad · embedding de la descripción |
| `IP` | Rasgos técnicos: versión, CGNAT, privada, atribuibilidad sin dato adicional |
| `UBICACION` | Coordenadas normalizadas · granularidad declarada |
| `DISPOSITIVO`, `TELEFONO`, `EMAIL` | Grado en el grafo · tipo · antigüedad de la primera aparición |

Los atributos categóricos se codifican como *embeddings* aprendidos, no como
*one-hot*: la cardinalidad de plataformas y clasificaciones crece con el tiempo
y el modelo debe tolerar categorías nuevas sin reentrenamiento estructural.

**Se excluyen deliberadamente** de las features: la jurisdicción, el operador
asignado y cualquier atributo que codifique la carga de trabajo de un área. Son
predictores espurios de la etiqueta —un área que trabaja más vincula más— y su
inclusión produce un modelo que aprende procesos internos en lugar de hechos.

### 8.4 Features de arista

Cada arista aporta al paso de mensajes: tipo de relación, clase epistemológica
(observada, derivada, inferida, afirmada), confianza cuando existe, y antigüedad
del hecho.

La clase epistemológica como feature es importante: **el modelo debe poder
aprender que una arista observada pesa distinto que una inferida**. Sin ella, la
GNN propaga por sus propias hipótesis anteriores con la misma fuerza que por lo
que consta en la evidencia, y amplifica su propio error.

### 8.5 Partición y prevención de fuga

**Partición temporal, no aleatoria.** Se entrena con reportes recibidos hasta
`T`, se valida en `(T, T+Δ]` y se prueba en `(T+Δ, T+2Δ]`.

Una partición aleatoria filtra información del futuro hacia el entrenamiento y
produce métricas infladas que se derrumban en producción. La partición temporal
reproduce la condición real: el sistema siempre predice sobre reportes que
llegan después de aquellos con los que aprendió.

Tres controles adicionales contra la fuga:

1. **Aristas de prueba removidas del grafo de entrenamiento.** El par que se va
   a predecir no puede estar presente como arista durante el entrenamiento.
2. **Sin fuga por entidad puente.** Si dos reportes comparten una entidad y esa
   entidad se usó para etiquetarlos, el modelo puede memorizar la entidad en
   lugar de aprender el patrón. Se evalúa también sobre un subconjunto donde
   los pares **no comparten ninguna entidad**, que es el escenario que la Etapa
   2 viene a resolver.
3. **Sin solapamiento de casos entre particiones.** Todos los reportes de un
   mismo legajo caen en la misma partición.

### 8.6 Entrenamiento

- **Función de pérdida:** entropía cruzada binaria por tipo de relación, con
  ponderación inversa a la frecuencia de cada tipo.
- **Muestreo de negativos:** 50 % negativos difíciles de la fuente C, 30 %
  negativos por corrupción estructurada —mismo tipo de plataforma, distinta
  familia de casos—, 20 % aleatorios. La proporción se ajusta midiendo, no por
  convención.
- **Regularización:** *dropout* en las aristas, no solo en las unidades. Obliga
  al modelo a no depender de una relación única.
- **Detención temprana** sobre precisión en los primeros puestos del ranking de
  validación, no sobre la pérdida. La pérdida y la utilidad operativa no se
  mueven juntas.
- **Semilla fija y registrada.** Dos entrenamientos con la misma configuración
  y los mismos datos producen el mismo modelo.

### 8.7 Evaluación

**La métrica principal es operativa**, no estadística:

> De los `k` primeros pares que el sistema propone para un reporte, ¿cuántos un
> operador confirma como relevantes?

Se reporta como **precisión en los primeros 5, 10 y 20**, que es la cantidad de
propuestas que una persona puede revisar razonablemente por caso.

Métricas complementarias:

| Métrica | Por qué |
|---|---|
| **AUC-PR** | Con clases muy desbalanceadas, el área bajo la curva ROC da valores altos y engañosos. La curva de precisión–recuperación no |
| **MRR** | Cuán arriba aparece el primer par relevante |
| **Recuperación en 50** | Cuánto del total relevante se alcanza revisando 50 candidatos |
| **Precisión por tipo de relación** | Un promedio agregado esconde que el modelo funciona para modus operandi y falla para misma víctima |
| **Precisión en pares sin entidad compartida** | El escenario que justifica toda la Etapa 2 |

**Criterios de aceptación**, evaluados sobre la misma partición temporal:

1. Supera al baseline Adamic–Adar en precisión en los primeros 10.
2. Supera al baseline semántico del capítulo 7 en el mismo indicador.
3. Sobre pares sin entidad compartida, supera a ambos con margen medible.
4. Ningún tipo de relación queda por debajo del baseline.
5. La evaluación por subgrupos —plataforma, antigüedad del reporte, volumen de
   texto disponible— no muestra un subgrupo con degradación severa.

**Si no se cumplen los cinco, el baseline semántico queda como sistema en
producción y la GNN vuelve a experimentación.** Es un resultado válido y hay que
poder aceptarlo.

---

## 9. Explicabilidad

Un puntaje sin fundamento no entra al circuito. Es un requisito de diseño, no
una mejora deseable.

### 9.1 Qué debe producir el modelo

Por cada par propuesto:

1. **El subgrafo justificante**: el conjunto mínimo de nodos y aristas cuya
   remoción hace caer el puntaje por debajo del umbral. Se obtiene con métodos
   de tipo GNNExplainer, que optimizan una máscara sobre aristas y features
   maximizando la información retenida.
2. **Los fragmentos de texto** que más contribuyeron a la similitud, con su
   locator: reporte, campo exacto y posición dentro del campo.
3. **La descomposición del puntaje** entre la contribución estructural (grafo)
   y la contribución semántica (texto).
4. **Los pares análogos ya validados** que sostienen la propuesta: casos
   confirmados con estructura similar. Es la forma de explicación más útil para
   quien decide, porque le permite comparar con algo conocido.

### 9.2 Redacción de la propuesta

La explicación que llega al operador se redacta en prosa castellana completa,
sin identificadores técnicos ni nombres de reglas. La forma es la misma que ya
usan las vinculaciones derivadas:

> *«Este reporte guarda semejanza con el 900000117 en la forma de aproximación
> descripta: en ambos la conversación se inicia ofreciendo participación en un
> casting, se traslada a una plataforma de mensajería en el segundo o tercer
> intercambio, y la solicitud de material aparece dentro de las primeras
> cuarenta y ocho horas. No comparten cuenta, dispositivo ni dirección IP. La
> semejanza se apoya en los pasajes que se citan a continuación, y es una
> hipótesis que requiere validación.»*

El párrafo dice tres cosas que no pueden faltar: **en qué se parecen**, **qué no
comparten** —para que nadie lea más de lo que hay— y **cuál es su estatuto**.

---

## 10. Integración con el circuito de decisión

### 10.1 Estatuto de la salida

Cada propuesta del modelo se materializa como una relación de clase
**inferida**, en estado **pendiente**, con procedencia completa:

| Campo | Contenido |
|---|---|
| `method` | Identificador del modelo |
| `method_version` | Versión del modelo entrenado |
| `training_set_version` | Versión del conjunto etiquetado |
| `embedding_model` | Modelo de embeddings y versión |
| `confidence` | Puntaje calibrado |
| `source_locator` | Los fragmentos que sostienen la propuesta |
| `explicacion` | La prosa del apartado 9.2 |
| `subgrafo_justificante` | Nodos y aristas de la explicación estructural |

**Calibración.** El puntaje crudo de una red no es una probabilidad. Se calibra
—escalado de Platt o regresión isotónica sobre el conjunto de validación— de
modo que «0,80» signifique que aproximadamente el 80 % de las propuestas con ese
puntaje resultan confirmadas. Sin calibración, un número en pantalla induce a
error a quien lo lee.

### 10.2 Umbrales operativos

Tres bandas, definidas con los operadores sobre datos medidos:

| Banda | Comportamiento |
|---|---|
| **Alta** | Se propone en primer plano, junto con las vinculaciones derivadas |
| **Media** | Se propone en una sección separada, rotulada como semejanza contextual |
| **Baja** | No se muestra; queda disponible para consulta explícita y para auditoría |

Las propuestas del modelo **nunca se presentan mezcladas** con las
vinculaciones que se apoyan en un dato objetivo compartido. Son cosas distintas
y se leen distinto.

### 10.3 Realimentación

Cada decisión sobre una propuesta del modelo se registra en el mismo libro
append-only que las demás, con la particularidad de que asienta la versión del
modelo que la produjo.

Eso permite, por versión de modelo:

- calcular la tasa de confirmación real en producción;
- detectar degradación cuando esa tasa cae respecto de la evaluación;
- comparar dos versiones sobre la misma población;
- reconstruir, para cualquier propuesta pasada, qué modelo la produjo y con qué
  conjunto se había entrenado.

### 10.4 Reversibilidad

Retirar una versión del modelo del circuito deja el sistema exactamente como
estaba: las propuestas se marcan como no vigentes, las decisiones humanas sobre
ellas se conservan, y las vinculaciones derivadas y observadas no se tocan.
**La capa de aprendizaje se puede desconectar sin pérdida.**

---

## 11. Infraestructura

### 11.1 Componentes

| Función | Tecnología | Ubicación |
|---|---|---|
| Embeddings de texto | `sentence-transformers` sobre PyTorch | Local |
| Almacenamiento vectorial | PostgreSQL + `pgvector`, índice HNSW | Local |
| Recuperación léxica | PostgreSQL *full-text search* o índice dedicado | Local |
| Grafo para entrenamiento | PyTorch Geometric | Local |
| Registro de experimentos | MLflow o equivalente | Local |
| Servicio de inferencia | FastAPI, proceso separado del transaccional | Local |

Toda la cadena corre dentro del entorno institucional. Ningún fragmento de
texto, ningún vector y ningún resultado sale por la red.

### 11.2 Dimensionamiento

**Generación de embeddings.** Un modelo de 1024 dimensiones procesa del orden de
100 a 200 fragmentos por segundo en GPU de gama media, y entre 5 y 15 por
segundo en CPU. Para un corpus de `N` reportes con un promedio de `f`
fragmentos por reporte, la generación inicial requiere `N × f` inferencias. Es
una operación por única vez más el incremental de los reportes nuevos.

**Almacenamiento.** Un vector de 1024 dimensiones en punto flotante de 4 bytes
ocupa 4 KB. Un millón de fragmentos son 4 GB de vectores más el índice HNSW,
que agrega entre el 50 % y el 100 %.

**Entrenamiento.** Para grafos de hasta cientos de miles de nodos, una R-GCN de
dos capas entrena en minutos a decenas de minutos por época en GPU de gama
media. El cuello de botella no es el cómputo: es el conjunto etiquetado.

**Inferencia.** Con las representaciones precalculadas, puntuar un reporte
contra los candidatos recuperados es despreciable. La recuperación vectorial con
índice HNSW responde en milisegundos sobre millones de vectores.

### 11.3 Reproducibilidad

Cada entrenamiento registra: hash del conjunto etiquetado, hash del grafo de
entrada, semilla, hiperparámetros completos, versión de cada biblioteca y hash
de los pesos resultantes. Un resultado que no se puede reproducir no se reporta.

---

## 12. Plan por fases

Cada fase entrega algo utilizable y tiene un criterio de salida verificable.
Ninguna avanza sin cumplir el de la anterior.

### Fase 1 — Corpus textual y capa de embeddings

**Se construye:** extracción del texto retenido, fragmentación con solapamiento,
evaluación comparativa de tres modelos sobre corpus propio, tabla vectorial con
índice HNSW, y buscador semántico con citación al locator.

**Se entrega:** búsqueda por semejanza sobre el archivo completo, con resultados
que citan reporte y campo exacto.

**Criterio de salida:** sobre 200 pares de fragmentos con relación conocida, el
modelo elegido recupera el par correcto entre los primeros 10 en una proporción
medida y documentada, superior a la de la búsqueda léxica sola.

### Fase 2 — Conjunto etiquetado

**Se construye:** guía de anotación con casos límite, herramienta de anotación
sobre pares, extracción de etiquetas desde las decisiones ya registradas,
protocolo de doble anotación y medición de acuerdo.

**Se entrega:** conjunto etiquetado versionado, con particiones temporales
congeladas.

**Criterio de salida:** κ ≥ 0,70 sobre el solapamiento de doble anotación, y el
volumen mínimo viable por tipo de relación.

### Fase 3 — Baseline semántico

**Se construye:** recuperación densa, recuperación léxica, fusión por rango
recíproco, incorporación de la señal estructural, modelo lineal de combinación.

**Se entrega:** sistema de vinculación contextual **en producción**, con
explicación citada.

**Criterio de salida:** supera al baseline Adamic–Adar en precisión en los
primeros 10 sobre la partición de prueba, con margen medido.

### Fase 4 — GNN experimental

**Se construye:** grafo heterogéneo con features, R-GCN de dos capas,
entrenamiento con muestreo estratificado de negativos, evaluación completa
incluyendo subgrupos.

**Se entrega:** informe de evaluación comparativa contra ambos baselines.

**Criterio de salida:** los cinco criterios de aceptación del apartado 8.7. Su
incumplimiento es un resultado válido: el baseline semántico queda en
producción.

### Fase 5 — Explicabilidad y puesta en circuito

**Se construye:** subgrafo justificante, atribución a fragmentos, calibración
del puntaje, redacción en prosa, integración con el registro de decisiones y
tablero de seguimiento de la tasa de confirmación.

**Se entrega:** propuestas del modelo dentro del circuito de validación, con
seguimiento de su rendimiento real.

**Criterio de salida:** la tasa de confirmación en producción se mantiene,
durante un período acordado, dentro del margen de lo medido en evaluación.

---

## 13. Riesgos y controles

| Riesgo | Manifestación | Control |
|---|---|---|
| **Fuga entre entrenamiento y prueba** | Métricas excelentes que se derrumban en producción | Partición temporal, remoción de aristas de prueba, evaluación sin entidad compartida |
| **Aprender el proceso en lugar del hecho** | El modelo predice qué vincula un área, no qué está relacionado | Exclusión de features de proceso, evaluación por subgrupos |
| **Sesgo por cobertura de plataforma** | Las plataformas que informan más campos dominan las propuestas | Normalización por riqueza de datos, métrica por plataforma |
| **Confianza inducida por un número** | Un puntaje alto se lee como acreditación | Calibración, banda explícita, redacción que declara el estatuto y lo que no se comparte |
| **Realimentación que se refuerza a sí misma** | El modelo propone, se confirma lo propuesto, se entrena con eso | Reserva de una fracción de casos anotados a ciegas, sin exposición previa a propuestas |
| **Deriva del criterio de anotación** | El conjunto pierde consistencia con el tiempo | Versionado de la guía, re-anotación periódica de una muestra |
| **Amplificación por aristas inferidas** | El modelo propaga por sus propias hipótesis anteriores | Clase epistemológica como feature de arista; opción de entrenar solo sobre observadas y derivadas |
| **Reconstrucción desde vectores** | Un embedding filtrado permite aproximar el texto | Control de acceso equivalente al del texto original |
| **Degradación silenciosa** | El modelo empeora sin que nadie lo note | Seguimiento continuo de la tasa de confirmación por versión |

---

## 14. Glosario

**Adamic–Adar.** Medida de proximidad entre dos nodos que suma el inverso del
logaritmo del grado de cada vecino común. Un vecino poco conectado aporta más
que uno muy conectado.

**AUC-PR.** Área bajo la curva de precisión–recuperación. Con clases muy
desbalanceadas es más informativa que el área bajo la curva ROC.

**BM25.** Función de puntuación para recuperación léxica que pondera la
frecuencia de un término en un documento contra su frecuencia en el corpus.

**Calibración.** Transformación del puntaje crudo de un modelo para que se
interprete como probabilidad.

**Embedding.** Representación de un objeto —un texto, un nodo— como vector de
números reales, construida de modo que la proximidad entre vectores refleje
semejanza.

**GNN.** Red neuronal que opera sobre grafos, produciendo la representación de
cada nodo a partir de la de sus vecinos, iterativamente.

**GNNExplainer.** Método que identifica el subconjunto mínimo de aristas y
features que explica la predicción de una GNN.

**HNSW.** Estructura de índice para búsqueda aproximada de vecinos más cercanos
en espacios vectoriales de alta dimensión.

**κ de Cohen.** Medida de acuerdo entre dos anotadores que descuenta el acuerdo
esperable por azar.

**MRR.** Media del inverso de la posición del primer resultado relevante.

**Negativo difícil.** Ejemplo negativo que comparte características con los
positivos, y que por eso enseña más que uno elegido al azar.

**PU learning.** Aprendizaje a partir de ejemplos positivos y de un conjunto no
etiquetado, sin negativos confirmados.

**R-GCN.** GNN con parámetros propios por tipo de relación, apta para grafos
heterogéneos.

**Reciprocal rank fusion.** Combinación de rankings de sistemas distintos
sumando el inverso de la posición en cada uno, sin necesidad de calibrar escalas.

**Subgrafo justificante.** Conjunto mínimo de nodos y aristas cuya presencia
explica una predicción.
