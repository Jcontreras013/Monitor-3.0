import type { Filtros } from './tipos'

export class ErrorApi extends Error {
  status: number

  constructor(status: number, mensaje: string) {
    super(mensaje)
    this.status = status
  }
}

function mensajeDeError(cuerpo: unknown, status: number): string {
  const detalle = (cuerpo as { detail?: unknown } | null)?.detail
  if (typeof detalle === 'string') return detalle
  if (Array.isArray(detalle) && detalle.length) {
    // Errores de validación de FastAPI (422)
    return detalle.map((d: { msg?: string }) => d.msg ?? '').join('. ')
  }
  return `Error ${status}`
}

export async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const respuesta = await fetch(`/api${ruta}`, {
    credentials: 'same-origin',
    ...opciones,
    headers: { 'Content-Type': 'application/json', ...opciones.headers },
  })
  if (respuesta.status === 204) return undefined as T
  const cuerpo = await respuesta.json().catch(() => null)
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, mensajeDeError(cuerpo, respuesta.status))
  return cuerpo as T
}

export const enviar = <T>(ruta: string, datos?: unknown) =>
  api<T>(ruta, { method: 'POST', body: datos === undefined ? undefined : JSON.stringify(datos) })

/** Filtros -> ?actividad=A&actividad=B&solo_criticas=true... */
export function parametros(filtros: Filtros, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams(extra)
  filtros.actividad.forEach((v) => p.append('actividad', v))
  filtros.estado.forEach((v) => p.append('estado', v))
  filtros.motivo.forEach((v) => p.append('motivo', v))
  if (filtros.tecnico) p.set('tecnico', filtros.tecnico)
  if (filtros.rapido === 'criticas') p.set('solo_criticas', 'true')
  if (filtros.rapido === 'no_asignadas') p.set('no_asignadas', 'true')
  const texto = p.toString()
  return texto ? `?${texto}` : ''
}
