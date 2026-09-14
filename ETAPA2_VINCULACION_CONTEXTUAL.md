# Desarrollo siguiente · Etiquetado y vinculación contextual

Este documento conserva el trabajo futuro relacionado con el módulo actual. **No describe funciones ya instaladas.** El objetivo es recuperar antecedentes que merecen revisión cuando los identificadores exactos no alcanzan, y evaluar si el aprendizaje sobre grafos mejora ese trabajo.

## Punto de partida comprobable

Ya existen el grafo con procedencia, reglas deterministas, candidatos Adamic–Adar sobre identificadores compartidos, textos retenidos, similitud controlada de lugares y registros de decisiones humanas. Los eventos positivos que revisan los operadores pueden alimentar un conjunto etiquetado futuro; el módulo todavía no exporta ese conjunto ni entrena modelos.

No hay búsqueda por embeddings, infraestructura vectorial, corpus de evaluación congelado, pipeline de entrenamiento ni GNN ejecutándose. No se agregan librerías para esas funciones hasta seleccionar e implementar un experimento verificable.

## 1. Convertir decisiones en etiquetas utilizables

La unidad de anotación debe especificar **qué se está afirmando**. Una vinculación útil para investigar, una hipótesis de misma persona, un posible duplicado y una coincidencia de material son preguntas diferentes.

| Registro disponible | Uso posible | Revisión necesaria |
|---|---|---|
| Validación humana de una vinculación | Positivo para la pregunta y evidencia revisadas | Identificar evento, par, fundamento y versión de las reglas |
| Vínculo afirmado por operador | Positivo de asociación operativa | No convertirlo automáticamente en misma persona o mismo hecho |
| Rechazo fundamentado | Posible negativo de la propuesta concreta | Distinguir «falso» de «datos insuficientes» o «atribución incorrecta» |
| Relación pendiente, en revisión o par sin enlace | Sin etiqueta definitiva | No usar como negativo confirmado |
| Relación observada con estado inicial `validada` | Dato de entrada | No tratar como un evento de validación humana |
| Reversión posterior | Actualización de la etiqueta vigente | Conservar ambos eventos, su fecha y el estado a la fecha del corte |

Trabajo pendiente: guía de anotación por tipo de relación, exportador reproducible, doble revisión de una muestra y resolución de desacuerdos. El exportador debe incluir IDs de reportes y arista, pregunta, etiqueta, operador, fundamento, locator, hashes de fuentes, fechas del hecho y de la decisión, versiones y estado de revisión al corte. Los campos nuevos requieren un contrato explícito; no se simulan con valores inventados.

Se debe separar un rechazo por falta de evidencia de una contradicción confirmada. Si solo hay positivos confiables y pares sin revisar, la evaluación debe reconocer ese escenario; no fabricar negativos por ausencia de aristas.

## 2. Construir una evaluación antes del modelo

Congelar el corpus, las etiquetas y las particiones por fecha y grupos relacionados. Evitar que duplicados, identidades consolidadas o el mismo material crucen entrenamiento y prueba de una forma que revele la respuesta. El grafo usado para predecir debe contener solo información disponible en ese momento; las aristas y decisiones futuras no pueden ser variables de entrada.

Comparar reglas y candidatos Adamic–Adar con recuperación textual simple. Medir precisión y recuperación entre los primeros resultados, carga de revisión y desempeño por plataforma, cobertura de datos y tipo de vínculo. La recuperación solo es interpretable en la parte del conjunto donde se conocen las relaciones relevantes. Fijar criterios de aceptación con resultados del corpus, sin prometer una precisión ni cantidad mínima de ejemplos sin medición.

## 3. Recuperación contextual explicable

La siguiente capacidad a evaluar es recuperar reportes por fragmentos relevantes de texto y combinar esa señal con coincidencias estructurales. Cada resultado debe citar fragmento, reporte y ubicación de origen. La similitud de relato, lugar o modo de actuar no prueba identidad.

Primero establecer una referencia léxica; después comparar embeddings adecuados al idioma y al material. Seleccionar modelos, índices y almacenamiento a partir de evaluación local y restricciones de acceso. No hay una base vectorial ni modelo previamente adoptado por el código actual.

Criterio para incorporarlo: mejor recuperación de antecedentes útiles o menor esfuerzo de revisión que las referencias existentes, con resultados reproducibles y explicaciones inspeccionables. El ranking debe entrar como propuesta para revisión, sin convertir el puntaje en probabilidad mientras no exista calibración evaluada.

## 4. Experimento con redes neuronales de grafos, GNN

Una GNN puede combinar atributos de un reporte con información de su vecindario: cuentas, dispositivos, evidencias y reportes conectados. Esto podría priorizar pares que resulten difíciles para reglas aisladas. Es una hipótesis que debe medirse, no una mejora garantizada.

El grafo es heterogéneo: el tipo y origen de cada relación importa. Un modelo relacional, por ejemplo una R-GCN como candidato experimental, podría aprender transformaciones distintas por relación. No se fija esa arquitectura ni se incorpora PyTorch u otra biblioteca sin el experimento y el corpus correspondientes.

Trabajo necesario:

1. Construir una representación versionada del grafo con atributos disponibles al corte; excluir decisiones o enlaces que revelen la etiqueta objetivo.
2. Diseñar el muestreo según positivos confirmados, negativos revisados y pares sin etiqueta. Separar las preguntas de identidad, asociación, duplicado y material.
3. Comparar una GNN pequeña con reglas, Adamic–Adar y recuperación contextual sobre la **misma evaluación**. Medir también costo, latencia y errores por grupo.
4. Explicar propuestas mediante vecinos, relaciones y fragmentos de soporte. La atribución del modelo no se presenta como prueba causal.
5. Incorporar el modelo solo si mejora de forma medible el trabajo de revisión. En caso contrario, mantener la referencia que funcione mejor.

Cada experimento debe registrar versiones, semillas, parámetros, hashes del conjunto y del grafo, particiones y resultados. Antes de integrar hipótesis aprendidas hacen falta un contrato para su procedencia y un mecanismo para retirarlas por versión sin perder observaciones ni decisiones.

## 5. Integración y seguimiento

Las propuestas aprendidas deben ser distinguibles de los datos observados, conservar su método y versión, y usar el circuito de revisión. Las decisiones de revisión pueden aportar nuevos ejemplos; para controlar el sesgo de realimentación hace falta una muestra revisada sin mostrar previamente el puntaje.

La validación con datos reales debe preceder a cualquier exposición multiusuario. La aplicación actual no tiene autenticación ni permisos institucionales, y los textos y vectores necesitan el mismo control de acceso que sus fuentes. Este trabajo de integración no se da por resuelto por utilizar un servidor HTTP local.

El orden de avance es: **etiquetas y evaluación → recuperación contextual → experimento GNN → integración si mejora**. No hay resultados de entrenamiento ni métricas de modelos que puedan documentarse como realizadas hoy.
