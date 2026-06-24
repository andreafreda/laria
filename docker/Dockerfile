# LARIA standalone image: installs the core package and serves the JSON API.
# Build from the repo root so the build can see core/:
#   docker build -f docker/Dockerfile -t laria:dev .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LARIA_DATA_DIR=/data \
    LARIA_DB_PATH=/data/laria.db \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8080

WORKDIR /app

# Install the core package and its runtime dependencies.
COPY core/ /app/core/
RUN pip install ./core

# Run as a non-root user; the SQLite database lives in /data, a mounted volume.
RUN useradd --create-home laria && mkdir -p /data && chown laria /data
USER laria

EXPOSE 8080

# Liveness via the API's own health endpoint, no extra tools needed.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status == 200 else 1)"

CMD ["python", "-m", "laria.web"]
