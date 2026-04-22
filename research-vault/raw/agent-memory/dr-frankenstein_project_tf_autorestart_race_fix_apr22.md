---
name: TF auto-restart race-condition fix
description: PLUMBER RCA 2026-04-22 closed — atomic state_lock on /api/run, module Hub pre-seed, while-not-stop loop on both NBA+POL TFs
type: project
---

PLUMBER traced false-positive "hard-wipe" alerts to a ~0.5s race window where keepalive `*/30 /api/run` collided with `_auto_start` daemon. Both entered `run_experiment()`, each reset `_llm_calls=0` before `_load_state_from_disk()` repopulated `_experiment_state`, so `/api/status` briefly returned `running=false, llm_calls=0, fleet_best=$100`. Monitoring loop alerted and keepalive re-kicked, amplifying the cascade.

**Why:** per-season `_llm_calls=0` reset in `run_experiment()` entry + unguarded `/api/run` gate + generator returning `_experiment_running=False` at season boundary = three independent race surfaces.

**How to apply:** Same pattern now applies to any long-running Gradio+FastAPI HF Space where keepalive pings `/api/run`:
1. Guard the running-flag gate with `threading.Lock` — check-and-flip in one critical section BEFORE spawning the daemon.
2. Pre-seed `_experiment_state` at module import time (not inside the generator), so `/api/status` never returns defaults during the uvicorn-bind → first-run window.
3. Wrap `run_experiment()` in `while not _stop_event.is_set(): run_experiment(); sleep(5)` — never drop `running=False` unless user explicitly stops.
4. Move lifetime counter resets (`_llm_calls`) into `/api/reset` only — NEVER into the generator body.

Commit `b3337cfce` (app.py x2) + `77b6da4af` (ledger). HF commits: NBA `c5de7d2241`, POL `6044fabe12`. Deploy token: `HF_TOKEN_2` (LBJLincoln26 owner). Local sha256: NBA `31f82b67101d`, POL `1524ff915e98`. 12 parity markers in each file. Verification: 6min polling (12 samples), NBA 0/12 running-false, POL 3/12 running-false — all 3 explained by actual container rebuild (`src=hub_preseed` served real $920.66 bankrolls, not $100). Multi-season compound continued on POL (182→183).

PQTF is FROZEN FOREVER — do NOT port this fix. ITF has its own app.py tree (`hf-intraday-trading-floor/`) — do NOT port blindly; ITF tick loop differs.
