import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api, enviar } from '../../api'
import type { AuditoriaCampo } from '../../tipos'

const fechaHN = (iso: string) => new Date(iso).toLocaleDateString('es-HN', { timeZone: 'America/Tegucigalpa' })

function Datos({ a }: { a: AuditoriaCampo }) {
  return (
    <>
      <span className="block text-xs text-slate-500">
        Ruta: {a.ruta_acometida || '—'} · Metraje: {a.metraje || '—'} · Viñeta: {a.vineta || '—'} · Auditó: {a.supervisor}
      </span>
      {a.comentario && <span className="block">💬 {a.comentario}</span>}
      {a.archivos.length > 0 && (
        <span className="flex flex-wrap gap-2 pt-1">
          {a.archivos.map((f) => (
            <a key={f.id} href={`/api/archivos/${f.id}`} target="_blank" rel="noreferrer" className="text-xs text-marca hover:underline">📷 {f.nombre}</a>
          ))}
        </span>
      )}
    </>
  )
}

/** Auditorías de fibra "Deficiente / Mal trabajo" que aún no se registraron como falta. */
export function PendientesFibra({ alRegistrar }: { alRegistrar: (a: AuditoriaCampo) => void }) {
  const clienteQuery = useQueryClient()
  const [abierto, setAbierto] = useState(true)
  const pendientes = useQuery({
    queryKey: ['expedientes', 'auditorias-fibra'],
    queryFn: () => api<AuditoriaCampo[]>('/expedientes/auditorias-fibra'),
  })
  const descartar = useMutation({
    mutationFn: (id: number) => enviar(`/expedientes/auditorias-fibra/${id}/descartar`),
    onSuccess: () => clienteQuery.invalidateQueries({ queryKey: ['expedientes', 'auditorias-fibra'] }),
  })
  const lista = pendientes.data ?? []
  if (lista.length === 0) return null

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 text-sm text-amber-950">
      <button className="flex w-full items-center justify-between px-4 py-2.5 text-left font-semibold" onClick={() => setAbierto((v) => !v)}>
        <span>🧵 {lista.length} auditoría(s) de fibra con trabajo deficiente pendiente(s) de revisar</span>
        <span>{abierto ? '▴' : '▾'}</span>
      </button>
      {abierto && (
        <ul className="divide-y divide-amber-200 border-t border-amber-200">
          {lista.map((a) => (
            <li key={a.id} className="flex flex-wrap items-start gap-3 px-4 py-2.5">
              <span className="min-w-0 flex-1">
                <span className="block font-medium">ORD-{a.num_orden} · {a.tecnico || 'sin técnico'} · {fechaHN(a.fecha_auditoria)}</span>
                <Datos a={a} />
              </span>
              <span className="flex gap-2">
                <button className="boton-primario py-1" onClick={() => alRegistrar(a)}>Registrar como falta</button>
                <button className="boton-secundario py-1" disabled={descartar.isPending} onClick={() => window.confirm('¿Descartar? Dejará de aparecer como pendiente sin registrar falta.') && descartar.mutate(a.id)}>
                  Descartar
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Auditorías de fibra del técnico filtrado (solo lectura). */
export function AuditoriasDelTecnico({ auditorias, colaborador }: { auditorias: AuditoriaCampo[]; colaborador: string }) {
  if (auditorias.length === 0) return null
  return (
    <details className="tarjeta px-4 py-2.5 text-sm">
      <summary className="cursor-pointer font-medium">🧵 Auditorías de fibra en campo de {colaborador} ({auditorias.length})</summary>
      <ul className="mt-2 divide-y divide-slate-100">
        {auditorias.map((a) => (
          <li key={a.id} className="py-2">
            <span className="block font-medium">
              ORD-{a.num_orden} · {fechaHN(a.fecha_auditoria)} · {a.evaluacion}
              {a.convertido_a_falta && <span className="ml-2 text-xs text-slate-500">(ya revisada)</span>}
            </span>
            <Datos a={a} />
          </li>
        ))}
      </ul>
    </details>
  )
}
