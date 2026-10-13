import { useQuery } from '@tanstack/react-query'

import { api } from '../../api'
import type { PendientesDispatch as Datos } from '../../tipos'
import TablaOrdenes from '../TablaOrdenes'
import { Aviso, Barras, Dato, Descarga } from '../ui'

const COLOR_CUBETA = ['border-l-red-600', 'border-l-orange-500', 'border-l-yellow-400', 'border-l-emerald-600']

export default function PendientesDispatch() {
  const datos = useQuery({ queryKey: ['monitor', 'reportes', 'pendientes'], queryFn: () => api<Datos>('/reportes/pendientes') })
  const d = datos.data
  if (datos.error) return <Aviso tipo="error">{datos.error.message}</Aviso>
  if (!d) return <div className="tarjeta h-40 animate-pulse" />

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm text-slate-500">Carga para el siguiente turno, para enviar a Dispatch.</p>
        <div className="ml-auto flex gap-2">
          <Descarga href="/api/reportes/pendientes.xlsx">Excel</Descarga>
          <Descarga href="/api/reportes/pendientes.pdf">PDF</Descarga>
        </div>
      </div>

      <section className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {d.cubetas.map((c, i) => <Dato key={c.nombre} titulo={c.nombre} valor={c.cantidad} color={COLOR_CUBETA[i]} />)}
      </section>

      <div className="tarjeta overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr><th className="px-3 py-2 text-left">Clasificación</th><th className="px-3">Asignadas</th><th className="px-3">Sin asignar</th><th className="px-3">Total</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-center tabular-nums">
            {d.resumen.map((r) => (
              <tr key={r.categoria}><td className="px-3 py-1.5 text-left">{r.categoria}</td><td>{r.asignadas}</td><td className={r.sin_asignar ? 'font-semibold text-amber-700' : ''}>{r.sin_asignar}</td><td>{r.total}</td></tr>
            ))}
            <tr className="bg-slate-50 font-bold"><td className="px-3 py-1.5 text-left">TOTAL PENDIENTES</td><td>{d.totales.asignadas}</td><td>{d.totales.sin_asignar}</td><td>{d.totales.total}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Barras titulo="FTTH / Fibra" filas={d.instalaciones} color="bg-blue-500" />
        <Barras titulo="Soporte" filas={d.soporte} color="bg-red-500" />
        <Barras titulo="Resto de actividades" filas={d.resto} color="bg-slate-400" />
      </div>

      <h2 className="font-semibold text-slate-900">Prioritario: órdenes sin asignar ({d.sin_asignar.length})</h2>
      <TablaOrdenes vista="pendientes" ordenes={d.sin_asignar} cargando={false} vacio="Todas las órdenes están asignadas a técnicos." />
    </div>
  )
}
