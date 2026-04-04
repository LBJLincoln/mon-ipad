---
tags: [trading-floor, traders, PnL, strategies, AI-competition, nomos42]
date: 2026-04-03
aliases: [Trading Floor, Traders, Arena, AI Competition]
---

# 03 — Trading Floor v4

> Season 2025-26 | 5 NBA traders | 5 Political traders | Iter 287 | Last: 2026-04-03T21:28Z

## NBA Season Leaderboard (Full Season 2025-26)

| Rank | Agent | Provider | Bankroll | ROI | Sharpe | Record | Peak | Max DD |
|------|-------|----------|----------|-----|--------|--------|------|--------|
| 1 | **Grok** | xAI | **$3,687.51** | **+3,587.5%** | 4.672 | 523W-705L | $3,816.21 | 53.5% |
| 2 | Gemini | Google | $1,731.08 | +1,631.1% | 2.660 | 1753W-1801L | $1,884.99 | 77.0% |
| 3 | Claude | Anthropic | $322.86 | +222.9% | 4.423 | 961W-975L | $329.87 | 38.4% |
| 4 | OpenRouter | Multi | $164.63 | +64.6% | 0.560 | 1036W-1089L | $231.45 | 93.5% |
| 5 | Codex | OpenAI | $0.63 | -99.4% | -0.268 | 2177W-2055L | $665.28 | 100% |

All start: **$100.00** virtual | Season start: 2025-10-21

---

## Agent Profiles

### T1 — Grok (CHAMPION)
- **Provider:** xAI | **Personality:** contrarian | **Risk:** 0.65
- **Strategy:** value_hunter + underdog_specialist
- **Top models:** elo_baseline ($+1,996.73), random_forest ($+937.03), extra_trees ($+653.74)
- **Top strategies:** value_hunter 280 bets ($+2,860.96), underdog_specialist 800 bets ($+728.21)
- **Key insight:** Contrarian + value_hunter on underdogs = massive edge at high odds

### T2 — Gemini (#2)
- **Provider:** Google | **Personality:** analytical | **Risk:** 0.6
- **Bankroll:** $1,731.08 | **ROI:** +1,631.1% | **Sharpe:** 2.66
- **Total wagered:** $16,086.64 | **Bets:** 3,554
- **Strategy:** confidence_scaled + half_kelly

### T3 — Claude (#3)
- **Provider:** Anthropic | **Personality:** conservative | **Risk:** 0.4
- **Strategy:** quarter_kelly (all 1,936 bets)
- **Top categories:** alt_spread_home_big ($+191.49), alt_spread_away_big ($+82.07)
- **Total wagered:** $1,655.59 | **Best Sharpe among all (tied 4.423 vs Grok 4.672)**

### T4 — OpenRouter (#4)
- **Provider:** Multi-model | **Personality:** diversified | **Risk:** 0.5
- **Bankroll:** $164.63 | **ROI:** +64.6% | **Sharpe:** 0.560
- **Total wagered:** $2,433.84 | **Bets:** 2,125
- **Model mix:** lightgbm + extra_trees + consensus_ensemble

### T5 — Codex (ELIMINATED)
- **Provider:** OpenAI | **Personality:** aggressive | **Risk:** 0.7
- **Bankroll:** $0.63 | **ROI:** -99.4% | **Nearly bankrupt**
- **Peak:** $665.28 (day 4+) then catastrophic drawdown
- **Lesson:** aggressive + high frequency + max drawdown = ruin

---

## Strategy Rankings (Backtest, All Agents)

| Rank | Strategy | Avg ROI | Verdict |
|------|----------|---------|---------|
| 1 | full_kelly | +135,550% | ELITE (but variance extreme) |
| 2 | anti_martingale | +125,583% | ELITE |
| 3 | proportional_edge | +73,112% | STRONG |
| 4 | ev_threshold_110 | +52,320% | STRONG |
| 5 | half_kelly | +34,739% | STRONG |

Note: full_kelly elite in theory but Codex disaster shows real-world variance risk.

---

## What Wins: Analysis

**Grok's recipe:**
1. Contrarian personality (bet underdogs)
2. value_hunter strategy (seek positive EV)
3. Simple models: elo_baseline outperformed all complex ML
4. Lower bet frequency (1,228 bets vs Codex's 4,232)

**Claude's recipe:**
1. Conservative (quarter_kelly only)
2. Best risk-adjusted returns (Sharpe 4.423)
3. Alt-spread categories dominate (+$273.56 combined)
4. No overexposure

**Codex's failure:**
1. Aggressive (risk 0.7) + high frequency
2. Position sizing too large after early peak ($665)
3. No stop-loss / drawdown protection

---

## Trading Floor Architecture

Each trader sees:
- All predictions + probabilities
- All strategy results from peers
- Market odds for all NBA games
- Peer P&L and current standings

Each decides:
- Which games to bet
- What size (Kelly fraction)
- Which model to use
- Which category to target

Backend: `scripts/arena/arena-engine.py` (runs daily at 11:00)
Data: `data/arena/traders/*.json` + `data/arena/docs/*-season-2025-26.md`

---

## Political Trading Floor

5 AI agents also trade ETFs, index funds, real stocks based on political signals.

- Starting capital: $100,000 virtual
- Daily rebalancing
- Political alpha: v3.1, 22 categories, 743 features
- Categories: insider trading signals, Trump policy, foreign sovereign funds

→ Details: [[04-Departments#Political]]

---

## Key Lessons for Live Betting

1. **Grok's value_hunter strategy** is the production target for live agent
2. **quarter_kelly** (Claude) offers best risk-adjusted returns for conservative mode
3. **half_kelly** is the sweet spot for balance
4. **elo_baseline** beats complex ML for underdog hunting
5. **alt_spread categories** (home/away big) have highest alpha

→ Bankroll management: [[07-Betting]]
→ Research roadmap to beat 0.20: [[06-Research]]

---

## Links

[[README]] | [[00-Dashboard]] | [[07-Betting]] | [[04-Departments]] | [[06-Research]]
