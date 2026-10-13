import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api, borrar, consulta } from '../../api'
import type { AuditoriaCampo, Conteo, GestionCalidad, HistoricoCalidad } from '../../tipos'
import Modal from '../Modal'
import { Aviso, Barras, Dato, Descarga, Segmentado } from '../ui'

type Base = 'gestiones' | 'operaciones' | 'instalaciones' | 'fibra'

const BASES: { valor: Base; texto: string }[] = [
  { valor: 'gestiones', texto: 'Llamadas' },
  { valor: 'operaciones', texto: 'Órdenes varias' },
  { valor: 'instalaciones', texto: 'Instalaciones' },
  { valor: 'fibra', texto: 'Fibra' },
]
const COLOR_RESULTADO: Record<string, string> = {
  Aprobado: 'bg-emerald-100 text-emerald-800',
  'Con Obs.': 'bg-amber-100 text-amber-800',
  Rechazado: 'bg-red-100 text-red-800',
  'Sin Gestión': 'bg-slate-100 text-slate-600',
}
const hoy = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Tegucigalpa' })
const haceDias = (dias: number) => {
  const d = new Date(`${hoy()}T12:00:00`)
  d.setDate(d.getDate() - dias)
  return d.toISOString().slice(0, 10)
}
const fechaHN = (iso: string) => new Date(iso).toLocaleString('es-HN', { timeZone: 'America/Tegucigalpa', dateStyle: 'short', timeStyle: 'short' })

export default function Historico({ puedeBorrar }: { puedeBorrar: boolean }) {
  const clienteQuery = useQueryClient()
  const [base, setBase] = useState<Base>('gestiones')
  const [desde, setDesde] = useState(haceDias(7))
  const [hasta, setHasta] = useState(hoy())
  const [detalle, setDetalle] = useState<GestionCalidad | AuditoriaCampo | null>(null)
  const filtros = consulta({ base, desde, hasta })
  const datos = useQuery({
    queryKey: ['calidad', 'historico', base, filtros],
    queryFn: () => api<HistoricoCalidad>(`/calidad/historico${filtros}`),
    // Al cambiar de base el resumen tiene otra forma: solo se conservan datos previos de la misma base.
    placeholderData: (previo, consultaPrevia) => (consultaPrevia?.queryKey[2] === base ? previo : undefined),
  })
  const eliminar = useMutation({
    mutationFn: (ruta: string) => borrar(ruta),
    onSuccess: () => {
      clienteQuery.invalidateQueries({ queryKey: ['calidad'] })
      setDetalle(null)
    },
  })
  const d = datos.data
  const resumenAuditorias = (d?.resumen ?? []) as { titulo: string; columna: string; filas: Conteo[] }[]
  const resumenGestiones = (d?.resumen ?? []) as Conteo[]

  return (
    <div className="space-y-3">
      <div className="tarjeta flex flex-wrap items-end gap-2 p-3">
        <Segmentado etiqueta="Base" opciones={BASES} valor={base} alCambiar={setBase} />
        <label className="space-y-1">
          <span className="etiqueta">Desde</span>
          <input type="date" className="campo py-1.5" value={desde} max={hasta} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="etiqueta">Hasta</span>
          <input type="date" className="campo py-1.5" value={hasta} min={desde} onChange={(e) => setHasta(e.target.value)} />
        </label>
        <div className="ml-auto"><Descarga href={`/api/calidad/historico.pdf${filtros}`}>PDF</Descarga></div>
      </div>
      {datos.error && <Aviso tipo="error">{datos.error.message}</Aviso>}

      {d && base === 'gestiones' && (
        <>
          <section className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Dato titulo="Gestiones" valor={d.gestiones.length} />
            <Dato titulo="CSAT (P7: 4 o 5)" valor={d.csat?.csat != null ? `${Math.round(d.csat.csat)}%` : '—'} color="border-l-emerald-500" />
            <Dato titulo="Respuestas válidas" valor={d.csat?.validas ?? 0} color="border-l-amber-500" />
            <Dato titulo="Sin gestión" valor={resumenGestiones.find((r) => r.nombre === 'Sin Gestión')?.cantidad ?? 0} color="border-l-slate-400" />
          </section>
          <div className="grid gap-3 lg:grid-cols-2">
            <Barras titulo="Diagnóstico por pregunta (promedio 1-5)" filas={d.diagnostico.map((x) => ({ nombre: x.pregunta, cantidad: x.promedio }))} color="bg-amber-400" />
            <div className="tarjeta overflow-x-auto">
              <p className="etiqueta p-3 pb-2">Por técnico</p>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                  <tr><th className="px-3 py-1.5 text-left">Técnico</th><th className="px-2">Total</th><th className="px-2">Aprob.</th><th className="px-2">Obs.</th><th className="px-2">Rech.</th><th className="px-2">Sin gest.</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-center tabular-nums">
                  {d.por_tecnico.map((t) => (
                    <tr key={t.tecnico}><td className="px-3 py-1.5 text-left">{t.tecnico}</td><td>{t.total}</td><td>{t.aprobado}</td><td>{t.con_obs}</td><td>{t.rechazado}</td><td>{t.sin_gestion}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <Lista
            vacio="No hay gestiones en este rango."
            filas={d.gestiones.map((g) => ({
              clave: g.id,
              principal: `ORD-${g.num_orden} · ${g.nombre_cliente}`,
              secundario: `${g.tecnico} · ${fechaHN(g.fecha_gestion)} · ${g.registrado_por}`,
              etiqueta: g.resultado,
              color: COLOR_RESULTADO[g.resultado],
              alAbrir: () => setDetalle(g),
            }))}
          />
        </>
      )}

      {d && base !== 'gestiones' && (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            {resumenAuditorias.map((r) => <Barras key={r.titulo} titulo={r.titulo} filas={r.filas} />)}
          </div>
          <Lista
            vacio="No hay auditorías en este rango."
            filas={d.auditorias.map((a) => ({
              clave: a.id,
              principal: `ORD-${a.num_orden} · ${a.nombre_cliente || a.cliente}`,
              secundario: `${a.tecnico || '—'} · ${fechaHN(a.fecha_auditoria)} · ${a.supervisor}`,
              etiqueta: a.evaluacion || a.estetica || undefined,
              color: a.evaluacion === 'Deficiente / Mal trabajo' || a.estetica === 'Deficiente' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600',
              alAbrir: () => setDetalle(a),
            }))}
          />
        </>
      )}

      {detalle && (
        <Modal titulo={`ORD-${detalle.num_orden}`} alCerrar={() => setDetalle(null)} ancho="max-w-2xl">
          <DetalleRegistro registro={detalle} />
          {puedeBorrar && (
            <div className="mt-4 flex justify-end border-t border-slate-200 pt-3">
              {eliminar.error && <p className="mr-auto text-sm text-red-600">{eliminar.error.message}</p>}
              <button
                className="boton text-red-700 hover:bg-red-50"
                disabled={eliminar.isPending}
                onClick={() =>
                  window.confirm('¿Eliminar este registro definitivamente?') &&
                  eliminar.mutate('fecha_gestion' in detalle ? `/calidad/gestiones/${detalle.id}` : `/calidad/auditorias/${detalle.id}`)
                }
              >
                Eliminar registro
              </button>
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}

function Lista({
  filas,
  vacio,
}: {
  vacio: string
  filas: { clave: number; principal: string; secundario: string; etiqueta?: string; color?: string; alAbrir: () => void }[]
}) {
  return (
    <ul className="tarjeta divide-y divide-slate-100">
      {filas.map((f) => (
        <li key={f.clave}>
          <button className="flex w-full flex-wrap items-center gap-2 px-3 py-2.5 text-left text-sm hover:bg-marca-suave/60" onClick={f.alAbrir}>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{f.principal}</span>
              <span className="block truncate text-xs text-slate-500">{f.secundario}</span>
            </span>
            {f.etiqueta && <span className={`rounded px-2 py-0.5 text-xs font-semibold ${f.color}`}>{f.etiqueta}</span>}
          </button>
        </li>
      ))}
      {filas.length === 0 && <li className="px-3 py-8 text-center text-slate-400">{vacio}</li>}
    </ul>
  )
}

function DetalleRegistro({ registro }: { registro: GestionCalidad | AuditoriaCampo }) {
  const campos: [string, string | number | null][] =
    'fecha_gestion' in registro
      ? [
          ['Cliente', `${registro.nombre_cliente} (${registro.cliente})`], ['Técnico', registro.tecnico],
          ['Actividad', registro.actividad], ['Fecha de visita', registro.fecha_visita],
          ['Resultado', registro.resultado], ['Promedio', registro.promedio],
          ['P1 Puntualidad', registro.p1], ['P2 Presentación', registro.p2], ['P3 Claridad', registro.p3],
          ['P4 TV/CCVEO', registro.p4 ?? 'No aplica'], ['P5 Calidad', registro.p5], ['P6 Limpieza', registro.p6],
          ['P7 Satisfacción', registro.p7], ['Aprobación interna', registro.aprobacion_interna],
          ['Método', registro.metodo_auditoria], ['Mejoras / detalle', registro.mejoras],
          ['Aceptación digital', registro.aceptacion_digital], ['Seguimiento', [registro.ticket_seguimiento, registro.responsable_seguimiento, registro.fecha_limite_seguimiento].filter(Boolean).join(' · ')],
          ['Nota', registro.tipo_nota !== 'Ninguna' ? `${registro.tipo_nota}: ${registro.detalle_nota}` : ''],
          ['Registrado por', registro.registrado_por],
        ]
      : [
          ['Cliente', `${registro.nombre_cliente} (${registro.cliente})`], ['Técnico', registro.tecnico],
          ['Servicio', registro.actividad], ['Viñeta', registro.vineta], ['Mufa', registro.mufa],
          ['Metraje', registro.metraje], ['Estética', registro.estetica], ['Ruta de acometida', registro.ruta_acometida],
          ['Tiempo invertido', registro.tiempo_invertido], ['Tipo F.O.', registro.tipo_fo],
          ['Evaluación', registro.evaluacion], ['Comentario', registro.comentario], ['Supervisor', registro.supervisor],
          ['Convertida en falta', registro.convertido_a_falta ? 'Sí' : ''],
        ]
  return (
    <div className="space-y-3">
      <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
        {campos.filter(([, v]) => v !== '' && v !== null).map(([k, v]) => (
          <div key={k}><dt className="etiqueta">{k}</dt><dd className="break-words">{v}</dd></div>
        ))}
      </dl>
      {'archivos' in registro && registro.archivos.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {registro.archivos.map((a) => (
            <a key={a.id} href={`/api/archivos/${a.id}`} target="_blank" rel="noreferrer">
              <img src={`/api/archivos/${a.id}`} alt={a.nombre} className="h-28 w-full rounded-lg border border-slate-200 object-cover" />
            </a>
          ))}
        </div>
      )}
      {'urls_externas' in registro && registro.urls_externas.map((u) => (
        <a key={u} className="block text-sm text-marca hover:underline" href={u} target="_blank" rel="noreferrer noopener">🔗 Foto del sistema anterior</a>
      ))}
    </div>
  )
}
