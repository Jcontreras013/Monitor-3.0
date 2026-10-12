from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.deps import SesionDB, UsuarioActual

router = APIRouter(tags=["eventos"])

_LATIDO_SEG = 25


@router.get("/eventos")
async def eventos(request: Request, db: SesionDB, _: UsuarioActual):
    """Server-Sent Events: avisa al navegador cuando hay órdenes nuevas."""
    # La conexión puede durar horas: se devuelve al pool la conexión a la base
    # que se usó para validar la sesión, en vez de retenerla todo ese tiempo.
    await db.close()
    notificador = request.app.state.notificador
    cola = notificador.suscribir()

    async def flujo() -> AsyncIterator[str]:
        try:
            yield "retry: 10000\n\n"
            while not await request.is_disconnected():
                try:
                    mensaje = await asyncio.wait_for(cola.get(), timeout=_LATIDO_SEG)
                    yield f"event: ordenes\ndata: {mensaje}\n\n"
                except TimeoutError:
                    yield ": latido\n\n"  # mantiene viva la conexión a través de proxies
        finally:
            notificador.desuscribir(cola)

    return StreamingResponse(
        flujo(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
