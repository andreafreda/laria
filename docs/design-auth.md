# LARIA: design auth e identità (spec)

Doc interno (IT). Decisioni prese per autenticazione, utenti e isolamento dati.
Guida l'implementazione. Vedi anche `reflections.md` (privato) per i perché.

## Principi

- **Scope**: single-household multi-utente. 1 istanza LARIA = 1 famiglia, N persone.
  Isolamento tra famiglie = istanze separate (container + volume + sqlite per
  household), non filtro per-query. Multi-tenant condiviso (Postgres + colonna
  household + audit) rimandato a eventuale SaaS, dietro futura `StorageBackend`.
- **No terze parti** per il login (niente social/OAuth). Credenziali locali.
- **SMTP non obbligatorio**: il recupero password funziona senza email.

## Entità

### Profilo (membro della famiglia)
- Esiste per **ogni** persona di casa, anche neonati. Permanente.
- È il **soggetto dei dati**: riusa il `member` (food) e l'`owner` (finance
  accounts) già presenti nello storage (per ora come nome/stringa; un profilo li
  possiede).
- Un profilo **può** avere un login associato, oppure no.

### User (login)
- Identità di accesso, **opzionale**, **attaccata a un profilo** (0 o 1 login per
  profilo).
- Campi: username, password hash (pbkdf2 stdlib, salt + iterazioni; nessuna dep
  nuova), ruolo, profilo collegato, eventuale `telegram_chat_id` verificato.
- Ruoli: **owner** (admin pieno: utenti, settings, chiavi LLM, connettori),
  **adult** (usa l'assistente, gestisce i profili che tutela), **dependent**
  (profilo con login limitato, raro: di norma i dipendenti non hanno login).

### Tutela (guardianship)
- Relazione user(adult/owner) → profilo. Il tutore legge/registra i dati del
  profilo tutelato (es. genitore → figlio).
- Un profilo dipendente è gestito via tutela finché non gli si attacca un login.

### Crescita (continuità identità)
- Profilo permanente: la storia si accumula sotto un'unica identità.
- Quando un dipendente cresce: si **attacca un login al profilo esistente** (non
  si crea un'identità nuova), poi si riduce la tutela. Storia intatta.

## Token e sessione
- **JWT firmato** (HMAC-SHA256), stateless. Scadenza nel token (TTL corto +
  refresh, da definire in implementazione). Niente lookup DB a ogni richiesta.
- Segreto di firma da env (`LARIA_JWT_SECRET`).

## Bootstrap
- Primo avvio crea l'**owner** da env seed (`LARIA_ADMIN_USER` / `LARIA_ADMIN_PASSWORD`).
- Owner poi crea profili, attacca login, assegna tutele dal pannello admin.

## Recupero password (senza SMTP obbligatorio)
1. **Owner-reset**: l'owner resetta la password dei membri dal pannello admin.
2. **CLI sul box**: per l'owner stesso (è self-host, la macchina è tua).
3. **Telegram** (opzionale, sicuro a condizione): solo per user con
   `telegram_chat_id` **già legato e verificato** in allowlist. Genera una
   temp-pass via Telegram → **cambio forzato** al primo login. Senza binding
   preventivo, disabilitato (altrimenti chiunque scrive al bot).
4. **SMTP**: opzionale, aggiunto dopo solo se serve reset self-service via email
   (scenario SaaS).

## Impatti per canale
- **Web API**: protetta. `/api/chat` e gli altri ricavano user+scope dal token,
  non più da `user_id` nel body. Middleware aiohttp valida il JWT.
- **Telegram**: identità = `chat_id`, già autenticata da Telegram. Serve
  **allowlist** `chat_id` → user/profilo (non passa dal login web). Chat non in
  allowlist = nessun accesso.
- **HA connector / MQTT**: **identità di servizio** (token HA, cred broker), non
  una persona, nessun ruolo. Chi apre la UI passando da HA si logga comunque come
  user LARIA. SSO HA→LARIA = futuro opzionale, non ora.

## Memoria e dati
- finance/food/utilities restano **household-shared** (dati di casa).
- conversazioni e memoria semantica sono **per-profilo/utente** via
  `Scope(household, user_id)` (già presente).

## Hash e dipendenze
- Password: `hashlib.pbkdf2_hmac` (stdlib), salt per-utente, iterazioni alte.
- JWT: HMAC-SHA256 via stdlib (`hmac`+`hashlib`+base64url) o PyJWT (da decidere a
  implementazione; preferenza per minime dipendenze).
