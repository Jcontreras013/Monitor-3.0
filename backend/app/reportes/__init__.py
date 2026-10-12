"""
Reportes descargables. Los PDF son plantillas HTML (Jinja2) convertidas con
WeasyPrint: cambiar el diseño es editar HTML/CSS en reportes/plantillas/, sin
tocar coordenadas como con fpdf2 en el sistema anterior.
"""

from __future__ import annotations

import base64
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from fastapi import Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.concurrency import run_in_threadpool

from app.dominio.fechas import ahora_hn

_DIR = Path(__file__).parent
MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

MARCA = {
    "tagline": "connecting your world",
    "pie": "@maxcomhn  |  +504 2454-7070 / 8730-2675  |  www.maxcom.hn  |  info@maxcom.hn",
}


def ruta_logo() -> Path:
    return _DIR / "recursos" / "logo.png"


@lru_cache
def logo_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(ruta_logo().read_bytes()).decode()


def _fecha(valor, formato="%d/%m/%Y") -> str:
    if not valor:
        return "N/D"
    return valor.strftime(formato) if hasattr(valor, "strftime") else str(valor)


@lru_cache
def _entorno() -> Environment:
    env = Environment(loader=FileSystemLoader(_DIR / "plantillas"), autoescape=select_autoescape(["html"]))
    env.filters["fecha"] = _fecha
    env.filters["fecha_hora"] = lambda v: _fecha(v, "%d/%m/%Y %H:%M")
    env.filters["miles"] = lambda v: f"{v:,}" if isinstance(v, int) else v
    return env


def html_a_pdf(plantilla: str, **contexto) -> bytes:
    from weasyprint import HTML  # import diferido: carga Pango solo al generar un PDF

    html = _entorno().get_template(plantilla).render(
        logo=logo_data_uri(), marca=MARCA, generado=ahora_hn(), **contexto
    )
    return HTML(string=html, base_url=str(_DIR)).write_pdf()


async def pdf(plantilla: str, **contexto) -> bytes:
    """Genera el PDF en un hilo aparte para no frenar las demás peticiones."""
    return await run_in_threadpool(html_a_pdf, plantilla, **contexto)


def descarga(contenido: bytes, nombre: str, mime: str) -> Response:
    return Response(
        content=contenido,
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nombre)}"},
    )


def sello_archivo(fecha: datetime | None = None) -> str:
    return (fecha or ahora_hn()).strftime("%Y%m%d_%H%M")
