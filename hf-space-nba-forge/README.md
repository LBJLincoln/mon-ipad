---
title: Nomos42 NBA Forge
emoji: "\u2699\ufe0f"
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: "5.0"
app_file: app.py
pinned: true
---

# Nomos42 NBA Forge -- Department Karpathy Loops

Autonomous department monitor for the NBA Quant AI prediction system.
Runs 5 department Karpathy loops every 10 minutes on CPU.

## Departments

| # | Department | Purpose |
|---|-----------|---------|
| D1 | Prediction Pipeline | Validate predict_today.py outputs, check freshness |
| D2 | Feature Engine | Monitor engine.py version, feature count, category coverage |
| D3 | Model Evaluation | Track Brier scores across models, walk-forward performance |
| D4 | Data Quality | Check data freshness, missing games, odds quality |
| D5 | Evolution Sync | Sync best configs from 6 HF evolution islands |

## Architecture

- Clones `nomos-nba-agent` at startup via git
- Reads JSON data files (predictions, evaluations, bankroll, odds)
- Polls HF evolution islands (S10-S15) for live status
- Git pulls fresh data every cycle
- NO ML training (CPU-only monitoring space)
