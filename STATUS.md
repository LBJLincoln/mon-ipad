# Session Context — Multi-RAG Orchestrator SOTA 2026

> This document is the entry point for any new session (human or agentic).
> Read this first, then consult `docs/data.json` for current metrics.

---

## Current State (Feb 8, 2026)

### Pipeline Status (from latest eval)

| Pipeline | Accuracy | Target | Gap | Errors | Status |
|----------|----------|--------|-----|--------|--------|
| **Standard** | 82.6% | 85% | -2.4pp | 0 | CLOSE — topK tuning helped |
| **Graph** | 52.0% | 70% | -18pp | 1 | ITERATING — entity extraction issues |
| **Quantitative** | 80.0% | 85% | -5pp | 14 | ITERATING — SQL edge cases + network errors |
| **Orchestrator** | 49.6% | 70% | -20.4pp | 37 | CRITICAL — 38% error rate (timeouts) |
| **Overall** | **67.7%** | **75%** | **-7.3pp** | — | **Phase 1 gate: NOT MET** |

### Key Numbers
- 200 unique questions, 396 total test runs across 3 iterations
- 25 questions improving, 14 regressing, 161 stable
- 17 flaky questions (inconsistent across runs)
- 102 error trace files in `logs/errors/`

---

## Iteration Cycle Protocol

Follow this for every iteration. See CLAUDE.md for detailed commands.

```
Step 0: Read current state (STATUS.md + docs/data.json meta)
Step 1: Sync workflows          → python workflows/sync.py
Step 2: Smoke test              → python eval/quick-test.py --questions 5
Step 3: Analyze failures        → python eval/analyzer.py
Step 4: Patch workflow in n8n   → then sync.py + quick-test.py
Step 5: Run evaluation          → python eval/run-eval.py --types ... --label "..."
Step 6: Commit + push           → git add docs/ workflows/ logs/ && git commit && git push
Step 7: Repeat from Step 3
```

**Rule**: ONE change per iteration. Don't change multiple things at once.

---

## Priority Fix Queue

1. **Orchestrator timeouts** (→48% to 70%): Per-pipeline timeout guards, smart routing
2. **Graph entity extraction** (→52% to 70%): Fuzzy matching, entity catalog in prompt
3. **Standard precision** (→82.6% to 85%): Prompt conciseness tuning
4. **Quantitative SQL edges** (→80% to 85%): SQL templates, data seeding

---

## Critical Blockers

1. **OpenRouter credits exhausted** — orchestrator + graph retests return empty/error
2. **Orchestrator timeouts** — sub-workflow chaining exceeds 60s
3. **Graph entity extraction** — many entities not found in Neo4j
4. **Quantitative** — employee table only 9 rows, product queries fail

---

## File Map (Quick Reference)

| What | Where |
|------|-------|
| Project anchor | `CLAUDE.md` |
| This file | `STATUS.md` |
| Dashboard | `docs/index.html` |
| Eval data | `docs/data.json` |
| Run eval | `eval/run-eval.py` |
| Smoke test | `eval/quick-test.py` |
| Analyze | `eval/analyzer.py` |
| Live writer | `eval/live-writer.py` |
| Iterate script | `eval/iterate.sh` |
| Sync workflows | `workflows/sync.py` |
| Deploy to n8n | `workflows/deploy/deploy.py` |
| Populate DBs | `db/populate/all.py` |
| Phase strategy | `phases/overview.md` |
| Dataset manifest | `datasets/manifest.json` |
| Error traces | `logs/errors/` |
| DB snapshots | `logs/db-snapshots/` |

---

## Environment Variables

```bash
export SUPABASE_PASSWORD="..."
export PINECONE_API_KEY="..."
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="..."
export OPENROUTER_API_KEY="..."
export N8N_API_KEY="..."
export N8N_HOST="https://amoret.app.n8n.cloud"
```
