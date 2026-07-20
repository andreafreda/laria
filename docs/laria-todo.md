# LARIA — cosa manca per essere completa

Stato: parità funzionale HARIA + portale web raggiunta. Questa lista è ciò che
resta per un prodotto completo/vendibile. Aggiornato 2026-07-20.

## Robustezza / parità (piccoli)

- [ ] **Fallback climate turn_off/on** nel connettore HA di LARIA (`connectors/ha`):
      quando l'entità non supporta turn_off/turn_on (HA risponde 400 o 500),
      ripiegare su `set_hvac_mode` (off / auto). Stesso fix già fatto su HARIA.
- [ ] **Risoluzione nome → entity_id** nel control HA: evitare che l'LLM tiri a
      indovinare id (es. `climate.salone` invece di quello reale). Mappare il
      nome richiesto all'entità giusta prima di chiamare il servizio.
- [ ] **MQTT**: oggi solo sensori finance; aggiungere food e bollette.
- [ ] **Scheduler nel processo web**: reminder/briefing creati da web partono solo
      al riavvio del processo Telegram. Valutare uno scheduler condiviso/persistente.

## Feature nuove (richieste)

- [x] **Notifiche eventi ricorrenti** (compleanni/anniversari/custom): FATTO —
      tabella `events` + tool `add_event/list_events/delete_event` + job giornaliero
      08:00 (`notifier.send_due_events`), anticipo configurabile (`notify_days_before`).
- [ ] **Onomastici**: mappa nome→data (calendario santi IT) + notifica onomastico.
      Rimandato (serve il dataset santi). Aggancio: stesso `events` con kind=nameday.
- [ ] **Push HA** per gli eventi (oltre a Telegram): opzionale, via `persistent_notification`
      o notify mobile quando HA abilitato.

## Prodotto / release (grossi)

- [ ] **Chat streaming** token-by-token (`provider.generate_stream`).
- [ ] **Mobile**: build Capacitor iOS/Android (`cap add ...`) + toolchain.
- [ ] **Secret cifrati** at-rest.
- [ ] **OpenAPI** docs + **observability** (log strutturati, metriche, health).
- [ ] **i18n** (UI + risposte).
- [ ] **Migrazione `haria.db`**: importare dati esistenti (economia/cibo/storico).
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
4. **Migrazione `haria.db`**: importare i dati veri così si parte con lo storico.
4. **Notifiche eventi/compleanni/onomastici**.
5. **Verifica docker build** + doc deploy.
6. Chat streaming, MQTT food/bollette, memory L0-L3, ecc. (maturazione backend).

### In coda (dopo che Telegram è solido)
- **Frontend/portale web**: rifiniture pagine, test UI Angular, streaming in UI.
- **Mobile** Capacitor.

Nota: il portale è un "in più" (come da premessa). Con Telegram funzionante
LARIA è già usabile in casa; l'UI web arriva dopo.
