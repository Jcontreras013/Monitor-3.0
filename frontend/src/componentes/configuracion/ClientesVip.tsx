import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { api, enviarFormulario } from '../../api'
import type { ClienteVip, VistaPreviaVip } from '../../tipos'
import { Aviso, Dato } from '../ui'

function Tabla({ clientes, limite = 200 }: { clientes: ClienteVip[]; limite?: number }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
          <tr><th className="px-3 py-2">Cliente</th><th className="px-3 py-2">Nombre</th><th className="px-3 py-2">Clase</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {clientes.slice(0, limite).map((c) => (
            <tr key={c.cliente}><td className="px-3 py-1.5 font-mono">{c.cliente}</td><td className="px-3 py-1.5">{c.nombre || '—'}</td><td className="px-3 py-1.5">{c.clase || '—'}</td></tr>
          ))}
        </tbody>
      </table>
      {clientes.length > limite && <p className="px-3 py-2 text-xs text-slate-500">… y {clientes.length - limite} más.</p>}
    </div>
  )
}

export default function ClientesVip() {
  const clienteQuery = useQueryClient()
  const actual = useQuery({ queryKey: ['configuracion', 'vip'], queryFn: () => api<ClienteVip[]>('/configuracion/vip') })
  const [busqueda, setBusqueda] = useState('')
  const [previa, setPrevia] = useState<VistaPreviaVip | null>(null)

  const leer = useMutation({
    mutationFn: (archivo: File) => {
      const datos = new FormData()
      datos.set('archivo', archivo)
      return enviarFormulario<VistaPreviaVip>('/configuracion/vip/vista-previa', datos)
    },
    onSuccess: setPrevia,
  })
  const guardar = useMutation({
    mutationFn: (clientes: ClienteVip[]) => api<{ total: number }>('/configuracion/vip', { method: 'PUT', body: JSON.stringify(clientes) }),
    onSuccess: () => {
      setPrevia(null)
      clienteQuery.invalidateQueries({ queryKey: ['configuracion', 'vip'] })
      clienteQuery.invalidateQueries({ queryKey: ['monitor', 'vip'] })
    },
  })

  const filtrados = useMemo(() => {
    const t = busqueda.trim().toLowerCase()
    const lista = actual.data ?? []
    return t ? lista.filter((c) => c.cliente.includes(t) || c.nombre.toLowerCase().includes(t)) : lista
  }, [actual.data, busqueda])

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        Las órdenes abiertas de estos clientes se marcan arriba del Monitor y el robot avisa por correo cuando se abre una
        orden nueva. Del archivo solo se guardan código, nombre y clase: los correos y teléfonos de contacto no se guardan.
      </p>

      <div className="tarjeta space-y-3 p-4">
        <label className="block space-y-1">
          <span className="etiqueta">Subir lista nueva (Excel .xlsx o CSV con una columna CLIENTE)</span>
          <input
            type="file"
            className="campo"
            accept=".xlsx,.csv"
            onChange={(e) => {
              const archivo = e.target.files?.[0]
              guardar.reset()
              if (archivo) leer.mutate(archivo)
              e.target.value = ''
            }}
          />
        </label>
        {leer.isPending && <p className="text-sm text-slate-500">Leyendo el archivo…</p>}
        {leer.error && <Aviso tipo="error">{leer.error.message}</Aviso>}
        {guardar.isSuccess && <Aviso tipo="exito">Lista VIP guardada: {guardar.data.total} clientes.</Aviso>}
        {previa && (
          <div className="space-y-3">
            <Aviso>
              El archivo trae <strong>{previa.clientes.length}</strong> clientes: {previa.nuevos} nuevo(s) y {previa.salen} que
              salen de la lista. La lista actual se reemplaza completa.
            </Aviso>
            <div className="max-h-72 overflow-y-auto rounded-lg border border-slate-200"><Tabla clientes={previa.clientes} /></div>
            {guardar.error && <Aviso tipo="error">{guardar.error.message}</Aviso>}
            <div className="flex justify-end gap-2">
              <button className="boton-secundario" onClick={() => setPrevia(null)}>Cancelar</button>
              <button className="boton-primario" disabled={guardar.isPending || !previa.clientes.length} onClick={() => guardar.mutate(previa.clientes)}>
                {guardar.isPending ? 'Guardando…' : 'Reemplazar lista VIP'}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Dato titulo="Clientes VIP cargados" valor={actual.data?.length ?? '—'} />
      </div>
      {actual.error && <Aviso tipo="error">{actual.error.message}</Aviso>}
      {!!actual.data?.length && (
        <div className="tarjeta">
          <div className="border-b border-slate-200 p-3">
            <input className="campo max-w-xs" placeholder="Buscar código o nombre…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
          </div>
          <Tabla clientes={filtrados} />
        </div>
      )}
    </div>
  )
}
