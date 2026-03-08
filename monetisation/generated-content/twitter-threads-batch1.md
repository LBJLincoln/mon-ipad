# Twitter/X Threads — Batch 1 (Ready to Post)

> Generated: 2026-03-08
> Author: @alexismoret (or relevant handle)
> Store: https://lbjlincoln.github.io/rag-dashboard/store.html

---

## THREAD 1 — "61K questions, 4 pipelines" (MAIN THREAD)

**1/12**
We tested 61,661 RAG questions across 4 different pipeline architectures.

86 engineering sessions. 1,100+ commits. $0/month infrastructure.

Here's what actually works in production RAG (thread) 🧵

**2/12**
Pipeline 1: Standard RAG → 87.5% accuracy on 10K questions

The secret sauce:
- Dual retrieval: HyDE + original query
- Reciprocal Rank Fusion to merge results
- BM25 keyword search in parallel
- Reranking before LLM generation

Single embedding search caps around 72%.

**3/12**
Pipeline 2: Graph RAG → 40.9% overall, but 90%+ on relationship queries

Neo4j with 79K nodes and 219K relationships.

Graph RAG is NOT a replacement for vector search. It's a complement. Use it for "who is connected to whom" — not "what is X?"

**4/12**
Pipeline 3: Quantitative RAG → 95.2% on financial questions

This one surprised us. SQL generation against PostgreSQL with structured financial data.

The game-changer: ILIKE fuzzy matching instead of exact WHERE clauses. One change = +12% accuracy.

**5/12**
Pipeline 4: Orchestrator → ON HOLD

Multi-hop query decomposition hit an architectural wall: n8n's executeWorkflow + respondToWebhook conflict.

Sub-workflows send responses to the client but return nothing to the parent.

Lesson: know your framework's limits before building.

**6/12**
The LLM stack (all free):

- meta-llama/llama-3.3-70b-instruct:free → SQL, intent, planning, QA
- google/gemma-3-27b-it:free → fast tasks
- arcee-ai/trinity-large-preview:free → extraction, summaries
- LiteLLM proxy for unified API

$0/month for the entire LLM layer.

**7/12**
Infrastructure (all free tier):

- 9 n8n instances on HuggingFace Spaces
- Pinecone: 77K+ vectors
- Neo4j Aura: 79K nodes
- Supabase: 40 tables
- Self-hosted embeddings (replaced Jina after 2 API keys exhausted)
- Google Cloud VM

Total monthly cost: $0.

**8/12**
The 5 most expensive production bugs:

1. n8n disabled nodes still fire HTTP requests
2. HF Spaces restart randomly (no persistent storage)
3. Pinecone metadata >40KB silently fails
4. Supabase port 6543 silently drops inserts
5. LLMs format SQL output differently per model

Each one cost 2-4 hours to debug.

**9/12**
What I wish I'd known on day 1:

- Start with 200 questions, not 10K
- Phase-gate your evaluation: 200 → 1K → 10K → 61K
- One fix per iteration. Never change two things at once.
- Commit every 15-20 minutes. Codespaces are ephemeral.

**10/12**
I packaged everything into tools you can actually use:

- 10 n8n workflow JSONs (import and run)
- 79+ fix debug playbook
- Architecture blueprint
- Evaluation framework
- 17 Claude Code custom skills

Full catalog: https://lbjlincoln.github.io/rag-dashboard/store.html

**11/12**
The MEGA BUNDLE ($497) includes everything — $1,400+ of tools for the price of one.

Or start small:
- Debug Playbook: $47
- Agent Context Kit: $27
- Claude Code Skills: $47

https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d

**12/12**
If you're building RAG in production, I've probably hit the bug you'll hit next.

Save yourself 80+ sessions of debugging.

Like/RT if this thread was useful — I'll share more production RAG insights.

---

## THREAD 2 — "Claude Code skills" (DEVELOPER NICHE)

**1/7**
I built 17 custom Claude Code skills that make my AI assistant 3x more productive.

Here's the system (thread) 🧵

**2/7**
The key insight: Claude Code can load custom .md files from `.claude/commands/` as slash commands.

Each file is a structured prompt that gives Claude domain expertise.

/session-start loads project state
/eval runs RAG evaluation
/self-heal fixes broken pipelines

**3/7**
My favorites:

/monitor → checks 9 services (n8n, Pinecone, Neo4j, Supabase, LiteLLM, HF Spaces, embeddings)

/cross-repo-sync → synchronizes 7 repos in one command

/regression-check → catches accuracy drops before they go live

**4/7**
The CLAUDE.md file is the foundation. It's a 250-line project manual that Claude loads at startup.

It contains:
- Infrastructure config
- Pipeline status
- Workflow IDs
- Debug rules
- Commit conventions

No more "let me explain the project."

**5/7**
Combined with auto-memory (persistent across sessions), Claude maintains context over 80+ sessions.

It remembers:
- Which n8n login method works (Python, not curl)
- Which Supabase port to use (5432, not 6543)
- Which workflow IDs are active

**6/7**
I packaged all 17 skills + the CLAUDE.md context system.

Claude Code Skill Pack ($47): https://buy.stripe.com/7sY8wIge64D93f53JX5J609

Agent Context Kit ($27): https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601

Full catalog: https://lbjlincoln.github.io/rag-dashboard/store.html

**7/7**
These work for ANY project — not just RAG.

Adapt the skill files for your domain. The pattern is universal: structured prompts → domain expertise → faster shipping.

Like/RT if you use Claude Code and want to level up.

---

## THREAD 3 — "Self-hosted embeddings" (COST-SAVING NICHE)

**1/5**
We exhausted 2 Jina API keys in a month.

So we built a self-hosted embeddings service on HuggingFace Spaces.

Cost: $0/month. Compatible with Jina API. Here's how (thread) 🧵

**2/5**
The service:
- Gradio app on HF Spaces (cpu-basic, free)
- Jina-compatible /v1/embeddings endpoint
- TEI-compatible /embed endpoint
- Lazy model loading (avoids startup timeout)
- Health monitoring via /health

Drop-in replacement for Jina/OpenAI embeddings API.

**3/5**
Key technical details:

- PyTorch 2.4+ breaks with `all_tied_weights_keys` — monkey-patch nn.Module.__init__
- cpu-basic can handle 2 texts per batch (16 overloads it)
- Rate: ~6.3 contexts/min — enough for ingestion, not real-time
- Lazy load avoids HF's 5-min startup timeout

**4/5**
We updated all 7 n8n workflows to use self-hosted embeddings.

Script: one Python file swaps all Jina URLs + removes auth headers.

Standard pipeline: 3/3 PASS confirmed after swap.

**5/5**
I packaged the service + deployment guide:

Self-Hosted Embeddings Service ($67): https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c

Stop paying per-token for embeddings. Deploy in 10 minutes.

---

## STANDALONE TWEETS (quick-fire)

**Tweet A:**
RAG accuracy tip that took me 3 sessions to discover:

n8n disabled nodes still fire HTTP requests.

The data passes through but the HTTP Request node STILL executes.

This silently corrupts your pipeline responses.

Fix: delete disabled nodes, don't just toggle them off.

**Tweet B:**
The #1 mistake in RAG evaluation:

Testing with <100 questions and declaring victory.

Phase-gate your eval:
- 200 questions → smoke test
- 1K → pattern validation
- 10K → statistical significance
- 61K → production confidence

We went from "90% accuracy!" to 87.5% when we scaled. That 2.5% gap was hiding real bugs.

**Tweet C:**
Free-tier RAG stack that handles 61K+ questions:

Groq (free) + OpenRouter (free) + HF Spaces (free) + Pinecone (free) + Neo4j Aura (free) + Supabase (free)

Monthly cost: $0
Questions evaluated: 61,661
Max accuracy: 95.2%

Full architecture: https://lbjlincoln.github.io/rag-dashboard/store.html

**Tweet D:**
Unpopular opinion: LangChain tutorials are actively harmful.

They teach you that RAG is 20 lines of code.

Then you deploy and everything breaks.

Production RAG is:
- Multi-pipeline routing
- Phase-gated evaluation
- Self-hosted embeddings
- 79+ documented failure modes

I wrote the guide: https://buy.stripe.com/00w7sEd1U2v14j92FT5J600
