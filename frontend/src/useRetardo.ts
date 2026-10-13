import { useEffect, useState } from 'react'

/** El valor, pero solo después de que deja de cambiar por `ms` (para no buscar en cada tecla). */
export function useRetardo<T>(valor: T, ms = 300): T {
  const [retrasado, setRetrasado] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setRetrasado(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return retrasado
}
