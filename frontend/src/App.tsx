import { useQuery } from '@tanstack/react-query'
import { Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { api, ErrorApi } from './api'
import Encabezado from './componentes/Encabezado'
import Login from './componentes/Login'
import { modulosDe } from './modulos'
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

  const modulos = modulosDe(usuario.modulos)
  return (
    <BrowserRouter>
      <div className="min-h-screen">
        <Encabezado usuario={usuario} modulos={modulos} />
        <main className="mx-auto max-w-[1600px] px-4 py-4 sm:px-6">
          <Suspense fallback={<div className="tarjeta h-40 animate-pulse" />}>
            <Routes>
              {modulos.map((m) => (
                <Route key={m.clave} path={`${m.ruta}/*`} element={<m.pantalla />} />
              ))}
              <Route
                path="*"
                element={
                  modulos.length ? (
                    <Navigate to={modulos[0].ruta} replace />
                  ) : (
                    <p className="tarjeta p-6 text-slate-600">Tu usuario no tiene módulos asignados.</p>
                  )
                }
              />
            </Routes>
          </Suspense>
        </main>
      </div>
    </BrowserRouter>
  )
}
