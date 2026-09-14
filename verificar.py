"""Comprobaciones reproducibles del modulo sin modificar sus datos de trabajo."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

RAIZ = Path(__file__).resolve().parent


def ejecutar(*args):
    print('\nEjecutando: '+' '.join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], cwd=RAIZ, check=True)


def enlaces_locales():
    documentos = list(RAIZ.glob('*.md'))
    for carpeta in ['docs', 'reportes_sinteticos', 'grafo']:
        documentos.extend(p for p in (RAIZ/carpeta).rglob('*.md')
                           if 'salida' not in p.relative_to(RAIZ).parts)
    errores = []
    for doc in documentos:
        texto = re.sub(r'```.*?```', '', doc.read_text(encoding='utf-8'), flags=re.S)
        for destino in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', texto):
            url = urlsplit(destino)
            if url.scheme or url.netloc or not url.path:
                continue
            archivo = doc.parent/unquote(url.path)
            if not archivo.exists():
                errores.append(str(doc.relative_to(RAIZ))+': '+destino)
    if errores:
        raise RuntimeError('Enlaces locales inexistentes:\n'+'\n'.join(errores))
    print('Enlaces locales: OK (%d documentos)' % len(documentos))


def main():
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Las pruebas del visor requieren Node.js 24; la aplicacion no lo necesita.')
    ejecutar(sys.executable, '-m', 'pip', 'check')
    ejecutar(sys.executable, '-m', 'compileall', '-q', 'grafo', 'iniciar.py', 'verificar.py')
    ejecutar(sys.executable, 'grafo/pruebas.py')
    ejecutar(sys.executable, '-m', 'unittest', 'discover', '-s', 'grafo', '-p', 'pruebas_*.py', '-v')
    ejecutar(node, 'grafo/pruebas_navegacion.js')
    ejecutar(sys.executable, 'grafo/documentar.py', '--comprobar')
    enlaces_locales()
    print('\nVerificacion completa: OK')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print('\nVerificacion fallida: %s' % error, file=sys.stderr)
        raise SystemExit(1)
