# Docker

Run LARIA as a standalone container: the core engine behind its JSON API.

## Quick start

```bash
# from the repo root
ANTHROPIC_API_KEY=sk-... docker compose -f docker/compose.yaml up --build
```

The image builds the Angular UI and serves it together with the API, so the app
is at `http://localhost:8080` (open it in a browser). The same origin also serves
the API:

```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"me","text":"how much did I spend this month?"}'
```

## Notes

- The SQLite database lives in the `laria-data` volume, so it survives restarts.
- Secrets stay out of the image. Pass `ANTHROPIC_API_KEY` (and other keys) via
  the environment or an `.env` file, never baked into the build.
- Build the image directly if you prefer:
  `docker build -f docker/Dockerfile -t laria:dev .` (run from the repo root).
- Configuration is environment-driven (see `.env.example`): `LLM_PROVIDER`,
  `LLM_MODEL`, `WEB_HOST`, `WEB_PORT`, `LARIA_DB_PATH`, and so on.
- The image ships the core API only. The Angular UI is built and served
  separately (see `ui/`); a combined image comes later.
