<!-- GENERADO POR src/docs_modelo.py A PARTIR DE src/ontologia.py.
     No editar a mano: regenerar con python grafo/documentar.py. -->

# Modelo de datos del grafo — Bóveda CIJ

Versión de ontología: **`0.4.0`**

Ontología preliminar. Debe validarse con los equipos jurídicos e institucionales antes de considerarse estable.

## 1. Clases de relación

Las 4 clases nunca se mezclan, ni en la persistencia ni en la interfaz.

| Clase | Qué significa | Estado inicial de validación |
|---|---|---|
| `observada` | El dato figura textualmente en un campo del reporte de origen. No fue calculado ni supuesto por el sistema. | `validada` |
| `derivada` | Resulta de aplicar una regla determinista y reproducible sobre datos que constan en la fuente. Puede volver a calcularse y debe ser revisada por una persona. | `pendiente` |
| `inferida` | Es una hipótesis producida por similitud o por un modelo. No acredita nada por sí sola y requiere validación humana. | `pendiente` |
| `afirmada` | La estableció una persona por su propio criterio, no el sistema. No surge de la fuente ni de una regla: queda registrada con quién la dispuso, cuándo y con qué fundamento, y puede revertirse. | `validada` |

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
| `ALIAS_PAGO` | sí | sí | Alias de cobro o transferencia (CVU/CBU/billetera) |
| `EMAIL` | sí | sí | Direccion de correo normalizada |
| `TELEFONO` | sí | sí | Numero telefonico en formato E.164 |
| `IP` | sí | sí | Direccion IP. Solo tiene valor junto a fecha, hora, prestador y puerto cuando exista |
| `DISPOSITIVO` | sí | sí | Device ID / IDFA / GAID |
| `EVIDENCIA` | sí | sí | Archivo reportado, identificado por hash |
| `HASH_PERCEPTUAL` | sí | sí | Huella perceptual de imagen; similitud, no igualdad criptografica |
| `HUELLA_AUDIO` | sí | sí | Huella algoritmica de audio declarada en el manifiesto multimedia |
| `SEGMENTO` | no | sí | Fragmento de una evidencia: frame, clip, pagina |
| `LUGAR_MENCION` | no | **no** | Descripcion de lugar extraida de texto; conserva categorias y locator, no el texto sensible |
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
| `TIENE_HASH_PERCEPTUAL` | Evidencia -> hash perceptual informado por el flujo multimedia |
| `TIENE_HUELLA_AUDIO` | Evidencia -> huella de audio informada por el flujo multimedia |
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
| `MENCIONA_TELEFONO` | Evento o cuenta -> telefono escrito en texto libre |
| `MENCIONA_EMAIL` | Evento o cuenta -> correo escrito en texto libre |
| `MENCIONA_ALIAS` | Evento o cuenta -> alias escrito en texto libre |
| `MENCIONA_ALIAS_PAGO` | Evento o cuenta -> alias de cobro escrito en texto libre |
| `MENCIONA_LUGAR` | Reporte -> descripcion de lugar categorizada desde texto libre |
| `SIMILITUD_PERCEPTUAL` | Dos imagenes tienen hashes perceptuales cercanos por Hamming |
| `COINCIDE_HUELLA_AUDIO` | Dos audios comparten la misma huella algoritmica declarada |

### Inferidas

| Relación | Descripción |
|---|---|
| `POSIBLE_MISMA_IDENTIDAD` | Dos menciones podrian ser la misma persona |
| `SIMILAR_A` | Similitud textual, semantica o multimodal |

### Afirmadas por una persona

| Relación | Descripción |
|---|---|
| `VINCULADO_POR_OPERADOR` | Reporte -> reporte. Vinculacion que un operador establece por su propio criterio, con fundamento registrado. No la propuso el sistema y no se recalcula: se conserva hasta que se revierta |

## 4. Metadatos obligatorios de cada arista

Si falta la fuente, el locator o la explicación, la arista **no se crea**: se registra un incumplimiento. Es preferible perder un vínculo a tener uno que no se pueda explicar.

| Campo | Para qué |
|---|---|
| `arista_id` | identificador determinista: (extremos, relación, método, locator, fuente) |
| `relation_type` | relación del vocabulario controlado |
| `origin` | una de las clases declaradas en `ORIGENES` |
| `source_evidence_id` | qué evidencia la sostiene |
| `source_locator` | ubicación exacta dentro de esa evidencia: campo JSON, página, timestamp, frame |
| `method` / `method_version` | qué produjo la arista y con qué versión |
| `ontologia_version` | con qué vocabulario y pesos se calculó |
| `confidence` | nombre técnico heredado del puntaje no calibrado; obligatorio para derivadas e inferidas, no equivale a una probabilidad |
| `confidence_calibrated` | `false` para todo puntaje calculado en esta demo |
| `observed_at` | cuándo ocurrió el hecho, distinto de cuándo se calculó |
| `created_at` | cuándo se produjo la arista |
| `validation_status` / `validated_by` / `validated_at` | revisión humana |
| `case_scope` | metadato de alcance; no implementa permisos de acceso |
| `explicacion` | por qué existe, en lenguaje legible |
| `vigente` | una arista rechazada se marca, no se borra |

## 5. Reglas deterministas de vinculación

`corrobora solamente`: nunca sostiene un vínculo por sí sola, solo refuerza otro sostenido por un dato objetivo fuerte. Es una condición explícita de combinar().

| Regla | Ver. | Tipo | Peso base | Corrobora solamente | Pondera por rareza | Qué detecta |
|---|---|---|---|---|---|---|
| `R01_CUENTA` | 1.0 | `CUENTA` | 0.98 | no | no | Misma cuenta: mismo ESP y mismo espUserId |
| `R02_DISPOSITIVO` | 1.0 | `DISPOSITIVO` | 0.92 | no | sí | Mismo identificador de dispositivo |
| `R03_TELEFONO` | 1.1 | `TELEFONO` | 0.90 | no | sí | Mismo telefono normalizado a E.164 |
| `R04_EMAIL` | 1.1 | `EMAIL` | 0.90 | no | sí | Mismo correo normalizado |
| `R05_EVIDENCIA` | 1.0 | `EVIDENCIA` | 0.88 | no | sí | Mismo hash de archivo |
| `R06_IP_VENTANA` | 1.0 | `IP` | 0.72 | no | sí | Misma IP dentro de la ventana temporal del prestador. La IP se valora siempre junto con su fecha y hora |
| `R07_IP_SUELTA` | 1.0 | `IP` | 0.28 | sí | sí | Misma IP fuera de la ventana temporal: indicio, no atribucion |
| `R08_ALIAS` | 1.1 | `ALIAS` | 0.22 | sí | sí | Mismo nombre visible: refuerza, nunca sostiene solo |
| `R10_ALIAS_PAGO` | 1.1 | `ALIAS_PAGO` | 0.62 | no | sí | Misma via de cobro: mismo alias de pago normalizado |
| `R09_UBICACION` | 1.0 | `UBICACION` | 0.08 | sí | sí | Misma ciudad estimada: contexto, nunca sostiene solo |
| `R11_PHASH_SIMILAR` | 1.0 | `HASH_PERCEPTUAL` | 0.82 | no | no | Hashes perceptuales de imagen a distancia Hamming menor o igual al umbral; indica similitud visual, no archivo identico |
| `R12_HUELLA_AUDIO` | 1.0 | `HUELLA_AUDIO` | 0.86 | no | sí | Misma huella algoritmica de audio declarada |
| `R13_CONTEXTO_LUGAR` | 1.0 | `LUGAR_MENCION` | 0.12 | sí | no | Descripciones de lugar comparten al menos dos dimensiones de un vocabulario controlado; solo corrobora |

### Combinación

Noisy-OR sobre las reglas que disparan, **solo si al menos una sostiene el vínculo por sí sola**. El resultado es un puntaje de priorización no calibrado, aunque por compatibilidad el campo se llame `confidence`; no es una probabilidad. Puntaje máximo `0.99`.


### Discriminancia

- Hasta `df = 10` reportes, el identificador conserva su peso completo.
- Por encima, el peso decae logarítmicamente.
- Desde `df = 50` deja de poder sostener un vínculo solo.
- La expansión combinatoria se limita por cantidad de pares y por tipo; si supera el límite, se conserva como grupo compacto con todos sus reportes.
- La fracción sobre el corpus (`20 %`) recién se aplica con al menos 200 reportes: con un corpus chico engaña.

| Tipo | Máximo de pares antes de compactar |
|---|---:|
| `ALIAS` | 1500 |
| `ALIAS_PAGO` | 4000 |
| `CUENTA` | 10000 |
| `DISPOSITIVO` | 5000 |
| `EMAIL` | 5000 |
| `EVIDENCIA` | 7500 |
| `HASH_PERCEPTUAL` | 5000 |
| `HUELLA_AUDIO` | 5000 |
| `IP` | 2500 |
| `TELEFONO` | 5000 |
| `UBICACION` | 1000 |
| `_default` | 1000 |

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
- CGNAT **sin** puerto de origen: el peso se multiplica por `0.35` y la regla pasa a corroborar solamente. El módulo no presume atribución al abonado.
- CGNAT **con** puerto y timestamp: factor `0.85`, se conserva como señal sujeta a confirmación.
- Las fechas se manejan en UTC. Un valor sin zona horaria se marca como supuesto: tres horas de corrimiento alcanzan para atribuir una conexión al abonado equivocado.

## 7. Umbrales

| Umbral | Valor | Qué controla |
|---|---|---|
| `UMBRAL_PROPONER` | 0.55 | debajo de esto no se materializa la arista |
| `UMBRAL_PROBABLE` | 0.70 | franja media del puntaje interno |
| `UMBRAL_ALTA` | 0.90 | franja alta del puntaje interno |
| `UMBRAL_CLUSTER` | 0.70 | mínimo para agrupar en un legajo lógico y para emitir alertas |
