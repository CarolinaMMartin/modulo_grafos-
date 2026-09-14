<!-- Generado por python grafo/documentar.py; no editar las tablas a mano. -->

# Parámetros de la implementación

Referencia del código actual. Los pesos no están calibrados. No es una probabilidad el valor del campo `confidence`: es un puntaje de reglas. El funcionamiento y los contratos están en [DOCUMENTACION_TECNICA.md](../DOCUMENTACION_TECNICA.md).

## Versiones de métodos

| Módulo | Versión |
|---|---|
| ontologia | 0.4.0 |
| resolucion | 1.4 |
| extractor_ncmec | 1.4 |
| identidades | 1.1 |
| analisis | 1.3 |
| normalizacion | 1.0 |
| multimedia | 1.0 |
| contexto_lugar | 1.0 |
| léxico de lugares | 1.0 |
| alertas | 2.0 |

## Reglas de coincidencia

El peso efectivo puede reducirse por frecuencia, procedencia textual o condiciones de IP. Una regla que solo corrobora no puede sostener la propuesta por sí sola.

| Regla | Tipo | Peso base | Solo corrobora | Rareza | Versión | Coincidencia |
|---|---|---|---|---|---|---|
| `R01_CUENTA` | CUENTA | 0,98 | no | no | 1.0 | Misma cuenta: mismo ESP y mismo espUserId |
| `R02_DISPOSITIVO` | DISPOSITIVO | 0,92 | no | sí | 1.0 | Mismo identificador de dispositivo |
| `R03_TELEFONO` | TELEFONO | 0,90 | no | sí | 1.1 | Mismo telefono normalizado a E.164 |
| `R04_EMAIL` | EMAIL | 0,90 | no | sí | 1.1 | Mismo correo normalizado |
| `R05_EVIDENCIA` | EVIDENCIA | 0,88 | no | sí | 1.0 | Mismo hash de archivo |
| `R06_IP_VENTANA` | IP | 0,72 | no | sí | 1.0 | Misma IP dentro de la ventana temporal del prestador. La IP se valora siempre junto con su fecha y hora |
| `R07_IP_SUELTA` | IP | 0,28 | sí | sí | 1.0 | Misma IP fuera de la ventana temporal: indicio, no atribucion |
| `R08_ALIAS` | ALIAS | 0,22 | sí | sí | 1.1 | Mismo nombre visible: refuerza, nunca sostiene solo |
| `R10_ALIAS_PAGO` | ALIAS_PAGO | 0,62 | no | sí | 1.1 | Misma via de cobro: mismo alias de pago normalizado |
| `R09_UBICACION` | UBICACION | 0,08 | sí | sí | 1.0 | Misma ciudad estimada: contexto, nunca sostiene solo |
| `R11_PHASH_SIMILAR` | HASH_PERCEPTUAL | 0,82 | no | no | 1.0 | Hashes perceptuales de imagen a distancia Hamming menor o igual al umbral; indica similitud visual, no archivo identico |
| `R12_HUELLA_AUDIO` | HUELLA_AUDIO | 0,86 | no | sí | 1.0 | Misma huella algoritmica de audio declarada |
| `R13_CONTEXTO_LUGAR` | LUGAR_MENCION | 0,12 | sí | no | 1.0 | Descripciones de lugar comparten al menos dos dimensiones de un vocabulario controlado; solo corrobora |

## Umbrales de vinculación

| Constante | Valor |
|---|---|
| `UMBRAL_PROPONER` | 0,55 |
| `UMBRAL_PROBABLE` | 0,70 |
| `UMBRAL_ALTA` | 0,90 |
| `UMBRAL_CLUSTER` | 0,70 |
| `CONFIANZA_MAXIMA` | 0,99 |

## Frecuencia y expansión de pares

| Constante | Valor |
|---|---|
| DF_PLENA_DISCRIMINANCIA | 10 |
| DF_HUB_ABSOLUTO | 50 |
| FRACCION_BAJA_DISCRIMINANCIA | 0.2 |
| CORPUS_MINIMO_PARA_FRACCION | 200 |

| Tipo | Pares máximos |
|---|---|
| ALIAS | 1500 |
| ALIAS_PAGO | 4000 |
| CUENTA | 10000 |
| DISPOSITIVO | 5000 |
| EMAIL | 5000 |
| EVIDENCIA | 7500 |
| HASH_PERCEPTUAL | 5000 |
| HUELLA_AUDIO | 5000 |
| IP | 2500 |
| TELEFONO | 5000 |
| UBICACION | 1000 |
| _default | 1000 |

## Direcciones IP

Los plazos siguientes son estimados y no están verificados con los prestadores. Son ventanas de la regla; no establecen titularidad ni duración real de una asignación.

| Prestador normalizado | Horas |
|---|---|
| _default | 24 |
| telecentro | 24 |
| telecom argentina | 24 |
| telefonica de argentina | 24 |
| claro | 12 |
| personal | 12 |
| movistar | 12 |

| Condición | Valor |
|---|---|
| Rango CGNAT | 100.64.0.0/10 |
| Factor sin puerto | 0,35 |
| Factor con puerto | 0,85 |

## Identidad, texto y contradicciones

| Constante | Valor |
|---|---|
| FACTOR_TEXTO_LIBRE | 0,85 |
| CONFIANZA_MISMA_IDENTIDAD | 0,85 |
| CONFIANZA_CONTRADICCION | 0,70 |
| DISTANCIA_MINIMA_KM | 50,00 |
| VELOCIDAD_IMPOSIBLE_KMH | 900,00 |

## Comparación multimedia y de lugares

| Parámetro | Valor |
|---|---|
| pHash: bits | 64 |
| Distancia Hamming máxima | 8 |
| Bloques del índice pHash | 9 |
| Similitud mínima de lugar | 0.45 |
| Peso de extracción de lugar | 0.72 |
| Dimensiones mínimas compartidas | 2 |
| Dimensiones de anclaje | estructura, rasgo, referencia |

| Dimensión de lugar | Peso |
|---|---|
| acceso | 0.08 |
| color | 0.12 |
| estructura | 0.3 |
| rasgo | 0.25 |
| referencia | 0.25 |

## Alertas por motivo de archivo

Se propone revisar un antecedente: no se reabre una actuación automáticamente. La alerta exige un vínculo vigente suficiente y un aporte que responda al motivo de archivo.

| Motivo | Aportes que se buscan | Prioridad |
|---|---|---|
| sin_datos_de_usuario | un identificador que permite individualizar | alta |
| no_atribuible_nat | un identificador que permite individualizar; una dirección IP atribuible, con fecha y hora | alta |
| sin_archivos | un archivo identificado por su hash | alta |
| sin_ubicacion | un dato de ubicación utilizable; una dirección IP atribuible, con fecha y hora | media |
| material_sin_relevancia | su condición de actuación con mérito para avanzar; un archivo identificado por su hash | media |
| _default | un identificador que permite individualizar; un archivo identificado por su hash; una dirección IP atribuible, con fecha y hora; su condición de actuación con mérito para avanzar | media |

| Grupo de estados | Valores |
|---|---|
| Archivados o pendientes | archivado, archivado_latente, pendiente |
| Activos | derivado, en_analisis, en_investigacion, judicializado |

## Parámetros de análisis

| Parámetro | Valor |
|---|---|
| Semilla de Louvain | 7 |
| Intermediación: nodos máximos | 3000 |
| PageRank: nodos máximos | 20000 |
| Resultados por centralidad | 10 |
| Candidatos Adamic–Adar | 15 |

La omisión de una métrica por tamaño se declara en `centralidades.omitidas`. Los puentes se recortan a la cantidad configurada, sin ranking de importancia. El método real de comunidades se conserva en `algoritmo` y los errores de la alternativa en `aviso_fallback`.
