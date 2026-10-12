"""
Fuente ÚNICA de verdad para clasificar actividades.

Portado sin cambios de comportamiento desde monitor-operativo/clasificador.py
(con sus pruebas de regresión en tests/test_clasificador.py). En el sistema
anterior el patrón PLEX y la agrupación SOP / Instalación / Otros llegaron a
estar copiados en ~14 lugares de app.py, y varios bugs (PEXTERNO cayendo en
"Otros", conteos malos) salieron de esas copias divergentes.

Aquí la clasificación se calcula UNA vez, al guardar la orden (ver
normalizacion.py), y queda en la base de datos: ninguna vista la recalcula.
"""

import re

# ==============================================================================
# PATRONES CENTRALES DE ACTIVIDAD
# ==============================================================================
# PLEX = "planta externa" y trabajos de fibra troncal. Se detectan SOLO por la
# actividad, nunca por el comentario (un PEXTERNO cuyo comentario diga
# "instalación" NO es una instalación residencial).
PATRON_PLEX = "PEXTERNO|SPLITTEROPT|PLEXISCA"

# Averías / soporte. Se detecta por la actividad.
PATRON_SOP = "SOP|FALLA|MANT"

# Instalaciones y sus variantes (nueva, adición, cambio, migración, recuperado).
PATRON_INSTALACION = "INS|NUEVA|ADIC|CAMBIO|MIGRACI|RECUP"


def _norm(texto) -> str:
    """Normaliza a mayúsculas y sin espacios sobrantes, tolerando None/NaN."""
    if texto is None:
        return ""
    s = str(texto)
    if s.lower() == "nan":
        return ""
    return s.upper().strip()


def es_plex(actividad) -> bool:
    """True si la actividad pertenece al área PLEX (planta externa)."""
    return bool(re.search(PATRON_PLEX, _norm(actividad)))


def es_sop(actividad) -> bool:
    """True si la actividad es una avería / soporte / mantenimiento."""
    return bool(re.search(PATRON_SOP, _norm(actividad)))


def es_instalacion(texto) -> bool:
    """True si el texto (actividad y/o comentario) indica una instalación."""
    return bool(re.search(PATRON_INSTALACION, _norm(texto)))


def subtipo_instalacion(texto) -> str:
    """Devuelve el subtipo de instalación a partir del texto."""
    t = _norm(texto)
    if re.search("ADIC", t):
        return "Adición"
    if re.search("CAMBIO|MIGRACI", t):
        return "Cambio / Migración"
    if re.search("RECUP", t):
        return "Recuperado"
    return "Nueva"


def subtipo_sop(actividad, comentario, es_offline=False) -> str:
    """Devuelve el subtipo de avería/soporte para el tablero de pendientes."""
    act = _norm(actividad)
    com = _norm(comentario)
    if es_offline:
        return "ONT/ONU Offline"
    if re.search("NIVEL|DB", com):
        return "Niveles alterados"
    if re.search("FIBRA|FTTH", act):
        return "FTTH / FIBRA"
    if re.search("NAV|INTERNET", act):
        return "Navegación / Internet"
    if re.search("TV|CABLE", act):
        return "Sin señal de TV"
    return "SOP General"


def clasificar_tablero(actividad, comentario, es_offline=False):
    """
    Clasifica una orden pendiente en (GRUPO, SUBTIPO) para el tablero.

    GRUPO es uno de: 'OTROS', 'INS', 'SOP'.

    El orden de evaluación es deliberado y NO debe alterarse:
      1. PLEX primero, por ACTIVIDAD -> 'OTROS' (así un PEXTERNO cuyo comentario
         mencione "instalación" o "falla" no se fuga a INS/SOP).
      2. Si ni actividad ni comentario mencionan SOP/INS -> 'OTROS'.
      3. Si el texto indica instalación y la actividad no es SOP -> 'INS'.
      4. En cualquier otro caso -> 'SOP'.
    """
    act = _norm(actividad)
    com = _norm(comentario)
    txt = act + " " + com

    if re.search(PATRON_PLEX, act):
        return "OTROS", (act if act else "N/A")
    if not re.search(PATRON_SOP + "|" + PATRON_INSTALACION, txt):
        return "OTROS", (act if act else "N/A")
    if re.search(PATRON_INSTALACION, txt) and not re.search(PATRON_SOP, act):
        return "INS", subtipo_instalacion(txt)
    return "SOP", subtipo_sop(act, com, es_offline)
