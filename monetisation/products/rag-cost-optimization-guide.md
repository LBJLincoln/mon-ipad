# RAG Cost Optimization Guide
## How We Run Production RAG at $0/month LLM Cost

> Built from 82+ sessions operating a Multi-RAG system with 87.5% accuracy — entirely on free-tier models.

---

## Table of Contents

1. [The $0 LLM Stack](#the-0-llm-stack)
2. [Self-Hosted Embeddings](#self-hosted-embeddings)
3. [Free Database Tier Maximization](#free-database-tier-maximization)
4. [Compute Architecture](#compute-architecture)
5. [Batch Processing Optimization](#batch-processing-optimization)
6. [Rate Limit Management](#rate-limit-management)
7. [Cost-Per-Query Analysis](#cost-per-query-analysis)
8. [Migration Playbook: Paid → Free](#migration-playbook)
9. [When to Pay: Decision Framework](#when-to-pay)
10. [Production Monitoring at Zero Cost](#production-monitoring)

---

## 1. The $0 LLM Stack

### Model Selection Matrix

We tested 30+ free-tier models across 61,000 questions. Here are the winners:

| Role | Model | Provider | Why It Won |
|------|-------|----------|------------|
| **SQL Generation** | `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter | Best structured output on free tier |
| **Intent Classification** | `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter | 94% intent accuracy |
| **Query Planning** | `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter | Handles multi-step reasoning |
| **HyDE Generation** | `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter | Quality hypothetical documents |
| **Final QA** | `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter | Best answer quality/cost ratio |
| **Fast Classification** | `google/gemma-3-27b-it:free` | OpenRouter | 3x faster, good enough for routing |
| **Extraction** | `arcee-ai/trinity-large-preview:free` | OpenRouter | Excellent at structured extraction |
| **Summarization** | `arcee-ai/trinity-large-preview:free` | OpenRouter | Concise, accurate summaries |

### OpenRouter Free Tier Strategy

**Key insight**: OpenRouter offers dozens of free models. The trick is knowing which ones work for which RAG tasks.

#### Free Tier Rules (2026)
- Rate limits: ~20 RPM for most free models
- No SLA — requests can be slow during peak
- Models rotate — always have fallback models configured
- Some models require site registration for higher limits

#### Reliability Pattern: Multi-Model Fallback

```
Primary: llama-3.3-70b-instruct:free
  ↓ (on 429 or timeout)
Fallback 1: gemma-3-27b-it:free
  ↓ (on 429 or timeout)
Fallback 2: trinity-large-preview:free
  ↓ (on 429 or timeout)
Emergency: qwen/qwen-2.5-72b-instruct:free
```

#### Model Selection Decision Tree

```
Is the task structured output (SQL, JSON)?
  → YES: Use llama-3.3-70b (best instruction following)
  → NO: Is speed critical?
    → YES: Use gemma-3-27b (fastest free model)
    → NO: Is it extraction/summarization?
      → YES: Use trinity-large-preview (best at extraction)
      → NO: Use llama-3.3-70b (safest default)
```

### Cost Comparison: Our Stack vs Paid Alternatives

| Component | Our Cost | GPT-4o Equivalent | Claude Equivalent |
|-----------|----------|-------------------|-------------------|
| LLM (per 1K queries) | **$0.00** | $12.50 | $18.75 |
| Embeddings (per 1K docs) | **$0.00** | $0.13 (OpenAI) | $0.10 (Voyage) |
| Monthly LLM spend | **$0.00** | ~$500-2,000 | ~$750-3,000 |
| Annual savings | — | **$6,000-24,000** | **$9,000-36,000** |

---

## 2. Self-Hosted Embeddings

### Why We Ditched Jina AI (and Saved $200/month)

We started with Jina AI's embedding API. It worked great — until we hit rate limits at scale. Our solution: self-hosted embeddings on HuggingFace Spaces (free tier).

### Architecture: HuggingFace Space Embedding Service

```
┌─────────────────────────────────┐
│  HuggingFace Space (Free Tier)  │
│  ┌───────────────────────────┐  │
│  │  FastAPI + Gradio         │  │
│  │  jinaai/jina-embeddings   │  │
│  │  -v3 (1024-dim)           │  │
│  │  PyTorch + Transformers   │  │
│  └───────────────────────────┘  │
│  CPU: 2 vCPU | RAM: 16GB       │
│  Storage: 20GB                  │
└─────────────────────────────────┘
         ↕ HTTPS
┌─────────────────────────────────┐
│  n8n Workflow Nodes             │
│  HTTP Request → /api/embed      │
│  Batch: 10 texts per request    │
└─────────────────────────────────┘
```

### Implementation Details

#### Model Choice: jina-embeddings-v3 (1024 dimensions)
- **Why**: Same model Jina API uses, so existing vectors remain compatible
- **Dimensions**: 1024 (configurable via Matryoshka)
- **Performance**: ~50ms per batch of 10 on HF free CPU
- **Compatibility**: Drop-in replacement for Jina API

#### Key Technical Challenges We Solved

**Problem 1: PyTorch 2.4+ breaks `torch.load`**
```python
# BROKEN (PyTorch 2.4+)
torch.load(path)  # Raises security warning

# FIX: Monkey-patch before model loads
original_load = torch.load
def patched_load(*args, **kwargs):
    kwargs.setdefault('weights_only', False)
    return original_load(*args, **kwargs)
torch.load = patched_load
```

**Problem 2: Cold start timeout on free tier**
```python
# Solution: Lazy loading with Gradio warmup
model = None

def get_model():
    global model
    if model is None:
        model = AutoModel.from_pretrained("jinaai/jina-embeddings-v3")
    return model

# Gradio keeps the Space awake
demo = gr.Interface(fn=embed_api, ...)
```

**Problem 3: Memory limits on free tier (16GB)**
```python
# Batch processing to stay under memory
MAX_BATCH = 10  # Process 10 texts at a time
# Use float16 to halve memory usage
model = model.half()
```

### Migration Checklist: API → Self-Hosted

- [ ] Deploy embedding model to HuggingFace Space
- [ ] Test embedding quality matches API (cosine similarity > 0.99)
- [ ] Update n8n workflow HTTP Request nodes (URL + remove auth headers)
- [ ] Verify existing Pinecone vectors remain compatible
- [ ] Set up health check monitoring
- [ ] Configure fallback to API if Space goes down

### Cost Savings

| Metric | Jina API | Self-Hosted |
|--------|----------|-------------|
| Monthly cost | $200+ at scale | **$0** |
| Rate limit | 500 RPM | **Unlimited** (CPU-bound) |
| Latency | 50ms | 50ms (comparable) |
| Reliability | 99.9% | ~98% (free tier cold starts) |
| Annual savings | — | **$2,400+** |

---

## 3. Free Database Tier Maximization

### Pinecone (Vector DB) — Free Tier Mastery

**Limits**: 100K vectors, 1 index, 1 namespace

#### Strategy: Dual-Index Architecture

We run TWO free Pinecone indexes (one per project):
- `sota-rag-jina-1024`: 42,758 vectors (RAG knowledge base)
- `website-sectors-jina-1024`: 31,916 vectors (website content)

**Total**: 74,674 vectors across 2 indexes — 74.7% of free tier used.

#### Optimization Techniques

1. **Metadata filtering** instead of separate namespaces
```json
{
  "sector": "finance",
  "source": "annual_report",
  "year": 2025
}
```

2. **Deduplication** before upsert
```python
# Hash content to avoid duplicate vectors
content_hash = hashlib.md5(text.encode()).hexdigest()
# Check if hash exists before upserting
```

3. **Dimension optimization**: 1024-dim (not 4096) saves 4x storage

4. **Pruning strategy**: Remove vectors with < 5 queries/month

### Neo4j Aura (Graph DB) — Free Tier

**Limits**: 200K nodes, 400K relationships

**Current usage**: 70,847 nodes / 76,717 relationships (35% / 19%)

#### Optimization Techniques

1. **Entity deduplication** — merge similar entities
2. **Relationship pruning** — remove redundant edges
3. **Property compression** — store JSON blobs instead of multiple properties
4. **TTL-based cleanup** — remove stale nodes older than 6 months

### Supabase (PostgreSQL) — Free Tier

**Limits**: 500MB storage, 50K rows

**Current usage**: 40 tables, ~200MB

#### Optimization Techniques

1. **JSONB columns** instead of wide tables
2. **Materialized views** for common aggregations
3. **Partition by tenant** for multi-tenant efficiency
4. **Vacuum regularly** to reclaim space

---

## 4. Compute Architecture: 9 Free HuggingFace Spaces

### The Round-Robin Pattern

We run **9 identical n8n instances** on HuggingFace Spaces (free tier). Why?

**Problem**: Free-tier Spaces sleep after 48h of inactivity.
**Solution**: Distribute load across 9 Spaces. If one sleeps, others handle traffic.

```
Request → Load Balancer (simple round-robin)
  → Space 1 (n8n instance)
  → Space 2 (n8n instance)
  → ...
  → Space 9 (n8n instance)
```

### Space Configuration

| Setting | Value | Why |
|---------|-------|-----|
| SDK | Docker | Full control over n8n setup |
| Hardware | CPU Basic (free) | Sufficient for workflow orchestration |
| Storage | 20GB persistent | Stores workflows + execution data |
| Secrets | 15+ env vars | API keys, DB credentials |
| Visibility | Public | Required for free tier |

### Cost: $0/month for 9 compute instances

Equivalent paid infrastructure:
- AWS: ~$200/month (9x t3.micro)
- Railway: ~$45/month (9x hobby plan)
- Render: ~$63/month (9x starter)

**Annual savings: $540-$2,400**

---

## 5. Batch Processing Optimization

### Why Batch Size Matters on Free Tiers

Free APIs have rate limits. Batch size directly impacts throughput vs. reliability.

### Our Tested Optimal Batch Sizes

| Pipeline | Batch Size | Concurrency | Timeout | Throughput |
|----------|-----------|-------------|---------|------------|
| Standard RAG | 10 | 5 | 90s | ~50 q/min |
| Graph RAG | 5 | 3 | 90s | ~25 q/min |
| Quantitative | 3 | 1 | 120s | ~8 q/min |
| Orchestrator | 2 | 1 | 180s | ~4 q/min |
| Embedding ingestion | 10 | 2 | 60s | ~6.3 docs/min |

### Adaptive Batch Sizing Algorithm

```python
class AdaptiveBatcher:
    def __init__(self, initial_batch=10):
        self.batch_size = initial_batch
        self.consecutive_429s = 0
        self.consecutive_200s = 0

    def on_response(self, status_code):
        if status_code == 429:
            self.consecutive_429s += 1
            self.consecutive_200s = 0
            # Exponential backoff on batch size
            self.batch_size = max(1, self.batch_size // 2)
        elif status_code == 200:
            self.consecutive_200s += 1
            self.consecutive_429s = 0
            # Slowly increase if stable
            if self.consecutive_200s >= 10:
                self.batch_size = min(20, self.batch_size + 1)
```

### Processing 61,000 Questions at Zero Cost

Our Phase 3 evaluation processed 10,000+ questions. Here's how:

1. **Time window**: Run evaluations during off-peak hours (2-6 AM UTC)
2. **Staggered batches**: 3-second delay between batches
3. **Multi-Space distribution**: Spread load across 9 n8n instances
4. **Checkpoint system**: Resume from last successful batch on failure
5. **Result caching**: Don't re-evaluate already-tested questions

**Total processing time**: ~48 hours for 10K questions
**Total cost**: $0

---

## 6. Rate Limit Management

### The Rate Limit Hierarchy

Understanding rate limits is critical for $0 operations:

```
OpenRouter Free Tier:
├── Account level: 200 RPM aggregate
├── Model level: 20 RPM per model
├── Burst: 5 requests/second
└── Daily: Soft limit ~1000 requests

Pinecone Free Tier:
├── Reads: 100 RPS
├── Writes: 50 RPS
└── Vectors/second: ~33

HuggingFace Spaces:
├── Inactivity timeout: 48 hours
├── Build timeout: 30 minutes
└── Request timeout: 5 minutes
```

### Rate Limit Survival Strategies

#### 1. Token Bucket with Retry
```python
import time
from collections import deque

class TokenBucket:
    def __init__(self, rate=20, period=60):
        self.rate = rate
        self.period = period
        self.timestamps = deque()

    def wait_if_needed(self):
        now = time.time()
        # Remove old timestamps
        while self.timestamps and now - self.timestamps[0] > self.period:
            self.timestamps.popleft()
        # Wait if at capacity
        if len(self.timestamps) >= self.rate:
            sleep_time = self.period - (now - self.timestamps[0])
            time.sleep(sleep_time)
        self.timestamps.append(time.time())
```

#### 2. Model Rotation on 429
```python
MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "arcee-ai/trinity-large-preview:free",
]

async def call_with_rotation(prompt, models=MODELS):
    for model in models:
        try:
            response = await call_llm(model, prompt)
            return response
        except RateLimitError:
            continue
    raise AllModelsExhausted()
```

#### 3. Exponential Backoff with Jitter
```python
import random

def backoff_delay(attempt, base=1, max_delay=60):
    delay = min(base * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter
```

---

## 7. Cost-Per-Query Analysis

### Our Actual Numbers

| Pipeline | Avg Latency | LLM Cost | Embedding Cost | DB Cost | Total Cost/Query |
|----------|------------|----------|----------------|---------|-----------------|
| Standard | 42s | $0.000 | $0.000 | $0.000 | **$0.000** |
| Graph | 32s | $0.000 | $0.000 | $0.000 | **$0.000** |
| Quantitative | 8s | $0.000 | $0.000 | $0.000 | **$0.000** |

### Equivalent Costs with Paid APIs

| Pipeline | GPT-4o + OpenAI | Claude + Voyage | Our Stack |
|----------|-----------------|-----------------|-----------|
| Standard (per query) | $0.0125 | $0.0188 | **$0.000** |
| Monthly (1K queries/day) | $375 | $564 | **$0** |
| Annual | $4,500 | $6,768 | **$0** |

### The Hidden Costs

While LLM/embedding costs are $0, there are real costs:
- **Your time**: Setting up and maintaining free-tier infrastructure
- **Reliability**: ~98% uptime vs 99.9% for paid services
- **Latency**: 2-3x slower during peak hours
- **Support**: No SLA, community forums only

### Break-Even Analysis: When to Switch to Paid

```
If your time costs $X/hour:
  Setup time: ~40 hours (one-time)
  Maintenance: ~5 hours/month

  Monthly time cost: 5h × $X = $5X

  Break-even vs GPT-4o: $5X < $375 → X < $75/hr
  Break-even vs Claude: $5X < $564 → X < $113/hr
```

**Conclusion**: Free-tier RAG makes sense if your hourly rate is under $75/hr OR you're bootstrapping.

---

## 8. Migration Playbook: Paid → Free

### Week 1: LLM Migration

**Day 1-2: Model Evaluation**
1. Sign up for OpenRouter (free)
2. Test 5 free models with your existing prompts
3. Measure: accuracy, latency, output format compliance
4. Select primary + fallback models

**Day 3-4: Workflow Updates**
1. Update API endpoints (OpenAI → OpenRouter)
2. Update model names in all workflow nodes
3. Add model rotation for rate limit handling
4. Test end-to-end with 50 queries

**Day 5-7: Validation**
1. Run full evaluation suite (200+ questions)
2. Compare accuracy vs paid models
3. Tune prompts for free-tier models if needed
4. Document any quality trade-offs

### Week 2: Embedding Migration

**Day 8-10: Self-Hosted Setup**
1. Deploy embedding model to HuggingFace Space
2. Test embedding quality (cosine similarity check)
3. Update workflow nodes to use self-hosted endpoint
4. Verify vector compatibility with existing DB

**Day 11-14: Validation**
1. Ingest test batch of 100 documents
2. Run retrieval quality tests
3. Benchmark latency vs API
4. Set up monitoring

### Week 3: Database Optimization

1. Audit current database usage vs free-tier limits
2. Implement deduplication
3. Set up pruning schedules
4. Optimize queries for free-tier performance

### Week 4: Compute Migration

1. Deploy n8n to HuggingFace Spaces (or Railway free tier)
2. Set up round-robin if needed
3. Configure health checks
4. Cut over from paid compute

### Expected Savings Timeline

| Week | Action | Monthly Savings |
|------|--------|----------------|
| 1 | LLM migration | $500-3,000 |
| 2 | Embedding migration | $100-500 |
| 3 | Database optimization | $50-200 |
| 4 | Compute migration | $50-500 |
| **Total** | **Full migration** | **$700-4,200/month** |

---

## 9. When to Pay: Decision Framework

### The Free-Tier Suitability Matrix

| Factor | Free Tier OK | Need Paid |
|--------|-------------|-----------|
| Queries/day | < 1,000 | > 5,000 |
| Latency requirement | > 5 seconds | < 2 seconds |
| Uptime SLA | None needed | 99.9%+ |
| Data sensitivity | Public/demo | PII/HIPAA |
| Team size | 1-3 people | 5+ people |
| Revenue from RAG | < $5K/month | > $10K/month |

### Recommended Paid Upgrades (Priority Order)

1. **First upgrade**: Pinecone Starter ($70/month) — removes vector limits
2. **Second upgrade**: Dedicated compute ($20/month) — eliminates cold starts
3. **Third upgrade**: OpenRouter Pro ($20/month) — higher rate limits
4. **Last upgrade**: Paid LLM API — only when accuracy gap is proven

### The Hybrid Approach

Our recommended production architecture for cost-conscious teams:

```
Critical path (customer-facing):
  → Paid LLM (GPT-4o-mini or Claude Haiku) — $20-50/month
  → Paid embeddings (Jina or Voyage) — $20-50/month

Non-critical path (internal, batch, testing):
  → Free-tier LLMs via OpenRouter
  → Self-hosted embeddings
  → Free database tiers

Estimated monthly cost: $40-100 (vs $500-3,000 all-paid)
```

---

## 10. Production Monitoring at Zero Cost

### Free Monitoring Stack

| Tool | Purpose | Cost |
|------|---------|------|
| HuggingFace Space logs | Application logs | $0 |
| GitHub Actions | Scheduled health checks | $0 (2000 min/month) |
| UptimeRobot | Endpoint monitoring | $0 (50 monitors) |
| Custom dashboard | Metrics visualization | $0 (GitHub Pages) |

### Health Check Script

```python
#!/usr/bin/env python3
"""Zero-cost RAG health monitoring"""

import requests
import json
from datetime import datetime

ENDPOINTS = {
    "standard": "https://space.hf.space/webhook/rag-multi-index-v3",
    "graph": "https://space.hf.space/webhook/graph-rag",
    "quant": "https://space.hf.space/webhook/quant-rag",
    "embeddings": "https://space.hf.space/api/embed",
}

def check_health():
    results = {}
    for name, url in ENDPOINTS.items():
        try:
            start = datetime.now()
            resp = requests.post(url, json={"query": "health check"}, timeout=30)
            latency = (datetime.now() - start).total_seconds()
            results[name] = {
                "status": "UP" if resp.status_code == 200 else "DOWN",
                "latency": f"{latency:.1f}s",
                "code": resp.status_code
            }
        except Exception as e:
            results[name] = {"status": "DOWN", "error": str(e)}
    return results
```

### Alerting (Free)

```yaml
# .github/workflows/health-check.yml
name: RAG Health Check
on:
  schedule:
    - cron: '*/30 * * * *'  # Every 30 minutes
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 scripts/health-check.py
      - name: Alert on failure
        if: failure()
        run: |
          curl -X POST "$WEBHOOK_URL" \
            -d '{"text": "🚨 RAG pipeline down!"}'
```

---

## Appendix A: Complete Free-Tier Resource Map

| Service | Free Tier Limits | Our Usage | Headroom |
|---------|-----------------|-----------|----------|
| OpenRouter | ~1000 req/day/model | ~500/day | 50% |
| Pinecone | 100K vectors × 2 | 74,674 | 25% |
| Neo4j Aura | 200K nodes | 70,847 | 65% |
| Supabase | 500MB | ~200MB | 60% |
| HuggingFace Spaces | Unlimited (CPU) | 10 Spaces | ∞ |
| GitHub Pages | 1GB, 100K req/month | ~50MB | 95% |
| GitHub Actions | 2000 min/month | ~200 min | 90% |

## Appendix B: Annual Cost Savings Summary

| Category | Paid Alternative | Our Cost | Annual Savings |
|----------|-----------------|----------|----------------|
| LLMs | $6,000-36,000 | $0 | **$6,000-36,000** |
| Embeddings | $1,200-6,000 | $0 | **$1,200-6,000** |
| Vector DB | $840-2,400 | $0 | **$840-2,400** |
| Graph DB | $1,200-3,600 | $0 | **$1,200-3,600** |
| Compute (9 instances) | $540-2,400 | $0 | **$540-2,400** |
| Monitoring | $240-1,200 | $0 | **$240-1,200** |
| **Total** | **$10,020-51,600** | **$0** | **$10,020-51,600** |

---

## About This Guide

This guide was built from **82+ sessions** of operating a production Multi-RAG system achieving:
- **87.5% accuracy** on 10,000+ benchmark questions
- **95.2% accuracy** on quantitative queries
- **$0/month** operational cost
- **61,000** test questions evaluated

Every technique in this guide has been battle-tested in production.

*Part of the Nomos AI Production RAG Toolkit — [nomos-ai.com](https://nomos-ai.com)*
