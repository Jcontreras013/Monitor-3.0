"""
Avisos en vivo: cuando el robot termina de guardar órdenes hace
NOTIFY ordenes_actualizadas en Postgres, y aquí se reenvía a cada navegador
conectado por Server-Sent Events. Así el Monitor se actualiza solo, sin que
cada usuario vuelva a descargar todo cada pocos minutos.
"""

from __future__ import annotations

import asyncio
import logging

import asyncpg

log = logging.getLogger(__name__)

CANAL_ORDENES = "ordenes_actualizadas"


class Notificador:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._suscriptores: set[asyncio.Queue[str]] = set()
        self._tarea: asyncio.Task | None = None

    def iniciar(self) -> None:
        self._tarea = asyncio.create_task(self._escuchar())

    async def detener(self) -> None:
        if self._tarea:
            self._tarea.cancel()
            try:
                await self._tarea
            except asyncio.CancelledError:
                pass

    def suscribir(self) -> asyncio.Queue[str]:
        cola: asyncio.Queue[str] = asyncio.Queue(maxsize=10)
        self._suscriptores.add(cola)
        return cola

    def desuscribir(self, cola: asyncio.Queue[str]) -> None:
        self._suscriptores.discard(cola)

    def publicar(self, mensaje: str) -> None:
        for cola in list(self._suscriptores):
            try:
                cola.put_nowait(mensaje)
            except asyncio.QueueFull:
                pass  # ese navegador va atrasado; con un aviso pendiente le basta

    async def _escuchar(self) -> None:
        """Mantiene una conexión LISTEN, reconectando si se cae."""
        espera = 5
        while True:
            conexion = None
            try:
                conexion = await asyncpg.connect(self._dsn)
                await conexion.add_listener(CANAL_ORDENES, lambda *args: self.publicar(args[3]))
                log.info("Escuchando avisos de Postgres en '%s'", CANAL_ORDENES)
                espera = 5
                while not conexion.is_closed():
                    await asyncio.sleep(30)
                    await conexion.execute("SELECT 1")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # red caída, pooler sin LISTEN, etc.
                log.warning("Sin avisos en vivo (%s); reintento en %ss", e, espera)
            finally:
                if conexion is not None and not conexion.is_closed():
                    await conexion.close()
            await asyncio.sleep(espera)
            espera = min(espera * 2, 300)
