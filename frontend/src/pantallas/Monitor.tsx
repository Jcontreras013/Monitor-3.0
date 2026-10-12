import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api, parametros } from '../api'
import BarraFiltros from '../componentes/BarraFiltros'
import { AvanceSegmentos, Kpis, TableroCarga } from '../componentes/Indicadores'
import TablaOrdenes from '../componentes/TablaOrdenes'
import { useEventosEnVivo } from '../useEventosEnVivo'
import type { Filtros, OpcionesFiltro, Orden, ResumenMonitor } from '../tipos'
import { FILTROS_VACIOS } from '../tipos'

// Respaldo por si se pierden los avisos en vivo; además recalcula lo que
// depende de la hora (días de retraso, alerta de 2 h).
const REFRESCO_MS = 5 * 60_000

const CLAVE_FILTROS = 'monitor.filtros.v2'
const SIN_ORDENES: Orden[] = []

type Pestana = 'pendientes' | 'cerradas_hoy' | 'carga' | 'avance'

function filtrosGuardados(): Filtros {
  try {
    const guardados = localStorage.getItem(CLAVE_FILTROS)
    return guardados ? { ...FILTROS_VACIOS, ...JSON.parse(guardados) } : FILTROS_VACIOS
  } catch {
    return FILTROS_VACIOS
  }
}

export default function Monitor() {
  const [filtros, setFiltrosEstado] = useState<Filtros>(filtrosGuardados)
  const [pestana, setPestana] = useState<Pestana>('pendientes')
  const enVivo = useEventosEnVivo()

  const setFiltros = (f: Filtros) => {
    setFiltrosEstado(f)
    try {
      localStorage.setItem(CLAVE_FILTROS, JSON.stringify(f))
    } catch {
      // sin almacenamiento local (modo privado): los filtros no se recuerdan
    }
  }

  const vistaTabla = pestana === 'cerradas_hoy' ? 'cerradas_hoy' : 'pendientes'
  const resumen = useQuery({
    queryKey: ['monitor', 'resumen', filtros],
    queryFn: () => api<ResumenMonitor>(`/monitor/resumen${parametros(filtros)}`),
    refetchInterval: REFRESCO_MS,
    placeholderData: keepPreviousData,
  })
  const ordenes = useQuery({
    queryKey: ['monitor', 'ordenes', vistaTabla, filtros],
    queryFn: () => api<Orden[]>(`/monitor/ordenes${parametros(filtros, { vista: vistaTabla })}`),
    refetchInterval: REFRESCO_MS,
    placeholderData: keepPreviousData,
    enabled: pestana === 'pendientes' || pestana === 'cerradas_hoy',
  })
  const opciones = useQuery({
    queryKey: ['monitor', 'filtros'],
    queryFn: () => api<OpcionesFiltro>('/monitor/filtros'),
  })

  const r = resumen.data
  const pestanas: { valor: Pestana; texto: string; corto?: string; cuenta?: number }[] = [
    { valor: 'pendientes', texto: 'Pendientes', cuenta: r?.kpis.total_pendientes },
    { valor: 'cerradas_hoy', texto: 'Cerradas hoy', corto: 'Cerradas', cuenta: r?.kpis.cerradas_hoy },
    { valor: 'carga', texto: 'Carga' },
    { valor: 'avance', texto: 'Avance' },
  ]

  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-3">
        <h1 className="text-lg font-bold text-slate-900">Monitor en vivo</h1>
        <span
          className={`text-xs ${enVivo ? 'text-emerald-600' : 'text-slate-400'}`}
          title={enVivo ? 'Se actualiza solo cuando el robot trae datos nuevos' : 'Sin conexión en vivo: se actualiza cada 5 min'}
        >
          {enVivo ? '● En vivo' : '○ Cada 5 min'}
        </span>
      </div>

      <BarraFiltros
        filtros={filtros}
        opciones={opciones.data}
        conteos={r?.rapidos}
        alCambiar={setFiltros}
      />

      {resumen.error && (
        <p className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          No se pudo cargar el resumen: {resumen.error.message}
        </p>
      )}
      {r ? <Kpis kpis={r.kpis} /> : !resumen.error && <div className="tarjeta h-16 animate-pulse" />}

      <nav className="flex gap-1 overflow-x-auto border-b border-slate-200 text-sm font-medium">
        {pestanas.map((p) => (
          <button
            key={p.valor}
            onClick={() => setPestana(p.valor)}
            className={`-mb-px border-b-2 px-2 py-2 whitespace-nowrap sm:px-3 ${
              pestana === p.valor ? 'border-marca text-marca' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {p.corto ? (
              <>
                <span className="sm:hidden">{p.corto}</span>
                <span className="hidden sm:inline">{p.texto}</span>
              </>
            ) : (
              p.texto
            )}
            {p.cuenta !== undefined && <span className="ml-1.5 text-xs text-slate-400 tabular-nums">{p.cuenta}</span>}
          </button>
        ))}
      </nav>

      {(pestana === 'pendientes' || pestana === 'cerradas_hoy') && (
        <TablaOrdenes key={vistaTabla} vista={vistaTabla} ordenes={ordenes.data ?? SIN_ORDENES} cargando={ordenes.isPending} />
      )}
      {pestana === 'carga' && r && <TableroCarga resumen={r} />}
      {pestana === 'avance' && r && <AvanceSegmentos consolidado={r.consolidado} />}

      {r && r.estados_no_reconocidos.length > 0 && (
        <p className="text-xs text-amber-700">
          Estados que el monitor no reconoce (no cuentan como pendientes ni cerradas):{' '}
          {r.estados_no_reconocidos.map((e) => `${e.nombre} (${e.cantidad})`).join(', ')}. Avisa a soporte.
        </p>
      )}
    </div>
  )
}
