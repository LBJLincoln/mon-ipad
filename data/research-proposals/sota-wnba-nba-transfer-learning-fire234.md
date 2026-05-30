# SOTA: WNBA→NBA Multi-Task Transfer Learning

**Fire**: 234 (EVEN WebSearch)
**Source**: MDPI 2079-3197/13/10/230 (2026) — "Machine Learning for Basketball Game Outcomes: NBA and WNBA Leagues"
**Priority**: 109
**Work-queue ID**: vm-research-wnba-nba-transfer-learning-fire234

## Key Finding

WNBA games are structurally identical to NBA (same rules, court dimensions, scoring) but provide **orthogonal prediction signal**:
- Different pace (slower, more physical in 2025-26)
- Smaller rosters → fewer substitution confounders
- Shorter season → cleaner temporal CV splits
- Same home/away fatigue dynamics → transferable schedule features

This creates a natural auxiliary domain for multi-task learning: pre-training or jointly training on WNBA can regularize NBA models and reduce overfitting on high-dimensional feature spaces.

## Applications

### Application 1: Joint Multi-Task Loss
Add WNBA prediction as auxiliary task with shared feature encoder:
```python
loss_total = loss_nba + 0.1 * loss_wnba
```
Expected: better-calibrated features in the 200f regime where NBA data is sparse.

### Application 2: WNBA Feature Importance as Prior
Pre-compute SHAP rankings on WNBA data (cleaner signal, less correlated features). Use WNBA top-K features as a prior for NBA feature selection — filters spurious NBA-specific noise.

### Application 3: Cross-Sport Calibration Holdout
Train NBA Brier calibration (isotonic/Venn-Abers) using WNBA as a held-out distribution. Tests calibration generalization beyond NBA temporal splits.

### Application 4: POL Domain Analog
Port concept to political_engine.py:
- Use **state legislative races** as auxiliary domain for federal race prediction
- Same party dynamics, polling mechanics, incumbency effects
- Larger N (more races per cycle) → regularization benefit

## Expected Improvement
- 0.001–0.003 Brier reduction (domain adaptation + auxiliary supervision literature)
- Particularly valuable for 200f feature spaces where NBA training data is thinner per feature

## Library Stack
- `sklearn.multioutput.MultiOutputClassifier` for joint training
- XGBoost/LightGBM multi-task via custom objective
- MAPIE for calibration holdout testing

## Related Work
- arXiv:2410.21484 (fire-228): ET > RF on 200f, Venn-Abers strongest calibration
- arXiv:2506.12183 (fire-230): Sliding-window CV for non-stationary time series
- IEEE 2024 (fire-232): `home_next` top-3 feature — transferable to WNBA
