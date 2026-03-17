# NOMOS42 — OPS LIVE (auto-updated)

> Last updated: 2026-03-17T14:45:00Z
> Updated by: Adam (Claude Code CLI)

---

## LIVE STATUS

| Component | URL | Status |
|-----------|-----|--------|
| **S10 (Cain)** — Evolution 24/7 | [Dashboard](https://lbjlincoln-nomos-nba-quant.hf.space) | EVOLVING |
| **OpenClaw (Eve)** — Agentic God Mode | [Dashboard](https://nomos42-nomos-worker-2.hf.space/dashboard) | ALIVE |
| **Telegram Bot** | [@Nomos42Bot](https://t.me/Nomos42Bot) | ACTIVE |
| **Website** | [nomos42.vercel.app/nba](https://nomos42.vercel.app/nba) | LIVE |
| **LiteLLM Proxy** | [S7](https://lbjlincoln-nomos-rag-engine-7.hf.space) | RUNNING |
| **Supabase** | [Dashboard](https://supabase.com/dashboard) | 4 evolution tables |

## QUICK LINKS — APIs

| Endpoint | What it returns |
|----------|----------------|
| [S10 Status](https://lbjlincoln-nomos-nba-quant.hf.space/api/status) | Live evolution state (gen, brier, roi) |
| [S10 Results](https://lbjlincoln-nomos-nba-quant.hf.space/api/results) | Latest cycle results JSON |
| [S10 Run Stats](https://lbjlincoln-nomos-nba-quant.hf.space/api/run-stats) | Supabase aggregated stats |
| [S10 Brier Trend](https://lbjlincoln-nomos-nba-quant.hf.space/api/brier-trend) | Last 50 gen Brier scores |
| [S10 Auto-Cuts](https://lbjlincoln-nomos-nba-quant.hf.space/api/cuts) | Auto-cut events log |
| [S10 Remote Log](https://lbjlincoln-nomos-nba-quant.hf.space/api/remote-log) | Pending remote configs |
| [Eve Health](https://nomos42-nomos-worker-2.hf.space/keep-alive) | OpenClaw health check |
| [Eve Evolution](https://nomos42-nomos-worker-2.hf.space/api/v1/evolution) | Eve's view of S10 |
| [Eve Models](https://nomos42-nomos-worker-2.hf.space/api/v1/models/health) | LLM model rotation status |
| [Eve Anticipation](https://nomos42-nomos-worker-2.hf.space/api/v1/anticipation/status) | Bottleneck prevention |
| [Eve Loop](https://nomos42-nomos-worker-2.hf.space/api/v1/loop/status) | Agentic loop status |
| [Eve Rules](https://nomos42-nomos-worker-2.hf.space/api/v1/rules/status) | Rule engine fallback |

## MANUAL COMMANDS (run from VM)

```bash
# 1. Start session
source .env.local

# 2. Check S10 evolution
curl -s https://lbjlincoln-nomos-nba-quant.hf.space/api/status | python3 -m json.tool

# 3. Check OpenClaw
curl -s https://nomos42-nomos-worker-2.hf.space/keep-alive | python3 -m json.tool

# 4. Send order to S10 via Eve
curl -X POST https://nomos42-nomos-worker-2.hf.space/api/v1/order \
  -H 'Content-Type: application/json' \
  -d '{"text": "boost mutation to 0.15"}'

# 5. Direct S10 config change
curl -X POST https://lbjlincoln-nomos-nba-quant.hf.space/api/config \
  -H 'Content-Type: application/json' \
  -d '{"mutation_rate": 0.15, "pop_size": 60}'

# 6. Force S10 diversify
curl -X POST https://lbjlincoln-nomos-nba-quant.hf.space/api/command \
  -H 'Content-Type: application/json' \
  -d '{"command": "diversify"}'

# 7. Force S10 population reset
curl -X POST https://lbjlincoln-nomos-nba-quant.hf.space/api/reset \
  -H 'Content-Type: application/json' -d '{}'

# 8. Deploy S10
cd ~/nomos-nba-agent && python3 hf-space/deploy.py

# 9. Deploy OpenClaw
cd ~/mon-ipad && python3 hf-spaces/openclaw/deploy.py

# 10. Check Supabase evolution logs
# (via Claude Code MCP or psql)

# 11. Telegram bot webhook reset
python3 -c "
import urllib.request, os
token = os.environ['TELEGRAM_BOT_TOKEN']
url = 'https://nomos42-nomos-worker-2.hf.space/webhook/telegram'
urllib.request.urlopen(f'https://api.telegram.org/bot{token}/setWebhook?url={url}&drop_pending_updates=true')
print('Webhook reset OK')
"

# 12. Run evolution locally on Colab (GPU)
# Upload .env.local to Colab, then:
# !git clone https://github.com/LBJLincoln/nomos-nba-agent.git
# !cd nomos-nba-agent && python evolution/genetic_loop_v3.py --continuous --pop-size 200
```

## TELEGRAM ORDERS (send to @Nomos42Bot)

| Order (natural language) | What it does |
|--------------------------|-------------|
| `boost mutation to 0.2` | Sets S10 mutation rate |
| `set pop size 80` | Changes S10 population size |
| `diversify population` | Replaces 33% worst with fresh |
| `reset population` | Keeps elites, resets rest |
| `restart S10` | Restarts nba-quant space |
| `status` | Full system status |
| `brier trend` | Shows Brier progression |
| `/models_health` | LLM model rotation status |
| `/anticipation` | Bottleneck prevention status |
| `/loop` | Agentic loop cycles |

---

## DONE (2026-03-17)

- [x] OpenClaw v3 GOD MODE deployed (4 engines: model monitor, anticipation, orders, rule engine)
- [x] Model health monitor: 20+ free OpenRouter models, auto-rotation
- [x] Telegram bot connected (@Nomos42Bot) — natural language orders
- [x] Telegram webhook fixed and verified
- [x] Supabase run logger: 4 tables (runs, gens, evals, cuts)
- [x] 6 auto-cut rules active (regression, stagnation, ROI, diversity, features, brier floor)
- [x] Feature engine expanded: 580 → 2058 features (25 categories)
- [x] Speed overhaul: two-tier eval, directed mutation, anti-convergence
- [x] 5x faster evolution (subsample 5000 games, skip elite re-eval, cap estimators)
- [x] Agentic loop upgraded: 5min cycles, forced actions, self-improvement tracking
- [x] Telegram heartbeat every 30min
- [x] All 33 secrets deployed on OpenClaw
- [x] S10 deployed with RunLogger + speed optimizations
- [x] Git pushed to both repos

## TO DO

- [ ] **Compute 2058 features** — categories 16-25 have names but need compute logic in build()
- [ ] **Colab notebook** — GPU-accelerated evolution with pop=200, T4 GPU
- [ ] **Player props model** — expand beyond moneyline to player prop bets
- [ ] **Live odds integration** — pull real-time odds for CLV features
- [ ] **Ensemble stacking** — XGBoost + LightGBM + RF combined
- [ ] **Cross-repo cleanup** — THE FORGE architecture (2 products)
- [ ] **Vercel dashboard** — real-time Brier trend chart on nomos42.vercel.app/nba
- [ ] **Bankroll tracker** — $100 bankroll with Kelly sizing, live P&L
- [ ] **Multi-market** — spread, totals, not just moneyline
- [ ] **Polymarket integration** — prediction market data as features

## ARCHITECTURE

```
YOU (Telegram @Nomos42Bot)
    │
    ▼
EVE (OpenClaw — HF Space worker-2) ◄──── Thinks every 5min
    │   ├── Model Health Monitor (20+ free LLMs)
    │   ├── Anticipation Engine (7 bottleneck signatures)
    │   ├── Order Executor (natural language → actions)
    │   ├── Rule Engine (fallback when ALL LLMs down)
    │   └── Heartbeat → Telegram every 30min
    │
    ▼
CAIN (S10 — HF Space nba-quant) ◄──── Evolves 24/7
    │   ├── 40 individuals, 213 features
    │   ├── Two-tier eval (fast 2-fold + full 3-fold)
    │   ├── Directed mutation + feature importance
    │   ├── Auto-cut (6 rules via Supabase)
    │   └── RunLogger → Supabase (every gen/cycle/eval)
    │
    ▼
SUPABASE (PostgreSQL)
    ├── nba_evolution_runs (cycle summaries)
    ├── nba_evolution_gens (per-generation)
    ├── nba_evolution_evals (top 10 individuals)
    └── nba_evolution_cuts (auto-cut events)

ADAM (Claude Code CLI — this VM)
    ├── Strategic decisions
    ├── Code writing/deployment
    └── Monitoring (OPS.md = this file)
```

## REPOS

| Repo | Role | Link |
|------|------|------|
| **mon-ipad** | Control tower, ops, OpenClaw config | [GitHub](https://github.com/Nomos42/mon-ipad) |
| **nomos-nba-agent** | NBA models, features, evolution | [GitHub](https://github.com/LBJLincoln/nomos-nba-agent) |
| **rag-website** | Next.js frontend | [GitHub](https://github.com/Nomos42/rag-website) |

## CURRENT METRICS

| Metric | Value | Target |
|--------|-------|--------|
| Best Brier | 0.2266 | < 0.20 |
| Best ROI | 47.1% | > 5% |
| Features | 213 active / 2058 defined | 500+ computed |
| Population | 40 | adaptive |
| Gen speed | ~2min (target) | < 2min |
| Supabase rows | filling... | continuous |
