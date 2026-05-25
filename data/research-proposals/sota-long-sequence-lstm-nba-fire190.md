# SOTA Research Proposal: Long-Sequence LSTM for NBA Game Outcome Prediction

**Source:** arXiv:2512.08591  
**Fire:** 190 (EVEN WebSearch)  
**Date:** 2026-05-29T22h

## Paper Summary

"Long-Sequence LSTM Modeling for NBA Game Outcome Prediction Using a Novel Multi-Season Dataset"

- **Dataset:** Novel multi-season NBA dataset covering the 2004-05 to 2024-25 seasons (9,840 games, 8 full seasons)
- **Architecture:** LSTM with extended sequence length (8 full seasons of per-game records per team)
- **Key innovation:** Leverages longitudinal team history to capture evolving dynamics invisible to single-season models
- **Contrast:** arXiv:2508.02725 uses NCAA (single tournament); this paper targets NBA specifically and uses ~8x more temporal history per team

## Key Insight

Current GA-evolved islands (S15, S18, S22) optimize feature sets within a single season or rolling short windows. A long-sequence LSTM trained on 8 full seasons of team history can capture:

1. **Dynasty cycles** — Warriors 2015-2019 trajectory; team peak/decline arcs
2. **Coaching system continuity** — new coach transition effects across seasons
3. **Player aging curves** — multi-season performance arc of key contributors
4. **Playoff experience effects** — teams with N prior playoff seasons perform differently under pressure
5. **Roster disruption signals** — trades/injuries that reshape team identity over time

These meta-patterns are invisible to any single-season rolling average, no matter how many features.

## Actionable Path

### Near-term: Data pipeline
1. Build multi-season game sequence per team: order all games chronologically for each team across 8+ seasons
2. Use existing engine.py features as per-game feature vectors (top-200 by SHAP from current 4581+ candidates)
3. Target sequence length: 82 games × 8 seasons = ~656 game-steps per team

### Mid-term: Model training
4. Train standalone LSTM with Brier loss (identical loss function validated by arXiv:2508.02725 on NCAA)
5. Evaluate on walk-forward holdout split (chronological, identical methodology to fleet best 0.22012)
6. Target: Brier < 0.22012 (fleet best) on NBA holdout

### Post-GA integration
7. Use LSTM output probability as a meta-feature alongside GA-evolved model predictions
8. Allow GA to select whether to include LSTM embedding as a feature group (engine.py feature category)

## Expected Improvement

- arXiv:2508.02725 NCAA LSTM+Brier-loss achieves 0.1589 (lower due to NCAA's higher skill variance)
- MDPI/2078-2489/17/1/56 MC-dropout RNN pregame NBA Brier=0.206 (best published NBA sequence model)
- Conservative NBA LSTM estimate: ~0.215-0.220, potentially below our fleet best 0.22012
- As post-GA meta-feature: expected 0.3-0.8% Brier improvement

## Synergies

- **arXiv:2508.02725:** Same LSTM+Brier-loss architecture; NCAA-validated; adapt for NBA
- **MDPI/2078-2489/17/1/56:** MC dropout wrapper for calibrated uncertainty (N=50 inference passes)
- **arXiv:2303.06021:** ECE Pareto objective — evaluate LSTM with ECE in addition to Brier
- **arXiv:2412.19318:** Adaptive conformal betting wrapper around LSTM output probabilities

## Dependencies

- Multi-season NBA game data (2004-2025, available from Basketball Reference or existing data pipeline)
- engine.py feature extraction pipeline (AFTER engine-parity-sync, priority=40)
- PyTorch or TensorFlow (not in current GA stack — requires new dependency)
- GPU training (current islands have GPU Disabled; separate training job needed)
- Estimated compute: ~2-4 hours on single GPU for 8-season LSTM training

## Work-queue Item

`vm-research-lstm-nba-multiseason-fire190` (priority=91) — complementary to `vm-research-lstm-sequence-model-fire160` (priority=90); this proposal is NBA-specific and uses multi-season scope vs fire-160 which focuses on single-sequence approach.
