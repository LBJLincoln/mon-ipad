---
title: Nomos42 Karpathy Arena
emoji: 🏀
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: "5.49.1"
app_file: app.py
pinned: false
---

# Nomos42 Karpathy Arena

Autonomous Karpathy iteration loop + Arena simulator running continuously on HF Spaces.

- **Tab 1 — Karpathy Loop**: Mutates model configs, trains on synthetic NBA data, keeps improvements. Targets Brier < 0.20.
- **Tab 2 — Arena Simulator**: 11 strategies × 6 models × full season. ROI, Sharpe, drawdown leaderboard.
- **Tab 3 — Metrics**: Live iteration stats, improvement rate, best config JSON.

Self-contained — no VM, no external APIs required.
