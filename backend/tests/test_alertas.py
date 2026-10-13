"""Alertas por correo del robot (con un envío falso: no sale nada a internet)."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app import repositorio
from app.alertas import procesar_alertas
from app.correo import ConfigCorreo
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import normalizar_orden
from app.models import AlertaEnviada, ClienteVip, EstadoAlerta

CONFIG = ConfigCorreo(servidor="smtp.ejemplo.hn", puerto=587, usuario="robot@ejemplo.hn", contrasena="x",
                      remitente="robot@ejemplo.hn", destinatarios=["jefe@ejemplo.hn"],
                      destinatarios_vip=["vip@ejemplo.hn"])
FMT = "%Y-%m-%d %H:%M:%S"


class EnvioFalso:
    def __init__(self, ok=True, nota=None):
        self.enviados, self.ok, self.nota = [], ok, nota

    def __call__(self, config, destinatarios, asunto, texto, cuerpo=None):
        self.enviados.append({"para": destinatarios, "asunto": asunto, "texto": texto, "html": cuerpo})
        return self.ok, self.nota


async def _cargar(sesiones, crudas):
    ahora = ahora_hn()
    async with sesiones() as s:
        await repositorio.guardar_ordenes(s, [o for c in crudas if (o := normalizar_orden(c, ahora))])
        s.add_all([ClienteVip(cliente="200100", nombre="Hotel Palmira", clase="Corporativo")])
        await s.commit()


def _ordenes(ahora):
    def h(horas):
        return (ahora - timedelta(hours=horas)).strftime(FMT)

    return [
        # VIP nueva, sin atender: se avisa.
        {"NUM": "1", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "ASIGNADA", "CLIENTE": "200100", "TECNICO": "Ana",
         "FECHA_APE": h(2), "COMENTARIO": "sin internet"},
        # VIP pero vieja: fuera de la ventana de 24 h.
        {"NUM": "2", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "ASIGNADA", "CLIENTE": "200100",
         "FECHA_APE": h(72)},
        # VIP ya cerrada: no se avisa.
        {"NUM": "3", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "CERRADA", "CLIENTE": "200100", "TECNICO": "Ana",
         "FECHA_APE": h(3), "HORA_LIQ": h(1)},
        # Cierre de soporte con molex nueva en medio: se avisa.
        {"NUM": "4", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "CERRADA", "CLIENTE": "1", "TECNICO": "Beto",
         "FECHA_APE": h(5), "HORA_LIQ": h(1),
         "COMENTARIO DE CIERRE": "Corte de acometida, se le añadió una molex en medio del tramo",
         "RAZON CIERRE": "Corte de Acometida"},
        # Molex de la casa: no se avisa.
        {"NUM": "5", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "CERRADA", "CLIENTE": "2", "TECNICO": "Beto",
         "FECHA_APE": h(5), "HORA_LIQ": h(1),
         "COMENTARIO DE CIERRE": "Fibra dañada en la molex, se preparó y se fusiona"},
        # Instalación con molex: no es soporte, no se avisa.
        {"NUM": "6", "ACTIVIDAD": "INSFIBRA", "ESTADO": "CERRADA", "CLIENTE": "3", "TECNICO": "Beto",
         "FECHA_APE": h(5), "HORA_LIQ": h(1),
         "COMENTARIO DE CIERRE": "se puso una molex nueva"},
    ]


async def test_avisa_una_sola_vez_vip_y_molex(sesiones):
    ahora = ahora_hn()
    await _cargar(sesiones, _ordenes(ahora))
    envio = EnvioFalso()

    estados = await procesar_alertas(sesiones, CONFIG, ahora, envio)
    assert [(a, r) for a, r, _ in estados] == [("Clientes VIP", "enviado"), ("Molex en cierres", "enviado")]
    vip, molex = envio.enviados
    assert vip["para"] == ["vip@ejemplo.hn"] and "Hotel Palmira" in vip["asunto"]
    assert "sin internet" in vip["html"] and ">2<" not in vip["html"]
    assert molex["para"] == ["jefe@ejemplo.hn"] and "1 orden(es)" in molex["asunto"]
    assert "Corte de Acometida" in molex["texto"] and "Beto" in molex["texto"]

    async with sesiones() as s:
        avisadas = {(a.alerta, a.num) for a in (await s.scalars(select(AlertaEnviada))).all()}
        guardados = {e.alerta: e.resultado for e in (await s.scalars(select(EstadoAlerta))).all()}
    assert avisadas == {("vip", "1"), ("molex", "4")}
    assert guardados == {"Clientes VIP": "enviado", "Molex en cierres": "enviado"}

    # Segundo ciclo: ya no hay nada nuevo que avisar.
    estados = await procesar_alertas(sesiones, CONFIG, ahora, envio)
    assert len(envio.enviados) == 2
    assert [r for _, r, _ in estados] == ["sin novedades", "sin novedades"]
    assert "ya avisadas antes: 1" in estados[0][2]


async def test_si_falla_el_envio_se_reintenta_en_el_siguiente_ciclo(sesiones):
    ahora = ahora_hn()
    await _cargar(sesiones, _ordenes(ahora))
    estados = await procesar_alertas(sesiones, CONFIG, ahora, EnvioFalso(ok=False, nota="contraseña rechazada"))
    assert [r for _, r, _ in estados] == ["error al enviar", "error al enviar"]
    assert "contraseña rechazada" in estados[0][2]

    envio = EnvioFalso()
    await procesar_alertas(sesiones, CONFIG, ahora, envio)
    assert len(envio.enviados) == 2


async def test_sin_configuracion_de_correo_y_sin_lista_vip(sesiones):
    ahora = ahora_hn()
    sin_correo = ConfigCorreo("", 587, "", "", "", [], [])
    estados = await procesar_alertas(sesiones, sin_correo, ahora, EnvioFalso())
    assert estados[0][:2] == ("Correo", "desactivado")
    assert "CORREO_SERVIDOR" in estados[0][2]
    assert estados[1][:2] == ("Clientes VIP", "sin lista VIP")
    assert estados[2][:2] == ("Molex en cierres", "sin novedades")
