# ScoringBench: Tabular Foundation Model Evaluation via Proper Scoring Rules

**Source 1:** arXiv:2603.29928 (Mar 2026) — "ScoringBench: A Benchmark for Evaluating Tabular Foundation Models with Proper Scoring Rules"  
**Source 2:** arXiv:2603.08206 (Mar 2026) — "Distributional Regression with Tabular Foundation Models: Evaluating Probabilistic Predictions via Proper Scoring Rules"  
**Added:** fire-236 (EVEN) 2026-06-06T16h  
**Priority:** 110 (highest in research pipeline)  
**Work-queue:** vm-research-scoring-bench-tabicl-fire236

---

## Key Findings

### arXiv:2603.29928 — ScoringBench
- Tabular FM models (TabICL, TabPFN) produce **full predictive distributions** but standard benchmarks evaluate only RMSE/R² — ignoring probabilistic quality
- **Model rankings shift substantially** depending on scoring rule: a model winning on RMSE may lose on CRPS/Brier
- 97 regression datasets evaluated with: CRPS, CRLS, interval score, energy score, weighted CRPS, Brier Score
- Critical for high-stakes domains where tail errors carry disproportionate costs — exactly our NBA betting use case
- Git-based leaderboard supporting community contributions and transparent protocols

### arXiv:2603.08206 — Distributional Regression
- Compares TabPFNv2.5 vs TabICLv2 on 20 OpenML datasets using proper scoring rules (CRPS, CRLS, Interval Score)
- TabICLv2 upgrade path confirmed: v2 introduces explicit distributional output calibrated for proper scoring rules
- Consistent improvement over standard tabular methods when evaluated on CRPS vs RMSE

---

## Direct Relevance to Nomos42

Our best model (TabICL, 0.21139 Brier walk-forward) already uses Brier Score. ScoringBench shows:
1. CRPS provides **additional calibration signal** not captured by Brier alone
2. TabICLv2 has better distributional calibration than original TabICL
3. Model rankings can change when CRPS is added — meaning our evolution islands selecting on Brier alone may be missing better-calibrated candidates

---

## Applications

### Application 1 — ScoringBench Oracle Comparison
Run ScoringBench-style evaluation on our TabICL Oracle model (186f, 11440 games):
```python
# pip install properscoring
from properscoring import crps_ensemble
crps = np.mean(crps_ensemble(y_true, prob_samples))
```
- Compare: TabICLv2 vs TabPFNv2.5 vs current TabICL vs XGBoost/RF
- Primary metric: Brier (already used) | Secondary: CRPS + CRLS
- Expected: TabICLv2 ≥ current TabICL by 0.001–0.003 Brier

### Application 2 — CRPS as 5th Pareto Objective
Add CRPS to evolution island evaluate_model():
```python
# In engine.py evaluate_model():
crps_score = np.mean(crps_ensemble(y_true, proba_matrix))
return (brier, -roi, -sharpe, n_features, crps)  # 5-objective pareto
```
Expected: CRPS guides selection toward better-calibrated models

### Application 3 — CRLS as 6th Pareto Objective
Add Continuous Ranked Log Score for tail-risk calibration:
- Penalizes overconfident predictions in tails harder than CRPS
- Directly relevant for large-stake NBA game bets

### Application 4 — TabICLv2 Upgrade
```bash
# In Colab:
pip install tabicl --upgrade  # Get TabICLv2
# Retrain on same 186f dataset, compare Brier/CRPS
```
Previous: 0.21139 walk-forward / 0.22169 CV. TabICLv2 expected: ~0.001–0.003 improvement

### Application 5 — Port to POL
- Add CRPS/CRLS to political_engine.py model evaluation
- Multi-scale CP (arXiv:2502.05565) + proper scoring rules = compound improvement
- State-level vs national hierarchy maps naturally to multi-scale CRPS

---

## Implementation Notes

```bash
pip install properscoring  # CRPS/CRLS
pip install tabicl --upgrade  # TabICLv2
```

**Prereq:** engine-parity-sync (priority=40) should complete first for consistent evaluation.

**Effort:** ~4h ScoringBench eval + 8h CRPS/CRLS Pareto integration

**Expected Total Improvement:** 0.002–0.004 Brier (CRPS-guided Pareto + TabICLv2 upgrade)

---

## Connection to Existing Research
- Complements Venn-Abers calibration (fire-158/197) — Venn-Abers provides interval calibration; CRPS provides single-value proper scoring
- Complements Brier Misconceptions (PMC12818272, fire-220) — CRPS addresses same coverage concerns
- Validates TabICL Oracle model approach — ScoringBench confirms proper scoring rules as gold standard for probabilistic tabular models
