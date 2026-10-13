"""Reprogramadas (órdenes agendadas a futuro) y No instalados (cierres NOINSTALADO de hoy)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.api.monitor import orden_out
from app.deps import SesionDB, requiere
from app.dominio import constantes as c
from app.dominio import monitor as m
from app.dominio.fechas import ahora_hn
from app.models import Orden
from app.schemas import OrdenOut

router = APIRouter(prefix="/reprogramadas", tags=["reprogramadas"], dependencies=[Depends(requiere("reprogramadas"))])


class OrdenAgendada(OrdenOut):
    dias_para_cita: int


class Reprogramadas(BaseModel):
    reprogramadas: list[OrdenAgendada]
    no_instalados: list[OrdenOut]


@router.get("", response_model=Reprogramadas)
async def listar(db: SesionDB):
    ahora = ahora_hn()
    hoy = ahora.date()
    futuras = (await db.scalars(select(Orden).where(
        Orden.vigente, Orden.es_viva, Orden.actividad.in_(c.ACTIVIDADES_PERMITIDAS),
        Orden.fecha_ape >= datetime.combine(hoy + timedelta(days=1), time()),
    ))).all()
    # El día operativo de un cierre (HORA_LIQ - 6 h) cae dentro de este rango.
    cierres = (await db.scalars(select(Orden).where(
        Orden.actividad.contains(m.ACTIVIDAD_NO_INSTALADO),
        Orden.hora_liq >= datetime.combine(hoy, time()),
        Orden.hora_liq < datetime.combine(hoy + timedelta(days=2), time()),
    ))).all()
    return Reprogramadas(
        reprogramadas=[
            OrdenAgendada(**orden_out(o, ahora).model_dump(), dias_para_cita=m.dias_para_cita(o, hoy))
            for o in m.reprogramadas(futuras, hoy)
        ],
        no_instalados=[orden_out(o, ahora) for o in m.no_instalados_hoy(cierres, hoy)],
    )
