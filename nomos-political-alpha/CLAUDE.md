# Nomos42 — Political Alpha (Trump Donor Trading)

> Architecture v1.0 — Claude Code 2026 | Created: 2026-03-26

## Mission
Exploit the documented pattern: Trump donor → political favor → stock/crypto move.
Combine 3 layers of insider signals: FEC donations, Polymarket whale activity, SEC Form 4 insider trades.

**Duplicated from:** nomos-nba-agent (NBA Quant AI) — same GA, Kelly, Karpathy loop, bankroll manager.

## Architecture

```
SIGNAL LAYER (continuous ingestion)
    ├── FEC API → donor amounts, timing, channels
    ├── Federal Register API → executive orders, rules by sector
    ├── Congress.gov API → bills, votes affecting donors
    ├── OpenSecrets → lobbying, PAC data
    ├── USAspending.gov → government contracts to donors
    ├── SEC EDGAR Form 4 → insider buying/selling at donor corps
    ├── Polymarket CLOB API → whale bets on Trump policy events
    ├── Kalshi API → policy outcome contracts
    ├── Unusual Whales → options flow, dark pool on donor tickers
    ├── yfinance → prices, volumes, fundamentals
    ├── FRED API → macro (VIX, DXY, 10Y, credit spreads)
    └── CoinGecko → crypto ecosystem (BTC, ETH, SOL, COIN proxy)

FEATURE ENGINE (~2,000 features, 8 categories)
    ├── Donor Profile (200) — amounts, timing, channels, sector, pending business
    ├── Policy Signal (300) — exec orders, bills, regulatory changes by sector
    ├── Market Features (500) — returns, volume, IV, put/call, dark pool, RSI
    ├── Trump Proximity (200) — CEO visits, Truth Social mentions, DOGE mentions
    ├── Polymarket/Kalshi (200) — whale positions, price moves, volume on policy
    ├── Insider Trading (200) — Form 4 buys/sells, cluster buying, timing
    ├── Macro & Cross-Asset (200) — VIX, DXY, sector ETFs, crypto sentiment
    └── Interactions & Temporal (200) — cross-feature, seasonal, decay

GA EVOLUTION (HF Space, always-on)
    ├── LBJLincoln26/nomos-political-alpha — main evolution island
    ├── NSGA-II Pareto ranking (same as NBA)
    ├── Multi-objective: Brier + ROI + Sharpe + ECE
    └── Population: 60 individuals, 3 islands

PREDICTION & EXECUTION
    ├── Daily political signal scan → affected donor corps
    ├── ML model predicts P(excess_return > X% | signal)
    ├── Kelly sizing with market-implied odds
    ├── Execution: XTB (CFDs) + Kraken (crypto) + Betclic (NBA parallel)
    └── Bankroll manager (same code as NBA)

DASHBOARD
    └── nomosdashboard.vercel.app/political — new section

VM MUSCLE (cron, same 34.136.180.66)
    ├── Run fetch_political_data.py (hourly)
    ├── Run polymarket_tracker.py (every 15min)
    ├── Run insider_tracker.py (daily after market close)
    └── Push results to Supabase

ApophisFIN RAG (n8n amoret.app.n8n.cloud)
    ├── Ingestion: exec orders, SEC filings, tariff news
    ├── Graph RAG: Trump ↔ donor ↔ policy ↔ sector (Neo4j)
    └── Quantitative RAG: structured donor/contract data
```

## Key Files

| File | Role | Duplicated From |
|------|------|-----------------|
| `features/political_engine.py` | ~2,000 feature candidates, 8 categories | NEW (inspired by NBA engine) |
| `models/donor_power_index.py` | Score each donor corp by Trump proximity | NEW |
| `models/kelly.py` | Kelly criterion (identical to NBA) | nomos-nba-agent/models/kelly.py |
| `ops/fetch_political_data.py` | FEC + Federal Register + Congress + FRED | NEW (replaces fetch-odds.py) |
| `ops/polymarket_tracker.py` | Polymarket CLOB whale tracking | NEW |
| `ops/insider_tracker.py` | SEC Form 4 insider trade detection | NEW |
| `ops/political_signal_analyzer.py` | Detect policy→donor→trade signals | NEW (replaces odds_analyzer.py) |
| `ops/bankroll_manager.py` | P&L tracking, compound, snapshots | IDENTICAL to NBA |
| `ops/karpathy_loop.py` | Self-improving cycle | ADAPTED from NBA |
| `calibration/conformal.py` | Conformal prediction | IDENTICAL to NBA |
| `evolution/genetic_loop.py` | GA NSGA-II island model | IDENTICAL to NBA |
| `hf-space/app.py` | Gradio + FastAPI evolution server | ADAPTED from NBA |

## HF Spaces Allocation

| Space | Account | Role |
|-------|---------|------|
| S10 LBJLincoln/nomos-nba-quant | LBJLincoln | NBA exploitation |
| S11 LBJLincoln/nomos-nba-quant-2 | LBJLincoln | NBA exploration |
| S12 LBJLincoln26/nba-evo-3 | LBJLincoln26 | NBA extra_trees |
| S13 LBJLincoln26/nba-evo-4 | LBJLincoln26 | NBA catboost |
| S14 Nomos42/nba-evo-5 | Nomos42 | NBA lightgbm |
| S15 Nomos42/nba-evo-6 | Nomos42 | NBA wide search |
| **P1** LBJLincoln26/nomos-political-alpha | LBJLincoln26 | **Political Alpha main** |
| **P2** Nomos42/nomos-political-alpha-2 | Nomos42 | **Political Alpha exploration** |
| RAG LBJLincoln26/nomos-rag-engine-10 | LBJLincoln26 | **Reactivate for political signals** |

## Data Sources (ALL FREE)

| Source | API | Key Required | Rate Limit |
|--------|-----|-------------|------------|
| FEC | api.open.fec.gov | DEMO_KEY (free) | 1000/hr |
| Federal Register | federalregister.gov/api | No | Unlimited |
| Congress.gov | api.congress.gov | Free signup | 5000/hr |
| OpenSecrets | opensecrets.org/api | Free signup | 200/day |
| USAspending | api.usaspending.gov | No | Unlimited |
| SEC EDGAR | efts.sec.gov | No | 10/sec |
| Polymarket CLOB | clob.polymarket.com | No | Generous |
| yfinance | Python lib | No | Unlimited |
| FRED | fred.stlouisfed.org | Free signup | Unlimited |
| CoinGecko | api.coingecko.com | No | 30/min |

## Supabase Tables (NEW)

| Table | Purpose |
|-------|---------|
| `political_donors` | FEC donor data, amounts, timing |
| `political_signals` | Policy events + affected companies |
| `polymarket_whales` | Whale positions on Trump policy markets |
| `insider_trades` | SEC Form 4 filings for donor tickers |
| `political_predictions` | ML predictions + outcomes |
| `political_experiments` | GA experiment results |
| `political_bankroll` | P&L tracking, daily snapshots |

## Donor Universe (publicly traded, tradeable from EU)

### Tier 1 — Direct Quid Pro Quo Documented
GEO, CXW, COIN, MO, UNH, PPC, OKLO, META, FOUR

### Tier 2 — Large Inaugural Donors ($1M+)
CVX, XOM, OXY, AMZN, UBER, QCOM, BA, FDX, TSLA, LVS

### Tier 3 — Ballroom/Antitrust Play
AAPL, MSFT, NVDA, CMCSA, UNP

### Tier 4 — Crypto Ecosystem Beneficiaries
COIN, MSTR, BTC, ETH, SOL

## Rules (same as NBA)
1. **ZERO ML on VM** — ALL training on HF Spaces
2. **Feature engine parity** — root = hf-space always
3. **1 fix per iteration**
4. **All experiments tagged** in Supabase
5. **Kelly NEVER exceeds 5% bankroll per position**
