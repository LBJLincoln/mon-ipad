---
title: Nomos42 Langfuse
emoji: 🔍
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Nomos42 Langfuse — LLM Observability

Self-hosted [Langfuse](https://langfuse.com) for Nomos42 Trading Floor observability.

Traces every LLM call across:
- 12 NBA Trading Floor agents
- 10 Political Trading Floor agents  
- 9 Department Council loops
- LLM Gateway proxy calls

## Setup

Requires these Space secrets:
- `DATABASE_URL` — Postgres connection string (Supabase pooler)
- `NEXTAUTH_SECRET` — random 32-char string
- `SALT` — random 32-char string
