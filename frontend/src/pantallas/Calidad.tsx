import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api, consulta } from '../api'
import BuscadorOrden from '../componentes/calidad/BuscadorOrden'
import Campo from '../componentes/calidad/Campo'
import Historico from '../componentes/calidad/Historico'
import Insfibra from '../componentes/calidad/Insfibra'
import Llamada from '../componentes/calidad/Llamada'
import { Aviso, Pestanas } from '../componentes/ui'
import type { ConfigCalidad, OrdenCalidad } from '../tipos'

const TEXTOS: Record<string, string> = {
  llamadas: 'Llamadas',
  insfibra: 'Cierres INSFIBRA',
  campo: 'Auditoría de campo',
  historico: 'Histórico',
}

export default function Calidad() {
  const clienteQuery = useQueryClient()
  const config = useQuery({ queryKey: ['calidad', 'configuracion'], queryFn: () => api<ConfigCalidad>('/calidad/configuracion') })
  const [pestana, setPestana] = useState<string | null>(null)
  const [orden, setOrden] = useState<OrdenCalidad | null>(null)

  if (config.error) return <Aviso tipo="error">{config.error.message}</Aviso>
  if (!config.data) return <div className="tarjeta h-40 animate-pulse" />
  const c = config.data
  const actual = pestana && c.pestanas.includes(pestana) ? pestana : c.pestanas[0]

  // Desde Cierres INSFIBRA: "llamar" abre la llamada con esa orden ya elegida.
  const llamar = async (num: string) => {
    const encontradas = await clienteQuery.fetchQuery({
      queryKey: ['calidad', 'ordenes', num],
      queryFn: () => api<OrdenCalidad[]>(`/calidad/ordenes${consulta({ q: num })}`),
    })
    setOrden(encontradas.find((o) => o.num === num) ?? null)
    setPestana('llamadas')
  }

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-bold text-slate-900">Control de Calidad</h1>
      <Pestanas opciones={c.pestanas.map((p) => ({ valor: p, texto: TEXTOS[p] }))} valor={actual} alCambiar={setPestana} />

      {(actual === 'llamadas' || actual === 'campo') && (
        <div className="grid gap-3 lg:grid-cols-[24rem_minmax(0,1fr)]">
          <div className="space-y-3"><BuscadorOrden orden={orden} alElegir={setOrden} /></div>
          <div>
            {!orden && <p className="tarjeta p-6 text-center text-slate-400">Busca y elige una orden para {actual === 'llamadas' ? 'registrar la llamada' : 'auditarla'}.</p>}
            {orden && actual === 'llamadas' && <Llamada key={orden.num} orden={orden} config={c} />}
            {orden && actual === 'campo' && <Campo key={orden.num} orden={orden} config={c} />}
          </div>
        </div>
      )}
      {actual === 'insfibra' && <Insfibra alLlamar={c.pestanas.includes('llamadas') ? llamar : undefined} />}
      {actual === 'historico' && <Historico puedeBorrar={c.puede_borrar} />}
    </div>
  )
}
