import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api, consulta } from '../../api'
import type { CierreDiario as Datos } from '../../tipos'
import { AvanceSegmentos } from '../Indicadores'
import TablaOrdenes from '../TablaOrdenes'
import { Aviso, Barras, Dato, Descarga, Segmentado } from '../ui'
import { hoyHN } from './fechas'

type Vista = 'resumen' | 'eficiencia' | 'primera' | 'detalle'

export default function CierreDiario() {
  const [fecha, setFecha] = useState(hoyHN())
  const [vista, setVista] = useState<Vista>('resumen')
  const q = consulta({ fecha })
  const datos = useQuery({
    queryKey: ['monitor', 'reportes', 'cierre', fecha],
    queryFn: () => api<Datos>(`/reportes/cierre${q}`),
    placeholderData: keepPreviousData,
  })
  const d = datos.data
  const global = d?.avance.find((a) => a.segmento === 'GLOBAL')

  return (
    <div className="space-y-3">
      <div className="tarjeta flex flex-wrap items-end gap-2 p-3">
        <label className="space-y-1">
          <span className="etiqueta">Jornada</span>
          <input type="date" className="campo py-1.5" value={fecha} max={hoyHN()} onChange={(e) => e.target.value && setFecha(e.target.value)} />
        </label>
        <div className="ml-auto flex flex-wrap gap-2">
          <Descarga href={`/api/reportes/cierre.pdf${q}`}>PDF cierre diario</Descarga>
          <Descarga href={`/api/reportes/cerradas.pdf${q}`}>PDF cerradas por hora</Descarga>
          <Descarga href={`/api/reportes/primera-orden.pdf${q}`}>PDF primera orden</Descarga>
        </div>
      </div>
      {datos.error && <Aviso tipo="error">{datos.error.message}</Aviso>}

      {d && (
        <>
          <section className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Dato titulo="Órdenes cerradas" valor={d.total_cerradas} />
            <Dato titulo="Técnicos con cierres" valor={d.eficiencia.length} color="border-l-emerald-500" />
            <Dato titulo="Avance global" valor={global?.total ? `${Math.round(global.porcentaje)}%` : '—'} color="border-l-amber-500" />
            <Dato titulo="Avance de mora" valor={global?.mora_total ? `${Math.round(global.mora_porcentaje)}%` : '—'} color="border-l-red-500" />
          </section>

          <Segmentado
            etiqueta="Sección"
            valor={vista}
            alCambiar={setVista}
            opciones={[
              { valor: 'resumen', texto: 'Resumen' },
              { valor: 'eficiencia', texto: 'Eficiencia' },
              { valor: 'primera', texto: 'Primera orden' },
              { valor: 'detalle', texto: `Cerradas (${d.total_cerradas})` },
            ]}
          />

          {vista === 'resumen' && (
            <>
              <AvanceSegmentos consolidado={d.avance} />
              <p className="text-xs text-slate-500">Cerradas de la jornada frente a las pendientes asignadas de este momento.</p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Barras titulo="Soporte" filas={d.produccion.sop} color="bg-red-500" />
                <Barras titulo="Instalaciones" filas={d.produccion.instalaciones} color="bg-blue-500" />
                <Barras titulo="PLEX" filas={d.produccion.plex} color="bg-orange-500" />
                <Barras titulo="Otros" filas={d.produccion.otros} color="bg-slate-400" />
              </div>
            </>
          )}

          {vista === 'eficiencia' && (
            <div className="tarjeta overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                  <tr><th className="px-3 py-2 text-left">Técnico</th><th className="px-2">INS</th><th className="px-2">SOP</th><th className="px-2">OTR</th><th className="px-2">Puntos</th><th className="px-2">Bono</th><th className="px-3">Logro</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-center tabular-nums">
                  {d.eficiencia.map((t) => (
                    <tr key={t.tecnico}>
                      <td className="px-3 py-1.5 text-left">{t.tecnico}</td><td>{t.ins}</td><td>{t.sop}</td><td>{t.otr}</td>
                      <td>{t.puntos_base.toFixed(1)}%</td><td>+{t.bono_mixto.toFixed(0)}%</td>
                      <td className={`px-3 font-bold ${t.logro_final >= 100 ? 'text-emerald-700' : t.logro_final >= 60 ? 'text-amber-700' : 'text-red-700'}`}>{t.logro_final.toFixed(1)}%</td>
                    </tr>
                  ))}
                  {!d.eficiencia.length && <tr><td colSpan={7} className="py-8 text-slate-400">Sin cierres en esta jornada.</td></tr>}
                </tbody>
              </table>
              <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
                Meta diaria = 100 %. PEXTERNO 100 %; instalación nueva / PLEX 25 %; adición, cambio, recuperado y soporte 12,5 %. +10 % si hizo más de un tipo de orden.
              </p>
            </div>
          )}

          {vista === 'primera' && (
            <div className="tarjeta overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                  <tr><th className="px-3 py-2">Técnico</th><th className="px-3 py-2">Inicio</th><th className="px-3 py-2">Orden</th><th className="px-3 py-2">Actividad</th><th className="px-3 py-2">Colonia</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {d.primera_orden.map((p) => (
                    <tr key={p.tecnico}>
                      <td className="px-3 py-1.5">{p.tecnico}</td><td className="px-3 font-mono">{p.hora_ini.slice(11, 16)}</td>
                      <td className="px-3 font-mono">{p.num}</td><td className="px-3">{p.actividad}</td><td className="px-3">{p.colonia ?? '—'}</td>
                    </tr>
                  ))}
                  {!d.primera_orden.length && <tr><td colSpan={5} className="py-8 text-center text-slate-400">No hay órdenes iniciadas en esta fecha.</td></tr>}
                </tbody>
              </table>
            </div>
          )}

          {vista === 'detalle' && (
            <TablaOrdenes key={fecha} vista="cerradas_hoy" ordenes={d.cerradas} cargando={datos.isFetching} vacio="No hay órdenes cerradas en esta jornada." />
          )}
        </>
      )}
    </div>
  )
}
