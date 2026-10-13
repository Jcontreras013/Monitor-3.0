import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { api, enviar } from '../../api'
import type { ConfigCalidad, GestionCalidad, OrdenCalidad } from '../../tipos'
import { Aviso, Segmentado } from '../ui'

type Nota = { fecha_gestion: string; tipo_nota: string; detalle_nota: string; registrado_por: string }
type Contesto = 'si' | 'no' | 'apagado'

const ETIQUETAS = ['Muy insatisfecho', 'Insatisfecho', 'Regular', 'Satisfecho', 'Muy satisfecho']
const ahoraHora = () => new Date().toLocaleTimeString('en-US', { timeZone: 'America/Tegucigalpa', hour: '2-digit', minute: '2-digit' })
const fechaHN = (iso: string) => new Date(iso).toLocaleString('es-HN', { timeZone: 'America/Tegucigalpa', dateStyle: 'short', timeStyle: 'short' })

function Estrellas({ valor, alCambiar, opcional }: { valor: number | null; alCambiar: (v: number | null) => void; opcional: boolean }) {
  return (
    <div className="flex flex-wrap gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          title={ETIQUETAS[n - 1]}
          onClick={() => alCambiar(n)}
          className={`size-9 rounded-lg border text-sm font-bold transition ${
            valor !== null && n <= valor ? 'border-amber-400 bg-amber-400 text-white' : 'border-slate-300 bg-white text-slate-500 hover:border-amber-400'
          }`}
        >
          {n}
        </button>
      ))}
      {opcional && (
        <button type="button" onClick={() => alCambiar(null)} className={`rounded-lg border px-2 text-xs ${valor === null ? 'border-tinta bg-tinta text-white' : 'border-slate-300 text-slate-500'}`}>
          No aplica
        </button>
      )}
      {valor !== null && <span className="self-center text-xs text-slate-500">{ETIQUETAS[valor - 1]}</span>}
    </div>
  )
}

export default function Llamada({ orden, config }: { orden: OrdenCalidad; config: ConfigCalidad }) {
  const clienteQuery = useQueryClient()
  const notas = useQuery({
    queryKey: ['calidad', 'notas', orden.num],
    queryFn: () => api<Nota[]>(`/calidad/ordenes/${orden.num}/notas`),
  })
  const [contesto, setContesto] = useState<Contesto>('si')
  const [respuestas, setRespuestas] = useState<Record<string, number | null>>(
    Object.fromEntries(config.preguntas.map((p) => [p.clave, 5])),
  )
  const [mejoras, setMejoras] = useState('')
  const [aceptacion, setAceptacion] = useState(orden.nombre ?? '')
  const [horaCierre, setHoraCierre] = useState(ahoraHora())
  const [aprobacion, setAprobacion] = useState(config.aprobaciones[0])
  const [resultado, setResultado] = useState(config.resultados_gestion[0])
  const [observaciones, setObservaciones] = useState('')
  const [ticketSeg, setTicketSeg] = useState('')
  const [responsableSeg, setResponsableSeg] = useState('')
  const [limiteSeg, setLimiteSeg] = useState('')
  const [tipoNota, setTipoNota] = useState('Ninguna')
  const [detalleNota, setDetalleNota] = useState('')

  const guardar = useMutation({
    mutationFn: () =>
      enviar<GestionCalidad>('/calidad/gestiones', {
        num_orden: orden.num,
        contesto: contesto === 'si',
        ...(contesto === 'si'
          ? { ...respuestas, mejoras, aceptacion_digital: aceptacion, hora_cierre_servicio: horaCierre, aprobacion_interna: aprobacion }
          : {
              estado_llamada: contesto === 'no' ? config.estados_sin_contestar[0] : config.estados_sin_contestar[1],
              resultado_gestion: resultado,
              observaciones,
              ticket_seguimiento: ticketSeg,
              responsable_seguimiento: responsableSeg,
              fecha_limite_seguimiento: limiteSeg || null,
            }),
        tipo_nota: tipoNota,
        detalle_nota: detalleNota,
      }),
    onSuccess: () => clienteQuery.invalidateQueries({ queryKey: ['calidad'] }),
  })

  const alEnviar = (e: FormEvent) => {
    e.preventDefault()
    guardar.mutate()
  }

  if (guardar.isSuccess) {
    const g = guardar.data
    return (
      <Aviso tipo="exito">
        Gestión guardada para la ORD-{g.num_orden}.{' '}
        {g.promedio !== null && <strong>Promedio de esta orden: {g.promedio.toFixed(1)} / 5.</strong>}{' '}
        <button className="underline" onClick={() => guardar.reset()}>Registrar otra gestión</button>
      </Aviso>
    )
  }

  return (
    <form onSubmit={alEnviar} className="space-y-3">
      {notas.data && notas.data.length > 0 && (
        <Aviso>
          <strong>Esta orden ya tiene {notas.data.length} nota(s) de gestiones anteriores:</strong>
          {notas.data.map((n, i) => (
            <span key={i} className="block">· {fechaHN(n.fecha_gestion)} — {n.tipo_nota}: {n.detalle_nota} ({n.registrado_por})</span>
          ))}
        </Aviso>
      )}

      <div className="tarjeta space-y-3 p-4">
        <span className="etiqueta">¿El cliente contestó?</span>
        <Segmentado
          etiqueta="¿Contestó?"
          valor={contesto}
          alCambiar={setContesto}
          opciones={[
            { valor: 'si', texto: 'Sí, contestó' },
            { valor: 'no', texto: 'No contestó / buzón' },
            { valor: 'apagado', texto: 'Apagado / fuera de servicio' },
          ]}
        />
      </div>

      {contesto === 'si' ? (
        <div className="tarjeta space-y-4 p-4">
          <p className="font-semibold text-slate-900">Encuesta de satisfacción (1 = muy insatisfecho, 5 = muy satisfecho)</p>
          {config.preguntas.map((p, i) => (
            <div key={p.clave} className="space-y-1">
              <p className="text-sm">{i + 1}. {p.texto}</p>
              <Estrellas valor={respuestas[p.clave]} opcional={p.opcional} alCambiar={(v) => setRespuestas({ ...respuestas, [p.clave]: v })} />
            </div>
          ))}
          <label className="block space-y-1">
            <span className="etiqueta">¿Hay algo que podamos mejorar? (opcional)</span>
            <textarea className="campo" value={mejoras} onChange={(e) => setMejoras(e.target.value)} />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="space-y-1 sm:col-span-2">
              <span className="etiqueta">Aceptación digital (cliente o responsable)</span>
              <input className="campo" value={aceptacion} onChange={(e) => setAceptacion(e.target.value)} />
            </label>
            <label className="space-y-1">
              <span className="etiqueta">Hora de cierre</span>
              <input className="campo" value={horaCierre} onChange={(e) => setHoraCierre(e.target.value)} />
            </label>
          </div>
          <label className="block space-y-1">
            <span className="etiqueta">Aprobación del servicio (uso interno)</span>
            <select className="campo" value={aprobacion} onChange={(e) => setAprobacion(e.target.value)}>
              {config.aprobaciones.map((a) => <option key={a}>{a}</option>)}
            </select>
          </label>
        </div>
      ) : (
        <div className="tarjeta grid gap-3 p-4 sm:grid-cols-2">
          <label className="space-y-1 sm:col-span-2">
            <span className="etiqueta">Resultado de la gestión</span>
            <select className="campo" value={resultado} onChange={(e) => setResultado(e.target.value)}>
              {config.resultados_gestion.map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
          <label className="space-y-1 sm:col-span-2">
            <span className="etiqueta">Detalle (buzón, apagado, etc.)</span>
            <textarea className="campo" value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="etiqueta">Ticket de seguimiento</span>
            <input className="campo" value={ticketSeg} onChange={(e) => setTicketSeg(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="etiqueta">Responsable</span>
            <input className="campo" value={responsableSeg} onChange={(e) => setResponsableSeg(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="etiqueta">Fecha límite</span>
            <input type="date" className="campo" value={limiteSeg} onChange={(e) => setLimiteSeg(e.target.value)} />
          </label>
        </div>
      )}

      <div className="tarjeta grid gap-3 p-4 sm:grid-cols-[16rem_minmax(0,1fr)]">
        <label className="space-y-1">
          <span className="etiqueta">Nota para la próxima gestión</span>
          <select className="campo" value={tipoNota} onChange={(e) => setTipoNota(e.target.value)}>
            {config.tipos_nota.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        {tipoNota !== 'Ninguna' && (
          <label className="space-y-1">
            <span className="etiqueta">Detalle de la nota</span>
            <input className="campo" value={detalleNota} onChange={(e) => setDetalleNota(e.target.value)} required />
          </label>
        )}
      </div>

      {guardar.error && <Aviso tipo="error">{guardar.error.message}</Aviso>}
      <div className="flex justify-end">
        <button className="boton-primario" disabled={guardar.isPending}>{guardar.isPending ? 'Guardando…' : 'Guardar gestión'}</button>
      </div>
    </form>
  )
}
