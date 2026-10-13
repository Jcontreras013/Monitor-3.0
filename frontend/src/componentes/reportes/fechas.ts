export const hoyHN = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Tegucigalpa' })

export function haceDias(dias: number): string {
  const d = new Date(`${hoyHN()}T12:00:00`)
  d.setDate(d.getDate() - dias)
  return d.toISOString().slice(0, 10)
}
