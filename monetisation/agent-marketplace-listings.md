# Agent Marketplace Listings — Nomos AI RAG Products

> Generated: 2026-03-08 | Version: 1.0.0
> Machine-readable structured listings for AI agent marketplaces.
> Optimized for agent discovery (GEO) — structured data, not marketing copy.

---

## Table of Contents

1. [Moltbot ClawdHub Listings](#1-moltbot-clawdhub-listings)
2. [AgentX.Market Listings](#2-agentxmarket-listings)
3. [AI Agent Store Listings](#3-ai-agent-store-listings)
4. [Product Catalog (Shared Reference)](#4-product-catalog-shared-reference)

---

## 1. Moltbot ClawdHub Listings

Format: Moltbot skill manifest (YAML front matter + markdown body)

### Listing 1A: Nomos RAG Query Skill

```yaml
# --- ClawdHub Skill Manifest ---
skill_id: nomos-rag-query
display_name: "Nomos RAG Query — Multi-Pipeline Retrieval"
version: 1.0.0
author: nomos-ai
author_url: https://lbjlincoln.github.io/rag-dashboard/store.html
category: knowledge-retrieval
license: commercial
pricing:
  free_tier: true
  free_limits: "10 req/min, 100 req/day"
  paid_price_usd: 127
  paid_product: "RAG Eval Framework"
  purchase_url: "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605"
  bundle_price_usd: 497
  bundle_url: "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d"

description: >
  Query a production RAG system with 3 pipelines: Standard (vector search,
  46K embeddings, 87.5% accuracy), Graph (Neo4j, 79K nodes), and Quantitative
  (SQL over 40 PostgreSQL tables, 95.2% accuracy). Free LLM inference via
  OpenRouter. Hosted on Hugging Face Spaces.

capabilities:
  - id: semantic_search
    description: "Vector similarity search over 46,263 Jina v3 embeddings (1024-dim)"
  - id: graph_traversal
    description: "Entity relationship queries over 79,451 Neo4j nodes and 219,414 relations"
  - id: sql_generation
    description: "Natural language to SQL over 40 Supabase tables (15,263 rows)"
  - id: multi_pipeline_routing
    description: "Automatic routing to best pipeline based on question type"

api:
  type: rest
  base_url: "https://lbjlincoln-nomos-rag-engine.hf.space"
  auth: none
  endpoints:
    - path: "/webhook/rag-multi-index-v3"
      method: POST
      pipeline: standard
      content_type: "application/json"
      request_schema:
        question: {type: string, required: true, max_length: 500}
        tenant_id: {type: string, required: true, default: "benchmark"}
      response_schema:
        answer: {type: string}
        sources: {type: array}
        pipeline: {type: string}
        latency_ms: {type: integer}
    - path: "/webhook/ff622742-6d71-4e91-af71-b5c666088717"
      method: POST
      pipeline: graph
      content_type: "application/json"
      request_schema:
        question: {type: string, required: true, max_length: 500}
        tenant_id: {type: string, required: true, default: "benchmark"}
    - path: "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
      method: POST
      pipeline: quantitative
      content_type: "application/json"
      request_schema:
        question: {type: string, required: true, max_length: 500}
        tenant_id: {type: string, required: true, default: "benchmark"}
  health_check:
    path: "/healthz"
    method: GET
    expected_status: 200

performance:
  standard_accuracy: 87.5
  graph_accuracy: 40.9
  quantitative_accuracy: 95.2
  questions_evaluated: 61661
  avg_latency_ms: {standard: 3500, graph: 7000, quantitative: 10000}
  uptime_percent: 95

tags: [rag, retrieval, vector-search, graph-rag, sql-rag, neo4j, pinecone, supabase, n8n, free-llm]
```

### Listing 1B: Nomos Eval Framework Skill

```yaml
# --- ClawdHub Skill Manifest ---
skill_id: nomos-eval-framework
display_name: "Nomos RAG Eval — 61K-Question Benchmark System"
version: 1.0.0
author: nomos-ai
category: testing-evaluation
license: commercial
pricing:
  free_tier: true
  free_limits: "Smoke tests only (3-5 questions)"
  paid_price_usd: 127
  paid_product: "RAG Eval Framework"
  purchase_url: "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605"
  bundle_price_usd: 497
  bundle_url: "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d"

description: >
  Run structured evaluations on RAG pipelines. 61,661 questions from 18 SOTA
  benchmarks (HotpotQA, TriviaQA, NQ, MMLU). Phase-gated progression from
  200 to 61K questions. Regression detection, golden-answer comparison,
  parallel batch execution across 9 n8n instances.

capabilities:
  - id: smoke_test
    description: "3-5 question quick validation per pipeline"
  - id: batch_eval
    description: "Parallel evaluation with round-robin across 9 instances"
  - id: phase_gates
    description: "Statistical significance testing at 200/1K/10K/61K thresholds"
  - id: regression_detection
    description: "Flag accuracy drops > 5pp vs baseline"
  - id: golden_check
    description: "Compare against verified known-good answers"

api:
  type: rest
  endpoints:
    - path: "/webhook/rag-multi-index-v3"
      method: POST
      pipeline: standard
    - path: "/webhook/ff622742-6d71-4e91-af71-b5c666088717"
      method: POST
      pipeline: graph
    - path: "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
      method: POST
      pipeline: quantitative

eval_specs:
  total_questions: 61661
  benchmarks: 18
  phases: [200, 1000, 10000, 61661]
  scripts: ["quick-test.py", "run-eval-parallel.py", "golden-check.py", "phase_gates.py", "node-analyzer.py"]
  batch_sizes: {standard: 10, graph: 5, quantitative: 3}
  concurrency: {standard: 5, graph: 3, quantitative: 1}

tags: [eval, benchmark, testing, accuracy, regression, rag-eval, hotpotqa, triviaqa, mmlu]
```

### Listing 1C: Nomos Debug Assistant Skill

```yaml
# --- ClawdHub Skill Manifest ---
skill_id: nomos-debug-assistant
display_name: "Nomos RAG Debug — 90+ Fix Patterns"
version: 1.0.0
author: nomos-ai
category: debugging-operations
license: commercial
pricing:
  free_tier: true
  free_limits: "Top 12 patterns + diagnostic flowcharts"
  paid_price_usd: 47
  paid_product: "RAG Debug Playbook"
  purchase_url: "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600"
  bundle_price_usd: 497
  bundle_url: "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d"

description: >
  Diagnose and fix RAG pipeline failures using 90+ documented fixes from
  76+ debugging sessions. Covers n8n workflow bugs, LLM provider errors,
  vector DB issues, SQL failures, and infrastructure outages. Implements
  Self-Healing RAG: detect, diagnose, classify, auto-fix, verify.

capabilities:
  - id: symptom_diagnosis
    description: "Match error symptoms to known fix patterns"
  - id: severity_classification
    description: "P0-P4 severity levels with action recommendations"
  - id: auto_fix_suggestions
    description: "Step-by-step fix instructions for documented patterns"
  - id: health_check
    description: "Infrastructure health verification (n8n, Pinecone, Neo4j, Supabase)"
  - id: regression_guard
    description: "Post-fix verification to prevent cascading failures"

fix_library:
  total_fixes: 90
  categories:
    infrastructure: 15
    rate_limiting: 12
    workflow_bugs: 25
    data_quality: 18
    llm_behavior: 20
  severity_levels: ["P0-Infrastructure", "P1-RateLimit", "P2-Workflow", "P3-Data", "P4-Model"]

tags: [debug, troubleshooting, n8n, self-healing, rag-debug, fix-library, diagnostics]
```

---

## 2. AgentX.Market Listings

Format: AgentX agent listing (JSON-LD structured data)

### Listing 2A: Nomos Multi-RAG Agent

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Nomos Multi-RAG Orchestrator",
  "alternateName": "nomos-multi-rag",
  "description": "Production multi-pipeline RAG system with 3 specialized pipelines (Standard vector search, Graph entity traversal, Quantitative SQL). 87.5% accuracy on 10K+ questions. Free LLM inference. Self-hosted on Hugging Face Spaces with n8n orchestration.",
  "applicationCategory": "AI Agent / Knowledge Retrieval",
  "operatingSystem": "Cloud (API)",
  "url": "https://lbjlincoln.github.io/rag-dashboard/store.html",
  "author": {
    "@type": "Organization",
    "name": "Nomos AI",
    "url": "https://lbjlincoln.github.io/rag-dashboard/store.html"
  },
  "offers": [
    {
      "@type": "Offer",
      "name": "MEGA BUNDLE - All 13 RAG Products",
      "price": "497.00",
      "priceCurrency": "USD",
      "url": "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",
      "description": "Complete RAG engineering toolkit: architecture, workflows, eval framework, debug playbook, dashboard, ingestion, embeddings, benchmarks, skills, and agent context kit.",
      "itemCondition": "https://schema.org/NewCondition",
      "availability": "https://schema.org/InStock"
    },
    {
      "@type": "Offer",
      "name": "Architecture Blueprint",
      "price": "197.00",
      "priceCurrency": "USD",
      "url": "https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602",
      "description": "Complete architecture for a production multi-pipeline RAG system. Standard, Graph, and Quantitative pipelines. n8n orchestration. Pinecone + Neo4j + Supabase."
    },
    {
      "@type": "Offer",
      "name": "n8n Workflow Collection",
      "price": "197.00",
      "priceCurrency": "USD",
      "url": "https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603",
      "description": "7 production n8n workflow JSON files. Standard RAG, Graph RAG, Quantitative RAG, 3 website pipelines, and orchestrator. Ready to import."
    },
    {
      "@type": "Offer",
      "name": "RAG Eval Framework",
      "price": "127.00",
      "priceCurrency": "USD",
      "url": "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605",
      "description": "61,661 evaluation questions from 18 SOTA benchmarks. 9 Python scripts. Phase-gated progression. Parallel execution across 9 instances."
    },
    {
      "@type": "Offer",
      "name": "RAG Debug Playbook",
      "price": "47.00",
      "priceCurrency": "USD",
      "url": "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600",
      "description": "90+ documented fixes from 76+ debugging sessions. Diagnostic flowcharts. Self-healing patterns. Covers n8n, LLM, vector DB, SQL, and infrastructure issues."
    },
    {
      "@type": "Offer",
      "name": "Agent Context Kit",
      "price": "27.00",
      "priceCurrency": "USD",
      "url": "https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601",
      "description": "CLAUDE.md templates, state file patterns, and agent instruction frameworks. Tested across 76+ Claude Code sessions and 1,100+ commits."
    }
  ],
  "softwareRequirements": "HTTP client capable of POST requests with JSON body",
  "featureList": [
    "3 specialized RAG pipelines (Standard, Graph, Quantitative)",
    "87.5% accuracy on Standard pipeline (10K questions)",
    "95.2% accuracy on Quantitative pipeline",
    "46,263 Jina v3 embeddings (1024-dim) in Pinecone",
    "79,451 nodes in Neo4j knowledge graph",
    "40 PostgreSQL tables in Supabase",
    "Free LLM inference via OpenRouter (Llama 3.3 70B, Gemma 27B)",
    "n8n workflow orchestration on Hugging Face Spaces",
    "61,661 evaluation questions from 18 SOTA benchmarks",
    "90+ documented debug fixes",
    "Self-healing RAG pattern implementation"
  ],
  "screenshot": "https://lbjlincoln.github.io/rag-dashboard/",
  "releaseNotes": "Phase 3 complete. Standard 87.5%, Quant 95.2%. 9 HF Space instances. LiteLLM proxy. Self-hosted embeddings."
}
```

### Listing 2B: AgentX Capabilities Spec

```yaml
# AgentX.Market — Agent Capabilities Spec
agent_id: nomos-multi-rag
version: 1.0.0
status: production
maturity: beta

input_types:
  - natural_language_question
  - structured_json

output_types:
  - natural_language_answer
  - json_with_sources
  - sql_query_result

protocols:
  - rest_api
  - webhook

authentication: none (free tier) | api_key (paid tier)

rate_limits:
  free:
    requests_per_minute: 10
    requests_per_day: 100
  paid:
    requests_per_minute: 60
    requests_per_day: unlimited

latency:
  p50_ms: 3500
  p95_ms: 12000
  p99_ms: 25000

reliability:
  uptime_sla: "95%"
  cold_start_seconds: 30
  retry_strategy: "exponential backoff, max 3 retries"

data_coverage:
  domains: [finance, legal, construction, manufacturing]
  languages: [en, fr]
  vector_count: 46263
  graph_nodes: 79451
  sql_tables: 40
  document_count: 11387

benchmarks:
  - name: "Phase 3 Standard"
    questions: 10917
    accuracy: 87.5
  - name: "Phase 3 Graph"
    questions: 11300
    accuracy: 40.9
  - name: "Phase 3 Quantitative"
    questions: 3550
    accuracy: 95.2

pricing_tiers:
  - tier: free
    price_usd: 0
    limits: "10 req/min, 100 req/day, smoke tests only"
  - tier: eval_framework
    price_usd: 127
    includes: "61K questions, 9 scripts, batch runner, phase gates"
    url: "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605"
  - tier: debug_playbook
    price_usd: 47
    includes: "90+ fixes, diagnostic flowcharts, self-healing scripts"
    url: "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600"
  - tier: full_bundle
    price_usd: 497
    includes: "All 13 products"
    url: "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d"
```

---

## 3. AI Agent Store Listings

Format: aiagentstore.ai submission format (structured markdown + metadata)

### Listing 3A: Main Agent Listing

```
--- AGENT LISTING ---
name: Nomos Multi-RAG Orchestrator
slug: nomos-multi-rag
tagline: Production RAG system — 3 pipelines, 87.5% accuracy, $0 inference cost
category: Knowledge Retrieval & QA
subcategory: RAG Systems
status: Production (Beta)
author: Nomos AI
website: https://lbjlincoln.github.io/rag-dashboard/store.html
store_url: https://lbjlincoln.github.io/rag-dashboard/store.html
demo_url: https://lbjlincoln-nomos-rag-engine.hf.space/healthz
documentation: https://github.com/lbjlincoln/mon-ipad

--- PRICING ---
free_tier: Yes (10 req/min, 100 req/day)
plans:
  - name: Agent Context Kit
    price: $27
    url: https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601
    type: one-time
    description: CLAUDE.md templates and agent instruction frameworks
  - name: Debug Playbook
    price: $47
    url: https://buy.stripe.com/00w7sEd1U2v14j92FT5J600
    type: one-time
    description: 90+ fixes, diagnostic flowcharts, self-healing patterns
  - name: Eval Framework
    price: $127
    url: https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605
    type: one-time
    description: 61K questions, 18 benchmarks, 9 eval scripts, phase gates
  - name: Architecture Blueprint
    price: $197
    url: https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602
    type: one-time
    description: Complete multi-pipeline RAG architecture documentation
  - name: n8n Workflows
    price: $197
    url: https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603
    type: one-time
    description: 7 production workflow files ready for n8n import
  - name: MEGA BUNDLE
    price: $497
    url: https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d
    type: one-time
    description: All 13 products in one package

--- TECHNICAL SPECS ---
type: API (REST webhooks)
authentication: None (free tier)
response_format: JSON
avg_response_time: 3-12 seconds
hosting: Hugging Face Spaces (9 instances)
databases:
  - Pinecone (46,263 vectors, Jina v3 1024-dim)
  - Neo4j Aura (79,451 nodes, 219,414 relationships)
  - Supabase PostgreSQL (40 tables, 15,263 rows)
llm_models:
  - meta-llama/llama-3.3-70b-instruct (free via OpenRouter)
  - google/gemma-3-27b-it (free via OpenRouter)
  - arcee-ai/trinity-large-preview (free via OpenRouter)
orchestration: n8n (self-hosted)
embeddings: Jina v3 (self-hosted on HF Space)
cost_per_query: $0.00

--- CAPABILITIES ---
1. Standard RAG Pipeline
   - Vector similarity search over 46K+ embeddings
   - Best for factual questions, definitions, explanations
   - 87.5% accuracy on 10,917 evaluation questions
   - Endpoint: POST /webhook/rag-multi-index-v3

2. Graph RAG Pipeline
   - Entity traversal over Neo4j knowledge graph
   - Best for relationship questions, entity connections
   - 40.9% accuracy on 11,300 questions (known limitation: entity enrichment pending)
   - Endpoint: POST /webhook/ff622742-6d71-4e91-af71-b5c666088717

3. Quantitative RAG Pipeline
   - Natural language to SQL generation
   - Best for numerical questions, comparisons, rankings
   - 95.2% accuracy on 3,550 questions
   - Endpoint: POST /webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9

4. Evaluation Framework
   - 61,661 questions from 18 SOTA benchmarks
   - Phase-gated progression (200 -> 1K -> 10K -> 61K)
   - Regression detection (5pp threshold)
   - Parallel execution across 9 n8n instances

5. Debug & Self-Healing
   - 90+ documented fix patterns
   - Severity classification (P0-P4)
   - Diagnostic flowcharts for common failures
   - Post-fix regression verification

--- API REFERENCE ---
Base URL: https://lbjlincoln-nomos-rag-engine.hf.space

Endpoints:
  GET /healthz
    Returns: 200 OK if n8n is running

  POST /webhook/rag-multi-index-v3
    Body: {"question": "string", "tenant_id": "benchmark"}
    Returns: {"answer": "string", "sources": [], "pipeline": "standard", "latency_ms": int}

  POST /webhook/ff622742-6d71-4e91-af71-b5c666088717
    Body: {"question": "string", "tenant_id": "benchmark"}
    Returns: {"answer": "string", "sources": [], "pipeline": "graph", "latency_ms": int}

  POST /webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
    Body: {"question": "string", "tenant_id": "benchmark"}
    Returns: {"answer": "string", "sources": [], "pipeline": "quantitative", "latency_ms": int}

Error Codes:
  200: Success
  404: Webhook not registered (workflow inactive)
  429: Rate limited (wait 60s)
  500: Internal error (retry once)
  502/503: HF Space sleeping (wait 30s for cold start)

--- INTEGRATION EXAMPLES ---

Python:
  import requests
  resp = requests.post(
      "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3",
      json={"question": "What is RAG?", "tenant_id": "benchmark"}
  )
  print(resp.json()["answer"])

JavaScript:
  const resp = await fetch(
    "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3",
    {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: "What is RAG?", tenant_id: "benchmark"})
    }
  );
  const data = await resp.json();
  console.log(data.answer);

curl:
  curl -X POST \
    "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
    -H "Content-Type: application/json" \
    -d '{"question": "What is RAG?", "tenant_id": "benchmark"}'

--- KEYWORDS ---
rag, retrieval-augmented-generation, multi-pipeline, vector-search, graph-rag,
sql-rag, neo4j, pinecone, supabase, n8n, evaluation-framework, debug-playbook,
self-healing, free-llm, hugging-face, jina-embeddings, llama-70b, gemma-27b,
knowledge-retrieval, qa-system, benchmark, hotpotqa, triviaqa, mmlu
```

### Listing 3B: Individual Product Listings

```
--- PRODUCT: Architecture Blueprint ---
id: nomos-architecture-blueprint
price: $197
url: https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602
format: ZIP (documentation + diagrams)
contents:
  - Multi-pipeline RAG architecture documentation
  - Pipeline flow diagrams (Standard, Graph, Quantitative, Orchestrator)
  - Database schema references (Pinecone, Neo4j, Supabase)
  - n8n workflow architecture overview
  - Deployment guide for Hugging Face Spaces
  - LiteLLM proxy configuration
  - Self-hosted embeddings setup
use_case: Build your own multi-pipeline RAG system from scratch
prerequisites: Familiarity with RAG concepts, n8n, vector databases

--- PRODUCT: n8n Workflows ---
id: nomos-n8n-workflows
price: $197
url: https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603
format: ZIP (7 JSON files)
contents:
  - WF1: Standard RAG V3.4 (Groq direct)
  - WF2: Graph RAG V3.3 (Groq direct)
  - WF3: Quantitative RAG V3.1 (LiteLLM)
  - WF4: Website Standard Pipeline
  - WF5: Website Graph Pipeline
  - WF6: Website Quantitative Pipeline
  - WF7: Orchestrator V10.1
  - Import instructions
  - Credential setup guide
use_case: Import production RAG workflows into your own n8n instance
prerequisites: n8n instance, API keys for LLM providers

--- PRODUCT: Eval Framework ---
id: nomos-eval-framework
price: $127
url: https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605
format: ZIP (Python scripts + datasets)
contents:
  - 9 Python evaluation scripts
  - 61,661 evaluation questions from 18 benchmarks
  - Phase gate configuration
  - Golden answer sets
  - Dashboard integration (status.json, data.json)
  - Parallel execution runner (round-robin across instances)
use_case: Evaluate any RAG system with production-grade benchmarks
prerequisites: Python 3.8+, HTTP access to RAG endpoints

--- PRODUCT: Debug Playbook ---
id: nomos-debug-playbook
price: $47
url: https://buy.stripe.com/00w7sEd1U2v14j92FT5J600
format: ZIP (markdown + scripts)
contents:
  - 90+ documented fixes (FIX-01 to FIX-90)
  - Diagnostic flowcharts
  - Iron rules (never violate)
  - LLM behavior patterns
  - Database troubleshooting guide
  - Self-healing automation scripts
  - Anti-patterns catalog
use_case: Debug RAG pipeline failures systematically
prerequisites: Basic understanding of RAG pipelines, n8n, REST APIs

--- PRODUCT: Agent Context Kit ---
id: nomos-agent-context-kit
price: $27
url: https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601
format: ZIP (markdown templates)
contents:
  - CLAUDE.md template (tested across 76+ sessions, 1,100+ commits)
  - State file patterns (PROJECT-STATE, DEBUG-PLAYBOOK, INFRASTRUCTURE)
  - Process runbook templates
  - Multi-repo directive sync system
  - 17 Claude Code skill templates
  - Session management patterns
use_case: Structure agent context for long-running engineering projects
prerequisites: Claude Code or similar AI coding assistant

--- PRODUCT: MEGA BUNDLE ---
id: nomos-mega-bundle
price: $497
url: https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d
format: ZIP (all products combined)
contents: All 13 products listed above plus:
  - Enterprise Site Template (Next.js 15)
  - Agentic Commerce Playbook
  - RAG Engineering Handbook
  - Ingestion Toolkit V4
  - Dashboard Template
  - Benchmark Dataset Toolkit
  - Embeddings Engine (self-hosted Jina)
  - Claude Code Skills Pack (17 commands)
savings: "$1,450 total value — save $953"
use_case: Complete RAG engineering toolkit for building production systems
prerequisites: Development experience with Python, JavaScript, REST APIs
```

---

## 4. Product Catalog (Shared Reference)

Machine-readable product catalog for cross-platform use.

```json
{
  "vendor": "Nomos AI",
  "catalog_version": "1.0.0",
  "last_updated": "2026-03-08",
  "store_url": "https://lbjlincoln.github.io/rag-dashboard/store.html",
  "payment_processor": "Stripe",
  "currency": "USD",
  "products": [
    {
      "id": "mega-bundle",
      "name": "MEGA BUNDLE - All 13 RAG Products",
      "price": 497,
      "stripe_url": "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",
      "category": "bundle",
      "tags": ["rag", "architecture", "workflows", "eval", "debug", "complete"]
    },
    {
      "id": "architecture-blueprint",
      "name": "Architecture Blueprint - Multi-Pipeline RAG System",
      "price": 197,
      "stripe_url": "https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602",
      "category": "documentation",
      "tags": ["architecture", "rag", "multi-pipeline", "design"]
    },
    {
      "id": "n8n-workflows",
      "name": "n8n Workflow Collection - Production RAG Workflows",
      "price": 197,
      "stripe_url": "https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603",
      "category": "code",
      "tags": ["n8n", "workflows", "automation", "rag"]
    },
    {
      "id": "eval-framework",
      "name": "RAG Eval Framework - 61K-Question System",
      "price": 127,
      "stripe_url": "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605",
      "category": "testing",
      "tags": ["eval", "benchmark", "testing", "accuracy", "61k-questions"]
    },
    {
      "id": "debug-playbook",
      "name": "RAG Debug Playbook - 90+ Fixes",
      "price": 47,
      "stripe_url": "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600",
      "category": "operations",
      "tags": ["debug", "troubleshooting", "fixes", "self-healing"]
    },
    {
      "id": "agent-context-kit",
      "name": "Agent Context Kit - CLAUDE.md Templates",
      "price": 27,
      "stripe_url": "https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601",
      "category": "agent-tools",
      "tags": ["claude-code", "agent", "context", "templates", "skills"]
    }
  ],
  "api_specs": {
    "base_url": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "auth": "none",
    "format": "JSON",
    "endpoints": {
      "health": "GET /healthz",
      "standard": "POST /webhook/rag-multi-index-v3",
      "graph": "POST /webhook/ff622742-6d71-4e91-af71-b5c666088717",
      "quantitative": "POST /webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
    },
    "request_schema": {
      "question": "string (required, max 500 chars)",
      "tenant_id": "string (required, default: benchmark)"
    }
  }
}
```
