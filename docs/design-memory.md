# LARIA — Design memoria persistente dell'agente (research & design)

> Doc interno (IT). **Tema centrale**: come LARIA ricorda. Qui NON si decide di pancia:
> si mappano cosa salvare, le architetture possibili (pro/cons) e i sistemi sul mercato.
> Principio guida: **astrazione** → qualunque motore scegliamo, deve essere sostituibile se
> ne emerge uno migliore. Stato: in valutazione (nessuna scelta finale).

## Principi (decisi)
- **Locale-first**: dato e recall sul posto (privacy, self-host Docker, no servizi obbligatori).
- **Astrazione/swappable**: interfaccia `MemoryBackend` + `Embedder` → cambiare motore senza toccare l'engine.
- **Embeddings astratti, default locale** (Ollama/sentence-transformers), cloud opzionale (Voyage/OpenAI).
- **Scope**: memoria **famiglia (condivisa)** + spazio **per-utente** (chi parla). Filtrabile per scope.
- Provider LLM-agnostica (la memoria non deve dipendere da Anthropic).

## 1. Cosa salvare (tassonomia)
| Tipo | Esempi | Volatilità | Note |
|---|---|---|---|
| **Conversazione raw** | ultimi N turni | alta | finestra in contesto; oggi c'è |
| **Riassunto** | sintesi turni vecchi | media | compressione lossy; oggi c'è |
| **Fatti semantici / preferenze** | "il salvadanaio Valeria è per la figlia", "Andrea odia i bonifici" | bassa | cuore della memoria nuova |
| **Episodica** | "il 12/6 abbiamo ricategorizzato le bollette" | media | utile per continuità ("ieri provammo X") |
| **Procedurale** | "per importare estratti usa il formato Postepay firmato" | bassa | how-to appresi |
| **Puntatori a dati di dominio** | "spesa media alimentari = X" | derivata | i dati veri stanno in tabelle finance/food, non duplicare |

Regola: la memoria-agente NON duplica i dati di dominio (finance/food sono già in DB);
memorizza *fatti/preferenze/contesto* e *come* usare i dati.

## 2. Architetture possibili (pro/cons)

### A. Flat full-text (HARIA oggi)
FTS5 su note + conversazioni + riassunto progressivo.
- ➕ semplice, zero dipendenze, locale.
- ➖ solo keyword (no semantica), summary lossy, piatta (no episodica/decay/priorità), recall scarso.

### B. Fatti + riassunto + RAG vettoriale (stile mem0)
Estrazione di fatti atomici da ogni scambio; ogni fatto ha testo+embedding+fonte+ts+confidenza;
operazioni ADD/UPDATE/DELETE/NOOP (dedup/aggiornamento); recall ibrido (vettori+keyword).
- ➕ recall semantico, dedup, aggiornamento fatti, footprint piccolo.
- ➖ qualità dipende dall'estrazione (1 LLM call/scambio), niente relazioni complesse.

### C. A livelli OS-like (Letta / MemGPT)
core memory (sempre in contesto) + recall (storia) + archival (vector store), paging gestito dall'agente.
- ➕ coerenza long-horizon ("ieri X fallì"), self-editing, open-source self-host.
- ➖ complessità+latenza, costo loop agentico, poco deterministico (cosa ricorda/dimentica).

### D. Knowledge graph temporale (Zep/Graphiti, Cognee)
fatti come grafo entità-relazioni con finestre di validità temporale.
- ➕ ragionamento temporale (fatti che cambiano nel tempo), relazioni ricche.
- ➖ costoso (Zep ~600k token/conv vs ~1.7k mem0), retrieval post-ingest a volte fallace, modello mentale ripido.

### E. File-based "LLM wiki della vita" (OpenClaw-style / Karpathy)
memoria = file **Markdown** nel workspace (fonte di verità) + SQLite+**sqlite-vec**; due livelli:
*daily log* append-only + *memoria curata* (fatti/preferenze/decisioni); `memory_search` ibrido
(vettori + BM25); **memory flush** prima della compattazione del contesto.
- ➕ trasparente/ispezionabile (file leggibili!), versionabile (git), locale, ibrido keyword+semantico,
  niente servizi esterni — combacia con "wiki della vita" e con come gira QUESTO assistente.
- ➖ struttura semi-libera (serve disciplina/curation), scaling su molti fatti da gestire.

### G. Piramide progressiva L0→L3 (TencentDB Agent Memory)
4 livelli che si distillano l'uno dall'altro:
- **L0 Raw Log**: conversazioni/eventi grezzi (evidence grounding, niente perdita).
- **L1 Atomic Memory**: fatti/preferenze/vincoli/stati estratti dal rumore.
- **L2 Scene Block**: cluster per progetto/topic/scenario (salvati in **Markdown**), recall contestuale.
- **L3 Persona**: profilo stabile di preferenze/stile utente.
Drill-down garantito Persona→Scenario(jsonl)→L0(refs); usa la Persona di default e scende agli
Atomi solo quando servono i dettagli. **Open-source, fully local, zero API esterne.**
- ➕ pragmatico (via di mezzo flat↔KG), locale, Markdown ispezionabile, riduce token, mappa la nostra tassonomia 1:1.
- ➖ pipeline di distillazione da gestire (estrazione L0→L1→L2→L3), giovane.
→ **Riferimento forte per LARIA**: è quasi esattamente "wiki della vita locale" + fatti, già strutturato.

### F. Ibrido (probabile direzione)
SQLite singolo (dati) + sqlite-vec (embeddings) + fatti atomici (B) **e/o** file Markdown curati (E),
recall ibrido, embedder astratto. Eventualmente un piccolo grafo per relazioni chiave (D-lite).

## 3. Sistemi sul mercato (snapshot 2026, da verificare)
| Sistema | Tipo | Self-host/locale | Licenza | Note |
|---|---|---|---|---|
| **mem0** | vettori+grafo+kv, estrazione fatti | sì (+ cloud) | Apache-2.0 | default "ricorda l'utente"; grande community; report di affidabilità sotto carico |
| **Zep / Graphiti** | KG temporale | parziale (cloud-first) | misto | top su query temporali; costoso in token |
| **Letta (MemGPT)** | runtime memoria OS-like | sì, open-source | Apache-2.0 | coerenza long-horizon; complesso/non deterministico |
| **Cognee** | KG da "tutto" | sì | open-source | costruisce grafo di conoscenza generico |
| **MemMachine** | memoria ground-truth per agenti personali | ? | ? | emergente (paper) |
| **OpenClaw memory** | file Markdown + sqlite-vec, hybrid search, flush | sì, locale | ? | = "wiki della vita"; ancora in evoluzione |
| **TencentDB Agent Memory** | piramide L0→L3 (vedi G) | **sì, fully local, zero API esterne** | open-source | candidato forte; Markdown+jsonl, drill-down, −token |
| **SuperMemory** | memory+context engine, graph | **sì, fully local (offline con Ollama), 1 binary** | **MIT** (repo OSS) | **#1 benchmark** (LongMemEval/LoCoMo/ConvoMem), MCP universale, multimodale. Candidato di primissima fascia. Esiste anche cloud a consumo (opzionale). |
| **OpenMemory (CaviraOSS)** | local persistent memory store | sì, locale | open | memoria locale per Claude/Copilot/Codex ecc.; da valutare |
| **"agent memory" (da chiarire)** | ? | ? | ? | nome ambiguo: capire se è prodotto specifico (es. AWS AgentCore Memory) o generico |
| **sqlite-vec / pgvector** | *infrastruttura* vettori | sì | open | mattoni per build-in (no logica memoria) |

## 3b. Analisi dettagliata per soluzione (pro/cons + fit LARIA)

Legenda fit: ⭐ forte · ◐ medio · ✗ debole (per i nostri criteri: locale, open, semplice, controllabile).

### mem0 — ⭐/◐
*Cosa:* memory layer "bolt-on"; estrae fatti dai messaggi e li distilla (ADD/UPDATE/DELETE/NOOP); store ibrido vettori+grafo+kv.
- ➕ default per "ricorda l'utente"; community enorme (47k★); footprint piccolo (~1.7k token/conv); self-host (Apache-2.0); aggiornamento/contraddizioni gestiti.
- ➖ qualità dipende dall'estrazione; report di affidabilità sotto carico (memorie non sempre indicizzate, recall fail); ingestion oltre la chat limitata; spinge il cloud a pagamento.
- *Fit:* ottimo come **backend** dietro la nostra interfaccia; rischio lock-in mentale ma è disaccoppiabile.

### SuperMemory — ⭐
*Cosa:* memory+context engine, grafo di memoria; 1 binary, offline con Ollama.
- ➕ **#1 sui benchmark** (LongMemEval/LoCoMo/ConvoMem); **MIT**, fully local; multimodale (PDF/img/video/code); MCP universale; veloce.
- ➖ progetto giovane in rapida evoluzione (API mobili); cloud a consumo affianca l'OSS (attenzione a feature solo-cloud); grafo = complessità.
- *Fit:* candidato di **primissima fascia** (open+local+top recall). Da provare come backend o riferimento.

### TencentDB Agent Memory — ⭐
*Cosa:* piramide progressiva L0→L3 (raw→atomic→scene(Markdown)→persona), fully local, zero API esterne.
- ➕ **locale, open, zero dipendenze cloud**; Markdown ispezionabile; drill-down con evidenza; riduce token (−61% con OpenClaw); struttura = nostra tassonomia 1:1.
- ➖ progetto recente; pipeline di distillazione L0→L3 da capire/operare; ecosistema piccolo.
- *Fit:* **fortissimo riferimento architetturale** (anche se non lo adottiamo, copiamo il modello L0-L3).

### Letta (MemGPT) — ◐
*Cosa:* runtime dove l'agente È la sua memoria; core/recall/archival con paging OS-like, self-editing.
- ➕ coerenza long-horizon ("ieri X fallì"); open-source self-host; potente per agenti autonomi.
- ➖ complesso, latenza/costo del loop; **non deterministico** (non sai esattamente cosa ricorda/dimentica); più "runtime" che "modulo".
- *Fit:* poco adatto se vogliamo **controllo/prevedibilità** (sistema famiglia). Buone idee (livelli) da rubare.

### Zep / Graphiti — ◐
*Cosa:* knowledge graph **temporale** con finestre di validità dei fatti.
- ➕ migliore sul ragionamento temporale (fatti che cambiano); relazioni ricche; modella l'evoluzione.
- ➖ **costoso** (~600k token/conv vs 1.7k mem0); retrieval post-ingest a volte fallace; cloud-first; modello mentale ripido.
- *Fit:* la temporalità ci serve, ma il costo/complessità ora è troppo. Tenere come ispirazione (validità temporale sui fatti).

### Cognee — ◐
*Cosa:* piattaforma memoria open-source che costruisce **knowledge graph** da dati eterogenei (doc/img/Slack…); backend grafo Kuzu in locale; pipeline "cognify"; 14 modalità di retrieval.
- ➕ grafo+vettori ibrido potente; **locale** (Kuzu) con Ollama; feature complete senza pagare; multi-fonte.
- ➖ orientato a "estrai conoscenza da documenti" più che memoria conversazionale; KG = complessità/manutenzione; può essere overkill per famiglia.
- *Fit:* utile se andremo verso KG/ingestione documenti; per ora pesante.

### OpenMemory (CaviraOSS) — ◐
*Cosa:* memory store **locale** persistente per app LLM (Claude desktop/Copilot/Codex…).
- ➕ locale, open, semplice, pensato per integrarsi con client esistenti.
- ➖ meno maturo/benchmarkato; feature di lifecycle (decay/contraddizioni) da verificare.
- *Fit:* candidato leggero locale; da valutare in PoC.

### Memary — ✗/◐
*Cosa:* memory layer leggero open (KG semplice + vector search), per **prototipazione**.
- ➕ accessibile, semplice, buono per imparare il graph-augmented memory.
- ➖ esplicitamente **non per produzione**; feature limitate.
- *Fit:* solo come riferimento didattico.

### Memobase — ◐
*Cosa:* memoria long-term **basata su profilo utente** per chatbot.
- ➕ centrato su user-profile/persona (utile per L3 persona); semplice.
- ➖ ambito stretto (profilo), meno su episodica/fatti generali.
- *Fit:* idee per il layer "persona"; non come motore unico.

### LangMem / LangGraph store — ◐
*Cosa:* primitive di memoria dentro l'ecosistema LangChain/LangGraph (checkpoint = short-term, store = long-term; estrazione async di fatti/preferenze).
- ➕ integrato se usi LangGraph; pattern chiari (short vs long); estrazione background.
- ➖ ci legherebbe a LangChain/LangGraph (dipendenza pesante che non vogliamo); valore minore fuori da quell'ecosistema.
- *Fit:* ✗ se non adottiamo LangGraph (non in piano).

### AWS Bedrock AgentCore Memory — ✗
*Cosa:* servizio gestito AWS: short-term (checkpoint) + long-term (estrazione async di fatti/preferenze/summary).
- ➕ zero infrastruttura, scalabile, integra LangGraph.
- ➖ **cloud/managed, lock-in AWS, dati fuori** → contro locale-first/privacy; a pagamento.
- *Fit:* ✗ per LARIA (viola locale-first).

### OpenHuman — ⭐ (riferimento) / ⚠️ licenza
*Cosa:* assistente personale local-first con **Memory Tree**: ogni sorgente (Gmail/Slack/GitHub/Notion/note)
→ Markdown canonico → chunk ≤3k token → scoring → **alberi di summary per-source/per-topic/per-day** → SQLite locale.
118+ integrazioni OAuth. Rust+Tauri.
- ➕ local-first, deterministico, **memoria leggibile** (Markdown), summary-tree = nostra L0-L3 con altro nome, tantissime integrazioni; valida la nostra direzione.
- ➖ **GPL3** (copyleft): non importabile nel nostro stack MIT/PolyForm senza contaminazione → usare come **riferimento di design**, non come dipendenza linkata. Rust+Tauri (stack diverso dal nostro Python).
- *Fit:* **riferimento architetturale top** (Memory Tree). Convergenza con TencentDB conferma il modello.

### Infrastruttura (mattoni, non logica di memoria)
- **sqlite-vec**: vettori dentro SQLite → ⭐ per noi (1 file, locale, zero servizi). 
- **pgvector**: vettori in Postgres → ◐ (quando passeremo a Postgres multi-tenant).
- **Chroma / Qdrant**: vector DB dedicati → ◐ (servizio extra; utili a scala).
- **txtai**: embeddings+search all-in-one → ◐ alternativa leggera.
Questi NON danno la logica di memoria (estrazione/decay/scope): la mettiamo noi o via uno dei motori sopra.

### Sintesi
- **Locali+open+forti**: SuperMemory (recall top), TencentDB (struttura ideale), mem0 (maturo), Cognee (se KG).
- **Da rubare idee, non adottare**: Letta (livelli), Zep (validità temporale).
- **Da escludere** (per locale-first): AWS AgentCore; LangMem se no-LangGraph.
- **Mattone base** se costruiamo noi: sqlite-vec.
- La nostra astrazione `MemoryBackend` permette di **partire con uno** (es. SuperMemory o build-in sqlite-vec sul modello L0-L3 TencentDB) **e cambiarlo** senza toccare l'engine.

Fonti (verificare, alcune 2026/near-future): mem0.ai/blog/state-of-ai-agent-memory-2026,
particula.tech (mem0 vs zep vs letta vs cognee), atlan.com best-frameworks-2026,
github coolmanns/openclaw-memory-architecture, mem0 openclaw integration guide.
⚠️ Alcune fonti potrebbero essere non verificate/speculative: confermare prima di basarci.

## 3c. Storage backend — esplorazione (performance & alternative)

Nota chiave: **a scala "famiglia" (10³–10⁴ memorie) la latenza di recall NON è l'indice**
(tutti μs–ms), ma **embedding + LLM**. L'indice conta oltre ~10⁵–10⁶ vettori. Quindi si sceglie
per **semplicità / portabilità / scala futura / hybrid (vettori+BM25)**, non per i μs.
Lo storage va **dietro un'astrazione** (`StorageBackend`) → sostituibile come il resto.

| Opzione | Embedded/Server | Vettori | Keyword/BM25 | Sweet-spot | Deps | Note |
|---|---|---|---|---|---|---|
| **SQLite + sqlite-vec (+FTS5)** | embedded, 1 file | brute/IVF | **FTS5 nativo** | ≤~1M | minime, cross-OS | semplice, hybrid out-of-the-box; consigliato fase 1 |
| **LanceDB** | embedded (Arrow) | **HNSW/IVF-PQ** | full-text index | milioni | media | 1M vett. <20ms (≈3-5ms tunato); multimodale, versioning |
| **DuckDB + VSS + FTS** | embedded, colonnare | HNSW | FTS | milioni + analytics | media | ottimo se faremo aggregazioni pesanti/SQL |
| **Chroma (embedded)** | embedded | HNSW | no BM25 nativo | ~10⁵ | py deps | semplice ma più pesante, no hybrid nativo |
| **FAISS / usearch + SQLite** | lib + file | ANN top | (SQLite FTS5) | milioni | C++/bindings | velocissimo ma è "solo indice": metadati/lifecycle a parte |
| **txtai** | embedded | (faiss) | sì | ~10⁵–10⁶ | py | all-in-one embeddings+search |
| **pgvector (Postgres)** | **server** | HNSW | tsvector | milioni, multi-tenant | Postgres | per fase cloud/multi-tenant |
| **Qdrant / Milvus / Weaviate** | **server** | HNSW top | ibrido | ≥10⁶ | servizio extra | scala grande; contro "locale semplice" |
| **Redis (vector)** | **server, in-mem** | HNSW | sì | bassa latenza | servizio+RAM | veloce ma RAM-bound |

**Raccomandazione fase 1:** **SQLite + sqlite-vec + FTS5** — un file, locale, cross-OS, hybrid
(vettori+BM25) nativo, zero servizi; perfetto per la scala famiglia e per il deploy Docker.
**Scala/futuro:** **LanceDB** (HNSW, multimodale, versioning) o **DuckDB+VSS** (se analytics);
**pgvector** quando andremo multi-tenant server. Tutti dietro `StorageBackend` → si cambia senza riscrivere la logica.

## 3d. Ingestione & sharing — lezioni da Mirage (layer separato dalla memoria)

Mirage (strukto-ai, Apache-2.0) NON è memoria: è un **filesystem virtuale unificato** che monta
sorgenti (S3/Drive/Slack/Gmail/Redis…) come un albero unico. Non lo adottiamo come motore, ma
**rubiamo idee** per il layer ingestione/sharing di LARIA (distinto dal motore di memoria):

- **Sorgenti come mount uniformi**: ogni fonte (banca, Gmail, HA, note) esposta con la stessa
  interfaccia → l'agente legge/scrive in modo uniforme. Per noi: un `SourceAdapter` comune per
  l'ingestione verso la memoria (separato dall'estrazione).
- **Cache a due livelli + stato condiviso (Redis)**: ripetere lavoro contro backend remoti colpisce
  lo stato locale, e la cache è condivisa tra worker/processi/macchine. Lezione per il nostro
  **sharing**: la memoria/cache deve poter essere condivisa tra più processi/istanze (UI, scheduler,
  canali) senza duplicazioni né race → opzione store condiviso (es. Redis) dietro astrazione.
- **Snapshot & versioning tipo git**: snapshot dello stato, clone per run paralleli, rollback.
  Lezione: la **memoria versionabile** (snapshot/rollback) è utile per audit, undo, e "memory flush"
  sicuri prima della compattazione.
- **Bash-compatibile / interfaccia minima**: qualunque LLM che sa bash sa già usarlo (zero vocabolario
  nuovo). Lezione: l'API di memoria deve essere **piccola e ovvia** (poche primitive) per qualunque modello.

In sintesi, separiamo 3 livelli: **(1) ingestione/sorgenti** (idee Mirage) → **(2) motore di memoria**
(L0-L3, nostro) → **(3) recall/contesto**. Lo sharing tra processi/istanze è una proprietà del layer
storage/cache, non del modello dati.

## 4. Astrazione (qualunque sia il motore)
```
Embedder (interface): embed(texts) -> vectors   # locale default, cloud opz.
MemoryBackend (interface):
  write(scope, items)            # fatti/eventi; estrazione+dedup interni
  recall(scope, query, k, filters) -> items   # ibrido keyword+semantico
  forget(scope, selector)        # decay/cancellazione
  consolidate(scope)             # riassunto/merge periodico
  export()/import()              # portabilità + migrazione da haria.db
scope = {tenant, household, user_id, module?}
```
Implementazioni intercambiabili: `FtsBackend` (A), `LocalHybridBackend` (B/E con sqlite-vec),
`Mem0Backend`, `LettaBackend`, … → si testano e si sceglie/cambia senza toccare l'engine.

## 5. Criteri di valutazione
qualità recall (semantico+temporale) · costo/latenza · **locale/privacy** · semplicità deploy
(meno servizi = meglio) · trasparenza/ispezionabilità · portabilità del dato · determinismo
(controllo su cosa ricorda/dimentica) · maturità/licenza.

## 6bis. DECISIONE fase 1 (presa)
**Backend di partenza: mem0**, MA **dietro un wrapper nostro** (`MemoryBackend`) →
cambio motore **plug & play**. mem0 dà recall semantico + estrazione/update fatti subito
(Apache-2.0, Python, locale). L'engine LARIA parla SOLO al nostro `MemoryBackend`, mai a mem0
direttamente. **Improvement successivo**: motore nostro (L0-L3 su sqlite-vec) come backend
alternativo, attivabile senza toccare l'engine. Niente lock-in.

Implementazione: `core/laria/memory/` con `MemoryBackend` (interfaccia), `Mem0Backend` (wrapper),
`Embedder` astratto. Test con backend fake (no rete).

## 6. Direzione provvisoria (storica, NON vincolante)
Forte candidato: **ibrido locale "wiki della vita" + fatti vettoriali** —
file Markdown curati (ispezionabili, versionabili) **+** SQLite/sqlite-vec per recall ibrido,
dietro `MemoryBackend`, con `Embedder` locale di default. Tiene la porta aperta a mem0/Letta
come backend alternativi grazie all'astrazione. Da confermare con un piccolo PoC/benchmark.

## 7. Domande aperte
- Estrazione fatti: automatica a ogni scambio (costo) vs on-demand/periodica?
- Markdown curati vs solo DB: o entrambi (file = sorgente, DB = indice)?
- Serve grafo/temporalità ora o dopo?
- Benchmark: come misuriamo il recall sui NOSTRI casi (famiglia/finance/food)?

## 8. Prossimo passo
PoC minimale `LocalHybridBackend` (sqlite-vec + fatti + recall ibrido) dietro l'interfaccia,
+ 1 backend FTS di baseline, per confrontare recall su casi reali. Poi si sceglie.
