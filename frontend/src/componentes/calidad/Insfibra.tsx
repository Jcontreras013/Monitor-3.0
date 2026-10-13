import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api, consulta } from '../../api'
import { horaLocal } from '../../formato'
import type { CierresInsfibra } from '../../tipos'
import { Aviso, Dato, Descarga } from '../ui'

const hoy = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Tegucigalpa' })
const haceDias = (dias: number) => {
  const d = new Date(`${hoy()}T12:00:00`)
  d.setDate(d.getDate() - dias)
  return d.toISOString().slice(0, 10)
}

export default function Insfibra({ alLlamar }: { alLlamar?: (num: string) => void }) {
  const [desde, setDesde] = useState(haceDias(7))
  const [hasta, setHasta] = useState(hoy())
  const [soloPendientes, setSoloPendientes] = useState(false)
  const filtros = consulta({ desde, hasta, solo_pendientes: soloPendientes ? 'true' : '' })
  const datos = useQuery({
    queryKey: ['calidad', 'insfibra', filtros],
    queryFn: () => api<CierresInsfibra>(`/calidad/insfibra${filtros}`),
    placeholderData: keepPreviousData,
  })
  const d = datos.data

  return (
    <div className="space-y-3">
      <div className="tarjeta flex flex-wrap items-end gap-2 p-3">
        <label className="space-y-1">
          <span className="etiqueta">Cierres desde</span>
          <input type="date" className="campo py-1.5" value={desde} max={hasta} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="etiqueta">Hasta</span>
          <input type="date" className="campo py-1.5" value={hasta} min={desde} onChange={(e) => setHasta(e.target.value)} />
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" className="accent-marca" checked={soloPendientes} onChange={(e) => setSoloPendientes(e.target.checked)} />
          Solo pendientes de llamar
        </label>
        <div className="ml-auto"><Descarga href={`/api/calidad/insfibra.pdf${filtros}`}>PDF</Descarga></div>
      </div>

      {datos.error && <Aviso tipo="error">{datos.error.message}</Aviso>}
      {d && (
        <section className="grid grid-cols-3 gap-2">
          <Dato titulo="INSFIBRA cerradas" valor={d.total} />
          <Dato titulo="Ya llamadas" valor={d.llamadas} color="border-l-emerald-500" />
          <Dato titulo="Pendientes" valor={d.pendientes} color="border-l-red-500" />
        </section>
      )}

      <div className="tarjeta overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr><th className="px-3 py-2">Orden</th><th className="px-3 py-2">Cliente</th><th className="px-3 py-2">Técnico</th><th className="px-3 py-2">Cierre</th><th className="px-3 py-2">¿Se llamó?</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(d?.filas ?? []).map((f) => (
              <tr key={f.num}>
                <td className="px-3 py-2 font-mono">{f.num}</td>
                <td className="px-3 py-2">{f.nombre ?? '—'} <span className="text-xs text-slate-400">{f.cliente}</span></td>
                <td className="px-3 py-2">{f.tecnico ?? '—'}</td>
                <td className="px-3 py-2 whitespace-nowrap">{horaLocal(f.fecha_cierre)}</td>
                <td className="px-3 py-2">
                  {f.llamada ? (
                    <span className="text-emerald-700">✓ Sí</span>
                  ) : alLlamar ? (
                    <button className="rounded bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700 hover:bg-red-100" onClick={() => alLlamar(f.num)}>
                      Pendiente · llamar
                    </button>
                  ) : (
                    <span className="text-red-700">Pendiente</span>
                  )}
                </td>
              </tr>
            ))}
            {d && d.filas.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-slate-400">No hay cierres en este rango.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
