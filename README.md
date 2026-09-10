# Módulo de grafos — Bóveda CIJ

Grafo de conocimiento sobre reportes de NCMEC: detecta vinculaciones entre
reportes, explica de dónde sale cada una y avisa cuándo un caso archivado
recibió el dato que le faltaba.

Corre entero en local, sin servicios de red. Python 3.8 o superior y una sola
dependencia: `networkx`.

```bash
pip install -r requisitos.txt
python grafo/servidor.py
```

Eso abre el visor en el navegador. **Es la forma de usarlo**: los botones que
registran decisiones —vincular dos reportes, revertir una vinculación— solo
funcionan acá, porque son los que escriben en el libro. El servidor escucha
únicamente en esta computadora.

El visor trabaja **sobre un caso por vez**. No es un explorador del archivo
general: abre en el primer caso y solo muestra sus relaciones. Los demás se
eligen en el selector de la barra superior.

Para generar las salidas sin levantar nada:

```bash
python grafo/construir.py
```

Eso deja `grafo/salida/grafo.html`, que se abre con doble clic pero sirve solo
para mirar: un archivo suelto no puede guardar nada.

```bash
python grafo/pruebas.py
```

123 invariantes sobre las reglas que el proyecto declara no negociables.

Para probarlo con otros reportes: el panel izquierdo del visor abre con **Probar
con otros reportes**, que toma archivos `.json`, los procesa con las mismas
reglas y reconstruye. Quedan en `grafo/entrada/`, que está fuera del
repositorio.

## Qué hay acá

| Carpeta | Qué es |
|---|---|
| [`grafo/`](grafo/) | El módulo. Su [README](grafo/README.md) explica cómo se usa y su [ESTADO.md](grafo/ESTADO.md) dice honestamente qué está implementado y qué no. |
| [`reportes_sinteticos/`](reportes_sinteticos/) | Dataset de trabajo: diez reportes con la estructura del JSON de NCMEC, cada uno construido para ejercitar una rama distinta de la lógica. |
| [`TRASPASO.md`](TRASPASO.md) | **Empezar por acá.** Todo lo trabajado: decisiones y su fundamento, errores corregidos, preguntas abiertas y qué falta. |
| [`DOCUMENTACION_TECNICA.md`](DOCUMENTACION_TECNICA.md) | **Referencia técnica completa**: cada peso, umbral y parámetro, con un ejemplo de cálculo. Se genera solo en cada corrida leyendo los valores del código, así que no puede desactualizarse. |
| [`TECNOLOGIAS.md`](TECNOLOGIAS.md) | Qué tecnología se usa para cada cosa y por qué esa y no otra. |
| [`contexto.md`](contexto.md) | Contexto funcional e institucional del proyecto. |
| `redactar_reporte.py` | Quita el texto libre y los datos de contacto de un reporte real, conservando los identificadores técnicos. |

## Qué hace el sistema

Toma reportes, extrae entidades —cuentas, dispositivos, direcciones IP,
teléfonos, nombres visibles, alias de cobro, ubicaciones— y busca cuáles
comparten dos reportes. Cuando encuentra algo, propone una vinculación con un
peso y explica en prosa qué la sostiene y qué solamente la refuerza.

Las lee de los campos del reporte **y del texto libre**: hay reportes donde lo
único que los conecta está escrito en la conversación o en la biografía del
perfil —*«agendá 11-6000-0147»*, *«buscame como Puente_Azul47»*—, porque quien
opera sabe no repetir la cuenta ni la IP ni el dispositivo. Esos identificadores
no se hacen pasar por datos declarados: van como derivados, pesan menos y la
explicación lo dice. Está en `grafo/src/mineria_texto.py` y el fundamento en
[`TRASPASO.md`](TRASPASO.md) §4.16.

Tres criterios lo gobiernan:

1. **Cada relación dice de dónde sale.** Fuente, campo exacto dentro de esa
   fuente, método y versión. Sin eso, la relación no se crea.
2. **Nunca se mezcla lo que consta en la fuente con lo que el sistema dedujo.**
   Observada, derivada e inferida son tres clases separadas, en la persistencia
   y en la pantalla. Un teléfono que el prestador informa y uno que alguien
   escribió en un chat no se guardan igual.
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

## Para incorporarlo

Quien vaya a integrarlo conviene que lea, en este orden,
[`TRASPASO.md`](TRASPASO.md) —el razonamiento completo— y
[`grafo/ESTADO.md`](grafo/ESTADO.md) —qué está implementado, qué simplificado y
qué ausente—. Tres cosas que no se ven en el código:

**Lo que hay que preservar al integrarlo.** `grafo/estado/` es lo único que no
se recalcula: guarda las decisiones humanas —validaciones, unificaciones de
identidad y vinculaciones manuales— en libros append-only encadenados por hash.
El grafo es una proyección reconstruible y `grafo/salida/` se regenera entero en
cada corrida; `grafo/estado/` no. Perderlo es perder el trabajo del operador.

**Lo que hace falta reemplazar.** `grafo/servidor.py` es un servidor de piloto:
escucha solo en `127.0.0.1`, no autentica a nadie y no aplica permisos. El campo
*«quién lo dispone»* es atribución, no identidad verificada. En la Bóveda eso lo
reemplaza la sesión institucional, y el estado lateral debería mudarse a la base
transaccional.

**Un apartamiento del documento rector.** El módulo declara un cuarto origen de
relación, `afirmada`, que [`contexto.md`](contexto.md) §10.1 no contempla: es para
las vinculaciones que dispone una persona. Está fundado en `TRASPASO.md` §4.13 y
pendiente de validar con los especialistas (§9.5). No presentarlo como ontología
aprobada.

Las salidas estructuradas —`grafo.json` con la procedencia de cada arista,
`analisis.json` con el resultado de cada módulo, `grafo.graphml` para Gephi o
Cytoscape— están descriptas en [`grafo/README.md`](grafo/README.md).
