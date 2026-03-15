# Nomos RAG Eval Framework — Moltbot Skill

> Version: 1.0.0 | Author: Nomos AI | License: Commercial (free tier + paid)
> Schema: moltbot-skill/v1

---

## Metadata

```yaml
name: nomos-eval-framework
version: 1.0.0
author: Nomos AI
category: testing-evaluation
tags: [rag-eval, benchmarking, accuracy, regression-testing, smoke-test, phase-gates]
pricing: free-tier-limited
purchase_url: https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605
full_access_price: "$127"
full_access_product: "RAG Eval Framework - 61K-Question System"
description: >
  Run structured evaluations on RAG pipelines using a battle-tested framework
  that has processed 61,661 questions across 18 SOTA benchmarks. Includes smoke
  tests, parallel batch evaluations, phase-gated progression, regression detection,
  and golden-answer comparison. Outputs machine-readable JSON results.
capabilities:
  - smoke_test_3_to_5_questions
  - batch_evaluation_parallel
  - phase_gate_checks
  - regression_detection
  - golden_answer_comparison
  - latency_benchmarking
  - per_pipeline_accuracy_tracking
```

---

## What This Skill Does

Run evaluations against RAG pipelines at multiple levels of depth:

| Eval Type | Questions | Time | Use Case |
|-----------|-----------|------|----------|
| **Smoke Test** | 3-5 per pipeline | 30-60s | Quick validation after a change |
| **Quick Eval** | 10-25 per pipeline | 2-5 min | Moderate confidence check |
| **Phase Eval** | 200-10,000+ | 1-24 hours | Full benchmark run with statistical significance |
| **Golden Check** | Subset with verified answers | 1-3 min | Regression detection against known-good answers |

---

## Baselines (Phase 3 — 10K Questions)

These are the current production accuracy numbers. Any evaluation you run should be compared against these:

| Pipeline | Accuracy | Questions Tested | Status |
|----------|----------|------------------|--------|
| Standard | **87.5%** | 10,917 | PASS |
| Graph | **40.9%** | 11,300 | ACCEPTED (known limitation) |
| Quantitative | **95.2%** | 3,550 | PASS |
| Orchestrator | ON HOLD | — | Inactive |

---

## Step-by-Step Instructions

### Step 1: Choose Evaluation Type

Decide what level of testing you need:

- **After a workflow change**: Smoke test (3-5 questions)
- **After a model swap**: Quick eval (10 questions)
- **Before a release**: Phase eval (200+ questions)
- **Checking for regressions**: Golden check

### Step 2: Run a Smoke Test

Send 3-5 known-good questions to each pipeline and check pass/fail.

**For each pipeline**, send a POST request:

```bash
# Standard pipeline — test question
curl -s -X POST \
  "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is retrieval-augmented generation?", "tenant_id": "benchmark"}' \
  | jq '.answer'
```

**Smoke test questions by pipeline**:

#### Standard (expect 3/3 correct):
1. "What is retrieval-augmented generation?"
2. "What are the main types of neural network architectures?"
3. "Explain the transformer attention mechanism"

#### Graph (expect 2/3 correct):
1. "What entities are related to deep learning?"
2. "How are neural networks connected to natural language processing?"
3. "What relationships exist between machine learning and computer vision?"

#### Quantitative (expect 3/3 correct):
1. "How many companies are in the BTP sector?"
2. "What is the average revenue in the finance sector?"
3. "Compare the number of documents across all sectors"

### Step 3: Evaluate Results

For each response, check:

1. **Non-empty**: The `answer` field is not empty, null, or "Unable to generate"
2. **Relevant**: The answer addresses the question (not a hallucination or off-topic)
3. **Latency**: Response time is under 30 seconds for Standard, 45 seconds for Graph/Quant
4. **No errors**: No "[object Object]", no HTML in response, no "Query must start with SELECT"

### Step 4: Calculate Accuracy

```
accuracy = correct_answers / total_questions * 100
```

Compare against baselines:
- Standard: expect >= 85% (baseline 87.5%)
- Graph: expect >= 35% (baseline 40.9%)
- Quantitative: expect >= 90% (baseline 95.2%)

**Regression threshold**: Flag if accuracy drops more than 5 percentage points below baseline.

### Step 5: Report Results

Format results as structured JSON:

```json
{
  "eval_type": "smoke_test",
  "timestamp": "2026-03-08T12:00:00Z",
  "results": {
    "standard": {
      "questions": 3,
      "correct": 3,
      "accuracy": 100.0,
      "avg_latency_ms": 2450,
      "baseline": 87.5,
      "regression": false
    },
    "graph": {
      "questions": 3,
      "correct": 2,
      "accuracy": 66.7,
      "avg_latency_ms": 5200,
      "baseline": 40.9,
      "regression": false
    },
    "quantitative": {
      "questions": 3,
      "correct": 3,
      "accuracy": 100.0,
      "avg_latency_ms": 8100,
      "baseline": 95.2,
      "regression": false
    }
  },
  "overall_pass": true
}
```

---

## Advanced: Batch Evaluation

For running larger evaluations (10+ questions), use the batch pattern:

### Step 1: Prepare Question Set

Questions should be in this format:

```json
[
  {
    "id": "q001",
    "question": "What is RAG?",
    "expected_answer": "Retrieval-Augmented Generation",
    "pipeline": "standard",
    "difficulty": "easy"
  }
]
```

### Step 2: Send in Batches

To avoid overloading the system, send in controlled batches:

| Pipeline | Batch Size | Concurrency | Timeout per Question |
|----------|------------|-------------|---------------------|
| Standard | 10 | 5 | 90s |
| Graph | 5 | 3 | 90s |
| Quantitative | 3 | 1 | 120s |

Wait for each batch to complete before sending the next.

### Step 3: Phase Gates

The framework uses phase-gated progression. A pipeline must pass the current phase before advancing:

| Phase | Questions | Required Accuracy | Statistical Confidence |
|-------|-----------|-------------------|----------------------|
| Phase 1 | 200 | >= 70% | Basic |
| Phase 2 | 1,000 | >= 75% | p < 0.05 |
| Phase 3 | 10,000 | >= 80% (Standard/Quant) | p < 0.01 |
| Phase 4 | 61,661 | >= 75% overall | p < 0.001 |

---

## Error Patterns to Watch For

These are the most common failure patterns from 90+ documented fixes:

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Response contains `[object Object]` | Serializer bug in n8n | Check typeof in Set node |
| Response contains HTML `<!DOCTYPE>` | Wrong API URL (missing `/chat/completions`) | Fix OpenRouter base URL |
| `"Query must start with SELECT"` | LLM generated bad SQL | Add ILIKE + sample data to prompt |
| Empty response `[]` or `""` | Missing Respond to Webhook node | Check n8n workflow terminal node |
| HTTP 429 | Rate limit on LLM provider | Wait 60s or rotate API key |
| HTTP 502/503 | HF Space cold start | Wait 30s, retry |

---

## Full Access

The free tier lets you run smoke tests against the live endpoints. For the complete framework:

- **61,661 evaluation questions** across 18 SOTA benchmarks (HotpotQA, TriviaQA, NQ, MMLU, etc.)
- **Parallel batch runner** (`run-eval-parallel.py`) with round-robin across 9 n8n instances
- **Phase gate system** with statistical significance testing
- **Golden answer sets** for regression detection
- **Node-level execution analyzer** to debug individual n8n nodes
- **Dashboard integration** (auto-updates `status.json` and `data.json`)
- **9 eval scripts**: quick-test, run-eval, run-eval-parallel, golden-check, iterative-eval, sector-eval, node-analyzer, phase-gates, generate-status

Purchase the **RAG Eval Framework** ($127):
https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605

Or get the **MEGA BUNDLE** with all 13 products ($497):
https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d

---

## Technical Specs

```yaml
eval_questions_total: 61,661
benchmarks_count: 18
pipelines_tested: 3 (Standard, Graph, Quantitative)
phases: 4 (200 → 1K → 10K → 61K)
scripts_count: 9
output_format: JSON (status.json, data.json)
parallel_instances: 9 (HF Space round-robin)
regression_threshold: 5 percentage points
max_batch_concurrency: 5 (Standard), 3 (Graph), 1 (Quantitative)
cost_per_eval: $0.00 (free LLM tier)
```
