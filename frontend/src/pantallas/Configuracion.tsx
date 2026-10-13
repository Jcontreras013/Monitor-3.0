import { useState } from 'react'

import ClientesVip from '../componentes/configuracion/ClientesVip'
import CorreoAlertas from '../componentes/configuracion/CorreoAlertas'
import { Pestanas } from '../componentes/ui'

type Pestana = 'vip' | 'correo'

export default function Configuracion() {
  const [pestana, setPestana] = useState<Pestana>('vip')
  return (
    <div className="space-y-3">
      <h1 className="text-lg font-bold text-slate-900">Configuración</h1>
      <Pestanas
        valor={pestana}
        alCambiar={setPestana}
        opciones={[
          { valor: 'vip', texto: 'Clientes VIP' },
          { valor: 'correo', texto: 'Correo de alertas' },
        ]}
      />
      {pestana === 'vip' ? <ClientesVip /> : <CorreoAlertas />}
    </div>
  )
}
