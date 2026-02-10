# Session Context -- Multi-RAG Orchestrator SOTA 2026

> This document is the entry point for any new session (human or agentic).
> Read this first, then consult `docs/data.json` for current metrics.

---

## Current State (Feb 10, 2026)

### Phase 1 -- COMPLETED
All Phase 1 exit criteria have been met.

| Pipeline | Final Accuracy | Target | Status |
|----------|---------------|--------|--------|
| **Standard** | 0% | 85% | CLOSE |
| **Graph** | 0% | 70% | CLOSE |
| **Quantitative** | 0% | 85% | CLOSE |
| **Orchestrator** | 0% | 70% | CLOSE |

### Phase 2 -- ACTIVE (1,000q Expansion)

| Pipeline | Target | Dataset Source | DB Status |
|----------|--------|---------------|-----------|
| **Graph** | >=60% | musique, 2wikimultihopqa | DB_READY (4884 entities) |
| **Quantitative** | >=70% | finqa, tatqa, convfinqa, wikitablequestions | DB_READY (450 rows) |

---

## Phase 2 Runbook

### Step 1: Verify DB readiness (already done)
```bash
cd ~/mon-ipad && git pull origin main
# DB already populated from previous PR
```

### Step 2: Run Phase 2 evaluation
```bash
# Set env vars first (see CLAUDE.md)

# Fast iteration on Phase 2 questions
python3 eval/fast-iter.py --label "Phase 2 baseline" --questions 10

# Full evaluation (Phase 1 + Phase 2)
python3 eval/run-eval-parallel.py --include-1000 --reset --label "Phase 2 baseline"

# Analyze
python3 eval/analyzer.py
```

### Step 3: Iterate on Phase 2
```bash
# If results are bad, fix workflows and re-test
python3 eval/fast-iter.py --only-failing --label "Phase 2 fix attempt"

# Check Phase 2 gates
python3 eval/phase-gate.py --phase 2
```

### Step 4: Use agentic loop for automated iteration
```bash
python3 eval/agentic-loop.py --phase 2 --full-eval --push --label "Phase 2"
```

---

## Agentic Workflow (NEW)

### Automated iteration loop
The agentic loop automates the entire evaluation cycle:
```bash
# Single iteration: deploy + fast-iter + analyze + gate check
python3 eval/agentic-loop.py --label "description"

# Full cycle with 200q eval
python3 eval/agentic-loop.py --full-eval --push --label "description"

# Multiple iterations until gates pass
python3 eval/agentic-loop.py --max-iterations 5 --full-eval --push

# Phase 2 with auto-transition
python3 eval/agentic-loop.py --phase 2 --full-eval --push --phase2-transition
```

### GitHub Actions (auto-runs every 6 hours)
- `.github/workflows/agentic-iteration.yml` -- Full agentic workflow
- Modes: fast-iter, full-eval, agentic-loop, gate-check, phase2-transition
- Auto-creates issues on regression
- Auto-transitions to Phase 2 when gates pass

---

## Key Scripts

| Script | Purpose | Speed |
|--------|---------|-------|
| `eval/agentic-loop.py` | **Full automated iteration cycle** | Varies |
| `eval/phase-gate.py` | **Phase gate validator** | <1s |
| `eval/phase2-transition.py` | **Phase 2 transition automation** | <1s |
| `eval/fast-iter.py` | Quick validation, 10q/pipeline, parallel | ~2-3 min |
| `eval/run-eval-parallel.py` | Full 200q eval, all pipelines parallel | ~15-20 min |
| `eval/analyzer.py` | Post-eval analysis + recommendations | <1s |
| `eval/quick-test.py` | Smoke test, 3-5 known-good questions | ~1 min |

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
