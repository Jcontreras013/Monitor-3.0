"""Centro de Reportes: cierre diario, primera orden, arranque y pendientes para Dispatch (admin y jefe)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import reportes as rep
from app.api.monitor import cargar_ordenes_monitor, orden_out
from app.deps import SesionDB, requiere
from app.dominio import constantes as c
from app.dominio import monitor as m
from app.dominio import reportes as dom
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import tecnico_asignado
from app.models import Orden
from app.reportes.excel import libro

router = APIRouter(prefix="/reportes", tags=["reportes"], dependencies=[Depends(requiere("reportes"))])

MAX_DIAS_ARRANQUE = 62


async def _ordenes_del_dia(db: AsyncSession, fecha: date) -> list[Orden]:
    """Órdenes que iniciaron o se cerraron ese día (el cierre de madrugada cuenta para el día anterior)."""
    inicio = datetime.combine(fecha, time())
    fin = inicio + timedelta(days=2)
    return list((await db.scalars(select(Orden).where(
        Orden.actividad.in_(c.ACTIVIDADES_PERMITIDAS),
        or_(Orden.hora_liq.between(inicio, fin), Orden.hora_ini.between(inicio, fin)),
    ))).all())


async def _pendientes(db: AsyncSession, ahora: datetime) -> list[Orden]:
    """Las mismas pendientes que el Monitor sin filtros."""
    return m.pendientes(m.base_activa(await cargar_ordenes_monitor(db, ahora)))


def _fecha(fecha: date | None) -> date:
    return fecha or ahora_hn().date()


# ------------------------------------------------------------------------------
# Cierre diario
# ------------------------------------------------------------------------------
async def _cierre(db: AsyncSession, fecha: date) -> dict:
    ahora = ahora_hn()
    del_dia = await _ordenes_del_dia(db, fecha)
    cerradas = dom.cerradas_del_dia(del_dia, fecha)
    asignadas = [o for o in await _pendientes(db, ahora) if tecnico_asignado(o.tecnico)]
    return {
        "fecha": fecha,
        "total_cerradas": len(cerradas),
        "avance": dom.avance(asignadas, cerradas, fecha),
        "produccion": dom.desglose_produccion(cerradas),
        "eficiencia": dom.eficiencia_por_tecnico(cerradas),
        "primera_orden": dom.primera_orden(del_dia, fecha),
        "cerradas": [orden_out(o, ahora) for o in cerradas],
        "_ordenes": cerradas,
    }


@router.get("/cierre")
async def cierre(db: SesionDB, fecha: date | None = None):
    datos = await _cierre(db, _fecha(fecha))
    datos.pop("_ordenes")
    return datos


@router.get("/cierre.pdf")
async def cierre_pdf(db: SesionDB, fecha: date | None = None):
    fecha = _fecha(fecha)
    datos = await _cierre(db, fecha)
    cerradas = datos.pop("_ordenes")
    contenido = await rep.pdf(
        "reportes_cierre.html", **datos,
        rangos_instalaciones=dom.tiempos_por_rango([o for o in cerradas if dom.tipo_orden(o) == "INSTALACION"]),
        rangos_mantenimientos=dom.tiempos_por_rango([o for o in cerradas if dom.tipo_orden(o) == "MANTENIMIENTO"]),
        por_ciudad=dom.cerradas_por_ciudad(cerradas),
        por_actividad=dom.resumen_por_actividad(cerradas),
        por_tecnico=dom.tiempos_por_tecnico_actividad(cerradas),
        distribucion=dom.distribucion(cerradas),
        minutos={o.num: dom.minutos(o) for o in cerradas},
    )
    return rep.descarga(contenido, f"Cierre_{fecha}.pdf", rep.MIME_PDF)


@router.get("/cerradas.pdf")
async def cerradas_pdf(db: SesionDB, fecha: date | None = None):
    fecha = _fecha(fecha)
    cerradas = dom.cerradas_del_dia(await _ordenes_del_dia(db, fecha), fecha)
    contenido = await rep.pdf("reportes_cerradas.html", fecha=fecha, cerradas=cerradas)
    return rep.descarga(contenido, f"Cerradas_Detalle_{fecha}.pdf", rep.MIME_PDF)


@router.get("/primera-orden.pdf")
async def primera_orden_pdf(db: SesionDB, fecha: date | None = None):
    fecha = _fecha(fecha)
    filas = dom.primera_orden(await _ordenes_del_dia(db, fecha), fecha)
    contenido = await rep.pdf("reportes_primera_orden.html", fecha=fecha, filas=filas)
    return rep.descarga(contenido, f"Primeras_Ordenes_{fecha}.pdf", rep.MIME_PDF)


# ------------------------------------------------------------------------------
# Promedio de arranque
# ------------------------------------------------------------------------------
async def _arranque(db: AsyncSession, desde: date | None, hasta: date | None) -> tuple[date, date, list[dict]]:
    hasta = hasta or ahora_hn().date()
    desde = desde or hasta - timedelta(days=6)
    if desde > hasta:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La fecha de inicio no puede ser mayor que la final")
    if (hasta - desde).days > MAX_DIAS_ARRANQUE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"El rango no puede pasar de {MAX_DIAS_ARRANQUE} días")
    ordenes = (await db.scalars(select(Orden).where(
        Orden.actividad.in_(c.ACTIVIDADES_PERMITIDAS),
        Orden.hora_ini >= datetime.combine(desde, time()),
        Orden.hora_ini < datetime.combine(hasta + timedelta(days=1), time()),
    ))).all()
    return desde, hasta, dom.promedio_arranque(ordenes, desde, hasta)


@router.get("/arranque")
async def arranque(db: SesionDB, desde: date | None = None, hasta: date | None = None):
    desde, hasta, filas = await _arranque(db, desde, hasta)
    return {"desde": desde, "hasta": hasta, "filas": filas}


@router.get("/arranque.pdf")
async def arranque_pdf(db: SesionDB, desde: date | None = None, hasta: date | None = None):
    desde, hasta, filas = await _arranque(db, desde, hasta)
    contenido = await rep.pdf("reportes_arranque.html", desde=desde, hasta=hasta, filas=filas)
    return rep.descarga(contenido, f"Promedio_Arranque_{desde}.pdf", rep.MIME_PDF)


# ------------------------------------------------------------------------------
# Pendientes generales (Dispatch)
# ------------------------------------------------------------------------------
async def _dispatch(db: AsyncSession) -> tuple[datetime, list[Orden], dict]:
    ahora = ahora_hn()
    pendientes = sorted(await _pendientes(db, ahora), key=lambda o: (-m.dias_retraso(o, ahora.date()), o.num))
    return ahora, pendientes, dom.pendientes_dispatch(pendientes, ahora.date())


@router.get("/pendientes")
async def pendientes(db: SesionDB):
    ahora, ordenes, datos = await _dispatch(db)
    datos["sin_asignar"] = [orden_out(o, ahora) for o in ordenes if not tecnico_asignado(o.tecnico)]
    return datos


@router.get("/pendientes.pdf")
async def pendientes_pdf(db: SesionDB):
    ahora, ordenes, datos = await _dispatch(db)
    contenido = await rep.pdf(
        "reportes_pendientes.html", **datos, ahora=ahora,
        ordenes=[(o, m.dias_retraso(o, ahora.date()), tecnico_asignado(o.tecnico)) for o in ordenes],
    )
    return rep.descarga(contenido, f"Pendientes_Dispatch_{ahora.date()}.pdf", rep.MIME_PDF)


@router.get("/pendientes.xlsx")
async def pendientes_excel(db: SesionDB):
    ahora, ordenes, datos = await _dispatch(db)
    hoy = ahora.date()
    contenido = libro([
        ("Pendientes", ["Días", "Orden", "Cliente", "Nombre", "Colonia", "Ciudad", "Actividad", "Motivo",
                        "Clasificación Dispatch", "Estado", "Técnico", "Apertura", "Comentario"],
         [[m.dias_retraso(o, hoy), o.num, o.cliente, o.nombre, o.colonia, o.sector, o.actividad, o.motivo,
           dom.categoria_dispatch(o), o.estado, o.tecnico or "SIN ASIGNAR", o.fecha_ape, o.comentario]
          for o in ordenes]),
        ("Resumen", ["Clasificación", "Asignadas", "Sin asignar", "Total"],
         [[r["categoria"], r["asignadas"], r["sin_asignar"], r["total"]] for r in datos["resumen"]]
         + [["TOTAL PENDIENTES", datos["totales"]["asignadas"], datos["totales"]["sin_asignar"],
             datos["totales"]["total"]]]),
    ])
    return rep.descarga(contenido, f"Pendientes_Dispatch_{hoy}.xlsx", rep.MIME_XLSX)
