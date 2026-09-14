"""Referencia de parametros: tablas obtenidas del codigo, sin datos de una corrida."""
from pathlib import Path

import alertas
import analisis
import contexto_lugar
import extractor_ncmec
import identidades
import multimedia
import normalizacion
import ontologia as ont
import resolucion


def _tabla(cabeceras, filas):
    def celda(x):
        return str(x).replace('|', r'\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(cabeceras) + ' |',
                      '|' + '|'.join('---' for _ in cabeceras) + '|'] +
                     ['| ' + ' | '.join(celda(x) for x in f) + ' |' for f in filas])


def generar(ruta, g=None, res=None):
    """g/res se aceptan por compatibilidad; no se incluyen datos de reportes."""
    partes = [
        '<!-- Generado por python grafo/documentar.py; no editar las tablas a mano. -->',
        '# Parámetros de la implementación',
        'Referencia del código actual. Los pesos no están calibrados. '
        'No es una probabilidad el valor del campo `confidence`: es un puntaje de reglas. '
        'El funcionamiento y los contratos están en [DOCUMENTACION_TECNICA.md](../DOCUMENTACION_TECNICA.md).',
        '## Versiones de métodos',
        _tabla(['Módulo', 'Versión'], [
            ['ontologia', ont.ONTOLOGIA_VERSION], ['resolucion', resolucion.VERSION],
            ['extractor_ncmec', extractor_ncmec.VERSION], ['identidades', identidades.VERSION],
            ['analisis', analisis.VERSION], ['normalizacion', normalizacion.NORMALIZACION_VERSION],
            ['multimedia', multimedia.VERSION], ['contexto_lugar', contexto_lugar.VERSION],
            ['léxico de lugares', contexto_lugar.LEXICO_VERSION], ['alertas', alertas.VERSION]]),
        '## Reglas de coincidencia',
        'El peso efectivo puede reducirse por frecuencia, procedencia textual o condiciones de IP. '
        'Una regla que solo corrobora no puede sostener la propuesta por sí sola.',
        _tabla(['Regla', 'Tipo', 'Peso base', 'Solo corrobora', 'Rareza', 'Versión', 'Coincidencia'], [
            ['`'+k+'`', v['tipo_nodo'], ont.numero(v['peso_base']),
             'sí' if v['corrobora_solamente'] else 'no',
             'sí' if v['usa_discriminancia'] else 'no', v['version'], v['desc']]
            for k,v in ont.REGLAS.items()]),
        '## Umbrales de vinculación',
        _tabla(['Constante', 'Valor'], [
            ['`'+k+'`', ont.numero(getattr(ont,k))] for k in (
                'UMBRAL_PROPONER','UMBRAL_PROBABLE','UMBRAL_ALTA','UMBRAL_CLUSTER','CONFIANZA_MAXIMA')]),
        '## Frecuencia y expansión de pares',
        _tabla(['Constante', 'Valor'], [[k, getattr(ont,k)] for k in (
            'DF_PLENA_DISCRIMINANCIA','DF_HUB_ABSOLUTO',
            'FRACCION_BAJA_DISCRIMINANCIA','CORPUS_MINIMO_PARA_FRACCION')]),
        _tabla(['Tipo', 'Pares máximos'], sorted(ont.MAX_PARES_POR_TIPO.items())),
        '## Direcciones IP',
        'Los plazos siguientes son estimados y no están verificados con los prestadores. '
        'Son ventanas de la regla; no establecen titularidad ni duración real de una asignación.',
        _tabla(['Prestador normalizado', 'Horas'], list(ont.VENTANA_IP_HORAS.items())),
        _tabla(['Condición', 'Valor'], [
            ['Rango CGNAT', ont.CGNAT_RED],
            ['Factor sin puerto', ont.numero(ont.FACTOR_NAT_SIN_PUERTO)],
            ['Factor con puerto', ont.numero(ont.FACTOR_NAT_CON_PUERTO)]]),
        '## Identidad, texto y contradicciones',
        _tabla(['Constante', 'Valor'], [[k, ont.numero(getattr(resolucion,k))] for k in (
            'FACTOR_TEXTO_LIBRE','CONFIANZA_MISMA_IDENTIDAD','CONFIANZA_CONTRADICCION',
            'DISTANCIA_MINIMA_KM','VELOCIDAD_IMPOSIBLE_KMH')]),
        '## Comparación multimedia y de lugares',
        _tabla(['Parámetro', 'Valor'], [
            ['pHash: bits', 64], ['Distancia Hamming máxima', multimedia.MAX_DISTANCIA_HAMMING],
            ['Bloques del índice pHash', multimedia.MAX_DISTANCIA_HAMMING+1],
            ['Similitud mínima de lugar', contexto_lugar.UMBRAL_SIMILITUD],
            ['Peso de extracción de lugar', contexto_lugar.CONFIANZA_EXTRACCION],
            ['Dimensiones mínimas compartidas', 2],
            ['Dimensiones de anclaje', ', '.join(sorted(contexto_lugar.DIMENSIONES_ANCLA))]]),
        _tabla(['Dimensión de lugar', 'Peso'], sorted(contexto_lugar.PESO_DIMENSION.items())),
        '## Alertas por motivo de archivo',
        'Se propone revisar un antecedente: no se reabre una actuación automáticamente. '
        'La alerta exige un vínculo vigente suficiente y un aporte que responda al motivo de archivo.',
        _tabla(['Motivo', 'Aportes que se buscan', 'Prioridad'], [
            [k, '; '.join(alertas.NOMBRE_APORTE.get(x,x) for x in v['aportes']),v['prioridad']]
            for k,v in alertas.DISPARADORES.items()]),
        _tabla(['Grupo de estados', 'Valores'], [
            ['Archivados o pendientes', ', '.join(sorted(alertas.ESTADOS_ARCHIVADOS))],
            ['Activos', ', '.join(sorted(alertas.ESTADOS_ACTIVOS))]]),
        '## Parámetros de análisis',
        _tabla(['Parámetro', 'Valor'], [
            ['Semilla de Louvain', analisis.SEMILLA_COMUNIDADES],
            ['Intermediación: nodos máximos', analisis.MAX_NODOS_INTERMEDIACION],
            ['PageRank: nodos máximos', analisis.MAX_NODOS_PAGERANK],
            ['Resultados por centralidad', analisis.TOP_CENTRALIDADES],
            ['Candidatos Adamic–Adar', analisis.TOP_CANDIDATOS]]),
        'La omisión de una métrica por tamaño se declara en `centralidades.omitidas`. '
        'Los puentes se recortan a la cantidad configurada, sin ranking de importancia. '
        'El método real de comunidades se conserva en `algoritmo` y los errores de la alternativa en `aviso_fallback`.'
    ]
    Path(ruta).write_text('\n\n'.join(partes)+'\n',encoding='utf-8')
    return ruta
