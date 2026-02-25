# Status — 25 Fevrier 2026 (Session 61)

> Last updated: 2026-02-25T09:30:00+00:00

### Session 61 — 25 fevrier 2026 (07:00+)
- **Objectif**: Launch massive Phase 2 eval (4 pipelines × 1000q), deploy HF Space #2, activate all satellite repos
- **Actions**:
  - Launched parallel eval: 4 pipelines, 12 workers, auto batch sizes, PID 42258
  - Deployed HF Space #2 (lbjlincoln26-nomos-rag-engine-2.hf.space) — running but Orch blocked by sub-WF deps
  - Created 4 new n8n credentials (Jina, Cohere, HF Primary, HF Secondary)
  - Set GH secrets on 4 satellite repos (VERCEL_TOKEN, OPENROUTER_API_KEY, N8N_HOST, N8N_API_KEY)
  - Created + deployed GH Actions for 3 repos — ALL PASSING:
    - rag-pme-connectors: Deploy Website to Vercel
    - rag-data-ingestion: CI - Data Ingestion
    - rag-tests: CI - RAG Tests
  - Verified chatbot: 9/12 tests pass (75%), ~2.3s response time
  - Audited data-ingestion: Dataset Ingestion WORKING, Ingestion V4.0 + Enrichissement V4.0 BROKEN (Redis)
  - Regular git pushes to origin (3 commits during session)
- **Resultat**: Eval running (PID 42258, ~80 results/127 log lines at session end). All infrastructure active. HF Space #2 partially working.

### Session 60 — 25 fevrier 2026 (00:00+)
- **Objectif**: Fix all 4 pipelines, deploy chatbot, CLAUDE.md overhaul
- **Actions**: Fixed Quantitative (API key NaN + Supabase wrong host), Fixed Orchestrator (Redis removed, 9 nodes), CLAUDE.md 27→15 rules
- **Resultat**: ALL 4 PIPELINES WORKING (5/5 each). Chatbot deployed on all sites.

### Session 59 — 24 fevrier 2026 (20:00+)
- **Objectif**: Fix HF Space, diagnose pipeline failures
- **Resultat**: HF Space rebuilt, Standard + Graph confirmed working

### Phase 2 Eval Progress (Session 61 — LIVE, 74 results)
| Pipeline | Tested | Total | Pass | Accuracy | Avg F1 | Status |
|----------|--------|-------|------|----------|--------|--------|
| Standard | 20 | 1000 | 15 | 75.0% | 0.650 | RUNNING |
| Graph | 20 | 980 | 4 | 20.0% | 0.140 | RUNNING |
| Quantitative | 21 | 970 | 4 | 19.0% | ~0.16 | RUNNING |
| Orchestrator | 16 | 1000 | 13 | 81.2% | 0.686 | RUNNING |
| **TOTAL** | **~80** | **3950** | **36** | **~45%** | — | **RUNNING** |

**NOTE**: Early results, sample too small. Eval PID 42258 continues in background.

### Infrastructure State (end of session)
| Component | Status | Detail |
|-----------|--------|--------|
| HF Space #1 | RUNNING | 14 workflows, all 4 RAG pipelines answering |
| HF Space #2 | PARTIAL | Debug Status OK, Quant HTTP 500, Orch blocked |
| VM | PILOTAGE | MCP servers + eval PID 42258 running |
| Supabase | OK | aws-1-eu-west-1, correct project ref |
| Pinecone | OK | 10,411 vectors (sota-rag-jina-1024) |
| Neo4j | OK | 19,788 nodes / 76,717 rels |
| GH Actions | 3/3 PASSING | pme-connectors, data-ingestion, rag-tests |

### BLOCKERS for Next Session
1. **Eval still running** — PID 42258, ~35-40h estimated. Must monitor, not kill.
2. **HF Space #2 Orchestrator** — References Standard/Graph sub-workflows by ID (don't exist on Space #2). Fix: replace Execute Workflow nodes with HTTP calls to Space #1.
3. **HF Space #2 Quantitative** — HTTP 500 (missing/invalid credentials on Space #2).
4. **Ingestion V4.0 + Enrichissement V4.0** — Redis lock nodes (Redis removed Session 42). Fix: same pattern as Orch Redis removal.
5. **Chatbot CORS** — Not configured for Vercel sites (chatbot works via direct webhook, not from browsers on Vercel domains).
6. **3 inactive workflows** — WhatsApp Bridge, Action Executor, Multi-Canal Gateway (missing credentials).

### Key Credential IDs (HF Space #1)
| Credential | ID | Status |
|-----------|-----|--------|
| Supabase Postgres | Ut8VCPreZHrMt17M | WORKING |
| OpenRouter Standard | TFM3Q663LHfBcIAc | WORKING |
| OpenRouter Graph | VIFun2QQQlekGLiA | WORKING |
| OpenRouter Quantitative | ccrJrp4Z0BL54iIM | WORKING |
| OpenRouter Orchestrator | poTgoaQxqSSYbckv | WORKING |

### Architecture (Session 61)
```
VM (34.136.180.66) — PILOTAGE ONLY
  - Claude Code (Termius)
  - Git repos (mon-ipad + 6 satellites)
  - MCP servers (Pinecone, Neo4j, Supabase, Jina, Cohere, HF, n8n)
  - Eval PID 42258 (background, 4 pipelines × 1000q)
  - RAM: ~400MB available

HF Space #1 (lbjlincoln-nomos-rag-engine.hf.space)
  - n8n 2.8.4 RUNNING
  - 14 workflows (11 active, 3 inactive)
  - 4 RAG pipelines: Standard, Graph, Quantitative, Orchestrator
  - 16 credentials
  - 16GB RAM

HF Space #2 (lbjlincoln26-nomos-rag-engine-2.hf.space)
  - n8n RUNNING (debug status OK)
  - Quantitative imported (HTTP 500)
  - Orchestrator imported (CANNOT ACTIVATE — sub-WF deps)
  - 21 env vars configured

GH Actions — ALL 3 PASSING
  - rag-pme-connectors: Vercel deploy
  - rag-data-ingestion: CI validation
  - rag-tests: CI validation

OpenRouter API Keys — 6 keys across 3 accounts
  - Per-pipeline isolation (Standard, Graph, Quant, Orch, PME, Spare)
```
