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

Fonti (verificare, alcune 2026/near-future): mem0.ai/blog/state-of-ai-agent-memory-2026,
particula.tech (mem0 vs zep vs letta vs cognee), atlan.com best-frameworks-2026,
github coolmanns/openclaw-memory-architecture, mem0 openclaw integration guide.
⚠️ Alcune fonti potrebbero essere non verificate/speculative: confermare prima di basarci.

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

## 6. Direzione provvisoria (NON vincolante)
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
