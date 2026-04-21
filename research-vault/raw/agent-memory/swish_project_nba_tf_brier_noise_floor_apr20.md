---
name: nba_tf_brier_noise_floor_apr20
description: NBA TF MIN_EDGE must exceed the fleet-best Brier vs random noise envelope, not sit inside it — why 0.04 failed and 0.06 is the right floor
type: project
---

2026-04-20: Raised NBA TF `_tiered_risk()` MIN_EDGE 0.04 → 0.06 on survival
tiers (<$25, <$50, <$100, <$500) and prompt-display floor in `_build_prompt`
0.01 → 0.03. PROVEN/MOONSHOT/CHAMPION tiers ≥$500 untouched (0.04/0.05/0.05).
Commit SHA on LBJLincoln26/nba-llm-trading-floor: `6ea565ea4f13`.

**Why:** 128-day bleed. qwen-quant went 7W/37L = 16% WR over 44 bets. Every
LLM agent crashed to $3-7. The ONE agent that survived at $7.28 (selfhost-gemma3)
had `llm_ok=0` for all 128 days and traded 195 bets via uniform-fallback —
the dumbest baseline beat every LLM persona. Fleet-best Brier (S22) = 0.22073
vs random 0.25, so the model's demonstrable information gain over random is
only **0.029 Brier-points**. A MIN_EDGE of 0.04 sat INSIDE that calibration-error
envelope, so agents were forced to stake on "edges" smaller than the model's
own uncertainty. The prompt-display floor of 0.01 let them see noise-edges in
the first place.

**How to apply:**
- Any future NBA TF MIN_EDGE tuning must stay **≥ 2× (0.25 − fleet_best_Brier)**.
  Today: 2 × 0.029 ≈ 0.058, rounded to 0.06.
- When S22 (or its successor) improves Brier, the envelope shrinks and this
  floor can relax. Recheck `fleet_best_bankroll` reports after each S22 gen
  bump; if Brier drops below 0.215, consider 0.06 → 0.05 on <$100 tiers.
- NEVER lower MIN_EDGE just because agents are "sitting on cash." Cash is
  correct when no real edge exists. MIN_DEPLOY_PCT drawdown-relax (line 2134)
  already handles the survival case.
- This rule applies NBA-only for now. POL agents get different signal
  (excess_return / event outcomes); they have their own gate. PQTF uses
  VaR-based sizing, not edge-threshold.
- Kill criterion for this change: 20 days post-reboot, if fleet_total_bets <
  0.3× pre-change rate AND fleet_avg < $95, revert to 0.04 (checkpoint at
  `data/nba-tf/checkpoints/pre-minedge-raise-20260420T231039Z.json`).
