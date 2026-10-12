import type { Filtros, OpcionesFiltro } from '../tipos'
import { FILTROS_VACIOS } from '../tipos'
import SelectorMultiple from './SelectorMultiple'

function Interruptor({ activo, alCambiar, texto }: { activo: boolean; alCambiar: (v: boolean) => void; texto: string }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm select-none">
      <button
        type="button"
        role="switch"
        aria-checked={activo}
        onClick={() => alCambiar(!activo)}
        className={`relative h-5 w-9 rounded-full transition ${activo ? 'bg-red-500' : 'bg-slate-300'}`}
      >
        <span className={`absolute top-0.5 size-4 rounded-full bg-white shadow transition ${activo ? 'left-4.5' : 'left-0.5'}`} />
      </button>
      {texto}
    </label>
  )
}

export default function PanelFiltros({
  filtros,
  opciones,
  alCambiar,
}: {
  filtros: Filtros
  opciones: OpcionesFiltro | undefined
  alCambiar: (f: Filtros) => void
}) {
  const poner = <K extends keyof Filtros>(clave: K, valor: Filtros[K]) => alCambiar({ ...filtros, [clave]: valor })

  return (
    <div className="tarjeta grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-[repeat(4,minmax(0,1fr))_auto]">
      <SelectorMultiple
        etiqueta="Actividad"
        textoTodas="Todas las actividades"
        opciones={opciones?.actividades ?? []}
        seleccion={filtros.actividad}
        alCambiar={(v) => poner('actividad', v)}
      />
      <SelectorMultiple
        etiqueta="Estado"
        textoTodas="Todos los estados"
        opciones={opciones?.estados ?? []}
        seleccion={filtros.estado}
        alCambiar={(v) => poner('estado', v)}
      />
      <SelectorMultiple
        etiqueta="Motivo / diagnóstico"
        textoTodas="Todos los motivos"
        opciones={opciones?.motivos ?? []}
        seleccion={filtros.motivo}
        alCambiar={(v) => poner('motivo', v)}
      />
      <label className="space-y-1">
        <span className="etiqueta">Técnico</span>
        <select className="campo" value={filtros.tecnico} onChange={(e) => poner('tecnico', e.target.value)}>
          <option value="">Todos</option>
          {(opciones?.tecnicos ?? []).map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </label>
      <div className="flex flex-col justify-end gap-2">
        <Interruptor texto="Solo críticas" activo={filtros.solo_criticas} alCambiar={(v) => poner('solo_criticas', v)} />
        <Interruptor texto="No asignadas" activo={filtros.no_asignadas} alCambiar={(v) => poner('no_asignadas', v)} />
      </div>
      <div className="sm:col-span-2 lg:col-span-5">
        <button className="text-xs text-marca hover:underline" onClick={() => alCambiar(FILTROS_VACIOS)}>
          Limpiar filtros
        </button>
      </div>
    </div>
  )
}
