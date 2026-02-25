# Session State — 25 Fevrier 2026 (Session 61)

> Last updated: 2026-02-25T09:15:00+00:00

## Current Status: MASSIVE PARALLEL EVAL RUNNING — ALL SYSTEMS ACTIVE

### Session 61 Progress

1. **Phase 2 eval launched** — 4 pipelines × 1000q, 12 workers, auto batch sizes (std=10, graph=5, quant=3, orch=2), PID 42258
2. **HF Space #2 deployed** — https://lbjlincoln26-nomos-rag-engine-2.hf.space (running but Orchestrator blocked by sub-workflow deps)
3. **4 new n8n credentials created** — Jina, Cohere, HF Primary, HF Secondary (total 16 on HF Space)
4. **GH secrets set** — VERCEL_TOKEN, OPENROUTER_API_KEY, N8N_HOST, N8N_API_KEY on rag-tests, rag-data-ingestion, rag-pme-connectors, rag-dashboard
5. **GH Actions workflows** — Being created for rag-pme-connectors (Vercel deploy), rag-data-ingestion (CI), rag-tests (CI + eval)
6. **Chatbot workflow** — Active on HF Space (ID: dfb1b9770f4b4a28a)
7. **Data ingestion workflows** — 3 active: Dataset Ingestion, Ingestion V4.0, Enrichissement V4.0

### Phase 2 Eval Progress (live)
- Eval PID 42258 running since 08:37 UTC
- ~50+ questions processed across all 4 pipelines (log buffered)
- data.json being actively updated

---

### Session 60 Progress (archived)

1. **CLAUDE.md overhaul** — 27 rules → 15 rules, false rules removed (Rule 8 seq tests), Codespace docs corrected
2. **Chatbot deployed on all 3 sites** — v1 (hardcoded) + v3 (RAG-enhanced) active on HF Space
3. **Quantitative pipeline FIXED** — Root causes:
   - Hardcoded API key in n8n expressions evaluated to NaN (`sk-or-v1-...` parsed as JS subtraction)
   - Supabase Postgres credential had wrong host (`aws-0` → `aws-1`) AND wrong project ref (`kfyrtsmdolgioyxsglbz` → `ayqviqmxifzmhphiqfmj`)
   - Fixed via n8n REST API: PATCH auth headers + create new credential + deactivate/reactivate with POST /activate
4. **Orchestrator FIXED** — Redis dependency removed (9 nodes bypassed/replaced):
   - 6 Code nodes modified to bypass Redis (Cache Parser, Cache Storage, Cache Semantic Search, Memory Merger, Redis Failure Handler, IF: Cache Hit?)
   - Memory Merger rewritten to Postgres-only mode (spreads Init V8 context through pipeline)
   - Conversational Handler defensive null checks added
   - 0% accuracy impact — Redis was only for caching/convenience, not core RAG
5. **All workflows Postgres credential updated** — 8 workflows patched with correct Supabase connection
6. **`.bashrc` stale env vars removed** — Old `N8N_HOST=http://34.136.180.66:5678` was overriding `.env.local`
7. **entrypoint.sh fixed** — Corrected Supabase host and user defaults
8. **Folder cleanup** — Deleted obsolete files, consolidated snapshots

### Pipeline Status (verified 04:00 UTC)
| Pipeline | Smoke | Status | Fix Applied |
|----------|-------|--------|-------------|
| Standard | 5/5 PASS | WORKING | Postgres credential updated |
| Graph | 5/5 PASS | WORKING | Postgres credential updated |
| Quantitative | **5/5 PASS** | **FIXED** (was 0/5) | Auth headers + Postgres host + project ref |
| Orchestrator | **5/5 PASS** | **FIXED** (was TIMEOUT) | Redis removed + Memory Merger context fix |

### Infrastructure State
| Component | Status | Note |
|-----------|--------|------|
| HF Space #1 | RUNNING | 14 workflows (11 active, 3 inactive) |
| HF Space #2 | BLOCKED | Both HF_TOKEN and HF_TOKEN_2 invalid/expired |
| VM | PILOTAGE ONLY | MCP servers active |
| Supabase | WORKING | Direct connection fixed (aws-1, correct project ref) |

### Workflow Credentials (session 60 new IDs)
| Credential | ID | Type | Status |
|-----------|-----|------|--------|
| Supabase Postgres (Fixed) | Ut8VCPreZHrMt17M | postgres | WORKING |
| OpenRouter (Standard) | TFM3Q663LHfBcIAc | httpHeaderAuth | WORKING |
| OpenRouter (Graph) | VIFun2QQQlekGLiA | httpHeaderAuth | WORKING |
| OpenRouter (Quantitative) | ccrJrp4Z0BL54iIM | httpHeaderAuth | WORKING |
| OpenRouter (Orchestrator) | poTgoaQxqSSYbckv | httpHeaderAuth | WORKING |
| Redis | FmGCS5UwjP5x5gRx | redis | NO LONGER NEEDED (Redis removed from Orch) |

### Key Fixes Applied (Session 60)
- **FIX-QT-AUTH**: Quantitative 4 HTTP nodes had hardcoded API key in expression mode → replaced with `$env.OPENROUTER_KEY_QUANTITATIVE`
- **FIX-QT-PG**: Supabase credential wrong host (aws-0→aws-1) + wrong user (kfyr→ayqv) → new credential Ut8VCPreZHrMt17M
- **FIX-ORCH-AUTH**: Orchestrator 4 HTTP nodes same hardcoded key issue → replaced with `$env.OPENROUTER_KEY_ORCHESTRATOR`
- **FIX-ORCH-REDIS**: 9 Redis nodes bypassed/rewritten — Cache Parser/Storage/Semantic always return cache_miss, Memory Merger rewritten to Postgres-only (spreading Init V8 context), Redis Failure Handler always returns degraded mode, IF Cache Hit always false
- **FIX-ORCH-CONV**: Conversational Handler defensive null checks — `(context.query || '').toLowerCase()` instead of `context.query.toLowerCase()`
- **FIX-ALL-PG**: All 8 workflows updated to use correct Supabase credential
- **FIX-ENTRYPOINT**: entrypoint.sh Supabase defaults corrected

### BLOCKERS (Remaining)
1. **HF Space #2** — Both HF tokens expired/revoked. User must regenerate
2. **3 inactive workflows** — WhatsApp Bridge, Action Executor, Multi-Canal Gateway (missing credentials/validation errors)

### Next Steps
1. Run Phase 2 eval on ALL 4 working pipelines (Standard 1000q, Graph 500q, Quant 500q, Orch 1000q)
2. Generate 1000q chatbot test dataset
3. Deploy entrypoint.sh fix to HF Space (next rebuild)
4. Deploy HF Space #2 (needs valid HF_TOKEN_2)

### Dataset Files
| File | Pipelines | Questions |
|------|-----------|-----------|
| datasets/phase-2/hf-1000.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/graph-quant-expansion-500x2.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/standard-orch-1000x2.json | standard(1000), orch(1000) | 2000 |
| datasets/phase-2/pme-gateway-1000.json | pme-gateway(1000) | 1000 |
| **TOTAL** | **5 pipelines** | **5000** |
