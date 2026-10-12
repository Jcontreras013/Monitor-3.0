import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api'
import Historial from '../componentes/expedientes/Historial'
import Repositorio from '../componentes/expedientes/Repositorio'
import { Pestanas } from '../componentes/ui'
import type { CatalogoExpedientes, Usuario } from '../tipos'

type Seccion = 'operaciones' | 'administrativo' | 'repositorio'

export default function Expedientes() {
  const usuario = useQueryClient().getQueryData<Usuario>(['yo'])
  const [seccion, setSeccion] = useState<Seccion>('operaciones')
  const catalogo = useQuery({
    queryKey: ['expedientes', 'catalogo'],
    queryFn: () => api<CatalogoExpedientes>('/expedientes/catalogo'),
    staleTime: 10 * 60_000,
  })

  const opciones: { valor: Seccion; texto: string }[] = [
    { valor: 'operaciones', texto: 'Operaciones' },
    { valor: 'administrativo', texto: 'Administrativo' },
    ...(usuario?.acceso_repositorio ? [{ valor: 'repositorio' as const, texto: 'Repositorio' }] : []),
  ]

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-bold text-slate-900">Expedientes</h1>
      <Pestanas opciones={opciones} valor={seccion} alCambiar={setSeccion} />
      {seccion === 'repositorio' ? (
        <Repositorio catalogo={catalogo.data} />
      ) : (
        <Historial
          key={seccion}
          seccion={seccion}
          catalogo={catalogo.data}
          esAdmin={usuario?.rol === 'admin'}
        />
      )}
    </div>
  )
}
