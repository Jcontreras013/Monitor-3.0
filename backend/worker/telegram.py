"""
Bot de Telegram: los jefes registran faltas desde su grupo y quedan en Expedientes.

    python -m worker.telegram     # queda escuchando el grupo (Ctrl+C para parar)

Necesita TELEGRAM_TOKEN y TELEGRAM_CHAT_ID (ver .env.example) y la misma
DATABASE_URL que la API. Solo atiende el grupo configurado. La conversación
(qué preguntar y cómo entender las respuestas) está en app/dominio/telegram.py;
aquí solo se habla con Telegram y se guarda.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import PurePosixPath

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import archivos as arch
from app.config import get_settings
from app.db import crear_engine, crear_sesiones
from app.dominio import telegram as dom
from app.dominio.fechas import ahora_hn
from app.models import EstadoBot, Expediente, Personal

log = logging.getLogger("telegram")

NOMBRE_ESTADO = "telegram"
ESPERA_TRAS_ERROR = 10


class ClienteTelegram:
    """Lo mínimo de la API de bots de Telegram que usa el bot."""

    def __init__(self, token: str, http: httpx.AsyncClient):
        self._base = f"https://api.telegram.org/bot{token}"
        self._archivos = f"https://api.telegram.org/file/bot{token}"
        self._http = http

    async def _llamar(self, metodo: str, **datos) -> dict:
        r = await self._http.post(f"{self._base}/{metodo}", json=datos, timeout=45)
        cuerpo = r.json()
        if not cuerpo.get("ok"):
            raise RuntimeError(f"Telegram {metodo}: {cuerpo.get('description', r.status_code)}")
        return cuerpo["result"]

    async def actualizaciones(self, offset: int | None) -> list[dict]:
        datos = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            datos["offset"] = offset + 1
        return await self._llamar("getUpdates", **datos)

    async def enviar(self, chat_id: int, texto: str, botones: dom.Botones | None = None,
                     responder_a: int | None = None) -> None:
        datos: dict = {"chat_id": chat_id, "text": texto}
        if botones:
            datos["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d}] for t, d in botones]}
        if responder_a:
            datos["reply_parameters"] = {"message_id": responder_a, "allow_sending_without_reply": True}
        await self._llamar("sendMessage", **datos)

    async def contestar_boton(self, callback_id: str) -> None:
        await self._llamar("answerCallbackQuery", callback_query_id=callback_id)

    async def descargar(self, file_id: str) -> tuple[str, bytes] | None:
        info = await self._llamar("getFile", file_id=file_id)
        if not info.get("file_path"):
            return None
        r = await self._http.get(f"{self._archivos}/{info['file_path']}", timeout=60)
        return (PurePosixPath(info["file_path"]).name, r.content) if r.status_code == 200 else None


def _quien(usuario: dict) -> str:
    nombre = f"{usuario.get('first_name', '')} {usuario.get('last_name', '')}".strip()
    return (nombre or usuario.get("username") or "Telegram")[:120]


class Bot:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession], telegram: ClienteTelegram, chat_id: str):
        self.sesiones = sesiones
        self.tg = telegram
        self.chat_id = str(chat_id)
        # Conversaciones guiadas en curso por (chat, usuario): dos jefes pueden llenar su
        # reporte a la vez sin cruzarse. Se pierden si el bot se reinicia (basta con /falta).
        self.conversaciones: dict[tuple[int, int], dom.Conversacion] = {}

    # --- Base de datos ---------------------------------------------------------------
    async def leer_offset(self) -> int | None:
        async with self.sesiones() as s:
            fila = await s.get(EstadoBot, NOMBRE_ESTADO)
            return fila.offset if fila else None

    async def guardar_offset(self, offset: int) -> None:
        async with self.sesiones() as s:
            await s.execute(insert(EstadoBot).values(nombre=NOMBRE_ESTADO, offset=offset)
                            .on_conflict_do_update(index_elements=["nombre"], set_={"offset": offset}))
            await s.commit()

    async def catalogo(self) -> dom.Catalogo:
        async with self.sesiones() as s:
            personal = (await s.scalars(select(Personal))).all()
        return dom.Catalogo(
            operaciones=[p.nombre for p in personal if p.area == dom.OPERACIONES],
            administrativos={p.nombre: p.area for p in personal if p.area != dom.OPERACIONES},
        )

    async def guardar(self, falta: dom.Falta, supervisor: str, foto: tuple[str, bytes] | None) -> str:
        """Guarda la falta; devuelve un aviso si la foto no se pudo adjuntar."""
        aviso = ""
        async with self.sesiones() as s:
            registro = Expediente(colaborador=falta.colaborador, area=falta.area, tipo_falta=falta.tipo_falta,
                                  fecha_incidencia=falta.fecha, comentario=falta.comentario, supervisor=supervisor,
                                  origen="telegram", urls_externas=[])
            s.add(registro)
            await s.flush()
            if foto:
                try:
                    await arch.guardar(s, [arch.ArchivoNuevo(*foto)], ambito="expediente", referencia=str(registro.id),
                                       subido_por="telegram", permitidas=arch.EXT_EVIDENCIA)
                except HTTPException as e:
                    aviso = f" (la foto no se adjuntó: {e.detail})"
            await s.commit()
        return aviso

    async def _foto_de(self, mensaje: dict) -> tuple[str, bytes] | None:
        fotos = mensaje.get("photo")
        if not fotos:
            return None
        try:
            return await self.tg.descargar(fotos[-1]["file_id"])  # la última es la de mayor resolución
        except Exception:
            log.exception("No se pudo descargar la foto")
            return None

    # --- Actualizaciones ---------------------------------------------------------------
    async def atender(self, update: dict) -> None:
        if mensaje := update.get("message"):
            await self.mensaje(mensaje)
        elif boton := update.get("callback_query"):
            await self.boton(boton)

    async def mensaje(self, m: dict) -> None:
        chat = m.get("chat", {}).get("id")
        if str(chat) != self.chat_id:
            return  # el bot puede estar en otros grupos: solo atiende el configurado
        usuario = m.get("from", {})
        clave = (chat, usuario.get("id"))
        texto = (m.get("text") or "").strip()
        comando = texto.split()[0].split("@")[0].lower() if texto.startswith("/") else ""

        if comando == "/falta":
            self.conversaciones[clave], respuesta = dom.Conversacion.iniciar()
            await self.tg.enviar(chat, respuesta.texto, respuesta.botones)
            return
        if comando == "/cancelar":
            if self.conversaciones.pop(clave, None):
                await self.tg.enviar(chat, "❌ Reporte cancelado.")
            return
        if comando in ("/start", "/ayuda", "/help"):
            await self.tg.enviar(chat, dom.AYUDA)
            return

        if conversacion := self.conversaciones.get(clave):
            if m.get("photo") and conversacion.paso == "foto_espera":
                foto = await self._foto_de(m)
                respuesta = (conversacion.foto_recibida(*foto) if foto else
                             dom.Respuesta("⚠️ No se pudo descargar la foto. Envíala de nuevo o escribe /cancelar."))
            else:
                respuesta = conversacion.texto(texto, await self.catalogo(), ahora_hn().date())
            if respuesta:
                await self.tg.enviar(chat, respuesta.texto, respuesta.botones)
            return

        campos = dom.parse_mensaje_falta(texto or m.get("caption"))
        if campos is None:
            return  # charla normal del grupo
        resultado = dom.falta_desde_texto(campos, await self.catalogo(), ahora_hn().date())
        if isinstance(resultado, str):
            await self.tg.enviar(chat, resultado, responder_a=m.get("message_id"))
            return
        aviso = await self.guardar(resultado, _quien(usuario), await self._foto_de(m))
        await self.tg.enviar(chat, f"✅ Falta registrada para {resultado.colaborador} ({campos['motivo']}).{aviso}",
                             responder_a=m.get("message_id"))

    async def boton(self, cb: dict) -> None:
        chat = cb.get("message", {}).get("chat", {}).get("id")
        try:
            await self.tg.contestar_boton(cb.get("id"))
        except Exception:
            log.warning("No se pudo contestar el botón", exc_info=True)
        if str(chat) != self.chat_id:
            return
        clave = (chat, cb.get("from", {}).get("id"))
        conversacion = self.conversaciones.get(clave)
        if conversacion is None:
            return  # botón de una conversación vieja o de otra persona
        respuesta = conversacion.boton(cb.get("data", ""), ahora_hn().date())
        if respuesta is None:
            return
        if respuesta.fin == "guardar":
            self.conversaciones.pop(clave, None)
            try:
                aviso = await self.guardar(conversacion.falta(), _quien(cb.get("from", {})), conversacion.foto)
            except Exception:
                log.exception("No se pudo guardar la falta")
                await self.tg.enviar(chat, "❌ Hubo un error guardando el reporte. Avisa a soporte.")
                return
            await self.tg.enviar(chat, f"✅ Falta registrada para {conversacion.colaborador} "
                                       f"({conversacion.motivo}).{aviso}")
            return
        if respuesta.fin == "cancelar":
            self.conversaciones.pop(clave, None)
        await self.tg.enviar(chat, respuesta.texto, respuesta.botones)


async def principal() -> int:
    settings = get_settings()
    if not settings.telegram_token or not settings.telegram_chat_id:
        log.error("Falta configurar TELEGRAM_TOKEN y TELEGRAM_CHAT_ID")
        return 1
    engine = crear_engine(settings.database_url)
    try:
        async with httpx.AsyncClient() as http:
            bot = Bot(crear_sesiones(engine), ClienteTelegram(settings.telegram_token, http), settings.telegram_chat_id)
            offset = await bot.leer_offset()
            log.info("Bot de faltas escuchando el grupo %s (/falta)", settings.telegram_chat_id)
            while True:
                try:
                    for update in await bot.tg.actualizaciones(offset):
                        offset = update["update_id"]
                        try:
                            await bot.atender(update)
                        except Exception:
                            log.exception("Error atendiendo una actualización")
                        await bot.guardar_offset(offset)
                except Exception:
                    log.exception("Error en el ciclo de escucha")
                    await asyncio.sleep(ESPERA_TRAS_ERROR)
    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx registra cada URL en INFO, y las de Telegram llevan el token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    raise SystemExit(asyncio.run(principal()))


if __name__ == "__main__":
    main()
