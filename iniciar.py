"""Instala dependencias en un entorno aislado e inicia el servidor local."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv


RAIZ = Path(__file__).resolve().parent
ENTORNO = RAIZ / ".venv"
PYTHON = ENTORNO / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUISITOS = RAIZ / "requisitos.txt"
MARCA = ENTORNO / ".requisitos.sha256"
SERVIDOR = RAIZ / "grafo" / "servidor.py"


def ejecutar(argumentos):
    return subprocess.run(argumentos, cwd=str(RAIZ), check=False).returncode


def main():
    if sys.version_info < (3, 8):
        print("Se necesita Python 3.8 o superior. Se recomienda Python 3.12.")
        return 1
    if not REQUISITOS.is_file() or not SERVIDOR.is_file():
        print("Faltan archivos. Extrae el ZIP completo antes de iniciar.")
        return 1

    if not PYTHON.is_file():
        print("Preparando el entorno de Python (solo la primera vez)...", flush=True)
        venv.EnvBuilder(with_pip=True).create(str(ENTORNO))

    huella = hashlib.sha256(REQUISITOS.read_bytes()).hexdigest()
    instalada = MARCA.read_text(encoding="ascii").strip() if MARCA.is_file() else ""
    comprobacion = subprocess.run(
        [str(PYTHON), "-c", "import networkx, numpy, scipy"],
        cwd=str(RAIZ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    if instalada != huella or comprobacion.returncode != 0:
        print("Instalando dependencias. Este paso necesita conexion a Internet.", flush=True)
        codigo = ejecutar([
            str(PYTHON), "-m", "pip", "install", "--disable-pip-version-check",
            "-r", str(REQUISITOS),
        ])
        if codigo != 0:
            print("La instalacion no termino. Revisa tu conexion y vuelve a iniciar.")
            return codigo
        if ejecutar([str(PYTHON), "-c", "import networkx, numpy, scipy"]) != 0:
            print("Las dependencias no se pudieron cargar. Revisa el error anterior.")
            return 1
        MARCA.write_text(huella + "\n", encoding="ascii")

    print("Iniciando la aplicacion local. Deja esta ventana abierta.", flush=True)
    print("Para detenerla, presiona Ctrl+C en esta ventana.", flush=True)
    return ejecutar([str(PYTHON), "-u", str(SERVIDOR)] + sys.argv[1:])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAplicacion detenida.")
        sys.exit(0)
    except OSError as error:
        print("No se pudo preparar o iniciar la aplicacion: %s" % error)
        print("Usa una carpeta local donde tengas permiso de escritura.")
        print("Si moviste la aplicacion de equipo o carpeta, elimina solo .venv y reintenta.")
        sys.exit(1)
