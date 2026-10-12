import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { ErrorApi } from './api'
import App from './App'
import './index.css'

// Si cualquier llamada responde 401 (sesión vencida), se vuelve al login.
const alVencerSesion = (error: Error) => {
  if (error instanceof ErrorApi && error.status === 401) {
    clienteQuery.setQueryData(['yo'], null)
  }
}

const clienteQuery = new QueryClient({
  queryCache: new QueryCache({ onError: alVencerSesion }),
  mutationCache: new MutationCache({ onError: alVencerSesion }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (intentos, error) => !(error instanceof ErrorApi && error.status < 500) && intentos < 2,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={clienteQuery}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
