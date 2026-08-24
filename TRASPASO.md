# Traspaso — módulo de grafos, Bóveda CIJ

Documento de continuidad. Reúne todo lo trabajado en la sesión del **24 de
agosto de 2026**: qué se construyó, por qué se tomó cada decisión, qué errores
se encontraron en el camino, qué quedó deliberadamente afuera y qué falta.

Está escrito para que otra sesión —u otra persona— pueda retomar sin
reconstruir el razonamiento.

---

## Índice

1. [Punto de partida](#1-punto-de-partida)
2. [Qué se construyó](#2-qué-se-construyó)
3. [Cómo correrlo](#3-cómo-correrlo)
4. [Decisiones de diseño y su fundamento](#4-decisiones-de-diseño-y-su-fundamento)
5. [Errores encontrados y corregidos](#5-errores-encontrados-y-corregidos)
6. [El visor: cómo llegó a ser lo que es](#6-el-visor-cómo-llegó-a-ser-lo-que-es)
7. [Criterios de trabajo acordados](#7-criterios-de-trabajo-acordados)
8. [Fuera de alcance por decisión](#8-fuera-de-alcance-por-decisión)
9. [Preguntas abiertas](#9-preguntas-abiertas)
10. [Qué falta hacer](#10-qué-falta-hacer)
11. [Manejo de datos sensibles](#11-manejo-de-datos-sensibles)
12. [Repositorio](#12-repositorio)

---

## 1. Punto de partida

La carpeta tenía tres cosas:

- `Prometea Cuántica- CIJ.pdf` — hoja de ruta del proyecto: relevamiento del
  proceso actual del CIJ y las tres etapas propuestas.
- `reporte anonimizado.txt` — un reporte real de NCMEC en JSON.
- `CLAUDE.md` — contexto integral del proyecto, escrito antes de esta sesión.
  **Es el documento rector.** Define la ontología preliminar, la separación
  observada/derivada/inferida, los principios no negociables y las preguntas
  que no deben resolverse por suposición.

El pedido inicial fue: *"analizá el contenido de la carpeta, quiero avanzar con
los grafos"*.

Lo que se construyó es el **corte vertical** que `CLAUDE.md` §21 recomienda como
primer objetivo: ingreso de reportes, extracción con procedencia, vínculo con un
caso archivado, hipótesis separada, visualización, validación humana e informe.

---

## 2. Qué se construyó

```
Cuantico/
  README.md                  presentación del repositorio
  TECNOLOGIAS.md             inventario de tecnologías y algoritmos
  TRASPASO.md                este documento
  CLAUDE.md                  contexto del proyecto (preexistente)
  redactar_reporte.py        quita texto libre y contactos de un reporte real
  reportes_sinteticos/       dataset de trabajo: 10 reportes + estado + README
  _privado/                  originales sin redactar (fuera del repositorio)
  grafo/
    construir.py             orquestador
    validar.py               CLI de validación humana
    informe_ia.py            informe vía modelo local (opcional)
    pruebas.py               55 invariantes
    generar_sinteticos.py    generador del dataset
    README.md                cómo se usa
    ESTADO.md                qué está implementado, simplificado o ausente
    MODELO_DATOS.md          generado desde la ontología, no editar a mano
    src/
      ontologia.py           tipos, vocabulario, reglas, umbrales, versión
      nucleo.py              contenedor del grafo y procedencia obligatoria
      normalizacion.py       teléfonos, correos, IP, alias, tiempo
      extractor_ncmec.py     JSON de NCMEC -> relaciones OBSERVADAS
      resolucion.py          vínculos DERIVADOS, identidades, contra-evidencia
      identidades.py         consolida las unificaciones aprobadas
      alertas.py             reapertura tipada por motivo de archivo
      analisis.py            componentes, comunidades, centralidades, baseline
      dossier.py             dossier crudo, seudonimización, prompt
      redaccion.py           informe en prosa, determinista
      validacion.py          libro append-only encadenado por hash
      render_html.py         visor autocontenido
      informe.py             informe técnico en Markdown
      docs_modelo.py         genera MODELO_DATOS.md
      jurisdiccion.py        SIN CONECTAR — ver sección 8
    estado/validaciones.jsonl  decisiones humanas registradas
    salida/                    resultados de la última corrida (no versionado)
```

### Resultado sobre el dataset de prueba

10 reportes → 65 nodos, 115 aristas (84 observadas, 28 derivadas, 3 inferidas),
**0 incumplimientos de procedencia**.

- **8 vinculaciones** propuestas, peso promedio 0,95.
- **4 descartadas**, todas informadas con su motivo.
- **5 antecedentes archivados** reactivados.
- **1 contradicción** por desplazamiento implausible.
- **3 hipótesis de identidad**, 1 unificada por decisión humana registrada.
- **5 casos** (legajos): L001 con 4 reportes, L002 y L003 con 2, y 2 reportes
  sueltos.

---

## 3. Cómo correrlo

```bash
pip install networkx
```

```bash
python grafo/construir.py
```

Después, abrir `grafo/salida/grafo.html`.

```bash
python grafo/pruebas.py
```

55 invariantes sobre las reglas no negociables. Si alguno falla, hay un problema
de diseño, no de presentación.

### Validación humana

```bash
python grafo/validar.py cola --origen inferida
python grafo/validar.py ver e_7e301ea5c99cbc0f
python grafo/validar.py e_7e301ea5c99cbc0f validada --usuario op_04 --nota "confirmado"
python grafo/validar.py identidades
python grafo/validar.py unificar e_95a74f9390f1562c --usuario op_04
python grafo/validar.py auditar
```

### Informe

Se genera solo en cada corrida (`salida/informe_vinculaciones.md`) y viaja
embebido en el visor. Para una redacción más fluida con un modelo local:

```bash
python grafo/informe_ia.py
```

### Regenerar el dataset sintético

```bash
python grafo/generar_sinteticos.py
```

No toca el reporte real.

---

## 4. Decisiones de diseño y su fundamento

Lo que sigue es el razonamiento detrás de cada pieza. Es lo que se perdería si
solo quedara el código.

### 4.1 Separación epistemológica

Tres clases de relación que nunca se mezclan, ni en la persistencia ni en la
pantalla:

- **observada** — consta textualmente en un campo del reporte;
- **derivada** — resulta de una regla determinista y reproducible;
- **inferida** — hipótesis por similitud o modelo, siempre pendiente.

Una inferencia nunca nace validada. Una observada no requiere validación para
existir, pero puede impugnarse.

### 4.2 Sin procedencia no hay arista

Cada arista lleva: fuente, ubicación exacta dentro de esa fuente (el campo del
JSON), método y versión, versión de ontología, confianza, momento del hecho,
momento del cálculo, estado de validación y explicación en prosa.

Si falta alguno de los campos esenciales, **la arista no se crea**: se registra
un incumplimiento. Es preferible perder un vínculo a tener uno que no se pueda
explicar.

### 4.3 El grafo es una proyección reconstruible

No es el registro oficial. Se puede borrar `salida/` y regenerarlo desde los
reportes. Por eso las decisiones humanas viven aparte, en `estado/`, y se
re-aplican sobre el grafo reconstruido.

Eso funciona porque **el identificador de arista es determinista**: se calcula
sobre extremos, relación, método, locator y fuente. Esa propiedad es la que no
se puede perder (ver preguntas abiertas, §9).

### 4.4 Una relación necesita un dato objetivo que la sostenga

Traducción de la regla del relevamiento: *una relación debe apoyarse en datos
objetivos coincidentes, no en semejanza contextual*.

Cada regla declara si puede sostener un vínculo por sí sola o si solamente
refuerza. Alias, zona estimada e IP fuera de su ventana temporal **solo
refuerzan**. La combinación (noisy-OR) únicamente se acumula si al menos una
regla sostiene.

El reporte 900000104 del dataset existe para ejercitar esto: comparte el nombre
visible y la ciudad con toda la familia de 255553607, y **no debe vincularse**.
Hay un invariante que lo verifica.

### 4.5 Discriminancia: la rareza es del identificador, no del corpus

El peso de una coincidencia decae según en cuántos reportes aparece ese
identificador. **No se mide como fracción del corpus.** Ver §5.2.

### 4.6 La IP solo vale con fecha, hora, prestador y puerto

- La ventana temporal de reasignación se declara **por prestador**, con un valor
  por defecto, y el supuesto viaja escrito en la explicación de cada arista.
- Bajo CGNAT (RFC 6598, `100.64.0.0/10`) **sin puerto de origen** el prestador
  no puede identificar al abonado: la regla se degrada y deja de sostener.
- El reporte real trae `port: 19096` y es un campo que suele ignorarse.

### 4.7 Zona horaria

NCMEC informa en UTC; los prestadores argentinos responden en hora local. Tres
horas de corrimiento alcanzan para atribuir una conexión al abonado equivocado.
Toda fecha sin zona horaria se marca como supuesto en la explicación.

### 4.8 Las alertas de reapertura son tipadas

Un archivado no se reabre porque *apareció una conexión*. Se reabre porque
**apareció el dato que le faltaba**.

El `motivo_archivo` es un campo de primera clase, y cada motivo declara qué
aporte lo reactiva:

| Motivo del archivo | Lo reactiva |
|---|---|
| `sin_datos_de_usuario` | un identificador atribuible |
| `no_atribuible_nat` | un identificador atribuible, o una IP con fecha y hora |
| `sin_archivos` | un archivo identificado por hash |
| `sin_ubicacion` | un dato de ubicación utilizable |
| `material_sin_relevancia` | que el otro reporte tenga mérito, o evidencia con hash |

Una alerta exige **dos** condiciones: que el vínculo esté sostenido por una
regla fuerte, y que el reporte disparador aporte efectivamente eso. Los vínculos
que no califican se registran como *silenciados*, no se descartan en silencio.

### 4.9 El grafo necesita aristas que debiliten

Un grafo que solo acumula coincidencias tiende a confirmar la hipótesis inicial.
Por eso existe `CONTRADICE`: dos observaciones de la misma cuenta a 1.290 km en
media hora. No invalida nada —puede ser VPN, cuenta compartida o geolocalización
errónea— pero **debilita la atribución** y conviene tenerlo a la vista.

### 4.10 Las personas no se fusionan solas

Cada reporte aporta su propia `PERSONA_MENCION`. Dos menciones que comparten
cuenta generan una hipótesis `POSIBLE_MISMA_IDENTIDAD`, no una fusión: una
cuenta puede estar compartida, vendida o comprometida.

La unificación existe pero **la aprueba una persona** (`validar.py unificar`), y:

- no borra las menciones —cada reporte conserva la suya con su fuente—;
- es transitiva: aprobar A=B y B=C agrupa las tres;
- es **reversible**: revertir la validación deshace la identidad sola en la
  próxima construcción.

### 4.11 El texto sensible no entra al grafo

Transcripciones de chat y bios de perfil quedan en `salida/textos_restringidos.json`,
referenciadas por hash. Del chat solo se leen los identificadores de perfil que
la plataforma agrega de forma estructurada. Hay invariantes que lo verifican.

### 4.12 Blocking, para que escale

Comparar todos contra todos es `O(n²)`. Se construye un índice
`identificador → reportes` y solo se comparan pares que ya comparten algo. El
índice se arma sin recorrer el grafo, porque la procedencia de cada arista ya
dice a qué reporte pertenece.

Los identificadores presentes en demasiados reportes se tratan como *hub*: no
generan pares y se informan aparte.

---

## 5. Errores encontrados y corregidos

Vale la pena conservarlos: son los que muestran dónde el diseño obvio falla.

### 5.1 El identificador de arista debía incluir la fuente

Sin eso, dos reportes que afirman lo mismo desde el mismo campo
(`reportedPersons[0]...`, idéntico en todos los reportes de NCMEC) colapsaban en
una sola arista y **se perdía evidencia**.

Error silencioso: el grafo quedaba plausible pero incompleto. Se detectó porque
la clasificación jurisdiccional del reporte real daba `INDETERMINADA` teniendo
geolocalización.

### 5.2 La discriminancia no puede medirse como fracción del corpus

El primer diseño degradaba a *solo corrobora* cualquier identificador presente
en más del 20 % de los reportes. Con 10 reportes de prueba, un dispositivo
compartido por 4 era el 40 % y quedaba degradado: se perdía un vínculo legítimo.

Ese mismo dispositivo en 100.000 reportes es altamente discriminante. **La
rareza de un identificador es una propiedad suya, no del tamaño de la base.**
Ahora el umbral es absoluto sobre `df`, y la fracción solo se aplica con corpus
grande.

### 5.3 Una alerta no se justifica por la existencia del vínculo

Primer diseño: cualquier coincidencia fuerte con un archivado generaba alerta.
Pero un vínculo por dispositivo no resuelve un archivo por falta de ubicación.
De ahí el modelo tipado de §4.8.

### 5.4 La raya blanca que iba a ninguna parte

En la hoja de estilos, `.sel` estaba declarada **después** de `.apagada`. Con la
misma especificidad gana la última: una arista filtrada se seguía pintando, en
blanco y a opacidad plena, hacia dos nodos que no estaban en pantalla. Lo mismo
con `.rechazada`.

**La auditoría automática no lo detectó porque miraba las clases CSS, no la
opacidad efectiva.** Lección aplicable a cualquier verificación de render: medir
lo que se ve, no lo que se declaró.

### 5.5 La cadena pasaba por el chat en vez de la persona

Del reporte a la cuenta había dos caminos de igual longitud —por la persona
mencionada o por el chat— y el BFS tomaba cualquiera. Se leía como *"un chat
participa en un hecho"*, que no significa nada.

Ahora la búsqueda **prefiere la persona**: *"el reporte, a través de esta
persona, opera con esta cuenta"* se lee solo.

### 5.6 Tres aristas hacia lo mismo

Tres reportes afirmando la misma relación producían tres líneas idénticas. Son
evidencia separada y por eso existen todas en el grafo, pero se dibuja **una** y
la etiqueta aclara *en 3 reportes*.

### 5.7 `requestAnimationFrame` no se dispara en segundo plano

Las animaciones de reacomodamiento quedaban a mitad de camino. Se agregó un
temporizador de respaldo. (Ya no aplica al visor actual, que no anima layout,
pero conviene recordarlo.)

---

## 6. El visor: cómo llegó a ser lo que es

Pasó por tres rediseños completos, cada uno a partir de una observación concreta
sobre el uso real. El recorrido importa porque explica por qué el resultado es
como es.

### Versión 1 — grafo de fuerzas

Nodos y aristas con simulación física, arrastrables. **Problema:** acomoda los
nodos donde el equilibrio los deja, produce un dibujo distinto en cada corrida y
no tiene jerarquía. Obliga a interpretar la forma antes de poder leer nada.

### Versión 2 — acotado al caso, en secuencia

Se introdujo el concepto de **caso** (un reporte y todos aquellos con los que
quedó vinculado, es decir la componente conexa) y el visor dejó de ser un
explorador del archivo general. Disposición en columnas de izquierda a derecha y
etiqueta de relación sobre cada arista.

También apertura en cascada: se empieza con los reportes y se abre de a un paso.

### Versión 3 — árbol (la actual)

A pedido explícito, con un boceto de referencia. El lienzo se lee de arriba
hacia abajo:

```
                    Reporte en análisis
        ┌──────────────────┼──────────────────┐
   misma cuenta,      misma cuenta,       mismo
   mismo dispositivo  misma IP            dispositivo
   peso 0,99          peso 0,99           peso 0,92
        ▼                  ▼                   ▼
   Reporte 900000101  Reporte 900000106   Reporte 900000105  ⊕
                                                 │
                    ┌──────────┬─────────────────┼──────────┐
               b53437…      Buenos Aires    991234567@…   200.123.45.6
               «en 4 reportes»
```

- **Conectores ortogonales con flecha**, como un diagrama de flujo.
- Sobre cada conector, **el motivo** de la vinculación y su peso.
- El botón **⊕** de cada reporte abre sus datos en la fila siguiente.
- Cuando un dato aparece además en otro reporte de la fila, **una línea de color
  vuelve hacia arriba** por su propio carril. Es lo que hace visible de un
  vistazo qué dato sostiene qué vinculación.

**El panel derecho acompaña lo que se toca:** el conector muestra por qué se
vinculan con la cadena completa; el reporte muestra su resumen y sus entidades
agrupadas por tipo; el dato muestra en qué reportes aparece.

### Qué no se dibuja, y por qué

- **Plataformas y prestadores.** Todos los reportes de Grindr comparten Grindr:
  no distingue nada. Se informan en la ficha.
- **La mención de persona y el chat.** Son estructura interna del reporte, no
  aquello por lo que un reporte se vincula con otro. Aparecen en la cadena
  completa de una vinculación.
- **Entidades de otros casos.** El visor nunca muestra dos casos a la vez.

### Detalles de interacción que costaron

- El clic en el vacío **no** descarta el recorrido. Antes reseteaba la vista.
- Hay historial con **Volver / Siguiente** (`Alt + ←` / `Alt + →`).
- El panel se pliega desde adentro, dejando un riel angosto: nunca desaparece
  del todo.

---

## 7. Criterios de trabajo acordados

Surgieron de la conversación y conviene respetarlos.

1. **Se escribe para abogados.** Prosa castellana con tildes, frases completas,
   decimales con coma. Nada de estilo telegráfico ni códigos de regla en
   pantalla: los identificadores técnicos quedan para la auditoría.

   Antes: `[R01_CUENTA] Ambos reportes involucran la cuenta grindr/888658825 (aporte 0.98)`

   Ahora: *"La vinculación se sostiene en que ambos reportes involucran la misma
   cuenta de plataforma (grindr/888658825) y en los dos aparece el mismo
   identificador de dispositivo. Se trata de datos objetivos que individualizan
   y que, por esa razón, alcanzan para proponer la relación."*

2. **Lo más simple posible.** Ante la duda, mostrar menos y explicar mejor.

3. **El sistema tiene que poder explicar cómo llegó ahí.** No alcanza con
   afirmar que dos reportes se vinculan: hay que mostrar la cadena completa.

4. **Estamos en piloto.** No sobre-invertir en infraestructura de IA ni en
   seudonimización: más adelante va una IA local con datos reales.

5. **Las correcciones al diseño previo son bienvenidas.**

---

## 8. Fuera de alcance por decisión

- **Clasificación jurisdiccional y derivación territorial** (Etapa 2). Se sacó
  del circuito. `src/jurisdiccion.py` quedó en el repositorio **sin conectar**,
  para cuando se retome. Hay tres invariantes que verifican que no queda rastro
  en el grafo. No reactivarlo sin que lo pidan.
- **Integración con SIPAR y KIWI.** Fuera del alcance del piloto.
- **Procesamiento multimodal** (imagen, audio, video, OCR, transcripción).
- **Embeddings y búsqueda semántica.**
- **GNN.** Existe el baseline determinista (Adamic-Adar) contra el cual
  compararla; el modelo no. `CLAUDE.md` §11.5 enumera lo que hace falta antes.

---

## 9. Preguntas abiertas

### 9.1 El identificador de arista

Hoy es un SHA-1 truncado propio de este módulo. Queda pendiente definir si
debería usar el esquema del resto del sistema —Bóveda, SIPAR, `.qaif`—. Para
decidirlo hace falta saber qué esquema usa cada sistema, si es estable, y sobre
todo **si puede calcularse localmente**: el grafo se reconstruye entero en cada
corrida y no puede depender de un servicio externo para volver a producir los
mismos identificadores.

La propiedad que no se puede perder es que sea **determinista**. Un identificador
aleatorio o asignado por un servicio rompería la re-aplicación de las decisiones
humanas. El cambio está aislado en `nucleo.Grafo._id_arista`.

### 9.2 ¿El motivo de archivo está estructurado en SIPAR?

**Toda la lógica de reapertura depende de esto.** Si hoy es texto libre, ese es
el primer cambio a pedir. Hoy se simula con `reportes_sinteticos/estado_institucional.json`.

### 9.3 Ventanas temporales de IP

Los valores por prestador son estimados. Hay que confirmarlos con cada uno.

### 9.4 Tabla de localidades del conurbano

Parcial y escrita a mano en `jurisdiccion.py` (hoy desconectado). Requiere
validación institucional si se retoma la Etapa 2.

### 9.5 Volumen real

No hay medición de cuántos reportes, nodos y aristas hay en el histórico. Sin
eso no se puede decidir si hace falta una base de grafos distribuida.

### 9.6 Punto pendiente de la conversación

En un mensaje quedó un **"3."** sin completar, después de pedir (1) el visor
acotado al caso y (2) el inventario de tecnologías. Nunca se aclaró qué era.

---

## 10. Qué falta hacer

### Inmediato: validar con operadores

**El próximo paso no es más código.** Hay que sentarse con una muestra de
reportes reales ya trabajados y verificar:

- si los vínculos que el sistema propone son los que un operador habría hecho;
- si las alertas de reapertura le resultan accionables o son ruido;
- si las ventanas temporales de IP por prestador son correctas;
- si el motivo de archivo se registra de forma estructurada.

Eso produce el conjunto validado que hoy falta y sin el cual no se puede medir
precisión ni entrenar nada.

### Para que sea una secuencia de trabajo completa

El visor es del caso, pero el circuito alrededor no existe:

- **Entrada por caso.** Hoy se elige en un selector; debería llegar desde el
  sistema que asigna trabajo, con el caso ya abierto.
- **Estado de avance dentro del caso.** No hay noción de *qué me falta revisar*:
  la cola de validación es global.
- **Cierre del caso.** No hay una acción que registre que el operador terminó y
  con qué conclusión.
- **Vuelta al archivo general.** Cuando se valida o rechaza, eso debería impactar
  y eventualmente reabrir otros casos. El efecto existe —el libro se re-aplica—
  pero no hay aviso de qué otros casos cambiaron.

### Técnico

- **Botón de validar en la interfaz.** Hoy la aprobación es por CLI porque no
  hay sesión de usuario.
- **Casos con muchos datos.** Con 9 datos abiertos y 13 líneas de cruce el
  dibujo se ensancha. Si en casos reales hay reportes con muchas más entidades,
  habría que mostrar por defecto solo los datos compartidos y dejar el resto
  detrás de un segundo clic.
- **PostgreSQL** como registro oficial, en reemplazo del archivo lateral de
  estado. Es la primera pieza a integrar cuando salga del banco de pruebas.
- **Control de acceso.** Hoy quien corre el script ve todo.
- **Libro de validaciones.** La cadena de hashes detecta modificación de
  registros previos, **no** impide reescribir el archivo entero ni sella el
  tiempo. Para eso hace falta almacenamiento append-only del lado del servidor.
- Extracción desde el PDF estandarizado y desde XML (hoy solo JSON).
- `RESPONDE_A` (oficio ↔ respuesta del prestador) está en el vocabulario sin
  implementación: falta definir el formato de las respuestas.

---

## 11. Manejo de datos sensibles

### El archivo original no estaba anonimizado

`reporte anonimizado.txt`, pese al nombre, conserva la dirección IP, el
identificador de dispositivo, el nombre de perfil, la transcripción completa del
chat con contenido explícito, y los datos de contacto de dos personas
identificables: el contacto del proveedor y la funcionaria del CIJ, con teléfono
y correos institucionales.

### Qué se hizo

Antes de subir nada al repositorio se redactó el reporte real con
`redactar_reporte.py`:

- **Se quitó:** transcripción del chat, bio del perfil, resúmenes de analistas,
  notas y datos de contacto.
- **Se conservó:** IP, dispositivo, cuenta, alias, geolocalización, fechas,
  puerto — los identificadores técnicos, que son los que hacen verificable la
  lógica.

El grafo resultante es **idéntico**: 65 nodos, 115 aristas. Se verificó.

El original intacto quedó en `_privado/255553607.original.json`, fuera del
repositorio.

### Reglas para el futuro

- Todo reporte real nuevo pasa por `redactar_reporte.py` antes de versionarse.
- `.gitignore` excluye `_privado/`, `reporte anonimizado.txt`, `*.pdf` y
  `grafo/salida/`. **No revertir.**
- El evidencia sensible no debe enviarse a servicios externos sin autorización
  institucional expresa (`CLAUDE.md` §14.1).

---

## 12. Repositorio

**https://github.com/CarolinaMMartin/modulo_grafos-** — privado, rama `main`.

El working copy es la carpeta entera del proyecto, no una subcarpeta.

### Historial

| Commit | Qué trae |
|---|---|
| `2dd02c0` | Módulo completo: ontología, procedencia, vinculación, alertas, identidades, visor, informe, 55 invariantes |
| `f0dbbad` | Visor acotado al caso en curso, lectura lineal, `TECNOLOGIAS.md` |
| `3155dd6` | Corrección de las líneas que iban a ninguna parte y del amontonamiento de etiquetas |
| `155a10c` | Apertura en cascada; se dejan de dibujar plataformas y aristas paralelas |
| `040316d` | El lienzo pasa a ser un árbol |

### Advertencia sobre `CLAUDE.md`

Está versionado. Es útil para cualquiera que trabaje el código, pero contiene
observaciones francas sobre el estado real de Prometea Cuántica —la biometría
desactivada que podía mostrarse simulada, la distinción entre narrativa
comercial e implementación—. En un repositorio privado no hay problema; si en
algún momento se abre o se comparte con el proveedor, conviene revisarlo antes.

---

## Resumen en una línea

Hay un módulo de grafos funcionando de punta a punta, que propone vinculaciones
entre reportes con reglas explicables, dice por qué y con qué peso, avisa cuándo
un archivado recibió el dato que le faltaba, y no decide nada por su cuenta. Lo
que falta no es código: es validarlo con quienes lo van a usar.
