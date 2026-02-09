# Session Context — Multi-RAG Orchestrator SOTA 2026

> This document is the entry point for any new session (human or agentic).
> Read this first, then consult `docs/data.json` for current metrics.

---

## Current State (Feb 8, 2026)

### Phase 2 Database: COMPLETE

All Phase 2 database ingestion is done:
- **Supabase**: 538 total rows (88 Phase 1 + 450 Phase 2: 200 finqa + 150 tatqa + 100 convfinqa)
- **Neo4j**: 19,788 nodes (4,884 Phase 2 entities) + 21,625 relationships
- **Pinecone**: 10,411 vectors (no changes needed)
- **Dataset**: 1,000 Phase 2 questions in `datasets/phase-2/hf-1000.json`

### Phase 1 Pipeline Status (from latest eval — gates NOT MET)

| Pipeline | Accuracy | Target | Gap | Errors | Status |
|----------|----------|--------|-----|--------|--------|
| **Standard** | 82.6% | 85% | -2.4pp | 5 | CLOSE — verbosity is main issue |
| **Graph** | 52.0% | 70% | -18pp | 21 | ITERATING — entity extraction failures |
| **Quantitative** | 80.0% | 85% | -5pp | 17 | ITERATING — SQL edge cases + network auth |
| **Orchestrator** | 49.6% | 70% | -20.4pp | 36 | CRITICAL — cascading timeouts + empty responses |
| **Overall** | **67.7%** | **75%** | **-7.3pp** | — | **Phase 1 gate: NOT MET** |

### Key Numbers
- 200 unique Phase 1 questions, 396 total test runs across 3 iterations
- 1,000 Phase 2 questions ready (500 graph + 500 quantitative)
- 25 questions improving, 14 regressing, 161 stable
- 17 flaky questions (inconsistent across runs)
- 80 error trace files in `logs/errors/`

---

## Next Steps (Priority Order)

### P0 — Pass Phase 1 Gates

#### Step 1: Set environment variables (CRITICAL BLOCKER)
```bash
export N8N_API_KEY="..."
export OPENROUTER_API_KEY="..."
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export N8N_HOST="https://amoret.app.n8n.cloud"
```

#### Step 2: Deploy workflow improvements
```bash
cd ~/mon-ipad && git pull origin main
python3 workflows/improved/apply.py --deploy
```

#### Step 3: Fast iteration test (10q/pipeline)
```bash
python3 eval/fast-iter.py --label "Iter 6: deploy apply.py P0 fixes"
```

#### Step 4: Full Phase 1 eval (200q)
```bash
python3 eval/run-eval-parallel.py --reset --label "Iter 6: P0 fixes deployed"
```

### P1 — Run Phase 2 Evaluation (1,000q)

Once Phase 1 gates pass (or are close enough to proceed):

```bash
# Phase 2 fast iteration (10q/pipeline, graph + quant only)
python3 eval/fast-iter.py --dataset phase-2 --label "Phase 2: baseline"

# Phase 2 full eval (1,000q, graph + quant only)
python3 eval/run-eval-parallel.py --dataset phase-2 --reset --label "Phase 2: baseline"
```

### P2 — Re-run Neo4j with --llm (when OpenRouter key renewed)
```bash
python3 db/populate/phase2_neo4j.py --reset --llm
```

---

## Root Cause Analysis (from Feb 8 deep dive)

### Orchestrator (49.6% — 36 errors, CRITICAL)
**Error breakdown**: 20 TIMEOUT + 16 EMPTY_RESPONSE
- **Cascading timeouts**: Broadcasts to ALL 3 sub-pipelines, waits for slowest
- **Response Builder V9 crash**: Gets empty `task_results` from timed-out sub-workflows
- **Query Router bug**: Leading space in `" direct_llm"` causes misrouting
- **Cache Hit bug**: Compares against string `"Null"` instead of boolean check
- **Fixes in apply.py**: 11 fixes (P0: Router, Cache, Response Builder, continueOnFail, Intent Analyzer single-pipeline preference)

### Graph RAG (52% — 21 errors, HIGH PRIORITY)
**All 21 errors are EMPTY_RESPONSE**
- **Entity extraction failures**: HyDE extracts wrong names → Neo4j lookup empty
- **Missing entities**: Historical figures not matched
- **Fixes in apply.py**: 7 fixes (P0: Fuzzy matching with Levenshtein, entity extraction rules, answer compression)

### Quantitative RAG (80% — 17 errors)
**Error breakdown**: 10 NETWORK (401 Tunnel auth) + 7 SERVER_ERROR (SQL failures)
- **SQL edge cases**: Multi-table JOINs, period filtering, entity name mismatch
- **Fixes in apply.py**: 8 fixes (P0: SQL hints, ILIKE, zero-row detection, Phase 2 table support)

### Standard RAG (82.6% — 5 errors)
**All 5 errors are SERVER_ERROR**: "No item to return" from Pinecone
- **Verbose answers**: Low F1 even on passing answers
- **Fixes in apply.py**: 6 fixes (P0: Answer compression, topK increase, HyDE improvement)

---

## Improvements Ready to Deploy

### Workflow patches (`workflows/improved/apply.py`)
- Orchestrator: 11 fixes targeting timeout cascade, routing bugs, Response Builder
- Graph RAG: 7 fixes for entity extraction, fuzzy matching, answer conciseness
- Standard RAG: 6 fixes for answer compression, topK, HyDE prompts
- Quantitative: 8 fixes for SQL generation, ILIKE, zero-row detection + Phase 2 tables
- Supports: `--local` (patch source files) + `--deploy` (push to n8n)

### Eval scripts
- `--dataset` flag: `phase-1` (200q), `phase-2` (1,000q), `all` (1,200q)
- Auto-adjusts pipeline types for Phase 2 (graph + quantitative only)
- Improved scoring: percentage matching, magnitude-aware numeric matching
- Phase 2 questions skip empty expected_answer entries

### Expected impact (Phase 1):
| Pipeline | Current | Expected After Fixes | Reasoning |
|---|---|---|---|
| Standard | 82.6% | ~88% | Answer compression reduces verbosity → higher F1 |
| Graph | 52.0% | ~65% | Fuzzy matching + entity rules fix 10-15 of 21 failures |
| Quantitative | 80.0% | ~85% | ILIKE + SQL hints fix 3-5 of 7 SQL errors |
| Orchestrator | 49.6% | ~68% | continueOnFail + null-safe Response Builder fix 15-20 of 36 |
| **Overall** | **67.7%** | **~77%** | **Above 75% Phase 1 gate** |

---

## Iteration Cycle Protocol

### Phase A: Fast Iteration (10q/pipeline, parallel)
```
A1: Pull latest              → cd ~/mon-ipad && git pull origin main
A2: Sync workflows           → python3 workflows/sync.py
A3: Smoke test               → python3 eval/quick-test.py --questions 5
A4: Fast iteration test      → python3 eval/fast-iter.py --label "description"
A5: Review results           → check logs/fast-iter/ and logs/pipeline-results/
A6: If bad → fix in n8n → repeat from A1
    If good → proceed to Phase B
A7: Commit results           → git add docs/ logs/ && git commit && git push origin main
```

### Phase B: Full Evaluation (200q or 1000q, parallel)
```
B1: Phase 1 eval             → python3 eval/run-eval-parallel.py --reset --label "..."
B2: Phase 2 eval             → python3 eval/run-eval-parallel.py --dataset phase-2 --reset --label "..."
B3: Analyze results          → python3 eval/analyzer.py
B4: Commit + push            → git add docs/ workflows/ logs/ && git commit && git push origin main
B5: Back to Phase A for next improvement
```

**Rule**: ONE change per iteration. Don't change multiple things at once.

### Key Scripts
| Script | Purpose | Flags |
|--------|---------|-------|
| `eval/fast-iter.py` | Quick validation, 10q/pipeline, parallel | `--dataset phase-2` |
| `eval/run-eval-parallel.py` | Full eval, all pipelines parallel | `--dataset phase-2` |
| `eval/run-eval.py` | Sequential eval (legacy/debug) | `--dataset phase-2` |
| `eval/quick-test.py` | Smoke test, 3-5 known-good questions | |
| `workflows/improved/apply.py` | Deploy workflow improvements | `--deploy` |

---

## Critical Blockers

1. **Phase 1 gates not met** — Need to deploy fixes and iterate before Phase 2 eval
2. **OpenRouter credits exhausted** — Need new key for orchestrator + graph LLM calls
3. **Orchestrator timeouts** — Sub-workflow chaining exceeds 60s
4. **Graph entity extraction** — Many entities not found in Neo4j

---

## File Map (Quick Reference)

| What | Where |
|------|-------|
| Project anchor | `CLAUDE.md` |
| This file | `STATUS.md` |
| Dashboard | `docs/index.html` |
| Eval data | `docs/data.json` |
| **Fast iteration** | **`eval/fast-iter.py`** |
| **Parallel eval** | **`eval/run-eval-parallel.py`** |
| Sequential eval (legacy) | `eval/run-eval.py` |
| Smoke test | `eval/quick-test.py` |
| Analyze | `eval/analyzer.py` |
| Live writer (thread-safe) | `eval/live-writer.py` |
| **Apply improvements** | **`workflows/improved/apply.py`** |
| Sync workflows | `workflows/sync.py` |
| Phase 1 questions | `datasets/phase-1/*.json` |
| **Phase 2 questions** | **`datasets/phase-2/hf-1000.json`** |
| Phase 2 readiness | `db/readiness/phase-2.json` |
| Phase 2 Supabase script | `db/populate/phase2_supabase.py` |
| Phase 2 Neo4j script | `db/populate/phase2_neo4j.py` |
| Phase strategy | `phases/overview.md` |
| Dataset manifest | `datasets/manifest.json` |
| Error traces | `logs/errors/` |
| DB snapshots | `logs/db-snapshots/` |
| Pipeline results | `logs/pipeline-results/` |
| Fast-iter snapshots | `logs/fast-iter/` |

---

## Environment Variables

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="sk-or-v1-..."  # EXPIRED — need new key
export N8N_API_KEY="..."
export N8N_HOST="https://amoret.app.n8n.cloud"
```
