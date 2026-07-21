# LARIA — stato del progetto

Snapshot aggiornato: **2026-07-21**. Fork standalone di HARIA, usabile via Telegram
senza portale. Il portale web è un "in più" (in coda).

Per il dettaglio task vivo vedi [laria-todo.md](laria-todo.md); questo file è la
fotografia completa (fatto + cosa manca + infrastruttura).

---

## Fatto

### Core / uso reale
- **Telegram end-to-end**: chat + tutti i tool (finance, food, utilities, lists,
  reminders, news, events, search) + controllo HA. Owner seed + claim
  (`/claim laria-start`).
- **Provider LLM agnostico** (anthropic default, openai-compatible, ollama).
- **Web search on-demand** in chat (`modules/search.py`, tool `search_web`, ddgs).
- **Eventi ricorrenti** (compleanni/anniversari/nameday/custom): tabella `events`,
  tool `add_event/list_events/delete_event`, job giornaliero 08:00, anticipi
  multipli discreti (`notify_offsets`: 1 mese / 1 settimana / 2 giorni / 1 giorno /
  stesso giorno).
- **Onomastici** senza dataset: evento `kind=nameday` a mano + data via `search_web`.

### Home Assistant
- **Controllo HA** abilitato (`HA_URL=192.168.1.32:8123`).
- **Fallback climate turn_off/on**: `connectors/ha/client.py` ripiega su
  `set_hvac_mode` (off/auto) quando HA risponde 400/500.
- **MQTT nativo `laria_` — disaccoppiato da HARIA (LIVE)**: LARIA pubblica un
  modello entità inglese pulito, device LARIA Finance/Utilities/Diet. Es.
  `sensor.laria_finance_total_balance`, `sensor.laria_utilities_electricity_cost_2026`,
  `sensor.laria_diet_andrea_kcal_today`. (NB: HA compone entity_id da device+nome,
  ignora object_id.)
  - `connectors/ha/dashboards.py` (collector utilities/finance/diet + `publish_native`)
    + `connectors/ha/_mqtt_model.py` (Sensor + builder + publish + cleanup `mqtt_topics`).
    `finance.month_transactions` per il drilldown mese. Cron `mqtt_dashboards_native` 15min.
  - **Dashboard Lovelace ripuntate** via MCP (`bollette-consumi-v2`, `haria-economia`,
    `haria-cibo`): entity_id + chiavi attr IT→EN.
  - Rimossi il compat `haria_` e il vecchio finance mirror namespaced; **97 entità**
    HARIA/mirror ritirate. Backup pre-migrazione: HA snapshot `73c200e5` + `laria.db` bak.
  - Verificato: 88 entità `laria_` con valori reali; zero residui `haria_`.

### Deploy / dati
- **Produzione su NAS QNAP** (`192.168.1.118`) via GHCR + Watchtower: push su
  `main` → CI builda+pubblica `ghcr.io/andreafreda/laria:latest` → Watchtower
  (ogni 5min) pulla+ricrea. Zero operazioni manuali.
- **Migrazione `haria.db`** completata: 1891 tx + conti/categorie/regole/budget/
  obiettivi, bollette, food, reminder/briefing. Backup su NAS.

---

## Cosa manca

### Piccoli / robustezza
- **Resolve nome → entity_id** nel control HA: l'LLM può ancora indovinare id
  sbagliati. Mitigato rinominando le entità lato HA, ma non risolto in codice.
- **MQTT `laria_` namespaced**: decidere se dismettere il mirror finance nativo
  ora che c'è il path compat (ridondante).
- **Scheduler nel processo web**: reminder/briefing creati da web partono solo al
  riavvio del bot Telegram → serve scheduler condiviso/persistente.
- **Push HA eventi** (compleanni ecc.) oltre Telegram, via `persistent_notification`
  — opzionale.

### Grossi / release
- **Chat streaming** token-by-token (`provider.generate_stream`).
- **Secret cifrati** at-rest (oggi `.env` in chiaro sul NAS).
- **Observability**: log strutturati, metriche, health; **OpenAPI** docs.
- **Memory engine L0-L3** (oggi solo wrapper mem0).
- **Plugin SDK** (formalizzare il registry moduli) + **backup** nativo.
- **i18n** (UI + risposte).
- **Test UI** Angular (unit + e2e); oggi solo pytest backend (212 test verdi).
- **Mobile**: build Capacitor iOS/Android + toolchain.

### Decisioni da prendere (sbloccano il resto)
- **Licenza**: BSL 1.1 vs PolyForm + edizione/change-date.
- **Target deploy iniziale**: self-host Docker vs cloud.

### In coda (dopo che Telegram è solido)
- **Frontend/portale web**: rifiniture pagine, test UI Angular, streaming in UI.

---

## Infrastruttura (riferimento operativo)

- **NAS QNAP** `192.168.1.118:22`, utente `claude` (paramiko; password fornita a
  runtime, non salvata). Docker: `/share/CACHEDEV2_DATA/.qpkg/container-station/bin/docker`.
  App dir `/share/Container/laria/` → `compose.nas.yaml` + `.env`.
  Container `laria-laria-telegram-1` + `laria-watchtower-1`, volume `laria_laria-data`.
- **HA** `192.168.1.32:8123`. Broker Mosquitto (addon `core_mosquitto`, porta 1883):
  login dedicato `username=laria`.
- **`.env` NAS** (segreti, non nel repo): `TELEGRAM_TOKEN`, `ANTHROPIC_API_KEY`,
  `LARIA_ADMIN_*`, `LARIA_JWT_SECRET`, `HA_ENABLED/HA_URL/HA_TOKEN`,
  `LARIA_DATA_DIR=/data`, `LARIA_DB_PATH=/data/laria.db`,
  `MQTT_HOST=192.168.1.32 / MQTT_PORT=1883 / MQTT_USERNAME=laria / MQTT_PASSWORD`.
- **Dipendenze core** (`core/pyproject.toml`): anthropic, aiosqlite, aiohttp,
  apscheduler, ddgs, **paho-mqtt** (necessaria al publishing MQTT).
