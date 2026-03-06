# Session State — 6 Mars 2026 (Session 74)

> Last updated: 2026-03-06T21:55:00Z

## Current Status: SESSION 74 — PIPELINE DEBUGGING + N8N PERSISTENCE DISCOVERY

### Session 74 Key Findings

1. **CRITICAL: n8n PATCH changes don't persist across HF Space restarts**
   - HF Space has NO persistent storage (`storage: null`, 1 replica)
   - REST API PATCHes update in-memory only, DB changes lost on Docker rebuild
   - Factory restart reverts to whatever is baked in the Docker image
   - **Solution**: Update `n8n/live/*.json` files and push to HF Space Git via `n8n/sync.py`
   - This explains why changes keep getting lost across sessions!

2. **LiteLLM Proxy WORKING** — `lbjlincoln-nomos-rag-engine-7.hf.space`
   - Master key: `sk-litellm-nomos-2026`
   - Model aliases: `smart` (Llama 70B), `fast` (Trinity+Gemma), `default` (Trinity)
   - All 5 Groq keys working (HTTP 200)
   - LiteLLM successfully routes and retries across 7 OpenRouter + 5 Groq + 1 Gemini keys

3. **Quant V5.0 Pipeline Issues**
   - `n8n/live/quantitative.json` has correct LiteLLM URLs but `model: 'llama-70b'`
   - Docker image bakes in older version with `model: 'llama-3.3-70b-versatile'` (Groq name)
   - "LiteLLM Proxy Key" credential was MISSING in n8n — created it (`0lRYcsfMxjrExYZn`)
   - n8n community edition: `$env.*` NOT supported (403 "Plan lacks license")

4. **Standard + Graph Pipelines** — REVERTED to Phase 3 configs
   - User will provide new Jina API key later
   - Phase 3 configs use Jina embeddings + LiteLLM for LLM + `sota-rag-jina-1024`

### Session 74 TODO (Next Session)

1. **Fix `n8n/live/quantitative.json`** — Change `model: 'llama-70b'` → `model: 'smart'` and sync via `n8n/sync.py` to persist changes
2. **Update `n8n/live/standard.json` and `n8n/live/graph.json`** with latest Phase 3 working configs
3. **Sync all workflow changes** via `n8n/sync.py` (not REST API PATCH!)
4. **Get Jina API key** from user for Standard/Graph embeddings
5. **Orchestrator** — still broken, ON HOLD

### Previous Session 73 Actions
   - Injects `period = 'FY'` for annual queries, prevents double-counting
   - Enhanced system prompt with HARD RULES and explicit SQL examples
   - Deployed to HF Space via PATCH REST API

2. **Graph Pipeline Fix** — DEPLOYED + VALIDATED (5/5)
   - MAX_DEPTH increased 2→3 with fallback guard
   - Enhanced HyDE entity extraction prompt (TECHNOLOGY, REGULATION, CONCEPT types)
   - Added domain-specific term extraction (cybersecurity, GDPR, etc.)
   - Added label-based Neo4j matching for better recall

3. **Orchestrator Fix (FIX-34)** — DEPLOYED, STILL FAILING
   - Replaced all 3 executeWorkflow nodes with httpRequest POST
   - Empty response persists — deeper issue in Execution Engine routing
   - ON HOLD for now, Quant+Graph are priority

4. **SOTA 2026 Ingestion** — IN PROGRESS (Codespace)
   - Codespace `ingestion-sota-x565xw4r744p2pvw7` created
   - 6 files created (652 lines):
     - `services/reranker/app.py` — Cross-encoder ms-marco-MiniLM-L-6-v2
     - `services/bm25/build_index.py` + `app.py` — BM25 hybrid + RRF fusion
     - `scripts/contextual_enrichment.py` — Anthropic-style context prefixes
     - `scripts/compact_qa_generator.py` — CompactRAG QA pairs
     - `scripts/validate_retrieval_quality.py` — Quality validation

---

## Previous Status: SESSION 72 — DOCS SYNC + GRAPH COMPLETE + QUANT REGEN

### Session 72 Actions

1. **Graph Phase 3 Eval** — **COMPLETE**
   - PID 987476 finished (process dead)
   - **1,500 questions tested, 614 correct → 40.9% accuracy**
   - Significant drop vs Phase 2 (78.0%) — Phase 3 questions are harder multi-hop (MuSiQue, 2WikiMultiHop, HotpotQA-bridge)
   - These questions require knowledge not in our Neo4j/Pinecone databases

2. **All CLAUDE.md Synced** — DONE
   - `CLAUDE.md` (principal): Phase 3 results, Pinecone 21,073 vec, sota-rag-integrated removed
   - `directives/repos/rag-tests.md`: Major refonte (Phase 1 PASSED, Phase 3 results, HF Space webhooks)
   - `directives/repos/rag-website.md`: Phase 3 status, sector data available (31,916 vectors)
   - `directives/repos/rag-dashboard.md`: Phase 3 metrics
   - `docs/executive-summary.md`: Session 72, Graph complete, Pinecone updated
   - All timestamps → 2026-03-06

3. **rag-data-ingestion** — ACTIVE
   - Session 72 (earlier): 34,095 records ingested, 31,916 sector vectors
   - Codespace running, 110 tests passing
   - CLAUDE.md already updated (2026-03-06T00:30:00Z)

4. **Quant Phase 3 Dataset Regeneration** — IN PROGRESS
   - Created `db/populate/regenerate_quant_phase3.py`
   - Queries Supabase `financials` table (24 rows: TechVision, GreenEnergy, HealthPlus x 8 periods)
   - Generates Q&A pairs with real expected answers from Supabase
   - Output: `datasets/phase-3/quantitative-500-v2.json`

### Phase 3 Eval Progress (FINAL)

| Pipeline | Total | Tested | % | Accuracy | Status |
|----------|-------|--------|---|----------|--------|
| Standard | 8,700 | **8,006** | 92.0% | **87.5%** | **COMPLETE** — above 85% target |
| Graph | 1,500 | **1,500** | 100% | **40.9%** | **COMPLETE** — 614 correct |
| Quantitative | 500 | 500 | 100% | **30.0%** | DONE — **dataset INVALID** (regenerating v2) |
| Orchestrator | 1,000 | 0 | 0% | — | ON HOLD (user decision) |

### Database State (verified Session 72)

| Database | Index/Table | Count | Note |
|----------|------------|-------|------|
| Pinecone `sota-rag-jina-1024` | 12 namespaces | **21,073 vectors** | **ACTIVE** — used by all pipelines |
| Pinecone `website-sectors-jina-1024` | sectors | **31,916 vectors** | Sector data for chatbot (4 secteurs) |
| Pinecone `sota-rag` | 12 namespaces | 10,411 vectors | Legacy index |
| Pinecone `sota-rag-phase2-graph` | 1 namespace | 1,248 vectors | Graph-specific |
| ~~Pinecone `sota-rag-integrated`~~ | — | — | **DELETED Session 71** |
| Supabase | 8 key tables | ~12,432 rows | Unchanged |
| Neo4j | Reported | ~70,847 nodes | Unverifiable (HTTP 403) |

### rag-data-ingestion Status

**OBJECTIVE: Downloads DONE, ingestion COMPLETE**
- All downloads complete (16/16 HF + 18/18 sectors = 23,381 items)
- Direct Python ingestion pipeline working (34,095 records total)
- `website-sectors-jina-1024`: 31,916 vectors for chatbot
- CI: 110 tests passing
- CLAUDE.md updated Session 72

### rag-tests Status

**OBJECTIVE: Phase 3 — Standard + Graph COMPLETE, Quant regenerating**
- Standard: **8,006 tested, 87.5% accuracy — COMPLETE**
- Graph: **1,500 tested, 40.9% accuracy — COMPLETE**
- Quant: dataset invalid, regenerating v2 with correct Supabase values
- Last commit: updated Session 72

### Key Infrastructure

- 8 HF Spaces: ALL UP (round-robin for eval)
- VM: stable, pilotage only
- Dashboard: Live on Vercel (4 sites)
- No eval processes running (all complete or stopped)

### Running Processes

| PID | Started | Label | Status |
|-----|---------|-------|--------|
| ~~824008~~ | ~~Mar 4~~ | ~~Phase3-S70-stdquant~~ | **FINISHED** — Standard 8006/8700 done at 87.5% |
| ~~987476~~ | ~~Mar 5~~ | ~~Phase3-Graph-S71-clean~~ | **FINISHED** — Graph 1500/1500 done at 40.9% |
| ~~1006670~~ | ~~Mar 5~~ | ~~Phase3-Quant-NumFix-S71~~ | **FINISHED** — confirmed bad dataset |
| ~~1008882~~ | ~~Mar 5~~ | ~~Phase3-Quant-EvalFix-S71~~ | **FINISHED** — confirmed bad dataset |

### Next Steps

1. **Regenerate Quant dataset** with correct Supabase values → `quantitative-500-v2.json`
2. **Re-run Quant eval** with v2 dataset
3. **Analyze Graph accuracy drop** (78% Phase 2 → 40.9% Phase 3)
4. **Push directives** to all 6 satellites
5. **Decide on Orchestrator** — fix or deprioritize?
