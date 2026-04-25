# NBA — combination coverage report
Generated 2026-04-25 16:20 UTC

**Theoretical universe per match-day**: 249 categories × ~5 games × parlay 2-6 legs ≈ 1.5M combos/day; agent picks ≤25 + 8 parlays/day

Reads: for each agent, how much of the 100k+ combination space did they actually explore?
Homogeneity = share of total bets in the agent's most-picked single category. >50% = template-bleed.

## Activity + coverage table

| agent | bets | par.legs | distinct_cats | distinct_combos | distinct_events | homogeneity | top class |
|---|---:|---:|---:|---:|---:|---:|---|
| `mistral-small` | 41 | 10 | 17 | 41 | 41 | 20% | pp_steals×32, alt_spread×4, pp_blocks×4 |
| `selfhost-qwen06` | 34 | 16 | 16 | 34 | 33 | 12% | pp_steals×19, pp_threes×10, pp_blocks×4 |
| `mistral-nemo` | 32 | 28 | 19 | 32 | 31 | 22% | pp_steals×18, pp_blocks×7, pp_threes×5 |
| `mistral-ministral` | 32 | 24 | 19 | 32 | 32 | 19% | pp_steals×17, pp_threes×6, pp_blocks×5 |
| `selfhost-gemma3` | 32 | 34 | 16 | 32 | 32 | 19% | pp_steals×21, pp_threes×6, pp_blocks×3 |
| `nemotron-120b` | 31 | 26 | 17 | 30 | 30 | 19% | pp_steals×20, pp_threes×7, alt_spread×3 |
| `qwen-quant` | 19 | 30 | 14 | 19 | 17 | 16% | pp_steals×8, pp_threes×5, pp_blocks×2 |
| `mistral-large` | 16 | 24 | 13 | 16 | 15 | 12% | pp_steals×10, pp_threes×2, pp_assists×1 |
| `nvidia-llama70` | 12 | 60 | 2 | 12 | 12 | 58% | ml×12 |
| `nvidia-minimax` | 9 | 6 | 7 | 9 | 9 | 33% | alt_total×3, q1×3, pp_threes×2 |
| `mistral-medium` | 8 | 2 | 6 | 8 | 8 | 25% | pp_steals×5, pp_threes×1, pp_blocks×1 |
| `selfhost-qwen4b` | 8 | 33 | 6 | 8 | 8 | 25% | ml×4, pp_steals×3, pp_blocks×1 |
| `gemini-anl` | 7 | 2 | 6 | 7 | 7 | 29% | ml×2, pp_steals×2, spread×1 |
| `selfhost-dolphin3` | 6 | 64 | 4 | 6 | 6 | 50% | ml×3, pp_steals×3 |
| `gemini-tact` | 5 | 8 | 4 | 5 | 5 | 40% | pp_steals×3, h1×1, pp_blocks×1 |
| `qwen-arb` | 4 | 8 | 4 | 4 | 4 | 25% | pp_steals×2, ml×1, pp_assists×1 |
| `llama-contra` | 2 | 6 | 2 | 2 | 2 | 50% | spread×1, ml×1 |

## Per-agent category-class breakdown

**`mistral-small`** (41 bets): pp_steals=32  alt_spread=4  pp_blocks=4  pp_threes=1
**`selfhost-qwen06`** (34 bets): pp_steals=19  pp_threes=10  pp_blocks=4  pp_rebounds=1
**`mistral-nemo`** (32 bets): pp_steals=18  pp_blocks=7  pp_threes=5  pp_assists=1  alt_spread=1
**`mistral-ministral`** (32 bets): pp_steals=17  pp_threes=6  pp_blocks=5  pp_assists=1  alt_spread=1  pp_points=1  pp_rebounds=1
**`selfhost-gemma3`** (32 bets): pp_steals=21  pp_threes=6  pp_blocks=3  alt_spread=1  alt_total=1
**`nemotron-120b`** (31 bets): pp_steals=20  pp_threes=7  alt_spread=3  pp_blocks=1
**`qwen-quant`** (19 bets): pp_steals=8  pp_threes=5  pp_blocks=2  team_total=1  pp_points=1  pp_assists=1  alt_total=1
**`mistral-large`** (16 bets): pp_steals=10  pp_threes=2  pp_assists=1  pp_blocks=1  pp_points=1  alt_spread=1
**`nvidia-llama70`** (12 bets): ml=12
**`nvidia-minimax`** (9 bets): alt_total=3  q1=3  pp_threes=2  alt_spread=1
**`mistral-medium`** (8 bets): pp_steals=5  pp_threes=1  pp_blocks=1  spread=1
**`selfhost-qwen4b`** (8 bets): ml=4  pp_steals=3  pp_blocks=1
**`gemini-anl`** (7 bets): ml=2  pp_steals=2  spread=1  pp_rebounds=1  alt_spread=1
**`selfhost-dolphin3`** (6 bets): ml=3  pp_steals=3
**`gemini-tact`** (5 bets): pp_steals=3  h1=1  pp_blocks=1
**`qwen-arb`** (4 bets): pp_steals=2  ml=1  pp_assists=1
**`llama-contra`** (2 bets): spread=1  ml=1

## Per-agent top-20 categories (with count)

### `mistral-small`
- distinct cats: 17 — distinct combos: 41 — homogeneity: 20%
  - `pp_steals_star1_away`: 8 (19.5%)
  - `pp_steals_star1_home`: 7 (17.1%)
  - `pp_steals_star2_away`: 4 (9.8%)
  - `pp_steals_role1_away`: 4 (9.8%)
  - `pp_steals_star3_home`: 4 (9.8%)
  - `alt_spread_home_minus3`: 2 (4.9%)
  - `pp_steals_star2_home`: 2 (4.9%)
  - `pp_threes_star1_home`: 1 (2.4%)
  - `pp_steals_role1_home`: 1 (2.4%)
  - `alt_spread_away_plus5`: 1 (2.4%)
  - `pp_steals_role2_away`: 1 (2.4%)
  - `pp_blocks_star2_home`: 1 (2.4%)
  - `pp_blocks_star3_home`: 1 (2.4%)
  - `pp_blocks_star3_away`: 1 (2.4%)
  - `pp_blocks_star2_away`: 1 (2.4%)
  - `alt_spread_home_minus1.5`: 1 (2.4%)
  - `pp_steals_star3_away`: 1 (2.4%)

### `selfhost-qwen06`
- distinct cats: 16 — distinct combos: 34 — homogeneity: 12%
  - `pp_steals_star2_away`: 4 (11.8%)
  - `pp_steals_star1_home`: 4 (11.8%)
  - `pp_steals_star3_away`: 4 (11.8%)
  - `pp_threes_role2_away`: 4 (11.8%)
  - `pp_steals_role2_away`: 2 (5.9%)
  - `pp_threes_role2_home`: 2 (5.9%)
  - `pp_blocks_star2_home`: 2 (5.9%)
  - `pp_steals_star1_away`: 2 (5.9%)
  - `pp_threes_star1_home`: 2 (5.9%)
  - `pp_steals_star2_home`: 2 (5.9%)
  - `pp_threes_role1_home`: 1 (2.9%)
  - `pp_blocks_star3_away`: 1 (2.9%)
  - `pp_threes_star1_away`: 1 (2.9%)
  - `pp_steals_role2_home`: 1 (2.9%)
  - `pp_blocks_role2_away`: 1 (2.9%)
  - `pp_rebounds_role2_away`: 1 (2.9%)

### `mistral-nemo`
- distinct cats: 19 — distinct combos: 32 — homogeneity: 22%
  - `pp_steals_star1_away`: 7 (21.9%)
  - `pp_steals_star1_home`: 3 (9.4%)
  - `pp_steals_star2_away`: 3 (9.4%)
  - `pp_blocks_star2_home`: 2 (6.2%)
  - `pp_steals_star2_home`: 2 (6.2%)
  - `pp_threes_star1_home`: 2 (6.2%)
  - `pp_assists_role1_away`: 1 (3.1%)
  - `pp_threes_star1_away`: 1 (3.1%)
  - `pp_steals_star3_home`: 1 (3.1%)
  - `pp_blocks_role1_home`: 1 (3.1%)
  - `pp_steals_role1_home`: 1 (3.1%)
  - `pp_steals_star3_away`: 1 (3.1%)
  - `pp_threes_star3_home`: 1 (3.1%)
  - `pp_blocks_star2_away`: 1 (3.1%)
  - `alt_spread_home_minus3`: 1 (3.1%)
  - `pp_blocks_role1_away`: 1 (3.1%)
  - `pp_blocks_star3_away`: 1 (3.1%)
  - `pp_threes_role2_home`: 1 (3.1%)
  - `pp_blocks_star3_home`: 1 (3.1%)

### `mistral-ministral`
- distinct cats: 19 — distinct combos: 32 — homogeneity: 19%
  - `pp_steals_star1_away`: 6 (18.8%)
  - `pp_steals_star3_home`: 3 (9.4%)
  - `pp_blocks_role1_home`: 2 (6.2%)
  - `pp_blocks_star3_home`: 2 (6.2%)
  - `pp_threes_star2_home`: 2 (6.2%)
  - `pp_steals_star2_away`: 2 (6.2%)
  - `pp_threes_star1_away`: 2 (6.2%)
  - `pp_steals_role1_home`: 2 (6.2%)
  - `pp_assists_role1_away`: 1 (3.1%)
  - `alt_spread_home_minus11.5`: 1 (3.1%)
  - `pp_steals_star3_away`: 1 (3.1%)
  - `pp_points_star1_away`: 1 (3.1%)
  - `pp_threes_star1_home`: 1 (3.1%)
  - `pp_rebounds_star2_away`: 1 (3.1%)
  - `pp_threes_star3_home`: 1 (3.1%)
  - `pp_steals_star1_home`: 1 (3.1%)
  - `pp_steals_role2_home`: 1 (3.1%)
  - `pp_steals_star2_home`: 1 (3.1%)
  - `pp_blocks_role1_away`: 1 (3.1%)

### `selfhost-gemma3`
- distinct cats: 16 — distinct combos: 32 — homogeneity: 19%
  - `pp_steals_star1_home`: 6 (18.8%)
  - `pp_steals_star1_away`: 5 (15.6%)
  - `pp_steals_star2_home`: 4 (12.5%)
  - `pp_blocks_role1_away`: 2 (6.2%)
  - `pp_threes_star3_home`: 2 (6.2%)
  - `pp_steals_role2_away`: 2 (6.2%)
  - `pp_threes_star3_away`: 2 (6.2%)
  - `pp_steals_star2_away`: 1 (3.1%)
  - `pp_threes_role2_home`: 1 (3.1%)
  - `pp_blocks_star2_away`: 1 (3.1%)
  - `alt_spread_away_plus3`: 1 (3.1%)
  - `pp_steals_star3_home`: 1 (3.1%)
  - `alt_total_under_minus3`: 1 (3.1%)
  - `pp_steals_role2_home`: 1 (3.1%)
  - `pp_steals_star3_away`: 1 (3.1%)
  - `pp_threes_star1_home`: 1 (3.1%)

### `nemotron-120b`
- distinct cats: 17 — distinct combos: 30 — homogeneity: 19%
  - `pp_steals_star1_away`: 6 (19.4%)
  - `pp_steals_star1_home`: 5 (16.1%)
  - `pp_threes_role2_away`: 3 (9.7%)
  - `pp_steals_star2_away`: 2 (6.5%)
  - `pp_steals_role1_away`: 2 (6.5%)
  - `pp_steals_star2_home`: 2 (6.5%)
  - `pp_steals_role2_home`: 1 (3.2%)
  - `alt_spread_away_plus14.5`: 1 (3.2%)
  - `pp_threes_star2_away`: 1 (3.2%)
  - `pp_threes_star1_home`: 1 (3.2%)
  - `pp_blocks_star3_away`: 1 (3.2%)
  - `pp_threes_star3_home`: 1 (3.2%)
  - `pp_steals_role1_home`: 1 (3.2%)
  - `pp_steals_star3_home`: 1 (3.2%)
  - `alt_spread_away_plus10`: 1 (3.2%)
  - `pp_threes_star1_away`: 1 (3.2%)
  - `alt_spread_home_minus18`: 1 (3.2%)

### `qwen-quant`
- distinct cats: 14 — distinct combos: 19 — homogeneity: 16%
  - `pp_steals_star3_home`: 3 (15.8%)
  - `pp_steals_role2_home`: 2 (10.5%)
  - `pp_threes_star1_away`: 2 (10.5%)
  - `pp_steals_star1_away`: 2 (10.5%)
  - `team_total_away_under_112.5`: 1 (5.3%)
  - `pp_blocks_role1_home`: 1 (5.3%)
  - `pp_points_star1_away`: 1 (5.3%)
  - `pp_steals_role1_home`: 1 (5.3%)
  - `pp_assists_role1_home`: 1 (5.3%)
  - `pp_blocks_star3_home`: 1 (5.3%)
  - `pp_threes_star1_home`: 1 (5.3%)
  - `alt_total_under_241.5`: 1 (5.3%)
  - `pp_threes_star2_home`: 1 (5.3%)
  - `pp_threes_role2_home`: 1 (5.3%)

### `mistral-large`
- distinct cats: 13 — distinct combos: 16 — homogeneity: 12%
  - `pp_steals_role1_home`: 2 (12.5%)
  - `pp_steals_star1_away`: 2 (12.5%)
  - `pp_steals_star2_home`: 2 (12.5%)
  - `pp_threes_star2_away`: 1 (6.2%)
  - `pp_assists_role2_away`: 1 (6.2%)
  - `pp_steals_role2_away`: 1 (6.2%)
  - `pp_steals_star1_home`: 1 (6.2%)
  - `pp_blocks_role1_away`: 1 (6.2%)
  - `pp_points_star1_home`: 1 (6.2%)
  - `alt_spread_away_plus18`: 1 (6.2%)
  - `pp_steals_role1_away`: 1 (6.2%)
  - `pp_steals_star3_away`: 1 (6.2%)
  - `pp_threes_star3_home`: 1 (6.2%)

### `nvidia-llama70`
- distinct cats: 2 — distinct combos: 12 — homogeneity: 58%
  - `ml_home`: 7 (58.3%)
  - `ml_away`: 5 (41.7%)

### `nvidia-minimax`
- distinct cats: 7 — distinct combos: 9 — homogeneity: 33%
  - `q1_total_under`: 3 (33.3%)
  - `alt_total_over_plus4`: 1 (11.1%)
  - `pp_threes_star1_home`: 1 (11.1%)
  - `alt_spread_away_plus20`: 1 (11.1%)
  - `pp_threes_star3_home`: 1 (11.1%)
  - `alt_total_under_237`: 1 (11.1%)
  - `alt_total_under_227`: 1 (11.1%)

### `mistral-medium`
- distinct cats: 6 — distinct combos: 8 — homogeneity: 25%
  - `pp_steals_star1_away`: 2 (25.0%)
  - `pp_steals_star2_away`: 2 (25.0%)
  - `pp_threes_role2_away`: 1 (12.5%)
  - `pp_blocks_star2_home`: 1 (12.5%)
  - `pp_steals_star1_home`: 1 (12.5%)
  - `spread_home`: 1 (12.5%)

### `selfhost-qwen4b`
- distinct cats: 6 — distinct combos: 8 — homogeneity: 25%
  - `ml_home`: 2 (25.0%)
  - `ml_away`: 2 (25.0%)
  - `pp_blocks_star2_home`: 1 (12.5%)
  - `pp_steals_star2_home`: 1 (12.5%)
  - `pp_steals_star3_away`: 1 (12.5%)
  - `pp_steals_role1_home`: 1 (12.5%)

### `gemini-anl`
- distinct cats: 6 — distinct combos: 7 — homogeneity: 29%
  - `ml_away`: 2 (28.6%)
  - `spread_home`: 1 (14.3%)
  - `pp_rebounds_star1_away`: 1 (14.3%)
  - `pp_steals_star1_home`: 1 (14.3%)
  - `alt_spread_home_minus18`: 1 (14.3%)
  - `pp_steals_star2_away`: 1 (14.3%)

### `selfhost-dolphin3`
- distinct cats: 4 — distinct combos: 6 — homogeneity: 50%
  - `ml_home`: 3 (50.0%)
  - `pp_steals_star2_away`: 1 (16.7%)
  - `pp_steals_star3_home`: 1 (16.7%)
  - `pp_steals_star1_home`: 1 (16.7%)

### `gemini-tact`
- distinct cats: 4 — distinct combos: 5 — homogeneity: 40%
  - `pp_steals_star1_home`: 2 (40.0%)
  - `h1_total_over`: 1 (20.0%)
  - `pp_blocks_star3_away`: 1 (20.0%)
  - `pp_steals_star2_away`: 1 (20.0%)

### `qwen-arb`
- distinct cats: 4 — distinct combos: 4 — homogeneity: 25%
  - `ml_away`: 1 (25.0%)
  - `pp_assists_role1_away`: 1 (25.0%)
  - `pp_steals_star2_home`: 1 (25.0%)
  - `pp_steals_role2_home`: 1 (25.0%)

### `llama-contra`
- distinct cats: 2 — distinct combos: 2 — homogeneity: 50%
  - `spread_away`: 1 (50.0%)
  - `ml_away`: 1 (50.0%)
