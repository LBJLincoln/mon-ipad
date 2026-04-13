# NBA Research Proposal: Market Anchor Lock + Bootstrap Brier Variance (4th Pareto Objective)
**Date:** 2026-04-13 | **Brain cycle:** 97 | **Priority:** HIGH | **Status:** PROPOSED

---

## Source

Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets
*MDPI Information 2025, Vol 17* — https://www.mdpi.com/2078-2489/17/1/56

Key results from paper:
- Non-market model alone: AUC=0.94
- Market-only model: AUC=0.76
- Combined market+model fusion: AUC=0.95, Brier ≈ 0.199
- Logistic regression baseline WITH market features: Brier 0.199
- Monte Carlo Dropout EV filter (EV > 1.10 threshold): focuses bets on highest-confidence predictions
- PCA(20) on shot features outperforms raw 128-dim CNN embeddings

---

## Problem Statement

Current best Brier: **0.22325** (S14, XGBoost, 55 features, cycle 93). Target: **< 0.20**. Gap: 0.0232.

The paper's central finding is that even a logistic regression baseline achieves Brier 0.199 *when market features are present*. Our GA already has `market_vig_removed` and related odds features in `features/odds_market.py` — but the GA can and does *drop* these features through mutation/selection pressure. When an island runs lean (low feature count for regularization), market features get pruned away.

This is the plateau mechanism: islands without the market anchor lose the most informative single signal (bookmaker consensus probability encodes crowd wisdom + sharp money), leaving the model to rediscover predictive structure from raw stats alone. That ceiling is approximately AUC=0.94, Brier ≈ 0.221-0.224.

A second issue: we have no measure of *model stability*. An individual with Brier=0.221 trained on 5 different 80% data subsets might have Brier variance of ±0.015 (unstable) or ±0.003 (robust). NSGA-II currently treats both identically. The MC Dropout concept from the paper (uncertainty quantification) maps cleanly to a bootstrap variance check for tree ensembles.

---

## Proposal 1: Mandatory Market Feature Lock

### What
Modify GA chromosome initialization and mutation so that `market_vig_removed` is **always included** and is **never removable** by mutation. This feature is the de-vigged bookmaker consensus probability from `features/odds_market.py`.

The feature acts as an information anchor: every evolved model is forced to incorporate the market's best estimate of win probability as an input. The model may weight it low or high, but it cannot ignore it.

### Pseudocode

```python
# In hf-space/app.py — chromosome initialization
MARKET_ANCHOR_FEATURES = ['market_vig_removed']  # always-on features

def init_chromosome(all_features, max_features=200):
    # Start with the anchor — guaranteed inclusion
    locked = [f for f in MARKET_ANCHOR_FEATURES if f in all_features]

    # Fill remainder from remaining pool
    remaining_pool = [f for f in all_features if f not in locked]
    n_additional = random.randint(20, max_features - len(locked))
    selected = random.sample(remaining_pool, min(n_additional, len(remaining_pool)))

    return locked + selected

def mutate_features(features, all_features, mutation_rate, max_features=200):
    # Separate locked features from mutable ones
    locked = [f for f in features if f in MARKET_ANCHOR_FEATURES]
    mutable = [f for f in features if f not in MARKET_ANCHOR_FEATURES]

    mutated = []
    for f in mutable:
        if random.random() < mutation_rate:
            pass  # drop this feature
        else:
            mutated.append(f)

    # Add new features (normal mutation logic), but never from locked pool
    pool = [f for f in all_features if f not in mutated and f not in locked]
    n_add = random.randint(0, max(1, int(mutation_rate * len(mutable))))
    additions = random.sample(pool, min(n_add, len(pool)))

    result = locked + mutated + additions
    return result[:max_features]  # enforce hard cap
```

### Secondary anchors (optional, lower priority)
Consider also locking `market_home_implied_prob` and `market_spread_implied_prob` if available in `features/odds_market.py`. Locking 2-3 market features provides redundancy; locking too many (>5) defeats the purpose of GA feature selection for remaining features.

### Why this works
The paper shows that a simple LR with market features matches our best XGBoost without them (Brier 0.199 vs 0.223). Market features contain information orthogonal to game stats. The GA should be exploring *how to use* market information alongside statistical features — not *whether to include* it at all.

---

## Proposal 2: Bootstrap Brier Variance as 4th NSGA-II Objective

### What
During GA evaluation, compute each individual's Brier score on 5 independent random 80% subsamples of the training window. Add the **variance** of these 5 Brier scores as a 4th Pareto objective to minimize.

Current NSGA-II objectives: Brier (minimize), ROI (maximize), Sharpe (maximize)
Proposed 4th objective: Bootstrap Brier variance (minimize)

### Why
A model with low Brier but high variance is overfit to the specific training window — it will underperform in deployment. A model with slightly higher mean Brier but near-zero variance is a better bet. This is the tree-ensemble analog to Monte Carlo Dropout uncertainty estimation from the paper.

NSGA-II handles this naturally: the variance objective adds a new dimension to the Pareto front. Models that are both accurate AND stable dominate. This also diversifies the population — some individuals optimize mean Brier, others optimize stability, crossover mixes both.

### Pseudocode

```python
# In hf-space/app.py — evaluate_individual()
def evaluate_individual(individual, X_train, y_train, X_test, y_test):
    # Existing evaluation (full training set)
    features = individual['features']
    model = build_model(individual)
    model.fit(X_train[features], y_train)
    preds = model.predict_proba(X_test[features])[:, 1]
    brier = brier_score_loss(y_test, preds)
    roi, sharpe = compute_betting_metrics(preds, y_test, individual)

    # NEW: Bootstrap Brier variance (5 subsamples of 80% training data)
    N_BOOTSTRAP = 5
    BOOTSTRAP_FRAC = 0.80
    bootstrap_briers = []

    n_train = len(X_train)
    for _ in range(N_BOOTSTRAP):
        idx = np.random.choice(n_train, size=int(n_train * BOOTSTRAP_FRAC), replace=False)
        X_sub = X_train.iloc[idx]
        y_sub = y_train.iloc[idx]

        sub_model = build_model(individual)  # fresh model, same hyperparams
        sub_model.fit(X_sub[features], y_sub)
        sub_preds = sub_model.predict_proba(X_test[features])[:, 1]
        bootstrap_briers.append(brier_score_loss(y_test, sub_preds))

    brier_variance = np.var(bootstrap_briers)

    # Return 4-objective tuple for NSGA-II
    # NSGA-II minimizes all: negate ROI and Sharpe for minimization convention
    return (brier, -roi, -sharpe, brier_variance)
```

### Pareto front update
```python
# In hf-space/app.py — NSGA-II selection
# Update objective count from 3 → 4
N_OBJECTIVES = 4
# Reference point for hypervolume: (0.30, -0.0, -0.0, 0.01)
# brier_variance target: < 0.0001 (well-calibrated robust model)
```

### Performance cost
5 extra model fits per individual per generation. For a population of 12 with tree models averaging 2s/fit, this adds ~2 minutes/generation. Acceptable on always-on HF CPU spaces. Can reduce to N_BOOTSTRAP=3 if generation time exceeds 15 minutes.

---

## Expected Improvement

| Change | Mechanism | Estimated Brier Delta |
|--------|-----------|----------------------|
| Market anchor lock | Forces use of highest-signal single feature | -0.005 to -0.015 |
| Bootstrap variance 4th objective | Selects for robust models, reduces overfit | -0.002 to -0.005 |
| Combined | Anchored + stable models | -0.008 to -0.020 |

Combined best case: 0.22325 - 0.020 = **0.203** (near target)
Combined conservative: 0.22325 - 0.008 = **0.215** (meaningful progress)

The paper's Brier 0.199 was achieved with a logistic regression + market features. Our XGBoost with more features and bootstrap stability should meet or beat that.

---

## Implementation Steps

### Files to modify

**`hf-space/app.py`** (primary target — all GA logic lives here)

1. Add `MARKET_ANCHOR_FEATURES = ['market_vig_removed']` constant near top of file (alongside `MAX_FEATURES`, `ALLOWED_MODELS`, etc.)

2. Modify chromosome initialization function (search for `def init_chromosome` or equivalent feature sampling logic) to always prepend anchor features.

3. Modify mutation function (search for feature drop/add logic in `mutate`) to skip anchor features during drop phase.

4. Modify `evaluate_individual` (or equivalent evaluation function) to add bootstrap loop. Return 4-tuple instead of 3-tuple.

5. Update NSGA-II selection: change objective count from 3 → 4. Update any reference points, crowding distance calculations, or hypervolume indicators that hardcode 3 objectives.

**`features/odds_market.py`** (read-only verification)

6. Verify `market_vig_removed` is the canonical feature name. If the feature is named differently (e.g., `mkt_vig_removed`, `odds_vig_removed`), update `MARKET_ANCHOR_FEATURES` to match the actual column name in the feature output.

### Verification checklist
- [ ] Run one generation manually, confirm `market_vig_removed` appears in all 12 individuals' feature lists
- [ ] Confirm no individual has `market_vig_removed` dropped after mutation
- [ ] Confirm `evaluate_individual` returns 4-tuple, NSGA-II selection processes 4 objectives without error
- [ ] Confirm generation time increase is < 3x (acceptable for 5 bootstrap fits)
- [ ] Check Supabase experiment logs show `brier_variance` as 4th objective value

### Deployment order
1. Deploy market anchor lock first (lower risk, no timing change)
2. Verify one full generation completes cleanly
3. Deploy bootstrap variance 4th objective
4. Monitor generation time; reduce N_BOOTSTRAP=3 if needed

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| `market_vig_removed` not available for all games (missing odds) | Medium | Medium | Fall back gracefully: if feature is all-NaN for a game, impute with 0.5. Lock only when feature has valid data. |
| 4th objective slows NSGA-II selection significantly | Low | Low | NSGA-II scales O(MN²) in objectives M, pop N. 4 vs 3 objectives is negligible at N=12. |
| Bootstrap adds too much generation time | Medium | Low | Reduce N_BOOTSTRAP from 5 to 3. Or evaluate bootstrap only every 5th generation. |
| Market anchor reduces GA exploration diversity | Low | Medium | Locking 1 feature out of 200 max leaves 199 free slots. Diversity impact is minimal. |
| Pareto front becomes harder to navigate (4D) | Low | Low | NSGA-II handles arbitrary dimension. Crowding distance still works. |

---

## Action Items

- [ ] Verify exact feature name: grep `market_vig_removed` in `features/odds_market.py`
- [ ] Add `MARKET_ANCHOR_FEATURES` constant to `hf-space/app.py`
- [ ] Patch `init_chromosome` and `mutate` to respect locked features
- [ ] Patch `evaluate_individual` to run 5 bootstrap subsamples, return 4-tuple
- [ ] Update NSGA-II objective count from 3 → 4
- [ ] Deploy to S14 first for A/B comparison vs baseline S10/S11
- [ ] After 5 generations, compare Brier trajectory vs S11 baseline
- [ ] If Brier improves, propagate to all 6 islands via `/api/config` broadcast

---

## Connection to Previous Proposals

- Cycle 95 (SHAP efficiency ratio): SHAP may confirm `market_vig_removed` as top feature after it is locked in — useful validation
- Cycle 94 (overround spread features): those features are in the same `odds_market.py` module; they remain freely selectable by GA
- Cycle 93 (market-implied calibration): isotonic calibration on market-implied probs is complementary — can be stacked on top of this proposal
- MC Dropout EV filter from paper: not directly implementable without neural models, but bootstrap variance serves same purpose (identify high-uncertainty predictions to filter or size conservatively)
