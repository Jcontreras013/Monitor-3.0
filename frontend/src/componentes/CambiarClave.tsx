import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { enviar } from '../api'
import Modal from './Modal'

export default function CambiarClave({ alCerrar }: { alCerrar: () => void }) {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')
  const cambiar = useMutation({
    mutationFn: () => enviar('/auth/cambiar-clave', { clave_actual: actual, clave_nueva: nueva }),
  })
  const noCoinciden = repetida.length > 0 && nueva !== repetida

  const alEnviar = (e: FormEvent) => {
    e.preventDefault()
    if (!noCoinciden) cambiar.mutate()
  }

  return (
    <Modal titulo="Cambiar contraseña" alCerrar={alCerrar}>
      {cambiar.isSuccess ? (
        <div className="space-y-4">
          <p className="text-sm text-emerald-700">
            Listo. Las sesiones abiertas en otros dispositivos se cerraron.
          </p>
          <button className="boton-primario w-full" onClick={alCerrar}>
            Cerrar
          </button>
        </div>
      ) : (
        <form onSubmit={alEnviar} className="space-y-4">
          <input
            className="campo"
            type="password"
            placeholder="Contraseña actual"
            autoComplete="current-password"
            value={actual}
            onChange={(e) => setActual(e.target.value)}
            required
          />
          <input
            className="campo"
            type="password"
            placeholder="Nueva contraseña (mínimo 8 caracteres)"
            autoComplete="new-password"
            minLength={8}
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
            required
          />
          <input
            className="campo"
            type="password"
            placeholder="Repite la nueva contraseña"
            autoComplete="new-password"
            value={repetida}
            onChange={(e) => setRepetida(e.target.value)}
            required
          />
          {noCoinciden && <p className="text-sm text-red-600">Las contraseñas no coinciden.</p>}
          {cambiar.error && <p className="text-sm text-red-600">{cambiar.error.message}</p>}
          <button className="boton-primario w-full" disabled={cambiar.isPending || noCoinciden}>
            Guardar
          </button>
        </form>
      )}
    </Modal>
  )
}
