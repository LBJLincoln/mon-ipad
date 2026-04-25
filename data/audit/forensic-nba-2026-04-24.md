# Forensic Bet Audit — NBA TF — 2026-04-24

**Source:** `data/tf-analytics/nba/day-*.json` — 54 day-files.
**Total bets:** 1154  |  **Aggregate PnL:** -245.49

## Per-agent Scorecard

| tid | persona | days | bets | W | L | WR | PnL | bestDay | worstDay | top3 targets | top3 cats | avgStake | avgEdge | fallback% |
|---|---|---:|---:|---:|---:|---|---:|---|---|---|---|---:|---|---:|
| `selfhost-qwen06` | conservative | 44 | 121 | 79 | 42 | 65.3% | +65.03 | d6:+68.5 | d67:-2.0 | WAS@CHA(2, +0.1), SAS@OKC(2, -0.2), ATL@TOR(2, +0.2) | ml_home(100, +67.4), ml_away(21, -2.4) | 1.16 | 1.192 | 2.5% |
| `mistral-large` | ensemble | 9 | 18 | 13 | 5 | 72.2% | +42.74 | d6:+43.5 | d62:-0.8 | CLE@CHI(1, +4.5), CHA@OKC(1, +19.5), GUA@LAC(1, +19.5) | ml_home(13, +43.5), ml_away(4, +0.3), pp_steals_star2_home(1, -1.1) | 3.95 | 0.618 | 16.7% |
| `nemotron-120b` | chainthought | 23 | 57 | 29 | 28 | 50.9% | +40.64 | d6:+45.7 | d65:-1.9 | HOU@DEN(2, -0.4), CLE@CHI(1, +4.7), CHA@OKC(1, +20.5) | ml_home(39, +44.8), ml_away(12, -1.6), pp_blocks_role1_away(2, -0.9) | 1.56 | 0.953 | 5.3% |
| `selfhost-dolphin3` | uncensored | 49 | 134 | 83 | 51 | 61.9% | +36.80 | d6:+56.7 | d67:-10.3 | WAS@CHA(2, +0.6), SAS@OKC(2, -1.0), ATL@TOR(2, +0.6) | ml_home(103, +49.5), ml_away(22, -11.6), total_over(2, +0.0) | 1.72 | 1.092 | 2.2% |
| `mistral-ministral` | theoretical | 18 | 47 | 28 | 19 | 59.6% | +32.94 | d17:+25.5 | d67:-0.6 | ATL@TOR(2, +0.2), MIN@NYK(1, +5.6), CLE@CHI(1, +1.6) | ml_home(32, +16.8), ml_away(9, +3.9), pp_steals_star3_home(2, -0.2) | 1.41 | 1.031 | 4.3% |
| `mistral-medium` | diversified | 3 | 7 | 6 | 1 | 85.7% | +30.43 | d17:+27.4 | d106:-0.1 | CLE@CHI(1, +1.2), CHA@OKC(1, +5.2), GUA@LAC(1, +5.2) | ml_home(5, +11.5), ml_away(1, +4.7), spread_home(1, +14.2) | 6.86 | 0.423 | 42.9% |
| `nvidia-minimax` | decisive | 44 | 120 | 73 | 47 | 60.8% | +16.99 | d6:+43.0 | d67:-11.8 | BOS@TOR(2, -5.0), SAS@OKC(2, -0.8), ATL@TOR(2, +0.6) | ml_home(101, +28.0), ml_away(14, -9.4), pp_threes_star1_away(1, -0.4) | 1.52 | 1.237 | 2.5% |
| `gemini-tact` | tactical | 46 | 129 | 75 | 54 | 58.1% | +13.93 | d6:+19.0 | d61:-4.3 | CLE@CHI(2, +0.3), GUA@LAC(2, +10.1), CHA@CLE(2, -0.4) | ml_home(88, +13.0), ml_away(16, -0.9), h1_total_over(4, +2.6) | 0.74 | 0.941 | 0.8% |
| `nvidia-llama70` | swing | 47 | 128 | 81 | 47 | 63.3% | +12.39 | d6:+52.7 | d67:-20.7 | BOS@TOR(2, -7.3), IND@PHI(2, +2.8), PHI@NYK(2, -1.8) | ml_home(105, +31.1), ml_away(21, -17.0), pp_steals_star1_home(1, -1.0) | 2.14 | 1.114 | 2.3% |
| `selfhost-qwen4b` | disciplined | 2 | 6 | 5 | 1 | 83.3% | +2.38 | d6:+7.6 | d17:+0.0 | CLE@CHI(1, +4.0), MIN@NYK(1, -21.4), DET@MIL(1, +14.6) | ml_home(4, +9.2), team_total_away_over_110(1, -21.4), spread_away(1, +14.6) | 10.89 | 0.070 | 33.3% |
| `mistral-nemo` | aggressive | 19 | 44 | 24 | 20 | 54.5% | -2.78 | d54:+6.0 | d6:-8.7 | MIN@NYK(1, -14.2), CLE@CHI(1, +2.1), DET@MIL(1, +1.8) | ml_home(25, +6.6), ml_away(14, -8.9), pp_steals_star3_away(1, -0.1) | 1.47 | 0.780 | 4.5% |
| `llama-contra` | contrarian | 10 | 24 | 11 | 13 | 45.8% | -16.51 | d92:+0.2 | d6:-13.2 | CLE@CHI(2, -8.1), MIN@NYK(1, -14.7), DET@MIL(1, +9.2) | ml_home(10, +4.2), spread_away(8, -11.7), ml_away(4, -8.8) | 1.95 | 0.330 | 12.5% |
| `qwen-arb` | arbitrage | 13 | 42 | 7 | 35 | 16.7% | -25.55 | d70:+0.2 | d6:-11.8 | CLE@CHI(2, -3.7), GUA@LAC(2, -0.4), MIN@NYK(1, -5.7) | ml_home(10, +5.0), spread_away(5, -1.7), pp_steals_star1_home(4, -1.4) | 1.12 | 0.271 | 7.1% |
| `qwen-quant` | quantitative | 1 | 5 | 3 | 2 | 60.0% | -34.01 | d17:+0.0 | d6:-41.6 | MIN@NYK(1, -22.7), CLE@CHI(1, +3.6), DET@MIL(1, -18.9) | ml_home(3, +7.5), total_over(1, -22.7), total_under(1, -18.9) | 12.85 | 0.056 | 40.0% |
| `selfhost-gemma3` | analytical | 48 | 136 | 81 | 55 | 59.6% | -35.62 | d6:+16.9 | d54:-23.9 | WAS@CHA(2, +0.5), SAS@OKC(2, -0.8), ATL@TOR(2, +0.6) | ml_home(99, +7.2), ml_away(22, -12.4), spread_away(4, -11.1) | 1.85 | 0.955 | 2.2% |
| `gemini-anl` | analytical | 44 | 123 | 80 | 43 | 65.0% | -68.12 | d17:+21.9 | d67:-38.5 | CHA@OKC(2, -12.1), CLE@CHI(2, -3.7), WAS@CHA(2, +3.5) | ml_home(94, -5.1), ml_away(25, -58.0), spread_away(2, +1.9) | 6.73 | 1.064 | 1.6% |
| `mistral-small` | conservative | 5 | 13 | 7 | 6 | 53.8% | -357.17 | d6:+9.7 | d17:-423.1 | CHA@OKC(2, -1.5), DET@MIL(1, +7.2), CLE@CHI(1, +1.1) | ml_home(9, +10.5), spread_away(2, +0.9), team_total_away_under_110(1, -204.8) | 30.77 | 1.295 | 23.1% |

## Representative Bets (per agent)

### `selfhost-qwen06` (conservative) — bets=121 pnl=+65.03
- Winners:
  - d6 CHA@OKC/ml_home stk=35.36 pnl=+30.73 edge=0.080 src=fallback-edge-post
  - d6 GUA@LAC/ml_home stk=35.36 pnl=+30.73 edge=0.080 src=fallback-edge-post
- Losers:
  - d61 BOS@TOR/ml_home stk=1.05 pnl=-1.05 edge=3.230 src=direct
  - d66 UTA@MEM/ml_home stk=0.84 pnl=-0.84 edge=1.440 src=direct

### `mistral-large` (ensemble) — bets=18 pnl=+42.74
- Winners:
  - d6 CHA@OKC/ml_home stk=22.47 pnl=+19.53 edge=0.080 src=fallback-edge-post
  - d6 GUA@LAC/ml_home stk=22.47 pnl=+19.53 edge=0.080 src=fallback-edge-post
- Losers:
  - d62 PHX@MIN/pp_steals_star2_home stk=1.06 pnl=-1.06 edge=0.077 src=direct
  - d92 MIA@IND/ml_away stk=0.14 pnl=-0.14 edge=0.720 src=direct

### `nemotron-120b` (chainthought) — bets=57 pnl=+40.64
- Winners:
  - d6 CHA@OKC/ml_home stk=23.60 pnl=+20.51 edge=0.080 src=fallback-edge-post
  - d6 GUA@LAC/ml_home stk=23.60 pnl=+20.51 edge=0.080 src=fallback-edge-post
- Losers:
  - d61 BOS@TOR/ml_home stk=0.93 pnl=-0.93 edge=3.230 src=direct
  - d65 LAC@HOU/pp_blocks_role1_away stk=0.74 pnl=-0.74 edge=0.111 src=direct

### `selfhost-dolphin3` (uncensored) — bets=134 pnl=+36.80
- Winners:
  - d6 CHA@OKC/ml_home stk=29.29 pnl=+25.45 edge=0.080 src=fallback-edge-post
  - d6 GUA@LAC/ml_home stk=29.29 pnl=+25.45 edge=0.080 src=fallback-edge-post
- Losers:
  - d61 BOS@TOR/ml_home stk=4.26 pnl=-4.26 edge=3.230 src=direct
  - d66 UTA@MEM/ml_home stk=4.23 pnl=-4.23 edge=1.440 src=direct

### `mistral-ministral` (theoretical) — bets=47 pnl=+32.94
- Winners:
  - d17 DEN@GSW/ml_home stk=14.49 pnl=+12.28 edge=0.047 src=direct
  - d6 DET@MIL/total_over stk=7.78 pnl=+7.08 edge=0.030 src=direct
- Losers:
  - d54 SAS@MIN/ml_away stk=1.74 pnl=-1.74 edge=0.077 src=direct
  - d67 LAL@PHX/ml_home stk=0.22 pnl=-0.22 edge=3.960 src=direct

### `mistral-medium` (diversified) — bets=7 pnl=+30.43
- Winners:
  - d17 DEN@GSW/spread_home stk=15.59 pnl=+14.19 edge=0.047 src=direct
  - d6 CHA@OKC/ml_home stk=6.01 pnl=+5.22 edge=0.080 src=fallback-edge-post
- Losers:
  - d106 CLE@ORL/ml_home stk=0.13 pnl=-0.13 edge=2.540 src=direct

### `nvidia-minimax` (decisive) — bets=120 pnl=+16.99
- Winners:
  - d6 CHA@OKC/ml_home stk=22.22 pnl=+19.31 edge=0.080 src=fallback-edge-post
  - d6 GUA@LAC/ml_home stk=22.22 pnl=+19.31 edge=0.080 src=fallback-edge-post
- Losers:
  - d66 UTA@MEM/ml_home stk=4.87 pnl=-4.87 edge=1.440 src=direct
  - d69 MEM@MIN/ml_home stk=4.80 pnl=-4.80 edge=0.430 src=direct

### `gemini-tact` (tactical) — bets=129 pnl=+13.93
- Winners:
  - d6 GUA@LAC/h1_ml_home stk=5.99 pnl=+5.45 edge=0.060 src=direct
  - d6 GUA@LAC/ml_home stk=5.31 pnl=+4.61 edge=0.080 src=fallback-edge-post
- Losers:
  - d66 UTA@MEM/ml_home stk=2.00 pnl=-2.00 edge=1.440 src=direct
  - d70 HOU@NOP/ml_away stk=1.44 pnl=-1.44 edge=0.250 src=direct

### `nvidia-llama70` (swing) — bets=128 pnl=+12.39
- Winners:
  - d6 CHA@OKC/ml_home stk=27.24 pnl=+23.67 edge=0.080 src=fallback-edge-post
  - d6 GUA@LAC/ml_home stk=27.24 pnl=+23.67 edge=0.080 src=fallback-edge-post
- Losers:
  - d67 LAL@PHX/ml_home stk=7.80 pnl=-7.80 edge=3.960 src=direct
  - d67 NOP@CHI/ml_home stk=6.86 pnl=-6.86 edge=0.260 src=direct

### `selfhost-qwen4b` (disciplined) — bets=6 pnl=+2.38
- Winners:
  - d6 DET@MIL/spread_away stk=16.05 pnl=+14.61 edge=0.050 src=direct
  - d6 CLE@CHI/ml_home stk=20.39 pnl=+4.04 edge=0.080 src=direct
- Losers:
  - d6 MIN@NYK/team_total_away_over_110 stk=21.40 pnl=-21.40 edge=0.060 src=direct

### `mistral-nemo` (aggressive) — bets=44 pnl=-2.78
- Winners:
  - d54 MEM@SAC/ml_away stk=4.79 pnl=+3.30 edge=0.072 src=direct
  - d6 CLE@CHI/ml_home stk=10.64 pnl=+2.11 edge=0.065 src=direct
- Losers:
  - d6 MIN@NYK/ml_away stk=14.19 pnl=-14.19 edge=0.045 src=direct
  - d61 BOS@TOR/ml_home stk=0.36 pnl=-0.36 edge=3.230 src=direct

### `llama-contra` (contrarian) — bets=24 pnl=-16.51
- Winners:
  - d6 DET@MIL/spread_away stk=10.14 pnl=+9.23 edge=0.060 src=direct
  - d6 CHA@OKC/ml_home stk=1.91 pnl=+1.66 edge=0.080 src=fallback-edge-post
- Losers:
  - d6 MIN@NYK/spread_away stk=14.72 pnl=-14.72 edge=0.050 src=direct
  - d6 CLE@CHI/ml_away stk=8.49 pnl=-8.49 edge=0.040 src=direct

### `qwen-arb` (arbitrage) — bets=42 pnl=-25.55
- Winners:
  - d70 GSW@PHX/ml_home stk=3.73 pnl=+4.10 edge=1.620 src=direct
  - d6 CHA@OKC/ml_home stk=1.49 pnl=+1.29 edge=0.080 src=fallback-edge-post
- Losers:
  - d6 MIN@NYK/team_total_away_under_110 stk=5.66 pnl=-5.66 edge=0.052 src=direct
  - d70 HOU@NOP/ml_away stk=4.24 pnl=-4.24 edge=0.250 src=direct

### `qwen-quant` (quantitative) — bets=5 pnl=-34.01
- Winners:
  - d6 CLE@CHI/ml_home stk=18.15 pnl=+3.59 edge=0.040 src=direct
  - d6 CHA@OKC/ml_home stk=2.27 pnl=+1.97 edge=0.080 src=fallback-edge-post
- Losers:
  - d6 MIN@NYK/total_over stk=22.68 pnl=-22.68 edge=0.050 src=direct
  - d6 DET@MIL/total_under stk=18.86 pnl=-18.86 edge=0.030 src=direct

### `selfhost-gemma3` (analytical) — bets=136 pnl=-35.62
- Winners:
  - d54 BOS@CLE/total_under stk=18.80 pnl=+17.11 edge=0.027 src=direct
  - d54 HOU@UTA/spread_away stk=17.68 pnl=+16.09 edge=0.035 src=direct
- Losers:
  - d54 TOR@NYK/spread_away stk=18.24 pnl=-18.24 edge=0.024 src=direct
  - d54 ATL@PHI/spread_home stk=12.40 pnl=-12.40 edge=0.030 src=direct

### `gemini-anl` (analytical) — bets=123 pnl=-68.12
- Winners:
  - d70 GSW@PHX/ml_home stk=10.75 pnl=+11.83 edge=1.620 src=direct
  - d63 MIA@ORL/ml_home stk=13.85 pnl=+11.54 edge=0.610 src=direct
- Losers:
  - d66 UTA@MEM/ml_home stk=15.14 pnl=-15.14 edge=1.440 src=direct
  - d67 LAL@PHX/ml_home stk=14.19 pnl=-14.19 edge=3.960 src=direct

### `mistral-small` (conservative) — bets=13 pnl=-357.17
- Winners:
  - d6 DET@MIL/spread_away stk=7.94 pnl=+7.23 edge=0.035 src=direct
  - d6 CHA@OKC/ml_home stk=5.52 pnl=+4.80 edge=0.080 src=fallback-edge-post
- Losers:
  - d17 OKC@IND/team_total_away_under_110 stk=204.75 pnl=-204.75 edge=0.041 src=direct
  - d17 DEN@GSW/team_total_home_over_120 stk=163.80 pnl=-163.80 edge=0.045 src=direct

## Anomalies

### 1. Lockstep pairs (Jaccard > 0.8 on bet signatures)
- `selfhost-dolphin3` ↔ `selfhost-qwen06` — Jaccard=0.903 (121/134 shared signatures)
- `gemini-anl` ↔ `selfhost-qwen06` — Jaccard=0.821 (110/134 shared signatures)

### 2. Monoculture agents (one cat/target > 70% of bets)
- `gemini-anl` — category=`ml_home` is 94/123 bets (76.4%)
- `mistral-large` — category=`ml_home` is 13/18 bets (72.2%)
- `nvidia-minimax` — category=`ml_home` is 101/120 bets (84.2%)
- `nvidia-llama70` — category=`ml_home` is 105/128 bets (82.0%)
- `selfhost-gemma3` — category=`ml_home` is 99/136 bets (72.8%)
- `selfhost-qwen06` — category=`ml_home` is 100/121 bets (82.6%)
- `selfhost-dolphin3` — category=`ml_home` is 103/134 bets (76.9%)

### 3. Off-thesis agents (assigned persona keyword absent from top-3 cats)
- `qwen-arb` assigned `arbitrage` but top-3 cats are `['ml_home', 'spread_away', 'pp_steals_star1_home']` (n=42)
- `gemini-anl` assigned `analytical` but top-3 cats are `['ml_home', 'ml_away', 'spread_away']` (n=123)
- `gemini-tact` assigned `tactical` but top-3 cats are `['ml_home', 'ml_away', 'h1_total_over']` (n=129)
- `mistral-nemo` assigned `aggressive` but top-3 cats are `['ml_home', 'ml_away', 'pp_steals_star3_away']` (n=44)
- `selfhost-gemma3` assigned `analytical` but top-3 cats are `['ml_home', 'ml_away', 'spread_away']` (n=136)
- `selfhost-qwen06` assigned `conservative` but top-3 cats are `['ml_home', 'ml_away']` (n=121)

### 4. Provider-fallback leakage (days where >30% of fleet bets are fallback source)
- day 6: 44/73 fallback (60.3%)

### 5. Monopoly days (one agent > 50% of fleet stake)
- day 17: `mistral-small` staked 368.55 of 457.55 (80.5%)
- day 54: `selfhost-gemma3` staked 91.53 of 121.01 (75.6%)
