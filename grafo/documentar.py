"""Genera o verifica las referencias del modelo y parametros, sin ejecutar la app."""
import argparse
from pathlib import Path
import sys
import tempfile

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'src'))
import docs_modelo
import docs_tecnicos


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--comprobar', action='store_true', help='Falla si las tablas versionadas difieren del codigo')
    args = ap.parse_args()
    referencias = [(docs_modelo.generar, BASE / 'MODELO_DATOS.md'),
                   (docs_tecnicos.generar, BASE.parent / 'docs' / 'PARAMETROS.md')]
    diferentes = []
    with tempfile.TemporaryDirectory() as tmp:
        for generar, destino in referencias:
            temporal = Path(tmp) / destino.name
            generar(temporal)
            contenido = temporal.read_text(encoding='utf-8')
            if args.comprobar:
                if not destino.is_file() or destino.read_text(encoding='utf-8') != contenido:
                    diferentes.append(str(destino.relative_to(BASE.parent)))
            else:
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(contenido, encoding='utf-8', newline='\n')
    if diferentes:
        print('Referencias desactualizadas: '+', '.join(diferentes))
        print('Ejecute python grafo/documentar.py y revise el diff.')
        return 1
    print('Referencias del modelo y parametros: '+('vigentes' if args.comprobar else 'generadas'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
