"""
Robot de sincronización: Cepheus -> Postgres.

Corre en una PC dentro de la red de MAXCOM (la única que alcanza Cepheus):

    python -m worker.sync              # ciclo continuo (cada SYNC_INTERVALO_MINUTOS)
    python -m worker.sync --una-vez    # un solo ciclo y termina
    python -m worker.sync --backfill 60  # trae hasta 60 días atrás una vez y termina

En cada ciclo: consulta Cepheus, normaliza, hace upsert por número de orden,
marca como no vigentes las vivas que ya no vinieron, avisa a los navegadores
(NOTIFY) y deja el resultado en la tabla estado_robot, que la app muestra.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import repositorio
from app.config import Settings, get_settings
from app.db import crear_engine, crear_sesiones
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import normalizar_orden
from app.models import EstadoRobot
from worker.cepheus import DIAS_MAXIMOS_ATRAS, consultar_ordenes

log = logging.getLogger("robot")


@dataclass
class ResultadoCiclo:
    ok: bool
    motivo: str = ""
    recibidas: int = 0
    cambiadas: int = 0
    descartadas: int = 0
    no_vigentes: int = 0


async def ejecutar_ciclo(
    sesiones: async_sessionmaker[AsyncSession],
    settings: Settings,
    dias_atras: int | None = None,
    cliente_http: httpx.AsyncClient | None = None,
) -> ResultadoCiclo:
    dias = min(dias_atras or settings.sync_dias_atras, DIAS_MAXIMOS_ATRAS)
    inicio = datetime.now(UTC)
    ahora = ahora_hn()

    respuesta = await consultar_ordenes(settings, (ahora - timedelta(days=dias)).date(), cliente_http)
    if not respuesta.ordenes:
        return ResultadoCiclo(ok=False, motivo=respuesta.motivo or "Cepheus no devolvió órdenes")

    normalizadas = [o for crudo in respuesta.ordenes if (o := normalizar_orden(crudo, ahora)) is not None]
    async with sesiones() as sesion:
        repositorio.aplicar_mx(normalizadas, await repositorio.mx_por_tecnico(sesion))
        cambiadas = await repositorio.guardar_ordenes(sesion, normalizadas)
        no_vigentes = await repositorio.marcar_no_vigentes(sesion, [o.num for o in normalizadas])
        if cambiadas or no_vigentes:
            await repositorio.avisar_ordenes_actualizadas(
                sesion, {"cambiadas": cambiadas, "no_vigentes": no_vigentes, "en": inicio})
        await sesion.commit()

    return ResultadoCiclo(
        ok=True,
        recibidas=len(respuesta.ordenes),
        cambiadas=cambiadas,
        descartadas=len(respuesta.ordenes) - len(normalizadas),
        no_vigentes=no_vigentes,
    )


async def registrar_estado(
    sesiones: async_sessionmaker[AsyncSession], resultado: ResultadoCiclo, duracion: float
) -> None:
    ahora = datetime.now(UTC)
    async with sesiones() as sesion:
        previo = await sesion.get(EstadoRobot, 1)
        ultima_ok = ahora if resultado.ok else (previo.ultima_sync_ok if previo else None)
        await repositorio.guardar_estado_robot(
            sesion,
            ultimo_ciclo=ahora,
            sync_ok=resultado.ok,
            motivo=resultado.motivo[:2000],
            ultima_sync_ok=ultima_ok,
            ordenes_recibidas=resultado.recibidas,
            duracion_seg=round(duracion, 1),
        )
        await sesion.commit()


async def ciclo_protegido(sesiones, settings: Settings, dias_atras: int | None = None) -> ResultadoCiclo:
    """Un ciclo que nunca lanza excepción: cualquier falla queda registrada en estado_robot."""
    t0 = time.monotonic()
    try:
        resultado = await ejecutar_ciclo(sesiones, settings, dias_atras)
    except Exception as e:  # el robot no debe morir por un ciclo fallido
        log.exception("Falla en el ciclo")
        resultado = ResultadoCiclo(ok=False, motivo=f"falla inesperada: {e}")
    duracion = time.monotonic() - t0
    if resultado.ok:
        log.info("Ciclo OK en %.1fs: %s recibidas, %s nuevas o con cambios, %s descartadas, %s ya no vigentes",
                 duracion, resultado.recibidas, resultado.cambiadas, resultado.descartadas, resultado.no_vigentes)
    else:
        log.warning("Ciclo SIN datos nuevos (%.1fs): %s", duracion, resultado.motivo)
    try:
        await registrar_estado(sesiones, resultado, duracion)
    except Exception:
        log.exception("No se pudo guardar el estado del robot")
    return resultado


async def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Robot de sincronización Cepheus -> Postgres")
    parser.add_argument("--una-vez", action="store_true", help="corre un solo ciclo y termina")
    parser.add_argument("--backfill", type=int, metavar="DIAS",
                        help=f"trae hasta DIAS días atrás (máx. {DIAS_MAXIMOS_ATRAS}) una vez y termina")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = crear_engine(settings.database_url)
    sesiones = crear_sesiones(engine)
    try:
        if args.backfill or args.una_vez:
            resultado = await ciclo_protegido(sesiones, settings, args.backfill)
            return 0 if resultado.ok else 1
        log.info("Robot iniciado: un ciclo cada %s minutos", settings.sync_intervalo_minutos)
        while True:
            await ciclo_protegido(sesiones, settings)
            await asyncio.sleep(settings.sync_intervalo_minutos * 60)
    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    raise SystemExit(asyncio.run(principal()))


if __name__ == "__main__":
    main()
