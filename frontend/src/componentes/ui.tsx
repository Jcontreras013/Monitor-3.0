import type { ReactNode } from 'react'

export function Pestanas<T extends string>({
  opciones,
  valor,
  alCambiar,
}: {
  opciones: { valor: T; texto: ReactNode; cuenta?: number }[]
  valor: T
  alCambiar: (v: T) => void
}) {
  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-slate-200 text-sm font-medium">
      {opciones.map((o) => (
        <button
          key={o.valor}
          onClick={() => alCambiar(o.valor)}
          className={`-mb-px border-b-2 px-2 py-2 whitespace-nowrap sm:px-3 ${
            valor === o.valor ? 'border-marca text-marca' : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          {o.texto}
          {o.cuenta !== undefined && <span className="ml-1.5 text-xs text-slate-400 tabular-nums">{o.cuenta}</span>}
        </button>
      ))}
    </nav>
  )
}

export function Segmentado<T extends string>({
  opciones,
  valor,
  alCambiar,
  etiqueta,
}: {
  opciones: { valor: T; texto: string }[]
  valor: T
  alCambiar: (v: T) => void
  etiqueta: string
}) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1" role="group" aria-label={etiqueta}>
      {opciones.map((o) => (
        <button
          key={o.valor}
          aria-pressed={valor === o.valor}
          onClick={() => alCambiar(o.valor)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition ${
            valor === o.valor ? 'bg-tinta text-white' : 'text-slate-600 hover:bg-white'
          }`}
        >
          {o.texto}
        </button>
      ))}
    </div>
  )
}

export function Dato({ titulo, valor, color = 'border-l-marca' }: { titulo: string; valor: ReactNode; color?: string }) {
  return (
    <div className={`tarjeta border-l-4 px-2.5 py-2 sm:px-3 ${color}`}>
      <p className="text-[10px] leading-tight font-semibold tracking-wide text-slate-500 uppercase sm:text-[11px]">{titulo}</p>
      <p className="truncate text-xl font-bold text-slate-900 tabular-nums sm:text-2xl">{valor}</p>
    </div>
  )
}

/** Lista de barras horizontales simple (sin librería de gráficos). */
export function Barras({ titulo, filas, color = 'bg-marca' }: { titulo: string; filas: { nombre: string; cantidad: number }[]; color?: string }) {
  const maximo = Math.max(1, ...filas.map((f) => f.cantidad))
  return (
    <div className="tarjeta p-4">
      <p className="etiqueta mb-2">{titulo}</p>
      {filas.length === 0 && <p className="text-sm text-slate-400">Sin datos</p>}
      <ul className="space-y-1.5 text-sm">
        {filas.map((f) => (
          <li key={f.nombre} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3">
            <span className="truncate" title={f.nombre}>
              {f.nombre}
            </span>
            <span className="font-semibold tabular-nums">{f.cantidad}</span>
            <span className="col-span-2 h-1.5 overflow-hidden rounded bg-slate-100">
              <span className={`block h-full ${color}`} style={{ width: `${(f.cantidad / maximo) * 100}%` }} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Aviso({ tipo = 'info', children }: { tipo?: 'info' | 'error' | 'exito'; children: ReactNode }) {
  const estilos = {
    info: 'border-amber-300 bg-amber-50 text-amber-900',
    error: 'border-red-300 bg-red-50 text-red-800',
    exito: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  }
  return <p className={`rounded-lg border p-3 text-sm ${estilos[tipo]}`}>{children}</p>
}

/** Enlace de descarga con estilo de botón (la cookie de sesión viaja sola). */
export function Descarga({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a className="boton-secundario py-1.5" href={href} download>
      {children}
    </a>
  )
}
