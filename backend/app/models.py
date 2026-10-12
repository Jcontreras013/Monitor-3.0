"""
Tablas de la base de datos.

Reemplazan a las pestañas de Google Sheets (Sheet1, Usuarios_Claves,
Estado_Robot, FTTX) y a sus espejos CSV en GCS.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Orden(Base):
    """
    Una orden de Cepheus. La llave es el número de orden: el robot hace
    upsert sobre ella en vez de reescribir toda la tabla en cada ciclo.

    Las horas de Cepheus (hora_ini, hora_liq, fecha_ape) son hora local de
    Honduras SIN zona horaria; las marcas del sistema (*_en) sí llevan zona.
    """

    __tablename__ = "ordenes"

    num: Mapped[str] = mapped_column(String(40), primary_key=True)
    actividad: Mapped[str] = mapped_column(String(60), default="")
    estado: Mapped[str] = mapped_column(String(60), default="")
    tecnico: Mapped[str | None] = mapped_column(String(160))
    cliente: Mapped[str | None] = mapped_column(String(40))
    nombre: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(Text)
    colonia: Mapped[str | None] = mapped_column(Text)
    comentario: Mapped[str | None] = mapped_column(Text)
    comentario_cierre: Mapped[str | None] = mapped_column(Text)
    razon_cierre: Mapped[str | None] = mapped_column(Text)
    olt: Mapped[str | None] = mapped_column(String(120))
    pon: Mapped[str | None] = mapped_column(String(120))
    mx: Mapped[str | None] = mapped_column(String(60))
    gps: Mapped[str | None] = mapped_column(Text)
    empresa: Mapped[str | None] = mapped_column(String(120))

    hora_ini: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    hora_liq: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    fecha_ape: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    # Derivados, calculados una sola vez al guardar (ver dominio/normalizacion.py).
    es_viva: Mapped[bool] = mapped_column(Boolean, default=False)
    es_offline: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo: Mapped[str] = mapped_column(String(60), default="")
    segmento: Mapped[str] = mapped_column(String(20), default="RESIDENCIAL")
    grupo_tablero: Mapped[str] = mapped_column(String(10), default="OTROS")
    subtipo_tablero: Mapped[str] = mapped_column(String(80), default="")

    # False cuando una orden viva dejó de venir en la respuesta de Cepheus
    # (anulada/reasignada fuera de la cuenta). No se borra: solo deja de
    # contar como pendiente.
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    # Todas las demás columnas que mande Cepheus. Así una columna nueva nunca
    # "desaparece" como pasaba en Sheet1 cuando un ciclo no la traía.
    datos: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))

    # Resumen del contenido normalizado: el robot solo reescribe la fila si cambió.
    huella: Mapped[str] = mapped_column(String(32), default="")
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_ordenes_vivas", "es_viva", postgresql_where=text("es_viva")),
        Index("ix_ordenes_hora_liq", "hora_liq"),
        Index("ix_ordenes_fecha_ape", "fecha_ape"),
        Index("ix_ordenes_tecnico", "tecnico"),
        Index("ix_ordenes_actividad", "actividad"),
    )


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(160), default="")
    # admin | jefe | monitoreo | llamados | ...
    rol: Mapped[str] = mapped_column(String(30))
    clave_hash: Mapped[str] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    clave_actualizada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EstadoRobot(Base):
    """Una sola fila (id=1) con el resultado del último ciclo del robot."""

    __tablename__ = "estado_robot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ultimo_ciclo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo: Mapped[str] = mapped_column(Text, default="")
    ultima_sync_ok: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ordenes_recibidas: Mapped[int] = mapped_column(Integer, default=0)
    duracion_seg: Mapped[float | None] = mapped_column()


class DispositivoFttx(Base):
    """Catálogo técnico -> vehículo (MX), antes la pestaña FTTX de Sheets."""

    __tablename__ = "dispositivos_fttx"

    tecnico_clave: Mapped[str] = mapped_column(String(160), primary_key=True)
    tecnico: Mapped[str] = mapped_column(String(160))
    mx: Mapped[str | None] = mapped_column(String(60))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
