# Piano — LARIA (fork standalone di HARIA)

> ⚠️ **QUESTO FILE È LA FONTE DI VERITÀ DEL PROGETTO.** La conversazione con l'assistente
> può essere compattata/persa in qualsiasi momento: tutto ciò che conta (decisioni, stato,
> prossimi passi) DEVE stare qui e aggiornato. Se l'assistente riparte da zero, legge questo.

Obiettivo: LARIA = **prodotto autonomo** (standalone-first), deployabile come Docker image,
con UI web propria (dashboard vere = app nativa), supporto multi-LLM, e Home Assistant come
**integrazione opzionale additiva** (MQTT + comandi remoti), mai dipendenza.

Origine: fork di HARIA (addon HA monolitico, Python 3.12, SQLite, MQTT, aiohttp ingress,
Telegram, scheduler, claude_engine, v0.3.3). Repo LARIA: github.com/andreafreda/laria.

## Stato avanzamento (aggiornare sempre)
- [x] Repo + scheletro monorepo (core/ connector-ha/ ui/ docker/ docs/), licenza PolyForm Noncommercial.
- [x] README standalone-first (EN), .gitignore (segreti esclusi), .env.example.
- [x] Core bootstrap: `laria.config` (env, no Supervisor) + `laria.llm` (provider astratto + registry) + test.
- [x] **LLM multi-provider**: Anthropic + OpenAI-compatible (openai/ollama/lm-studio/vllm), conversione formato in funzioni pure testate.
- [x] **Memory wrapper** `core/laria/memory/`: `MemoryBackend` astratto + `FakeBackend` + `Mem0Backend` + `Embedder` + registry (mem0 plug&play).
- [x] **Port storage COMPLETO** `core/laria/storage/` de-personalizzato, EN, settings-driven: finance, food, utilities, conversations, misc (33 test verdi).
- [x] **Engine agentico provider-agnostic** `core/laria/engine/`: loop tool-use su `provider.generate`, ToolRegistry pluggable, core-tool memory/recall/respond, prompt EN, summary rolling (38 test verdi).
- [x] Moduli dominio come tool registrabili: **finance + food + utilities** (`modules/`, 22 tool) + **nutrition lookup** (`services/nutrition.py` OFF/USDA + tool `lookup_nutrition`) + **parser estratti** (`ingest/bank_statements.py` BancoPosta/Postepay, categorie EN) + **endpoint upload** `POST /api/finance/import` (multipart → parse → import dedup).
- [x] **Convenzione codice**: skill `/codecraft` (repo `.claude/skills/`, globale, pubblicata su `andreafreda/skills`) project-agnostic: leggibilità umana, SOLID con giudizio, no code smell, docstring human-oriented, niente trattini come punteggiatura in prosa.
- [x] **Refactor /codecraft**: `storage/finance` e `storage/food` splittati in package per concetto + facade; helper `db.build_set_clause`; sweep trattini su core+README. Suite a quel punto: 46 test verdi (ora 116).
- [x] **Auth** (vedi `design-auth.md`): hash pbkdf2 + JWT, profiles/users/guardianships, login + change-password, middleware Bearer, /api/chat da token, Telegram allowlist, admin API owner-only, owner seed. Resta solo: reset Telegram self-service.
- [x] Canali: **web API JSON** (auth, /api/chat, /api/chat/ws WebSocket, /api/finance/* read-model, /api/finance/import, /api/auth/*, /api/admin/*) + **Telegram** (allowlist + /reset). WebSocket = request/reply persistente (streaming token-by-token rimandato, serve provider streaming).
- [x] connector-ha: **client REST/WS + tool HA + MQTT mirror + calendar tools**. subscribe_events RIMANDATO di proposito (senza un reaction-engine sarebbe codice morto; lo si fa col layer reazioni).
- [ ] UI Angular (incl. dashboard configurazione LLM).
- [~] Docker: **immagine core fatta** (`docker/Dockerfile` python-slim non-root + healthcheck, `docker/compose.yaml` con volume dati, `.dockerignore`; `python -m laria.web`). Build non ancora verificata in locale (Docker Desktop engine spento). Resta: immagine combinata con UI.
- [x] **Consolidamento backend**: CI GitHub Actions (pytest 3.11/3.12 offline), `.env.example` completo, smoke test composition root, README quickstart. **Suite attuale: 116 test verdi**.
- [x] Traduzione prompt/stringhe model-facing IT→EN: di fatto completa (prompt e tool LARIA scritti EN da subito). L'unico italiano residuo è in `ingest/bank_statements.py` = header dei file estratto banca italiani da matchare (voluto, non prompt).
- [ ] **Memoria agente**: fase 1 = **mem0 dietro wrapper nostro `MemoryBackend`** (plug&play); improvement = motore proprio L0-L3 dopo. Vedi `design-memory.md` §6bis + `memory-engine-handoff.md`.

## Lingua
- Codice, README, commenti, commit, **nomi di dominio/moduli**: **inglese**.
- Piani e docs interni (questo file): italiano.
- C'è uno **step dedicato di traduzione** quando si porta il codice da HARIA (oggi IT).
  Terminologia da anglicizzare (esempi): `bollette` → **bills/utilities**, `economia` → **finance**,
  `cibo`/`food_diary` → **food**, `conti` → **accounts**, `salvadanai/obiettivi` → **savings goals**,
  `spese` → **expenses**, `prelievo contanti` → **cash withdrawal**. Da consolidare in un glossario.

---

## 1. Fork su repo parallelo
- Nuovo repo Git (separato da `andreafreda/haria`), per non rompere l'addon esistente in produzione.
- Strategia: `git clone` + nuovo remote, oppure fork GitHub. Mantenere la storia.
- Da decidere: monorepo (core + connettore + ui) o repo multipli.
- **Aperto:** pubblico o privato? Licenza?

## 2. Nome nuovo
- HARIA = "Home Assistant Reactive Intelligent Agent" → legato a HA, non più adatto.
- Serve nome provider-agnostico (no "Home Assistant", no "Anthropic").
- **Aperto:** brainstorming nome + check dominio/PyPI/GitHub disponibili.

## 3. Disaccoppiamento da HASSIO (core autonomo)
- Oggi dipende da: `SUPERVISOR_TOKEN`, `/config/`, servizio MQTT del Supervisor, ingress.
- Astrarre in un layer di config: percorsi DB/dati da env var (già `DB_PATH`), niente assunzioni Supervisor.
- Rimuovere/rendere opzionali: `_mqtt_config()` via Supervisor, ingress-only auth, shell_command repair.
- Il core deve girare anche **senza** HA: Telegram + web UI + LLM + DB funzionano da soli.
- I moduli che NON dipendono da HA (economia, food_diary, agenda promemoria, news, web_search) restano nativi.
- I moduli/feature HA-specifici (controllo entità, MQTT discovery) → dietro il connettore (sez. 4).

## 4. Connettore Home Assistant
- Plugin/adapter che parla con HA via **API ufficiali** (REST + WebSocket) con long-lived token, NON via Supervisor.
- Funzioni: leggere entità/stati, chiamare servizi, (opz.) pubblicare sensori via MQTT esterno.
- Config: URL HA + token (UI). Se assente → HARIA gira lo stesso, feature HA disattivate.
- Vantaggio: HARIA esterno controlla qualsiasi HA raggiungibile in rete, non solo quello che lo ospita.

## 5. Deploy come Docker image
- `Dockerfile` standalone (base python-slim, non Alpine-addon).
- `docker-compose.yml`: app + (opz.) MQTT broker + volume per `data/` (DB, diete, allegati).
- Config via env / file `.env` / config UI.
- **Futuro:** pacchettizzazione come applicativo (desktop/installer) — tenere il core disaccoppiato dall'I/O così è riusabile.

## 6. Interfaccia web propria (dashboard app)
- Oggi: pannello aiohttp minimale (ingress). Serve una UI vera, indipendente da HA.
- Funzioni: chat, gestione economia/cibo/agenda/bollette, grafici, config (LLM keys, connettore HA, utenti).
- "Clonare e migliorare ciò che fa HARIA ora": ricostruire le pagine attuali + dashboard ricche (i grafici economia fatti in Lovelace diventano nativi nell'app).
- **Aperto:** stack frontend (mantenere aiohttp+template server-side, o SPA React/Vue + API REST/WS?). Auth propria (login utenti).

## 7. Gestione Lovelace (app esterna)
- Problema: oggi le dashboard economia vivono in Lovelace (HA). Con app esterna, non più garantito.
- Strategia doppia:
  - **Dentro l'app**: dashboard native (grafici/tabelle) → fonte di verità.
  - **Verso HA (se connettore attivo)**: continuare a pubblicare sensori MQTT + (opz.) generare/aggiornare card Lovelace via WebSocket API, così chi usa HA mantiene le viste.
- Garantire che le feature funzionino in entrambi i mondi: la UI app non deve dipendere da Lovelace; Lovelace diventa un *export* opzionale.

## 8. Multi-LLM (non solo Anthropic)
- Astrarre `claude_engine` dietro un'interfaccia provider (chat + tool-calling).
- Provider: Anthropic, OpenAI, Google Gemini, + **locali** (Ollama, LM Studio, llama.cpp / OpenAI-compatible endpoint).
- Config per-utente o globale: provider + modello + key/endpoint (UI).
- **Dashboard di configurazione LLM nell'app** (requisito): pagina UI dedicata per
  gestire provider, modelli, API key/endpoint, parametri (max_tokens, temperatura),
  selezione modello per task (es. summary su modello economico/locale), test connessione,
  e (futuro) stato/uso/costi. Le key si salvano cifrate, mai nel repo.
- Attenzione: tool-calling/prompt-caching differiscono per provider → layer di adattamento (normalizzare tool schema, gestire chi non supporta cache/feature).
- Fallback e selezione modello per task (es. summary su modello economico/locale).

---

## Memoria persistente dell'agente (DA REINGEGNERIZZARE)

Requisito: **rivalutare da zero** come LARIA ricorda, valutando strade alternative
a quella attuale di HARIA. Non dare per scontato l'approccio esistente.

**Com'è oggi (HARIA):**
- Tabella `conversations` (turni raw) con finestra recente (`MAX_HISTORY`).
- Riassunto progressivo dei turni vecchi (1 chiamata LLM, "summary").
- `notes` (note utente salvate, iniettate nel system prompt).
- Recall keyword via **FTS5** (full-text) su note + conversazioni.
- Limiti: niente semantica (solo keyword), summary lossy, memoria piatta (no episodica/semantica),
  nessun decay/priorità, cresce nel prompt, non multi-utente robusto.

**Strade alternative da valutare (scegliere/ibridare):**
- **Memoria vettoriale / semantica (RAG)**: embeddings + vector store (sqlite-vec, pgvector,
  Chroma, Qdrant) → recall per significato, non keyword. Embeddings locali o via provider.
- **Memoria a livelli** (stile MemGPT/Letta): working / episodic / semantic / archival, con
  paging dentro-fuori dal contesto gestito dall'agente.
- **Librerie dedicate**: mem0, Letta (MemGPT), Zep — valutare adozione vs build-in.
- **Knowledge graph** (entità/relazioni) per fatti strutturati su utente/casa/abitudini.
- **Fatti estratti + dedup** (memory distillation): l'agente estrae fatti atomici, con
  fonte/timestamp/confidenza, decay e merge (no duplicati) — simile alla memoria-file attuale ma automatica.
- **Per-utente / multi-tenant**: isolamento e scope (globale vs per-utente vs per-stanza).
- **Provider-agnostica**: gli embeddings devono passare dal layer provider (anche locali, no lock-in).

**Criteri di scelta:** qualità recall, costo/latenza, locale-first (privacy), semplicità deploy
(meno servizi esterni meglio → sqlite-vec/pgvector candidati forti), portabilità del dato.

**Output atteso:** mini design doc che confronta 2-3 architetture e propone quella per LARIA,
con schema dati e API di memoria (write/recall/forget). Da fare prima/insieme al port dello storage.

## Cose che aggiungo io (da valutare)

- **A. Astrazione storage**: DECISO di restare **sqlite-diretto** ora (YAGNI). `StorageBackend` (per Postgres/multi-tenant condiviso) si introduce solo se serve scala SaaS. Vedi `reflections.md`.
- **B. Auth & multi-tenant**: ✅ IMPLEMENTATO (vedi `design-auth.md`). Restano: multi-tenant condiviso (dopo, dietro StorageBackend).
- **C. Sicurezza segreti**: ⬜ TODO. Chiavi LLM/token cifrate a riposo, niente key nel repo (oggi `.env` gitignored, ok; manca cifratura at-rest + gestione da UI).
- **D. API pubblica**: 🟡 REST + WebSocket fatti; manca **documentazione OpenAPI**.
- **E. Canali oltre Telegram**: ⬜ WhatsApp/Matrix/Discord, dietro un layer messaging astratto.
- **F. Observability**: ⬜ log strutturati, metriche, health (oggi /health base + error_log).
- **G. Test & CI**: ✅ CI GitHub Actions (pytest 3.11/3.12). Manca: build/push immagine, lint.
- **H. Migrazione dati**: ⬜ tool per importare `haria.db` esistente (economia/cibo/storico) in LARIA.
- **I. Plugin/modulo SDK**: ⬜ formalizzare il registry moduli (`ToolRegistry`) come SDK documentato.
- **J. Backup/restore** nativi: ⬜ (sqlite su volume = backup banale del file; manca comando dedicato).
- **K. i18n**: ⬜ predisporre multilingua UI/risposte se prodotto pubblico.

---

## Ordine — stato
FATTO: fork+nome, disaccoppiamento core, multi-LLM, storage+moduli, engine,
connettore HA (+MQTT+calendar), Docker (core), auth completa, canali (web+WS+
Telegram), read-model dashboard, CI.
PROSSIMO:
1. **UI Angular** (Ionic + Capacitor): login, chat (REST + WebSocket), dashboard
   finance (consuma /api/finance/*), config LLM, admin utenti/profili/tutele.
2. Docker immagine combinata (core + UI servita).
3. WebSocket **streaming token-by-token** (serve `provider.generate_stream`), insieme alla UI.
4. Incrementale: secret cifrati (C), OpenAPI (D), migrazione `haria.db` (H), backup (J),
   reaction-engine + `subscribe_events`, canali extra (E), i18n (K), motore memoria L0-L3.

## Decisioni prese
- **UI:** SPA **Angular** + backend API (REST/WS). Frontend separato dal core.
- **Repo:** **pubblico** ma **non** open-source classico → licenza **source-available commerciale**
  ("lo vedi/provi gratis, se lo usi/lo monetizzi paghi"). Candidate: **BSL 1.1** (Business Source
  License: uso non-produttivo libero, produzione richiede licenza) o **PolyForm Noncommercial/Commercial**.
  Conseguenza: igiene segreti obbligatoria dal commit 1 (niente token nel repo, `.env`/secret manager).
- **Layout:** **monorepo** (core + connettore-HA + UI Angular + docker in cartelle/packages).
- **LLM:** layer provider **universale**. Anthropic + **OpenAI-compatible fatto** (`openai`/`ollama`/`openai-compatible`, copre OpenAI/Ollama/LM Studio/vLLM). Selezione via `LLM_PROVIDER`.
- **Storage:** **sqlite-diretto** (no astrazione ora). Isolamento famiglie = istanze dedicate (1 container + 1 volume + 1 sqlite = 1 household). Vedi `reflections.md`/`design-auth.md`.
- **Auth:** single-household multi-utente; profili (permanenti) + user (login opzionale) + tutela; JWT. Vedi `design-auth.md`.
- **Frontend:** **Ionic + Angular + Capacitor** (un codebase web + iOS + Android).

## Nome scelto: **LARIA**
- **L**ocal **A**ssistant **R**eactive **I**ntelligent **A**gent (HARIA: Home→Local, coerente col disaccoppiamento da HA).
- **LAR** = spirito guardiano della casa (latino) + **IA** = intelligenza artificiale.
- Bonus IT: "l'aria" = presenza che pervade la casa.
- Disponibilità: PyPI `laria` libero; nessuna collisione smart-home/AI (solo repo P2P morto Luphia/Laria). Da verificare domini.

## Ancora da decidere
- Versione/edizione licenza esatta (BSL vs PolyForm) + change-date/grant BSL.
- Target deploy iniziale: assumo **Docker self-host**; cloud dopo.
