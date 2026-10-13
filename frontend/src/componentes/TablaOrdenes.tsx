import { useMemo, useState, type ReactNode } from 'react'

import { duracion, horaLocal } from '../formato'
import type { Orden } from '../tipos'
import Modal from './Modal'

type Columna = {
  clave: string
  titulo: string
  valor: (o: Orden) => string | number | null
  celda?: (o: Orden) => ReactNode
  clase?: string
}

export type VistaTabla = 'pendientes' | 'cerradas_hoy' | 'reprogramadas' | 'no_instalados'

const COLOR_DIAS = (d: number) =>
  d >= 7 ? 'bg-red-100 text-red-800' : d >= 4 ? 'bg-amber-100 text-amber-800' : d >= 1 ? 'bg-yellow-100 text-yellow-800' : 'bg-emerald-100 text-emerald-800'

function Marcas({ o }: { o: Orden }) {
  return (
    <span className="flex flex-wrap gap-1">
      {o.es_offline && <span className="rounded bg-red-600 px-1.5 text-[10px] font-bold text-white">OFFLINE</span>}
      {o.alerta_tiempo && <span className="rounded bg-amber-500 px-1.5 text-[10px] font-bold text-white">+2 H</span>}
    </span>
  )
}

function Cliente({ o, detalle }: { o: Orden; detalle: (string | null)[] }) {
  return (
    <>
      <span className="block max-w-56 truncate">{o.nombre ?? '—'}</span>
      <span className="block text-xs text-slate-400">{detalle.filter(Boolean).join(' · ')}</span>
    </>
  )
}

const COLUMNAS_PENDIENTES: Columna[] = [
  {
    clave: 'dias',
    titulo: 'Días',
    valor: (o) => o.dias_retraso,
    celda: (o) => <span className={`rounded px-2 py-0.5 text-xs font-bold ${COLOR_DIAS(o.dias_retraso)}`}>{o.dias_retraso}</span>,
  },
  { clave: 'num', titulo: 'Orden', valor: (o) => o.num, clase: 'font-mono' },
  { clave: 'actividad', titulo: 'Actividad', valor: (o) => o.actividad },
  {
    clave: 'tecnico',
    titulo: 'Técnico',
    valor: (o) => o.tecnico ?? '',
    celda: (o) => o.tecnico ?? <span className="text-xs font-semibold text-amber-700">SIN ASIGNAR</span>,
  },
  { clave: 'cliente', titulo: 'Cliente', valor: (o) => o.nombre, celda: (o) => <Cliente o={o} detalle={[o.cliente, o.colonia]} /> },
  { clave: 'motivo', titulo: 'Motivo', valor: (o) => o.motivo, celda: (o) => <>{o.motivo} <Marcas o={o} /></> },
  { clave: 'estado', titulo: 'Estado', valor: (o) => o.estado, clase: 'text-xs text-slate-500' },
  {
    clave: 'gps',
    titulo: '',
    valor: (o) => o.gps,
    celda: (o) =>
      o.gps ? (
        <a
          href={o.gps}
          target="_blank"
          rel="noreferrer"
          title="Ubicación del técnico"
          className="text-marca hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          GPS
        </a>
      ) : null,
  },
]

const COLUMNAS_CERRADAS: Columna[] = [
  { clave: 'num', titulo: 'Orden', valor: (o) => o.num, clase: 'font-mono' },
  { clave: 'actividad', titulo: 'Actividad', valor: (o) => o.actividad },
  { clave: 'tecnico', titulo: 'Técnico', valor: (o) => o.tecnico },
  { clave: 'cliente', titulo: 'Cliente', valor: (o) => o.nombre, celda: (o) => <Cliente o={o} detalle={[o.cliente]} /> },
  { clave: 'cierre', titulo: 'Cierre', valor: (o) => o.hora_liq, celda: (o) => horaLocal(o.hora_liq) },
  { clave: 'tiempo', titulo: 'Tiempo', valor: (o) => o.tiempo_real_min, celda: (o) => duracion(o.tiempo_real_min) },
  { clave: 'razon', titulo: 'Razón de cierre', valor: (o) => o.razon_cierre, clase: 'text-xs' },
]

function EnDias({ dias }: { dias: number }) {
  return (
    <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-bold whitespace-nowrap text-blue-800">
      {dias === 1 ? 'mañana' : `en ${dias} d`}
    </span>
  )
}

const COLUMNAS_REPROGRAMADAS: Columna[] = [
  {
    clave: 'cita',
    titulo: 'Cita',
    valor: (o) => o.fecha_ape,
    celda: (o) => (
      <span className="flex items-center gap-2 whitespace-nowrap">
        <EnDias dias={o.dias_para_cita ?? 0} /> {horaLocal(o.fecha_ape)}
      </span>
    ),
  },
  { clave: 'num', titulo: 'Orden', valor: (o) => o.num, clase: 'font-mono' },
  { clave: 'actividad', titulo: 'Actividad', valor: (o) => o.actividad },
  {
    clave: 'tecnico',
    titulo: 'Técnico',
    valor: (o) => o.tecnico ?? '',
    celda: (o) => o.tecnico ?? <span className="text-xs font-semibold text-amber-700">SIN ASIGNAR</span>,
  },
  { clave: 'cliente', titulo: 'Cliente', valor: (o) => o.nombre, celda: (o) => <Cliente o={o} detalle={[o.cliente, o.colonia]} /> },
  { clave: 'estado', titulo: 'Estado', valor: (o) => o.estado, clase: 'text-xs text-slate-500' },
  { clave: 'comentario', titulo: 'Comentario', valor: (o) => o.comentario, celda: (o) => <span className="line-clamp-2 max-w-80 text-xs">{o.comentario}</span> },
]

const COLUMNAS_NO_INSTALADOS: Columna[] = [
  { clave: 'cierre', titulo: 'Cierre', valor: (o) => o.hora_liq, celda: (o) => horaLocal(o.hora_liq), clase: 'whitespace-nowrap' },
  { clave: 'num', titulo: 'Orden', valor: (o) => o.num, clase: 'font-mono' },
  { clave: 'tecnico', titulo: 'Técnico', valor: (o) => o.tecnico },
  { clave: 'cliente', titulo: 'Cliente', valor: (o) => o.nombre, celda: (o) => <Cliente o={o} detalle={[o.cliente, o.colonia]} /> },
  {
    clave: 'razon',
    titulo: 'Razón / comentario de cierre',
    valor: (o) => o.razon_cierre,
    celda: (o) => (
      <span className="block max-w-96 text-xs">
        {o.razon_cierre && <strong className="block">{o.razon_cierre}</strong>}
        <span className="line-clamp-2">{o.comentario_cierre || o.comentario}</span>
      </span>
    ),
  },
]

const COLUMNAS: Record<VistaTabla, Columna[]> = {
  pendientes: COLUMNAS_PENDIENTES,
  cerradas_hoy: COLUMNAS_CERRADAS,
  reprogramadas: COLUMNAS_REPROGRAMADAS,
  no_instalados: COLUMNAS_NO_INSTALADOS,
}

// El CSV lleva todos los datos, aunque la tabla muestre menos columnas.
const COLUMNAS_CSV: [string, (o: Orden) => string | number | null][] = [
  ['Orden', (o) => o.num],
  ['Días de retraso', (o) => o.dias_retraso],
  ['Actividad', (o) => o.actividad],
  ['Estado', (o) => o.estado],
  ['Técnico', (o) => o.tecnico],
  ['Vehículo', (o) => o.mx],
  ['Cliente', (o) => o.cliente],
  ['Nombre', (o) => o.nombre],
  ['Colonia', (o) => o.colonia],
  ['Sector', (o) => o.sector],
  ['Motivo', (o) => o.motivo],
  ['Offline', (o) => (o.es_offline ? 'Sí' : '')],
  ['Más de 2 h', (o) => (o.alerta_tiempo ? 'Sí' : '')],
  ['Apertura', (o) => horaLocal(o.fecha_ape)],
  ['Inicio', (o) => horaLocal(o.hora_ini)],
  ['Cierre', (o) => horaLocal(o.hora_liq)],
  ['Tiempo (min)', (o) => o.tiempo_real_min],
  ['OLT', (o) => o.olt],
  ['PON', (o) => o.pon],
  ['Comentario', (o) => o.comentario],
  ['Razón de cierre', (o) => o.razon_cierre],
  ['Comentario de cierre', (o) => o.comentario_cierre],
]

const POR_PAGINA = 50

function exportarCsv(ordenes: Orden[], nombre: string) {
  const escapar = (v: unknown) => {
    let texto = String(v ?? '')
    // Un comentario que empiece con = + - @ se ejecutaría como fórmula al abrirlo en Excel.
    if (typeof v === 'string' && /^[=+\-@]/.test(texto)) texto = `'${texto}`
    return `"${texto.replaceAll('"', '""')}"`
  }
  const filas = [COLUMNAS_CSV.map(([titulo]) => titulo), ...ordenes.map((o) => COLUMNAS_CSV.map(([, valor]) => valor(o)))]
  // BOM para que Excel respete los acentos.
  const contenido = '\ufeff' + filas.map((f) => f.map(escapar).join(',')).join('\r\n')
  const enlace = document.createElement('a')
  enlace.href = URL.createObjectURL(new Blob([contenido], { type: 'text/csv;charset=utf-8' }))
  enlace.download = nombre
  enlace.click()
  URL.revokeObjectURL(enlace.href)
}

function Detalle({ orden, alCerrar }: { orden: Orden; alCerrar: () => void }) {
  const dato = (titulo: string, valor: ReactNode) => (
    <div>
      <dt className="etiqueta">{titulo}</dt>
      <dd className="text-sm break-words">{valor || '—'}</dd>
    </div>
  )
  return (
    <Modal titulo={`Orden ${orden.num}`} alCerrar={alCerrar} ancho="max-w-2xl">
      <dl className="grid gap-4 sm:grid-cols-2">
        {dato('Actividad', `${orden.actividad} · ${orden.subtipo_tablero}`)}
        {dato('Estado', <>{orden.estado} <Marcas o={orden} /></>)}
        {dato('Técnico', orden.tecnico)}
        {dato('Vehículo (MX)', orden.mx)}
        {dato('Cliente', `${orden.cliente ?? ''} ${orden.nombre ?? ''}`)}
        {dato('Ubicación', [orden.colonia, orden.sector].filter(Boolean).join(', '))}
        {dato('OLT / PON', [orden.olt, orden.pon].filter(Boolean).join(' / '))}
        {dato('Motivo', orden.motivo)}
        {dato('Apertura', horaLocal(orden.fecha_ape))}
        {dato('Inicio / cierre', `${horaLocal(orden.hora_ini)} → ${horaLocal(orden.hora_liq)}`)}
        <div className="sm:col-span-2">{dato('Comentario de apertura', orden.comentario)}</div>
        <div className="sm:col-span-2">{dato('Razón de cierre', orden.razon_cierre)}</div>
        <div className="sm:col-span-2">{dato('Comentario de cierre', orden.comentario_cierre)}</div>
      </dl>
    </Modal>
  )
}

export default function TablaOrdenes({
  ordenes,
  vista,
  cargando,
  vacio = 'No hay órdenes con estos filtros.',
}: {
  ordenes: Orden[]
  vista: VistaTabla
  cargando: boolean
  vacio?: string
}) {
  const columnas = COLUMNAS[vista]
  const [busqueda, setBusqueda] = useState('')
  const [orden, setOrden] = useState<{ clave: string; asc: boolean } | null>(null)
  const [pagina, setPagina] = useState(0)
  const [detalle, setDetalle] = useState<Orden | null>(null)

  const filas = useMemo(() => {
    const texto = busqueda.trim().toLowerCase()
    let lista = texto
      ? ordenes.filter((o) =>
          [o.num, o.cliente, o.nombre, o.colonia, o.tecnico, o.comentario, o.actividad]
            .some((v) => v?.toLowerCase().includes(texto)),
        )
      : ordenes
    const columna = orden && columnas.find((c) => c.clave === orden.clave)
    if (columna) {
      lista = [...lista].sort((a, b) => {
        const va = columna.valor(a) ?? ''
        const vb = columna.valor(b) ?? ''
        const comparacion = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb), 'es')
        return orden.asc ? comparacion : -comparacion
      })
    }
    return lista
  }, [ordenes, busqueda, orden, columnas])

  const paginas = Math.max(1, Math.ceil(filas.length / POR_PAGINA))
  const paginaActual = Math.min(pagina, paginas - 1)
  const visibles = filas.slice(paginaActual * POR_PAGINA, (paginaActual + 1) * POR_PAGINA)

  const ordenarPor = (clave: string) =>
    setOrden((prev) => (prev?.clave === clave ? (prev.asc ? { clave, asc: false } : null) : { clave, asc: true }))

  return (
    <div className="tarjeta overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 p-3">
        <input
          className="campo max-w-xs"
          placeholder="Buscar orden, cliente, nombre, colonia…"
          value={busqueda}
          onChange={(e) => {
            setBusqueda(e.target.value)
            setPagina(0)
          }}
        />
        <span className="text-sm text-slate-500">{filas.length.toLocaleString('es-HN')} órdenes</span>
        <button
          className="boton-secundario ml-auto"
          disabled={!filas.length}
          onClick={() => exportarCsv(filas, `ordenes_${vista}_${new Date().toISOString().slice(0, 10)}.csv`)}
        >
          Descargar CSV
        </button>
      </div>
      {/* En celular: tarjetas en vez de una tabla ancha. */}
      <ul className="divide-y divide-slate-100 sm:hidden">
        {visibles.map((o) => (
          <li key={o.num}>
            <button className="w-full space-y-1 px-3 py-2.5 text-left text-sm active:bg-slate-50" onClick={() => setDetalle(o)}>
              <span className="flex items-center gap-2">
                {vista === 'pendientes' && (
                  <span className={`rounded px-2 py-0.5 text-xs font-bold ${COLOR_DIAS(o.dias_retraso)}`}>{o.dias_retraso} d</span>
                )}
                {vista === 'reprogramadas' && <EnDias dias={o.dias_para_cita ?? 0} />}
                <span className="font-mono font-semibold">{o.num}</span>
                <span className="text-slate-500">{o.actividad}</span>
                <span className="ml-auto text-xs text-slate-500">
                  {vista === 'pendientes' ? o.estado : horaLocal(vista === 'reprogramadas' ? o.fecha_ape : o.hora_liq)}
                </span>
              </span>
              <span className="block text-slate-700">{o.tecnico ?? 'SIN ASIGNAR'}</span>
              <span className="flex flex-wrap items-center gap-1 text-xs text-slate-500">
                {[o.nombre, o.colonia].filter(Boolean).join(' · ')}
                {vista === 'no_instalados' ? o.razon_cierre && <> · {o.razon_cierre}</> : <> · {o.motivo} <Marcas o={o} /></>}
              </span>
            </button>
          </li>
        ))}
        {!visibles.length && (
          <li className="px-3 py-8 text-center text-slate-400">{cargando ? 'Cargando…' : vacio}</li>
        )}
      </ul>
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
            <tr>
              {columnas.map((c) => (
                <th key={c.clave} className="px-3 py-2 font-semibold whitespace-nowrap">
                  <button className="hover:text-slate-900" onClick={() => ordenarPor(c.clave)}>
                    {c.titulo}
                    {orden?.clave === c.clave ? (orden.asc ? ' ▲' : ' ▼') : ''}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visibles.map((o) => (
              <tr key={o.num} className="cursor-pointer hover:bg-marca-suave/60" onClick={() => setDetalle(o)}>
                {columnas.map((c) => (
                  <td key={c.clave} className={`px-3 py-2 align-top ${c.clase ?? ''}`}>
                    {c.celda ? c.celda(o) : (c.valor(o) ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
            {!visibles.length && (
              <tr>
                <td colSpan={columnas.length} className="px-3 py-8 text-center text-slate-400">
                  {cargando ? 'Cargando…' : vacio}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {paginas > 1 && (
        <div className="flex items-center justify-end gap-2 border-t border-slate-200 p-3 text-sm">
          <button className="boton-secundario" disabled={paginaActual === 0} onClick={() => setPagina(paginaActual - 1)}>
            Anterior
          </button>
          <span className="text-slate-500">
            Página {paginaActual + 1} de {paginas}
          </span>
          <button className="boton-secundario" disabled={paginaActual >= paginas - 1} onClick={() => setPagina(paginaActual + 1)}>
            Siguiente
          </button>
        </div>
      )}
      {detalle && <Detalle orden={detalle} alCerrar={() => setDetalle(null)} />}
    </div>
  )
}
