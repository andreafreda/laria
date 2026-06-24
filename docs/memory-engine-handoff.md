# Handoff — Motore di memoria (sessione dedicata)

> Brief self-contained per una **nuova sessione** che costruisce il **motore di memoria**
> come **repo separato** (prodotto/libreria riusabile). LARIA si sviluppa altrove e lo
> *consuma* come dipendenza. Leggere ANCHE `design-memory.md` (analisi completa).

## Missione
Costruire un **motore di memoria per agenti AI**: generico, **locale-first**, **open**,
**editabile**, **deterministico**, **provider-agnostico**, **riusabile fuori da LARIA**.
Prende il meglio dei sistemi esistenti + idee nostre. NON è legato al dominio di LARIA.

## Contesto (perché esiste)
Nasce dal progetto LARIA (assistente AI domestico standalone, fork di HARIA). La memoria
è "il vero core". Si è deciso di NON adottare un motore black-box ma **costruirne uno nostro**
sottile, con backend pluggable. Vedi `plan.md` e `design-memory.md` nel repo LARIA.

## Decisioni già prese (NON ridiscutere senza motivo)
1. **Confine**: motore **generico**; la **policy di estrazione** ("cosa ricordare") è **pluggable**, fornita dall'host. Il motore NON sa di finance/food/casa.
2. **Build-in nostro** (no scatola nera come cervello). SuperMemory/mem0 ammessi solo come *backend* opzionali dietro interfaccia.
3. **Storage fase 1**: **SQLite + sqlite-vec + FTS5** (1 file, locale, hybrid vettori+BM25, cross-OS). Dietro astrazione `StorageBackend` → poi LanceDB/DuckDB/pgvector per scala. (A scala famiglia la latenza è embedding+LLM, non l'indice.)
4. **Modello dati**: piramide **L0→L3** (stile TencentDB / OpenHuman Memory Tree):
   - **L0 Raw**: conversazioni/eventi grezzi (evidenza, append-only).
   - **L1 Atomic**: fatti/preferenze/vincoli/stati atomici (unità di recall).
   - **L2 Scene**: cluster per topic/progetto/giorno (riassunti).
   - **L3 Persona**: profilo stabile preferenze/stile (sempre in contesto, piccolo).
   Drill-down garantito L3→L2→L1→L0 (provenienza).
5. **Determinismo + editabilità**: fatti espliciti, **CRUD via API** (no agente che riscrive da solo). Markdown solo export/import opzionale, NON sorgente di verità (il DB lo è).
6. **Scope**: ogni item taggato `{household, user_id}`; access-control **al recall** (fatti privati non emergono nel contesto condiviso). Default: famiglia condivisa + spazio per-utente.
7. **Provenienza/fiducia**: ogni fatto ha fonte (detto-da-utente vs dedotto), confidenza, timestamp, link a L0. Non agire su dedotti a bassa confidenza senza conferma.
8. **Temporalità leggera**: campi `valid_from` / `superseded_by` + UPDATE-on-contradiction (stile mem0). NIENTE knowledge-graph pesante ora.
9. **Write async**: estrazione non bloccante (periodica + "memory flush" prima della compattazione del contesto), modello economico per l'estrazione.
10. **Recall ibrido**: vettori + keyword(BM25) + **re-rank** per recency/importanza/scope/task. Mai solo similarità.
11. **Embedder astratto**, default **locale** (Ollama/sentence-transformers), cloud opzionale (Voyage/OpenAI).

## Interfacce da progettare (bozza)
```
Embedder:        embed(texts) -> vectors
StorageBackend:  put/get/search(vector+keyword)/delete/snapshot   # sqlite-vec fase 1
MemoryBackend (API pubblica del motore):
  write(scope, items|raw)          # ingest L0; estrazione L0->L1->L2->L3 (pluggable)
  recall(scope, query, k, filters) -> items     # ibrido + re-rank, entro budget token
  get/update/delete(scope, id)     # CRUD editabile, deterministico
  forget(scope, selector)          # decay/TTL + cancellazione vera
  consolidate(scope)               # summarize/merge periodico, dedup
  export()/import()                # portabilità + migrazione
ExtractionPolicy (plugin host):    decide cosa diventa L1/L2/L3 da L0
```
Tutto swappable: `FtsBackend` (baseline), `LocalHybridBackend` (sqlite-vec, default),
`Mem0Backend`/`SuperMemoryBackend` (wrapper opzionali).

## Riferimenti (studiare, NON copiare-incollare; attenzione licenze)
- **TencentDB Agent Memory** (open, local, L0-L3) — modello dati di riferimento.
- **OpenHuman** (tinyhumansai/openhuman) — Memory Tree markdown+sqlite, summary per source/topic/day. ⚠️ **GPL3**: solo design, NON importare.
- **SuperMemory** (MIT, local, #1 benchmark) — recall; possibile backend.
- **mem0** (Apache-2.0) — estrazione fatti ADD/UPDATE/DELETE/NOOP; possibile backend.
- **Mirage** (Apache-2.0) — lezioni su ingestione/sharing/versioning (layer separato, vedi design-memory §3d).
- Idee da rubare: Letta (livelli), Zep (validità temporale). Da escludere: AWS AgentCore (cloud), LangMem (lega a LangGraph).

## Vincoli
- **Open repo pubblico** → zero segreti, zero dati personali nei test/codice/commit.
- **Lingua**: codice/README/commit in **inglese**; doc di design in italiano.
- **Licenza repo motore**: da scegliere (MIT se vogliamo adozione larga, o PolyForm come LARIA). DECIDERE all'inizio.
- **Nessuna dipendenza cloud obbligatoria**; nessun import GPL.
- Python (coerente con LARIA core). py>=3.11. Async.

## Nome (da decidere a inizio sessione)
Campo "memoria" SATURO (mneme/mnemo/engram/memora… tutti presi). Rosa coniata/obliqua libera
(verificata): **Cista** (preferito), **Arca**, **Larchive**. Scegliere e verificare PyPI/GitHub/dominio.

## Primo obiettivo concreto (PoC)
1. Init repo (nome scelto) + pyproject + licenza + .gitignore (segreti).
2. Interfacce `Embedder` / `StorageBackend` / `MemoryBackend`.
3. `LocalHybridBackend` su **sqlite-vec + FTS5** con modello L0-L3 minimale.
4. `write`/`recall`/`forget` funzionanti + test (no rete: embedder fake nei test).
5. Mini eval-set per misurare recall@k su casi realistici.

## Come si lega a LARIA
LARIA `core/` importa il motore come dipendenza; fornisce la propria `ExtractionPolicy`
(dominio finance/food/casa) e lo scope famiglia/utente. La sostituzione del backend non
tocca l'engine LARIA.
