# LARIA — stato implementativo (dev notes)

> Doc interno (IT). Insieme a `plan.md` è la **fonte di verità**. Se la sessione si
> compatta, leggere QUESTO per riprendere col dettaglio tecnico. Aggiornare a ogni step.

Ultimo aggiornamento: ENGINE provider-agnostic (`core/laria/engine/`), 38 test verdi.

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
- **FATTO food** `storage/food.py` (port `memory/food.py`): diet_profiles, weight_log, meals+meal_items (macro+micro denormalizzati), meal_plan, hydration_log, shopping_items, pantry_items, food_cache (TTL 90gg). Commenti EN, `member` free-text (no membri hardcoded). Schema `_FOOD_SCHEMA` in db.py.
- **FATTO utilities** `storage/utilities.py` (port `memory/bollette.py`): `utility_bills` (utility/metric/year/month/value). bolletta→bill: set_bill/set_bill_range/get_bill_csv/get_bill_existing_range/get_bill_years/bills_empty/seed_bills. Schema `_UTILITIES_SCHEMA`.
- `tests/test_food.py`: 8 test (profili, pasti+day_totals, peso, spesa+dispensa, piano, idratazione, bollette+range). Totale 27 verdi.
- **FATTO conversations** `storage/conversations.py` (port parti chat di `memory/core.py`): `conversations` (turni raw), `conv_summary` (summary rolling), `notes` (key/value). Costanti MAX_HISTORY=10, SUMMARY_BATCH=20. **Decisione**: conversation-store = trascritto raw che l'engine ripropone; DISTINTO dalla memoria semantica (`laria.memory.MemoryBackend`). FTS `search_memory` HARIA NON portata → recall keyword/semantico ora è del MemoryBackend.
- **FATTO misc** `storage/misc.py` (port `memory/misc.py`): reminders, briefings, news_blocklist, error_log (retention 500).
- **NON portati da `memory/core.py`** (di proposito): `entity_cache` + `mqtt_topics` → concern del **connector-ha** (HA-specifici), andranno lì. Migrazioni one-shot `ha_chat_`/`deactivate_generic_conti` = cruft HARIA, droppate.
- `tests/test_conversations_misc.py`: 6 test. Totale 33 verdi.

## REFACTOR /codecraft (storage)
- Skill `/codecraft` (repo `laria/.claude/skills/`, globale, e repo `andreafreda/skills`): codice leggibile-umano, SOLID con giudizio, no code smell, docstring human-oriented su ogni metodo, facade su split, no test-churn.
- `storage/finance.py` (888 righe) → **package `storage/finance/`**: accounts, transactions, categories, rules, budgets, goals, reports + facade `__init__` (API invariata). 38 verdi.
- `storage/food.py` (645 righe) → **package `storage/food/`**: profiles, weight, meals, plan, hydration, shopping, pantry, cache + facade. 38 verdi.
- Pattern: split per concetto dietro facade re-export → chiamanti e test invariati.
- Smell `update_*` RISOLTO: helper unico `db.build_set_clause(changes)` (dict colonna:valore, scarta None, ritorna clause+params); coercion resta esplicita nel chiamante. Applicato a update_account/transaction/weight/meal/pantry_item.
- Convenzione prosa: niente trattini come punteggiatura (em-dash/` - `) in docstring/commenti/README; usare virgola/due-punti/parentesi (skill /codecraft regola 10). Sweep fatto su core + README.
- Candidati refactor residui: `misc.py` (271, 4 concern) opzionale; `conversations.py`/`engine` ok.

## STORAGE PORT COMPLETO ✅
Tutti i domini dati portati, tradotti EN, de-personalizzati, settings-driven, testati (33 verdi):
finance, food, utilities, conversations, misc. Schema unico in `db.py:init_db()`.

## FATTO — ENGINE provider-agnostic (`core/laria/engine/`)
Port di `claude_engine.py`, **riprogettato** (non 1:1) per disaccoppiare da HA/anthropic:
- `tools.py`: `Tool` (name/description/input_schema/handler), `ToolContext` (user_id/memory/scope/user_config), `ToolRegistry` (register/owns/schemas/dispatch). Rimpiazza `modules.tools()/owns()/dispatch()` + i core-tool HA hardcoded.
- `prompts.py`: prompt EN (system_base/datetime_block/summarize_*). `get(key, **fmt)`.
- `core_tools.py`: tool built-in connector-independent: `get_memory`/`save_memory` (note key/value via `storage.conversations` + index in MemoryBackend), `recall` (MemoryBackend semantico). `respond` gestito dal loop.
- `engine.py`: `Engine(provider, memory, registry?, settings?, max_turns=8)`. `chat(user_id, text, user_config)`: loop agentico con `provider.generate` (blocchi normalizzati), tool_choice any/force-respond ultimo giro, deferred-respond se respond+altri tool insieme, summary rolling via provider, system con cache-breakpoint (base stabile / volatile note+summary / datetime uncached). History da `storage.conversations`.
- Tool HA (house_state/control_device/speak_alexa) NON inclusi → si registrano dal **connector-ha** quando attivo.
- `tests/test_engine.py`: 5 test con `FakeProvider` scriptato (respond, tool→respond, save+recall, deferred-respond, max_turns force-respond). Migliorato `FakeBackend.recall` (tokenizza `\w+`). Totale 38 verdi.

## FATTO — modulo finance come tool (`core/laria/modules/`)
- `modules/finance.py`: `register_finance_tools(registry)` aggiunge 8 tool che fanno da ponte sottile tra LLM e `storage.finance`: add_transaction, list_recent_transactions, get_balances, expense_summary, set_budget, budget_status, list_goals, add_to_goal. Handler ritornano JSON (dati) o frase di conferma (azioni).
- `modules/__init__.py`: esporta `register_finance_tools`. Pattern: ogni dominio ha un `register_*`; l'app sceglie cosa accendere; engine resta generico.
- Niente cicli: modules importa da `engine.tools` + `storage.finance`; engine non importa modules (registry iniettato).
- `tests/test_modules_finance.py`: 3 test (tool registrati, add_transaction via Engine+FakeProvider persiste sul DB, get_balances dispatch). Totale 41 verdi.
- Engine ora opera davvero su finance end-to-end (config→llm→engine→registry→storage).

## FATTO — moduli food + utilities come tool
- `modules/food.py`: `register_food_tools` (10 tool): log_meal, get_day_totals, log_weight, log_hydration, add_shopping_items, get_shopping_list, check_shopping_item, add_pantry_items, get_pantry, pantry_expiring. `member` esplicito (diverso da user_id).
- `modules/utilities.py`: `register_utilities_tools` (3 tool): record_bill, record_bill_range, get_bill_year (ritorna i 12 valori mensili).
- `tests/test_modules_food_utilities.py`: 5 test (dispatch diretto su registry). Totale 46 verdi.
- Restano moduli logici: nutrition lookup (OFF/USDA), econ_import parser (estratti banca).

## FATTO — composition root + web API JSON
- `app.py` (composition root): `build_engine(settings)` cabla provider (`get_provider`) + memory (`get_memory_backend`) + registra moduli finance/food/utilities → `Engine` pronto. Unico punto che sa come si incastrano i pezzi.
- `web/app.py`: `create_app(engine)` aiohttp. `GET /health`, `POST /api/chat` (body {user_id?, text, user_config?} → {reply}). Engine iniettato (test con stub). `web.AppKey` per lo stash (idiomatic). Error handling specifico: JSON invalido→400, text vuoto→400, errore engine→500 loggato non leaked.
- `web/server.py`: `serve()` = build_engine + init_db on_startup + web.run_app (host/port da settings). `web/__main__.py`: `python -m laria.web` (entrypoint container).
- `tests/test_web_api.py`: 5 test con StubEngine + aiohttp TestClient (health, chat reply, default user_id, 400 text vuoto, 400 JSON invalido). Totale 51 verdi.
- LARIA ora avviabile end-to-end: `python -m laria.web` (serve ANTHROPIC_API_KEY in env).

## FATTO — Docker (immagine core)
- `docker/Dockerfile`: python:3.12-slim, `pip install ./core`, utente non-root `laria`, DB in volume `/data`, HEALTHCHECK via `/health` (urllib, no tool extra), CMD `python -m laria.web`. Build context = repo root.
- `docker/compose.yaml`: service `laria`, porta 8080, volume `laria-data:/data`, `ANTHROPIC_API_KEY` richiesta da env (mai nell'immagine), restart unless-stopped.
- `.dockerignore`: esclude git/docs/ui/tests/__pycache__/db/segreti.
- `docker/README.md`: quick start + curl esempi.
- Verifica: import entrypoint ok (`laria.web.server`/`laria.app`/`laria.web`). Build immagine NON eseguita (Docker Desktop engine spento sul dev box); da fare quando l'engine è attivo.

## FATTO — connector Home Assistant (additivo)
- `connectors/ha/client.py`: `HaClient` (classe, DI url/token via `from_settings`, no global HARIA). REST get_states/call_service/get_calendar_events + ws_command. Errori mappati a ConnectionError/PermissionError/TimeoutError.
- `connectors/ha/tools.py`: `register_ha_tools(registry, client)` con closure sul client. Tool: get_house_state (discovery senza entity_ids = lista entity_id+nome; con = stato live), control_device, speak_alexa (announce→tts fallback). Errori di raggiungibilità → stringa leggibile per il modello, non crash del turno.
- Composition root `app.py`: registra i tool HA SOLO se `settings.ha.enabled` (import lazy). LARIA gira identico senza HA.
- Scelta: messo in `laria.connectors.ha` dentro core (additivo, nessuna nuova dep, dentro la suite). Estraibile a package `connector-ha/` separato dopo se serve.
- `tests/test_connector_ha.py`: 6 test con StubHaClient (registrazione, discovery, stato specifico, control_device, speak_alexa, HA irraggiungibile→messaggio). Totale 57 verdi.
- NON ancora portati da HARIA: subscribe_events (WS push), MQTT mirror (mqtt_pub/mqtt_topics), calendar tools, entity_cache su DB (token-opt).

## FATTO — secondo provider LLM (OpenAI-compatible)
- `llm/openai_provider.py`: `OpenAICompatibleProvider` (base_url/api_key/model). Copre OpenAI, Ollama, LM Studio, vLLM (tutti parlano Chat Completions). Conversione formato neutro↔OpenAI in funzioni PURE testabili: `to_openai_messages` (tool_use→tool_calls, tool_result→role:tool), `to_openai_tools`, `to_openai_tool_choice` (any→required, tool→named), `parse_response` (tool_calls.arguments JSON→dict, malformato→{}). HTTP via aiohttp (no nuova dep). `supports_prompt_cache=False`.
- `registry.py`: `LLM_PROVIDER` ∈ {anthropic, openai, openai-compatible, ollama}. ollama→base `OLLAMA_BASE_URL/v1` key vuota; openai→`OPENAI_BASE_URL` (default api.openai.com/v1).
- `config.py`: aggiunto `openai_base_url`.
- `tests/test_openai_provider.py`: 5 test (conversione messaggi/tool/tool_choice, parse, selezione registry ollama+openai). Totale 62 verdi.
- Astrazione provider provata con 2 implementazioni reali; engine invariato.

## FATTO — consolidamento backend
- CI: `.github/workflows/ci.yml` (pytest su push/PR, Python 3.11+3.12, offline, niente segreti).
- `.env.example` aggiornato: LLM_PROVIDER multi + OPENAI_BASE_URL/OLLAMA_BASE_URL + MEMORY_*.
- `tests/test_app.py`: smoke test `build_engine` (provider ollama, no key): registra core+finance+food+utilities; HA off di default, on con HA_ENABLED. 65 verdi.
- README: Quickstart (docker + core) + Status aggiornato.

## FATTO — moduli logici (nutrition + parser estratti)
- `ingest/bank_statements.py`: port di `econ_import.py`. Logica PURA (parse rows→movimenti {date,amount,description,category,hash}) + lettori csv (stdlib) e xlsx (openpyxl opzionale, import lazy). Categorie target EN, keyword IT (matchano descrizioni banca). Fix bug: selezione colonna data con check `is not None` (l'indice 0 è valido, `or` lo saltava). Dedup hash: 1ª occorrenza hash storico, ripetizioni con suffisso.
- `services/nutrition.py`: port di `nutrition.py`. Parser PURI `parse_off_nutriments`/`parse_usda_food` + `lookup_food`/`lookup_barcode` (cache `storage.food` → OFF → USDA). Network best-effort: errore→None (mai rompe il log pasto). USDA key da `settings.usda_api_key` (env USDA_API_KEY, default DEMO_KEY).
- Tool nuovo `lookup_nutrition(query)` nel modulo food (22 tool totali).
- `tests/test_ingest_bank_statements.py` (6) + `tests/test_nutrition.py` (4, parser puri + cache-hit no-rete). Totale 74 verdi.
- FATTO endpoint upload: `POST /api/finance/import` (multipart: account + file) → `rows_from_file` → `parse` → `finance.import_transactions`. Errori client→400 (no multipart, campi mancanti, account sconosciuto, formato non riconosciuto, xlsx senza openpyxl). `tests/test_web_import.py`: 5 test (csv import, idempotenza, account ignoto, formato ignoto, file mancante). Totale 79 verdi.

## FATTO — canale Telegram
- `channels/telegram.py`: `TelegramClient` (Bot API via aiohttp, no nuova dep: get_updates long-poll + send_message), `handle_update` (logica pura testabile: text→engine.chat keyed su chat_id→reply), `run` (loop poll con offset), `serve`/`__main__` (`python -m laria.channels.telegram`).
- IO separato dalla logica: `handle_update(update, engine, client)` testato con stub.
- `tests/test_channel_telegram.py`: 3 test (text→chat+reply, update non-message ignorato, testo vuoto ignorato). Totale 82 verdi.
- 2 canali ora sullo stesso engine (web + telegram), entrambi via `build_engine`.

## FATTO — MQTT mirror (connector-ha)
- `connectors/ha/mqtt.py`: mirror dati finance→sensori HA via MQTT discovery. Builder PURI: `slugify`, `Sensor`, `discovery_payload` (config+state topic, unique_id/object_id namespaced), `balance_sensors`/`goal_sensors`, `collect_finance_sensors`. `MqttMirror.publish` = IO paho-mqtt (lazy import, opzionale).
- **Anti-conflitto HARIA**: namespacing via `MQTT_NODE_ID` (default `laria`) su unique_id/object_id/topic + device unico "LARIA". `MQTT_DISCOVERY_PREFIX` default "homeassistant". Coesistenza con HARIA garantita; off finché HA_ENABLED/MQTT non configurati.
- `tests/test_connector_mqtt.py`: 4 test (slugify, payload namespaced, node_id custom, sensori balance/goal). Totale 86 verdi.
- **POLICY conflitti HARIA** (vedi memoria): MQTT namespace laria_; Telegram bot SEPARATO (token diverso, altrimenti i poller si rubano gli update); addon/DB nessun conflitto (LARIA è Docker, sqlite proprio). HARIA resta acceso, LARIA coesiste.

## FATTO — AUTH (incrementi 1-4, vedi design-auth.md)
- `security/passwords.py`: hash pbkdf2-sha256 stdlib (salt, self-describing), verify constant-time. `security/tokens.py`: JWT HS256 stdlib (encode/decode, iat/exp, TokenError). 8 test puri.
- `storage/identity.py` + schema: `profiles` (membri, data subject) / `users` (login opzionale su profilo, role, telegram_chat_id, must_change) / `guardianships` (tutore→profilo). CRUD + count_users. 5 test.
- `config.py`: `AuthSettings` (jwt_secret, token_ttl, admin_user/password seed).
- `auth/service.py`: authenticate (verifica cred→token, stesso errore per user ignoto/pwd errata), issue/verify_token (AuthError), change_password, ensure_owner (seed owner al primo run, idempotente). 5 test.
- `web/app.py`: middleware Bearer obbligatorio (public: /health, /api/auth/login), `/api/auth/login`→{token,must_change}, `/api/auth/change-password`, `/api/chat` ricava user_id dal **token** (non dal body), import protetto. `server.py` startup: init_db + ensure_owner. Test web aggiornati (chat/import richiedono token) + `test_web_auth.py`. Totale 109 verdi.
- `.env.example`: LARIA_JWT_SECRET/TOKEN_TTL/ADMIN_USER/ADMIN_PASSWORD.
- **FATTO Telegram allowlist**: `handle_update` risolve `chat_id`→user via `identity.get_user_by_telegram`; chat non linkata → rifiuto ("not linked"), nessun accesso; chat linkata → engine sotto `user["id"]` (Telegram condivide identità/memoria col login web). Binding manuale via `identity.link_telegram` (admin). 4 test aggiornati. 110 verdi.
- Scope memoria/conversazioni: già isolato per user_id (dal token web / dall'utente linkato Telegram). household="default" (single-household).
- **FATTO admin API** (owner-only, `web/app.py`): GET /api/admin/users (senza password_hash), GET/POST /api/admin/profiles, POST /api/admin/users, /users/reset-password, /users/link-telegram, /guardianships. Guard `_require_owner` → 403 se non owner, 401 se no token. `auth.create_user_account`/`reset_password` (hash + identity). `tests/test_web_admin.py`: 6 test (403 non-owner, 401 no-token, create profile+user+login, reset, guardianship+telegram link). Totale 116 verdi.
- Resta auth: reset password via Telegram (temp-pass self-service); enforcement tutela quando un utente registra dati per un profilo dipendente (oggi finance/food sono household-shared, ok; il check tutela serve se in futuro si vincola la scrittura a un profilo).

## FATTO — chiusura parziali (read-model, calendar, telegram reset, websocket, prompt)
- **Read-model finance** GET: /api/finance/balances /summary /matrix /budget-status /goals (autenticati). Per le dashboard, senza MQTT. `test_web_finance.py` (4).
- **Calendar tools** connector-ha: list_calendar_events + create_calendar_event. `test_connector_ha.py` esteso.
- **Reset Telegram** `/reset` su chat linkata → temp-pass + must_change. `test_channel_telegram.py` (5).
- **WebSocket** GET /api/chat/ws: request/reply persistente, auth da `?token=`. `test_web_ws.py` (3). NB: streaming token-by-token rimandato (serve provider.generate_stream + rework loop respond).
- **Prompt translation**: già EN (niente da tradurre; italiano residuo solo negli header bank-statement, voluto).
- **subscribe_events**: RIMANDATO (codice morto senza reaction-engine).
- **Docker immagine con UI**: bloccato sulla UI (non esiste ancora).
- Suite: **126 test verdi**.

## UI — stack e skill (deciso, da iniziare)
- Stack: **Ionic + Angular + Capacitor** (un codebase web + iOS + Android). Frontend in `ui/`, consuma la JSON API (`/api/auth/login`, `/api/chat`, `/api/chat/ws`, `/api/finance/*`, `/api/admin/*`). Auth: JWT in header (Bearer) per REST, `?token=` per WebSocket.
- Skill installate globali (per la UI): angular-developer, angular-new-app, ionic-angular, ionic-app-creation, ionic-app-development, ionic-expert, capacitor-angular, capacitor-app-creation, capacitor-app-development, capacitor-plugins, capacitor-expert, high-end-visual-design, design-taste-frontend, minimalist-ui, redesign-existing-projects, codecraft.
- Pagine MVP: login (+ forced change se must_change), chat (REST ora, WS dopo), dashboard finance (balances/summary/matrix/budget/goals da /api/finance/*), config LLM, admin utenti/profili/tutele.

## FATTO — UI (Ionic+Angular+Capacitor) MVP
- Scaffold in `ui/` (Ionic Angular standalone + Capacitor). Build: `cd ui && npx ng build` (output `www/`).
- `src/app/core/`: `AuthService` (JWT in localStorage via signals, decodifica role/isOwner), `auth.interceptor` (Bearer su /api/), `auth.guard`, `ChatService`, `FinanceService`, `AdminService`.
- `src/app/pages/`: login (→ change-password se must_change), chat (POST /api/chat, bolle), change-password, dashboard (balances/summary/goals da /api/finance/*), admin (owner: lista+crea profili/utenti).
- `app.component`: app-shell con side menu (Chat/Finance/Family[owner]/Sign out) + split-pane. Routes guardate. `main.ts`: provideHttpClient(interceptor).
- Tema: `index.html` font Plus Jakarta Sans; `variables.scss` palette teal+amber, sfondo sand; `global.scss` card arrotondate/ombra.
- **Core serve la UI**: `web/app.py._serve_ui` (da `LARIA_UI_DIR`, SPA fallback); middleware ora guarda solo `/api/`. Dockerfile multi-stage (node build UI + python serve) → immagine combinata su :8080.
- Dev: API `python -m laria.web` (:8080) + UI `cd ui && npx ng serve` (:4200, punta a apiBaseUrl :8080). Prod/Docker: tutto su :8080.

- Aggiunto: dashboard "spese per categoria" (barre CSS, da /api/finance/summary); pagina **import estratto** (`/import`, upload multipart → /api/finance/import) con link dal dashboard.

## Prossimo UI: pagina config LLM (serve endpoint backend), grafici matrix, consumo WebSocket streaming, build mobile Capacitor (cap add). Verificare build Docker quando engine attivo.
- moduli dominio come tool registrabili: portare `nutrition.py` (lookup OFF/USDA), `econ_import.py` (parser estratti) e wrapper tool che espongono `storage.finance/food/...` all'LLM (oggi l'engine ha solo i core-tool). Questi erano i `modules/*` di HARIA.
- canali: web API REST/WS (aiohttp `webpanel.py`→API vera), Telegram astratto.
- poi connector-ha (entity_cache/mqtt/ha_client), UI Angular, Docker.

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
