# NBA Research Proposal: SHAP-Informed Efficiency Ratio Features (Cat51)

**Cycle:** 95  
**Date:** 2026-04-12  
**Source:** Nature Scientific Reports 2025 — "Stacked ensemble model for NBA game outcome prediction analysis" (PMC12357926)  
**Rotation:** A (every-other-cycle NBA research)  
**Priority:** HIGH — addresses identified model weakness  
**Target Islands:** S13 (catboost), S15 (wide_search) — deploy when awake  
**Expected Brier Delta:** -0.002 to -0.004  

---

## Key Finding from Research

The 2025 Nature stacked ensemble paper (83.27% accuracy, AUC 0.9213) performed SHAP analysis
on all features. Critical result:

| Feature | SHAP Impact | Direction |
|---------|------------|-----------|
| FGA (field goal attempts) | HIGH | **NEGATIVE** — more attempts → predicts loss |
| 2PA (2-point attempts) | HIGH | **NEGATIVE** — same pattern |
| FG (field goals made) | HIGH | POSITIVE |
| TRB (total rebounds) | HIGH | POSITIVE |

**Interpretation:** Raw shot attempt counts are misleading — teams shooting more are often
in high-paced games or losing late (volume shooting to catch up). The GA is including
FGA/2PA as noise features that hurt calibration.

**Solution:** Replace or supplement raw counts with **efficiency ratios** that encode
the quality signal directly.

---

## Proposed Features (Cat51 — Efficiency Ratio Metrics)

All features are CPU-feasible (pure division), derive from existing Cat05/Cat10 data,
and can be added to features/engine.py without new data sources.

### Primary Features

```python
# Cat51 — SHAP-Informed Efficiency Ratio Metrics

# 1. Effective FG% differential vs. opponent defensive rating
# Encodes: are we more efficient than they defend?
'tc51_efg_vs_opp_def': team_efg_pct - opp_efg_allowed_season,

# 2. True Shooting momentum (10-game vs season baseline)
# Encodes: are we getting more efficient recently? (temporal form)
'tc51_ts_momentum_10g': ts_pct_10g_rolling - ts_pct_season,

# 3. FG efficiency ratio (made/attempted) — direct SHAP-correction
# Encodes: quality over quantity (the key finding)
'tc51_fg_efficiency': fg_made / (fg_attempted + 1e-6),

# 4. Shot quality adjusted scoring rate
# Encodes: 3Ps count 1.5x corner, 2Ps count 0.8x (zone-weighted)
'tc51_shot_quality_adj': (fg2_made * 0.8 + fg3_made * 1.5) / (fga + 1e-6),

# 5. Defensive efficiency: opponent FGA generated
# Encodes: forcing more attempts (opponent) = defensive dominance
'tc51_opp_fg_allowed_ratio': opp_fga_allowed / (opp_fga_season_avg + 1e-6),

# 6. Paint vs perimeter ratio (2PA/3PA differential)
# Encodes: perimeter-heavy offense shifts under defensive pressure
'tc51_paint_perimeter_ratio': fg2_attempted / (fg3_attempted + 1e-6),

# 7. Points Per Shot Attempt (comprehensive efficiency)
'tc51_ppa': pts / (fga + 0.44 * fta + 1e-6),

# 8. Rebound efficiency leverage
# TRB positive SHAP — amplify by opponent ORB rate
'tc51_reb_leverage': trb / (opp_trb + 1e-6),
```

### Implementation in features/engine.py

Add Cat51 block after Cat50 (overround features) in `_build_feature_candidates()`:

```python
# ── Cat51: Efficiency Ratio Metrics (SHAP-driven, cycle 95) ──────────────
# Addresses negative SHAP of raw FGA/2PA found in Nature 2025 ensemble study.
# Convert raw counts → quality ratios for cleaner signal.
_add_category(51, [
    ('efg_vs_opp_def',        efg_pct - opp_efg_allowed),
    ('ts_momentum_10g',       ts_pct_10g - ts_pct_season),
    ('fg_efficiency',         fg / (fga + 1e-6)),
    ('shot_quality_adj',      (fg2 * 0.8 + fg3 * 1.5) / (fga + 1e-6)),
    ('opp_fga_gen_ratio',     opp_fga / (opp_fga_avg + 1e-6)),
    ('paint_perimeter_ratio', fg2a / (fg3a + 1e-6)),
    ('ppa',                   pts / (fga + 0.44 * fta + 1e-6)),
    ('reb_leverage',          trb / (opp_trb + 1e-6)),
], home=True, away=True, diff=True)  # 24 candidates (8 × home/away/diff)
```

---

## Why This Works

The critical insight: **our GA selects from candidates, so if we include both raw
counts AND efficiency ratios, the GA will naturally select the ratios and drop the
raw counts** — achieving the effect found by SHAP analysis without manually removing
features. The ratios encode the same information more cleanly.

Supporting evidence:
- Tabular ICL (best run, Brier 0.21570) likely does implicit feature normalization
- Our current best CPU Brier: 0.21906 (S15, gen 864)  
- Gap to checkpoint: 0.00069
- Cat51 features give the GA better building blocks to close this gap

---

## Implementation Checklist

- [ ] Add Cat51 block to `features/engine.py` (lines ~950-980, after Cat50)
- [ ] Add Cat51 to `hf-space/features/engine.py` (parity — OBLIGATOIRE Rule 2)
- [ ] Verify `_add_category(51, ...)` works with existing infrastructure
- [ ] Update `FEATURE_ENGINE_VERSION` to `v3.1-60cat`
- [ ] Run smoke test: `python features/engine.py --test` (or equivalent)
- [ ] Deploy to S13 first (catboost specialist), monitor Brier for 50 gens
- [ ] If Brier improves, deploy to S15 (closest to checkpoint)

**Target feature count:** 200 max (current + 24 Cat51 candidates)  
**Engine version after:** v3.1-60cat (from v3.1-59cat)  
**Deploy when:** S13/S15 wake from 503  

---

## Cross-Project Relevance

The efficiency ratio approach is also applicable to **Political Alpha**:
- Political features currently use raw counts (contribution amounts, filing counts)
- Could create velocity/efficiency ratios for campaign finance signals
- e.g., `donations_per_event` vs raw `total_donations` — the ratio may be more predictive
  of polling momentum than the absolute amount

---

## Sources

- [Stacked ensemble model for NBA game outcome prediction analysis (PMC12357926)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12357926/)
- [Uncertainty-Aware Machine Learning for NBA Forecasting (MDPI 2078-2489/17/1/56)](https://www.mdpi.com/2078-2489/17/1/56)
- [Machine Learning for Basketball Game Outcomes: NBA and WNBA (MDPI 2025)](https://www.mdpi.com/2079-3197/13/10/230)
