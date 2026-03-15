# Product Hunt Launch — Ready to Submit

> URL: https://www.producthunt.com/posts/new
> Date: 2026-03-09 (schedule for Tuesday/Wednesday for best results)

---

## Product Name

Multi-RAG Orchestrator

## Tagline (60 chars max)

4 specialized RAG pipelines. 87.5% accuracy. $0/month to run.

## Website URL

https://whop.com/nomosai

## Description (short, for the card)

A multi-pipeline RAG system that routes queries to specialized pipelines — Standard (vector search), Graph (Neo4j knowledge graph), and Quantitative (LLM-generated SQL). Tested on 10,000+ questions. Runs entirely on free-tier infrastructure.

## Maker Comment (first comment after launch)

Hi Product Hunt! I'm Alexis, and I've spent 90+ engineering sessions building this system.

The core insight: not all questions should go through the same RAG pipeline. "What is the company's revenue?" needs SQL, not vector search. "Who sits on the board?" needs a knowledge graph, not text retrieval.

So I built 3 specialized pipelines, each optimized for different query types:

- **Standard RAG** (87.5% accuracy): HyDE + Reciprocal Rank Fusion + reranking against Pinecone
- **Graph RAG**: Neo4j with 87K nodes for entity relationships
- **Quantitative RAG** (95.2% accuracy): LLM-generated SQL against PostgreSQL

The entire stack runs on free-tier services: Llama 3.3 70B + Gemma 27B (free via OpenRouter/Groq), Pinecone, Neo4j Aura, Supabase, n8n on HuggingFace Spaces. Monthly cost: literally $0.

Along the way, I documented 79 production fixes — the failures that no tutorial or documentation warns you about. Things like Pinecone silently dropping vectors when metadata exceeds 40KB, or n8n disabled nodes still firing HTTP requests.

I've packaged everything into products you can actually use:
- Import the n8n workflow JSONs and run them
- Drop the debug playbook .md into your project as an AI assistant context file
- Use the 61K-question benchmark dataset to evaluate your own system

Happy to answer any questions about the architecture or specific failure modes!

## Topics

- Artificial Intelligence
- Developer Tools
- Open Source
- SaaS
- Productivity

## Gallery Images (descriptions for what to create)

**Image 1 — Hero:** Architecture diagram showing the 3 pipelines with accuracy numbers. Clean, dark background, colored pipeline cards.

**Image 2 — Results:** Table showing Phase 1 vs Phase 3 accuracy numbers. Standard 85.5% -> 87.5%, Graph 78% -> 40.9%, Quant 92% -> 95.2%.

**Image 3 — Stack:** Infrastructure diagram: n8n + Pinecone + Neo4j + Supabase + LiteLLM. All logos. "$0/month" label.

**Image 4 — Products:** Product catalog grid. 14 products from $27 to $497.

**Image 5 — Debug Playbook:** Screenshot of the playbook structure: categories, fix format (symptom/cause/solution/prevention).

## Categories to Submit To

- AI Tools
- Developer Tools
- Productivity Tools

## Launch Timing

- **Best:** Tuesday or Wednesday, 12:01 AM Pacific (products go live at midnight PT)
- **Prep:** Get 5-10 friends/colleagues to upvote in the first 2 hours
- **Thread:** Be online to respond to every comment for the first 4-6 hours
- **Social:** Cross-post to Twitter, LinkedIn, Reddit with "We just launched on Product Hunt" message

## Upvote Strategy

1. Post a teaser on Twitter/LinkedIn 24 hours before: "Launching on Product Hunt tomorrow. 90+ sessions of production RAG debugging in one toolkit."
2. Send personal messages to contacts in AI/ML. Not "please upvote" but "we're launching this, would love your feedback."
3. Post in relevant Slack/Discord communities (n8n Discord 74K members, AI/ML Discords).
4. Update Reddit posts with "Edit: We also just launched on Product Hunt [link]"

## Alternative: Product Hunt Discussion (lower effort)

If a full product launch feels premature, post a Discussion instead:

**Title:** What's the hardest production RAG bug you've encountered?

**Body:** I've documented 79 production RAG fixes over 90+ sessions. The sneakiest ones are silent failures: Pinecone dropping vectors when metadata is too large (no error), Supabase's transaction pooler port dropping inserts (no error), n8n disabled nodes still executing HTTP calls.

I'm curious what patterns others have seen. What's the bug that cost you the most time?

(Link to products in profile, not in the post itself.)
