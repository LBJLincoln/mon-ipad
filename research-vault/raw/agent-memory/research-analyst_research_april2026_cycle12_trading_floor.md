---
name: April 2026 Cycle 12 — SOTA Trading Floor Experiments + Visualization
description: Apr 7 2026 cycle 12: MDPI NBA Brier 0.089 (shot-chart CNN), Kelly-Bayesian ensemble, HedgeAgents 70% return, TradingAgents Bull/Bear UI, CPCV definitively beats WF, Bloomberg ASKB agentic, prediction market microstructure, referee bias L2M
type: project
---

# SOTA Trading Floor — April 7 2026

## New CRITICAL Papers

### MDPI NBA 2026 (Brier 0.089)
- arxiv-equivalent: MDPI Information 17(1):56, Jan 2026
- URL: https://www.mdpi.com/2078-2489/17/1/56
- Architecture: GRU + MC dropout + CNN shot-chart embeddings (PCA 20 components)
- Brier 0.089 (fused) vs LR 0.199 baseline — 55% better
- Train ≤2022, val 2023, test 2024. Season-fixed effects for concept drift.
- **Deploy: shot-chart CNN as Category 50, 40 features (home+away embeddings)**

### Kelly as Bayesian Model Evaluation (arXiv:2602.09982)
- URL: https://arxiv.org/abs/2602.09982
- Core: model bankroll = Bayesian posterior. Outperforms Brier/log-loss at model discrimination.
- **3-hour deploy: ModelBankrollTracker. Weekly update. Blend by normalized bankroll.**
- Expected Brier delta: -0.003

### HedgeAgents 70% Annual Return (arXiv:2502.13165, WWW 2025 oral)
- Three conference types: BAC (capital allocation), ESC (experience sharing), EMC (extreme market)
- 70% annualized, 400% total, Sharpe 2.41
- **Map to Trading Floor v5: BAC=daily category allocation, ESC=weekly retro, EMC=anomaly**

### CPCV Definitively Beats Walk-Forward (ScienceDirect 2024)
- URL: https://www.sciencedirect.com/article/pii/S0950705124011110
- Walk-forward: 10 false positives / 100 strategies
- CPCV: < 3 false positives / 100 strategies
- Novel variants: Bagged CPCV, Adaptive CPCV
- **Replace Kaggle walk-forward with CPCV N=8, k=4, purge=3 games**

### Sharpe Inference New Standard (SSRN:5520741, Sep 2025)
- López de Prado, Lipton, Zoonekynd
- 5 pitfalls: no sig test, non-IID bias, min sample ignored, p-value misinterpretation, no multiple-testing correction
- **D6 gate: 50+ bets OOS, DSR>0 p<0.05, multiple-testing correction**

## New Alpha Features Identified
- Cat50: Shot-chart CNN embeddings (40 features/game)
- Cat51: ATS momentum (Moskowitz factor) — ATS_record_last_10/20, OU_cover_last_10
- Cat52: Prediction market divergence (Kalshi/Polymarket vs sportsbook vs our model)
- Cat53: Referee crew tendency (L2M error rate, home bias)
- Referee L2M finding: 23% fewer errors for visiting underdogs, 42% fewer for home underdogs in close games (Belasen SAGE Aug 2025)

## Visualization Upgrades Mapped
- Bull/Bear debate: TradingAgents two-column pattern (green/red border cards)
- 102-category heatmap: ApexCharts treemap (cell=ROI%, size=volume, drill-down)
- Bloomberg ASKB pattern: every chart shows underlying formula (View Code button)
- Color tokens: bg #0A0F1E, card rgba(255,255,255,0.04), green #00FF88, blue #4D9CFF
- Agent swarm drill-down: React Flow node graph (D1-D9 → subagents → decisions)

## Full Research Report
Path: /home/lahargnedebartoli/mon-ipad/data/research/2026-sota-trading-floor.md

## Why: User requested 2026 SOTA scientific trading floor experiments + enterprise visualization patterns. Specifically: multi-agent backtest architectures, walk-forward validation, Bayesian optimization, robust statistical testing (White Reality Check, SPA, DSR), portfolio construction, Kelly advances. Plus: Bloomberg, TradingView, Jane Street UI patterns for leaderboards, heatmaps, Bull/Bear debates, agent swarm drill-down.
## How to apply: Reference this cycle for shot-chart features (Cat50), Kelly-Bayesian ensemble, CPCV gating, HedgeAgents conference pattern for TF v5, and all visualization color tokens/patterns.
