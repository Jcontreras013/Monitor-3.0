from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.api import archivos, auth, eventos, expedientes, monitor, robot
from app.config import get_settings, url_libpq
from app.db import crear_engine, crear_sesiones
from app.eventos import Notificador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.secreto_jwt()  # falla al arrancar, no al primer login, si falta JWT_SECRET
    engine = crear_engine(settings.database_url)
    app.state.sesiones = crear_sesiones(engine)
    app.state.notificador = Notificador(url_libpq(settings.database_url))
    app.state.notificador.iniciar()
    try:
        yield
    finally:
        await app.state.notificador.detener()
        await engine.dispose()


def crear_app() -> FastAPI:
    app = FastAPI(title="Monitor Operativo 3.0", lifespan=lifespan)

    api = APIRouter(prefix="/api")
    api.include_router(auth.router)
    api.include_router(monitor.router)
    api.include_router(robot.router)
    api.include_router(eventos.router)
    api.include_router(archivos.router)
    api.include_router(expedientes.router)

    @api.get("/salud", tags=["salud"])
    async def salud():
        async with app.state.sesiones() as sesion:
            await sesion.execute(text("SELECT 1"))
        return {"ok": True}

    app.include_router(api)
    _servir_frontend(app, get_settings().frontend_dist)
    return app


def _servir_frontend(app: FastAPI, carpeta: str | None) -> None:
    """Sirve el build de React (frontend/dist) en la misma URL que la API."""
    if not carpeta or not Path(carpeta, "index.html").is_file():
        return
    raiz = Path(carpeta).resolve()

    @app.get("/{ruta:path}", include_in_schema=False)
    async def spa(ruta: str):
        if ruta == "api" or ruta.startswith("api/"):
            raise HTTPException(404)
        archivo = (raiz / ruta).resolve()
        if ruta and archivo.is_file() and archivo.is_relative_to(raiz):
            return FileResponse(archivo)
        return FileResponse(raiz / "index.html")


app = crear_app()
