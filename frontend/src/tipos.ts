// Formas que devuelve la API (backend/app/schemas.py).

export type Usuario = {
  usuario: string
  nombre: string
  rol: string
  modulos: string[]
  acceso_repositorio: boolean
}

export type Conteo = { nombre: string; cantidad: number }

export type GrupoTablero = { subtipos: Conteo[]; total: number; exceden_2h?: number | null }

export type Consolidado = {
  segmento: string
  total: number
  cerradas: number
  porcentaje: number
  mora_total: number
  mora_cerradas: number
  mora_porcentaje: number
  hoy_total: number
  hoy_cerradas: number
  hoy_porcentaje: number
}

export type ResumenMonitor = {
  generado_en: string
  dia: string
  mostrando: number
  total_base: number
  kpis: {
    pendientes_asignadas: number
    cerradas_hoy: number
    tecnicos_en_ruta: number
    offline: number
    total_pendientes: number
  }
  rapidos: Record<Rapido, number>
  retraso: { cubeta: string; cantidad: number; porcentaje: number }[]
  tablero: { sop: GrupoTablero; instalaciones: GrupoTablero; plex: GrupoTablero }
  consolidado: Consolidado[]
  estados_no_reconocidos: Conteo[]
}

export type Orden = {
  num: string
  actividad: string
  estado: string
  tecnico: string | null
  cliente: string | null
  nombre: string | null
  colonia: string | null
  sector: string | null
  comentario: string | null
  comentario_cierre: string | null
  razon_cierre: string | null
  olt: string | null
  pon: string | null
  mx: string | null
  gps: string | null
  hora_ini: string | null
  hora_liq: string | null
  fecha_ape: string | null
  dias_retraso: number
  tiempo_real_min: number | null
  es_offline: boolean
  alerta_tiempo: boolean
  motivo: string
  segmento: string
  grupo_tablero: string
  subtipo_tablero: string
}

export type OpcionesFiltro = {
  actividades: string[]
  estados: string[]
  motivos: string[]
  tecnicos: string[]
}

export type EstadoRobot = {
  ultimo_ciclo: string | null
  sync_ok: boolean
  motivo: string
  ultima_sync_ok: string | null
  ordenes_recibidas: number
  duracion_seg: number | null
  minutos_desde_ultimo_ciclo: number | null
  atrasado: boolean
}

// Filtro rápido (exclusivo): todas las pendientes, solo críticas o solo sin técnico.
export type Rapido = 'todas' | 'criticas' | 'no_asignadas'

export type Filtros = {
  rapido: Rapido
  tecnico: string
  actividad: string[]
  estado: string[]
  motivo: string[]
}

export const FILTROS_VACIOS: Filtros = {
  rapido: 'todas',
  tecnico: '',
  actividad: [],
  estado: [],
  motivo: [],
}

// ---------------------------------------------------------------------------
// Expedientes
// ---------------------------------------------------------------------------
export type ArchivoMeta = {
  id: string
  nombre: string
  mime: string
  tamano: number
  descripcion: string
  subido_por: string
  creado_en: string
}

export type RegistroExpediente = {
  id: number
  fecha_registro: string
  fecha_incidencia: string
  colaborador: string
  area: string
  tipo_falta: string
  comentario: string
  supervisor: string
  origen: string
  clasificacion: 'GRAVE' | 'LEVE' | 'OTRO'
  archivos: ArchivoMeta[]
  urls_externas: string[]
}

export type ListadoExpedientes = {
  registros: RegistroExpediente[]
  panel: {
    total: number
    personas: number
    rubro_dominante: string | null
    clasificacion: Record<'GRAVE' | 'LEVE' | 'OTRO', number>
    reincidentes: { colaborador: string; motivo: string; veces: number }[]
    por_dia: Conteo[]
    por_rubro: Conteo[]
    por_motivo: Conteo[]
  }
  mes: string
  resumen_mes: { colaborador: string; tardes: number; otras: number; total: number }[]
  colaboradores: string[]
  areas: string[]
}

export type CatalogoExpedientes = {
  personal: Record<string, string[]>
  motivos_operaciones: string[]
  motivos_administrativo: string[]
}

export type ConsolidadoMes = { mes: string; total: number; filas: { colaborador: string; faltas: number }[] }

export type CarpetaRepositorio = { colaborador: string; archivos: ArchivoMeta[] }
