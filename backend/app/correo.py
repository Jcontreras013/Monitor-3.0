"""
Envío de correos por SMTP (alertas del robot y correo de prueba).

Port de notificaciones.py. La configuración viene de las variables CORREO_*
(ver .env.example). smtplib es bloqueante: desde código async se llama con
asyncio.to_thread.
"""

from __future__ import annotations

import html
import smtplib
import ssl
from collections.abc import Sequence
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import Settings


@dataclass(frozen=True)
class ConfigCorreo:
    servidor: str
    puerto: int
    usuario: str
    contrasena: str
    remitente: str
    destinatarios: list[str]
    destinatarios_vip: list[str]

    @classmethod
    def desde(cls, settings: Settings) -> ConfigCorreo:
        return cls(
            servidor=settings.correo_servidor.strip(), puerto=settings.correo_puerto,
            usuario=settings.correo_usuario.strip(), contrasena=settings.correo_contrasena,
            remitente=(settings.correo_remitente or settings.correo_usuario).strip(),
            destinatarios=list(settings.correo_destinatarios),
            # Sin lista VIP propia, los avisos VIP van a la lista general.
            destinatarios_vip=list(settings.correo_destinatarios_vip or settings.correo_destinatarios),
        )

    def falta(self) -> str | None:
        """Qué falta para poder enviar, o None si está completo."""
        faltantes = [nombre for nombre, valor in (
            ("CORREO_SERVIDOR", self.servidor), ("CORREO_USUARIO", self.usuario),
            ("CORREO_CONTRASENA", self.contrasena), ("CORREO_DESTINATARIOS", self.destinatarios),
        ) if not valor]
        return ", ".join(faltantes) if faltantes else None


def modo(puerto: int) -> str:
    return "SSL/TLS" if puerto == 465 else "STARTTLS (TLS)"


def tabla_html(encabezados: Sequence[str], filas: Sequence[Sequence[object]]) -> str:
    """Tabla HTML con estilos en línea (los clientes de correo ignoran <style>)."""
    celda = "border:1px solid #d0d7e2;padding:4px 8px;font-size:12px;vertical-align:top;"
    cabeza = "".join(f'<th style="{celda}background:#e6ebf5;text-align:left;">{html.escape(str(c))}</th>'
                     for c in encabezados)
    cuerpo = "".join(
        "<tr>" + "".join(f'<td style="{celda}">{html.escape("" if v is None else str(v))}</td>' for v in fila) + "</tr>"
        for fila in filas
    )
    return f'<table style="border-collapse:collapse;font-family:Arial,sans-serif;"><tr>{cabeza}</tr>{cuerpo}</table>'


def texto_plano(encabezados: Sequence[str], filas: Sequence[Sequence[object]]) -> str:
    return "\n".join(" | ".join(f"{k}: {'' if v is None else v}" for k, v in zip(encabezados, fila, strict=True))
                     for fila in filas)


def _enviar_por_puerto(config: ConfigCorreo, puerto: int, mensaje: EmailMessage) -> None:
    contexto = ssl.create_default_context()
    if puerto == 465:
        with smtplib.SMTP_SSL(config.servidor, puerto, context=contexto, timeout=30) as smtp:
            smtp.login(config.usuario, config.contrasena)
            smtp.send_message(mensaje)
    else:
        with smtplib.SMTP(config.servidor, puerto, timeout=30) as smtp:
            smtp.starttls(context=contexto)
            smtp.login(config.usuario, config.contrasena)
            smtp.send_message(mensaje)


def enviar_correo(config: ConfigCorreo, destinatarios: list[str], asunto: str, texto: str,
                  cuerpo_html: str | None = None) -> tuple[bool, str | None]:
    """Envía un correo. Devuelve (True, nota opcional) o (False, motivo)."""
    if faltante := config.falta():
        return False, f"falta configurar {faltante}"
    if not destinatarios:
        return False, "no hay destinatarios"

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = config.remitente
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(texto)
    if cuerpo_html:
        mensaje.add_alternative(cuerpo_html, subtype="html")

    # Si el puerto configurado no conecta, se prueban los puertos cifrados
    # estándar (587 = STARTTLS, 465 = SSL/TLS). Solo ante fallas de CONEXIÓN:
    # una contraseña o un destinatario rechazado no se arreglan cambiando de puerto.
    puertos = [config.puerto] + [p for p in (587, 465) if p != config.puerto]
    fallas = []
    for puerto in puertos:
        try:
            _enviar_por_puerto(config, puerto, mensaje)
            if puerto != config.puerto:
                return True, (f"se envió por el puerto {puerto} ({modo(puerto)}) porque el {config.puerto} "
                              f"no conectó; conviene poner CORREO_PUERTO={puerto}")
            return True, None
        # El orden importa: los errores SMTP y de certificado también son OSError.
        except smtplib.SMTPAuthenticationError:
            return False, "el servidor de correo rechazó el usuario o la contraseña"
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as e:
            fallas.append(f"{puerto} ({modo(puerto)}): {e}")
        except smtplib.SMTPException as e:
            return False, f"el servidor de correo respondió con un error: {e}"
        except ssl.SSLCertVerificationError:
            return False, (f"el certificado del servidor no corresponde a '{config.servidor}'. Usa el nombre "
                           "del servidor del proveedor de correo (en MAXCOM: smtp.us-east.atmailcloud.com)")
        except OSError as e:
            fallas.append(f"{puerto} ({modo(puerto)}): {e}")
    return False, (f"no se pudo conectar a {config.servidor} por ningún puerto [{'; '.join(fallas)}]. "
                   "Revisa el nombre del servidor y que el firewall permita salir por los puertos 465 o 587")


def enviar_prueba(config: ConfigCorreo, origen: str = "la app") -> tuple[bool, str | None]:
    texto = (
        f"Este es un correo de prueba enviado desde {origen} del Monitor Operativo MAXCOM.\n\n"
        "Si lo recibiste, las alertas por correo (cajas molex en soporte y órdenes de clientes VIP) "
        "van a llegar a esta misma lista de destinatarios."
    )
    return enviar_correo(config, config.destinatarios, "✅ Prueba de alertas por correo - Monitor Operativo", texto)
