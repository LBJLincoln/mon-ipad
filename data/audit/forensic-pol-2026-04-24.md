# Forensic Bet Audit — POL TF — 2026-04-24

**Source:** `data/tf-analytics/pol/day-*.json` — 55 day-files.
**Total bets:** 1618  |  **Aggregate PnL:** -6559.44

## Per-agent Scorecard

| tid | persona | days | bets | W | L | WR | PnL | bestDay | worstDay | top3 targets | top3 cats | avgStake | avgEdge | fallback% |
|---|---|---:|---:|---:|---:|---|---:|---|---|---|---|---:|---|---:|
| `gemini-anl` | analytical | 41 | 110 | 59 | 51 | 53.6% | +65.37 | d82:+115.3 | d173:-40.5 | XLK(16, +247.2), XLF(14, +38.7), SPY(14, -36.9) | insider_trade(105, +74.6), fed_rule(5, -9.2) | 77.28 | - | 0.0% |
| `mistral-medium` | diversified | 33 | 78 | 41 | 37 | 52.6% | +34.69 | d171:+19.8 | d173:-23.3 | SPY(14, +5.0), QQQ(14, -2.5), IWM(14, -3.4) | insider_trade(76, +33.0), exec_order(1, -0.1), fed_rule(1, +1.8) | 11.70 | - | 0.0% |
| `mistral-small` | conservative | 35 | 101 | 57 | 44 | 56.4% | +32.63 | d171:+20.8 | d173:-24.5 | XLK(20, +4.6), XLF(15, +8.3), SPY(12, +3.1) | insider_trade(96, +31.1), fed_rule(4, +1.7), exec_order(1, -0.1) | 10.34 | - | 0.0% |
| `llama-contra` | contrarian | 43 | 155 | 87 | 68 | 56.1% | +0.41 | d173:+5.4 | d182:-13.3 | XLK(37, +14.9), XLF(36, -13.0), XLP(28, -3.0) | insider_trade(146, +1.0), fed_rule(9, -0.5) | 4.86 | - | 0.0% |
| `mistral-nemo` | aggressive | 28 | 66 | 29 | 37 | 43.9% | -3.93 | d171:+10.1 | d173:-12.3 | QQQ(18, -2.5), IWM(18, -5.5), SPY(17, +2.1) | insider_trade(65, -3.9), exec_order(1, -0.1) | 6.76 | - | 0.0% |
| `mistral-ministral` | theoretical | 28 | 72 | 34 | 38 | 47.2% | -4.40 | d171:+4.7 | d173:-6.7 | QQQ(15, -2.5), SPY(14, -1.1), IWM(14, -3.3) | insider_trade(72, -4.4) | 3.48 | - | 0.0% |
| `nemotron-120b` | chainthought | 29 | 73 | 34 | 39 | 46.6% | -10.08 | d171:+6.6 | d173:-7.7 | SPY(20, +2.0), QQQ(20, -5.0), IWM(20, -7.8) | insider_trade(73, -10.1) | 4.40 | - | 0.0% |
| `selfhost-gemma3` | analytical | 25 | 68 | 25 | 43 | 36.8% | -10.69 | d164:+0.5 | d49:-5.8 | SPY(21, -4.4), QQQ(21, -3.8), IWM(21, -2.8) | insider_trade(66, -11.0), fed_rule(2, +0.3) | 1.54 | - | 0.0% |
| `mistral-large` | ensemble | 36 | 98 | 47 | 51 | 48.0% | -11.59 | d182:+3.1 | d49:-9.7 | SPY(18, -5.7), QQQ(17, -4.4), IWM(17, -3.3) | insider_trade(97, -11.7), fed_rule(1, +0.1) | 3.35 | - | 0.0% |
| `gemini-tact` | tactical | 41 | 108 | 52 | 56 | 48.1% | -12.41 | d182:+26.7 | d174:-21.4 | XLK(18, +20.3), IWM(16, -14.6), SPY(16, -19.0) | insider_trade(106, -7.6), fed_rule(2, -4.8) | 15.22 | - | 0.0% |
| `nvidia-llama70` | swing | 28 | 76 | 34 | 42 | 44.7% | -13.97 | d171:+4.4 | d173:-6.4 | SPY(24, -2.4), QQQ(24, -4.9), IWM(24, -5.3) | insider_trade(76, -14.0) | 4.08 | - | 0.0% |
| `selfhost-qwen4b` | disciplined | 27 | 68 | 24 | 44 | 35.3% | -14.95 | d182:+1.1 | d49:-10.4 | SPY(19, -5.8), QQQ(19, -5.8), IWM(19, -4.7) | insider_trade(68, -14.9) | 2.14 | - | 0.0% |
| `nvidia-minimax` | decisive | 33 | 92 | 39 | 53 | 42.4% | -15.04 | d171:+4.4 | d173:-6.3 | SPY(27, -9.8), QQQ(27, -6.0), IWM(26, -1.3) | insider_trade(90, -15.9), fed_rule(2, +0.9) | 3.99 | - | 0.0% |
| `selfhost-qwen06` | conservative | 31 | 82 | 36 | 46 | 43.9% | -15.35 | d182:+5.5 | d173:-5.7 | SPY(23, -5.2), QQQ(23, -3.9), IWM(22, -4.5) | insider_trade(78, -17.0), fed_rule(4, +1.6) | 4.95 | - | 0.0% |
| `selfhost-dolphin3` | uncensored | 31 | 87 | 39 | 48 | 44.8% | -27.46 | d182:+9.3 | d173:-8.8 | SPY(27, -13.2), QQQ(27, -3.3), IWM(27, -6.1) | insider_trade(85, -29.2), fed_rule(2, +1.7) | 7.99 | - | 0.0% |
| `qwen-quant` | quantitative | 46 | 149 | 83 | 66 | 55.7% | -902.69 | d87:+40.1 | d303:-998.7 | XLK(28, +16.4), XLF(25, +53.5), XLE(24, +16.2) | insider_trade(143, -905.7), fed_rule(6, +3.0) | 75.92 | - | 0.0% |
| `qwen-arb` | arbitrage | 42 | 135 | 79 | 56 | 58.5% | -5649.98 | d82:+1200.3 | d303:-6861.6 | XLF(25, +389.3), XLK(21, +856.8), XLE(19, -8.1) | insider_trade(134, -5652.6), fed_rule(1, +2.6) | 439.65 | - | 0.0% |

## Representative Bets (per agent)

### `gemini-anl` (analytical) — bets=110 pnl=+65.37
- Winners:
  - d82 XLK/insider_trade stk=806.86 pnl=+183.38 edge=? src=direct
  - d87 XLK/insider_trade stk=897.41 pnl=+46.48 edge=? src=direct
- Losers:
  - d82 XLY/insider_trade stk=806.86 pnl=-67.95 edge=? src=direct
  - d140 XLF/insider_trade stk=41.98 pnl=-20.99 edge=? src=direct

### `mistral-medium` (diversified) — bets=78 pnl=+34.69
- Winners:
  - d171 SPY/insider_trade stk=13.19 pnl=+6.59 edge=? src=direct
  - d171 QQQ/insider_trade stk=13.19 pnl=+6.59 edge=? src=direct
- Losers:
  - d173 SPY/insider_trade stk=15.54 pnl=-7.77 edge=? src=direct
  - d173 QQQ/insider_trade stk=15.54 pnl=-7.77 edge=? src=direct

### `mistral-small` (conservative) — bets=101 pnl=+32.63
- Winners:
  - d171 SPY/insider_trade stk=13.86 pnl=+6.93 edge=? src=direct
  - d171 QQQ/insider_trade stk=13.86 pnl=+6.93 edge=? src=direct
- Losers:
  - d173 SPY/insider_trade stk=16.33 pnl=-8.16 edge=? src=direct
  - d173 QQQ/insider_trade stk=16.33 pnl=-8.16 edge=? src=direct

### `llama-contra` (contrarian) — bets=155 pnl=+0.41
- Winners:
  - d144 XLK/insider_trade stk=5.93 pnl=+2.73 edge=? src=direct
  - d177 XLF/insider_trade stk=6.73 pnl=+2.50 edge=? src=direct
- Losers:
  - d182 XLF/insider_trade stk=12.41 pnl=-4.42 edge=? src=direct
  - d182 XLF/insider_trade stk=12.41 pnl=-4.42 edge=? src=direct

### `mistral-nemo` (aggressive) — bets=66 pnl=-3.93
- Winners:
  - d171 SPY/insider_trade stk=6.76 pnl=+3.38 edge=? src=direct
  - d171 QQQ/insider_trade stk=6.76 pnl=+3.38 edge=? src=direct
- Losers:
  - d173 SPY/insider_trade stk=8.21 pnl=-4.11 edge=? src=direct
  - d173 QQQ/insider_trade stk=8.21 pnl=-4.11 edge=? src=direct

### `mistral-ministral` (theoretical) — bets=72 pnl=-4.40
- Winners:
  - d171 SPY/insider_trade stk=4.19 pnl=+2.10 edge=? src=direct
  - d171 QQQ/insider_trade stk=4.19 pnl=+2.10 edge=? src=direct
- Losers:
  - d173 SPY/insider_trade stk=4.46 pnl=-2.23 edge=? src=direct
  - d173 QQQ/insider_trade stk=4.46 pnl=-2.23 edge=? src=direct

### `nemotron-120b` (chainthought) — bets=73 pnl=-10.08
- Winners:
  - d49 XLF/insider_trade stk=7.02 pnl=+2.23 edge=? src=direct
  - d171 SPY/insider_trade stk=4.37 pnl=+2.19 edge=? src=direct
- Losers:
  - d154 QQQ/insider_trade stk=5.42 pnl=-2.71 edge=? src=direct
  - d154 IWM/insider_trade stk=5.42 pnl=-2.71 edge=? src=direct

### `selfhost-gemma3` (analytical) — bets=68 pnl=-10.69
- Winners:
  - d172 IWM/insider_trade stk=1.39 pnl=+0.65 edge=? src=direct
  - d182 XLY/insider_trade stk=1.14 pnl=+0.41 edge=? src=direct
- Losers:
  - d49 SPY/insider_trade stk=6.14 pnl=-1.95 edge=? src=direct
  - d49 QQQ/insider_trade stk=6.14 pnl=-1.95 edge=? src=direct

### `mistral-large` (ensemble) — bets=98 pnl=-11.59
- Winners:
  - d158 QQQ/insider_trade stk=3.61 pnl=+1.78 edge=? src=direct
  - d172 IWM/insider_trade stk=3.54 pnl=+1.66 edge=? src=direct
- Losers:
  - d49 SPY/insider_trade stk=10.20 pnl=-3.23 edge=? src=direct
  - d49 QQQ/insider_trade stk=10.20 pnl=-3.23 edge=? src=direct

### `gemini-tact` (tactical) — bets=108 pnl=-12.41
- Winners:
  - d171 XLF/insider_trade stk=18.31 pnl=+9.15 edge=? src=direct
  - d182 SPY/insider_trade stk=25.01 pnl=+8.91 edge=? src=direct
- Losers:
  - d173 SPY/insider_trade stk=17.29 pnl=-8.64 edge=? src=direct
  - d174 SPY/insider_trade stk=16.00 pnl=-7.15 edge=? src=direct

### `nvidia-llama70` (swing) — bets=76 pnl=-13.97
- Winners:
  - d171 SPY/insider_trade stk=3.99 pnl=+2.00 edge=? src=direct
  - d171 QQQ/insider_trade stk=3.99 pnl=+2.00 edge=? src=direct
- Losers:
  - d173 SPY/insider_trade stk=4.25 pnl=-2.12 edge=? src=direct
  - d173 QQQ/insider_trade stk=4.25 pnl=-2.12 edge=? src=direct

### `selfhost-qwen4b` (disciplined) — bets=68 pnl=-14.95
- Winners:
  - d182 XLP/insider_trade stk=2.95 pnl=+1.05 edge=? src=direct
  - d172 IWM/insider_trade stk=1.80 pnl=+0.85 edge=? src=direct
- Losers:
  - d49 SPY/insider_trade stk=10.92 pnl=-3.46 edge=? src=direct
  - d49 QQQ/insider_trade stk=10.92 pnl=-3.46 edge=? src=direct

### `nvidia-minimax` (decisive) — bets=92 pnl=-15.04
- Winners:
  - d149 XLF/insider_trade stk=4.53 pnl=+2.27 edge=? src=direct
  - d171 SPY/insider_trade stk=3.96 pnl=+1.98 edge=? src=direct
- Losers:
  - d138 SPY/insider_trade stk=4.98 pnl=-2.49 edge=? src=direct
  - d154 SPY/insider_trade stk=4.82 pnl=-2.41 edge=? src=direct

### `selfhost-qwen06` (conservative) — bets=82 pnl=-15.35
- Winners:
  - d171 SPY/insider_trade stk=5.26 pnl=+2.63 edge=? src=direct
  - d182 SPY/insider_trade stk=5.18 pnl=+1.84 edge=? src=direct
- Losers:
  - d173 SPY/insider_trade stk=5.03 pnl=-2.52 edge=? src=direct
  - d173 QQQ/insider_trade stk=5.03 pnl=-2.52 edge=? src=direct

### `selfhost-dolphin3` (uncensored) — bets=87 pnl=-27.46
- Winners:
  - d171 SPY/insider_trade stk=8.14 pnl=+4.07 edge=? src=direct
  - d182 SPY/insider_trade stk=8.71 pnl=+3.10 edge=? src=direct
- Losers:
  - d154 SPY/insider_trade stk=9.47 pnl=-4.74 edge=? src=direct
  - d173 SPY/insider_trade stk=7.80 pnl=-3.90 edge=? src=direct

### `qwen-quant` (quantitative) — bets=149 pnl=-902.69
- Winners:
  - d87 XLF/insider_trade stk=415.50 pnl=+28.09 edge=? src=direct
  - d87 XLK/insider_trade stk=415.50 pnl=+21.52 edge=? src=direct
- Losers:
  - d303 XLP/insider_trade stk=6179.51 pnl=-998.70 edge=? src=direct
  - d173 SPY/insider_trade stk=29.41 pnl=-14.71 edge=? src=direct

### `qwen-arb` (arbitrage) — bets=135 pnl=-5649.98
- Winners:
  - d82 XLK/insider_trade stk=3805.75 pnl=+864.95 edge=? src=direct
  - d82 XLF/insider_trade stk=3805.75 pnl=+350.41 edge=? src=direct
- Losers:
  - d303 XLP/insider_trade stk=42456.48 pnl=-6861.60 edge=? src=direct
  - d144 XLE/insider_trade stk=77.22 pnl=-35.53 edge=? src=direct

## Anomalies

### 1. Lockstep pairs (Jaccard > 0.8 on bet signatures)
- None detected.

### 2. Monoculture agents (one cat/target > 70% of bets)
- `qwen-quant` — category=`insider_trade` is 143/149 bets (96.0%)
- `qwen-arb` — category=`insider_trade` is 134/135 bets (99.3%)
- `llama-contra` — category=`insider_trade` is 146/155 bets (94.2%)
- `gemini-anl` — category=`insider_trade` is 105/110 bets (95.5%)
- `gemini-tact` — category=`insider_trade` is 106/108 bets (98.1%)
- `mistral-large` — category=`insider_trade` is 97/98 bets (99.0%)
- `mistral-medium` — category=`insider_trade` is 76/78 bets (97.4%)
- `mistral-small` — category=`insider_trade` is 96/101 bets (95.0%)
- `mistral-nemo` — category=`insider_trade` is 65/66 bets (98.5%)
- `mistral-ministral` — category=`insider_trade` is 72/72 bets (100.0%)
- `nemotron-120b` — category=`insider_trade` is 73/73 bets (100.0%)
- `selfhost-qwen4b` — category=`insider_trade` is 68/68 bets (100.0%)
- `nvidia-minimax` — category=`insider_trade` is 90/92 bets (97.8%)
- `nvidia-llama70` — category=`insider_trade` is 76/76 bets (100.0%)
- `selfhost-gemma3` — category=`insider_trade` is 66/68 bets (97.1%)
- `selfhost-qwen06` — category=`insider_trade` is 78/82 bets (95.1%)
- `selfhost-dolphin3` — category=`insider_trade` is 85/87 bets (97.7%)

### 3. Off-thesis agents (assigned persona keyword absent from top-3 cats)
- `qwen-quant` assigned `quantitative` but top-3 cats are `['insider_trade', 'fed_rule']` (n=149)
- `qwen-arb` assigned `arbitrage` but top-3 cats are `['insider_trade', 'fed_rule']` (n=135)
- `llama-contra` assigned `contrarian` but top-3 cats are `['insider_trade', 'fed_rule']` (n=155)
- `gemini-anl` assigned `analytical` but top-3 cats are `['insider_trade', 'fed_rule']` (n=110)
- `gemini-tact` assigned `tactical` but top-3 cats are `['insider_trade', 'fed_rule']` (n=108)
- `mistral-small` assigned `conservative` but top-3 cats are `['insider_trade', 'fed_rule', 'exec_order']` (n=101)
- `mistral-nemo` assigned `aggressive` but top-3 cats are `['insider_trade', 'exec_order']` (n=66)
- `selfhost-gemma3` assigned `analytical` but top-3 cats are `['insider_trade', 'fed_rule']` (n=68)
- `selfhost-qwen06` assigned `conservative` but top-3 cats are `['insider_trade', 'fed_rule']` (n=82)

### 4. Provider-fallback leakage (days where >30% of fleet bets are fallback source)
- None detected (sources rarely use explicit `fallback` tag — may indicate instrumentation gap).

### 5. Monopoly days (one agent > 50% of fleet stake)
- day 303: `qwen-arb` staked 42456.48 of 48636.72 (87.3%)
- day 82: `qwen-arb` staked 11417.25 of 13990.69 (81.6%)
- day 143: `qwen-arb` staked 228.57 of 383.27 (59.6%)
- day 87: `gemini-anl` staked 2467.88 of 4167.57 (59.2%)
- day 152: `qwen-arb` staked 44.38 of 77.37 (57.4%)
- day 183: `qwen-arb` staked 41.11 of 78.97 (52.1%)
- day 158: `gemini-anl` staked 117.57 of 231.45 (50.8%)
