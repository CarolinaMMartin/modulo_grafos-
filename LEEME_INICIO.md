# Inicio en Windows

1. Extraé el ZIP completo en una carpeta local. No abras la aplicación desde el ZIP.
2. Hacé doble clic en **INICIAR_WINDOWS.bat**. Usa tu Python instalado; se recomienda **Python 3.12**. Si falta Python, el iniciador te lo indica.
3. La primera vez se prepara un entorno `.venv` y se descargan las dependencias: necesitás Internet para ese paso. Los siguientes inicios funcionan localmente, sin descargar otra vez mientras no cambien los requisitos.
4. Se abre el navegador con la aplicación. Dejá la consola abierta mientras trabajás. Para detenerla, presioná **Ctrl+C** en esa consola. Cerrar solamente la pestaña no detiene el servidor.

La dirección local aparece en la consola; el puerto habitual es **8731**. Si el navegador no se abre, copiá esa dirección en Chrome o Edge. No se necesita ejecutar como administrador.

## Conservar tu trabajo

Los reportes locales están en **grafo/entrada** y el historial de validaciones y vínculos manuales está en **grafo/estado**. El iniciador no borra ni reemplaza esas carpetas.

Si venís de otra copia de la aplicación, cerrala y guardá una copia de seguridad. Antes del primer inicio, copiá sus carpetas **grafo/entrada** y **grafo/estado** completas a las mismas ubicaciones de esta versión. Si ya usaste ambas copias, guardá las dos: reemplazar archivos del mismo nombre puede hacerte perder cambios.

Si movés la aplicación a otra carpeta o equipo y Python deja de funcionar, eliminá únicamente **.venv** y volvé a abrir **INICIAR_WINDOWS.bat**. Esto reinstala las dependencias y requiere Internet; conservá **grafo/entrada** y **grafo/estado**.

## Si aparece un error

La consola queda abierta para que puedas leer o copiar el mensaje. Verificá que extrajiste todo el ZIP y que la carpeta permite guardar archivos. Si falla la instalación de dependencias, revisá la conexión y reintentá.

Para un inicio manual, desde una terminal situada en la carpeta de la aplicación: `py -3 iniciar.py`. Podés añadir `--sin-navegador` o `--puerto 8732`.

El lanzador está preparado para Windows. Las pruebas realizadas en el entorno de entrega no sustituyen una ejecución nativa en Windows.
