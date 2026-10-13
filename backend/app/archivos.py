"""
Archivos adjuntos (evidencias de faltas, documentos del repositorio, fotos de
auditorías). Se guardan en la base de datos y se entregan solo por la API.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Archivo
from app.schemas import ArchivoOut

TAMANO_MAXIMO = 15 * 1024 * 1024  # 15 MB por archivo

MIMES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "csv": "text/csv",
    "zip": "application/zip",
}
EXT_EVIDENCIA = frozenset({"pdf", "png", "jpg", "jpeg", "webp"})
EXT_DOCUMENTO = frozenset(MIMES) - {"zip"}

# Firmas de los formatos que el navegador mostraría en línea: se comprueban
# para que nadie suba, por ejemplo, un HTML renombrado a .png.
_FIRMAS = {
    "pdf": (b"%PDF",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "webp": (b"RIFF",),
}
MIMES_EN_LINEA = frozenset({"application/pdf", "image/png", "image/jpeg", "image/webp"})


@dataclass
class ArchivoNuevo:
    nombre: str
    datos: bytes


def extension(nombre: str) -> str:
    return PurePath(nombre or "").suffix.lower().lstrip(".")


def validar(nombre: str, datos: bytes, permitidas: frozenset[str]) -> str:
    """Devuelve el tipo MIME o lanza 400 si el archivo no es aceptable."""
    ext = extension(nombre)
    if ext not in permitidas:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"«{nombre}»: tipo no permitido (se aceptan {', '.join(sorted(permitidas))})")
    if len(datos) > TAMANO_MAXIMO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{nombre}» pesa más de 15 MB")
    if not datos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{nombre}» está vacío")
    firmas = _FIRMAS.get(ext)
    if firmas and not any(datos.startswith(f) for f in firmas):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{nombre}» no es realmente un archivo .{ext}")
    return MIMES[ext]


async def leer_subidas(subidas: list[UploadFile] | None) -> list[ArchivoNuevo]:
    archivos = []
    for subida in subidas or []:
        if not subida.filename:
            continue
        datos = await subida.read(TAMANO_MAXIMO + 1)
        archivos.append(ArchivoNuevo(PurePath(subida.filename).name, datos))
    return archivos


def expandir_zip(archivo: ArchivoNuevo, permitidas: frozenset[str]) -> list[ArchivoNuevo]:
    """Los archivos válidos dentro de un ZIP (para subir una carpeta completa)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(archivo.datos))
    except zipfile.BadZipFile as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{archivo.nombre}» no es un ZIP válido") from e
    salida = []
    for info in zf.infolist():
        nombre = PurePath(info.filename).name
        if info.is_dir() or nombre.startswith((".", "~$")) or "__MACOSX" in info.filename:
            continue
        if extension(nombre) in permitidas and info.file_size <= TAMANO_MAXIMO:
            salida.append(ArchivoNuevo(nombre, zf.read(info)))
    return salida


async def guardar(
    sesion: AsyncSession, nuevos: list[ArchivoNuevo], *, ambito: str, referencia: str,
    subido_por: str, permitidas: frozenset[str], descripcion: str = "",
) -> list[Archivo]:
    guardados = []
    for nuevo in nuevos:
        mime = validar(nuevo.nombre, nuevo.datos, permitidas)
        archivo = Archivo(
            ambito=ambito, referencia=referencia, nombre=nuevo.nombre[:255], mime=mime, tamano=len(nuevo.datos),
            descripcion=descripcion, subido_por=subido_por, contenido=nuevo.datos,
        )
        sesion.add(archivo)
        guardados.append(archivo)
    await sesion.flush()
    return guardados


async def listar(sesion: AsyncSession, ambito: str, referencias: list[str]) -> dict[str, list[Archivo]]:
    """Metadatos (sin contenido) de los archivos de varias referencias."""
    if not referencias:
        return {}
    filas = await sesion.scalars(
        select(Archivo).where(Archivo.ambito == ambito, Archivo.referencia.in_(referencias))
        .order_by(Archivo.creado_en)
    )
    por_ref: dict[str, list[Archivo]] = {}
    for archivo in filas:
        por_ref.setdefault(archivo.referencia, []).append(archivo)
    return por_ref


def a_salida(a: Archivo) -> ArchivoOut:
    return ArchivoOut(id=str(a.id), nombre=a.nombre, mime=a.mime, tamano=a.tamano, descripcion=a.descripcion,
                      subido_por=a.subido_por, creado_en=a.creado_en)


async def borrar_de(sesion: AsyncSession, ambito: str, referencia: str) -> None:
    await sesion.execute(delete(Archivo).where(Archivo.ambito == ambito, Archivo.referencia == referencia))
