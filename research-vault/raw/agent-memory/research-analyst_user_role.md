---
name: user_role
description: User's role as NBA quant analyst at sports hedge fund, goals, collaboration style
type: user
---

Elite NBA quantitative research analyst at a $1B sports hedge fund. Runs Nomos42 — a 24/7 autonomous NBA prediction AI (architecture v14 as of 2026-03-24).

**Technical depth**: Comfortable with XGBoost/LightGBM/CatBoost internals, Brier score decomposition, isotonic calibration, Kelly criterion. Expects concrete paper citations, specific implementation details, and realistic Brier delta estimates.

**Collaboration preferences**: Wants extremely specific findings — paper titles, author names, Brier deltas, effort hours, which HF Space to run it on. Not interested in vague "consider using X" guidance. Wants prioritized roadmap with cumulative Brier projections.

**Infrastructure**: 6 HF Spaces (evolution islands), VM with 1 vCPU/969MB (ZERO ML on VM), Google Colab for GPU work, Supabase for experiment tracking, Claude Code as orchestrator.

**Decision authority**: Makes all config changes to HF Spaces via POST /api/config. Research output feeds directly into brain decisions.
