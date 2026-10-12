from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import SesionDB, UsuarioMonitor
from app.dominio import constantes as c
from app.dominio import monitor as m
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import tecnico_asignado
from app.models import Orden
from app.schemas import OpcionesFiltro, OrdenOut, ResumenMonitor

router = APIRouter(prefix="/monitor", tags=["monitor"])

# Cuánto historial reciente carga el Monitor además de las órdenes vivas
# (igual que el sistema anterior: últimos 7 días).
DIAS_VENTANA = 7


def filtros_query(
    actividad: Annotated[list[str], Query()] = [],
    estado: Annotated[list[str], Query()] = [],
    motivo: Annotated[list[str], Query()] = [],
    tecnico: str | None = None,
    solo_criticas: bool = False,
    no_asignadas: bool = False,
) -> m.Filtros:
    return m.Filtros(
        actividades=actividad, estados=estado, motivos=motivo,
        tecnico=tecnico or None, solo_criticas=solo_criticas, no_asignadas=no_asignadas,
    )


FiltrosDep = Annotated[m.Filtros, Depends(filtros_query)]


async def cargar_ordenes_monitor(db: AsyncSession, ahora: datetime) -> list[Orden]:
    """Órdenes vivas vigentes + las cerradas o abiertas en los últimos días."""
    desde = ahora - timedelta(days=DIAS_VENTANA)
    stmt = select(Orden).where(
        Orden.actividad.in_(c.ACTIVIDADES_PERMITIDAS),
        or_(Orden.vigente, ~Orden.es_viva),
        or_(Orden.es_viva, Orden.hora_liq >= desde, Orden.fecha_ape >= desde),
    )
    return list((await db.scalars(stmt)).all())


def orden_out(o: Orden, ahora: datetime) -> OrdenOut:
    tiempo = None
    if o.hora_ini and o.hora_liq:
        tiempo = int((o.hora_liq - o.hora_ini).total_seconds() // 60)
    # El GPS es la ubicación EN VIVO del técnico: solo tiene sentido con la
    # orden iniciada y todavía abierta.
    gps = o.gps if (o.hora_ini is not None and o.es_viva) else None
    return OrdenOut(
        num=o.num, actividad=o.actividad, estado=o.estado, tecnico=o.tecnico, cliente=o.cliente,
        nombre=o.nombre, colonia=o.colonia, sector=o.sector, comentario=o.comentario,
        comentario_cierre=o.comentario_cierre, razon_cierre=o.razon_cierre, olt=o.olt, pon=o.pon,
        mx=o.mx, gps=gps, hora_ini=o.hora_ini, hora_liq=o.hora_liq, fecha_ape=o.fecha_ape,
        dias_retraso=m.dias_retraso(o, ahora.date()), tiempo_real_min=tiempo,
        es_offline=o.es_offline, alerta_tiempo=m.alerta_tiempo(o, ahora), motivo=o.motivo,
        segmento=o.segmento, grupo_tablero=o.grupo_tablero, subtipo_tablero=o.subtipo_tablero,
    )


@router.get("/resumen", response_model=ResumenMonitor)
async def resumen(filtros: FiltrosDep, db: SesionDB, _: UsuarioMonitor):
    ahora = ahora_hn()
    return m.calcular_resumen(await cargar_ordenes_monitor(db, ahora), filtros, ahora)


class Vista(StrEnum):
    pendientes = "pendientes"
    cerradas_hoy = "cerradas_hoy"


@router.get("/ordenes", response_model=list[OrdenOut])
async def ordenes(filtros: FiltrosDep, db: SesionDB, _: UsuarioMonitor, vista: Vista = Vista.pendientes):
    ahora = ahora_hn()
    filtradas = m.aplicar_filtros(m.base_activa(await cargar_ordenes_monitor(db, ahora)), filtros, ahora)
    if vista is Vista.cerradas_hoy:
        lista = sorted(m.cerradas_hoy(filtradas, ahora.date()), key=lambda o: o.hora_liq, reverse=True)
    else:
        hoy = ahora.date()
        lista = sorted(
            m.pendientes(filtradas),
            key=lambda o: (-m.dias_retraso(o, hoy), o.fecha_ape or datetime.max),
        )
    return [orden_out(o, ahora) for o in lista]


@router.get("/filtros", response_model=OpcionesFiltro)
async def opciones_filtro(db: SesionDB, _: UsuarioMonitor):
    base = m.base_activa(await cargar_ordenes_monitor(db, ahora_hn()))
    return OpcionesFiltro(
        actividades=sorted({o.actividad for o in base if o.actividad}),
        estados=sorted({o.estado for o in base if o.estado}),
        motivos=sorted({o.motivo for o in base if o.motivo}),
        tecnicos=sorted({o.tecnico for o in base if tecnico_asignado(o.tecnico)}),
    )
