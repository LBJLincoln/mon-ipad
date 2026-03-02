# Test Environment — Single Source of Truth

> Last updated: 2026-03-01T20:30:00Z (Session 67)

## 1. Eval Scripts Inventory

### Core Scripts (use daily)

| Script | Purpose | CLI Example |
|--------|---------|-------------|
| `eval/quick-test.py` | Smoke test (3-5q per pipeline, ~2 min) | `python3 eval/quick-test.py --questions 5` |
| `eval/run-eval-parallel.py` | Parallel eval across pipelines | `python3 eval/run-eval-parallel.py --max 200 --dataset phase-1` |
| `eval/iterative-eval.py` | Progressive gates (5→10→50q) | `python3 eval/iterative-eval.py --label "After fix X"` |
| `eval/phase_gates.py` | Phase transition enforcement | `python3 eval/phase_gates.py --phase 2 --json` |
| `eval/generate_status.py` | Generate docs/status.json from data.json | `python3 eval/generate_status.py` |

### Diagnostic Scripts (use when debugging)

| Script | Purpose | CLI Example |
|--------|---------|-------------|
| `eval/node-analyzer.py` | Node-level execution analysis | `python3 eval/node-analyzer.py --pipeline standard --last 5 -v` |
| `eval/golden-check.py` | Validate against golden thresholds | `python3 eval/golden-check.py --pipeline standard` |
| `scripts/analyze_n8n_executions.py` | Raw n8n execution data | `python3 scripts/analyze_n8n_executions.py --pipeline standard` |
| `scripts/pipeline-doctor.py` | Diagnose→Fix→Verify loop | `python3 scripts/pipeline-doctor.py --pipeline standard --apply` |
| `scripts/cross-repo-health.py` | All 7 repos + infra health | `python3 scripts/cross-repo-health.py --quick` |

### Support Scripts (background/automation)

| Script | Purpose | CLI Example |
|--------|---------|-------------|
| `eval/live-writer.py` | Dashboard data writer (thread-safe) | Called by eval scripts (not standalone) |
| `eval/progress_callback.py` | Progress reporter | Imported as module |
| `eval/tz_utils.py` | Paris timezone utilities | Imported as module |
| `scripts/openrouter-key-rotation.py` | Auto-rotate API keys on 429 | `python3 scripts/openrouter-key-rotation.py` |
| `scripts/openrouter-monitor.py` | Monitor key usage/limits | `python3 scripts/openrouter-monitor.py` |

---

## 2. Dependency Graph

```
quick-test.py ──────→ tz_utils.py + live-writer.py

iterative-eval.py ──→ run-eval.py ──→ tz_utils.py
                   ├─→ live-writer.py ──→ generate_status.py
                   ├─→ node-analyzer.py
                   └─→ phase_gates.py

run-eval-parallel.py ─→ run-eval.py
                     ├─→ live-writer.py
                     └─→ progress_callback.py

live-writer.py ──────→ generate_status.py ──→ phase_gates.py
```

**All scripts require**: `source .env.local` before execution.

---

## 3. Phase Gates (Single Source of Truth)

### Phase 1: Baseline (200 questions) — **PASSED** (2026-02-20)
| Pipeline | Target | Achieved | Status |
|----------|--------|----------|--------|
| Standard | ≥85% | 85.5% | PASSED |
| Graph | ≥70% | 78.0% | PASSED |
| Quantitative | ≥85% | 92.0% | PASSED |
| Orchestrator | ≥70% | 80.0% | PASSED |
| **Overall** | **≥75%** | **83.9%** | **PASSED** |

### Phase 2: Expand (1,000 questions) — **IN PROGRESS**
| Pipeline | Target | Tested | Accuracy | Status |
|----------|--------|--------|----------|--------|
| Standard | — | 90/1000 | ~76% | Running (background) |
| Graph | ≥60% | 500/500 | 78.0% | **COMPLETE** |
| Quantitative | ≥70% | 500/500 | 92.0% | **COMPLETE** |
| Orchestrator | — | 57/1000 | 0% | **BROKEN** (empty body) |
| **Overall** | **≥65%** | — | — | Pending Standard + Orch |

### Phase 3: Scale (~9,500 questions) — PLANNED
| Pipeline | Target | Questions | Prerequisites |
|----------|--------|-----------|--------------|
| Standard | ≥75% | ~2,500 | Phase 2 pass |
| Graph | ≥55% | ~2,500 | Phase 2 pass |
| Quantitative | ≥65% | ~2,500 | Phase 2 pass |
| Orchestrator | ≥60% (<10% errors, <20s p95) | ~2,000 | Phase 2 pass |
| **Overall** | **≥65%** | **~9,500** | Phase 2 pass + data ingestion |

### Phase 4-5: Full HF (100K+) and Production — FUTURE

---

## 4. Datasets

### Phase 1 (200 questions)
| File | Questions | Pipelines |
|------|-----------|-----------|
| `eval/datasets/phase-1/standard-orch-50x2.json` | 100 | Standard (50) + Orchestrator (50) |
| `eval/datasets/phase-1/graph-quant-50x2.json` | 100 | Graph (50) + Quantitative (50) |

### Phase 2 (5,000 questions)
| File | Questions | Pipelines |
|------|-----------|-----------|
| `eval/datasets/phase-2/standard-orch-1000x2.json` | 2,000 | Standard (1000) + Orchestrator (1000) |
| `eval/datasets/phase-2/graph-quant-expansion-500x2.json` | 1,000 | Graph (500) + Quantitative (500) |
| `eval/datasets/phase-2/hf-1000.json` | 1,000 | Generic multi-domain |
| `eval/datasets/phase-2/pme-gateway-1000.json` | 1,000 | PME-specific |

### Other
| File | Questions | Purpose |
|------|-----------|---------|
| `eval/datasets/chatbot/chatbot-1000q.json` | 1,000 | Website chatbot validation |

---

## 5. Scoring Methodology

### Primary: Token F1 Score
```
F1 = 2 * (precision * recall) / (precision + recall)
- Tokenize expected and actual answers
- precision = matching tokens / actual tokens
- recall = matching tokens / expected tokens
```

### Match Categories
| Category | F1 Threshold | Description |
|----------|-------------|-------------|
| EXACT_MATCH | 1.0 | Perfect match |
| CONTAINS_MATCH | 0.9 | Answer contains expected (normalized) |
| FUZZY_RECALL | 0.3-0.9 | Partial token overlap |
| TOKEN_F1 | 0.0-0.3 | Low overlap |
| NO_MATCH | 0.0 | No match at all |

### Secondary: LLM-as-Judge (--semantic-score flag)
- Model: `arcee-ai/trinity-large-preview:free` via OpenRouter
- Binary yes/no correctness + explanation
- Used alongside F1, not replacing it

### Pass/Fail Rules
- F1 ≥ 0.3 → PASS (question counts as correct)
- F1 < 0.3 → FAIL
- Empty response, timeout, HTTP error → FAIL (F1 = 0.0)
- Pipeline returns "NO_ANSWER", "N/A", "ERROR" → filtered out, treated as empty

### Early-Stop
- Default: 4 consecutive failures → pipeline halts (prevents wasting time)
- Configurable via `--early-stop N` (0 = disable)
- Auto-stop on 3+ consecutive failures across pipelines → structured report

---

## 6. Batch Configuration

### Per-Pipeline Optimal Sizes (Session 66)
| Pipeline | Batch Size | Concurrency | Timeout | Delay |
|----------|-----------|-------------|---------|-------|
| Standard | 5 | 5 concurrent | 90s | 2s |
| Graph | 5 | 3 concurrent | 90s | 2s |
| Quantitative | 3 | 1 concurrent | 120s | 2s |
| Orchestrator | 2 | 1 concurrent | 180s | 5s |
| PME Gateway | 2 | 1 concurrent | 120s | 2s |

### Run Modes
```bash
# Quick validation (5q smoke test)
python3 eval/quick-test.py --questions 5

# Phase 1 full (200q, all pipelines, ~30 min)
python3 eval/run-eval-parallel.py --max 200 --dataset phase-1 --label "Phase1-retest"

# Phase 2 Standard only (1000q, ~2 hours)
python3 eval/run-eval-parallel.py --max 1000 --dataset phase-2 --types standard --reset --label "Phase2-std" --force

# Phase 2 all pipelines (5000q, ~4 hours)
python3 eval/run-eval-parallel.py --max 1000 --dataset phase-2 --all-parallel --label "Phase2-full" --force

# Background run with nohup
source .env.local && nohup python3 eval/run-eval-parallel.py --max 1000 --dataset phase-2 --types standard --reset --label "bg-run" --force --early-stop 20 > /tmp/eval-run.log 2>&1 &
```

---

## 7. Output Files

| File | Purpose | Auto-Updated |
|------|---------|-------------|
| `docs/data.json` | Full results (iterations, question_registry, traces) | Yes (live-writer.py) |
| `docs/status.json` | Lightweight status summary (<3KB) | Yes (generate_status.py) |
| `docs/tested_ids.json` | Dedup tracker (questions already tested) | Yes (eval scripts) |
| `docs/cross-repo-health.json` | 7-repo health report | Yes (cross-repo-health.py) |

### Reading Current Status
```bash
# Quick status check
python3 -c "import json; d=json.load(open('docs/status.json')); print(json.dumps(d, indent=2))"

# Phase gate check
python3 eval/phase_gates.py --phase 2

# Cross-repo health
python3 scripts/cross-repo-health.py --quick
```

---

## 8. Known Issues & Workarounds

| Issue | Impact | Workaround |
|-------|--------|------------|
| Orchestrator empty body | Orch pipeline 0% accuracy | Deferred — 68-node workflow needs deep debug |
| Chatbot fetch error | 4 Vercel sites can't reach HF Space | Needs CORS/proxy fix on HF Space |
| HF rebuild wipes creds | All workflows break after rebuild | Restore via REST API (FIX-58) |
| Stuck executions block webhooks | All pipelines timeout | DELETE stuck execs via REST API |
| Jina 1M token/month limit | Embedding throughput capped | Get additional Jina keys |
| data.json 13MB | Git operations slow | Consider .gitignore or LFS |

---

## 9. Pre-Session Checklist

```bash
# 1. Load environment
source .env.local

# 2. Check pipeline health
python3 eval/quick-test.py --questions 3

# 3. Check phase gates
python3 eval/phase_gates.py

# 4. Check for stuck executions
curl -s -b /tmp/n8n_cookies.txt "${N8N_HOST}/rest/executions?status=running&limit=10"

# 5. Check cross-repo health
python3 scripts/cross-repo-health.py --quick

# 6. Read last session state
cat directives/session-state.md
```
