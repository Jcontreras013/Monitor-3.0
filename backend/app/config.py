"""Configuración por variables de entorno (o archivo .env), nunca en el código."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def url_asyncpg(url: str) -> str:
    """
    Acepta la URL tal como la dan Supabase/Neon/Railway (postgres:// o
    postgresql://, con sslmode=...) y la deja en el formato que espera
    SQLAlchemy con asyncpg.
    """
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            url = "postgresql+asyncpg://" + url[len(prefijo):]
            break
    return url.replace("sslmode=", "ssl=")


def url_libpq(url: str) -> str:
    """La misma URL en formato plano, para abrir una conexión asyncpg directa (LISTEN)."""
    return url_asyncpg(url).replace("postgresql+asyncpg://", "postgresql://", 1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://monitor:monitor@localhost:5432/monitor"

    # Firma de las sesiones. En producción DEBE venir del entorno.
    jwt_secret: str = ""
    sesion_minutos: int = 30
    cookie_segura: bool = True
    entorno: str = "produccion"  # "desarrollo" permite jwt_secret vacío

    # Carpeta con el build del frontend (frontend/dist) para servirlo desde la API.
    frontend_dist: str | None = None

    # Robot de sincronización con Cepheus
    cepheus_url: str = ""
    cepheus_usuario: str = ""
    cepheus_contrasena: str = ""
    # Lista separada por comas: CEPHEUS_USUARIOS_CONSULTA=usuario1,usuario2
    cepheus_usuarios_consulta: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Cepheus es un servidor interno con certificado propio: se puede apuntar a
    # su CA (ruta a un .pem) o, como último recurso, desactivar la verificación.
    cepheus_verificar_tls: bool | str = True
    cepheus_timeout_seg: int = 240
    sync_intervalo_minutos: int = 15
    sync_dias_atras: int = 55

    # Correo de alertas (SMTP). 587 = STARTTLS, 465 = SSL/TLS.
    correo_servidor: str = ""
    correo_puerto: int = 587
    correo_usuario: str = ""
    correo_contrasena: str = ""
    correo_remitente: str = ""
    # Listas separadas por comas. Si no hay lista VIP propia, se usa la general.
    correo_destinatarios: Annotated[list[str], NoDecode] = Field(default_factory=list)
    correo_destinatarios_vip: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Bot de Telegram para registrar faltas desde el grupo de jefes.
    telegram_token: str = ""
    telegram_chat_id: str = ""

    @field_validator("database_url")
    @classmethod
    def _normalizar_url(cls, v: str) -> str:
        return url_asyncpg(v)

    @field_validator("cepheus_usuarios_consulta", "correo_destinatarios", "correo_destinatarios_vip", mode="before")
    @classmethod
    def _lista_separada_por_comas(cls, v):
        if isinstance(v, str):
            return [u.strip() for u in v.replace(";", ",").split(",") if u.strip()]
        return v

    @field_validator("cepheus_verificar_tls", mode="before")
    @classmethod
    def _verificar_tls(cls, v):
        if isinstance(v, str) and v.strip().lower() in ("true", "1", "si", "sí", "false", "0", "no"):
            return v.strip().lower() in ("true", "1", "si", "sí")
        return v

    def secreto_jwt(self) -> str:
        if self.jwt_secret:
            if len(self.jwt_secret) < 32:
                raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres (openssl rand -hex 32)")
            return self.jwt_secret
        if self.entorno == "desarrollo":
            return "solo-para-desarrollo-no-usar-en-produccion"
        raise RuntimeError("Falta JWT_SECRET en el entorno (genera uno con: openssl rand -hex 32)")


@lru_cache
def get_settings() -> Settings:
    return Settings()
