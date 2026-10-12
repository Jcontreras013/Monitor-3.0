from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app import archivos as arch
from app import reportes
from app.deps import SesionDB
from app.deps import requiere as _requiere
from app.dominio import expedientes as dom
from app.dominio.fechas import ZONA_HN, ahora_hn
from app.models import Archivo, Expediente, Personal, Usuario
from app.permisos import es_admin
from app.reportes import word

router = APIRouter(prefix="/expedientes", tags=["expedientes"])

UsuarioExpedientes = Annotated[Usuario, Depends(_requiere("expedientes"))]
DIAS_POR_DEFECTO = 60


class Seccion(StrEnum):
    operaciones = "operaciones"
    administrativo = "administrativo"


class TipoFiltro(StrEnum):
    todos = "todos"
    llamado = "llamado"
    tarde = "tarde"
    ausencia = "ausencia"
    medica = "medica"


# ------------------------------------------------------------------------------
# Esquemas
# ------------------------------------------------------------------------------
class ArchivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nombre: str
    mime: str
    tamano: int
    descripcion: str = ""
    subido_por: str = ""
    creado_en: datetime


class RegistroOut(BaseModel):
    id: int
    fecha_registro: datetime
    fecha_incidencia: date
    colaborador: str
    area: str
    tipo_falta: str
    comentario: str
    supervisor: str
    origen: str
    clasificacion: str
    archivos: list[ArchivoOut]
    urls_externas: list[str]


class Conteo(BaseModel):
    nombre: str
    cantidad: int


class Reincidente(BaseModel):
    colaborador: str
    motivo: str
    veces: int


class Panel(BaseModel):
    total: int
    personas: int
    rubro_dominante: str | None
    clasificacion: dict[str, int]
    reincidentes: list[Reincidente]
    por_dia: list[Conteo]
    por_rubro: list[Conteo]
    por_motivo: list[Conteo]


class FilaMes(BaseModel):
    colaborador: str
    tardes: int
    otras: int
    total: int


class ListadoOut(BaseModel):
    registros: list[RegistroOut]
    panel: Panel
    mes: str
    resumen_mes: list[FilaMes]
    colaboradores: list[str]
    areas: list[str]


class CatalogoOut(BaseModel):
    personal: dict[str, list[str]]
    motivos_operaciones: list[str]
    motivos_administrativo: list[str]


class FilaConsolidado(BaseModel):
    colaborador: str
    faltas: int


class ConsolidadoOut(BaseModel):
    mes: str
    total: int
    filas: list[FilaConsolidado]


class CarpetaOut(BaseModel):
    colaborador: str
    archivos: list[ArchivoOut]


def _archivo_out(a: Archivo) -> ArchivoOut:
    return ArchivoOut(id=str(a.id), nombre=a.nombre, mime=a.mime, tamano=a.tamano, descripcion=a.descripcion,
                      subido_por=a.subido_por, creado_en=a.creado_en)


def _nombre_supervisor(usuario: Usuario) -> str:
    return usuario.nombre or usuario.usuario


# ------------------------------------------------------------------------------
# Consultas
# ------------------------------------------------------------------------------
class Filtros:
    def __init__(
        self,
        seccion: Seccion = Seccion.operaciones,
        area: str | None = None,
        colaborador: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        tipo: TipoFiltro = TipoFiltro.todos,
    ):
        hoy = ahora_hn().date()
        self.seccion = seccion
        self.area = area or None
        self.colaborador = colaborador or None
        self.desde = desde or hoy - timedelta(days=DIAS_POR_DEFECTO)
        self.hasta = hasta or hoy
        self.tipo = tipo

    def descripcion(self) -> str:
        partes = ["Operaciones" if self.seccion is Seccion.operaciones else (self.area or "Administrativo").title()]
        if self.colaborador:
            partes.append(self.colaborador)
        partes.append(f"{self.desde:%d/%m/%Y} al {self.hasta:%d/%m/%Y}")
        if self.tipo is not TipoFiltro.todos:
            partes.append({"llamado": "Llamados de atención", "tarde": "Llegadas tardías",
                           "ausencia": "Ausencias", "medica": "Incidencias médicas"}[self.tipo.value])
        return " · ".join(partes)


FiltrosDep = Annotated[Filtros, Depends()]


def _de_la_seccion(stmt, filtros: Filtros):
    if filtros.seccion is Seccion.operaciones:
        return stmt.where(Expediente.area == dom.AREA_OPERACIONES)
    stmt = stmt.where(Expediente.area != dom.AREA_OPERACIONES)
    return stmt.where(Expediente.area == filtros.area) if filtros.area else stmt


@dataclass
class Registro:
    """Un expediente tal como se muestra: con el motivo combinado antiguo ya separado."""

    id: int
    fecha_registro: datetime
    fecha_incidencia: date
    colaborador: str
    area: str
    tipo_falta: str
    comentario: str
    supervisor: str
    origen: str
    urls_externas: list[str]

    @classmethod
    def de(cls, e: Expediente) -> Registro:
        return cls(id=e.id, fecha_registro=e.fecha_registro, fecha_incidencia=e.fecha_incidencia,
                   colaborador=e.colaborador, area=e.area, tipo_falta=dom.normalizar_motivo(e.tipo_falta, e.comentario),
                   comentario=e.comentario, supervisor=e.supervisor, origen=e.origen,
                   urls_externas=list(e.urls_externas or []))


async def _registros(db: AsyncSession, filtros: Filtros) -> list[Registro]:
    stmt = _de_la_seccion(select(Expediente), filtros).where(
        Expediente.fecha_incidencia >= filtros.desde, Expediente.fecha_incidencia <= filtros.hasta)
    if filtros.colaborador:
        stmt = stmt.where(Expediente.colaborador == filtros.colaborador)
    filas = (await db.scalars(stmt.order_by(Expediente.fecha_incidencia.desc(), Expediente.id.desc()))).all()
    return [r for r in map(Registro.de, filas) if dom.cumple_tipo(r, filtros.tipo.value)]


async def _historial_del_mes(db: AsyncSession, personas: list[str], hoy: date) -> list[Registro]:
    if not personas:
        return []
    inicio = hoy.replace(day=1)
    return [Registro.de(e) for e in (await db.scalars(select(Expediente).where(
        Expediente.colaborador.in_(personas), Expediente.fecha_incidencia >= inicio,
        Expediente.fecha_incidencia <= hoy,
    ))).all()]


# ------------------------------------------------------------------------------
# Rutas
# ------------------------------------------------------------------------------
@router.get("/catalogo", response_model=CatalogoOut)
async def catalogo(db: SesionDB, _: UsuarioExpedientes):
    personal: dict[str, list[str]] = {}
    for nombre, area in await db.execute(
        select(Personal.nombre, Personal.area).where(Personal.activo).order_by(Personal.area, Personal.nombre)
    ):
        personal.setdefault(area, []).append(nombre)
    personal.setdefault(dom.AREA_OPERACIONES, [])
    return CatalogoOut(personal=personal, motivos_operaciones=list(dom.MOTIVOS_OPERACIONES),
                       motivos_administrativo=list(dom.MOTIVOS_ADMINISTRATIVO))


@router.get("", response_model=ListadoOut)
async def listar(filtros: FiltrosDep, db: SesionDB, _: UsuarioExpedientes):
    hoy = ahora_hn().date()
    registros = await _registros(db, filtros)
    clasificacion = dom.clasificar(registros)
    adjuntos = await arch.listar(db, "expediente", [str(r.id) for r in registros])
    personas = sorted({r.colaborador for r in registros})

    colaboradores = (await db.scalars(
        _de_la_seccion(select(Expediente.colaborador).distinct(), Filtros(seccion=filtros.seccion, area=filtros.area))
        .order_by(Expediente.colaborador)
    )).all()
    areas = [] if filtros.seccion is Seccion.operaciones else (await db.scalars(
        select(Expediente.area).where(Expediente.area != dom.AREA_OPERACIONES).distinct().order_by(Expediente.area)
    )).all()

    return ListadoOut(
        registros=[
            RegistroOut(
                id=r.id, fecha_registro=r.fecha_registro, fecha_incidencia=r.fecha_incidencia,
                colaborador=r.colaborador, area=r.area, tipo_falta=r.tipo_falta, comentario=r.comentario,
                supervisor=r.supervisor, origen=r.origen, clasificacion=c,
                archivos=[_archivo_out(a) for a in adjuntos.get(str(r.id), [])], urls_externas=r.urls_externas,
            )
            for r, c in zip(registros, clasificacion, strict=True)
        ],
        panel=Panel(**dom.panel(registros)),
        mes=dom.nombre_mes(hoy),
        resumen_mes=[FilaMes(**f) for f in dom.resumen_mes_por_persona(
            await _historial_del_mes(db, personas, hoy), personas, hoy)],
        colaboradores=list(colaboradores),
        areas=list(areas),
    )


@router.post("", response_model=RegistroOut, status_code=status.HTTP_201_CREATED)
async def crear(
    db: SesionDB,
    usuario: UsuarioExpedientes,
    seccion: Annotated[Seccion, Form()],
    colaborador: Annotated[str, Form()] = "",
    area: Annotated[str, Form()] = "",
    motivo: Annotated[str, Form()] = "",
    motivo_otro: Annotated[str, Form()] = "",
    fecha_incidencia: Annotated[date | None, Form()] = None,
    comentario: Annotated[str, Form()] = "",
    archivos: Annotated[list[UploadFile], File()] = [],  # noqa: B006
):
    opciones = dom.MOTIVOS_OPERACIONES if seccion is Seccion.operaciones else dom.MOTIVOS_ADMINISTRATIVO
    if motivo not in opciones:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elige un motivo de la lista")
    tipo = motivo_otro.strip().upper() if motivo == "Otro" else motivo.upper()
    if not tipo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Especifica el motivo de la falta")

    if seccion is Seccion.operaciones:
        area_final = dom.AREA_OPERACIONES
        if motivo == "Reco / Cambio de Postes":
            colaborador, tipo = dom.COLABORADOR_RECO, "RECO / CAMBIO DE POSTES"
    else:
        area_final = " ".join(area.upper().split())
        if not area_final or area_final == dom.AREA_OPERACIONES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elige el área o departamento")
    colaborador = " ".join(colaborador.upper().split())
    if not colaborador:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elige el colaborador")
    if not comentario.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Escribe la descripción de los hechos")

    nuevos = await arch.leer_subidas(archivos)
    registro = Expediente(
        colaborador=colaborador, area=area_final, tipo_falta=tipo,
        fecha_incidencia=fecha_incidencia or ahora_hn().date(), comentario=comentario.strip(),
        supervisor=_nombre_supervisor(usuario), origen="app", urls_externas=[],
    )
    db.add(registro)
    await db.flush()
    guardados = await arch.guardar(db, nuevos, ambito="expediente", referencia=str(registro.id),
                                   subido_por=usuario.usuario, permitidas=arch.EXT_EVIDENCIA)
    await db.commit()
    await db.refresh(registro)
    return RegistroOut(
        id=registro.id, fecha_registro=registro.fecha_registro, fecha_incidencia=registro.fecha_incidencia,
        colaborador=registro.colaborador, area=registro.area, tipo_falta=registro.tipo_falta,
        comentario=registro.comentario, supervisor=registro.supervisor, origen=registro.origen,
        clasificacion=dom.clasificar_grave_o_leve(registro.tipo_falta, registro.comentario),
        archivos=[_archivo_out(a) for a in guardados], urls_externas=[],
    )


@router.delete("/{registro_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(registro_id: int, db: SesionDB, usuario: UsuarioExpedientes):
    if not es_admin(usuario.rol):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo un administrador puede eliminar registros")
    resultado = await db.execute(delete(Expediente).where(Expediente.id == registro_id))
    if not resultado.rowcount:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El registro no existe")
    await arch.borrar_de(db, "expediente", str(registro_id))
    await db.commit()


# ------------------------------------------------------------------------------
# Reportes
# ------------------------------------------------------------------------------
_SECCIONES_PDF = (
    ("LEVE", "FALTAS LEVES",
     "Llegadas tarde (<3), almuerzo/break excedido, no marcó entrada/salida, mala documentación"),
    ("GRAVE", "FALTAS GRAVES",
     "Mal uso o cuidado del vehículo, no apertura/cierre, órdenes pendientes, insultos/irrespeto, o 3+ llegadas tarde"),
    ("OTRO", "OTRAS INCIDENCIAS",
     "Incidencias médicas, méritos, documentos administrativos y registros sin clasificación definida"),
)


def _nombre_archivo(filtros: Filtros, extension: str) -> str:
    base = "_".join(filtros.colaborador.split()[:2]) if filtros.colaborador else "General"
    return f"Reporte_Expedientes_{base}.{extension}"


@router.get("/reporte.pdf")
async def reporte_pdf(filtros: FiltrosDep, db: SesionDB, _: UsuarioExpedientes):
    hoy = ahora_hn().date()
    registros = await _registros(db, filtros)
    clasificacion = dom.clasificar(registros)
    secciones = [
        {"clave": clave, "etiqueta": etiqueta, "descripcion": desc,
         "filas": [r for r, c in zip(registros, clasificacion, strict=True) if c == clave]}
        for clave, etiqueta, desc in _SECCIONES_PDF
    ]
    personas = sorted({r.colaborador for r in registros})

    imagenes = (await db.scalars(
        select(Archivo).options(undefer(Archivo.contenido)).where(
            Archivo.ambito == "expediente", Archivo.referencia.in_([str(r.id) for r in registros]),
            Archivo.mime.like("image/%"))
    )).all() if registros else []
    por_id = {str(r.id): r for r in registros}
    anexos = [
        {"colaborador": por_id[a.referencia].colaborador, "tipo_falta": por_id[a.referencia].tipo_falta,
         "fecha": por_id[a.referencia].fecha_incidencia,
         "imagen": f"data:{a.mime};base64,{base64.b64encode(a.contenido).decode()}"}
        for a in imagenes
    ]
    enlaces = [{"colaborador": r.colaborador, "fecha": r.fecha_incidencia, "url": u}
               for r in registros for u in r.urls_externas]

    contenido = await reportes.pdf(
        "expedientes.html",
        descripcion=filtros.descripcion(),
        conteo={c: clasificacion.count(c) for c in ("GRAVE", "LEVE", "OTRO")},
        secciones=[s for s in secciones if s["filas"]] if registros else [],
        mes=dom.nombre_mes(hoy),
        resumen_mes=dom.resumen_mes_por_persona(await _historial_del_mes(db, personas, hoy), personas, hoy),
        anexos=anexos,
        enlaces=enlaces,
    )
    return reportes.descarga(contenido, _nombre_archivo(filtros, "pdf"), reportes.MIME_PDF)


@router.get("/reporte.docx")
async def reporte_word(filtros: FiltrosDep, db: SesionDB, _: UsuarioExpedientes):
    registros = await _registros(db, filtros)
    personas = sorted({r.colaborador for r in registros})
    cargos = dict((await db.execute(
        select(Personal.nombre, Personal.cargo).where(Personal.nombre.in_(personas)))).all()) if personas else {}
    fichas = [
        word.FichaEmpleado(
            nombre=persona, puesto=cargos.get(persona, ""),
            departamento=next(r.area for r in registros if r.colaborador == persona),
            incidencias=[
                word.Incidencia(fecha=r.fecha_incidencia, motivo=r.tipo_falta, comentario=r.comentario,
                                hora=dom.extraer_hora_falta(
                                    r.comentario, r.fecha_registro.astimezone(ZONA_HN).strftime("%H:%M")))
                for r in registros if r.colaborador == persona
            ],
        )
        for persona in personas
    ]
    contenido = word.reporte_faltas(fichas, ahora_hn())
    return reportes.descarga(contenido, _nombre_archivo(filtros, "docx"), reportes.MIME_DOCX)


async def _consolidado(db: AsyncSession) -> ConsolidadoOut:
    hoy = ahora_hn().date()
    filas = dom.consolidado_mes((await db.scalars(select(Expediente).where(
        Expediente.fecha_incidencia >= hoy.replace(day=1), Expediente.fecha_incidencia <= hoy))).all(), hoy)
    return ConsolidadoOut(mes=dom.nombre_mes(hoy), total=sum(f["faltas"] for f in filas),
                          filas=[FilaConsolidado(**f) for f in filas])


@router.get("/consolidado-mes", response_model=ConsolidadoOut)
async def consolidado_mes(db: SesionDB, _: UsuarioExpedientes):
    return await _consolidado(db)


@router.get("/consolidado-mes.pdf")
async def consolidado_mes_pdf(db: SesionDB, _: UsuarioExpedientes):
    datos = await _consolidado(db)
    contenido = await reportes.pdf("consolidado_mes.html", mes=datos.mes, total=datos.total,
                                   filas=[f.model_dump() for f in datos.filas])
    return reportes.descarga(contenido, f"Consolidado_Faltas_{datos.mes.replace(' ', '_')}.pdf", reportes.MIME_PDF)


# ------------------------------------------------------------------------------
# Repositorio de documentos (solo usuarios con acceso)
# ------------------------------------------------------------------------------
async def _usuario_repositorio(usuario: UsuarioExpedientes) -> Usuario:
    if not usuario.acceso_repositorio:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes acceso al repositorio de documentos")
    return usuario


UsuarioRepositorio = Annotated[Usuario, Depends(_usuario_repositorio)]


@router.get("/repositorio", response_model=list[CarpetaOut])
async def repositorio(db: SesionDB, _: UsuarioRepositorio):
    filas = (await db.scalars(
        select(Archivo).where(Archivo.ambito == "repositorio").order_by(Archivo.referencia, Archivo.creado_en.desc())
    )).all()
    carpetas: dict[str, list[ArchivoOut]] = {}
    for a in filas:
        carpetas.setdefault(a.referencia, []).append(_archivo_out(a))
    return [CarpetaOut(colaborador=c, archivos=lista) for c, lista in carpetas.items()]


@router.post("/repositorio", response_model=list[ArchivoOut], status_code=status.HTTP_201_CREATED)
async def subir_al_repositorio(
    db: SesionDB,
    usuario: UsuarioRepositorio,
    colaborador: Annotated[str, Form()],
    archivos: Annotated[list[UploadFile], File()],
    descripcion: Annotated[str, Form()] = "",
):
    colaborador = " ".join(colaborador.upper().split())
    if not colaborador:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Indica el colaborador")
    nuevos = []
    for archivo in await arch.leer_subidas(archivos):
        # Una carpeta completa se sube como ZIP: se guardan sus archivos uno por uno.
        if arch.extension(archivo.nombre) == "zip":
            nuevos.extend(arch.expandir_zip(archivo, arch.EXT_DOCUMENTO))
        else:
            nuevos.append(archivo)
    if not nuevos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No hay archivos válidos para subir")
    guardados = await arch.guardar(db, nuevos, ambito="repositorio", referencia=colaborador,
                                   subido_por=usuario.usuario, permitidas=arch.EXT_DOCUMENTO,
                                   descripcion=descripcion.strip())
    await db.commit()
    return [_archivo_out(a) for a in guardados]


@router.delete("/repositorio/{archivo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_del_repositorio(archivo_id: uuid.UUID, db: SesionDB, _: UsuarioRepositorio):
    resultado = await db.execute(delete(Archivo).where(Archivo.ambito == "repositorio", Archivo.id == archivo_id))
    if not resultado.rowcount:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El archivo no existe")
    await db.commit()
