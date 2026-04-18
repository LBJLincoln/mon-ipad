# POL TF Post-Mortem — 32 days analyzed
Space: `LBJLincoln26/political-llm-trading-floor`

## Leaderboard (by final bankroll)
| rank | trader | final | peak | drawdown | peak_day |
|------|--------|-------|------|----------|----------|
| 1 | `nvidia-llama70` | $95.19 | $162.09 | 41.3% | 19 |
| 2 | `llama-contra` | $94.83 | $161.25 | 41.2% | 22 |
| 3 | `qwen-quant` | $93.92 | $159.68 | 41.2% | 22 |
| 4 | `qwen-arb` | $93.92 | $159.68 | 41.2% | 22 |
| 5 | `gemini-anl` | $93.92 | $159.68 | 41.2% | 22 |
| 6 | `gemini-tact` | $93.92 | $159.68 | 41.2% | 22 |
| 7 | `mistral-large` | $93.92 | $159.68 | 41.2% | 22 |
| 8 | `mistral-small` | $93.92 | $159.68 | 41.2% | 22 |
| 9 | `mistral-ministral` | $93.92 | $159.68 | 41.2% | 22 |
| 10 | `nemotron-120b` | $93.92 | $159.68 | 41.2% | 22 |
| 11 | `selfhost-qwen4b` | $93.92 | $159.68 | 41.2% | 22 |
| 12 | `nvidia-minimax` | $93.92 | $159.68 | 41.2% | 22 |
| 13 | `selfhost-gemma3` | $93.92 | $159.68 | 41.2% | 22 |
| 14 | `selfhost-qwen06` | $93.92 | $159.68 | 41.2% | 22 |
| 15 | `selfhost-dolphin3` | $92.25 | $156.90 | 41.2% | 22 |
| 16 | `mistral-medium` | $91.38 | $155.39 | 41.2% | 22 |
| 17 | `mistral-nemo` | $90.25 | $153.45 | 41.2% | 22 |

## Top peak-rationales (what winners thought at their best day)

### nvidia-llama70 — peak $162.09 on day 19
- d19 ($162.09): Focusing on top 3 events with strongest signal strengths and clear sector mappings, prioritizing tech and energy sectors based on recent trends and insider trades.
- d22 ($161.84): Diversified sector approach focusing on energy, finance, and healthcare with a long bias, driven by insider trades and regulatory arbitrage signals.

### llama-contra — peak $161.25 on day 22
- d22 ($161.25): Fade the crowded insider-trade signals in tech and finance while overweighting energy and healthcare based on strong insider alignment and sector trends. Deploy as a consensus diverge against peers likely piling into tech (AMZN) and finance (COIN) longs.
- d19 ($160.90): Fade the crowded tech insider trades (META/MSFT) with short positions in XLK, while capitalizing on the underdog consumer discretionary signal (UBER) via XLY long. Align with council's healthcare focus (XLV) for stability.

### qwen-quant — peak $159.68 on day 22
- d22 ($159.68): Focus on high-conviction insider trades in finance and healthcare sectors, leveraging regulatory-delta quantification and sector-beta matrices to maximize expected value. Deviate from tech due to weak signal strength and low edge.
- d19 ($159.33): CONSENSUS DIVERGE NVIDIA Llama 3.3-70B: Prioritize healthcare (XLV) and energy (XLE) over tech insider trades due to stronger sector trends and regulatory clarity, while shorting tech (XLK) on weak historical performance and negative insider signal direction.

## Top 8 gainers (single-day jumps ≥+10%)
- `qwen-quant` d10 2026-02-02: $91.18→$117.25 (+28.59%) — Leverage strong insider trade signals in energy (XOM) and counter-consensus short positions in tech (AAPL, MSFT) based on regulatory delta and sector-
- `qwen-arb` d10 2026-02-02: $91.18→$117.25 (+28.59%) — fallback-injection: LLM silent, forcing 75% deploy on first 4 events (SPY long)
- `llama-contra` d10 2026-02-02: $91.18→$117.25 (+28.59%) — Fade the crowded tech insider trades (AAPL/MSFT) due to high signal strength and consensus fade edge. Allocate residual capital to energy (XOM) as a h
- `gemini-anl` d10 2026-02-02: $91.18→$117.25 (+28.59%) — CONSENSUS AGREE [Mistral Medium]: Prioritizing energy and tech insider signals while applying TitFor2Tats cooperation to stabilize group reputation. L
- `gemini-tact` d10 2026-02-02: $91.18→$117.25 (+28.59%) — CONSENSUS AGREE [mistral-medium]: Prioritizing energy momentum and tech fade based on NOMOS42 model edges and calendar-based insider trade patterns.
- `mistral-large` d10 2026-02-02: $91.18→$117.25 (+28.59%) — CONSENSUS DIVERGE Mistral Medium: Prioritize high-conviction insider trade signals in energy (XOM) and avoid tech (AAPL/MSFT) due to weak sector trend
- `mistral-small` d10 2026-02-02: $91.18→$117.25 (+28.59%) — Leverage insider trade signals in energy (XOM) and tech (AAPL/MSFT) while avoiding overcrowded SPY allocations. Focus on high-confidence energy sector
- `mistral-nemo` d10 2026-02-02: $91.18→$117.25 (+28.59%) — Focus on high-signal insider trades in energy and tech sectors, leveraging momentum and strong sector trends.

## Top 8 crashes (single-day drops ≤−20%)
- `qwen-quant` d9 2026-01-30: $118.24→$91.18 (-22.89%) — Focus on regulatory arbitrage and insider tracking in finance and tech sectors, with a tilt toward short positions in tech due to consistent negative 
- `qwen-arb` d9 2026-01-30: $118.24→$91.18 (-22.89%) — fallback-injection: LLM silent, forcing 75% deploy on first 5 events (SPY long)
- `llama-contra` d9 2026-01-30: $118.24→$91.18 (-22.89%) — Fade the crowded tech insider trade narrative; tech sector has seen 5 consecutive bullish congressional trades with negative expected returns. Target 
- `gemini-anl` d9 2026-01-30: $118.24→$91.18 (-22.89%) — CONSENSUS AGREE [Mistral Medium]: Prioritizing sector-specific insider signals with high signal_fade probability in tech while following council's foc
- `gemini-tact` d9 2026-01-30: $118.24→$91.18 (-22.89%) — CONSENSUS DIVERGE [Mistral Medium]: While the leader favored broad SPY, I am fading tech congressional trades based on the NOMOS42 signal_fade edge (0
- `mistral-large` d9 2026-01-30: $118.24→$91.18 (-22.89%) — Focus on insider tracking and regulatory arbitrage, prioritizing finance and tech sectors with strong multi-agency signals. Deviate from tech short co
- `mistral-medium` d9 2026-01-30: $120.31→$92.77 (-22.89%) — Diversified portfolio approach focusing on insider tracking and regulatory arbitrage with a balanced exposure across multiple sectors.
- `mistral-small` d9 2026-01-30: $118.24→$91.18 (-22.89%) — Leverage multi-agency insider signals with sector ETFs, prioritizing finance and energy where congressional trades show positive momentum. Spread smal