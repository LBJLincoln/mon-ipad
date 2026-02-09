# Multi-RAG Orchestrator — SOTA 2026

## Session Start — READ FIRST

```bash
cat docs/status.json    # Live metrics, phase gates, blockers, next action (<3KB)
```

Then: fix the ONE pipeline with the worst gap → deploy → eval → commit → push.

**Phase roadmap**: Phase 1 (200q) → Phase 2 (1,000q) → Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+q)

---

## Key Commands

| Action | Command |
|---|---|
| **Live status** | `cat docs/status.json` |
| **Phase gates** | `python3 eval/phase_gates.py` |
| **Regenerate status** | `python3 eval/generate_status.py` |
| **Fast iter (10q)** | `python3 eval/fast-iter.py --label "..."` |
| **Full eval (200q)** | `python3 eval/run-eval-parallel.py --reset --label "..."` |
| **Phase 2 eval** | `python3 eval/run-eval-parallel.py --dataset phase-2 --reset --label "..."` |
| **Sync workflows** | `python3 workflows/sync.py` |
| **Deploy patches** | `python3 workflows/improved/apply.py --deploy` |
| **Smoke test** | `python3 eval/quick-test.py --questions 5` |

---

## Access

| Resource | Access | Note |
|---|---|---|
| n8n Webhooks + REST API | DIRECT | `amoret.app.n8n.cloud` |
| GitHub, Pinecone | DIRECT | git + HTTPS API |
| Supabase, Neo4j | BLOCKED | Proxy 403 — access via n8n workflows only |

DB population scripts (`db/populate/`) require user action on GCloud VM.

---

## Credentials

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export SUPABASE_API_KEY="sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
export N8N_HOST="https://amoret.app.n8n.cloud"
```

---

## Architecture (brief)

4 n8n RAG workflows on `amoret.app.n8n.cloud`:
- **Standard** — Pinecone vector search (webhook: `/webhook/rag-multi-index-v3`)
- **Graph** — Neo4j entity graph (webhook: `/webhook/ff622742-...`)
- **Quantitative** — Supabase SQL (webhook: `/webhook/3e0f8010-...`)
- **Orchestrator** — Routes to all 3 above (webhook: `/webhook/92217bb8-...`)

All LLMs: `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter ($0 cost).

**Full architecture details**: `docs/architecture.md`

---

## Rules

1. **ONE fix per iteration** — never change multiple pipelines simultaneously
2. **Phase gates enforced** — eval scripts block if prerequisites unmet (`--force` to override)
3. **Commit + push after every iteration** to keep agents in sync
4. **Workflow JSON via deploy scripts only** — never edit JSONs directly
5. **`docs/status.json` is auto-generated** — regenerated after every eval by `live-writer.py`
6. If accuracy < target → analyze `logs/errors/`, fix ONE root cause, re-test
7. If error rate > 10% → prioritize error fixes over accuracy
8. If 3+ regressions → REVERT last change immediately

---

## Key Files

| File | Purpose |
|---|---|
| `docs/status.json` | Compact live status (auto-generated, <3KB) |
| `docs/data.json` | Full eval data (1MB+, source of truth) |
| `docs/architecture.md` | Detailed architecture reference |
| `STATUS.md` | Human-readable status summary |
| `eval/generate_status.py` | Generates status.json from data.json |
| `eval/live-writer.py` | Writes eval results + auto-regenerates status.json |
| `eval/phase_gates.py` | Phase gate validator |
| `workflows/improved/apply.py` | 30+ workflow patches + deploy |
| `phases/overview.md` | Full 5-phase strategy |
