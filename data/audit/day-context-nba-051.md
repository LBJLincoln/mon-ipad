# NBA day-051 (2025-12-12) — full agent + engine context
Generated 2026-04-26 09:15 UTC
Day file written: 2026-04-26T07:35:49.083246+00:00

**7 games** | **17 agents** | total bets: 15

Loading engine predictions + games + rosters (large files, may take 30s)…

## Per-game forensic

### ATL@DET
- **engine consensus**: ml=home (agree 96%) | spread=home | total=under
- **engine predicted**: margin=+6.55 | total=233.3 | p(home)=0.780
- **TOP-15 engine edges** (out of 285):
  | category | prob | edge | NOTE |
  |---|---:|---:|---|
  | `pp_steals_role1_away` | 0.000 | +0.100 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_blocks_role1_away` | 0.000 | +0.100 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_star2_home` | 0.000 | +0.083 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_star2_away` | 0.000 | +0.083 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_star1_away` | 0.000 | +0.083 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `ml_home` | 0.780 | +0.073 |  |
  | `ml_away` | 0.220 | -0.073 |  |
  | `pp_steals_star1_home` | 0.000 | +0.071 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_star2_away` | 0.000 | +0.069 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_assists_role1_away` | 0.000 | +0.067 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_star1_away` | 0.000 | +0.062 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_rebounds_star2_away` | 0.000 | +0.062 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_rebounds_role2_away` | 0.000 | +0.062 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_rebounds_star2_home` | 0.000 | +0.060 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_assists_star3_home` | 0.000 | +0.059 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
- **2 agent bets**:
  | agent | category | odds | edge | edge_source | LLM_edge | engine_edge | stake | won | profit |
  |---|---|---:|---:|---|---:|---:|---:|:---:|---:|
  | `nvidia-llama70` | ml_home | 1.22 | 0.073 | engine | 0.073 | 0.073 | $15.37 | ✓ | $+3.40 |
  | `mistral-large` | ml_home | 1.22 | 0.073 | engine | 0.073 | 0.073 | $5.64 | ✓ | $+1.25 |

### IND@PHI
- **engine consensus**: ml=home (agree 100%) | spread=home | total=under
- **engine predicted**: margin=+5.58 | total=221.1 | p(home)=0.744
- **TOP-15 engine edges** (out of 285):
  | category | prob | edge | NOTE |
  |---|---:|---:|---|
  | `pp_steals_star1_away` | 0.000 | +0.100 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_blocks_role1_home` | 0.000 | +0.100 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_role1_home` | 0.000 | +0.083 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_star3_home` | 0.000 | +0.083 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `ml_home` | 0.744 | +0.080 |  |
  | `ml_away` | 0.256 | -0.080 |  |
  | `pp_steals_star2_home` | 0.000 | +0.077 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_role2_home` | 0.000 | +0.067 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_star1_home` | 0.000 | +0.065 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_star1_away` | 0.000 | +0.062 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_role2_away` | 0.000 | +0.062 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_rebounds_role2_away` | 0.000 | +0.062 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_assists_star3_home` | 0.000 | +0.062 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_rebounds_role2_home` | 0.000 | +0.061 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_star3_home` | 0.000 | +0.059 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
- **12 agent bets**:
  | agent | category | odds | edge | edge_source | LLM_edge | engine_edge | stake | won | profit |
  |---|---|---:|---:|---|---:|---:|---:|:---:|---:|
  | `gemini-tact` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $2.70 | ✓ | $+0.76 |
  | `mistral-small` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $2.20 | ✓ | $+0.62 |
  | `selfhost-qwen4b` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $2.08 | ✓ | $+0.58 |
  | `mistral-ministral` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $2.05 | ✓ | $+0.58 |
  | `gemini-anl` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $2.02 | ✓ | $+0.57 |
  | `llama-contra` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $2.00 | ✓ | $+0.56 |
  | `nvidia-minimax` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $1.84 | ✓ | $+0.52 |
  | `nemotron-120b` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $1.81 | ✓ | $+0.51 |
  | `qwen-quant` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $1.76 | ✓ | $+0.49 |
  | `mistral-nemo` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $1.68 | ✓ | $+0.47 |
  | `selfhost-qwen06` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $1.54 | ✓ | $+0.43 |
  | `selfhost-gemma3` | ml_home | 1.28 | 0.080 | engine_forced_floor | — | 0.080 | $1.45 | ✓ | $+0.41 |

### UTA@MEM
- **engine consensus**: ml=home (agree 91%) | spread=home | total=under
- **engine predicted**: margin=+7.94 | total=243.5 | p(home)=0.767
- **TOP-15 engine edges** (out of 284):
  | category | prob | edge | NOTE |
  |---|---:|---:|---|
  | `pp_threes_star1_home` | 0.000 | +0.111 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_star2_away` | 0.000 | +0.111 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_star1_home` | 0.000 | +0.111 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_role2_away` | 0.000 | +0.100 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_assists_role2_home` | 0.000 | +0.100 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_role1_away` | 0.000 | +0.083 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_role1_home` | 0.000 | +0.071 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_threes_star2_home` | 0.000 | +0.067 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_star3_away` | 0.000 | +0.067 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_rebounds_star3_home` | 0.000 | +0.067 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_assists_star3_home` | 0.000 | +0.067 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `ml_home` | 0.767 | +0.066 |  |
  | `ml_away` | 0.233 | -0.066 |  |
  | `pp_rebounds_star1_home` | 0.000 | +0.065 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
  | `pp_steals_star1_away` | 0.000 | +0.062 | ⚠ prob=0 but edge!=0 — likely engine hallucination |
- **1 agent bets**:
  | agent | category | odds | edge | edge_source | LLM_edge | engine_edge | stake | won | profit |
  |---|---|---:|---:|---|---:|---:|---:|:---:|---:|
  | `qwen-arb` | ml_home | 1.24 | 0.066 | engine | 0.066 | 0.066 | $7.79 | ✗ | $-7.79 |

## Silent agents (no bets today)

- `selfhost-dolphin3` bk=$28.5
- `mistral-medium` bk=$28.8
