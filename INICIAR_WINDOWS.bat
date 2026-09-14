@echo off
setlocal
title Modulo de grafos y vinculaciones
cd /d "%~dp0"
if errorlevel 1 goto carpeta_inaccesible

if exist ".venv\Scripts\python.exe" goto entorno_existente
py -3.12 -c "import sys; sys.exit(not ((3, 12) <= sys.version_info[:2] < (3, 15) and sys.version_info[:3] != (3, 14, 1)))" >nul 2>&1
if not errorlevel 1 goto python312
py -3 -c "import sys; sys.exit(not ((3, 12) <= sys.version_info[:2] < (3, 15) and sys.version_info[:3] != (3, 14, 1)))" >nul 2>&1
if not errorlevel 1 goto python_py
python -c "import sys; sys.exit(not ((3, 12) <= sys.version_info[:2] < (3, 15) and sys.version_info[:3] != (3, 14, 1)))" >nul 2>&1
if not errorlevel 1 goto python_path
echo.
echo No se encontro Python 3.12, 3.13 o 3.14 compatible. Se recomienda Python 3.12.
echo Instala Python desde https://www.python.org/downloads/windows/
echo Marca "Add Python to PATH" y vuelve a abrir este archivo.
goto error

:entorno_existente
".venv\Scripts\python.exe" "iniciar.py" %*
goto resultado

:python312
py -3.12 "iniciar.py" %*
goto resultado

:python_py
py -3 "iniciar.py" %*
goto resultado

:python_path
python "iniciar.py" %*
goto resultado

:resultado
if errorlevel 1 goto error
exit /b 0

:carpeta_inaccesible
echo No se pudo abrir la carpeta de la aplicacion.
echo Extrae el ZIP en una carpeta local antes de iniciar.

:error
echo.
echo La aplicacion no pudo iniciarse. Revisa el mensaje anterior.
echo Puedes copiarlo para solicitar ayuda. No se borraron tus reportes ni tu historial.
pause
exit /b 1
