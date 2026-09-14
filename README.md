# Módulo de grafos · Vinculaciones

Aplicación local para explorar reportes CyberTipline, encontrar datos compartidos, revisar vinculaciones y conservar el fundamento y el historial de las decisiones. El visor tiene temas claro y oscuro, navegación hacia atrás y adelante, y grafos SVG con tipografía sin serif.

## Iniciar

1. Instalar **Python 3.12 de 64 bits** y habilitar su acceso desde la consola. También se admiten 3.13 y 3.14, excepto 3.14.1.
2. Descargar y extraer el repositorio completo.
3. En Windows, abrir **INICIAR_WINDOWS.bat**. En otros sistemas, ejecutar `python3 iniciar.py`.

El iniciador crea `.venv`, instala las versiones de `requisitos.txt` y abre el visor en `http://127.0.0.1:8731/`. La primera instalación y las actualizaciones de dependencias necesitan Internet; el visor y sus cálculos se ejecutan localmente. Dejar abierta la consola. Para detener: **Ctrl+C**.

Para actualizar una copia obtenida con Git: cerrar la aplicación, ejecutar `git pull --ff-only` y volver a abrir el iniciador. Conservar `grafo/entrada/` y `grafo/estado/`: contienen los reportes importados y las decisiones. Las instrucciones para copias ZIP y entornos antiguos están en [LEEME_INICIO.md](LEEME_INICIO.md).

## Trabajo en el visor

- Elegir un legajo y desplegar sus reportes. La marca **en N reportes ›** cuenta reportes distintos del caso; sigue visible después de seleccionar, centrar o volver. El puntero resalta cuáles son; la marca centra el dato.
- **Volver** en la barra lateral recupera la ficha anterior y su vista; **Adelante** permite retomarla. La navegación no revierte decisiones guardadas.
- Las líneas de cruce están apagadas inicialmente. Se activan en **Qué se muestra** y su estado se conserva al navegar.
- Azul: vinculación calculada por reglas. Violeta rosado: posible duplicado. Gris: vínculo establecido por un operador. La tarjeta con fondo invertido indica el centro del análisis. La leyenda explica también los tipos de datos y el grosor.
- Al revisar una relación se muestran la explicación y la ubicación legible de los datos de origen. El detalle técnico conserva el locator original para auditoría.
- Las revisiones y los vínculos manuales piden operador y fundamento cuando corresponde. Se guardan antes de reconstruir los resultados.

## Documentación vigente

| Documento | Contenido |
|---|---|
| [Inicio y actualización](LEEME_INICIO.md) | Instalación, operación y recuperación del entorno |
| [Documentación técnica](DOCUMENTACION_TECNICA.md) | Tecnologías, arquitectura, algoritmos, API, persistencia y límites |
| [Modelo de datos](grafo/MODELO_DATOS.md) | Vocabulario y contrato de procedencia, generados desde el código |
| [Parámetros](docs/PARAMETROS.md) | Reglas, pesos, umbrales y versiones vigentes |
| [Desarrollo siguiente](ETAPA2_VINCULACION_CONTEXTUAL.md) | Etiquetado, evaluación contextual y condiciones para experimentar con GNN |

El repositorio incluye un [dataset de demostración](reportes_sinteticos/README.md). No es una muestra de evaluación del desempeño. El sistema actual aplica reglas y algoritmos clásicos; no entrena ni ejecuta una GNN.

## Verificar el desarrollo

Con las dependencias instaladas y Node.js 24 para las pruebas JavaScript:

```bash
python verificar.py
```

Usar el Python de `.venv` si las dependencias están allí. El comando verifica dependencias, código Python, invariantes, importación y revisión HTTP, navegación, contadores, colores y referencias de documentación. No instala Node.js como dependencia de la aplicación.

Las tablas de referencia se actualizan explícitamente con `python grafo/documentar.py`. Iniciar o reconstruir el grafo **no reescribe la documentación**.
