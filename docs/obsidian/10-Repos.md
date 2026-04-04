---
tags: [repos, ecosystem, codebase, git, nomos42]
date: 2026-04-03
aliases: [Repos, Repositories, Codebase, Ecosystem]
---

# 10 — All Repos

> 5 active repos | 8 ecosystem components | Updated: 2026-04-03T20:00Z

## Ecosystem Map

```
mon-ipad          ──────── Brain / Control Tower
nomos-nba-agent   ──────── NBA Engine (features, models, evolution)
nomos-political-alpha ──── Political Intelligence Engine
rgwa              ──────── AI Art Generation
nomos-dashboard   ──────── Public Dashboard (Vercel)
hf-brain          ──────── HF Space subtree (in mon-ipad)
```

---

## Repo Details

### 1. mon-ipad (Brain)
- **Type:** brain / control tower
- **Path:** `/home/termius/mon-ipad`
- **GitHub:** github.com/LBJLincoln/mon-ipad
- **Status:** ACTIVE | 18 uncommitted changes
- **Last commit:** `data: Trading Floor council iter 203 (tf-iter 281, gen 38216)`
- **Last commit hash:** `ddab08d2`
- **Data size:** 70 MB

**Purpose:** Central intelligence. Houses the cloud brain trigger (Sonnet 4.6 every 4h), all crons, Telegram bots, department councils, Guardian Orchestrator, agent health monitoring, Trading Floor, and all data files.

**Key directories:**
- `scripts/` — all automation scripts (kaggle, councils, agents, infra)
- `data/` — all JSON state files (agent-health, bankroll, departments, arena)
- `features/` — feature engine (must stay in parity with hf-brain)
- `docs/obsidian/` — THIS VAULT
- `logs/` — all operational logs

**Key scripts:**
- `scripts/autonomous-cycle.sh` — main 4h cycle
- `scripts/councils/department-council.sh` — department Karpathy runner
- `scripts/arena/arena-engine.py` — Trading Floor engine
- `scripts/agents/multi-brain.sh` — cloud brain trigger
- `scripts/watchdog.sh` — keepalive watchdog

---

### 2. nomos-nba-agent (NBA Engine)
- **Type:** engine
- **Path:** `/home/termius/nomos-nba-agent`
- **Status:** ACTIVE | 4 uncommitted changes (predictions, value-bets)
- **Last commit:** `evolution: 4 critical fixes — elitism + CatBoost cap + feature penalty + n_splits=3`
- **Last commit hash:** `ae166414`
- **Data size:** 32 MB

**Purpose:** NBA prediction engine. All ML training logic, feature engine, evolution (GA), HF space code, predict_today, backtest, evaluate_predictions.

**Key components:**
- `features/engine.py` — feature engine v3.1-46cat (must match hf-brain)
- `hf-space/` — HF Space source (deployed to all 6 islands)
- `scripts/predict_today.py` — daily prediction runner
- `scripts/evaluate_predictions.py` — post-game evaluator
- `data/nba-agent/predictions-today.json` — latest predictions
- `data/nba-agent/value-bets.json` — Kelly-sized value bets

---

### 3. nomos-political-alpha (Political Intelligence)
- **Type:** engine
- **Path:** `/home/termius/nomos-political-alpha`
- **Status:** ACTIVE | 277 uncommitted changes (lots of data files)
- **Last commit:** `chore: add features/__pycache__ to .gitignore`
- **Last commit hash:** `e293de68`
- **Data size:** 36 MB

**Purpose:** Political alpha signal generation. Tracks congressional trades, FEC donor flows, social signals, crypto as sentiment proxy. Feeds political trading agents.

**Key components:**
- `ops/fetch_political_data.py` — data fetcher (fast/full/insider/prices modes)
- `ops/fetch_social_signals.py` — social sentiment
- `features/` — political feature engine v3.1 (22 categories, 743 features)
- `data/congressional/` — insider trading signals
- `data/donors/` — FEC donor data
- `data/historical/` — price + crypto history

**HF Spaces:** P1_pol (Brier 0.24186, gen 8871) + P2_pol (Brier 0.23134, gen 4104)

---

### 4. rgwa (AI Art Generation)
- **Type:** creative
- **Path:** `/home/termius/rgwa`
- **GitHub:** github.com/LBJLincoln/rgwa
- **Status:** ACTIVE | 0 uncommitted changes | Clean
- **Last commit:** `feat: Add creative Karpathy loop — Forge department structure`
- **Last commit hash:** `fe1f3afe`
- **Data size:** 7 MB

**Purpose:** AI artistic generation. @RGWAbot manages generation, gallery, quality scoring. Forge creative department (D8) runs here.

**Bots:** @RGWAbot (Telegram) — generation, gallery, quality
**Karpathy loop:** generate → quality → curate → publish

---

### 5. nomos-dashboard (Public Dashboard)
- **Type:** dashboard / web
- **Path:** `/home/termius/nomos-dashboard`
- **Deployment:** Vercel (auto-deploy on push)
- **Status:** ACTIVE | 0 uncommitted changes | Clean
- **Last commit:** `feat: add 5 live charts to arena — bankroll, strategies, heatmap, evolution, P&L`
- **Last commit hash:** `75ca5e51`
- **Data size:** 0 MB (Next.js app, no data in repo)

**Purpose:** Public-facing dashboard. Shows NBA predictions, arena, political, infra, forge status.

**Pages:**
- `/` — hub homepage
- `/nba` — predictions + evolution
- `/arena` — Trading Floor + 5 live charts
- `/political` — political alpha
- `/infra` — infrastructure health
- `/forge` — department councils

**Tech stack:** Next.js + Vercel + Tailwind CSS
**Data source:** Reads from mon-ipad git (public data files)

**Note:** NEVER run `next build` / `tsc` on VM — push to Vercel instead

---

### 6. hf-brain (HF Space Subtree)
- **Type:** HF subtree (inside mon-ipad)
- **Path:** `/home/termius/mon-ipad/hf-brain`
- **Status:** submodule / subtree of mon-ipad
- **Deploy:** `git subtree push` to HF Space repos

**Purpose:** HF Space source code for evolution islands. Deployed via subtree push to all 6 NBA islands + 2 political islands.

**Parity rule:** `hf-brain/features/engine.py` must ALWAYS equal `nomos-nba-agent/features/engine.py`

---

## Ecosystem Health Summary (2026-04-03)

| Repo | Commits | Dirty | Last Activity |
|------|---------|-------|---------------|
| mon-ipad | clean | 18 files | 2026-04-03 |
| nomos-nba-agent | clean | 4 files | 2026-04-03 |
| nomos-political-alpha | clean | 277 files | 2026-04-03 |
| rgwa | CLEAN | 0 | 2026-04-01 |
| nomos-dashboard | CLEAN | 0 | 2026-04-03 |

---

## Git Workflow

```bash
# Standard push (all repos)
git add -p && git commit -m "data: description" && git push

# Deploy to HF Space (S10 example)
git subtree push --prefix=hf-brain hf-s10 main

# Check cross-repo health
python3 scripts/cross-repo-monitor.py

# Sync all data
scripts/autonomous-cycle.sh
```

---

## Future Repos (Planned)

| Repo | Purpose | Status |
|------|---------|--------|
| nomos-api | Public API gateway (FastAPI + auth + billing) | PLANNED |
| nomos-mobile | Mobile app (React Native) | BACKLOG |
| nomos-agent-sdk | SDK for building custom trading agents | PLANNED |

---

## Links

[[README]] | [[00-Dashboard]] | [[01-Architecture]] | [[05-Infrastructure]] | [[08-API-Vision]]
