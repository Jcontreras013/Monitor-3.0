import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { api, enviar } from '../api'
import { haceCuanto } from '../formato'
import type { EstadoRobot, Usuario } from '../tipos'
import CambiarClave from './CambiarClave'

function IndicadorRobot() {
  const { data: estado } = useQuery({
    queryKey: ['robot'],
    queryFn: () => api<EstadoRobot | null>('/robot/estado'),
    refetchInterval: 60_000,
  })
  if (estado === undefined) return null
  const problema = !estado || estado.atrasado || !estado.sync_ok
  const corto = !estado ? 'Robot sin reportar' : estado.atrasado ? 'Robot detenido' : estado.sync_ok ? 'Datos al día' : 'Sin datos nuevos'
  const detalle = !estado
    ? 'El robot de sincronización aún no ha reportado ningún ciclo.'
    : `Último ciclo ${haceCuanto(estado.ultimo_ciclo)}. Última sincronización exitosa ${haceCuanto(estado.ultima_sync_ok)}.` +
      (estado.motivo ? ` Motivo: ${estado.motivo}` : '')
  return (
    <span
      title={detalle}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs whitespace-nowrap ${
        problema ? 'bg-amber-400/15 text-amber-200' : 'bg-emerald-400/15 text-emerald-200'
      }`}
    >
      <span className={`size-2 rounded-full ${problema ? 'bg-amber-400' : 'bg-emerald-400'}`} />
      {corto}
      {estado?.sync_ok && !estado.atrasado && (
        <span className="hidden opacity-70 sm:inline">· {haceCuanto(estado.ultima_sync_ok)}</span>
      )}
    </span>
  )
}

export default function Encabezado({ usuario }: { usuario: Usuario }) {
  const clienteQuery = useQueryClient()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [cambiandoClave, setCambiandoClave] = useState(false)
  const menu = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!menuAbierto) return
    const alClic = (e: MouseEvent) => {
      if (!menu.current?.contains(e.target as Node)) setMenuAbierto(false)
    }
    document.addEventListener('mousedown', alClic)
    return () => document.removeEventListener('mousedown', alClic)
  }, [menuAbierto])
  const salir = useMutation({
    mutationFn: () => enviar('/auth/logout'),
    onSettled: () => {
      clienteQuery.clear()
      clienteQuery.setQueryData(['yo'], null)
    },
  })

  return (
    <header className="sticky top-0 z-20 bg-tinta text-white shadow">
      <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-2.5 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="rounded-md bg-white px-2 py-1">
            <img src="/logo-monitor.png" alt="Monitor Operativo" className="h-5" />
          </span>
          <span className="hidden text-xs text-slate-400 sm:inline">3.0</span>
        </div>
        <IndicadorRobot />
        <div className="relative ml-auto" ref={menu}>
          <button className="boton text-slate-200 hover:bg-white/10" onClick={() => setMenuAbierto((v) => !v)}>
            <span className="max-w-32 truncate">{usuario.nombre || usuario.usuario}</span>
            <span className="hidden rounded bg-white/10 px-1.5 py-0.5 text-[10px] uppercase sm:inline">{usuario.rol}</span>
          </button>
          {menuAbierto && (
            <div
              className="absolute right-0 mt-2 w-48 overflow-hidden rounded-lg bg-white text-sm text-slate-700 shadow-lg"
            >
              <button
                className="block w-full px-4 py-2 text-left hover:bg-slate-50"
                onClick={() => {
                  setCambiandoClave(true)
                  setMenuAbierto(false)
                }}
              >
                Cambiar contraseña
              </button>
              <button className="block w-full px-4 py-2 text-left hover:bg-slate-50" onClick={() => salir.mutate()}>
                Salir
              </button>
            </div>
          )}
        </div>
      </div>
      {cambiandoClave && <CambiarClave alCerrar={() => setCambiandoClave(false)} />}
    </header>
  )
}
