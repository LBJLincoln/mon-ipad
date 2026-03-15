# Show HN Post — Ready to Submit

> URL: https://news.ycombinator.com/submit
> Date: 2026-03-09

---

## Title

Show HN: 79 Production RAG Fixes from 90+ Debugging Sessions (87.5% on 10K Questions)

## URL

https://whop.com/nomosai

## Text (Show HN body)

After 90+ engineering sessions building a multi-pipeline RAG system, I compiled every production failure into a structured debug playbook.

The system routes queries to 3 specialized pipelines:
- Standard RAG (87.5% on 10K questions) — HyDE + Reciprocal Rank Fusion + reranking
- Graph RAG — Neo4j with 87K nodes for entity relationships
- Quantitative RAG (95.2%) — LLM-generated SQL against PostgreSQL

Everything runs on free-tier infrastructure: Llama 3.3 70B + Gemma 27B (OpenRouter/Groq), Pinecone, Neo4j Aura, Supabase, n8n on HuggingFace Spaces. $0/month.

The playbook covers failures documentation never mentions:

- n8n disabled nodes still fire HTTP requests (data passes through AND the call executes)
- Supabase port 5432 vs 6543: one works, the other silently drops inserts
- Pinecone metadata >40KB causes silent upsert failures
- HF Spaces lose all state on restart (no persistent storage)
- LLMs format SQL output inconsistently even with the same prompt (multi-strategy extraction required)
- The 3-regression revert rule: if a fix breaks 3+ existing tests, revert immediately

Phase-gated evaluation (200 -> 10K -> 61K questions from SOTA benchmarks) catches qualitatively different failure classes at each scale. Bugs invisible at 200 questions become 50 failures at 10K.

Each fix is structured: symptom, root cause, solution code, prevention strategy.

Products:
- RAG Debug Playbook ($47) — 79+ fixes, diagnostic flowcharts, anti-patterns (PDF + .md for AI assistants)
- Agent Context Kit ($27) — Drop-in .md context files for Claude Code / Copilot / Cursor
- Architecture Blueprint ($197) — Complete system with n8n workflow JSONs
- MEGA BUNDLE ($497) — All 14 products

Background: Polytechnique + HEC (France). Founded an AI company in construction/BTP.

---

## Posting Notes

- **Best time:** Tuesday-Thursday, 8-10am Pacific (11am-1pm Eastern)
- **Best day for tonight (Sunday):** Not ideal. Consider scheduling for Tuesday morning.
- **If posting tonight:** Still viable. HN gets less traffic on Sundays but also less competition.
- **Comment strategy:** Be in the thread immediately. Answer every question thoroughly. HN values depth and honesty.
- **Do NOT:** Be promotional. HN will downvote overt self-promotion. Lead with technical content.
- **DO:** Acknowledge limitations (Graph RAG at 40.9%, Orchestrator on hold). HN respects honesty.
