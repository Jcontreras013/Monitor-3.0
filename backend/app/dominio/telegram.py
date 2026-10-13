"""
Bot de Telegram para registrar faltas desde el grupo de jefes.

Port de telegram_bot.py. Aquí está solo la conversación (qué preguntar, cómo
entender lo que escriben), sin Telegram ni base de datos: worker/telegram.py
hace el envío de mensajes, descarga las fotos y guarda en Expedientes.

Dos formas de reportar, igual que antes:
  1) /falta: formulario guiado con botones (las mismas opciones que el
     formulario de Expedientes de la app).
  2) Un mensaje de texto libre que empieza con FALTA, con líneas
     "Etiqueta: valor" (ver parse_mensaje_falta).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.dominio import expedientes as dom_exp
from app.dominio.nombres import normalizar_nombre_cruce, resolver_tecnico_por_similitud

OPERACIONES = dom_exp.AREA_OPERACIONES
ADMINISTRATIVO = "ADMINISTRATIVO"

# Sinónimos aceptados para el "Área" del mensaje libre: los jefes no siempre
# escriben exactamente "Operaciones" o "SAC".
SINONIMOS_AREA = {
    "OPERACIONES": OPERACIONES, "OPERACION": OPERACIONES, "TECNICOS": OPERACIONES, "TECNICO": OPERACIONES,
    "CAMPO": OPERACIONES, "INSTALACIONES": OPERACIONES,
    "SAC": ADMINISTRATIVO, "ADMINISTRATIVO": ADMINISTRATIVO, "ADMINISTRACION": ADMINISTRATIVO,
    "ADMIN": ADMINISTRATIVO, "VENTAS": ADMINISTRATIVO, "CALL CENTER": ADMINISTRATIVO,
    "CALLCENTER": ADMINISTRATIVO, "OFICINA": ADMINISTRATIVO,
}
MOTIVO_RECO = "Reco / Cambio de Postes"

AYUDA = (
    "Para registrar una falta:\n"
    "• /falta — formulario guiado con botones.\n"
    "• O un mensaje así (la foto es opcional, va en el mismo mensaje):\n"
    "FALTA\nColaborador: Juan Pérez\nÁrea: Operaciones\nMotivo: Llegada tarde\n"
    "Fecha: 19/09/2026\nDescripción: llegó 8:40 sin avisar\n\n"
    "/cancelar cancela un reporte a medias."
)


def motivos_de(area: str) -> tuple[str, ...]:
    return dom_exp.MOTIVOS_OPERACIONES if area == OPERACIONES else dom_exp.MOTIVOS_ADMINISTRATIVO


@dataclass
class Catalogo:
    """Personal contra el que se resuelve el nombre que escriben."""

    operaciones: list[str]
    administrativos: dict[str, str]  # nombre -> departamento


@dataclass
class Falta:
    """Lo que se guarda en Expedientes."""

    colaborador: str
    area: str
    tipo_falta: str
    fecha: date
    comentario: str


def resolver_area(texto: str) -> str | None:
    norm = normalizar_nombre_cruce(texto)
    if not norm:
        return None
    if norm in SINONIMOS_AREA:
        return SINONIMOS_AREA[norm]
    parecido = difflib.get_close_matches(norm, list(SINONIMOS_AREA), n=1, cutoff=0.75)
    return SINONIMOS_AREA[parecido[0]] if parecido else None


def resolver_colaborador(nombre: str, area: str, catalogo: Catalogo) -> tuple[str, str] | None:
    """(nombre del catálogo, área para guardar) o None si no está en el listado de esa área."""
    if area == OPERACIONES:
        candidato, _ = resolver_tecnico_por_similitud(nombre, catalogo.operaciones)
        conocidos = {normalizar_nombre_cruce(n) for n in catalogo.operaciones}
        return (candidato, OPERACIONES) if normalizar_nombre_cruce(candidato) in conocidos else None
    candidato, _ = resolver_tecnico_por_similitud(nombre, list(catalogo.administrativos))
    por_norm = {normalizar_nombre_cruce(n): (n, a) for n, a in catalogo.administrativos.items()}
    return por_norm.get(normalizar_nombre_cruce(candidato))


def parse_fecha_libre(texto: str) -> date | None:
    """DD/MM/AAAA, DD-MM-AAAA o AAAA-MM-DD."""
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime((texto or "").strip(), formato).date()
        except ValueError:
            continue
    return None


def _tipo_falta(motivo: str) -> str:
    return " ".join(motivo.upper().split())


def _colaborador(nombre: str) -> str:
    return " ".join(nombre.upper().split())


# ------------------------------------------------------------------------------
# Formulario guiado (/falta)
# ------------------------------------------------------------------------------
Botones = list[tuple[str, str]]  # (texto, callback_data)


@dataclass
class Respuesta:
    texto: str
    botones: Botones | None = None
    # "guardar": la conversación terminó y hay que guardar la falta;
    # "cancelar": terminó sin guardar. None: sigue.
    fin: str | None = None


@dataclass
class Conversacion:
    paso: str = "area"
    area: str = ""
    motivo: str = ""
    colaborador: str = ""
    area_colaborador: str = ""
    fecha: date | None = None
    descripcion: str = ""
    foto: tuple[str, bytes] | None = None  # (nombre, contenido), lo llena el worker

    @classmethod
    def iniciar(cls) -> tuple[Conversacion, Respuesta]:
        return cls(), Respuesta("📝 Nuevo reporte de falta/incidencia.\n¿Cuál es el área del colaborador?",
                                [("Operaciones (técnicos/campo)", f"area|{OPERACIONES}"),
                                 ("SAC / Administrativo", f"area|{ADMINISTRATIVO}")])

    def falta(self) -> Falta:
        if self.motivo == MOTIVO_RECO:
            colaborador, tipo = dom_exp.COLABORADOR_RECO, "RECO / CAMBIO DE POSTES"
        else:
            colaborador, tipo = _colaborador(self.colaborador), _tipo_falta(self.motivo)
        return Falta(colaborador=colaborador, area=self.area_colaborador or OPERACIONES, tipo_falta=tipo,
                     fecha=self.fecha, comentario=self.descripcion or "Sin descripción")

    def resumen(self) -> Respuesta:
        texto = (f"📋 Resumen del reporte:\nÁrea: {self.area_colaborador}\nMotivo: {self.motivo}\n"
                 f"Colaborador: {self.colaborador}\nFecha: {self.fecha:%d/%m/%Y}\n"
                 f"Descripción: {self.descripcion}\nFoto: {'Sí' if self.foto else 'No'}\n\n¿Guardar este reporte?")
        return Respuesta(texto, [("✅ Guardar", "confirmar|si"), ("❌ Cancelar", "confirmar|no")])

    def _preguntar_fecha(self) -> Respuesta:
        self.paso = "fecha"
        return Respuesta("¿Cuándo ocurrió?",
                         [("Hoy", "fecha|hoy"), ("Ayer", "fecha|ayer"), ("Otra fecha", "fecha|otra")])

    def _preguntar_colaborador(self) -> Respuesta:
        self.paso = "colaborador"
        return Respuesta("¿Quién es el colaborador? Escribe su nombre.")

    def _preguntar_descripcion(self) -> Respuesta:
        self.paso = "descripcion"
        return Respuesta("Describe lo sucedido:")

    def boton(self, dato: str, hoy: date) -> Respuesta | None:
        """Un botón tocado. None si no corresponde al paso actual (botón viejo)."""
        tipo, _, valor = dato.partition("|")
        if tipo == "area" and self.paso == "area" and valor in (OPERACIONES, ADMINISTRATIVO):
            self.area, self.paso = valor, "motivo"
            return Respuesta("¿Cuál es el motivo?", [(m, f"motivo|{i}") for i, m in enumerate(motivos_de(valor))])
        if tipo == "motivo" and self.paso == "motivo" and valor.isdigit():
            motivos = motivos_de(self.area)
            elegido = motivos[int(valor)] if int(valor) < len(motivos) else "Otro"
            if elegido == "Otro":
                self.paso = "motivo_otro"
                return Respuesta("Escribe el motivo específico:")
            self.motivo = elegido
            if elegido == MOTIVO_RECO:
                # Igual que en la app: esta falta queda a nombre de RECO, sin pedir colaborador.
                self.colaborador, self.area_colaborador = dom_exp.COLABORADOR_RECO, OPERACIONES
                return self._preguntar_fecha()
            return self._preguntar_colaborador()
        if tipo == "fecha" and self.paso == "fecha":
            if valor in ("hoy", "ayer"):
                self.fecha = hoy if valor == "hoy" else hoy - timedelta(days=1)
                return self._preguntar_descripcion()
            self.paso = "fecha_texto"
            return Respuesta("Escribe la fecha (DD/MM/AAAA):")
        if tipo == "foto" and self.paso == "foto":
            if valor == "si":
                self.paso = "foto_espera"
                return Respuesta("Envía la foto ahora.")
            self.paso = "confirmar"
            return self.resumen()
        if tipo == "confirmar" and self.paso == "confirmar":
            if valor == "si":
                return Respuesta("", fin="guardar")
            return Respuesta("❌ Reporte cancelado, no se guardó nada.", fin="cancelar")
        return None

    def texto(self, texto: str, catalogo: Catalogo, hoy: date) -> Respuesta | None:
        """Texto escrito en un paso que lo espera. None si el paso espera un botón."""
        texto = (texto or "").strip()
        if self.paso == "motivo_otro":
            if not texto:
                return Respuesta("Escribe el motivo específico:")
            self.motivo = texto
            return self._preguntar_colaborador()
        if self.paso == "colaborador":
            encontrado = resolver_colaborador(texto, self.area, catalogo)
            if encontrado is None:
                listado = "Operaciones" if self.area == OPERACIONES else "personal administrativo"
                return Respuesta(f"⚠️ No encontré a \"{texto}\" en el listado de {listado}. "
                                 "Escribe el nombre de nuevo (o /cancelar).")
            self.colaborador, self.area_colaborador = encontrado
            return self._preguntar_fecha()
        if self.paso == "fecha_texto":
            fecha = parse_fecha_libre(texto)
            if fecha is None or fecha > hoy:
                return Respuesta("⚠️ No entendí esa fecha. Escríbela como DD/MM/AAAA (ej. 19/09/2026); "
                                 "no puede ser una fecha futura.")
            self.fecha = fecha
            return self._preguntar_descripcion()
        if self.paso == "descripcion":
            self.descripcion = texto or "Sin descripción"
            self.paso = "foto"
            return Respuesta("¿Quieres adjuntar una foto?",
                             [("Sí, la envío ahora", "foto|si"), ("No, continuar", "foto|no")])
        if self.paso == "foto_espera":
            return Respuesta("Envía una foto (o escribe /cancelar).")
        return None

    def foto_recibida(self, nombre: str, contenido: bytes) -> Respuesta | None:
        if self.paso != "foto_espera":
            return None
        self.foto = (nombre, contenido)
        self.paso = "confirmar"
        return self.resumen()


# ------------------------------------------------------------------------------
# Texto libre con formato fijo
# ------------------------------------------------------------------------------
_ETIQUETAS = {
    "COLABORADOR": "colaborador", "TECNICO": "colaborador", "NOMBRE": "colaborador",
    "AREA": "area", "DEPARTAMENTO": "area",
    "MOTIVO": "motivo", "TIPO": "motivo",
    "FECHA": "fecha",
    "DESCRIPCION": "descripcion", "DETALLE": "descripcion", "COMENTARIO": "descripcion",
}


def parse_mensaje_falta(texto: str | None) -> dict | None:
    """
    Campos del reporte, o None si el mensaje no es un reporte (la primera línea
    debe ser la palabra FALTA, para no confundirlo con la charla del grupo).
    """
    lineas = [linea.strip() for linea in (texto or "").strip().splitlines() if linea.strip()]
    if not lineas or normalizar_nombre_cruce(lineas[0]) != "FALTA":
        return None
    campos = dict.fromkeys(("colaborador", "area", "motivo", "fecha", "descripcion"), "")
    for linea in lineas[1:]:
        etiqueta, separador, valor = linea.partition(":")
        if separador and (clave := _ETIQUETAS.get(normalizar_nombre_cruce(etiqueta))):
            campos[clave] = valor.strip()
    return campos


def falta_desde_texto(campos: dict, catalogo: Catalogo, hoy: date) -> Falta | str:
    """La falta lista para guardar, o el mensaje de error para el grupo (no se guarda nada)."""
    faltantes = [c for c in ("colaborador", "area", "motivo") if not campos.get(c)]
    if faltantes:
        return (f"⚠️ Faltan estos campos en el reporte: {', '.join(faltantes)}. "
                "No se guardó nada, corrígelo y vuelve a mandarlo completo.")
    area = resolver_area(campos["area"])
    if area is None:
        return f"⚠️ No reconozco el área \"{campos['area']}\". Usa \"Operaciones\" o \"SAC\". No se guardó nada."
    encontrado = resolver_colaborador(campos["colaborador"], area, catalogo)
    if encontrado is None:
        listado = "Operaciones" if area == OPERACIONES else "personal administrativo"
        return (f"⚠️ No encontré a \"{campos['colaborador']}\" en el listado de {listado}. "
                "Revisa el nombre y vuelve a mandarlo. No se guardó nada.")
    fecha = parse_fecha_libre(campos["fecha"]) if campos["fecha"] else None
    return Falta(colaborador=_colaborador(encontrado[0]), area=encontrado[1], tipo_falta=_tipo_falta(campos["motivo"]),
                 fecha=fecha if fecha and fecha <= hoy else hoy,
                 comentario=campos["descripcion"].strip() or "Sin descripción")
