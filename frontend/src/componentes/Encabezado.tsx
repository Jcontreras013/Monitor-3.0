import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

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
  if (estado === null) {
    return <span className="text-xs text-amber-300">El robot de sincronización aún no ha reportado</span>
  }
  const problema = estado.atrasado || !estado.sync_ok
  const texto = estado.atrasado
    ? `Robot sin reportar desde ${haceCuanto(estado.ultimo_ciclo)}`
    : estado.sync_ok
      ? `Datos al día · ${haceCuanto(estado.ultima_sync_ok)}`
      : `Último ciclo sin datos nuevos · última sincronización ${haceCuanto(estado.ultima_sync_ok)}`
  return (
    <span
      title={estado.motivo || undefined}
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs ${
        problema ? 'bg-amber-400/15 text-amber-200' : 'bg-emerald-400/15 text-emerald-200'
      }`}
    >
      <span className={`size-2 rounded-full ${problema ? 'bg-amber-400' : 'bg-emerald-400'}`} />
      {texto}
    </span>
  )
}

export default function Encabezado({ usuario }: { usuario: Usuario }) {
  const clienteQuery = useQueryClient()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [cambiandoClave, setCambiandoClave] = useState(false)
  const salir = useMutation({
    mutationFn: () => enviar('/auth/logout'),
    onSettled: () => {
      clienteQuery.clear()
      clienteQuery.setQueryData(['yo'], null)
    },
  })

  return (
    <header className="sticky top-0 z-20 bg-tinta text-white shadow">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="rounded-md bg-white px-2 py-1">
            <img src="/logo-monitor.png" alt="Monitor Operativo" className="h-5" />
          </span>
          <span className="hidden text-xs text-slate-400 sm:inline">3.0</span>
        </div>
        <div className="order-3 w-full sm:order-none sm:w-auto sm:flex-1 sm:text-center">
          <IndicadorRobot />
        </div>
        <div className="relative ml-auto">
          <button className="boton text-slate-200 hover:bg-white/10" onClick={() => setMenuAbierto((v) => !v)}>
            {usuario.nombre || usuario.usuario}
            <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] uppercase">{usuario.rol}</span>
          </button>
          {menuAbierto && (
            <div
              className="absolute right-0 mt-2 w-48 overflow-hidden rounded-lg bg-white text-sm text-slate-700 shadow-lg"
              onMouseLeave={() => setMenuAbierto(false)}
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
