import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api, consulta } from '../../api'
import { duracion, horaLocal } from '../../formato'
import type { OrdenCalidad } from '../../tipos'
import { useRetardo } from '../../useRetardo'

export default function BuscadorOrden({
  orden,
  alElegir,
}: {
  orden: OrdenCalidad | null
  alElegir: (o: OrdenCalidad | null) => void
}) {
  const [texto, setTexto] = useState('')
  const q = useRetardo(texto.trim())
  const resultados = useQuery({
    queryKey: ['calidad', 'ordenes', q],
    queryFn: () => api<OrdenCalidad[]>(`/calidad/ordenes${consulta({ q })}`),
    enabled: q.length >= 2 && !orden,
  })

  if (orden) {
    return (
      <div className="tarjeta space-y-2 p-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono font-semibold">ORD-{orden.num}</span>
          <span className="text-slate-500">{orden.actividad} · {orden.estado}</span>
          <button className="ml-auto text-xs text-marca hover:underline" onClick={() => { alElegir(null); setTexto('') }}>
            Cambiar de orden
          </button>
        </div>
        <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
          <div><dt className="etiqueta">Cliente</dt><dd>{orden.nombre ?? '—'} <span className="text-slate-400">· {orden.cliente}</span></dd></div>
          <div><dt className="etiqueta">Técnico</dt><dd>{orden.tecnico ?? '—'}</dd></div>
          <div><dt className="etiqueta">Colonia</dt><dd>{orden.colonia ?? '—'}</dd></div>
          <div><dt className="etiqueta">Cierre · tiempo</dt><dd>{horaLocal(orden.hora_liq)} · {duracion(orden.tiempo_invertido_min)}</dd></div>
        </dl>
        {(orden.comentario_cierre || orden.comentario) && (
          <details className="text-slate-600">
            <summary className="cursor-pointer text-xs text-marca">Ver comentarios de la orden</summary>
            {orden.comentario && <p className="mt-1"><strong>Apertura:</strong> {orden.comentario}</p>}
            {orden.comentario_cierre && <p className="mt-1"><strong>Cierre:</strong> {orden.comentario_cierre}</p>}
          </details>
        )}
      </div>
    )
  }

  return (
    <div className="tarjeta space-y-2 p-4">
      <label className="block space-y-1">
        <span className="etiqueta">Buscar orden</span>
        <input className="campo" autoFocus placeholder="Número de orden, número de cliente o nombre…" value={texto} onChange={(e) => setTexto(e.target.value)} />
      </label>
      {q.length >= 2 && (
        <ul className="divide-y divide-slate-100 text-sm">
          {resultados.isFetching && <li className="py-2 text-slate-400">Buscando…</li>}
          {!resultados.isFetching && resultados.data?.length === 0 && <li className="py-2 text-slate-400">Sin coincidencias.</li>}
          {resultados.data?.map((o) => (
            <li key={o.num}>
              <button className="w-full py-2 text-left hover:bg-marca-suave/60" onClick={() => alElegir(o)}>
                <span className="font-mono font-semibold">ORD-{o.num}</span> · {o.nombre ?? '—'}
                <span className="text-slate-500"> · {o.cliente} · {o.actividad} · {o.tecnico ?? 'sin técnico'}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
