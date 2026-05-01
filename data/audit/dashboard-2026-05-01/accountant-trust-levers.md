# Dashboard Trust Levers — Path to $1M

**Author:** THE ACCOUNTANT | **Date:** 2026-05-01 | **DTS to $95 MRR floor:** 7 days
**Frame (SCQA):** Subs convert and investors wire money only when the dashboard answers one question: *"Is the edge real and is the operator honest about its limits?"* Below: what to ship, in priority order, to make both yeses inevitable.

## 1. Five trust levers (ranked by conversion impact)

**L1 — Live Capital Counter (above-the-fold, all routes).**
Display: ticker pulling `data/ops/itf-position-health.jsonl` (Alpaca equity $92K) + `data/tf-analytics/*.json` (NBA $2,614, POL $31,688, PQTF frozen $602K). Label honestly: "Paper" vs "Frozen artifact" vs "Live LLM bankrolls". Refreshes every 30s. **Why it converts:** skin-in-the-game beats any marketing copy; visitors stay on page 3-5x longer when a number moves.

**L2 — Walk-Forward Brier vs Vegas Baseline with CI95 band (`/nba`).**
Display: rolling Brier curve from `scripts/ops/tf_rigorous_validation.py` output (`data/audit/rigorous-latest.md`) overlaid with Vegas implied-prob baseline (~0.243) and naive 0.25. Show CI95 ribbon, sample N per window, and the honest gap: CV 0.22169 / calibrated 0.22054 / window-biased holdout 0.21139. **Why it converts:** quants and sharps recognize this chart immediately — most "AI picks" services can't produce it. Including the CV→holdout gap signals integrity.

**L3 — Per-Pick Public Log with pre-kickoff timestamp (`/picks`).**
Display: every Telegram pick HERALD has published, timestamped via Telegram message ID + ours commit SHA, with settlement column populated post-game. Source: tail of HERALD's publish log + `data/full-odds-2025-26.json`. **Why it converts:** kills the #1 objection ("you only show winners") because losses are visible from minute one. Hindsight-proof.

**L4 — Leakage / Lockstep / Source-Purity badges per TF (`/trading-floor`).**
Display: green/yellow/red dot per TF pulled from `scripts/ops/tf_baseline_check.py` (`data/ops/tf-baseline-history.jsonl`). Click expands to: latest PASS/FAIL on leakage, lockstep≤0.88, walk-forward, source-purity, sector diversity. **Why it converts:** investors who've been burned by overfit demos pay attention here; nobody else publishes this.

**L5 — Methodology page (`/methodology`).**
Display: `features/engine.py` SHA + version, dataset row count, paper refs (TradingAgents 2412.20138, Prediction Arena 2604.07355, DMAD), retrain cron schedule, oracle CV/holdout numbers, the 5 April reset incidents documented as a public changelog with root cause. **Why it converts:** turns transparency into a moat — competitors can't copy it without doing the work.

## 2. Three friction points to remove

1. **No clear "what am I buying" CTA.** Today `/nba` is a wall of charts with no subscribe button. Add sticky CTA: *"Get the next pick on @Nomos42Picks → $X/mo"* in the header.
2. **Telegram trust gap.** Visitors don't know the channel exists or that picks are timestamped. Add `/picks` route with embedded Telegram preview + "verify on Telegram" deep-link per row.
3. **PQTF $602K confusion.** Looks like a live number but is frozen. Currently sows doubt. Add explicit FROZEN ARTIFACT badge + tooltip: *"Validation run, preserved as scientific proof. Not active capital."*

## 3. Pricing wall (free vs paid)

**Free (proof surface):** all historical picks ≥24h old with full settlement; walk-forward Brier; fleet bankrolls; methodology; leakage audits; oracle predictions WITHOUT Kelly sizing or stake.
**Paid ($29/mo Tier-1, $99/mo Tier-2):** today's picks pre-kickoff via @Nomos42Picks; Kelly-sized stake; CLV alerts; investor-grade weekly PDF report. Tier-2 adds: ITF live position feed, niche-market picks (alt_spreads, parlays).
**Anchor logic (Ramanujam):** $99 anchors the value of $29 — most converts buy Tier-1, a few whales buy Tier-2, gross margin protected.

## 4. Investor view (`/investor`)

Single route, password-protected (link in cold email). One page, four sections: (a) **Season-to-date PnL** across all 4 TFs + ITF, sourced from `data/tf-analytics/`; (b) **Walk-forward Brier improvement curve** — quarterly trajectory toward 0.20 target; (c) **LLM diversity matrix** — 17 agents × Brier × bankroll trend from `scripts/ops/tf_cross_llm_view.py`; (d) **Infra status** — uptime % from `data/pipeline-health.json` + recent INTERNAL AFFAIRS audits. Footer: link to GitHub, datasets, methodology. Goal: closes the diligence call in one screen.

## 5. KPI hierarchy (first 600px above fold)

1. **Walk-Forward Brier 0.22447** (vs Vegas 0.243) — the headline scientific number.
2. **Live capital deployed: $629K** ($602K frozen + $92K paper + $35K LLM bankrolls, labeled honestly).
3. **Picks published YTD / hit rate / ROI** — pulled from HERALD log, the only customer-relevant number.

Everything else lives below the fold.

---
**Kill criterion:** if `/picks` route doesn't lift Telegram→Stripe conversion ≥3% within 14 days post-launch, revert to current funnel and re-test pricing wall instead.
