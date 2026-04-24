# POL day-217 (2025-11-21) — per-agent analysis
Generated 2026-04-24 21:34 UTC

## `qwen-quant` — day PnL $-24.17
- **Pattern in outcomes**: All bets relied on the same "strong insider trade signal" thesis, yet results varied (-25.0, -14.4, +15.2). No clear correlation between thesis strength (uniformly "high") and PnL.
- **Edge misalignment**: Edge=0.00 for all bets suggests the model overestimated signal strength or failed to price risk accurately—wins were likely noise, not edge.
- **Stake consistency**: Uniform stakes (83.42) indicate no dynamic sizing based on conviction or odds, increasing variance.
- **Mistake to correct**: **Stop assuming "high strength" insider signals guarantee edge**. Validate with historical hit rates or odds before betting; discard edge=0.00 trades.
- **Strength to keep**: **Thesis specificity**—focusing on SEC-reported insider trades with clear agency signals avoids vague narratives.
- **Actionable fix**: Tomorrow, require non-zero edge or odds >2.0 for insider trades, and size bets based on signal confidence (e.g., reduce stake if edge <5%).

## `llama-contra` — day PnL $+7.34
- **Win/Loss Pattern**: All bets were on SEC Form 4 insider trades, but wins (GOOGL, HOOD) came from sectors with explicit positive catalysts (tech’s avg_ret, finance’s high signal volume). The loss (CVX) lacked a clear catalyst beyond "underpriced energy"—vague thesis.
- **Edge/Stake Mismatch**: All bets had `edge=0.00`, yet stakes varied ($14.34–$17.2). No correlation between stake size and thesis strength (e.g., HOOD’s high-volume thesis justified higher PnL but lower stake).
- **Thesis Quality**: Wins cited *quantifiable* sector metrics (avg_ret, volume); loss relied on qualitative "underpriced." Data-driven theses outperformed narrative-driven.
- **Mistake**: Overlooking sector-specific *momentum* (e.g., tech’s +0.0031 avg_ret). CVX’s energy thesis ignored recent sector trends (e.g., oil price delta, insider sell/buy ratio).
- **Strength**: Sector filtering (tech/finance) aligned with higher win rates. HOOD’s finance thesis leveraged signal volume—a repeatable metric.
- **Actionable Fix**: Tomorrow, require *explicit* sector momentum (e.g., 30-day avg_ret > 0) or insider trade *direction* (buys > sells) to avoid "underpriced" narratives.

## `mistral-ministral` — day PnL $+4.67
- **Win/Loss Patterns**:
  - **Winning pick (HOOD)**: Finance sector alignment (avg_ret=-2.88%) + insider trade (strength=0.60) *contrarian* to weak sector beta. Edge likely hidden in mean-reversion or event timing (Form 4 filing).
  - **Losing pick (MSFT)**: Tech sector-beta *momentum* trade (VIX=18.0 neutral) but no clear edge (reported edge=0.00). Thesis relied on generic "strength=0.60" without quantifiable catalyst (e.g., volume spike, earnings delta).

- **Mistake to Fix**:
  - **Edge transparency**: Both trades reported `edge=0.00`—likely a logging error. *Action*: Pre-commit edge calculations (e.g., `(insider_strength * sector_zscore) - implied_odds`) and validate before execution. Today’s HOOD win suggests edge existed but wasn’t documented.

- **Strength to Keep**:
  - **Sector-beta awareness**: HOOD’s win leveraged sector weakness as a signal (finance underperformance = higher alpha potential for contrarian insider buys). *Double down*: Backtest sector-beta thresholds (e.g., only trade if sector_ret < -2%) to filter noise.

- **Data Gaps**:
  - Missing odds/stake % of bankroll. Standardize logs: `stake=X% | odds=Y | edge=Z%`.
  - VIX=18.0 unused in MSFT thesis—correlate VIX regimes with insider trade success rates.

## `mistral-large` — day PnL $+4.45
- **Win/Loss Patterns**: Wins cluster around *contrarian* theses (e.g., CVX’s negative sector trend, CMCSA’s mixed signals) with **low edge (0.00)** but **high odds** (implied by PnL/stake ratios >1:1). Losses align with *macro-narrative* bets (QCOM’s AI-healthcare) despite insider signals—suggesting **overfitting to thematic stories** over data.
- **Stake Mismatch**: Losses risk **2x wins** (e.g., $20.07 vs. $10.03) without compensating edge. PnL asymmetry (-$2 vs. +$3.5) reveals **poor risk-adjusted sizing**.
- **Thesis Quality**: Wins exploit **SEC Form 4 contradictions** (CVX) or **sector dissonance** (CMCSA). Losing thesis (QCOM) lacks **counterfactual validation** (e.g., no check for insider trades *against* AI narrative).
- **Mistake to Fix**: **Stake normalization**—equalize bet sizes to **≤1% of bankroll** ($1.38 max) until edge >0.05. Current sizing amplifies variance without edge.
- **Strength to Keep**: **Signal vs. sector divergence** (e.g., CVX insider trade *despite* negative sector returns) is a repeatable pattern. Codify as: *"Bet insider trades against sector momentum if win_rate <30%."*

## `mistral-medium` — day PnL $-4.18
- **Patterns in losses**:
  Both losing bets were **insider-trade signals** (CMCSA/MSFT) with **zero quantified edge** (edge=0.00) despite "high strength" claims. Thesis relied on **SEC filings** (public data) without pricing inefficiency or catalyst timing. Stake sizing (13.31) was **~13% of bankroll**—high for unedged trades.

- **Category risk**:
  Insider trades underperformed (2/2 losses), while other categories (e.g., earnings, macro) lack data. **Hypothesis**: Market efficiently prices SEC filings; edge requires *pre-filing* info or structural arbitrage (e.g., options skew).

- **Mistake to correct**:
  **Betting without edge quantification**. Replace "high strength" subjective labels with **backtested win rate/odds** (e.g., "insider buys >$5M in last 3 days beat SPX by X% over Y days"). Today’s trades assumed agency ≠ edge.

- **Strength to keep**:
  **Thesis specificity** (e.g., "clear agency")—better than vague narratives. Double down on **catalyst clarity** but pair with **statistical validation** (e.g., "CMCSA insider clusters precede +3% moves 60% of the time").

- **Actionable tweak**:
  Reduce insider-trade stakes to **<5% of bankroll** until edge is proven. Allocate saved capital to **high-edge categories** (e.g., earnings surprises with IV crush).

## `qwen-arb` — day PnL $-2.68
- **Win/Loss Patterns**:
  - **Category**: All bets were insider-trade signals (SEC filings) in large-cap tech/energy (CVX/GOOGL/QCOM). No diversification in thesis type.
  - **Edge/Thesis**: Claimed "high strength/clear agency" but **no edge % logged**—suggests subjective overconfidence. GOOGL won despite identical stated edge, implying **execution luck** (e.g., timing, sizing) mattered more than thesis differentiation.
  - **Odds/PnL**: Similar stakes ($29.49) but asymmetric payouts: GOOGL’s +$5.4 win barely covered CVX (-$5.1) + QCOM (-$3.0). **Net negative expectancy** despite 1/3 win rate.

- **Mistake to Correct**:
  - **Quantify edge pre-trade**: "High strength" is vague. Assign numeric edge % (e.g., "70% historical win rate for >$500K insider buys in sector") and **skip bets below 5% edge**. Today’s implied edge was ~0% (1 win, 2 losses).

- **Strength to Keep**:
  - **Thesis consistency**: Sticking to SEC-insider signals (a proven alpha source) avoids narrative drift. **Double down on post-trade analysis**: Log *why* GOOGL worked (e.g., earnings beat?) while CVX/QCOM failed (e.g., oil volatility?). Refine filters accordingly.

## `mistral-nemo` — day PnL $-1.97
- **Patterns**:
  - Losses so far outpace wins (3+ today alone). Edge=0.00 on last bet suggests weak or mispriced thesis.
  - Tech momentum (XLK) vs stock-specific events (GOOGL) shows poor alignment—momentum decay (-1.2σ) may overwhelm event-driven gains.

- **Mistake to correct**:
  Ignoring sector momentum (XLK) when trading single stocks. Require edge >0.10 when momentum trends strongly negative (-1σ+).

- **Strength to keep**:
  Using event-driven theses (e.g., GOOGL insider trade) for alpha, but tighten filters to exclude trades where sector context contradicts stock thesis.

## `gemini-tact` — day PnL $-1.22
- **Losing pattern**: Both losses stemmed from **tech-sector insider trades** (MSFT/QCOM) with **identical edge=0.00**, suggesting overconfidence in weak signals (strength=0.60). No clear differentiation in thesis quality despite varying stock liquidity.
- **Edge mispricing**: Zero-edge bets imply **no statistical advantage**—likely overestimating insider trade impact without correlating with price action or volume spikes.
- **Stake sizing**: $12.83 (12.5% of bankroll) on MSFT vs. $10.26 (10%) on QCOM shows **inconsistent risk management** despite similar thesis strength.
- **Strength to keep**: **Event-driven focus** (SEC Form 4) is a valid niche, but needs tighter filters (e.g., trade size >$1M, concurrent news catalysts).
- **Key mistake**: **Ignoring base rates**—insider trades alone rarely move stocks; pair with earnings/guidance or macro tailwinds (e.g., Fed policy).
- **Fix tomorrow**: **Drop edge=0.00 bets** or cap stakes at 5% of bankroll until edge >0.1. Add a "confirmation layer" (e.g., options flow, analyst upgrades).
