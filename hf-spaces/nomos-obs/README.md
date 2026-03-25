---
title: Nomos42 Agent Observatory
emoji: 🔭
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: "4.44.1"
app_file: app.py
pinned: false
---

# Nomos42 Agent Observatory (S16)

Read-only dashboard for the Nomos42 NBA Quant AI system.

## Tabs

| Tab | Purpose |
|-----|---------|
| **Agent Dashboard** | All 5 agents: status, runs (24h), success rate, tokens, cost |
| **Activity Timeline** | Recent agent runs (last 48h), newest first |
| **Token & Cost** | 7-day rolling token/cost breakdown per agent with bar chart |
| **Health Status** | All 6 evolution island statuses, engine parity, recommendations |
| **Research Feed** | Latest research proposals (status, impact, agent source) |

## Data Sources

Priority order:
1. **Supabase pooler** — `DATABASE_URL` env var (PostgreSQL)
2. **VM direct** — `http://34.136.180.66:8080/health-status.json`
3. **GitHub raw** — `https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/data/`

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Supabase pooler connection string (PostgreSQL) |

## Required Supabase Tables (Phase 2)

The `agent_runs` table enables Tabs 1-3:

```sql
CREATE TABLE public.agent_runs (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    agent_name TEXT,
    skill TEXT,
    status TEXT,  -- 'success' | 'error' | 'running'
    duration_s FLOAT,
    tokens_used INT,
    cost_usd FLOAT,
    budget_cap_usd FLOAT,
    output_summary TEXT
);
```

Until this table exists, Tabs 1-3 show a graceful fallback message.
