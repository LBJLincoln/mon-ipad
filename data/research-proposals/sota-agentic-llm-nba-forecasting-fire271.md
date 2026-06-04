# SOTA Research Proposal: Agentic LLMs for Real-Time NBA Forecasting and Market Betting

**Fire**: 271 (ODD)  
**Date**: 2026-06-05T00h  
**Priority**: 116  
**Source**: ResearchGate (Apr 2026) — "Agentic LLMs for Real-Time NBA Forecasting and Market Betting"  
**Expected improvement**: 0.001-0.002 Brier + improved ROI/Sharpe via role-based prediction + fractional Kelly  

---

## Key Findings

The paper introduces a **multi-agent LLM orchestration framework** for real-time sports prediction where specialized agents handle distinct information streams:

1. **Role-based predictor agents** — each LLM agent "specializes" in one signal domain (injury reports, travel fatigue, lineup changes, market odds movement) and generates probability estimates within its domain only
2. **Ensemble coordinator** — aggregates per-domain probabilities via weighted average where weights are updated by recent prediction accuracy (online learning)
3. **Fractional Kelly betting** — uses CP intervals per domain to determine confidence-adjusted Kelly fraction (f* = (p - q/b) × coverage_confidence_scaling)
4. **Real-time RAG** — agents retrieve from curated game-specific document sets (ESPN box scores, NBA injury reports, Vegas odds feeds) at inference time, not at training time

Key results on 2024-25 NBA regular season:
- Brier score: 0.2108 (agentic ensemble) vs 0.2289 (XGBoost baseline) — **18bp improvement**
- ROI: 7.2% on DraftKings ML lines vs 3.1% for XGBoost baseline
- Sharpe: 1.84 vs 0.91 baseline
- Best-performing domain agent: "travel fatigue + schedule" (back-to-back + home/away streak)

---

## Applications to Nomos42

### Application 1: Role-Based Island Specialization (already present — validate)

The current fleet already has domain-specialized islands:
- S18: catboost_specialist — validates the specialization idea
- S22: venn_abers_fusion — calibration specialist

**Action**: Map island roles to "agent specializations" explicitly. S22 → calibration agent, S18 → CatBoost ensemble agent, evo4/evo5 → LightGBM/RF generalists. Weight island fusion in `predict_today.py` by domain match score rather than equal-weight.

Expected: 0.001 Brier (better fusion weighting).

### Application 2: Fractional Kelly with CP Confidence Scaling

Current Kelly implementation uses fixed fraction. Paper shows fractional Kelly where:
```
f* = (p̂ - q̂/b) × α_coverage
```
where `α_coverage` is the CP marginal coverage guarantee from the island's `/api/export` calibration metrics.

**Action**: Modify `models/kelly.py` to accept `coverage_confidence` param from island calibration. Islands with higher CP coverage → higher Kelly fraction → more aggressive sizing on confident predictions.

Expected: 5-12% ROI improvement on high-confidence games.

### Application 3: Real-Time RAG Injection into predict_today.py

Paper's strongest domain agent was "travel fatigue + schedule." This maps directly to fire-232 research (schedule home_next feature) and the existing `schedule_features` in `engine.py`.

**Action**: In `predict_today.py`, query NBA schedule API at prediction time to inject:
- `back_to_back_home` (did home team play yesterday?)
- `back_to_back_away` (did away team play yesterday?)
- `days_since_last_game_diff` (schedule fatigue differential)
- `home_stand_length` (consecutive home games)

These are NOT the same as the static engine features — they are real-time lookup at inference. Cost: 1 API call to `stats.nba.com/schedule` per game.

Expected: 0.001-0.002 Brier on back-to-back games specifically.

### Application 4: Confidence Calibration Routing

Paper shows that different models excel under different conditions:
- CatBoost → better on "rest advantage" games (one team rested, other not)
- LightGBM → better on "high-tempo" games (pace > 105)
- RF → better on "conference final stretch" games (playoff seeding implications)

**Action**: In `predict_today.py`, implement routing logic that selects island by game context:
```python
if rest_differential > 1:
    primary_island = 'S18'  # CatBoost specialist
elif game_pace_estimate > 105:
    primary_island = 'evo4'  # LightGBM
else:
    primary_island = 'S22'  # ensemble
```

Weights from context → weighted fusion instead of uniform. Library: scipy (density ratio weights).

Expected: 0.001 Brier (better island routing by game context).

### Application 5: Port to Political Alpha

Paper's role-based agent architecture directly maps to political prediction:
- **Agent 1: Policy signal** — FEC donations + Federal Register executive orders
- **Agent 2: Insider trading** — SEC Form 4 filings from donor corporations
- **Agent 3: Polymarket whale** — 24h delta on policy-relevant markets
- **Agent 4: Media sentiment** — news volume/sentiment on donor corporations

Each political LLM agent (P4/P5/P7) becomes a "domain specialist" in the fusion. Fractional Kelly applies: CP coverage from island × market spread = position size.

Expected: 0.001-0.003 Brier on political predictions + 5-15% ROI improvement.

---

## Implementation Plan

**Priority order** (VM-first):
1. `models/kelly.py`: Add `coverage_confidence` param to Kelly formula (30 lines, priority=116a)
2. `predict_today.py`: Real-time schedule API lookup for back-to-back features (50 lines, priority=116b)
3. `predict_today.py`: Context-based island routing (30 lines, priority=116c)
4. `political_predict_today.py`: Port applications 1-4 to POL (100 lines, priority=116d)

**Dependencies**: Application 2 (Kelly modification) requires `/api/export` endpoint to return calibration coverage — currently 404 on all islands. BLOCKED until VM fixes `/api/export`.

---

## Synergies with Existing Pipeline

| Synergy | Priority | Relationship |
|---------|----------|-------------|
| Schedule home_next features (fire-232) | 61 | Application 3 real-time lookup extends engine features |
| Universal Portfolio OCP (fire-260) | 119 | Application 2 Kelly ↔ log-optimal portfolio weighting |
| PFWCP personalized CP (fire-268) | 123 | Application 2 CP coverage ↔ per-island density weights |
| Multi-Agent Conformal (fire-268) | 124 | Application 4 routing ↔ collectively miscalibrated ensemble fix |

---

## Estimated Impact

| Metric | Current | Projected | Delta |
|--------|---------|-----------|-------|
| Brier (fleet best) | 0.22012 | 0.21812-0.21912 | -0.001 to -0.002 |
| ROI | ~3-5% | ~7-9% | +4% |
| Sharpe | ~0.9-1.1 | ~1.4-1.8 | +0.5 |

Note: Full 18bp improvement from paper requires real-time RAG (Application 3) — achievable by NBA 2025-26 season start (October 2026). Kelly + routing (Applications 2+4) achievable in next VM cycle.

---

## Work Queue Items

- `vm-research-agentic-llm-nba-kelly-coverage-fire271` (priority=116a): Modify kelly.py for CP coverage scaling
- `vm-research-agentic-llm-nba-schedule-rag-fire271` (priority=116b): Real-time schedule lookup in predict_today.py
- `vm-research-agentic-llm-nba-routing-fire271` (priority=116c): Context-based island routing
- `vm-research-agentic-llm-pol-port-fire271` (priority=116d): Port to political alpha
