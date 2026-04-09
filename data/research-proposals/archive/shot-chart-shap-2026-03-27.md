# Research Proposal: Shot-Chart Zone Features + SHAP-Driven Feature Selection
**Date:** 2026-03-27  
**Source:** NBA ML literature scan (MDPI 2026, Scientific Reports 2025, arXiv 2025)  
**Priority:** HIGH — addresses current plateau at Brier ~0.221

## 1. Context

Fleet best Brier is 0.22126 (S14, gen 358). All-time best is 0.2189 (S13, gen 338).  
Published SOTA on NBA game prediction: CNN achieves **Brier 0.221**, XGBoost **0.202** (MDPI 2026).  
We are competitive with CNN but lagging XGBoost SOTA by ~0.019 Brier points.

## 2. Key Finding: Shot-Chart Spatial Embeddings

**Source:** "Uncertainty-Aware Machine Learning for NBA Forecasting" (MDPI 2026)  
> "Ablation study shows that removing shot-chart embeddings causes a consistent decrease in  
> discrimination and calibration, confirming that spatial shooting patterns provide  
> complementary information beyond team-level statistics."

### Proposed Implementation (CPU-safe, tree-compatible)

Instead of neural shot embeddings, encode shot-chart as **zone-based percentage features**:

```python
# In features/engine.py — new Cat38: SHOT_CHART_ZONES (12 features per team)
SHOT_ZONES = [
    'restricted_area_pct',    # % FGA from restricted area
    'non_ra_paint_pct',       # % from non-RA paint
    'mid_range_pct',          # % from mid-range
    'left_corner_3_pct',      # % from left corner 3
    'right_corner_3_pct',     # % from right corner 3  
    'above_break_3_pct',      # % above-break 3
    'restricted_area_fg_pct', # FG% in restricted area
    'non_ra_paint_fg_pct',    # FG% in non-RA paint
    'mid_range_fg_pct',       # FG% mid-range
    'corner_3_fg_pct',        # FG% corners
    'above_break_3_fg_pct',   # FG% above-break 3
    'shot_quality_index',     # weighted expected pts per shot zone
]
# Apply rolling windows: 5g, 10g, 20g EWMA per zone
# = 12 zones × 6 windows × 2 teams = 144 new features
# Data source: NBA stats API /shotchartdetail or nba_api library
```

**Expected impact:** -0.003 to -0.008 Brier (based on ablation in paper)

## 3. SHAP-Driven Feature Selection (replaces random mutation)

**Source:** Scientific Reports 2025, PMC/SHAP + XGBoost NBA study  
Top features by SHAP: `home_next`, `team_elo_5y`, `team_elo`, net_rtg, pace differentials.

### Proposal: SHAP-seeded initial population

In `init_population()`, instead of pure random feature selection:  
1. Train a quick XGBoost on all 200 candidates (5-fold, 30s)
2. Rank features by mean |SHAP|
3. Seed top-50% individuals with top-N SHAP features as starting points
4. Bottom-50% remain random (diversity preserved)

```python
# In ga/evolution.py — add to init_population()
def shap_seed_individual(shap_rankings, n_features, top_k_bias=0.7):
    """Create individual biased toward high-SHAP features."""
    top_k = int(len(shap_rankings) * top_k_bias)
    # Sample n_features from top-k with higher probability
    weights = np.zeros(len(shap_rankings))
    weights[:top_k] = 2.0
    weights[top_k:] = 1.0
    weights /= weights.sum()
    selected = np.random.choice(len(shap_rankings), size=n_features, 
                                replace=False, p=weights)
    return shap_rankings[selected]
```

**Expected impact:** faster convergence in first 50 gens, estimated -0.002 Brier

## 4. Auto-Calibration Selection

**Source:** sklearn `CalibratedClassifierCV` + Brier auto-select  
> "Use Brier loss score to automatically select the best calibration method — sigmoid, isotonic, or none."

We already deploy sigmoid/isotonic/venn_abers. Add **automatic selection** at the individual level:
- Evaluate all 3 calibration methods on val set
- Pick lowest Brier for that individual's final fitness
- Tag in genome: `calibration: auto_best`

This is low-cost (already computing Brier for each) and could yield -0.001 Brier.

## 5. Implementation Priority

| Improvement | Est. Brier Gain | Complexity | Priority |
|-------------|----------------|------------|----------|
| Shot-chart zones (Cat38) | -0.003 to -0.008 | Medium (needs API data) | HIGH |
| SHAP-seeded init | -0.002 | Low (pure GA code) | HIGH |
| Auto-calibration select | -0.001 | Very low | MEDIUM |

**Total potential:** -0.006 to -0.011 Brier → could reach 0.210-0.215

## 6. Data Requirements

Shot-chart data available from:
- `nba_api` library: `shotchartdetail` endpoint (free, rate-limited)
- Pre-compute per-team rolling averages once per day (VM side, ZERO ML)
- Store in `data/shot-zones-{season}.csv`, load in feature engine

## 7. Next Steps

1. Add `nba_api` call for shot zones in `scripts/fetch-shot-zones.py` on VM
2. Add Cat38 to `features/engine.py` (both VM and hf-space copy — parity rule)
3. Add SHAP seeding to GA init on one island (S11 exploration — best testbed)
4. Measure Brier change after 50 gens vs current baseline
