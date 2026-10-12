import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'

import { api, borrar, enviarFormulario } from '../../api'
import type { ArchivoMeta, CarpetaRepositorio, CatalogoExpedientes } from '../../tipos'
import { Aviso } from '../ui'

const tamano = (bytes: number) => (bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`)

export default function Repositorio({ catalogo }: { catalogo: CatalogoExpedientes | undefined }) {
  const clienteQuery = useQueryClient()
  const carpetas = useQuery({
    queryKey: ['expedientes', 'repositorio'],
    queryFn: () => api<CarpetaRepositorio[]>('/expedientes/repositorio'),
  })
  const [colaborador, setColaborador] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [archivos, setArchivos] = useState<FileList | null>(null)
  const [busqueda, setBusqueda] = useState('')
  const [abierta, setAbierta] = useState<string | null>(null)

  const nombres = useMemo(() => {
    const todos = new Set<string>()
    Object.values(catalogo?.personal ?? {}).forEach((lista) => lista.forEach((n) => todos.add(n)))
    carpetas.data?.forEach((c) => todos.add(c.colaborador))
    return [...todos].sort()
  }, [catalogo, carpetas.data])

  const subir = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      datos.set('colaborador', colaborador)
      datos.set('descripcion', descripcion)
      for (const a of Array.from(archivos ?? [])) datos.append('archivos', a)
      return enviarFormulario<ArchivoMeta[]>('/expedientes/repositorio', datos)
    },
    onSuccess: (guardados) => {
      clienteQuery.invalidateQueries({ queryKey: ['expedientes', 'repositorio'] })
      setAbierta(colaborador.toUpperCase().trim())
      setDescripcion('')
      setArchivos(null)
      return guardados
    },
  })
  const quitar = useMutation({
    mutationFn: (id: string) => borrar(`/expedientes/repositorio/${id}`),
    onSuccess: () => clienteQuery.invalidateQueries({ queryKey: ['expedientes', 'repositorio'] }),
  })

  const visibles = (carpetas.data ?? []).filter((c) => c.colaborador.toLowerCase().includes(busqueda.toLowerCase()))

  const alEnviar = (e: FormEvent) => {
    e.preventDefault()
    subir.mutate()
  }

  return (
    <div className="grid gap-3 lg:grid-cols-[22rem_minmax(0,1fr)]">
      <form onSubmit={alEnviar} className="tarjeta h-fit space-y-3 p-4">
        <p className="font-semibold text-slate-900">Subir documentos</p>
        <label className="block space-y-1">
          <span className="etiqueta">Colaborador</span>
          <input className="campo uppercase" list="lista-colaboradores" value={colaborador} onChange={(e) => setColaborador(e.target.value)} required />
          <datalist id="lista-colaboradores">{nombres.map((n) => <option key={n} value={n} />)}</datalist>
        </label>
        <label className="block space-y-1">
          <span className="etiqueta">Descripción (opcional)</span>
          <input className="campo" placeholder="Ej: Contrato firmado 2026" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
        </label>
        <label className="block space-y-1">
          <span className="etiqueta">Archivos o una carpeta en ZIP</span>
          <input type="file" className="campo" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg,.zip" onChange={(e) => setArchivos(e.target.files)} required />
        </label>
        {subir.error && <p className="text-sm text-red-600">{subir.error.message}</p>}
        {subir.isSuccess && <p className="text-sm text-emerald-700">Se guardaron {subir.data.length} archivo(s).</p>}
        <button className="boton-primario w-full" disabled={subir.isPending}>{subir.isPending ? 'Subiendo…' : 'Subir'}</button>
        <p className="text-xs text-slate-500">Los documentos quedan privados: solo los ven los usuarios con acceso al repositorio.</p>
      </form>

      <div className="space-y-2">
        <input className="campo max-w-xs" placeholder="Buscar colaborador…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
        {carpetas.error && <Aviso tipo="error">{carpetas.error.message}</Aviso>}
        {visibles.length === 0 && !carpetas.isPending && <p className="tarjeta p-6 text-center text-slate-400">No hay documentos.</p>}
        <ul className="space-y-2">
          {visibles.map((c) => (
            <li key={c.colaborador} className="tarjeta overflow-hidden">
              <button className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-medium" onClick={() => setAbierta(abierta === c.colaborador ? null : c.colaborador)}>
                <span>📁 {c.colaborador}</span>
                <span className="text-xs text-slate-500">{c.archivos.length} archivo(s) {abierta === c.colaborador ? '▴' : '▾'}</span>
              </button>
              {abierta === c.colaborador && (
                <ul className="divide-y divide-slate-100 border-t border-slate-200 text-sm">
                  {c.archivos.map((a) => (
                    <li key={a.id} className="flex flex-wrap items-center gap-2 px-4 py-2">
                      <a className="min-w-0 flex-1 truncate text-marca hover:underline" href={`/api/archivos/${a.id}`} target="_blank" rel="noreferrer">{a.nombre}</a>
                      <span className="text-xs text-slate-500">{a.descripcion} · {tamano(a.tamano)} · {a.subido_por}</span>
                      <button className="text-xs text-red-700 hover:underline" disabled={quitar.isPending} onClick={() => window.confirm(`¿Eliminar ${a.nombre}?`) && quitar.mutate(a.id)}>
                        Eliminar
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
