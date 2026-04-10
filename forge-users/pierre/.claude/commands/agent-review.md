---
description: Run weekly agent performance review — "HR for AI Agents" (Jensen model)
---

## Agent Performance Review

Perform a formal weekly review of all registered agents. Compare actual execution metrics against KPI targets defined in the registry. Produce a graded report and push it to git.

### Step 1: Load Registry

Read `data/agent-registry.json` to get the list of agents and their KPI targets.

### Step 2: Query Performance Data

Query Supabase `agent_runs` table for the past 7 days:

```sql
SELECT
  agent_name,
  COUNT(*) as total_runs,
  COUNT(*) FILTER (WHERE status = 'success') as successes,
  COUNT(*) FILTER (WHERE status = 'failed') as failures,
  COUNT(*) FILTER (WHERE status = 'timeout') as timeouts,
  ROUND(AVG(tokens_input + tokens_output)) as avg_tokens,
  ROUND(SUM(cost_usd)::numeric, 4) as total_cost,
  ROUND(AVG(cost_usd)::numeric, 6) as avg_cost_per_run,
  ROUND(SUM(proposals_count)::numeric, 0) as total_proposals,
  ROUND(SUM(quick_wins)::numeric, 0) as total_quick_wins,
  MAX(ended_at) as last_active
FROM agent_runs
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY agent_name
ORDER BY agent_name;
```

If the `agent_runs` table does not exist yet, note it in the report summary and use zeros for all metrics — this does not block the review.

### Step 3: Compute Grades

For each agent in the registry, compare actual metrics vs KPI targets:

| Signal | Weight |
|--------|--------|
| success_rate vs target | 40% |
| proposals_per_cycle vs target | 25% |
| token usage vs budget | 20% |
| quick_wins vs target | 15% |

Grade thresholds:
- **A** — all KPIs met, cost under budget
- **B** — 3/4 KPIs met
- **C** — 2/4 KPIs met
- **D** — 1/4 KPI met
- **F** — 0 KPIs met or agent has not run in 7 days

### Step 4: Write Report

Compute `REVIEW_DATE` as today's date in `YYYY-MM-DD` format.
Compute `PERIOD_START` as 7 days ago.

Write the review to `data/agent-reviews/{REVIEW_DATE}-review.json`:

```json
{
  "review_date": "{REVIEW_DATE}",
  "period": "{PERIOD_START} to {REVIEW_DATE}",
  "agents": {
    "research-analyst": {
      "runs": 28,
      "success_rate": 0.96,
      "kpi_success_rate_target": 0.90,
      "kpi_met": true,
      "total_tokens": 1680000,
      "total_cost_usd": 5.04,
      "budget_cap_usd": 1.80,
      "budget_used_pct": 2.80,
      "proposals": 140,
      "quick_wins": 8,
      "grade": "A",
      "notes": "Exceeding all KPIs. Token efficiency improving."
    }
  },
  "summary": {
    "total_cost_usd": 12.50,
    "daily_cap_usd": 5.12,
    "budget_used_pct": 2.44,
    "top_performer": "research-analyst",
    "needs_attention": [],
    "recommendations": []
  }
}
```

Fill in real values from Step 2 and Step 3 for each agent in the registry (research-analyst, market-analyst, feature-engineer, evolution-optimizer, repo-scout).

For `needs_attention`: include any agent where grade is C, D, or F, or where `budget_used_pct > 1.5`.
For `recommendations`: propose concrete fixes — e.g. "reduce WebFetch calls", "increase token budget", "check Supabase connectivity".

### Step 5: Push to Git

```bash
cd /home/termius/mon-ipad
git add data/agent-reviews/
git commit -m "data: agent review $(date +%Y-%m-%d)"
git push
```
