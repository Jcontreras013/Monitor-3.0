from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.deps import Config, SesionDB, UsuarioActual
from app.models import EstadoRobot
from app.schemas import EstadoRobotOut

router = APIRouter(prefix="/robot", tags=["robot"])


@router.get("/estado", response_model=EstadoRobotOut | None)
async def estado(db: SesionDB, settings: Config, _: UsuarioActual):
    """Último ciclo del robot de sincronización, para avisar si dejó de reportar."""
    fila = await db.get(EstadoRobot, 1)
    if fila is None:
        return None
    salida = EstadoRobotOut.model_validate(fila)
    if fila.ultimo_ciclo:
        minutos = (datetime.now(UTC) - fila.ultimo_ciclo).total_seconds() / 60
        salida.minutos_desde_ultimo_ciclo = round(minutos, 1)
        # Más de dos ciclos sin noticias: el robot está caído o colgado.
        salida.atrasado = minutos > settings.sync_intervalo_minutos * 2 + 5
    return salida
