"""
Las pruebas de dominio no necesitan base de datos. Las de API y robot usan
un Postgres real, indicado en TEST_DATABASE_URL (se omiten si no está):

    TEST_DATABASE_URL=postgresql://monitor:monitor@localhost:5432/monitor_test uv run pytest
"""

from __future__ import annotations

import os

import httpx
import pytest
from alembic.config import Config as AlembicConfig
from sqlalchemy import text

from alembic import command
from app.config import get_settings, url_asyncpg

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
TABLAS = ("ordenes", "usuarios", "estado_robot", "dispositivos_fttx", "personal", "expedientes", "archivos",
          "calidad_gestiones", "auditorias_campo")


@pytest.fixture(scope="session")
def url_bd() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL no está definida")
    url = url_asyncpg(TEST_DATABASE_URL)
    # Se prueba con las migraciones reales, no con create_all: así una
    # migración que no cuadre con los modelos rompe las pruebas.
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    # Falla si un modelo cambió y nadie generó la migración correspondiente.
    command.check(cfg)
    return url


@pytest.fixture
def entorno(url_bd, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", url_bd)
    monkeypatch.setenv("ENTORNO", "desarrollo")
    monkeypatch.setenv("JWT_SECRET", "secreto-de-pruebas-con-al-menos-32-caracteres")
    monkeypatch.setenv("COOKIE_SEGURA", "false")
    monkeypatch.setenv("FRONTEND_DIST", "")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
async def sesiones(entorno):
    from app.db import crear_engine, crear_sesiones

    engine = crear_engine(entorno.database_url)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLAS)} RESTART IDENTITY"))
    yield crear_sesiones(engine)
    await engine.dispose()


@pytest.fixture
async def cliente(sesiones):
    from app.main import crear_app, lifespan

    app = crear_app()
    async with lifespan(app):
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte, base_url="http://test") as c:
            yield c


@pytest.fixture
def crear_usuario(sesiones):
    from app.models import Usuario
    from app.security import cifrar_clave

    async def _crear(usuario="javier", clave="clave-segura-1", rol="admin", **extra):
        async with sesiones() as s:
            s.add(Usuario(usuario=usuario, nombre=usuario.title(), rol=rol, clave_hash=cifrar_clave(clave), **extra))
            await s.commit()

    return _crear
