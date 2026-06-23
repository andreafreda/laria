# LARIA

**L**ocal **A**ssistant **R**eactive **I**ntelligent **A**gent.

A self-hosted AI home assistant that runs as a standalone Docker app with its own web
interface. Home Assistant is an **optional** integration, not a dependency. Multi-LLM
(Anthropic first, then local backends like Ollama).

> Standalone fork of HARIA (a Home Assistant add-on). "Lar" = the Roman guardian spirit
> of the home; "IA" = artificial intelligence.

## Status
Bootstrap. See [docs/plan.md](docs/plan.md) for the full plan (in Italian).

## Layout (monorepo)
| Folder | Purpose |
|---|---|
| `core/` | engine: LLM providers, modules (finance, food, agenda, news…), storage, scheduler |
| `connector-ha/` | Home Assistant adapter over REST/WebSocket API (token), MQTT discovery, Lovelace export |
| `ui/` | web interface (Angular SPA) |
| `docker/` | Dockerfile, docker-compose, self-host deploy |
| `docs/` | plan and documentation |

## Principles
- **Decoupled core**: runs without Home Assistant. Config via env / `.env`.
- **Single source of truth** (core): the LARIA UI is full-featured and real-time; Lovelace
  is a reactive mirror fed via MQTT (existing dashboards keep working with no changes).
- **Multi-LLM**: universal provider layer (phase 1: Anthropic).
- **Secrets stay out of the repo**: `.env` / secret manager only.

## License
**PolyForm Noncommercial 1.0.0** — free for noncommercial use. Commercial use requires a
separate license: contact the author. See [LICENSE](LICENSE).
