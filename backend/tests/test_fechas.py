from datetime import UTC, date, datetime, time

from app.dominio.fechas import dia_operativo, parse_fecha

AHORA = datetime(2026, 10, 12, 9, 30)


# --- Día operativo (portado de test_dia_operativo.py) ---------------------------
def test_dia_operativo_mismo_dia():
    assert dia_operativo("2026-09-03 11:23") == date(2026, 9, 3)


def test_dia_operativo_madrugada_cuenta_dia_anterior():
    assert dia_operativo("2026-09-03 02:00") == date(2026, 9, 2)
    assert dia_operativo(datetime(2026, 9, 3, 5, 59)) == date(2026, 9, 2)
    assert dia_operativo(datetime(2026, 9, 3, 6, 0)) == date(2026, 9, 3)


def test_dia_operativo_nulo_devuelve_none():
    assert dia_operativo(None) is None
    assert dia_operativo("no es fecha") is None


# --- Parseo de lo que manda Cepheus --------------------------------------------
def test_formatos_de_texto():
    assert parse_fecha("2026-10-11 14:05:00", ahora=AHORA) == datetime(2026, 10, 11, 14, 5)
    assert parse_fecha("2026-10-11T14:05:00", ahora=AHORA) == datetime(2026, 10, 11, 14, 5)
    assert parse_fecha("11/10/2026 14:05", ahora=AHORA) == datetime(2026, 10, 11, 14, 5)
    assert parse_fecha("11/10/2026 02:05:09 p. m.", ahora=AHORA) == datetime(2026, 10, 11, 14, 5, 9)
    assert parse_fecha("11-10-2026", ahora=AHORA) == datetime(2026, 10, 11)


def test_dia_va_primero():
    # 03/04 es 3 de abril, no 4 de marzo.
    assert parse_fecha("03/04/2026 10:00", ahora=AHORA) == datetime(2026, 4, 3, 10, 0)


def test_hora_suelta_se_asume_de_hoy_solo_si_se_permite():
    assert parse_fecha("14:30", ahora=AHORA) == datetime(2026, 10, 12, 14, 30)
    assert parse_fecha("2:30 PM", ahora=AHORA) == datetime(2026, 10, 12, 14, 30)
    assert parse_fecha("14:30", permitir_asumir_hoy=False, ahora=AHORA) is None
    assert parse_fecha(time(8, 15), ahora=AHORA) == datetime(2026, 10, 12, 8, 15)
    # Excel guarda una hora sola como fecha del año 1900.
    assert parse_fecha(datetime(1900, 1, 1, 7, 0), ahora=AHORA) == datetime(2026, 10, 12, 7, 0)


def test_numeros_de_excel():
    assert parse_fecha(46307.5, ahora=AHORA) == datetime(2026, 10, 12, 12, 0)
    assert parse_fecha(0.25, ahora=AHORA) == datetime(2026, 10, 12, 6, 0)
    assert parse_fecha(0, ahora=AHORA) is None


def test_vacios_y_basura():
    for valor in (None, "", "  ", "nan", "NaT", "None", "NULL", "no es fecha", float("nan"), True):
        assert parse_fecha(valor, ahora=AHORA) is None


def test_hora_con_zona_se_pasa_a_honduras():
    utc = datetime(2026, 10, 12, 18, 0, tzinfo=UTC)
    assert parse_fecha(utc, ahora=AHORA) == datetime(2026, 10, 12, 12, 0)
    assert parse_fecha("2026-10-12T18:00:00Z", ahora=AHORA) == datetime(2026, 10, 12, 12, 0)
