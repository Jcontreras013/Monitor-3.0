from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import Config, SesionDB, UsuarioActual, poner_cookie_sesion
from app.models import Usuario
from app.permisos import modulos_de
from app.schemas import CambioClaveIn, LoginIn, UsuarioOut
from app.security import COOKIE_SESION, cifrar_clave, clave_coincide

router = APIRouter(prefix="/auth", tags=["auth"])

# Freno básico contra adivinar contraseñas: tras 5 intentos fallidos en 10
# minutos, ese usuario queda bloqueado hasta que los intentos viejos expiren.
_MAX_FALLOS = 5
_VENTANA_SEG = 600
_fallos: dict[str, deque[float]] = defaultdict(deque)
# Hash de relleno para que un usuario inexistente tarde lo mismo que uno real.
_HASH_RELLENO = cifrar_clave("relleno-para-igualar-tiempos")


def _bloqueado(usuario: str) -> bool:
    intentos = _fallos[usuario]
    limite = time.monotonic() - _VENTANA_SEG
    while intentos and intentos[0] < limite:
        intentos.popleft()
    return len(intentos) >= _MAX_FALLOS


@router.post("/login", response_model=UsuarioOut)
async def login(datos: LoginIn, response: Response, db: SesionDB, settings: Config):
    nombre_usuario = datos.usuario.strip().lower()
    if _bloqueado(nombre_usuario):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Espera unos minutos.")

    usuario = await db.scalar(select(Usuario).where(Usuario.usuario == nombre_usuario))
    valida = clave_coincide(datos.clave, usuario.clave_hash if usuario else _HASH_RELLENO)
    if not usuario or not valida or not usuario.activo:
        _fallos[nombre_usuario].append(time.monotonic())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")

    _fallos.pop(nombre_usuario, None)
    poner_cookie_sesion(response, usuario, settings)
    return usuario_out(usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(COOKIE_SESION, path="/")


@router.get("/me", response_model=UsuarioOut)
async def yo(usuario: UsuarioActual):
    return usuario_out(usuario)


def usuario_out(usuario: Usuario) -> UsuarioOut:
    salida = UsuarioOut.model_validate(usuario)
    salida.modulos = modulos_de(usuario.rol)
    return salida


@router.post("/cambiar-clave", status_code=status.HTTP_204_NO_CONTENT)
async def cambiar_clave(
    datos: CambioClaveIn, usuario: UsuarioActual, response: Response, db: SesionDB, settings: Config
):
    if not clave_coincide(datos.clave_actual, usuario.clave_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    usuario.clave_hash = cifrar_clave(datos.clave_nueva)
    usuario.clave_actualizada_en = datetime.now(UTC)
    await db.commit()
    # Las demás sesiones de este usuario quedan invalidadas; esta se renueva.
    poner_cookie_sesion(response, usuario, settings)
