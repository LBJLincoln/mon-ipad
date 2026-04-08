# Nomos42 Bloomberg Terminal

NBA Betting Intelligence Terminal inspired by Bloomberg / OpenBB architecture.

## Quick Start

### Terminal (Rich CLI)

```bash
# Install dependency
pip install rich

# Run terminal
python3 scripts/bloomberg/nomos42-terminal.py
```

**Keyboard commands:**
| Key | Action |
|-----|--------|
| `a` | All panels (dashboard) |
| `o` | Odds view |
| `p` | Predictions view |
| `t` | Trading Floor |
| `e` | Evolution fleet |
| `b` | Bankroll & P&L |
| `h` | System health |
| `v` | Value bets |
| `r` | Refresh |
| `q` | Quit |

Auto-refreshes every 60 seconds.

### API Server

```bash
# No dependencies needed — uses stdlib http.server
python3 scripts/bloomberg/bloomberg-api.py

# Custom port
python3 scripts/bloomberg/bloomberg-api.py --port 9000

# Bind to all interfaces (e.g., for Tailscale access)
python3 scripts/bloomberg/bloomberg-api.py --host 0.0.0.0
```

Default: `http://127.0.0.1:8042`

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/odds` | Latest NBA odds |
| `GET /api/predictions` | Model predictions for today |
| `GET /api/value-bets` | Current value bets with Kelly sizing |
| `GET /api/trading-floor` | Trading Floor v4 leaderboard (5 AI traders) |
| `GET /api/evolution` | 6-island HF Space fleet status |
| `GET /api/bankroll` | Bankroll state and P&L |
| `GET /api/quant` | Quant summary (models, features, calibration) |
| `GET /api/health` | System health overview |
| `GET /api/all` | Everything combined |

All endpoints return JSON with CORS headers enabled.

### Example

```bash
# Get trading floor leaderboard
curl -s http://localhost:8042/api/trading-floor | python3 -m json.tool

# Get bankroll state
curl -s http://localhost:8042/api/bankroll | jq '.bankroll.balance'

# Get all data
curl -s http://localhost:8042/api/all | jq '.evolution.best'
```

## Architecture

```
scripts/bloomberg/
  nomos42-terminal.py  — Rich-based interactive CLI terminal
  bloomberg-api.py     — Lightweight HTTP JSON API server (stdlib only)

Data sources (all local JSON):
  data/nba-agent/odds-latest.json
  data/nba-agent/predictions-today.json
  data/nba-agent/value-bets.json
  data/nba-agent/bankroll-state.json
  data/nba-agent/quant-summary.json
  data/nba-agent/latest-eval.json
  data/arena/trading-floor-v4-latest.json
  data/agent-health.json
  data/infra-status.json
```

## VM Constraints

- Runs on 1 vCPU / 969 MB RAM
- ZERO ML — reads pre-computed data only
- Terminal: requires `rich` (~2MB)
- API server: zero dependencies (stdlib `http.server`)
