"""Dependencias compartidas de FastAPI: base de datos, usuario en sesión y permisos."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import Usuario
from app.security import COOKIE_SESION, crear_token, leer_token

# Se renueva la cookie si al token le quedan menos de estos minutos: así la
# sesión vence tras SESION_MINUTOS de inactividad, igual que antes.
_RENOVAR_SI_QUEDAN_MIN = 25

# Roles con acceso solo a Expedientes (no ven el Monitor).
ROLES_SOLO_EXPEDIENTES = frozenset({"llamados"})


async def sesion_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sesiones() as sesion:
        yield sesion


SesionDB = Annotated[AsyncSession, Depends(sesion_db)]
Config = Annotated[Settings, Depends(get_settings)]


def poner_cookie_sesion(response: Response, usuario: Usuario, settings: Settings) -> None:
    token = crear_token(usuario.id, usuario.rol, settings.secreto_jwt(), settings.sesion_minutos)
    response.set_cookie(
        COOKIE_SESION,
        token,
        max_age=settings.sesion_minutos * 60,
        httponly=True,
        secure=settings.cookie_segura,
        samesite="lax",
        path="/",
    )


async def usuario_actual(request: Request, response: Response, db: SesionDB, settings: Config) -> Usuario:
    no_autorizado = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión vencida o inválida")
    token = request.cookies.get(COOKIE_SESION)
    datos = leer_token(token, settings.secreto_jwt()) if token else None
    if not datos:
        raise no_autorizado
    usuario = await db.get(Usuario, int(datos["sub"]))
    if usuario is None or not usuario.activo:
        raise no_autorizado
    # Un cambio de contraseña invalida las sesiones abiertas antes de él.
    emitido = datetime.fromtimestamp(datos["iat"], tz=UTC)
    if usuario.clave_actualizada_en and emitido < usuario.clave_actualizada_en.replace(microsecond=0):
        raise no_autorizado
    restante = datos["exp"] - datetime.now(UTC).timestamp()
    if restante < _RENOVAR_SI_QUEDAN_MIN * 60:
        poner_cookie_sesion(response, usuario, settings)
    return usuario


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]


async def usuario_monitor(usuario: UsuarioActual) -> Usuario:
    if usuario.rol in ROLES_SOLO_EXPEDIENTES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu rol no tiene acceso al Monitor")
    return usuario


UsuarioMonitor = Annotated[Usuario, Depends(usuario_monitor)]
