"""
Cliente de la API de Cepheus (red interna de MAXCOM).

Límites que impone Cepheus y que este cliente respeta:
- 5 consultas por hora (código 102): al recibirlo NO se insiste con las
  demás cuentas, porque el cupo es compartido.
- fechaInicio de máximo ~2 meses atrás (si no, responde 400).
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import date

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

CODIGO_LIMITE_CONSULTAS = 102
DIAS_MAXIMOS_ATRAS = 60
_HORA_INICIO = "07:00"
_CABECERAS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "*/*"}


@dataclass
class RespuestaCepheus:
    ordenes: list[dict] = field(default_factory=list)
    cuenta: str | None = None
    # Por qué no hubo órdenes (límite de consultas, credenciales, red...).
    motivo: str | None = None


def _url_consulta(base: str, cuenta: str, fecha_inicio: date) -> str:
    # Se arma igual que el robot anterior, sin codificar ',', '/' ni ':',
    # por si el servidor interno es estricto con el formato.
    return (f"{base}?usuario={cuenta}&medios=FTTH,C"
            f"&fechaInicio={fecha_inicio:%d/%m/%Y}&horaInicio={_HORA_INICIO}")


def _leer_csv(texto: str) -> list[dict]:
    try:
        dialecto = csv.Sniffer().sniff(texto[:5000], delimiters=",;\t|")
    except csv.Error:
        dialecto = csv.excel
    return [dict(fila) for fila in csv.DictReader(io.StringIO(texto), dialect=dialecto)]


async def consultar_ordenes(
    settings: Settings, fecha_inicio: date, cliente: httpx.AsyncClient | None = None
) -> RespuestaCepheus:
    if not (settings.cepheus_url and settings.cepheus_usuario and settings.cepheus_contrasena):
        return RespuestaCepheus(motivo="falta configurar CEPHEUS_URL / CEPHEUS_USUARIO / CEPHEUS_CONTRASENA")
    if not settings.cepheus_usuarios_consulta:
        return RespuestaCepheus(motivo="falta configurar CEPHEUS_USUARIOS_CONSULTA")

    propio = cliente is None
    if propio:
        cliente = httpx.AsyncClient(
            verify=settings.cepheus_verificar_tls,
            timeout=settings.cepheus_timeout_seg,
            trust_env=False,  # servidor interno: sin pasar por proxies del sistema
        )
    auth = httpx.BasicAuth(settings.cepheus_usuario, settings.cepheus_contrasena)
    motivos: list[str] = []
    try:
        for cuenta in settings.cepheus_usuarios_consulta:
            url = _url_consulta(settings.cepheus_url, cuenta, fecha_inicio)
            try:
                resp = await cliente.get(url, auth=auth, headers=_CABECERAS)
            except httpx.HTTPError as e:
                motivos.append(f"{cuenta}: error de conexión ({e.__class__.__name__}: {e})")
                continue

            if resp.status_code != 200:
                # El cuerpo es donde Cepheus explica el porqué (rango de fechas, parámetros...).
                motivos.append(f"{cuenta}: HTTP {resp.status_code}: {resp.text.strip()[:300]}")
                continue

            tipo = resp.headers.get("content-type", "").lower()
            texto = resp.text.strip()
            if "json" in tipo or texto.startswith("{"):
                try:
                    datos = resp.json()
                except ValueError as e:
                    motivos.append(f"{cuenta}: respuesta JSON inválida ({e})")
                    continue
                codigo = datos.get("codigo")
                mensaje = datos.get("mensaje", "sin mensaje")
                if codigo == CODIGO_LIMITE_CONSULTAS:
                    return RespuestaCepheus(
                        cuenta=cuenta,
                        motivo=f"límite de consultas de Cepheus alcanzado (código 102): {mensaje}",
                    )
                ordenes = datos.get("ordenes") or []
                if codigo != 200 or not ordenes:
                    motivos.append(f"{cuenta}: sin órdenes (código {codigo}): {mensaje}")
                    continue
                log.info("Cepheus devolvió %s órdenes con la cuenta %s", len(ordenes), cuenta)
                return RespuestaCepheus(ordenes=ordenes, cuenta=cuenta)

            # Compatibilidad: el webservice viejo respondía un archivo; se acepta CSV.
            filas = _leer_csv(texto) if texto else []
            if filas:
                log.info("Cepheus devolvió un archivo con %s filas (cuenta %s)", len(filas), cuenta)
                return RespuestaCepheus(ordenes=filas, cuenta=cuenta)
            motivos.append(f"{cuenta}: respuesta vacía o en formato no reconocido ({tipo or 'sin tipo'})")
    finally:
        if propio:
            await cliente.aclose()

    return RespuestaCepheus(motivo="; ".join(motivos) or "Cepheus no devolvió órdenes")
