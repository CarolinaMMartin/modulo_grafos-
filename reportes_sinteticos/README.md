# Dataset de trabajo — reportes CyberTipline

Diez reportes con la estructura del JSON que envía NCMEC, más un archivo lateral
con el estado institucional de cada uno.

Sirven para probar la lógica de vinculación sin usar datos reales de casos en
trámite. Cada reporte sintético está construido para ejercitar una rama distinta
del razonamiento, de modo que el conjunto no es una muestra estadística: es un
banco de pruebas.

## Contenido

| Archivo | Origen | Para qué está |
|---|---|---|
| `255553607.json` | **Real, anonimizado.** Es el reporte que estaba en la carpeta. | Caso base |
| `900000101.json` | Sintético | Misma cuenta y mismo dispositivo que el anterior, pero la IP coincide fuera de la ventana temporal del prestador |
| `900000102.json` | Sintético | Archivado por IP bajo NAT no atribuible; solo aporta un teléfono |
| `900000103.json` | Sintético | Trae el mismo teléfono que el 102, escrito en otro formato. Verifica la normalización y dispara la alerta de reapertura |
| `900000104.json` | Sintético | Comparte únicamente el nombre visible y la ciudad. **No debe generar vinculación**: es el control negativo |
| `900000105.json` | Sintético | Mismo dispositivo que el caso base, con una cuenta distinta y en otra zona |
| `900000106.json` | Sintético | Casi idéntico al caso base: prueba la detección de duplicados. Además incluye dos conexiones geográficamente incompatibles en media hora |
| `900000107.json` | Sintético | Archivado por falta de datos de ubicación; solo aporta un dispositivo |
| `900000108.json` | Sintético | Comparte el dispositivo con el 107 y sí tiene ubicación: reactiva aquel antecedente |
| `900000109.json` | Sintético | Geolocalización fuera de la Argentina |
| `estado_institucional.json` | Sintético | Estado, motivo de archivo, fecha y operador de cada reporte. Simula lo que en producción vive en SIPAR, no en el grafo |

## Advertencias

- El contenido de los chats sintéticos es un marcador de posición. Solo se
  conservan los identificadores de perfil, que es lo único que lee el extractor.
- `255553607.json` **no está realmente anonimizado**: conserva la dirección IP,
  el identificador de dispositivo, el nombre de perfil y los datos de contacto
  de las personas que intervinieron en el trámite. Antes de compartirlo fuera
  del equipo conviene seudonimizarlo.
- Los identificadores sintéticos empiezan en `9000001xx` para que nunca puedan
  confundirse con un número de reporte real.

## Cómo se usan

El módulo de grafos los lee desde acá:

```bash
python grafo/construir.py
```

Para regenerar los sintéticos (el reporte real no se toca):

```bash
python grafo/generar_sinteticos.py
```
