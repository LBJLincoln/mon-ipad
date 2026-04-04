---
tags: [infrastructure, VM, HF-spaces, GPU, crons, bots, nomos42]
date: 2026-04-03
aliases: [Infrastructure, Infra, System Health, Compute]
---

# 05 — Infrastructure

> 5 repos | 6 HF spaces | 2 political spaces | 2 bots | 35 crons | 4 missing | Updated: 2026-04-03T23:47Z

## Compute Nodes

| Node | Type | Specs | Role |
|------|------|-------|------|
| VM (iPad terminal) | Cloud VPS | 1 vCPU, 969 MB RAM | Control tower, brain, crons |
| Laptop | Local (Windows/WSL) | Acer Aspire 3 | Claude Code Desktop, experiments |
| Brother's PC | 3rd node | Windows, Termius | Extra compute, via Tailscale |
| HF Spaces (×8) | Cloud CPU | Free tier | 24/7 evolution (ZERO ML on VM) |
| Kaggle | Cloud GPU (P100) | 9h sessions | Karpathy loops, bulk training |
| Colab | Cloud GPU (T4) | On-demand | TabICL, ATR experiments |
| Lightning AI | Cloud GPU | 22h sessions | Available |
| Vast.ai | Cloud GPU | $0.16/hr | On-demand burst |

**Critical rule:** ZERO ML on VM. All training → HF Spaces, Kaggle, Colab.

Mesh networking: **Tailscale** connecting VM + Laptop + iPad

---

## HF Spaces Status

### NBA Evolution (Nomos42 account)

| Space | Space ID | URL | Status | Brier | Gen |
|-------|----------|-----|--------|-------|-----|
| S10 | Nomos42/nba-quant | nomos42-nba-quant.hf.space | running | 0.22454 | 207 |
| S11 | Nomos42/nba-quant-2 | nomos42-nba-quant-2.hf.space | running | 0.22273 | 284 |
| S12 | Nomos42/nba-evo-3 | nomos42-nba-evo-3.hf.space | running | 0.22506 | 576 |
| S13 | Nomos42/nba-evo-4 | nomos42-nba-evo-4.hf.space | running | 0.22455 | 374 |
| S14 | Nomos42/nba-evo-5 | nomos42-nba-evo-5.hf.space | running | 0.22666 | 443 |
| S15 | Nomos42/nba-evo-6 | nomos42-nba-evo-6.hf.space | running | 0.22159 | 464 |

### Political Evolution

| Space | Status | Brier | Gen |
|-------|--------|-------|-----|
| P1_pol | running | 0.24186 | 8871 |
| P2_pol | running | 0.23134 | 4104 |

### HF Accounts
- **LBJLincoln** → HF_TOKEN (primary)
- **LBJLincoln26** → HF_TOKEN_2 (secondary)
- **Nomos42** → HF_TOKEN_3 (spaces account)

Keepalive: `scripts/keepalive-spaces.sh` (every 30 min — MISSING from cron!)

---

## Cron Jobs (VM)

Total: 35 | By project: brain=27, political-alpha=7, unknown=1

### Key Crons

| Schedule | Script | Purpose |
|----------|--------|---------|
| `*/5 * * * *` | watchdog.sh | System watchdog |
| `*/30 * * * *` | agent-cron.sh | Agent heartbeat |
| `0 */2 * * *` | cross-repo-monitor.py | Cross-repo health |
| `0 3 * * *` | kaggle-gpu-evolution.sh | Nightly Kaggle GPU |
| `*/30 18-23,0-6 * * *` | fetch_free_odds.py | NBA odds during game hours |
| `0 22 * * *` | betting_agent.py | Daily betting |
| `0 10 * * *` | evaluate_predictions.py | Morning evaluator |
| `17 */4 * * *` | multi-brain.sh | 4h brain cycle |
| `0 4,16 * * *` | karpathy-scheduler.sh | Karpathy sessions |
| `30 23 * * *` | daily-summary.py | Daily Telegram summary |
| `0 4 * * 0` | cross-pollinate.py | Weekly island cross-pollination |
| `0 0,4,8,12,16,20 * * *` | swarm-metrics-collector.sh | 6x daily metrics |

### Department Councils

| Dept | Schedule |
|------|----------|
| research | `2 * * * *` (every hour :02) |
| engineering | `12 * * * *` (every hour :12) |
| evolution | `22 * * * *` (every hour :22) |
| betting | `10 */2 * * *` |
| evaluation | `20 */2 * * *` |
| infra | `40 */2 * * *` |
| political | `0 8,20 * * *` |
| creative | `0 9,21 * * *` |
| comms | `0 7 * * *` |
| business | `0 8 * * *` |
| finance | `0 23 * * *` |

### Missing Crons (Critical)

| Missing | Purpose |
|---------|---------|
| keepalive-spaces | Ping all 6 HF spaces every 30min |
| nba-daily-odds | Fetch NBA odds daily |
| autonomous-cycle | Main 4h autonomous cycle |
| cross-repo-optimize | Cross-repo optimization |

---

## Telegram Bots

| Bot | Repo | PID | Status | Purpose |
|-----|------|-----|--------|---------|
| @Nomos42Bot | mon-ipad | 8422, 720588 | ALIVE | NBA Brain — predictions, analysis |
| @RGWAbot | rgwa | 8444, 720591 | ALIVE | AI Art Terminal |

Channel: @Nomos42

---

## Running Processes

| Process | Status |
|---------|--------|
| nba_data_server | running |
| nba_daily_odds | running |
| autonomous_cycle | running |
| political_fetcher | running |
| keepalive | running |

Data server endpoints: backtest-results.json (200), bankroll-state.json (200), quant-summary.json (200)

---

## GPU Platforms

| Platform | Status | Best Result | Notes |
|----------|--------|-------------|-------|
| Colab T4 | not_running | ATR 0.21570 (TabICL) | On-demand, best for TabICL |
| Kaggle P100 | ERROR (timeout) | 0.21844 (gen52) | 9h sessions, relaunching |
| Lightning AI | available | — | 22h, SSH credentials in memory |
| Vast.ai | available | — | $0.16/hr, spot instance |
| Modal | idle_peak | — | Serverless GPU |

---

## Storage & Backups

| Item | Location | Size |
|------|----------|------|
| mon-ipad repo | /home/termius/mon-ipad | 70 MB |
| nomos-nba-agent | /home/termius/nomos-nba-agent | 32 MB |
| nomos-political-alpha | /home/termius/nomos-political-alpha | 36 MB |
| rgwa | /home/termius/rgwa | 7 MB |
| nomos-dashboard | /home/termius/nomos-dashboard | 0 MB |

Backup cron: `0 3 * * *` → backup-to-drive.sh (Google Drive)

Database: Supabase (primary: ayqviq paused 402, using pooler: xivvnr)

---

## Alerts

1. CRON MISSING: keepalive-spaces
2. CRON MISSING: nba-daily-odds
3. CRON MISSING: autonomous-cycle
4. CRON MISSING: cross-repo-optimize
5. REPO DIRTY: mon-ipad (18 uncommitted)
6. REPO DIRTY: nomos-political-alpha (277 uncommitted)
7. GPU Kaggle: ERROR (timeout)
8. Colab: not_running

---

## Links

[[README]] | [[00-Dashboard]] | [[01-Architecture]] | [[02-Evolution]] | [[04-Departments]] | [[10-Repos]]
