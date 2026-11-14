FROM node:24-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 \
    AGRICOLIX_PRODUCCION=1 \
    COOKIE_SECURE=true \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1
COPY backend/requirements.txt backend/requirements_ia.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements_ia.txt
COPY backend/*.py backend/esquema.sql ./
COPY backend/ia/*.py ./ia/
COPY backend/migrations ./migrations
COPY --from=frontend /app/frontend/dist /app/frontend/dist
USER 10001
CMD ["sh", "-c", "exec uvicorn servidor:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
