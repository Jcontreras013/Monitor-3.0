"""Bot de Telegram: conversación (sin red) y bot completo contra la base con un Telegram falso."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.dominio import telegram as dom
from app.models import Archivo, Expediente, Personal
from tests.utiles import png
from worker.telegram import Bot

HOY = date(2026, 10, 13)
CATALOGO = dom.Catalogo(
    operaciones=["CARLOS ALBERTO MEJIA LOPEZ", "ANA MARIA RODRIGUEZ"],
    administrativos={"SAYRA ESCOBAR": "SAC", "CARLOS GARCIA": "BODEGA"},
)


def test_parse_mensaje_falta():
    assert dom.parse_mensaje_falta("hola a todos") is None
    assert dom.parse_mensaje_falta(None) is None
    campos = dom.parse_mensaje_falta(
        "Falta\nColaborador: Carlos Mejia\nÁrea: operaciones\nMotivo: Llegada tarde\n"
        "Fecha: 12/10/2026\nDescripción: llegó 8:40: sin avisar\nlínea suelta")
    assert campos == {"colaborador": "Carlos Mejia", "area": "operaciones", "motivo": "Llegada tarde",
                      "fecha": "12/10/2026", "descripcion": "llegó 8:40: sin avisar"}


def test_resolver_area_y_colaborador():
    assert dom.resolver_area("Técnicos") == dom.OPERACIONES
    assert dom.resolver_area("call center") == dom.ADMINISTRATIVO
    assert dom.resolver_area("Opreaciones") == dom.OPERACIONES  # con error de dedo
    assert dom.resolver_area("Gerencia") is None
    assert dom.resolver_colaborador("carlos mejia", dom.OPERACIONES, CATALOGO) == (
        "CARLOS ALBERTO MEJIA LOPEZ", dom.OPERACIONES)
    assert dom.resolver_colaborador("Sayra Escobar", dom.ADMINISTRATIVO, CATALOGO) == ("SAYRA ESCOBAR", "SAC")
    assert dom.resolver_colaborador("Sayra Escobar", dom.OPERACIONES, CATALOGO) is None
    assert dom.resolver_colaborador("Pedro Picapiedra", dom.OPERACIONES, CATALOGO) is None


def test_falta_desde_texto():
    base = {"colaborador": "carlos mejia", "area": "campo", "motivo": "llegada  tarde", "fecha": "", "descripcion": ""}
    falta = dom.falta_desde_texto(base, CATALOGO, HOY)
    assert falta == dom.Falta("CARLOS ALBERTO MEJIA LOPEZ", dom.OPERACIONES, "LLEGADA TARDE", HOY, "Sin descripción")
    assert "colaborador" in dom.falta_desde_texto({**base, "colaborador": ""}, CATALOGO, HOY)
    assert "No reconozco el área" in dom.falta_desde_texto({**base, "area": "x"}, CATALOGO, HOY)
    assert "No encontré" in dom.falta_desde_texto({**base, "colaborador": "Nadie"}, CATALOGO, HOY)
    assert dom.falta_desde_texto({**base, "fecha": "01/01/2030"}, CATALOGO, HOY).fecha == HOY  # futura -> hoy
    assert dom.falta_desde_texto({**base, "fecha": "2026-10-01"}, CATALOGO, HOY).fecha == date(2026, 10, 1)


def test_formulario_guiado_completo():
    conv, r = dom.Conversacion.iniciar()
    assert [d for _, d in r.botones] == ["area|OPERACIONES", "area|ADMINISTRATIVO"]
    assert conv.boton("motivo|1", HOY) is None  # botón fuera de orden: se ignora
    r = conv.boton("area|OPERACIONES", HOY)
    assert ("Llegada Tarde", "motivo|1") in r.botones
    assert "colaborador" in conv.boton("motivo|1", HOY).texto
    assert "No encontré" in conv.texto("Juan Nadie", CATALOGO, HOY).texto
    assert conv.texto("ana rodriguez", CATALOGO, HOY).botones[1] == ("Ayer", "fecha|ayer")
    assert conv.boton("fecha|ayer", HOY).texto == "Describe lo sucedido:"
    assert conv.texto("No llegó a la primera orden", CATALOGO, HOY).botones[1] == ("No, continuar", "foto|no")
    r = conv.boton("foto|si", HOY)
    assert conv.texto("aquí va", CATALOGO, HOY).texto.startswith("Envía una foto")
    r = conv.foto_recibida("f.png", b"...")
    assert "Foto: Sí" in r.texto and "Fecha: 12/10/2026" in r.texto
    assert conv.boton("confirmar|si", HOY).fin == "guardar"
    assert conv.falta() == dom.Falta("ANA MARIA RODRIGUEZ", dom.OPERACIONES, "LLEGADA TARDE",
                                     HOY - timedelta(days=1), "No llegó a la primera orden")


def test_formulario_reco_otro_y_administrativo():
    reco, _ = dom.Conversacion.iniciar()
    reco.boton("area|OPERACIONES", HOY)
    assert reco.boton(f"motivo|{dom_index('Reco / Cambio de Postes')}", HOY).texto == "¿Cuándo ocurrió?"
    reco.boton("fecha|hoy", HOY)
    reco.texto("Poste caído en Col. Kennedy", CATALOGO, HOY)
    reco.boton("foto|no", HOY)
    assert reco.falta().colaborador == "RECO" and reco.falta().tipo_falta == "RECO / CAMBIO DE POSTES"

    admin, _ = dom.Conversacion.iniciar()
    admin.boton("area|ADMINISTRATIVO", HOY)
    assert "específico" in admin.boton("motivo|7", HOY).texto  # Otro
    admin.texto("uso del celular", CATALOGO, HOY)
    admin.texto("carlos garcia", CATALOGO, HOY)
    admin.boton("fecha|otra", HOY)
    assert "No entendí" in admin.texto("mañana", CATALOGO, HOY).texto
    admin.texto("01/10/2026", CATALOGO, HOY)
    admin.texto("", CATALOGO, HOY)
    admin.boton("foto|no", HOY)
    assert admin.falta() == dom.Falta("CARLOS GARCIA", "BODEGA", "USO DEL CELULAR", date(2026, 10, 1),
                                      "Sin descripción")
    assert admin.boton("confirmar|no", HOY).fin == "cancelar"


def dom_index(motivo: str) -> int:
    return dom.motivos_de(dom.OPERACIONES).index(motivo)


# ------------------------------------------------------------------------------
# Bot completo con un Telegram falso
# ------------------------------------------------------------------------------
GRUPO = -100123


class TelegramFalso:
    def __init__(self):
        self.enviados: list[tuple[int, str, list | None]] = []
        self.contestados = 0

    async def enviar(self, chat_id, texto, botones=None, responder_a=None):
        self.enviados.append((chat_id, texto, botones))

    async def contestar_boton(self, callback_id):
        self.contestados += 1

    async def descargar(self, file_id):
        return ("foto.png", png()) if file_id == "buena" else ("foto.jpg", b"no es imagen")


def _mensaje(texto, usuario=7, chat=GRUPO, **extra):
    return {"message": {"message_id": 1, "chat": {"id": chat}, "from": {"id": usuario, "first_name": "Jefe",
                                                                        "last_name": "Ruta"}, "text": texto, **extra}}


def _boton(dato, usuario=7):
    return {"callback_query": {"id": "c", "data": dato, "from": {"id": usuario, "first_name": "Jefe"},
                               "message": {"chat": {"id": GRUPO}}}}


async def _bot(sesiones) -> tuple[Bot, TelegramFalso]:
    async with sesiones() as s:
        s.add_all([Personal(nombre="CARLOS ALBERTO MEJIA LOPEZ", area="OPERACIONES"),
                   Personal(nombre="SAYRA ESCOBAR", area="SAC")])
        await s.commit()
    tg = TelegramFalso()
    return Bot(sesiones, tg, str(GRUPO)), tg


async def test_bot_texto_libre_con_foto_y_otros_grupos(sesiones):
    bot, tg = await _bot(sesiones)
    await bot.atender(_mensaje("FALTA\nColaborador: carlos mejia\nÁrea: operaciones\nMotivo: Exceso de velocidad",
                               chat=-999))
    await bot.atender(_mensaje("buenos días"))
    assert tg.enviados == []

    texto = "FALTA\nColaborador: carlos mejia\nArea: operaciones\nMotivo: Exceso de velocidad\nDetalle: 92 km/h"
    await bot.atender({"message": {**_mensaje(None)["message"], "caption": texto, "photo": [{"file_id": "x"},
                                                                                          {"file_id": "buena"}]}})
    assert tg.enviados[-1][1] == "✅ Falta registrada para CARLOS ALBERTO MEJIA LOPEZ (Exceso de velocidad)."
    async with sesiones() as s:
        e = await s.scalar(select(Expediente))
        fotos = (await s.scalars(select(Archivo).where(Archivo.referencia == str(e.id)))).all()
    assert (e.colaborador, e.area, e.tipo_falta, e.origen, e.supervisor) == (
        "CARLOS ALBERTO MEJIA LOPEZ", "OPERACIONES", "EXCESO DE VELOCIDAD", "telegram", "Jefe Ruta")
    assert e.comentario == "92 km/h" and [f.mime for f in fotos] == ["image/png"]

    await bot.atender(_mensaje("FALTA\nColaborador: Nadie\nÁrea: SAC\nMotivo: x"))
    assert "No encontré" in tg.enviados[-1][1]


async def test_bot_formulario_guiado(sesiones):
    bot, tg = await _bot(sesiones)
    await bot.atender(_mensaje("/falta@MaxcomBot"))
    await bot.atender(_boton("area|ADMINISTRATIVO", usuario=8))  # otra persona: no le toca
    assert len(tg.enviados) == 1
    await bot.atender(_boton("area|ADMINISTRATIVO"))
    await bot.atender(_boton("motivo|1"))                # Amonestación Escrita
    await bot.atender(_mensaje("sayra escobar"))
    await bot.atender(_boton("fecha|hoy"))
    await bot.atender(_mensaje("Llegó tarde a turno"))
    await bot.atender(_boton("foto|si"))
    await bot.atender(_mensaje(None, photo=[{"file_id": "mala"}]))  # foto que no es imagen
    assert "Foto: Sí" in tg.enviados[-1][1]
    await bot.atender(_boton("confirmar|si"))
    assert tg.enviados[-1][1].startswith("✅ Falta registrada para SAYRA ESCOBAR (Amonestación Escrita).")
    assert "la foto no se adjuntó" in tg.enviados[-1][1]
    assert tg.contestados == 6  # todos los botones se contestan, también el de la otra persona
    async with sesiones() as s:
        e = await s.scalar(select(Expediente))
    assert (e.colaborador, e.area, e.tipo_falta) == ("SAYRA ESCOBAR", "SAC", "AMONESTACIÓN ESCRITA")
    assert bot.conversaciones == {}

    await bot.atender(_mensaje("/falta"))
    await bot.atender(_mensaje("/cancelar"))
    assert tg.enviados[-1][1] == "❌ Reporte cancelado." and bot.conversaciones == {}


async def test_offset_se_guarda_en_la_base(sesiones):
    bot, _ = await _bot(sesiones)
    assert await bot.leer_offset() is None
    await bot.guardar_offset(41)
    await bot.guardar_offset(42)
    assert await bot.leer_offset() == 42


async def test_cliente_telegram_arma_bien_las_peticiones():
    import json

    import httpx

    from worker.telegram import ClienteTelegram

    vistas = []

    def responder(peticion: httpx.Request) -> httpx.Response:
        vistas.append(peticion)
        if peticion.url.path.endswith("/getFile"):
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "photos/file_9.jpg"}})
        if "/file/" in peticion.url.path:
            return httpx.Response(200, content=b"\xff\xd8\xffdatos")
        return httpx.Response(200, json={"ok": True, "result": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        tg = ClienteTelegram("123:ABC", http)
        assert await tg.actualizaciones(41) == []
        await tg.enviar(GRUPO, "hola", [("Sí", "foto|si")], responder_a=5)
        assert await tg.descargar("f") == ("file_9.jpg", b"\xff\xd8\xffdatos")

    assert vistas[0].url.path == "/bot123:ABC/getUpdates" and json.loads(vistas[0].content)["offset"] == 42
    envio = json.loads(vistas[1].content)
    assert envio["reply_markup"] == {"inline_keyboard": [[{"text": "Sí", "callback_data": "foto|si"}]]}
    assert envio["reply_parameters"]["message_id"] == 5
    assert vistas[3].url.path == "/file/bot123:ABC/photos/file_9.jpg"
