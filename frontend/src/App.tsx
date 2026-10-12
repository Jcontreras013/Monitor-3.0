import { useQuery } from '@tanstack/react-query'

import { api, ErrorApi } from './api'
import Encabezado from './componentes/Encabezado'
import Login from './componentes/Login'
import Monitor from './pantallas/Monitor'
import type { Usuario } from './tipos'

async function cargarUsuario(): Promise<Usuario | null> {
  try {
    return await api<Usuario>('/auth/me')
  } catch (e) {
    if (e instanceof ErrorApi && e.status === 401) return null
    throw e
  }
}

export default function App() {
  const { data: usuario, isPending, error } = useQuery({
    queryKey: ['yo'],
    queryFn: cargarUsuario,
    staleTime: Infinity,
  })

  if (isPending) {
    return <div className="grid min-h-screen place-items-center text-slate-500">Cargando…</div>
  }
  if (error) {
    return (
      <div className="grid min-h-screen place-items-center p-4 text-center text-red-700">
        No se pudo conectar con el servidor. Revisa tu conexión y recarga la página.
      </div>
    )
  }
  if (!usuario) return <Login />

  return (
    <div className="min-h-screen">
      <Encabezado usuario={usuario} />
      <main className="mx-auto max-w-[1600px] px-4 py-4 sm:px-6">
        {usuario.rol === 'llamados' ? (
          <p className="tarjeta p-6 text-slate-600">
            Tu rol tiene acceso solo a Expedientes, que todavía no está migrado a esta versión.
          </p>
        ) : (
          <Monitor />
        )}
      </main>
    </div>
  )
}
