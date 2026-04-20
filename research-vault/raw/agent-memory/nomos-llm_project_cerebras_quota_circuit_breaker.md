---
name: Cerebras quota exhaustion — window circuit breaker
description: Cerebras qwen-3-235b regularly exhausts hourly free-tier quota (196+ NBA + 203+ POL failures). Fix: time-windowed circuit breaker in provider_health.py.
type: project
---

Cerebras free tier (30 RPM, hourly quota) exhausts under dual-TF load. When quota is gone, every call returns 429, the old consecutive-failure counter kept re-arming every 5 min (CIRCUIT_COOLDOWN=300), and agents emitted "pass" instead of bets.

**Fix deployed 2026-04-19 (commit efdddd5e1, HF commits 249a926 / 05377f3e):**
- `scripts/arena/hf-llm-trading-floor/provider_health.py` (sha256-parity with POL)
- Added `_apply_window_breaker()`: tracks failure timestamps per provider in a 30-min rolling window (WINDOW_SECONDS=1800). When ≥3 failures fire in that window, opens circuit for WINDOW_COOLDOWN seconds.
- `PROVIDER_WINDOW_COOLDOWN["cerebras:qwen-3-235b"] = 3600` — 1h, matching Cerebras hourly quota reset.
- `EMERGENCY_POOL["L"]` reordered: `mistral:large` promoted to head so T1 (qwen-quant) + T2 (qwen-arb) immediately land on mistral-large-latest when Cerebras is tripped.
- `record_success()` clears `_failure_ts` so a transient spike doesn't permanently poison the breaker after quota resets.
- `get_snapshot()` now exposes `window_breaker` dict for audit.

**Confirmed live:** both TFs show `window_breaker: cerebras:qwen-3-235b: failures_in_window=3, skip_until=~3600s` within minutes of deploy. `mistral:large` is the next fallback once its short consecutive cooldown (~255s) clears.

**Why:** The consecutive-only breaker (threshold=3, cooldown=300s) was too aggressive at re-arming — every 5 min it retried Cerebras which was still quota-exhausted. With 17 agents × 2 TFs this caused ~400 wasted API calls per hour and agents sitting idle.

**How to apply:** When adding future providers with hourly/daily quota limits, add their key to `PROVIDER_WINDOW_COOLDOWN` in provider_health.py with the appropriate cooldown.
