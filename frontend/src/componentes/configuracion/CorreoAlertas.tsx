import { useMutation, useQuery } from '@tanstack/react-query'

import { api, enviar } from '../../api'
import { haceCuanto } from '../../formato'
import type { EstadoCorreo, EstadoRobot } from '../../tipos'
import { Aviso } from '../ui'

const ICONOS: Record<string, string> = {
  enviado: '✅', 'sin novedades': '➖', desactivado: '⛔', 'sin lista VIP': '⚠️', 'error al enviar': '❌', error: '❌',
}

function Lista({ titulo, valores }: { titulo: string; valores: string[] }) {
  return (
    <div>
      <dt className="etiqueta">{titulo}</dt>
      <dd>{valores.length ? valores.map((v) => <span key={v} className="block">{v}</span>) : '—'}</dd>
    </div>
  )
}

export default function CorreoAlertas() {
  const datos = useQuery({ queryKey: ['configuracion', 'correo'], queryFn: () => api<EstadoCorreo>('/configuracion/correo') })
  // Misma consulta que el encabezado: la API ya calcula si el robot está atrasado.
  const robot = useQuery({ queryKey: ['robot'], queryFn: () => api<EstadoRobot | null>('/robot/estado') })
  const prueba = useMutation({ mutationFn: () => enviar<{ destinatarios: string[]; nota: string | null }>('/configuracion/correo/prueba') })
  const d = datos.data
  if (datos.error) return <Aviso tipo="error">{datos.error.message}</Aviso>
  if (!d) return <div className="tarjeta h-40 animate-pulse" />

  const atrasado = robot.data?.atrasado ?? false

  return (
    <div className="space-y-3">
      <section className="tarjeta space-y-2 p-4">
        <h2 className="font-semibold text-slate-900">Último ciclo de alertas del robot</h2>
        <p className={`text-sm ${atrasado ? 'text-amber-700' : 'text-slate-500'}`}>
          Último ciclo del robot: {haceCuanto(robot.data?.ultimo_ciclo ?? null)}
          {atrasado && '. El robot parece detenido: no reporta desde hace más de dos ciclos.'}
        </p>
        {d.alertas.length ? (
          <ul className="space-y-1.5 text-sm">
            {d.alertas.map((a) => (
              <li key={a.alerta}>
                <span aria-hidden>{ICONOS[a.resultado] ?? '•'}</span> <strong>{a.alerta}:</strong> {a.resultado} — <span className="text-slate-600">{a.detalle}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">El robot todavía no reporta alertas: aparecen después de su primer ciclo con esta versión.</p>
        )}
      </section>

      <section className="tarjeta space-y-3 p-4">
        <div>
          <h2 className="font-semibold text-slate-900">Correo de esta app (botón de prueba)</h2>
          <p className="text-sm text-slate-500">
            Las alertas las envía el robot con las variables CORREO_* de la PC donde corre. Aquí se ven las de la app, que
            solo se usan para el correo de prueba. En el robot se prueba con <code>python -m worker.sync --probar-correo</code>.
          </p>
        </div>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="etiqueta">Servidor</dt><dd>{d.servidor ? `${d.servidor}:${d.puerto} (${d.modo})` : '—'}</dd></div>
          <div><dt className="etiqueta">Envía</dt><dd>{d.remitente || '—'}</dd></div>
          <div><dt className="etiqueta">Contraseña</dt><dd>{d.contrasena_configurada ? 'configurada' : '❌ falta'}</dd></div>
          <Lista titulo="Alertas de molex a" valores={d.destinatarios} />
          <Lista titulo="Avisos VIP a" valores={d.destinatarios_vip} />
        </dl>
        {d.falta && <Aviso>Falta configurar: {d.falta}.</Aviso>}
        {prueba.error && <Aviso tipo="error">{prueba.error.message}</Aviso>}
        {prueba.isSuccess && (
          <Aviso tipo="exito">
            Correo de prueba enviado a {prueba.data.destinatarios.length} destinatario(s). Revisen la bandeja (y el spam).
            {prueba.data.nota && ` Nota: ${prueba.data.nota}.`}
          </Aviso>
        )}
        <button className="boton-primario" disabled={!!d.falta || prueba.isPending} onClick={() => prueba.mutate()}>
          {prueba.isPending ? 'Enviando…' : 'Enviar correo de prueba'}
        </button>
      </section>
    </div>
  )
}
