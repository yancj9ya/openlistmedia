FROM node:20-bookworm AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY backend/ ./backend/
COPY openlist_sdk/ ./openlist_sdk/
COPY config_loader.py ./
COPY tmdb_sdk.py ./
COPY serve_media_wall.py ./
COPY media_wall_builder.py ./
COPY media_wall_service.py ./
COPY README.md ./
COPY MEDIA_WALL.md ./
COPY media_wall_site/ ./media_wall_site/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["python", "-m", "backend.main"]
