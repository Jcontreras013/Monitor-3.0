import { useState } from 'react'

import { etiquetasActivas } from '../filtros'
import type { Filtros, OpcionesFiltro, Rapido } from '../tipos'
import { FILTROS_VACIOS } from '../tipos'
import SelectorMultiple from './SelectorMultiple'

const RAPIDOS: { valor: Rapido; texto: string; activo: string }[] = [
  { valor: 'todas', texto: 'Todas', activo: 'bg-tinta text-white' },
  { valor: 'criticas', texto: 'Críticas', activo: 'bg-red-600 text-white' },
  { valor: 'no_asignadas', texto: 'No asignadas', activo: 'bg-amber-500 text-white' },
]

export default function BarraFiltros({
  filtros,
  opciones,
  conteos,
  alCambiar,
}: {
  filtros: Filtros
  opciones: OpcionesFiltro | undefined
  conteos: Record<Rapido, number> | undefined
  alCambiar: (f: Filtros) => void
}) {
  const etiquetas = etiquetasActivas(filtros)
  const avanzados = filtros.actividad.length + filtros.estado.length + filtros.motivo.length
  const [verMas, setVerMas] = useState(avanzados > 0)
  const poner = <K extends keyof Filtros>(clave: K, valor: Filtros[K]) => alCambiar({ ...filtros, [clave]: valor })
  const hayFiltros = etiquetas.length > 0 || filtros.rapido !== 'todas'

  return (
    <div className="tarjeta space-y-3 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex w-full gap-1 rounded-lg bg-slate-100 p-1 sm:w-auto" role="group" aria-label="Filtro rápido">
          {RAPIDOS.map((r) => {
            const activo = filtros.rapido === r.valor
            return (
              <button
                key={r.valor}
                aria-pressed={activo}
                onClick={() => poner('rapido', r.valor)}
                className={`flex-1 rounded-md px-2 py-1.5 text-sm font-medium whitespace-nowrap transition sm:flex-none sm:px-3 ${
                  activo ? r.activo : 'text-slate-600 hover:bg-white'
                }`}
              >
                {r.texto}
                {conteos && <span className={`ml-1.5 tabular-nums ${activo ? 'opacity-90' : 'text-slate-400'}`}>{conteos[r.valor]}</span>}
              </button>
            )
          })}
        </div>

        <select
          className="campo w-auto max-w-56 min-w-0 flex-1 py-1.5 sm:flex-none"
          value={filtros.tecnico}
          onChange={(e) => poner('tecnico', e.target.value)}
          aria-label="Técnico"
        >
          <option value="">Todos los técnicos</option>
          {(opciones?.tecnicos ?? []).map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>

        <button className="boton-secundario py-1.5" onClick={() => setVerMas((v) => !v)} aria-expanded={verMas}>
          Más filtros{avanzados ? ` (${avanzados})` : ''} <span className="text-slate-400">{verMas ? '▴' : '▾'}</span>
        </button>
      </div>

      {verMas && (
        <div className="grid gap-3 sm:grid-cols-3">
          <SelectorMultiple
            etiqueta="Actividad"
            textoTodas="Todas"
            opciones={opciones?.actividades ?? []}
            seleccion={filtros.actividad}
            alCambiar={(v) => poner('actividad', v)}
          />
          <SelectorMultiple
            etiqueta="Estado"
            textoTodas="Todos"
            opciones={opciones?.estados ?? []}
            seleccion={filtros.estado}
            alCambiar={(v) => poner('estado', v)}
          />
          <SelectorMultiple
            etiqueta="Motivo"
            textoTodas="Todos"
            opciones={opciones?.motivos ?? []}
            seleccion={filtros.motivo}
            alCambiar={(v) => poner('motivo', v)}
          />
        </div>
      )}

      {hayFiltros && (
        <div className="flex flex-wrap items-center gap-1.5 text-sm">
          {etiquetas.map((e) => (
            <span key={e.clave} className="inline-flex items-center gap-1 rounded-full bg-marca-suave py-0.5 pr-1 pl-2.5 text-blue-900">
              {e.texto}
              <button
                className="rounded-full px-1 text-blue-700 hover:bg-blue-200"
                onClick={() => alCambiar(e.quitar(filtros))}
                aria-label={`Quitar ${e.texto}`}
              >
                ×
              </button>
            </span>
          ))}
          <button className="ml-auto text-xs text-marca hover:underline" onClick={() => alCambiar(FILTROS_VACIOS)}>
            Quitar todos
          </button>
        </div>
      )}
    </div>
  )
}
