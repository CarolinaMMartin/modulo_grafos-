# Dataset de demostración

Contiene diez reportes y `estado_institucional.json`, que aporta el estado y motivo de archivo de cada uno para probar las reglas. Nueve reportes son sintéticos; `255553607.json` es una fuente redactada que conserva identificadores técnicos. **No corresponde describir todo el conjunto como anónimo o sintético.**

| Reporte | Escenario que ejercita |
|---|---|
| 255553607 | Fuente base para las coincidencias |
| 900000101 | Misma cuenta y dispositivo; IP fuera de ventana |
| 900000102 y 900000103 | Teléfono normalizado y aporte para revisar un antecedente archivado |
| 900000104 | Alias y ciudad compartidos: insuficientes para una propuesta automática |
| 900000105 | Dispositivo compartido con otra cuenta |
| 900000106 | Indicios de duplicado y contradicción geotemporal |
| 900000107 y 900000108 | Dispositivo compartido y nueva información de ubicación |
| 900000109 | Coordenadas fuera de Argentina; no se asigna jurisdicción automáticamente |

Los libros de demostración pueden incorporar vínculos manuales, incluso para un par que las reglas automáticas descartaron. El visor identifica el origen humano de ese vínculo.

El conjunto verifica casos concretos. No permite estimar precisión, calibración ni desempeño sobre reportes nuevos. Los números de legajo pueden cambiar al aplicar decisiones: no son identificadores persistentes.

`python grafo/generar_sinteticos.py` vuelve a escribir los reportes sintéticos y sus estados. No hace falta ejecutarlo para instalar ni para actualizar la aplicación.
