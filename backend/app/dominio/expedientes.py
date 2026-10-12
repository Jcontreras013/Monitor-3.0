"""
Reglas de Expedientes (faltas e incidencias de personal).

Port de monitor-operativo/expediente.py sin cambios de comportamiento:
clasificación GRAVE / LEVE / OTRO, separación del motivo combinado antiguo
"LLEGADA TARDÍA / AUSENCIA", promoción a GRAVE a partir de la 3.ª llegada
tarde y resúmenes del mes.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from datetime import date
from typing import Protocol

MOTIVO_LLEGADA_TARDE = "LLEGADA TARDÍA"
MOTIVO_AUSENCIA = "AUSENCIA LABORAL"

AREA_OPERACIONES = "OPERACIONES"

# Motivos que ofrece el formulario de Operaciones (técnicos).
MOTIVOS_OPERACIONES = (
    "Exceso de Velocidad", "Llegada Tarde", "Abandono de Ruta", "Mala Documentación",
    "Incidencia Médica", "Reco / Cambio de Postes", "Trabajo Deficiente (Auditoría de Fibra)", "Otro",
)
# Tipos de registro del formulario Administrativo.
MOTIVOS_ADMINISTRATIVO = (
    "Llamado de Atención Verbal", "Amonestación Escrita", "Llegada Tardía", "Ausencia Laboral",
    "Incidencia Médica", "Felicitación / Mérito", "Curriculum / Contrato", "Otro",
)
# "Reco / Cambio de Postes" no es de una persona: se registra a nombre de RECO.
COLABORADOR_RECO = "RECO"

DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")

# Filtro "Tipo de registro" del historial.
TIPOS_FILTRO = ("todos", "llamado", "tarde", "ausencia", "medica")


class RegistroLike(Protocol):
    colaborador: str
    tipo_falta: str
    comentario: str
    fecha_incidencia: date


def _u(texto) -> str:
    return str(texto or "").upper().strip()


def _sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


# ------------------------------------------------------------------------------
# Tipo de falta
# ------------------------------------------------------------------------------
def es_ausencia_laboral(motivo, comentario) -> bool:
    """True si es una AUSENCIA (no se presentó) y no una llegada tarde."""
    motivo_u, com_u = _u(motivo), _u(comentario)
    tiene_tarde = "TARD" in motivo_u
    tiene_ausencia = "AUSENCIA" in motivo_u or "INASISTENCIA" in motivo_u
    if tiene_ausencia and not tiene_tarde:
        return True
    if tiene_tarde and not tiene_ausencia:
        return False
    if tiene_tarde and tiene_ausencia:
        # Motivo combinado antiguo: decide el comentario.
        return "AUSENCIA" in com_u or "INASISTENCIA" in com_u
    return "AUSENCIA LABORAL" in com_u


def normalizar_motivo(motivo, comentario) -> str:
    """Separa el antiguo "LLEGADA TARDÍA / AUSENCIA" en sus dos categorías reales."""
    motivo_u = _u(motivo)
    if "TARD" in motivo_u and ("AUSENCIA" in motivo_u or "INASISTENCIA" in motivo_u):
        return MOTIVO_AUSENCIA if es_ausencia_laboral(motivo, comentario) else MOTIVO_LLEGADA_TARDE
    return motivo_u


_EXCLUSIONES_TARDE = ("ALMUERZO", "BREAK", "DESCANSO", "ORDEN", "ÓRDEN", "CIERRE", "CERRADA", "APERTURA",
                      "APERTURADA", "LIQUIDADA", "LIQUIDACION", "LIQUIDACIÓN", "CEQUI", "SOP")
_CLAVES_TARDE = ("LLEGADA TARDE", "LLEGADA TARDIA", "LLEGADA TARDÍA", "TARDANZA", "TARDE", "RETRASO",
                 "LLEGADA TARDÍA / AUSENCIA")


def es_llegada_tarde(motivo, comentario) -> bool:
    motivo_u, com_u = _u(motivo), _u(comentario)
    if es_ausencia_laboral(motivo, comentario):
        return False
    if any(ex in motivo_u + " " + com_u for ex in _EXCLUSIONES_TARDE):
        return False
    return any(kw in motivo_u for kw in _CLAVES_TARDE) or any(kw in com_u for kw in _CLAVES_TARDE)


def es_incidencia_medica(motivo) -> bool:
    return _u(motivo) in ("INCIDENCIA MÉDICA", "INCIDENCIA MEDICA")


# Cualquier falta cuyo MOTIVO trate del vehículo es GRAVE (solo el motivo: en
# el comentario el vehículo puede aparecer de pasada sin ser la falta).
_PATRON_MOTIVO_VEHICULO = re.compile(
    r"VEHICUL|\bUNIDAD\b|\bCARRO\b|CAMION|\bMOTO\b|MOTOCICLETA|PICK ?UP|AUTOMOVIL|LLANTA|"
    r"COMBUSTIBLE|GASOLINA|VELOCIDAD|CONDUCC|CONDUCIR|CONDUJO|\bMANEJ|ESTACIONAD|ESTACIONAMIENTO|"
    r"PLACA|FLOTA"
)


def es_falta_de_vehiculo(motivo) -> bool:
    return _PATRON_MOTIVO_VEHICULO.search(_sin_acentos(str(motivo)).upper()) is not None


_VEHICULO_DESCUIDO = (
    "MAL CUIDADO", "CUIDADO VEHICULO", "CUIDADO DEL VEHICULO", "CUIDADO DE VEHICULO",
    "CUIDADO VEHÍCULO", "CUIDADO DEL VEHÍCULO", "CUIDADO DE VEHÍCULO",
    "MALTRATO VEHICULO", "MALTRATO DE VEHICULO", "MALTRATO DEL VEHICULO",
    "DESCUIDO VEHICULO", "DESCUIDO DE VEHICULO", "DESCUIDO DEL VEHICULO",
    "DESCUIDO VEHÍCULO", "DESCUIDO DE VEHÍCULO", "DESCUIDO DEL VEHÍCULO",
    "DAÑO VEHICULO", "DAÑO AL VEHICULO", "DAÑO DE VEHICULO",
    "DAÑO VEHÍCULO", "DAÑO AL VEHÍCULO", "DAÑO DE VEHÍCULO",
    "GOLPE VEHICULO", "GOLPE AL VEHICULO", "GOLPE DE VEHICULO",
    "ABUSO VEHICULO", "ABUSO DEL VEHICULO", "ABUSO DE VEHICULO",
    "DAÑO CARRO", "DAÑO AL CARRO", "DAÑO UNIDAD", "DAÑO A UNIDAD",
)
_SUCIEDAD = ("SUCI", "BASURA", "DESORDEN", "DESASEO", "MUGR")
_UNIDAD = ("VEHICULO", "VEHÍCULO", "UNIDAD VEHICULAR", "CARRO", "PICKUP", "PICK UP", "MOTOCICLETA")
_RAIZ_OBJETO = ("ORDEN", "ÓRDEN", "RUTA")
_RAIZ_ACCION = ("APERTUR", "CERR", "CIERR", "INIC", "LIQUID", "FINALIZ")
_RAIZ_ANOMALIA = ("TARDE", "TARDÍ", "TARDI", "DESFAS", "DESFAC", "RETRAS", "INCUMPLI")
_GRAVES_DIRECTAS = (
    "FALTA DE RESPETO", "FALTA DE RESPET", "FALTAS DE RESPETO", "IRRESPETO", "INSULTO", "INSULTOS", "GOLPE",
    "PELEA", "AGRESION", "AGRESIÓN", "AMENAZA", "HOSTIGAMIENTO", "FALTA AL RESPETO", "OFENSA", "OFENSAS",
    "FALTA RESPETO", "APERTURADA TARDE", "CERRADA TARDE", "APERTURADAS TARDES", "CERRADAS TARDES",
    "MAL USO", "MAL MANEJO", "MALA MANIPULACIÓN", "MALA MANIPULACION", "CHOQUE", "ACCIDENTE", "ALCOHOL",
    "EBRIEDAD", "EBRIO", "DROGA", "ROBO", "HURTO", "ABANDONO DE RUTA", "ABANDONO RUTA", "ABANDONO",
    "INJUSTIFICADA", "DAÑO", "PÉRDIDA", "PERDIDA", "FRAUDE", "NEGLIGENCIA", "REINCIDENCIA", "DORMIDO",
    "GRAVE", "IRRESPONSABILIDAD", "FALSIFIC", "MINTIÓ", "MINTIO", "MENTIRA",
)
_GRAVES_COMBOS = (
    ("ABANDONO", "RUTA"), ("DAÑO", "EQUIPO"), ("DAÑO", "VEHICULO"), ("DAÑO", "VEHÍCULO"), ("DAÑO", "CARRO"),
    ("DAÑO", "UNIDAD"), ("FALTA", "RESPETO"), ("RESPETO", "COMPAÑERO"), ("RESPETO", "SUPERVISOR"),
    ("ORDENES", "PENDIENTES"), ("ÓRDENES", "PENDIENTES"),
    ("ORDEN", "NO ATENDIDA"), ("ÓRDEN", "NO ATENDIDA"), ("ORDEN", "SIN ATENDER"), ("ÓRDEN", "SIN ATENDER"),
    ("ORDEN", "NO ATENDIO"), ("ÓRDEN", "NO ATENDIO"), ("ORDEN", "NO ATENDIÓ"), ("ÓRDEN", "NO ATENDIÓ"),
    ("AUSENCIA", "AVISO"), ("AUSENCIA", "JUSTIF"), ("INASISTENCIA", "AVISO"), ("INASISTENCIA", "JUSTIF"),
    ("IRRESPETO", "COMPAÑERO"), ("IRRESPETO", "SUPERVISOR"),
    ("INVENTO", "DATOS"), ("INVENTÓ", "DATOS"), ("INVENTAR", "DATOS"), ("DATOS", "INVENTADOS"),
    ("DATOS", "FALSOS"), ("ALTERO", "DATOS"), ("ALTERÓ", "DATOS"), ("MANIPULO", "DATOS"), ("MANIPULÓ", "DATOS"),
)
_LEVES = (
    "ALMUERZO EXCEDIDO", "HORA ALMUERZO", "HORA DE ALMUERZO", "EXCEDIÓ ALMUERZO", "EXCEDIO ALMUERZO",
    "TIEMPO DE ALMUERZO", "TIEMPO ALMUERZO", "EXCESO ALMUERZO", "BREAK EXCEDIDO", "HORA BREAK", "HORA DE BREAK",
    "EXCEDIÓ BREAK", "EXCEDIO BREAK", "TIEMPO DE BREAK", "TIEMPO BREAK", "EXCESO BREAK", "DESCANSO EXCEDIDO",
    "NO MARCÓ", "NO MARCO", "SIN MARCAJE", "MARCAJE FALTANTE", "NO MARCÓ ENTRADA", "NO MARCÓ SALIDA",
    "NO MARCO ENTRADA", "NO MARCO SALIDA", "NO REGISTRO ENTRADA", "NO REGISTRO SALIDA", "OLVIDO MARCAJE",
    "FALTA DE MARCAJE", "OLVIDO DE MARCAJE", "MALA DOCUMENTACION", "MALA DOCUMENTACIÓN",
    "TARDE", "RETRASO", "TRÁFICO", "TRAFICO", "LLANTA", "UNIFORME", "GAFETE", "SUCIO", "DESORDEN", "OLVIDO",
    "MINUTOS", "LEVE",
)
_LEVES_COMBOS = (
    ("HORA", "ALMUERZO"), ("HORA", "BREAK"), ("EXCEDIÓ", "ALMUERZO"), ("EXCEDIÓ", "BREAK"),
    ("NO", "MARCÓ"), ("NO", "MARCO"), ("SIN", "MARCAJE"), ("SIN", "MARCA"),
    ("MALA", "DOCUMENTACION"), ("MALA", "DOCUMENTACIÓN"),
)


def clasificar_grave_o_leve(motivo, comentario, n_tardes: int = 0) -> str:
    """'GRAVE', 'LEVE' u 'OTRO', con el mismo orden de reglas del sistema anterior."""
    texto = _u(motivo) + " " + _u(comentario)

    if es_falta_de_vehiculo(motivo):
        return "GRAVE"
    if any(x in texto for x in _VEHICULO_DESCUIDO):
        return "GRAVE"
    if any(s in texto for s in _SUCIEDAD) and any(u in texto for u in _UNIDAD):
        return "GRAVE"
    if (any(o in texto for o in _RAIZ_OBJETO) and any(a in texto for a in _RAIZ_ACCION)
            and any(x in texto for x in _RAIZ_ANOMALIA)):
        return "GRAVE"
    if any(kw in texto for kw in _GRAVES_DIRECTAS):
        return "GRAVE"
    if any(a in texto and b in texto for a, b in _GRAVES_COMBOS):
        return "GRAVE"
    # Reincidencia: 3 o más llegadas tarde = GRAVE.
    if es_llegada_tarde(motivo, comentario):
        return "GRAVE" if n_tardes >= 3 else "LEVE"
    if es_ausencia_laboral(motivo, comentario):
        return "LEVE"
    if any(p in texto for p in _LEVES):
        return "LEVE"
    if any(a in texto and b in texto for a, b in _LEVES_COMBOS):
        return "LEVE"
    return "OTRO"


def rubro(motivo, comentario, n_tardes: int = 0) -> str:
    """Etiqueta "[GRAVE] MOTIVO" del panel de KPIs."""
    clasificacion = clasificar_grave_o_leve(motivo, comentario, n_tardes)
    limpio = _u(motivo)
    for etiqueta in ("[GRAVE]", "[LEVE]", "[OTRO]"):
        limpio = limpio.replace(etiqueta, "")
    return f"[{clasificacion}] {normalizar_motivo(limpio.strip(), comentario)}"


def cumple_tipo(registro: RegistroLike, tipo: str) -> bool:
    if tipo == "medica":
        return es_incidencia_medica(registro.tipo_falta)
    if tipo == "tarde":
        return es_llegada_tarde(registro.tipo_falta, registro.comentario)
    if tipo == "ausencia":
        return es_ausencia_laboral(registro.tipo_falta, registro.comentario)
    if tipo == "llamado":
        return not es_incidencia_medica(registro.tipo_falta)
    return True


# ------------------------------------------------------------------------------
# Textos
# ------------------------------------------------------------------------------
_RE_ETIQUETA_AREA = re.compile(r"^(.*?)\s*\(([^)]*)\)\s*$")


def separar_colaborador_area(nombre_etiquetado: str) -> tuple[str, str]:
    """
    El sistema anterior guardaba a los administrativos como "NOMBRE (ÁREA)".
    Devuelve (NOMBRE, ÁREA sin acentos) o (NOMBRE, OPERACIONES) si no trae área.
    """
    texto = " ".join(str(nombre_etiquetado or "").upper().split())
    m = _RE_ETIQUETA_AREA.match(texto)
    if not m:
        return texto, AREA_OPERACIONES
    area = " ".join(_sin_acentos(m.group(2).strip()).split()) or "SIN ÁREA"
    return m.group(1).strip(), area


def extraer_hora_falta(comentario, hora_registro: str | None = None) -> str:
    """Hora escrita en el comentario ("llegó a las 8:30 am"); si no hay, la del registro."""
    if comentario:
        m = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(A\.?M\.?|P\.?M\.?)?", str(comentario).upper())
        if m:
            hora, minuto = int(m.group(1)), m.group(2)
            sufijo = (m.group(3) or "").replace(".", "")
            if sufijo == "PM" and hora < 12:
                hora += 12
            elif sufijo == "AM" and hora == 12:
                hora = 0
            if 0 <= hora <= 23:
                return f"{hora:02d}:{minuto}"
    if hora_registro:
        m = re.search(r"(\d{1,2}):(\d{2})", str(hora_registro))
        if m:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
    return "N/D"


def nombre_mes(d: date) -> str:
    return f"{MESES[d.month - 1]} {d.year}"


# ------------------------------------------------------------------------------
# Resúmenes
# ------------------------------------------------------------------------------
def conteo_tardes(registros: Iterable[RegistroLike]) -> Counter:
    return Counter(
        _u(r.colaborador) for r in registros if es_llegada_tarde(r.tipo_falta, r.comentario)
    )


def clasificar(registros: list[RegistroLike]) -> list[str]:
    """Clasificación de cada registro, contando la reincidencia dentro del mismo conjunto."""
    tardes = conteo_tardes(registros)
    return [clasificar_grave_o_leve(r.tipo_falta, r.comentario, tardes[_u(r.colaborador)]) for r in registros]


def panel(registros: list[RegistroLike]) -> dict:
    """KPIs del historial filtrado (igual que el panel "Analítica de personal")."""
    tardes = conteo_tardes(registros)
    rubros = [rubro(r.tipo_falta, r.comentario, tardes[_u(r.colaborador)]) for r in registros]
    clasif = Counter(r.split("]")[0].lstrip("[") for r in rubros)
    por_rubro = Counter(rubros)
    reincidencias = Counter((r.colaborador, normalizar_motivo(r.tipo_falta, r.comentario)) for r in registros)
    por_dia = Counter(DIAS_SEMANA[r.fecha_incidencia.weekday()] for r in registros)
    return {
        "total": len(registros),
        "personas": len({r.colaborador for r in registros}),
        "rubro_dominante": por_rubro.most_common(1)[0][0] if por_rubro else None,
        "clasificacion": {k: clasif.get(k, 0) for k in ("GRAVE", "LEVE", "OTRO")},
        "reincidentes": [
            {"colaborador": c, "motivo": m, "veces": n}
            for (c, m), n in reincidencias.most_common() if n > 1
        ],
        "por_dia": [{"nombre": d, "cantidad": por_dia.get(d, 0)} for d in DIAS_SEMANA],
        "por_rubro": [{"nombre": k, "cantidad": v} for k, v in por_rubro.most_common()],
        "por_motivo": [
            {"nombre": k, "cantidad": v}
            for k, v in Counter(normalizar_motivo(r.tipo_falta, r.comentario) for r in registros).most_common()
        ],
    }


def del_mes(registros: Iterable[RegistroLike], hoy: date) -> list[RegistroLike]:
    return [r for r in registros if r.fecha_incidencia.year == hoy.year and r.fecha_incidencia.month == hoy.month]


def resumen_mes_por_persona(historial: Iterable[RegistroLike], personas: Iterable[str], hoy: date) -> list[dict]:
    """
    Llegadas tarde y demás incidencias del MES EN CURSO de cada persona, sobre
    su historial completo (no sobre el rango de fechas filtrado).
    """
    mes = del_mes(historial, hoy)
    filas = []
    for persona in sorted(set(personas)):
        suyas = [r for r in mes if r.colaborador == persona]
        n_tarde = sum(1 for r in suyas if es_llegada_tarde(r.tipo_falta, r.comentario))
        filas.append({"colaborador": persona, "tardes": n_tarde, "otras": len(suyas) - n_tarde, "total": len(suyas)})
    return filas


def consolidado_mes(historial: Iterable[RegistroLike], hoy: date) -> list[dict]:
    """Cuántas faltas lleva cada colaborador en el mes (todo el personal), de mayor a menor."""
    conteo = Counter(r.colaborador for r in del_mes(historial, hoy))
    return [{"colaborador": c, "faltas": n} for c, n in conteo.most_common()]
