# NBA — per-agent factual audit
Generated 2026-04-25 10:01 UTC
Days simmed: 25  |  reset cutoff: 2026-04-25T08:00:00Z

## Aggregate (sorted by total bets)

| agent | days_traded | bets | parlays | distinct_cats | mean_odds | mean_edge | mean_stake | W-L | WR | bankroll | PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `mistral-nemo` | 19/25 | 31 | 14 | 19 | 1.89 | 0.104 | $1.85 | 1-30 | 3.2% | $96→$26 | -55.1 |
| `mistral-ministral` | 14/25 | 25 | 9 | 16 | 1.91 | 0.105 | $2.00 | 0-25 | 0.0% | $96→$34 | -50.1 |
| `selfhost-qwen06` | 12/25 | 21 | 6 | 13 | 1.91 | 0.108 | $2.06 | 0-21 | 0.0% | $94→$43 | -43.2 |
| `nemotron-120b` | 8/25 | 14 | 4 | 9 | 1.91 | 0.107 | $2.25 | 0-14 | 0.0% | $94→$57 | -31.6 |
| `mistral-small` | 12/25 | 12 | 3 | 8 | 1.92 | 0.107 | $2.50 | 2-10 | 16.7% | $98→$71 | -24.3 |
| `selfhost-gemma3` | 8/25 | 11 | 5 | 10 | 1.92 | 0.106 | $2.47 | 0-11 | 0.0% | $96→$64 | -27.1 |
| `mistral-large` | 7/25 | 7 | 4 | 7 | 1.91 | 0.101 | $2.65 | 0-7 | 0.0% | $102→$77 | -18.6 |
| `nvidia-llama70` | 11/25 | 6 | 6 | 2 | 1.58 | 0.080 | $3.07 | 4-2 | 66.7% | $100→$95 | +1.8 |
| `selfhost-qwen4b` | 7/25 | 5 | 4 | 3 | 1.53 | 0.080 | $9.81 | 3-2 | 60.0% | $105→$86 | -8.6 |
| `qwen-quant` | 4/25 | 3 | 3 | 3 | 1.91 | 0.104 | $2.94 | 0-3 | 0.0% | $102→$94 | -8.8 |
| `qwen-arb` | 2/25 | 3 | 2 | 3 | 1.85 | 0.094 | $4.84 | 0-3 | 0.0% | $100→$77 | -14.5 |
| `gemini-anl` | 2/25 | 3 | 0 | 3 | 1.78 | 0.087 | $3.00 | 1-2 | 33.3% | $100→$96 | -4.4 |
| `selfhost-dolphin3` | 9/25 | 3 | 7 | 1 | 1.69 | 0.080 | $2.02 | 2-1 | 66.7% | $100→$96 | +1.3 |
| `llama-contra` | 4/25 | 2 | 2 | 2 | 1.55 | 0.080 | $7.72 | 1-1 | 50.0% | $100→$97 | -9.9 |
| `gemini-tact` | 3/25 | 2 | 2 | 2 | 1.91 | 0.090 | $4.29 | 0-2 | 0.0% | $100→$82 | -8.6 |
| `mistral-medium` | 1/25 | 2 | 0 | 2 | 1.91 | 0.111 | $2.87 | 0-2 | 0.0% | $97→$91 | -5.7 |
| `nvidia-minimax` | 1/25 | 2 | 1 | 2 | 1.88 | 0.095 | $2.01 | 0-2 | 0.0% | $102→$96 | -4.0 |

## Per-agent top categories
- **mistral-nemo** (19 cats): `pp_steals_star1_away`×6, `pp_steals_star1_home`×3, `pp_steals_star2_away`×3, `pp_blocks_star2_home`×2, `pp_steals_star2_home`×2, `pp_threes_star1_home`×2
- **mistral-ministral** (16 cats): `pp_steals_star1_away`×5, `pp_blocks_star3_home`×2, `pp_threes_star2_home`×2, `pp_steals_star2_away`×2, `pp_threes_star1_away`×2, `pp_steals_role1_home`×2
- **selfhost-qwen06** (13 cats): `pp_steals_star2_away`×3, `pp_threes_role2_home`×2, `pp_steals_star1_away`×2, `pp_threes_star1_home`×2, `pp_steals_star1_home`×2, `pp_steals_star3_away`×2
- **nemotron-120b** (9 cats): `pp_steals_star1_home`×3, `pp_steals_star1_away`×3, `pp_threes_role2_away`×2, `pp_steals_role2_home`×1, `alt_spread_away_plus14.5`×1, `pp_steals_star2_away`×1
- **mistral-small** (8 cats): `pp_steals_star1_away`×3, `pp_steals_role1_away`×2, `alt_spread_home_minus3`×2, `pp_steals_star1_home`×1, `pp_steals_star2_away`×1, `pp_threes_star1_home`×1
- **selfhost-gemma3** (10 cats): `pp_threes_star3_home`×2, `pp_steals_star1_away`×1, `pp_steals_star1_home`×1, `pp_steals_star2_away`×1, `pp_threes_role2_home`×1, `pp_blocks_role1_away`×1
- **mistral-large** (7 cats): `pp_threes_star2_away`×1, `pp_assists_role2_away`×1, `pp_steals_role2_away`×1, `pp_steals_star1_home`×1, `pp_steals_role1_home`×1, `pp_blocks_role1_away`×1
- **nvidia-llama70** (2 cats): `ml_away`×3, `ml_home`×3
- **selfhost-qwen4b** (3 cats): `ml_home`×2, `ml_away`×2, `pp_blocks_star2_home`×1
- **qwen-quant** (3 cats): `pp_steals_role2_home`×1, `pp_steals_star3_home`×1, `team_total_away_under_112.5`×1
- **qwen-arb** (3 cats): `ml_away`×1, `pp_assists_role1_away`×1, `pp_steals_star2_home`×1
- **gemini-anl** (3 cats): `ml_away`×1, `spread_home`×1, `pp_rebounds_star1_away`×1
- **selfhost-dolphin3** (1 cats): `ml_home`×3
- **llama-contra** (2 cats): `spread_away`×1, `ml_away`×1
- **gemini-tact** (2 cats): `h1_total_over`×1, `pp_steals_star1_home`×1
- **mistral-medium** (2 cats): `pp_steals_star1_away`×1, `pp_threes_role2_away`×1
- **nvidia-minimax** (2 cats): `alt_total_over_plus4`×1, `pp_threes_star1_home`×1

## Odds distribution per agent
- **mistral-nemo** n=31 mean=1.893 median=1.91 min=1.39 max=1.91
- **mistral-ministral** n=25 mean=1.91 median=1.91 min=1.909 max=1.91
- **selfhost-qwen06** n=21 mean=1.91 median=1.91 min=1.909 max=1.91
- **nemotron-120b** n=14 mean=1.91 median=1.91 min=1.909 max=1.91
- **mistral-small** n=12 mean=1.923 median=1.91 min=1.199 max=3.307
- **selfhost-gemma3** n=11 mean=1.918 median=1.91 min=1.91 max=1.997
- **mistral-large** n=7 mean=1.91 median=1.91 min=1.909 max=1.91
- **nvidia-llama70** n=6 mean=1.579 median=1.476 min=1.2 max=2.35
- **selfhost-qwen4b** n=5 mean=1.527 median=1.526 min=1.2 max=1.91
- **qwen-quant** n=3 mean=1.91 median=1.91 min=1.91 max=1.91
- **qwen-arb** n=3 mean=1.854 median=1.91 min=1.741 max=1.91
- **gemini-anl** n=3 mean=1.782 median=1.909 min=1.526 max=1.91
- **selfhost-dolphin3** n=3 mean=1.69 median=1.571 min=1.4 max=2.1
- **llama-contra** n=2 mean=1.551 median=1.551 min=1.193 max=1.91
- **gemini-tact** n=2 mean=1.909 median=1.909 min=1.909 max=1.91
- **mistral-medium** n=2 mean=1.91 median=1.91 min=1.91 max=1.91
- **nvidia-minimax** n=2 mean=1.88 median=1.88 min=1.85 max=1.91