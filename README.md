# Módulo de grafos — Bóveda CIJ

Grafo de conocimiento sobre reportes de NCMEC: detecta vinculaciones entre
reportes, explica de dónde sale cada una y avisa cuándo un caso archivado
recibió el dato que le faltaba.

Corre entero en local, sin servicios de red. Única dependencia: `networkx`.

```bash
pip install networkx
python grafo/construir.py
```

Después, abrir `grafo/salida/grafo.html` en el navegador.

El visor trabaja **sobre un caso por vez**. No es un explorador del archivo
general: abre en el primer caso y solo muestra sus relaciones. Los demás se
eligen en el selector de la barra superior.

```bash
python grafo/pruebas.py
```

69 invariantes sobre las reglas que el proyecto declara no negociables.

## Qué hay acá

| Carpeta | Qué es |
|---|---|
| [`grafo/`](grafo/) | El módulo. Su [README](grafo/README.md) explica cómo se usa y su [ESTADO.md](grafo/ESTADO.md) dice honestamente qué está implementado y qué no. |
| [`reportes_sinteticos/`](reportes_sinteticos/) | Dataset de trabajo: diez reportes con la estructura del JSON de NCMEC, cada uno construido para ejercitar una rama distinta de la lógica. |
| [`TRASPASO.md`](TRASPASO.md) | **Empezar por acá.** Todo lo trabajado: decisiones y su fundamento, errores corregidos, preguntas abiertas y qué falta. |
| [`TECNOLOGIAS.md`](TECNOLOGIAS.md) | Todo lo que corre acá: tecnologías, algoritmos y qué papel cumple cada uno. |
| [`CLAUDE.md`](CLAUDE.md) | Contexto funcional e institucional del proyecto. |
| `redactar_reporte.py` | Quita el texto libre y los datos de contacto de un reporte real, conservando los identificadores técnicos. |

## Qué hace el sistema

Toma reportes, extrae entidades —cuentas, dispositivos, direcciones IP,
teléfonos, nombres visibles, ubicaciones— y busca cuáles comparten dos reportes.
Cuando encuentra algo, propone una vinculación con un peso y explica en prosa
qué la sostiene y qué solamente la refuerza.

Tres criterios lo gobiernan:

1. **Cada relación dice de dónde sale.** Fuente, campo exacto dentro de esa
   fuente, método y versión. Sin eso, la relación no se crea.
2. **Nunca se mezcla lo que consta en la fuente con lo que el sistema dedujo.**
   Observada, derivada e inferida son tres clases separadas, en la persistencia
   y en la pantalla.
3. **Nada se decide solo.** El sistema propone vinculaciones, duplicados,
   unificaciones de identidad y reaperturas. La decisión es siempre del
   operador, y queda registrada.

Un reporte archivado no es un caso negativo: describe insuficiencia de evidencia
en el momento del archivo. El sistema avisa cuando otro reporte aporta
exactamente aquello que le faltaba.

## Sobre los datos

Los nueve reportes `9000001xx` son sintéticos: los generó
`grafo/generar_sinteticos.py` y su contenido es un marcador de posición.

`255553607.json` proviene de un reporte real y está **redactado**: se le quitaron
la transcripción del chat, la bio del perfil, los resúmenes de analistas y los
datos de contacto de quienes intervinieron en el trámite. Se conservaron los
identificadores técnicos, que son los que hacen verificable la lógica de
vinculación. El original sin redactar no está en este repositorio.

Nada de lo que hay acá debe usarse como evidencia ni tratarse como material de
una actuación en trámite.

## Estado

Piloto. Es un corte vertical completo y funcionando, no un producto. Lo que
falta —procesamiento multimodal, búsqueda semántica, GNN, integración con SIPAR
y KIWI, control de acceso— está enumerado en
[`grafo/ESTADO.md`](grafo/ESTADO.md), junto con lo que está simplificado a
propósito y por qué.
