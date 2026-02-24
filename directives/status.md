# Status — 24 Fevrier 2026 (Session 57)

> Last updated: 2026-02-24T17:00:00+01:00

### Session 57 — 24 fevrier 2026 (14:00+)
- **Objectif**: Fix eval scripts, disable LOCAL fallback, debug all 4 pipelines
- **Actions**:
  - DISABLED LOCAL fallback in run-eval-parallel.py (was masking pipeline failures with fake accuracy)
  - DISABLED --local-pipelines flag with guard
  - Fixed .env.local: added `export` to all 28 vars (child process inheritance)
  - Fixed live-writer.py: race condition with PID+thread+counter tmp filenames
  - Killed eval PID 426220 (was using LOCAL fallback)
  - Ran 5 background debug agents: Quantitative, Orchestrator, CS rag-tests, CS data-ingestion, API keys
  - Committed + pushed (commit 2a72686)
- **Resultat**: ALL 4 HF Space webhooks unreachable. HF Space healthz HTTP 000 (completely down at session end). LOCAL fallback permanently disabled. Root causes identified for all 4 pipeline failures.
- **Key Discovery**: Phase 1 and Phase 2 accuracy numbers (~65%, ~62%) were INFLATED by LOCAL fallback calling OpenRouter directly, bypassing the entire n8n RAG pipeline. Real pipeline accuracy is much lower.

### Session 56 — 24 fevrier 2026 (10:30+)
- **Objectif**: Cleanup + launch full 1000q parallel eval + create max infra
- **Actions**: Aggressive cleanup, renewed HF API key, launched 1000q eval, created docker-compose + GH Actions
- **Resultat**: Standard running ~62%, Graph early-stopped 51.5%, Quant+Orch early-stopped 0%

### Session 55 — 24 fevrier 2026 (03:00+)
- **Objectif**: Fix API credits (Cohere + Jina) and launch 1000q eval
- **Resultat**: Webhooks reachable but application errors. Chatbot LIVE 7/7 tests passing.

### Phase 2 cumulative results (Session 57 — CORRECTED)
| Pipeline | Tested | Total | Real Accuracy | Status |
|----------|--------|-------|---------------|--------|
| Standard | ~600 | 1000 | **~36%** (no fallback) | **BLOCKED** — HF Space DOWN |
| Graph | **500** | 500 | **78%** (Phase 1 only) | **COMPLETE** (Phase 1) |
| Quantitative | **500** | 500 | **92%** (Phase 1 only) | **COMPLETE** (Phase 1) |
| Orchestrator | 57 | 1000 | **0%** | **BROKEN** — empty/timeout |

**NOTE**: Graph 78% and Quant 92% are Phase 1 numbers (200q baseline). Phase 2 (1000q) re-evaluation pending HF Space recovery.

### CRITICAL BLOCKERS
1. **HF Space DOWN** — healthz HTTP 000, all webhooks unreachable
2. **Quantitative n8n workflow** — doesn't read table_data/context from webhook body
3. **Orchestrator n8n workflow** — executeWorkflow returns empty (FIX-34)
4. **Standard dataset mismatch** — Phase 2 questions are general trivia, not in Pinecone KB
5. **LOCAL fallback was masking ALL failures** — Now permanently disabled

### Architecture (Session 57)
```
VM (34.136.180.66) — PILOTAGE ONLY (NO n8n, NO local eval)
  - Claude Code (Termius)
  - Git repos (mon-ipad + 6 satellites)
  - MCP servers (Pinecone, Neo4j, Supabase, Jina, Cohere, HF)
  - LOCAL fallback: PERMANENTLY DISABLED in code
  - .env.local: All vars exported
  - RAM: ~400MB available

HF Space — DOWN (healthz 000)
  - n8n 2.8.4 (was running, now unreachable)
  - All credentials imported (12/12)
  - 18 workflows (11 active)
  - 16GB RAM

Codespaces — 2 attempted
  - rag-tests: Docker broken (iptables)
  - data-ingestion: Was provisioning

OpenRouter API Keys — 6/7 working (~120 req/min)
```
