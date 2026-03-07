# Project State — Multi-RAG Orchestrator SOTA 2026

> Last updated: 2026-03-07T14:00:00Z

## Session 77 — Current Status

### Overview
- **Phase 1**: PASSED (83.9% overall)
- **Phase 2**: PARTIAL (Graph 78% + Quant 92% COMPLETE, Std+Orch BLOCKED)
- **Phase 3**: **DONE** (Std 87.5% PASS, Graph 40.9% ACCEPTED, Quant 95.2% PASS)
- **Phase 4**: STARTING (~100K questions from 13 HF benchmarks)
- **Claude Code**: Updated to 2.1.71 (was 2.1.39). New: /simplify, /batch, auto-memory
- **Infrastructure**: 3/4 pipelines ACTIVE, LiteLLM UP (9 models)
- **Sessions**: 77 | **Commits**: 1,100+

---

## Pipeline Status (Session 75 Verified)

| Pipeline | Status | Response Time | Accuracy | Notes |
|----------|--------|--------------|----------|-------|
| Standard | WORKING | ~42s | 87.5% (P3) | Jina key updated, correct ML answers |
| Graph | WORKING | ~32s | 40.9% (P3) | Pipeline OK but Neo4j data returns unrelated entities |
| Quantitative | WORKING | ~7-9s | 30% (P3) | Pipeline FIXED S75, dataset INVALID (need v2) |
| Orchestrator | 404 | — | — | ON HOLD (empty body issue) |

---

## Active Workflow IDs (Session 75)

| Pipeline | Workflow Name | ID | Status | Notes |
|----------|--------------|-----|--------|-------|
| Standard | WF5 Standard RAG V3.4 | `TmgyRP20N4JFd9CB` | ACTIVE | Uses Groq direct |
| Graph | WF2 Graph RAG V3.3 | `6257AfT1l4FMC6lY` | ACTIVE | Uses Groq direct |
| **Quantitative** | **WF4 Quant V3.1 (Local+LiteLLM)** | **cjhEhVs0KV1ExHqX** | **ACTIVE** | Fixed S75, uses LiteLLM |
| Quant V5.0 | WF4 Quant V5.0 (Clean) | `EW07B8H7OmoghE8Z` | INACTIVE | Deactivated S75 |
| Orchestrator | V10.1 orchestrator copy | `ALd4gOEqiKL5KR1p` | BROKEN | Empty body issue |

### Critical Discovery (FIX-71 — Session 75)
**DUPLICATE WORKFLOWS TRAP**: Multiple workflows can share the same webhook ID. Always check execution's `workflowId` to identify which workflow is actually running. In Session 75, V3.1 was active while V5.0 was being patched in vain.

---

## Phase Progress

### Phase 1 — Baseline (PASSED ✅ — 20 Feb 2026)
| Pipeline | Total | Tested | Accuracy | Target | Status |
|----------|-------|--------|----------|--------|--------|
| Standard | 200 | 200 | 85.5% | >= 85% | PASS |
| Graph | 200 | 200 | 78.0% | >= 70% | PASS |
| Quantitative | 200 | 200 | 92.0% | >= 85% | PASS |
| Orchestrator | 200 | 200 | 80.0% | >= 70% | PASS |
| **Overall** | **800** | **800** | **83.9%** | **>= 75%** | **PASS** |

### Phase 2 — HuggingFace Expansion (PARTIAL)
| Pipeline | Total | Tested | Accuracy | Target | Status |
|----------|-------|--------|----------|--------|--------|
| Standard | 1,000 | 579 | ~36% | >= 75% | STOPPED |
| Graph | 500 | **500** | **78.0%** | >= 55% | **COMPLETE** |
| Quantitative | 500 | **500** | **92.0%** | >= 65% | **COMPLETE** |
| Orchestrator | 1,000 | 57 | 0% | >= 70% | BROKEN |

### Phase 3 — Scale Testing (DONE — Mar 2026)
| Pipeline | Total | Tested | Accuracy | Target | Status |
|----------|-------|--------|----------|--------|--------|
| Standard | 8,700 | **8,006** | **87.5%** | >= 85% | **PASS** |
| Graph | 1,500 | **1,500** | **40.9%** | >= 70% | **ACCEPTED** — user decision: proceed to P4 |
| Quantitative | 500 | 500 | **95.2%** | >= 85% | **PASS** (v2 dataset) |
| Orchestrator | 1,000 | 0 | — | >= 70% | ON HOLD (not blocking P4) |

**Notes**:
- Standard Phase 3: **PASS** — 87.5% exceeds 85% target
- Graph Phase 3: 40.9% below target but user accepted (hard multi-hop questions + Neo4j data gaps)
- Quant Phase 3: **PASS** — 95.2% on v2 dataset (pipeline fixed S75)
- Orchestrator: ON HOLD, not blocking Phase 4
- **Phase 3 → Phase 4 GATE: PASSED** (Session 77 user decision)

---

## Infrastructure State

| Component | Status | Details |
|-----------|--------|---------|
| HF Space #1 | UP | n8n primary, 8 instances round-robin, 14 workflows (11 active) |
| HF Space #7 | UP | LiteLLM proxy, 9 models, 73 endpoints, auto key rotation |
| Supabase Postgres | UP | 40 tables, 24 financials rows, tenant_id=`benchmark` |
| Pinecone sota-rag-jina-1024 | UP | 21,073 vectors, 12 namespaces |
| Pinecone website-sectors-jina-1024 | UP | 31,916 vectors (sector data) |
| Pinecone sota-rag-phase2-graph | UP | 1,248 vectors (e5-large) |
| Neo4j Aura | UP | ~70,847 nodes, 76,717 relationships |
| n8n API Key | EXPIRED | Use cookie auth via `/rest/login` (ci@nomos.ai / CI-Nomos-2026!) |
| Jina API Key | NEW KEY | `jina_63fa...` deployed S75 (1024 dims) |
| VM Google Cloud | PILOTAGE ONLY | 34.136.180.66, ~413MB RAM available, n8n removed S42 |

---

## Session 75 Key Achievements (7 Mar 2026)

### 1. Jina API Key Replacement
- **New key**: `jina_63fa...` deployed to `.env.local`, Standard, Graph, Ingestion workflows
- **Old key**: Expired, causing all embeddings to fail
- **Impact**: Standard and Graph pipelines restored to working state

### 2. Quantitative Pipeline — 3 Cascading Bugs Fixed
- **FIX-69**: Postgres credential `cH96tQ3I9uIHqiiq` → `b44avEJtnkw46GL6` (working)
- **FIX-68**: SQL Validator now extracts SQL from markdown/CoT responses
  - Multi-strategy: JSON extraction, ```sql blocks, ```json blocks, regex fallback
- **FIX-70**: tenant_id default changed `'default'` → `'benchmark'`
- **FIX-71**: Discovered duplicate active workflows (V3.1 vs V5.0) sharing same webhook
  - V3.1 was active, V5.0 patched in vain
  - Lesson: Always check execution's `workflowId` to verify which workflow is running

### 3. Pipeline Validation
- **Standard**: OK (42s, correct answers after Jina key update)
- **Graph**: OK (32s, pipeline works but data relevance issues in Neo4j)
- **Quant**: FIXED (7-9s, returns correct financial data from Supabase)
- **Orchestrator**: 404 (still broken, ON HOLD pending user decision)

### 4. n8n Authentication
- **n8n API Key**: Expired (invalidates on HF Space rebuild)
- **Solution**: Cookie auth via `/rest/login` is the reliable fallback
- **Tool**: `scripts/n8n-api.py` for all n8n REST API operations

### 5. n8n 2.8+ Activation Requirements
- POST `/rest/workflows/{id}/activate` requires `{"versionId": "..."}`
- Get versionId from PATCH response before activating

---

## Session 77 Achievements (7 Mar 2026)

### 1. Phase 4 Dataset Generator Created
- `scripts/generate-phase4-datasets.py` — downloads & formats ~90K questions from HF
  - Standard: 7 datasets → ~50K (SQuAD v2, MS MARCO, HotpotQA, WebQ, TriviaQA, NQ, PubMedQA)
  - Graph: 3 datasets → ~17K (HotpotQA distractor, 2WikiMultiHopQA, MuSiQue)
  - Quantitative: 3 datasets → ~13K (FinQA, TAT-QA, WikiTableQuestions)

### 2. Phase 4 Quick Test (36 questions)
- Overall: 2.8% (expected — raw HF benchmark questions vs our domain-specific RAG)
- Standard: 0/16, Graph: 1/12, Quant: 0/8
- Confirms Phase 4 datasets are harder than Phase 1-3 curated questions

### 3. Claude Code Updated to 2.1.71
- New features: /simplify, /batch, auto-memory, HTTP hooks
- Termius snippet: `bash ~/mon-ipad/scripts/claude-session.sh "question"`

### 4. Dashboard & Status Updated
- `docs/data.json`, `docs/status.json`, `docs/tested_ids.json` refreshed
- 12,288 unique questions tracked, 63 iterations total

---

## Session 78 Achievements (7 Mar 2026)

### 1. Phase 4 Datasets V2 (SOTA Benchmarks)
- `scripts/generate-phase4-datasets-v2.py` — 18 SOTA benchmarks
- Standard: **39,805** questions (RAGBench×8, SQuAD v2, MS MARCO, TriviaQA, CRAG)
- Graph: **13,856** questions (RAGBench HotpotQA, HotpotQA, MuSiQue, MultiHop-RAG)
- Quant: **8,000** questions (RAGBench FinQA + TAT-QA)
- **Total: 61,661 questions** (was 35K in V1 — +75%)

### 2. Sector Ingestion COMPLETE (rag-data-ingestion)
- **Supabase**: 7,509 docs across 4 sectors (Finance 2,150 | Juridique 2,500 | BTP 1,844 | Industrie 1,015)
- **Neo4j**: 7,509 docs + entity extraction (law refs, courts, companies, metrics)
- New scripts: `ingest-all-sectors.py` (universal QA + corpus format handler)
- Bug fix: Supabase port 6543 → 5432 (transaction pooler doesn't persist)

### 3. Phase 4 Eval Run
- 244 questions tested: **4.9% accuracy** (Std 0%, Graph 0%, Quant 6.8%)
- Expected: HF benchmark data NOT in our vector DBs
- Quant best: partial Supabase financial table matches

### 4. Eval Auto-Discovery Fix
- `run-eval.py` now auto-discovers Phase 4 files by prefix (no more hardcoded names)

---

## Session 79 TODO (Next)

### Priority 1: Phase 4 Data Gap
1. **Ingest Phase 4 benchmark data into Pinecone** — currently only sector data, not the HF benchmark contexts
2. **Evaluate after ingestion** — accuracy should improve dramatically
3. **Scale to full 61K eval** (currently only 244 tested)

### Priority 2: rag-data-ingestion Completion
1. **Finance sectors** → Supabase tables + Neo4j entities
2. **Juridique sectors** → Neo4j relationships + Supabase
3. **Fix Enrichment V4.0** (HTTP 500)
4. **Post-Phase 4**: Connect to ETI website (rag-website)

### Priority 3: Eval Script Upgrades
1. **Auto model rotation on 429** (switch OpenRouter key automatically)
2. **Max batch sizes** per pipeline (already: std=10, graph=5, quant=3)
3. **Multiple HF Space round-robin** for throughput
4. **RAGAS metrics** integration (faithfulness, context recall)

### Priority 4: Orchestrator (DEFERRED)
- ON HOLD — not blocking Phase 4
- Revisit after Phase 4 completion

---

## Running Processes

None currently running.

---

## Critical Patterns & Pitfalls (Session 75 Discoveries)

### n8n Patterns
- **Login via Python only**: curl fails with "Failed to parse request body" (HTTP/2 + HF Space proxy)
- **Use cookie auth**: API key expires on HF Space rebuild
- **PATCH not PUT**: Workflow updates use PATCH method, PUT returns 404
- **PATCH does NOT persist**: HF Space has `storage: null`, changes lost on restart
  - Must update `n8n/live/*.json` and sync via `n8n/sync.py` for permanent changes
- **Activation requires versionId**: POST `/activate` needs `{"versionId": "..."}`
- **Disabled nodes pass through**: Data passes unchanged, but HTTP Request nodes STILL fire
- **Duplicate workflows**: Multiple workflows can share same webhook ID (FIX-71)

### Database Patterns
- **Supabase tenant_id**: Use `benchmark` (NOT `default`)
- **Postgres credential**: Use `b44avEJtnkw46GL6` (NOT `cH96tQ3I9uIHqiiq`)
- **Pinecone**: 21,073 vectors in sota-rag-jina-1024, 1024 dims

### LLM Patterns
- **LiteLLM proxy**: Auto key rotation across 7 OpenRouter + 5 Groq keys
- **Model aliases**: `default` (Trinity), `fast` (Trinity+Gemma), `smart` (Llama 70B)
- **Groq direct**: Standard and Graph use Groq directly (faster than LiteLLM)
- **SQL Validator**: Must extract SQL from markdown/CoT (multi-strategy parsing)

---

## Repository Structure (7 Repos)

| Repo | Role | Executor | Status |
|------|------|----------|--------|
| **mon-ipad** | Tower of control, directives, eval scripts | VM (Opus) | This repo |
| **rag-tests** | Eval scripts, datasets, results | VM → HF Space webhooks | Active |
| **rag-website** | Next.js 14, 4 sectors, chatbots | Codespace + Vercel | Live (nomos-ai-pied.vercel.app) |
| **rag-dashboard** | HTML/JS, live metrics read-only | Vercel | Live (nomos-dashboard-alexis-morets-projects.vercel.app) |
| **rag-data-ingestion** | Ingestion V3.1, Enrichment V3.1 | Codespace | 34,095 records ingested |
| **rag-pme-connectors** | Next.js 15, 15 apps, MacBook chat | Codespace + Vercel | Live |
| **rag-pme-usecases** | Next.js 14, 200 use cases | Vercel | Live |

---

## Credentials Status

### OpenRouter Keys (6 keys, 3 accounts)
- Per-pipeline rotation: OPENROUTER_KEY_STANDARD, GRAPH, QUANTITATIVE, ORCHESTRATOR
- Generic OPENROUTER_API_KEY removed from core workflows (Session 57)

### Groq Keys (5 keys)
- Used by LiteLLM proxy for fallback
- Standard and Graph use Groq direct (faster)

### Jina Embeddings
- **Current**: `jina_63fa...` (deployed Session 75)
- **Limit**: 1M tokens/month
- **Dimensions**: 1024

### Cohere Reranking
- Trial quota almost exhausted
- Used sparingly

---

## Metrics Snapshot (Session 75)

| Metric | Value |
|--------|-------|
| Total questions tested (all phases) | ~9,000+ |
| Phase 3 Standard tested | 8,006 / 8,700 |
| Phase 3 Graph tested | 1,500 / 1,500 |
| Phase 3 Quant tested | 500 / 500 (dataset invalid) |
| Pinecone vectors (sota-rag-jina-1024) | 21,073 |
| Pinecone vectors (website-sectors) | 31,916 |
| Neo4j nodes | ~70,847 |
| Neo4j relationships | ~76,717 |
| Supabase tables | 40 |
| Supabase rows | ~12,432 |
| Commits (all repos) | 1,100+ |
| Sessions | 75 |

---

## Gates & Targets

### Phase 1 Gates (PASSED ✅)
- Overall accuracy >= 75%: **83.9% PASS**
- Standard >= 85%: **85.5% PASS**
- Graph >= 70%: **78.0% PASS**
- Quantitative >= 85%: **92.0% PASS**
- Orchestrator >= 70%: **80.0% PASS**

### Phase 2 Gates (PARTIAL)
- Graph >= 55%: **78.0% PASS**
- Quantitative >= 65%: **92.0% PASS**
- Standard >= 75%: **~36% FAIL** (stopped)
- Orchestrator >= 70%: **0% FAIL** (broken)

### Phase 3 Gates (IN PROGRESS)
- Standard >= 85%: **87.5% PASS**
- Graph >= 70%: **40.9% FAIL**
- Quantitative >= 85%: **30% INVALID** (dataset issue, pipeline working)
- Orchestrator >= 70%: **ON HOLD**

---

## Key Files to Read (Session Startup)

```bash
cat directives/PROJECT-STATE.md                # This file (session state)
cat directives/PROCESS-RUNBOOKS.md             # Process & runbooks
cat technicals/debug/knowledge-base.md         # Persistent brain (24+ sections)
cat technicals/debug/fixes-library.md          # 71+ documented fixes
cat docs/executive-summary.md                  # Global project summary
source .env.local                              # Load environment vars
```

---

## Vision & Mission

**Vision**: Build a Multi-RAG Orchestrator SOTA capable of routing questions to 4 specialized RAG pipelines (Standard, Graph, Quantitative, Orchestrator) and achieving state-of-the-art performance on HuggingFace benchmarks.

**Current Reality**:
- Phase 1: ✅ PASSED (83.9% overall)
- Phase 2: 🟡 PARTIAL (Graph + Quant complete, Std + Orch blocked)
- Phase 3: ✅ DONE (Std 87.5%, Graph 40.9% accepted, Quant 95.2%)
- Phase 4: 🟡 STARTING (dataset generator ready, quick test done)
- Infrastructure: ✅ STABLE (HF Space + LiteLLM + Supabase + Pinecone + Neo4j)

**Next Milestone**: Phase 4 — scale to ~100K HF benchmark questions.
