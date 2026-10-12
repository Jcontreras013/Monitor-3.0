import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { enviarFormulario } from '../../api'
import type { CatalogoExpedientes, RegistroExpediente } from '../../tipos'
import Modal from '../Modal'

const RECO = 'Reco / Cambio de Postes'
const hoy = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Tegucigalpa' })

export default function FormularioFalta({
  seccion,
  catalogo,
  alCerrar,
}: {
  seccion: 'operaciones' | 'administrativo'
  catalogo: CatalogoExpedientes
  alCerrar: () => void
}) {
  const clienteQuery = useQueryClient()
  const motivos = seccion === 'operaciones' ? catalogo.motivos_operaciones : catalogo.motivos_administrativo
  const areas = Object.keys(catalogo.personal).filter((a) => a !== 'OPERACIONES').sort()

  const [area, setArea] = useState('')
  const [motivo, setMotivo] = useState(motivos[0])
  const [motivoOtro, setMotivoOtro] = useState('')
  const [colaborador, setColaborador] = useState('')
  const [fecha, setFecha] = useState(hoy())
  const [comentario, setComentario] = useState('')
  const [archivos, setArchivos] = useState<FileList | null>(null)

  const personas = seccion === 'operaciones' ? catalogo.personal.OPERACIONES ?? [] : catalogo.personal[area] ?? []
  const esReco = seccion === 'operaciones' && motivo === RECO

  const guardar = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      datos.set('seccion', seccion)
      datos.set('area', area)
      datos.set('colaborador', esReco ? 'RECO' : colaborador)
      datos.set('motivo', motivo)
      datos.set('motivo_otro', motivoOtro)
      datos.set('fecha_incidencia', fecha)
      datos.set('comentario', comentario)
      for (const archivo of Array.from(archivos ?? [])) datos.append('archivos', archivo)
      return enviarFormulario<RegistroExpediente>('/expedientes', datos)
    },
    onSuccess: () => {
      clienteQuery.invalidateQueries({ queryKey: ['expedientes'] })
      alCerrar()
    },
  })

  const alEnviar = (e: FormEvent) => {
    e.preventDefault()
    guardar.mutate()
  }

  return (
    <Modal titulo={seccion === 'operaciones' ? 'Nuevo registro · Operaciones' : 'Nuevo registro · Administrativo'} alCerrar={alCerrar} ancho="max-w-xl">
      <form onSubmit={alEnviar} className="grid gap-3 sm:grid-cols-2">
        {seccion === 'administrativo' && (
          <label className="space-y-1 sm:col-span-2">
            <span className="etiqueta">Área / departamento</span>
            <select className="campo" value={area} onChange={(e) => { setArea(e.target.value); setColaborador('') }} required>
              <option value="">Seleccione…</option>
              {areas.map((a) => <option key={a}>{a}</option>)}
            </select>
          </label>
        )}
        <label className="space-y-1">
          <span className="etiqueta">{seccion === 'operaciones' ? 'Motivo' : 'Tipo de registro'}</span>
          <select className="campo" value={motivo} onChange={(e) => setMotivo(e.target.value)}>
            {motivos.map((m) => <option key={m}>{m}</option>)}
          </select>
        </label>
        <label className="space-y-1">
          <span className="etiqueta">Fecha</span>
          <input type="date" className="campo" value={fecha} max={hoy()} onChange={(e) => setFecha(e.target.value)} required />
        </label>
        {motivo === 'Otro' && (
          <label className="space-y-1 sm:col-span-2">
            <span className="etiqueta">Especifique el motivo</span>
            <input className="campo" value={motivoOtro} onChange={(e) => setMotivoOtro(e.target.value)} required />
          </label>
        )}
        <label className="space-y-1 sm:col-span-2">
          <span className="etiqueta">Colaborador</span>
          {esReco ? (
            <input className="campo" value="RECO" disabled />
          ) : personas.length ? (
            <select className="campo" value={colaborador} onChange={(e) => setColaborador(e.target.value)} required>
              <option value="">Seleccione…</option>
              {personas.map((p) => <option key={p}>{p}</option>)}
            </select>
          ) : (
            <input className="campo uppercase" placeholder="Nombre completo" value={colaborador} onChange={(e) => setColaborador(e.target.value)} required />
          )}
        </label>
        <label className="space-y-1 sm:col-span-2">
          <span className="etiqueta">Descripción de los hechos</span>
          <textarea className="campo min-h-24" value={comentario} onChange={(e) => setComentario(e.target.value)} required />
        </label>
        <label className="space-y-1 sm:col-span-2">
          <span className="etiqueta">Evidencias (fotos o PDF, opcional)</span>
          <input type="file" className="campo" accept=".png,.jpg,.jpeg,.webp,.pdf" multiple onChange={(e) => setArchivos(e.target.files)} />
        </label>
        {guardar.error && <p className="text-sm text-red-600 sm:col-span-2">{guardar.error.message}</p>}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <button type="button" className="boton-secundario" onClick={alCerrar}>Cancelar</button>
          <button className="boton-primario" disabled={guardar.isPending}>{guardar.isPending ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}
