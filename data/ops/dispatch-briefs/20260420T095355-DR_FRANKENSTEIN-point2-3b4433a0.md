# DR_FRANKENSTEIN — Point #2: ITF uniform-fallback emitter parity (port from NBA/POL/PQTF)

_Dispatched 2026-04-20T09:53:55Z — severity=4_

**Department:** D1 Research
**Target file(s):** `scripts/arena/hf-intraday-trading-floor/app.py`

## Why This
NBA/POL/PQTF have _fallback_bet emitter (commits efdddd5e1+77a01a839); ITF missing. Silent storage-drops are dominant TF failure mode.

## Spec (concrete steps)
1. Port `_uniform_fallback_order` from scripts/arena/hf-llm-trading-floor/app.py (hash-rotation pattern, 25% slots)
2. ITF version: pick 1 equity + 1 crypto pair from universe, 0.5% position each, 120-min hold
3. Wire into tick_loop after _parse_llm_response returns empty/malformed
4. Emit order_id prefixed `fb_` (fallback) so analytics can segregate
5. Upload via HfApi.upload_file to LBJLincoln26/intraday-trading-floor
6. Verify: next ITF tick without LLM response produces fb_* order, logged to decisions

## Acceptance Criteria
≥1 fb_* order in data/intraday/decisions/ within 24h of deploy if any LLM fails

## Context
- Full empire ledger: `data/empire/MASTER.md`
- Your per-agent brief: `data/empire/briefs/dr_frankenstein.md`
- Dispatch-log: `data/ops/dispatch-log.jsonl`
- Live 3-min intel: `data/ops/tf-intel-latest.json`

## How to Ack
When you start: `git log --author="DR_FRANKENSTEIN"` should show your first commit within 24h.
When done: update `data/empire/strategy-scorecard.json` point-2 status → DONE.
