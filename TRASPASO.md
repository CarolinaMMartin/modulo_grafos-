# Traspaso — módulo de grafos, Bóveda CIJ

Documento de continuidad. Reúne todo lo trabajado en las sesiones del **24 de
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
- `contexto.md` — contexto integral del proyecto, escrito antes de esta sesión.
  **Es el documento rector.** Define la ontología preliminar, la separación
  observada/derivada/inferida, los principios no negociables y las preguntas
  que no deben resolverse por suposición.

El pedido inicial fue: *"analizá el contenido de la carpeta, quiero avanzar con
los grafos"*.

Lo que se construyó es el **corte vertical** que `contexto.md` §21 recomienda como
primer objetivo: ingreso de reportes, extracción con procedencia, vínculo con un
caso archivado, hipótesis separada, visualización, validación humana e informe.

---

## 2. Qué se construyó

```
Cuantico/
  README.md                  presentación del repositorio
  TECNOLOGIAS.md             qué tecnología se usa y por qué esa
  DOCUMENTACION_TECNICA.md   pesos, umbrales y parámetros — generado, no editar
  TRASPASO.md                este documento
  contexto.md                  contexto del proyecto (preexistente)
  requisitos.txt             la única dependencia: networkx
  redactar_reporte.py        quita texto libre y contactos de un reporte real
  reportes_sinteticos/       dataset de trabajo: 10 reportes + estado + README
  _privado/                  originales sin redactar (fuera del repositorio)
  grafo/
    construir.py             orquestador
    servidor.py              la aplicación: es lo que permite decidir en pantalla
    validar.py               CLI de validación humana (equivalente, para técnicos)
    informe_ia.py            informe vía modelo local (opcional)
    pruebas.py               123 invariantes
    generar_sinteticos.py    generador del dataset
    README.md                cómo se usa
    ESTADO.md                qué está implementado, simplificado o ausente
    MODELO_DATOS.md          generado desde la ontología, no editar a mano
    src/
      ontologia.py           tipos, vocabulario, reglas, umbrales, versión
      nucleo.py              contenedor del grafo y procedencia obligatoria
      normalizacion.py       teléfonos, correos, IP, alias, tiempo
      extractor_ncmec.py     JSON de NCMEC -> relaciones OBSERVADAS
      mineria_texto.py       identificadores escritos en texto libre -> DERIVADAS
      resolucion.py          vínculos DERIVADOS, identidades, contra-evidencia
      identidades.py         consolida las unificaciones aprobadas
      alertas.py             reapertura tipada por motivo de archivo
      analisis.py            componentes, comunidades, centralidades, baseline
      dossier.py             dossier crudo, recorte por caso, seudonimización
      redaccion.py           informe en prosa, determinista, uno por caso
      validacion.py          libro append-only encadenado por hash
      render_html.py         visor autocontenido
      informe.py             informe técnico en Markdown
      docs_modelo.py         genera MODELO_DATOS.md
      docs_tecnicos.py       genera DOCUMENTACION_TECNICA.md
      jurisdiccion.py        SIN CONECTAR — ver sección 8
    entrada/                   banco de pruebas (fuera del repositorio)
    estado/validaciones.jsonl        decisiones sobre relaciones existentes
    estado/vinculos_manuales.jsonl   vinculaciones que dispuso una persona
    salida/                    resultados de la última corrida (no versionado)
    salida/informes_por_caso/  un informe por caso, que es el que se firma
```

### Resultado sobre el dataset de prueba

Con el libro de vinculaciones tal como quedó al cierre de la sesión: 10 reportes
→ 65 nodos, 118 aristas (84 observadas, 28 derivadas, 3 inferidas, 3 afirmadas
por un operador), **0 incumplimientos de procedencia**.

- **8 vinculaciones** propuestas por reglas, peso promedio 0,95.
- **4 descartadas**, todas informadas con su motivo.
- **3 vinculaciones establecidas a mano**, cada una con su fundamento. Una es
  el ejemplo del dataset (900000104 ↔ 900000109, dos archivados por
  insuficiencia); **las otras dos son pruebas del circuito** y conviene
  revertirlas desde el visor antes de mostrar esto.
- **5 antecedentes archivados** reactivados.
- **1 contradicción** por desplazamiento implausible.
- **3 hipótesis de identidad**, 1 unificada por decisión humana registrada.
- **3 casos** (legajos), cada uno con su informe.

Estos números **se mueven** con el libro: vincular dos reportes a mano cambia
la cantidad de aristas y reagrupa los legajos. Las pruebas no dependen de ellos
—verifican propiedades, no cantidades—, y el número de corrida sale siempre de
`python grafo/construir.py`.

---

## 3. Cómo correrlo

```bash
pip install -r requisitos.txt
```

Python 3.8 o superior. Una sola dependencia, `networkx`: todo lo demás —el
servidor, el visor, el informe, los libros— usa la biblioteca estándar.

```bash
python grafo/servidor.py
```

Abre el visor en el navegador. **Es la forma de usarlo**: los botones que
registran decisiones solo funcionan acá.

Para generar las salidas sin levantar nada:

```bash
python grafo/construir.py
```

Eso deja `grafo/salida/grafo.html`, que se puede abrir con doble clic, pero
sirve solo para mirar: un archivo suelto no puede guardar nada. Si se toca un
botón de decisión, el visor lo dice en lugar de fingir que anduvo.

```bash
python grafo/pruebas.py
```

123 invariantes sobre las reglas no negociables. Si alguno falla, hay un problema
de diseño, no de presentación.

### Probar con otros reportes

`grafo/entrada/` es el banco de pruebas: todo `.json` que se deje ahí se ingiere
junto al dataset de `reportes_sinteticos/` y se procesa con las mismas reglas.
Sirve para pasarle reportes distintos a los algoritmos sin tocar el material del
proyecto.

Desde el visor, la primera sección del panel izquierdo —**Probar con otros
reportes**— los sube, los valida y reconstruye sin salir de la pantalla, los
lista aparte y los saca con **Quitar**. Sin el visor, copiar los archivos ahí y
correr `python grafo/construir.py`.

Se valida lo mínimo que el extractor necesita: que sea un JSON, que sea un
objeto y que traiga `reportId`. Lo que falte adentro se tolera —un reporte con
pocos datos también es un caso que vale la pena probar—. El archivo se guarda
como `<reportId>.json` y no con el nombre con que vino: un nombre de archivo es
entrada no confiable y no tiene por qué decidir dónde se escribe.

**La carpeta está fuera del repositorio.** Ahí puede terminar un reporte real, y
esos no se versionan; si alguno tiene que compartirse, antes pasa por
`redactar_reporte.py` (§11).

### Validación humana

```bash
python grafo/validar.py cola --origen inferida
python grafo/validar.py ver e_7e301ea5c99cbc0f
python grafo/validar.py e_7e301ea5c99cbc0f validada --usuario op_04 --nota "confirmado"
python grafo/validar.py identidades
python grafo/validar.py unificar e_95a74f9390f1562c --usuario op_04
python grafo/validar.py auditar
```

### Vincular a mano

Cuando el sistema no vinculó dos reportes y el operador, con el expediente
delante, concluye que sí tienen que ver: en el visor, cada coincidencia que no
alcanzó trae el botón **Vincular estos reportes**. Se abre un cuadro que pide
quién lo dispone y el fundamento, se registra, se reconstruye el grafo y la
pantalla vuelve al mismo reporte con el aviso de lo que quedó asentado.

Los mismos actos por consola, para quien esté trabajando en el código:

```bash
python grafo/validar.py vincular 900000104 900000109 --usuario op_04 --motivo "..."
python grafo/validar.py vinculos
python grafo/validar.py desvincular 900000104 900000109 --usuario op_04
```

### Informe

Se genera solo en cada corrida. Hay **uno por caso** en
`salida/informes_por_caso/`, que es el que el visor muestra y descarga: el
informe que firma un operador es de la actuación que tiene entre manos. El
general de toda la corrida queda en `salida/informe_vinculaciones.md`.

Para una redacción más fluida con un modelo local:

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

### 4.11 El texto sensible no entra al grafo, pero los identificadores que menciona sí

Transcripciones de chat y bios de perfil quedan en `salida/textos_restringidos.json`,
referenciadas por hash. El texto no se copia al grafo. Hay invariantes que lo
verifican.

Lo que sí entra es el **identificador normalizado** que ese texto menciona, con
el locator del texto del que salió. Ver 4.16.

### 4.16 Lo que conecta dos reportes no siempre está en un campo

Al probar el motor con un lote de reportes preparado para eso, el resultado fue
que parseaba bien y no correlacionaba nada. La razón: el lote estaba armado con
las cuentas, las IP, los dispositivos y las plataformas **todos distintos**, y
las tres cosas que ataban los dos reportes estaban escritas en el texto:

| En un reporte | En el otro |
|---|---|
| bio: *«Contacto alternativo: +54 9 11 6000-0147»* | chat: *«Agendá 11-6000-0147»* |
| chat: *«Buscame como Puente_Azul47»* | chat: *«Escribí a puenteazul47»* |
| bio: *«Transferencias: luna.rio.47»* | chat: *«El anticipo sale desde LUNA-RIO-47»* |

No es una rareza del lote: es cómo se ve una red que sabe no repetir
identificadores. Un motor que solo mira campos estructurados no la ve nunca.

`src/mineria_texto.py` extrae esos identificadores y los normaliza para que
converjan. Las decisiones que importan:

- **No se hacen pasar por observados.** La relación es `MENCIONA_TELEFONO`,
  `MENCIONA_ALIAS`, `MENCIONA_ALIAS_PAGO`, `MENCIONA_EMAIL`, todas de origen
  *derivada*, y el método que las produce (`mineria_texto`) es distinto del que
  lee los campos (`extractor_ncmec`). Una auditoría puede separar las dos cosas.
  La diferencia entre *«el prestador informa este teléfono»* y *«alguien lo
  escribió en una conversación»* no se recupera después si las dos se guardan
  igual.
- **Pesan menos.** `FACTOR_TEXTO_LIBRE` = 0,85 sobre la coincidencia, y la
  explicación lo dice en un párrafo aparte, una sola vez y en castellano.
- **Se cuelgan del hecho, no de una cuenta.** En una conversación los escribe
  cualquiera de los dos, y el extractor no está en condiciones de decidir de
  quién es cada uno.
- **La regla del alias suelto es conservadora**: se admite si lleva un dígito o
  si una frase lo introduce expresamente. Sin eso, cualquier palabra escrita
  raro entraría al grafo como identificador. Prefiere perderse un alias antes
  que llenar el grafo de ruido que después nadie descarta de a uno.
- **El alias de cobro es un tipo aparte** (`ALIAS_PAGO`, regla `R10`, peso
  0,62). Meterlo en `ALIAS` lo habría hecho valer 0,22 —*refuerza, nunca
  sostiene solo*—, y dos cuentas que cobran por la misma vía comparten algo
  bastante más concreto que un apodo.
- **La clave de comparación del alias cambió para todos**, no solo para los del
  texto: se comparan sin mayúsculas, acentos ni separadores, porque si no
  `Puente_Azul47` y `puenteazul47` quedaban como dos cosas y el vínculo se
  perdía por una barra baja. La forma con la que apareció se conserva, que es
  lo que el operador va a buscar en el expediente.

`ALIAS_PAGO` y las relaciones `MENCIONA_*` **no figuran en `contexto.md` 10.1 y
10.3**. Son adiciones a la ontología, marcadas como tales en el código y
pendientes de validación, igual que el origen `afirmada`.

Sobre el mismo lote quedaron sin resolver tres señales, y hacen falta piezas
que hoy no existen:

1. **El lugar descrito con palabras** —*«galpón del mural azul cerca de la
   estación»* contra *«depósito con mural celeste, entrada lateral»*— necesita
   similitud semántica. Es trabajo para el modelo local, no para una regla.
2. **La imagen casi duplicada** (pHash a distancia 1, SHA-256 distintos) y
3. **la huella de audio compartida** necesitan ingerir el manifiesto de
   `fileDetails`, que viene como archivo aparte, y además un mecanismo nuevo:
   hoy dos reportes se vinculan porque **comparten un nodo**, y dos imágenes
   parecidas no son el mismo nodo. La salida natural es indexar el pHash por
   bandas (LSH) para que la coincidencia aproximada vuelva a ser un nodo
   compartido, y verificar después la distancia de Hamming.

### 4.12 El informe es del caso, y el archivo no se enumera

El grafo se construye sobre todo el archivo —de ahí salen los antecedentes—,
pero el informe se acota al caso: sus reportes, sus vinculaciones, sus
antecedentes, sus contradicciones y sus descartadas, con los pesos recalculados
sobre ese subconjunto.

El material restante **no se enumera**. Se lo nombra como *carpeta de archivo
provisorio*, con la explicación de qué reúne y por qué el sistema la recorre en
cada corrida. Enumerarla no aporta nada al caso, incorpora al informe material
ajeno a él y deja de ser posible apenas hay unos miles de reportes.

La única excepción son las coincidencias descartadas, que sí nombran reportes de
afuera: es el registro de *"se comparó y no alcanzó"*, y el informe aclara
expresamente que esos reportes no integran el caso.

### 4.13 Una persona puede vincular lo que el sistema no vinculó

El caso es real y frecuente: dos reportes se archivaron por insuficiencia y el
operador, con el expediente delante, concluye que tienen que ver. Eso el sistema
no lo puede deducir; lo que sí tiene que hacer es conservarlo.

Esa vinculación **no es ninguna de las tres categorías** de `contexto.md` §10.1: no
consta en la fuente, no sale de una regla, y no es una hipótesis del sistema
esperando validación —ya es la decisión—. Meterla en cualquiera de las tres sería
mezclar justamente lo que el proyecto pide no mezclar.

Por eso se agregó un cuarto origen, **`afirmada`**, con su propia relación
`VINCULADO_POR_OPERADOR`. Es un apartamiento del documento rector y **queda
pendiente de validar con los especialistas** (§9.7).

Propiedades que la distinguen:

- **No lleva peso.** No hay nada calculado que ponderar, y un número ahí sería
  precisión inventada. La ficha lo dice con todas las letras.
- **Nace validada**, porque la validación *es* el acto que la crea. Pero registra
  quién la dispuso, cuándo y con qué fundamento, como cualquier otra.
- **Conserva procedencia completa**: fuente `operador:<usuario>`, locator al
  registro del libro, método y versión, explicación en prosa.
- **Agrupa los dos reportes en el mismo caso**, que es lo que el operador está
  afirmando al establecerla. Entra a la proyección sin pasar por el umbral, y
  ninguna derivada la pisa.
- **Se revierte con otro registro**, nunca borrando el anterior.
- **Sobrevive a reconstruir el grafo**, porque el identificador se recalcula
  igual desde el libro. Hay un invariante que lo verifica.

Vive en `estado/vinculos_manuales.jsonl`, con la misma cadena de hashes y las
mismas limitaciones que el libro de validaciones.

### 4.14 La decisión se toma en pantalla, no en la consola

El visor nació como un HTML autocontenido, y eso fue correcto mientras servía
para mirar: se abre con doble clic y no necesita nada levantado. Dejó de
alcanzar en el momento en que el operador tuvo que poder **vincular** dos
reportes, porque un archivo abierto con doble clic no puede escribir en ningún
lado.

La primera versión dejaba el comando armado para copiar y pegar en una consola.
No sirve: **quien usa esto es abogado y no entra a una consola.** Un botón que
en realidad no hace nada es peor que no tener el botón.

Por eso existe `servidor.py`: el mínimo que hace falta para que el botón
funcione de verdad. Es Python de biblioteca estándar, sin dependencias.

- Escucha **solo en 127.0.0.1**. No queda expuesto a la red.
- Toda escritura pasa por el libro append-only encadenado por hash. El servidor
  no toca el grafo.
- Después de cada escritura **reconstruye el grafo entero** desde los reportes.
  Lo que se ve en pantalla siempre sale de una corrida completa, nunca de un
  parche en memoria.
- La página se recarga y **vuelve al reporte donde estaba el operador**, con un
  aviso de lo que quedó registrado.
- No hay autenticación. El campo *«quién lo dispone»* es **atribución, no
  identidad verificada**: sirve para saber quién dijo qué, no para probar que
  fue esa persona. En la Bóveda lo reemplaza la sesión institucional. Está
  dicho en el arranque del servidor y en `ESTADO.md`.
- Abierto como archivo suelto, el botón **explica cómo abrir la aplicación** en
  lugar de fallar en silencio.

Es un servidor de piloto, sin hardening, y no se despliega así.

### 4.15 Blocking, para que escale

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

### 5.8 El atributo de presentación pierde contra la hoja de estilos

El color de cada línea de cruce se ponía con `setAttribute("stroke", color)`.
Eso es un **atributo de presentación**, y pierde contra cualquier regla CSS:
`.con { stroke:#3d5070 }` ganaba siempre y todas las líneas salían grises.

Lo grave es cómo se ocultó: la auditoría leía `getAttribute("stroke")` y veía
los colores correctos. Es la misma lección de §5.4 —medir lo que se ve, no lo
que se declaró— aplicada al color: hay que usar `getComputedStyle`. Ahora el
color va por `style.stroke`, que sí manda, y hay un invariante de auditoría que
cuenta cuántos cruces quedan del gris por defecto.

### 5.9 Tres copias del mismo bloque de constantes

`render_html.py` tenía **tres veces** el bloque `ATRIBUTOS_LEGIBLES`, `OCULTAR`,
`MOTIVO_CORTO`, `TIPOS_EN_TARJETA` y `NIVEL_JERARQUICO`. Idénticas, así que el
programa funcionaba: ganaba la última. Pero editar la primera no hacía nada, y
ese es el peor tipo de error para quien retome el código. Quedó una sola.

### 5.10 El estilo en línea sobrevive al plegado

Al redimensionar un panel a mano queda un `flex-basis` en línea. Al plegarlo
después, el estilo en línea le ganaba a `#der.plegado { flex-basis:44px }`: el
panel se vaciaba pero seguía ocupando todo el ancho al que lo habían llevado.
Ahora se guarda ese ancho, se suelta el estilo mientras está plegado y se
devuelve al reabrirlo.

Misma familia que §5.4 y §5.8: **la cascada CSS decide cosas que el código cree
estar decidiendo él**.

### 5.11 El ámbar del duplicado era el ámbar de «ubicación»

El conector de *posible duplicado* se dibujaba en ámbar, que es exactamente el
color del tipo de dato **ubicación**. Con el criterio de color vigente —el color
dice de qué dato se trata— esa línea entre reportes se leía como una línea de
Monte Grande: al poner ese dato en foco aparecían cuatro líneas de su color
para tres reportes.

Lo encontró la auditoría contando líneas por color, no la vista. El duplicado
volvió al cian de las vinculaciones, con la raya más corta, y ahora **lo dice
con letras** en el rótulo. Hay un invariante que verifica que ningún color de
conector coincida con un color de tipo de dato.

### 5.12 El interlineado de 12 px no alcanzaba para 10 px de letra

Los dos renglones de un motivo largo se tocaban por un pixel. El alto real de un
renglón de 10 px —con acentos y colas— llega a 12. Pasó a 14. Lo detectó la
auditoría de superposiciones, no la vista.

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

### Versión 3 — árbol

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

### Versión 4 — legible con diez líneas en pantalla (la actual)

La versión 3 se leía bien con tres reportes y se caía con nueve datos abiertos:
etiquetas encimadas, líneas todas del mismo gris, y ninguna forma de aislar lo
que se estaba mirando. Los cambios salieron de mirarla en uso, uno por uno.

**Un solo criterio de línea, y está en la leyenda del panel.**

- El **grosor** dice el peso de la vinculación, en escala absoluta (0,50 a
  1,00) y no relativa al caso en pantalla: si dependiera del máximo del caso, la
  misma vinculación se vería distinta según con quién comparta la pantalla y
  dejaría de poder compararse entre casos. Empezó siendo el trazo el que decía
  el origen —lleno, rayado, punteado—, pero a simple vista un rayado y un
  punteado se parecen, y el peso, que es lo que el operador mira para decidir,
  no se veía en ningún lado.
- El **color** de una línea entre dos reportes dice cómo se obtuvo la
  vinculación: derivada, posible duplicado, hipótesis sin validar, o dispuesta
  por un operador. Es la separación observada/derivada/inferida/afirmada,
  dibujada.
- El **color** de una línea que toca un dato dice de qué dato se trata. Es el mismo en la barra de la caja, en
  la línea y en su punta de flecha. Toda línea que toca un dato es de su color,
  incluida la que baja del reporte del que cuelga: mientras esa era gris, al
  elegir un dato quedaba un reporte encendido sin ninguna línea de su color y
  se leía como suelto (§5.8 y la nota de abajo).
- Cada línea de cruce lleva **un punto en el arranque** y corre por su propio
  carril, con esquinas redondeadas: con el ángulo vivo, dos líneas que doblan en
  el mismo lugar se leen como una cruz.

**El clic aísla, y el segundo clic devuelve la vista.** Al tocar un dato se
apaga todo lo que no lo involucra —de 19 cajas encendidas a 5— y la ficha abre
con *«Vinculaciones que sostiene»*: el porqué, no dónde aparece. Lo mismo al
tocar un conector, que enciende sus dos reportes y los datos que lo sostienen.

**Las cajas se mueven de a una** y los conectores las siguen, porque salen de la
posición y no de un dibujo guardado. **Ordenar** las devuelve a su lugar.

**Un dato puede ponerse en el centro.** El árbol se cuelga de él y la fila de
abajo pasa a ser la de los reportes en los que consta. Es la vista para
investigar un identificador —una cuenta, un dispositivo— en lugar de un reporte.

**Volvió el panel de filtros**, a la izquierda: buscar dentro del caso,
antecedentes a revisar, peso mínimo, mostrar el peso sobre la línea, mostrar
solo los datos compartidos, tipos de dato con su color, y la leyenda. El peso
sobre la línea sale **apagado**: satura y casi nunca es lo que se está mirando.

**Los textos se recortan midiendo lo que ocupan**, no contando caracteres, y el
título manda: si la marca de la derecha no entra, se reduce a un punto de color
y su texto queda en el globo de ayuda. Antes que recortar el número de reporte,
se pierde la marca.

### Qué no se dibuja, y por qué

- **Plataformas y prestadores.** Todos los reportes de Grindr comparten Grindr:
  no distingue nada. Se informan en la ficha.
- **La mención de persona y el chat.** Son estructura interna del reporte, no
  aquello por lo que un reporte se vincula con otro. Aparecen en la cadena
  completa de una vinculación.
- **La identidad unificada.** No es un dato del reporte: es una conclusión sobre
  una persona que un operador aprobó *porque* dos reportes comparten una cuenta.
  Dibujarla al lado de esa cuenta la hacía competir con ella y se leía como una
  segunda coincidencia independiente. Los reportes que agrupa llevan la marca
  *«misma persona»* y la ficha lo explica.
- **Entidades de otros casos.** El visor nunca muestra dos casos a la vez. Pero
  si un dato aparece además en reportes de otros casos, la caja lo dice —*«en
  otros casos»*— y la ficha explica que la coincidencia se evaluó y no alcanzó.
  Sin eso, la ausencia de línea se leía como una falla del sistema, cuando era
  justamente el criterio funcionando.

### Detalles de interacción que costaron

- El clic en el vacío **no** descarta el recorrido. Antes reseteaba la vista.
- Hay historial con **Volver / Siguiente** (`Alt + ←` / `Alt + →`).
- Los dos paneles se pliegan desde adentro, dejando un riel angosto: nunca
  desaparecen del todo. Y recuerdan el ancho al que los llevaron (§5.10).

### Cómo se verifica que se ve bien

No alcanza con mirarlo. Hay una auditoría que se corre desde la consola del
navegador y **mide rectángulos en pantalla**: recorre los cinco casos con todos
los reportes abiertos, cuenta pares de textos superpuestos, textos recortados,
líneas sin color efectivo y líneas sin punta. Es lo que detectó §5.8 y §5.11,
que a ojo pasaban. El criterio quedó en §5.4 y se sigue cumpliendo: **medir lo
que se ve, no lo que se declaró**.

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
  compararla; el modelo no. `contexto.md` §11.5 enumera lo que hace falta antes.

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

### 9.5 El cuarto origen

`afirmada` no está en `contexto.md` §10.1, que enumera tres. Se agregó porque una
vinculación que dispone una persona no entra en ninguna de las tres sin
desdibujarlas (§4.13). Hay que validar con los especialistas si la categoría es
correcta, cómo se llama, y qué efecto tiene sobre una actuación: en particular,
si una vinculación manual debe poder disparar por sí sola la revisión de un
archivado, cosa que hoy **no** hace.

### 9.6 Volumen real

No hay medición de cuántos reportes, nodos y aristas hay en el histórico. Sin
eso no se puede decidir si hace falta una base de grafos distribuida.

### 9.7 Punto pendiente de la conversación

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

- **Validar y rechazar desde la interfaz.** La vinculación manual ya se hace en
  pantalla (§4.14) y el servidor expone `/api/decidir`, pero el visor todavía no
  tiene el botón: la aprobación de relaciones y la unificación de identidades
  siguen siendo por CLI. Es el mismo circuito, falta el control.
- **Identificador de caso estable.** El legajo se numera por posición: al
  vincular dos reportes, todos los legajos se renumeran y "L003" pasa a ser otro
  caso. El visor ya no depende de eso —guarda el reporte, no el legajo—, pero
  cualquier cosa que referencie un caso desde afuera se va a romper.
- **Casos con muchos datos.** Existe el filtro *«solo los datos que comparte con
  otro reporte»*, pero sale apagado. Si en casos reales hay reportes con muchas
  más entidades, habría que invertirlo: mostrar por defecto solo los
  compartidos y dejar el resto detrás de un segundo clic. Hace falta ver un
  caso real antes de decidirlo.
- **Casos con muchos reportes vinculados.** La disposición en árbol pone todos
  los reportes en una fila. Con más de siete u ocho el lienzo se vuelve muy
  ancho y hay que alejarse tanto que deja de leerse. Falta una segunda fila, o
  paginado, o algún criterio de recorte por peso.
- **La redacción del modelo local no llega al visor.** `informe_ia.py` escribe
  su versión en `salida/informe_vinculaciones.md`, pero el visor muestra los
  informes por caso que produce `construir.py` con plantillas. Cuando haya un
  modelo, hay que decidir si redacta también uno por caso.
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
  institucional expresa (`contexto.md` §14.1).

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

### Advertencia sobre `contexto.md`

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
