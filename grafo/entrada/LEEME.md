# Banco de pruebas

Todo archivo `.json` que se deje en esta carpeta se ingiere junto con el
dataset de `reportes_sinteticos/`, y se procesa con las mismas reglas.

Sirve para probar los algoritmos con otros reportes sin tocar el dataset del
proyecto.

## Dos formas de usarla

Copiar los archivos acá y reconstruir:

```bash
python grafo/construir.py
```

O, con el visor abierto, el botón **Probar con otros reportes** del panel
izquierdo: los sube, los valida y reconstruye sin salir de la pantalla.

## Qué se valida al importar

Lo mínimo para que el extractor no falle: que sea un JSON, que sea un objeto y
que traiga `reportId`. Lo que falte adentro lo tolera el extractor, y el visor
lo muestra como lo que es —un reporte con pocos datos—, que también es un caso
que vale la pena probar.

El archivo se guarda con el nombre `<reportId>.json`, no con el nombre con que
vino. Si ya había un reporte con ese número, lo reemplaza y el visor lo avisa.

## Sobre los datos

**Esta carpeta está fuera del repositorio.** Puede terminar acá un reporte
real, y esos no se versionan. Si alguno tiene que compartirse, antes pasa por
`redactar_reporte.py`, que le quita el texto libre y los datos de contacto y
conserva los identificadores técnicos.

Para vaciar el banco de pruebas alcanza con borrar los `.json` de esta carpeta.
