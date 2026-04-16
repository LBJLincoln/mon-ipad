# Nomos42 — Claude Code Routines Manifest

**Launched:** 2026-04-14 by Anthropic | **Tier:** Max = 15 runs/24h | **Docs:** https://code.claude.com/docs/en/routines

## Decision: hybrid VM-cron + Routines

| Cadence | What | Where |
|---------|------|-------|
| Every 30 min | keepalive, odds fetch, CPCV watcher, infra-agent | VM cron (too frequent for Routines) |
| Every 2-4 h | autonomous-cycle, karpathy tuning | Routines (move off VM, free RAM) |
| Daily 1-2x | research scraper, daily summary, lightning-burst | Routines |
| Weekly | calibration fit | Routines |

**Routines budget:** 10 routines @ avg 1 run/day each = 10 runs/day, leaves 5-run buffer under the 15-cap.

## 10 Routines to create (via https://claude.ai/code/routines — no CLI, manual setup)

### R1 — `nomos42-fleet-4h-cycle`
- **Schedule:** every 4h at :05 UTC (6 runs/day) ⚠️ EXCEEDS SOLO BUDGET — drop to every 8h = 3 runs/day
- **Prompt:** "Run the nba-fleet-ops agent 4h cycle for S10-S17. Diagnose stagnation, checkpoint pareto-best, restart dead Spaces. Commit state snapshot. Under 200 words report."
- **Repos:** `LBJLincoln/mon-ipad`
- **Env vars:** `HF_TOKEN_NBA`, `HF_TOKEN_POL`, `HF_TOKEN_LLM`, `HF_TOKEN_COUNCILS`, `GITHUB_TOKEN`

### R2 — `nomos42-political-4h-cycle`
- **Schedule:** every 8h at :15 UTC (3 runs/day)
- **Prompt:** "Run political-fleet-ops agent for P1-P8. Same protocol as NBA fleet. Emphasize P5-P8 breakout progress (recently deployed)."
- **Repos:** `LBJLincoln/mon-ipad`, `LBJLincoln/nomos-political-alpha`

### R3 — `nomos42-llm-gateway-health`
- **Schedule:** daily 08:00 UTC (1 run/day)
- **Prompt:** "Run llm-fleet-ops. Verify gateway /ping, /api/chat, 20 models. Restart TF-NBA and TF-Political if loop stuck. Under 200 words."
- **Repos:** `LBJLincoln/mon-ipad`

### R4 — `nomos42-research-scan`
- **Schedule:** daily 06:00 UTC (1 run/day, replaces VM cron `0 6,18`)
- **Prompt:** "Run research-scout agent. Scan arXiv R1-R6, alert on Brier <0.20, write proposals. Commit vault refresh."
- **Repos:** `LBJLincoln/mon-ipad`

### R5 — `nomos42-feature-lab`
- **Schedule:** every 12h (2 runs/day)
- **Prompt:** "Run feature-lab agent. Implement oldest unimplemented research proposal into features/engine.py + hf-space/features/engine.py. Verify sha256 parity. Commit."
- **Repos:** `LBJLincoln/mon-ipad`

### R6 — `nomos42-monetization-daily`
- **Schedule:** daily 09:00 UTC (1 run/day)
- **Prompt:** "Run monetization-ops. Reconcile Stripe/Whop/LemonSqueezy. Compute MRR/ARPU/churn. Alert if MRR < $50 (May 1 shutdown gate)."
- **Repos:** `LBJLincoln/mon-ipad`

### R7 — `nomos42-market-scanner-gameday`
- **Schedule:** every 2h during 18:00-00:00 UTC (NBA windows, ~3 runs/day)
- **Prompt:** "Run market-scanner. Scan odds, detect steam moves, compute CLV vs our model. Alert edge >5%."
- **Repos:** `LBJLincoln/mon-ipad`

### R8 — `nomos42-picks-publisher`
- **Schedule:** daily 18:00 UTC (1 run/day)
- **Prompt:** "Run picks-publisher. Publish value bets to @Nomos42Picks Telegram. Enforce Stripe gate. Post ROI report."
- **Repos:** `LBJLincoln/mon-ipad`

### R9 — `nomos42-councils-ops`
- **Schedule:** every 12h (2 runs/day)
- **Prompt:** "Run councils-ops for D1-D9. Karpathy loop per dept (SCAN→PROPOSE→EXECUTE 5min→EVALUATE). Cross-pollinate wins between depts."
- **Repos:** `LBJLincoln/mon-ipad`

### R10 — `nomos42-brain-orchestrator`
- **Schedule:** 00:00 UTC daily (1 run/day — top-level dispatcher)
- **Prompt:** "Run brain-orchestrator. Read health snapshots. Dispatch sub-agents that have work. Commit daily state."
- **Repos:** `LBJLincoln/mon-ipad`

## Daily budget: 3+3+1+1+2+1+3+1+2+1 = **18 runs/day** ⚠️

**Exceeds Max 15/day by 3.** Options:
- (a) Drop R7 from 3→1 = 16/day, drop R1 or R5 by 1 = **15/day** ✅
- (b) Enable Extra Usage billing (Anthropic metered overage)
- (c) Fold R1+R10 into one "fleet + brain" combined routine = **17/day**

## What stays on VM cron (too frequent for Routines)
- `*/30 keepalive-spaces.sh` (33 Spaces probed, 48 runs/day)
- `*/30 cpcv_watcher.py`
- `*/30 nba_drift_monitor.py`
- `15,45 infra-agent.sh`
- `5,35 auto_pav_refit.sh`
- `15,45 lineage injector`
- `*/10 bloomberg-api watchdog`

## Manual setup steps
1. https://claude.ai/code/routines → "New routine"
2. Pick prompt from above
3. Add repo `LBJLincoln/mon-ipad` (+ `nomos-political-alpha` for R2)
4. Create environment `nomos42-default` with env vars (HF_TOKEN_*, GITHUB_TOKEN, STRIPE_SECRET_KEY, TELEGRAM_BOT_TOKEN)
5. Set schedule (cron-like)
6. Save. Routine fires on cadence; watch live at /routines UI.

## Gap vs local: routine defs are NOT version-controlled
This manifest is the poor-man's git-backed source of truth. If you recreate a routine, copy the prompt from here.
