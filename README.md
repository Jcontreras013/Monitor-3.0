# Monitor Operativo 3.0 · MAXCOM

Reescritura de [monitor-operativo](https://github.com/Jcontreras013/monitor-operativo) (Streamlit + Google Sheets) con **FastAPI + React + PostgreSQL**. Se migra por fases, con el sistema anterior funcionando en paralelo hasta que los números cuadren.

## Por qué el cambio

| Problema en el sistema anterior | Cómo se resuelve aquí |
|---|---|
| Google Sheets como base de datos: el robot reescribía las 26 mil+ filas de `Sheet1` cada 15 min, por lotes y con errores 503 de Google. Si un ciclo no traía una columna (OLT/PON), la columna desaparecía. | **PostgreSQL**. El robot solo escribe las órdenes nuevas o que cambiaron (huella del contenido): un ciclo normal tarda ~1 s. Las columnas que Cepheus agregue quedan en `datos` (JSONB), así que nunca se pierden. |
| Dos fuentes de verdad (Sheets + espejo CSV en GCS) y lógica para decidir cuál estaba más al día. | Una sola base de datos. |
| Streamlit vuelve a ejecutar las 5,500 líneas de `app.py` en cada clic. Cada usuario descargaba la hoja completa y la limpiaba con pandas en su propia sesión. | La limpieza se hace **una vez**, al guardar. La API responde el resumen del Monitor en menos de 100 ms con ~5 mil órdenes activas. |
| Refresco cada 10 min por usuario, con `time.sleep()` en la interfaz. | **Actualización en vivo**: el robot avisa a Postgres (`NOTIFY`) y la API lo reenvía a cada navegador (Server-Sent Events). |
| Reglas copiadas que ya se habían desincronizado: `PATRON_ASIGNADAS_VIVA_STR` tenía 14 estados en `app.py` y 10 en `tools.py`, y `ACTIVIDADES_BASURA` tenía 7 entradas en uno y 5 en el otro. | Una sola fuente: [`backend/app/dominio/constantes.py`](backend/app/dominio/constantes.py). |
| Robot y bot sostenidos con bucles `.bat`/`.vbs`. | Servicio de Windows (NSSM) o contenedor Docker con reinicio automático. |
| Usuarios y contraseñas en `secrets.toml`; los cambios de contraseña iban a una hoja aparte. | Tabla `usuarios` con argon2, sesión en cookie httpOnly que vence a los 30 min de inactividad, bloqueo tras 5 intentos fallidos, y cambio de contraseña que cierra las otras sesiones. |

## Arquitectura

```
  Red interna MAXCOM                          Nube
 ┌──────────────────────┐            ┌──────────────────────────────┐
 │ API Cepheus          │            │ PostgreSQL (Supabase / Neon / │
 │   ▲                  │            │ propio)                       │
 │   │ cada 15 min      │  upsert +  │   ▲            │ NOTIFY        │
 │ ┌─┴────────────────┐ │  NOTIFY    │   │            ▼               │
 │ │ Robot            ├─┼───────────►│ ┌─┴──────────────────────────┐│
 │ │ worker/sync.py   │ │            │ │ API FastAPI (app/)          ││
 │ └──────────────────┘ │            │ │  + frontend React (dist/)   ││
 └──────────────────────┘            │ └─────────────┬──────────────┘│
                                     └───────────────┼───────────────┘
                                                     │ HTTPS + SSE
                                              navegador / celular
```

- **El robot** debe correr dentro de la red de MAXCOM, porque es la única que alcanza Cepheus. Es el mismo código del backend con otro comando.
- **La API sirve también el frontend**: es una sola URL y un solo despliegue, sin CORS.
- La lógica de negocio vive en `backend/app/dominio/`. Es Python puro, sin base de datos, y está probada aparte: clasificador, normalización, offline, motivo, segmento, día operativo e indicadores del Monitor.

## Stack

| Capa | Tecnología |
|---|---|
| Base de datos | PostgreSQL 16, migraciones con Alembic |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async) + asyncpg, Pydantic v2, `uv` |
| Robot | El mismo backend: `python -m worker.sync` (httpx) |
| Frontend | React 19 + TypeScript, Vite, TanStack Query, Tailwind CSS 4 |
| Calidad | pytest (con Postgres real), Ruff, oxlint, GitHub Actions |
| Despliegue | Una imagen Docker (API + frontend; el robot usa la misma imagen) |

## Estado de la migración

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Repositorio, PostgreSQL, migraciones, CI, Docker | ✅ |
| 1 | Robot Cepheus → Postgres e importación del historial de Sheets | ✅ |
| 2 | Login, roles, Monitor en vivo (filtros rápidos con conteo, KPIs, pestañas de pendientes / cerradas / carga / avance, detalle de orden y CSV) | ✅ |
| 3 | Expedientes (faltas, análisis, resumen del mes, repositorio, PDF y formulario oficial en Word) y Control de Calidad (llamadas, cierres INSFIBRA, auditorías de campo, histórico con CSAT y PDF; las auditorías de fibra deficientes pasan a Expedientes) | ✅ |
| 4 | Centro de Reportes (PDF/Excel), Reprogramadas / No instalados, Gantt | Pendiente |
| 5 | Bot de Telegram y alertas por correo (VIP, molex) | Pendiente |
| 6 | Auditoría de vehículos, tiempos de técnicos, materiales, IA (`ia.py`), configuración | Pendiente |

Del Monitor anterior todavía faltan: el Gantt, el panel de clientes VIP, las órdenes manuales, el filtro de técnicos contra el catálogo de técnicos principales y el PDF de órdenes totales (por ahora hay exportación a CSV).

## Desarrollo local

Requisitos: Python 3.12 con [uv](https://docs.astral.sh/uv/), Node 22 con pnpm, y PostgreSQL 16. Para la base de datos basta con `docker compose up db`.

```bash
# Backend
cd backend
cp .env.example .env            # poner DATABASE_URL, ENTORNO=desarrollo y COOKIE_SEGURA=false
uv sync
uv run alembic upgrade head
uv run python -m scripts.datos_demo     # usuario demo / demo-monitor + 400 órdenes inventadas
uv run uvicorn app.main:app --reload    # http://localhost:8000/docs

# Frontend (en otra terminal)
cd frontend
pnpm install
pnpm dev                                 # http://localhost:5173 (pasa /api al backend)
```

Todo junto en contenedores: `docker compose up --build` y luego `docker compose exec api python -m scripts.usuarios crear TU_USUARIO --rol admin`.

### Pruebas

```bash
cd backend
uv run ruff check .
TEST_DATABASE_URL=postgresql://monitor:monitor@localhost:5432/monitor_test uv run pytest
```

Las pruebas de dominio corren sin base de datos. Las de API y robot usan un Postgres real (`TEST_DATABASE_URL`), aplican las migraciones de verdad y simulan Cepheus. Se omiten si esa variable no está definida. Incluyen las pruebas de regresión del clasificador del sistema anterior.

## Cómo pasar del sistema anterior a este

1. **Crear la base de datos.** Recomiendo Supabase o Neon (PostgreSQL administrado con respaldos). Usa la cadena de conexión **directa o en modo sesión** (puerto 5432): el modo transacción (6543) no admite el `LISTEN` de las actualizaciones en vivo.
2. **Desplegar la API** con el `Dockerfile` en Railway, Render, Fly.io o un VPS. Variables: `DATABASE_URL`, `JWT_SECRET` (`openssl rand -hex 32`) y `COOKIE_SEGURA=true`. Al arrancar aplica las migraciones sola.
3. **Pasar los usuarios** del `secrets.toml` actual, con su contraseña y rol:
   `python -m scripts.usuarios importar ruta/.streamlit/secrets.toml`
   Las contraseñas que se cambiaron desde la app anterior (hoja `Usuarios_Claves`) no se pueden leer. A esos usuarios se les crea una nueva con `python -m scripts.usuarios crear USUARIO --rol ROL`.
4. **Importar el historial**: descarga como CSV las pestañas de la base de datos de Google Sheets (`Sheet1`, `FTTX`, `Expedientes`, `Calidad`, `Operaciones`, `Instalaciones`, `Auditoria_Fibra`) y corre
   ```
   python -m scripts.importar_historial Sheet1.csv --fttx FTTX.csv \
       --expedientes Expedientes.csv \
       --personal-tecnico personal_tecnico.txt --personal-sac personal_sac.txt \
       --calidad Calidad.csv --auditoria-operaciones Operaciones.csv \
       --auditoria-instalaciones Instalaciones.csv --auditoria-fibra Auditoria_Fibra.csv
   ```
   Cada opción es independiente. Hazlo **antes** de arrancar el robot nuevo. Se puede repetir sin duplicar nada. Las fotos viejas (Catbox/Drive) quedan como enlaces; las nuevas se guardan en la base de datos.
5. **Instalar el robot** en la PC de MAXCOM (ver abajo). Durante la prueba en paralelo, ten en cuenta el límite de **5 consultas por hora** de Cepheus: dos robots cada 15 min suman 8. Lo recomendable es subir ambos a 25–30 min (`SYNC_INTERVALO_MINUTOS=30`) o apagar el viejo.
6. **Comparar** los indicadores del Monitor de ambos sistemas durante unos días. Las reglas se portaron sin cambios, así que deben coincidir, salvo por las correcciones descritas abajo.
7. Apagar `sync_job.py` y la app de Streamlit cuando todos los módulos que se usen estén migrados.

### Robot en Windows (PC de MAXCOM)

```powershell
# 1. Instalar uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# 2. Código y dependencias
git clone https://github.com/Jcontreras013/Monitor-3.0 C:\Maxcom\Monitor-3.0
cd C:\Maxcom\Monitor-3.0\backend
uv sync --no-dev
copy .env.example .env    # DATABASE_URL (la misma de la API) y CEPHEUS_*
# 3. Probar un ciclo
uv run python -m worker.sync --una-vez
# 4. Dejarlo como servicio de Windows con NSSM (https://nssm.cc): arranca con
#    Windows, sin ventana, y se reinicia solo si se cae (espera 5 min por el
#    límite de consultas de Cepheus)
nssm install MonitorRobot C:\Maxcom\Monitor-3.0\backend\.venv\Scripts\python.exe -m worker.sync
nssm set MonitorRobot AppDirectory C:\Maxcom\Monitor-3.0\backend
nssm set MonitorRobot AppStdout C:\Maxcom\Monitor-3.0\backend\robot.log
nssm set MonitorRobot AppStderr C:\Maxcom\Monitor-3.0\backend\robot.log
nssm set MonitorRobot AppRestartDelay 300000
nssm start MonitorRobot
```

Para traer historial más viejo una sola vez: `uv run python -m worker.sync --backfill 60` (Cepheus no acepta más de ~60 días). El estado de cada ciclo queda en la tabla `estado_robot`, y la app avisa en el encabezado si el robot deja de reportar.

## Diferencias con el sistema anterior (a propósito)

- **Listas unificadas**: se usa la versión completa de los estados vivos (14) y de las actividades basura (7). Antes, una orden `ABIERTA` contaba como pendiente en el Monitor pero el robot la trataba como terminada.
- **Órdenes que dejan de venir de Cepheus**: antes desaparecían de `Sheet1`. Ahora se marcan `vigente = false`, dejan de contar como pendientes y no se borran. Si vuelven a aparecer, vuelven a contar.
- **Sin catálogo FTTX el ciclo sigue**: antes se abortaba. El vehículo (MX) solo se completa si el catálogo existe.
- **"Cerradas hoy" se mantiene igual**: a `HORA_LIQ` se le restan 6 h y se compara con la fecha de hoy. Entre las 00:00 y las 06:00 eso da 0 cerradas del "día nuevo", aunque operativamente sigue la jornada anterior. Se dejó igual para que los números cuadren en la comparación; conviene decidir si se pasa a día operativo completo.
- **Ventana del Monitor**: se cargan las órdenes vivas y las abiertas o cerradas en los últimos 7 días. Ya no entran las órdenes viejas sin hora de liquidación, que solo afectaban el aviso de "estados no reconocidos".
- **Filtros rápidos exclusivos**: Todas / Críticas / No asignadas son botones con su conteo y se elige uno a la vez. Antes eran dos interruptores que se podían combinar ("críticas sin técnico"). Actividad, estado, motivo y técnico sí se combinan con cualquiera de los tres.
- **Contraseñas**: cualquier rol puede cambiar la suya (antes solo admin y jefe), con un mínimo de 8 caracteres.
- **Archivos**: las evidencias de Expedientes y las fotos de auditorías se guardan en Postgres (se valida que sean imagen o PDF de verdad) en lugar de Catbox/Drive, que eran públicos.
- **Permisos por módulo** en un solo lugar (`app/permisos.py`). El rol `llamados` solo ve Expedientes; las vistas de Calidad para `sac` y `miguel` se mantienen como antes.
- **Envío de encuestas por WhatsApp (WATI)**: no se migró. Los envíos viejos se importan como gestiones "Sin Gestión".

## Estructura

```
backend/
  app/
    dominio/          lógica de negocio pura (probada sin base de datos)
      constantes.py     estados, actividades permitidas/basura, umbrales
      clasificador.py   PLEX / SOP / Instalación (portado tal cual)
      normalizacion.py  orden cruda de Cepheus -> fila (offline, motivo, segmento...)
      monitor.py        KPIs, tablero de carga, avance por segmento
      fechas.py         hora de Honduras, día operativo, formatos de Cepheus
      nombres.py        cruce difuso de nombres (para Expedientes y Telegram)
      expedientes.py    gravedad, reincidencias, resumen del mes
      calidad.py        encuesta, CSAT, resultado de la gestión, diagnóstico
    api/              rutas: auth, monitor, robot, eventos (SSE), archivos, expedientes, calidad
    reportes/         PDF (HTML + WeasyPrint) y formulario oficial en Word
    models.py         tablas
    repositorio.py    upsert de órdenes, estado del robot
    main.py           app FastAPI (+ sirve el frontend)
  worker/             robot: cliente de Cepheus y ciclo de sincronización
  scripts/            usuarios, importación del historial, datos de demostración
  alembic/            migraciones
  tests/
frontend/src/
  modulos.tsx         menú: qué módulos ve cada usuario (lo decide la API)
  pantallas/          Monitor, Calidad, Expedientes
  componentes/        login, encabezado, filtros, indicadores, tabla de órdenes, calidad/, expedientes/
Dockerfile            imagen única (API + frontend; el robot usa la misma)
docker-compose.yml    Postgres + API (+ robot con --profile robot)
```
