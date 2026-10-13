"""Configuración: lista de clientes VIP y correo de alertas (admin y jefe)."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import delete, select

from app.correo import ConfigCorreo, enviar_prueba, modo
from app.deps import Config, SesionDB, requiere
from app.dominio.vip import leer_archivo_vip, normalizar_codigo
from app.models import ClienteVip, EstadoAlerta

router = APIRouter(prefix="/configuracion", tags=["configuracion"], dependencies=[Depends(requiere("configuracion"))])

TAMANO_MAXIMO_VIP = 5 * 1024 * 1024


class ClienteVipIO(BaseModel):
    cliente: str
    nombre: str = ""
    clase: str = ""

    @field_validator("cliente")
    @classmethod
    def _codigo(cls, v: str) -> str:
        v = normalizar_codigo(v)
        if not re.fullmatch(r"\d+", v):
            raise ValueError("el código de cliente debe ser numérico")
        return v


class VistaPreviaVip(BaseModel):
    clientes: list[ClienteVipIO]
    nuevos: int
    salen: int


@router.get("/vip", response_model=list[ClienteVipIO])
async def listar_vip(db: SesionDB):
    return (await db.scalars(select(ClienteVip).order_by(ClienteVip.nombre, ClienteVip.cliente))).all()


@router.post("/vip/vista-previa", response_model=VistaPreviaVip)
async def vista_previa_vip(db: SesionDB, archivo: UploadFile):
    """Lee el archivo y dice qué cambiaría, sin guardar nada."""
    contenido = await archivo.read(TAMANO_MAXIMO_VIP + 1)
    if len(contenido) > TAMANO_MAXIMO_VIP:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo pesa más de 5 MB")
    try:
        clientes = leer_archivo_vip(contenido, archivo.filename or "")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except Exception as e:  # Excel dañado o con un formato que openpyxl no entiende
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No se pudo leer el archivo: {e}") from e
    actuales = set((await db.scalars(select(ClienteVip.cliente))).all())
    nuevos = {c.cliente for c in clientes}
    return VistaPreviaVip(clientes=[ClienteVipIO(**c.__dict__) for c in clientes],
                          nuevos=len(nuevos - actuales), salen=len(actuales - nuevos))


@router.put("/vip")
async def reemplazar_vip(db: SesionDB, clientes: list[ClienteVipIO]):
    """Reemplaza la lista completa (la que devolvió la vista previa)."""
    unicos = {c.cliente: c for c in reversed(clientes)}  # si se repite, gana el primero
    await db.execute(delete(ClienteVip))
    db.add_all(ClienteVip(cliente=c.cliente, nombre=c.nombre.strip(), clase=c.clase.strip()[:60])
               for c in unicos.values())
    await db.commit()
    return {"total": len(unicos)}


class EstadoAlertaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alerta: str
    resultado: str
    detalle: str
    actualizado_en: datetime


class CorreoOut(BaseModel):
    servidor: str
    puerto: int
    modo: str
    remitente: str
    contrasena_configurada: bool
    destinatarios: list[str]
    destinatarios_vip: list[str]
    falta: str | None
    alertas: list[EstadoAlertaOut]


@router.get("/correo", response_model=CorreoOut)
async def estado_correo(db: SesionDB, settings: Config):
    """Configuración de correo de ESTA app (sin la contraseña) y el resultado de las alertas del robot."""
    c = ConfigCorreo.desde(settings)
    return CorreoOut(
        servidor=c.servidor, puerto=c.puerto, modo=modo(c.puerto), remitente=c.remitente,
        contrasena_configurada=bool(c.contrasena), destinatarios=c.destinatarios,
        destinatarios_vip=c.destinatarios_vip, falta=c.falta(),
        alertas=(await db.scalars(select(EstadoAlerta).order_by(EstadoAlerta.alerta))).all(),
    )


@router.post("/correo/prueba")
async def correo_de_prueba(settings: Config):
    c = ConfigCorreo.desde(settings)
    ok, nota = await asyncio.to_thread(enviar_prueba, c)
    if not ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"No se pudo enviar: {nota}")
    return {"destinatarios": c.destinatarios, "nota": nota}
