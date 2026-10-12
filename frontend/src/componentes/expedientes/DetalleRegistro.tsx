import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { borrar } from '../../api'
import type { RegistroExpediente } from '../../tipos'
import Modal from '../Modal'
import { COLOR_CLASIFICACION } from '../../estilos'

const fechaCorta = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`

export default function DetalleRegistro({
  registro,
  esAdmin,
  alCerrar,
}: {
  registro: RegistroExpediente
  esAdmin: boolean
  alCerrar: () => void
}) {
  const clienteQuery = useQueryClient()
  const [confirmar, setConfirmar] = useState(false)
  const eliminar = useMutation({
    mutationFn: () => borrar(`/expedientes/${registro.id}`),
    onSuccess: () => {
      clienteQuery.invalidateQueries({ queryKey: ['expedientes'] })
      alCerrar()
    },
  })
  const imagenes = registro.archivos.filter((a) => a.mime.startsWith('image/'))
  const otros = registro.archivos.filter((a) => !a.mime.startsWith('image/'))

  return (
    <Modal titulo={registro.colaborador} alCerrar={alCerrar} ancho="max-w-2xl">
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-xs font-bold ${COLOR_CLASIFICACION[registro.clasificacion]}`}>
            {registro.clasificacion}
          </span>
          <span className="font-semibold">{registro.tipo_falta}</span>
          <span className="text-slate-500">· {fechaCorta(registro.fecha_incidencia)}</span>
          {registro.area !== 'OPERACIONES' && <span className="text-slate-500">· {registro.area}</span>}
        </div>
        <p className="rounded-lg bg-slate-50 p-3 whitespace-pre-wrap">{registro.comentario}</p>
        <p className="text-xs text-slate-500">
          Registrado por {registro.supervisor || '—'} el{' '}
          {new Date(registro.fecha_registro).toLocaleString('es-HN', { timeZone: 'America/Tegucigalpa' })}
          {registro.origen === 'telegram' && ' desde Telegram'}
          {registro.origen === 'importado' && ' (importado del sistema anterior)'}
        </p>

        {imagenes.length > 0 && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {imagenes.map((a) => (
              <a key={a.id} href={`/api/archivos/${a.id}`} target="_blank" rel="noreferrer">
                <img src={`/api/archivos/${a.id}`} alt={a.nombre} className="h-32 w-full rounded-lg border border-slate-200 object-cover" />
              </a>
            ))}
          </div>
        )}
        {(otros.length > 0 || registro.urls_externas.length > 0) && (
          <ul className="space-y-1">
            {otros.map((a) => (
              <li key={a.id}>
                <a className="text-marca hover:underline" href={`/api/archivos/${a.id}`} target="_blank" rel="noreferrer">📄 {a.nombre}</a>
              </li>
            ))}
            {registro.urls_externas.map((u) => (
              <li key={u}>
                <a className="text-marca hover:underline" href={u} target="_blank" rel="noreferrer noopener">🔗 Evidencia del sistema anterior</a>
              </li>
            ))}
          </ul>
        )}
        {registro.archivos.length === 0 && registro.urls_externas.length === 0 && (
          <p className="text-xs text-slate-400">Sin evidencias adjuntas.</p>
        )}

        {esAdmin && (
          <div className="flex justify-end gap-2 border-t border-slate-200 pt-3">
            {eliminar.error && <p className="mr-auto text-red-600">{eliminar.error.message}</p>}
            {confirmar ? (
              <>
                <span className="self-center text-slate-600">¿Eliminar definitivamente?</span>
                <button className="boton-secundario" onClick={() => setConfirmar(false)}>No</button>
                <button className="boton bg-red-600 text-white hover:bg-red-700" disabled={eliminar.isPending} onClick={() => eliminar.mutate()}>
                  Sí, eliminar
                </button>
              </>
            ) : (
              <button className="boton text-red-700 hover:bg-red-50" onClick={() => setConfirmar(true)}>Eliminar registro</button>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
