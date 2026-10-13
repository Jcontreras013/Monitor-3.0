import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api, consulta } from '../../api'
import type { Arranque as Datos } from '../../tipos'
import { Aviso, Descarga } from '../ui'
import { haceDias, hoyHN } from './fechas'

export default function Arranque() {
  const [desde, setDesde] = useState(haceDias(6))
  const [hasta, setHasta] = useState(hoyHN())
  const q = consulta({ desde, hasta })
  const datos = useQuery({
    queryKey: ['reportes', 'arranque', desde, hasta],
    queryFn: () => api<Datos>(`/reportes/arranque${q}`),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-3">
      <div className="tarjeta flex flex-wrap items-end gap-2 p-3">
        <label className="space-y-1">
          <span className="etiqueta">Desde</span>
          <input type="date" className="campo py-1.5" value={desde} max={hasta} onChange={(e) => e.target.value && setDesde(e.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="etiqueta">Hasta</span>
          <input type="date" className="campo py-1.5" value={hasta} min={desde} max={hoyHN()} onChange={(e) => e.target.value && setHasta(e.target.value)} />
        </label>
        <div className="ml-auto"><Descarga href={`/api/reportes/arranque.pdf${q}`}>PDF</Descarga></div>
      </div>
      <p className="text-sm text-slate-500">Hora promedio en que cada técnico inicia su primera orden de cada día del rango.</p>
      {datos.error && <Aviso tipo="error">{datos.error.message}</Aviso>}
      <div className="tarjeta overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr><th className="px-3 py-2">Técnico</th><th className="px-3 py-2 text-center">Días evaluados</th><th className="px-3 py-2 text-center">Hora promedio de arranque</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(datos.data?.filas ?? []).map((f) => (
              <tr key={f.tecnico}><td className="px-3 py-1.5">{f.tecnico}</td><td className="px-3 text-center">{f.dias}</td><td className="px-3 text-center font-mono">{f.hora_promedio}</td></tr>
            ))}
            {datos.data && !datos.data.filas.length && <tr><td colSpan={3} className="py-8 text-center text-slate-400">No hay órdenes iniciadas en este rango.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
