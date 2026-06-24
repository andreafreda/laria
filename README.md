# LARIA

**L**ocal **A**ssistant **R**eactive **I**ntelligent **A**gent.

A standalone, self-hosted AI assistant for your home and daily life. It runs as its own
Docker app with its own native web interface, no platform required to function.
Multi-LLM (Anthropic first, then local backends like Ollama).

> "Lar" = the Roman guardian spirit of the home; "IA" = artificial intelligence.

## What LARIA is

LARIA is a complete product on its own. Out of the box it gives you:

- A conversational AI agent (chat + tools) over a **native web app** and messaging
  channels (Telegram first).
- Built-in **modules**: household finance, food/nutrition, agenda & reminders, news,
  web search, with full data ownership in a local database.
- Its **own dashboards** (Angular SPA): charts, drill-down, interactive views. These are
  the real dashboards, rich and real-time over WebSocket.
- Pluggable **LLM providers** (cloud or fully local).

Nothing above needs Home Assistant, a hub, or any external platform.

## Home Assistant: an optional bonus, not a foundation

If you already run Home Assistant, LARIA can connect to it as an **add-on integration**
to do more:

- Read entities/states and send **remote commands** to your devices.
- React to home **events** in real time (event subscription).
- Mirror data into HA via **MQTT** so your existing Lovelace cards keep working, but the
  primary, full-featured dashboards live in LARIA's own app.

The HA connector is strictly **additive**. Disable it and LARIA loses none of its core
value, it simply stops talking to your home devices.

## Layout (monorepo)
| Folder | Purpose |
|---|---|
| `core/` | engine: LLM providers, modules (finance, food, agenda, news…), storage, scheduler, messaging |
| `ui/` | native web app (Angular SPA), the real dashboards |
| `connector-ha/` | **optional** Home Assistant integration: REST/WebSocket commands, event subscription, MQTT mirror |
| `docker/` | Dockerfile, docker-compose, self-host deploy |
| `docs/` | plan and documentation |

## Principles
- **Standalone first**: the core runs fully without Home Assistant. Config via env / `.env`.
- **Native app is the source of truth**: LARIA's UI owns the dashboards; HA/Lovelace is just
  an optional mirror fed via MQTT.
- **Integrations are additive**: HA (and future platforms) extend LARIA, never gate it.
- **Multi-LLM**: universal provider layer (phase 1: Anthropic).
- **Secrets stay out of the repo**: `.env` / secret manager only.

## Status
Bootstrap. See [docs/plan.md](docs/plan.md) for the full plan (in Italian).

## License
**PolyForm Noncommercial 1.0.0**, free for noncommercial use. Commercial use requires a
separate license: contact the author. See [LICENSE](LICENSE).
