import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { enviar } from '../api'
import type { Usuario } from '../tipos'

export default function Login() {
  const clienteQuery = useQueryClient()
  const [usuario, setUsuario] = useState('')
  const [clave, setClave] = useState('')
  const entrar = useMutation({
    mutationFn: () => enviar<Usuario>('/auth/login', { usuario, clave }),
    onSuccess: (datos) => clienteQuery.setQueryData(['yo'], datos),
  })

  const alEnviar = (e: FormEvent) => {
    e.preventDefault()
    entrar.mutate()
  }

  return (
    <div className="grid min-h-screen place-items-center bg-tinta p-4">
      <form onSubmit={alEnviar} className="w-full max-w-sm space-y-5 rounded-2xl bg-white p-8 shadow-xl">
        <img src="/logo-monitor.png" alt="Monitor Operativo" className="mx-auto h-8" />
        <p className="text-center text-sm text-slate-500">Ingresa con tu usuario de MAXCOM</p>
        <label className="block space-y-1">
          <span className="etiqueta">Usuario</span>
          <input
            className="campo"
            autoComplete="username"
            autoFocus
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            required
          />
        </label>
        <label className="block space-y-1">
          <span className="etiqueta">Contraseña</span>
          <input
            className="campo"
            type="password"
            autoComplete="current-password"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            required
          />
        </label>
        {entrar.error && <p className="text-sm text-red-600">{entrar.error.message}</p>}
        <button className="boton-primario w-full" disabled={entrar.isPending}>
          {entrar.isPending ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
