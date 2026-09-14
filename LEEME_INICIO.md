# Inicio y actualización

## Instalación

Usar una carpeta local con permiso de escritura y extraer el ZIP completo antes de iniciar. Se requiere Python de **64 bits, 3.12, 3.13 o 3.14**; 3.14.1 está excluido por NetworkX. La opción recomendada es 3.12.

En Windows: instalar Python con el lanzador `py` o la opción de agregar Python al PATH, y abrir `INICIAR_WINDOWS.bat`. En Linux o macOS: `python3 iniciar.py`.

El iniciador crea `.venv`, instala las tres dependencias fijadas en `requisitos.txt`, comprueba sus versiones y abre el navegador. No copiar `.venv` desde otra computadora. El navegador usa `http://127.0.0.1:8731/`. Mantener la consola abierta; detener con Ctrl+C.

Si el puerto está ocupado:

```bat
INICIAR_WINDOWS.bat --puerto 8732
```

También se pueden pasar `--sin-navegador` y `--puerto` a `python iniciar.py`. La opción `--puerto 0` elige un puerto disponible y muestra la dirección real. No abrir dos procesos sobre la misma carpeta de trabajo.

## Actualizar sin perder el trabajo

Cerrar la aplicación y conservar una copia de `grafo/entrada/` y `grafo/estado/`.

- **Copia con Git:** ejecutar `git pull --ff-only` y abrir el iniciador. Si Git informa cambios locales, conservarlos y resolver ese aviso antes de actualizar; no usar un reinicio forzado para descartarlos.
- **Copia ZIP:** extraer la versión nueva en otra carpeta. Copiar allí los JSON de `grafo/entrada/` y los dos libros propios de `grafo/estado/`, reemplazando únicamente los libros de demostración de la carpeta nueva. No concatenar cadenas JSONL. Conservar además cualquier dataset o manifiesto propio.

Si `.venv` proviene de un Python antiguo o de otra computadora, eliminar **solo `.venv`** y volver a iniciar con un Python admitido. El entorno se recrea; los reportes y las decisiones viven fuera de él. La reinstalación necesita Internet.

## Reportes y decisiones

En **Probar con otros reportes** se cargan JSON compatibles con el extractor. Se validan antes de guardarlos en `grafo/entrada/`. Un mismo `reportId` reemplaza su variante importada. Quitar una importación elimina esa variante; si había un reporte base con el mismo ID, vuelve a usarse el base.

`grafo/estado/validaciones.jsonl` conserva revisiones y `grafo/estado/vinculos_manuales.jsonl` conserva vinculaciones y reversiones. **Volver** navega por las fichas; no deshace esos registros.

Si aparece «La operación quedó guardada, pero no se pudo actualizar el visor», no repetir la decisión: cerrar y reiniciar para reconstruir. Si vuelve a fallar, conservar los archivos y el error de la consola.

## Reconstrucción por consola

Con el Python del entorno preparado:

```bash
python grafo/construir.py --datos reportes_sinteticos grafo/entrada --salida grafo/salida
```

Para trabajar solo con otro dataset, pasar únicamente esa carpeta a `--datos`. La ejecución directa del constructor genera salidas; abrir `grafo.html` como archivo permite consultar, pero para guardar decisiones hace falta el servidor local.

La aplicación es local y de un solo puesto. No incorpora autenticación institucional, permisos por caso ni acceso multiusuario.
