import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api'
import { horaLocal } from '../formato'
import type { OrdenVip } from '../tipos'

/** Aviso compacto arriba del Monitor con las órdenes de clientes VIP sin atender. */
export default function PanelVip() {
  const [abierto, setAbierto] = useState(false)
  const datos = useQuery({ queryKey: ['monitor', 'vip'], queryFn: () => api<OrdenVip[]>('/monitor/vip') })
  const ordenes = datos.data ?? []
  if (!ordenes.length) return null
  const clientes = new Set(ordenes.map((o) => o.cliente)).size

  return (
    <section className="rounded-xl border border-amber-300 bg-amber-50 text-sm">
      <button className="flex w-full items-center gap-2 px-3 py-2 text-left font-semibold text-amber-900" onClick={() => setAbierto((v) => !v)} aria-expanded={abierto}>
        <span aria-hidden>⭐</span>
        {ordenes.length} orden(es) de clientes VIP sin atender
        <span className="font-normal text-amber-800">· {clientes} cliente(s)</span>
        <span className="ml-auto text-xs font-normal text-amber-800">{abierto ? 'Ocultar ▲' : 'Ver ▼'}</span>
      </button>
      {abierto && (
        <ul className="divide-y divide-amber-200 border-t border-amber-200">
          {ordenes.map((o) => (
            <li key={o.num} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 px-3 py-2">
              <span className="font-mono font-semibold">{o.num}</span>
              <span className="font-medium">{o.nombre_vip || o.nombre}</span>
              {o.clase_vip && <span className="rounded bg-amber-200 px-1.5 text-xs text-amber-900">{o.clase_vip}</span>}
              <span className="text-slate-600">{o.actividad} · {o.estado}</span>
              <span className="text-slate-600">{o.tecnico ?? 'SIN ASIGNAR'}</span>
              <span className="ml-auto text-xs text-slate-500">
                {horaLocal(o.fecha_ape)} · {o.dias_retraso} d · {o.colonia ?? ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
