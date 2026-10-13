"""
Centro de Reportes: cierre diario y pendientes para Dispatch.

Port de la pestaña "📊 Centro de Reportes" de app.py y de sus PDF en tools.py
(generar_pdf_cierre_diario, generar_pdf_primera_orden,
generar_pdf_promedio_arranque, generar_pdf_cerradas_detalle y
generar_pdf_pendientes_dispatch). Funciones puras sobre órdenes: se prueban
sin base de datos.

Diferencias a propósito con el sistema anterior:
- El día de un cierre es siempre el día operativo (HORA_LIQ - 6 h), igual que
  "Cerradas hoy" del Monitor. El PDF viejo usaba la fecha sin restar las 6 h y
  la pantalla sí la restaba, así que no siempre coincidían entre sí.
- La antigüedad de una orden liquidada son los días entre su apertura y su
  cierre (antes, los días de retraso que tenía la última vez que el robot la vio).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import Protocol

from app.dominio import constantes as c
from app.dominio.clasificador import subtipo_instalacion
from app.dominio.fechas import dia_operativo
from app.dominio.monitor import OrdenLike, cerradas_hoy, consolidado, dias_retraso
from app.dominio.normalizacion import tecnico_asignado


class OrdenReporte(OrdenLike, Protocol):
    cliente: str | None
    nombre: str | None
    colonia: str | None
    sector: str | None
    comentario: str | None


def _act(o: OrdenReporte) -> str:
    return (o.actividad or "").upper()


def _txt(o: OrdenReporte) -> str:
    return f"{o.actividad or ''} {o.comentario or ''}".upper()


def minutos(o: OrdenReporte) -> int | None:
    if o.hora_ini and o.hora_liq and o.hora_liq >= o.hora_ini:
        return int((o.hora_liq - o.hora_ini).total_seconds() // 60)
    return None


def _promedio(valores: list[int]) -> float:
    return round(sum(valores) / len(valores), 1) if valores else 0.0


def _conteo(valores: Iterable[str]) -> list[dict]:
    return [{"nombre": k, "cantidad": v} for k, v in Counter(valores).most_common()]


# ------------------------------------------------------------------------------
# Cierre diario
# ------------------------------------------------------------------------------
def cerradas_del_dia(ordenes: Iterable[OrdenReporte], fecha: date) -> list[OrdenReporte]:
    """Las mismas que cuenta "Cerradas hoy" del Monitor, para cualquier día. Por hora de cierre."""
    return sorted(cerradas_hoy(ordenes, fecha), key=lambda o: o.hora_liq)


def tipo_orden(o: OrdenReporte) -> str:
    t = _txt(o)
    if re.search("INS|NUEVA|ADIC|CAMBIO|PLEX|MIGRACI|RECUP", t):
        return "INSTALACION"
    if re.search("SOP|FALLA|MANT", t):
        return "MANTENIMIENTO"
    return "OTROS"


def tipo_detalle(o: OrdenReporte) -> str:
    t = _txt(o)
    if "RECON" in t:
        return "RECONEXIONES"
    if "TRASLADO" in t:
        return "TRASLADOS"
    return tipo_orden(o)


def aporte_meta(o: OrdenReporte) -> float:
    """Puntos que aporta una orden a la meta diaria del técnico (100 % = jornada completa)."""
    act, txt = _act(o), _txt(o)
    if "PEXTERNO" in act:
        return 100.0
    if re.search("ADIC|CAMBIO|MIGRACI|RECUP", txt):
        return 12.5
    if re.search("INS|NUEVA|PLEX|SPLITTEROPT", act):
        return 25.0
    return 12.5


BONO_RUTA_MIXTA = 10.0


def eficiencia_por_tecnico(cerradas: Iterable[OrdenReporte]) -> list[dict]:
    """Puntos por meta + 10 % de bono si el técnico hizo más de un tipo de orden en el día."""
    por_tecnico: dict[str, dict] = {}
    for o in cerradas:
        t = por_tecnico.setdefault(o.tecnico or "N/D", {"tecnico": o.tecnico or "N/D", "ins": 0, "sop": 0,
                                                        "otr": 0, "puntos_base": 0.0})
        t[{"INSTALACION": "ins", "MANTENIMIENTO": "sop", "OTROS": "otr"}[tipo_orden(o)]] += 1
        t["puntos_base"] += aporte_meta(o)
    filas = []
    for t in por_tecnico.values():
        tipos = sum(1 for k in ("ins", "sop", "otr") if t[k] > 0)
        t["bono_mixto"] = BONO_RUTA_MIXTA if tipos > 1 else 0.0
        t["logro_final"] = t["puntos_base"] + t["bono_mixto"]
        filas.append(t)
    return sorted(filas, key=lambda t: (-t["logro_final"], t["tecnico"]))


RANGOS_ATENCION = ("Menos de 1 día", "De 1 a 3 días", "De 4 a 6 días", "Más de 6 días")


def dias_atencion(o: OrdenReporte) -> int | None:
    """Días entre la apertura y el cierre (día operativo) de una orden liquidada."""
    if o.fecha_ape is None or o.hora_liq is None:
        return None
    return max(0, (dia_operativo(o.hora_liq) - o.fecha_ape.date()).days)


def rango_atencion(dias: int) -> str:
    if dias < 1:
        return RANGOS_ATENCION[0]
    if dias <= 3:
        return RANGOS_ATENCION[1]
    if dias <= 6:
        return RANGOS_ATENCION[2]
    return RANGOS_ATENCION[3]


def _ciudad(o: OrdenReporte) -> str:
    return (o.sector or "").strip().upper() or "SIN CIUDAD"


def tiempos_por_rango(cerradas: Iterable[OrdenReporte]) -> dict:
    """Cuántas liquidadas cayeron en cada rango de antigüedad, por ciudad."""
    filas = [(o, d) for o in cerradas if (d := dias_atencion(o)) is not None]
    ciudades = [k for k, _ in Counter(_ciudad(o) for o, _ in filas).most_common()]
    conteo = Counter((rango_atencion(d), _ciudad(o)) for o, d in filas)
    totales = Counter(_ciudad(o) for o, _ in filas)

    def celda(rango: str, ciudad: str) -> dict:
        n = conteo.get((rango, ciudad), 0)
        return {"cantidad": n, "porcentaje": round(n / totales[ciudad] * 100) if totales[ciudad] else 0}

    return {
        "ciudades": ciudades,
        "filas": [{"rango": r, "celdas": [celda(r, ci) for ci in ciudades]} for r in RANGOS_ATENCION],
        "totales": [totales[ci] for ci in ciudades],
    }


def cerradas_por_ciudad(cerradas: Iterable[OrdenReporte]) -> list[dict]:
    """Por ciudad: cantidad y minutos promedio de atención por tipo de actividad."""
    grupos: dict[str, dict[str, list[int | None]]] = defaultdict(lambda: defaultdict(list))
    for o in cerradas:
        grupos[_ciudad(o)][tipo_detalle(o)].append(minutos(o))
    salida = []
    for ciudad in sorted(grupos):
        tipos = sorted(grupos[ciudad].items(), key=lambda kv: -len(kv[1]))
        filas = [{"tipo": t, "cantidad": len(v), "minutos": round(_promedio([m for m in v if m is not None]))}
                 for t, v in tipos]
        todos = [m for _, v in tipos for m in v]
        salida.append({"ciudad": ciudad, "filas": filas, "cantidad": len(todos),
                       "minutos": round(_promedio([m for m in todos if m is not None]))})
    return salida


def tiempos_por_tecnico_actividad(cerradas: Iterable[OrdenReporte]) -> list[dict]:
    grupos: dict[str, dict[str, list[int | None]]] = defaultdict(lambda: defaultdict(list))
    for o in cerradas:
        grupos[o.tecnico or "N/D"][o.actividad].append(minutos(o))
    salida = []
    for tecnico in sorted(grupos):
        acts = sorted(grupos[tecnico].items(), key=lambda kv: -len(kv[1]))
        todos = [m for _, v in acts for m in v]
        salida.append({
            "tecnico": tecnico,
            "filas": [{"actividad": a, "cantidad": len(v), "minutos": _promedio([m for m in v if m is not None])}
                      for a, v in acts],
            "cantidad": len(todos), "minutos": _promedio([m for m in todos if m is not None]),
        })
    return salida


def desglose_produccion(cerradas: list[OrdenReporte]) -> dict:
    """Lo producido en el día en cuatro grupos (como en la pantalla anterior)."""
    patron_otros = "SOP|MANT|INS|PLEXISCA|PLEX|PEXTERNO|SPLITTEROPT|NUEVA|ADIC|CAMBIO|MIGRACI|RECUP"
    return {
        "sop": _conteo(o.actividad for o in cerradas if re.search("SOP|FALLA|MANT", _act(o))),
        "instalaciones": _conteo(subtipo_instalacion(_txt(o)) for o in cerradas
                                 if re.search("INS|NUEVA|ADIC|CAMBIO|MIGRACI|RECUP", _txt(o))),
        "plex": _conteo(o.actividad for o in cerradas if re.search("PLEXISCA|PEXTERNO|SPLITTEROPT", _act(o))),
        "otros": _conteo(o.actividad for o in cerradas if not re.search(patron_otros, _txt(o))),
    }


def resumen_por_actividad(cerradas: list[OrdenReporte]) -> list[dict]:
    return _conteo(o.actividad for o in cerradas)


def distribucion(cerradas: list[OrdenReporte]) -> list[dict]:
    """Instalaciones vs mantenimientos vs otros (por actividad), para la gráfica del PDF."""
    tipos = Counter(
        "Instalaciones" if re.search("INS|NUEVA|ADIC|CAMBIO|PLEX", _act(o))
        else "Mantenimientos" if re.search("SOP|FALLA|MANT", _act(o)) else "Otros"
        for o in cerradas
    )
    total = sum(tipos.values())
    return [{"nombre": k, "cantidad": tipos[k], "porcentaje": round(tipos[k] / total * 100) if total else 0}
            for k in ("Instalaciones", "Mantenimientos", "Otros") if tipos[k]]


def avance(pendientes_asignadas: list[OrdenReporte], cerradas: list[OrdenReporte], fecha: date) -> list[dict]:
    """Avance del día por segmento (mismo cálculo que la pestaña Avance del Monitor)."""
    return [consolidado(seg, pendientes_asignadas, cerradas, fecha)
            for seg in (c.SEGMENTO_RESIDENCIAL, c.SEGMENTO_PLEX, "GLOBAL")]


def primera_orden(ordenes: Iterable[OrdenReporte], fecha: date) -> list[dict]:
    """La primera orden que inició cada técnico ese día, de la más temprana a la más tardía."""
    primeras: dict[str, OrdenReporte] = {}
    for o in ordenes:
        if (o.hora_ini is None or o.hora_ini.date() != fecha or not tecnico_asignado(o.tecnico)
                or not (o.es_viva or o.estado == "CERRADA")):
            continue
        if o.tecnico not in primeras or o.hora_ini < primeras[o.tecnico].hora_ini:
            primeras[o.tecnico] = o
    return [{"tecnico": o.tecnico, "hora_ini": o.hora_ini, "colonia": o.colonia, "num": o.num,
             "actividad": o.actividad} for o in sorted(primeras.values(), key=lambda o: o.hora_ini)]


def _hhmmss(segundos: float) -> str:
    s = int(segundos)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def promedio_arranque(ordenes: Iterable[OrdenReporte], desde: date, hasta: date) -> list[dict]:
    """Hora promedio en que cada técnico arranca su primera orden en el rango."""
    primeras: dict[tuple[str, date], datetime] = {}
    for o in ordenes:
        if o.hora_ini is None or not tecnico_asignado(o.tecnico) or not desde <= o.hora_ini.date() <= hasta:
            continue
        clave = (o.tecnico.strip(), o.hora_ini.date())
        if clave not in primeras or o.hora_ini < primeras[clave]:
            primeras[clave] = o.hora_ini
    por_tecnico: dict[str, list[int]] = defaultdict(list)
    for (tecnico, _), inicio in primeras.items():
        por_tecnico[tecnico].append(inicio.hour * 3600 + inicio.minute * 60 + inicio.second)
    filas = [{"tecnico": t, "dias": len(s), "segundos": sum(s) / len(s), "hora_promedio": _hhmmss(sum(s) / len(s))}
             for t, s in por_tecnico.items()]
    return sorted(filas, key=lambda f: f["segundos"])


# ------------------------------------------------------------------------------
# Pendientes generales (Dispatch)
# ------------------------------------------------------------------------------
CATEGORIAS_DISPATCH = ("INSTALACIONES", "MANTENIMIENTOS", "PLEX", "OTRAS")


def categoria_dispatch(o: OrdenReporte) -> str:
    act, txt = _act(o), _txt(o)
    if re.search("INS|NUEVA|ADIC|CAMBIO|MIGRACI|RECUP", txt) and not re.search("SOP|FALLA|MANT", act):
        return "INSTALACIONES"
    if re.search("SOP|FALLA|MANT", act):
        return "MANTENIMIENTOS"
    if re.search("PLEX|PEXTERNO|SPLITTEROPT", txt):
        return "PLEX"
    return "OTRAS"


def _subtipo_instalacion_dispatch(o: OrdenReporte) -> str:
    t = _txt(o)
    if "ADIC" in t:
        return "Instalación Adición"
    if re.search("CAMBIO|MIGRACI", t):
        return "Instalación Cambio de Medio"
    if "RECUP" in t:
        return "Recuperado"
    return "Instalación Nueva"


def _subtipo_sop_dispatch(o: OrdenReporte) -> str:
    if o.es_offline:
        return "ONT/ONU Offline"
    com = (o.comentario or "").upper()
    if re.search("TV|ANALOGIC|DIGITAL", com):
        return "Problemas de TV (Analógica o Digital)"
    if re.search("FIBRA|OPTIC|OPTICO|PON|SEÑAL", com):
        return "Problemas de Fibra / Óptica"
    return "Otro Diagnóstico"


CUBETAS_DISPATCH = ((">= 7 días", 7, None), ("4 a 6 días", 4, 6), ("1 a 3 días", 1, 3), ("Del día", 0, 0))


def pendientes_dispatch(pendientes: list[OrdenReporte], hoy: date) -> dict:
    """Resumen de carga para el siguiente turno (lo que se manda a Dispatch)."""
    asignada = {o.num: tecnico_asignado(o.tecnico) for o in pendientes}
    por_categoria = Counter((categoria_dispatch(o), asignada[o.num]) for o in pendientes)
    resumen = [{"categoria": cat, "asignadas": por_categoria[(cat, True)], "sin_asignar": por_categoria[(cat, False)],
                "total": por_categoria[(cat, True)] + por_categoria[(cat, False)]} for cat in CATEGORIAS_DISPATCH]
    dias = [dias_retraso(o, hoy) for o in pendientes]
    act = {o.num: _act(o) for o in pendientes}
    es_ins = {o.num: bool(re.search("INS|NUEVA|ADIC|CAMBIO|MIGRACI|RECUP", _txt(o)))
              and not re.search("SOP|FALLA|MANT", act[o.num]) for o in pendientes}
    es_sop = {o.num: bool(re.search("SOP|FALLA|MANT", act[o.num])) for o in pendientes}
    return {
        "resumen": resumen,
        "totales": {"asignadas": sum(asignada.values()), "sin_asignar": len(pendientes) - sum(asignada.values()),
                    "total": len(pendientes)},
        "cubetas": [{"nombre": n, "cantidad": sum(1 for d in dias if d >= desde and (hasta is None or d <= hasta))}
                    for n, desde, hasta in CUBETAS_DISPATCH],
        "instalaciones": _conteo(_subtipo_instalacion_dispatch(o) for o in pendientes if es_ins[o.num]),
        "soporte": _conteo(_subtipo_sop_dispatch(o) for o in pendientes if es_sop[o.num]),
        "resto": _conteo(o.actividad for o in pendientes if not es_ins[o.num] and not es_sop[o.num]),
    }
