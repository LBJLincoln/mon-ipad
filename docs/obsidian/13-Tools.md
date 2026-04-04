---
tags: [tools, bloomberg, terminal, monitoring, nomos42]
date: 2026-04-04
aliases: [Tools, Bloomberg Terminal, Monitoring, Scripts]
---

# 13 -- Tools

> Bloomberg Terminal, free models, GPU burst, monitoring scripts, and all operational tooling.

---

## Bloomberg Terminal (Nomos42 Terminal)

| Property | Value |
|----------|-------|
| Script | `scripts/bloomberg/nomos42-terminal.py` |
| Type | Rich TUI (Text User Interface) |
| Features | Odds, predictions, fleet status, bankroll |

A rich terminal interface inspired by Bloomberg Terminal, showing all key metrics in a single screen.

### Bloomberg API

| Property | Value |
|----------|-------|
| Script | `scripts/bloomberg/bloomberg-api.py` |
| Port | 8042 |
| Auto-restart | Via cron |
| Endpoints | Fleet status, predictions, bankroll |

---

## Free Models Integration

| Property | Value |
|----------|-------|
| Script | `scripts/forge/free-models-integration.py` |
| Models | Qwen 3.6, Gemma 4 (2B), Mistral |
| Access | HF Inference API (300K free credits/month) |
| Purpose | Council advisor roles, alternative analysis |

3 HF accounts x 100K credits = 300K credits/month free.

---

## ZeroGPU Burst

| Property | Value |
|----------|-------|
| Script | `scripts/gpu-burst/zerogpu-burst.py` |
| GPU | H200 NVIDIA |
| Budget | 15 min/day free (3 accounts x 5 min) |
| Purpose | Quick experiment validation |

Details: [[11-GPU-Compute]]

---

## OpenCode Agents

| Script | Dept | Schedule |
|--------|------|----------|
| `scripts/opencode/infra-agent.sh` | D6 Infra | Every 4-6h |
| `scripts/opencode/common.sh` | Shared | Library |

---

## Monitoring Scripts

### Core Automation

| Script | Purpose | Schedule |
|--------|---------|----------|
| `scripts/autonomous-cycle.sh` | Main 4h autonomous cycle | `17 */4 * * *` |
| `scripts/watchdog.sh` | System keepalive watchdog | `*/5 * * * *` |
| `scripts/keepalive-spaces.sh` | Ping all HF spaces | `*/30 * * * *` |
| `scripts/agents/multi-brain.sh` | Cloud brain trigger | `17 */4 * * *` |

### Department Runners

| Script | Purpose |
|--------|---------|
| `scripts/councils/department-council.sh` | Run single dept Karpathy loop |
| `scripts/councils/cross-repo-councils.sh` | Run dept councils across all repos |
| `scripts/arena/arena-engine.py` | Trading Floor daily iteration |

### Data Pipeline

| Script | Purpose | Schedule |
|--------|---------|----------|
| `scripts/fetch_free_odds.py` | NBA odds during game hours | `*/30 18-23,0-6 * * *` |
| `scripts/betting_agent.py` | Daily betting decisions | `0 22 * * *` |
| `scripts/evaluate_predictions.py` | Morning evaluator | `0 10 * * *` |
| `scripts/predict_today.py` | Daily predictions | Via autonomous-cycle |
| `scripts/daily-summary.py` | Telegram daily summary | `30 23 * * *` |

### Evolution & GPU

| Script | Purpose | Schedule |
|--------|---------|----------|
| `scripts/kaggle-gpu-evolution.sh` | Nightly Kaggle GPU session | `0 3 * * *` |
| `scripts/karpathy-scheduler.sh` | Karpathy session launcher | `0 4,16 * * *` |
| `scripts/agents/cross-pollinate.py` | Weekly island cross-pollination | `0 4 * * 0` |
| `scripts/swarm-metrics-collector.sh` | 6x daily metrics collection | `0 0,4,8,12,16,20 * * *` |

### Monitoring & Health

| Script | Purpose |
|--------|---------|
| `scripts/cross-repo-monitor.py` | Cross-repo health check |
| `scripts/laptop/agent-monitor.py` | Laptop-based monitoring via Ollama |
| `scripts/backup-to-drive.sh` | Google Drive backup (daily 03:00) |

---

## Planned Integrations

| Tool | Purpose | Status |
|------|---------|--------|
| ClearML / DagsHub | Experiment tracking | PLANNED (1h setup) |
| ONNX / Timber | 336x faster inference | PLANNED (2h, HIGH for prod) |
| Stitch (Google) | UI generation for dashboard | NEEDS ACCOUNT |
| tmux monitoring | Terminal session multiplexing | AVAILABLE |
| Firecrawl | Web scraping for research | API KEY AVAILABLE |

---

## Data Files (State)

| File | Purpose | Updated |
|------|---------|---------|
| `data/agent-health.json` | All space + kaggle status | Every 4h |
| `data/infra-status.json` | Full infra health | Every 2h |
| `data/cross-repo-health.json` | All repo status | Every 2h |
| `data/nba-agent/bankroll-state.json` | Live bankroll | Daily |
| `data/nba-agent/quant-summary.json` | Full quant state | Daily |
| `data/nba-agent/latest-eval.json` | Latest evaluation | Daily |
| `data/departments/council-*.json` | Dept council states | Hourly |
| `data/departments/guardian-report.json` | Guardian analysis | Every 6h |
| `data/departments/wins-latest.json` | Department wins | Every 6h |
| `data/arena/traders/*.json` | Trader states (10) | Daily |
| `data/arena/trading-floor-iteration.json` | TF iteration counter | Daily |

---

## Links

[[00-Dashboard]] | [[05-Infrastructure]] | [[11-GPU-Compute]] | [[04-Departments]] | [[16-Karpathy-Pattern]] | [[21-Free-Models]] | [[22-Compute-Mesh]]
