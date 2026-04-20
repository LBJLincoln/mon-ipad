# Cat 66 Canary Plan — `v3.1-66cat`

**Date**: 2026-04-20
**Owner**: DR FRANKENSTEIN (impl) → SWISH (canary)
**Source paper**: MDPI Information 17(1):56 (Jan 2026) — *Uncertainty-Aware ML for NBA Forecasting*
**Port origin**: nomos-nba-agent/features/engine.py (authored Apr 19) → mon-ipad/features/engine.py + hf-space mirror (ported Apr 20)

---

## What Cat 66 adds

**12 Pace-Normalized Per-100 Possession Box-Score Differentials**, computed as rolling 10-game means per team:

| Feature | Definition |
|--|--|
| `p100_66_h_pts`, `_a_pts`, `_diff_pts` | Offensive rating (pts × 100 / poss), home/away/diff |
| `p100_66_h_ast`, `_a_ast`, `_diff_ast` | Assists per 100 possessions (PROXY via ast_rate × 25) |
| `p100_66_h_tov`, `_a_tov`, `_diff_tov` | Turnovers per 100 (PROXY via tov_rate × 85; diff is Away-Home) |
| `p100_66_h_reb`, `_a_reb`, `_diff_reb` | Total rebounds per 100 (PROXY via (oreb+dreb)_pct × 45) |

## Why it should help

- Removes pace confounding from raw counting stats (high-pace teams no longer inflate raw totals).
- Matches how modern NBA analysts measure true efficiency.
- Expected Brier delta from paper: **-0.002 to -0.004** (0.22073 fleet-best → 0.21673-0.21873 target on S22).

## Math caveats (flagged in parity-check JSON)

- **pts**: mathematically faithful (ortg reused).
- **ast / tov / reb**: all use `rate × constant` shortcuts, not the paper's exact `stat × 100 / poss` formula.
- Resulting values are **monotonic** to true per-100 values but numerically undercook ast (~13 vs ~25 league-true), tov (~7.5 vs ~14), reb (~39 vs ~44).
- Genetic selection will prune if useless. If selected AND underperforming, **HAWKEYE escalation** for v2 math rewrite.

---

## Canary rollout (SWISH, next mutation cycle)

### Step 1 — S22 first
- **Target**: `Nomos42/nba-evo-s22` (TESTforge42 account)
- **Rationale**: fleet-best Brier 0.22073 (venn_abers_fusion, gen 39, checkpointed 2026-04-19). Any regression from Cat 66 shows up fastest on the tightest island.
- **Action**: upload new `features/engine.py` (sha `5e66371c4a39ea42ea76457ea83e3ee3175a203dc6823e5a8ace646015565cba`) via `HfApi.upload_file` on next SWISH mutation tick. `factory_reboot=True`.
- **Wait**: 3 evaluation cycles (≈ 3 generations × ~30 min on S22 = ~1.5h).

### Step 2 — Evaluate
- PASS criteria (promote to fleet):
  - S22 Brier moves to **≤ 0.22073** (no regression) AND
  - At least **1 of 12** Cat 66 features gets selected into S22's active feature set, OR
  - Feature importance (permutation) for selected Cat 66 features > median of other cats.
- FAIL criteria (revert S22, do not fleet-promote):
  - S22 Brier > 0.22200 after 3 gens (regression > 0.001 is not noise at this scale) OR
  - Exception in feature generation (NaN, shape mismatch, exception in build loop).

### Step 3 — Fleet promotion (SWISH decision, if PASS)
- Roll out to S13, S14, S15, S17, S18 in that order, one per mutation cycle. Watch each island's Brier after 3 gens.

### Step 4 — Cross-repo parity
- After fleet promotion, SWISH confirms `nomos-nba-agent` island deploys also carry v3.1-66cat.

---

## Rollback recipe (if kill-criterion triggers)

1. `git revert <Cat 66 commit>` in mon-ipad
2. `cp /home/termius/mon-ipad/features/engine.py /home/termius/mon-ipad/hf-space/features/engine.py`
3. SWISH redeploys v3.1-65cat to S22
4. DR FRANKENSTEIN files follow-up proposal with HAWKEYE flag re: ast/tov/reb math correction

---

## Ledger entry (to append)

```json
{
  "ts": "2026-04-20T23:45:00Z",
  "agent": "DR_FRANKENSTEIN",
  "feature_name": "p100_66_pace_normalized_per_100_box_score_diffs",
  "category": 66,
  "target_engine": "NBA",
  "files_changed": [
    "features/engine.py",
    "hf-space/features/engine.py"
  ],
  "sha256_after": "5e66371c4a39ea42ea76457ea83e3ee3175a203dc6823e5a8ace646015565cba",
  "engine_version_before": "v3.1-65cat",
  "engine_version_after": "v3.1-66cat",
  "n_features_added": 12,
  "total_feature_candidates": 6446,
  "expected_brier_delta": -0.003,
  "canary_island": "S22",
  "source_paper": "MDPI Information 17(1):56 Jan 2026",
  "math_review": "pts-faithful, ast/tov/reb proxies (monotonic but undercooked scaling). Acceptable v1.",
  "parity_check_path": "data/ops/engine-parity-check-2026-04-20.json"
}
```
