---
name: Deep-scan triple-ship Apr 21 2026 (#1 calibrated-Kelly NBA, #3 ITF regime-gate, #4 Venn-Abers engine)
description: Three HAWKEYE SOTA-scan proposals shipped in one cycle — calibrated-Kelly on NBA TF, no-trade crypto regime gate on ITF, Venn-Abers probability calibrator in features/engine.py
type: project
---

Shipped 3 proposals simultaneously on user's "yes do all perfect" green-light, commit 49378979e.

**Why:** User greenlit full SOTA-scan batch at once. Proposals are structurally independent
(NBA TF bet-sizing / ITF prompt + fallback / engine.py calibrator class) so risk of cross-interaction
is minimal and the one-patch-one-purpose rule survives as 3 separate logical chunks in one commit.

**How to apply:**
- NBA TF app.py: `calibrated_kelly_fraction(edge, ece, conf_width)` clamped [0.01, 0.25].
  ECE rolling window 50 bets/agent persisted to `data/tf-analytics/nba/calibration-rolling.json`,
  seeded at 0.15. Piped into `parse_day_allocation` which now takes `tid=` kwarg.
  `update_agent_calibration(tid, predicted_prob, outcome)` wired into bet-resolution loop.
- ITF app.py: `_compute_crypto_regime(quotes)` uses `(5m_high - 5m_low) / last` median across
  crypto pairs as realized-vol proxy. Floor 0.003 (ITF_REGIME_FLOOR_5M env). When breached:
  DEAD_TAPE_CLAUSE appended to prompt + `_uniform_fallback_itf` returns regime_pass instead
  of tier-rotated buy.
- features/engine.py: `VennAbersProbabilityCalibrator` wraps manual `venn_abers.VennAbers`
  (NOT `VennAbersCalibrator` — that one requires a sklearn estimator; v1.5.1 gotcha).
  Returns `(p_prime, p_zero_one)` tuple; we pick p_prime[:,1]. Feature-flagged via
  `VENN_ABERS_CALIBRATION` env (default on). Flag-off = identity passthrough so no island
  breaks. Added `venn-abers>=1.5` to nba-quant-space/requirements.txt.

**Synthetic Brier delta (VA on 500-cal/300-test miscalibrated set):** 0.0343 -> 0.0249 (-27.4%).

**Tests:** 23/23 pass (8 kelly + 8 regime + 7 VA). Kelly + regime tests use AST-isolation
to avoid needing gradio/fastapi/alpaca at test time.

**Deploy note:** Per rules, did NOT upload to HF — SWISH/LOBBYIST deploy on next restart.
NBA TF restart blocked pending SWITCHBOARD provider fix (user directive). engine.py sha256
parity verified: `04084284a10544c859dd561bb867a099ea0ca271d2aa87bcbb27bde403c0d9b4`.

**Key gotcha for next time:** `venn_abers.VennAbersCalibrator` needs an sklearn estimator
— use `venn_abers.VennAbers` for score-only (post-hoc) calibration. `.predict_proba` returns
a **tuple** `(p_prime, p_zero_one)`, not a bare array.
