"""Contraseñas (argon2) y sesiones (JWT en cookie httpOnly)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

COOKIE_SESION = "monitor_sesion"
LARGO_MINIMO_CLAVE = 8
_ALGORITMO = "HS256"
_hasher = PasswordHasher()


def cifrar_clave(clave: str) -> str:
    return _hasher.hash(clave)


def clave_coincide(clave: str, clave_hash: str) -> bool:
    try:
        return _hasher.verify(clave_hash, clave)
    except (VerificationError, InvalidHashError):
        return False


def crear_token(usuario_id: int, rol: str, secreto: str, minutos: int) -> str:
    ahora = datetime.now(UTC)
    datos = {"sub": str(usuario_id), "rol": rol, "iat": ahora, "exp": ahora + timedelta(minutes=minutos)}
    return jwt.encode(datos, secreto, algorithm=_ALGORITMO)


def leer_token(token: str, secreto: str) -> dict | None:
    """Contenido del token, o None si es inválido o ya venció."""
    try:
        return jwt.decode(token, secreto, algorithms=[_ALGORITMO])
    except jwt.PyJWTError:
        return None
