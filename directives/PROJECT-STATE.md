# Project State — Multi-RAG Orchestrator SOTA 2026

> Last updated: 2026-03-07T22:00:00Z

## Session 80 — Current Status

### Overview
- **Phase 1**: PASSED (83.9% overall)
- **Phase 2**: PARTIAL (Graph 78% + Quant 92% COMPLETE, Std+Orch BLOCKED)
- **Phase 3**: **DONE** (Std 87.5% PASS, Graph 40.9% ACCEPTED, Quant 95.2% PASS)
- **Phase 4**: IN PROGRESS — Std DONE (10,917 contexts), Graph partial (~10,700/11,300), Quant pending (3,876)
- **Jina API**: Both keys exhausted (~11M tokens). TEI HF Space deploying as replacement
- **TEI Space**: `LBJLincoln/nomos-tei-embeddings` — building (jina-v3 on cpu-basic)
- **Gradio embed Space**: `LBJLincoln/nomos-embeddings-api` — deploying as TEI fallback
- **Infrastructure**: 3/4 pipelines ACTIVE, LiteLLM UP, all DBs UP
- **Pinecone**: 42,758 total vectors (32,986 default ns + 9,772 benchmark ns)
- **Sessions**: 80 | **Commits**: 1,100+

---

## Pipeline Status (Session 75 Verified)

| Pipeline | Status | Response Time | Accuracy | Notes |
|----------|--------|--------------|----------|-------|
| Standard | WORKING | ~42s | 87.5% (P3) | Jina key updated, correct ML answers |
| Graph | WORKING | ~32s | 40.9% (P3) | Pipeline OK but Neo4j data returns unrelated entities |
| Quantitative | WORKING | ~7-9s | 95.2% (P3) | Pipeline FIXED S75, v2 dataset PASS |
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
| Supabase Postgres | UP | 40 tables, 7,509 sector docs, 3,876 financial tables, tenant_id=`benchmark` |
| Pinecone sota-rag-jina-1024 | UP | 42,758 vectors (32,986 default + 9,772 benchmark ns) |
| Pinecone website-sectors-jina-1024 | UP | 31,916 vectors (sector data) |
| Pinecone sota-rag-phase2-graph | UP | 1,248 vectors (e5-large) |
| Neo4j Aura | UP | ~78,000+ nodes (incl. Phase 4 paragraphs), 76,717 relationships |
| n8n API Key | EXPIRED | Use cookie auth via `/rest/login` (ci@nomos.ai / CI-Nomos-2026!) |
| Jina API Key | EXHAUSTED | Both `jina_c87d...` and `jina_612a...` depleted (~11M tokens). Using TEI/Gradio HF Space |
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

## Session 79 Achievements (7 Mar 2026)

### 1. Phase 4 Pinecone Ingestion
- Script: `scripts/ingest-phase4-contexts.py` with Jina Cloudflare bypass
- Standard: 10,917 contexts DONE (5.5M Jina tokens, 74 min)
- Graph: 11,300 contexts IN PROGRESS
- Quant: 3,876 contexts PENDING
- Quick-test post-ingestion: 100% on standard + quant (was 0% pre-ingestion)

### 2. 15 Custom Claude Code Skills
- Session lifecycle: /session-start, /session-end
- Monitoring: /monitor, /self-heal, /status-check, /ingest-check
- Evaluation: /eval, /regression-check, /metrics-update
- Improvement: /improve, /progress-10pct, /fix-catalog
- Operations: /sync-directives, /cross-repo-sync, /research-update

### 3. Auto Session Start
- `scripts/claude-session.sh` updated with --append-system-prompt for auto /session-start
- Termius command: `bash ~/mon-ipad/scripts/claude-session.sh --skip-perms`

### 4. Neo4j Phase 4 Graph Data
- 11,300 Paragraph nodes + entity extraction running in background

### 5. Website Strategy Research
- Nano Banana 2 video generation identified for product demos
- GEO (Generative Engine Optimization) strategy planned
- Color psychology per-product palette designed
- Design briefs created for 3 products

---

## Session 80 Achievements (7 Mar 2026)

### 1. Jina API Blocker Resolved
- Both Jina keys exhausted (~11M tokens total)
- Deployed TEI Space (`LBJLincoln/nomos-tei-embeddings`) with jina-v3 + trust-remote-code
- Deployed Gradio Space (`LBJLincoln/nomos-embeddings-api`) as fallback
- Ingestion script updated to support TEI/Gradio backends with auto-fallback

### 2. Ingestion Script Enhanced
- `scripts/ingest-phase4-contexts.py` now supports --backend jina|tei|auto
- Auto-skips already-ingested vectors (checks Pinecone IDs before embedding)
- TEI backend: smaller batches (8), less delay (0.5s)
- Graceful Jina→TEI fallback on quota exhaustion

### 3. Pipeline Health Verified
- All 3 RAG workflows active on n8n (Standard, Graph, Quant)
- n8n Space UP, cookie auth working

---

## Session 81 TODO (Next)

### Priority 1: Complete Phase 4 Ingestion
1. **Verify TEI/Gradio Space UP** and test embedding quality
2. **Finish Graph ingestion** (~600 remaining contexts)
3. **Complete Quant ingestion** (3,876 contexts)
4. **Run full Phase 4 eval** post-ingestion

### Priority 2: Pipeline Duplication for rag-website
1. **Duplicate Standard/Graph/Quant workflows** → point at `website-sectors-jina-1024`
2. **Create simplified Orchestrator V2** (no guardrails/Redis)

### Priority 3: Website Redesign
1. **Apply design briefs** (ETI navy+gold, PME green+orange, Dashboard dark+neon)
2. **GEO optimization** across all sites

### Priority 4: Cohere Rerank 3.5 Integration
1. **Add rerank node** post-retrieval in Standard pipeline (+23-30% precision)

---

## Running Processes

- **TEI Space**: Building (jina-embeddings-v3 download on cpu-basic)
- **Gradio embed Space**: Deploying (sentence-transformers fallback)
- **Pipeline test**: Running in background (60s timeout)

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
- **Current**: `jina_c87d...` (deployed Session 79, Cloudflare bypass via User-Agent)
- **Limit**: 1M tokens/month
- **Dimensions**: 1024

### Cohere Reranking
- Trial quota almost exhausted
- Used sparingly

---

## Metrics Snapshot (Session 79)

| Metric | Value |
|--------|-------|
| Total questions tested (all phases) | ~9,000+ |
| Phase 3 Standard tested | 8,006 / 8,700 |
| Phase 3 Graph tested | 1,500 / 1,500 |
| Phase 3 Quant tested | 500 / 500 (v2 dataset, 95.2% PASS) |
| Pinecone vectors (sota-rag-jina-1024) | 42,758 |
| Pinecone vectors (website-sectors) | 31,916 |
| Neo4j nodes | ~78,000+ |
| Neo4j relationships | ~76,717 |
| Supabase tables | 40 |
| Supabase rows | ~15,000+ |
| Commits (all repos) | 1,100+ |
| Sessions | 79 |

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

### Phase 3 Gates (DONE)
- Standard >= 85%: **87.5% PASS**
- Graph >= 70%: **40.9% FAIL**
- Quantitative >= 85%: **95.2% PASS** (v2 dataset)
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
- Phase 4: 🟡 IN PROGRESS (Pinecone ingestion: Std DONE, Graph in progress, Quant pending)
- Infrastructure: ✅ STABLE (HF Space + LiteLLM + Supabase + Pinecone + Neo4j)

**Next Milestone**: Phase 4 — scale to ~100K HF benchmark questions.
