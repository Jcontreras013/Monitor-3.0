"""
Constantes de negocio, en UN solo lugar.

En monitor-operativo varias de estas listas estaban duplicadas y ya se habían
desincronizado entre sí:

- PATRON_VIVA: app.py tenía 14 estados y tools.py/sync_job.py 10 (les
  faltaban ABIERTA, EJECUCION, ATENDIENDO y TRABAJANDO). Una orden ABIERTA
  contaba como pendiente en el Monitor, pero el robot la trataba como
  terminada al consolidar el historial.
- ACTIVIDADES_BASURA: app.py tenía 7 y tools.py 5 (faltaban ACTIVARRES y
  DESTEFO).

Aquí se usa la versión más completa de cada una.
"""

# Estados en los que la orden sigue abierta (se busca como subcadena).
ESTADOS_VIVOS = (
    "PENDIENTE", "INICIADA", "PROCESO", "ASIGNADA", "DESPACHO", "RUTA", "SITIO",
    "VIAJANDO", "CAMINO", "LLEGADA", "ABIERTA", "EJECUCION", "ATENDIENDO", "TRABAJANDO",
)
PATRON_VIVA = "|".join(ESTADOS_VIVOS)

# Estados que dan por terminada una orden.
ESTADOS_TERMINALES = ("CERRADA", "ANULADA", "CANCELADA", "LIQUIDADA", "FINALIZADA", "RECHAZADA")
# Terminales en los que sí hubo trabajo del técnico.
ESTADOS_TRABAJO_HECHO = ("CERRADA", "LIQUIDADA", "FINALIZADA")

# Lista blanca: las únicas actividades que son visitas técnicas reales y por
# lo tanto aparecen en el Monitor, reportes y KPIs.
ACTIVIDADES_PERMITIDAS = (
    "CEQUI", "INSEQUIPO", "INSFIBRA", "INSFIBRACORP", "INSHFC", "INS-WA",
    "PEXTERNO", "PLEXISCA", "SOP", "SOPCORP", "SOPFIBRA", "SOPFIBRACORP",
    "SOPRECONCORP", "SOPRECONFIBRA", "SOPRECONHFC", "SPLITTEROPT",
    "TRASLADOEXTFIBRA", "TRASLADOEXTFIBRACORP", "TRASLADOINTERNOFIBRA",
    "TRASLADOINTFIBRACORP", "TVADICIONAL",
)

# Tareas internas de mantenimiento de equipo: ni siquiera se guardan.
ACTIVIDADES_BASURA = (
    "ACTUALIZACIONDATOS", "ACTUALIZACIOFW", "ACTUALIZAINFOTECNICA",
    "ACTUALIZARDATOSTECNICOS", "ACTUALIZARSENSOR", "ACTIVARRES", "DESTEFO",
)

# Actividades que nunca son críticas (offline / demora): PLEX, instalaciones,
# traslados de TV, etc. Se busca como subcadena en la ACTIVIDAD.
PATRON_NO_CRITICAS = "PLEXISCA|PEXTERNO|SPLITTEROPT|PLEX|INS|NUEVA|ADIC|CAMBIO|RECU|TVADICIONAL|MIGRACI"

# Una orden SOPFIBRA iniciada hace más de esto sin liquidar genera alerta.
MINUTOS_ALERTA_SOP = 120

# Técnico cuyas órdenes no cuentan días de retraso ni offline (así estaba en
# el sistema anterior; se compara como subcadena del nombre en mayúsculas).
TECNICOS_SIN_RETRASO = ("JOSUE MIGUEL SAUCEDA",)

# Valores que significan "sin técnico asignado".
VALORES_SIN_TECNICO = frozenset({"", "NONE", "NAN", "N/D", "NULL", "0"})

# Empresa propia: órdenes de otra empresa explícita (ej. Cable Color) se descartan.
MARCA_EMPRESA_PROPIA = "ISCA"

SEGMENTO_PLEX = "PLEX"
SEGMENTO_RESIDENCIAL = "RESIDENCIAL"

# Cubetas de días de retraso, en el orden en que se muestran.
CUBETAS_RETRASO = (">= 7 Dia", "= 4 a 6 Dias", "= 1 a 3 Dias", "= 0 Dia")

SUBTIPOS_INSTALACION = ("Nueva", "Adición", "Cambio / Migración", "Recuperado")
