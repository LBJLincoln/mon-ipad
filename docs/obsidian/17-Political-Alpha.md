---
tags: [political, alpha, ETF, signals, congressional, nomos42]
date: 2026-04-04
aliases: [Political Alpha, Political Signals, ETF Trading, Congressional Trades]
---

# 17 -- Political Alpha

> v3.1 | 22 categories | 743 features | 2 HF evolution spaces | 5 political traders | Repo: nomos-political-alpha

---

## Overview

Political Alpha generates trading signals from political data sources:
- Congressional insider trades
- FEC donor data flows
- Social media sentiment
- Crypto prices as sentiment proxy

These signals drive ETF, index fund, and stock trading via the Political Trading Floor.

---

## Feature Engine

| Property | Value |
|----------|-------|
| Version | v3.1 |
| Categories | 22 (Cat1-22) |
| Features | 743 |
| Recent additions | Cat17-22: insider + Trump policy + foreign sovereign |

### Key Categories

| Category | Type | Features | Source |
|----------|------|----------|--------|
| Cat1-5 | Base political | ~150 | FEC, voting records |
| Cat6-10 | Economic indicators | ~120 | Federal Reserve, BLS |
| Cat11-16 | Market signals | ~180 | ETF flows, sector rotation |
| Cat17 | Insider trading | ~50 | Congressional trades |
| Cat18 | Trump policy signals | ~40 | Executive orders, tariffs |
| Cat19 | Foreign sovereign | ~35 | Foreign government actions |
| Cat20-22 | Social + crypto | ~168 | Twitter, Reddit, BTC/ETH |

---

## Evolution Spaces

| Space | Status | Brier | Gen | Account |
|-------|--------|-------|-----|---------|
| P1_pol | RUNNING | 0.24997 | 326 | Nomos42 |
| P2_pol | RUNNING | 0.23134 | 6,030 | Nomos42 |

Planned (need cleanup first):
- P3_pol (CatBoost specialist) -> LBJLincoln account
- P4_pol (Wide search) -> LBJLincoln account

Kaggle loop: `scripts/kaggle/political_karpathy_loop.py` -- RUNNING

---

## Political Trading Floor

5 AI agents trading ETFs and stocks based on political signals.
Starting capital: **$100,000** virtual | 12 trading days.

| Rank | Agent | Capital | ROI | Sharpe | Strategy | Win Rate |
|------|-------|---------|-----|--------|----------|----------|
| 1 | **Codex** | $101,083 | +1.08% | 6.569 | event_driven + momentum | 52.2% |
| 2 | Gemini | $100,790 | +0.79% | **12.289** | momentum | **61.0%** |
| 3 | OpenRouter | $100,204 | +0.20% | 5.440 | sector_rotation + insider_follow | 49.5% |
| 4 | Claude | $100,030 | +0.03% | 2.656 | mean_reversion | 48.6% |
| 5 | Grok | $99,708 | -0.29% | -13.441 | mean_reversion | 36.7% |

### Strategy Breakdown

| Strategy | Best Agent | Trades | PnL |
|----------|-----------|--------|-----|
| momentum | Gemini | 117 | +$763 |
| event_driven | Codex | 5 | +$866 |
| insider_follow | OpenRouter | 35 | +$73 |
| mean_reversion | Claude | 35 | +$30 |
| sector_rotation | OpenRouter | -- | -- |

> [!info] Key insight
> Political markets behave very differently from NBA. Codex (#1 here, LAST in NBA) thrives on event-driven trades. Grok (#1 in NBA, LAST here) struggles with mean_reversion in political markets.

---

## Data Pipeline

### Fetch Cadence

| Schedule | Mode | Source |
|----------|------|--------|
| `*/30 * * * *` | fast | Quick social signals |
| `*/6h * * * *` | full | Complete data refresh |
| `0 22 * * 1-5` | insider | Congressional trades (weekdays) |
| `30 22 * * 1-5` | prices | ETF/crypto prices (weekdays) |

### Data Sources

| Source | Type | Access |
|--------|------|--------|
| Congressional trades | Insider signals | Public (STOCK Act) |
| FEC donor data | Donor flows | Public government data |
| Social signals | Sentiment (Twitter, Reddit) | `ops/fetch_social_signals.py` |
| Crypto prices | Sentiment proxy | Public APIs |
| ETF data | Price history | Public APIs |

---

## Repo Status

| Property | Value |
|----------|-------|
| Path | `/home/termius/nomos-political-alpha` |
| Last commit | `a860cf3d` -- deploy consolidated_events to HF |
| Uncommitted | 364 files (mostly data) |
| Size | 42 MB |

> [!warning] 364 uncommitted files
> Mostly data files in `data/congressional/`, `data/donors/`, etc. Needs cleanup commit.

---

## Links

[[00-Dashboard]] | [[03-Trading-Floor]] | [[04-Departments]] | [[10-Repos]] | [[06-Research]]
