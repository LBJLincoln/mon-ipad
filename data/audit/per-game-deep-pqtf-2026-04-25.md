# PQTF — per-game cross-agent forensic
Generated 2026-04-25 14:24 UTC
Last 14 dates expanded (295 total game-rows in JSON)

> Reads: for each (date, game/event), which agents picked WHAT and WHY.
> Use to spot consensus vs divergence, and identify why agents diverged.

## 2026-04-02
### XLC (3 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | 6 consecutive insider buys in XLC (signal_strength=0.60) indicate strong bullish momentum. ATM call spread (0.98/1.02) balances upside capture with defined risk at ~$250 per spread. IV likely compress |
| `mistral-medium` |  | — | — | — | · | 5 CMCSA insider trades (neutral bias but high cluster volume) in communications; XLC spot 95.62 → 1.015 strike (97.00) balances participation with 12δ. Risk: 0.6% of bankroll per contract. |
| `mistral-large` |  | — | — | — | · | Multiple CMCSA insider filings indicate accumulation. OTM call (3% out) targets potential breakout while limiting premium exposure. |

### XLE (9 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | XLE underperforming SPY by 1.8% over past 5 sessions despite crude flatlining; 98 strike (2% OTM) puts offer 2:1 reward/risk if sector retests 95 support. Beta to WTI futures roll-off next week. |
| `mistral-medium` |  | — | — | — | · | XLE’s spot ($95.97) sitting at resistance (96.00–96.50) with crude oil inventories report due tomorrow. OTM put (2% OTM) as tail-risk hedge; skew favors puts (IV 22% vs. 19% for calls). Allocating 3 c |
| `gemini-anl` |  | — | — | — | · | Defined-risk bull call spread to capitalize on energy sector strength while limiting capital exposure. |
| `mistral-nemo` |  | — | — | — | · | XLE at 95.85 after 3-day decline; oversold RSI (~35) with mean-reversion target near 97.50. Low IV skew favors cheap OTM calls for quick mean-reversion play. |
| `mistral-medium` |  | — | — | — | · | XLE testing 50-day MA with RSI(14) at 38 after 6% drawdown from March highs; 102 strike calls (~2% OTM) offer 3:1 reward/risk with earnings season tailwind for energy (OXY/COP next week). |
| `mistral-large` |  | — | — | — | · | XLE has underperformed relative to SPY (95.85 vs 649.03, ~14.8% ratio vs historical ~16%). OTM call for mean-reversion play with tight TTE to avoid theta decay. |
| `mistral-nemo` |  | — | — | — | · | XLE lagging energy complex despite oil strength. Momentum fade play with 3-day RSI divergence (42 vs oil's 58). Selling OTM call spread to collect theta on sector rotation. |
| `mistral-medium` |  | — | — | — | · | XLE's 96.17 spot sits at 50-day MA support; bull call spread (98/102) capitalizes on mean-reversion toward 100 handle with 1:2 risk/reward. Theta decay favors 5DTE structure. |
| `mistral-large` |  | — | — | — | · | XLE testing 95.80 support (3rd touch) with RSI divergence (58 → 42) and crude oil futures rolling over. 0.98 strike offers 3:1 reward/risk to 94.00 downside target. |

### XLF (11 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLF is oversold near multi-week lows with RSI < 30. Buying the 48.50/49.95 call vertical profits from a mean-reversion bounce with defined risk (max loss = width * qty). |
| `mistral-large` |  | — | — | — | · | Bull call spread (49.95/52) on XLF to exploit flattening yield curve + regional bank earnings tailwinds. Max risk $1.20 for $2.05 reward (68% max gain). Theta decay favorable with 5DTE. |
| `mistral-medium` |  | — | — | — | · | XLF’s Bollinger Band width at 10th percentile (tight consolidation) + IV rank at 38% (low). Long vol play ahead of potential Fed commentary next week; ATM straddle captures breakout in either directio |
| `gemini-anl` |  | — | — | — | · | Momentum play on XLF testing the $50 level; looking for a breakout supported by sector rotation flows. |
| `mistral-nemo` |  | — | — | — | · | 14 insider buys in XLF signal sector rotation into financials. ATM/OTM call spread (1.00/1.04) targets 4% upside with 100% protection on the downside. XLF's low IV rank makes this a high theta/gamma s |
| `mistral-medium` |  | — | — | — | · | 14 clustered FOUR/HOOD insider buys (signal_strength=0.60) in financials; XLF spot 49.52 → 1.02 strike (50.51) targets 2% upside with 16δ. Risk: 0.8% of bankroll per contract. |
| `mistral-large` |  | — | — | — | · | Concentrated insider activity in FOUR and HOOD (XLF components) with neutral bias suggests potential upward pressure. OTM call (2% out) balances risk-reward for short-term momentum. |
| `mistral-nemo` |  | — | — | — | · | XLF at 79.33 with oversold momentum (RSI ~38) and potential Fed dovish pivot expectations. 2% OTM calls offer asymmetric upside with defined risk. |
| `mistral-large` |  | — | — | — | · | XLF (79.33) is near 52-week lows; financials often rebound post-quarter-end. ATM call with ultra-short TTE for gamma scalping. |
| `mistral-medium` |  | — | — | — | · | XLF at 80.14 after a 1.8% intraday range; 98% strike ($78.54) offers 72% POP with SPY's IV rank (38th %) suggesting overbought conditions in financials. Risk/reward 1:3 with 5% capital allocation. |
| `mistral-large` |  | — | — | — | · | XLF IV rank (62) elevated ahead of regional bank earnings next week; selling 77/83 strangle for ~$0.80 credit with 10-point wings. Probability of profit >65% per TastyTrade backtest. |

### XLK (10 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLK has rallied ~4% in 5 sessions; RSI > 70 suggests momentum exhaustion. Selling the 240.58/252.61 put vertical captures overbought decay with defined risk (max loss = width * qty). |
| `mistral-large` |  | — | — | — | · | XLK holding above 240 with RSI(14) at 62 and 20-day momentum > 0. Targeting 245 strike (2% OTM) for 3DTE to capture gamma acceleration if SPY pushes to 525. Risk/reward 1:3 with 40% win rate historica |
| `mistral-medium` |  | — | — | — | · | XLK’s 2-period RSI at 28 (oversold) + 3-day decline of 2.1% vs. 20-day avg of +0.4%. Betting on mean-reversion to $243–$245 with 72% historical probability of bounce after similar setups. Strike at 98 |
| `gemini-anl` |  | — | — | — | · | Mean-reversion play on tech after potential overextension; seeking to capture a short-term retracement. |
| `mistral-nemo` |  | — | — | — | · | QCOM insider buys (event_idx=47-50) in XLK-tech sector. OTM call (3% strike) captures potential upside from tech momentum with minimal capital ($800 risk). Short duration reduces IV exposure while ben |
| `mistral-large` |  | — | — | — | · | QCOM insider filings (XLK component) with neutral bias may signal near-term tech strength. ATM call with shorter TTE captures potential intraday move. |
| `mistral-medium` |  | — | — | — | · | XLK/SPY ratio breaking out above 0.40 resistance (2024 highs); 258/268 call spread caps risk at 1.80 debit while targeting 4.20 max profit if tech leads next leg up (NVDA momentum + MSFT cloud growth) |
| `mistral-large` |  | — | — | — | · | XLK (258.77) has high implied vol (IV rank ~70%). Long straddle to capitalize on potential vol expansion ahead of earnings season (April 10+). |
| `mistral-nemo` |  | — | — | — | · | XLK near-term overbought (RSI 68) with 3 consecutive closes above 6-day MA. Buying 98% put spread to capitalize on mean-reversion into earnings season. |
| `mistral-large` |  | — | — | — | · | XLK breaking above 259 resistance on 1.5× relative volume; 3-day momentum score (82/100) with IV percentile (48) favoring long premium. Target 265 (1.02× strike) by Friday close. |

### XLP (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Counter-rotation hedge: 12 MO insider trades in staples (defensive sector) may signal profit-taking; XLP spot 82.33 → 0.99 strike (81.51) as tail-risk offset. Risk: 0.4% of bankroll per contract. |

### XLU (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `llama-contra` |  | — | — | — | · | Given the recent decline in XLU, a put option with a strike price at the 98th percentile of its 20-day historical volatility presents a potential mean-reversion opportunity. |
| `mistral-medium` |  | — | — | — | · | XLU IV rank at 12th percentile with 73.50-76.00 range holding for 15 sessions; selling 70/73.5/77/80 wings for ~0.80 credit targets 60% POP with defined 2.20 risk (utilities typically lag in April sea |

## 2026-04-01
### SPY (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Neutral SPY vol play to monetize stagnation; 514 spot → short 509/520 wings, long 498/527. Credit spread targets 10% of width (~$0.55 credit per wing). |

### XLE (11 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Bear put spread hedging downside to $93 (2.9% drawdown) while collecting premium; OPEC+ meeting next week could trigger volatility. Net debit <1.5% of bankroll. |
| `mistral-medium` |  | — | — | — | · | XLE underperformed SPY by 1.2σ over past 5 sessions; 98-103 call spread capitalizes on oversold RSI (32) with 78% max profit if spot hits $98.50+ by Friday. Theta decay favors short leg. |
| `mistral-nemo` |  | — | — | — | · | Confluence of 3 insider buys in XLE (CVX, OKLO) with 0.60 signal strength + rising spot post-news. IV crush risk mitigated by 5-day expiry capturing gamma squeeze. Bankroll allows 3 contracts ($3k ris |
| `mistral-medium` |  | — | — | — | · | Triple insider activity in XLE (CVX + 2x OKLO) with 0.60 signal strength; strike 2% OTM to balance delta and theta for a 3-day hold. Spot at 95.15 → 97.05 strike targets ~$99 upside (1.04x). |
| `mistral-large` |  | — | — | — | · | Clustered insider buying in XLE components (CVX, OKLO) with neutral bias suggests potential mean reversion or positive catalyst. OTM call provides leverage to upside move with limited time decay risk. |
| `mistral-large` |  | — | — | — | · | Pin risk play on XLE around current spot (95.15) given multiple insider signals. Butterfly provides defined risk with high reward if XLE settles near 97-98 by expiration. |
| `mistral-nemo` |  | — | — | — | · | XLE rallied 4.2% in 3 sessions to 100.84, near resistance. Bear put spread (short 100 put, long 97.82 put) captures mean-reversion to 98-99 zone with 3:1 reward/risk. |
| `mistral-large` |  | — | — | — | · | XLE is near recent lows with strong support at $100; mean-reversion likely with OPEC+ meetings approaching. OTM call for leverage. |
| `mistral-medium` |  | — | — | — | · | XLE lagging WTI's 3% weekly gain (now at $88/bbl) with 10-day correlation breaking down; bear put spread (100/104) limits risk to 1.20 debit while targeting 102 support. |
| `mistral-medium` |  | — | — | — | · | Bull call spread (100/105) on XLE as crude oil (WTI) holds $82 support with OPEC+ meeting 4/3. Defined risk ($2.50) for 5:1 max reward; IV rank (62%) justifies debit. |
| `mistral-large` |  | — | — | — | · | XLE at 100.00 psychological support with RSI(14) at 32 (oversold) and crude oil futures contango easing. 5DTE 98-strike calls (~2% ITM) capture mean-reversion while limiting premium decay. |

### XLF (6 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLF spot at 49.60 near 20-day low; IV rank 68%. Buying 49.5 call (ATM) + selling 50.5 call (5% OTM) for $0.45 credit/debit, targeting 2.5x return on margin. Defined risk ($0.55) with 8% upside to shor |
| `mistral-large` |  | — | — | — | · | Single-leg FOMO play on financials if 10Y yield breaks 4.35%; tight stop at 49.00 (1.2% risk). Low correlation to XLK/XLE. |
| `mistral-nemo` |  | — | — | — | · | XLF near 50.50 support after earnings beat. Bull call spread (long 50.50 call, short 52.02 call) targets 51-53 breakout with 2.8:1 reward/risk. |
| `mistral-large` |  | — | — | — | · | Financials (XLF) are oversold relative to SPY; ATM call for near-term rebound ahead of Fed minutes. |
| `mistral-medium` |  | — | — | — | · | XLF IV rank at 38th percentile with earnings season lull; selling 49-52 range for 0.40 credit (8% ROI if holds). Hedges tail risk from potential Fed speak volatility. |
| `mistral-medium` |  | — | — | — | · | XLF testing 50.48 after failing to hold 50.75 resistance (200-period VWAP on 5m); 51 strike (1.02×) offers 3:1 reward/risk with IV percentile (48%) below 50th. Earnings season for regionals (e.g., RF |

### XLK (10 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Bull call spread targeting 3% OTM upside with 80% max gain; tech earnings catalysts (MSFT, AAPL) in 2 weeks. Short leg sells theta to offset long call premium. |
| `mistral-medium` |  | — | — | — | · | XLK IV rank (68%) + 5-day momentum (99th %ile) suggests pullback risk; 234/241/248 put butterfly costs $1.20 with $4.80 max payoff if XLK pins below $241 by next Tuesday. Defined risk of $240. |
| `mistral-nemo` |  | — | — | — | · | TSLA insider buy in XLK adds tech sector volatility. Short 3-day expiry maximizes IV exposure while limiting time decay. Risk-controlled at $2k for high-beta tech play. |
| `mistral-medium` |  | — | — | — | · | XLK at all-time high (238.60) with neutral TSLA insider signal; 2% OTM put as macro-hedge against mean reversion. Defined risk to $233 (~2.3% downside). |
| `mistral-large` |  | — | — | — | · | TSLA insider activity may signal sector rotation into tech. Bull call spread limits risk while capturing potential upside from XLK's recent pullback (238.60 spot vs. 52wk high ~250). |
| `mistral-nemo` |  | — | — | — | · | XLK consolidating at 241.77 after tech rally. Net-credit iron condor (241/237 puts, 247/251 calls) profits from range-bound action with 1.5% credit and 2.5x max reward. |
| `mistral-large` |  | — | — | — | · | Tech (XLK) volatility likely to expand pre-earnings; long straddle to capitalize on breakout or breakdown. |
| `mistral-medium` |  | — | — | — | · | XLK holding above 240 with RSI(14) at 58 and MACD crossing upward; targeting 248 (102% strike) as next resistance. Short-dated to capitalize on acceleration if SPY holds 520. |
| `mistral-medium` |  | — | — | — | · | XLK rejected at 240.50 (prior ATH) with RSI(14) diverging on hourly; 235 put (0.98×) targets 236.50 support (50-day MA). Short-dated to avoid theta decay before NVDA earnings (4/8). |
| `mistral-large` |  | — | — | — | · | XLK holding 240 support with MACD curl-up and 1.2x avg volume in last 2 sessions; targeting 245 (2% OTM) on tech leadership continuation. 3DTE balances theta decay vs. breakout window. |

### XLU (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Defensive hedge: XLU IV percentile (30) underprices tail risk from tomorrow’s FOMC minutes. 74.50 strike puts (~0.3% OTM) cost 0.45% of bankroll, asymmetric payoff if utilities gap down on hawkish sur |

## 2026-03-31
### SPY (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | Defined-risk hedge against broader market volatility during the final trading sessions of the quarter. |

### XLE (6 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Bear put spread to capitalize on XLE’s 52-week high IV (68th percentile) and recent failure to hold $96. Defined risk ($1.20 wide) with max loss at $240; targets $93.50 support (2.5% downside). |
| `gemini-anl` |  | — | — | — | · | Energy typically shows relative strength during Q1-Q2 transitions; looking for a momentum breakout above $97. |
| `mistral-medium` |  | — | — | — | · | XLE failed to hold 95.00 support twice this week; crude oil inventories build (+4.2M vs. est. +1.8M) suggests near-term downside to 93.50 (98% strike). Short-dated to avoid theta decay; 3% allocation. |
| `mistral-large` |  | — | — | — | · | Long straddle on XLE to profit from potential volatility expansion ahead of weekend macro data (e.g., rig counts, inventory reports). |
| `mistral-nemo` |  | — | — | — | · | Energy sector consolidating near resistance with geopolitical risks skewed to downside. 2% OTM puts benefit from mean-reversion if oil demand concerns resurface. |
| `mistral-medium` |  | — | — | — | · | XLE testing 50-day MA at $94.50 with RSI(14) at 38 (oversold); 98% strike delta ~0.30, targeting $96 rebound by Friday. Risk 2.1% of bankroll. |

### XLF (10 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | XLF is trading near 52-week lows relative to SPY; mean-reversion likely with financials stabilizing post-Fed commentary. OTM call for leverage. |
| `mistral-nemo` |  | — | — | — | · | XLF spot at 50.05 with 3 insider buys (signal_strength=0.6) in FOUR/MSTR. Long 50.50 call, short 52.50 call for net debit. Expect finance sector rotation into value plays pre-Q2 earnings. |
| `mistral-medium` |  | — | — | — | · | FOUR insider trades (XLF) with 0.60 signal strength but neutral bias imply limited upside momentum; selling OTM call spread to collect premium while defining risk at 50.55 (spot 50.05). |
| `mistral-medium` |  | — | — | — | · | Complementary put spread to balance gamma exposure; MSTR insider trade adds minor tailwind but overall sector IV remains stable (no expansion). |
| `mistral-large` |  | — | — | — | · | FOUR insider buys (x2) + MSTR insider buy signal a floor in financials; 2% OTM call captures upside while limiting premium decay. 3-day TTE aligns with typical insider trade follow-through. |
| `mistral-large` |  | — | — | — | · | Defined-risk bull call spread on XLF to exploit insider accumulation (FOUR/MSTR) with 5% upside target; wider TTE reduces theta burn. |
| `mistral-nemo` |  | — | — | — | · | XLF near session lows with RSI <30, oversold bounce likely due to sector rotation into financials ahead of earnings season. ATM 2D calls offer asymmetric upside with limited downside. |
| `mistral-large` |  | — | — | — | · | XLF has lagged SPY in recent sessions; OTM call for mean-reversion play with 3-day TTE to capture potential bounce before weekly options expiry. |
| `mistral-nemo` |  | — | — | — | · | Financials showing strength with rising rate expectations. 3% OTM calls provide leveraged exposure to potential breakout above 54 resistance. |
| `mistral-large` |  | — | — | — | · | XLF is near 52-week lows relative to SPY; mean-reversion likely in financials given stable macro backdrop. OTM call for leverage. |

### XLK (9 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLK breaking out relative to SPY (238.46 vs. 521.39) with 1.3x 30d vol ratio; targeting 2% OTM for 70% delta on 3-day horizon. Risk/reward 1:2.5 with IV rank at 48th percentile (neutral). |
| `mistral-large` |  | — | — | — | · | Tech sector (XLK) poised for vol expansion ahead of earnings; long straddle captures breakout in either direction with defined risk. |
| `gemini-anl` |  | — | — | — | · | Anticipating institutional selling in tech for window dressing and rebalancing at quarter-end. |
| `mistral-nemo` |  | — | — | — | · | XLK showing early momentum with price holding above VWAP, OTM calls target breakout above 241 resistance. 3D expiry balances theta decay with room for movement. |
| `mistral-medium` |  | — | — | — | · | XLK breaking above 240 psychological level with 3-day RSI at 62 (bullish but not overbought). Targeting 245 (102% strike) with 72-hour expiry to capture FOMO into quarter-end window dressing. Risk-rew |
| `mistral-large` |  | — | — | — | · | Bull call spread on XLK to capitalize on tech sector rotation with defined risk. Recent consolidation suggests upside breakout potential. |
| `mistral-nemo` |  | — | — | — | · | XLK holding above 240 with momentum from tech earnings season. 2% OTM call captures delta while minimizing theta decay over 3 days. High beta to market rallies expected into quarter-end. |
| `mistral-medium` |  | — | — | — | · | XLK IV rank 42nd percentile; selling 97/103 short wings for $1.20 credit ($240 total), defined risk $400. Theta play with 70% POP. |
| `mistral-large` |  | — | — | — | · | Tech volatility expected to rise ahead of earnings; long straddle captures potential breakout or breakdown with defined risk. |

### XLP (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Clustered MO insider trades (x4) in staples may reflect defensive positioning; 2% OTM put hedges against macro pullback with longer TTE for rotation to develop. |

### XLRE (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Real estate (XLRE) oversold; mean-reversion play with OTM call to capitalize on potential rebound in rates-sensitive sector. |

### XLU (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Defensive play on utilities as SPY RSI(14) sits at 62 (neutral-overbought); XLU’s 10-day correlation to SPY turned negative (-0.12) suggesting decoupling. 1% OTM strike balances theta decay and delta |
| `mistral-medium` |  | — | — | — | · | Bear put spread (72/75) hedges against utility sector pullback if 10Y yield spikes above 4.35%. Defined risk ($1.20 wide) with 70% POP based on 20-day Bollinger Band squeeze. 2.5% allocation. |

### XLY (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | BA insider cluster (8 trades, signal_strength=0.6) may pressure aerospace OEMs in XLY. Buy 200.14*0.98=196.14 put for 1.5% portfolio hedge. Tight expiry to cap theta decay. |

## 2026-03-30
### SPY (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | Statistical expectation of price consolidation in the S&P 500 during a session with zero news catalysts, capturing theta decay. |

### XLE (5 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLE’s spot (95.22) sits at upper Bollinger band (95.40) with crude oil inventories due tomorrow. 102% strike put offers asymmetric payoff if energy pulls back to 94.00 (-1.3%), with minimal theta deca |
| `mistral-large` |  | — | — | — | · | XLE has rallied 12% YTD but is showing overbought RSI signals. An iron condor captures range-bound behavior while benefiting from time decay. The structure profits if XLE stays between $91.41 and $101 |
| `mistral-nemo` |  | — | — | — | · | XLE bear put spread to hedge energy sector volatility from OKLO insider trades, defined risk with reward capped at 5% spread width. |
| `mistral-medium` |  | — | — | — | · | OKLO insider activity (strength 0.60) is less compelling, but energy’s recent IV rank (68th percentile) justifies a defined-risk bear put spread as a macro hedge against a pullback in oil. |
| `mistral-medium` |  | — | — | — | · | XLE testing 98 support (50-day MA) with RSI(14) at 32—oversold bounce play. 96/98 call spread would define risk but single-leg ITM offers higher delta for mean-reversion. |

### XLF (11 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLF’s 3-day RSI (32) is oversold vs. its 20-day mean (45), with SPY holding above 518 support. 98% strike balances delta (0.30) and theta decay, targeting a rebound to 50.50 (+1.5%). |
| `mistral-large` |  | — | — | — | · | XLF has lagged SPY by ~2% over the past 5 sessions, trading near 52-week lows relative to the index. With Fed signaling potential rate cuts later in 2026, financials are poised for a relief rally. OTM |
| `mistral-medium` |  | — | — | — | · | Six clustered FOUR insider buys (avg strength 0.60) in financials—unusual consensus suggests 2-3% upside potential. OTM strike balances premium cost with delta exposure. |
| `mistral-large` |  | — | — | — | · | Strong insider buying in FOUR (6 Form 4 filings) signals potential upside in XLF. OTM call with short TTE to capture near-term momentum while limiting theta decay. |
| `mistral-large` |  | — | — | — | · | Bull call spread to define risk while benefiting from XLF's potential breakout. Balances cost and reward with a 5-day horizon. |
| `mistral-nemo` |  | — | — | — | · | XLF holding above key support at $56.50 with SPY softening; 102-strike call offers 2% OTM for cheap gamma exposure with 3-day theta decay working in our favor. Historical 3-day mean-reversion stats fo |
| `mistral-medium` |  | — | — | — | · | XLF’s 5-day RSI (42) sits in neutral territory after a 3% pullback from its 52-week high; betting on reversion to $57.50–$58.50 range with 80% PoP. Risk defined to $0.80 debit, targeting $1.20 credit |
| `mistral-large` |  | — | — | — | · | Financials (XLF) are range-bound with elevated implied vol. Selling an iron condor collects premium while betting on sideways movement. |
| `mistral-medium` |  | — | — | — | · | XLF lagging SPY’s rally (relative weakness in regional banks); 56/57 bear put spread limits downside to $1.20 debit while targeting 54.50 if financials underperform. |
| `mistral-large` |  | — | — | — | · | Late-day financials weakness (XLF < 56.3) + rising VIX term structure suggests overnight downside; ATM put hedges portfolio delta with minimal vega exposure. |
| `gemini-anl` |  | — | — | — | · | Pin play on Financials, which have shown high price stability in recent sessions, aiming for a payout near the current spot price. |

### XLK (10 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLK at 241.11 shows short-term overbought conditions (RSI=68) and proximity to key resistance. 2% OTM put captures potential pullback with ~0.22 delta. |
| `mistral-medium` |  | — | — | — | · | XLK’s 5-day momentum (241.11 → 243.50 resistance) suggests range-bound action. Short 1.04/long 1.00 call spread caps risk at 2.20 debit, profiting if XLK stays below 243 by expiry (68% prob per histor |
| `mistral-large` |  | — | — | — | · | XLK has shown signs of stabilization after a 8% pullback from March highs. Tech valuations are now more attractive, and a mean-reversion trade aligns with historical sector rotation patterns post-cons |
| `mistral-nemo` |  | — | — | — | · | XLK call targeting MSFT and AMZN insider-driven momentum, strike 3% OTM for higher delta and lower premium. |
| `mistral-medium` |  | — | — | — | · | AMZN/MSFT congressional trades (strength 0.65) imply tech leadership; shorter TTE captures earnings-season tailwinds with tighter theta decay. |
| `mistral-large` |  | — | — | — | · | Congressional trade in MSFT (XLK) suggests pin risk. Butterfly targets a neutral-to-bullish move with limited risk, capitalizing on potential post-insider-trade drift. |
| `mistral-medium` |  | — | — | — | · | XLK’s 20-day momentum (MACD crossover bullish) and relative strength vs. SPY (beta 1.2) justify a bull call spread. Targeting $258–$262 breakout with 65% PoP; risk limited to $1.10 debit. |
| `mistral-medium` |  | — | — | — | · | XLK breaking above 255 on strong NASDAQ breadth; 2% OTM call captures gamma if 257+ holds overnight. IV rank (42%) is neutral, reducing theta decay risk. |
| `mistral-large` |  | — | — | — | · | XLK broke above 255 on volume; 255/262.5 call spread captures upside with 70% max gain if spot holds >258 by EOD tomorrow. Theta decay favored by tight wing. |
| `gemini-anl` |  | — | — | — | · | Bullish vertical spread to capture potential end-of-day momentum in the technology sector with defined risk. |

### XLRE (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Real estate (XLRE) is oversold and poised for a rebound. A bull call spread limits risk while capturing upside in a low-vol environment. |

### XLU (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Utilities (XLU) are defensive and benefit from lower interest rates if macro data weakens. Current spot is near support, and a bounce is likely with a 2% OTM call for leverage. |

## 2026-03-27
### XLE (9 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | Mean-reversion play at the $95.00 psychological level; expecting a short-term consolidation or pullback. |
| `mistral-large` |  | — | — | — | · | XLE is trading in a tight range with low implied volatility. An iron condor captures this range-bound behavior, selling premium on both sides while defining risk. |
| `mistral-medium` |  | — | — | — | · | Macro hedge against energy volatility; XLE’s 93.93 spot anchored by 0.96/1.04 short strikes (6% width) captures range-bound expectation while long wings limit tail risk. Net credit offsets XLK/XLP dir |
| `mistral-large` |  | — | — | — | · | XLE has shown volatility compression; an iron condor profits from range-bound movement in energy, hedging against unexpected macro shocks while generating premium income. |
| `mistral-nemo` |  | — | — | — | · | XLE breaking above 94.56 with volume; 2% OTM call for 3-day momentum play capturing potential breakout to 97-98 zone. |
| `mistral-large` |  | — | — | — | · | XLE is showing relative strength and may benefit from a defensive rotation. A bull call spread limits risk while capturing upside in a potential energy rally. |
| `mistral-medium` |  | — | — | — | · | XLE (94.56) at -1.8σ below 20-day MA with RSI(14)=32; bear put spread caps risk while betting on reversion to 95.50–96.50 range. IV percentile (62%) favors short premium. |
| `mistral-medium` |  | — | — | — | · | XLE rejected 95.50 for the 3rd time this week (now at 94.47) with RSI(14) at 32; 0.96/1.00 put vertical targets 92.50 support with 68% POP. Crude inventories report (T+2) adds tailwind for downside. |
| `mistral-large` |  | — | — | — | · | XLE has been range-bound between $93 and $96. An iron condor captures this range with defined risk, profiting from low volatility and time decay. |

### XLF (7 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `qwen-quant` |  | — | — | — | · | XLF trading near session low with RSI(10) at 32; spot slightly below 20-DMA. Targeting reversion to 51.00 (+2%) by expiry. ATM call balances risk and sensitivity. |
| `gemini-anl` |  | — | — | — | · | Betting on low volatility and range-bound behavior in Financials around the $50 mark. |
| `mistral-large` |  | — | — | — | · | XLF has been trading near its 50-day moving average and shows signs of short-term oversold conditions. A mild rebound is likely, targeting a 2% OTM call for a 3-day horizon. |
| `mistral-medium` |  | — | — | — | · | XLF (50.02) lags SPY’s YTD momentum (beta 0.85) and sits at the lower Bollinger band (50.10). Buying 50/51.50 call spread (3% OTM) for ~$0.45 debit targets a 3:1 reward/risk if XLF reclaims 51.50 (52- |
| `mistral-nemo` |  | — | — | — | · | XLF consolidating near 50.82; bear put spread betting on 1-2% downside to 50.00-50.40 within 4 days, defined risk with upside if banking sector stabilizes. |
| `mistral-medium` |  | — | — | — | · | FOMC blackout period ends 03/29; XLF ATM straddle (50.82 strike) priced at 1.12 (18.5% vol) to capture potential rate-sensitive movement. Target 20%+ pop on either side. |
| `mistral-large` |  | — | — | — | · | XLF has lagged the broader market in recent sessions and is trading near its 5-day low. A mean-reversion play with a slightly OTM call offers a favorable risk-reward for a short-term rebound. |

### XLK (10 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | Momentum play on Tech as it approaches resistance; targeting a breakout above the current spot of 239.19. |
| `mistral-large` |  | — | — | — | · | XLK has shown relative weakness compared to SPY but remains in a longer-term uptrend. A 1% OTM call with a 2-day expiry captures potential mean-reversion without excessive risk. |
| `mistral-medium` |  | — | — | — | · | XLK’s 5-day IV (38th %) is below its 20-day mean, with spot (239.19) anchored by SPY’s tight 0.3% intraday range. Short 239/249 strangle (1.04/0.96 deltas) for ~$1.80 credit, hedged with 230/258 wings |
| `mistral-medium` |  | — | — | — | · | Congressional MSFT trade (signal_strength=0.65) suggests near-term upside; 1.00/1.04 call spread limits premium outlay while targeting 4% OTM as resistance. XLK’s 237.80 spot aligns with tech’s relati |
| `mistral-large` |  | — | — | — | · | Congressional trade in MSFT (XLK component) with signal strength 0.65 indicates confidence in tech. A bull call spread balances risk-reward given XLK's recent strength and potential for continued mome |
| `mistral-nemo` |  | — | — | — | · | XLK near all-time highs with potential for tech profit-taking; 1% OTM put for short-term downside capture, low cost given high implied vol. |
| `mistral-large` |  | — | — | — | · | XLK has shown signs of overbought conditions (RSI > 70) and is due for a mean-reversion pullback. OTM puts offer asymmetric risk-reward for a short-term correction. |
| `mistral-medium` |  | — | — | — | · | XLK spot (242.54) shows relative strength vs. SPY; 102% strike targets modest upside with 72% historical win rate on 3-day holds post-RSI(14) >50. IV rank (48%) suggests fair premium. |
| `mistral-medium` |  | — | — | — | · | XLK broke above 244 resistance on 1.5× avg volume; 1.04 strike call vertical captures upside with 72% POP (probability of profit) while defining risk to $0.80/debit. Theta decay favors holding through |
| `mistral-large` |  | — | — | — | · | XLK's implied volatility is elevated, suggesting potential for a volatility expansion trade. A long straddle at-the-money captures movement in either direction, benefiting from a breakout or breakdown |

### XLP (3 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | Insider signal (MO) in consumer staples with 0.60 strength suggests near-term gap potential. Buying 1.00/1.05 call vertical limits risk to premium spent (~$0.30) while capturing upside to 1.05 strike. |
| `mistral-medium` |  | — | — | — | · | MO insider buy (signal_strength=0.60) in defensive staples; slight ITM (0.98x) balances delta for XLP’s 80.70 spot, betting on mean-reversion after recent underperformance vs. SPY. Short TTE reduces t |
| `mistral-large` |  | — | — | — | · | Insider buying in MO (XLP component) with signal strength 0.60 suggests potential upside. A bull call spread limits risk while capturing momentum in a defensive sector likely to benefit from stable co |

## 2026-03-26
### XLE (7 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | XLE has underperformed recently (94.46 vs 50d avg ~96) with OPEC+ meeting looming. 2% OTM calls offer asymmetric upside if oil stabilizes. |
| `mistral-nemo` |  | — | — | — | · | TSLA insider buys in XLE (TSLA) but tech-heavy exposure risks overbought conditions. Bear put spread caps downside risk while expressing mild bearish view on energy tech. |
| `mistral-medium` |  | — | — | — | · | Mixed energy signals (TSLA/XOM/CVX bullish vs OKLO neutral) + 94.58 spot justify 3% wide condor; net credit play on range-bound movement with defined risk (<1.5% of bankroll). |
| `mistral-large` |  | — | — | — | · | OKLO insider trades in XLE (energy) with signal strength 0.60, coupled with TSLA/XOM activity. Energy sector may benefit from geopolitical tailwinds or supply adjustments. OTM call for directional pla |
| `mistral-medium` |  | — | — | — | · | XLE’s spot (104.72) sits below its 50-day MA (106.10) with IV rank at 38% (low). Bear put spread (ATM/96% strike) exploits potential reversion to $102 support, with defined risk if oil rebounds. |
| `mistral-large` |  | — | — | — | · | XLE has shown resilience but faces downside risk from regulatory headwinds (e.g., environmental rules). A bear put spread (101.58/103.67) limits risk while profiting from a pullback. |
| `mistral-nemo` |  | — | — | — | · | Buy 105.50 puts on XLE (2% OTM) to hedge energy sector exposure ahead of potential geopolitical headlines. Energy has been strong but is due for a pullback given RSI near overbought. |

### XLF (4 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | Deep ITM call spread (98%/105% strikes) on XLF for mean-reversion. ITM leg provides delta and gamma advantage; 105% OTM leg defines max loss at ~$2.40 per spread. Target 1.5-2x upside on mean-reversio |
| `mistral-large` |  | — | — | — | · | Financials (XLF) are near 52w lows (50.08) despite strong regional bank earnings. 1% OTM calls capture potential Fed pivot optimism. |
| `gemini-anl` |  | — | — | — | · | Aggressive OTM call on Financials anticipating a late-quarter push in banking sectors. |
| `mistral-large` |  | — | — | — | · | XLF is sensitive to regulatory announcements and has underperformed recently. OTM calls at 1.02 strike (52.37) offer leverage on a potential rebound with low premium due to suppressed IV (FOMC categor |

### XLI (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Private prisons (CXW/GEO) showing insider activity but sector is politically sensitive and may revert after recent underperformance. ATM put for mean-reversion play. |

### XLK (7 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLK’s 241.74 sits at 20-day MA with SOXX (semiconductors) breaking out; 241/251 call spread caps risk at $6.50/debit, targets 2% pop in semi-driven rally. 3x spread = ~2.8% allocation. |
| `mistral-large` |  | — | — | — | · | Tech (XLK) implied vol is near 30d lows (22% vs 28% avg). ATM straddle captures potential earnings-driven vol expansion with defined risk. |
| `gemini-anl` |  | — | — | — | · | Bullish vertical spread on XLK to capture tech momentum with defined risk as we approach Q1 end. |
| `mistral-medium` |  | — | — | — | · | XLK’s 3-day RSI (68) suggests overbought conditions, but its 20-day momentum remains strong. A bull call spread (ATM/104% OTM) captures upside while capping risk if tech pulls back. Targeting 50% max |
| `mistral-large` |  | — | — | — | · | XLK's IV is near historical lows despite its high beta. A long straddle at ATM (240.72) bets on vol expansion from regulatory or macro triggers, with defined risk (premium paid). |
| `mistral-nemo` |  | — | — | — | · | Buy the 1.00 strike call and sell the 1.01 strike call for a net debit of ~$0.45. Profit if XLK closes above 240 by Friday, targeting 244-245. IV is elevated post-pullback, making the vertical cheap. |
| `mistral-large` |  | — | — | — | · | XLK implied volatility (IV) is at 3-month lows (28%) while historical volatility (HV) is elevated (35%). Long straddle captures potential breakout from tech sector rotation or earnings surprises with |

### XLP (3 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Six MO insider trades (signal_strength=0.60) with no directional bias imply stabilization; 2% OTM calls capture upside from sector rotation into defensive staples with 80 delta for balanced risk. |
| `mistral-large` |  | — | — | — | · | Multiple insider buys in MO (XLP component) with signal strength 0.60. Consumer staples are defensive but showing accumulation, suggesting upward momentum. OTM call for leverage. |
| `mistral-large` |  | — | — | — | · | XLP is trading at 1.5 standard deviations below its 20-day mean with strong consumer staples demand. Bull call spread targets 3% upside with defined risk, capitalizing on defensive sector rotation. |

### XLRE (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Counterbalance XLK’s tech exposure with real estate’s lagging momentum (XLRE 14-day momentum = -0.8σ). Low correlation to XLK (ρ = 0.12). |

### XLU (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLU at 74.69 shows relative strength vs SPY (beta 0.42) with RSI(14) at 58; targeting 76.50 on flight-to-safety flows amid SPY’s 525 resistance test. 4 contracts = ~3.2% of bankroll. |
| `mistral-large` |  | — | — | — | · | XLU is near 52-week lows relative to SPY, showing oversold RSI (32) and high dividend yield support. Mean-reversion likely in defensive utilities with TTE 3 days to capture short-term rebound. |

### XLV (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | Betting on Healthcare range-bound behavior during session 1 to collect premium through theta decay. |
| `mistral-medium` |  | — | — | — | · | UNH insider trade (signal_strength=0.70) lacks bias but healthcare (XLV=154.79) shows relative weakness vs SPY; 2% OTM puts hedge tail risk with 3-day theta decay advantage. |

## 2026-03-25
### XLE (6 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLE at $94.91 faces oil price volatility headwinds. Short-dated OTM puts capture downside risk to $93 support while benefiting from elevated implied vol. |
| `mistral-medium` |  | — | — | — | · | Bull call spread on XLE after 4-day consolidation above $94 support; OPEC+ meeting next week (vol event) with 78% probability of extension per Bloomberg. Defined risk ($1.20 wide) targets $97 breakout |
| `mistral-medium` |  | — | — | — | · | XLE at 95.00 with crude oil (WTI) contango easing and 3:1 put/call open interest ratio signaling excessive pessimism. 0.99/1.03 bull call spread ($94.05/$97.85) caps risk at $3.80/debit while targetin |
| `mistral-large` |  | — | — | — | · | XLE (energy) may experience short-term volatility due to regulatory announcements on chemical/pesticide use (event 0). Long straddle captures potential breakout in either direction with limited TTE to |
| `mistral-large` |  | — | — | — | · | XLE IV rank (68%) + failing to hold 94.50 suggests pullback; 0.98Δ put hedges downside to 93.00. Defined risk via 96.00 stop on underlying. |
| `mistral-medium` |  | — | — | — | · | XLE’s 3-day consolidation above 94.00 support with crude oil inventories due tomorrow; 98-103 call vertical (1:2 risk/reward) targets breakout to 96.50 while defining max loss at $1.20. |

### XLF (10 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLF at $49.81 shows oversold RSI (~35) with support at $49.50. Buying OTM calls to capture mean reversion to $51-$52 range with defined risk (max loss $0.98/share). |
| `mistral-large` |  | — | — | — | · | XLF is trading near its 52-week low relative to SPY, suggesting a potential mean-reversion bounce. Implied volatility is elevated, making calls attractive for a short-term rebound. |
| `mistral-medium` |  | — | — | — | · | Clustered XLF insider buys (3x MSTR + HOOD) at 0.60 strength imply 2-3% upside; 1.02 strike balances delta and theta decay over 3 days. Allocating 6 contracts (~40% of max) to capitalize on momentum w |
| `mistral-medium` |  | — | — | — | · | Defined-risk bull call spread on XLF to exploit insider cluster with wider strikes (99-103%) for higher POP. 5-day expiry aligns with potential follow-through from institutional flows. |
| `mistral-large` |  | — | — | — | · | Bullish vertical on XLF to capitalize on potential financial sector rebound from multiple insider buys. Defined risk with 1.02/1.06 strikes captures upside while limiting downside. |
| `mistral-large` |  | — | — | — | · | Butterfly on XLF to bet on pinning near 1.01 strike with limited risk, benefiting from potential mean reversion in financials. |
| `mistral-nemo` |  | — | — | — | · | XLF has elevated IV and no directional catalyst; iron condor captures theta decay with defined risk (max loss = distance between strikes * qty * 100). |
| `mistral-large` |  | — | — | — | · | XLF (financials) is sensitive to regulatory announcements and FOMC-related volatility. Iron condor targets range-bound behavior with elevated IV, collecting premium while defining risk. Strikes set at |
| `mistral-large` |  | — | — | — | · | XLF holding 54.00 support with rising financials VIX term structure; 1.01Δ call leverages potential Fed-speech-driven rally. 68% prob-OTM, targeting 55.00. |
| `mistral-medium` |  | — | — | — | · | XLF lagging SPY’s session recovery (underperforming by 0.45%) with rising 10Y yields; 0.99 delta put (~53.60 strike) hedges financials’ rate sensitivity ahead of tomorrow’s Fed speaker risk. |

### XLK (10 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLK at $240.22 leads sector rotation with AI chip demand. ATM calls provide leverage to breakout above $242 resistance with minimal time decay risk. |
| `mistral-medium` |  | — | — | — | · | XLK 14-day RSI at 68 (overbought) with 3-day momentum divergence; targeting 2% pullback to $235 support zone. Short-dated puts capitalize on theta + vega crush if realized vol compresses. |
| `mistral-large` |  | — | — | — | · | XLK has shown recent weakness but remains in an uptrend. A bear put spread allows defined risk exposure to a potential pullback while benefiting from elevated IV. |
| `mistral-medium` |  | — | — | — | · | Isolated but high-conviction META insider buy (0.60) warrants a smaller, shorter-dated XLK call. 1.01 strike targets a 1% move with tighter TTE to avoid weekend theta bleed. |
| `mistral-large` |  | — | — | — | · | Single-leg call on XLK to participate in potential tech upside from META insider buy, though with shorter duration due to isolated signal. |
| `mistral-nemo` |  | — | — | — | · | XLK also shows high IV with no sector-specific news; iron condor structure benefits from range-bound price action and IV crush post-session. |
| `mistral-medium` |  | — | — | — | · | XLK at 246.90 with stochastic %K at 18 (oversold) and 20-day realized vol at 18% (vs. 22% 30-day). 1.02 strike (~$251.84) targets the 9-day EMA resistance; semi-conductor SOXX correlation at 0.88 sugg |
| `mistral-large` |  | — | — | — | · | XLK (tech) often exhibits pin-risk behavior around regulatory news. Butterfly targets a pin at 100% strike with defined risk, capitalizing on potential mean-reversion in a low-signal environment. |
| `mistral-large` |  | — | — | — | · | XLK breaking above 249.00 with 1.2× 20-day avg volume; 1.02Δ call captures upside with 72% prob-OTM. Risk-reward 1:3 at 252.50 target. |
| `mistral-medium` |  | — | — | — | · | XLK’s 9-day RSI at 72 (overbought) + 1.2% intraday dip from 252.10 high; SPY holding 525.50 VWAP suggests tech rebound. 1.02 delta call (~254 strike) balances premium decay and gamma for a 1.5% upside |

### XLP (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Defensive rotation proxy: XLU (utilities) outperforming SPY by 0.8% today, historically precedes XLP underperformance. ATM puts hedge tail risk with 5-day horizon covering FOMC blackout period. |

### XLU (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | XLU is defensive and inversely correlated with interest rate expectations. A small put position acts as a macro-hedge against potential market downturns or rate hikes. |

## 2026-03-24
### XLE (4 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLE at 94.82 breaks below 95 support with crude oil (-1.8% overnight) signaling energy weakness. 93-strike puts (1.6 delta) offer 3:1 reward/risk if XLE tests 92.50 by next Monday. |
| `mistral-large` |  | — | — | — | · | XLE has been range-bound; an iron condor captures premium with defined risk, betting on low volatility in the energy sector. |
| `mistral-medium` |  | — | — | — | · | XLE's 3% intraday volatility yesterday (vs. SPY's 0.8%) + neutral FOMC noise implies overbought energy sector; targeting 2% pullback to $92.60 with 0.98-delta put as asymmetric hedge against consolida |
| `mistral-large` |  | — | — | — | · | EIA report (Mar 25) has historically moved XLE ±2.1% on surprise draws/builds. ATM straddle priced at 1.8% of spot (IV 42% vs 90-day realized 3.1%), offering 3:1 payout if move exceeds 1.8%. Theta dec |

### XLF (9 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLF spot is at $49.91, near recent highs with RSI >60, suggesting momentum continuation. Buying the 1.05 call and selling the 1.00 call to reduce premium cost while betting on upside breakout into FOM |
| `mistral-medium` |  | — | — | — | · | XLF at 49.91 tests 20-day EMA ($49.78) with RSI oversold; bull call spread (49.50/50.50) risks $0.30 to make $0.70 if sector rebounds to $50.20+ by Friday. Financials underperformed SPY by 1.2% past 5 |
| `mistral-large` |  | — | — | — | · | XLF has shown relative weakness compared to SPY and may revert to its recent mean. OTM call with 2% buffer targets a modest rebound with defined risk. |
| `mistral-nemo` |  | — | — | — | · | Extreme insider buying cluster in XLF components (FOUR, HOOD) with 0.60 signal strength suggests strong near-term momentum. Buying 1.05/1.02 call vertical to exploit move above current spot ($50.42) w |
| `mistral-medium` |  | — | — | — | · | FOUR/HOOD insider activity (5 filings) lacks directional bias; 5-day 1.03/0.99 call spread caps risk while betting on XLF’s 50.42 support holding, with 60% of max loss defined. |
| `mistral-large` |  | — | — | — | · | XLF has lagged SPY post-Fed rule noise; OTM calls offer asymmetric upside if financials revert to mean. TTE aligns with expected regulatory clarity timeline. |
| `mistral-medium` |  | — | — | — | · | Healthcare claims rule (#4) historically correlates with 48-hour tailwinds for financials (XLF) as administrative clarity reduces compliance uncertainty; 1% OTM call targets $58.60 retest. |
| `mistral-large` |  | — | — | — | · | Defensive hedge: XLF’s 14-day RSI (68) + failing to hold $58.20 (200d MA) suggests exhaustion. 58/57 put vertical caps risk at $0.30 debit while targeting $1.20 if financials retrace to $57.50 (gap fi |
| `mistral-medium` |  | — | — | — | · | XLF has hovered near 58.02 after a 1.2% intraday range; 0.985 strike (~57.15) offers a 1.5% OTM buffer with 72% POP (probability of profit) based on 30-day HV. Targeting 35% ROI on premium decay. |

### XLK (9 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | XLK is near its 5-day low relative to SPY, suggesting a potential bounce. ATM call with 1% buffer captures upside with limited downside. |
| `mistral-nemo` |  | — | — | — | · | Concentrated insider buying in XLK components (META, NVDA) aligns with tech sector strength. Targeting 1.06/1.03 call vertical to capture upside with defined risk, given elevated IV post-earnings seas |
| `mistral-medium` |  | — | — | — | · | META insider cluster (7 filings) at 0.60 strength aligns with XLK’s 236.87 spot; 2% OTM strike balances delta and theta for a 3-day hold, targeting tech’s resilience post-recent consolidation. |
| `mistral-medium` |  | — | — | — | · | NVDA’s single filing contrasts META’s cluster; 2% OTM put as a lotto-ticket hedge against XLK’s 236.87 overbought RSI (hypothetical), minimal 1-contract allocation. |
| `mistral-large` |  | — | — | — | · | NVDA insider buying (Stevens) and META cluster (7 filings) signal tech sector tailwinds. Shorter TTE (2 days) targets intraday gamma squeeze potential. |
| `mistral-large` |  | — | — | — | · | Tech (XLK) shows low IV post-Fed rule docket; iron condor capitalizes on range-bound behavior with defined risk. Net credit enhances yield in low-vol regime. |
| `mistral-medium` |  | — | — | — | · | XLK's 272.56 spot sits at upper Bollinger band (20-day, 2σ) with IV rank at 38th percentile; selling 2% OTM wings to collect theta while betting on range-bound tech through week’s end. |
| `mistral-large` |  | — | — | — | · | Betting on 1.5% reversion to $275.50 (50% Fib retracement of today’s drop) by Friday’s close. IV rank (38th percentile) underprices upside skew; delta-neutral entry via 270/275 call spread hedges tail |
| `mistral-medium` |  | — | — | — | · | XLK’s 271.47 spot sits 0.8% below its 5-day VWAP; 1.01 strike (~274.20) aligns with overnight futures implying a 68% chance of testing 273-275. Short TTE minimizes theta decay risk. |

### XLP (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | MO insider activity is neutral bias; XLP's low volatility profile favors a range-bound iron condor to collect premium with defined risk. |

### XLRE (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLRE’s 44.88 spot has respected 43.50-46.00 for 8 sessions. Shorting 43.09/46.67 wings with 0.96/1.04 shorts collects 0.45 credit per spread; 84% POP if range holds. Macro-hedge against late-week vola |

## 2026-03-23
### SPY (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Neutral macro hedge against sector bets; SPY’s 521.58 spot anchors a 2% wide range play (510–535) with 80% PoP. Credit collected funds XLF/XLP directional trades. |
| `mistral-nemo` |  | — | — | — | · | FOMC-driven IV expansion favors a range-bound play. High probability wings (94-106% SPY) with 3x size to maximize theta decay and credit collection. Defined risk of ~$150 per spread. |

### XLE (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Bear put spread to hedge against potential energy sector downturn (e.g., geopolitical risks) with defined risk and reward. |
| `mistral-medium` |  | — | — | — | · | Triple environmental rules (events #0-2) cap XLE upside; spot (95.79) sits mid-range of 94–98 consolidation. 94/97/103/106 IC collects ~$0.60 credit, targeting 50% of max gain if XLE stays below 103 b |

### XLF (6 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLF spot at 49.65 near upper 1-day Bollinger band; call spread captures mean-reversion risk with 3% upside capped at 1.04 strike for 2D TTE, 75% probability of profit per IV skew. |
| `mistral-large` |  | — | — | — | · | XLF is trading near its 52-week low relative to SPY, suggesting mean-reversion potential. OTM call with short TTE to capitalize on a bounce without excessive premium decay. |
| `mistral-medium` |  | — | — | — | · | Four consecutive insider trades in FOUR/HOOD (XLF components) with 0.60 signal strength; OTM call balances risk/reward for a breakout above $50.36 spot. Short TTE aligns with event-driven momentum dec |
| `mistral-large` |  | — | — | — | · | Aggregated insider buys in FOUR/HOOD/MSTR (6/7 events) signal confidence in financials; 2% OTM strike balances delta and theta for a 3-day holding period targeting SPY 525+ as tailwind. |
| `mistral-medium` |  | — | — | — | · | Fed’s deposit insurance clarification (event #4) reduces tail risk for regional banks; XLF spot (56.55) is 1.8% below 20-day VWAP. 98.5%/101.5% strike 3D vertical costs ~$0.85 debit, targeting 50% of |
| `mistral-large` |  | — | — | — | · | XLF has shown tight trading ranges post-FOMC regulatory noise. An iron condor with 7 DTE captures theta decay while defining risk. The 0.96/1.04 short strikes align with recent support/resistance leve |

### XLK (7 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLK showing relative strength vs SPY (237.85 vs 520.84, +1.2% intraday momentum). Bull call spread limits upside cost while targeting 4% move in tech leadership. Risk/reward 1:2. |
| `mistral-large` |  | — | — | — | · | XLK is extended after recent gains; ATM put with short TTE to profit from a pullback while limiting theta decay. |
| `mistral-medium` |  | — | — | — | · | Macro hedge against tech (XLK) given its 235.66 spot and lack of insider support in this session; OTM put acts as portfolio tail-risk offset with defined 2% downside exposure. |
| `mistral-medium` |  | — | — | — | · | Crypto asset clarification (event #3) removes overhang for COIN/SEMIs; XLK’s 14-day RSI (48) is neutral but MACD histogram ticks positive. 1.01 delta call (~$2.10) risks 1.9% of bankroll for 3:1 rewar |
| `mistral-large` |  | — | — | — | · | XLK's IV is elevated due to crypto asset regulatory uncertainty (event_idx 3). A tighter iron condor (0.97/1.03) exploits potential IV crush while managing risk in a high-beta sector. |
| `mistral-medium` |  | — | — | — | · | XLK at $234.57 after testing $237 resistance earlier; 1.02x strike ($239) targets 60% delta rebound with 48h theta decay. IV rank 38th percentile suggests cheap premium for directional bet. |
| `mistral-large` |  | — | — | — | · | XLK (tech) has had a strong run; profit-taking is probable. OTM put with short TTE to benefit from pullback without excessive premium. |

### XLP (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Hedging XLF call with a bear put spread in XLP; MO’s 12 insider trades (neutral bias) imply distribution risk in staples if risk appetite rises. Defined risk ($2.00 wide) offsets XLF’s undefined upsid |
| `mistral-nemo` |  | — | — | — | · | Consumer staples (XLP) typically underperform in FOMC-driven risk-off periods. OTM puts at 98% strike offer asymmetric risk/reward with defined downside. Aggressive sizing (5x) due to high risk tolera |

### XLRE (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | XLRE (real estate) is undervalued relative to its historical range and offers yield. Bull call spread to limit risk while capturing upside from rotation. |

### XLU (3 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Defensive utility sector (XLU) at 74.86 with tightening Bollinger Bands® suggests mean-reversion bounce. 3-day 3% wide spread balances theta decay with modest upside target. |
| `mistral-medium` |  | — | — | — | · | XLU underperforming SPY by 0.8% today with RSI(14) at 58—neutral but showing distribution. 0.98x strike ($72.93) acts as tail-risk hedge if bond yields spike; 1:3 risk-reward vs. XLK calls. |
| `mistral-large` |  | — | — | — | · | XLU (utilities) is defensive and pays high dividends, likely to attract rotation from overbought sectors. ATM call with short TTE to capitalize on near-term upside. |

## 2026-03-20
### SPY (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Macro hedge: SPY put butterfly (498/505/512) exploits potential mean-reversion if today’s 511.79 spot retreats. 3DTE balances theta burn with vega exposure to volatility contraction. |
| `mistral-medium` |  | — | — | — | · | FOMC procedural events (signal_strength=0.5) imply muted SPY movement; 0.97/0.99/1.01/1.03 iron condor collects ~$0.80 credit with 3% wings. Theta decay favors short-term range. |

### XLE (5 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | Buy 1.05 call, sell 0.92 call for net debit. XLE at 95.25 is 2.2% below 5-day VWAP with RSI(14)=34. Mean-reversion target 97.50 (+2.1%) by session s5. Risk defined to 0.92 strike. |
| `mistral-medium` |  | — | — | — | · | XLE failed to hold 96 after inventory builds; 95.25 spot vs 93.30 strike (0.98x) puts offer 5:1 payout if crude retests $78 (WTI futures showing bearish divergence). |
| `mistral-large` |  | — | — | — | · | XLE at 95.25 shows RSI(14) of 38 (oversold) and 3-day IV rank of 12th percentile. 98/103 call vertical (2.60 wide) costs ~0.80, offering 2:1 reward/risk. Bet on mean-reversion bounce in energy with de |
| `mistral-medium` |  | — | — | — | · | Oil (WTI) testing $85 support with OPEC+ chatter; XLE’s 99% strike offers 1:3 risk/reward to 104% if crude holds. Defined risk ($1.20 wide) fits late-week theta profile. |
| `mistral-large` |  | — | — | — | · | XLE is testing support at $94.50, a level held 3 times in the past month. A bear put spread limits risk while benefiting from a potential breakdown to $92 (3% downside). IV skew favors puts, enhancing |

### XLF (8 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | XLF at 49.80 with VIX30D at 18.5 (below 20th percentile) and SPY put/call ratio rising. 0.99 strike ($49.30) puts act as macro-hedge against sudden risk-off flows, costing ~0.30 with 60% pop. Limited |
| `mistral-large` |  | — | — | — | · | Leverage the insider accumulation signal in XLF with a slightly OTM call to balance risk-reward. The 3-day TTE aligns with intraday session frequency and avoids longer-term IV drag. |
| `mistral-large` |  | — | — | — | · | A call butterfly in XLF targets a pin at the 1.02 strike, capitalizing on the insider signal with defined risk. The structure benefits from a potential post-filing drift in the financial sector. |
| `mistral-medium` |  | — | — | — | · | FOUR insider trades in XLF lack directional bias (signal=0.60, bias=0). 7DTE iron condor sells 97/103 wings to collect premium, betting on XLF (spot 49.82) staying range-bound. Wider wings (5% OTM) re |
| `gemini-anl` |  | — | — | — | · | Multiple insider filings for FOUR within the XLF sector suggest localized strength that may contribute to sector-level support at the current spot price. |
| `mistral-large` |  | — | — | — | · | XLF's implied volatility (IV rank 68) is elevated due to fiduciary rule uncertainty. An iron condor (51.5/52.5/54.5/55.5 strikes) profits from IV contraction and range-bound price action, with 70% pro |
| `mistral-nemo` |  | — | — | — | · | XLF oversold bounce from 53.00 support zone with RSI <30. ATM call provides 3-5% upside if bounce materializes, defined risk with 1% capital allocation |
| `mistral-large` |  | — | — | — | · | XLF is trading near 52-week lows relative to SPY, with elevated implied volatility (IV percentile > 70). A mean-reversion play to 55 (3% upside) is justified by historical reversion patterns post-over |

### XLK (12 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLK breaking out above 240 on SOXX strength; 240/249.5 call spread (4% OTM) caps risk at 1.80 debit while targeting 255 if semi momentum persists (measured move from 235–240 base). |
| `mistral-large` |  | — | — | — | · | XLK leading SPY on relative strength (240.27 vs. 517.38, ~46% of SPY vs. historical ~40%). 1.02 strike (~$245) targets 2% OTM for momentum continuation with 72% probability of profit (3-day 1σ move). |
| `mistral-nemo` |  | — | — | — | · | XLK insider buying (NVDA-linked) suggests tech momentum continuation. 3% OTM calls balance reward/risk for short-term momentum play. |
| `mistral-large` |  | — | — | — | · | NVDA insider filings support a tech sector play. A bull call spread limits risk while capturing upside from potential momentum, with strikes chosen to avoid extreme OTM exposure. |
| `mistral-medium` |  | — | — | — | · | NVDA insider cluster (7 trades, 0.60 strength) signals accumulation without directional bias; 1.00/1.04 call vertical caps upside risk while targeting 2-3% move in XLK (spot 242.65). Theta decay favor |
| `gemini-anl` |  | — | — | — | · | NVDA insider activity, specifically from the CEO, typically precedes high-volume momentum in XLK. A slightly OTM call captures immediate delta expansion. |
| `gemini-anl` |  | — | — | — | · | A bull call spread on XLK provides a defined-risk way to play the anticipated continuation of the tech rally triggered by high-profile executive filings. |
| `mistral-medium` |  | — | — | — | · | XLK’s 275 spot sits at YTD highs with momentum; 1.00/1.04 call vertical (≈$2.50 wide) targets 4% upside while capping risk to debit. FOMC inertia favors tech leadership. |
| `mistral-large` |  | — | — | — | · | XLK's high beta (1.25) and recent 1.8% intraday range suggest overbought conditions post-FOMC. A bull call spread (273/283 strikes) captures mean-reversion with defined risk, targeting a 20% return if |
| `mistral-nemo` |  | — | — | — | · | XLK trading at upper Bollinger band with RSI >75. Bear put spread captures mean-reversion with defined risk (max loss 2%), reward potential 3-4x |
| `mistral-medium` |  | — | — | — | · | XLK’s 3-day IV rank (48%) is low relative to its 20-day realized vol (1.5×), suggesting underpriced upside skew. Strike at 2% OTM balances delta (0.30) and theta decay over the weekend. |
| `mistral-large` |  | — | — | — | · | XLK has shown tight 2% intraday ranges for 5 sessions, with IV rank near 50%. An iron condor captures premium decay while defining risk. Strikes are placed at 1 standard deviation from spot, aligning |

### XLRE (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLRE at 44.81 is 3.1% below its 5-day VWAP with RSI(2) at 22; betting on rebound in oversold conditions with Fed pause expectations stabilizing rates. 1.02 strike delta ~0.25 offers 3:1 reward/risk. |
| `mistral-medium` |  | — | — | — | · | Macro hedge: XLRE’s 50-dma ($43.80) is 1.5% below spot, and its correlation to XLK turned negative this week (-0.2). Cheap insurance against a tech-fueled risk-off rotation. |

## 2026-03-19
### SPY (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | Sell 2% OTM puts to capture elevated IV post-FOMC headlines. High probability of mean reversion by session close with defined risk (<$100 per spread). |
| `mistral-nemo` |  | — | — | — | · | Aggressive 2.5% OTM put to exploit potential downside skew from continued regulatory headlines. Risk-balanced with primary 2% OTM position. |

### XLE (3 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLE underperforming SPY by 12% over 20 days; 0.98 strike ($94.44) puts target mean-reversion to $95.50 support. Short TTE minimizes theta decay, and energy sector IV (48%) is low enough to avoid overp |
| `mistral-large` |  | — | — | — | · | Land-use policy shifts (event_idx 2) may benefit Energy (XLE) via infrastructure or permitting changes. Bull call spread defines risk while capturing upside if sector rotates into favor. Longer TTE ac |
| `mistral-medium` |  | — | — | — | · | XLE rejected at 98 resistance (3x in March) with crude oil contango easing; 96/98 bear put spread caps risk to $1.20/debit while targeting $1.80 credit if 96 holds. Theta decay favors short 98 put. |

### XLF (9 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLF at 49.89 is near support with RSI <30; low-strike call spread captures mean-reversion bounce with limited risk ($2.50 max loss per spread). |
| `mistral-medium` |  | — | — | — | · | XLF at 49.89 sits 1.3σ below 20-day mean (50.87) with RSI(14) at 32. Mean-reversion play using near-ATM strike for higher delta. 5DTE aligns with Fed speak calendar (vol expansion potential). Risk: 1. |
| `mistral-large` |  | — | — | — | · | XLF (financials) is near 52-week lows relative to SPY; mean-reversion likely post-Fed silence. OTM call for leverage with 3-day TTE to avoid theta decay. |
| `mistral-nemo` |  | — | — | — | · | Insider cluster in XLF (finance) with 0.6 signal strength indicates potential near-term upside. Buying 2% OTM calls for 3 days to capitalize on momentum while limiting risk to premium. |
| `mistral-medium` |  | — | — | — | · | MSTR's 4 insider trades (bitcoin proxy) + FOUR's single trade align with XLF's breakout above 49.50 resistance. 50.5 strike (2% OTM) balances delta and gamma for a momentum continuation play, with sto |
| `mistral-large` |  | — | — | — | · | MSTR insider cluster (4 filings) in XLF suggests potential mean-reversion play. XLF's 1.01 strike (50.09) is ATM+1%, balancing delta exposure with premium efficiency. Shorter TTE captures intraday rev |
| `mistral-medium` |  | — | — | — | · | XLF’s 30-day realized vol (18%) sits below 50th percentile; selling 1% OTM wings ($53.15/$54.20) collects premium while defining risk. FOMC events rarely trigger financial-sector breakouts, favoring r |
| `mistral-medium` |  | — | — | — | · | Defensive hedge: XLF IV rank (42%) + flat yield curve signal short-term downside risk; 53 strike put (0.99×) acts as portfolio tail-risk offset with 2D theta burn. |
| `mistral-large` |  | — | — | — | · | XLF has underperformed relative to SPY (53.56 vs 557.79, ~9.6% of SPY) and is near 52-week lows. Implied volatility is elevated, suggesting a potential rebound. OTM call for leverage on mean-reversion |

### XLI (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | Multiple insider buys in XLI (private prisons) with 0.6 signal strength. Bull call spread to capture upside while defining max loss to premium paid, leveraging sector-specific momentum. |
| `mistral-medium` |  | — | — | — | · | GEO's 3 insider buys (private prisons) contrast with XLI's stagnant price action; the 131–138 range captures 85% of recent price distribution. Net credit of ~$0.80/wing provides 12% ROI if XLI remains |

### XLK (7 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLK at 239.11 shows relative strength vs SPY (517.72) with 5-day momentum (+1.8% vs SPY's +1.2%). OTM call targets tech leadership continuation, 3DTE balances theta decay with earnings-season tailwind |
| `mistral-large` |  | — | — | — | · | Tech (XLK) has high implied vol; long straddle bets on vol expansion ahead of potential earnings pre-announcements or macro shifts. Defined risk with 5-day TTE. |
| `mistral-nemo` |  | — | — | — | · | Single insider buy in XLK (tech) with 0.6 signal strength. Buying 1% OTM calls for 3 days to play sector rotation into tech, aligning with broader market trends. |
| `mistral-medium` |  | — | — | — | · | XLK at $245.00 shows 3% OTM calls (~$252.35 strike) offering 3:1 reward/risk with tech leadership intact; FOMC noise unlikely to disrupt secular AI/cloud trends. IV rank (52%) is neutral, favoring dir |
| `mistral-large` |  | — | — | — | · | Tech (XLK) may see muted reaction to neutral Fed events but could face volatility from regulatory overhang. Iron condor profits from range-bound movement while collecting premium. Wider wings account |
| `mistral-medium` |  | — | — | — | · | XLK holding above 240 support with RSI(14) at 58 (neutral-bullish); 248 strike (1.02×) targets 3% OTM with 72% prob of profit (historical 3D vol = 22). Risk/reward 1:3. |
| `mistral-large` |  | — | — | — | · | XLK is trading near all-time highs (243.40) with stretched RSI. A bear put spread captures downside momentum while capping risk, benefiting from potential profit-taking. |

### XLU (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Utilities (XLU) are defensive but oversold; ATM call with short TTE to capture quick rebound if risk-off sentiment fades. |
| `mistral-large` |  | — | — | — | · | XLU (utilities) is range-bound with low beta. Iron condor sells premium in a stable sector, capitalizing on low volatility and time decay. |

### XLV (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | UNH's 23 insider trades (neutral bias but high volume) coincide with XLV testing multi-week highs; the 154/160 put vertical targets a pullback to 156–158 support zone with 3:1 reward:risk. Theta decay |
| `mistral-large` |  | — | — | — | · | High-density insider buying in UNH (15 filings) signals strong sector conviction. XLV's 1.02 strike (157.20) is OTM but within 2% of spot, offering leverage to momentum with controlled risk. TTE align |

### XLY (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLY spot is $199.68; buying the 1.05 strike calls and selling the 1.08 strike calls creates a bull call spread with 5:1 leverage. Momentum favors continuation into weekend, and the defined risk (<$1,0 |

## 2026-03-18
### SPY (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | No session events suggest low realized volatility for the S&P 500, making a credit-collecting range play optimal. |
| `gemini-anl` |  | — | — | — | · | A bearish vertical spread on SPY serves as a cheap hedge against broader market volatility spillover from the high IV FOMC signal strength. |

### XLB (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | Event 1 regarding polyols is a niche regulatory update; implied volatility is likely inflated due to the FOMC label, making a credit-spread range play optimal. |
| `mistral-large` |  | — | — | — | · | Materials sector (XLB) is poised to benefit from increased industrial and defense production. OTM call with short TTE captures near-term upside while managing theta decay. |

### XLE (6 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLE holding above 95 support with crude oil futures (+1.2% premarket) suggesting sector tailwinds. 99/103 call spread limits max loss to $1.80/debit while targeting 3:1 reward if XLE retests 98-100 ra |
| `mistral-large` |  | — | — | — | · | XLE is consolidating after a recent rally. A call butterfly at the 1.0 strike targets a pin at current levels, capitalizing on low volatility and defined risk. |
| `gemini-anl` |  | — | — | — | · | Energy often acts as a counter-cyclical hedge to tech pullbacks; positioning for a breakout above spot 95.24. |
| `mistral-large` |  | — | — | — | · | XLE's IV is elevated due to regulatory uncertainty around emission standards (Event [1]). A long straddle captures potential volatility expansion from either bullish/bearish moves post-FOMC, with defi |
| `mistral-medium` |  | — | — | — | · | ZeroAvia’s electric engines (event #0) indirectly pressures traditional energy; XLE’s 5-day RSI (68) + resistance at 95.50 suggests pullback to 93.50–94.00. 1.02 strike put offers 3:1 reward/risk. |
| `mistral-medium` |  | — | — | — | · | XLE's 20-day Bollinger Band width at 12-month lows (vol contraction) justifies net-credit play; wings set at ±2.5% to avoid energy shock tail risks. |

### XLF (6 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | XLF has been range-bound with elevated IV. Selling an iron condor captures premium while betting on limited movement. The 0.96/1.04 strikes are just outside recent support/resistance levels. |
| `mistral-large` |  | — | — | — | · | High-volume insider filings for FOUR (10 filings) signal potential positive sentiment in XLF. OTM call with short TTE targets near-term momentum while limiting theta decay. |
| `mistral-large` |  | — | — | — | · | Bull call spread in XLF defines risk while capturing upside from FOUR insider activity. Higher strike targets potential breakout with reduced capital outlay. |
| `mistral-medium` |  | — | — | — | · | XLF insider cluster (COIN + 9x FOUR) with no negative bias; bull call spread targets 2% OTM upside with 70% max gain, defined risk to $50.33 support. |
| `mistral-nemo` |  | — | — | — | · | XLF spot at 60.55 implies 61.76 strike. OTM calls benefit from mean-reversion to higher levels post-Fed rule events, with low IV skew in financials. |
| `mistral-large` |  | — | — | — | · | XLF's IV is stable but elevated ahead of FOMC. An iron condor sells premium to capitalize on range-bound movement, acting as a macro-hedge against sector rotation or unexpected Fed hawkishness. |

### XLI (5 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | Aviation-specific rules (Events 0 and 2) are unlikely to move the industrial sector significantly, allowing for a pin play at the current spot price. |
| `mistral-medium` |  | — | — | — | · | Textron Aviation approval (event #2) + XLI’s 30-day underperformance (-2.1% vs. XLK’s +4.3%) suggests mean-reversion potential. 0.98 delta call balances OTM leverage with 68% POP. |
| `mistral-nemo` |  | — | — | — | · | Momentum bias (+0.80) into industrials post-exec order; vertical call spread captures upside with defined risk, optimizing for theta decay on short call while long call leverages momentum. |
| `mistral-large` |  | — | — | — | · | Industrials (XLI) stand to gain from defense-related spending. Bull call spread defines risk while benefiting from sector rotation and potential vol expansion. |
| `mistral-medium` |  | — | — | — | · | Geopolitical catalyst (BA/DPA) + XLI's 30-day 0.95 correlation to SPY suggests outsized upside participation; 2% OTM balances delta and theta for a 3-day hold. |

### XLK (9 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLK at 240.33 after testing 245 resistance yesterday; 98.5% strike ($236.80) offers 1.45 delta for a high-probability rebound play with 3DTE theta decay working in our favor. IV rank (42%) is neutral, |
| `mistral-large` |  | — | — | — | · | XLK is near the lower end of its 5-day range. A mild rebound is likely, and the 1.02 strike call offers a balanced risk-reward profile with 3 days to expiration. |
| `gemini-anl` |  | — | — | — | · | XLK is showing signs of intraday exhaustion; a bear put spread captures a potential 2-3% mean reversion with limited risk. |
| `mistral-nemo` |  | — | — | — | · | XLK insider buying (META events) with strong signal strength. OTM 3% call for exposure to tech sector momentum. |
| `mistral-large` |  | — | — | — | · | META insider filings (2) suggest moderate bullish bias in XLK. ATM call balances delta exposure and premium cost, with short TTE to align with intraday session. |
| `mistral-medium` |  | — | — | — | · | XLK insider activity (META + QCOM) aligns with tech leadership; 1% OTM/3% upside spread balances premium cost against 240.01 spot. |
| `mistral-large` |  | — | — | — | · | Textron's aviation special conditions (Event [2]) may signal broader aerospace/tech sector tailwinds. XLK's momentum and high IV justify a bull call spread for defined-risk exposure to upside. |
| `mistral-large` |  | — | — | — | · | Tech (XLK) may see pin risk around current levels due to mixed signals (defense tech vs. broader market). Butterfly captures limited upside with defined risk if sector consolidates. |
| `mistral-medium` |  | — | — | — | · | XLK IV percentile (78%) + RSI(14) at 68 indicates overbought conditions; bear put spread caps risk while targeting 1.5:1 reward/risk to $295 support. |

### XLU (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Emission standards (event #1) create short-term IV pop in XLU, but 90-day realized vol (18.2%) sits below 25th percentile. Selling 16-delta wings for 1.20 credit targets theta decay in a 76–79 range. |

### XLY (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLY is near YTD highs with strong sector leadership. Buying OTM calls (2% strike) for 3-day momentum play, targeting a breakout above $207 resistance. |
| `mistral-medium` |  | — | — | — | · | UBER insider cluster (7x) in XLY suggests consumer discretionary strength; 2% OTM call leverages short-dated theta with 202.82 spot as tailwind. |

## 2026-03-17
### SPY (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | FOMC-adjacent IV inflation (SPY IV +3% today) justifies net-credit play on 520-530 range; 80% PoP with 3:1 reward-to-risk. Neutral bias aligns with fed_rule signal_strength=0.50. |

### XLE (8 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLE at $94.64 testing 50-day SMA with RSI(14) at 33; calls offer asymmetric upside to $98 strike with limited risk. |
| `mistral-medium` |  | — | — | — | · | Crude oil contango + inventory builds suggest downside risk; 94/99 put spread limits risk to $4.50/debit while targeting $92 handle. |
| `mistral-large` |  | — | — | — | · | XLE is near recent lows with a slight oversold RSI; mean-reversion likely with oil prices stabilizing. OTM call for leverage. |
| `mistral-nemo` |  | — | — | — | · | XLE has one insider buy (XOM) in energy, a sector likely to benefit from recent macro trends. OTM+2% call balances participation with risk control. |
| `mistral-nemo` |  | — | — | — | · | Energy sector XLE could see upside if regulatory clarity reduces compliance costs or spurs investment. Slightly OTM call for 4DTE balances risk/reward. |
| `mistral-medium` |  | — | — | — | · | XLE at 95.45 sits at 10-day low with RSI(14) ~32 (oversold) and crude oil futures (+1.8% intraday) showing bounce potential; bull call spread (92.5/95 strikes) limits downside to 1.5% of bankroll. |
| `mistral-large` |  | — | — | — | · | XLE's volatility has compressed post-Fed announcements. An iron condor targets range-bound behavior, profiting from low IV while hedging against minor swings in either direction. |
| `mistral-nemo` |  | — | — | — | · | XLE at 95.72 (-0.24% session) overshoots bearish momentum from oil inventory data. Put vertical captures mean-reversion to 91-93 range by Friday, defined risk (-$6.5k max loss vs +$1.5k max gain per s |

### XLF (8 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLF underperforming SPY by ~1.2σ over 5d; IV rank (42%) suggests cheap downside protection. Targeting 50.00 support level with 48h theta decay. |
| `mistral-large` |  | — | — | — | · | Financials (XLF) are undervalued relative to SPY; expect a bounce from recent underperformance. ATM call for higher delta. |
| `gemini-anl` |  | — | — | — | · | Anticipating capital rotation into financials as tech cools; low strike premium offers high leverage. |
| `mistral-medium` |  | — | — | — | · | FOUR insider barrage (8 filings, 60% strength) justifies bullish bias, but vertical spread (49.65→51.63) caps risk to 2.5% of bankroll. Wider wing accommodates XLF’s 1.8x average daily range. |
| `mistral-large` |  | — | — | — | · | Multiple insider buys in FOUR (XLF component) suggest confidence in financials. OTM call with short TTE targets a quick pop from sector rotation or earnings optimism. Strike at 102% of spot balances r |
| `mistral-large` |  | — | — | — | · | XLF has lagged SPY in recent sessions and is trading near its 20-day low. The Fed's neutral stance reduces systemic risk for financials, making a mild OTM call a high-probability reversion play. |
| `mistral-large` |  | — | — | — | · | XLF RSI at 72 (overbought) with VIX term structure inverting—short-term pullback likely. 99% strike offers 2:1 reward/risk if spot retreats to 57.50. |
| `mistral-medium` |  | — | — | — | · | XLF underperformed SPY by 0.45% today with rising 10Y yields; 0.99Δ put hedges a retest of 57.50 support (2x today’s range). Short-dated to avoid theta decay over weekend. |

### XLK (11 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLK leading momentum (RSI 62) with semis outperforming; using as a hedge against macro risk-off scenarios. 245 strike aligns with recent breakout level. |
| `mistral-large` |  | — | — | — | · | Tech (XLK) is poised for volatility ahead of key economic reports. Long straddle to capitalize on potential breakout or breakdown. |
| `gemini-anl` |  | — | — | — | · | Mean reversion play on tech sector overextension during an event-light session. |
| `mistral-nemo` |  | — | — | — | · | XLK has two insider buys (AAPL/NVDA) in a tech sector already showing strength. OTM+3% call capitalizes on short-term momentum with high risk/reward ratio. |
| `mistral-medium` |  | — | — | — | · | AAPL/NVDA insider clusters (60% strength) + XLK spot at 241.11 suggest near-term upside; OTM call balances delta with theta decay management. Targeting 2% OTM to avoid overpaying for IV in tech. |
| `mistral-large` |  | — | — | — | · | Neutral bias on AAPL (XLK) insider trade with DEFAULT IV suggests range-bound action. Iron condor collects premium while betting on tech stability. Wider strikes (96/104) reflect XLK's higher volatili |
| `llama-contra` |  | — | — | — | · | Buy XLK calls on momentum play |
| `mistral-medium` |  | — | — | — | · | XLK at 249.43 shows RSI(14) ~68 (overbought) after a 5-day +4.2% run; bear put spread (249/257 strikes) targets 2-3% pullback with 1:2 risk-reward. IV rank (52%) suggests premium selling is favorable. |
| `mistral-large` |  | — | — | — | · | XLK has shown consolidation after a pullback, with RSI nearing oversold territory. A slight OTM call captures potential upside as tech reverts to its 5-day mean. |
| `mistral-large` |  | — | — | — | · | XLK breaking above 247 on 1.5× avg volume; MACD crossover confirms upside momentum. Targeting 252 (102% strike) with 48h theta decay manageable given IV rank at 38th percentile. |
| `mistral-medium` |  | — | — | — | · | XLK pulled back 1.2% from its 2026 high (249.50) on no sector-specific news; 0.985Δ call offers 3:1 reward/risk with 72% prob of touching 248.50 by Friday. IV rank (38%) suggests cheap premium. |

### XLP (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | MO insider activity (6 filings) may reflect staples rotation, but XLP’s 82.05 spot and low IV rank (22nd percentile) favor range-bound play. Net credit targets 1.2x the wing width. |
| `mistral-large` |  | — | — | — | · | Bullish vertical on XLP (MO insider activity) captures upside with defined risk. ATM/OTM spread benefits from potential defensive rotation while capping loss at net debit. Longer TTE (5d) allows for s |

### XLRE (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Fed speak tomorrow + sticky CPI prints imply vol expansion in rates-sensitive sectors. XLRE ATM straddle priced at 18th percentile IV—asymmetry favors long vol. |

### XLU (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` |  | — | — | — | · | Defined-risk bull call spread to capture rotation into defensive utilities amid potential volatility expansion. |
| `mistral-medium` |  | — | — | — | · | XLU’s 30-day realized vol (12%) sits at 52-week low; selling 72/75/77/80 IC collects $0.80 credit with 84% POP. Defensive play given bankroll size and lack of catalysts. |

## 2026-03-16
### SPY (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | A small long straddle on SPY serves as a macro-hedge against unexpected late-session volatility or news-driven moves. The position is sized minimally to avoid over-allocation while providing downside |

### XLE (6 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLE IV rank at 68th percentile with spot pinned between 94-96 range for 12/15 sessions. Selling 96/100 call spread and 90/93 put spread for ~$0.80 net credit. Defined risk/reward ($2.20/$0.80) with 77 |
| `mistral-nemo` |  | — | — | — | · | XLE at $94.67 with 3 insider buys in OKLO (energy sector) signals sector rotation. 2% OTM calls to ride energy momentum with tight TTE for quick profit. |
| `mistral-large` |  | — | — | — | · | OKLO insider trades (3x Form 4) in energy innovation contrast with XLE’s recent consolidation (94.67). Long straddle captures potential breakout (96+) or breakdown (93-) from earnings/geopolitical cat |
| `mistral-nemo` |  | — | — | — | · | XLE butterfly plays energy sector pin risk at $100.27 strike with 4% wing width, benefiting from low probability of large move given current spot and Fed event backdrop. |
| `mistral-medium` |  | — | — | — | · | XLE’s 2.5% decline today outpaces crude’s 1.2% drop (divergence). 1-hour Bollinger %B at 0.08 suggests mean-reversion to $101.50; ATM-5δ calls offer 4:1 skew. |
| `mistral-large` |  | — | — | — | · | XLE has shown relative weakness recently but is near a key support level (99.93). A mean-reversion play with a slight OTM call (1.02 strike) offers a favorable risk-reward given the sector's historica |

### XLF (8 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | XLF at 50.11 with Bollinger %B at 0.12 (lower band touch) and rising 10Y yields suggesting bank net interest margin expansion. 51 strike (1.8% OTM) balances theta decay with upside to 52.50 resistance |
| `mistral-large` |  | — | — | — | · | XLF is trading near its 52-week low relative to SPY, with elevated implied volatility. A mean-reversion bounce is likely in the financial sector, supported by potential Fed dovishness in the near term |
| `mistral-large` |  | — | — | — | · | FOUR insider cluster (5x Form 4, signal=0.60) in regional banking suggests sector stabilization. XLF at 49.67 has support at 49.50; near-ATM calls balance delta and theta for a 2-day hold. |
| `mistral-medium` |  | — | — | — | · | FOUR insider activity is broad but lacks conviction (signal=0.60); selling 0.98/1.02 strangle for theta with wings at 0.95/1.05 to monetize stagnation. |
| `mistral-nemo` |  | — | — | — | · | XLF attractive for call vertical as financials often lead market optimism post-FOMC clarity. Defined risk with 5% spread width, betting on modest upside continuation from current $54.89. |
| `mistral-large` |  | — | — | — | · | XLF is near its 20-day low relative to SPY; mean reversion likely post-FOMC noise. OTM call for leverage with limited downside. |
| `mistral-nemo` |  | — | — | — | · | XLF 1D IV rank 45% (cheap vs historical), 5-day RSI 62 (not overbought). Vertical call spread (ATM/OTM) exploits momentum continuation with defined risk ($500 max loss per spread vs $1,500 potential g |
| `mistral-medium` |  | — | — | — | · | XLF’s 30-day IV rank (78%) + tomorrow’s Fed speaker risk justify a 1D ATM straddle. Breakeven at ±1.2% move (historical 68% probability). |

### XLI (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` |  | — | — | — | · | Industrials (XLI) underperforming SPY on airworthiness directive uncertainty; 1.0/1.03 put vertical targets 3% downside with 70% POP, defined risk ($1.20 debit). |

### XLK (12 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLK down 3% from 241.79 to 234.50 (approx) in session; mean-reversion to 240 expected due to strong sector support and oversold conditions (RSI <30). |
| `mistral-medium` |  | — | — | — | · | XLK showing RSI(14) bounce from 38 (oversold) with 200d MA support at $238. Targeting 245 strike (2.5% OTM) for 3DTE to capture momentum rebound in semis (SOXX +1.2% premarket). Risk: 3.8% of bankroll |
| `mistral-large` |  | — | — | — | · | XLK has shown overbought signals relative to its 20-day moving average. A short-term pullback is probable, and this put provides a hedge against tech sector rotation. |
| `mistral-nemo` |  | — | — | — | · | XLK at $242.88 with 3 insider buys in tech (AAPL, AMZN, MSFT) signals strong momentum. 2% OTM calls with 3D TTE to capitalize on gamma squeeze and IV expansion. |
| `mistral-large` |  | — | — | — | · | Congressional trades in AAPL/AMZN (signal_strength=0.65) + MSFT Form 4 cluster (6x events) imply institutional accumulation. XLK spot (242.88) has room to 248-250 on tech leadership; OTM calls maximiz |
| `mistral-medium` |  | — | — | — | · | AAPL/AMZN insider clusters (signal=0.65) + MSFT follow-through suggest sector upside; 1.00/1.04 call vertical caps risk at ~2% of bankroll while targeting 1:3 reward/risk. |
| `mistral-medium` |  | — | — | — | · | MSFT insider buy (signal=0.60) complements AAPL/AMZN momentum; 1.02 strike balances delta and gamma for a 48-hour hold. |
| `mistral-nemo` |  | — | — | — | · | XLK call vertical targets tech sector momentum with tighter 4% spread. Lower delta profile fits conservative risk approach while capturing sector rotation potential. |
| `mistral-medium` |  | — | — | — | · | Tech (XLK) IV elevated post-FOMC noise; 2-day 255/256/257 call butterfly exploits IV crush with 1:3 risk/reward ($0.40 debit, max profit $1.20). |
| `mistral-large` |  | — | — | — | · | Tech valuations stretched; XLK's RSI(14) at 68 suggests pullback. ATM put for high delta without excessive premium. |
| `mistral-medium` |  | — | — | — | · | XLK spot ($253.41) sits 1.8% below its 5-day VWAP after a 3% intraday drop; RSI(14) at 32 signals oversold. Targeting 1% OTM calls for a 3:1 reward/risk on a reversion to $257. |
| `mistral-large` |  | — | — | — | · | XLK has been range-bound but exhibits elevated implied volatility. A bear put vertical (0.97/0.99) allows us to capitalize on a potential pullback while defining risk. The position is sized conservati |

### XLU (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-large` |  | — | — | — | · | Defensive sectors like utilities (XLU) often benefit from macro uncertainty. This bull call spread captures upside with defined risk, aligning with a potential flight-to-safety rotation. |

### XLY (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-nemo` |  | — | — | — | · | XLY oversold near 195 with consumer confidence at 4-month highs; potential bounce to 200+ on retail data tomorrow. |
| `mistral-medium` |  | — | — | — | · | Discretionary (XLY) vulnerable to regulatory overhang (HAVANA Act + controlled substances); 0.99 put delta-hedges gamma exposure from XLI vertical, 15-delta target. |
