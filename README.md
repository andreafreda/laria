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
- **Multi-LLM**: universal provider layer (Anthropic and OpenAI-compatible/Ollama).
- **Secrets stay out of the repo**: `.env` / secret manager only.

## Quickstart

Run the API with Docker (the SQLite database persists in a volume):

```bash
ANTHROPIC_API_KEY=sk-... docker compose -f docker/compose.yaml up --build
# then:
curl -X POST http://localhost:8080/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"me","text":"add a 12 euro grocery expense on my checking account"}'
```

Or run the core directly:

```bash
cd core && pip install -e ".[dev]"
python -m pytest -q                 # 65 offline tests
ANTHROPIC_API_KEY=sk-... python -m laria.web
```

Use a local model instead of Anthropic by setting `LLM_PROVIDER=ollama` (and
`LLM_MODEL` to an installed model). See `.env.example` for all settings.

## Status
Core backend works end to end: config, LLM providers (Anthropic and
OpenAI-compatible/Ollama), agent memory, storage (finance, food, utilities,
conversations), the agentic engine with domain tools, the optional Home Assistant
connector, a JSON API, and a Docker image. The Angular UI is next. See
[docs/plan.md](docs/plan.md) for the full plan (in Italian).

## License
**PolyForm Noncommercial 1.0.0**, free for noncommercial use. Commercial use requires a
separate license: contact the author. See [LICENSE](LICENSE).
