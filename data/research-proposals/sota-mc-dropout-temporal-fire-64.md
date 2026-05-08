# SOTA Proposal: MC-Dropout Temporal Line Movement Features

**Fire**: 64 | **Rotation**: A | **Date**: 2026-05-08T18:00:00Z  
**Source**: "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets", MDPI Information 2026-01-08  
**URL**: https://www.mdpi.com/2078-2489/17/1/56

## Gap Analysis

| Metric | Value |
|--------|-------|
| Fleet best (validated) | 0.22012 (S15 RF 75f) |
| SOTA paper | 0.199 (MC-dropout RNN) |
| Gap | −0.021 Brier |
| XGBoost tabular baseline in same paper | 0.202 |

## Technique

RNN with Monte Carlo dropout over temporal betting-line sequences. Key: temporal momentum across multiple odds snapshots (1h, 3h, 24h, 48h before tip-off). The RNN learns when market moves are informative vs noise.

Our engine has static odds snapshots. Limited temporal velocity = main gap.

## Proposed: Cat55 Temporal Line Movement (6 features)

Add to `features/engine.py`:

```python
def _cat55_temporal_line_movement(self, game: dict):
    """Cat 55: Temporal betting-line momentum — 6 features."""
    odds = game.get("line_history", {})
    current = float(odds.get("ml_home_current", 0))
    h1  = float(odds.get("ml_home_1h_ago", current))
    h3  = float(odds.get("ml_home_3h_ago", current))
    h24 = float(odds.get("ml_home_24h_ago", current))
    d1h  = current - h1
    d3h  = current - h3
    d24h = current - h24
    momentum = 0.5*d1h + 0.3*d3h + 0.2*d24h
    def sgn(x): return 1 if x > 0.005 else (-1 if x < -0.005 else 0)
    steam   = 1.0 if abs(d1h) > 0.03 and sgn(d1h) == sgn(d3h) else 0.0
    reversal = 1.0 if sgn(d1h) != sgn(d3h) and sgn(d3h) != 0 else 0.0
    features = [d1h, d3h, d24h, momentum, steam, reversal]
    names = ["line_delta_1h", "line_delta_3h", "line_delta_24h",
             "line_momentum_weighted", "steam_move_flag", "line_reversal_flag"]
    return features, names
```

**Data requirement**: `line_history` sub-dict. Already partially available via `data/full-odds-2025-26.json` (249 categories). Add second `nba-daily-odds.py` snapshot at 03:00 UTC (currently only 12:18 UTC) to capture overnight line movements.

## Expected Impact

| Component | Estimated Brier delta |
|-----------|----------------------|
| Cat55 temporal line features | −0.010 |
| Venn-Abers calibration on S15 RF | −0.003 |
| Combined target | **~0.207** |

## Political Cross-Port

Cat27 has 72h Kalshi/Polymarket delta. Cat45 `_pm_extended_windows` (7d/14d) already coded in restore script — **blocked on restore_political_engine_fire53.py (VM)**. Once restored, Cat45 adds 8 temporal prediction-market features directly analogous to Cat55.

## Priority

**MEDIUM** — after:
1. VM restore political_engine.py (priority 0)
2. VM restart S17 (priority 1)
3. VM restart political data crons (priority 1)
4. engine-parity-sync nomos-nba-agent (priority 40)
