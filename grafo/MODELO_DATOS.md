<!-- GENERADO POR src/docs_modelo.py A PARTIR DE src/ontologia.py.
     No editar a mano: los cambios se pisan en la proxima construccion. -->

# Modelo de datos del grafo — Bóveda CIJ

Versión de ontología: **`0.3.0`**

Ontología preliminar. Debe validarse con los equipos jurídicos e institucionales antes de considerarse estable (contexto.md 10.2).

## 1. Clases de relación

Las tres clases nunca se mezclan, ni en la persistencia ni en la interfaz.

| Clase | Qué significa | Estado inicial de validación |
|---|---|---|
| `observada` | Surge directamente de un campo de la fuente | `validada` |
| `derivada` | Producto de una regla determinista y reproducible | `pendiente` |
| `inferida` | Hipótesis por similitud, modelo, LLM o GNN | `pendiente` |

## 2. Tipos de nodo

`identificador`: el valor es un dato objetivo apto para sostener un vínculo entre reportes. `fusionable`: dos menciones del mismo valor son el mismo objeto — las personas **no** lo son.

| Tipo | Identificador | Fusionable | Descripción |
|---|---|---|---|
| `REPORTE` | no | sí | Reporte NCMEC/CyberTipline ingresado a SIPAR |
| `EVENTO` | no | sí | Hecho reportado: chat, email, webpage, p2p, gaming |
| `PERSONA_MENCION` | no | **no** | Mencion de persona dentro de UN reporte. El rol procesal vive en la arista, no en el nodo |
| `IDENTIDAD` | no | **no** | Agrupamiento de menciones confirmado por una persona |
| `CUENTA` | sí | sí | Cuenta de plataforma: ESP + espUserId |
| `ALIAS` | sí | sí | Nombre visible / screen name (identificador debil) |
| `EMAIL` | sí | sí | Direccion de correo normalizada |
| `TELEFONO` | sí | sí | Numero telefonico en formato E.164 |
| `IP` | sí | sí | Direccion IP. Solo tiene valor junto a fecha, hora, prestador y puerto cuando exista |
| `DISPOSITIVO` | sí | sí | Device ID / IDFA / GAID |
| `EVIDENCIA` | sí | sí | Archivo reportado, identificado por hash |
| `SEGMENTO` | no | sí | Fragmento de una evidencia: frame, clip, pagina |
| `UBICACION` | no | sí | Ciudad / region estimada o declarada |
| `JURISDICCION` | no | sí | Jurisdiccion competente propuesta |
| `ORGANIZACION` | no | sí | ESP, prestador de internet, organismo, fiscalia |
| `DOCUMENTO` | no | sí | Oficio, respuesta de prestador, informe |

## 3. Vocabulario de relaciones


### Observadas

| Relación | Descripción |
|---|---|
| `REPORTADO_EN` | Mencion de persona -> reporte. El rol procesal va en la arista |
| `CONTIENE_EVENTO` | Reporte -> evento o incidente |
| `EMITIDO_POR` | Reporte -> organizacion que lo genero |
| `USA_CUENTA` | Mencion de persona -> cuenta |
| `ALIAS_DE` | Cuenta -> alias o nombre visible |
| `ASOCIADO_A_TELEFONO` | Cuenta o mencion -> telefono |
| `ASOCIADO_A_EMAIL` | Cuenta o mencion -> email |
| `OBSERVADO_DESDE_IP` | Cuenta -> IP, con fecha, hora, evento y puerto |
| `USA_DISPOSITIVO` | Cuenta -> dispositivo |
| `PARTICIPA_EN` | Cuenta -> evento |
| `ADJUNTA` | Reporte o evento -> evidencia |
| `UBICADO_EN` | Entidad -> ubicacion declarada por la fuente |
| `PUESTO_A_DISPOSICION_DE` | Reporte -> organismo al que NCMEC lo puso a disposicion |

### Derivadas

| Relación | Descripción |
|---|---|
| `GEOLOCALIZA_EN` | IP -> ubicacion por geolookup (aproximada) |
| `ASIGNADA_A` | IP -> prestador de acceso |
| `PERTENECE_A_JURISDICCION` | Ubicacion o reporte -> jurisdiccion competente |
| `COINCIDE_CON` | Reporte <-> reporte por identificador objetivo compartido |
| `POSIBLE_DUPLICADO_DE` | Reporte <-> reporte con indicios de duplicacion |
| `CONTRADICE` | Vinculo que debilita otro, por ejemplo un viaje imposible |
| `RESPONDE_A` | Respuesta de prestador -> oficio |
| `IDENTIFICADO_COMO` | Mencion -> identidad unificada por decision humana |

### Inferidas

| Relación | Descripción |
|---|---|
| `POSIBLE_MISMA_IDENTIDAD` | Dos menciones podrian ser la misma persona |
| `SIMILAR_A` | Similitud textual, semantica o multimodal |

## 4. Metadatos obligatorios de cada arista

Si falta la fuente, el locator o la explicación, la arista **no se crea**: se registra un incumplimiento. Es preferible perder un vínculo a tener uno que no se pueda explicar.

| Campo | Para qué |
|---|---|
| `arista_id` | identificador determinista: (extremos, relación, método, locator, fuente) |
| `relation_type` | relación del vocabulario controlado |
| `origin` | observada / derivada / inferida |
| `source_evidence_id` | qué evidencia la sostiene |
| `source_locator` | ubicación exacta dentro de esa evidencia: campo JSON, página, timestamp, frame |
| `method` / `method_version` | qué produjo la arista y con qué versión |
| `ontologia_version` | con qué vocabulario y pesos se calculó |
| `confidence` | confianza; obligatoria para derivadas e inferidas |
| `observed_at` | cuándo ocurrió el hecho, distinto de cuándo se calculó |
| `created_at` | cuándo se produjo la arista |
| `validation_status` / `validated_by` / `validated_at` | revisión humana |
| `case_scope` | alcance y permisos |
| `explicacion` | por qué existe, en lenguaje legible |
| `vigente` | una arista rechazada se marca, no se borra |

## 5. Reglas deterministas de vinculación

`corrobora solamente`: nunca sostiene un vínculo por sí sola, solo refuerza otro sostenido por un dato objetivo fuerte. Es la traducción de la regla del relevamiento 3.5.

| Regla | Ver. | Tipo | Peso base | Corrobora solamente | Pondera por rareza | Qué detecta |
|---|---|---|---|---|---|---|
| `R01_CUENTA` | 1.0 | `CUENTA` | 0.98 | no | no | Misma cuenta: mismo ESP y mismo espUserId |
| `R02_DISPOSITIVO` | 1.0 | `DISPOSITIVO` | 0.92 | no | sí | Mismo identificador de dispositivo |
| `R03_TELEFONO` | 1.0 | `TELEFONO` | 0.90 | no | sí | Mismo telefono normalizado a E.164 |
| `R04_EMAIL` | 1.0 | `EMAIL` | 0.90 | no | sí | Mismo correo normalizado |
| `R05_EVIDENCIA` | 1.0 | `EVIDENCIA` | 0.88 | no | sí | Mismo hash de archivo |
| `R06_IP_VENTANA` | 1.0 | `IP` | 0.72 | no | sí | Misma IP dentro de la ventana temporal del prestador. La IP se valora siempre junto con su fecha y hora |
| `R07_IP_SUELTA` | 1.0 | `IP` | 0.28 | sí | sí | Misma IP fuera de la ventana temporal: indicio, no atribucion |
| `R08_ALIAS` | 1.0 | `ALIAS` | 0.22 | sí | sí | Mismo nombre visible: refuerza, nunca sostiene solo |
| `R09_UBICACION` | 1.0 | `UBICACION` | 0.08 | sí | sí | Misma ciudad estimada: contexto, nunca sostiene solo |

### Combinación

Noisy-OR sobre las reglas que disparan, **solo si al menos una sostiene el vínculo por sí sola**. Confianza máxima `0.99`: ninguna regla determinista produce certeza absoluta.


### Discriminancia

- Hasta `df = 10` reportes, el identificador conserva su peso completo.
- Por encima, el peso decae logarítmicamente.
- Desde `df = 50` deja de poder sostener un vínculo solo.
- Desde `df = 100` ni siquiera genera pares candidatos (se informa como *hub*).
- La fracción sobre el corpus (`20 %`) recién se aplica con al menos 200 reportes: con un corpus chico engaña.

## 6. Política de IP

Una IP aislada no identifica a una persona. Se valora junto con fecha, hora, prestador y puerto.

| Prestador | Ventana temporal asumida |
|---|---|
| *(default)* | 24 h |
| telecentro | 24 h |
| telecom argentina | 24 h |
| telefonica de argentina | 24 h |
| claro | 12 h |
| personal | 12 h |
| movistar | 12 h |

- Rango CGNAT: `100.64.0.0/10`.
- CGNAT **sin** puerto de origen: el peso se multiplica por `0.35` y la regla pasa a corroborar solamente. El prestador no puede identificar al abonado.
- CGNAT **con** puerto y timestamp: factor `0.85`, la atribución vuelve a ser posible.
- Las fechas se manejan en UTC. Un valor sin zona horaria se marca como supuesto: tres horas de corrimiento alcanzan para atribuir una conexión al abonado equivocado.

## 7. Umbrales

| Umbral | Valor | Qué controla |
|---|---|---|
| `UMBRAL_PROPONER` | 0.55 | debajo de esto no se materializa la arista |
| `UMBRAL_PROBABLE` | 0.70 | franja de confianza media |
| `UMBRAL_ALTA` | 0.90 | franja de confianza alta |
| `UMBRAL_CLUSTER` | 0.70 | mínimo para agrupar en un legajo lógico y para emitir alertas |

## 8. Estado de la última construcción

- Nodos: **65** · Aristas: **118**
- Por origen: afirmada 3, derivada 28, inferida 3, observada 84
- Incumplimientos de procedencia: **0**

| Tipo de nodo | Cantidad |
|---|---|
| `REPORTE` | 10 |
| `ORGANIZACION` | 10 |
| `CUENTA` | 10 |
| `PERSONA_MENCION` | 10 |
| `IP` | 7 |
| `ALIAS` | 5 |
| `UBICACION` | 5 |
| `EVENTO` | 4 |
| `DISPOSITIVO` | 2 |
| `TELEFONO` | 1 |
| `IDENTIDAD` | 1 |
