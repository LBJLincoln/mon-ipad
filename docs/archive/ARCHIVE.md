# Archived Scripts

Dead / orphan scripts moved out of live paths so future agents and lore readers
don't confuse them with active components. Files are preserved verbatim (just
renamed to encode their original path with hyphens) in `docs/archive/scripts/`.

## Log

- **scripts/gpu-burst/colab-nba-burst.py** (archived 2026-04-16) — manual Colab only per CLAUDE.md, no active cron/Action reference; only caller was `compute-orchestrator.py` which itself is not in the VM crontab.
- **scripts/gpu-burst/kaggle-nba-burst.py** (archived 2026-04-16) — Kaggle separately managed (STALE since Mar 28 per CLAUDE.md); only caller was `compute-orchestrator.py` which is not in the VM crontab.
- **scripts/gpu-burst/hf-inference-eval.py** (archived 2026-04-16) — claimed "dispatched by compute-orchestrator" but neither `compute-orchestrator.py` nor `zerogpu-burst.py` actually reference it; only live mention was a comment in `scripts/setup-crons.sh`.
