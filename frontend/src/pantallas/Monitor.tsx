import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api, parametros } from '../api'
import { AvanceSegmentos, Kpis, TableroCarga } from '../componentes/Indicadores'
import PanelFiltros from '../componentes/PanelFiltros'
import TablaOrdenes from '../componentes/TablaOrdenes'
import { filtrosActivos } from '../filtros'
import { useEventosEnVivo } from '../useEventosEnVivo'
import type { Filtros, OpcionesFiltro, Orden, ResumenMonitor } from '../tipos'
import { FILTROS_VACIOS } from '../tipos'

// Respaldo por si se pierden los avisos en vivo; además recalcula lo que
// depende de la hora (días de retraso, alerta de 2 h).
const REFRESCO_MS = 5 * 60_000

const CLAVE_FILTROS = 'monitor.filtros'
const SIN_ORDENES: Orden[] = []

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
  const [vista, setVista] = useState<'pendientes' | 'cerradas_hoy'>('pendientes')
  const [verFiltros, setVerFiltros] = useState(false)
  const enVivo = useEventosEnVivo()

  const setFiltros = (f: Filtros) => {
    setFiltrosEstado(f)
    try {
      localStorage.setItem(CLAVE_FILTROS, JSON.stringify(f))
    } catch {
      // sin almacenamiento local (modo privado): los filtros no se recuerdan
    }
  }

  const resumen = useQuery({
    queryKey: ['monitor', 'resumen', filtros],
    queryFn: () => api<ResumenMonitor>(`/monitor/resumen${parametros(filtros)}`),
    refetchInterval: REFRESCO_MS,
    placeholderData: keepPreviousData,
  })
  const ordenes = useQuery({
    queryKey: ['monitor', 'ordenes', vista, filtros],
    queryFn: () => api<Orden[]>(`/monitor/ordenes${parametros(filtros, { vista })}`),
    refetchInterval: REFRESCO_MS,
    placeholderData: keepPreviousData,
  })
  const opciones = useQuery({
    queryKey: ['monitor', 'filtros'],
    queryFn: () => api<OpcionesFiltro>('/monitor/filtros'),
  })

  const activos = filtrosActivos(filtros)
  const r = resumen.data

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold text-slate-900">Monitor en vivo</h1>
        <span className={`text-xs ${enVivo ? 'text-emerald-600' : 'text-slate-400'}`}>
          {enVivo ? '● Actualización automática' : '○ Actualiza cada 5 min'}
        </span>
        <button className="boton-secundario ml-auto" onClick={() => setVerFiltros((v) => !v)}>
          Filtros{activos.length ? ` (${activos.length})` : ''}
        </button>
      </div>

      {verFiltros && <PanelFiltros filtros={filtros} opciones={opciones.data} alCambiar={setFiltros} />}

      {activos.length > 0 && r && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <strong>Hay filtros ocultando información:</strong> {activos.join(' · ')}. Se muestran{' '}
          <strong>{r.mostrando}</strong> de <strong>{r.total_base}</strong> órdenes.{' '}
          <button className="font-semibold underline" onClick={() => setFiltros(FILTROS_VACIOS)}>
            Quitar filtros
          </button>
        </div>
      )}

      {r && r.estados_no_reconocidos.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Hay órdenes con un estado que el monitor no reconoce (no cuentan como pendientes ni como cerradas):{' '}
          {r.estados_no_reconocidos.map((e) => `${e.nombre} (${e.cantidad})`).join(', ')}. Avisa a soporte para
          agregarlos.
        </div>
      )}

      {resumen.error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          No se pudo cargar el resumen: {resumen.error.message}
        </div>
      )}

      {r ? (
        <>
          <Kpis kpis={r.kpis} />
          <TableroCarga resumen={r} />
          <AvanceSegmentos consolidado={r.consolidado} />
        </>
      ) : (
        !resumen.error && <div className="tarjeta h-40 animate-pulse" />
      )}

      <div className="flex gap-1 rounded-lg bg-slate-200 p-1 text-sm font-medium sm:w-fit">
        {(['pendientes', 'cerradas_hoy'] as const).map((v) => (
          <button
            key={v}
            onClick={() => setVista(v)}
            className={`flex-1 rounded-md px-4 py-1.5 sm:flex-none ${vista === v ? 'bg-white shadow-sm' : 'text-slate-600'}`}
          >
            {v === 'pendientes' ? 'Pendientes' : 'Cerradas hoy'}
          </button>
        ))}
      </div>
      <TablaOrdenes key={vista} vista={vista} ordenes={ordenes.data ?? SIN_ORDENES} cargando={ordenes.isPending} />
    </div>
  )
}
