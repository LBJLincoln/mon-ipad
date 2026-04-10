# Nomos42 — Broker & Market Data Setup Guide

## Summary of Integrations

| Script | Status | Purpose | Keys Needed |
|--------|--------|---------|-------------|
| `paper_client.py` | ✅ Scaffold | Alpaca paper trading (stocks/ETFs) | ALPACA_PAPER_KEY, ALPACA_PAPER_SECRET |
| `kraken_client.py` | ✅ New (cycle85) | Kraken crypto (BTC/ETH/SOL basket) | KRAKEN_API_KEY, KRAKEN_API_SECRET |
| `odds_api_client.py` | ✅ New (cycle85) | Pinnacle + 70 books via The Odds API | ODDS_API_KEY |

---

## 1. Alpaca (Stocks/ETFs for Political Alpha)

Free paper account at https://alpaca.markets/

```bash
# Add to .env.local
ALPACA_PAPER_KEY=PKxxxxxx
ALPACA_PAPER_SECRET=xxxxxxxx
ALPACA_PAPER_BASE=https://paper-api.alpaca.markets

# Test
python3 scripts/alpaca/paper_client.py status
python3 scripts/alpaca/paper_client.py sync-political   # dry-run default
python3 scripts/alpaca/paper_client.py sync-political --live   # real paper orders
```

---

## 2. Kraken (Crypto: BTC, ETH, SOL)

Account at https://www.kraken.com/ → Settings → API → Create Key
Permissions needed: **Query Funds** + **Create & Modify Orders** (no withdraw)

```bash
# Add to .env.local
KRAKEN_API_KEY=xxxxxxxx
KRAKEN_API_SECRET=xxxxxxxx==  # base64 encoded
DRY_RUN=true   # flip to false for live

# Test
python3 scripts/alpaca/kraken_client.py status
python3 scripts/alpaca/kraken_client.py ticker
python3 scripts/alpaca/kraken_client.py sync-political   # reads political-trading-floor-latest.json
```

**Rate limits**: 1 call per 3 seconds enforced internally (Starter tier: counter 15, decay 0.33/sec)

**Basket**:
- BTC → XBTUSD
- ETH → ETHUSD  
- SOL → SOLUSD
- COIN (Coinbase) → not on Kraken (COIN is a US stock, use Alpaca instead)

---

## 3. The Odds API — Pinnacle Lines (NBA + Political)

**Why**: Pinnacle's direct API closed July 2025. The Odds API aggregates Pinnacle + 70 books.

Free key at https://the-odds-api.com/ (500 req/month free)

```bash
# Add to .env.local
ODDS_API_KEY=xxxxxxxx

# Test
python3 scripts/alpaca/odds_api_client.py sports          # list available markets
python3 scripts/alpaca/odds_api_client.py nba --pinnacle  # Pinnacle NBA lines
python3 scripts/alpaca/odds_api_client.py nba --compare   # model vs Pinnacle edge finder
python3 scripts/alpaca/odds_api_client.py usage           # check remaining quota

# Quota-efficient cron (3x daily = ~90 req/month on free tier)
0 14,18,22 * * * python3 /home/termius/mon-ipad/scripts/alpaca/odds_api_client.py nba
```

**Output**: `data/odds/odds-api-latest.json` — same dir as existing odds files.
Pinnacle lines are vig-removed before saving (fair probabilities, not raw implied).

---

## 4. TradingView MCP (Optional — Research/Internal Use)

Two community MCP servers exist. **Not official** — scrapers against TradingView public endpoints.

### Option A: `atilaahmettaner/tradingview-mcp` (recommended — most features)
```bash
# Install
pip install mcp tradingview-screener

# Add to ~/.claude.json mcpServers section:
{
  "tradingview": {
    "command": "python",
    "args": ["-m", "tradingview_mcp"],
    "env": {}
  }
}
```
Gives Claude: real-time screening, Bollinger Bands, candlestick patterns, multi-exchange.

### Option B: `bidouilles/mcp-tradingview-server` (simpler)
```bash
pip install fastmcp tradingview-scraper
# Then configure same way
```
Gives Claude: get_indicators, get_historical_data (OHLCV candles).

**Caution**: TOS compliance unclear. Use for research/analysis only, not production data feeds.
For production NBA odds — use `odds_api_client.py` (The Odds API) instead.

---

## Recommended Cron Setup (add to VM crontab)

```bash
crontab -e

# NBA odds — 3x daily when games are likely
0 14,18,22 * * * cd /home/termius/mon-ipad && python3 scripts/alpaca/odds_api_client.py nba >> logs/odds-api.log 2>&1

# Kraken ticker snapshot — every 30 min
*/30 * * * * cd /home/termius/mon-ipad && python3 scripts/alpaca/kraken_client.py ticker >> logs/kraken.log 2>&1

# Alpaca account status — daily
0 9 * * * cd /home/termius/mon-ipad && python3 scripts/alpaca/paper_client.py status >> logs/alpaca.log 2>&1

# Compute orchestrator — 4x daily for GPU dispatch
0 6,8,12,18 * * * python3 /home/termius/mon-ipad/scripts/gpu-burst/compute-orchestrator.py >> logs/compute-orchestrator.log 2>&1

# CRITICAL MISSING: autonomous cycle (trading floor + data server)
30 * * * * /home/termius/mon-ipad/scripts/autonomous-cycle.sh >> /tmp/ac.log 2>&1
```

---

## Data Server (required for website to show live data)

```bash
# Start permanently (add to autonomous-cycle.sh Phase 4 — already there, just needs scheduling)
nohup python3 /home/termius/mon-ipad/scripts/nba-data-server.py > logs/data-server.log 2>&1 &
echo $! > /tmp/data-server.pid
```

The website `nomos42.com/trading-floor` shows stale April 6-7 data because:
1. `nba-data-server.py` is not running (port 8080 down)
2. `autonomous-cycle.sh` has no crontab entry
Both must be fixed for the dashboard to go live.
