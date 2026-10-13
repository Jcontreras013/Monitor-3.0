"""
Tablas de la base de datos.

Reemplazan a las pestañas de Google Sheets (Sheet1, Usuarios_Claves,
Estado_Robot, FTTX) y a sus espejos CSV en GCS.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column

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
    # Acceso al repositorio de documentos laborales de Expedientes (por persona,
    # no por rol: antes era la lista fija oscar / afajardo / jaison).
    acceso_repositorio: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
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


class Personal(Base):
    """
    Catálogo de colaboradores (antes personal_tecnico.txt y personal_sac.txt).
    Los técnicos van en el área OPERACIONES; los administrativos, en su
    departamento (SAC, VENTAS EN CAMPO, BODEGA...).
    """

    __tablename__ = "personal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    area: Mapped[str] = mapped_column(String(80))
    cargo: Mapped[str] = mapped_column(String(120), default="")
    # TÉCNICO PRINCIPAL | AYUDANTE | SUPERVISOR | OTRAS ÁREAS / SOPORTE
    clasificacion: Mapped[str] = mapped_column(String(60), default="")
    estatus: Mapped[str] = mapped_column(String(30), default="ACTIVO")
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    __table_args__ = (UniqueConstraint("nombre", "area", name="uq_personal_nombre_area"),)


class Expediente(Base):
    """Una falta, incidencia o registro de personal (antes la pestaña Expedientes)."""

    __tablename__ = "expedientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    colaborador: Mapped[str] = mapped_column(String(200))
    area: Mapped[str] = mapped_column(String(80))
    tipo_falta: Mapped[str] = mapped_column(String(200))
    fecha_incidencia: Mapped[date] = mapped_column(Date)
    comentario: Mapped[str] = mapped_column(Text, default="")
    supervisor: Mapped[str] = mapped_column(String(120), default="")
    # app | telegram | importado
    origen: Mapped[str] = mapped_column(String(20), default="app")
    # Enlaces de evidencias del sistema anterior (Catbox / Freeimage).
    urls_externas: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'::text[]"))

    __table_args__ = (
        Index("ix_expedientes_fecha", "fecha_incidencia"),
        Index("ix_expedientes_colaborador", "colaborador"),
        Index("ix_expedientes_area", "area"),
    )


class Archivo(Base):
    """
    Evidencias y documentos. Se guardan en la base y solo se entregan a un
    usuario con sesión y permiso sobre el módulo (antes iban a Catbox, con
    enlaces públicos que cualquiera podía abrir).
    """

    __tablename__ = "archivos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # expediente | repositorio | calidad | ...
    ambito: Mapped[str] = mapped_column(String(30))
    # A qué pertenece dentro del ámbito: id del expediente, nombre del colaborador...
    referencia: Mapped[str] = mapped_column(String(200))
    nombre: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(120))
    tamano: Mapped[int] = mapped_column(Integer)
    descripcion: Mapped[str] = mapped_column(Text, default="")
    subido_por: Mapped[str] = mapped_column(String(120), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    contenido: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))

    __table_args__ = (Index("ix_archivos_ambito_referencia", "ambito", "referencia"),)


class GestionCalidad(Base):
    """
    Llamada de control de calidad post-servicio (antes la pestaña Calidad):
    encuesta completa si el cliente contestó, o constancia de la gestión.
    """

    __tablename__ = "calidad_gestiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha_gestion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    num_orden: Mapped[str] = mapped_column(String(40))
    cliente: Mapped[str] = mapped_column(String(40), default="")
    nombre_cliente: Mapped[str] = mapped_column(Text, default="")
    tecnico: Mapped[str] = mapped_column(String(160), default="")
    actividad: Mapped[str] = mapped_column(String(60), default="")
    fecha_visita: Mapped[str] = mapped_column(String(20), default="")
    contesto: Mapped[bool] = mapped_column(Boolean, default=False)
    # Calificaciones 1-5 (NULL si no contestó; P4 también NULL si "No aplica").
    p1: Mapped[int | None] = mapped_column(Integer)
    p2: Mapped[int | None] = mapped_column(Integer)
    p3: Mapped[int | None] = mapped_column(Integer)
    p4: Mapped[int | None] = mapped_column(Integer)
    p5: Mapped[int | None] = mapped_column(Integer)
    p6: Mapped[int | None] = mapped_column(Integer)
    p7: Mapped[int | None] = mapped_column(Integer)
    mejoras: Mapped[str] = mapped_column(Text, default="")
    aceptacion_digital: Mapped[str] = mapped_column(String(200), default="")
    hora_cierre_servicio: Mapped[str] = mapped_column(String(20), default="")
    aprobacion_interna: Mapped[str] = mapped_column(String(80), default="")
    metodo_auditoria: Mapped[str] = mapped_column(String(160), default="")
    resultado_gestion: Mapped[str] = mapped_column(String(80), default="")
    ticket_seguimiento: Mapped[str] = mapped_column(String(80), default="")
    responsable_seguimiento: Mapped[str] = mapped_column(String(120), default="")
    fecha_limite_seguimiento: Mapped[date | None] = mapped_column(Date)
    # Ninguna | Seguimiento | Promesa
    tipo_nota: Mapped[str] = mapped_column(String(20), default="Ninguna")
    detalle_nota: Mapped[str] = mapped_column(Text, default="")
    registrado_por: Mapped[str] = mapped_column(String(120), default="")

    __table_args__ = (
        Index("ix_calidad_gestiones_orden", "num_orden"),
        Index("ix_calidad_gestiones_fecha", "fecha_gestion"),
    )


class AuditoriaCampo(Base):
    """
    Auditoría presencial (antes las pestañas Operaciones, Instalaciones y
    Auditoria_Fibra). Las fotos van en `archivos` (ámbito calidad).
    """

    __tablename__ = "auditorias_campo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # operaciones | instalaciones | fibra
    tipo: Mapped[str] = mapped_column(String(20))
    fecha_auditoria: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    num_orden: Mapped[str] = mapped_column(String(40))
    cliente: Mapped[str] = mapped_column(String(40), default="")
    nombre_cliente: Mapped[str] = mapped_column(Text, default="")
    tecnico: Mapped[str] = mapped_column(String(160), default="")
    actividad: Mapped[str] = mapped_column(String(60), default="")
    vineta: Mapped[str] = mapped_column(String(60), default="")
    mufa: Mapped[str] = mapped_column(String(60), default="")
    metraje: Mapped[str] = mapped_column(String(40), default="")
    estetica: Mapped[str] = mapped_column(String(30), default="")
    ruta_acometida: Mapped[str] = mapped_column(Text, default="")
    tiempo_invertido: Mapped[str] = mapped_column(String(40), default="")
    tipo_fo: Mapped[str] = mapped_column(String(80), default="")
    comentario: Mapped[str] = mapped_column(Text, default="")
    # Correcto | Con observaciones | Deficiente / Mal trabajo (solo fibra)
    evaluacion: Mapped[str] = mapped_column(String(40), default="")
    supervisor: Mapped[str] = mapped_column(String(120), default="")
    # Una auditoría de fibra deficiente se puede convertir en falta en Expedientes.
    expediente_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("expedientes.id", ondelete="SET NULL"))
    convertido_a_falta: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    urls_externas: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'::text[]"))

    __table_args__ = (
        Index("ix_auditorias_campo_tipo_fecha", "tipo", "fecha_auditoria"),
        Index("ix_auditorias_campo_tecnico", "tecnico"),
    )
