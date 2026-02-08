# Session Context — Multi-RAG Orchestrator SOTA 2026

> This document is the entry point for any new session (human or agentic).
> Read this first, then consult `docs/data.json` for current metrics.

---

## Current State (Feb 8, 2026)

### Pipeline Status (from latest smoke tests)

| Pipeline | Smoke Test | Last Accuracy | Target | Gap | Status |
|----------|-----------|---------------|--------|-----|--------|
| **Standard** | 5/5 PASS | 83.6% | 85% | -1.4pp | PLATEAUED — close to target |
| **Graph** | 5/5 PASS | 76.4% | 70% | +6.4pp | ON TARGET |
| **Quantitative** | 4/5 PASS | 65.5% | 85% | -19.5pp | NETWORK errors in last iter |
| **Orchestrator** | 1/3 PASS | 20.0% | 70% | -50pp | CRITICAL — 80% error rate |

### Key Numbers
- 200 unique questions, 396 total test runs across 3 iterations
- 25 questions improving, 14 regressing, 161 stable
- 17 flaky questions (inconsistent across runs)
- 13 regressions in last iteration (mostly NETWORK errors on quant, TIMEOUT on orch)

---

## How the System Works

### Evaluation Pipeline
```
workflow-sync.py          →  Pull workflow JSON from n8n
                              ↓
quick-test.py             →  Smoke test (5q/pipeline)
                              ↓
run-comprehensive-eval.py →  Full eval (50q/pipeline)
                              ↓
live-results-writer.py    →  Write to docs/data.json (v2 format)
                              ↓
agentic-analyzer.py       →  Analyze regressions, errors, gaps
                              ↓
docs/index.html           →  Dashboard (8 tabs, auto-refresh 15s)
```

### Data Format (v2)
`docs/data.json` contains:
- `meta{}` — status, phase, totals
- `iterations[]` — grouped test runs with per-question results
- `question_registry{}` — 200 unique questions with cross-iteration history
- `pipelines{}` — endpoints, targets, accuracy trends
- `workflow_versions{}` — current n8n workflow state (hash, nodes, models)
- `workflow_history[]` — version change log with diffs
- `quick_tests[]` — smoke test results
- `workflow_changes[]` — modification descriptions with before/after metrics

### Dashboard Tabs
1. **Test Matrix** — Questions x Iterations grid (green/red/yellow per cell)
2. **Smoke Tests** — Quick endpoint health checks (5q/pipeline)
3. **Iterations** — Timeline + iteration comparison (fixed/broken/improved)
4. **Questions** — Searchable explorer with full answer history
5. **Pipelines** — Accuracy/error/latency charts + category breakdown
6. **Workflows** — n8n workflow versions, hashes, node diffs
7. **Changes Log** — Workflow modifications + DB snapshots
8. **Agentic API** — Schema docs + decision rules for AI evaluator

---

## How to Resume Work

### Step 1: Sync workflows from n8n
```bash
python benchmark-workflows/workflow-sync.py
```
This pulls the latest workflow state, stores a snapshot, and computes diffs.

### Step 2: Run smoke tests
```bash
python benchmark-workflows/quick-test.py --questions 5
```
This tests 5 known-good questions per pipeline. If any fail, investigate before proceeding.

### Step 3: Run full evaluation (if needed)
```bash
python benchmark-workflows/run-comprehensive-eval.py \
  --types standard,graph \
  --label "After topK increase" \
  --description "Increased Standard RAG topK from 5 to 10" \
  --reset
```

### Step 4: Analyze results
```bash
python benchmark-workflows/agentic-analyzer.py
```

### Step 5: Commit + push
```bash
git add docs/ workflows/ logs/
git commit -m "eval: description of what was tested"
git push
```

---

## Workflow Modification Protocol

When modifying a workflow in n8n:

1. **Before**: Run `workflow-sync.py` to snapshot current state
2. **Before**: Run `quick-test.py` to establish baseline
3. **Modify** the workflow in n8n
4. **After**: Run `workflow-sync.py` again (captures diff)
5. **After**: Run `quick-test.py` to validate change didn't break anything
6. **If regression**: Revert in n8n, re-sync
7. **If stable**: Run full eval on affected pipeline

---

## Critical Blockers

1. **Orchestrator (20% accuracy, 80% error rate)**
   - Root cause: timeouts on sub-workflow chaining, empty responses
   - Fix needed: per-pipeline timeout guards, smart routing instead of broadcast
   - Blocked by: n8n execution timeout (30s)

2. **Quantitative NETWORK errors (10 in last iteration)**
   - Root cause: connectivity issues to n8n cloud during eval
   - May be transient — retest needed

3. **Standard RAG plateaued at 83.6%**
   - Close to 85% target
   - Low F1 scores even on passing answers (verbose responses)
   - Fix: prompt tuning for conciseness, topK increase

---

## File Map

| File | Purpose |
|------|---------|
| `docs/index.html` | Dashboard (8 tabs) |
| `docs/data.json` | All evaluation data (v2 format) |
| `workflows/manifest.json` | Workflow version tracking |
| `workflows/snapshots/*.json` | Full workflow JSON snapshots |
| `benchmark-workflows/run-comprehensive-eval.py` | Main eval script |
| `benchmark-workflows/live-results-writer.py` | Data writer (v2) |
| `benchmark-workflows/quick-test.py` | Endpoint smoke tests |
| `benchmark-workflows/workflow-sync.py` | Pull workflows from n8n |
| `benchmark-workflows/agentic-analyzer.py` | Automated analysis |
| `benchmark-workflows/deploy-corrected-workflows.py` | Deploy to n8n |
| `.github/workflows/rag-eval.yml` | Daily eval runner |
| `.github/workflows/agentic-eval.yml` | Post-eval analysis |
| `.github/workflows/dashboard-deploy.yml` | Auto-deploy dashboard |
| `.github/workflows/n8n-error-log.yml` | n8n error receiver |
| `CLAUDE.md` | Full project context (architecture, roadmap) |

---

## Environment Variables

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export PINECONE_API_KEY="..."
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="..."
export OPENROUTER_API_KEY="..."
export N8N_API_KEY="eyJhbGci..."  # JWT token for n8n cloud API
export N8N_HOST="https://amoret.app.n8n.cloud"
```
