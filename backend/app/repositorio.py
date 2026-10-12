"""
Escritura de órdenes en la base de datos (la usan el robot y la importación
del historial).

Reemplaza la reescritura completa de Sheet1 en cada ciclo (26 mil+ filas por
lotes, con 503 de Google) por un upsert por número de orden.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import String, all_, any_, bindparam, func, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.normalizacion import OrdenNormalizada
from app.eventos import CANAL_ORDENES
from app.models import DispositivoFttx, EstadoRobot, Orden

# asyncpg admite hasta 32767 parámetros por sentencia; con ~30 columnas por
# orden, 500 filas por lote queda muy por debajo.
FILAS_POR_LOTE = 500


def _lista_param(nombre: str, valores: list[str]):
    """Una lista como UN solo parámetro de tipo arreglo (sirve con miles de valores)."""
    return bindparam(nombre, valores, type_=ARRAY(String))


def deduplicar(ordenes: Iterable[OrdenNormalizada]) -> list[OrdenNormalizada]:
    """
    Una fila por número de orden. Si Cepheus manda la misma orden dos veces,
    gana la que ya trae hora de liquidación (la más avanzada) y, entre
    iguales, la última recibida.
    """
    por_num: dict[str, OrdenNormalizada] = {}
    for orden in ordenes:
        previa = por_num.get(orden.num)
        if previa is None or orden.hora_liq is not None or previa.hora_liq is None:
            por_num[orden.num] = orden
    return list(por_num.values())


async def guardar_ordenes(sesion: AsyncSession, ordenes: Iterable[OrdenNormalizada]) -> int:
    """
    Inserta las órdenes nuevas y actualiza solo las que cambiaron (compara la
    huella del contenido), así un ciclo típico escribe unas pocas filas en vez
    de reescribir todo. Una orden ya liquidada (con hora_liq) nunca vuelve a
    quedar abierta porque llegue una copia vieja sin liquidación, igual que en
    la consolidación del robot anterior.

    Devuelve cuántas órdenes eran nuevas o cambiaron.
    """
    candidatas = deduplicar(ordenes)
    if not candidatas:
        return 0
    existentes = {
        num: (huella, vigente, liquidada)
        for num, huella, vigente, liquidada in await sesion.execute(
            select(Orden.num, Orden.huella, Orden.vigente, Orden.hora_liq.is_not(None))
            .where(Orden.num == any_(_lista_param("nums", [o.num for o in candidatas])))
        )
    }

    filas = []
    for orden in candidatas:
        huella = orden.huella()
        previa = existentes.get(orden.num)
        if previa is not None:
            huella_previa, vigente, liquidada = previa
            if (liquidada and orden.hora_liq is None) or (huella == huella_previa and vigente):
                continue
        filas.append(orden.como_fila() | {"huella": huella, "vigente": True})

    for i in range(0, len(filas), FILAS_POR_LOTE):
        stmt = insert(Orden).values(filas[i:i + FILAS_POR_LOTE])
        columnas = {k: stmt.excluded[k] for k in filas[0] if k != "num"}
        columnas["actualizado_en"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=[Orden.num],
            set_=columnas,
            # La misma regla, en la base, por si otro proceso escribió entre medio.
            where=or_(Orden.hora_liq.is_(None), stmt.excluded.hora_liq.is_not(None)),
        )
        await sesion.execute(stmt)
    return len(filas)


async def marcar_no_vigentes(sesion: AsyncSession, nums_recibidos: list[str]) -> int:
    """Órdenes vivas que ya no vinieron en esta consulta a Cepheus dejan de contar como pendientes."""
    if not nums_recibidos:
        return 0  # sin lista no se puede saber qué faltó; nunca se apagan todas
    resultado = await sesion.execute(
        update(Orden)
        .where(Orden.es_viva, Orden.vigente, Orden.num != all_(_lista_param("recibidos", nums_recibidos)))
        .values(vigente=False, actualizado_en=func.now())
    )
    return resultado.rowcount or 0


async def avisar_ordenes_actualizadas(sesion: AsyncSession, datos: dict) -> None:
    """NOTIFY a los navegadores conectados (se entrega al hacer commit)."""
    await sesion.execute(select(func.pg_notify(CANAL_ORDENES, json.dumps(datos, default=str))))


async def mx_por_tecnico(sesion: AsyncSession) -> dict[str, str]:
    filas = await sesion.execute(select(DispositivoFttx.tecnico_clave, DispositivoFttx.mx))
    return {clave: mx for clave, mx in filas if mx}


def clave_tecnico(tecnico: str | None) -> str:
    return (tecnico or "").strip().upper()


def aplicar_mx(ordenes: Iterable[OrdenNormalizada], catalogo: dict[str, str]) -> None:
    """El vehículo del catálogo FTTX tiene prioridad sobre el que traiga la orden."""
    for orden in ordenes:
        mx = catalogo.get(clave_tecnico(orden.tecnico))
        if mx:
            orden.mx = mx


async def guardar_estado_robot(sesion: AsyncSession, **campos) -> None:
    stmt = insert(EstadoRobot).values(id=1, **campos)
    stmt = stmt.on_conflict_do_update(index_elements=[EstadoRobot.id], set_=campos)
    await sesion.execute(stmt)
