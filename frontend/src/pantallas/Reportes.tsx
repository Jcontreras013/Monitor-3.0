import { useState } from 'react'

import Arranque from '../componentes/reportes/Arranque'
import CierreDiario from '../componentes/reportes/CierreDiario'
import PendientesDispatch from '../componentes/reportes/PendientesDispatch'
import { Pestanas } from '../componentes/ui'

type Pestana = 'cierre' | 'pendientes' | 'arranque'

export default function Reportes() {
  const [pestana, setPestana] = useState<Pestana>('cierre')
  return (
    <div className="space-y-3">
      <h1 className="text-lg font-bold text-slate-900">Centro de Reportes</h1>
      <Pestanas
        valor={pestana}
        alCambiar={setPestana}
        opciones={[
          { valor: 'cierre', texto: 'Cierre diario' },
          { valor: 'pendientes', texto: 'Pendientes (Dispatch)' },
          { valor: 'arranque', texto: 'Arranque de jornada' },
        ]}
      />
      {pestana === 'cierre' && <CierreDiario />}
      {pestana === 'pendientes' && <PendientesDispatch />}
      {pestana === 'arranque' && <Arranque />}
    </div>
  )
}
