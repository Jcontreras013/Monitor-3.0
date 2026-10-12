import type { Filtros } from './tipos'

export type EtiquetaFiltro = { clave: string; texto: string; quitar: (f: Filtros) => Filtros }

const sin = (lista: string[], valor: string) => lista.filter((v) => v !== valor)

/** Filtros activos (además del rápido) como etiquetas que se pueden quitar una por una. */
export function etiquetasActivas(f: Filtros): EtiquetaFiltro[] {
  return [
    ...(f.tecnico ? [{ clave: 'tecnico', texto: f.tecnico, quitar: (x: Filtros) => ({ ...x, tecnico: '' }) }] : []),
    ...f.actividad.map((v) => ({ clave: `a:${v}`, texto: v, quitar: (x: Filtros) => ({ ...x, actividad: sin(x.actividad, v) }) })),
    ...f.estado.map((v) => ({ clave: `e:${v}`, texto: v, quitar: (x: Filtros) => ({ ...x, estado: sin(x.estado, v) }) })),
    ...f.motivo.map((v) => ({ clave: `m:${v}`, texto: v, quitar: (x: Filtros) => ({ ...x, motivo: sin(x.motivo, v) }) })),
  ]
}
