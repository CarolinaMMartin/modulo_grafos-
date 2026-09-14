"""Prepara un entorno aislado con versiones verificadas e inicia el visor local."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

RAIZ = Path(__file__).resolve().parent
ENTORNO = RAIZ / '.venv'
PYTHON = ENTORNO / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
REQUISITOS = RAIZ / 'requisitos.txt'
MARCA = ENTORNO / '.requisitos.sha256'
SERVIDOR = RAIZ / 'grafo' / 'servidor.py'


def python_admitido(version):
    return (3, 12) <= tuple(version[:2]) < (3, 15) and tuple(version[:3]) != (3, 14, 1)


def ejecutar(argumentos):
    return subprocess.run(argumentos, cwd=str(RAIZ), check=False).returncode


def requisitos_fijados():
    versiones = {}
    for linea in REQUISITOS.read_text(encoding='utf-8').splitlines():
        linea = linea.partition('#')[0].strip()
        if not linea:
            continue
        nombre, separador, version = linea.partition('==')
        if not separador or not nombre or not version:
            raise ValueError('Cada dependencia debe declarar su version exacta: '+linea)
        versiones[nombre] = version
    return versiones


def dependencias_correctas():
    # No basta con importar: una .venv antigua puede importar versiones distintas.
    codigo = ('import importlib.metadata as m; import networkx,numpy,scipy; '
              'import json,sys; esperado=json.loads(sys.argv[1]); '
              'sys.exit(0 if all(m.version(k)==v for k,v in esperado.items()) else 1)')
    res = subprocess.run([str(PYTHON), '-c', codigo, json.dumps(requisitos_fijados())],
                         cwd=str(RAIZ), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, check=False)
    return res.returncode == 0


def main():
    if not python_admitido(sys.version_info) or sys.maxsize <= 2**32:
        print('Use Python 3.12, 3.13 o 3.14 de 64 bits (excepto 3.14.1).')
        print('Se recomienda Python 3.12. Las dependencias actuales requieren al menos 3.12.')
        return 1
    if not REQUISITOS.is_file() or not SERVIDOR.is_file():
        print('Faltan archivos. Extraiga o descargue la aplicacion completa.')
        return 1
    if not PYTHON.is_file():
        print('Preparando el entorno de Python...', flush=True)
        venv.EnvBuilder(with_pip=True).create(str(ENTORNO))
    comprobar_python = subprocess.run(
        [str(PYTHON), '-c', 'import json,sys; print(json.dumps(list(sys.version_info[:3])))'],
        capture_output=True, text=True, check=False)
    try:
        compatible = comprobar_python.returncode == 0 and python_admitido(json.loads(comprobar_python.stdout))
    except (ValueError, TypeError):
        compatible = False
    if not compatible:
        print('El entorno .venv usa un Python incompatible o dejo de funcionar.')
        print('Cierre la aplicacion, elimine solo .venv y vuelva a iniciar con Python 3.12.')
        print('Conserve grafo/entrada y grafo/estado: contienen sus reportes y decisiones.')
        return 1
    huella = hashlib.sha256(REQUISITOS.read_bytes()).hexdigest()
    instalada = MARCA.read_text(encoding='ascii').strip() if MARCA.is_file() else ''
    if instalada != huella or not dependencias_correctas():
        print('Instalando las versiones verificadas. Este paso necesita Internet.', flush=True)
        codigo = ejecutar([str(PYTHON), '-m', 'pip', 'install', '--disable-pip-version-check',
                           '--only-binary=:all:', '-r', str(REQUISITOS)])
        if codigo or not dependencias_correctas():
            print('La instalacion no se completo. Revise el error anterior y su conexion.')
            return codigo or 1
        MARCA.write_text(huella+'\n', encoding='ascii')
    if ejecutar([str(PYTHON), '-m', 'pip', 'check']):
        print('El entorno contiene dependencias incompatibles. Recree solo .venv.')
        return 1
    print('Iniciando la aplicacion. Deje esta ventana abierta; Ctrl+C para detener.', flush=True)
    return ejecutar([str(PYTHON), '-u', str(SERVIDOR)] + sys.argv[1:])


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nAplicacion detenida.')
        sys.exit(0)
    except (OSError, ValueError) as error:
        print('No se pudo preparar o iniciar la aplicacion: %s' % error)
        print('Use una carpeta local con permiso de escritura. Sus reportes y decisiones se conservan.')
        sys.exit(1)
