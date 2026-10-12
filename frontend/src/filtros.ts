import type { Filtros } from './tipos'

/** Descripción de los filtros activos, porque algunos ocultan categorías completas. */
export function filtrosActivos(f: Filtros): string[] {
  const lista: string[] = []
  if (f.solo_criticas) lista.push('Solo críticas (oculta todas las PLEX, PEXTERNO, SPLITTEROPT e instalaciones)')
  if (f.no_asignadas) lista.push('No asignadas (oculta las órdenes que ya tienen técnico)')
  if (f.actividad.length) lista.push(`Actividad: ${f.actividad.join(', ')}`)
  if (f.estado.length) lista.push(`Estado: ${f.estado.join(', ')}`)
  if (f.motivo.length) lista.push(`Motivo: ${f.motivo.join(', ')}`)
  if (f.tecnico) lista.push(`Técnico: ${f.tecnico}`)
  return lista
}
