// Las horas de Cepheus llegan como hora local de Honduras sin zona
// ("2026-10-12T09:30:00"): se formatean como texto, sin pasar por Date, para
// que la zona horaria del navegador no las corra.
export function horaLocal(iso: string | null): string {
  if (!iso) return '—'
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)} ${iso.slice(11, 16)}`
}

// Las marcas del sistema (robot) sí traen zona: se muestran en hora de Honduras.
export function haceCuanto(iso: string | null): string {
  if (!iso) return 'nunca'
  const minutos = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutos < 1) return 'hace un momento'
  if (minutos < 60) return `hace ${minutos} min`
  const horas = Math.floor(minutos / 60)
  if (horas < 24) return `hace ${horas} h ${minutos % 60} min`
  return new Date(iso).toLocaleString('es-HN', { timeZone: 'America/Tegucigalpa' })
}

export function duracion(minutos: number | null): string {
  if (minutos === null || minutos === undefined) return '—'
  return `${Math.floor(minutos / 60)}h ${minutos % 60}m`
}

export const pct = (valor: number) => `${Math.round(valor)}%`
