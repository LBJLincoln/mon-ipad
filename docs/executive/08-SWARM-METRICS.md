# NOMOS42 — Swarm Metrics Registry v1.0
> Every agent. One metric. Measured automatically.
> Last updated: 2026-03-31

## Design Principles

1. **One metric per agent** — each agent has exactly one number it is responsible for improving.
2. **Measurable without ML** — metrics read from files, APIs, or database counts. No inference on VM.
3. **Threshold-driven alerts** — each metric has a RED/YELLOW/GREEN threshold band.
4. **Frequency matched to agent cadence** — fast agents measure every 30min, slow agents daily.

---

## NBA Product — Layer 1 Agents

### O1: Brain (Strategy Definer)

| Field | Value |
|-------|-------|
| **Metric name** | decisions_actioned_per_cycle |
| **Unit** | count |
| **Current value** | 1 (one action per 4h cycle — enforced by rules) |
| **Target value** | 1 (steady — "1 fix per iteration" rule) |
| **Measurement method** | Count writes to data/health-status.json per 24h window |
| **Frequency** | Every 4h |
| **Data source** | `data/health-status.json` — check `last_action` field timestamp |
| **Alert: RED** | 0 actions in 24h (brain frozen or unreachable) |
| **Alert: YELLOW** | >1 action per 4h cycle (rule violation) |
| **Alert: GREEN** | Exactly 1 action per 4h cycle |

### R1: Research Analyst

| Field | Value |
|-------|-------|
| **Metric name** | research_proposals_per_week |
| **Unit** | count |
| **Current value** | ~4 (estimated from /karpathy-loop runs) |
| **Target value** | 7 (one per day) |
| **Measurement method** | `SELECT COUNT(*) FROM research_proposals WHERE created_at > NOW() - INTERVAL '7 days'` |
| **Frequency** | Daily at 06:00 |
| **Data source** | Supabase `research_proposals` table |
| **Alert: RED** | 0 proposals in 72h |
| **Alert: YELLOW** | < 3 proposals in 7 days |
| **Alert: GREEN** | >= 7 proposals in 7 days |

### R2: Karpathy Researcher

| Field | Value |
|-------|-------|
| **Metric name** | karpathy_iterations_per_session |
| **Unit** | count |
| **Current value** | 12 iterations/hr on Kaggle |
| **Target value** | 15 iterations/hr |
| **Measurement method** | Parse Kaggle notebook output log: count "iter X: Brier=" lines |
| **Frequency** | Per Kaggle session |
| **Data source** | `scripts/kaggle/nba_karpathy_loop.py` output log |
| **Alert: RED** | < 5 iterations in a session (stalled) |
| **Alert: YELLOW** | 5-10 iterations |
| **Alert: GREEN** | >= 12 iterations/hr |

### R3: Repo Scout

| Field | Value |
|-------|-------|
| **Metric name** | new_repos_flagged_per_week |
| **Unit** | count |
| **Current value** | unknown (deploying) |
| **Target value** | 5 new repos/week flagged as relevant |
| **Measurement method** | Count entries in `data/research/repos-latest.json` with `status: new` |
| **Frequency** | Every 12h (aligned to research-cron.sh) |
| **Data source** | `data/research/repos-latest.json` |
| **Alert: RED** | 0 new repos in 7 days |
| **Alert: GREEN** | >= 5 per week |

### R4: Market Analyst

| Field | Value |
|-------|-------|
| **Metric name** | value_bets_identified_per_day |
| **Unit** | count |
| **Current value** | ~2-3/day (active game days) |
| **Target value** | >= 3 on game days |
| **Measurement method** | Count picks in `data/nba-agent/latest-eval.json` where `edge > 0.05` |
| **Frequency** | Daily per /daily-edge run |
| **Data source** | `data/nba-agent/latest-eval.json` |
| **Alert: RED** | 0 value bets on game day |
| **Alert: GREEN** | >= 3 value bets with edge > 5% |

---

## NBA Product — Engineering Agents

### E1: Feature Engineer

| Field | Value |
|-------|-------|
| **Metric name** | feature_categories_added_per_month |
| **Unit** | count |
| **Current value** | 3 (Cat47/48/49 added 2026-03-31) |
| **Target value** | 4/month (one per week) |
| **Measurement method** | Grep `features/engine.py` for `# Cat` lines: `grep -c "^# Cat" features/engine.py` |
| **Frequency** | Daily at 06:00 |
| **Data source** | `features/engine.py` line count + Supabase `feature_engine_version` |
| **Alert: RED** | No new category in 30 days |
| **Alert: YELLOW** | 1-2 new categories in 30 days |
| **Alert: GREEN** | >= 4 new categories per month |

### E2: Evolution Optimizer

| Field | Value |
|-------|-------|
| **Metric name** | best_brier_improvement_per_week |
| **Unit** | delta (lower is better) |
| **Current value** | ATR 0.21570 (walk-forward 0.22447) |
| **Target value** | -0.002 per week |
| **Measurement method** | Read `data/nba-agent/latest-eval.json` field `best_brier`, compare to 7-day-old value |
| **Frequency** | Weekly (Sunday 05:00 after cross-pollination) |
| **Data source** | `data/nba-agent/latest-eval.json`, Supabase `experiments` table |
| **Alert: RED** | Brier degrades > +0.005 from previous week |
| **Alert: YELLOW** | No improvement in 2 weeks |
| **Alert: GREEN** | Brier improves >= -0.001 per week |

### E3: Predictions Agent

| Field | Value |
|-------|-------|
| **Metric name** | predictions_posted_before_gametime |
| **Unit** | pct (0-100) |
| **Current value** | ~90% (estimated) |
| **Target value** | 100% |
| **Measurement method** | Count predictions with timestamp > 2h before game tip-off vs total games |
| **Frequency** | Daily post-predictions-run |
| **Data source** | `data/nba-agent/latest-eval.json` + game schedule |
| **Alert: RED** | Any game day with 0 predictions posted |
| **Alert: YELLOW** | < 80% of games covered |
| **Alert: GREEN** | 100% coverage, all posted > 2h before tip |

### E4: Backtest Agent

| Field | Value |
|-------|-------|
| **Metric name** | backtest_weeks_validated |
| **Unit** | count |
| **Current value** | 19 weeks validated (Kaggle walk-forward) |
| **Target value** | Full 2025-26 season (27+ weeks) |
| **Measurement method** | Count rows in Kaggle backtest output CSV |
| **Frequency** | Per Kaggle GPU session |
| **Data source** | Kaggle output + `data/nba-agent/backtest-results.json` (when available) |
| **Alert: RED** | Backtest not run in 30 days |
| **Alert: GREEN** | Validated on >= 20 weeks |

### E5: Data Pipeline

| Field | Value |
|-------|-------|
| **Metric name** | data_freshness_hours |
| **Unit** | hours since last successful fetch |
| **Current value** | < 0.5h (30min cron) |
| **Target value** | < 1h always |
| **Measurement method** | Read `data/nba-agent/live-odds.json` field `fetched_at`, compute age |
| **Frequency** | Every 30min |
| **Data source** | `data/nba-agent/live-odds.json` + `data/nba-agent/odds-latest.json` |
| **Alert: RED** | Data > 3h old on game day |
| **Alert: YELLOW** | Data > 2h old |
| **Alert: GREEN** | Data < 1h old |

---

## NBA Product — Evolution Agents

### V1: Island Coordinator

| Field | Value |
|-------|-------|
| **Metric name** | islands_active_count |
| **Unit** | count (of 6) |
| **Current value** | 6 (all running) |
| **Target value** | 6 at all times |
| **Measurement method** | Fetch `/api/status` from each of S10-S15 URLs, count HTTP 200 responses |
| **Frequency** | Every 30min |
| **Data source** | `https://nomos42-nba-quant.hf.space/api/status` (and S11-S15 equivalents) |
| **Alert: RED** | < 4 islands responding |
| **Alert: YELLOW** | 4-5 islands responding |
| **Alert: GREEN** | All 6 responding |

### V2: GPU Trainer

| Field | Value |
|-------|-------|
| **Metric name** | kaggle_brier_from_last_session |
| **Unit** | Brier score |
| **Current value** | 0.21737 (RF 94f iter10) |
| **Target value** | < 0.21 (GPU evolution target) |
| **Measurement method** | Parse `data/nba-agent/kaggle-session-log.json` for latest Brier |
| **Frequency** | Per session (daily GPU run at 03:00 if enabled) |
| **Data source** | `data/nba-agent/kaggle-session-log.json` |
| **Alert: RED** | No GPU session in 7 days |
| **Alert: YELLOW** | Session ran but Brier > 0.22 |
| **Alert: GREEN** | Brier < 0.21 achieved |

### V3: Political Evolution

| Field | Value |
|-------|-------|
| **Metric name** | political_engine_categories_live |
| **Unit** | count |
| **Current value** | 22 |
| **Target value** | 25 (3 new categories before end of Q2) |
| **Measurement method** | Count `# Cat` lines in `nomos-political-alpha/features/political_engine.py` |
| **Frequency** | Weekly |
| **Data source** | `nomos-political-alpha/features/political_engine.py` |
| **Alert: RED** | No new category in 60 days |
| **Alert: GREEN** | >= 1 new category added this month |

---

## NBA Product — Betting Agents

### B1: Odds Monitor

| Field | Value |
|-------|-------|
| **Metric name** | odds_sources_active |
| **Unit** | count |
| **Current value** | 3 (BetMGM + SBR + ESPN) |
| **Target value** | >= 3 at all times |
| **Measurement method** | Check `data/nba-agent/live-odds.json` for distinct `source` fields |
| **Frequency** | Every 30min on game days |
| **Data source** | `data/nba-agent/live-odds.json` |
| **Alert: RED** | 0 odds sources on game day |
| **Alert: YELLOW** | Only 1 source |
| **Alert: GREEN** | >= 3 sources with fresh data |

### B2: Value Detector

| Field | Value |
|-------|-------|
| **Metric name** | avg_edge_on_flagged_bets |
| **Unit** | percentage |
| **Current value** | unknown (need arena history) |
| **Target value** | > 5% avg edge on flagged bets |
| **Measurement method** | Read `data/nba-agent/latest-eval.json` picks, avg `edge` field on `recommended: true` bets |
| **Frequency** | Daily |
| **Data source** | `data/nba-agent/latest-eval.json` |
| **Alert: RED** | Avg edge < 1% (noise level) |
| **Alert: GREEN** | Avg edge > 5% |

### B3: Kelly Sizer

| Field | Value |
|-------|-------|
| **Metric name** | bankroll_utilization_pct |
| **Unit** | percentage |
| **Current value** | unknown |
| **Target value** | 5-15% per bet (fractional Kelly) |
| **Measurement method** | Read `data/nba-agent/bankroll-state.json` compute avg bet size / bankroll |
| **Frequency** | Daily |
| **Data source** | `data/nba-agent/bankroll-state.json` |
| **Alert: RED** | > 20% bankroll on single bet (Kelly overbetting) |
| **Alert: GREEN** | 5-15% per bet |

### B4: Betting Strategist

| Field | Value |
|-------|-------|
| **Metric name** | portfolio_sharpe_ratio |
| **Unit** | Sharpe (dimensionless) |
| **Current value** | 4.57 (13 bets, corrected) |
| **Target value** | > 1.5 sustained over season |
| **Measurement method** | Read `data/nba-agent/bankroll-state.json` field `sharpe` |
| **Frequency** | Weekly (Sunday review) |
| **Data source** | `data/nba-agent/bankroll-state.json` |
| **Alert: RED** | Sharpe < 0.5 (strategy breaking down) |
| **Alert: YELLOW** | Sharpe 0.5-1.5 |
| **Alert: GREEN** | Sharpe > 1.5 |

### B5: Evaluator

| Field | Value |
|-------|-------|
| **Metric name** | season_roi_pct |
| **Unit** | percentage |
| **Current value** | +3.92% |
| **Target value** | > 5% ROI |
| **Measurement method** | Read `data/nba-agent/bankroll-state.json` field `roi_pct` |
| **Frequency** | Daily at 10:00 (post-evaluation) |
| **Data source** | `data/nba-agent/bankroll-state.json` |
| **Alert: RED** | ROI < 0% (losing money) |
| **Alert: YELLOW** | ROI 0-3% |
| **Alert: GREEN** | ROI > 5% |

---

## NBA Product — Evaluation Agents

### Q1: Quality Tracker

| Field | Value |
|-------|-------|
| **Metric name** | brier_vs_atr_gap |
| **Unit** | delta |
| **Current value** | 0.0 (current = ATR 0.21570) |
| **Target value** | <= 0.0 (current run never worse than ATR) |
| **Measurement method** | Read Supabase `experiments` latest Brier, compare to `0.21570` hardcoded ATR |
| **Frequency** | Every 4h (aligned to O1 brain cycle) |
| **Data source** | Supabase `experiments` table, field `brier_score` |
| **Alert: RED** | Current run Brier > ATR + 0.005 (regression detected) |
| **Alert: YELLOW** | Within 0.005 of ATR but not improving |
| **Alert: GREEN** | Current run Brier <= ATR |

### Q2: Arena Benchmark

| Field | Value |
|-------|-------|
| **Metric name** | arena_profitable_strategies_count |
| **Unit** | count (of 60 evaluated) |
| **Current value** | 5/60 profitable |
| **Target value** | >= 10/60 profitable at Brier < 0.21 |
| **Measurement method** | Count strategies with ROI > 0 in arena output JSON |
| **Frequency** | Daily at 11:00 (arena-engine.py) |
| **Data source** | Arena output in `data/` directory |
| **Alert: RED** | < 3 profitable strategies |
| **Alert: GREEN** | >= 10 profitable strategies |

---

## Infrastructure Agents

### I1: Fleet Manager

| Field | Value |
|-------|-------|
| **Metric name** | fleet_uptime_pct |
| **Unit** | percentage |
| **Current value** | ~99% (estimated) |
| **Target value** | 99.5% |
| **Measurement method** | Divide (successful pings in 24h / total ping attempts) × 100 for all 20 HF Spaces |
| **Frequency** | Every 5min (watchdog.sh) |
| **Data source** | `data/agent-health.json` |
| **Alert: RED** | Any core service (evolution island or bot) down > 10min |
| **Alert: YELLOW** | Uptime < 99% in 24h |
| **Alert: GREEN** | All 20 spaces healthy, all 5 bots running |

### I2: Infra Agent

| Field | Value |
|-------|-------|
| **Metric name** | auto_restarts_per_day |
| **Unit** | count |
| **Current value** | unknown |
| **Target value** | < 3 per day (high count = systemic issue) |
| **Measurement method** | Count restart events in watchdog.sh log (`grep "restarted" /var/log/watchdog.log | wc -l`) |
| **Frequency** | Daily |
| **Data source** | VM system logs, `data/infra-status.json` |
| **Alert: RED** | > 5 restarts in 24h (thrashing) |
| **Alert: YELLOW** | 3-5 restarts |
| **Alert: GREEN** | < 3 restarts |

---

## Monitoring Agents (M1-M7)

### M1: Fleet Monitor

| Field | Value |
|-------|-------|
| **Metric name** | services_reporting_healthy |
| **Unit** | count |
| **Current value** | tracked in data/agent-health.json |
| **Target value** | All services healthy |
| **Measurement method** | Read `data/agent-health.json`, count `status: healthy` fields |
| **Frequency** | Every 30min |
| **Alert: RED** | Any evolution island down |

### M2: Island Coordinator

| Field | Value |
|-------|-------|
| **Metric name** | generations_run_per_island_per_day |
| **Unit** | count |
| **Current value** | ~50-100 gens/day per island (estimated) |
| **Target value** | >= 50 gens/day per island |
| **Measurement method** | Fetch `/api/status` from each island, read `generation` field, compute daily delta |
| **Frequency** | Every 4h |
| **Data source** | `/api/status` endpoint on S10-S15 |
| **Alert: RED** | Island frozen (0 new gens in 12h) |
| **Alert: GREEN** | All islands advancing >= 50 gens/day |

### M3: Betting Monitor

| Field | Value |
|-------|-------|
| **Metric name** | odds_staleness_hours |
| **Unit** | hours |
| **Current value** | < 0.5h on game days |
| **Target value** | < 2h at all times |
| **Measurement method** | Read `data/nba-agent/live-odds.json` field `fetched_at`, compute age |
| **Frequency** | Every 30min on game days |
| **Alert: RED** | > 3h old on game day (missed game coverage) |

### M4: Quality Tracker

| Field | Value |
|-------|-------|
| **Metric name** | days_since_new_atr |
| **Unit** | days |
| **Current value** | ~4 days (ATR set 2026-03-27) |
| **Target value** | New ATR at least every 30 days |
| **Measurement method** | Compare `data/nba-agent/latest-eval.json` brier to known ATR = 0.21570 |
| **Frequency** | Daily |
| **Alert: RED** | > 60 days without new ATR (evolution stagnant) |
| **Alert: GREEN** | New ATR set within last 30 days |

### M5: Research Radar

| Field | Value |
|-------|-------|
| **Metric name** | papers_found_per_week |
| **Unit** | count |
| **Current value** | unknown (deploying) |
| **Target value** | >= 3 relevant papers/week |
| **Measurement method** | Count entries in `data/research/papers-latest.json` added this week |
| **Frequency** | Every 12h |
| **Alert: RED** | 0 papers in 2 weeks |
| **Alert: GREEN** | >= 3 papers/week flagged as relevant |

### M6: Predictions Monitor

| Field | Value |
|-------|-------|
| **Metric name** | game_coverage_pct |
| **Unit** | percentage |
| **Current value** | ~90% |
| **Target value** | 100% on game days |
| **Measurement method** | Count predictions in `data/nba-agent/latest-eval.json` / count games scheduled that day |
| **Frequency** | Daily at 14:00 (post-predictions) |
| **Alert: RED** | < 50% game coverage on game day |
| **Alert: GREEN** | 100% coverage |

### M7: Political Monitor

| Field | Value |
|-------|-------|
| **Metric name** | signal_sources_fresh |
| **Unit** | count of sources with data < 24h old |
| **Current value** | estimated 7/10 sources fresh |
| **Target value** | >= 8/10 sources fresh |
| **Measurement method** | Check timestamps in political data files in `nomos-political-alpha/data/` |
| **Frequency** | Every 6h |
| **Alert: RED** | < 5 sources fresh (signal gap) |
| **Alert: GREEN** | >= 8 sources fresh |

---

## Political Alpha — Unique Metrics

### PA-E: Political Engine (E5 analog)

| Field | Value |
|-------|-------|
| **Metric name** | political_signal_accuracy_pct |
| **Unit** | percentage |
| **Current value** | not yet measured |
| **Target value** | > 55% directional accuracy (above coin flip) |
| **Measurement method** | Compare political predictions to realized outcomes in Polymarket |
| **Frequency** | Weekly (as markets resolve) |
| **Alert: RED** | < 50% accuracy (worse than random) |
| **Alert: GREEN** | > 60% accuracy |

---

## RGWA — Unique Metrics

### RGWA-Q: Quality Critic

| Field | Value |
|-------|-------|
| **Metric name** | avg_generation_quality_score |
| **Unit** | score 0-10 |
| **Current value** | not yet measured |
| **Target value** | >= 7.5 average across all outputs |
| **Measurement method** | Average quality scores in `rgwa/data/gallery/quality-scores.json` |
| **Frequency** | Per generation batch |
| **Alert: RED** | Avg score < 5 (model degradation or prompt drift) |
| **Alert: YELLOW** | Avg 5-7 |
| **Alert: GREEN** | Avg >= 7.5 |

### RGWA-S: Style Curator

| Field | Value |
|-------|-------|
| **Metric name** | trend_freshness_days |
| **Unit** | days since last trend update |
| **Current value** | not tracked yet |
| **Target value** | <= 7 days (weekly trend refresh) |
| **Measurement method** | Check modification date on `rgwa/data/trends/current-trends.json` |
| **Frequency** | Weekly |
| **Alert: RED** | > 14 days without trend update |
| **Alert: GREEN** | Updated within 7 days |

---

## Forge Factory — Unique Metrics

### F0: Strategy Definer (per-user)

| Field | Value |
|-------|-------|
| **Metric name** | time_to_product_brief_minutes |
| **Unit** | minutes |
| **Current value** | not deployed |
| **Target value** | < 15 minutes from idea to structured brief |
| **Measurement method** | Timestamp delta between `/forge-intake` call and `briefs/product-brief.json` creation |
| **Frequency** | Per onboarding |
| **Alert: RED** | > 60 minutes (agent stuck) |
| **Alert: GREEN** | < 15 minutes |

### F1: Product Builder (per-user)

| Field | Value |
|-------|-------|
| **Metric name** | karpathy_iterations_completed |
| **Unit** | count |
| **Current value** | not deployed |
| **Target value** | >= 10 iterations before MVP ship |
| **Measurement method** | Count entries in `forge-users/{name}/data/iterations/` |
| **Frequency** | Per product sprint |
| **Alert: GREEN** | MVP shipped after >= 10 measured iterations |

### F2: Business Strategist (per-user)

| Field | Value |
|-------|-------|
| **Metric name** | niche_opportunity_score |
| **Unit** | score 0-100 |
| **Current value** | not deployed |
| **Target value** | > 65 before building begins |
| **Measurement method** | Read `forge-users/{name}/strategy/niche-analysis.json` field `opportunity_score` |
| **Frequency** | Per product |
| **Alert: RED** | Score < 30 (bad idea — stop building) |
| **Alert: GREEN** | Score > 65 (validated opportunity) |

---

## Metric Hierarchy (what the brain watches first)

Priority 1 — Existential (system must act immediately):
- fleet_uptime_pct < 99% (I1)
- brier_vs_atr_gap > +0.005 (Q1)
- data_freshness_hours > 3 on game day (E5)

Priority 2 — Strategic (act within next cycle):
- best_brier_improvement_per_week < -0.001 for 2+ weeks (E2)
- islands_active_count < 6 (V1)
- season_roi_pct < 0% (B5)

Priority 3 — Growth (plan within week):
- research_proposals_per_week < 3 (R1)
- feature_categories_added < 1/month (E1)
- value_bets_identified < 3 on game days (R4)

Priority 4 — Quality (review monthly):
- arena_profitable_strategies < 5 (Q2)
- backtest_weeks_validated < 20 (E4)
- political_signal_accuracy < 55% (PA-E)
