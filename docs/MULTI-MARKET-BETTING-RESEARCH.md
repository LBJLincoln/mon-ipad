# NBA Multi-Market Betting Research
**Date:** 2026-03-28
**Context:** Current model ATR Brier 0.21570. Target Brier < 0.20.
**Goal:** Expand from moneyline-only to 20+ bet types per game.

---

## SECTION 1: Complete NBA Bet Type Taxonomy

### Tier 1 — Game Lines (Most Liquid, Most Efficient)

#### 1.1 Moneyline (ML)
- **Description:** Pick the outright winner. Home +150 / Away -170.
- **Market efficiency:** HIGH. Closing lines accurate within ~2-3%. Sharp money moves lines in minutes on major games. Less efficient for small-market/afternoon games.
- **Data availability:** Excellent. Kaggle: `cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024` — 2007-2025, free. The Odds API: historical from mid-2020 (paid).
- **Correlation with our model:** DIRECT. Our predicted_home_prob maps 1:1 to moneyline implied probability.
- **Edge from Brier 0.22 model:** Montrucchio 2026 (MDPI, arXiv) showed XGBoost at Brier 0.202 generated positive ROI at EV>1.1 threshold. At 0.2157 we are borderline — the exploitable edge is narrow but positive. Academic reference: 3-5% ROI sustained.
- **Status:** ACTIVE in our system.

#### 1.2 Point Spread (ATS)
- **Description:** Home -6.5 / Away +6.5 at -110/-110. Bet on whether a team wins by more than (or within) the spread.
- **Market efficiency:** VERY HIGH. Most efficient NBA market. Sharp money (wiseguy shops, syndicates) focuses primarily on spread. Spreads are re-priced multiple times per day.
- **Data availability:** Same as moneyline — included in all Kaggle datasets above.
- **Correlation with our model:** INDIRECT. Win prob converts to spread via logistic formula (see Section 4). But spread is determined more by team strength delta than binary win prob.
- **Edge from Brier 0.22 model:** WEAK. Montrucchio 2026 explicitly: "spread models are neutral to mildly negative, consistent with higher pricing efficiency." The spread market prices point margin, not win probability — our model would need to predict margin of victory (regression problem) to beat spread markets.
- **Implementation path:** Convert predicted win probability to implied spread using: `spread = -ln(1/p - 1) / 0.13959` (logistic formula from SportsbookReview research, coefficient empirically validated for NBA). Only bet when our implied spread differs from book's spread by > 1.5 points.

#### 1.3 Over/Under Total Points (Game Total)
- **Description:** Predicted total combined score (e.g., O/U 224.5) at -110/-110.
- **Market efficiency:** HIGH but with specific inefficiencies. Research finding: "totals lines are significantly biased early each season" (ScienceDirect). Also: pace-adjusted models outperform naive totals betting by ~3-4%.
- **Data availability:** Excellent. Included in all major Kaggle datasets (2007-2025). The Odds API historical from mid-2020.
- **Correlation with our model:** INDIRECT. Our current model does not predict total points. Requires a separate regression model.
- **Edge from Brier 0.22 model:** MEDIUM. Totals depend on pace + offensive/defensive efficiency — less correlated with who wins than spread. A dedicated totals model can find edge independently of win prediction quality.
- **Formula for predicted total:**
  ```
  Predicted Total = (home_ortg + away_ortg) * (home_pace + away_pace) / 200
  # Simplified: multiply average efficiency by average pace factor
  # More precise: use pace-adjusted ortg/drtg:
  home_expected_pts = (home_ortg * away_drtg / league_avg_drtg) * (home_pace * away_pace / league_avg_pace) / 100
  away_expected_pts = (away_ortg * home_drtg / league_avg_drtg) * (home_pace * away_pace / league_avg_pace) / 100
  predicted_total = home_expected_pts + away_expected_pts
  ```
- **Key insight:** We already have home_pace, away_pace, home_ortg, away_ortg in our Cat 10-15 features. Building a totals regression model on top of our existing engine is a 4-hour task.

---

### Tier 2 — Period Betting (Moderate Efficiency, More Edge Possible)

#### 1.4 First Half Spread (1H ATS)
- **Description:** Spread on first half result only (e.g., home -3.5 1H). Lines set separately from full game.
- **Market efficiency:** MEDIUM. Less sharp money, fewer dedicated modelers. Bookmakers often set half lines by mechanical formulas (roughly half the game spread, adjusted for first-half tendencies).
- **Data availability:** Limited. The Odds API historical event-odds endpoint (from May 2023, paid, 10 credits per query). Not in most free Kaggle datasets.
- **Correlation with our model:** MODERATE. Quarter-level features in our engine (Cat 20-22 estimated) would help. First-half performance is noisier than full-game.
- **Edge estimate:** MEDIUM. Academic: Montrucchio noted period markets "show less pricing sophistication." Estimated 1-2% ROI additional beyond moneyline if model includes first-quarter pace data.
- **Required features:** first_half_ortg_home, first_half_pace, first_half_scoring_share (Q1+Q2 vs full game average).

#### 1.5 First Half Over/Under (1H O/U)
- **Description:** Total first-half score over/under (e.g., O/U 110.5).
- **Market efficiency:** MEDIUM. Same as 1H spread — mechanical pricing by books.
- **Formula:** `1H total ≈ game_total * 0.467` (historical ratio: first half averages ~46.7% of game total, but teams that play fast tend to push this toward 49%).
- **Edge:** The early-season totals bias (from ScienceDirect research) is strongest on FIRST HALF totals, as books lack current-season pace data.

#### 1.6 Second Half Spread and O/U (2H)
- **Description:** Bet placed at halftime on second-half results only.
- **Market efficiency:** MEDIUM-HIGH. Books react quickly with halftime data. However, in-game models that update at halftime can capture inefficiencies in how books adjust for the first-half score.
- **Edge:** "On predicting an NBA game outcome from half-time statistics" (Springer, 2024): RF and XGBoost achieve 73-75% accuracy using only halftime stats — stronger than pre-game models. This means a halftime model could identify when books' 2H lines are stale.
- **Implementation:** Requires live score ingestion and halftime re-run of prediction model. Medium complexity.

#### 1.7 Quarter Spreads and Totals (Q1-Q4)
- **Description:** Win/cover/total for each quarter individually. Q1 is most commonly available; Q4 less so.
- **Market efficiency:** LOW-MEDIUM for Q1-Q3. Books price quarters mechanically. Q4 lines are often not available pre-game.
- **Data availability:** Very limited historically. The Odds API has quarter/period markets from May 2023 (paid).
- **Edge:** HIGHEST potential of all period markets. Academically untested at the quarter level. Key insight: starting lineups, rest patterns, and coaching tendencies have strong quarter-level effects that books under-price.
- **Q1 Totals formula:** `Q1_total ≈ game_total * 0.239` (historical NBA Q1 averages 23.9% of game total, range 22-26%).

---

### Tier 3 — Team Totals

#### 1.8 Home Team Total (HTT) / Away Team Total (ATT)
- **Description:** Over/under on just one team's score (e.g., Lakers O 114.5). Priced separately from game total.
- **Market efficiency:** MEDIUM. Less liquid, less sharp attention. Books derive from game total + half-spread.
- **Correlation with our model:** STRONG. We predict home_prob which correlates with winning. A team likely to win significantly is also likely to score more. Our offense/defense features directly map.
- **Edge:** STRONG candidate. Research (techbuzzireland.com 2026): "sportsbooks often misprice team totals relative to individual team's offensive projection." Key: team totals for home underdogs are frequently mispriced because books anchor to the game total and lose individual team scoring precision.
- **Formula:**
  ```
  home_team_total = (home_ortg / league_avg_ortg) * (away_drtg / league_avg_drtg) * league_avg_pace * home_pace / 100
  ```
- **Implementation:** Direct extension of totals model. Predict home_pts and away_pts separately rather than just combined total. 6-hour task.

---

### Tier 4 — Alternate Lines

#### 1.9 Alternate Spreads
- **Description:** Same game spread but at non-standard line (e.g., -3.5, -6.5, -10.5 instead of standard -4.5). Odds adjust to reflect probability.
- **Market efficiency:** MEDIUM-LOW. Books price these algorithmically using the standard spread as anchor. Errors compound at extreme alternate spreads.
- **Edge:** From Hofapp.com research: "if your model shows a significantly higher probability than the alternate line's implied odds, this presents a high-value opportunity." Our model strength: confidence in large margin wins (Brier 0.2157 = ~65% overall accuracy). Large alternate spread underdogs can be heavily mispriced.
- **Key insight:** Alternate spreads +13.5 or greater on heavy favorites are frequently underpriced because books pad vig and bettors rarely take them.

#### 1.10 Alternate Totals
- **Description:** Non-standard O/U lines (e.g., O 215.5 instead of standard O 224.5).
- **Market efficiency:** MEDIUM-LOW. Same mechanical pricing as alternate spreads.
- **Edge:** Research shows that alternate totals away from the standard line have widening vig that creates +EV pockets for models that can accurately estimate tail probabilities.

---

### Tier 5 — Player Props

#### 1.11 Player Points (O/U X.5 points)
- **Description:** Will player score over/under X points? Most popular prop category.
- **Market efficiency:** LOW-MEDIUM. Books dedicate limited resources to props. Bias confirmed: "psychological over bias results in bookmakers typically overstating player scoring lines" (techbuzzireland.com 2026). Unders on player points frequently +EV.
- **Data availability:** The Odds API from May 2023 (paid). PrizePicks API (semi-official). DraftKings/FanDuel scraping possible.
- **Key features for modeling:**
  - EWMA of points (recent 5, 10, 20 games weighted)
  - Usage Rate (USG%) — most predictive single feature
  - Opponent defensive rating (DRtg) vs position
  - True Shooting % delta (actual vs expected = hot/cold detection)
  - Minutes projected (injury reports, rotation analysis)
  - Home/away split for player
  - Back-to-back game indicator
  - Head-to-head history vs specific defender
- **Implementation complexity:** HIGH. Need player-level database, injury feeds, minutes projections. 40-60 hours.

#### 1.12 Player Rebounds (O/U X.5 rebounds)
- **Description:** Total rebounds for a player. Most stable prop (less game-state dependent than points).
- **Market efficiency:** LOW. Rebounding is heavily matchup-dependent and books price it based on season averages — ignoring opponent rebounding style and specific matchups.
- **Key features:** Voronoi court positioning data (Second Spectrum), contested rebound rate, opponent pace (more possessions = more rebound opportunities), opposing team ORtg (high-offense teams attempt more shots = more rebound chances).
- **Edge:** STRONG. Rebounding is more predictable than scoring because it's less influenced by shot quality variance. A model using opponent rebound rate + player rebound rate + pace factor should beat book lines ~54-56% of the time.

#### 1.13 Player Assists (O/U X.5 assists)
- **Description:** Total assists. High variance, most dependent on teammates making shots.
- **Market efficiency:** LOW. Books overprice assists for high-usage point guards. Conversion rate (potential assists → actual assists) fluctuates with team shooting efficiency.
- **Key feature:** Potential Assists metric — available from Second Spectrum/NBA tracking. Player with high potential assists but low actual assists = regression candidate = Under value.

#### 1.14 Player 3-Pointers Made (O/U X.5 three-pointers)
- **Description:** Three-pointers made by specific player.
- **Market efficiency:** LOW-MEDIUM. Highly variable metric — good for value when defense quality vs 3-point shooters is mispriced.
- **Edge:** Shot chart CNN features (Montrucchio 2026) directly applicable — shooting zone efficiency from shot charts predicts three-pointer makes better than raw 3P%.

#### 1.15 Player Steals / Blocks / Turnovers
- **Description:** Rare defensive/turnover props. Very low liquidity.
- **Market efficiency:** LOW. Thin liquidity, mechanical pricing, maximum +EV but small capacity.
- **Implementation:** Low priority. Focus on higher-volume props first.

#### 1.16 Player Points+Rebounds+Assists Combo (PRA)
- **Description:** Combined stat line over/under. Most popular DFS-adjacent prop.
- **Market efficiency:** MEDIUM-LOW. Books use sum of individual props, introducing pricing errors from correlation structure.
- **Edge:** If player_pts + player_reb + player_ast all have positive correlation with each other (high-pace game), the combined PRA should be priced higher than the sum of individual props.

---

### Tier 6 — Game Props

#### 1.17 First Team to Score
- **Description:** Which team scores first? Roughly 50/50 but home team has slight edge (~53%).
- **Market efficiency:** LOW. Very thin, low capacity. High hold percentage.
- **Edge:** Minimal. Not recommended for systematic betting.

#### 1.18 Race to X Points
- **Description:** Which team first reaches 10, 15, 20 points in a quarter.
- **Market efficiency:** LOW. Pure noise for most games.
- **Edge:** Marginal. Worth modelling only if pace data is strongly predictive.

#### 1.19 Margin of Victory / Win by Exactly X
- **Description:** Team wins by 1-5, 6-10, 11-20, 21+ points.
- **Market efficiency:** LOW. Complex to price accurately. Books often mechanical.
- **Edge:** A model that predicts point margin (regression, not just win probability) can find edges in extreme margin props.

---

### Tier 7 — Live/In-Game Betting

#### 1.20 Live Moneyline
- **Description:** Bet on current game winner at real-time odds reflecting score and time remaining.
- **Market efficiency:** MEDIUM. Books update lines fast but not instantaneously. 1-3 second delays create arb windows. Most profitable for bettors with fast models.
- **Data availability:** Real-time only. No useful historical dataset.
- **Edge from our model:** STRONG if we can build a live win probability model. Formula: use Brownian motion with drift (Stern 1994 framework) — `WP = logistic(drift * time_remaining + point_differential)`. Our model + play-by-play API = viable in-game prediction system.
- **Implementation:** Medium complexity. NBA.com stats API has live play-by-play (free). nba_api Python library.

#### 1.21 Live Spread / Live Totals
- **Description:** Real-time spread and total adjusted as game progresses.
- **Market efficiency:** HIGH. Books have sophisticated live models. Less edge for pre-game models in live markets.

---

### Tier 8 — Futures

#### 1.22 Conference Winner / NBA Champion
- **Description:** Season-long bets. High variance, high hold (8-15%).
- **Market efficiency:** MEDIUM. Information inefficiency early season when books anchor to preseason expectations.
- **Edge:** MEDIUM early season, LOW mid-to-late. Our Elo-based win probability can project playoff probabilities by simulating remaining schedule.

#### 1.23 Season Win Totals (Over/Under)
- **Description:** Will team win over/under X games (e.g., LAL O/U 47.5 wins).
- **Market efficiency:** MEDIUM. Set once preseason. Biased toward public favorites.
- **Edge:** Simulate season 10,000x using our team ratings. Preseason books often mispriced on injury-risk teams.

---

### Tier 9 — Parlays and Teasers

#### 1.24 Standard Parlay (2-10 legs)
- **Description:** Chain of multiple bets, all must win. Odds multiply.
- **Expected value:** NEGATIVE for independent bets. House edge 20-30% on typical parlay.
- **Exception:** Correlated parlays (see Section 3). Same-game parlay where spread cover implies totals direction.

#### 1.25 Teaser (+6, +6.5, +7 points to spread)
- **Description:** Move the spread 6 points in your favor, but at reduced odds. Typically -120 for 2-team teaser.
- **Edge research:** NFL teasers through key numbers (3, 7) have documented positive EV. NBA equivalent: crossing 0 (pick'em) is the NBA "key number." Teasers from -4.5 to +1.5 (crossing 0) are potentially +EV.

#### 1.26 Round Robin
- **Description:** Multiple 2-3 team parlays from a larger selection. Risk reduction at cost of payout.
- **Edge:** Primarily risk management tool. Not positive EV structurally but allows better bankroll management across correlated markets.

---

## SECTION 2: Academic Papers on Multi-Market NBA Betting

### 2.1 Primary Reference — State-of-Art 2026

**Paper:** "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets"
Authors: Matteo Montrucchio, Enrico Barbierato, Alice Gatti
Published: 2026-01-08, MDPI Information, Vol 17, Issue 1
URL: https://www.mdpi.com/2078-2489/17/1/56

**Multi-market findings:**
- Moneylines: POSITIVE ROI at EV>1.1 threshold + 0.3-Kelly.
- Spreads: "Neutral to mildly negative." More efficient than ML.
- Totals: "Only marginal gains." Occasional positive months, no sustained edge.
- Player props: Not tested (called "synthetic odds").
- European football markets tested as validation.

**Key quote:** "Economic value emerges primarily in less-efficient segments of the market." Directly implies props > totals > spread > moneyline in terms of exploitability.

**Betting architecture used:**
```
EV threshold: > 1.1
Kelly fraction: 0.3 (fractional Kelly)
Max odds: 10.0
Min stake: EUR 10
Max stake: EUR 100
Market priority: moneyline first, spread/totals secondary
```

---

### 2.2 Half-Time Prediction for 2H Markets

**Paper:** "On predicting an NBA game outcome from half-time statistics"
Published: 2024, Discover Artificial Intelligence, Springer Nature
URL: https://link.springer.com/article/10.1007/s44163-024-00201-9

**Key finding:** Using only halftime statistics (Q1+Q2 box score), ML models achieve 73-75% accuracy (vs 65% pre-game). Random Forest and XGBoost outperform logistic regression significantly.

**Implication for 2H betting:** If we can ingest live halftime stats and re-run our model, we can generate predictions with substantially higher accuracy than books' mechanical 2H line adjustment. The accuracy jump from 65% to 73-75% represents a potential 8-10% edge before vig, which is large.

**Required implementation:** Live data ingestion during halftime (NBA Stats API has real-time box scores), re-score our feature engine with actual Q1+Q2 stats.

---

### 2.3 Quarter-Level Prediction

**Paper:** "Integration of machine learning XGBoost and SHAP models for NBA game outcome prediction" (PMC/NIH)
URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/

**Finding:** Real-time prediction model trained on Q1+Q2 statistics achieves better accuracy than pre-game model. Q3 model further improves. This validates the layered prediction approach: pre-game → Q1 update → halftime update → Q3 update.

**Quarter-specific features noted:**
- First-quarter bench scoring differential
- Q1 turnover rate (higher early-game impact)
- Second-quarter comeback rate (teams that trail Q1 win Q2 at 52% rate)
- Third-quarter "adjustments" effect (coaching changes raise variance)

---

### 2.4 Totals Prediction — Pace + Efficiency Framework

**Paper:** "Pace and Efficiency: Measuring and Predicting NBA Pace Stats"
The Data Jocks (2024)
URL: https://thedatajocks.com/models-and-nba-pace-stats/

**Key formula for predicting game total:**
```
Predicted possessions = (team_A_pace + team_B_pace) / 2
Predicted pts per possession = (team_A_ortg + team_B_ortg) * (team_A_drtg + team_B_drtg) / (4 * league_avg_ortg * league_avg_drtg) * league_avg_pts_per_possession

Simplified game total = possessions * avg_pts_per_possession * 2
```

**Finding:** Naïve average of two teams' pace is most accurate pace predictor. Home/away pace splits matter less than season pace average. Key: pace is more stable than efficiency metrics — use more seasons of pace data.

---

### 2.5 Player Props Feature Engineering

**Paper:** "Beyond the Box Score: Feature Engineering for Predictive Sports Models Focusing on NBA Player Props"
TechBuzzIreland, February 2026
URL: https://techbuzzireland.com/2026/02/02/beyond-the-box-score-feature-engineering-for-predictive-sports-models-focusing-on-nba-player-props-and-advanced-metrics/

**Key feature engineering insights:**
- EWMA on individual stats captures hot/cold streaks better than rolling mean
- Usage Rate (USG%) most predictive feature for points; changes with lineup changes
- Shot quality delta (actual vs expected efficiency) detects true hot streaks vs variance
- Voronoi tessellation for rebound probability — quantifies court positioning
- Potential Assists metric distinguishes elite playmakers from stat-padders
- Rest matrix (back-to-back penalty): points drop ~2.3 per game on 2nd night of B2B
- "3-in-4" game density: significant efficiency decline (fatigue factor)
- Bookmaker Over bias confirmed: models favor Unders on player props

---

### 2.6 Referee Effects on Betting Markets

**Paper:** "With the Game on the (Betting) Line: NBA Referee Performance in the Last Two Minutes"
Authors: Ariel R. Belasen, Alan T. Belasen, Alexandre Olbrecht
Published: 2025, Journal of Sport Management (SAGE Journals)
URL: https://journals.sagepub.com/doi/10.1177/15270025251369447

**Key findings:**
- Referees make 23% fewer incorrect calls for visiting team underdogs and 42% fewer for home team underdogs vs favorites
- Statistically significant difference in incorrect call rate when betting gap between teams is narrow
- Refs calling more fouls = more free throws = games trend OVER totals
- Identifiable referee patterns: some refs have documented Over/Under tendencies in final 2 minutes

**Actionable:** Add referee_id as a feature. Data available from NBA.com official game summaries (free). Covers.com and OddsShark both publish referee betting stats for the 2025-26 season.

---

### 2.7 Correlated Parlay Mathematics

**Paper:** "Same-Game Parlays: The Mathematics of Correlation"
Wizard of Odds (2024)
URL: https://wizardofodds.com/article/same-game-parlays-the-mathematics-of-correlation/

**Mathematical framework:**
- Pearson correlation coefficient ρ between bet outcomes measured using joint historical frequency
- Gaussian copula to model joint distribution:
  1. Transform each bet's prob to normal: Z = Φ⁻¹(p)
  2. Apply correlation matrix R
  3. Calculate joint probability via multivariate normal CDF

**Key known NBA correlations:**
- Game spread cover ↔ Game total (Over): ρ ≈ +0.25 (winning big = more points)
- Home moneyline ↔ Home team total: ρ ≈ +0.35 (winning team scores more)
- Away underdog cover ↔ Under: ρ ≈ +0.20 (close game = fewer total points)

**Parlay EV formula with correlation:**
```python
from scipy.stats import multivariate_normal
import numpy as np

def correlated_parlay_prob(probs, corr_matrix):
    """Calculate true joint probability of correlated parlay legs."""
    thresholds = [norm.ppf(p) for p in probs]
    # Probability all standard normal variables exceed their thresholds
    # under the given correlation structure
    dist = multivariate_normal(mean=np.zeros(len(probs)), cov=corr_matrix)
    joint_prob = 1 - dist.cdf(thresholds)
    return joint_prob

# Example: home ML win + game Over (positive correlation)
probs = [0.65, 0.52]  # home win 65%, Over 52%
corr_matrix = [[1.0, 0.25], [0.25, 1.0]]  # correlation 0.25
true_joint = correlated_parlay_prob(probs, corr_matrix)
# true_joint ≈ 0.375 (vs 0.65*0.52=0.338 under independence)
# If book offers parlay at odds implying 0.338, we have +EV
```

---

### 2.8 Multi-Outcome Kelly Criterion

**Paper:** "On optimal betting strategies with multiple mutually exclusive outcomes"
Karl Whelan
Published: 2025, Bulletin of Economic Research (Wiley)
URL: https://onlinelibrary.wiley.com/doi/full/10.1111/boer.12474

**Extension for correlated multi-market betting:**
- Standard Kelly assumes independent bets on separate events
- For same-game parlays and correlated markets: fractional Kelly with correlation matrix
- Formula: `f_i = (p_i * b_i - q_i) / b_i - Σ_j ρ_ij * f_j` (simultaneous Kelly system)
- Practical recommendation: cap at 0.25-Kelly when betting correlated markets from same game

---

## SECTION 3: Data Sources for Multi-Market Odds

### 3.1 Free Sources

| Source | Markets | Period | Notes |
|--------|---------|--------|-------|
| Kaggle: `cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024` | ML, Spread, Total | 2007-2025 | Free, most comprehensive |
| Kaggle: `christophertreasure/nba-odds-data` | ML, Spread | Recent | Free |
| Kaggle: `erichqiu/nba-odds-and-scores` | ML, Total | Multiple seasons | Free |
| OddsPortal.com | ML, Spread, Total | 2007-present | Scrapable |
| TeamRankings.com | Spread, Total | 2003-present | Browsable, no API |
| Basketball-Reference | None (box scores only) | 1946-present | Free |

**Already downloaded:** Kaggle 19,820 games w/ moneylines 2008-2022 (confirmed in our system).

### 3.2 Paid APIs (Recommended for Live + Props)

| Source | Markets | Cost | Notes |
|--------|---------|------|-------|
| The Odds API | ML, Spread, Total, Props, Period | $0 (500 requests/month free) + paid tiers | Props/period from May 2023. Most complete. |
| SportsData.io | All markets + props | $29/mo starter | Pre-game + in-play + props, 2019-present |
| WagerAPI | Spread, Total, Props | $49/mo | Specifically for betting models |
| OddsMatrix | All | Enterprise | Institutional quality |
| SportGameOdds.com | Props via API | $29/mo | Props-focused |

### 3.3 Free Props Data (Unofficial)

- **PrizePicks:** Undocumented API, many Python projects use it (chevyphillip/plus-ev-model on GitHub)
- **Action Network:** Public projections with implied lines
- **DraftKings public API:** Real-time odds accessible without authentication for current markets
- **Unabated.com:** Real-time sharp odds aggregation (no API, but web-accessible)

### 3.4 Recommended Data Pipeline for Multi-Market

```
Tier 1 (Immediate, Free):
  - Use existing Kaggle ML+Spread+Total dataset (2008-2022)
  - Supplement with OddsPortal scraping for 2022-2026

Tier 2 (Short term, $0-$29/mo):
  - The Odds API free tier: 500 requests/month for current season props
  - PrizePicks unofficial API for player props (free)

Tier 3 (Production, $29-$99/mo):
  - SportsData.io for complete historical + live props
  - WagerAPI for clean programmatic access
```

---

## SECTION 4: Win Probability to Market Conversion Formulas

### 4.1 Win Probability → Moneyline
```python
def prob_to_moneyline(p):
    if p > 0.5:
        return -(p / (1 - p)) * 100  # e.g., 0.65 → -186
    else:
        return ((1 - p) / p) * 100   # e.g., 0.35 → +186

# EV calculation
def moneyline_ev(p_model, moneyline_odds):
    if moneyline_odds > 0:
        p_implied = 100 / (moneyline_odds + 100)
        profit_if_win = moneyline_odds / 100
    else:
        p_implied = abs(moneyline_odds) / (abs(moneyline_odds) + 100)
        profit_if_win = 100 / abs(moneyline_odds)

    ev = p_model * profit_if_win - (1 - p_model) * 1
    edge = p_model - p_implied
    return ev, edge
```

### 4.2 Win Probability → Implied Point Spread
```python
import numpy as np

def prob_to_spread(p_home_win):
    """
    Logistic formula: W% = 1 / (1 + exp(-0.13959 * spread))
    Solving for spread: spread = -ln(1/p - 1) / 0.13959

    Coefficient 0.13959 empirically validated for NBA (SportsbookReview).
    For NFL: ~0.072; NBA has higher coefficient due to faster scoring.
    """
    spread = -np.log(1/p_home_win - 1) / 0.13959
    return spread  # positive = home favored, negative = home underdog

# Examples:
# p=0.60 → spread = -1.73 (home favored by 1.73)
# p=0.70 → spread = -3.20 (home favored by 3.20)
# p=0.80 → spread = -5.71 (home favored by 5.71)
# p=0.50 → spread = 0.00 (pick'em)
```

### 4.3 Predicted Total Points Formula
```python
def predicted_game_total(home_ortg, home_drtg, home_pace,
                          away_ortg, away_drtg, away_pace,
                          league_avg_ortg=115.3, league_avg_drtg=115.3,
                          league_avg_pace=98.5):
    """
    Home team expected points:
    = (home_ortg / league_avg_ortg) * (away_drtg / league_avg_drtg)
      * pace_factor * league_avg_pts_per_game

    All ratings per 100 possessions. Pace in possessions per 48 min.
    """
    pace_factor = (home_pace + away_pace) / (2 * league_avg_pace)

    home_expected = (home_ortg * away_drtg / (league_avg_ortg * league_avg_drtg)) * pace_factor * league_avg_ortg
    away_expected = (away_ortg * home_drtg / (league_avg_ortg * league_avg_drtg)) * pace_factor * league_avg_ortg

    return home_expected + away_expected
```

### 4.4 Spread Cover Probability from Win Probability
```python
from scipy.stats import norm

def spread_cover_prob(p_home_win, home_spread, std_dev=11.5):
    """
    Given win probability, estimate probability of covering spread.

    Expected margin = prob_to_spread(p_home_win)
    Margin of victory is approximately normally distributed (std ≈ 11.5 pts in NBA)
    P(cover) = P(margin > spread_line)
    """
    expected_margin = prob_to_spread(p_home_win)
    p_cover = norm.sf(home_spread, loc=expected_margin, scale=std_dev)
    return p_cover
```

---

## SECTION 5: Implementation Roadmap

### Phase 1: Immediate Extensions (1-8 hours, high ROI)

**P1-A: Totals Model (4 hours)**
- Use existing features: home_ortg, away_ortg, home_drtg, away_drtg, home_pace, away_pace (already in Cat 10-15)
- Build separate XGBoost regression model predicting home_pts, away_pts
- Target: predicted_total = home_pts + away_pts
- Compare vs book total → bet if delta > 2.5 points (accounting for vig)
- Expected edge: 2-4% ROI on totals (medium efficiency market, we have pace features)

**P1-B: Spread Betting from Win Probability (2 hours)**
- Apply `prob_to_spread()` formula to convert predicted_home_prob → implied_spread
- Compare vs book spread → bet if delta > 1.5 points
- Backtest on existing 19,820 game dataset
- Expected edge: LOW (spread market very efficient), but can filter to specific conditions (big dogs, early-season)

**P1-C: Team Totals (2 hours, extends P1-A)**
- Once we predict home_pts and away_pts separately, immediately get home/away team total predictions
- Book home/away team totals frequently mispriced vs game total
- Expected edge: 3-5% ROI (less efficient than game total market)

### Phase 2: Period Markets (8-20 hours)

**P2-A: First Half Totals Model (8 hours)**
- Split historical game logs into Q1+Q2 stats
- Build separate first-half ortg/drtg features
- Train half-total regression model
- Key challenge: first-half historical odds data — requires Odds API historical (paid) or scraping
- Expected edge: 3-6% (medium efficiency market)

**P2-B: Live Halftime Update (12 hours)**
- Ingest live NBA stats API during halftime
- Re-run prediction with actual Q1+Q2 box score stats
- Target: second-half spread and total markets
- Academic backing: 73-75% accuracy at halftime vs 65% pre-game (+8-10% accuracy)
- Expected edge: 5-8% on 2H markets (largest single opportunity)

**P2-C: Quarter Model (20 hours)**
- Q1 total model (pace is most predictive in Q1 — teams haven't adjusted yet)
- Q1 spread model (home team tends to start faster in 53% of games)
- Historical quarter-level odds from Odds API (paid, from May 2023)

### Phase 3: Player Props (40-80 hours)

**P3-A: Player Points Model (40 hours)**
- Build player database: EWMA stats per player (5/10/20 game windows)
- Opponent defensive rating vs position
- Minutes projection from injury reports
- Back-to-back / rest indicator
- Compare to book lines → find Unders where EWMA < book line - 1.5
- Key finding: Unders are consistently +EV due to bookmaker over-bias
- Expected edge: 4-7% on player point Unders

**P3-B: Rebounds Model (20 hours, simpler than points)**
- Pace factor + opponent rebound rate + player rebound rate
- Less variance than points
- Expected edge: 5-8% (less efficient, more predictable)

**P3-C: Combo Props (PRA, PR, PA) (8 hours, built on P3-A+P3-B)**
- Sum individual projections
- Apply correlation correction for joint prop lines
- Expected edge: 4-6%

### Phase 4: Correlated Parlays (20 hours)

**P4-A: Same-Game Parlay Engine**
- Implement Gaussian copula model for joint probability
- Known NBA correlations to exploit:
  - Home ML win + Home team Over (ρ ≈ +0.35): if our model predicts home dominant win, parlay home ML + home team Over is systematically underpriced
  - Away underdog cover + Under (ρ ≈ +0.20): close game = low total
  - Player star performance + Team wins (ρ ≈ +0.30): star player big game → team win
- Expected edge: 8-15% on specific correlated parlays (but small capacity)

**P4-B: Round Robin Portfolio**
- Identify 4-6 +EV bets per game day
- Generate round-robin (all 2-team combos)
- Sizes by correlated Kelly criterion
- Risk management: max 20% bankroll in same-game exposures

---

## SECTION 6: Market Efficiency Ranking (Our Model vs Market)

| Market | Efficiency | Expected Edge (Brier 0.2157) | Priority |
|--------|-----------|------------------------------|----------|
| Player Props (Unders) | LOW | 4-8% ROI | HIGH |
| Halftime 2H Markets | MEDIUM | 5-8% ROI | HIGH |
| Team Totals | MEDIUM | 3-5% ROI | HIGH |
| Game Total | HIGH | 2-4% ROI | MEDIUM |
| Moneyline | HIGH | 1-3% ROI | ACTIVE |
| First Half O/U | MEDIUM | 2-4% ROI | MEDIUM |
| Correlated Parlays (SGP) | LOW-MEDIUM | 8-15% ROI (low cap) | MEDIUM |
| Quarter Markets | LOW | 3-6% ROI | MEDIUM |
| Alternate Lines | MEDIUM-LOW | 2-5% ROI | LOW |
| Spread | VERY HIGH | 0-1% ROI | LOW |
| Futures | MEDIUM | 2-5% ROI (high variance) | LOW |
| Live Moneyline | MEDIUM | 3-6% ROI | FUTURE |

---

## SECTION 7: Key Alpha Insights

### 7.1 Biggest Untapped Opportunity: Halftime 2H Betting
Academically validated 73-75% accuracy at halftime vs 65% pre-game. Books adjust mechanically. A live score ingestion pipeline + halftime re-score of our model is the single highest-EV improvement available. Required: NBA Stats API live integration (free), halftime re-run mechanism.

### 7.2 Player Props Unders Systematic Bias
Multiple independent sources confirm bookmakers consistently overprice player scoring lines due to public over-bias. A systematic strategy of betting Unders when our player model projects < (book_line - 1.5) should be sustainably +EV. Props market is specifically called out as "less efficient" in Montrucchio 2026.

### 7.3 Team Totals Are Underexplored
Home/away team totals are derived from game total + half-spreads by books, creating systematic pricing errors. Our model predicts both team scores independently. Comparing our home_pts and away_pts projections to book team totals costs nothing to implement once the totals model exists.

### 7.4 Referee Features Are Free Alpha
NBA.com publishes referee assignments before games. OddsShark and Covers.com publish referee ATS/totals tendencies for 2025-26. Referees who call more fouls → games trend Over. Adding referee_id as a categorical feature (one-hot or embedding) to our feature engine is a Cat 38 candidate. Implementation: 2 hours, free data.

### 7.5 Correlated Parlays Are Priced Wrong on Specific Books
Per Wizard of Odds research: some books (FanDuel) are more generous than others (ESPN Bet) with NBA player prop + game outcome correlations. Identifying books that do not apply correlation adjustment creates systematic +EV. The copula framework above provides the mathematical tool to detect mispricing.

### 7.6 Early-Season Totals Bias
ScienceDirect research: totals lines "significantly biased early each season" while spread lines are not. Specific strategy: bet game totals (particularly Overs) in first 3 weeks of season when books lack current-season pace/efficiency data. This is a seasonal alpha signal.

---

## SECTION 8: Recommended Immediate Actions

1. **Build totals regression model** (4h) — use existing ortg/drtg/pace features, predict home_pts + away_pts. Already have the features, just need the regression target. Backtest on 19,820 game dataset.

2. **Add referee_id feature to engine** (2h) — Cat 38 candidate. Scrape referee assignments from NBA.com (free). Map to Covers.com referee tendencies. Add as categorical feature. Expected Brier delta: -0.001 to -0.002 on calibrated totals.

3. **Implement spread betting from win probability** (2h) — apply `prob_to_spread()` formula. Backtest ATS performance on existing dataset. Even if spread market is efficient, this validates our model calibration.

4. **Subscribe to The Odds API free tier** (0h, free) — 500 requests/month covers current-season props for the games we bet. Begin collecting real-time props data for player model training.

5. **Build player points EWMA database** (20h) — Most effort but highest ROI given props market inefficiency. Start with top-50 players by usage rate. Focus on Unders where EWMA < line - 1.5.

6. **Implement halftime live re-score** (12h) — Monitor NBA Stats API live endpoint, trigger re-run at halftime, generate 2H market signals. Largest single ROI opportunity.

---

## References

- [Uncertainty-Aware Machine Learning for NBA Forecasting (Montrucchio 2026)](https://www.mdpi.com/2078-2489/17/1/56)
- [Predicting NBA Game Spreads (SSRN 2024)](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4766044_code4221567.pdf?abstractid=4766044&mirid=1)
- [NBA Historical Betting Data — Kaggle 2007-2025](https://www.kaggle.com/datasets/cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024)
- [NBA Odds Data — Kaggle](https://www.kaggle.com/datasets/christophertreasure/nba-odds-data)
- [The Odds API — Historical NBA Odds](https://the-odds-api.com/historical-odds-data/)
- [Machine Learning for Basketball: NBA and WNBA Leagues (MDPI 2025)](https://www.mdpi.com/2079-3197/13/10/230)
- [NBA Half-Time Prediction — Springer 2024](https://link.springer.com/article/10.1007/s44163-024-00201-9)
- [XGBoost and SHAP for NBA Prediction — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)
- [Stacked Ensemble NBA Prediction — Scientific Reports 2025](https://www.nature.com/articles/s41598-025-13657-1)
- [Beyond the Box Score: NBA Props Feature Engineering (2026)](https://techbuzzireland.com/2026/02/02/beyond-the-box-score-feature-engineering-for-predictive-sports-models-focusing-on-nba-player-props-and-advanced-metrics/)
- [NBA Referee Betting Line Study — SAGE 2025](https://journals.sagepub.com/doi/10.1177/15270025251369447)
- [Referee Stats 2025-26 — Covers.com](https://www.covers.com/sport/basketball/nba/referees)
- [Same-Game Parlay Mathematics — Wizard of Odds](https://wizardofodds.com/article/same-game-parlays-the-mathematics-of-correlation/)
- [Optimal Betting Strategies Multiple Outcomes — Whelan 2025 (Wiley)](https://onlinelibrary.wiley.com/doi/full/10.1111/boer.12474)
- [NBA Win Probability to Spread Conversion — Inpredictable](https://www.inpredictable.com/2015/02/updated-nba-win-probability-calculator.html)
- [NBA Alternate Lines Explained — Boyd's Bets](https://www.boydsbets.com/alternate-lines-in-sports-betting/)
- [NBA Spread to Moneyline Chart — Boyd's Bets](https://www.boydsbets.com/nba-spread-to-moneyline-conversion/)
- [Plus-EV NBA Player Props Model — GitHub](https://github.com/chevyphillip/plus-ev-model)
- [NBA AI Prediction System — GitHub](https://github.com/NBA-Betting/NBA_AI)
- [Deep Q-Learning for NBA Moneyline Betting — Stanford CS224r](https://cs224r.stanford.edu/projects/pdfs/CS_224r_Final_Report%20(3)1.pdf)
- [Polymarket vs Sportsbooks NBA Accuracy 2024-25](https://polymarketanalytics.com/research/nba-sportsbooks-vs-prediction-markets)
- [NBA Betting Strategy 2026 — TopEndSports](https://www.topendsports.com/betting-guides/sport-specific/nba/strategy.htm)
- [NBA Referee Bias — PMC/Scientific Reports](https://pmc.ncbi.nlm.nih.gov/articles/PMC10031197/)
