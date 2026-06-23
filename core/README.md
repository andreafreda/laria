# core

LARIA engine: provider-agnostic agentic LLM loop, module registry
(finance, food, agenda, news, web_search…), storage (repository pattern,
SQLite now → Postgres later), scheduler, messaging layer (Telegram…).

Decoupled from Home Assistant: runs on its own. HA features live in `connector-ha/`.

Bootstrap TODO: port the core from HARIA (`haria/app/`), abstracting the LLM provider and config.
