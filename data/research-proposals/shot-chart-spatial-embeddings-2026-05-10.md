# SOTA Proposal: Spatial Shot-Chart Embeddings for NBA Prediction

**Date:** 2026-05-10 (fire-79)
**Source:** MDPI 2078-2489/17/1/56 (MC-dropout LSTM, Jan 2026); MDPI 2079-3197/13/10/230 (CNN 2025)
**Priority:** HIGH — first architectural path to sub-0.21 Brier

## Findings

- CNN achieves Brier 0.221 (MDPI 2025) — now slightly above our fleet best 0.22012
- MC-dropout LSTM with shot-chart embeddings: sub-0.20 Brier target plausible
- Key differentiator: **spatial shot-chart embeddings** encode where shots are taken, not just counts
- MC-dropout at inference (N=50 passes) → calibrated probability distributions → better Kelly sizing
- Strict chronological split (train ≤2022, val 2023, test 2024) prevents window bias

## Feature Engineering Proposal

New feature category for `features/engine.py`: `spatial_shot_chart` (10-15 features)

```python
# Shot zone efficiency by court region (NBA API: /v1/stats/shotchartdetail)
# Zones: restricted_area, paint_non_ra, mid_range, left_corner_3, right_corner_3, above_break_3
shot_zone_efg_restricted_area_home   # eFG% in restricted area, home team, 7-day rolling
shot_zone_efg_restricted_area_away
shot_zone_efg_paint_non_ra_home
shot_zone_attempt_rate_corner3_home  # corner 3 attempt rate (high-value shot selection)
shot_zone_attempt_rate_corner3_away
shot_zone_vs_defense_delta_home      # team shot zone efficiency vs opponent defensive zone
shot_chart_entropy_home              # shot distribution entropy (higher = more varied attack)
shot_chart_entropy_away
shot_zone_transition_pct_home        # % of shots from transition (pace signal)
```

## Why This Works

1. Shot location encodes **team strategy** that aggregate stats (3PA, FGA) miss
2. Corner 3s are highest-value shots — teams that generate them have structural edge
3. Shot entropy differentiates adaptable offenses from predictable ones
4. These features exist in NBA API shot chart data (already partially in engine as raw 3P%)

## Implementation Path

1. **VM:** Add `spatial_shot_chart` category to `features/engine.py` (10 new features)
2. **GA:** Features will be selected/weighted by S13/S14/S15 islands naturally
3. **Validate:** Check if feature importance rises in top-performing individuals
4. **No GPU needed:** Tree models handle spatial features natively

## MC-Dropout for Kelly Sizing (Secondary)

- Current Kelly: uses single-point Brier estimate per agent
- MC-dropout upgrade: run N=50 forward passes, use variance of predictions as uncertainty
- High variance → reduced Kelly stake (uncertainty-aware sizing)
- Implementation: only applicable to neural models; tree models use calibrated OOB probabilities
- **Fleet verdict:** Skip MC-dropout for islands (CPU tree-only). Apply to TabICL Colab models.

## Expected Impact

- Shot-chart features: est. +5-10 features in top-50 selected; potential 0.001-0.003 Brier improvement
- Fleet best target: 0.22012 → <0.219 with 3 cycles of GA selection
- Cross-project: shot-location proxy features can be added to political engine (not applicable)

## Status

- [ ] VM: add `spatial_shot_chart` category to features/engine.py
- [ ] VM: sync to nomos-nba-agent (engine-parity-sync work-queue item)
- [ ] GA: natural selection over 2-4 fire cycles
- [ ] Validate: check feature_importance in S15 (fleet best) checkpoint
