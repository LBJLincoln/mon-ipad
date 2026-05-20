# SCIRP 2025: FG_PCT_home vs Elo — Feature Importance is Dataset-Dependent

**Source:** Wang, Yuqi. "Comparative Evaluation of Machine Learning Models for NBA Game Outcome Prediction." *Journal of Computer and Communications*, Vol. 13, No. 11, November 2025. SCIRP.
https://www.scirp.org/journal/paperinformation?paperid=147163

**Fire:** fire-156 (EVEN cycle, 2026-05-24T04h)

## Key Findings

Dataset: 25,796 NBA games (2014–2022)

| Model | Accuracy |
|-------|----------|
| SVM | **0.7749** |
| LR | 0.7743 |
| AutoGluon | 0.7738 |
| DNN | 0.7726 |
| RF | 0.7685 |
| CNN | 0.760 |
| KNN | 0.7508 |

**RF Feature Importance (top-3 without Elo):**
1. FG_PCT_home: ~0.32 (field goal percentage)
2. REB_home: ~0.22 (rebounds)
3. PTS_home: ~0.18 (points)

## Critical Insight: Feature Importance is Dataset-Dependent

IEEE 2026 + MDPI 2026 consistently cite **Elo ratings as SHAP #1+#2** features (18+ confirms in our fire log).
This SCIRP paper (box-score dataset WITHOUT Elo engineered in) shows **FG_PCT_home as #1** (importance 0.32).

**Resolution (not a contradiction):**
- When Elo is engineered and included → Elo dominates as SHAP leader (it encodes cumulative team quality across seasons)
- When Elo is absent → current-game box-score stats (FG%, REB) reveal the next-best predictors
- Both signals are complementary: Elo captures long-run quality; FG_PCT captures game-day execution

## Implications for Nomos42

1. **Add Elo** (vm-add-elo-ratings-engine, priority=75) — **ELEVATE to priority=60**. With Elo in pool, GA will select it and drive Brier improvement.
2. **FG_PCT rolling average** — verify `fg_pct_rolling_*` categories exist in features/engine.py. If missing, add rolling 5/10-game FG% as a category (may become SHAP #1 behind Elo).
3. **SVM test** — SVM achieved 0.7749 (above AutoGluon). SVM is slow on large feature sets (N>200) but worth testing on small-feature configurations (N<60). Add to experiment backlog.
4. **LR confirmed** — LR accuracy 0.7743 consistent with Brier=0.199 from uncertainty-aware RNN paper (19+ fire log confirms). Keep LR in MODEL_TYPES.

## Priority Actions

- [ ] **ELEVATE vm-add-elo-ratings-engine priority 75→60** in work-queue
- [ ] Verify `FG_PCT_rolling_*` in features/engine.py — add if missing (rolling 5g, 10g, season)
- [ ] SVM backlog entry: test on N<60f islands post-stacking-removal

## Status

New EVEN-cycle research fire-156. Core finding: Elo and FG_PCT are complementary, not competing. Both belong in engine.py and GA selects winners.
