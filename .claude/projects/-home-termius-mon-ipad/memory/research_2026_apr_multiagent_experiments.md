---
name: SOTA Multi-Agent Trading Experiments April 2026
description: Top 5 papers + categories for NBA playoffs + political→stocks + crypto. Prediction Arena, Agent Trading Arena, TradingAgents, DMAD, QuantAgents.
type: research
---

## TOP 5 Papers (April 2026)

### 1. Prediction Arena (2604.07355) — Harvard+Arcada, Mar 28 2026
57-day live experiment, 6 models, $10K each, Kalshi+Polymarket. KEY: market selection dominates model choice (-22.6% Kalshi vs -1.1% Polymarket). Gemini-3.1-pro +6%. **Adapt: per-book ROI tracking, route bets to softest lines per category.**

### 2. Agent Trading Arena (2502.17967) — EMNLP 2025
Chart visualizations >> text for LLM numerical reasoning (+40%). Reflection module > more agents.
**Adapt: embed matplotlib PNG in agent prompts instead of raw JSON stats. Add pre-decision reflection step.**

### 3. TradingAgents v0.2.3 (2412.20138) — TauricResearch
LangGraph 7-role, Bull/Bear debate. Sharpe 8.21 vs 1.64 baseline. Claude 4.6 + Gemini 3.1 supported.
**Adapt: structured 2-round Bull/Bear debate per game. Prevents groupthink. -0.002 Brier estimated.**

### 4. DMAD (ICLR 2025) — Diverse Multi-Agent Debate
Forces structurally distinct reasoning: each agent locked to different data source.
**Adapt: Agent1=box-score-only, Agent2=odds-movement-only, Agent3=momentum-only, Agent4=regression-only, Agent5=contrarian-default. Biggest convergence fix available.**

### 5. QuantAgents (2510.04643) — EMNLP 2025
4-role: Stats Analyst, Risk Control, Market News, Manager. 111% return, Sharpe 2.02, 61% WR. 3-type memory.
**Adapt: restructure 5 agents as differentiated roles with weekly meeting protocol.**

## Investment Categories to Add

### NBA Playoffs (starts ~Apr 19 2026)
- First-half totals Under (overs only 45% in playoffs vs 52% regular season)
- Series betting (who advances) — structural advantage with momentum features
- Game 7 totals Under — historically defense-dominant
- Player props Under for stars in B2B spots
- Elimination game spreads — higher variance = larger Kelly edge

### Political → Stocks/ETF
- Defense ETFs (ITA, XAR) — strongest Trump military/tariff correlation
- Energy (XLE, XOP) — deregulation legislative language = leading indicator
- Pharma (XPH) — drug pricing bill activity
- STOCK Act disclosures (sec.gov, 45-day lag), quiverquant.com (2-3 day lead)
- "HALO trade" 2026: Heavy Assets Low Obsolescence (industrials/energy > AI software)

### Crypto
- Conservative HedgeFundAgent approach, BTC/ETH momentum + drawdown constraints, 25% Kelly cap

## Experimental Design Rules
1. Minimum 57 days / 50+ resolved bets per agent per category
2. DMAD: when >3/5 agents agree → reduce bet size 40% (consensus = low information)
3. Track agent divergence rate as primary health metric
4. Metrics per agent per category: Brier, Sharpe, Calmar, WR, p-value (n>50)
5. Memory: episodic (past bets) + semantic (domain knowledge) + working (current context)
