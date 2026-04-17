# Nomos42 — 4 Tracks (supersedes 9 departments)

> Old: D1 Research, D2 Engineering, D3 Evolution, D4 Product, D5 Business,
>      D6 Evaluation, D7 Infra, D8 Finance, D9 Cross-repo (9 HF Spaces).
> New: 4 tracks. Same HF Spaces stay alive (cheap), but ONE Opus orchestrator
>      decides for all 4 every 8h instead of 9 rubber-stamp subagents.

## Mapping

| Track | Absorbs | Owns | Ships |
|-------|---------|------|-------|
| **T1 SCIENCE** | D1 + D3 + D6 | Brier floor, calibration, mutation, arXiv scan | feature engine bumps, PAV refits, CPCV gate, new research proposals |
| **T2 PLATFORM** | D2 + D7 + D9 | Code parity, deploys, uptime, cross-repo hash | auto-deploy-engine, sister-repo sync, space restarts, CI health |
| **T3 MARKET** | D4 + D5 | Dashboard UX, Telegram/@Nomos42Picks, subs, pricing | Vercel pages, paywall, Stripe/Whop/LS reconciliation |
| **T4 CAPITAL** | D8 + Trading Floors | NBA TF + POL TF, bankroll, $1M collective goal, May-1 deadline | MIN_DEPLOY_PCT=0.75, Kelly caps, parlay sizing, TF LLM routing |

## Orchestrator

ONE Opus 4.7 cloud session every 8h (00:30, 08:30, 16:30 UTC) reads:
- `data/tracks/t1-science.json`
- `data/tracks/t2-platform.json`
- `data/tracks/t3-market.json`
- `data/tracks/t4-capital.json`

Each track file ≤2kB summary: `{status, last_metric, last_action, next_proposal, blocked_on}`.
Orchestrator emits ONE plan touching 1-2 tracks max (not all 4 every cycle).

## What disappears

- 9 dept HF Spaces keep running (they already exist) but are NOT auto-pinged by a cron.
  Their outputs are pulled on-demand by the T-track orchestrator.
- D6 TF-monitor + D7 GPU-monitor crons killed → consumed by T4/T2 on orchestrator tick.
- coord/coord.py --tick killed → replaced by orchestrator.
- Every-30min cadence → hourly or less where not critical.

## Track status files (cron writers, not humans)

- `t1-science.json` ← written by `scripts/monitoring/nba_drift_monitor.py` + CPCV watcher
- `t2-platform.json` ← written by `scripts/infra-agent.sh` + auto-deploy-engine
- `t3-market.json` ← written by Vercel deploy webhook + Telegram channel stats
- `t4-capital.json` ← written by monitor-tf-d6 aggregator (runs daily now, not hourly)

## Why this is better than 9 depts

1. Opus sees 4 summaries instead of 9 rubber-stamp LLM outputs — less noise.
2. One decision-maker avoids the "D3 says mutate, D6 says don't" contradiction.
3. Budget fits: 3 Opus sessions/day × ~5k tokens = ~$1/day, not $15-30.
4. Cron count halved. `git status` no longer a war crime.
