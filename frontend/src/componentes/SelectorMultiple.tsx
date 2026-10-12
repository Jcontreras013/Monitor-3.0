import { useEffect, useRef, useState } from 'react'

export default function SelectorMultiple({
  etiqueta,
  opciones,
  seleccion,
  alCambiar,
  textoTodas,
}: {
  etiqueta: string
  opciones: string[]
  seleccion: string[]
  alCambiar: (valores: string[]) => void
  textoTodas: string
}) {
  const [abierto, setAbierto] = useState(false)
  const contenedor = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!abierto) return
    const alClic = (e: MouseEvent) => {
      if (!contenedor.current?.contains(e.target as Node)) setAbierto(false)
    }
    document.addEventListener('mousedown', alClic)
    return () => document.removeEventListener('mousedown', alClic)
  }, [abierto])

  const alternar = (valor: string) =>
    alCambiar(seleccion.includes(valor) ? seleccion.filter((v) => v !== valor) : [...seleccion, valor])

  const resumen =
    seleccion.length === 0 ? textoTodas : seleccion.length === 1 ? seleccion[0] : `${seleccion.length} seleccionados`

  return (
    <div className="relative space-y-1" ref={contenedor}>
      <span className="etiqueta">{etiqueta}</span>
      <button
        type="button"
        className={`campo flex items-center justify-between text-left ${seleccion.length ? 'border-marca' : ''}`}
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
      >
        <span className="truncate">{resumen}</span>
        <span className="text-slate-400">▾</span>
      </button>
      {abierto && (
        <div className="absolute z-30 mt-1 max-h-72 w-full min-w-56 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {seleccion.length > 0 && (
            <button className="w-full px-3 py-1.5 text-left text-xs text-marca hover:bg-slate-50" onClick={() => alCambiar([])}>
              Quitar selección
            </button>
          )}
          {opciones.length === 0 && <p className="px-3 py-2 text-sm text-slate-400">Sin opciones</p>}
          {opciones.map((opcion) => (
            <label key={opcion} className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm hover:bg-slate-50">
              <input
                type="checkbox"
                className="accent-marca"
                checked={seleccion.includes(opcion)}
                onChange={() => alternar(opcion)}
              />
              {opcion}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
