# THE PLUMBER — Dashboard Data-Layer Gap Audit

**Run**: 2026-05-01 (read-only)
**Cwd**: /home/user/mon-ipad
**Today**: 2026-05-01. Baseline mtime cluster: 2026-04-26 00:14Z (everything except `quarantine.json` and `overnight-latest.json` is frozen at that timestamp — the VM was last hydrated 5 days ago).

## TL;DR

The dashboard's data layer is point-estimate-only, ~5 days stale, and missing all trust signals (CI, N, ECE-per-bucket, per-agent rolling Brier, calibration curves) needed by a lab-grade UI. `tf_rigorous_validation.py` and `tf_cross_llm_view.py` emit good shape; the rest emit aggregates without uncertainty. The sync cron hasn't run since 2026-04-26 — that one fact poisons every chart on Vercel.

---

## A. Gap Matrix

| File | Schema (top-level fields) | Freshness (mtime) | What's MISSING for lab-grade UI | Emitter | Effort |
|---|---|---|---|---|---|
| `data/pipeline-health.json` | agent, timestamp, rollup, summary, nba_tf{}, pol_tf{}, itf_tf{}, audit_sync{}, data_sources{}, alerts[], scientific_signals{}, summary_oneline | **2026-04-25 17:37Z (~5d STALE)** | per-pipeline `last_good_ts`, `sla_breach_count_24h`, `sla_breach_history_jsonl_url`, `freshness_ms`, `next_run_at`, `prev_run_at`, `mttr_min`. Currently boolean PASS/FAIL only — no time series. | `scripts/audit/run_pipeline_health.py` (not on disk — must be authored) | M |
| `data/audit/scientific-scorecard-latest.json` | ts, nba_pre{}, nba_post{}, pol_pre{}, pol_post{}, alpaca{} | **2026-04-25 14:00Z (~5d STALE)** | bootstrap CI95 (lo/hi) for every scalar; per-day arrays w/ ts+brier+wr+pnl; per-agent {tid, brier, wr, pnl, n, ci_low, ci_high, badges[]}; reliability buckets[10]; methodology_url; window_n. Pure rigid pre/post pair — no rolling story. | `tf_scientific_scorecard.py` (226 LOC) | L |
| `data/audit/scorecard-<ts>.json` (rotated) | ts, tfs.{nba,pol}.{wr_overall, brier_mean, source_purity_direct, fleet_pnl_window, per_day[], per_agent_top5/bottom5} | **2026-04-25 08:50Z (~5d STALE)** | CI95 around `wr_overall` and `brier_mean`; `n_agents_total`, `n_agents_active`; `per_day` lacks `wr_ci_low/hi` and `cum_pnl`; `per_agent` lacks `brier`, `confidence_n`, `kelly_cap`, `since_date`, `last_bet_at`. | `tf_scientific_scorecard.py` lines 138-175 | M |
| `data/audit/rigorous-<ts>.json` | ts, tfs.{nba,pol}.{ok, n_days, n_bets, brier{lo,mid,hi}, wr{lo,mid,hi}, pnl{lo,mid,hi}, ece, reliability[], walk_forward[], per_agent[]} | **2026-04-25 12:10Z (~5d STALE)** | This is the **best** file shape we emit — already has CIs + reliability + walk-forward. Still missing: per-bucket `ci_low/ci_high` (only `n` + `gap`); per-agent `brier_ci`, `wr_ci`; walk-forward window `start_date`/`end_date` (only day idx); `welch_t_stat` + `welch_p_value` keys (computed but never serialized). | `tf_rigorous_validation.py` (330 LOC) | S |
| `data/audit/cross-llm-latest.json` | ts, by_llm[].{llm, total_bankroll, tfs_present, total_bets, wr_combined, per_tf{}}, per_row[] | **2026-04-25 12:55Z (~5d STALE)** | `brier_combined`, `brier_per_tf`, `cost_per_call_usd`, `latency_p50_ms`, `decision_quality_score`, `llm_provider_health` (rate-limit / dead status), `since_date`, `n_dead_calls_24h`. Bankroll alone hides cost+latency tradeoff. | `tf_cross_llm_view.py` (214 LOC) | M |
| `data/audit/trajectory-latest.md` | (markdown only) | **2026-04-25 ~12:10Z (~5d STALE)** | **No JSON sibling** — frontend can't render charts from prose. Need `trajectory-latest.json` with `{tf, brier_series[{day, brier, ci_low, ci_high}], verdict, slope_per_day, p_value_trend}`. | `tf_trajectory_flash.py` (52 LOC) | S |
| `data/audit/digest-latest.md` | (markdown only) | **2026-04-26 00:14Z (~5d STALE)** | No JSON twin. Champion ledger lines show `?` for trader_id (line 44-48 of digest-2026-04-25.md). Path-to-$1M math one bullet only. | `daily_scientific_digest.py` (174 LOC) | S |
| `data/audit/coverage-report-latest.json` | unknown | **2026-04-26 00:14Z (~5d STALE)** | not opened — verify schema; likely missing per-day coverage time series. | unknown | M |
| `data/tf-analytics/summary.json` | ts, tfs.{nba,pol,itf,pqtf}.{day, date, fleet{}, source_file} | **2026-04-26 00:14Z (~5d STALE)** | `fleet.bankroll_history[]` (day, total, leader_bk, laggard_bk), `fleet.equity_ci95`, `fleet.sharpe_30d`, `fleet.max_dd_30d`, `fleet.unique_llm_count`. Latest snapshot only — no series. | unknown emitter (likely `per_agent_deep_audit.py`) | M |
| `data/tf-analytics/{nba,pol}/day-NNN.json` | tf, day_idx, date, written_at, fleet{}, per_agent{}, per_bet{}, per_category{} | **2026-04-26 00:14Z (~5d STALE)** | `per_agent.<tid>.confidence` (declared probability) — already in source decisions but dropped here; `per_agent.<tid>.brier_today`; `per_agent.<tid>.kelly_cap_used`; `per_agent.<tid>.bet_history_30d[]`. Has `day_strategy` text but truncated at 100 chars (line 37 of day-127.json). | unknown emitter | M |
| `data/tf-analytics/itf/day-YYYY-MM-DD.json` | tf, date, fleet{}, per_agent{}, per_bet{}, per_ticker{} | **2026-04-26 00:14Z (~5d STALE)** | only 2 days exist (2026-04-21, 2026-04-24) — gap of 3 days; `per_agent.<tid>.equity_history`, `realized_pnl`, `unrealized_pnl`, `n_open_positions`, `avg_holding_period_min`. | unknown emitter | M |
| `data/ops/itf-position-health.jsonl` | ts, equity, cash, long_mv, short_mv, buying_power, daytrade_count, n_positions, by_class{}, unrealized_pnl_total, top_losers[], top_winners[] | **2026-04-26 00:14Z (~5d STALE)** | Only **1 line in the entire file** — useless as a series. Need: `realized_pnl_today`, `realized_pnl_30d`, `sharpe_intraday`, `var_95`, `max_position_concentration_pct`, `pdt_warning_level`, `concentration_by_symbol[]`. | `itf_position_health.py` (95 LOC) lines 51-73 | S |
| `data/ops/quarantine.json` | quarantines{<space>:{active, days, expires_at, reason, set_at}}, updated_at | **2026-05-01 01:14Z (FRESH)** | `current_equity_at_set`, `current_equity_now`, `compounding_delta_pct` (the whole point of quarantine — but no metric tracks it!), `expires_in_days`. | `scripts/ops/tf_quarantine.py status` | S |
| `data/champions/index.json` | champions[].{bankroll, captured_at, days_traded, roi_pct, snapshot_path, tf, trader_id} | **2026-04-26 00:14Z (~5d STALE)** | `peak_bankroll`, `current_bankroll` (vs captured), `survived_resets[]`, `llm`, `seed_usd`, `multiplier_at_capture`. Index has duplicate snapshots (multiple captures per agent) — needs dedup-by-tid/agent or `current_only` flag. | `champion_preserve.py` (224 LOC) | S |
| `data/audit/latest.json` (symlink) | — | **BROKEN SYMLINK** → `/home/termius/mon-ipad/data/audit/2026-04-20T2348.json` (path doesn't exist on this VM) | dangling symlink. Emitter wrote with hardcoded foreign-host path. | unknown — investigate symlink creator | S |
| `data/ops/tf-baseline-history.jsonl` | (per CLAUDE.md should exist) | **MISSING ENTIRELY** | `tf_baseline_check.py` line 34 declares `HISTORY = OUT_DIR / "tf-baseline-history.jsonl"` — file never created on VM. Cron not running → no history → no PASS/FAIL trend chart. | `tf_baseline_check.py` (515 LOC) | S |
| `data/ops/tf-improvement-history.jsonl` | (per CLAUDE.md) | **MISSING ENTIRELY** | Same — `tf_improvement_cycle.py` cron output never landed on VM. | `tf_improvement_cycle.py` (322 LOC) | S |

---

## B. Top 10 Missing Fields (rank: frontend impact ÷ backend effort)

1. **`bootstrap_ci95: {lo, hi}` on every scalar in `scorecard-*.json` and `summary.json`** — unlocks all KPI cards with confidence bands. Already computed in `tf_rigorous_validation.py`; copy that pattern into `tf_scientific_scorecard.py:138-175`. Without this, every "Brier=0.40" tile lies by omission. **Impact: 10/10. Effort: S.**
2. **`per_agent[].brier`, `brier_ci`, `wr_ci`, `n_bets`, `kelly_cap`, `llm`, `since_date` in `scorecard-*.json`** — current `agent_summary` (line 153) only has bets/wins/pnl. Lab-grade leaderboard needs per-agent calibration + sample size + capacity (Kelly cap). **Impact: 10/10. Effort: S.**
3. **`reliability[].ci_low / ci_high` in `rigorous-*.json`** — Wilson/Clopper-Pearson CI per bucket. Line 192-220 has `n` + `avg_actual` but no error bars. Reliability diagrams without bars are misleading. **Impact: 9/10. Effort: S.**
4. **`trajectory-latest.json` JSON sibling to the .md** — `tf_trajectory_flash.py` (52 LOC) currently writes only markdown. Add a 5-line JSON dump with `{verdict, old_mean, new_mean, delta, brier_series[{day, brier}]}`. Without JSON, the dashboard cannot render the trajectory line chart that headlines every quant report. **Impact: 9/10. Effort: S.**
5. **`walk_forward[].start_date / end_date` (real dates, not day indexes)** — `rigorous-*.json` line 56-103 uses `day_idx`. Frontends need ISO dates for x-axis. **Impact: 8/10. Effort: S.**
6. **`fleet.bankroll_history[]` (per-day series) in `summary.json`** — currently single snapshot. Frontend can only render a number, not the equity curve that everyone actually wants to see. **Impact: 9/10. Effort: M.**
7. **`per_agent.confidence` carried into `tf-analytics/{nba,pol}/day-NNN.json`** — agents emit confidence in raw decisions; the day-rollup drops it. Without confidence per bet, no calibration curve, no Brier-per-day. **Impact: 9/10. Effort: M.**
8. **`brier_combined` + `cost_per_call_usd` + `latency_p50_ms` in `cross-llm-latest.json`** — current cross-LLM ranks by bankroll only. The user has spent weeks fighting LLM cost/dead-provider issues; the dashboard hides that signal. **Impact: 8/10. Effort: M.**
9. **`last_good_ts` + `freshness_ms` + `next_run_at` per pipeline in `pipeline-health.json`** — dashboard currently can't show a "stale 5 days" warning because the file itself doesn't expose freshness machine-readably (only human prose in `summary_oneline`). **Impact: 9/10. Effort: S.**
10. **`itf-position-health.jsonl` with >1 line + `realized_pnl_today`** — currently 1 line ever written. Sharpe/MaxDD/equity-curve charts need this jsonl as a real series. The script works (line 89 appends) — the cron isn't firing. **Impact: 9/10. Effort: S (fix cron, not code).**

---

## C. Top 5 Broken / Stale Files

1. **`data/audit/latest.json`** — **broken symlink** to `/home/termius/mon-ipad/...` (foreign machine path). Whoever wrote this used the wrong cwd. Frontend `fetch('/tf-analytics/latest.json')` will 404 silently. **Action: delete symlink, recreate as relative or rewrite emitter.**
2. **`data/ops/tf-baseline-history.jsonl`** + **`data/ops/tf-improvement-history.jsonl`** — both **missing entirely**. CLAUDE.md scientific-scorecard table promises them; cron output proves it never ran on this VM. **Action: SWITCHBOARD/INTERNAL AFFAIRS — verify crontab `:10` and `:20` are wired.**
3. **`data/ops/itf-position-health.jsonl`** — exactly **1 line** (2026-04-24T18:58Z). Cron should have written ~240 lines by now (every 30min × 5 days). **Action: verify `*/30` cron.**
4. **Whole `data/tf-analytics/` tree** — every file frozen at `2026-04-26 00:14:35`. The `:40 hourly` sync cron (`sync_tf_analytics_to_dashboard.sh`) hasn't fired in 5 days. Same for `data/audit/scorecard-*.json` (last `2026-04-25T0850Z`) and `rigorous-*.json` (last `2026-04-25T1210Z`). **The dashboard has been showing 5-day-old data**, which is the most likely root cause of user dissatisfaction.
5. **Schema drift between `summary.json` and `day-*.json`** — `summary.json` `tfs.itf` has `fleet_total_deploy_pct`, `day_total_decisions`, `n_unique_tickers`; `tfs.nba/pol` use `day_total_bets`, `jaccard_fleet_*`. ITF day files have `per_ticker` key, NBA/POL have `per_category`. Frontend cannot write one component for "TF day card" — needs branching. **Action: define a canonical TF day schema and emit normalized fields across all 4 TFs.**

Bonus stale: `data/audit/digest-2026-04-25.md` line 44-48 — champion ledger trader_ids show `?` (champion_preserve.py is failing to populate `trader_id` field in the digest's pull). Cosmetic but visible.

---

## D. Three Scripts to Upgrade First (5-line patch sketches)

### 1. `scripts/ops/tf_scientific_scorecard.py` (226 LOC) — **biggest dashboard payoff**
- Lines 138-156 build `wr`, `brier`, `agent_summary` as point estimates only. Add a `_bootstrap_ci(samples, n=1000, alpha=0.05)` helper (steal from `tf_rigorous_validation.py`).
- Replace `wr_overall: round(wr, 4)` with `wr: {value, ci_low, ci_high, n}`. Same for `brier_mean` and `fleet_pnl_window`.
- Extend `per_tid_bets` to track `confidences: list[float]` so `agent_summary` can emit `brier`, `brier_ci`, `kelly_cap` (read from `_AGENT_KELLY_OVERRIDE` map), `since_date` (first bet date), `llm` (use `tf_cross_llm_view.NBA_POL_LLM_MAP`).
- Emit `last_updated: _now().isoformat()` and `methodology_url: "https://github.com/.../tf_scientific_scorecard.py#L80"` at top level.
- New keys: `calibration_buckets[10]` produced from `(confidence, won)` pairs — same shape as `rigorous.reliability[]` so frontend reuses one chart component.

### 2. `scripts/ops/tf_trajectory_flash.py` (52 LOC) — **smallest fix, biggest unlock**
- Currently writes markdown only (line 43 `outp.write_text("\n".join(out))`). Add a parallel `outp_json = AUDIT / "trajectory-latest.json"` and dump `{ts, tfs:{<tf>:{verdict, old_mean, new_mean, delta, brier_series:[{window_idx, brier, n}], best_brier, latest_brier}}}`.
- Change verdict thresholds from raw 0.01 to standard-error-aware: `verdict = "IMPROVING" if delta < -1.96 * stderr else ...` (uses bootstrap stderr from rigorous file).
- Carry `walk_forward[].start_day / end_day / n` straight through into `brier_series[]` so the frontend can chart with proper sample-size weighting.
- Compute trend slope (linregress over briers) + p_value; emit `slope_per_window`, `p_value_trend`. Tells the user whether the trend is real or noise.
- Five-line addition gives the dashboard its single most important chart: "is our edge improving?"

### 3. `scripts/ops/tf_cross_llm_view.py` (214 LOC) — **cross-market truth**
- Lines 91-114 (`_nba_pol_snapshot`): currently pulls only bankroll/wins/losses from `/api/leaderboard`. Also fetch `/api/llm-health` (or `data/audit/llm-health.json` line ~265KB jsonl) and join `cost_usd_per_call`, `latency_p50_ms`, `dead_count_24h` per LLM.
- Line 138 (`_aggregate_by_llm`): sum `total_bets`, `total_wins`, `total_losses` already done — add `total_brier_weighted = sum(brier * n) / sum(n)` once `per_tf` carries `brier` (depends on Patch #1 landing first).
- New top-level field `dead_providers_24h` (list of LLMs with >5 dead calls) so the dashboard can render a red-stripe banner — directly answers "which providers are flaky?"
- Output a `cross-llm-history.jsonl` (append every 4h) so frontend can render LLM-bankroll-time-series stacked-area chart.
- Add `since_date` per LLM (first observation in cross-llm-history) so the leaderboard can sort by "LLMs that survived ≥7 days" — a strong quality filter.

---

## E. One-line Recommendation to THE BOSS

**Before commissioning any frontend redesign, fix the cron stoppage** (`*/40 hourly` `sync_tf_analytics_to_dashboard.sh`, `:50` scorecard, `:10` rigorous, `*/30 min` itf-position-health, `:20` improvement-cycle) — every chart has been showing 5-day-old numbers. **Then** ship Patch #1 (CI bands in scorecard) and Patch #2 (trajectory JSON) — they alone unlock ~70% of the visual upgrade with <100 LOC of changes across two files.

---
*Read-only audit. No files modified outside `data/audit/dashboard-2026-05-01/`.*
