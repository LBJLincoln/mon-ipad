# AI Agent Marketplace Submissions — Status Tracker

> Generated: 2026-03-08 | Updated by: Claude Code Session 87

---

## Summary

| # | Platform | Type | Cost | Status | Action Needed |
|---|----------|------|------|--------|---------------|
| 1 | ClawdHub (OpenClaw) | Skill Registry | Free | READY TO PUBLISH | Get token from clawhub.ai web UI |
| 2 | AgentX.Market | Marketplace | Free | PENDING | Register at agentx.market/register |
| 3 | AI Agent Store | Directory | Free | PENDING | Register at aiagentstore.ai/register |
| 4 | AI Agents Directory | Directory | Free | PENDING | Submit at aiagentsdirectory.com/submit-agent |
| 5 | AI Agents List | Directory | Free | PENDING | Submit at aiagentslist.com/submit |
| 6 | Product Hunt | Launch | Free | PENDING | Schedule launch at producthunt.com |
| 7 | There's An AI For That | Directory | Free (monthly X thread) | PENDING | Follow @theresanaiforthat, submit in free thread |
| 8 | Futurepedia | Directory | $247+ | SKIP | Too expensive for now |
| 28 | LobeChat Agents | Agent Registry | Free | SUBMITTED | PR #1507 at lobehub/lobe-chat-agents |
| 9 | AI Tools Directory | Directory | Free? | PENDING | Submit at aitoolsdirectory.com/submit-tool |
| 10 | SubmitYourAITool.com | Directory | Free | PENDING | Submit at submityouraitool.com |
| 11 | Agent.ai | Network | Free | PENDING | Explore builder network at agent.ai |
| 12 | DropYourAI | Directory | Free/Paid | PENDING | Submit at dropyourai.com/submit-tool |
| 13 | AI Tools Inc | Directory | Free | PENDING | Submit at aitools.inc/submit |
| 14 | Insidr.ai | Directory | Free | PENDING | Submit at insidr.ai/submit-tools |
| 15 | OpenTools.ai | Directory | Free | PENDING | Submit at opentools.ai |
| 16 | AI Pedia Hub | Directory | Free | PENDING | Submit at aipediahub.com |
| 17 | FindMyAITool | Directory | Free/Paid | PENDING | Submit at findmyaitool.com/submit-tool |
| 18 | All Things AI | Directory | Free | PENDING | Submit at allthingsai.com |
| 19 | FutureTools.io | Directory | Free | PENDING | Submit at futuretools.io |
| 20 | AI Agents Base | Directory | Free | PENDING | Submit at aiagentsbase.com |
| 21 | AI Agents Verse | Directory | Free | PENDING | Submit at aiagentsverse.com |
| 22 | AgentHunter.io | Directory | Free | PENDING | Submit at agenthunter.io |
| 23 | FindYourAgent.ai | Directory | Free | PENDING | Submit at findyouragent.ai |
| 24 | TrillionAgent.com | Marketplace | Free | PENDING | Submit at trillionagent.com |
| 25 | CogList | Directory | Free | PENDING | Submit at coglist.com |
| 26 | AI Agents Live | Directory | Free | PENDING | Submit at aiagentslive.com |
| 27 | Add AI Directory | Directory | Free | PENDING | Submit at addaidirectory.com |

---

## 1. ClawdHub (OpenClaw Skill Registry)

### Status: SKILL FILES READY, NEED AUTH TOKEN

### What it is
ClawdHub is the official skill registry for OpenClaw (formerly Moltbot). 13,729+ skills hosted. Free, public registry.

### Skill folders created
```
monetisation/clawhub-skills/
  nomos-rag-query/SKILL.md
  nomos-eval-framework/SKILL.md
  nomos-debug-assistant/SKILL.md
```

### How to publish (manual steps needed)

1. **Get a ClawdHub token** (MUST be done in browser):
   ```
   1. Go to https://clawhub.ai
   2. Sign in with GitHub (account must be >=1 week old)
   3. Go to Settings → API Tokens
   4. Generate a CLI token
   5. Copy the token (starts with clh_)
   ```

2. **Set the token on the VM**:
   ```bash
   export CLAWHUB_TOKEN="clh_your_token_here"
   # Or save to .env.local:
   echo 'CLAWHUB_TOKEN=clh_your_token_here' >> ~/mon-ipad/.env.local
   ```

3. **Publish all 3 skills**:
   ```bash
   cd ~/mon-ipad
   clawhub publish monetisation/clawhub-skills/nomos-rag-query \
     --slug nomos-rag-query \
     --name "Nomos RAG Query — Multi-Pipeline Retrieval" \
     --version 1.0.0 \
     --tags "latest,rag,retrieval,vector-search,graph-rag,sql-rag"

   clawhub publish monetisation/clawhub-skills/nomos-eval-framework \
     --slug nomos-eval-framework \
     --name "Nomos RAG Eval — 61K-Question Benchmark System" \
     --version 1.0.0 \
     --tags "latest,eval,benchmark,testing,rag-eval"

   clawhub publish monetisation/clawhub-skills/nomos-debug-assistant \
     --slug nomos-debug-assistant \
     --name "Nomos RAG Debug — 90+ Fix Patterns" \
     --version 1.0.0 \
     --tags "latest,debug,troubleshooting,n8n,self-healing"
   ```

4. **Verify**:
   ```bash
   clawhub search nomos
   ```

### Known issue
- `clawhub login --token` has a known bug returning "Unauthorized" on headless servers
- Workaround: generate token from web UI and set as env var

---

## 2. AgentX.Market

### Status: NEED MANUAL FORM SUBMISSION

### How to submit
1. Go to https://agentx.market/register
2. Fill out registration form with:
   - Agent name: **Nomos Multi-RAG Orchestrator**
   - Description: Production multi-pipeline RAG system with 3 specialized pipelines (Standard vector search 87.5%, Graph entity traversal, Quantitative SQL 95.2%). Free inference. No API key needed.
   - Website: https://lbjlincoln.github.io/rag-dashboard/store.html
   - API endpoint: https://lbjlincoln-nomos-rag-engine.hf.space
   - Category: Knowledge Retrieval / AI Agent
   - Pricing: Free tier (10 req/min) + paid products ($27-$497)
3. Wait for approval

### Features include
- Built-in Stripe billing
- Health monitoring
- Usage analytics
- Auto-scaling infrastructure

---

## 3. AI Agent Store (aiagentstore.ai)

### Status: NEED MANUAL FORM SUBMISSION

### How to submit
1. Go to https://aiagentstore.ai/register
2. Choose "Submit AI Agent"
3. Create account with email/password
4. Fill in agent details:
   - Name: Nomos Multi-RAG Orchestrator
   - Description: (use listing from agent-marketplace-listings.md section 3A)
   - URL: https://lbjlincoln.github.io/rag-dashboard/store.html
   - Category: Knowledge Retrieval & QA
   - Tags: rag, retrieval, vector-search, graph-rag, sql-rag, free-llm
   - Pricing: Free tier + paid ($27-$497)

---

## 4. AI Agents Directory (aiagentsdirectory.com)

### Status: NEED MANUAL FORM SUBMISSION

### How to submit
1. Go to https://aiagentsdirectory.com/submit-agent
2. Fill in:
   - Agent name: Nomos Multi-RAG Orchestrator
   - Tagline: Production RAG system — 3 pipelines, 87.5% accuracy, $0 inference cost
   - Description: Production multi-pipeline RAG system with Standard (vector search, 87.5% accuracy), Graph (Neo4j entity traversal), and Quantitative (SQL, 95.2% accuracy) pipelines. Free LLM inference via OpenRouter. Self-hosted on Hugging Face Spaces.
   - URL: https://lbjlincoln.github.io/rag-dashboard/store.html
   - Category: Knowledge Retrieval
   - Pricing: Free tier available
3. Contact: hello@aiagentsdirectory.com for questions

---

## 5. AI Agents List (aiagentslist.com)

### How to submit
1. Go to https://aiagentslist.com/submit
2. Fill in agent details (same as #4 above)

---

## 6. Product Hunt

### How to submit
1. Go to https://www.producthunt.com
2. Click "Submit" / post a product
3. Product name: Nomos Multi-RAG Orchestrator
4. Tagline: 3 RAG pipelines, 87.5% accuracy, $0 per query — production-ready
5. Description: (use full description from listings)
6. Link: https://lbjlincoln.github.io/rag-dashboard/store.html
7. **Best practice**: Schedule launch for a Tuesday/Wednesday for max visibility
8. Add to categories: AI Agents, Developer Tools, Open Source

---

## 7-27. Bulk Directory Submissions

### Standard submission data for all directories:

```
Name: Nomos Multi-RAG Orchestrator
Tagline: Production RAG system — 3 pipelines, 87.5% accuracy, $0 inference
URL: https://lbjlincoln.github.io/rag-dashboard/store.html
Demo: https://lbjlincoln-nomos-rag-engine.hf.space/healthz
Category: Knowledge Retrieval / RAG / AI Agent
Pricing: Free (10 req/min, 100 req/day) + paid tiers ($27-$497)
Contact: alexis.moret6@outlook.fr

Description (short):
Query a production RAG system with 3 specialized pipelines. Standard pipeline searches 46K+ vector embeddings (87.5% accuracy). Graph pipeline traverses 79K+ Neo4j nodes. Quantitative pipeline generates SQL over 40 PostgreSQL tables (95.2% accuracy). Free LLM inference. No API key required.

Description (long):
Nomos Multi-RAG Orchestrator is a production-grade Retrieval-Augmented Generation system featuring three specialized pipelines:

1. Standard Pipeline — Vector similarity search over 46,263 Jina v3 embeddings in Pinecone. 87.5% accuracy on 10,917 evaluation questions. Best for factual questions.

2. Graph Pipeline — Entity traversal over 79,451 nodes and 219,414 relationships in Neo4j. Best for relationship and connection questions.

3. Quantitative Pipeline — Natural language to SQL generation over 40 Supabase PostgreSQL tables. 95.2% accuracy on 3,550 questions. Best for numerical comparisons and rankings.

Built with n8n workflow orchestration on 9 Hugging Face Spaces instances, free LLM inference via OpenRouter (Llama 3.3 70B, Gemma 27B), and self-hosted Jina v3 embeddings. Evaluated against 61,661 questions from 18 SOTA benchmarks (HotpotQA, TriviaQA, NQ, MMLU, etc.).

No API key required for the free tier. Production-tested across 76+ debugging sessions with 90+ documented fixes.

Tags: rag, retrieval-augmented-generation, vector-search, graph-rag, sql-rag, neo4j, pinecone, supabase, n8n, free-llm, hugging-face, ai-agent, knowledge-retrieval
```

### Free directories to submit to (in priority order):

| # | URL | Notes |
|---|-----|-------|
| 1 | submityouraitool.com | Free, manual review |
| 2 | aiagentsdirectory.com/submit-agent | 2,218 agents listed |
| 3 | aiagentslist.com/submit | 600+ agents |
| 4 | aiagentstore.ai/register | Directory + marketplace |
| 5 | agentx.market/register | Marketplace with Stripe |
| 6 | aitoolsdirectory.com/submit-tool | General AI tools |
| 7 | aitools.inc/submit | General AI tools |
| 8 | insidr.ai/submit-tools | AI tools |
| 9 | findmyaitool.com/submit-tool | AI tools |
| 10 | dropyourai.com/submit-tool | AI tools |
| 11 | aipediahub.com | Large directory |
| 12 | allthingsai.com | Curated |
| 13 | futuretools.io | Popular directory |
| 14 | aiagentsbase.com | Agent-specific |
| 15 | aiagentsverse.com | Agent-specific |
| 16 | agenthunter.io | Agent-specific |
| 17 | findyouragent.ai | Agent-specific |
| 18 | trillionagent.com | Marketplace |
| 19 | coglist.com | Indie hackers |
| 20 | aiagentslive.com | Discovery platform |
| 21 | addaidirectory.com | General directory |
| 22 | opentools.ai | AI tools |
| 23 | agent.ai | Professional network |
| 24 | producthunt.com | Launch platform |

---

## Product-Specific Submissions

For individual products, also submit:

### Claude Code Skills ($47)
- Submit to ClawdHub as skill
- Submit to claudepro.directory (Claude-specific directory)
- Submit to EveryDev.ai (developer tools)

### n8n Workflows ($197)
- Submit to n8n community workflows
- Submit to automation directories

### Debug Playbook ($47)
- Submit to developer tool directories
- Submit to DevOps tool lists

---

## Paid Directories (For Later)

| Platform | Cost | ROI Potential |
|----------|------|--------------|
| Futurepedia.io | $497 (verified) | High traffic, 400K monthly |
| There's An AI For That | Varies | Highest AI directory traffic |
| Product Hunt (featured) | Free but competitive | Huge launch traffic |
| Google Cloud AI Agent Marketplace | Enterprise | Long sales cycle |
| AWS Marketplace | Enterprise | Long sales cycle |
