import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { api, consulta } from '../../api'
import type { CatalogoExpedientes, ConsolidadoMes, ListadoExpedientes, RegistroExpediente } from '../../tipos'
import { COLOR_CLASIFICACION } from '../../estilos'
import { Aviso, Barras, Dato, Descarga, Pestanas, Segmentado } from '../ui'
import DetalleRegistro from './DetalleRegistro'
import FormularioFalta from './FormularioFalta'

type Tipo = 'todos' | 'llamado' | 'tarde' | 'ausencia' | 'medica'
type Vista = 'registros' | 'analisis' | 'mes'

const TIPOS: { valor: Tipo; texto: string }[] = [
  { valor: 'todos', texto: 'Todos' },
  { valor: 'llamado', texto: 'Llamados' },
  { valor: 'tarde', texto: 'Tardanzas' },
  { valor: 'ausencia', texto: 'Ausencias' },
  { valor: 'medica', texto: 'Médicas' },
]

const hoy = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Tegucigalpa' })
const haceDias = (dias: number) => {
  const d = new Date(`${hoy()}T12:00:00`)
  d.setDate(d.getDate() - dias)
  return d.toISOString().slice(0, 10)
}
const fechaCorta = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`

export default function Historial({
  seccion,
  catalogo,
  esAdmin,
}: {
  seccion: 'operaciones' | 'administrativo'
  catalogo: CatalogoExpedientes | undefined
  esAdmin: boolean
}) {
  const [area, setArea] = useState('')
  const [colaborador, setColaborador] = useState('')
  const [desde, setDesde] = useState(haceDias(60))
  const [hasta, setHasta] = useState(hoy())
  const [tipo, setTipo] = useState<Tipo>('todos')
  const [vista, setVista] = useState<Vista>('registros')
  const [formulario, setFormulario] = useState(false)
  const [detalle, setDetalle] = useState<RegistroExpediente | null>(null)

  const filtros = consulta({ seccion, area, colaborador, desde, hasta, tipo })
  const listado = useQuery({
    queryKey: ['expedientes', 'listado', filtros],
    queryFn: () => api<ListadoExpedientes>(`/expedientes${filtros}`),
    placeholderData: keepPreviousData,
  })
  const consolidado = useQuery({
    queryKey: ['expedientes', 'consolidado'],
    queryFn: () => api<ConsolidadoMes>('/expedientes/consolidado-mes'),
    enabled: vista === 'mes' && seccion === 'operaciones',
  })
  const d = listado.data

  return (
    <div className="space-y-3">
      <div className="tarjeta flex flex-wrap items-end gap-2 p-3">
        {seccion === 'administrativo' && (
          <label className="space-y-1">
            <span className="etiqueta">Área</span>
            <select className="campo py-1.5" value={area} onChange={(e) => { setArea(e.target.value); setColaborador('') }}>
              <option value="">Todas las áreas</option>
              {(d?.areas ?? []).map((a) => <option key={a}>{a}</option>)}
            </select>
          </label>
        )}
        <label className="min-w-48 flex-1 space-y-1 sm:flex-none">
          <span className="etiqueta">Colaborador</span>
          <select className="campo py-1.5" value={colaborador} onChange={(e) => setColaborador(e.target.value)}>
            <option value="">Todos</option>
            {(d?.colaboradores ?? []).map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="space-y-1">
          <span className="etiqueta">Desde</span>
          <input type="date" className="campo py-1.5" value={desde} max={hasta} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="etiqueta">Hasta</span>
          <input type="date" className="campo py-1.5" value={hasta} min={desde} onChange={(e) => setHasta(e.target.value)} />
        </label>
        <Segmentado etiqueta="Tipo de registro" opciones={TIPOS} valor={tipo} alCambiar={setTipo} />
        <button className="boton-primario ml-auto py-1.5" onClick={() => setFormulario(true)}>
          + Registrar
        </button>
      </div>

      {listado.error && <Aviso tipo="error">No se pudo cargar el historial: {listado.error.message}</Aviso>}

      {d && (
        <section className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Dato titulo="Casos" valor={d.panel.total} />
          <Dato titulo="Personas" valor={d.panel.personas} color="border-l-emerald-500" />
          <Dato titulo="Graves" valor={d.panel.clasificacion.GRAVE} color="border-l-red-500" />
          <Dato titulo="Leves" valor={d.panel.clasificacion.LEVE} color="border-l-amber-500" />
        </section>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1">
          <Pestanas
            opciones={[
              { valor: 'registros', texto: 'Registros', cuenta: d?.registros.length },
              { valor: 'analisis', texto: 'Análisis' },
              { valor: 'mes', texto: 'Resumen del mes' },
            ]}
            valor={vista}
            alCambiar={setVista}
          />
        </div>
        <Descarga href={`/api/expedientes/reporte.pdf${filtros}`}>PDF</Descarga>
        <Descarga href={`/api/expedientes/reporte.docx${filtros}`}>Word</Descarga>
      </div>

      {vista === 'registros' && <TablaRegistros registros={d?.registros ?? []} cargando={listado.isPending} alAbrir={setDetalle} />}

      {vista === 'analisis' && d && (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="tarjeta p-4">
            <p className="etiqueta mb-2">Reincidentes (mismo motivo más de una vez)</p>
            {d.panel.reincidentes.length === 0 ? (
              <p className="text-sm text-emerald-700">Sin reincidentes.</p>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm">
                {d.panel.reincidentes.slice(0, 8).map((r) => (
                  <li key={r.colaborador + r.motivo} className="flex justify-between gap-2 py-1.5">
                    <span className="truncate">{r.colaborador} · <span className="text-slate-500">{r.motivo}</span></span>
                    <span className="font-semibold text-red-700">{r.veces}×</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Barras titulo="Faltas por día de la semana" filas={d.panel.por_dia} color="bg-red-400" />
          <Barras titulo="Rubros" filas={d.panel.por_rubro} />
          <Barras titulo="Tipos de falta" filas={d.panel.por_motivo} color="bg-emerald-500" />
        </div>
      )}

      {vista === 'mes' && d && (
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="tarjeta overflow-hidden">
            <p className="etiqueta p-3 pb-2">Lo que va de {d.mes} (personas del filtro)</p>
            <TablaSimple
              encabezados={['Colaborador', 'Tardanzas', 'Otras', 'Total']}
              filas={d.resumen_mes.map((f) => [f.colaborador, f.tardes, f.otras, f.total])}
            />
          </div>
          {seccion === 'operaciones' && (
            <div className="tarjeta overflow-hidden">
              <div className="flex items-center justify-between p-3 pb-2">
                <p className="etiqueta">Consolidado de {consolidado.data?.mes ?? d.mes} (todo el personal)</p>
                <Descarga href="/api/expedientes/consolidado-mes.pdf">PDF</Descarga>
              </div>
              <TablaSimple
                encabezados={['Colaborador', 'Faltas del mes']}
                filas={(consolidado.data?.filas ?? []).map((f) => [f.colaborador, f.faltas])}
                resaltar={(fila) => Number(fila[1]) >= 3}
              />
            </div>
          )}
        </div>
      )}

      {formulario && catalogo && (
        <FormularioFalta seccion={seccion} catalogo={catalogo} alCerrar={() => setFormulario(false)} />
      )}
      {detalle && <DetalleRegistro registro={detalle} esAdmin={esAdmin} alCerrar={() => setDetalle(null)} />}
    </div>
  )
}

function TablaRegistros({
  registros,
  cargando,
  alAbrir,
}: {
  registros: RegistroExpediente[]
  cargando: boolean
  alAbrir: (r: RegistroExpediente) => void
}) {
  const [busqueda, setBusqueda] = useState('')
  const filas = useMemo(() => {
    const t = busqueda.trim().toLowerCase()
    return t
      ? registros.filter((r) => [r.colaborador, r.tipo_falta, r.comentario, r.supervisor].some((v) => v.toLowerCase().includes(t)))
      : registros
  }, [registros, busqueda])

  return (
    <div className="tarjeta overflow-hidden">
      <div className="border-b border-slate-200 p-3">
        <input className="campo max-w-xs" placeholder="Buscar en el historial…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
      </div>
      <ul className="divide-y divide-slate-100">
        {filas.map((r) => (
          <li key={r.id}>
            <button className="grid w-full gap-1 px-3 py-2.5 text-left text-sm hover:bg-marca-suave/60 sm:grid-cols-[6rem_14rem_minmax(0,1fr)_9rem]" onClick={() => alAbrir(r)}>
              <span className="text-slate-500 tabular-nums">{fechaCorta(r.fecha_incidencia)}</span>
              <span className="font-medium">{r.colaborador}</span>
              <span className="min-w-0">
                <span className={`mr-2 rounded px-1.5 py-0.5 text-[10px] font-bold ${COLOR_CLASIFICACION[r.clasificacion]}`}>
                  {r.clasificacion}
                </span>
                <span className="font-medium">{r.tipo_falta}</span>
                <span className="block truncate text-slate-500">{r.comentario}</span>
              </span>
              <span className="text-xs text-slate-500">
                {r.supervisor}
                {(r.archivos.length > 0 || r.urls_externas.length > 0) && (
                  <span className="ml-1 text-marca">· {r.archivos.length + r.urls_externas.length} adjunto(s)</span>
                )}
              </span>
            </button>
          </li>
        ))}
        {filas.length === 0 && (
          <li className="px-3 py-8 text-center text-slate-400">{cargando ? 'Cargando…' : 'No hay registros con estos filtros.'}</li>
        )}
      </ul>
    </div>
  )
}

function TablaSimple({
  encabezados,
  filas,
  resaltar,
}: {
  encabezados: string[]
  filas: (string | number)[][]
  resaltar?: (fila: (string | number)[]) => boolean
}) {
  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-left text-xs text-slate-500 uppercase">
        <tr>{encabezados.map((e, i) => <th key={e} className={`px-3 py-2 ${i ? 'text-right' : ''}`}>{e}</th>)}</tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {filas.map((f) => (
          <tr key={String(f[0])} className={resaltar?.(f) ? 'bg-red-50' : ''}>
            {f.map((v, i) => <td key={i} className={`px-3 py-1.5 ${i ? 'text-right tabular-nums' : ''}`}>{v}</td>)}
          </tr>
        ))}
        {filas.length === 0 && (
          <tr><td colSpan={encabezados.length} className="px-3 py-6 text-center text-slate-400">Sin faltas este mes.</td></tr>
        )}
      </tbody>
    </table>
  )
}
