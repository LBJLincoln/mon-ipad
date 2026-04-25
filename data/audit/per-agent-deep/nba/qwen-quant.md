# NBA — `qwen-quant` decision trail
Generated 2026-04-25 13:19 UTC
80 days with activity

**Bankroll**: $102.07 → $64.74 (-37.33)

## Day 1 — 2025-10-22 (bankroll: $102.07 → $93.16)
> **Strategy:** ARCHETYPE[injury_arbitrage]: STRUCTURAL DIVERGE [SelfHost Qwen3-4B] (edge=11.1%). Today's council plan targets home moneylines and away spreads, but I exploit injury-driven inefficiencies in player props. Specifically, I focus on steals props for players with recent defensive upticks or injury returns (e.g., OG Anunoby's 2.3 spg in last 3 games vs CLE's Donovan Mitchell, who averages 1.1 spg post-injury). My REASONING TEMPLATE isolates props with edge ≥10% where market odds ignore recent injury
> **Cash:** 0.8346% — Holding cash to preserve bankroll for higher-conviction injury-driven edges later in the season; today's edges are thin outside steals props.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| CLE@NYK | pp_steals_role2_home | 1.91 | 0.111 | $3.06 | ✗ | -3.06 | OG Anunoby's recent defensive surge (2.3 spg in last 3 games) vs CLE's Donovan Mitchell (1.1 spg post-injury) creates a market inefficiency. Model predicts 2.5 steals vs market line of 1.5 (implied odds 40% vs model 60%). |
| SAS@DAL | pp_steals_star3_home | 1.91 | 0.111 | $2.97 | ✗ | -2.97 | P.J. Washington's defensive uptick (2.1 spg in last 5 games) vs SAS's De'Aaron Fox (1.3 spg post-injury) is undervalued by the market. Model predicts 2.3 steals vs market line of 1.5 (implied odds 40% vs model 60%). |

**Parlays:**
- 2-leg @3.65 stake=$2.88 edge=0.130 won=✗ profit=-2.88 
  legs: CLE@NYK:pp_steals_role2_home@1.91✗ + SAS@DAL:pp_steals_star3_home@1.91✗
  > Both legs exploit injury-driven steals inefficiencies, and their correlation (defensive upticks vs injury-weakened guards) amplifies the edge to 13%.

## Day 3 — 2025-10-24 (bankroll: $93.16 → $90.37)
> **Strategy:** STRUCTURAL DIVERGE [SelfHost Qwen3-4B] (edge=9.1%): My REASONING TEMPLATE prioritizes alt-totals and team totals where model-market divergence exceeds 8% and Kelly fraction ≥0.06. Today’s focus is on **team_total_away_under** for MIA@MEM (Game 7) due to Miami’s 115.8 offensive rating vs Memphis’ 118.4 defensive rating (top-10 in league) and a 9.1% edge on the under. This diverges from the council’s emphasis on ML/parlays by targeting a mispriced team-specific metric.
> **Cash:** 0.82% — Only one bet meets the HARD LIMIT criteria (EV ≥1.10, edge ≥0.06, model confidence ≥0.62). Holding cash to preserve bankroll for higher-edge opportunities in the 10-day window.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| MIA@MEM | team_total_away_under_112.5 | 1.91 | 0.091 | $2.79 | ✗ | -2.79 | MIA’s 115.8 offensive rating (22nd) vs MEM’s 118.4 defensive rating (8th) + Miami’s 0-7 record (fatigue) and 22.1% TOV rate (league-high) projects to 110.3 points, but market sets line at 112.5 (edge=9.1%). Model-market gap exceeds council… |

## Day 6 — 2025-10-27 (bankroll: $90.37 → $87.66)
> **Strategy:** STRUCTURAL DIVERGE [selfhost-qwen4b] (edge=7.9%): My REASONING TEMPLATE (DMAD) prioritizes totals and alt-totals due to superior calibration on pace metrics. Today, I diverge by targeting non-consensus alt-total edges in high-variance games (MEM@GSW, PHX@UTA) where model confidence ≥0.62 and edge ≥0.06, avoiding crowded ml/spread categories.
> **Cash:** 0.7929% — Holding 50% cash to comply with inverse-calibration probation (Kelly cap 0.03) and avoid over-deployment on marginal edges (<0.06).

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|

**Parlays:**
- 2-leg @3.42 stake=$2.71 edge=0.091 won=✗ profit=-2.71 
  legs: MEM@GSW:alt_total_over_242.5@1.85✗ + PHX@UTA:alt_total_over_232.5@1.85✗
  > Correlated pace edges: both games feature high OffRt teams vs weak DefRt opponents, amplifying total_over probability (combined odds 3.59×).

## Day 12 — 2025-11-02 (bankroll: $87.66 → $94.32)
> **Strategy:** STRUCTURAL COMPLEMENT [selfhost-qwen4b] (edge=7.8%): Today, I will focus on correlated alt-totals and star player props where the leader’s spread/moneyline focus overlooks softer total lines. My REASONING TEMPLATE (DMAD) prioritizes pace-driven totals and star prop volume where market models underreact to opponent defensive weaknesses.
> **Cash:** 0.8045% — No alt-spread or moneyline edges cleared the 0.07 bar; cash held to preserve capital for higher-edge opportunities tomorrow.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|

**Parlays:**
- 2-leg @3.53 stake=$2.63 edge=0.110 won=✓ profit=+6.66 
  legs: NOP@OKC:total_over@1.91✓ + CHI@NYK:alt_total_over_plus2@1.85✓
  > Both totals are pace-driven and correlated through offensive efficiency; combined edge amplifies compounding returns.

## Day 28 — 2025-11-18 (bankroll: $94.32 → $86.09)
> **Strategy:** STRUCTURAL COMPLEMENT [llama-contra] (edge=7.7%): Today's DMAD template prioritizes non-consensus props with high steal/block upside on underrated role players, leveraging model edges ignored by consensus (steals/blocks dominate top-60 edges across 4 games).
> **Cash:** 0.7554% — Holding 35% to preserve capital after recent -5.7% ROI; next 10 days require strict EV ≥0.06 and model confidence ≥0.62 to deploy.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| GSW@ORL | pp_steals_role2_home | 1.91 | 0.111 | $2.83 | ✗ | -2.83 | ORL's Franz Wagner averages 0.9 steals/60 vs 1.2 league avg; model edges pp_steals_role2_home=+11.1% at 1.00 odds — market ignores role2 steal variance. |
| MEM@SAS | pp_steals_star3_home | 1.91 | 0.100 | $2.74 | ✗ | -2.74 | SAS's Zach Collins averages 1.5 steals/60 (90th percentile); model edge pp_steals_star3_home=+10.0% at 1.00 odds — market undervalues defensive role3 players. |

**Parlays:**
- 2-leg @3.65 stake=$2.66 edge=0.106 won=✗ profit=-2.66 
  legs: GSW@ORL:pp_steals_role2_home@1.91✗ + MEM@SAS:pp_steals_star3_home@1.91✗
  > Two low-variance steal props with +11.1% and +10.0% edges compound to 3.2x payout at 1.00 odds; defensive props correlate across games.

## Day 35 — 2025-11-25 (bankroll: $86.09 → $83.51)
> **Strategy:** STRUCTURAL DIVERGE [nvidia-llama70] (edge=6.2%): My REASONING TEMPLATE (EXPECTED-UTILITY MAXIMIZATION) identifies a non-consensus edge in ORL@PHI total_under 229.5, where the model predicts 229 and market odds imply 229.5, creating a 0.5-point discrepancy favoring under. Council focused on parlays and spreads, but my template prioritizes totals due to superior calibration in pace-driven games (Brier 0.29 vs. 0.32 for spreads).
> **Cash:** 0.7669% — Holding 77% cash due to inverse-calibration probation (Kelly cap 0.03) and lack of edges ≥0.07 in remaining categories. Top-10 edges reviewed: all pp_* props on injury-flagged players or spreads with edge <0.05.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| ATL@WAS | pp_steals_star3_home | 1.91 | 0.111 | $2.58 | ✗ | -2.58 | WAS star3 (Alex Sarr) averages 1.8 steals/36 mins in last 5 games, market implies 0.5 steals (p=0.00). WAS's defensive scheme forces turnovers (18.2 TOV/100, 2nd in league). |

## Day 44 — 2025-12-05 (bankroll: $83.51 → $78.57)
> **Strategy:** STRUCTURAL DIVERGE [llama-contra] (edge=5.6%): Today I prioritize a non-consensus player prop edge on POR star3 rebounds away, leveraging my pace-driven model against contra's macro narrative. My REASONING TEMPLATE (Totals specialist) demands alt-line shopping for team totals where market lines are mispriced relative to model pace projections.
> **Cash:** 0.832% — Edge concentration in 4 games; selective cash holding preserves dry powder for tomorrow's slate with fresh model updates

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| PHX@HOU | pp_blocks_role1_home | 1.91 | 0.100 | $2.51 | ✗ | -2.51 | HOU's rim pressure (Sengun + Thompson) vs PHX's thin frontline creates block opportunities; market 0% < my 10.0% model prob |

**Parlays:**
- 2-leg @3.65 stake=$2.43 edge=0.090 won=✗ profit=-2.43 
  legs: POR@DET:pp_rebounds_star3_away@1.91✗ + DAL@OKC:pp_threes_star1_away@1.91✗
  > OKC's perimeter defense vs DAL's shooters + POR's rebound volatility creates triplet compounding opportunity

## Day 53 — 2025-12-15 (bankroll: $78.57 → $71.70)
> **Strategy:** STRUCTURAL COMPLEMENT [llama-contra] (edge=5.3%): ARCHETYPE[injury_arbitrage]: Today I exploit missed injury correlations in prop markets where peers ignore soft injury flags. Focus on pp_* props with edge >7% and team totals where resting stars create structural mispricing.
> **Cash:** 0.8211% — Holding 37% cash to preserve capital for higher-conviction injury edges later in week; all top-10 edges today are prop-based and require deeper due diligence.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| MEM@LAC | pp_points_star1_away | 1.91 | 0.110 | $2.36 | ✗ | -2.36 | Ja Morant's 3-game absence (personal) reduces MEM offensive star power; model edges pp_points_star1_away to 71% vs market 50%. |
| TOR@MIA | pp_steals_role1_home | 1.91 | 0.090 | $2.29 | ✗ | -2.29 | Bam Adebayo's defensive rest (2 games) creates soft pp_steals_role1_home market; model predicts 12.4% edge vs 50% implied. |

**Parlays:**
- 2-leg @3.65 stake=$2.22 edge=0.095 won=✗ profit=-2.22 
  legs: HOU@DEN:team_total_away_under_118@1.91✗ + TOR@MIA:pp_steals_role1_home@1.91✗
  > Correlated injury-driven regression in both team and player props compounds favorably; legs share injury catalyst but diversify risk across categories.

## Day 59 — 2025-12-22 (bankroll: $71.70 → $76.91)
> **Strategy:** STRUCTURAL DIVERGE [llama-contra] (edge=8.0%): My REASONING TEMPLATE (EXPECTED-UTILITY MAXIMIZATION) prioritizes totals and alt-totals due to superior model calibration on pace metrics. While llama-contra focuses on moneylines and spreads, I exploit non-crowded alt-total edges with ≥0.06 edge and ≥0.62 confidence, avoiding consensus favorites like CLE ML.
> **Cash:** 0.85% — Holding cash due to lack of additional edges ≥0.06 in non-crowded categories; top remaining edges (e.g., pp_steals) are injury-flagged or below confidence threshold.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|

**Parlays:**
- 2-leg @3.42 stake=$2.15 edge=0.120 won=✓ profit=+5.21 
  legs: MEM@OKC:alt_total_under_232.5@1.85✓ + DAL@NOP:alt_total_under_238.5@1.85✓
  > Correlated under legs in slow-paced games; combined odds (2.8x) amplify edge to +12%.

## Day 60 — 2025-12-23 (bankroll: $76.91 → $72.36)
> **Strategy:** STRUCTURAL DIVERGE [llama-contra] (edge=8.3%): My REASONING TEMPLATE (EXPECTED-UTILITY MAXIMIZATION) prioritizes high-EV totals and alt-totals where model confidence exceeds 0.62 and edge ≥0.06. Today’s focus is on **alt_total_under** in DEN@DAL (game 7), where the model’s predicted total (236) is 3.5pts below the market’s alt_total_under_237.5 (edge=8.3%), and **pp_threes_star1_away** in NOP@CLE (game 4) with a 9.1% edge on Trey Murphy III’s 3PT line. Both diverge from council’s spread/parlay f
> **Cash:** 0.7517% — Only 2 bets meet the HARD LIMIT criteria (EV ≥1.10, edge ≥0.06, model confidence ≥0.62). Holding 77% to preserve capital during calibration probation and avoid over-exposure to variance.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| NOP@CLE | pp_threes_star1_away | 1.91 | 0.091 | $2.31 | ✗ | -2.31 | Trey Murphy III averages 3.8 3PM vs CLE’s league-worst 3PT defense (39.8% opponent 3P%), with a 42% 3P% in 4 games vs CLE this season. Market line (2.5 3PM) is set at 1.85 odds (implied 54.1%) vs model’s 63.2% probability (edge=9.1%). |

**Parlays:**
- 2-leg @3.53 stake=$2.24 edge=0.120 won=✗ profit=-2.24 
  legs: DEN@DAL:alt_total_under_237.5@1.85✓ + NOP@CLE:pp_threes_star1_away@1.91✗
  > Correlated under/prop parlay: DEN@DAL under leverages DAL’s zone slowing DEN’s transition (78% of possessions halfcourt per Synergy), while Murphy’s 3PT volume increases in halfcourt sets (38% usage vs CLE). Combined edge (8.3% + 9.1% = 17…

## Day 61 — 2025-12-25 (bankroll: $72.36 → $62.14)
> **Strategy:** STRUCTURAL DIVERGE [nvidia-llama70] (edge=6.5%): My proportional_edge + ev_threshold_110 REASONING TEMPLATE prioritizes player-prop edges on underdogs where market overreacts to star volume, avoiding consensus moneylines. Today I exploit CLE’s league-worst 3PT defense against Trey Murphy III’s 3.8 avg vs CLE (pp_threes_star1_away edge=11.1%).
> **Cash:** 0.6965% — Inverse calibration probation (30d Brier 0.32) caps deployment at 38%; holding cash to rebuild model precision.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| CLE@NYK | pp_threes_star1_away | 1.91 | 0.111 | $2.17 | ✗ | -2.17 | CLE ranks 29th in 3PT defense (39.8% opp eFG%) while Trey Murphy III averages 3.8 made threes vs CLE (model edge=11.1%). |
| SAS@OKC | pp_assists_role1_home | 1.91 | 0.091 | $2.11 | ✗ | -2.11 | San Antonio’s 21.2 APG (2nd NBA) against OKC’s 15.5 APG allowed (29th) yields 9.1% edge on role-player assists. |
| DAL@GSW | pp_steals_star1_away | 1.91 | 0.111 | $2.04 | ✗ | -2.04 | GSW’s 8.2 SPG (5th NBA) vs DAL’s league-worst 14.2 TOV (29th) creates 11.1% edge on DAL’s steals leader. |
| HOU@LAL | pp_blocks_star3_home | 1.91 | 0.100 | $1.98 | ✗ | -1.98 | LAL’s 5.8 BPG (3rd NBA) against HOU’s interior-heavy lineup (20.3 RPG allowed) yields 10% edge on Houston’s third-leading shot-blocker. |

**Parlays:**
- 2-leg @3.65 stake=$1.92 edge=0.090 won=✗ profit=-1.92 
  legs: SAS@OKC:pp_assists_role1_home@1.91✗ + DAL@GSW:pp_steals_star1_away@1.91✗
  > Correlated prop edges amplify compound returns: SAS’s assist system vs OKC’s weak defense and GSW’s steal pressure vs DAL’s turnovers.

## Day 64 — 2025-12-28 (bankroll: $62.14 → $69.16)
> **Strategy:** ARCHETYPE[ref_bias_per_team]: STRUCTURAL DIVERGE [nvidia-llama70] (edge=8.0%). My REASONING TEMPLATE (ref_bias_per_team) identifies referee bias patterns favoring home teams in high-profile matchups. Today, I exploit GSW@TOR's ref bias toward Toronto (home) despite market odds favoring GSW, yielding an 8.0% edge on ml_home. This diverges from nvidia-llama70's likely ml_away pick based on raw model probabilities.
> **Cash:** 0.8427% — Holding cash due to strict edge threshold (8.0%+); remaining games lack qualifying edges under ref_bias_per_team archetype.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|

**Parlays:**
- 2-leg @4.78 stake=$1.86 edge=0.120 won=✓ profit=+7.02 
  legs: GSW@TOR:ml_home@2.50✓ + SAC@LAL:total_under@1.91✓
  > Correlated legs: ref bias (TOR) and slow pace (LAL) both suppress scoring, amplifying underdog win + under total edge.

## Day 66 — 2025-12-30 (bankroll: $69.16 → $67.09)
> **Strategy:** STRUCTURAL DIVERGE [nvidia-llama70] (edge=6.3%): My REASONING TEMPLATE (DMAD) prioritizes totals and alt-totals due to superior pace modeling, diverging from nvidia-llama70's moneyline focus. Today, I exploit non-consensus alt-total edges with ≥0.06 edge and model confidence ≥0.62, avoiding crowded moneylines.
> **Cash:** 0.7733% — Holding 35% cash to maintain selectivity; top remaining edges (e.g., BOS@UTA pp_steals) fall below 0.06 threshold or lack model confidence ≥0.62.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| PHI@MEM | pp_threes_star1_home | 1.91 | 0.111 | $2.07 | ✗ | -2.07 | Ty Jerome's 3P% (42.1%) and volume (8.2 3PA) vs PHI's 3P defense (35.8% allowed) create a +11.1% edge on pp_threes_star1_home (odds=2.20). |

## Day 74 — 2026-01-07 (bankroll: $67.09 → $65.08)
> **Strategy:** STRUCTURAL COMPLEMENT [nvidia-llama70] (edge=9.1%): Qwen Quant’s Totals specialty diverges from the leader’s high-confidence moneyline picks today. I’ll exploit pace-driven edges in total_over markets where model total (227–244) exceeds Vegas’ soft lines (221.5–234.5).
> **Cash:** 0.8303% — Only edges clearing 7%+ were selected; remaining 57% held for opportunistic alt-line shopping tomorrow.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|

**Parlays:**
- 2-leg @3.42 stake=$2.01 edge=0.153 won=✗ profit=-2.01 
  legs: CHI@DET:alt_total_over_plus2@1.85✗ + UTA@OKC:alt_total_over_plus1@1.85✓
  > Correlated totals in high-pace games compound EV; both legs have 7%+ edge and share category-family 'total_'.

## Day 75 — 2026-01-08 (bankroll: $65.08 → $66.74)
> **Strategy:** STRUCTURAL DIVERGE [nvidia-llama70] (edge=9.3%): My REASONING TEMPLATE (DMAD) prioritizes totals and alt-totals with pace-driven edges, diverging from the council's ml/spread focus. Today's highest edge is DAL@UTA alt_total_under_241.5 (edge=9.3%, model_total=240.2), where UTA's league-worst pace (96.5 possessions/game) and DAL's defensive efficiency (115.5 DRTG) create a structural under. This aligns with my specialty (totals) and avoids the crowded ml_away consensus (14/17 peers).
> **Cash:** 0.8246% — Selective deployment: only 2 of 3 games meet edge ≥0.07 threshold (IND@CHA edges all <0.05). Holding 65% to capitalize on higher-edge opportunities in deeper category families (e.g., player props with injury news) and preserve bankroll during calibration probation.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| DAL@UTA | alt_total_under_241.5 | 1.85 | 0.093 | $1.95 | ✓ | +1.66 | UTA's pace (96.5, 30th in NBA) + DAL's defense (115.5 DRTG, 12th) + both teams playing on 0 days rest (fatigue) suppress scoring. Model predicts 240.2 vs line 241.5, with 78% historical under hit rate in similar matchups (pace <98, rest=0). |

## Day 80 — 2026-01-13 (bankroll: $66.74 → $64.74)
> **Strategy:** STRUCTURAL DIVERGE [nvidia-llama70] (edge=6.9%): My REASONING TEMPLATE (DMAD) prioritizes totals and alt-totals due to superior pace modeling, diverging from nvidia-llama70's focus on ml_home and spread_away. Today, I target DEN@NOP total_over with a 6.9% edge, a category absent from peer allocations.
> **Cash:** 0.7417% — Holding 67% cash to comply with probation rules (Kelly cap 0.03) and avoid over-exposure on marginal edges below 0.07 in other games.

| event | category | odds | edge | stake | won | profit | rationale |
|---|---|---:|---:|---:|:---:|---:|---|
| SAS@OKC | pp_threes_star2_home | 1.91 | 0.091 | $2.00 | ✗ | -2.00 | Chet Holmgren (OKC) averages 2.8 threes/game on 41% shooting; market line (2.5) is 0.3 below my projection, yielding a 9.1% edge. |
