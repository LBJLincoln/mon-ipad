# SOTA Research — fire-59 Rotation B | 2026-05-07T22h

## NBA SOTA Summary (May 2026)

### External benchmarks
| Source | Method | Brier | Accuracy | Notes |
|--------|--------|-------|----------|-------|
| MDPI 2025 (Computational Intelligence) | CNN ensemble | **0.221** | ~69% | Tabular only |
| MDPI Jan 2026 (Information 17/1/56) | Uncertainty-Aware LSTM + MC dropout | **0.089** | — | Requires live betting lines (not tabular-only) |
| SportBot AI 2025-26 production | Ensemble + market | 0.20–0.23 | 75–80% | Uses real-time odds feed |
| FiveThirtyEight Elo | Elo + HCA | ~0.245 | 66% | Public benchmark |

### Our fleet status
| Island | Pareto candidate | Model | Gen | Validated? |
|--------|-----------------|-------|-----|------------|
| S15 Rank-1 | **0.21885** | RF 200f | 2393 | No — Pareto only |
| S15 Rank-2 | **0.21879** | RF 200f | 2392 | No — Pareto only |
| S22 Rank-2 | **0.21886** | CatBoost | — | No — Pareto only |
| Production oracle | 0.22054 | TabICL isotonic | — | Yes |
| Fleet GA best | 0.22019 | LR (S14) | 1078 | Validated |

**Key insight:** S15 RF_200f candidates at gens 2392-2393 exceed published tabular-only CNN SOTA (0.221) in Pareto front. Need external walk-forward validation to confirm. Priority: extract these 3 candidate configs and run on Kaggle P100 with full walk-forward holdout.

### Top features (literature consensus)
1. `team_elo_last_5` — rolling Elo over last 5 games (top-3 most predictive per MDPI 2026)
2. `home_advantage` — binary + rolling HCA estimate
3. `rest_days_diff` — rest days home minus away
4. `market_implied_prob` — FanDuel/DraftKings line → Kelly implied probability (adds ~0.01 Brier improvement)
5. `back_to_back_flag` — schedule fatigue

Our engine has features 1-3 and 5. Feature 4 (market implied) is missing → **estimated 0.005-0.01 Brier improvement** if added.

## Political SOTA Summary (May 2026)

### External benchmarks
| Source | Method | Brier | Notes |
|--------|--------|-------|-------|
| Polymarket (2026) | Prediction market mechanism | **0.187** | Not ML — crowd wisdom |
| LLM ensemble forecasters (arxiv 2507.04562) | LLM-based | ~0.24 | Close to our islands |
| Expert human forecasters | Human | ~0.22 | Superforecaster level |

### Our fleet status
| Island | Best | Model |
|--------|------|-------|
| P4 (fleet best) | 0.24904 | LightGBM |
| P2 | 0.24902 | LightGBM |
| P1 | 0.24990 | XGBoost |

**Gap to Polymarket:** 0.062 — significant. Key opportunities:

## Rotation B Action Plan: Political Engine Improvements

### 1. Market-implied probability feature (HIGH IMPACT)
- Add Polymarket current probability as `market_implied_prob` feature
- Rationale: Polymarket achieves 0.187 Brier; our models at 0.249 are 33% worse
- Estimated improvement: 0.020-0.030 Brier reduction
- Implementation: `scrape_fec_edgar.py` already has Polymarket endpoint stub → activate
- **BLOCKED ON**: `fix-pol-engine-placeholder` (VM must restore political_engine.py first)

### 2. Rolling Elo for political actors (MEDIUM IMPACT)
- Adapt NBA Elo implementation to political context:
  - Track polling approval rating as "Elo" — exponential decay with K-factor
  - `pol_elo_3mo` (3-month rolling), `pol_elo_30d` (30-day), `pol_elo_momentum`
- Estimated improvement: 0.005-0.010 Brier reduction

### 3. 72h overcorrection fade signal (MEDIUM IMPACT)
- Literature finding: prediction markets show 72h overcorrection after major news
- Feature: `market_delta_72h` = (current - 72h_ago) price change
- Signal: large negative `market_delta_72h` → fade (bet opposite direction)
- Implementation: requires 72h history in Polymarket/PredictIt data pipeline

### 4. Data pipeline restart (CRITICAL BLOCKER)
- POL has only 272 feature_candidates vs NBA's 3377 (12x fewer!)
- Root cause: `fetch_political_data.py` + `insider_tracker.py` stale 39+ days
- Expected gain: +50 feature candidates → better GA selection pressure
- **VM action**: `vm-restart-political-data-crons` in work-queue (priority 1)

### 5. Isotonic calibration port from NBA
- NBA oracle already uses isotonic calibration (achieves 0.22054 vs raw 0.22169)
- Port same `sklearn.isotonic.IsotonicRegression` wrapper to political engine
- Expected improvement: 0.003-0.007 Brier reduction

## Proposed political_engine.py additions (Rotation B)
```python
# After existing feature extraction:

# Feature: market-implied probability (Polymarket)
if 'polymarket_prob' in event_data:
    features['market_implied_prob'] = event_data['polymarket_prob']
    features['market_delta_72h'] = event_data.get('polymarket_delta_72h', 0.0)
    features['market_momentum_7d'] = event_data.get('polymarket_7d_change', 0.0)

# Feature: rolling political Elo
elo_rating = compute_rolling_elo(
    actor_id=event_data['primary_actor'],
    approval_series=approval_history,
    k_factor=32, decay_halflife_days=90
)
features['actor_elo_90d'] = elo_rating['elo_90d']
features['actor_elo_30d'] = elo_rating['elo_30d']
features['elo_momentum'] = elo_rating['elo_30d'] - elo_rating['elo_90d']
```

Note: Implementation blocked until VM restores political_engine.py from fire-53 placeholder accident.
