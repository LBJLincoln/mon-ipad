---
name: POL TF ceiling 184→304 dates + stub-regression save (2026-04-22)
description: LOBBYIST shipped the 304-day dataset extension AND caught that commit 5f223b12ee had truncated app.py to a 792-byte docstring stub that would brick the Space on next rebuild. Restored 178KB engine from 96fa88f385.
type: project
---

Day of the qwen-arb $3,119 ATH getting eclipsed. User directive 2026-04-22 ~13:20Z: "destroy the ceilings of all for perfect."

**Why (root cause):**
- Prior `apr19 184-day extension` had ceiling baked at event-date count; Multi-season compounding carries bankrolls across cycles but visible day counter always resets at 184.
- Additionally, commit `5f223b12ee` on 2026-04-22 overwrote `app.py` with a docstring-only 792-byte stub. Live Space still running from cached image (RUNNING_BUILDING state), but next rebuild would have bricked. Had to fix BEFORE extending.

**How to apply:**
- When "extend TF horizon", first probe live app.py size via `raw/<sha>/app.py`. If it's a stub, that's the REAL emergency.
- Extension recipe: `backfill_form4_extend.py` (SEC, 2025-01-02 → 2025-06-30, 10 req/s, UA required) + `backfill_prices_h1.py` (yfinance, 37 tickers, ~125 bars/ticker for H1) → `build_full_dataset.py` auto-unions via `form4_*.json` glob. Result: 184 → 304 unique dates, 2153 → 3597 events.
- Upload `data/political_events.json` to Space; multi-season seed-carry (`app.py:2494-2505`) preserves champion bankroll across rebuilds.
- 368 target not achievable without consolidated_events Fed-rule / exec-order H1-2025 backfill (not automated). 304 is +65% ceiling lift.

**Fingerprints:**
- HF app.py restore: commit 6742f83e876d
- HF events extend: commit 9ba9ecf48257
- mon-ipad git: d71ea56c7
- qwen-arb during op: $2,511 seed → $3,790 ATH day 24 of cycle 2

**Preserve across sessions:** `_AGENT_KELLY_OVERRIDE` dict (`app.py:827-841`), AGENT_SYSTEM_PROMPTS block (`app.py:849+`), state.json day-24 checkpoint. Do NOT `/api/reset`.
