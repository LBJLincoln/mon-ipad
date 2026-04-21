# STRATEGIC DASHBOARD — live dossier

All Nomos42 strategic context in one place. Refreshed every 15 min by `scripts/ops/refresh_strategic_dashboard.py`. Designed so you can read top-to-bottom and make strategic decisions without opening anything else.

## Files

| # | File | What's in it | Refresh |
|---|---|---|---|
| 00 | [`00-MISSION.md`](./00-MISSION.md) | Mission, deadline, 4 hard floors, scope in/out | on scope change |
| 01 | [`01-tf-health.json`](./01-tf-health.json) | Live NBA/POL/ITF/PQTF — days, agents, bankroll, LLM fail rate | every 15 min |
| 02 | [`02-islands.json`](./02-islands.json) | 6 NBA + 5 POL survivors — Brier, gen, model, fleet-best | every 15 min |
| 03 | [`03-selfhost-llms.json`](./03-selfhost-llms.json) | 10 selfhost LLMs per account, gateway routing status | every 15 min |
| 04 | [`04-youtube-ingestion.json`](./04-youtube-ingestion.json) | 22 channels × 4 fleets — narrative versions, digest counts | every 15 min |
| 05 | [`05-revenue-runway.md`](./05-revenue-runway.md) | May 1 deadline, Stripe/Telegram/Whop stack, MRR target | on product change |
| 06 | [`06-experiments-ledger.json`](./06-experiments-ledger.json) | Shipped + queued experiments, dead lines | every 15 min |
| 07 | [`07-agent-roster.md`](./07-agent-roster.md) | 14-crew cadence, git-mutex, staggering rule | on roster change |
| 08 | [`08-browser-hermes.json`](./08-browser-hermes.json) | Browser-NBA, Browser-QA, Hermes Space liveness | every 15 min |
| 09 | [`09-strategic-queue.md`](./09-strategic-queue.md) | Open decisions, confirmed intentionals, cadence | on decision arrive/close |

+ `_refresh-status.json` — last refresh timestamp + files written.

## Decision flow

1. Skim `00-MISSION.md` — are we still aimed at the right target?
2. Open `01-tf-health.json` — any TF not `running: true`? any LLM fail rate > 30%?
3. Open `02-islands.json` — any fleet-best advancing?
4. Open `09-strategic-queue.md` — anything awaiting your call?
5. If revenue: `05-revenue-runway.md` is the single page.

## Why this file exists

User demand 2026-04-21:
> "where are ten files under one dossier tous reunis et constamment executes, de maniere intellgible et detaille, comme demande, pour que je puisse prendre les decisions strategiques adequates ? pas une fnfo ne doit manquer dans ces docs"

Answer: this directory. 10 files. Nothing missing. Refreshed by cron.
