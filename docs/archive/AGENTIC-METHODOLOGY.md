# Agentic Improvement Methodology

> The continuous loop that makes our product better every cycle.
> THIS IS THE MOST IMPORTANT DOCUMENT IN THE PROJECT.

---

## The Loop (runs continuously, 24/7)

```
STRATEGIZE → PLAN → OBSERVE → BUILD → TEST → COLLECT → ANALYZE → IMPROVE → repeat
```

Each cycle:
- Makes the product better (higher accuracy)
- Generates MORE test data (from failures → new questions)
- Ingests MORE documents (from discovery → Docling)
- Produces BETTER metrics (from judging every execution)

## The Goal

**The best AI sector expert for French and European enterprises.**

4 sectors: Finance, BTP, Juridique, Industrie
Clients: CAC40, grands groupes, PMEs
Documents: IFRS, Eurocodes, Code civil, ISO norms, internal DBs
Scale: 1M+ documents per sector, 10K+ queries/day

## Phase 1: STRATEGIZE

**Script**: `ops/agentic-loop.py --phase strategize`
**Input**: Latest eval scores, failure patterns, metrics
**Output**: Priority decision (which sector/pipeline to improve)

The LLM reads all available data and picks the SINGLE highest-impact improvement.
Example: "Finance quant at 23% → missing financial data for French companies"

## Phase 2: PLAN

**Script**: `ops/agentic-loop.py --phase plan`
**Input**: Priority from Phase 1
**Output**: Specific action plan (which nodes to change, what to test)

The LLM creates a detailed fix plan with:
- Target n8n nodes to modify
- Test questions that verify the fix
- Success metric (score delta needed)

## Phase 3: OBSERVE (baseline)

**Script**: `eval/parallel-eval.py --sector {target} --pipeline {target}`
**Input**: Target sector/pipeline from plan
**Output**: Baseline scores BEFORE any changes

Never change anything without measuring first.

## Phase 4: BUILD

**Script**: `ops/staging-deploy.py --workflow {fix} --pipeline {target}`
**Input**: Fix from plan
**Process**: Deploy to S9 (staging) → smoke test → if PASS promote to S1-S5

## Phase 5: TEST

**Script**: `eval/queue-eval-orchestrator.py run`
**Input**: 5,276+ questions across all sectors/pipelines
**Output**: Scores per sector, per pipeline, per Space

## Phase 6: COLLECT

**Scripts**:
- `eval/continuous-judge.py` — LLM scores every execution (5 criteria)
- `ops/metrics-collector.py` — n8n node-level performance
- `eval/expert-discovery.py` — Tavily finds new real documents

**Storage**:
- Supabase `execution_scores` — every judgment
- `data/eval/execution-board.json` — top 20 best / bottom 20 worst
- `data/metrics/` — execution logs, node performance, errors

## Phase 7: ANALYZE

**Script**: `eval/continuous-judge.py --suggestions`
**Input**: All collected data
**Output**: Ranked improvement suggestions

The LLM groups failures by type, identifies root causes, and suggests specific fixes ranked by impact.

## Phase 8: IMPROVE

**Script**: `ops/agentic-loop.py` (full cycle)
**Input**: Analysis from Phase 7
**Output**: Applied fix → measured improvement → next priority

If improvement achieved → log success, move to next priority.
If no improvement → try different approach or escalate.

## Tools Inventory

| Tool | Repo | Purpose |
|------|------|---------|
| `ops/agentic-loop.py` | mon-ipad | Master orchestrator (THE LOOP) |
| `eval/parallel-eval.py` | mon-ipad | Parallel eval across 6 Spaces |
| `eval/queue-eval-orchestrator.py` | mon-ipad | Redis-backed massive eval |
| `eval/continuous-judge.py` | mon-ipad | LLM-as-Judge + good/bad board |
| `eval/expert-discovery.py` | mon-ipad | Tavily real doc discovery |
| `eval/mass-question-generator.py` | mon-ipad | 5000+ question generation |
| `ops/staging-deploy.py` | mon-ipad | CI/CD: staging → promote |
| `ops/deploy-eval-judge.py` | mon-ipad | Deploy judge to S8 |
| `ops/metrics-collector.py` | mon-ipad | n8n execution metrics |
| `ops/metrics-analyzer.py` | mon-ipad | LLM analysis of metrics |
| `codespace/docling-cron.py` | mon-ipad | Continuous PDF ingestion |
| `ops/fast-ingest.py` | mon-ipad | Vector ingestion (E5 + Supabase) |

## Repos and Their Roles

| Repo | Role in Loop |
|------|-------------|
| **mon-ipad** | Brain — eval, ops, agentic loop, metrics |
| **rag-data-ingestion** | Data — Docling, chunking, embedding pipelines |
| **rag-website** | Product — chatbot serving improved pipelines |
| **rag-dashboard** | Visibility — live metrics, eval results |

## Running the Loop

### One-shot cycle
```bash
source .env.local
python3 ops/agentic-loop.py
```

### Continuous (every 30 min)
```bash
python3 ops/agentic-loop.py --daemon 1800
```

### Manual step-by-step
```bash
# 1. Check current state
python3 ops/agentic-loop.py --report

# 2. Run targeted eval
python3 eval/parallel-eval.py --sector finance --pipeline standard

# 3. Judge results
python3 eval/continuous-judge.py --board

# 4. Get improvement suggestions
python3 eval/continuous-judge.py --suggestions

# 5. Deploy fix to staging
python3 ops/staging-deploy.py --workflow n8n/live/standard-rag-v3.9-multi-index.json --pipeline standard

# 6. Run full eval to verify improvement
python3 eval/queue-eval-orchestrator.py load --dataset extended
python3 eval/queue-eval-orchestrator.py run --workers 12

# 7. Check results
python3 eval/queue-eval-orchestrator.py results
```

## Current Scores (S97 baseline)

| Sector | Standard | Graph | Quant | Orchestrator |
|--------|----------|-------|-------|-------------|
| Finance | ~41% | ~30% | ~26% | ~40% |
| BTP | ~38% | ~25% | ~24% | ~35% |
| Juridique | ~52% | ~35% | N/A | ~45% |
| Industrie | ~54% | ~30% | ~25% | ~40% |

## Target Scores

| Sector | Standard | Graph | Quant | Orchestrator |
|--------|----------|-------|-------|-------------|
| Finance | >= 90% | >= 75% | >= 95% | >= 85% |
| BTP | >= 85% | >= 70% | >= 80% | >= 75% |
| Juridique | >= 90% | >= 80% | N/A | >= 80% |
| Industrie | >= 85% | >= 70% | >= 80% | >= 75% |

**Gap**: 30-60 points per sector. The agentic loop closes this gap, one cycle at a time.
