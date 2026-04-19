# POL TF Post-Mortem — 50 days analyzed
Space: `LBJLincoln26/political-llm-trading-floor`

## Leaderboard (by final bankroll)
| rank | trader | final | peak | drawdown | peak_day |
|------|--------|-------|------|----------|----------|
| 1 | `gemini-tact` | $531.42 | $2,686.83 | 80.2% | 43 |
| 2 | `gemini-anl` | $454.21 | $2,233.46 | 79.7% | 43 |
| 3 | `llama-contra` | $421.04 | $1,119.90 | 62.4% | 33 |
| 4 | `selfhost-gemma3` | $355.60 | $919.98 | 61.3% | 33 |
| 5 | `mistral-small` | $354.15 | $998.83 | 64.5% | 34 |
| 6 | `mistral-nemo` | $353.42 | $849.49 | 58.4% | 33 |
| 7 | `mistral-medium` | $328.53 | $1,006.46 | 67.4% | 34 |
| 8 | `nvidia-minimax` | $324.56 | $839.55 | 61.3% | 33 |
| 9 | `qwen-quant` | $311.58 | $956.71 | 67.4% | 33 |
| 10 | `qwen-arb` | $308.32 | $651.48 | 52.7% | 42 |
| 11 | `selfhost-dolphin3` | $300.11 | $735.61 | 59.2% | 33 |
| 12 | `mistral-large` | $296.43 | $933.58 | 68.2% | 34 |
| 13 | `nvidia-llama70` | $275.49 | $749.76 | 63.3% | 33 |
| 14 | `selfhost-qwen06` | $272.71 | $742.80 | 63.3% | 33 |
| 15 | `mistral-ministral` | $272.45 | $721.68 | 62.2% | 33 |
| 16 | `nemotron-120b` | $251.82 | $685.40 | 63.3% | 33 |
| 17 | `selfhost-qwen4b` | $245.62 | $650.47 | 62.2% | 33 |

## Top peak-rationales (what winners thought at their best day)

### gemini-tact — peak $2,686.83 on day 43
- d43 ($2,686.83): STRUCTURAL COMPLEMENT [Llama Contrarian]: TACTICAL TIMING focuses on the high-frequency cluster of insider trades in MSTR and HOOD as a volatility signal for the finance sector (XLF) while Llama focuses on contrarian inversions.
- d42 ($2,246.43): STRUCTURAL COMPLEMENT [Llama Contrarian]: TACTICAL TIMING identifies a cluster of finance insider trades (FOUR, HOOD) that Llama Contrarian often fades; I will capture the sector-wide momentum in XLF and XLP while they focus on individual stock inversions.

### gemini-anl — peak $2,233.46 on day 43
- d43 ($2,233.46): STRUCTURAL COMPLEMENT [Gemini Tactical]: While the leader targets high-volatility tech/crypto proxies, I apply a baseline_deviation approach to the Fed regulatory signals in the 'other' category to capture mean-reversion in macro-sensitive sectors.
- d42 ($1,919.64): STRUCTURAL COMPLEMENT [Gemini Tactical]: While the leader targets high-volatility momentum, my REASONING TEMPLATE (Fed/SEC statistics-first) prioritizes the 30-day sector win-rate baselines for consumer staples and tech mean-reversion.

### llama-contra — peak $1,119.90 on day 33
- d33 ($1,119.90): tier-pad: 10 events
- d34 ($1,066.62): tier-pad: 5 events

## Top 10 gainers (single-day jumps ≥+10%)
- `qwen-quant` d22 2026-02-24: $342.59→$523.07 (+52.68%) — STRUCTURAL DIVERGE [Gemini Tactical]: My REASONING TEMPLATE (EXPECTED-UTILITY MAXIMIZATION) prioritizes insider trades with high signal strength and f
- `mistral-medium` d32 2026-03-10: $685.42→$915.54 (+33.57%) — STRUCTURAL COMPLEMENT [Gemini Tactical]: My diversified portfolio approach focuses on balancing exposure across uncorrelated sectors (healthcare, ener
- `gemini-tact` d32 2026-03-10: $1232.69→$1646.04 (+33.53%) — STRUCTURAL COMPLEMENT [Llama Contrarian]: TACTICAL TIMING identifies a high-density insider cluster in private prisons (GEO) and energy (OKLO) which t
- `gemini-anl` d32 2026-03-10: $1070.39→$1425.56 (+33.18%) — STRUCTURAL COMPLEMENT [Gemini Tactical]: While the leader focuses on tactical timing of high-volatility finance trades, I apply a baseline_deviation a
- `qwen-arb` d22 2026-02-24: $187.32→$248.71 (+32.77%) — tier-pad: 37 events
- `selfhost-qwen06` d22 2026-02-24: $293.29→$389.32 (+32.74%) — tier-pad: 37 events
- `mistral-small` d22 2026-02-24: $369.95→$490.84 (+32.68%) — tier-pad: 37 events
- `nemotron-120b` d22 2026-02-24: $270.81→$359.32 (+32.68%) — tier-pad: 37 events
- `gemini-anl` d22 2026-02-24: $598.85→$794.52 (+32.67%) — tier-pad: 37 events
- `gemini-tact` d22 2026-02-24: $725.95→$963.10 (+32.67%) — tier-pad: 37 events

## Top 10 crashes (single-day drops ≤−20%)
- `qwen-quant` d40 2026-03-20: $865.61→$605.93 (-30.0%) — tier-pad: 4 events
- `llama-contra` d40 2026-03-20: $1013.19→$709.23 (-30.0%) — tier-pad: 4 events
- `mistral-large` d40 2026-03-20: $857.44→$600.20 (-30.0%) — tier-pad: 4 events
- `mistral-medium` d40 2026-03-20: $913.15→$639.23 (-30.0%) — tier-pad: 4 events
- `mistral-small` d40 2026-03-20: $943.20→$660.24 (-30.0%) — tier-pad: 4 events
- `mistral-nemo` d40 2026-03-20: $768.52→$537.96 (-30.0%) — tier-pad: 4 events
- `mistral-ministral` d40 2026-03-20: $653.02→$457.10 (-30.0%) — tier-pad: 4 events
- `nemotron-120b` d40 2026-03-20: $620.21→$434.13 (-30.0%) — tier-pad: 4 events
- `selfhost-qwen4b` d40 2026-03-20: $588.53→$411.97 (-30.0%) — tier-pad: 4 events
- `nvidia-minimax` d40 2026-03-20: $759.68→$531.76 (-30.0%) — tier-pad: 4 events