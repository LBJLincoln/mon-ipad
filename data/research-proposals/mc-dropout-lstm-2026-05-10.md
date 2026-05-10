# Research Proposal: Uncertainty-Aware LSTM with Monte Carlo Dropout

**Source:** MDPI Information 2026, 17(1), 56 — <https://www.mdpi.com/2078-2489/17/1/56>
**Detected by:** cloud-brain fire-78 (2026-05-10T18h)
**Priority:** HIGH
**Status:** PROPOSED

## SOTA Finding

Uncertainty-Aware Machine Learning for NBA Forecasting introduces an LSTM-based architecture
with Monte Carlo dropout at inference time to provide calibrated probabilistic predictions:

- **Brier score on 2024 NBA test set: 0.199** — beats fleet best 0.22012 by 0.021
- Architecture: LSTM + MC dropout (N=50 forward passes per prediction)
- Output: mean probability + epistemic uncertainty (std across passes)
- Train ≤2022 / Val 2023 / Test 2024 — strict chronological, no leakage
- Evaluation: accuracy, ROC-AUC, Brier, log-loss, calibration curves
- Equity curve: uncertainty-aware Kelly on NBA moneylines shows positive expected value

Related: Multi-level Monte Carlo Dropout (arxiv 2601.13272, Jan 2026) reduces inference
compute cost by treating dropout masks as a source of epistemic randomness.

## Why This Matters

Our current fleet best (S15 extra_trees, Brier 0.22012) uses point estimates.
MC dropout adds two complementary capabilities:
1. **Calibration**: uncertainty bands → more honest probability predictions
2. **Kelly gating**: only bet when MC std < threshold → reduces false-confidence bets

This directly targets the TF NBA fleet empirical Brier ~0.36–0.41 (worse than random),
because the root cause is over-confident predictions on low-signal games.

## Implementation Path

### Phase 1 — GPU Burst validation (Modal A10G or Lightning T4)
1. Add `lstm_mc_dropout` to `scripts/gpu-burst/` (new variant in modal-burst.py)
2. Features: existing `features/engine.py` output, top 200 features by variance
3. Architecture: 2-layer LSTM (hidden=128) + dropout(p=0.3) after each layer
4. MC inference: 50 forward passes, mean + std output
5. Chronological split: train 2017-2022, val 2022-23, test 2023-24
6. Target: Brier < 0.22012 (beat fleet best) on same holdout

### Phase 2 — Kelly uncertainty gating (if Phase 1 succeeds)
1. Add to TF NBA `app.py`: `if mc_std > 0.15 → PASS, else kelly_fraction *= (1 - mc_std)`
2. Reduces bet frequency but improves precision → higher Sharpe
3. Gate can be tuned: start at std < 0.12 (conservative) → relax to 0.18 if WR improves

### Phase 3 — Political alpha (if NBA succeeds)
1. Same architecture on `nomos-political-alpha` feature vectors
2. pol-oracle LSTM variant (weekly retrain via Kaggle)
3. MC uncertainty gating on political bets: only trade when model is confident

## Cross-reference with Existing Work

| Prior finding | Brier | Comparison |
|---|---|---|
| TabICL Colab best | 0.21139 (window-biased) | LSTM may close gap honestly |
| LR + isotonic (MDPI 2026, fire-75) | 0.199 | Same ballpark — both confirm <0.20 is achievable |
| Fleet best S15 extra_trees | 0.22012 | LSTM target: beat this |
| pol-oracle RF | 0.23274 CV | LSTM expected to match/beat |

## Effort Estimate

- Phase 1: ~2h coding + 1h GPU run (Modal A10G free tier)
- Phase 2: ~1h TF app.py patch + 30min validation
- Phase 3: ~1h port + 1h GPU run

## Next Action

VM: implement `scripts/gpu-burst/lstm_mc_dropout_burst.py` and trigger via Modal.
Cloud brain: verify Brier on holdout, compare to 0.22012 fleet best.
