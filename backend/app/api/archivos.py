from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.archivos import MIMES_EN_LINEA
from app.deps import SesionDB, UsuarioActual
from app.models import Archivo, Usuario
from app.permisos import es_admin, puede

router = APIRouter(prefix="/archivos", tags=["archivos"])

# Qué módulo da acceso a los archivos de cada ámbito.
MODULO_DEL_AMBITO = {"expediente": "expedientes", "calidad": "calidad", "vehiculos": "vehiculos"}


def puede_ver(usuario: Usuario, ambito: str) -> bool:
    if ambito == "repositorio":
        return usuario.acceso_repositorio
    modulo = MODULO_DEL_AMBITO.get(ambito)
    return puede(usuario.rol, modulo) if modulo else es_admin(usuario.rol)


@router.get("/{archivo_id}")
async def descargar(archivo_id: uuid.UUID, db: SesionDB, usuario: UsuarioActual, descargar: bool = False):
    archivo = await db.scalar(select(Archivo).options(undefer(Archivo.contenido)).where(Archivo.id == archivo_id))
    if archivo is None or not puede_ver(usuario, archivo.ambito):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Archivo no encontrado")
    disposicion = "inline" if archivo.mime in MIMES_EN_LINEA and not descargar else "attachment"
    return Response(
        content=archivo.contenido,
        media_type=archivo.mime,
        headers={
            "Content-Disposition": f"{disposicion}; filename*=UTF-8''{quote(archivo.nombre)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )
