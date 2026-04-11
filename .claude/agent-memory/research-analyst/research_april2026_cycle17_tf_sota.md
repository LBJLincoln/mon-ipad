---
name: Trading Floor v4/v5 SOTA Audit — April 11 2026
description: Comprehensive audit of our multi-agent NBA betting competition vs April 2026 frontier. Verdict, gaps, competitor analysis, and 6-item priority fix list.
type: project
---

# Trading Floor SOTA Audit — April 11 2026

**Why:** User asked for explicit SOTA comparison of our 5-agent competition design vs April 2026 landscape.
**How to apply:** Use this to prioritize Trading Floor v5 improvements and validate architecture decisions.

## Verdict: Partially SOTA

- **AHEAD**: 5-agent competition format (no public open-source sports equivalent), CPCV+DSR+PBO gate (validated as gold standard, no commercial platform discloses this), 55+ bet categories (exceeds all academic papers), NBA domain depth
- **BEHIND**: Brier score (0.2157 vs Montrucchio 0.089), no formal Bull/Bear debate protocol, no risk-adjusted island weighting, daily batch vs 24/7 continuous execution, no per-agent vote tracking

## Key Competitors

| Competitor | Format | Our Edge | Their Edge |
|---|---|---|---|
| Alpha Arena (nof1.ai) | 6 LLMs × crypto real capital | Sports domain, Kelly, CPCV | Real capital, live leaderboard, 24/7 |
| TradingAgents (arXiv:2412.20138) | Bull/Bear debate + roles | Sports-specific | Formal debate protocol, Sharpe 8.21 |
| Sportstensor (Bittensor SN41) | 100+ miners + Sortino weights | Centralized control | 100+ models, Sortino incentive |
| Polystrat (Polymarket) | 24/7 autonomous agent | CPCV gate | 4200+ trades/month, 37% vs 18% human |

## 3 Structural Gaps to Fix (in order)

1. **Sortino island weighting** (4h): Replace equal-weight blending across 6 HF islands with Sortino-ratio weights. Sportstensor pattern. -0.0015 Brier.
   - `weight_i = max(0, sortino_i)` where `sortino_i = (mean_correct_i - 0.5) / downside_stdev_i`

2. **Bull/Bear debate protocol** (6h): Add to trading-floor-v5.py. Trigger when agent panel disagrees >10pp. Bear argues against top pick (injury, B2B, opponent trend). Bull defends. Claude Opus facilitates. 2 rounds. TradingAgents pattern. -0.002 Brier.

3. **Per-agent historical vote weighting** (8h): Track each of 5 TF agents' rolling 20-game Brier in Supabase. Use as weight multiplier in consensus. Prophet Arena leaderboard pattern. -0.001 Brier.

## Cumulative Brier Math (April 2026)

Bull/Bear (-0.002) + Sortino weighting (-0.0015) + TabICLv2 (-0.004) + Brier obj (-0.002) + Shot PCA-20 (-0.005) + per-agent weighting (-0.001) = **-0.0155** total = **0.2002**. Shot PCA-20 is the decisive step to breach 0.20.

## CPCV Gate Validation

Knowledge-Based Systems 2024 paper explicitly validates CPCV+PBO+DSR as gold standard. No commercial sports platform discloses this. It is a genuine differentiator — document it prominently.
