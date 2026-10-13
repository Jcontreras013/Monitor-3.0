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
  /** Solo en Reprogramadas: días que faltan para la cita. */
  dias_para_cita?: number
}

export type OrdenVip = Orden & { nombre_vip: string; clase_vip: string }

export type ClienteVip = { cliente: string; nombre: string; clase: string }
export type VistaPreviaVip = { clientes: ClienteVip[]; nuevos: number; salen: number }

export type EstadoCorreo = {
  servidor: string
  puerto: number
  modo: string
  remitente: string
  contrasena_configurada: boolean
  destinatarios: string[]
  destinatarios_vip: string[]
  falta: string | null
  alertas: { alerta: string; resultado: string; detalle: string; actualizado_en: string }[]
}

export type Reprogramadas = {
  reprogramadas: (Orden & { dias_para_cita: number })[]
  no_instalados: Orden[]
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
  auditorias_fibra: AuditoriaCampo[]
}

export type CatalogoExpedientes = {
  personal: Record<string, string[]>
  motivos_operaciones: string[]
  motivos_administrativo: string[]
}

export type ConsolidadoMes = { mes: string; total: number; filas: { colaborador: string; faltas: number }[] }

export type CarpetaRepositorio = { colaborador: string; archivos: ArchivoMeta[] }

// ---------------------------------------------------------------------------
// Control de Calidad
// ---------------------------------------------------------------------------
export type OrdenCalidad = {
  num: string
  actividad: string
  estado: string
  cliente: string | null
  nombre: string | null
  colonia: string | null
  tecnico: string | null
  comentario: string | null
  comentario_cierre: string | null
  olt: string | null
  hora_ini: string | null
  hora_liq: string | null
  tiempo_invertido_min: number | null
}

export type ConfigCalidad = {
  pestanas: string[]
  preguntas: { clave: string; texto: string; opcional: boolean }[]
  aprobaciones: string[]
  estados_sin_contestar: string[]
  resultados_gestion: string[]
  tipos_nota: string[]
  esteticas: string[]
  evaluaciones_fibra: string[]
  puede_borrar: boolean
}

export type GestionCalidad = {
  id: number
  fecha_gestion: string
  num_orden: string
  cliente: string
  nombre_cliente: string
  tecnico: string
  actividad: string
  fecha_visita: string
  contesto: boolean
  p1: number | null
  p2: number | null
  p3: number | null
  p4: number | null
  p5: number | null
  p6: number | null
  p7: number | null
  mejoras: string
  aceptacion_digital: string
  hora_cierre_servicio: string
  aprobacion_interna: string
  metodo_auditoria: string
  resultado_gestion: string
  ticket_seguimiento: string
  responsable_seguimiento: string
  fecha_limite_seguimiento: string | null
  tipo_nota: string
  detalle_nota: string
  registrado_por: string
  resultado: string
  promedio: number | null
}

export type AuditoriaCampo = {
  id: number
  tipo: 'operaciones' | 'instalaciones' | 'fibra'
  fecha_auditoria: string
  num_orden: string
  cliente: string
  nombre_cliente: string
  tecnico: string
  actividad: string
  vineta: string
  mufa: string
  metraje: string
  estetica: string
  ruta_acometida: string
  tiempo_invertido: string
  tipo_fo: string
  comentario: string
  evaluacion: string
  supervisor: string
  convertido_a_falta: boolean
  expediente_id: number | null
  urls_externas: string[]
  archivos: ArchivoMeta[]
}

export type CierresInsfibra = {
  total: number
  llamadas: number
  pendientes: number
  filas: { num: string; cliente: string | null; nombre: string | null; tecnico: string | null; fecha_cierre: string | null; llamada: boolean }[]
  por_tecnico: { tecnico: string; cierres: number; llamadas: number; pendientes: number }[]
}

export type HistoricoCalidad = {
  gestiones: GestionCalidad[]
  auditorias: AuditoriaCampo[]
  csat: { csat: number | null; validas: number; top: number } | null
  diagnostico: { pregunta: string; promedio: number; respuestas: number }[]
  por_tecnico: { tecnico: string; total: number; aprobado: number; con_obs: number; rechazado: number; sin_gestion: number }[]
  resumen: ({ nombre: string; cantidad: number } | { titulo: string; columna: string; filas: Conteo[] })[]
}

export type CierreDiario = {
  fecha: string
  total_cerradas: number
  avance: Consolidado[]
  produccion: { sop: Conteo[]; instalaciones: Conteo[]; plex: Conteo[]; otros: Conteo[] }
  eficiencia: { tecnico: string; ins: number; sop: number; otr: number; puntos_base: number; bono_mixto: number; logro_final: number }[]
  primera_orden: { tecnico: string; hora_ini: string; colonia: string | null; num: string; actividad: string }[]
  cerradas: Orden[]
}

export type Arranque = { desde: string; hasta: string; filas: { tecnico: string; dias: number; hora_promedio: string }[] }

export type PendientesDispatch = {
  resumen: { categoria: string; asignadas: number; sin_asignar: number; total: number }[]
  totales: { asignadas: number; sin_asignar: number; total: number }
  cubetas: Conteo[]
  instalaciones: Conteo[]
  soporte: Conteo[]
  resto: Conteo[]
  sin_asignar: Orden[]
}
