import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

/**
 * Escucha /api/eventos (Server-Sent Events). Cuando el robot guarda órdenes
 * nuevas, refresca el Monitor sin que el usuario recargue la página.
 * EventSource reconecta solo si se corta la conexión.
 */
export function useEventosEnVivo(): boolean {
  const clienteQuery = useQueryClient()
  const [conectado, setConectado] = useState(false)

  useEffect(() => {
    const fuente = new EventSource('/api/eventos')
    fuente.onopen = () => setConectado(true)
    fuente.onerror = () => setConectado(false)
    fuente.addEventListener('ordenes', () => {
      clienteQuery.invalidateQueries({ queryKey: ['monitor'] })
      clienteQuery.invalidateQueries({ queryKey: ['robot'] })
    })
    return () => fuente.close()
  }, [clienteQuery])

  return conectado
}
