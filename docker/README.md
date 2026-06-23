# docker

Self-host deployment. `Dockerfile` (python-slim) to build the core + UI, plus a
`docker-compose.yml` with the app + (optional) MQTT broker + a `data/` volume.
Config via `.env`.

Bootstrap TODO: multi-stage Dockerfile (build Angular UI + core runtime), compose file.
