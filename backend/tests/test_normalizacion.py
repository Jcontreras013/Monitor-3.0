from datetime import datetime

from app.dominio.normalizacion import (
    calcular_es_offline,
    calcular_motivo,
    calcular_segmento,
    codigo_limpio,
    es_offline_preciso,
    normalizar_orden,
    telemetria_dice_online,
)

AHORA = datetime(2026, 10, 12, 9, 30)


def crudo(**extra):
    """Orden como la manda la API nueva de Cepheus."""
    base = {
        "IDORDEN": "95695421",
        "NOMACTIVIDAD": "SOPFIBRA",
        "ESTADO": "Asignada",
        "TECNICO": "Juan Pérez",
        "CLIENTE": 12345.0,
        "NOMBRECLIENTE": "Cliente de prueba",
        "COLONIA": "Centro",
        "COMENTARIO": "cliente sin internet",
        "FECHAAPERTURA": "10/10/2026 08:00",
        "HORAINICIOORDEN": "",
        "HORACIERREORDEN": "",
    }
    base.update(extra)
    return base


def test_mapea_columnas_de_la_api_nueva():
    o = normalizar_orden(crudo(), AHORA)
    assert o.num == "95695421"
    assert o.actividad == "SOPFIBRA"
    assert o.estado == "ASIGNADA"
    assert o.tecnico == "Juan Pérez"
    assert o.cliente == "12345"
    assert o.nombre == "Cliente de prueba"
    assert o.fecha_ape == datetime(2026, 10, 10, 8, 0)
    assert o.hora_ini is None and o.hora_liq is None
    assert o.es_viva


def test_columnas_desconocidas_se_guardan_en_datos():
    o = normalizar_orden(crudo(**{"Columna Nueva": "valor", "VACIA": ""}), AHORA)
    assert o.datos == {"COLUMNA NUEVA": "valor"}


def test_lee_el_historial_de_sheet1_con_columnas_canonicas():
    fila = {"NUM": "123.0", "ACTIVIDAD": "INSFIBRA", "ESTADO": "CERRADA", "TECNICO": "Ana",
            "HORA_INI": "2026-10-11 08:00:00", "HORA_LIQ": "2026-10-11 10:30:00",
            "FECHA_APE": "2026-10-10 07:00:00", "ES_OFFLINE": "False", "DIAS_RETRASO": "1"}
    o = normalizar_orden(fila, AHORA)
    assert o.num == "123"
    assert o.hora_liq == datetime(2026, 10, 11, 10, 30)
    assert not o.es_viva
    assert "ES_OFFLINE" not in o.datos and "DIAS_RETRASO" not in o.datos


def test_estado_del_formato_nuevo():
    o = normalizar_orden(crudo(ESTADO="", **{"ESTADO ORDEN": "Iniciada"}), AHORA)
    assert o.estado == "INICIADA"
    assert o.es_viva


def test_descartes():
    assert normalizar_orden(crudo(IDORDEN=""), AHORA) is None
    assert normalizar_orden(crudo(IDORDEN="0"), AHORA) is None
    assert normalizar_orden(crudo(NOMACTIVIDAD="ACTUALIZARDATOSTECNICOS"), AHORA) is None
    assert normalizar_orden(crudo(NOMACTIVIDAD="DESTEFO"), AHORA) is None
    assert normalizar_orden(crudo(EMPRESA="CABLE COLOR"), AHORA) is None
    # Empresa propia o vacía NO se descarta.
    assert normalizar_orden(crudo(EMPRESA="ISCA-MAXCOM"), AHORA) is not None
    assert normalizar_orden(crudo(EMPRESA=""), AHORA) is not None


def test_tecnico_vacio_queda_sin_asignar():
    for valor in ("", "N/D", "nan", "None", "0", None):
        assert normalizar_orden(crudo(TECNICO=valor), AHORA).tecnico is None


def test_codigo_limpio():
    assert codigo_limpio(95695421.0) == "95695421"
    assert codigo_limpio("95695421.0") == "95695421"
    assert codigo_limpio(" 123 ") == "123"
    assert codigo_limpio(0) is None
    assert codigo_limpio("nan") is None


# --- Offline -----------------------------------------------------------------
def test_offline_solo_en_sopfibra_abierta():
    assert calcular_es_offline("SOPFIBRA", "ASIGNADA", "Ana", "ONU OFFLINE desde ayer")
    assert calcular_es_offline("SOPFIBRACORP", "ASIGNADA", "Ana", "pon rojo")
    assert not calcular_es_offline("SOPFIBRA", "CERRADA", "Ana", "ONU OFFLINE")
    assert not calcular_es_offline("INSFIBRA", "ASIGNADA", "Ana", "ONU OFFLINE")
    assert not calcular_es_offline("SOP", "ASIGNADA", "Ana", "ONU OFFLINE")
    assert not calcular_es_offline("SOPFIBRA", "ASIGNADA", "Ana", "sin internet")
    assert not calcular_es_offline("SOPFIBRA", "ASIGNADA", "JOSUE MIGUEL SAUCEDA", "ONU OFFLINE")


def test_offline_preciso():
    assert es_offline_preciso("LOS RED en la ONT")
    assert not es_offline_preciso("LOS RED pero ya quedo OK")
    assert not es_offline_preciso("")


def test_telemetria_online_anula_el_offline():
    assert telemetria_dice_online("onuStatus: up, rxPower: -21000")
    assert not telemetria_dice_online("onuStatus: up, rxPower: -31000")  # señal demasiado baja
    assert not telemetria_dice_online("onuStatus: down")
    assert not telemetria_dice_online("sin datos")
    o = normalizar_orden(crudo(COMENTARIO="ONU OFFLINE", TELEMETRIA="onuStatus: up rx: -2100"), AHORA)
    assert not o.es_offline
    o = normalizar_orden(crudo(COMENTARIO="ONU OFFLINE", TELEMETRIA="onuStatus: down"), AHORA)
    assert o.es_offline
    assert o.grupo_tablero == "SOP" and o.subtipo_tablero == "ONT/ONU Offline"
    assert o.motivo == "🔴 Offline / Caída"


# --- Motivo y segmento -----------------------------------------------------------
def test_motivo_con_la_prioridad_del_sistema_anterior():
    assert calcular_motivo("INSFIBRA", "ADICION de tv", False) == "➕ Adición"
    assert calcular_motivo("INSFIBRA", "cambio de plan", False) == "🔄 Cambio / Migración"
    assert calcular_motivo("INSFIBRA", "recuperado", False) == "♻️ Recuperado"
    assert calcular_motivo("INSFIBRA", "", False) == "🆕 Instalación Nueva"
    assert calcular_motivo("SOPFIBRA", "niveles altos", False) == "⚡ Niveles Alterados"
    assert calcular_motivo("SOP", "sin señal", False) == "📺 Falla de TV"
    assert calcular_motivo("SOP", "navegacion lenta", False) == "🌐 Lentitud / Navegación"
    assert calcular_motivo("SOP", "revisar equipo", False) == "🔧 Mantenimiento General"
    assert calcular_motivo("SOPFIBRA", "instalacion", True) == "🔴 Offline / Caída"


def test_segmento():
    assert calcular_segmento("PEXTERNO", "1", "") == "PLEX"
    assert calcular_segmento("SOPFIBRA", "1", "revisar splitteropt") == "PLEX"
    assert calcular_segmento("SOPFIBRA", "1", "sin internet") == "RESIDENCIAL"
