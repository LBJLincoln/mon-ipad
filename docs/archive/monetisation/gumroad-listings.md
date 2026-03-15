# Gumroad Product Listings — Ready to Publish

> Store: https://nomos42.gumroad.com
> Last updated: 2026-03-07

---

## GUMROAD API NOTES

**Product creation is NOT supported via the Gumroad API.**
Products must be created manually on the Gumroad website. The API only supports:
- `GET /v2/products` — List products
- `GET /v2/products/:id` — Get product details
- `PUT /v2/products/:id` — Update existing product
- `PUT /v2/products/:id/enable` — Enable product
- `PUT /v2/products/:id/disable` — Disable product
- `DELETE /v2/products/:id` — Delete product

**To set up API access:**
1. Go to https://gumroad.com/settings/advanced
2. Create a new application (name + redirect URI)
3. Get your Access Token (keep secret)
4. Use Bearer auth: `Authorization: Bearer YOUR_ACCESS_TOKEN`

Once products are created manually, use the API commands below to update them programmatically.

---

## PRODUCT 1: RAG Debug Playbook

### Gumroad Fields (copy-paste into Gumroad product form)

**Name:** RAG Debug Playbook — 79+ Production Fixes for AI Pipelines

**Price:** $47

**Custom URL:** `rag-debug-playbook`
→ Full URL: https://nomos42.gumroad.com/l/rag-debug-playbook

**Summary (SEO — appears in search results, max 750 chars):**
The definitive troubleshooting guide for RAG systems in production. 79 documented fixes from 78 engineering sessions building a multi-pipeline RAG orchestrator. Covers Pinecone, Neo4j, Supabase, n8n workflows, LLM rate limiting, embedding failures, and query routing. Includes diagnostic flowcharts that take you from symptom to fix in under 5 minutes. Used internally to achieve 87.5% accuracy on 10,000-question benchmarks. PDF + Markdown format — works as a Claude/Copilot/Cursor context file. Stop debugging blind. Ship RAG systems that work.

**Tags:** RAG, debugging, AI, LLM, production, Pinecone, Neo4j, Supabase, n8n, machine-learning, retrieval-augmented-generation, vector-database, developer-tools

**Description (HTML for Gumroad):**

```html
<h2>Stop Debugging RAG Systems Blind</h2>

<p>You've built a RAG pipeline. It works on 10 test questions. Then production hits and everything breaks — empty retrievals, hallucinated SQL, serialization errors, rate limits at 2 AM.</p>

<p><strong>This playbook is the fix library we wish existed when we started.</strong></p>

<h3>What You Get</h3>

<ul>
  <li><strong>79+ documented production fixes</strong> — each with root cause, solution code, and prevention strategy</li>
  <li><strong>Diagnostic flowcharts</strong> — go from symptom to fix in under 5 minutes</li>
  <li><strong>Iron rules</strong> — the non-negotiable patterns that prevent 80% of RAG failures</li>
  <li><strong>Database gotchas</strong> — Pinecone metadata limits, Neo4j Cypher pitfalls, Supabase connection pooling traps</li>
  <li><strong>LLM reliability patterns</strong> — rate limit rotation, model fallbacks, prompt injection defense</li>
  <li><strong>n8n workflow debugging</strong> — the hidden behaviors that silently break your pipelines</li>
</ul>

<h3>Battle-Tested Results</h3>

<p>This playbook was built across <strong>78 engineering sessions</strong> and <strong>1,100+ commits</strong>. It powered a system that achieved:</p>
<ul>
  <li>87.5% accuracy on 10,000-question benchmarks (Standard RAG)</li>
  <li>95.2% accuracy on quantitative/financial queries</li>
  <li>4 specialized pipelines running on 100% free infrastructure</li>
</ul>

<h3>Format</h3>

<p><strong>PDF + Markdown (.md)</strong> — The Markdown version works directly as a context file for Claude Code, GitHub Copilot, or Cursor. Paste it into your project and your AI assistant instantly knows every fix.</p>

<h3>Who This Is For</h3>

<ul>
  <li>Developers building RAG systems who are tired of cryptic errors</li>
  <li>Teams deploying LLM applications to production</li>
  <li>AI engineers working with vector databases + knowledge graphs</li>
  <li>Anyone using n8n, LangChain, or LlamaIndex for retrieval pipelines</li>
</ul>

<p><em>"The 10 mistakes every RAG builder makes — and how to never make them again."</em></p>
```

---

### Twitter/X Post (280 chars max)

```
We built a RAG system across 78 sessions and 1,100+ commits. Every failure became a fix.

79+ production fixes. Diagnostic flowcharts. Works as a Claude/Copilot context file.

RAG Debug Playbook — $47

https://nomos42.gumroad.com/l/rag-debug-playbook
```

(276 chars)

---

### Reddit Post — r/MachineLearning or r/LangChain

**Title:** We documented 79+ production RAG fixes from 78 engineering sessions — releasing as a debug playbook

**Body:**

```
After 78 engineering sessions building a multi-pipeline RAG orchestrator (Standard, Graph, Quantitative, Orchestrator), we compiled every production failure into a structured debug playbook.

**What's inside:**
- 79+ fixes with root cause analysis, solution code, and prevention
- Diagnostic flowcharts: symptom → fix in <5 min
- Database-specific gotchas (Pinecone, Neo4j, Supabase)
- LLM reliability: rate limiting, model fallback, key rotation
- n8n workflow debugging (disabled nodes still fire HTTP requests — yes, really)

**Results this playbook helped achieve:**
- 87.5% accuracy on 10K-question benchmarks (Standard pipeline)
- 95.2% on quantitative queries
- Running on 100% free-tier infrastructure (HF Spaces + Supabase + Pinecone + Neo4j)

**Format:** PDF + Markdown. The .md version works as a Claude Code / Copilot / Cursor context file — drop it in your project and your AI knows every fix.

$47 on Gumroad: https://nomos42.gumroad.com/l/rag-debug-playbook

Happy to answer questions about specific fixes or the architecture.
```

---

### JSON-LD Structured Data (Agentic Commerce)

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "RAG Debug Playbook — 79+ Production Fixes for AI Pipelines",
  "description": "The definitive troubleshooting guide for RAG systems in production. 79 documented fixes from 78 engineering sessions. Diagnostic flowcharts, database gotchas, LLM reliability patterns. PDF + Markdown format compatible with Claude Code, Copilot, and Cursor.",
  "brand": {
    "@type": "Brand",
    "name": "Nomos AI"
  },
  "category": "Software > Developer Tools > AI/ML Debugging",
  "sku": "NOMOS-RAG-DEBUG-001",
  "image": "https://nomos42.gumroad.com/assets/rag-debug-playbook-cover.png",
  "url": "https://nomos42.gumroad.com/l/rag-debug-playbook",
  "offers": {
    "@type": "Offer",
    "url": "https://nomos42.gumroad.com/l/rag-debug-playbook",
    "priceCurrency": "USD",
    "price": "47.00",
    "availability": "https://schema.org/InStock",
    "priceValidUntil": "2027-03-07",
    "seller": {
      "@type": "Organization",
      "name": "Nomos AI",
      "url": "https://nomos42.gumroad.com"
    }
  },
  "additionalProperty": [
    {
      "@type": "PropertyValue",
      "name": "format",
      "value": "PDF + Markdown (.md)"
    },
    {
      "@type": "PropertyValue",
      "name": "ai_agent_compatible",
      "value": "true"
    },
    {
      "@type": "PropertyValue",
      "name": "context_file_format",
      "value": "Claude Code, GitHub Copilot, Cursor"
    },
    {
      "@type": "PropertyValue",
      "name": "fixes_count",
      "value": "79+"
    }
  ],
  "potentialAction": {
    "@type": "BuyAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://nomos42.gumroad.com/l/rag-debug-playbook",
      "actionPlatform": [
        "https://schema.org/DesktopWebPlatform",
        "https://schema.org/MobileWebPlatform"
      ]
    }
  }
}
```

---

### Gumroad API: Update Product (after manual creation)

```bash
# First, get the product ID by listing all products
curl -s https://api.gumroad.com/v2/products \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -X GET | jq '.products[] | {id, name}'

# Update the product (replace PRODUCT_ID with actual ID)
curl -s https://api.gumroad.com/v2/products/PRODUCT_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -X PUT \
  -d "name=RAG Debug Playbook — 79+ Production Fixes for AI Pipelines" \
  -d "price=4700" \
  -d "description=The definitive troubleshooting guide for RAG systems in production. 79 documented fixes from 78 engineering sessions building a multi-pipeline RAG orchestrator." \
  -d "custom_permalink=rag-debug-playbook" \
  -d "published=true"

# Enable the product
curl -s https://api.gumroad.com/v2/products/PRODUCT_ID/enable \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -X PUT
```

---
---

## PRODUCT 2: AI Agent Context Kit

### Gumroad Fields

**Name:** AI Agent Context Kit — RAG Debugging for Claude, Copilot & Cursor

**Price:** $27

**Custom URL:** `ai-agent-context-kit`
→ Full URL: https://nomos42.gumroad.com/l/ai-agent-context-kit

**Summary (SEO):**
Drop-in context files that make your AI coding assistant an expert RAG debugger. Structured .md files optimized for Claude Code (CLAUDE.md), GitHub Copilot, and Cursor. Contains 79+ production fixes, architecture references, error pattern databases, and prompt templates — all formatted so AI agents can parse and apply them instantly. The fastest way to give your AI assistant production RAG knowledge. Works with any LLM-based IDE integration.

**Tags:** AI-agent, context-file, Claude, Copilot, Cursor, RAG, debugging, developer-tools, prompt-engineering, CLAUDE-md, LLM, machine-learning, agentic-commerce

**Description (HTML for Gumroad):**

```html
<h2>Give Your AI Coding Assistant Production RAG Knowledge — Instantly</h2>

<p>Your AI assistant is only as good as its context. Right now, it knows nothing about your RAG pipeline's failure modes. <strong>Fix that in 30 seconds.</strong></p>

<h3>What You Get</h3>

<ul>
  <li><strong>CLAUDE.md context file</strong> — Drop into any project. Claude Code instantly knows 79+ RAG fixes, diagnostic patterns, and architecture decisions.</li>
  <li><strong>Copilot/Cursor context file</strong> — Same knowledge, formatted for GitHub Copilot and Cursor's context systems.</li>
  <li><strong>RAG architecture reference card</strong> — Compact overview of multi-pipeline RAG (Standard, Graph, Quantitative) with routing logic.</li>
  <li><strong>Error pattern database</strong> — Structured data: symptom → root cause → fix → prevention. Machine-readable.</li>
  <li><strong>Prompt templates</strong> — Pre-built prompts for RAG debugging, query analysis, retrieval diagnostics.</li>
</ul>

<h3>How It Works</h3>

<ol>
  <li>Download the .md files</li>
  <li>Drop them into your project root (or <code>.claude/</code>, <code>.github/</code>, <code>.cursorrules</code>)</li>
  <li>Your AI assistant now has production RAG expertise</li>
</ol>

<h3>Why Context Files Beat Documentation</h3>

<p>Documentation sits in a browser tab you never read. Context files live <em>inside</em> your workflow. Every time you ask Claude, Copilot, or Cursor for help, it automatically reads these files and applies the knowledge.</p>

<p><strong>No copy-pasting. No tab-switching. No "let me look that up."</strong></p>

<h3>Built From Real Production Data</h3>

<p>These aren't theoretical patterns. They come from 78 engineering sessions, 1,100+ commits, and 79+ production failures that were diagnosed, fixed, and documented. The system they debug achieved 87.5% accuracy on 10K-question benchmarks.</p>

<h3>Compatible With</h3>

<ul>
  <li>Claude Code (CLAUDE.md native support)</li>
  <li>GitHub Copilot (workspace context)</li>
  <li>Cursor (.cursorrules + context files)</li>
  <li>Any LLM that accepts system prompts or context injection</li>
  <li>AI agents that purchase and consume developer tools</li>
</ul>
```

---

### Twitter/X Post (280 chars max)

```
Your AI coding assistant knows nothing about RAG failures.

Fix that in 30 seconds — drop-in context files for Claude, Copilot & Cursor. 79+ production fixes, instantly available.

AI Agent Context Kit — $27

https://nomos42.gumroad.com/l/ai-agent-context-kit
```

(270 chars)

---

### Reddit Post — r/LangChain or r/ClaudeAI

**Title:** Made drop-in context files that give Claude/Copilot/Cursor instant RAG debugging expertise (79+ fixes)

**Body:**

```
I've been building a multi-pipeline RAG system for ~78 sessions. Along the way, I documented every production failure as a structured fix (root cause + solution + prevention).

I packaged those fixes as context files optimized for AI coding assistants:

- **CLAUDE.md** — native Claude Code format, drops into project root
- **Copilot context** — works with GitHub Copilot workspace context
- **Cursor rules** — .cursorrules compatible format

**What your AI assistant learns:**
- 79+ RAG production fixes (Pinecone, Neo4j, Supabase, n8n)
- Diagnostic flowcharts (symptom → fix)
- Architecture patterns (multi-pipeline routing, HyDE, RRF)
- Error pattern database (structured, machine-readable)
- Prompt templates for RAG debugging

**Why it works:** Claude Code natively reads CLAUDE.md at session start. Copilot reads workspace context. Cursor reads .cursorrules. No manual lookup — the knowledge is just _there_ when you ask for help.

$27 on Gumroad: https://nomos42.gumroad.com/l/ai-agent-context-kit

This is specifically designed for developers who are building RAG and want their AI assistant to stop suggesting generic solutions.
```

---

### JSON-LD Structured Data (Agentic Commerce)

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "AI Agent Context Kit — RAG Debugging for Claude, Copilot & Cursor",
  "description": "Drop-in .md context files that give AI coding assistants instant expertise in RAG debugging. 79+ production fixes, architecture references, error patterns, and prompt templates. Compatible with Claude Code (CLAUDE.md), GitHub Copilot, and Cursor.",
  "brand": {
    "@type": "Brand",
    "name": "Nomos AI"
  },
  "category": "Software > Developer Tools > AI Agent Context",
  "sku": "NOMOS-AGENT-CTX-001",
  "image": "https://nomos42.gumroad.com/assets/ai-agent-context-kit-cover.png",
  "url": "https://nomos42.gumroad.com/l/ai-agent-context-kit",
  "offers": {
    "@type": "Offer",
    "url": "https://nomos42.gumroad.com/l/ai-agent-context-kit",
    "priceCurrency": "USD",
    "price": "27.00",
    "availability": "https://schema.org/InStock",
    "priceValidUntil": "2027-03-07",
    "seller": {
      "@type": "Organization",
      "name": "Nomos AI",
      "url": "https://nomos42.gumroad.com"
    }
  },
  "additionalProperty": [
    {
      "@type": "PropertyValue",
      "name": "format",
      "value": "Markdown (.md) context files"
    },
    {
      "@type": "PropertyValue",
      "name": "ai_agent_compatible",
      "value": "true"
    },
    {
      "@type": "PropertyValue",
      "name": "compatible_tools",
      "value": "Claude Code, GitHub Copilot, Cursor, any LLM"
    },
    {
      "@type": "PropertyValue",
      "name": "machine_readable",
      "value": "true"
    },
    {
      "@type": "PropertyValue",
      "name": "integration_method",
      "value": "Drop .md file into project root"
    }
  ],
  "potentialAction": {
    "@type": "BuyAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://nomos42.gumroad.com/l/ai-agent-context-kit",
      "actionPlatform": [
        "https://schema.org/DesktopWebPlatform",
        "https://schema.org/MobileWebPlatform"
      ]
    }
  },
  "audience": {
    "@type": "Audience",
    "audienceType": "Developers, AI Agents, Software Engineers"
  }
}
```

---

### Gumroad API: Update Product

```bash
curl -s https://api.gumroad.com/v2/products/PRODUCT_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -X PUT \
  -d "name=AI Agent Context Kit — RAG Debugging for Claude, Copilot & Cursor" \
  -d "price=2700" \
  -d "description=Drop-in context files that make your AI coding assistant an expert RAG debugger. 79+ production fixes formatted for Claude Code, GitHub Copilot, and Cursor." \
  -d "custom_permalink=ai-agent-context-kit" \
  -d "published=true"
```

---
---

## PRODUCT 3: Multi-RAG Architecture Blueprint

### Gumroad Fields

**Name:** Multi-RAG Architecture Blueprint — 4 Pipelines, Free Infrastructure, Production-Ready

**Price:** $197

**Custom URL:** `multi-rag-blueprint`
→ Full URL: https://nomos42.gumroad.com/l/multi-rag-blueprint

**Summary (SEO):**
Complete architecture for building a multi-pipeline RAG system with 4 specialized pipelines (Standard, Graph, Quantitative, Orchestrator). Includes n8n workflow JSON files ready to import, LiteLLM proxy config for free LLM access, evaluation methodology from 200 to 61K questions, and full infrastructure setup on 100% free tiers (HF Spaces, Supabase, Pinecone, Neo4j). Built across 78 sessions, 1,100+ commits. Achieved 87.5% Standard and 95.2% Quantitative accuracy. For tech leads and AI engineers who want production RAG without cloud bills.

**Tags:** RAG, architecture, multi-pipeline, n8n, LLM, free-infrastructure, AI-engineering, vector-database, knowledge-graph, Pinecone, Neo4j, Supabase, HuggingFace, blueprint, production, evaluation

**Description (HTML for Gumroad):**

```html
<h2>The Complete Blueprint for Multi-Pipeline RAG — On Free Infrastructure</h2>

<p>Most RAG tutorials show you a single pipeline with 20 lines of LangChain. Production RAG is nothing like that.</p>

<p>This blueprint documents the <strong>full architecture</strong> of a system that routes queries to 4 specialized pipelines, runs on 100% free-tier infrastructure, and achieves benchmark-beating accuracy.</p>

<h3>What You Get</h3>

<h4>Architecture Documentation</h4>
<ul>
  <li><strong>4 specialized pipelines</strong> — Standard (text), Graph (relationships), Quantitative (tables/numbers), Orchestrator (multi-hop)</li>
  <li><strong>Intelligent query routing</strong> — Intent classification that sends each query to the right pipeline</li>
  <li><strong>Dual-retrieval strategy</strong> — HyDE (Hypothetical Document Embedding) + Original query + BM25 keyword search</li>
  <li><strong>RRF merge algorithm</strong> — Reciprocal Rank Fusion to combine results from multiple retrieval methods</li>
  <li><strong>Reranking integration</strong> — Cohere and Jina rerankers for precision</li>
</ul>

<h4>Ready-to-Import Workflow Files</h4>
<ul>
  <li><strong>n8n workflow JSONs</strong> — Import directly into n8n and have working pipelines in minutes</li>
  <li><strong>LiteLLM proxy configuration</strong> — Access 9 LLM models for free (Llama 3.3 70B, Gemma 3 27B, Qwen 2.5 235B, Gemini Flash)</li>
  <li><strong>Evaluation scripts</strong> — Python scripts for testing accuracy across datasets</li>
</ul>

<h4>Infrastructure Guide</h4>
<ul>
  <li><strong>HuggingFace Spaces</strong> — Run n8n instances with 16GB RAM for free</li>
  <li><strong>Supabase</strong> — PostgreSQL + Row Level Security (500MB free)</li>
  <li><strong>Pinecone</strong> — Vector database with 100K vector free tier</li>
  <li><strong>Neo4j Aura</strong> — Knowledge graph with 200K nodes free</li>
  <li><strong>Total monthly cost: $0</strong></li>
</ul>

<h4>Evaluation Methodology</h4>
<ul>
  <li><strong>Phase 1:</strong> 200 hand-crafted questions — baseline validation</li>
  <li><strong>Phase 2:</strong> 500 questions — stress testing</li>
  <li><strong>Phase 3:</strong> 10,000 questions — statistical significance</li>
  <li><strong>Phase 4:</strong> 61,000 questions from 18 SOTA benchmarks (RAGBench, CRAG, SQuAD v2, MS MARCO)</li>
</ul>

<h3>Proven Results</h3>

<table>
  <tr><th>Pipeline</th><th>Phase 3 Accuracy (10K questions)</th></tr>
  <tr><td>Standard RAG</td><td><strong>87.5%</strong></td></tr>
  <tr><td>Graph RAG</td><td>40.9% (knowledge graph dependent)</td></tr>
  <tr><td>Quantitative RAG</td><td><strong>95.2%</strong></td></tr>
</table>

<h3>Who This Is For</h3>

<ul>
  <li><strong>Tech leads</strong> evaluating RAG architectures for their team</li>
  <li><strong>AI engineers</strong> who want production patterns, not toy examples</li>
  <li><strong>Startups</strong> that need enterprise-grade RAG on a zero budget</li>
  <li><strong>Consultants</strong> building RAG solutions for clients</li>
</ul>

<h3>What Makes This Different</h3>

<p>This isn't a course or tutorial. It's the actual architecture documentation and workflow files from a system built across <strong>78 sessions and 1,100+ commits</strong>. You get the blueprints, not the theory.</p>

<p><em>Build what took us 2 months — in a weekend.</em></p>
```

---

### Twitter/X Post (280 chars max)

```
4 RAG pipelines. 100% free infrastructure. 87.5% accuracy on 10K questions.

We open-sourced the architecture blueprint: n8n workflows, LiteLLM config, eval scripts, infra guide.

Built across 78 sessions. Yours for $197.

https://nomos42.gumroad.com/l/multi-rag-blueprint
```

(278 chars)

---

### Reddit Post — r/MachineLearning or r/LangChain

**Title:** After 78 sessions building multi-pipeline RAG on free infra (87.5% accuracy, 10K questions), we're releasing the full architecture blueprint

**Body:**

```
We spent 2 months building a multi-pipeline RAG system from scratch. Not a wrapper around LangChain — a full orchestration layer with 4 specialized pipelines, each optimized for different query types.

**Architecture highlights:**
- **Standard RAG** — HyDE + original embedding + BM25, merged via Reciprocal Rank Fusion
- **Graph RAG** — Neo4j knowledge graph with entity extraction and relationship traversal
- **Quantitative RAG** — Specialized for tables, financial data, SQL generation
- **Orchestrator** — Multi-hop query decomposition across pipelines

**Infrastructure (100% free tier):**
- n8n on HuggingFace Spaces (16GB RAM, 9 instances)
- Pinecone (100K vectors free)
- Neo4j Aura (200K nodes free)
- Supabase PostgreSQL (500MB free)
- LiteLLM proxy → Llama 3.3 70B, Gemma 3 27B, Qwen 235B (all free via OpenRouter)

**Results (Phase 3 — 10,000 questions):**
- Standard: 87.5%
- Quantitative: 95.2%
- Graph: 40.9% (limited by knowledge graph coverage)

**What's in the blueprint ($197):**
- Full architecture documentation
- n8n workflow JSON files (import and run)
- LiteLLM proxy configuration
- Evaluation scripts (Python)
- Infrastructure setup guide
- 78 sessions of debugging knowledge distilled

Link: https://nomos42.gumroad.com/l/multi-rag-blueprint

Ask me anything about the architecture or specific pipeline designs.
```

---

### JSON-LD Structured Data (Agentic Commerce)

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Multi-RAG Architecture Blueprint — 4 Pipelines, Free Infrastructure, Production-Ready",
  "description": "Complete architecture for a multi-pipeline RAG system: 4 specialized pipelines (Standard, Graph, Quantitative, Orchestrator), n8n workflow files, LiteLLM proxy config, evaluation methodology (200 to 61K questions), and infrastructure setup on 100% free tiers. 87.5% Standard accuracy, 95.2% Quantitative accuracy on 10K-question benchmarks.",
  "brand": {
    "@type": "Brand",
    "name": "Nomos AI"
  },
  "category": "Software > AI/ML > RAG Architecture",
  "sku": "NOMOS-RAG-ARCH-001",
  "image": "https://nomos42.gumroad.com/assets/multi-rag-blueprint-cover.png",
  "url": "https://nomos42.gumroad.com/l/multi-rag-blueprint",
  "offers": {
    "@type": "Offer",
    "url": "https://nomos42.gumroad.com/l/multi-rag-blueprint",
    "priceCurrency": "USD",
    "price": "197.00",
    "availability": "https://schema.org/InStock",
    "priceValidUntil": "2027-03-07",
    "seller": {
      "@type": "Organization",
      "name": "Nomos AI",
      "url": "https://nomos42.gumroad.com"
    }
  },
  "additionalProperty": [
    {
      "@type": "PropertyValue",
      "name": "format",
      "value": "PDF + n8n JSON workflows + Python scripts + Config files"
    },
    {
      "@type": "PropertyValue",
      "name": "pipelines_count",
      "value": "4"
    },
    {
      "@type": "PropertyValue",
      "name": "infrastructure_cost",
      "value": "$0/month (100% free tier)"
    },
    {
      "@type": "PropertyValue",
      "name": "benchmark_accuracy_standard",
      "value": "87.5%"
    },
    {
      "@type": "PropertyValue",
      "name": "benchmark_accuracy_quantitative",
      "value": "95.2%"
    },
    {
      "@type": "PropertyValue",
      "name": "benchmark_questions",
      "value": "10,000 (Phase 3)"
    },
    {
      "@type": "PropertyValue",
      "name": "engineering_sessions",
      "value": "78"
    },
    {
      "@type": "PropertyValue",
      "name": "ai_agent_compatible",
      "value": "true"
    }
  ],
  "potentialAction": {
    "@type": "BuyAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://nomos42.gumroad.com/l/multi-rag-blueprint",
      "actionPlatform": [
        "https://schema.org/DesktopWebPlatform",
        "https://schema.org/MobileWebPlatform"
      ]
    }
  },
  "audience": {
    "@type": "Audience",
    "audienceType": "Tech Leads, AI Engineers, Startups, Consultants"
  }
}
```

---

### Gumroad API: Update Product

```bash
curl -s https://api.gumroad.com/v2/products/PRODUCT_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -X PUT \
  -d "name=Multi-RAG Architecture Blueprint — 4 Pipelines, Free Infrastructure, Production-Ready" \
  -d "price=19700" \
  -d "description=Complete architecture blueprint for multi-pipeline RAG. 4 specialized pipelines, n8n workflows, LiteLLM config, eval scripts. 87.5%% Standard, 95.2%% Quantitative accuracy. 100%% free infrastructure." \
  -d "custom_permalink=multi-rag-blueprint" \
  -d "published=true"
```

---
---

## PRODUCT 4: Site Pro en 5 min

### Gumroad Fields

**Name:** Site Pro en 5 min — Landing Page Template + Deploy Guide

**Price:** $17

**Custom URL:** `site-pro-5min`
→ Full URL: https://nomos42.gumroad.com/l/site-pro-5min

**Summary (SEO):**
Go from zero to a professional landing page deployed on Vercel in under 5 minutes. Next.js 14 + Tailwind CSS template with animations, responsive design, and SEO meta tags pre-configured. Includes step-by-step deploy guide, AI-assisted copywriting prompts, and custom domain setup. Perfect for solopreneurs, freelancers, and anyone who needs a professional web presence fast. No backend needed. Free hosting on Vercel. Just clone, customize, deploy.

**Tags:** website, landing-page, Next.js, Tailwind, template, Vercel, deploy, solopreneur, freelancer, web-design, quick-start, startup, portfolio, no-code, AI

**Description (HTML for Gumroad):**

```html
<h2>Professional Landing Page — Live in 5 Minutes</h2>

<p>You need a website. You don't need to spend a week building one.</p>

<p>This template gets you from <strong>zero to deployed</strong> in under 5 minutes. Not "5 minutes if you already know React" — actual 5 minutes, with a step-by-step guide.</p>

<h3>What You Get</h3>

<ul>
  <li><strong>Next.js 14 + Tailwind CSS template</strong> — Clean, modern, responsive design</li>
  <li><strong>Smooth animations</strong> — Framer Motion transitions that feel premium</li>
  <li><strong>SEO pre-configured</strong> — Meta tags, OpenGraph, JSON-LD structured data, sitemap</li>
  <li><strong>One-click Vercel deploy</strong> — Free hosting, automatic HTTPS, global CDN</li>
  <li><strong>Custom domain guide</strong> — Connect your .com in 2 minutes</li>
  <li><strong>AI copywriting prompts</strong> — Generate your headline, CTA, and about section with Claude or ChatGPT</li>
</ul>

<h3>What It Looks Like</h3>

<ul>
  <li>Hero section with headline + CTA button</li>
  <li>Features/benefits grid (3 or 4 columns)</li>
  <li>Social proof / testimonials section</li>
  <li>Pricing table (optional)</li>
  <li>Footer with links + newsletter signup</li>
  <li>Mobile-first responsive design</li>
</ul>

<h3>The 5-Minute Process</h3>

<ol>
  <li><strong>Clone</strong> — One command: <code>npx create-next-app --example</code></li>
  <li><strong>Customize</strong> — Edit 1 config file: your name, headline, colors</li>
  <li><strong>Deploy</strong> — Push to GitHub, connect Vercel, live in 60 seconds</li>
  <li><strong>Domain</strong> — (Optional) Point your domain in Vercel settings</li>
  <li><strong>Done</strong> — Share your URL</li>
</ol>

<h3>Who This Is For</h3>

<ul>
  <li><strong>Solopreneurs</strong> who need a landing page today, not next month</li>
  <li><strong>Freelancers</strong> who want a portfolio without the overhead</li>
  <li><strong>Indie hackers</strong> launching a product and need a sales page fast</li>
  <li><strong>Anyone</strong> tired of Wix/Squarespace monthly fees ($0/month on Vercel)</li>
</ul>

<h3>Tech Stack</h3>

<ul>
  <li>Next.js 14 (React framework)</li>
  <li>Tailwind CSS (utility-first styling)</li>
  <li>Framer Motion (animations)</li>
  <li>Vercel (hosting — free tier)</li>
  <li>No backend, no database, no monthly costs</li>
</ul>

<p><em>Stop paying $15/month for a website builder. Own your site. Deploy it free. Keep it forever.</em></p>
```

---

### Twitter/X Post (280 chars max)

```
Professional landing page in 5 minutes. For real.

Next.js + Tailwind template. One config file to customize. Free Vercel hosting. No monthly fees.

Clone. Edit. Deploy. Done.

$17: https://nomos42.gumroad.com/l/site-pro-5min
```

(228 chars)

---

### Reddit Post — r/SideProject or r/webdev

**Title:** Made a Next.js landing page template that actually deploys in 5 minutes — $0/month hosting on Vercel

**Body:**

```
I keep seeing people spend weeks on landing pages or paying $15-30/month for Squarespace/Wix. Built a template that solves this:

**What it is:**
- Next.js 14 + Tailwind CSS landing page template
- Framer Motion animations (smooth, not cheesy)
- SEO pre-configured (meta tags, OpenGraph, JSON-LD, sitemap)
- Mobile-first responsive design

**The actual 5-minute process:**
1. Clone the repo
2. Edit ONE config file (your name, headline, colors, CTA)
3. Push to GitHub → connect Vercel → live
4. (Optional) Point your custom domain

**What's included beyond the template:**
- AI copywriting prompts (use Claude/ChatGPT to generate your headline and copy)
- Custom domain setup guide
- Vercel deploy walkthrough with screenshots

**Cost:** $17 one-time. $0/month hosting (Vercel free tier).

Compare that to Squarespace at $16/month ($192/year) for something you don't even own.

https://nomos42.gumroad.com/l/site-pro-5min

Built this as part of a larger project where we ship production AI systems. Figured the website template we use internally was worth packaging.
```

---

### JSON-LD Structured Data (Agentic Commerce)

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Site Pro en 5 min — Landing Page Template + Deploy Guide",
  "description": "Professional landing page from zero to deployed in under 5 minutes. Next.js 14 + Tailwind CSS template with animations, SEO pre-configured, and free Vercel hosting. Includes AI copywriting prompts and custom domain guide. No monthly fees.",
  "brand": {
    "@type": "Brand",
    "name": "Nomos AI"
  },
  "category": "Software > Web Development > Templates",
  "sku": "NOMOS-SITE-5MIN-001",
  "image": "https://nomos42.gumroad.com/assets/site-pro-5min-cover.png",
  "url": "https://nomos42.gumroad.com/l/site-pro-5min",
  "offers": {
    "@type": "Offer",
    "url": "https://nomos42.gumroad.com/l/site-pro-5min",
    "priceCurrency": "USD",
    "price": "17.00",
    "availability": "https://schema.org/InStock",
    "priceValidUntil": "2027-03-07",
    "seller": {
      "@type": "Organization",
      "name": "Nomos AI",
      "url": "https://nomos42.gumroad.com"
    }
  },
  "additionalProperty": [
    {
      "@type": "PropertyValue",
      "name": "format",
      "value": "Git repository + Guide PDF"
    },
    {
      "@type": "PropertyValue",
      "name": "tech_stack",
      "value": "Next.js 14, Tailwind CSS, Framer Motion, Vercel"
    },
    {
      "@type": "PropertyValue",
      "name": "hosting_cost",
      "value": "$0/month (Vercel free tier)"
    },
    {
      "@type": "PropertyValue",
      "name": "setup_time",
      "value": "5 minutes"
    },
    {
      "@type": "PropertyValue",
      "name": "ai_agent_compatible",
      "value": "true"
    }
  ],
  "potentialAction": {
    "@type": "BuyAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://nomos42.gumroad.com/l/site-pro-5min",
      "actionPlatform": [
        "https://schema.org/DesktopWebPlatform",
        "https://schema.org/MobileWebPlatform"
      ]
    }
  },
  "audience": {
    "@type": "Audience",
    "audienceType": "Solopreneurs, Freelancers, Indie Hackers, Startups"
  }
}
```

---

### Gumroad API: Update Product

```bash
curl -s https://api.gumroad.com/v2/products/PRODUCT_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -X PUT \
  -d "name=Site Pro en 5 min — Landing Page Template + Deploy Guide" \
  -d "price=1700" \
  -d "description=Professional landing page deployed in 5 minutes. Next.js 14 + Tailwind CSS. Free Vercel hosting. SEO pre-configured. AI copywriting prompts included." \
  -d "custom_permalink=site-pro-5min" \
  -d "published=true"
```

---
---

## COMBINED API WORKFLOW

After creating all 4 products manually on Gumroad, run this script to retrieve their IDs and update them programmatically:

```bash
#!/bin/bash
# gumroad-update-all.sh
# Run after creating products manually on https://gumroad.com/products

ACCESS_TOKEN="YOUR_ACCESS_TOKEN"
BASE="https://api.gumroad.com/v2"

echo "=== Listing all products ==="
curl -s "$BASE/products" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -X GET | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('success'):
    for p in data['products']:
        print(f\"  ID: {p['id']}  |  Name: {p['name']}  |  Price: {p.get('price', 'N/A')}  |  Published: {p.get('published', 'N/A')}\")
else:
    print('Error:', data)
"

echo ""
echo "=== Copy the IDs above and replace PRODUCT_ID in the curl commands ==="
echo ""
echo "Products to update:"
echo "  1. RAG Debug Playbook (\$47)"
echo "  2. AI Agent Context Kit (\$27)"
echo "  3. Multi-RAG Architecture Blueprint (\$197)"
echo "  4. Site Pro en 5 min (\$17)"
```

### Enable All Products

```bash
# After updating, enable all products
for PRODUCT_ID in "ID1" "ID2" "ID3" "ID4"; do
  curl -s "$BASE/products/$PRODUCT_ID/enable" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -X PUT
  echo " -> Enabled $PRODUCT_ID"
done
```

---

## COMBINED JSON-LD (All Products — for website embedding)

Embed this in the `<head>` of your landing page or storefront for AI agent discoverability:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Nomos AI — Digital Products",
  "description": "Production-grade RAG tools, architecture blueprints, and web development templates from Nomos AI.",
  "url": "https://nomos42.gumroad.com",
  "numberOfItems": 4,
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "item": {
        "@type": "Product",
        "name": "RAG Debug Playbook",
        "url": "https://nomos42.gumroad.com/l/rag-debug-playbook",
        "offers": { "@type": "Offer", "price": "47.00", "priceCurrency": "USD", "availability": "https://schema.org/InStock" }
      }
    },
    {
      "@type": "ListItem",
      "position": 2,
      "item": {
        "@type": "Product",
        "name": "AI Agent Context Kit",
        "url": "https://nomos42.gumroad.com/l/ai-agent-context-kit",
        "offers": { "@type": "Offer", "price": "27.00", "priceCurrency": "USD", "availability": "https://schema.org/InStock" }
      }
    },
    {
      "@type": "ListItem",
      "position": 3,
      "item": {
        "@type": "Product",
        "name": "Multi-RAG Architecture Blueprint",
        "url": "https://nomos42.gumroad.com/l/multi-rag-blueprint",
        "offers": { "@type": "Offer", "price": "197.00", "priceCurrency": "USD", "availability": "https://schema.org/InStock" }
      }
    },
    {
      "@type": "ListItem",
      "position": 4,
      "item": {
        "@type": "Product",
        "name": "Site Pro en 5 min",
        "url": "https://nomos42.gumroad.com/l/site-pro-5min",
        "offers": { "@type": "Offer", "price": "17.00", "priceCurrency": "USD", "availability": "https://schema.org/InStock" }
      }
    }
  ]
}
</script>
```

---

## NOTES ON GUMROAD PRICING

- Gumroad prices are in **cents** via API (e.g., `4700` = $47.00)
- Gumroad takes a **10% flat fee** on each sale (no monthly subscription)
- Payment processing fees apply on top (~2.9% + $0.30 for US cards)
- Net revenue per sale:
  - $47 product → ~$38.77 net
  - $27 product → ~$21.52 net
  - $197 product → ~$174.43 net
  - $17 product → ~$12.81 net

## GUMROAD SEO BEST PRACTICES

1. **Product cover image** — Products with covers convert at 2x the rate of those without
2. **Tags** — Add tags (found at bottom of Share page) to appear in Gumroad Discover
3. **Category** — Set your account category in Settings to qualify for Gumroad Discover
4. **Custom URL** — Use descriptive permalinks (e.g., `rag-debug-playbook` not `abc123`)
5. **Description** — First 160 chars appear in search results; front-load value proposition
6. **Price psychology** — Odd pricing ($47 not $50) signals considered pricing

Sources:
- [Gumroad API](https://gumroad.com/api)
- [Gumroad Help — Create Application for API](https://gumroad.com/help/article/280-create-application-api)
- [Gumroad Help — Adding a Product](https://help.gumroad.com/article/149-adding-a-product)
- [Gumroad Help — Gumroad Discover](https://gumroad.com/help/article/79-gumroad-discover)
- [Gumroad SEO Tips](https://gumroad.gumroad.com/p/5-seo-tips-to-optimize-your-gumroad-sales-page)
- [JSON-LD Product Schema](https://jsonld.com/product/)
- [Schema.org Product Type](https://schema.org/Product)
- [JSON-LD Masterclass for AI Agents](https://www.jasminedirectory.com/blog/json-ld-masterclass-implementing-schema-for-ai-agents/)
- [Rollout — Gumroad API Integration Guide](https://rollout.com/integration-guides/gumroad/sdk/step-by-step-guide-to-building-a-gumroad-api-integration-in-python)
