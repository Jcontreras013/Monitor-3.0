"""Formas de entrada y salida de la API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.security import LARGO_MINIMO_CLAVE


class LoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=60)
    clave: str = Field(min_length=1, max_length=200)


class CambioClaveIn(BaseModel):
    clave_actual: str = Field(min_length=1, max_length=200)
    clave_nueva: str = Field(min_length=LARGO_MINIMO_CLAVE, max_length=200)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usuario: str
    nombre: str
    rol: str


class Conteo(BaseModel):
    nombre: str
    cantidad: int


class Kpis(BaseModel):
    pendientes_asignadas: int
    cerradas_hoy: int
    tecnicos_en_ruta: int
    offline: int
    total_pendientes: int


class CubetaRetraso(BaseModel):
    cubeta: str
    cantidad: int
    porcentaje: float


class GrupoTablero(BaseModel):
    subtipos: list[Conteo]
    total: int
    exceden_2h: int | None = None


class Tablero(BaseModel):
    sop: GrupoTablero
    instalaciones: GrupoTablero
    plex: GrupoTablero


class Consolidado(BaseModel):
    segmento: str
    total: int
    cerradas: int
    porcentaje: float
    mora_total: int
    mora_cerradas: int
    mora_porcentaje: float
    hoy_total: int
    hoy_cerradas: int
    hoy_porcentaje: float


class ResumenMonitor(BaseModel):
    generado_en: datetime
    dia: date
    mostrando: int
    total_base: int
    kpis: Kpis
    retraso: list[CubetaRetraso]
    tablero: Tablero
    consolidado: list[Consolidado]
    estados_no_reconocidos: list[Conteo]


class OrdenOut(BaseModel):
    num: str
    actividad: str
    estado: str
    tecnico: str | None
    cliente: str | None
    nombre: str | None
    colonia: str | None
    sector: str | None
    comentario: str | None
    comentario_cierre: str | None
    razon_cierre: str | None
    olt: str | None
    pon: str | None
    mx: str | None
    gps: str | None
    hora_ini: datetime | None
    hora_liq: datetime | None
    fecha_ape: datetime | None
    dias_retraso: int
    tiempo_real_min: int | None
    es_offline: bool
    alerta_tiempo: bool
    motivo: str
    segmento: str
    grupo_tablero: str
    subtipo_tablero: str


class OpcionesFiltro(BaseModel):
    actividades: list[str]
    estados: list[str]
    motivos: list[str]
    tecnicos: list[str]


class EstadoRobotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ultimo_ciclo: datetime | None
    sync_ok: bool
    motivo: str
    ultima_sync_ok: datetime | None
    ordenes_recibidas: int
    duracion_seg: float | None
    minutos_desde_ultimo_ciclo: float | None = None
    atrasado: bool = False
