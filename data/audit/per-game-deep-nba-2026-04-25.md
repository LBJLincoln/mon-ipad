# NBA — per-game cross-agent forensic
Generated 2026-04-25 13:19 UTC
Last 14 dates expanded (168 total game-rows in JSON)

> Reads: for each (date, game/event), which agents picked WHAT and WHY.
> Use to spot consensus vs divergence, and identify why agents diverged.

## 2026-01-13
### MIN@MIL (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-tact` | pp_blocks_star3_away | 1.91 | 0.111 | $2.99 | ✗ | Anthony Edwards' 0.9 bpg career average vs Giannis' 1.4 bpg creates a blocks mismatch; model edge 11.1% on pp_blocks_star3_away. |

### PHX@MIA (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-tact` | pp_steals_star1_home | 1.91 | 0.091 | $2.54 | ✗ | Norman Powell's 22p usage and 1.5 spg career average vs MIA's 13.8 TOV/gm create a steal-heavy matchup; model edge 9.1% on pp_steals_star1_home. |
| `mistral-small` | pp_steals_star2_away | 1.91 | 0.111 | $1.05 | ✗ | Tyler Herro's 21% usage rate + MIA's 113.6 defensive rating create a 11.1% edge on steals props vs market price. |

### SAS@OKC (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `qwen-quant` | pp_threes_star2_home | 1.91 | 0.091 | $2.00 | ✗ | Chet Holmgren (OKC) averages 2.8 threes/game on 41% shooting; market line (2.5) is 0.3 below my projection, yielding a 9.1% edge. |

## 2026-01-12
### UTA@CLE (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-small` | alt_spread_home_minus1.5 | 2.87 | 0.111 | $1.10 | ✗ | Model predicts CLE margin +13.6 vs alt_spread_home_minus1.5 line (-1.5) implying 90% win probability; market odds 1.50 imply 66.7% — edge 11.1% is the highest non-prop edge today. |

## 2026-01-11
### NOP@ORL (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `selfhost-gemma3` | pp_steals_star2_home | 1.91 | 0.111 | $1.43 | ✗ | Franz Wagner's steals per game (1.8) and NOP's turnovers (15.2/game) drive a 11.1% edge vs. market odds (p=0.00). |

### WAS@PHX (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `selfhost-gemma3` | pp_steals_star2_home | 1.91 | 0.111 | $1.37 | ✗ | Dillon Brooks averages 1.5 steals in last 10 games; WAS's 14.8 turnovers/game create a 11.1% edge vs. market (p=0.00). |
| `mistral-small` | pp_blocks_star2_away | 1.91 | 0.111 | $1.14 | ✗ | PHX's frontcourt averages 6.2 blocks/game; Devin Booker's role players average 0.8 blocks vs market implied 0.3%. Model edge 11.1% is highest non-crowded edge today. |

## 2026-01-10
### MIN@CLE (3 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` | pp_steals_star2_away | 1.91 | 0.100 | $2.58 | ✗ | Julius Randle averages 1.1 steals in last 10 games; market line at 1.0 underprices his recent form and pace. |
| `mistral-large` | pp_steals_role1_away | 1.91 | 0.111 | $1.71 | ✗ | Anthony Edwards averages 1.8 steals per game with 3.5 steals in last 5; model flags +11.1% edge on his steal prop vs market |
| `mistral-small` | pp_blocks_star3_away | 1.91 | 0.111 | $1.19 | ✗ | Jaden McDaniels averages 1.8 blocks in last 10 games vs CLE's 51% FG% allowed at rim; market underprices away player blocks |

## 2026-01-08
### CLE@MIN (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-small` | pp_blocks_star3_home | 1.91 | 0.111 | $1.24 | ✗ | Anthony Edwards averages 1.2 blocks in last 10 games; market line 1.5 blocks at 1.00 implies 0.5 blocks edge. |

### DAL@UTA (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `qwen-quant` | alt_total_under_241.5 | 1.85 | 0.093 | $1.95 | ✓ | UTA's pace (96.5, 30th in NBA) + DAL's defense (115.5 DRTG, 12th) + both teams playing on 0 days rest (fatigue) suppress scoring. Model predicts 240.2 vs line 241.5, with 78% historical under hit rate in similar matchups (pace <98, rest=0). |

### IND@CHA (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `nvidia-llama70` | ml_home | 1.35 | 0.080 | $3.09 | ✗ | CHA's home advantage and recent form give them an edge, beating the market price. |
| `selfhost-dolphin3` | pp_steals_star1_home | 1.91 | 0.100 | $2.47 | ✗ | The model predicts LaMelo Ball will have more steals than his average, and the market odds are undervaluing this prop. |

## 2026-01-07
### CHI@DET (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `selfhost-gemma3` | pp_steals_star1_home | 1.91 | 0.100 | $1.58 | ✗ | Cade Cunningham averages 1.2 steals/game in last 10; market odds imply 0.00 edge but model shows 10.0% edge. |

### DEN@BOS (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `selfhost-gemma3` | pp_steals_role2_away | 1.91 | 0.110 | $1.52 | ✗ | Jamal Murray averages 1.4 steals/game in last 10; model edge=11.1% vs market implied 0.00. |

## 2026-01-06
### CLE@IND (3 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` | pp_steals_star1_away | 1.91 | 0.100 | $2.74 | ✗ | Donovan Mitchell's recent performance and steal metrics indicate a strong edge over the market price. |
| `selfhost-gemma3` | pp_steals_star1_away | 1.91 | 0.100 | $1.65 | ✗ | James Harden averages 2.1 steals/game in last 5 games; market odds underprice his steals role (p=0.00 vs implied 0.50). |
| `mistral-small` | pp_steals_star1_away | 1.91 | 0.100 | $1.29 | ✗ | Evan Mobley averages 1.8 steals/game in last 10; market odds imply 0.9 steals (p=0.00 vs model p=0.10). |

### ORL@WAS (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-medium` | pp_blocks_star2_home | 1.91 | 0.111 | $2.66 | ✗ | Anthony Davis's block metrics show a significant edge over the market price. |

## 2026-01-05
### CHA@OKC (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `nvidia-llama70` | ml_home | 1.00 | 0.100 | $3.12 | ✗ | OKC's strong offense and defense metrics give them a high edge on ml_home. |

## 2026-01-04
### MIN@WAS (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `selfhost-dolphin3` | pp_steals_star2_away | 1.91 | 0.100 | $2.79 | ✗ | Anthony Edwards (MIN) has 2.1 steals/game in last 5 games, market underprices his defensive impact (model: 2.5 steals, odds imply 1.5). |
| `mistral-small` | pp_steals_star2_away | 1.91 | 0.111 | $1.34 | ✗ | Model edge 11.1% on MIN's away steals (star2) vs market p=0.00; WAS's defensive rating (121.5) and MIN's aggressive defense create structural steal opportunities. |

### NOP@MIA (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `selfhost-dolphin3` | pp_steals_star3_home | 1.91 | 0.100 | $2.71 | ✗ | Bam Adebayo (MIA) averages 1.8 steals/game but market odds imply 1.0; model predicts 1.5 steals (edge=10.0%). |

## 2026-01-03
### POR@SAS (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `gemini-anl` | pp_steals_star2_away | 1.91 | 0.100 | $2.62 | ✗ | SAS's Fox/Wembanyama generate 10.0% edge on away steals due to defensive pressure and POR's turnover-prone guards (McCollum/Sharpe avg 3.8 TOV). |

## 2026-01-02
### DEN@CLE (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `nvidia-llama70` | ml_home | 1.21 | 0.080 | $3.08 | ✓ | CLE's home-court advantage (+4.1 NetRTG) and 88.9% implied probability (1.12 odds) undervalue model's 79% win probability, creating +8.0% edge. |

### SAC@PHX (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-small` | pp_steals_star2_home | 1.91 | 0.111 | $1.40 | ✗ | PHX's defensive rating (112.9) and model's 93% ML confidence create a market mispricing of steals props; SAC's role players (e.g., Sabonis) are prone to turnovers. |

## 2026-01-01
### HOU@BKN (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `nvidia-llama70` | ml_away | 1.03 | 0.080 | $3.08 | ✓ | The ml_away category in game 1 has the highest edge today, driven by the significant difference in team performance metrics. |

## 2025-12-30
### PHI@MEM (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `qwen-quant` | pp_threes_star1_home | 1.91 | 0.111 | $2.07 | ✗ | Ty Jerome's 3P% (42.1%) and volume (8.2 3PA) vs PHI's 3P defense (35.8% allowed) create a +11.1% edge on pp_threes_star1_home (odds=2.20). |

## 2025-12-29
### GSW@BKN (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-small` | pp_steals_star1_home | 1.91 | 0.100 | $1.46 | ✗ | Model edge 10.0% on BKN's steals rate (10.0%) vs GSW's (7.1%) with Claxton's rim protection limiting GSW's transition. |

### IND@HOU (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `nvidia-llama70` | ml_home | 1.05 | 0.080 | $3.17 | ✓ | HOU’s +5.4 NetRTG and 5-5 L10 vs IND’s -7.8 NetRTG and 2-8 L10 drive 91% model probability (edge=8.0%) vs market’s 86.2%. |

### MIL@CHA (1 bet)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `mistral-small` | pp_steals_star3_home | 1.91 | 0.100 | $1.58 | ✗ | Model edge 10.0% on CHA's steals rate (10.1%) vs MIL's (7.8%) with Miller/Ball's ball-dominant roles. |

### PHX@WAS (2 bets)
| agent | category | odds | edge | stake | won | rationale |
|---|---|---:|---:|---:|:---:|---|
| `nvidia-llama70` | ml_away | 1.12 | 0.080 | $3.16 | ✓ | PHX’s NetRTG (+1.4) and 6-4 L10 form vs WAS’s -11.8 NetRTG and 4-6 L10 drive 85% model probability (edge=8.0%) vs market’s 81%. |
| `mistral-small` | pp_steals_star1_home | 1.91 | 0.100 | $1.52 | ✗ | Model edge 10.0% on WAS's steals rate (9.1%) vs PHX's (6.2%) with Trae Young's turnover-prone style. |
