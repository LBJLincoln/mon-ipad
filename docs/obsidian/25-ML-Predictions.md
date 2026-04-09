---
tags: [predictions, ml, ensemble, trading-floor, agents, betting]
date: 2026-04-04
aliases: [ML Predictions, Model Predictions, Real Predictions, Agent Predictions]
---

# 25 -- ML Prediction System

> Real model predictions from 6 evolution islands feed ALL 207 trading agents.
> Agents use ML signal, not LLM intuition.
> See also: [[03-Trading-Floor]], [[24-GPU-Autoresearch]], [[12-Agent-Registry]]

---

## Architecture

```
6 HF Evolution Islands (always-on, CPU tree models)
    ├── S10: xgboost_brier, 50f, exploitation
    ├── S11: mixed, exploration (OFFLINE)
    ├── S12: catboost, 43f, specialist
    ├── S13: extra_trees, 69f, specialist
    ├── S14: xgboost_brier, 55f, specialist
    └── S15: random_forest, 79f, wide search
         │
         ▼
model_predictions.py (fetches in parallel)
         │
         ▼
Ensemble (inverse-brier weighting)
    ├── P(home_win) + 90% CI
    ├── Predicted spread + CI
    ├── Predicted total + CI
    └── Edge vs market
         │
         ▼
model-predictions-latest.json
         │
         ▼
trading-floor-v5.py → ctx["model_prob_home"], ctx["model_spread"], ctx["model_total"]
         │
         ▼
All 207 agent prompts include ML predictions + "use model signal as primary"
```

## 120+ Bet Categories → ML Target Mapping

| Bet Group | Categories | ML Target |
|-----------|-----------|-----------|
| Moneyline (FG, halves, Qs) | 7 | moneyline classifier |
| Spread (FG, halves, alt) | 9 | spread regressor |
| Totals (FG, halves, alt) | 10 | total regressor |
| Player Props | 30 | total + moneyline |
| Margin | 8 | spread regressor |
| Race/Quarter | 7 | moneyline + spread |
| Exotic | 11 | spread + moneyline |
| Parlay/SGP | 6 | all 3 models |
| Live/Advanced | 14 | all 3 models |

## What Each Agent Receives

```json
{
  "model_prob_home": 0.471,
  "model_prob_ci": [0.424, 0.518],
  "model_spread": -1.6,
  "model_spread_ci": [-6.6, 3.4],
  "model_total": 215.0,
  "model_total_ci": [200.0, 230.0],
  "model_ml_edge": -0.043,
  "model_confidence": "high",
  "model_n_models": 5,
  "model_avg_brier": 0.23410,
  "model_details": [
    {"source": "S10", "model_type": "xgboost_brier", "n_features": 50, "brier": 0.22893},
    {"source": "S12", "model_type": "catboost", "n_features": 43, "brier": 0.23100}
  ]
}
```

## Ensemble Aggregation

1. **Inverse-brier weighting**: weight = 1 / max(brier, 0.15)
2. **Confidence interval**: from model disagreement (stdev of predictions)
3. **Spread proxy**: logistic approximation from P(home) when regression not available
4. **Edge calculation**: model P - implied P from odds
5. **Confidence level**: high (std < 0.03 + brier < 0.23), medium (std < 0.06), low

## Files

| File | Purpose |
|------|---------|
| `scripts/arena/model_predictions.py` | Fetch + ensemble + save |
| `data/arena/model-predictions-latest.json` | Latest predictions |
| `scripts/arena/trading-floor-v5.py` | Injects into agent ctx |
| `scripts/arena/bet_categories.py` | ML section in all prompts |
