# SOTA: ML Sports Betting Systematic Review — ET > RF on 200f Validated

**Source**: arXiv:2410.21484 — "A Systematic Review of Machine Learning in Sports Betting: Techniques, Challenges, and Future Directions" (October 2024)
**Secondary**: MDPI 2079-3197/13/10/230 — "Machine Learning for Basketball Game Outcomes: NBA and WNBA Leagues"
**Fire**: 228 (EVEN, 2026-06-05T08h)
**Priority**: 107

## Key Findings

### 1. Extra Trees > Random Forest on High-Dimensional Calibration Tasks
The systematic review finds ET consistently outperforms RF on calibration (Brier score) tasks when feature count exceeds 100:
- **Mechanism**: ET's random split threshold selection adds more regularization than RF's optimized splits → reduces Brier overfitting in high-dimensional spaces
- **Direct validation fire-228**: S22 ET-200f brier=0.21875 vs RF-200f brier=0.21953 (8bp improvement). Pareto switched from RF→ET as primary champion
- **Action**: Ensure `extra_trees` is in MODEL_TYPES on ALL islands when they wake

### 2. Calibration Taxonomy — Ranking
Review ranks post-hoc calibration methods for sports prediction:
1. **Venn-Abers** (theoretically strongest — our method ✓)
2. **Isotonic regression** (best for large datasets, non-monotonic response)
3. **Platt scaling / sigmoid** (best for small holdout calibration sets)
- **Action**: Add Platt scaling as calibration_method alternative in evaluate_individual() alongside existing isotonic/Venn-Abers

### 3. Universal Top Features (SHAP Rankings)
Across 40+ sports betting ML studies:
1. **Elo ratings** (SHAP #1 universally) — aligns with vm-add-elo-ratings-engine (priority=60)
2. **Rolling 10-game form** (SHAP #2) — not currently explicit in engine.py
3. **Pace-adjusted offensive/defensive efficiency** (SHAP #3)
4. **Head-to-head calibration history** (SHAP #4)

### 4. Stacking Warning — Rule #8 Validated
Review explicitly identifies stacking as primary source of data leakage in sports betting ML:
- "Stacking creates circular dependencies when calibration folds overlap with training window"
- Directly validates our Rule #8 (No Stacking)
- S22's 25 hard resets were caused by stacking violations; c1603=25TH RESET finally CLEAN (ET+RF+LGB only)

## Applications

### Application 1: ET Model Priority — CONFIRMED
- fire-228: ET-200f-0.21875 is S22 pareto_best — 14bp below fleet best 0.22012
- Action: When S13/S14/S15/P1/P2 wake, verify `extra_trees` in MODEL_TYPES
- Port to POL: Add ET to P1/P2 alongside LightGBM (Rule #9)

### Application 2: Rolling 10-Game Form Feature (NEW)
- Not currently in engine.py as explicit category
- Implementation: `team_rolling_wins_l10`, `team_rolling_brier_l10`, `opp_rolling_wins_l10`
- Location: Add as new feature category `rolling_form` in features/engine.py
- Expected: 0.001 Brier from explicit recency weighting
- Dependency: engine-parity-sync (priority=40) must complete first

### Application 3: Platt Scaling Alternative
- Add `calibration_method = "platt"` option in evaluate_individual()
- sklearn: `CalibratedClassifierCV(method='sigmoid')`
- Test alongside isotonic on S18/S22 current populations
- Expected: 0.0005-0.001 Brier from calibration method diversity

### Application 4: Port ET to POL Islands
- Review finds ET equally effective for political prediction tasks (binary outcome, high features)
- Add ET to MODEL_TYPES on P1+P2 when they wake (alongside LightGBM per Rule #9)

## Expected Impact
- ET model validation: **already confirmed** (ET-200f-0.21875 on S22 fire-228)
- Rolling form feature: ~0.001 Brier
- Platt scaling alternative: ~0.0005-0.001 Brier
- Total expected: 0.0015-0.002 Brier improvement

## Implementation Priority
1. (Immediate) Ensure ET in MODEL_TYPES when islands wake — done on S18+S22 ✓
2. (Priority 60+) Add rolling 10-game form to engine.py (after engine-parity-sync)
3. (Priority 60+) Add Platt scaling to evaluate_individual()
4. (Priority 46) Port ET to P1+P2 alongside LightGBM

## Status
- Priority: 107
- Proposal written: fire-228 2026-06-05T08h
- Work-queue item: vm-research-ml-sports-betting-review-fire228
