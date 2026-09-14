# Reportes importados

Los JSON de esta carpeta se procesan junto con `reportes_sinteticos/` al iniciar el servidor. Una importación con el mismo `reportId` tiene prioridad sobre el reporte base. Quitarla recupera la versión base, si existe.

Se pueden copiar archivos aquí y reiniciar, o usar **Probar con otros reportes** en el visor. La carga HTTP valida cada archivo con el extractor real antes de reemplazarlo; un lote puede informar archivos aceptados y archivos rechazados por separado.

El documento debe ser un objeto JSON con `reportId`. El ID admite de 1 a 60 letras ASCII, dígitos, guiones y guiones bajos; los nombres reservados de Windows no se admiten. Los contenedores presentes deben tener la estructura esperada. Los campos opcionales ausentes no impiden cargar un reporte mínimo.

El servidor guarda `<reportId>.json`. No modifica el ID para convertirlo en nombre de archivo: si es inválido, lo rechaza. La construcción detecta IDs duplicados dentro de una carpeta y ambigüedades de mayúsculas/minúsculas.

Los archivos importados están excluidos del repositorio; este instructivo sí se versiona. Conservar la carpeta al actualizar. Los datos técnicos y el texto pueden ser sensibles aunque se hayan eliminado nombres: el script de redacción no garantiza anonimización.
