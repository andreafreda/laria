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

- [ ] **Notifiche eventi ricorrenti**: compleanni, onomastici, anniversari e
      simili. Idea: anagrafica date (per profilo/persona) + job giornaliero che
      genera un promemoria/notifica (Telegram + eventuale push HA) il giorno
      dell'evento, con anticipo configurabile. Onomastici: mappa nome → data
      dal calendario dei santi (o tabella). Integrare con i profili esistenti e
      con lo scheduler/notifier già presenti.

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

## Priorità suggerita

1. Fix climate + resolve-entity in LARIA (robustezza HA).
2. Verifica docker build.
3. Migrazione `haria.db` (partire coi dati veri).
4. Notifiche eventi/compleanni/onomastici.
5. Chat streaming.
Il resto = maturazione.
