# LARIA — stato implementativo (dev notes)

> Doc interno (IT). Insieme a `plan.md` è la **fonte di verità**. Se la sessione si
> compatta, leggere QUESTO per riprendere col dettaglio tecnico. Aggiornare a ogni step.

Ultimo aggiornamento: port storage finance (`core/laria/storage/`) tradotto+de-personalizzato, 19 test verdi.

## Coordinate
- Repo LARIA: `C:\projects\laria` → github.com/andreafreda/laria (branch `main`).
- Repo HARIA sorgente (da cui si porta): `C:\projects\haria\haria\app` (addon HA, v0.3.3).
- Push: git già configurato (stesso account andreafreda). `gh` NON installato → repo GitHub
  creato a mano dall'utente; per nuovi repo serve crearli a mano o installare gh.

## Regole ferree
- **HARIA è READ-ONLY**: `C:\projects\haria` NON si tocca mai. È solo sorgente da cui
  leggere per portare il codice in LARIA. Resta in produzione com'è.
- **Glossario obbligatorio**: nomi EN in `docs/glossary.md` — usare quelli per ogni identificatore.
- **Repo pubblico** → ZERO segreti e ZERO dati personali nel codice/commit.
  - Segreti: solo `.env` (gitignored). HARIA ha token in chiaro in `configuration.yaml`/`config.py`: NON portarli.
  - Dati personali: HARIA `econ_def.py` contiene nomi reali (conti `postepay_andrea`, intestatari `andrea`/`marina`).
    NON copiarli: i conti/membri vanno resi **configurabili** (seed da config/UI, default generici/vuoti).
- **Lingua**: codice/README/commenti/commit/nomi-dominio in **inglese**; piani/docs interni in italiano.
  Esiste uno step di traduzione IT→EN quando si porta il codice HARIA (oggi IT). Glossario in `plan.md`.
- **Licenza**: PolyForm Noncommercial 1.0.0 (gratis non-commerciale, commerciale = a pagamento).

## Layout monorepo
```
core/         pacchetto Python `laria` (engine, moduli, storage, llm) + pyproject + tests
connector-ha/ integrazione HA opzionale (REST/WS, subscribe_events, MQTT mirror) — VUOTO (solo README)
ui/           Angular SPA (dashboard vere, config LLM) — VUOTO (solo README)
docker/       Dockerfile + compose — VUOTO (solo README)
docs/         plan.md (piano+tracker), dev-state.md (questo)
```

## Fatto finora — dettaglio file (core/)
- `pyproject.toml`: pkg `laria-core` v0.1.0, py>=3.11, deps anthropic/aiosqlite/aiohttp,
  extra dev pytest+pytest-asyncio, `asyncio_mode=auto`, testpaths=tests.
- `laria/__init__.py`: docstring + `__version__`.
- `laria/config.py`: config **env-based** (dataclass frozen). Singleton `get_settings()` /
  `reload_settings()` (test). Gruppi: `Settings` (data_dir, db_path, log_level, telegram_token,
  web_host/port) + `LLMSettings` (provider, model, max_tokens, anthropic_api_key, openai_api_key,
  ollama_base_url) + `HASettings` (enabled=false default, url, token, mqtt_*). Helpers `_env/_env_bool/_env_int`.
  Sostituisce `haria/app/config.py` (che leggeva /config/haria_options.json del Supervisor).
- `laria/llm/base.py`: tipi normalizzati `TextBlock`, `ToolUseBlock(id,name,input)`,
  `ToolResult(tool_use_id,content).to_message_block()`, `LLMResponse(blocks, stop_reason, raw)` con
  proprietà `.text` e `.tool_uses`. ABC `LLMProvider.generate(system, messages, tools, tool_choice,
  max_tokens, model) -> LLMResponse` + `supports_prompt_cache()`. Formato messaggi = Anthropic-like
  (role + content str|blocchi text/tool_use/tool_result); altri provider convertono internamente.
- `laria/llm/anthropic_provider.py`: `AnthropicProvider` (AsyncAnthropic). Mappa generate→messages.create,
  invia beta header `extended-cache-ttl-2025-04-11`, normalizza content→blocks. Richiede api_key.
- `laria/llm/registry.py`: `get_provider(settings)` → per ora solo 'anthropic' (import lazy), altrimenti ValueError.
- `laria/llm/__init__.py`: ri-esporta tipi + get_provider.
- `tests/test_config.py`, `tests/test_llm.py`: 5 test verdi. Run: `cd core && python -m pytest -q`.

## FATTO — storage finance (`core/laria/storage/`)
- `db.py`: foundation SQLite. `connect()` + `init_db()` da `get_settings().db_path` (no Supervisor, no `/config`). WAL+busy_timeout+foreign_keys. Crea dir, seed `DEFAULT_CATEGORIES` (EN generiche). `CATEGORY_TRANSFER="transfer"` (categoria sistema, esclusa dai report). Schema finance: `finance_accounts/transactions/categories/budgets/rules/goals`.
- `finance.py`: port completo di `memory/econ.py`, tradotto EN, **de-personalizzato** (niente MEMBRI/CONTI hardcoded; owner default 'family'; conti creati via `add_account`/config). API EN: accounts (list/get/add/update/delete), transactions (add/list/update/delete/get_balance), rules (add/delete/list/apply_rule/apply_rules), categories (list/normalize/rename/merge/delete), budgets (set/delete/list/get_budget_status), goals (set_goal/add_to_goal/get_goals/delete_goal), reports (expense_summary/monthly_trend/category_spending_year/years_with_data/monthly_category_matrix/recent_transactions/get_balances/balances_by_owner/reset_finance).
- `tests/test_finance.py`: 9 test su DB temp (LARIA_DB_PATH env + reload_settings). Totale 19 verdi.
- Differenze vs HARIA: droppata migrazione one-shot `deactivate_generic_conti` (cruft personale); `recent_transactions` usa chiavi piene (date/amount/category/description) non compatte d/i/c/n (vincolo MQTT non più valido).
- **Prossimo storage**: port food (`memory/food.py`→`storage/food.py`) + utilities (`bollette.py`→`storage/utilities.py`); poi conversation-store (history/notes/summary) — valutare se va in storage o resta separato dal MemoryBackend.

## Mappa sorgente HARIA → destinazione LARIA (per i prossimi port)
HARIA `haria/app/`:
- `memory/` (package: core/misc/food/bollette/econ + facade) → `core/laria/storage/` (de-personalizzare econ seed).
  - `core.py` init_db (schema completo), history/note/summary/FTS/entity_cache/mqtt_topics.
  - `econ.py` conti/transazioni/categorie/regole/budget/obiettivi/report/`spese_mensili_per_categoria`/`movimenti_recenti`.
  - `food.py` profili/pasti/piano/idratazione/spesa/dispensa. `bollette.py`. `misc.py` reminder/briefing/news/errorlog.
  - Stato condiviso: `DB_PATH` (→ da settings), `_FTS_OK`, costanti. Sottomoduli leggono `core.DB_PATH` a runtime.
- `claude_engine.py` → engine provider-agnostic: sostituire `client.messages.create` con `provider.generate(...)`,
  costruzione system/tools/messages resta simile; gestione respond/tool_result già robusta (round bugfix).
- `prompts.py` (testi IT → tradurre), `nutrition.py` (lookup OFF/USDA, dipende da memory+config),
  `econ_import.py` (parser estratti BancoPosta/Postepay — generico, ok), `*_def.py` (econ_def=DATI PERSONALI!, bollette_def, ).
- Canali/IO: `telegram_handler.py`, `notifier.py`, `webpanel.py` (aiohttp ingress → diventa web API REST/WS),
  `scheduler.py` (APScheduler), `mqtt_pub.py` + `ha_client.py` → confluiscono in `connector-ha/`.
- `main.py` orchestrazione.

## Memoria agente — DECISO (fase 1)
- Backend di partenza: **mem0** (Apache-2.0, Python, locale) **dietro wrapper nostro `MemoryBackend`** → cambio motore plug & play. L'engine parla solo al wrapper.
- Improvement dopo: motore proprio **L0-L3** (modello TencentDB/OpenHuman) su **sqlite-vec+FTS5**, come backend alternativo.
- Analisi completa: `design-memory.md` (architetture A-G, sistemi mercato pro/cons, storage §3c, ingestione/sharing da Mirage §3d, decisione §6bis). Handoff per sessione dedicata: `memory-engine-handoff.md`.
- **FATTO — scaffold wrapper** `core/laria/memory/`:
  - `types.py`: `Scope(household,user_id)` + `MemoryItem` (text/source/confidence/created_at/updated_at/metadata/score).
  - `base.py`: ABC `MemoryBackend` — write/recall/get/update/delete/forget. Unica dipendenza dell'engine.
  - `embedder.py`: ABC `Embedder` (default locale, fake nei test).
  - `fake.py`: `FakeBackend` in-memory (recall = overlap keyword), **scope isolation** (privati non emergono in scope altrui). Default per test/dev.
  - `mem0_backend.py`: `Mem0Backend` wrapper, import mem0 lazy (dep opzionale); Scope→`user_id` via `Scope.key()`.
  - `registry.py`: `get_memory_backend(settings)` → 'fake' | 'mem0'.
  - `config.py`: aggiunto `MemorySettings` (backend/embedder/embedder_model/store_path), default backend='fake'.
  - Test: `tests/test_memory.py` (registry default, write/recall, CRUD, scope isolation, forget). 10 test verdi totali.
- **Prossimo memoria**: (a) embedder locale reale (sentence-transformers/Ollama) + `LocalHybridBackend` sqlite-vec quando serve; (b) integrare `MemoryBackend` nell'engine quando si porta `claude_engine`.

## Note operative
- Skill `/handoff` (mattpocock) installata in `~/.claude/skills/handoff` ma NON ancora caricata dal harness in questa sessione (manca dalla lista). Riprovare dopo reload completo; per ora usare `memory-engine-handoff.md`.

## Prossimo step pianificato
**Port storage (memory→storage) de-personalizzato**: portare il package memory in `core/laria/storage/`,
`DB_PATH` da `get_settings().db_path`, e sostituire il seed conti/membri hardcoded (econ_def) con
config/seed generico (niente nomi). Poi portare i test economia adattati.

## Comandi utili
- Test core: `cd C:/projects/laria/core && python -m pytest -q`
- Commit/push: standard git; commit message in inglese; co-author Claude.
