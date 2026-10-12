import { useEffect, type ReactNode } from 'react'

export default function Modal({
  titulo,
  alCerrar,
  children,
  ancho = 'max-w-md',
}: {
  titulo: string
  alCerrar: () => void
  children: ReactNode
  ancho?: string
}) {
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => e.key === 'Escape' && alCerrar()
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [alCerrar])

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={alCerrar}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        className={`max-h-[90vh] w-full ${ancho} overflow-y-auto rounded-xl bg-white text-slate-800 shadow-2xl`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h2 className="font-semibold">{titulo}</h2>
          <button className="rounded p-1 text-slate-400 hover:bg-slate-100" onClick={alCerrar} aria-label="Cerrar">
            ✕
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}
