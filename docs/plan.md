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
- [x] Core bootstrap: `laria.config` (env, no Supervisor) + `laria.llm` (provider astratto + Anthropic + registry) + test.
- [x] **Memory wrapper** `core/laria/memory/`: `MemoryBackend` astratto + `FakeBackend` + `Mem0Backend` + `Embedder` + registry (mem0 plug&play).
- [x] **Port storage COMPLETO** `core/laria/storage/` de-personalizzato, EN, settings-driven: finance, food, utilities, conversations, misc (33 test verdi).
- [x] **Engine agentico provider-agnostic** `core/laria/engine/`: loop tool-use su `provider.generate`, ToolRegistry pluggable, core-tool memory/recall/respond, prompt EN, summary rolling (38 test verdi).
- [~] Moduli dominio come tool registrabili: **finance + food + utilities fatti** (`modules/`, 21 tool). Restano: nutrition lookup, econ_import parser.
- [x] **Convenzione codice**: skill `/codecraft` (repo `.claude/skills/`, globale, pubblicata su `andreafreda/skills`) project-agnostic: leggibilità umana, SOLID con giudizio, no code smell, docstring human-oriented, niente trattini come punteggiatura in prosa.
- [x] **Refactor /codecraft**: `storage/finance` e `storage/food` splittati in package per concetto + facade; helper `db.build_set_clause`; sweep trattini su core+README. Suite attuale: **46 test verdi**.
- [ ] Canali (Telegram) astratti; web API (REST/WS).
- [ ] connector-ha (REST/WS + subscribe_events + MQTT mirror).
- [ ] UI Angular (incl. dashboard configurazione LLM).
- [ ] Docker (Dockerfile multi-stage + compose).
- [ ] Step traduzione completa IT→EN (terminologia, vedi sotto).
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

- **A. Astrazione storage**: oggi SQLite hardcoded. Tenere repository pattern così in futuro Postgres/multi-utente cloud è possibile. Migrazioni versionate (oggi migrazioni leggere ad hoc).
- **B. Auth & multi-tenant**: app esterna esposta → serve login vero, ruoli, isolamento dati per utente/famiglia. Oggi multi_user è leggero (chat_id).
- **C. Sicurezza segreti**: oggi token in chiaro in config/yaml. Vault/secret manager, cifratura a riposo, niente key nel repo.
- **D. API pubblica**: REST/WebSocket documentata (OpenAPI) → UI, integrazioni, eventuale app mobile.
- **E. Canali oltre Telegram**: WhatsApp, web chat, Matrix, Discord — astrarre il layer "messaging" come i provider LLM.
- **F. Observability**: log strutturati, metriche, health endpoint (oggi errorlog → notifica HA; va reso generico).
- **G. Test & CI**: oggi pytest locale; aggiungere CI (GitHub Actions), build/push immagine, lint, pin dipendenze (già fatto).
- **H. Migrazione dati**: tool per importare il `haria.db` esistente nel nuovo prodotto senza perdere economia/cibo/storico.
- **I. Plugin/modulo SDK**: formalizzare l'attuale registry moduli come SDK documentato, così terzi aggiungono moduli.
- **J. Backup/restore** nativi (oggi si appoggia ai backup HA).
- **K. i18n**: oggi IT hardcoded; predisporre multilingua se prodotto pubblico.

---

## Ordine suggerito (bozza, da discutere)
1. Fork + nome (1,2) — setup.
2. Disaccoppiamento core + astrazione storage/config (3, A) — fondamenta.
3. Provider LLM astratto (8) — sblocca valore subito.
4. Connettore HA via API (4) + Lovelace export (7).
5. Docker image (5).
6. UI web nuova + auth (6, B, C).
7. Resto (D–K) incrementale.

## Decisioni prese
- **UI:** SPA **Angular** + backend API (REST/WS). Frontend separato dal core.
- **Repo:** **pubblico** ma **non** open-source classico → licenza **source-available commerciale**
  ("lo vedi/provi gratis, se lo usi/lo monetizzi paghi"). Candidate: **BSL 1.1** (Business Source
  License: uso non-produttivo libero, produzione richiede licenza) o **PolyForm Noncommercial/Commercial**.
  Conseguenza: igiene segreti obbligatoria dal commit 1 (niente token nel repo, `.env`/secret manager).
- **Layout:** **monorepo** (core + connettore-HA + UI Angular + docker in cartelle/packages).
- **LLM:** layer provider **universale**, ma **fase 1 = solo Anthropic funzionante end-to-end**.
  Ollama primo target locale subito dopo (endpoint OpenAI-compatible → copre anche LM Studio/llama.cpp/vLLM).

## Nome scelto: **LARIA**
- **L**ocal **A**ssistant **R**eactive **I**ntelligent **A**gent (HARIA: Home→Local, coerente col disaccoppiamento da HA).
- **LAR** = spirito guardiano della casa (latino) + **IA** = intelligenza artificiale.
- Bonus IT: "l'aria" = presenza che pervade la casa.
- Disponibilità: PyPI `laria` libero; nessuna collisione smart-home/AI (solo repo P2P morto Luphia/Laria). Da verificare domini.

## Ancora da decidere
- Versione/edizione licenza esatta (BSL vs PolyForm) + change-date/grant BSL.
- Target deploy iniziale: assumo **Docker self-host**; cloud dopo.
