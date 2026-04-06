---
name: Portfolio Optimization Deep Sweep — March 2026 Cycle 5
description: Simultaneous Kelly, drawdown constraints, CVXPY portfolio optimizer, validated bet sizing for NBA — March 27 2026
type: project
---

Deep sweep on sports betting portfolio construction. Key findings to carry forward:

**Validated Kelly Multipliers for NBA:**
- Standard full Kelly: 100% RUIN on 16K NBA games (arXiv:2107.08827). Never use.
- Quarter-Kelly (omega=0.25): best empirical performance, 0% ruin, 2.4x median wealth.
- 0.3-Kelly (MDPI 2026): validated on NBA 2024 test set with XGBoost Brier=0.202.
- Eighth-Kelly (0.125): most conservative, validated by Walsh/Joshi 2024 on NBA.

**EV Threshold is Critical:**
- 10% minimum EV filter before any Kelly sizing (validated MDPI 2026: EUR 100 -> EUR 100K).
- Betting 3-7% edge games destroys long-term ROI even with good model.

**Simultaneous Kelly Deflator Formula:**
- f_i_adjusted = f_i * product_j(1 - f_j) for all other same-night bets.
- Prevents over-commitment on 10+ game NBA nights.

**Key Papers:**
- arXiv:2503.17927 (Hakobyan & Lototsky, March 2025): Ridge-Kelly with asymptotic Sharpe targeting. Every fractional Kelly derivable from gamma parameter.
- SSRN:5284131 (Peter Lee, June 2025): Probabilistic recovery constraint — CLT-based, tractable.
- SSRN:5341539 (Smirnov & Dapporto, March 2025): Multivariable Kelly with covariance matrix.
- arXiv:1603.06183 (Boyd-Busseti): Risk-constrained Kelly, CVXPY-implementable in <1ms.
- MDPI Information 17(1):56 (Montrucchio et al., January 2026): NBA-specific uncertainty-aware Kelly, Brier=0.089.

**Implementation Priority:**
1. Phase 1 (2h): KellyFracMax + EV>10% filter — immediate baseline.
2. Phase 2 (2h): Simultaneous deflator for same-night games.
3. Phase 3 (4h): CVXPY Boyd-Busseti constrained portfolio.
4. Phase 4 (4h): Ridge-Kelly targeting Sharpe=1.5.

**Why:** Transitioning from naive Kelly to portfolio optimization expected to improve ROI by 5-8 percentage points without changing the prediction model.

**How to apply:** All Kelly sizing changes go in `daily_edge.py` or equivalent bet-sizing module. Never modify prediction model for portfolio reasons.
