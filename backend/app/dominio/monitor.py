"""
Indicadores del Monitor en Vivo.

Port de la pantalla "⚡ Monitor en Vivo" de monitor-operativo/app.py, con las
mismas reglas (para poder comparar los números de ambos sistemas mientras
corren en paralelo). Trabaja sobre cualquier objeto con los atributos de una
orden (el modelo de la base de datos o un dataclass en las pruebas), así que
se prueba sin base de datos.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Protocol

from app.dominio import constantes as c
from app.dominio.fechas import dia_operativo
from app.dominio.normalizacion import es_no_critica, es_plex, es_tecnico_sin_retraso, tecnico_asignado


class OrdenLike(Protocol):
    num: str
    actividad: str
    estado: str
    tecnico: str | None
    fecha_ape: datetime | None
    hora_ini: datetime | None
    hora_liq: datetime | None
    es_viva: bool
    es_offline: bool
    motivo: str
    segmento: str
    grupo_tablero: str
    subtipo_tablero: str


@dataclass
class Filtros:
    actividades: list[str] = field(default_factory=list)
    estados: list[str] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)
    tecnico: str | None = None
    solo_criticas: bool = False
    no_asignadas: bool = False


# ------------------------------------------------------------------------------
# Cálculos por orden que dependen de la hora actual
# ------------------------------------------------------------------------------
def dias_retraso(orden: OrdenLike, hoy: date) -> int:
    if orden.fecha_ape is None or es_tecnico_sin_retraso(orden.tecnico):
        return 0
    return max(0, (hoy - orden.fecha_ape.date()).days)


def cubeta_retraso(dias: int) -> str:
    if dias >= 7:
        return ">= 7 Dia"
    if dias >= 4:
        return "= 4 a 6 Dias"
    if dias >= 1:
        return "= 1 a 3 Dias"
    return "= 0 Dia"


def alerta_tiempo(orden: OrdenLike, ahora: datetime) -> bool:
    """Soporte de fibra iniciado hace más de 2 h y sin liquidar."""
    return (
        orden.hora_ini is not None
        and orden.hora_liq is None
        and ahora - orden.hora_ini > timedelta(minutes=c.MINUTOS_ALERTA_SOP)
        and orden.estado != "CERRADA"
        and "SOPFIBRA" in orden.actividad
        and not es_no_critica(orden.actividad)
    )


def es_critica(orden: OrdenLike, ahora: datetime) -> bool:
    return (
        (orden.es_offline or alerta_tiempo(orden, ahora))
        and "SOP" in orden.actividad
        and not es_no_critica(orden.actividad)
    )


# ------------------------------------------------------------------------------
# Selección de órdenes
# ------------------------------------------------------------------------------
def base_activa(ordenes: Iterable[OrdenLike]) -> list[OrdenLike]:
    """Solo actividades de la lista blanca (visitas técnicas reales)."""
    return [o for o in ordenes if o.actividad in c.ACTIVIDADES_PERMITIDAS]


def aplicar_filtros(ordenes: Iterable[OrdenLike], filtros: Filtros, ahora: datetime) -> list[OrdenLike]:
    resultado = list(ordenes)
    if filtros.actividades:
        resultado = [o for o in resultado if o.actividad in filtros.actividades]
    if filtros.estados:
        resultado = [o for o in resultado if o.estado in filtros.estados]
    if filtros.motivos:
        resultado = [o for o in resultado if o.motivo in filtros.motivos]
    if filtros.solo_criticas:
        resultado = [o for o in resultado if es_critica(o, ahora)]
    if filtros.no_asignadas:
        resultado = [o for o in resultado if not tecnico_asignado(o.tecnico)]
    if filtros.tecnico:
        resultado = [o for o in resultado if o.tecnico == filtros.tecnico]
    return resultado


def pendientes(filtradas: Iterable[OrdenLike]) -> list[OrdenLike]:
    """Órdenes vivas (asignadas y no asignadas)."""
    return [
        o for o in filtradas
        if o.es_viva and (tecnico_asignado(o.tecnico) or o.actividad in c.ACTIVIDADES_PERMITIDAS)
    ]


def cerradas_hoy(filtradas: Iterable[OrdenLike], hoy: date) -> list[OrdenLike]:
    """
    Cerradas con técnico cuyo cierre cae en `hoy`. Igual que el sistema
    anterior, a HORA_LIQ se le restan 6 h antes de comparar con la fecha de hoy.
    """
    return [
        o for o in filtradas
        if o.hora_liq is not None
        and dia_operativo(o.hora_liq) == hoy
        and o.estado == "CERRADA"
        and o.actividad in c.ACTIVIDADES_PERMITIDAS
        and tecnico_asignado(o.tecnico)
    ]


# ------------------------------------------------------------------------------
# Resumen completo
# ------------------------------------------------------------------------------
def _pct(parte: int, total: int) -> float:
    return round(parte / total * 100, 1) if total else 0.0


def _conteo(valores: Iterable[str]) -> list[dict]:
    return [{"nombre": k, "cantidad": v} for k, v in Counter(valores).most_common()]


def _consolidado(segmento: str, pend: list[OrdenLike], cerr: list[OrdenLike], hoy: date) -> dict:
    if segmento != "GLOBAL":
        pend = [o for o in pend if o.segmento == segmento]
        cerr = [o for o in cerr if o.segmento == segmento]
    p_mora = sum(1 for o in pend if dias_retraso(o, hoy) > 0)
    p_hoy = len(pend) - p_mora
    c_mora = sum(1 for o in cerr if o.fecha_ape is not None and o.fecha_ape.date() < hoy)
    c_hoy = sum(1 for o in cerr if o.fecha_ape is not None and o.fecha_ape.date() == hoy)
    tot_mora, tot_hoy = p_mora + c_mora, p_hoy + c_hoy
    return {
        "segmento": segmento,
        "total": tot_mora + tot_hoy,
        "cerradas": c_mora + c_hoy,
        "porcentaje": _pct(c_mora + c_hoy, tot_mora + tot_hoy),
        "mora_total": tot_mora,
        "mora_cerradas": c_mora,
        "mora_porcentaje": _pct(c_mora, tot_mora),
        "hoy_total": tot_hoy,
        "hoy_cerradas": c_hoy,
        "hoy_porcentaje": _pct(c_hoy, tot_hoy),
    }


def calcular_resumen(ordenes: Iterable[OrdenLike], filtros: Filtros, ahora: datetime) -> dict:
    hoy = ahora.date()
    base = base_activa(ordenes)
    filtradas = aplicar_filtros(base, filtros, ahora)

    pend = pendientes(filtradas)
    asignadas = [o for o in pend if tecnico_asignado(o.tecnico)]
    foco = [o for o in pend if not tecnico_asignado(o.tecnico)] if filtros.no_asignadas else asignadas
    cerr = cerradas_hoy(filtradas, hoy)

    retrasos = Counter(cubeta_retraso(dias_retraso(o, hoy)) for o in pend)
    total_retraso = sum(retrasos.values())

    sop = [o for o in pend if o.grupo_tablero == "SOP"]
    ins = [o for o in pend if o.grupo_tablero == "INS"]
    conteo_ins = Counter(o.subtipo_tablero for o in ins)
    plex = [o for o in pend if es_plex(o.actividad) and tecnico_asignado(o.tecnico)]

    # Cuántas pendientes deja ver cada filtro rápido, con los demás filtros
    # aplicados (los números que muestran los botones Todas / Críticas / No asignadas).
    sin_rapidos = pendientes(aplicar_filtros(base, replace(filtros, solo_criticas=False, no_asignadas=False), ahora))

    no_reconocidos = Counter(
        (o.estado or "(vacío)") for o in filtradas
        if not o.es_viva and not any(t in o.estado for t in c.ESTADOS_TERMINALES)
    )

    return {
        "generado_en": ahora,
        "dia": hoy,
        "mostrando": len(filtradas),
        "total_base": len(base),
        "kpis": {
            "pendientes_asignadas": len(asignadas),
            "cerradas_hoy": len(cerr),
            "tecnicos_en_ruta": 0 if filtros.no_asignadas else len({o.tecnico for o in foco}),
            "offline": sum(1 for o in pend if o.es_offline),
            "total_pendientes": len(pend),
        },
        "rapidos": {
            "todas": len(sin_rapidos),
            "criticas": sum(1 for o in sin_rapidos if es_critica(o, ahora)),
            "no_asignadas": sum(1 for o in sin_rapidos if not tecnico_asignado(o.tecnico)),
        },
        "retraso": [
            {"cubeta": k, "cantidad": retrasos.get(k, 0), "porcentaje": _pct(retrasos.get(k, 0), total_retraso)}
            for k in c.CUBETAS_RETRASO
        ],
        "tablero": {
            "sop": {
                "subtipos": _conteo(o.subtipo_tablero for o in sop),
                "total": len(sop),
                "exceden_2h": sum(1 for o in sop if alerta_tiempo(o, ahora)),
            },
            "instalaciones": {
                "subtipos": [{"nombre": k, "cantidad": conteo_ins.get(k, 0)} for k in c.SUBTIPOS_INSTALACION],
                "total": len(ins),
            },
            "plex": {"subtipos": _conteo(o.actividad for o in plex), "total": len(plex)},
        },
        "consolidado": [
            _consolidado(seg, foco, cerr, hoy)
            for seg in (c.SEGMENTO_RESIDENCIAL, c.SEGMENTO_PLEX, "GLOBAL")
        ],
        "estados_no_reconocidos": [
            {"nombre": k, "cantidad": v} for k, v in no_reconocidos.most_common(8)
        ],
    }
