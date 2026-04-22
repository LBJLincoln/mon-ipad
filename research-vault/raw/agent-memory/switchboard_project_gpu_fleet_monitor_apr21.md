---
name: GPU Fleet Monitor extension
description: SWITCHBOARD probes 5 GPU platforms every 6h at :20, writes data/gpu-burst/gpu-health.json. Paperspace = setup_in_progress until API wired.
type: project
---

GPU fleet monitoring added 2026-04-21 — extends SWITCHBOARD from HF Space only to HF Space + 5 GPU platforms.

**Why:** user asked "all GPUs now running and monitored like the clusters perfectly?" — answer was NO because no agent watched all 5. SWISH/LOBBYIST watch islands; GPUs had nothing.

**How to apply:**
- Probe script: `scripts/ops/gpu_health_probe.py` (observation-only, NEVER restarts).
- Output: `data/gpu-burst/gpu-health.json` (dashboard-consumable — tally {green,yellow,red,stale,setup_in_progress} + per-platform dict).
- Cron: `20 */6 * * * cd /home/termius/mon-ipad && /usr/bin/python3 scripts/ops/gpu_health_probe.py >> /tmp/switchboard-gpu-health.log 2>&1` (parallel to the :20 HF Space cycle).
- Workflow name gotcha: ZeroGPU's `.github/workflows/zerogpu-burst.yml` is registered as display-name **"GPU Compute Burst"** — `gh run list --workflow=zerogpu-burst.yml` 404s; must pass `--workflow "GPU Compute Burst"`.
- Kaggle polling uses `kaggle kernels list -m --page-size 20` (the old `-L N` flag is gone in 2.0.0+); matches on `alexismoret6/nba-karpathy-loop` + `alexismoret6/political-alpha-karpathy-loop`.
- Restarts are explicitly the **user's call** — probe emits `next_action` hints only.
- Kaggle status thresholds are different from daily GH Action workflows (manual 9h sessions): green <48h, yellow <96h, red <168h, stale >168h.

**Fleet state at install (2026-04-21 23:40 UTC):** 3 green (Modal / Lightning / ZeroGPU) + 1 yellow (Kaggle 63-65h stale) + 1 setup (Paperspace). Also fixed CLAUDE.md line 89 which falsely said Kaggle "STALE since Mar 28" — both kernels ran 2026-04-19.
