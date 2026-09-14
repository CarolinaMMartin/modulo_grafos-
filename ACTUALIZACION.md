# Actualización del módulo integrado

## Navegación de la barra lateral

- «‹ Volver» recupera la ficha y el lienzo anteriores, con tarjetas desplegadas,
  posiciones, centro del análisis, zoom y desplazamiento del grafo.
- Recupera también las secciones abiertas y la posición de lectura de la ficha.
- «Siguiente ›» permite avanzar de nuevo. Ambos botones comparten el historial
  con la barra superior y los atajos Alt + flecha izquierda/derecha.
- La barra de navegación permanece visible al desplazarse por el detalle.
- Volver cambia la vista; las validaciones y vínculos guardados siguen vigentes.

## Integración

Se incorporó la versión completa entregada anteriormente: diseño claro/oscuro,
tipografía sin serif, revisión de relaciones, importación validada, información
de origen legible, mejoras del lienzo y módulos de multimedia y contexto de lugar.
Se conservan los reportes, las validaciones y los vínculos manuales del repositorio.
El inicio en Windows está en `INICIAR_WINDOWS.bat`; instrucciones en `LEEME_INICIO.md`.

## Verificación reproducible

Con las dependencias de `requisitos.txt` instaladas, desde la carpeta principal:

```sh
python grafo/pruebas.py
python grafo/pruebas_revision.py
python grafo/pruebas_importacion.py
node grafo/pruebas_navegacion.js
node grafo/pruebas_lienzo.js
```

Resultados: 153 invariantes correctos, 4 pruebas de revisión y 4 de importación
correctas. Las dos comprobaciones JavaScript pasan con las funciones reales del
visor y un DOM mínimo: historial y cámara, navegación lateral, secciones y scroll,
marca del dato, interacción por teclado, realce de reportes y prestador vigente.
Node solo se necesita para estas comprobaciones, no para iniciar la aplicación.

Las pruebas de escritura usan copias temporales. Se verificó la generación del
HTML y la sintaxis de sus scripts. Esta verificación no incluye una ejecución
visual en navegador ni una ejecución nativa en Windows.
