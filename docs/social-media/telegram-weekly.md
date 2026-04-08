# Nomos42 -- Telegram Weekly Update Template (@Nomos42 Channel)

> **Status:** READY | Created: 2026-04-04
> **Channel:** @Nomos42
> **Cadence:** Every Monday morning
> **Format:** Telegram HTML (copy-paste ready with placeholder tags)

---

## Full Template

```
NOMOS42 WEEKLY REPORT -- Week of [DATE]
========================================

FLEET STATUS (6 HF Islands)
  Status: [N_UP]/6 UP | Generations: [TOTAL_GENS]
  Best Brier: [BEST_BRIER] ([BEST_ISLAND])
  Fleet Avg: [FLEET_AVG] | ATR: 0.21570
  Gap to Target (0.200): [GAP]

  S10 Exploitation  [BRIER_10]  gen=[GEN_10]  [MODEL_10]
  S11 Exploration   [BRIER_11]  gen=[GEN_11]  [MODEL_11]
  S12 Extra-Trees   [BRIER_12]  gen=[GEN_12]  [MODEL_12]
  S13 CatBoost      [BRIER_13]  gen=[GEN_13]  [MODEL_13]
  S14 LightGBM      [BRIER_14]  gen=[GEN_14]  [MODEL_14]
  S15 Wide Search   [BRIER_15]  gen=[GEN_15]  [MODEL_15]

  Weekly improvement: [DELTA] Brier points
  New best this week: [YES/NO] -- [DETAILS]

TRADING FLOOR LEADERBOARD

  NBA Tournament (start $100):
  1. [T1_NAME] ([T1_PROVIDER])  $[T1_BANK]  ROI [T1_ROI]%  Sharpe [T1_SH]
  2. [T2_NAME] ([T2_PROVIDER])  $[T2_BANK]  ROI [T2_ROI]%  Sharpe [T2_SH]
  3. [T3_NAME] ([T3_PROVIDER])  $[T3_BANK]  ROI [T3_ROI]%  Sharpe [T3_SH]
  4. [T4_NAME] ([T4_PROVIDER])  $[T4_BANK]  ROI [T4_ROI]%  Sharpe [T4_SH]
  5. [T5_NAME] ([T5_PROVIDER])  $[T5_BANK]  ROI [T5_ROI]%  Sharpe [T5_SH]

  Eliminated: [N_ELIM] traders | Strategies active: [N_STRATS]
  Week's biggest winner: [WINNER_NAME] +$[WINNER_DELTA]
  Week's biggest loser: [LOSER_NAME] -$[LOSER_DELTA]

  Political Tournament (start $100K):
  1. [P1_NAME]  $[P1_BANK]  ROI [P1_ROI]%
  2. [P2_NAME]  $[P2_BANK]  ROI [P2_ROI]%
  3. [P3_NAME]  $[P3_BANK]  ROI [P3_ROI]%
  4. [P4_NAME]  $[P4_BANK]  ROI [P4_ROI]%
  5. [P5_NAME]  $[P5_BANK]  ROI [P5_ROI]%

BEST PICKS OF THE WEEK

  [DATE_1]: [TEAM_A] vs [TEAM_B]
    Prediction: [TEAM] [PROB]% | Odds: [ODDS] | Result: [W/L]
    Edge: [EDGE]% | Kelly: [KELLY]%

  [DATE_2]: [TEAM_A] vs [TEAM_B]
    Prediction: [TEAM] [PROB]% | Odds: [ODDS] | Result: [W/L]
    Edge: [EDGE]% | Kelly: [KELLY]%

  [DATE_3]: [TEAM_A] vs [TEAM_B]
    Prediction: [TEAM] [PROB]% | Odds: [ODDS] | Result: [W/L]
    Edge: [EDGE]% | Kelly: [KELLY]%

  Weekly record: [WINS]W-[LOSSES]L ([WIN_PCT]%)
  Weekly ROI: [ROI]% | Weekly P&L: $[PNL]

RESEARCH HIGHLIGHTS

  Papers scanned: [N_PAPERS]
  Techniques extracted: [N_TECHS]
  Experiments run: [N_EXPERIMENTS]

  Key findings:
  - [FINDING_1]
  - [FINDING_2]
  - [FINDING_3]

  Best experiment: [EXPERIMENT_DESC] -- Brier delta [DELTA]

DEPARTMENT HEALTH

  D1 Research:    [STATUS] -- [DETAIL]
  D2 Engineering: [STATUS] -- [DETAIL]
  D3 Evolution:   [STATUS] -- [DETAIL]
  D4 Betting:     [STATUS] -- [DETAIL]
  D5 Evaluation:  [STATUS] -- [DETAIL]
  D6 Infra:       [STATUS] -- uptime [UPTIME]%
  D7 Political:   [STATUS] -- [DETAIL]
  D8 Creative:    [STATUS] -- [DETAIL]

  Guardian actions this week: [N_ACTIONS]
  Cross-pollination routes: [N_ROUTES]

COMING NEXT WEEK

  1. [PRIORITY_1]
  2. [PRIORITY_2]
  3. [PRIORITY_3]

  Target: Brier [TARGET_BRIER] | ROI [TARGET_ROI]% | Sharpe [TARGET_SHARPE]

----------------------------------------
ATR: 0.21570 | Target: < 0.200
Dashboard: nomos-dashboard.vercel.app
Predictions: @Nomos42Bot
Code: github.com/LBJLincoln/mon-ipad
```

---

## Example Fill (Week of 2026-04-04)

```
NOMOS42 WEEKLY REPORT -- Week of April 4, 2026
================================================

FLEET STATUS (6 HF Islands)
  Status: 6/6 UP | Generations: 3,693
  Best Brier: 0.22159 (S15 Wide Search)
  Fleet Avg: 0.22419 | ATR: 0.21570
  Gap to Target (0.200): +0.02159

  S10 Exploitation  0.22454  gen=349   xgboost_brier
  S11 Exploration   0.22273  gen=548   xgboost
  S12 Extra-Trees   0.22506  gen=797   catboost
  S13 CatBoost      0.22455  gen=542   extra_trees
  S14 LightGBM      0.22666  gen=600   xgboost_brier
  S15 Wide Search   0.22159  gen=857   random_forest  *

  Weekly improvement: TBD Brier points
  New best this week: S15 hit 0.22159 (random_forest)

TRADING FLOOR LEADERBOARD

  NBA Tournament (start $100):
  1. Grok (xAI)           $3,687.51  ROI +3,588%  Sharpe 4.67
  2. Gemini (Google)       $1,731.08  ROI +1,631%  Sharpe 2.66
  3. Claude (Anthropic)      $322.86  ROI +223%    Sharpe 4.42
  4. OpenRouter (Multi)      $164.63  ROI +65%     Sharpe 0.56
  5. Codex (OpenAI)            $0.63  ROI -99%     Sharpe -0.27

  Eliminated: 0 traders | Strategies active: TBD
  Week's biggest winner: Grok
  Week's biggest loser: Codex (near-zero balance)

  Political Tournament (start $100K):
  1. Codex        $101,083  ROI +1.08%
  2. Gemini       $100,790  ROI +0.79%
  3. OpenRouter   $100,204  ROI +0.20%
  4. Claude       $100,030  ROI +0.03%
  5. Grok          $99,708  ROI -0.29%

BEST PICKS OF THE WEEK

  (Fill from daily predictions after games resolve)

RESEARCH HIGHLIGHTS

  Papers scanned: 14
  Techniques extracted: 18
  Experiments run: TBD

  Key findings:
  - S15 random_forest achieved new fleet best 0.22159
  - Guardian recommending S10 seed from S14 config
  - Full_kelly strategy rated ELITE by evaluation dept

DEPARTMENT HEALTH

  D1 Research:    COMPLETED -- 14 papers, 18 techniques
  D2 Engineering: UNKNOWN -- pending cycle
  D3 Evolution:   COMPLETED -- best Brier 0.22182
  D4 Betting:     COMPLETED -- full_kelly ELITE
  D5 Evaluation:  COMPLETED
  D6 Infra:       COMPLETED -- uptime 88%
  D7 Political:   COMPLETED
  D8 Creative:    IDLE

  Guardian actions this week: 3
  Cross-pollination routes: 1

COMING NEXT WEEK

  1. Push fleet best below 0.2200 (current: 0.22159)
  2. Seed S10 with S14/S12 winning configs
  3. Fix Kaggle political-alpha karpathy loop error

  Target: Brier < 0.2200 | ROI > 0% | Sharpe > 0

----------------------------------------
ATR: 0.21570 | Target: < 0.200
Dashboard: nomos-dashboard.vercel.app
Predictions: @Nomos42Bot
Code: github.com/LBJLincoln/mon-ipad
```

---

## Posting Checklist

- [ ] All [BRACKETS] filled with current data
- [ ] Trading Floor leaderboard matches latest trader state JSONs
- [ ] Fleet Brier numbers match agent-health.json
- [ ] Best picks section filled with resolved bets only (no pending)
- [ ] "Coming next week" reflects actual Guardian priority queue
- [ ] Post to @Nomos42 channel (not bot, not admin DM)
- [ ] Cross-post summary to Twitter/X thread if applicable
