"""
Fechas y hora de Honduras, sin pandas.

Las horas de Cepheus (HORA_INI, HORA_LIQ, FECHA_APE) se guardan tal como
llegan, como hora local de Honduras SIN zona horaria (TIMESTAMP WITHOUT TIME
ZONE en Postgres). Todo lo que compara contra "ahora" usa ahora_hn(), que
también es hora local sin zona, para que las restas cuadren.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

# Honduras no tiene horario de verano: UTC-6 todo el año. Se usa un desfase
# fijo en vez de zoneinfo para no depender de tzdata en el contenedor.
ZONA_HN = timezone(timedelta(hours=-6), "America/Tegucigalpa")

# La jornada arranca a las 6:00: un cierre de las 02:00 pertenece al día anterior.
HORAS_DIA_OPERATIVO = 6

_VACIOS = {"", "NONE", "NAN", "NAT", "NULL"}
_EXCEL_ORIGEN = datetime(1899, 12, 30)

_RE_AM = re.compile(r"(?i)a\.?\s*m\.?")
_RE_PM = re.compile(r"(?i)p\.?\s*m\.?")
_RE_SOLO_HORA = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)?$", re.I)
_RE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")

_FORMATOS_HORA = ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M:%S%p", "%I:%M%p")
_FORMATOS_ISO = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %I:%M %p", "%Y-%m-%d")
_FORMATOS_DIA_PRIMERO = tuple(
    f"%d{sep}%m{sep}{anio}{hora}"
    for sep in ("/", "-")
    for anio in ("%Y", "%y")
    for hora in (" %H:%M:%S", " %H:%M", " %I:%M:%S %p", " %I:%M %p", "")
)


def ahora_hn() -> datetime:
    """Hora actual de Honduras, sin zona horaria (comparable con las horas de Cepheus)."""
    return datetime.now(ZONA_HN).replace(tzinfo=None)


def _a_hora_local(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(ZONA_HN).replace(tzinfo=None)
    return dt


def _probar_formatos(texto: str, formatos) -> datetime | None:
    for formato in formatos:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def parse_fecha(valor, permitir_asumir_hoy: bool = True, ahora: datetime | None = None) -> datetime | None:
    """
    Convierte lo que mande Cepheus (texto en varios formatos, número de serie
    de Excel, datetime, hora suelta) a datetime local sin zona, o None.

    Port de parse_date_ultra_safe(): una hora suelta ("14:30", o un datetime
    del año 1900/1970 que en realidad es solo una hora) se interpreta como
    de HOY solo si permitir_asumir_hoy es True.
    """
    if valor is None or isinstance(valor, bool):
        return None
    hoy = datetime.combine((ahora or ahora_hn()).date(), time())

    if isinstance(valor, datetime):
        dt = _a_hora_local(valor)
        if dt.year <= 1970:
            return datetime.combine(hoy.date(), dt.time()) if permitir_asumir_hoy else None
        return dt
    if isinstance(valor, date):
        return datetime.combine(valor, time())
    if isinstance(valor, time):
        return datetime.combine(hoy.date(), valor.replace(tzinfo=None)) if permitir_asumir_hoy else None
    if isinstance(valor, (int, float)):
        if valor != valor or valor == 0:  # NaN o cero
            return None
        if valor > 10000:
            return _EXCEL_ORIGEN + timedelta(days=float(valor))
        if 0 < valor < 1:
            return hoy + timedelta(days=float(valor)) if permitir_asumir_hoy else None
        return None

    texto = str(valor).strip()
    if texto.upper() in _VACIOS:
        return None
    texto = _RE_PM.sub("PM", _RE_AM.sub("AM", texto))
    texto = re.sub(r"\s+", " ", texto)

    if _RE_SOLO_HORA.match(texto):
        if not permitir_asumir_hoy:
            return None
        hora = _probar_formatos(texto.upper(), _FORMATOS_HORA)
        return datetime.combine(hoy.date(), hora.time()) if hora else None

    dt = None
    if _RE_ISO.match(texto):
        try:
            dt = datetime.fromisoformat(texto)
        except ValueError:
            dt = _probar_formatos(texto, _FORMATOS_ISO)
    else:
        dt = _probar_formatos(texto, _FORMATOS_DIA_PRIMERO)
    if dt is None:
        return None
    dt = _a_hora_local(dt)
    if dt.year <= 1970:
        return datetime.combine(hoy.date(), dt.time()) if permitir_asumir_hoy else None
    return dt


def dia_operativo(valor) -> date | None:
    """
    Día operativo al que pertenece una fecha/hora: se le restan
    HORAS_DIA_OPERATIVO y se toma la fecha.
    """
    dt = valor if isinstance(valor, datetime) else parse_fecha(valor, permitir_asumir_hoy=False)
    if dt is None:
        return None
    return (dt - timedelta(hours=HORAS_DIA_OPERATIVO)).date()
