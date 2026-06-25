# LARIA — spec UI completa (tutte le schermate)

Documento di progettazione del portale web LARIA: design system, shell di navigazione e
mockup di **ogni** schermata. Serve come riferimento unico per costruire/rifinire l'intera app
con un linguaggio coerente. Riferimenti: `docs/plan.md` (gap residui), HARIA `webpanel.py`.

Legenda mockup: `[..]` controllo/bottone, `▾` select, `‹ ›` nav, `[##==]` barra, `•` voce lista.

---

## 0. Design system (in `ui/src/theme/variables.scss`)

- **Un solo accento: teal brand.** Verde/rosso solo semantici (entrate/uscite, ok/scaduto/errore).
- Fondo off-white freddo (light) / off-black (dark). Mai sand, mai nero/bianco puri.
- Una scala radius (`--laria-radius` 16, `-sm` 10, `-pill`), una shadow tinta.
- Due pesi font (400 / 600). Sentence case ovunque. Niente trattino come connettore in prosa.
- `.laria-content-wrap` (max-width ~760) centra il contenuto sui grandi schermi.
- Dark mode pieno (`prefers-color-scheme`). Stati sempre: loading (skeleton), empty, error.
- Niente AI-tells (no gradient viola, no card uguali a triplette, no numeri finti).

### Shell / navigazione

`ion-split-pane`: menu laterale persistente su desktop, a scomparsa su mobile.

```
+-----------------+--------------------------------------+
|  LARIA          |  [≡] Page title              [action]|   header per pagina
|                 +--------------------------------------+
|  • Home         |                                      |
|  • Chat         |   .laria-content-wrap                |
|  • Finance      |     ... card ...                     |
|  • Food         |                                      |
|  • News         |                                      |
|  · (owner)      |                                      |
|  • Family       |                                      |
|  • System log   |                                      |
|  • Sign out     |                                      |
+-----------------+--------------------------------------+
```

Voci menu: Home, Chat, Finance, Food, News, [Family, System log] (solo owner), Sign out.
Pattern header pagina: toolbar titolo (+ azione a destra) e, dove serve, una seconda toolbar
con `ion-segment` (switch periodo/tab).

---

## 1. Login (`/login`)

Scopo: autenticazione. Schermo centrato, calmo, brand in alto.

```
+------------------------------------------+
|                                          |
|                LARIA                      |   wordmark + 1 riga tagline
|        your household, in one place       |
|                                          |
|   +----------------------------------+   |
|   | Username                         |   |
|   | [______________________________]|   |
|   | Password                         |   |
|   | [______________________________]|   |
|   | [ Sign in ]                      |   |   primary, full width
|   | invalid credentials (error)      |   |   error inline
|   +----------------------------------+   |
+------------------------------------------+
```

Stati: bottone busy ("Signing in…"), error inline. Su successo → Home (o /change-password se must_change).

---

## 2. Change password (`/change-password`)

Scopo: primo accesso / reset. Stesso layout centrato del login.

```
+------------------------------------------+
|   Set a new password                     |
|   New password     [________________]    |
|   Confirm          [________________]    |
|   [ Update password ]                    |
|   passwords do not match (error)         |
+------------------------------------------+
```

Validazione: match + lunghezza minima. Su successo → Home.

---

## 3. Home (`/home`)  — NUOVA, default post-login

Scopo: riepilogo a colpo d'occhio + accesso rapido.

Dati: total balance + net mese (`/api/finance/*`), pasti oggi (`/api/food/plan`),
voci spesa aperte (`/api/food/shopping`), briefing attivi (`/api/news/briefings`).

```
  Good morning, Andrea

  +----------------+  +----------------+
  | Net this month |  | Total balance  |     metric card x2
  |   +806.61      |  |   10,306.61    |
  +----------------+  +----------------+

  Quick links
  +---------+ +---------+ +---------+ +---------+
  | Finance | | Food    | | News    | | Chat    |   tile (icon + label + hint)
  | +806    | | 3 today | | 2 active| |         |
  +---------+ +---------+ +---------+ +---------+

  Today
  • Dinner: pasta
  • 4 items on the shopping list
```

Empty: hint "—". Tile → naviga.

---

## 4. Chat (`/chat`)

Scopo: conversazione con l'assistente (stesso engine del Telegram).

Dati: `POST /api/chat` (ora). Futuro: `/api/chat/ws` streaming token-by-token.

```
+------------------------------------------+
|  [≡] Chat                                |
+------------------------------------------+
|                                          |
|         user bubble (right, teal)  ▸     |
|   ◂  assistant bubble (left, surface)    |
|         ...                              |
|                                          |
+------------------------------------------+
|  [ type a message…           ] [ Send ]  |   input bar sticky in fondo
+------------------------------------------+
```

Stati: invio → bolla "…" placeholder finché arriva la risposta; error → bolla rossa.
Migliorie: auto-scroll, invio con Enter. (Streaming: fase successiva.)

---

## 5. Finance (`/dashboard`)

Scopo: panoramica economica. Switch **Week / Month / Year** + nav ‹ ›.

Dati: `/api/finance/summary?date_from&date_to` (week/month), `/trend` + `/category-year` (year),
`/balances`, `/goals`, `/budget-status` (month).

```
+------------------------------------------+
|  [≡] Finance                  [⤓ import]  |
|  [ Week | Month | Year ]                  |   segment
+------------------------------------------+
|        ‹   June 2026   ›                  |   period nav (cap su corrente)
|                                          |
|  +--------+ +----------+ +-------+         |
|  | Income | | Expenses | | Net   |        |   metric card (income verde, exp rosso)
|  | 2400   | | -1593    | | 806   |        |
|  +--------+ +----------+ +-------+         |
|                                          |
|  [ANNO] Expenses by month                 |   solo Year: bar chart 12 mesi
|  ▁▃▅▂▆▇▅▃▅▆▂▁                              |
|                                          |
|  Budget  [solo Month]                     |
|  groceries  240/300 · left 60  [##==] 80% |   ok/amber/over
|                                          |
|  Spending by category                     |
|  housing   820   [##########]             |
|  groceries 420   [#####]                  |
|                                          |
|  Balances                                 |
|  checking 2,006.61 · savings 8,300.00     |
|                                          |
|  Savings goals                            |
|  Summer trip   0 / 2000   [=]             |
+------------------------------------------+
```

Stati: empty per categorie/budget/goals. (Budget = da aggiungere; resto già fatto.)

---

## 6. Food (`/food`)

Scopo: cibo famiglia. Tab **Plan / Diary / Shopping / Pantry**.

### 6a Plan — switch Week/Month + nav ‹ ›
Dati: `/api/food/plan?date_from&date_to`.
```
  Plan  [ Week | Month ]      ‹  June 2026  ›
  +-- Mon 2 Jun -------------------+
  |  Breakfast  oats               |
  |  Dinner     pasta              |
  +--------------------------------+      (Month: salta giorni vuoti)
```

### 6b Diary — date nav + chart + storico
Dati: `/api/food/diary?date=`, nuovo `/api/food/diary/history?days=30`. Azione: Export CSV.
```
  Diary   ‹  2026-06-26  ›             [⤓ CSV]
  +-- Sam ------------------------------+
  | kcal 600/2000 · P40 C70 F20 · 💧500 |
  | Lunch  rice  600 kcal               |
  +-------------------------------------+
  kcal / day (last 30)   ▁▃▅▂▆▇▅▃
  History
  • 2026-06-25  sam, mara  4 meals  1850 →   (riga → diary di quel giorno)
```

### 6c Shopping — checkable + costo
Dati: `/api/food/shopping`, toggle `POST /api/food/shopping/toggle`.
```
  Estimated 42.50 (6/9 priced)
  [x] milk        1 L
  [ ] bread
```

### 6d Pantry — scadenze in evidenza
Dati: `/api/food/pantry`.
```
  Expiring soon
  • yogurt   2026-06-28
  Pantry
  • rice  1 kg
```

Stati: empty per ogni tab. (Plan-month, Diary-chart/storico, Export = da aggiungere.)

---

## 7. Profiles (`/profiles`)  — NUOVA

Scopo: profili nutrizionali famiglia + storico peso + modifica. Linkata da Food/Family.

Dati: `/api/food/profiles` (+ `macro_targets`), `/api/food/weight?member=`.
Salva: nuovo `POST /api/food/profile`.

```
  +-- Sam ----------------------------------------+
  | M · 38 · 178 cm · 74 kg · BMI 23.4            |
  | maintain · moderate · 2000 kcal               |
  | P 118 / C 225 / F 56 g                [Edit ▾]|
  |  [sex▾][age][height][weight]                  |
  |  [goal▾][activity▾][kcal target]              |
  |  [allergies][preferences][restrictions]       |
  |  [ Save ]   ✔ saved (BMI 23.4)                |
  |  Weight history                               |
  |  2026-06-01  74.0 kg  BMI 23.4                 |
  +-----------------------------------------------+
```

Stati: empty "No profiles yet"; Save busy/ok/error; ricalcolo BMI mostrato.

---

## 8. News briefings (`/news`)

Scopo: gestione briefing notizie programmati (cron → ricerca web → riassunto via Telegram).

Dati: `/api/news/briefings` (GET/POST/delete).

```
  +-- briefing -----------------------------+
  | 0 8 * * *                      [Delete] |
  | ai                                       |
  | football (gazzetta.it)                   |
  | up to 4 items per topic                  |
  +-----------------------------------------+

  New briefing
  Topics (one per line, optional | site1, site2)
  [__________________________________]
  Cron [0 8 * * *]   Max items [5]
  [ Add briefing ]
```

Stati: empty "No briefings yet"; error create.

---

## 9. Import statement (`/import`)

Scopo: caricare estratto banca (BancoPosta/Postepay) → import movimenti.

Dati: `POST /api/finance/import` (multipart account + file).

```
  Import statement
  Account [ checking ]
  [ choose file ]  statement.xlsx
  [ Import ]
  Imported 23, skipped 4 duplicates (postepay)   (result)
```

Stati: busy "Importing…", result success, error.

---

## 10. Family / Admin (`/admin`)  — owner only

Scopo: gestione household. Profili (anagrafica permanente), utenti (login), tutele.

Dati: `/api/admin/profiles`, `/api/admin/users` (+ create), reset-password, link-telegram, guardianships.

```
  Profiles
  • Sam (adult)     • Mara (adult)    • Lia (dependent)
  [ + Add profile ]   name [____] [dependent ▾]

  Users
  • sam  owner  → profile Sam  · telegram linked
  [ + Add user ]  username [__] role[▾] profile[▾] [Create]

  (azioni riga: reset password, link telegram, add guardianship)
```

Stati: empty, create busy/error. Solo owner (403 altrimenti).

---

## 11. System log (`/logs`)  — owner only

Scopo: errori catturati (ora scritti da `errors.report_error`). Clear.

Dati: `/api/system/logs`, `POST /api/system/logs/clear`.

```
  [≡] System log                       [ Clear ]
  +-----------------------------------------+
  | 2026-06-26 10:12 · web · error          |
  | unhandled error on /api/finance/trend   |
  +-----------------------------------------+
```

Stati: empty "No errors logged".

---

## Endpoint backend mancanti (delta per queste UI)

- `POST /api/food/profile` — upsert profilo (riusa `food.upsert_profile`, ricalcola BMI).
- `GET /api/food/diary/history?days=30` — riusa `food.get_logged_days`.
- `GET /api/food/export.csv?date_from&date_to` — riusa `food.export_meals`, `text/csv`.
- (Plan mese e Finance budget: endpoint già esistenti, basta usarli dalla UI.)

## Ordine di build

A. Backend delta (3 endpoint + test).
B. Profili view+edit (`/profiles`) + menu.
C. Finance budget (sezione Month).
D. Diary chart + storico + date nav; Export CSV.
E. Plan Week/Month.
F. Home (`/home`) + redirect post-login (default da chat → home).
G. Rifiniture: Login/Change-password/Chat/Import/Admin allineate al design system, stati loading/empty/error ovunque.

Ogni step: `ng build` verde + commit. Pagine nuove → route + voce menu.
