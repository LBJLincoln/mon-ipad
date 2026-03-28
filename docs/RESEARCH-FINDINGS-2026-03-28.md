# Nomos42 Research Findings — 2026-03-28
# Results from 5 parallel research agents

## 1. ODDS DATA BUG — FIXED
**Bug**: `predict_today.py` stored away team odds in `market_odds_home` field.
**Impact**: Inflated P&L from $100→$305.64 (fake) to $100→$103.42 (real).
**Fix**: Lines 1415-1417 now use `bet_side` to assign odds correctly.
**Also fixed**: 39 corrupted rows in Supabase, evaluator handles both sides.

## 2. REAL PERFORMANCE (corrected)
| Metric | Value |
|--------|-------|
| Bankroll | $100 → $103.42 (+3.42%) |
| Record | 6W-7L (46.2%) |
| Bets | 13 (of 30 evaluated games) |
| Brier (live) | 0.25313 (30 games) |
| Brier (ATR) | 0.21570 (evolved) |
| Max DD | 7.31% |
| Sharpe | 3.96 |

## 3. HISTORICAL ODDS DATASETS (for real backtesting)

### Tier 1 — Free, Ready to Use
| Source | Date Range | Format | Moneyline? |
|--------|------------|--------|------------|
| **Kaggle NBA Betting Data** (cviaxmiwnptr) | 2007-2025 | CSV | YES (2007-2022) |
| **SBR Archives** (sportsbookreviewsonline.com) | 2007-2023 | Excel | YES (Pinnacle closing) |
| **Kaggle NBA Odds (Eric Qiu)** | varies | CSV | YES |

### Tier 2 — API/Scrape
| Source | Method | Cost |
|--------|--------|------|
| OddsPortal.com | Scrape | Free (historical archive) |
| The Odds API | API | Free tier (500 req/mo, recent only) |
| DonBest.com | API/Scrape | Paid |

**Action**: Download Kaggle dataset (2007-2022 moneylines) → use as backtest baseline.
Command: `kaggle datasets download cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024`

## 4. NEW FEATURE CATEGORIES (18 proposals from research)

### Quick Wins (1-4 hours each, expected Brier -0.001 to -0.005)
| Cat | Name | Data Source | Expected Impact |
|-----|------|-------------|-----------------|
| 39 | **Circadian Rhythm + Travel Fatigue** | nba_api + city coords | -0.002 to -0.004 |
| 40 | **Referee Crew Analytics** | Covers.com/OddsShark scrape | -0.002 to -0.005 |
| 41 | **Transition vs Half-Court Splits** | NBA.com PlayType API | -0.001 to -0.003 |
| 42 | **Zone-Based Shot Charts** | NBA.com ShotChart API | -0.001 to -0.003 |
| 43 | **Clutch Performance Trends** | nba_api clutch stats | -0.001 to -0.003 |
| 44 | **Lineup Entropy + Rotation Depth** | NBA.com lineup data | -0.001 to -0.002 |

### Medium Effort
| Cat | Name | Data Source | Expected Impact |
|-----|------|-------------|-----------------|
| 45 | Player-vs-Player Matchup Matrix | NBA.com matchup data | -0.001 to -0.003 |
| 46 | Pace Mismatch Index | NBA.com pace stats | -0.001 to -0.002 |
| 47 | Twitter/X Sentiment | Nitter/snscrape | -0.001 to -0.002 |
| 48 | Injury Impact Score | ESPN injury reports | -0.002 to -0.004 |

### Research: If we implement ALL quick wins, expected total: Brier -0.008 to -0.020
### That would put us at: 0.217 - 0.015 ≈ 0.202 — near target!

## 5. SEASON BACKTEST STATUS
- **Kaggle backtest**: 18/20 weeks completed, then IndexError (fixed)
- **Fake baseline**: Used flat 58% instead of real odds → $2.6M fake result
- **Next step**: Re-run with Kaggle historical odds dataset (real closing moneylines)
- **CUDA fix needed**: TabICL fails on Kaggle P100 (kernel mismatch)

## 6. BETTING STRATEGY vs REAL ODDS
**Answer: NOT YET TESTED against real odds.**
- Current evaluator uses Supabase odds (now corrected)
- Real backtest needs Kaggle historical odds dataset
- Monte Carlo simulation was broken (independent noise = fake edges)
- Proper test = walk-forward with real closing moneylines per game

## 7. DATA LEAKAGE TEST SUITE
17 tests, 15 passed, 2 failures:
- Market odds in engine: **VALID** (pre-game signal, not leakage)
- Flat baseline in backtest: **BUG** (needs real odds replacement)

## 8. AGENT SWARM STATUS
| Agent | Status | File |
|-------|--------|------|
| Orchestrator | BUILT + TESTED | scripts/agents/orchestrator.py |
| Data Leakage Tests | BUILT + TESTED | scripts/agents/test_data_leakage.py |
| Season Simulation | BUILT (needs fix) | scripts/agents/season_simulation.py |
| Cron System | BUILT | scripts/agents/agent-cron.sh |
| Betting Agent | BUILT + PARAMS FIXED | scripts/betting_agent.py |
| Evaluator | REBUILT + CORRECTED | scripts/evaluate_predictions.py |
| Paper Scout | RAN (findings above) | via research-analyst agent |
| Repo Scout | RAN (findings above) | via repo-scout agent |
| Feature Researcher | RAN (18 proposals) | via karpathy-researcher agent |

## PRIORITY ACTIONS
1. Download Kaggle historical odds → real season backtest
2. Implement Cat 39-44 (quick win features) → target Brier -0.015
3. Fix CUDA for TabICL on Kaggle P100
4. Wire agent-cron.sh into system crontab
5. Build infra agent for GPU credit management
