# Una sola imagen para todo: la API (que también sirve el frontend) y el
# robot de sincronización (mismo código, otro comando).

# --- 1. Build del frontend (React) ---------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /web
RUN npm install -g pnpm@10.28.0
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# --- 2. Backend (FastAPI) ------------------------------------------------------
FROM python:3.12-slim
# Librerías que WeasyPrint necesita para generar los PDF (texto y fuentes).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.11.32
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend_dist
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY --from=frontend /web/dist /app/frontend_dist
RUN useradd --system --uid 1001 monitor
USER monitor
EXPOSE 8000
# Aplica las migraciones pendientes y arranca la API. PORT lo fijan
# Railway/Render/Fly; si no, 8000.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
