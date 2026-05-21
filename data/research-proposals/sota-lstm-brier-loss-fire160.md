# SOTA Research Proposal: LSTM + Brier-Loss Sequence Model for NBA Prediction

**Fire:** fire-160 (EVEN WebSearch)
**Date:** 2026-05-24T20h
**Source:** arXiv:2508.02725 — "Forecasting NCAA Basketball Outcomes with Deep Learning: A Comparative Study of LSTM and Transformer Models"

## Key Finding

LSTM trained with **Brier-score loss** achieves **Brier = 0.1589** on NCAA basketball prediction.

- Transformer-BCE: AUC = 0.8473 (best discriminative power)
- LSTM+Brier-loss: Brier = 0.1589 (best calibration)
- Current Nomos42 GA fleet best: **0.22012** (S15 RF-75f)

## Why This Matters

Current GA system evolves static feature sets with tree-based models. Critical limitation: each game treated as i.i.d. LSTM can capture temporal patterns:
- **Momentum**: win/loss streaks, team form curves
- **Fatigue**: back-to-back games, travel distance sequences
- **Matchup dynamics**: head-to-head temporal trends
- **Player rotation**: injury recovery sequences

Using Brier loss (MSE of probabilities) during training directly optimizes the same metric we evaluate on, unlike cross-entropy which can diverge from calibration.

## Proposed Implementation

### Phase 1: Feasibility (priority=90 in work-queue)
```python
# Input: rolling window of last 10 games per team
# Shape: (batch, 10, n_team_features) for home and away
# Output: win probability scalar
# Loss: Brier = mean((p - y)^2)

model = Sequential([
    LSTM(64, input_shape=(10, n_features), return_sequences=True),
    Dropout(0.2),
    LSTM(32),
    Dropout(0.2),
    Dense(1, activation='sigmoid')
])
model.compile(optimizer='adam', loss='mse')  # mse on probs = Brier score
```

### Phase 2: Hybrid Calibration Layer
Use LSTM outputs as features for GA pareto-best ensemble:
```python
# Stack: GA_pareto_best_prediction + LSTM_sequence_prediction -> final_brier
# Similar to isotonic calibration but sequence-aware
final_p = alpha * ga_pred + (1 - alpha) * lstm_pred  # learned alpha
```

### Phase 3: Island Integration (if Phase 2 validates)
Add `lstm_sequence` to MODEL_TYPES pool in features/engine.py.

## Expected Improvement

- NCAA LSTM+Brier-loss: 0.1589 Brier
- NBA is harder (more parity, shorter seasons) — expect ~0.21x range realistically
- Hybrid approach: +0.001 to 0.003 Brier improvement over current 0.22012

## Prerequisites

1. `engine-parity-sync` (priority=40) — need full feature set in nomos-nba-agent
2. S15 checkpoint (fleet-best preserved before any model changes)
3. GPU access for LSTM training (current islands: gpu=false)

## Priority

**priority=90** in work-queue (after checkpoints, engine-parity-sync, stacking removal).

## Related Research

- arXiv:2605.03816: CatBoost wins 26/30 Brier datasets, Venn-Abers for XGB/LGBM calibration (fire-158)
- arXiv:2508.02725: LSTM+Brier-loss NCAA=0.1589 (this proposal, fire-160)
