"""
Pruebas de la clasificación de actividades, portadas de monitor-operativo.
Incluyen los casos que fallaron en producción (regresión).
"""

from app.dominio.clasificador import (
    clasificar_tablero,
    es_instalacion,
    es_plex,
    es_sop,
    subtipo_instalacion,
)


def test_es_plex_por_actividad():
    assert es_plex("PEXTERNO")
    assert es_plex("SPLITTEROPT")
    assert es_plex("PLEXISCA")
    assert not es_plex("SOPFIBRA")
    assert not es_plex("INSFIBRA")
    assert not es_plex("")
    assert not es_plex(None)


def test_es_sop_y_instalacion():
    assert es_sop("SOPFIBRACORP")
    assert es_sop("SOP")
    assert not es_sop("INSFIBRA")
    assert es_instalacion("INSFIBRA")
    assert es_instalacion("orden NUEVA de cliente")
    assert not es_instalacion("PEXTERNO")


def test_subtipo_instalacion():
    assert subtipo_instalacion("INS ADIC") == "Adición"
    assert subtipo_instalacion("CAMBIO de plan") == "Cambio / Migración"
    assert subtipo_instalacion("MIGRACION") == "Cambio / Migración"
    assert subtipo_instalacion("RECUPERADO") == "Recuperado"
    assert subtipo_instalacion("INSFIBRA nueva") == "Nueva"


def test_regresion_pexterno_no_se_fuga_a_ins_o_sop():
    # Un PEXTERNO cuyo comentario menciona instalación, nueva, falla, cambio,
    # etc. NO debe salir de "OTROS".
    casos = [
        ("PEXTERNO", "instalacion de nueva acometida"),
        ("PEXTERNO", "falla en poste"),
        ("PEXTERNO", "revision de cambio de ruta"),
        ("SPLITTEROPT", "nueva caja splitter"),
        ("SPLITTEROPT", "mantenimiento preventivo"),
        ("PLEXISCA", "cliente reporta falla"),
    ]
    for act, com in casos:
        grupo, _ = clasificar_tablero(act, com)
        assert grupo == "OTROS", f"{act} / {com} -> {grupo} (debía ser OTROS)"


def test_clasificacion_normal_se_mantiene():
    assert clasificar_tablero("SOPFIBRA", "sin internet")[0] == "SOP"
    assert clasificar_tablero("INSFIBRA", "instalacion nueva")[0] == "INS"
    # Un SOP cuyo comentario dice "instalada" NO se va a INS (la actividad manda).
    assert clasificar_tablero("SOPFIBRA", "antena recien instalada")[0] == "SOP"


def test_offline_tiene_prioridad_en_subtipo_sop():
    grupo, subtipo = clasificar_tablero("SOPFIBRA", "ONU OFFLINE", es_offline=True)
    assert grupo == "SOP"
    assert subtipo == "ONT/ONU Offline"
