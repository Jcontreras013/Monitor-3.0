"""
Alertas por correo que corre el robot después de cada ciclo exitoso.

- Clientes VIP: órdenes de clientes VIP sin atender abiertas en las últimas
  24 h. La ventana evita que, al activar el aviso, lleguen de golpe todas las
  órdenes viejas de esos clientes.
- Molex en cierres: soportes de fibra cerrados en las últimas 24 h cuyo
  comentario de cierre dice que se puso una molex NUEVA en medio del tramo
  (esa debe estar depurada en Odoo; la de la casa ya se depuró al instalar).

Cada orden se avisa una sola vez (tabla alertas_enviadas, antes los archivos
vip_avisadas.json / molex_avisadas.json de la PC del robot) y el resultado de
cada alerta queda en estado_alertas para verlo en Configuración.
Port de _procesar_alertas() de sync_job.py.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.correo import ConfigCorreo, enviar_correo, tabla_html, texto_plano
from app.dominio import materiales as mat
from app.models import AlertaEnviada, ClienteVip, EstadoAlerta, Orden

log = logging.getLogger("alertas")

ALERTA_VIP = "vip"
ALERTA_MOLEX = "molex"
HORAS_VENTANA = 24
# Pasado este tiempo una orden ya no entra en la ventana de 24 h: se puede olvidar.
DIAS_RECORDAR = 30

Estado = tuple[str, str]  # (resultado, detalle)


def _fecha(valor: datetime | None) -> str:
    return valor.strftime("%d/%m/%Y %H:%M") if valor else ""


async def _ya_avisadas(sesion: AsyncSession, alerta: str) -> set[str]:
    return set((await sesion.scalars(select(AlertaEnviada.num).where(AlertaEnviada.alerta == alerta))).all())


# ------------------------------------------------------------------------------
# Clientes VIP
# ------------------------------------------------------------------------------
def _vip_sin_atender():
    return (select(Orden, ClienteVip).join(ClienteVip, Orden.cliente == ClienteVip.cliente)
            .where(Orden.vigente, Orden.es_viva))


async def seleccionar_vip_nuevas(sesion: AsyncSession, ahora: datetime) -> list[tuple[Orden, ClienteVip]]:
    filas = (await sesion.execute(
        _vip_sin_atender().where(Orden.fecha_ape >= ahora - timedelta(hours=HORAS_VENTANA)).order_by(Orden.fecha_ape)
    )).all()
    ya = await _ya_avisadas(sesion, ALERTA_VIP)
    return [(o, v) for o, v in filas if o.num not in ya]


async def diagnostico_vip(sesion: AsyncSession, ahora: datetime) -> str:
    """Explica en una línea por qué no hubo nada que avisar."""
    total_vip = await sesion.scalar(select(func.count()).select_from(ClienteVip))
    vivas = (await sesion.execute(_vip_sin_atender())).all()
    if not vivas:
        return (f"no hay órdenes sin atender de los {total_vip} clientes VIP (revisa que el código de cliente "
                "sea el mismo que en Cepheus)")
    desde = ahora - timedelta(hours=HORAS_VENTANA)
    recientes = [o.num for o, _ in vivas if o.fecha_ape and o.fecha_ape >= desde]
    ya = await _ya_avisadas(sesion, ALERTA_VIP)
    return (f"órdenes VIP sin atender: {len(vivas)}; abiertas en las últimas {HORAS_VENTANA} h: {len(recientes)}"
            + (f" ({', '.join(recientes)}), ya avisadas antes: {sum(n in ya for n in recientes)}" if recientes else ""))


def armar_correo_vip(filas: list[tuple[Orden, ClienteVip]]) -> tuple[str, str, str]:
    """(asunto, texto, html) del aviso de órdenes nuevas VIP."""
    if len(filas) == 1:
        asunto = f"⭐ Orden nueva de cliente VIP: {filas[0][1].nombre or filas[0][1].cliente}"
    else:
        asunto = f"⭐ {len(filas)} órdenes nuevas de clientes VIP"
    encabezados = ["Orden", "Cliente", "Nombre", "Clase", "Actividad", "Estado", "Técnico", "Apertura", "Colonia",
                   "Comentario de apertura"]
    tabla = [[o.num, o.cliente, v.nombre, v.clase, o.actividad, o.estado, o.tecnico or "", _fecha(o.fecha_ape),
              o.colonia or "", o.comentario or ""] for o, v in filas]
    texto = ("Se abrieron órdenes para clientes VIP:\n\n" + texto_plano(encabezados, tabla)
             + "\n\nMonitor Operativo MAXCOM - aviso automático de clientes VIP")
    cuerpo = ('<div style="font-family:Arial,sans-serif;font-size:13px;">'
              "<p>Se abrieron órdenes para <b>clientes VIP</b>:</p>" + tabla_html(encabezados, tabla)
              + '<p style="color:#666;font-size:11px;">Monitor Operativo MAXCOM · aviso automático. '
              "Cada orden se avisa una sola vez.</p></div>")
    return asunto, texto, cuerpo


# ------------------------------------------------------------------------------
# Molex en cierres de soporte
# ------------------------------------------------------------------------------
async def seleccionar_molex_nuevas(sesion: AsyncSession, ahora: datetime) -> list[tuple[Orden, str, str]]:
    ordenes = (await sesion.scalars(select(Orden).where(
        Orden.actividad.in_(mat.ACTIVIDADES_ALERTA_MOLEX), Orden.estado == "CERRADA",
        Orden.hora_liq >= ahora - timedelta(hours=HORAS_VENTANA), Orden.comentario_cierre.ilike("%molex%"),
    ).order_by(Orden.hora_liq))).all()
    ya = await _ya_avisadas(sesion, ALERTA_MOLEX)
    nuevas = []
    for o in ordenes:
        if o.num in ya:
            continue
        que_dice, frase = mat.clasificar_comentario_molex(o.comentario_cierre)
        if que_dice in mat.COMENTARIOS_MOLEX_NUEVA:
            nuevas.append((o, que_dice, frase))
    return nuevas


def armar_correo_molex(filas: list[tuple[Orden, str, str]]) -> tuple[str, str, str]:
    actividades = ", ".join(sorted({o.actividad for o, _, _ in filas}))
    asunto = f"⚠️ Molex en cierre de soporte: {len(filas)} orden(es) por revisar"
    intro = (f"En {len(filas)} orden(es) de soporte ({actividades}) el técnico dice en el comentario de cierre que "
             "puso una caja molex nueva en medio del tramo. Revisar que esté depurada en Odoo (la molex de la casa "
             "ya se depuró en la instalación).")
    encabezados = ["Orden", "Técnico", "Actividad", "Cliente", "Cierre", "Razón de cierre", "Qué dice",
                   "Comentario de cierre"]
    tabla = [[o.num, o.tecnico or "", o.actividad, o.cliente or "", _fecha(o.hora_liq), o.razon_cierre or "",
              que_dice, frase] for o, que_dice, frase in filas]
    texto = intro + "\n\n" + texto_plano(encabezados, tabla) + "\n\nMonitor Operativo MAXCOM - alerta automática"
    cuerpo = (f'<div style="font-family:Arial,sans-serif;font-size:13px;"><p>{intro}</p>'
              + tabla_html(encabezados, tabla)
              + '<p style="color:#666;font-size:11px;">Monitor Operativo MAXCOM · alerta automática. '
              "Cada orden se avisa una sola vez.</p></div>")
    return asunto, texto, cuerpo


# ------------------------------------------------------------------------------
# Ciclo de alertas
# ------------------------------------------------------------------------------
Enviar = Callable[..., tuple[bool, str | None]]


async def _enviar_y_registrar(sesion: AsyncSession, alerta: str, nums: list[str], correo: tuple[str, str, str],
                              config: ConfigCorreo, destinatarios: list[str], enviar: Enviar) -> Estado:
    asunto, texto, cuerpo = correo
    ok, nota = await asyncio.to_thread(enviar, config, destinatarios, asunto, texto, cuerpo)
    lista = ", ".join(nums)
    if not ok:
        return "error al enviar", f"{len(nums)} orden(es) sin avisar ({lista}): {nota}"
    await sesion.execute(insert(AlertaEnviada).values([{"alerta": alerta, "num": n} for n in nums])
                         .on_conflict_do_nothing())
    await sesion.commit()
    return "enviado", f"{len(nums)} orden(es): {lista}" + (f". Nota: {nota}" if nota else "")


async def alerta_vip(sesion: AsyncSession, config: ConfigCorreo, ahora: datetime, enviar: Enviar) -> Estado:
    if not await sesion.scalar(select(func.count()).select_from(ClienteVip)):
        return "sin lista VIP", "no hay clientes VIP cargados (Configuración → Clientes VIP)"
    nuevas = await seleccionar_vip_nuevas(sesion, ahora)
    if not nuevas:
        return "sin novedades", await diagnostico_vip(sesion, ahora)
    return await _enviar_y_registrar(sesion, ALERTA_VIP, [o.num for o, _ in nuevas], armar_correo_vip(nuevas),
                                     config, config.destinatarios_vip, enviar)


async def alerta_molex(sesion: AsyncSession, config: ConfigCorreo, ahora: datetime, enviar: Enviar) -> Estado:
    nuevas = await seleccionar_molex_nuevas(sesion, ahora)
    if not nuevas:
        return "sin novedades", ("ningún cierre de soporte nuevo (últimas 24 h) dice que se puso una molex nueva "
                                 "en medio del tramo")
    return await _enviar_y_registrar(sesion, ALERTA_MOLEX, [o.num for o, _, _ in nuevas], armar_correo_molex(nuevas),
                                     config, config.destinatarios, enviar)


async def procesar_alertas(sesiones: async_sessionmaker[AsyncSession], config: ConfigCorreo, ahora: datetime,
                           enviar: Enviar = enviar_correo) -> list[tuple[str, str, str]]:
    """Corre las alertas, guarda el resultado de cada una y devuelve [(alerta, resultado, detalle)]."""
    estados: list[tuple[str, str, str]] = []
    if faltante := config.falta():
        estados.append(("Correo", "desactivado", f"falta en la configuración del robot: {faltante}"))
    for nombre, funcion in (("Clientes VIP", alerta_vip), ("Molex en cierres", alerta_molex)):
        try:
            async with sesiones() as sesion:
                estados.append((nombre, *await funcion(sesion, config, ahora, enviar)))
        except Exception as e:  # una alerta rota no debe frenar a la otra ni al robot
            log.exception("Falla en la alerta %s", nombre)
            estados.append((nombre, "error", str(e)[:2000]))

    async with sesiones() as sesion:
        await sesion.execute(delete(EstadoAlerta))
        sesion.add_all(EstadoAlerta(alerta=a, resultado=r, detalle=d) for a, r, d in estados)
        limite = datetime.now(UTC) - timedelta(days=DIAS_RECORDAR)
        await sesion.execute(delete(AlertaEnviada).where(AlertaEnviada.enviada_en < limite))
        await sesion.commit()
    return estados
