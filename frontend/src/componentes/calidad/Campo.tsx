import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { enviarFormulario } from '../../api'
import type { AuditoriaCampo, ConfigCalidad, OrdenCalidad } from '../../tipos'
import { Aviso, Segmentado } from '../ui'

type Tipo = 'operaciones' | 'instalaciones' | 'fibra'

function Campo({ etiqueta, valor, alCambiar, ...resto }: { etiqueta: string; valor: string; alCambiar: (v: string) => void; placeholder?: string }) {
  return (
    <label className="space-y-1">
      <span className="etiqueta">{etiqueta}</span>
      <input className="campo" value={valor} onChange={(e) => alCambiar(e.target.value)} {...resto} />
    </label>
  )
}

export default function Campo_({ orden, config }: { orden: OrdenCalidad; config: ConfigCalidad }) {
  const clienteQuery = useQueryClient()
  const [tipo, setTipo] = useState<Tipo>(orden.actividad === 'INSFIBRA' ? 'instalaciones' : 'operaciones')
  const [d, setD] = useState({
    vineta: '', mufa: '', metraje: '', estetica: config.esteticas[0], ruta_acometida: '',
    tiempo_invertido: orden.tiempo_invertido_min !== null ? `${orden.tiempo_invertido_min} minutos` : '',
    tipo_fo: '', comentario: '', evaluacion: config.evaluaciones_fibra[0],
  })
  const [fotos, setFotos] = useState<FileList | null>(null)
  const poner = (clave: keyof typeof d) => (valor: string) => setD({ ...d, [clave]: valor })

  const guardar = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      datos.set('tipo', tipo)
      datos.set('num_orden', orden.num)
      Object.entries(d).forEach(([k, v]) => datos.set(k, v))
      for (const f of Array.from(fotos ?? [])) datos.append('fotos', f)
      return enviarFormulario<AuditoriaCampo>('/calidad/auditorias', datos)
    },
    onSuccess: () => clienteQuery.invalidateQueries({ queryKey: ['calidad'] }),
  })

  const alEnviar = (e: FormEvent) => {
    e.preventDefault()
    guardar.mutate()
  }

  if (guardar.isSuccess) {
    return (
      <Aviso tipo="exito">
        Auditoría guardada para la ORD-{orden.num}.
        {guardar.data.evaluacion === 'Deficiente / Mal trabajo' && ' Quedó pendiente en Expedientes para registrar el llamado de atención.'}{' '}
        <button className="underline" onClick={() => guardar.reset()}>Registrar otra</button>
      </Aviso>
    )
  }

  return (
    <form onSubmit={alEnviar} className="space-y-3">
      <Segmentado
        etiqueta="Tipo de auditoría"
        valor={tipo}
        alCambiar={setTipo}
        opciones={[
          { valor: 'operaciones', texto: 'Órdenes varias' },
          { valor: 'instalaciones', texto: 'Instalaciones (INSFIBRA)' },
          { valor: 'fibra', texto: 'Fibra en campo' },
        ]}
      />
      <div className="tarjeta grid gap-3 p-4 sm:grid-cols-2">
        {tipo === 'operaciones' && (
          <>
            <Campo etiqueta="Viñeta" valor={d.vineta} alCambiar={poner('vineta')} placeholder="V-12345" />
            <Campo etiqueta="Mufa" valor={d.mufa} alCambiar={poner('mufa')} placeholder="MUFA-A" />
            <Campo etiqueta="Metraje (m)" valor={d.metraje} alCambiar={poner('metraje')} />
            <label className="space-y-1">
              <span className="etiqueta">Estética</span>
              <select className="campo" value={d.estetica} onChange={(e) => poner('estetica')(e.target.value)}>
                {config.esteticas.map((x) => <option key={x}>{x}</option>)}
              </select>
            </label>
            <div className="sm:col-span-2"><Campo etiqueta="Ruta de acometida" valor={d.ruta_acometida} alCambiar={poner('ruta_acometida')} placeholder="Poste 3 a fachada" /></div>
          </>
        )}
        {tipo === 'instalaciones' && (
          <>
            <Campo etiqueta="Tiempo invertido" valor={d.tiempo_invertido} alCambiar={poner('tiempo_invertido')} placeholder="45 minutos" />
            <Campo etiqueta="Tipo F.O." valor={d.tipo_fo} alCambiar={poner('tipo_fo')} placeholder="Drop Flat 1 hilo" />
            <Campo etiqueta="Metros F.O." valor={d.metraje} alCambiar={poner('metraje')} />
            <Campo etiqueta="Viñeta" valor={d.vineta} alCambiar={poner('vineta')} />
            <Campo etiqueta="Ruta de acometida" valor={d.ruta_acometida} alCambiar={poner('ruta_acometida')} />
            <Campo etiqueta="Mufa" valor={d.mufa} alCambiar={poner('mufa')} />
          </>
        )}
        {tipo === 'fibra' && (
          <>
            <Campo etiqueta="Ruta de acometida" valor={d.ruta_acometida} alCambiar={poner('ruta_acometida')} placeholder="Poste 3 a caja NAP" />
            <Campo etiqueta="Metraje" valor={d.metraje} alCambiar={poner('metraje')} placeholder="45 o 45M" />
            <Campo etiqueta="Viñeta" valor={d.vineta} alCambiar={poner('vineta')} />
            <label className="space-y-1">
              <span className="etiqueta">Evaluación del trabajo</span>
              <select className="campo" value={d.evaluacion} onChange={(e) => poner('evaluacion')(e.target.value)}>
                {config.evaluaciones_fibra.map((x) => <option key={x}>{x}</option>)}
              </select>
            </label>
          </>
        )}
        <label className="space-y-1 sm:col-span-2">
          <span className="etiqueta">{tipo === 'fibra' ? 'Comentarios' : 'Comentario del auditor'}</span>
          <textarea className="campo" value={d.comentario} onChange={(e) => poner('comentario')(e.target.value)} />
        </label>
        <label className="space-y-1 sm:col-span-2">
          <span className="etiqueta">Fotos (opcional)</span>
          <input type="file" className="campo" accept=".png,.jpg,.jpeg,.webp" multiple onChange={(e) => setFotos(e.target.files)} />
        </label>
        {tipo === 'fibra' && d.evaluacion === 'Deficiente / Mal trabajo' && (
          <p className="text-xs text-amber-700 sm:col-span-2">Al guardarla queda en Expedientes para registrar el llamado de atención al técnico.</p>
        )}
      </div>
      {guardar.error && <Aviso tipo="error">{guardar.error.message}</Aviso>}
      <div className="flex justify-end">
        <button className="boton-primario" disabled={guardar.isPending}>{guardar.isPending ? 'Guardando…' : 'Guardar auditoría'}</button>
      </div>
    </form>
  )
}
