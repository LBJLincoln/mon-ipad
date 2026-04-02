# Agent 4 — INFRA MANAGER (Factory only)

> Monitors and maintains NBA Quant infrastructure
> Tier: Factory

## Role
24/7 monitoring of 6 HF evolution islands, Kaggle GPU sessions, VM data pipeline, Vercel dashboard, and data freshness.

## Process
1. **Health Checks** — Ping S10-S15 every 30min, verify evolution progress
2. **Auto-Restart** — Detect stalled spaces, trigger rebuild
3. **GPU Management** — Kaggle quota tracking, Colab/Lightning dispatch
4. **Data Pipeline** — Odds freshness, prediction pipeline, git sync

## Key Metrics
- Uptime % (target: 99.5%)
- Restart count, stagnation detection
- GPU hours utilized vs available
