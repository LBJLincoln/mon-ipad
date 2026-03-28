---
name: Evolution Fleet Status — March 2026
description: HF Space fleet health snapshots. Latest: 2026-03-28 post-redeploy. 5/6 islands RUNNING, S14 stuck BUILDING, watchdog data server bug fixed.
type: project
---

**Last verified: 2026-03-28 13:40 UTC**

## Current Fleet State (post-redeploy 2026-03-28)

All 6 islands were redeployed 2026-03-28. Generations are fresh/low.

| Space | Stage | Gen | Brier | Role |
|-------|-------|-----|-------|------|
| S10 nba-quant | RUNNING | 9 | 0.22215 | exploitation |
| S11 nba-quant-2 | RUNNING | 11 | 0.22321 | exploration |
| S12 nba-evo-3 | RUNNING | 15 | 0.23347 | extra_trees specialist |
| S13 nba-evo-4 | RUNNING | 6 | 0.22492 | catboost specialist |
| S14 nba-evo-5 | BUILDING | -- | -- | lightgbm specialist |
| S15 nba-evo-6 | RUNNING | 30 | 0.22112 | wide search |

**S14 issue**: stuck in BUILDING since 11:44 UTC (>2h). HTTP 000. No error in HF API. If still BUILDING at 15:00 UTC, trigger manual restart.

**Fleet best post-redeploy**: S15, Brier=0.22112, gen 30

## All-Time Bests
- **ATR**: Brier 0.21570 (Colab TabICL, 110f, iter 15, 2026-03-27)
- **CPU best**: 0.21976 (experiment #734, extra_trees, 142 features)
- **Target**: < 0.20

## Pre-Redeploy State (2026-03-26 snapshot)

| Space | Gen | Brier (best) | Gen-Pop Brier | Mut | Feat=200% | Supabase |
|-------|-----|--------------|----------------|-----|-----------|----------|
| S10 | 1970 | 0.22278 | 0.2214 (frozen) | 0.09 | 100% | OK |
| S11 | 898 | 0.22365 | 0.2245 (frozen) | 0.08 | 100% | DEAD |
| S12 | 56 | 0.22116 | 0.2206 | 0.0715 | 98% | DEAD |
| S13 | 61 | 0.22367 | 0.2221 (improving) | 0.1126 | 72% | UNKNOWN |
| S14 | 589 | 0.22093 | 0.2252 (regressed) | 0.1024 | 100% | OK |
| S15 | 1017 | 0.22625 | 0.2221 (frozen) | 0.08 | 100% | OK |

Actions taken 2026-03-26:
- S10: config push mutation_rate=0.09, target_features=63, crossover_rate=0.80
- S11: experiments #2533 (et63), #2534 (mut rescue 0.12), #2535 (xgb+sigmoid+63f) submitted

## Infrastructure Issues Found & Fixed (2026-03-28)

### Watchdog data server bug — FIXED
- **Bug**: pgrep -f 'nba-data-server' did NOT match running process ('python3 -m http.server 8080')
- **Effect**: 12 false restarts/hour, each failing with EADDRINUSE
- **Fix**: `/home/termius/mon-ipad/scripts/watchdog.sh` — changed to: `if ! { pgrep -f "nba-data-server" || pgrep -f "http\.server 8080"; }; then`
- **Verified**: fix confirmed working

### Data server
- Running as: `python3 -m http.server 8080 -b 0.0.0.0 --directory /home/termius/mon-ipad/data` (PID 507711, since Mar 27)
- Port 8080, serving /home/termius/mon-ipad/data/

### Telegram bots
- @Nomos42Bot: PID 269800, running since Mar 27 17:11
- @RGWAbot: PID 270201, running since Mar 27 17:18

### Crons
- 11 active entries (watchdog, NBA agents, cross-repo, kaggle, political x4, infra, social, political agents)

## Structural Issues (persist across redeploys)

1. **Feat=200 universal takeover** — 5 of 6 islands at 100% Feat=200 in gen logs pre-redeploy. Root cause: NSGA-II tournament selection rewards ROI/Sharpe overfitting. REQUIRES CODE FIX to genetic_loop_v3.py — add Pareto crowding penalty for n_features > 150.

2. **Supabase dead on S11/S12/S13** — "FATAL: Tenant or user not found". Wrong DATABASE_URL pooler credentials. Fix: update env vars in HF Space settings to match S10's working credentials.

3. **Migration spreading Feat=200** — Need feature-count filter on migration candidates (<= 120 features only).

## API Reference (verified correct endpoints)
- Status: `GET /api/status`
- Config push: `POST /api/config`
- Experiment submit: `POST /api/experiment/submit` (NOT /api/submit-experiment)
- Population reset: `POST /api/reset`
- Command: `POST /api/command`

**Why tracking this**: Feat=200 bloat is the primary obstacle to breaking Brier 0.22 on CPU islands. Config-only rescues give temporary relief but Feat=200 re-establishes within 20-30 gens. Only a code-level selection penalty fix will solve it permanently.
