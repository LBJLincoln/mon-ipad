---
name: Multi-Agent Workflow Scan (April 2026)
description: Top repos for orchestration, state management, council debate, monitoring — all no-Kubernetes, low-RAM, cron-compatible
type: project
---

Scan date: 2026-04-07. Full JSON at /home/termius/nomos-nba-agent/data/results/repo-scout-multiagent.json. 6 proposals inserted into Supabase research_proposals.

## Top finds

**atlas-gic (chrisworsey55)** — 1.3k stars. Darwinian agent weight (0.3–2.5, *1.05/*0.95 daily by Sharpe quartile). +22% over 173 days on $20/mo VM. Directly applicable to trading-floor-v4.py traders T1-T5.

**ClawTeam (HKUDS)** — 4.5k stars. JSON/SQLite state, atomic tmp+rename writes, git worktrees per agent, ZeroMQ P2P optional. Has a 7-agent hedge fund TOML template. Fits department-council.sh architecture exactly.

**skfolio** — 1.9k stars, BSD. CombinatorialPurgedCV with built-in purge+embargo+visualization. Drop-in sklearn API. Target: features/cpcv_gate.py.

**autoevolve (MrTsepa)** — Elo/Bradley-Terry for strategy self-play. Use to rate 6 HF islands, route Kaggle compute to highest-Elo island. Expected -0.002 Brier.

**axe (jrswab)** — 783 stars. TOML agent definitions, no daemon, cron-safe, sub-agent nesting, markdown-log memory. Replacement for scripts/opencode/*.sh wrappers.

**Phoenix (Arize-ai)** — 5k stars. SQLite default, self-hosted port 6006, Agent Graph node visualization. 3-line OTLP instrumentation. Fits in 969MB RAM.

## Workflow recommendation

Priority 1: Darwinian weights for trading floor (atlas-gic) — 4h, no Brier impact but ROI impact.
Priority 2: Island Elo + Kaggle routing (autoevolve) — 3h, -0.002 Brier.
Priority 3: skfolio CPCV gate — 3h, -0.002 Brier, also fixes visualization.

**Why:** All three fit on 1vCPU/969MB, use JSON/SQLite, are cron-compatible, and build on existing scripts.
