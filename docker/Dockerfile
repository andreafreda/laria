# LARIA standalone image: builds the Angular UI, then serves it together with
# the JSON API from the core. Build from the repo root so it sees core/ and ui/:
#   docker build -f docker/Dockerfile -t laria:dev .

# Stage 1: build the Angular/Ionic UI into static files.
FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# Stage 2: the runtime image (Python core + the built UI).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LARIA_DATA_DIR=/data \
    LARIA_DB_PATH=/data/laria.db \
    LARIA_UI_DIR=/app/ui \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8080

WORKDIR /app

# Install the core package and its runtime dependencies.
COPY core/ /app/core/
RUN pip install ./core

# Bring in the built UI; the core serves it (see web.app._serve_ui).
COPY --from=ui /ui/www /app/ui

# Run as a non-root user; the SQLite database lives in /data, a mounted volume.
RUN useradd --create-home laria && mkdir -p /data && chown laria /data
USER laria

EXPOSE 8080

# Liveness via the API's own health endpoint, no extra tools needed.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status == 200 else 1)"

CMD ["python", "-m", "laria.web"]
