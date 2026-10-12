"""
De una orden cruda de Cepheus a una fila lista para la base de datos.

En monitor-operativo esta limpieza se hacía DOS veces: en sync_job.py al
escribir Google Sheets y otra vez en app.py, en cada sesión de cada usuario,
al leer la hoja entera. Aquí se hace una sola vez, al guardar, y los campos
derivados (offline, motivo, segmento, grupo del tablero) quedan en la base.

Lo que depende de la hora actual (días de retraso, alerta de 2 h) NO se
guarda: se calcula al consultar, en monitor.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime

from app.dominio import constantes as c
from app.dominio.clasificador import PATRON_PLEX, clasificar_tablero
from app.dominio.fechas import parse_fecha

# Nombre canónico -> nombres posibles de la columna en Cepheus (formato viejo
# de archivo y formato nuevo de la API). Gana el primero que aparezca.
COLUMNS_MAPPING: dict[str, tuple[str, ...]] = {
    "HORA_INI": ("HORA ENTRADA", "HORA INICIO", "HORAINICIOORDEN", "HORA INICIO ORDEN", "FECHA ENTRADA",
                 "INICIO", "FECHAENTRADA"),
    "HORA_LIQ": ("HORA LIQUIDADO", "HORA CIERRE", "HORACIERREORDEN", "HORA CIERRE ORDEN", "FECHA LIQUIDADO",
                 "LIQUIDADO", "FECHALIQUIDADO"),
    "TECNICO": ("TÉCNICO", "TECNICO", "OPERADOR", "USER NAME"),
    "ACTIVIDAD": ("NOMBRE ACTIVIDAD", "TIPO ORDEN", "ACTIVIDAD", "NOMACTIVIDAD"),
    "FECHA_APE": ("FECHA APERTURA", "APERTURA", "DIASASIGNADA", "DÍAS", "FECHAAPERTURA"),
    "ESTADO": ("ESTADO", "STATUS"),
    "SECTOR": ("SECTOR", "SECT", "CIUDAD", "ZONA"),
    "COLONIA": ("COLONIA", "BARRIO", "DIRECCION", "LOCALIDAD"),
    "NUM": ("NUM", "IDORDEN", "NÚMERO"),
    "CLIENTE": ("CLIENTE", "CUENTA", "NO. CLIENTE"),
    "NOMBRE": ("NOMBRE CLIENTE", "SUSCRIPTOR", "NOMBRE", "NOMBRECLIENTE"),
    "COMENTARIO": ("COMENTARIO", "OBSERVACIONES"),
    "MX": ("MX", "VEHICULO", "UNIDAD"),
    "GPS": ("GPS", "UBICACION", "LINK", "COORDENADAS"),
    "OLT": ("OLT", "NOMBRE OLT", "NOMBREOLT", "EQUIPO OLT", "OLT NAME"),
    "PON": ("PON", "PUERTO PON", "PUERTOPON", "PON PORT", "PUERTO", "SPLITTER", "TARJETA/PUERTO"),
    "RAZON_CIERRE_SOP": ("RAZON CIERRE", "RAZÓN CIERRE", "RAZONCIERRE", "RAZON DE CIERRE", "RAZÓN DE CIERRE",
                         "RAZON_CIERRE", "MOTIVO CIERRE", "MOTIVO DE CIERRE", "RAZON CIERRE SOP"),
    "COMENTARIO_CIERRE": ("COMENTARIO DE CIERRE", "COMENTARIO CIERRE", "COMENTARIOCIERRE", "COMENTARIO_CIERRE",
                          "OBSERVACION CIERRE", "OBSERVACIONES CIERRE", "COMENTARIO TECNICO", "COMENTARIO DEL TECNICO"),
    "EMPRESA": ("EMPRESA",),
}

# Cepheus cambió su API (oct-2026): en órdenes nuevas el estado llega en
# "ESTADO ORDEN" y "ESTADO" viene vacío. ("ESTADO SERVICIO" NO es
# equivalente: es el estado del servicio del cliente, no de la orden.)
COLUMNAS_EQUIVALENTES = {"ESTADO": ("ESTADO ORDEN", "ESTADO_ORDEN", "ESTADOORDEN")}

# Columnas calculadas por el sistema anterior que venían guardadas en Sheet1:
# aquí se recalculan, así que al importar el historial no se copian a `datos`.
COLUMNAS_DERIVADAS_ANTERIORES = frozenset({
    "ES_OFFLINE", "ALERTA_TIEMPO", "DIAS_RETRASO", "MINUTOS_CALC", "TIEMPO_REAL", "SEGMENTO",
    "MOTIVO", "SOP", "ES_VIVA", "SORT_DATE", "TIENE_LIQ", "TECKEY", "TECREF", "MXREF", "HORA_LIQ_CLEAN",
})

_VACIOS = {"", "N/D", "NAN", "NONE", "NULL", "NAT"}

_RE_OFFLINE_APERTURA = re.compile("ONU OFFLINE|OFF LINE|OFFLINE|LOS EN ROJO|PON ROJO")
_JERGA_SOLUCION = ("OK", "LISTO", "RECUPERADO", "SOLUCIONADO", "NAVEGA", "YA QUEDO", "ARRIBA", "FUNCIONAL", "ONLINE")
_CLAVES_FALLA = ("OFFLINE", "OFF LINE", "LOS RED", "PON ROJO", "LOS EN ROJO", "EQUIPO OFFLINE", "ONU OFFLINE",
                 "ONT OFFLINE")
_RE_TELEMETRIA = re.compile("onustatus|statustext|adminstate|rxpower", re.I)
_RE_PLEX_SEGMENTO = re.compile("PLEX|PEXTERNO|SPLITTEROPT")


@dataclass
class OrdenNormalizada:
    num: str
    actividad: str
    estado: str
    tecnico: str | None = None
    cliente: str | None = None
    nombre: str | None = None
    sector: str | None = None
    colonia: str | None = None
    comentario: str | None = None
    comentario_cierre: str | None = None
    razon_cierre: str | None = None
    olt: str | None = None
    pon: str | None = None
    mx: str | None = None
    gps: str | None = None
    empresa: str | None = None
    hora_ini: datetime | None = None
    hora_liq: datetime | None = None
    fecha_ape: datetime | None = None
    es_viva: bool = False
    es_offline: bool = False
    motivo: str = ""
    segmento: str = c.SEGMENTO_RESIDENCIAL
    grupo_tablero: str = "OTROS"
    subtipo_tablero: str = ""
    datos: dict[str, str] = field(default_factory=dict)

    def como_fila(self) -> dict:
        return asdict(self)

    def huella(self) -> str:
        """Resumen del contenido: si no cambió, el robot no reescribe la fila."""
        contenido = json.dumps(self.como_fila(), sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.blake2b(contenido.encode("utf-8"), digest_size=16).hexdigest()


# ------------------------------------------------------------------------------
# Limpieza de valores
# ------------------------------------------------------------------------------
def texto_limpio(valor) -> str | None:
    """Texto sin espacios sobrantes, o None si viene vacío / 'nan' / 'N/D'."""
    if valor is None or isinstance(valor, bool):
        return None if valor is None else str(valor)
    if isinstance(valor, float):
        if valor != valor:
            return None
        if valor.is_integer():
            return str(int(valor))
    texto = str(valor).strip()
    return None if texto.upper() in _VACIOS else texto


def codigo_limpio(valor) -> str | None:
    """Número de orden o de cliente: sin el '.0' que deja Excel/Sheets, y None si es 0."""
    texto = texto_limpio(valor)
    if texto is None:
        return None
    texto = re.sub(r"\.0$", "", texto).strip()
    return None if texto in ("", "0") else texto


def _mayus(valor) -> str:
    return (texto_limpio(valor) or "").upper()


def tecnico_asignado(tecnico) -> bool:
    return (str(tecnico).strip().upper() if tecnico is not None else "") not in c.VALORES_SIN_TECNICO


def es_viva(estado) -> bool:
    return bool(re.search(c.PATRON_VIVA, _mayus(estado)))


def es_no_critica(actividad) -> bool:
    """PLEX, instalaciones, traslados de TV...: nunca cuentan como offline ni demora."""
    return bool(re.search(c.PATRON_NO_CRITICAS, _mayus(actividad)))


def es_tecnico_sin_retraso(tecnico) -> bool:
    nombre = _mayus(tecnico)
    return any(t in nombre for t in c.TECNICOS_SIN_RETRASO)


def es_empresa_ajena(empresa) -> bool:
    """True solo si la orden es de OTRA empresa explícita; vacío no descarta."""
    e = _mayus(empresa)
    return bool(e) and c.MARCA_EMPRESA_PROPIA not in e


# ------------------------------------------------------------------------------
# Detección de equipo caído (offline)
# ------------------------------------------------------------------------------
def es_offline_preciso(comentario) -> bool:
    txt = _mayus(comentario)
    if not txt:
        return False
    if any(palabra in txt for palabra in _JERGA_SOLUCION):
        return False
    return any(palabra in txt for palabra in _CLAVES_FALLA)


def telemetria_dice_online(valor) -> bool:
    """
    Lee el texto de telemetría FTTX que a veces trae la orden (onustatus,
    statusText, rxPower...). True solo si el equipo reporta estar arriba con
    una potencia razonable: entonces la orden NO es un offline real.
    """
    if valor is None:
        return False
    t = str(valor).lower().strip()
    if not t:
        return False
    marcas_caido = ("onustatus: down", "onustatus:down", "status: offline", "status_text: offline",
                    "statustext: offline", "statustext:offline")
    if any(m in t for m in marcas_caido):
        return False
    marcas_arriba = ("onustatus: up", "onustatus:up", "statustext: online", "status_text: online", "statustext:online")
    if not any(m in t for m in marcas_arriba):
        return False
    dbm = None
    if m := re.search(r"\brx:\s*(-?\d+\.?\d*)", t):
        dbm = float(m.group(1)) / 100.0
    if m := re.search(r"rxpower:\s*(-?\d+\.?\d*)", t):
        dbm = float(m.group(1)) / 1000.0
    return not (dbm is not None and dbm <= -30)


def calcular_es_offline(actividad, estado, tecnico, comentario, telemetria_online=False) -> bool:
    act = _mayus(actividad)
    com = _mayus(comentario)
    if es_tecnico_sin_retraso(tecnico) or _mayus(estado) == "CERRADA":
        return False
    if "SOPFIBRA" not in act or es_no_critica(act) or telemetria_online:
        return False
    return bool(_RE_OFFLINE_APERTURA.search(com)) or es_offline_preciso(com)


# ------------------------------------------------------------------------------
# Motivo y segmento
# ------------------------------------------------------------------------------
def calcular_motivo(actividad, comentario, es_offline: bool) -> str:
    """Diagnóstico corto de la orden, con la misma prioridad que el sistema anterior."""
    texto = _mayus(actividad) + " " + _mayus(comentario)
    if es_offline:
        return "🔴 Offline / Caída"
    if re.search("INS|NUEVA|ADIC|CAMBIO|MIGRACI|RECUP", texto):
        if "ADIC" in texto:
            return "➕ Adición"
        if re.search("CAMBIO|MIGRACI", texto):
            return "🔄 Cambio / Migración"
        if "RECUP" in texto:
            return "♻️ Recuperado"
        return "🆕 Instalación Nueva"
    if re.search("NIVEL|DB|POTENCIA|ATENU", texto):
        return "⚡ Niveles Alterados"
    if re.search("TV|CABLE|SEÑAL", texto):
        return "📺 Falla de TV"
    if re.search("NAV|INTERNET|LENT", texto):
        return "🌐 Lentitud / Navegación"
    return "🔧 Mantenimiento General"


def calcular_segmento(actividad, cliente, comentario) -> str:
    texto = " ".join((_mayus(actividad), _mayus(cliente), _mayus(comentario)))
    return c.SEGMENTO_PLEX if _RE_PLEX_SEGMENTO.search(texto) else c.SEGMENTO_RESIDENCIAL


def es_plex(actividad) -> bool:
    return bool(re.search(PATRON_PLEX, _mayus(actividad)))


# ------------------------------------------------------------------------------
# Orden completa
# ------------------------------------------------------------------------------
def _clave(nombre) -> str:
    return unicodedata.normalize("NFC", str(nombre)).upper().strip()


def mapear_columnas(crudo: dict) -> tuple[dict, dict]:
    """(campos canónicos, resto de columnas) de una orden cruda."""
    datos = {_clave(k): v for k, v in crudo.items()}
    usadas: set[str] = set()
    canonicos: dict = {}
    for canonico, opciones in COLUMNS_MAPPING.items():
        # El nombre canónico también vale: así se lee el historial de Sheet1,
        # que ya venía con las columnas renombradas (HORA_INI, HORA_LIQ...).
        for opcion in (*opciones, canonico):
            if opcion in datos and opcion not in usadas:
                canonicos[canonico] = datos[opcion]
                usadas.add(opcion)
                break
    for canonico, equivalentes in COLUMNAS_EQUIVALENTES.items():
        if texto_limpio(canonicos.get(canonico)) is None:
            for equivalente in equivalentes:
                if texto_limpio(datos.get(equivalente)) is not None:
                    canonicos[canonico] = datos[equivalente]
                    break
    extras = {
        k: str(v) for k, v in datos.items()
        if k not in usadas and k not in COLUMNAS_DERIVADAS_ANTERIORES and texto_limpio(v) is not None
    }
    return canonicos, extras


def normalizar_orden(crudo: dict, ahora: datetime | None = None) -> OrdenNormalizada | None:
    """
    Orden cruda -> OrdenNormalizada. Devuelve None si la orden se descarta:
    sin número, actividad "basura" (mantenimiento interno de equipos) u
    orden de otra empresa.
    """
    campos, extras = mapear_columnas(crudo)

    num = codigo_limpio(campos.get("NUM"))
    actividad = _mayus(campos.get("ACTIVIDAD"))
    if num is None or actividad in c.ACTIVIDADES_BASURA or es_empresa_ajena(campos.get("EMPRESA")):
        return None

    estado = _mayus(campos.get("ESTADO"))
    tecnico = texto_limpio(campos.get("TECNICO"))
    if tecnico is not None and not tecnico_asignado(tecnico):
        tecnico = None
    comentario = texto_limpio(campos.get("COMENTARIO"))
    cliente = codigo_limpio(campos.get("CLIENTE"))

    telemetria_online = any(
        telemetria_dice_online(v) for v in extras.values() if _RE_TELEMETRIA.search(v)
    )
    offline = calcular_es_offline(actividad, estado, tecnico, comentario, telemetria_online)
    grupo, subtipo = clasificar_tablero(actividad, comentario, es_offline=offline)

    return OrdenNormalizada(
        num=num,
        actividad=actividad,
        estado=estado,
        tecnico=tecnico,
        cliente=cliente,
        nombre=texto_limpio(campos.get("NOMBRE")),
        sector=texto_limpio(campos.get("SECTOR")),
        colonia=texto_limpio(campos.get("COLONIA")),
        comentario=comentario,
        comentario_cierre=texto_limpio(campos.get("COMENTARIO_CIERRE")),
        razon_cierre=texto_limpio(campos.get("RAZON_CIERRE_SOP")),
        olt=texto_limpio(campos.get("OLT")),
        pon=texto_limpio(campos.get("PON")),
        mx=texto_limpio(campos.get("MX")),
        gps=texto_limpio(campos.get("GPS")),
        empresa=texto_limpio(campos.get("EMPRESA")),
        hora_ini=parse_fecha(campos.get("HORA_INI"), ahora=ahora),
        hora_liq=parse_fecha(campos.get("HORA_LIQ"), ahora=ahora),
        fecha_ape=parse_fecha(campos.get("FECHA_APE"), ahora=ahora),
        es_viva=es_viva(estado),
        es_offline=offline,
        motivo=calcular_motivo(actividad, comentario, offline),
        segmento=calcular_segmento(actividad, cliente, comentario),
        grupo_tablero=grupo,
        subtipo_tablero=subtipo,
        datos=extras,
    )
