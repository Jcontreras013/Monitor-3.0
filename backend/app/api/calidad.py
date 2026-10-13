from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import archivos as arch
from app import reportes
from app.deps import SesionDB
from app.deps import requiere as _requiere
from app.dominio import calidad as dom
from app.dominio.fechas import ZONA_HN, ahora_hn
from app.models import AuditoriaCampo, GestionCalidad, Orden, Usuario
from app.permisos import ROLES_COMPLETOS, USUARIOS_CALIDAD_SOLO_CAMPO, USUARIOS_CALIDAD_SOLO_LLAMADAS
from app.schemas import ArchivoOut

router = APIRouter(prefix="/calidad", tags=["calidad"])
UsuarioCalidad = Annotated[Usuario, Depends(_requiere("calidad"))]
MAX_RESULTADOS = 20


def pestanas_de(usuario: Usuario) -> list[str]:
    """Qué secciones ve cada usuario (por NOMBRE de usuario, como antes)."""
    nombre = usuario.usuario.lower()
    if nombre in USUARIOS_CALIDAD_SOLO_CAMPO:
        return ["campo", "historico"]
    if nombre in USUARIOS_CALIDAD_SOLO_LLAMADAS:
        return ["llamadas", "insfibra", "historico"]
    return ["llamadas", "insfibra", "campo", "historico"]


def _exigir(usuario: Usuario, pestana: str) -> None:
    if pestana not in pestanas_de(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu usuario no tiene acceso a esta sección")


def _puede_borrar(usuario: Usuario) -> None:
    if usuario.rol.lower() not in ROLES_COMPLETOS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo gerencia (admin o jefe) puede eliminar registros")


# ------------------------------------------------------------------------------
# Esquemas
# ------------------------------------------------------------------------------
class OrdenCalidad(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    num: str
    actividad: str
    estado: str
    cliente: str | None
    nombre: str | None
    colonia: str | None
    tecnico: str | None
    comentario: str | None
    comentario_cierre: str | None
    olt: str | None
    hora_ini: datetime | None
    hora_liq: datetime | None
    tiempo_invertido_min: int | None = None


class Configuracion(BaseModel):
    pestanas: list[str]
    preguntas: list[dict]
    aprobaciones: list[str]
    estados_sin_contestar: list[str]
    resultados_gestion: list[str]
    tipos_nota: list[str]
    esteticas: list[str]
    evaluaciones_fibra: list[str]
    puede_borrar: bool


class Nota(BaseModel):
    fecha_gestion: datetime
    tipo_nota: str
    detalle_nota: str
    registrado_por: str


class GestionIn(BaseModel):
    num_orden: str
    contesto: bool
    fecha_visita: str = ""
    p1: int | None = Field(None, ge=1, le=5)
    p2: int | None = Field(None, ge=1, le=5)
    p3: int | None = Field(None, ge=1, le=5)
    p4: int | None = Field(None, ge=1, le=5)
    p5: int | None = Field(None, ge=1, le=5)
    p6: int | None = Field(None, ge=1, le=5)
    p7: int | None = Field(None, ge=1, le=5)
    mejoras: str = ""
    aceptacion_digital: str = ""
    hora_cierre_servicio: str = ""
    aprobacion_interna: str = dom.APROBACIONES[0]
    # Si no contestó:
    estado_llamada: str = ""
    resultado_gestion: str = ""
    observaciones: str = ""
    ticket_seguimiento: str = ""
    responsable_seguimiento: str = ""
    fecha_limite_seguimiento: date | None = None
    tipo_nota: str = "Ninguna"
    detalle_nota: str = ""

    @field_validator("tipo_nota")
    @classmethod
    def _nota(cls, v: str) -> str:
        if v not in dom.TIPOS_NOTA:
            raise ValueError("tipo de nota inválido")
        return v


class GestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_gestion: datetime
    num_orden: str
    cliente: str
    nombre_cliente: str
    tecnico: str
    actividad: str
    fecha_visita: str
    contesto: bool
    p1: int | None
    p2: int | None
    p3: int | None
    p4: int | None
    p5: int | None
    p6: int | None
    p7: int | None
    mejoras: str
    aceptacion_digital: str
    hora_cierre_servicio: str
    aprobacion_interna: str
    metodo_auditoria: str
    resultado_gestion: str
    ticket_seguimiento: str
    responsable_seguimiento: str
    fecha_limite_seguimiento: date | None
    tipo_nota: str
    detalle_nota: str
    registrado_por: str
    resultado: str = ""
    promedio: float | None = None


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    fecha_auditoria: datetime
    num_orden: str
    cliente: str
    nombre_cliente: str
    tecnico: str
    actividad: str
    vineta: str
    mufa: str
    metraje: str
    estetica: str
    ruta_acometida: str
    tiempo_invertido: str
    tipo_fo: str
    comentario: str
    evaluacion: str
    supervisor: str
    convertido_a_falta: bool
    expediente_id: int | None
    urls_externas: list[str]
    archivos: list[ArchivoOut] = []


class CierreInsfibra(BaseModel):
    num: str
    cliente: str | None
    nombre: str | None
    tecnico: str | None
    fecha_cierre: datetime | None
    llamada: bool


class CierresOut(BaseModel):
    total: int
    llamadas: int
    pendientes: int
    filas: list[CierreInsfibra]
    por_tecnico: list[dict]


class Base_(StrEnum):
    gestiones = "gestiones"
    operaciones = "operaciones"
    instalaciones = "instalaciones"
    fibra = "fibra"


class HistoricoOut(BaseModel):
    gestiones: list[GestionOut] = []
    auditorias: list[AuditoriaOut] = []
    csat: dict | None = None
    diagnostico: list[dict] = []
    por_tecnico: list[dict] = []
    resumen: list[dict] = []


def _gestion_out(g: GestionCalidad) -> GestionOut:
    salida = GestionOut.model_validate(g)
    salida.resultado = dom.resultado(g.metodo_auditoria, g.aprobacion_interna)
    salida.promedio = dom.promedio_encuesta({c: getattr(g, c) for c, _ in dom.PREGUNTAS})
    return salida


# ------------------------------------------------------------------------------
# Órdenes
# ------------------------------------------------------------------------------
async def _orden(db: AsyncSession, num: str) -> Orden:
    orden = await db.get(Orden, num.strip().removeprefix("ORD-"))
    if orden is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La orden no existe")
    return orden


def _minutos(o: Orden) -> int | None:
    if o.hora_ini is None:
        return None
    fin = o.hora_liq or ahora_hn()
    return int((fin - o.hora_ini).total_seconds() // 60)


def _orden_out(o: Orden) -> OrdenCalidad:
    salida = OrdenCalidad.model_validate(o)
    salida.tiempo_invertido_min = _minutos(o)
    return salida


@router.get("/configuracion", response_model=Configuracion)
async def configuracion(usuario: UsuarioCalidad):
    return Configuracion(
        pestanas=pestanas_de(usuario),
        preguntas=[{"clave": c, "texto": t, "opcional": c in dom.PREGUNTAS_OPCIONALES} for c, t in dom.PREGUNTAS],
        aprobaciones=list(dom.APROBACIONES), estados_sin_contestar=list(dom.ESTADOS_SIN_CONTESTAR),
        resultados_gestion=list(dom.RESULTADOS_GESTION), tipos_nota=list(dom.TIPOS_NOTA),
        esteticas=list(dom.ESTETICAS), evaluaciones_fibra=list(dom.EVALUACIONES_FIBRA),
        puede_borrar=usuario.rol.lower() in ROLES_COMPLETOS,
    )


@router.get("/ordenes", response_model=list[OrdenCalidad])
async def buscar_ordenes(q: str, db: SesionDB, usuario: UsuarioCalidad):
    """
    Busca por número de orden, número de cliente o nombre (todas las palabras,
    en cualquier orden). SAC solo ve INSFIBRA cerradas de los últimos 15 días.
    """
    if len(q.strip()) < 2:
        return []
    stmt = select(Orden.num, Orden.cliente, Orden.nombre).where(~Orden.estado.contains("ANULADA"))
    if usuario.usuario.lower() in USUARIOS_CALIDAD_SOLO_LLAMADAS:
        hoy = ahora_hn().date()
        limite = datetime.combine(hoy - timedelta(days=dom.DIAS_INSFIBRA_SAC), datetime.min.time())
        stmt = stmt.where(Orden.actividad == "INSFIBRA", Orden.estado == "CERRADA", Orden.hora_liq >= limite)
    coincidencias = [num for num, cliente, nombre in await db.execute(stmt)
                     if dom.coincide_busqueda(q, num, cliente, nombre)][:MAX_RESULTADOS]
    if not coincidencias:
        return []
    ordenes = (await db.scalars(select(Orden).where(Orden.num.in_(coincidencias)))).all()
    recientes = sorted(ordenes, key=lambda o: o.hora_liq or o.fecha_ape or datetime.min, reverse=True)
    return [_orden_out(o) for o in recientes]


@router.get("/ordenes/{num}/notas", response_model=list[Nota])
async def notas_previas(num: str, db: SesionDB, _: UsuarioCalidad):
    """Notas de seguimiento o promesa de gestiones anteriores de la orden."""
    return (await db.scalars(select(GestionCalidad).where(
        GestionCalidad.num_orden == num, GestionCalidad.tipo_nota.in_(("Seguimiento", "Promesa")),
    ).order_by(GestionCalidad.fecha_gestion))).all()


# ------------------------------------------------------------------------------
# Gestiones de llamada
# ------------------------------------------------------------------------------
@router.post("/gestiones", response_model=GestionOut, status_code=status.HTTP_201_CREATED)
async def registrar_gestion(datos: GestionIn, db: SesionDB, usuario: UsuarioCalidad):
    _exigir(usuario, "llamadas")
    orden = await _orden(db, datos.num_orden)
    ahora = ahora_hn()
    fecha_visita = datos.fecha_visita or (orden.hora_liq or ahora).strftime("%d/%m/%Y")
    gestion = GestionCalidad(
        num_orden=orden.num, cliente=orden.cliente or "", nombre_cliente=orden.nombre or "",
        tecnico=orden.tecnico or "", actividad=orden.actividad, fecha_visita=fecha_visita, contesto=datos.contesto,
        tipo_nota=datos.tipo_nota,
        detalle_nota=datos.detalle_nota.strip() if datos.tipo_nota != "Ninguna" else "",
        registrado_por=usuario.nombre or usuario.usuario,
    )
    if datos.contesto:
        obligatorias = [c for c, _ in dom.PREGUNTAS if c not in dom.PREGUNTAS_OPCIONALES]
        if any(getattr(datos, c) is None for c in obligatorias):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Califica todas las preguntas de la encuesta")
        if datos.aprobacion_interna not in dom.APROBACIONES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elige el estado de aprobación del servicio")
        for clave, _ in dom.PREGUNTAS:
            setattr(gestion, clave, getattr(datos, clave))
        gestion.mejoras = datos.mejoras.strip()
        gestion.aceptacion_digital = datos.aceptacion_digital.strip() or (orden.nombre or "")
        gestion.hora_cierre_servicio = datos.hora_cierre_servicio or ahora.strftime("%I:%M %p")
        gestion.aprobacion_interna = datos.aprobacion_interna
        gestion.metodo_auditoria = dom.METODO_COMPLETADA
    else:
        if datos.resultado_gestion not in dom.RESULTADOS_GESTION:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elige el resultado de la gestión")
        estado = datos.estado_llamada if datos.estado_llamada in dom.ESTADOS_SIN_CONTESTAR else "No contestó"
        gestion.mejoras = datos.observaciones.strip() or f"Se llamó al cliente. Estado: {estado}."
        gestion.resultado_gestion = datos.resultado_gestion
        gestion.ticket_seguimiento = datos.ticket_seguimiento.strip()
        gestion.responsable_seguimiento = datos.responsable_seguimiento.strip()
        gestion.fecha_limite_seguimiento = datos.fecha_limite_seguimiento
        gestion.aprobacion_interna = (dom.APROBACIONES[2] if datos.resultado_gestion == "Requiere seguimiento"
                                      else "Sin encuesta completada")
        gestion.metodo_auditoria = f"Gestión sin encuesta - {datos.resultado_gestion}"
    db.add(gestion)
    await db.commit()
    await db.refresh(gestion)
    return _gestion_out(gestion)


@router.delete("/gestiones/{gestion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_gestion(gestion_id: int, db: SesionDB, usuario: UsuarioCalidad):
    _puede_borrar(usuario)
    if not (await db.execute(delete(GestionCalidad).where(GestionCalidad.id == gestion_id))).rowcount:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El registro no existe")
    await db.commit()


# ------------------------------------------------------------------------------
# Auditorías de campo
# ------------------------------------------------------------------------------
async def auditorias_out(db: AsyncSession, auditorias: list[AuditoriaCampo]) -> list[AuditoriaOut]:
    fotos = await arch.listar(db, "calidad", [str(a.id) for a in auditorias])
    salida = []
    for a in auditorias:
        item = AuditoriaOut.model_validate(a)
        item.archivos = [arch.a_salida(f) for f in fotos.get(str(a.id), [])]
        salida.append(item)
    return salida


@router.post("/auditorias", response_model=AuditoriaOut, status_code=status.HTTP_201_CREATED)
async def registrar_auditoria(
    db: SesionDB,
    usuario: UsuarioCalidad,
    tipo: Annotated[str, Form()],
    num_orden: Annotated[str, Form()],
    vineta: Annotated[str, Form()] = "",
    mufa: Annotated[str, Form()] = "",
    metraje: Annotated[str, Form()] = "",
    estetica: Annotated[str, Form()] = "",
    ruta_acometida: Annotated[str, Form()] = "",
    tiempo_invertido: Annotated[str, Form()] = "",
    tipo_fo: Annotated[str, Form()] = "",
    comentario: Annotated[str, Form()] = "",
    evaluacion: Annotated[str, Form()] = "",
    fotos: Annotated[list[UploadFile], File()] = [],  # noqa: B006
):
    _exigir(usuario, "campo")
    if tipo not in dom.TIPOS_AUDITORIA:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tipo de auditoría inválido")
    if tipo == "operaciones" and estetica not in dom.ESTETICAS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elige la estética")
    if tipo == "fibra" and evaluacion not in dom.EVALUACIONES_FIBRA:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Elige la evaluación del trabajo")
    orden = await _orden(db, num_orden)
    nuevos = await arch.leer_subidas(fotos)
    auditoria = AuditoriaCampo(
        tipo=tipo, num_orden=orden.num, cliente=orden.cliente or "", nombre_cliente=orden.nombre or "",
        tecnico=orden.tecnico or "", actividad=orden.actividad, vineta=vineta.strip(), mufa=mufa.strip(),
        metraje=metraje.strip(), estetica=estetica if tipo == "operaciones" else "",
        ruta_acometida=ruta_acometida.strip(), tiempo_invertido=tiempo_invertido.strip(), tipo_fo=tipo_fo.strip(),
        comentario=comentario.strip(), evaluacion=evaluacion if tipo == "fibra" else "",
        supervisor=usuario.nombre or usuario.usuario, urls_externas=[],
    )
    db.add(auditoria)
    await db.flush()
    await arch.guardar(db, nuevos, ambito="calidad", referencia=str(auditoria.id), subido_por=usuario.usuario,
                       permitidas=arch.EXT_EVIDENCIA)
    await db.commit()
    await db.refresh(auditoria)
    return (await auditorias_out(db, [auditoria]))[0]


@router.delete("/auditorias/{auditoria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_auditoria(auditoria_id: int, db: SesionDB, usuario: UsuarioCalidad):
    _puede_borrar(usuario)
    if not (await db.execute(delete(AuditoriaCampo).where(AuditoriaCampo.id == auditoria_id))).rowcount:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El registro no existe")
    await arch.borrar_de(db, "calidad", str(auditoria_id))
    await db.commit()


# ------------------------------------------------------------------------------
# Cierres INSFIBRA por rango, con marca de "ya se llamó"
# ------------------------------------------------------------------------------
def _rango(desde: date | None, hasta: date | None, dias: int = 7) -> tuple[date, date]:
    hoy = ahora_hn().date()
    return desde or hoy - timedelta(days=dias), hasta or hoy


async def _cierres(db: AsyncSession, desde: date, hasta: date, solo_pendientes: bool) -> CierresOut:
    inicio = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    ordenes = (await db.scalars(select(Orden).where(
        Orden.actividad == "INSFIBRA", Orden.estado == "CERRADA", Orden.hora_liq >= inicio, Orden.hora_liq < fin,
    ).order_by(Orden.hora_liq))).all()
    llamadas = set((await db.scalars(select(GestionCalidad.num_orden).where(
        GestionCalidad.num_orden.in_([o.num for o in ordenes])))).all()) if ordenes else set()
    filas = [CierreInsfibra(num=o.num, cliente=o.cliente, nombre=o.nombre, tecnico=o.tecnico, fecha_cierre=o.hora_liq,
                            llamada=o.num in llamadas) for o in ordenes]
    por_tecnico: dict[str, Counter] = {}
    for f in filas:
        por_tecnico.setdefault(f.tecnico or "N/D", Counter())["llamada" if f.llamada else "pendiente"] += 1
    total_llamadas = sum(1 for f in filas if f.llamada)
    return CierresOut(
        total=len(filas), llamadas=total_llamadas, pendientes=len(filas) - total_llamadas,
        filas=[f for f in filas if not f.llamada] if solo_pendientes else filas,
        por_tecnico=[{"tecnico": t, "cierres": c["llamada"] + c["pendiente"], "llamadas": c["llamada"],
                      "pendientes": c["pendiente"]} for t, c in sorted(por_tecnico.items())],
    )


@router.get("/insfibra", response_model=CierresOut)
async def cierres_insfibra(db: SesionDB, usuario: UsuarioCalidad, desde: date | None = None,
                           hasta: date | None = None, solo_pendientes: bool = False):
    _exigir(usuario, "insfibra")
    return await _cierres(db, *_rango(desde, hasta), solo_pendientes)


@router.get("/insfibra.pdf")
async def cierres_insfibra_pdf(db: SesionDB, usuario: UsuarioCalidad, desde: date | None = None,
                               hasta: date | None = None, solo_pendientes: bool = False):
    _exigir(usuario, "insfibra")
    desde, hasta = _rango(desde, hasta)
    datos = await _cierres(db, desde, hasta, solo_pendientes)
    contenido = await reportes.pdf("calidad_insfibra.html", desde=desde, hasta=hasta, datos=datos)
    return reportes.descarga(contenido, f"Cierres_INSFIBRA_{desde}_a_{hasta}.pdf", reportes.MIME_PDF)


# ------------------------------------------------------------------------------
# Histórico y reportes
# ------------------------------------------------------------------------------
async def _historico(db: AsyncSession, base: Base_, desde: date, hasta: date) -> HistoricoOut:
    inicio = datetime.combine(desde, datetime.min.time(), tzinfo=ZONA_HN)
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time(), tzinfo=ZONA_HN)
    if base is Base_.gestiones:
        gestiones = (await db.scalars(select(GestionCalidad).where(
            GestionCalidad.fecha_gestion >= inicio, GestionCalidad.fecha_gestion < fin,
        ).order_by(GestionCalidad.fecha_gestion.desc()))).all()
        return HistoricoOut(gestiones=[_gestion_out(g) for g in gestiones], csat=dom.csat(gestiones),
                            diagnostico=dom.diagnostico(gestiones), por_tecnico=dom.resumen_por_tecnico(gestiones),
                            resumen=dom.conteo(dom.resultado(g.metodo_auditoria, g.aprobacion_interna)
                                               for g in gestiones))
    auditorias = list((await db.scalars(select(AuditoriaCampo).where(
        AuditoriaCampo.tipo == base.value, AuditoriaCampo.fecha_auditoria >= inicio,
        AuditoriaCampo.fecha_auditoria < fin,
    ).order_by(AuditoriaCampo.fecha_auditoria.desc()))).all())
    if base is Base_.operaciones:
        resumen = [
            {"titulo": "Por servicio", "columna": "Servicio", "filas": dom.conteo(a.actividad for a in auditorias)},
            {"titulo": "Por estética", "columna": "Estética", "filas": dom.conteo(a.estetica for a in auditorias)},
        ]
    else:
        resumen = [{"titulo": "Por técnico", "columna": "Técnico", "filas": dom.conteo(a.tecnico for a in auditorias)}]
        if base is Base_.fibra:
            resumen.append({"titulo": "Por evaluación", "columna": "Evaluación",
                            "filas": dom.conteo(a.evaluacion for a in auditorias)})
    return HistoricoOut(auditorias=await auditorias_out(db, auditorias), resumen=resumen)


@router.get("/historico", response_model=HistoricoOut)
async def historico(db: SesionDB, _: UsuarioCalidad, base: Base_ = Base_.gestiones,
                    desde: date | None = None, hasta: date | None = None):
    return await _historico(db, base, *_rango(desde, hasta))


TITULOS_HISTORICO = {
    Base_.gestiones: "REPORTE GERENCIAL: AUDITORÍAS DE CALIDAD",
    Base_.operaciones: "REPORTE GERENCIAL: AUDITORÍA DE OPERACIONES",
    Base_.instalaciones: "REPORTE GERENCIAL: AUDITORÍA DE INSTALACIONES (INSFIBRA)",
    Base_.fibra: "REPORTE GERENCIAL: AUDITORÍA DE FIBRA EN CAMPO",
}


@router.get("/historico.pdf")
async def historico_pdf(db: SesionDB, _: UsuarioCalidad, base: Base_ = Base_.gestiones,
                        desde: date | None = None, hasta: date | None = None):
    desde, hasta = _rango(desde, hasta)
    datos = await _historico(db, base, desde, hasta)
    contenido = await reportes.pdf("calidad_historico.html", titulo=TITULOS_HISTORICO[base], base=base.value,
                                   desde=desde, hasta=hasta, datos=datos)
    return reportes.descarga(contenido, f"Reporte_Calidad_{base.value}_{desde}.pdf", reportes.MIME_PDF)


# Para Expedientes: auditorías de fibra deficientes pendientes de convertir en falta.
async def fibra_deficientes_pendientes(db: AsyncSession) -> list[AuditoriaCampo]:
    return list((await db.scalars(select(AuditoriaCampo).where(
        AuditoriaCampo.tipo == "fibra", AuditoriaCampo.evaluacion == dom.EVALUACION_DEFICIENTE,
        ~AuditoriaCampo.convertido_a_falta,
    ).order_by(AuditoriaCampo.fecha_auditoria))).all())

