# ---- Stage 1: build the React SPA ----
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Django backend serving the built SPA ----
FROM python:3.12-slim AS backend
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps for psycopg / Pillow build wheels are bundled, but keep curl for
# healthchecks and ensure build tooling for any sdist fallbacks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Bring in the built SPA so WhiteNoise can serve it at the root.
COPY --from=frontend /frontend/dist ./frontend_dist

ENV DJANGO_SETTINGS_MODULE=config.settings
ENV PORT=8000
ENV DATA_DIR=/data

EXPOSE 8000

# Run migrations + collectstatic on boot, then serve with daphne (ASGI).
COPY backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
