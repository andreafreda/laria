# LARIA — cosa manca per essere completa

Stato: parità funzionale HARIA + portale web raggiunta. Questa lista è ciò che
resta per un prodotto completo/vendibile. Aggiornato 2026-07-20.

## Robustezza / parità (piccoli)

- [x] **Fallback climate turn_off/on** (FATTO): `connectors/ha/client.py`
      `_climate_hvac_fallback` ripiega su `set_hvac_mode` (off/auto) su 400/500.
- [ ] **Risoluzione nome → entity_id** nel control HA: evitare che l'LLM tiri a
      indovinare id (es. `climate.salone` invece di quello reale). Mappare il
      nome richiesto all'entità giusta prima di chiamare il servizio.
- [x] **MQTT dashboard HARIA-compat** (FATTO): LARIA ripubblica le entità MQTT
      con gli **unique_id/topic esatti di HARIA** (device HARIA Bollette/Economia/Cibo)
      → le dashboard Lovelace esistenti si aggiornano senza modifiche. Vedi
      `connectors/ha/compat.py` (bollette+economia+food), tabella `mqtt_topics` per
      cleanup entità fantasma, cron `mqtt_dashboards` ogni 15min. **LIVE in prod
      dal 2026-07-21**: login broker `laria` su Mosquitto, `.env` NAS con MQTT_*,
      `paho-mqtt` ora dep core. Verificato: bollette/economia/food aggiornati.
- [x] **Disaccoppiamento HARIA (MQTT `laria_` nativo)** FATTO: LARIA pubblica un
      modello entità inglese pulito (`laria_finance_*`/`laria_utility_*`/`laria_diet_*`,
      device LARIA Finance/Utilities/Diet). Le 3 dashboard Lovelace ripuntate via MCP
      (bollette/economia/food). Compat `haria_` + finance mirror namespaced rimossi;
      97 entità HARIA/mirror ritirate. Vedi `connectors/ha/dashboards.py` + `_mqtt_model.py`.
- [ ] **Scheduler nel processo web**: reminder/briefing creati da web partono solo
      al riavvio del processo Telegram. Valutare uno scheduler condiviso/persistente.

## Feature nuove (richieste)

- [x] **Notifiche eventi ricorrenti** (compleanni/anniversari/custom): FATTO —
      tabella `events` + tool `add_event/list_events/delete_event` + job giornaliero
      08:00 (`notifier.send_due_events`), anticipi multipli discreti (`notify_offsets`:
      1 mese/1 settimana/2 giorni/1 giorno/stesso giorno).
- [x] **Onomastici** (RISOLTO senza dataset): l'utente crea un evento `kind=nameday`
      a mano; la data si trova con `search_web` (tool web search on-demand, FATTO).
      Nessun calendario santi hardcoded.
- [ ] **Push HA** per gli eventi (oltre a Telegram): opzionale, via `persistent_notification`
      o notify mobile quando HA abilitato.

## Prodotto / release (grossi)

- [ ] **Chat streaming** token-by-token (`provider.generate_stream`).
- [ ] **Mobile**: build Capacitor iOS/Android (`cap add ...`) + toolchain.
- [ ] **Secret cifrati** at-rest.
- [ ] **OpenAPI** docs + **observability** (log strutturati, metriche, health).
- [ ] **i18n** (UI + risposte).
- [x] **Migrazione `haria.db`** (FATTO): dati veri importati in prod NAS via
      `tools/migrate_haria.py` (1891 tx + conti/categorie/regole/budget/obiettivi,
      bollette, food, reminder/briefing rimappati). Backup su NAS.
- [ ] **Plugin SDK** (formalizzare il registry moduli) + **backup** nativo.
- [ ] **Memory engine L0-L3** (oggi solo wrapper mem0).
- [ ] **Test UI** Angular (unit + e2e); oggi solo pytest backend.
- [ ] **Docker build** verificato in locale + doc deploy/ops.

## Decisioni da prendere (sbloccano il resto)

- [ ] **Licenza**: BSL 1.1 vs PolyForm + edizione/change-date.
- [ ] **Target deploy iniziale**: self-host Docker vs cloud.

## Priorità (Telegram-first; frontend in coda)

Obiettivo: usare LARIA **subito via Telegram**, senza dipendere dal portale.
Il frontend web resta valido ma va **in fondo**.

> STATO 2026-07-20: LARIA **in uso** via Telegram da docker locale (container
> `laria-telegram`, volume `laria-data`). Chat + tool + **HA control** funzionanti.
> Fatti: claim bootstrap, owner seed, fix climate turn_off/on (HARIA + LARIA),
> HA abilitato (`HA_URL=192.168.1.32:8123`). Resta: consolidare deploy, NAS.

1. **Uso reale via Telegram** (FATTO):
   - configurare `.env`: `ANTHROPIC_API_KEY` vero, `TELEGRAM_TOKEN` (bot separato
     da HARIA), `LARIA_ADMIN_*`, `LARIA_JWT_SECRET`, DB su volume; HA opzionale
     (`HA_ENABLED`+`HA_URL`+`HA_TOKEN`) se si vuole comandare casa.
   - creare l'utente + link `telegram_chat_id` (via admin/CLI).
   - avviare il processo Telegram (`python -m laria.channels.telegram` o
     `docker compose --profile telegram`), verificare chat + reminder/briefing +
     food/finance end-to-end su Telegram.
2. **Robustezza HA**: fix climate turn_off/on FATTO. Resta: resolve nome→entity_id
   (ora mitigato rinominando le entità con id chiari lato HA).
3. **Deploy** (FATTO): produzione su **NAS QNAP** via GHCR + Watchtower
   (auto-update a ogni push su main), compose + `.env` con segreti veri,
   LARIA cappata 0.5 CPU/512M. Vedi memoria `project_laria_deploy`.
4. Migrazione haria.db: FATTA (vedi sopra).
4. **Notifiche eventi/compleanni/onomastici**.
5. **Verifica docker build** + doc deploy.
6. Chat streaming, MQTT food/bollette, memory L0-L3, ecc. (maturazione backend).

### In coda (dopo che Telegram è solido)
- **Frontend/portale web**: rifiniture pagine, test UI Angular, streaming in UI.
- **Mobile** Capacitor.

Nota: il portale è un "in più" (come da premessa). Con Telegram funzionante
LARIA è già usabile in casa; l'UI web arriva dopo.
