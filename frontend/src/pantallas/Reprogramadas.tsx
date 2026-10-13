import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api'
import TablaOrdenes from '../componentes/TablaOrdenes'
import { Aviso, Pestanas } from '../componentes/ui'
import type { Reprogramadas as Datos } from '../tipos'

type Vista = 'reprogramadas' | 'no_instalados'

export default function Reprogramadas() {
  const [vista, setVista] = useState<Vista>('reprogramadas')
  // La clave empieza con 'monitor' para que se refresque sola cuando el robot guarda órdenes.
  const datos = useQuery({ queryKey: ['monitor', 'reprogramadas'], queryFn: () => api<Datos>('/reprogramadas') })
  const d = datos.data

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-bold text-slate-900">Reprogramadas y No instalados</h1>
      <Pestanas
        valor={vista}
        alCambiar={setVista}
        opciones={[
          { valor: 'reprogramadas', texto: 'Agendadas a futuro', cuenta: d?.reprogramadas.length },
          { valor: 'no_instalados', texto: 'NOINSTALADO hoy', cuenta: d?.no_instalados.length },
        ]}
      />
      <p className="text-sm text-slate-500">
        {vista === 'reprogramadas'
          ? 'Órdenes vivas cuya cita quedó para un día posterior a hoy.'
          : 'Órdenes asignadas que el técnico cerró hoy como NO INSTALADAS.'}
      </p>
      {datos.error && <Aviso tipo="error">{datos.error.message}</Aviso>}
      <TablaOrdenes
        key={vista}
        vista={vista}
        ordenes={(vista === 'reprogramadas' ? d?.reprogramadas : d?.no_instalados) ?? []}
        cargando={datos.isPending}
        vacio={vista === 'reprogramadas' ? 'No hay órdenes reprogramadas a fechas futuras.' : 'Hoy no hay órdenes cerradas como NOINSTALADO.'}
      />
    </div>
  )
}
