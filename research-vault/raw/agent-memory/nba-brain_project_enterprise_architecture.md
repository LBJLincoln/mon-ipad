---
name: Enterprise Agent Matrix — 3-product 3-layer architecture
description: Documents the complete 3-layer Forge Factory pattern applied to NBA/Political/RGWA with per-agent single metrics
type: project
---

3-layer enterprise architecture established 2026-03-31.

**Why:** User wants all 3 products (NBA, Political, RGWA) treated as reference implementations of the Forge Factory pattern, each demonstrating the exact same methodology that external Forge users would inherit.

**3 layers:**
- L1: Product Strategy & Creation (Karpathy loop — modify, measure, keep if better)
- L2: Communication & Growth (websites, social, content automation)
- L3: Logistics & Intendance (infra, admin/legal, finance)

**Key docs created:**
- `/home/termius/mon-ipad/docs/executive/07-ENTERPRISE-AGENT-MATRIX.md` — per-product agent map, deployment status
- `/home/termius/mon-ipad/docs/executive/08-SWARM-METRICS.md` — every agent's single metric with thresholds
- `/home/termius/mon-ipad/scripts/agents/swarm-metrics-collector.sh` — auto-collects to data/swarm-metrics.json

**swarm-metrics.json** reads: agent-health.json, bankroll-state.json, latest-eval.json, live-odds.json, engine.py version — no HTTP calls unless forced.

**Engine path:** hf-space/features/engine.py (v3.0-43cat), NOT features/engine.py.

**How to apply:** When asked about swarm health or agent performance, run the collector first (`bash /home/termius/mon-ipad/scripts/agents/swarm-metrics-collector.sh`) then read `data/swarm-metrics.json`.
