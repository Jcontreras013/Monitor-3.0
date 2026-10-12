import { pct } from '../formato'
import type { Conteo, Consolidado, ResumenMonitor } from '../tipos'

const COLOR_CUBETA: Record<string, string> = {
  '>= 7 Dia': 'bg-red-500 text-white',
  '= 4 a 6 Dias': 'bg-amber-500 text-white',
  '= 1 a 3 Dias': 'bg-yellow-300 text-slate-900',
  '= 0 Dia': 'bg-emerald-500 text-white',
}

function TarjetaKpi({ titulo, valor, color }: { titulo: string; valor: number; color: string }) {
  return (
    <div className={`tarjeta border-l-4 p-4 ${color}`}>
      <p className="etiqueta">{titulo}</p>
      <p className="mt-1 text-3xl font-bold text-slate-900 tabular-nums">{valor.toLocaleString('es-HN')}</p>
    </div>
  )
}

export function Kpis({ kpis }: { kpis: ResumenMonitor['kpis'] }) {
  return (
    <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      <TarjetaKpi titulo="Pendientes asignadas" valor={kpis.pendientes_asignadas} color="border-l-marca" />
      <TarjetaKpi titulo="Cerradas hoy" valor={kpis.cerradas_hoy} color="border-l-emerald-500" />
      <TarjetaKpi titulo="Técnicos en ruta" valor={kpis.tecnicos_en_ruta} color="border-l-amber-500" />
      <TarjetaKpi titulo="Caídas (offline)" valor={kpis.offline} color="border-l-red-500" />
      <TarjetaKpi titulo="Total pendientes" valor={kpis.total_pendientes} color="border-l-slate-400" />
    </section>
  )
}

function TablaConteo({ titulo, filas, total, pie }: { titulo: string; filas: Conteo[]; total: number; pie?: string }) {
  return (
    <div className="tarjeta flex flex-col p-4">
      <p className="etiqueta mb-2">{titulo}</p>
      <ul className="flex-1 divide-y divide-slate-100 text-sm">
        {filas.length === 0 && <li className="py-1.5 text-slate-400">Sin órdenes</li>}
        {filas.map((f) => (
          <li key={f.nombre} className="flex justify-between gap-2 py-1.5">
            <span className="truncate">{f.nombre}</span>
            <span className="font-semibold tabular-nums">{f.cantidad}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 border-t border-slate-200 pt-2 text-sm font-semibold">Total: {total}</p>
      {pie && <p className="text-xs text-amber-700">{pie}</p>}
    </div>
  )
}

export function TableroCarga({ resumen }: { resumen: ResumenMonitor }) {
  const { retraso, tablero } = resumen
  const totalRetraso = retraso.reduce((s, r) => s + r.cantidad, 0)
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div className="tarjeta p-4">
        <p className="etiqueta mb-2">Días de retraso (todas las pendientes)</p>
        <ul className="space-y-1.5 text-sm">
          {retraso.map((r) => (
            <li key={r.cubeta} className="flex items-center gap-2">
              <span className={`w-28 rounded px-2 py-0.5 text-xs font-semibold ${COLOR_CUBETA[r.cubeta]}`}>{r.cubeta}</span>
              <span className="flex-1 overflow-hidden rounded bg-slate-100">
                <span className="block h-2 bg-slate-400" style={{ width: `${r.porcentaje}%` }} />
              </span>
              <span className="w-10 text-right font-semibold tabular-nums">{r.cantidad}</span>
              <span className="w-10 text-right text-xs text-slate-500">{pct(r.porcentaje)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 border-t border-slate-200 pt-2 text-sm font-semibold">Total: {totalRetraso}</p>
      </div>
      <TablaConteo
        titulo="SOP / mantenimiento"
        filas={tablero.sop.subtipos}
        total={tablero.sop.total}
        pie={tablero.sop.exceden_2h ? `${tablero.sop.exceden_2h} exceden 2 h` : undefined}
      />
      <TablaConteo titulo="Instalaciones" filas={tablero.instalaciones.subtipos} total={tablero.instalaciones.total} />
      <TablaConteo titulo="PLEX (asignadas)" filas={tablero.plex.subtipos} total={tablero.plex.total} />
    </section>
  )
}

function Dona({ porcentaje, color }: { porcentaje: number; color: string }) {
  const radio = 42
  const circunferencia = 2 * Math.PI * radio
  return (
    <svg viewBox="0 0 100 100" className="size-28 -rotate-90">
      <circle cx="50" cy="50" r={radio} fill="none" stroke="#e2e8f0" strokeWidth="10" />
      <circle
        cx="50"
        cy="50"
        r={radio}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${(porcentaje / 100) * circunferencia} ${circunferencia}`}
      />
    </svg>
  )
}

const ESTILO_SEGMENTO: Record<string, { titulo: string; color: string }> = {
  RESIDENCIAL: { titulo: 'Residencial', color: '#ef4444' },
  PLEX: { titulo: 'PLEX', color: '#f59e0b' },
  GLOBAL: { titulo: 'Global', color: '#10b981' },
}

export function AvanceSegmentos({ consolidado }: { consolidado: Consolidado[] }) {
  return (
    <section className="grid gap-3 md:grid-cols-3">
      {consolidado.map((c) => {
        const estilo = ESTILO_SEGMENTO[c.segmento] ?? { titulo: c.segmento, color: '#64748b' }
        return (
          <div key={c.segmento} className="tarjeta flex items-center gap-4 p-4">
            <div className="relative">
              <Dona porcentaje={c.total ? c.porcentaje : 0} color={estilo.color} />
              <span className="absolute inset-0 grid place-items-center text-xl font-bold" style={{ color: estilo.color }}>
                {c.total ? pct(c.porcentaje) : 'N/A'}
              </span>
            </div>
            <div className="space-y-1.5">
              <p className="font-semibold text-slate-900">{estilo.titulo}</p>
              <p className="text-sm text-slate-500">
                {c.total ? `${c.cerradas} de ${c.total} cerradas` : 'Sin asignaciones'}
              </p>
              <p className="flex flex-wrap gap-1.5 text-xs font-semibold">
                <span className="rounded-full bg-red-50 px-2 py-0.5 text-red-700 ring-1 ring-red-200">
                  Mora {c.mora_cerradas}/{c.mora_total} ({pct(c.mora_porcentaje)})
                </span>
                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700 ring-1 ring-blue-200">
                  Hoy {c.hoy_cerradas}/{c.hoy_total} ({pct(c.hoy_porcentaje)})
                </span>
              </p>
            </div>
          </div>
        )
      })}
    </section>
  )
}
