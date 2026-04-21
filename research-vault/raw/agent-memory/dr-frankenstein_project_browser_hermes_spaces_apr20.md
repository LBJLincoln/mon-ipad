---
name: Browser + Hermes HF Spaces shipped
description: 3 new docker Spaces across 3 accounts for browser-use scraping, pixel/dashboard QA, and Hermes RPC orchestration
type: project
---

Shipped 2026-04-20 per HAWKEYE proposal `data/research/hermes-browser-agents-2026-04-20.md`.

**Spaces deployed** (all LIVE, /api/status returned 200):
- `LBJLincoln/nomos-browser-nba` (browser-use 0.12.6 NBA line scraper)
- `TESTforge42/nomos-browser-qa` (Playwright + browser-use for pixel/dashboard QA)
- `LBJLincoln26/nomos-hermes-agent` (NousResearch/hermes-agent CLI + FastAPI RPC, binary installed from curl script, 71 skills auto-preloaded)

**Why:** HAWKEYE research picked browser-use for scraping (MIT, 88.9k stars, YC W25) and NousResearch/hermes-agent for orchestration (MIT, 95.6k stars, v0.10.0 2026-02-25). Expected Brier impact −0.002 to −0.005 via new line-movement features; revenue protection via weekly dashboard + pixel QA; ~40% orchestration speedup via Hermes skill learning.

**How to apply:**
- Dockerfile gotcha: `mcr.microsoft.com/playwright/python:v1.49.0-noble` already has `pwuser` at UID 1000. Do NOT add `useradd -m -u 1000 user` — it fails with "UID 1000 is not unique" and the whole build errors. Reuse `pwuser` instead.
- Hermes install script writes to `/dev/tty` during `hermes setup` wizard (non-interactive) — this prints a warning but does NOT fail the build. The `hermes` binary still lands in `~/.local/bin/hermes` and the RPC server finds it.
- Setting Space secrets via `HfApi.add_space_secret(repo_id, key, value)` works without a restart prompt — but a factory_reboot is still needed for the running container to pick them up on next boot.
- `/data` is NOT writable on HF Docker Spaces by default (permission error); my app.py + hermes_rpc_server.py fall back to `/tmp/<service>/` and flag `persistent_data=false` in `/api/status`. For persistence, either upgrade the Space to `cpu-upgrade` with attached persistent storage, or periodically rsync `/tmp/.../history/` out via HfApi.

**Wiring:**
- `scripts/agents/nba_line_scraper_client.py` — cron-friendly VM client → `data/lines/YYYY-MM-DD.json`.
- `scripts/agents/pixel_qa_client.py` — triggered by `.github/workflows/pixel-qa.yml` on push to `scripts/arena/hf-pixel-world/**`.
- Hermes has no wired cron client yet (queued: Hermes as cross-dept orchestrator per proposal workflow #4).

**Next blockers for user:**
- Add `ANTHROPIC_API_KEY` to LBJLincoln/nomos-browser-nba + TESTforge42/nomos-browser-qa (primary LLM path; currently Gemini-only fallback).
- Add `NOUS_API_KEY` and `OPENROUTER_API_KEY` to LBJLincoln26/nomos-hermes-agent so Hermes has a working LLM provider chain.
- Optional: add `BROWSERUSE_API_KEY` (ChatBrowserUse free community tier, 3-5x faster than LLM-driven).
