# Estado del módulo de grafos

Clasificación honesta de cada capacidad, según pide `CLAUDE.md` §20.7.
Nada de lo listado como **ausente** debe presentarse como disponible.

## 1. Qué existe hoy

| Capacidad | Estado | Dónde |
|---|---|---|
| Ontología versionada con separación observada/derivada/inferida | **implementada** | `src/ontologia.py` |
| Procedencia obligatoria por arista, con locator al campo de origen | **implementada** | `src/nucleo.py` |
| Hash de la fuente al ingerir | **implementada** | `nucleo.registrar_fuente` |
| Extracción de entidades desde el JSON de NCMEC | **implementada** | `src/extractor_ncmec.py` |
| Normalización de teléfono (E.164 AR), correo, IP, alias, tiempo | **implementada** | `src/normalizacion.py` |
| Vinculación entre reportes por reglas, con blocking | **implementada** | `src/resolucion.py` |
| Detección de posibles duplicados | **implementada** | `resolucion._indicios_de_duplicado` |
| Hipótesis de identidad sin fusión automática | **implementada** | `resolucion.proponer_identidades` |
| Unificación de identidades aprobada por una persona, reversible | **implementada** | `src/identidades.py`, `validar.py unificar` |
| Dossier crudo con el peso de cada vinculación y el aporte de cada regla | **implementada** | `src/dossier.py` |
| Seudonimización antes de enviar a un modelo, y restitución local | **implementada** | `dossier.seudonimizar` / `restituir` |
| Informe discursivo redactado por un modelo local | **implementada** | `informe_ia.py` |
| Redacción de respaldo sin ningún modelo | **implementada** | `informe_ia.py --sin-modelo` |
| Paneles plegables y redimensionables, tres niveles de detalle, tres disposiciones | **implementada** | `src/render_html.py` |
| Historial de navegación con volver y siguiente | **implementada** | `src/render_html.py` |
| Vista "por qué se vinculan": cadena completa entre dos reportes | **implementada** | `render_html._camino`, `dispPorQue` |
| Visor acotado al caso en curso, con selector de caso | **implementada** | `render_html._casos`, `conjuntoVisible` |
| Lienzo en árbol: reporte en análisis, reportes vinculados y datos, con conectores en ángulo recto rotulados | **implementada** | `render_html`, función `dibujar` |
| Apertura por reporte, con líneas de color hacia los otros reportes que comparten el dato | **implementada** | `render_html`, función `dibujar` |
| Colapso visual de aristas paralelas, informando en cuántos reportes constan | **implementada** | `GRUPO` / `MIEMBROS` en `aplicar` |
| Informe en prosa, uno por caso, embebido en el visor y descargable | **implementada** | `dossier.recortar`, `src/redaccion.py` |
| Panel de filtros: buscar, peso mínimo, tipos de dato, solo datos compartidos | **implementada** | `src/render_html.py` |
| Criterio único de línea: el trazo dice el origen, el color dice el tipo de dato | **implementada** | `render_html.COLOR_VISOR`, hoja de estilos |
| Foco por dato o por vinculación: apaga lo que no interviene, y el segundo clic lo devuelve | **implementada** | `render_html`, `alternarFoco` |
| Cajas movibles de a una, con los conectores recalculados | **implementada** | `render_html.arrastrable` |
| Un dato puesto en el centro: el árbol se cuelga de él | **implementada** | `render_html.centrarEn` |
| Coincidencias evaluadas que no alcanzaron, visibles en el lienzo y en la ficha | **implementada** | `render_html`, campo `descartados` |
| Contra-evidencia por desplazamiento implausible | **implementada** | `resolucion.detectar_contradicciones` |
| Alertas de reapertura tipadas por motivo de archivo | **implementada** | `src/alertas.py` |
| Componentes, comunidades (Louvain), centralidades, puentes | **implementada** | `src/analisis.py` |
| Baseline de link prediction (Adamic-Adar) sin materializar aristas | **implementada** | `analisis.candidatos_de_enlace` |
| Libro append-only de validaciones encadenado por hash | **implementada** | `src/validacion.py` |
| Re-aplicación de decisiones humanas tras reconstruir | **implementada** | `validacion.aplicar` |
| Visor interactivo con filtros y foco progresivo | **implementada** | `src/render_html.py` |
| Informe con trazabilidad a la fuente | **implementada** | `src/informe.py` |
| Pruebas de invariantes | **implementada** | `pruebas.py` |

## 2. Qué está simplificado a propósito

| Simplificación | Consecuencia | Qué haría falta |
|---|---|---|
| Todo en memoria, con `networkx` | No escala más allá de decenas de miles de nodos | Evaluar JanusGraph o similar recién con volúmenes reales medidos |
| Estado institucional como sidecar JSON | No hay transaccionalidad ni concurrencia | Integración con la base transaccional (PostgreSQL) |
| El libro de validaciones es un archivo local | Detecta modificación de registros previos, **no** impide reescribir el archivo entero, ni sella el tiempo | Almacenamiento append-only del lado del servidor o anclaje externo |
| Sin control de acceso | Cualquiera que corra el script ve todo | Permisos por rol, caso, jurisdicción y sensibilidad |
| El informe del visor se redacta con plantillas | Texto correcto pero rígido. Además la versión que redacta `informe_ia.py` no llega al visor: escribe el informe general, no los de cada caso | Un modelo local vía `informe_ia.py`, y decidir si redacta uno por caso |
| La unificación de identidades se aprueba por CLI | No hay botón en la interfaz | Un control en el visor, cuando exista la aplicación con sesión de usuario |
| Visor propio en SVG, con disposición en árbol calculada a mano | Alcanza y se lee bien para un caso. Los reportes vinculados van todos en una fila: con más de siete u ocho el lienzo se vuelve tan ancho que deja de leerse | Un algoritmo de dibujo por capas con ruteo de aristas, o una librería especializada |
| La legibilidad del lienzo se verifica midiendo rectángulos en pantalla desde la consola | Es una auditoría manual, no una prueba automática | Llevarla a `pruebas.py` con un navegador headless |
| Ventanas temporales de IP por prestador, estimadas | El supuesto viaja en la explicación de cada arista, pero no está verificado | Confirmar tiempos de lease con cada prestador |

## 3. Qué está ausente

- Extracción desde el PDF estandarizado y desde XML (hoy solo JSON).
- Cualquier procesamiento multimodal: imagen, audio, video, OCR, transcripción.
- Embeddings y búsqueda semántica.
- GNN. Existe el baseline determinista contra el cual compararla; el modelo no.
- Vínculo entre oficios y respuestas de prestadores (`RESPONDE_A` está en el
  vocabulario, sin implementación: falta definir el formato de las respuestas).
- Nodos `SEGMENTO`: declarados en la ontología, todavía sin productor.
- Clasificación jurisdiccional y derivación territorial: se sacaron del
  circuito por decisión del proyecto. `src/jurisdiccion.py` quedó sin conectar.
- Integración con SIPAR y con KIWI: fuera del alcance del piloto.
- Métricas de evaluación contra un ground truth. Hoy hay invariantes, no
  precisión ni recall: no existe todavía un conjunto de vínculos validados por
  especialistas contra el cual medir.

## 4. Observaciones sobre la lógica previa

Puntos donde el diseño se apartó del enfoque más directo, con el motivo.

1. **La ponderación por rareza no puede medirse como fracción del corpus.**
   Un primer intento degradaba a "solo corrobora" cualquier identificador
   presente en más del 20 % de los reportes. Con 10 reportes de prueba, un
   dispositivo compartido por 4 quedaba degradado y se perdía un vínculo
   legítimo entre un caso de CABA y uno de provincia. La rareza de un
   identificador es una propiedad suya, no del tamaño de la base: ahora el
   umbral es absoluto (`df`), y la fracción recién se aplica con corpus grande.

2. **El identificador de arista debe incluir la fuente.** Sin eso, dos reportes
   que afirman lo mismo desde el mismo campo (`reportedPersons[0]...`) colapsan
   en una sola arista y se pierde evidencia. Es un error silencioso: el grafo
   queda plausible pero incompleto. Se detectó porque la clasificación
   jurisdiccional del reporte real daba `INDETERMINADA` teniendo geolookup.

3. **Una alerta de reapertura no se justifica por la existencia del vínculo.**
   Lo que la justifica es que el reporte nuevo aporte *lo que le faltaba* al
   archivado. Un vínculo por dispositivo no resuelve un archivo por jurisdicción
   indeterminada. Por eso el motivo de archivo es un campo de primera clase y
   cada motivo declara qué aporte lo reactiva. Los vínculos que no califican se
   registran como silenciados, no se descartan sin dejar rastro.

4. **Con CGNAT, el puerto de origen es tan necesario como la IP.** El reporte
   real trae `port: 19096` y ese campo suele ignorarse. Sin puerto y timestamp
   exacto, el prestador no puede identificar al abonado: la regla se degrada y
   el caso queda `PENDIENTE_NAT` en lugar de derivarse mal.

5. **La unificación de identidades tenía que existir, pero como decisión y no
   como cálculo.** Sin ella el grafo acumula una mención de persona por reporte
   y se vuelve ilegible. Con fusión automática, un error de atribución se
   propaga sin dejar rastro. La salida es que el sistema proponga, una persona
   apruebe, y la unificación sea una capa por encima de las menciones —nunca un
   reemplazo—, de modo que revertir la decisión deshaga la identidad sola.

6. **Zona horaria.** NCMEC informa en UTC; las respuestas de prestadores
   argentinos suelen venir en hora local. Tres horas de corrimiento alcanzan
   para atribuir una conexión al abonado equivocado. Toda fecha sin zona horaria
   se marca como supuesto en la explicación de la arista.

7. **El grafo necesita aristas que debiliten, no solo que acumulen.** Un grafo
   que solo suma coincidencias tiende a confirmar la hipótesis inicial. Por eso
   se modela `CONTRADICE`: dos observaciones de la misma cuenta a 1.290 km en
   media hora no invalidan nada por sí solas, pero debilitan la atribución a una
   persona y pueden indicar VPN, cuenta compartida o geolookup erróneo.

8. **Los descartes se informan.** Cada par evaluado y no vinculado aparece en el
   informe con su motivo. Un descarte silencioso se lee como "no había nada".

## 5. Qué falta para que sea una secuencia de trabajo completa

El visor ya es del caso, no del archivo. Lo que todavía no existe es el resto
del circuito alrededor de esa unidad:

- **Entrada por caso.** Hoy el caso se elige en un selector. En la aplicación
  debería llegar desde el sistema que asigna trabajo, con el caso ya abierto.
- **Estado de avance dentro del caso.** No hay noción de "qué me falta revisar":
  la cola de validación es global, no por caso.
- **Cierre del caso.** No hay una acción que registre que el operador terminó de
  revisarlo y con qué conclusión.
- **Vuelta al archivo general.** Cuando el operador valida o rechaza, eso debería
  impactar en el archivo y eventualmente reabrir otros casos. Hoy el efecto
  existe —el libro se re-aplica— pero no hay aviso de qué otros casos cambiaron.

## 6. Próximo paso sugerido

Antes de sumar capas: **validar la ontología y las reglas con los operadores**.
Concretamente, sentarse con una muestra de reportes reales ya trabajados y
verificar:

- si los vínculos que el sistema propone son los que un operador habría hecho;
- si las alertas de reapertura le resultan accionables o ruido;
- si las ventanas temporales de IP por prestador son correctas;
- si el motivo de archivo se registra hoy de forma estructurada, porque toda la
  lógica de reapertura depende de eso. Si hoy es texto libre, ese es el primer
  cambio a pedir en SIPAR.

Eso produce el conjunto validado que hoy falta y sin el cual no se puede medir
precisión ni entrenar nada.
