import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

export type Modulo = {
  clave: string
  titulo: string
  ruta: string
  pantalla: LazyExoticComponent<ComponentType>
}

// Cada módulo se carga solo cuando se abre, para que la primera carga sea liviana.
export const MODULOS: Modulo[] = [
  { clave: 'monitor', titulo: 'Monitor', ruta: '/monitor', pantalla: lazy(() => import('./pantallas/Monitor')) },
  { clave: 'reprogramadas', titulo: 'Reprogramadas', ruta: '/reprogramadas', pantalla: lazy(() => import('./pantallas/Reprogramadas')) },
  { clave: 'calidad', titulo: 'Calidad', ruta: '/calidad', pantalla: lazy(() => import('./pantallas/Calidad')) },
  { clave: 'expedientes', titulo: 'Expedientes', ruta: '/expedientes', pantalla: lazy(() => import('./pantallas/Expedientes')) },
  { clave: 'configuracion', titulo: 'Configuración', ruta: '/configuracion', pantalla: lazy(() => import('./pantallas/Configuracion')) },
]

export const modulosDe = (claves: string[]) => MODULOS.filter((m) => claves.includes(m.clave))
