# Agentic RAG Blueprint — Build AI Agents That Actually Think

> **Price: $147** | Based on 88+ real engineering sessions, 1,100+ commits, 61K+ benchmark questions
> **Format:** Markdown guides + n8n workflow JSONs + Python evaluation script + System prompts

---

## Product Overview

### What This Is

A complete engineering blueprint for building **agentic RAG systems** — where AI agents autonomously classify queries, select the right retrieval pipeline, recover from failures without human intervention, and chain multiple strategies to maximize answer quality.

This is not a tutorial built from documentation. Every pattern, every fallback strategy, every routing decision in this blueprint was extracted from a **production Multi-RAG system** with 4 specialized pipelines (Standard, Graph, Quantitative, Orchestrator) running across 9 compute instances, processing 61,000+ benchmark questions at 87-95% accuracy — all on $0/month infrastructure.

You get the exact agent architectures, routing logic, self-healing patterns, and evaluation frameworks that took 88 sessions and 1,100+ commits to refine.

### What Makes This Different

Most RAG guides stop at "retrieve context, generate answer." Real production systems fail constantly — LLMs time out, vector databases return stale results, graph queries explode in complexity, SQL generation hallucinates column names. **Agentic RAG** means the system handles all of this autonomously:

- The agent **decides** which of 4 pipelines handles each query best
- When a pipeline fails, the agent **falls back** to alternatives without dropping the request
- When accuracy regresses, the agent **self-corrects** by adjusting retrieval parameters
- When multiple pipelines contribute, the agent **merges** responses intelligently

This blueprint gives you the architecture to build that system.

### Who This Is For

- **AI Engineers** building multi-pipeline RAG systems that need autonomous routing
- **Tech Leads** designing agent architectures for production retrieval systems
- **Startups** shipping AI products that need to handle diverse query types reliably
- **Platform Engineers** running n8n, LangChain, or custom orchestration for RAG
- **Solo Builders** wanting production-grade agentic AI without a $10K/month cloud bill

### Who This Is NOT For

- Beginners without Python + API experience (you need to understand HTTP, JSON, async)
- Teams building single-purpose chatbots (a simple RAG pipeline is enough — see our $97 Runbook)
- Projects requiring sub-100ms latency (agentic routing adds 1-3s decision overhead)
- Enterprise teams needing SOC2/HIPAA compliance (this covers free-tier infrastructure)

---

## What's Inside

### Deliverables

| File | Description | Size |
|------|-------------|------|
| `agentic-rag-blueprint.md` | Main guide — complete agentic RAG architecture | 3,000+ lines |
| `agent-routing-patterns.md` | 12 routing strategies with decision trees | 800+ lines |
| `self-healing-playbook.md` | Failure recovery patterns, circuit breakers, fallback chains | 600+ lines |
| `n8n-agent-workflows/orchestrator-v10.json` | Production orchestrator workflow (4-pipeline routing) | n8n JSON |
| `n8n-agent-workflows/self-healing-agent.json` | Self-healing wrapper with retry + fallback logic | n8n JSON |
| `n8n-agent-workflows/eval-routing-agent.json` | Evaluation workflow for testing agent decisions | n8n JSON |
| `eval-agent-decisions.py` | Python script to benchmark agent routing accuracy | 400+ lines |
| `prompts/intent-classifier.md` | System prompt for query intent classification | Optimized |
| `prompts/pipeline-selector.md` | System prompt for pipeline routing decisions | Optimized |
| `prompts/failure-analyst.md` | System prompt for diagnosing pipeline failures | Optimized |
| `prompts/response-merger.md` | System prompt for merging multi-pipeline outputs | Optimized |
| `prompts/quality-judge.md` | System prompt for evaluating response quality | Optimized |

---

## Key Topics

### 1. Agent-Driven Query Routing

The core of an agentic RAG system: **the agent decides how to answer before retrieving anything.**

#### Intent Classification Architecture

```
User Query
    |
    v
[Intent Classifier] ── LLM call with few-shot examples
    |
    ├── factual_lookup    → Standard RAG (vector search)
    ├── relationship      → Graph RAG (entity traversal)
    ├── numerical/stats   → Quantitative RAG (text-to-SQL)
    ├── comparative        → Multi-pipeline merge
    ├── temporal           → Standard + recency filter
    ├── aggregation        → Quantitative primary, Standard fallback
    ├── definition         → Standard with exact match boost
    ├── procedural         → Graph (step-by-step relationships)
    ├── opinion/analysis   → Standard with expanded context
    ├── ambiguous          → Confidence-based multi-pipeline
    └── unknown            → Default to Standard with monitoring flag
```

#### What You Learn

- **4-way intent classification** with confidence scoring (threshold tuning: 0.6-0.85 range)
- **Cascade routing** — primary pipeline with ranked fallbacks per intent type
- **Confidence-calibrated decisions** — when the agent is unsure, it queries multiple pipelines and merges
- **Few-shot prompt engineering** for intent classification (25 tested examples included)
- **Latency budgets** — how to allocate time across classification (200ms) + retrieval (2-5s) + generation (3-8s)

#### Real Production Data

| Intent Type | Frequency | Best Pipeline | Accuracy | Fallback Pipeline | Fallback Accuracy |
|-------------|-----------|---------------|----------|-------------------|-------------------|
| Factual | 45% | Standard | 87.5% | Graph | 72% |
| Numerical | 20% | Quantitative | 95.2% | Standard | 61% |
| Relationship | 15% | Graph | 78.0% | Standard | 70% |
| Comparative | 12% | Multi-merge | 83% | Standard | 68% |
| Other | 8% | Standard | 85% | — | — |

---

### 2. Self-Healing Patterns

Production RAG systems fail. Agentic RAG systems **recover autonomously.**

#### Pattern Catalog

**Pattern 1: Retry with Backoff**
```
Failure detected → Wait 1s → Retry same pipeline
  ├── Success → Return result
  └── Failure → Wait 2s → Retry
       ├── Success → Return result
       └── Failure → Escalate to fallback
```
- When to use: Transient failures (timeouts, rate limits, cold starts)
- Max retries: 3 (tested — beyond 3, success rate drops below 5%)
- Backoff multiplier: 2x (1s → 2s → 4s)

**Pattern 2: Pipeline Fallback Chain**
```
Primary pipeline fails → Route to fallback pipeline
  Standard fails → Retry Standard → Graph fallback
  Graph fails → Retry Graph → Standard fallback
  Quant fails → Retry Quant → Standard fallback (reformulate as text query)
  Orchestrator fails → Bypass → Direct pipeline call based on cached intent
```

**Pattern 3: Circuit Breaker**
```
Track failure rate per pipeline (sliding window: 5 min)
  ├── < 30% failure → CLOSED (normal operation)
  ├── 30-60% failure → HALF-OPEN (reduced traffic, monitor)
  └── > 60% failure → OPEN (route all traffic to fallback)
Auto-reset: Check every 60s, close circuit if 3 consecutive successes
```

**Pattern 4: Graceful Degradation**
```
All pipelines degraded → Serve cached response if available
  ├── Cache hit (semantic match > 0.92) → Return cached + "approximate" flag
  ├── Cache miss → Return "system busy" with estimated recovery time
  └── Partial results → Return what's available + "incomplete" flag
```

**Pattern 5: Self-Correcting Retrieval**
```
Low-confidence answer detected (LLM judge score < 0.6)
  → Expand query (HyDE: generate hypothetical document)
  → Increase top-k (5 → 10)
  → Broaden metadata filters
  → Re-retrieve and re-generate
```

#### What You Learn

- Implementation of all 5 patterns in n8n workflows and Python
- **Failure taxonomy** — 15 classified failure modes with detection signatures
- **Recovery time targets** — retry adds 3-8s, fallback adds 5-12s, degradation is instant
- **Monitoring hooks** — what to log at each failure point for post-mortem analysis
- How we reduced pipeline failure rate from 12% to 2.3% using these patterns

---

### 3. Multi-Pipeline Orchestration

Coordinating 4 specialized pipelines is the hardest part of agentic RAG. This section covers the architecture that took 40+ sessions to stabilize.

#### Orchestration Architecture

```
                    ┌─────────────────┐
                    │   Orchestrator   │
                    │   Agent (LLM)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼──────┐ ┌────▼────┐ ┌──────▼────────┐
    │  Standard RAG  │ │  Graph  │ │ Quantitative  │
    │  (Vector + BM25)│ │  RAG   │ │    RAG        │
    │  87.5% acc     │ │ 78% acc │ │  95.2% acc    │
    └────────────────┘ └─────────┘ └───────────────┘
         Pinecone         Neo4j        Supabase
       53K vectors      71K nodes     40 tables
```

#### What You Learn

- **Pipeline independence** — why each pipeline must be callable standalone (webhook architecture)
- **Parallel vs sequential execution** — when to fan-out to multiple pipelines simultaneously
- **Response merging strategies** — weighted voting, confidence-based selection, LLM-judged synthesis
- **State management** — tracking which pipelines were called, their latencies, and results
- **Conflict resolution** — when Standard says "X" and Quant says "Y", how the agent decides
- **Webhook coordination patterns** — async calls with timeout and cancellation
- **Pipeline version management** — running V3.3 and V3.4 simultaneously for A/B testing

#### Real Complexity Lessons

| Challenge | Naive Approach | Production Approach | Sessions to Learn |
|-----------|---------------|--------------------|--------------------|
| Routing accuracy | Keyword matching | LLM intent classifier + confidence | 8 sessions |
| Pipeline timeout | Global 30s timeout | Per-pipeline tuned (90-180s) | 5 sessions |
| Response merging | Concatenation | LLM-judged synthesis with citation | 12 sessions |
| Error cascading | Fail entire request | Isolate + fallback per pipeline | 6 sessions |
| Cold starts | Pray | Keep-alive pings every 5 min | 3 sessions |

---

### 4. Tool-Use Patterns for RAG

Modern agentic RAG treats retrieval pipelines as **tools** the agent can call with function calling.

#### Tool Definitions

```json
{
  "tools": [
    {
      "name": "search_documents",
      "description": "Search indexed documents using semantic vector search. Best for factual questions, definitions, and general knowledge queries.",
      "parameters": {
        "query": "The search query",
        "top_k": "Number of results (default: 5, max: 20)",
        "filter_sector": "Optional sector filter",
        "rerank": "Whether to apply reranking (default: true)"
      }
    },
    {
      "name": "query_knowledge_graph",
      "description": "Traverse the knowledge graph for relationship and entity questions. Best for 'how are X and Y related' or multi-hop reasoning.",
      "parameters": {
        "entities": "List of entities to find",
        "relationship_type": "Type of relationship to traverse",
        "max_depth": "Maximum traversal depth (default: 2)"
      }
    },
    {
      "name": "run_data_query",
      "description": "Execute structured data queries for numerical, statistical, or aggregation questions. Best for 'how many', 'what percentage', rankings.",
      "parameters": {
        "question": "Natural language question to convert to SQL",
        "table_hint": "Optional table name hint",
        "format": "Output format: number, table, or text"
      }
    },
    {
      "name": "evaluate_response",
      "description": "Judge whether a generated response adequately answers the question. Returns confidence score and improvement suggestions.",
      "parameters": {
        "question": "Original question",
        "response": "Generated response to evaluate",
        "sources": "Retrieved source documents"
      }
    }
  ]
}
```

#### What You Learn

- **Tool schema design** — how to describe retrieval tools so the LLM calls them correctly
- **Multi-tool chaining** — agent calls `search_documents`, evaluates result, then calls `query_knowledge_graph` for enrichment
- **Iterative retrieval** — agent decides "not enough context" and calls tools again with modified parameters
- **Tool result parsing** — extracting structured data from heterogeneous pipeline outputs
- **Error handling in tool calls** — malformed parameters, empty results, timeout recovery
- **Cost control** — limiting tool call depth (max 3 iterations) to prevent runaway LLM usage

---

### 5. Evaluation of Agentic Systems

Standard RAG evaluation measures answer quality. **Agentic RAG evaluation** also measures decision quality.

#### Three-Layer Evaluation Framework

**Layer 1: Routing Accuracy**
Did the agent choose the right pipeline?

| Metric | How to Measure | Target |
|--------|---------------|--------|
| Routing precision | % queries sent to optimal pipeline | > 85% |
| Routing recall | % query types correctly identified | > 90% |
| Fallback rate | % queries needing fallback pipeline | < 15% |
| Misroute rate | % queries sent to wrong pipeline | < 5% |

**Layer 2: Recovery Effectiveness**
When things fail, does the agent recover?

| Metric | How to Measure | Target |
|--------|---------------|--------|
| Recovery rate | % failures recovered via fallback | > 90% |
| Recovery latency | Additional time for recovery path | < 8s |
| False recovery | % recovered answers that are wrong | < 10% |
| Escalation rate | % failures requiring human intervention | < 2% |

**Layer 3: End-to-End Quality**
Does the agentic system outperform static routing?

| Metric | Static Routing | Agentic Routing | Improvement |
|--------|---------------|-----------------|-------------|
| Overall accuracy | 79.3% | 87.5% | +8.2pp |
| Numerical questions | 61.0% | 95.2% | +34.2pp |
| Mixed-type questions | 65.0% | 83.0% | +18.0pp |
| Failure recovery | 0% | 91.7% | +91.7pp |

#### What You Learn

- **Building routing evaluation datasets** — 500 questions with ground-truth pipeline labels
- **Agent decision logging** — structured logs for every routing decision (intent, confidence, pipeline, latency)
- **A/B testing agent versions** — running two routing strategies simultaneously
- **Regression detection** — automated alerts when routing accuracy drops > 3%
- **The `eval-agent-decisions.py` script** — end-to-end benchmarking with detailed reports

---

### 6. n8n Workflow Patterns for Agentic RAG

All 3 included workflow JSONs are production-tested. Here's what each does and how to customize them.

#### Workflow 1: Orchestrator Agent (orchestrator-v10.json)

The master workflow that receives all queries and routes them to specialized pipelines.

```
Webhook In → Intent Classifier (LLM) → Route Switch
  ├── Standard → Call Standard Webhook → Format Response
  ├── Graph → Call Graph Webhook → Format Response
  ├── Quant → Call Quant Webhook → Format Response
  └── Multi → Fan-out to 2-3 pipelines → Merge Responses
→ Quality Check (LLM) → Webhook Out
```

Key nodes: 23 | Tested configurations: 10 versions | Current: V10.1

#### Workflow 2: Self-Healing Agent (self-healing-agent.json)

Wraps any pipeline call with retry, fallback, and circuit breaker logic.

```
Pipeline Call → Response Check
  ├── Success (200 + valid JSON) → Pass through
  ├── Timeout → Retry (backoff) → Fallback pipeline
  ├── Error (500) → Log → Circuit breaker check → Fallback
  └── Bad response → Reformulate query → Retry
→ Metrics logging → Response out
```

#### Workflow 3: Eval Routing Agent (eval-routing-agent.json)

Runs evaluation datasets through the orchestrator and measures routing decisions.

```
Dataset In (CSV/JSON) → Batch Process (size: 3)
  → Call Orchestrator → Capture routing decision
  → Compare to ground truth → Score
→ Aggregate metrics → Generate report
```

#### What You Learn

- **n8n patterns** for LLM-powered routing (Switch nodes, HTTP Request with retry, error workflows)
- **Expression syntax** for dynamic webhook URLs and conditional logic
- **Credential management** across 9 instances (environment variables, not hardcoded)
- **Workflow versioning** — how to iterate without breaking production
- **Performance tuning** — batch sizes, concurrency limits, timeout configuration

---

### 7. Cost Optimization: $0 Infrastructure

The entire agentic RAG system runs on free tiers. Here's the complete cost architecture.

#### Free Tier Stack

| Service | What We Use | Free Tier Limit | Our Usage | Headroom |
|---------|-------------|-----------------|-----------|----------|
| HuggingFace Spaces | n8n compute (9 instances) | Unlimited (2 vCPU) | 9 instances | Unlimited |
| Pinecone | Vector storage | 100K vectors | 53K | 47K |
| Neo4j Aura | Graph database | 200K nodes / 400K rels | 71K / 77K | 129K / 323K |
| Supabase | SQL database | 500MB | 40 tables | ~400MB |
| OpenRouter | LLM inference | Free models | 3 models | Unlimited |
| GitHub | Code + storage | Unlimited repos | 7 repos | Unlimited |

**Total monthly cost: $0.00**

#### LLM Cost Strategy

| Model | Role in Agent System | Cost | Quality |
|-------|---------------------|------|---------|
| Llama 3.3 70B (free) | Intent classification, SQL generation, QA | $0 | High |
| Gemma 3 27B (free) | Fast routing decisions, lightweight tasks | $0 | Medium |
| Trinity Large (free) | Document extraction, summarization | $0 | Medium |

#### What You Learn

- **Free tier arbitrage** — which services give the most value at $0
- **Compute distribution** — why 9 small instances beats 1 large instance (redundancy + cold start mitigation)
- **Token budget management** — keeping agentic overhead (routing + evaluation) under 20% of total tokens
- **When to upgrade** — decision framework for when free tier limits become a bottleneck
- **Cost modeling** — projecting costs at 10x, 100x, 1000x current query volume

---

### 8. Production Monitoring and Observability

An agentic system has more moving parts. Monitoring must cover agent decisions, not just pipeline health.

#### Monitoring Architecture

```
┌─────────────────────────────────────────────┐
│               Dashboard Layer               │
│  Pipeline Health │ Routing Stats │ Accuracy  │
└──────────┬──────────────┬──────────┬────────┘
           │              │          │
┌──────────▼──┐ ┌────────▼────┐ ┌──▼──────────┐
│  Health     │ │  Decision   │ │  Quality    │
│  Checks    │ │  Logs       │ │  Metrics    │
│  (5 min)   │ │  (per query)│ │  (hourly)   │
└─────────────┘ └─────────────┘ └─────────────┘
```

#### What You Monitor

**Pipeline Health (every 5 minutes)**
- Webhook response codes (200/404/500)
- Response latency (P50, P95, P99)
- Instance availability (9/9 up = green, <7/9 = alert)

**Agent Decision Quality (per query)**
- Intent classification result + confidence score
- Pipeline selected + alternatives considered
- Fallback triggered (yes/no) + fallback result
- Total routing overhead (ms)

**End-to-End Accuracy (hourly on golden set)**
- Accuracy per pipeline (target: Standard 85%+, Quant 90%+)
- Accuracy per intent type
- Regression alerts (> 3% drop triggers investigation)

**Operational Metrics (daily)**
- Total queries processed
- Failure rate by pipeline
- Recovery success rate
- Average tokens per query (agent overhead tracking)

#### What You Learn

- **Structured logging schema** for agent decisions (JSON format, 12 fields per decision)
- **Dashboard implementation** — HTML/JS metrics display (from our rag-dashboard repo)
- **Alerting rules** — which metrics trigger immediate action vs. weekly review
- **Post-mortem templates** — how to analyze agent failures systematically
- **Golden set maintenance** — keeping evaluation datasets current as your data evolves

---

## Files Included — Detailed Breakdown

### 1. `agentic-rag-blueprint.md` (Main Guide — 3,000+ lines)

The comprehensive technical guide covering the complete agentic RAG architecture:

- **Chapter 1: Foundations** — What makes RAG "agentic," architecture overview, when you need it (and when you don't)
- **Chapter 2: Intent Classification** — Building the routing brain, prompt engineering, confidence calibration
- **Chapter 3: Pipeline Architecture** — Designing independent pipelines with clean webhook interfaces
- **Chapter 4: Orchestrator Design** — The agent loop: classify → route → retrieve → evaluate → respond
- **Chapter 5: Self-Healing** — Implementing retry, fallback, circuit breaker, and degradation patterns
- **Chapter 6: Tool-Use Patterns** — Function calling with retrieval tools, iterative retrieval, chain-of-retrieval
- **Chapter 7: Evaluation** — Three-layer evaluation framework, building routing benchmarks, regression testing
- **Chapter 8: n8n Implementation** — Node-by-node workflow construction, expression syntax, error handling
- **Chapter 9: Production Operations** — Monitoring, alerting, scaling, cost management
- **Chapter 10: Case Studies** — 5 real production incidents and how the agent handled them

### 2. `agent-routing-patterns.md` (12 Routing Strategies)

Deep dive into routing decision patterns:

| # | Pattern | Use Case | Complexity |
|---|---------|----------|------------|
| 1 | Single-pipeline direct | Simple queries, known type | Low |
| 2 | Confidence-threshold routing | Most queries | Medium |
| 3 | Cascade fallback | Pipeline failures | Medium |
| 4 | Parallel fan-out | Comparative questions | High |
| 5 | Sequential enrichment | Multi-hop reasoning | High |
| 6 | Cached routing | Repeated query patterns | Low |
| 7 | Sector-aware routing | Domain-specific optimization | Medium |
| 8 | Load-balanced routing | High traffic distribution | Medium |
| 9 | A/B routing | Testing new pipelines | Medium |
| 10 | Time-aware routing | Temporal queries, recency | Medium |
| 11 | Complexity-adaptive routing | Simple vs complex queries | High |
| 12 | Hybrid consensus routing | Maximum accuracy, high latency | Very High |

Each pattern includes: decision tree diagram, implementation pseudocode, n8n node configuration, when to use/avoid, and real accuracy measurements.

### 3. `self-healing-playbook.md` (Failure Recovery)

The complete failure taxonomy and recovery playbook:

- **15 classified failure modes** with detection signatures
- **5 recovery patterns** with implementation details
- **Circuit breaker state machine** — complete specification
- **Fallback chain configuration** per pipeline
- **Recovery time budgets** — how long each recovery path takes
- **Monitoring integration** — logging recovery events for analysis
- **Postmortem templates** — structured analysis for each failure type

### 4. `n8n-agent-workflows/` (3 Workflow JSONs)

Production-tested n8n workflows, importable directly:

- `orchestrator-v10.json` — Full orchestrator with 4-pipeline routing (23 nodes)
- `self-healing-agent.json` — Wrapper workflow with retry + fallback (15 nodes)
- `eval-routing-agent.json` — Evaluation harness for routing decisions (12 nodes)

### 5. `eval-agent-decisions.py` (Evaluation Script)

Python script for benchmarking agent routing:

```
Usage: python eval-agent-decisions.py --dataset routing-benchmark.json --endpoint https://your-n8n.hf.space

Features:
  - Tests routing accuracy against ground-truth labels
  - Measures per-intent-type accuracy
  - Tracks fallback rate and recovery success
  - Generates detailed report (JSON + human-readable)
  - Supports parallel execution (configurable concurrency)
  - Outputs confusion matrix for routing decisions
```

### 6. `prompts/` (5 Optimized System Prompts)

| Prompt File | Role | Tokens | Tested Variants |
|-------------|------|--------|-----------------|
| `intent-classifier.md` | Classify query intent into routing categories | ~800 | 25 variants tested |
| `pipeline-selector.md` | Select optimal pipeline given intent + context | ~600 | 15 variants tested |
| `failure-analyst.md` | Diagnose pipeline failure and suggest recovery | ~500 | 10 variants tested |
| `response-merger.md` | Merge outputs from multiple pipelines | ~700 | 12 variants tested |
| `quality-judge.md` | Evaluate response quality and suggest improvements | ~600 | 18 variants tested |

Each prompt includes: the production prompt, explanation of key design choices, common failure modes, and tuning guidance.

---

## Pricing Justification

### Why $147

This blueprint represents the distilled engineering output of:

- **88+ production sessions** — each 2-4 hours of focused engineering
- **1,100+ commits** — iterative refinement, not theoretical design
- **61,661 benchmark questions** — real evaluation at scale
- **79+ documented production fixes** — every failure mode catalogued
- **4 specialized pipelines** — Standard, Graph, Quantitative, Orchestrator
- **9 compute instances** — distributed architecture, battle-tested
- **10 orchestrator versions** — the current V10.1 is the survivor of 9 failed attempts

### What It Saves You

| Without This Blueprint | With This Blueprint |
|----------------------|-------------------|
| 3-6 months building routing from scratch | Working orchestrator in 1-2 weeks |
| Discovering failure modes in production | 15 failure modes pre-catalogued |
| 10+ orchestrator iterations | Start from V10 (the one that works) |
| $0 figuring out free tier limits yourself | Complete free-tier stack documented |
| Unknown accuracy baselines | Real benchmarks to compare against |

### Comparable Pricing

- LangChain/LlamaIndex courses on agentic RAG: $200-500 (theory-heavy, no production patterns)
- RAG consulting engagement: $5,000-20,000 (custom, but same patterns)
- Hiring an engineer to build this: $15,000-30,000 (3-6 months at any salary level)

**$147 for production-tested agentic RAG patterns is an engineering shortcut, not an expense.**

---

## Guarantee

**30-Day Money-Back Guarantee**

If you implement the patterns in this blueprint and they don't improve your RAG system's routing accuracy or failure recovery, email us within 30 days for a full refund. No questions asked.

We are confident because these patterns are not theoretical — they are extracted from a system currently running in production with measurable results.

---

## Technical Prerequisites

Before purchasing, ensure you have:

- [ ] A working single-pipeline RAG system (or willingness to build one first)
- [ ] Python 3.9+ and basic async programming knowledge
- [ ] Familiarity with REST APIs and webhook patterns
- [ ] Access to an LLM API (OpenRouter free tier is sufficient)
- [ ] Basic understanding of vector databases and embeddings
- [ ] Optional: n8n instance (free on HuggingFace Spaces) for workflow imports

---

## FAQ

**Q: Do I need n8n to use this?**
A: The concepts and patterns are framework-agnostic. The workflow JSONs are n8n-specific, but the routing logic, self-healing patterns, and evaluation framework work with LangChain, LlamaIndex, custom Python, or any orchestration tool.

**Q: Does this work with OpenAI / Anthropic / local models?**
A: Yes. The patterns are model-agnostic. We use free OpenRouter models (Llama 3.3 70B, Gemma 3 27B), but every pattern works with GPT-4, Claude, Mistral, or local models. The prompts may need minor tuning for different model families.

**Q: I only have one RAG pipeline. Is this useful?**
A: Partially. The self-healing patterns (retry, fallback, circuit breaker) and evaluation framework are valuable for single-pipeline systems. But the core value — agent-driven routing across multiple pipelines — requires at least 2 pipelines to be meaningful.

**Q: How is this different from the $97 Operations Runbook?**
A: The Operations Runbook covers building and operating RAG pipelines (infrastructure, ingestion, evaluation, monitoring). This Blueprint focuses specifically on the **agentic layer** — the autonomous decision-making, routing, and self-healing that sits on top of your pipelines. They are complementary: the Runbook builds the foundation, the Blueprint adds the intelligence.

**Q: What if my accuracy is lower than your benchmarks?**
A: Expected. Our numbers (87.5% Standard, 95.2% Quant) are dataset-specific. The patterns will improve your system relative to its current baseline. The evaluation framework helps you measure your specific improvement.

---

*Built from 88+ real engineering sessions · 1,100+ commits · 61,661 benchmark questions · 79+ production fixes · 10 orchestrator versions*
*By Alexis Moret — Polytechnique x HEC Paris · Building production AI systems since 2024*
