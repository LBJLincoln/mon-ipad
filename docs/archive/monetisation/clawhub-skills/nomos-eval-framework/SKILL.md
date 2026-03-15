---
name: nomos-eval-framework
description: Run structured evaluations on RAG pipelines using 61,661 questions from 18 SOTA benchmarks. Phase-gated progression, regression detection, golden-answer comparison, and parallel batch execution across 9 n8n instances.
version: 1.0.0
metadata:
  openclaw:
    requires:
      env: []
      bins:
        - curl
---

# Nomos RAG Eval Framework

Evaluate any RAG system with production-grade benchmarks. 61,661 questions from 18 SOTA benchmarks (HotpotQA, TriviaQA, NQ, MMLU, etc.).

## Current Baselines (Phase 3 — 10K Questions)

| Pipeline | Accuracy | Questions | Status |
|----------|----------|-----------|--------|
| Standard | **87.5%** | 10,917 | PASS |
| Graph | **40.9%** | 11,300 | ACCEPTED |
| Quantitative | **95.2%** | 3,550 | PASS |

## Evaluation Types

| Type | Questions | Time | Use Case |
|------|-----------|------|----------|
| Smoke Test | 3-5 | 30-60s | Quick validation after a change |
| Quick Eval | 10-25 | 2-5 min | Moderate confidence check |
| Phase Eval | 200-10K+ | 1-24 hours | Full benchmark with stat significance |
| Golden Check | Subset | 1-3 min | Regression detection |

## Step 1: Run Smoke Test

Send 3 known-good questions to each pipeline:

### Standard (expect 3/3):
```bash
curl -s -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is retrieval-augmented generation?", "tenant_id": "benchmark"}' | jq '.answer'
```

### Graph (expect 2/3):
```bash
curl -s -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"question": "What entities are related to deep learning?", "tenant_id": "benchmark"}' | jq '.answer'
```

### Quantitative (expect 3/3):
```bash
curl -s -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many companies are in the BTP sector?", "tenant_id": "benchmark"}' | jq '.answer'
```

## Step 2: Evaluate Results

For each response check:
1. **Non-empty**: answer is not null, empty, or "Unable to generate"
2. **Relevant**: answer addresses the question
3. **Latency**: under 30s (Standard), 45s (Graph/Quant)
4. **No errors**: no [object Object], no HTML, no "Query must start with SELECT"

## Step 3: Calculate Accuracy

```
accuracy = correct / total * 100
```

Regression threshold: flag if accuracy drops >5pp below baseline.

## Step 4: Phase Gates

| Phase | Questions | Required Accuracy |
|-------|-----------|-------------------|
| Phase 1 | 200 | >= 70% |
| Phase 2 | 1,000 | >= 75% |
| Phase 3 | 10,000 | >= 80% |
| Phase 4 | 61,661 | >= 75% |

## Step 5: Report Results

```json
{
  "eval_type": "smoke_test",
  "timestamp": "2026-03-08T12:00:00Z",
  "results": {
    "standard": {"questions": 3, "correct": 3, "accuracy": 100.0, "baseline": 87.5, "regression": false},
    "graph": {"questions": 3, "correct": 2, "accuracy": 66.7, "baseline": 40.9, "regression": false},
    "quantitative": {"questions": 3, "correct": 3, "accuracy": 100.0, "baseline": 95.2, "regression": false}
  },
  "overall_pass": true
}
```

## Full Access

Complete framework with 61K questions, 9 Python scripts, batch runner, and phase gates:

- **Eval Framework** ($127): https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605
- **MEGA BUNDLE** ($497): https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d
