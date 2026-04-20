# INTERNAL_AFFAIRS — Point #6: Auto-revert overrides that fail walk-forward gate

_Dispatched 2026-04-20T09:53:55Z — severity=4_

**Department:** D6 Evaluation
**Target file(s):** `scripts/audit/run_audit.py + scripts/arena/prompt_mutator.py`

## Why This
Currently INTERNAL_AFFAIRS flags leakage/outliers but does NOT act. POL $13K leakage ran 3 days before manual wipe. Closed-loop requires auto-revert.

## Spec (concrete steps)
1. Extend scripts/audit/run_audit.py with `_walk_forward_check(fleet)`: compare last-3-day realized WR vs prompt's effective-rule activation date
2. If realized WR drops >20% after a specific prompt_vN activation AND lockstep rises >0.10, flag override as SUSPECT
3. New helper: scripts/arena/revert_override.py (CLI: --fleet nba --revert-to prompt_v2)
4. Audit runs every 4h (existing); suspect → auto-run revert_override.py → commit via safe_commit.sh
5. Emit ALERT.json with reason + reverted_version + realized WR delta
6. Test: manually trigger on POL prompt_v4 post-wipe to verify the revert loop

## Acceptance Criteria
data/audit/ALERT.json showing at least one SUSPECT-then-REVERTED cycle by 2026-04-25

## Context
- Full empire ledger: `data/empire/MASTER.md`
- Your per-agent brief: `data/empire/briefs/internal_affairs.md`
- Dispatch-log: `data/ops/dispatch-log.jsonl`
- Live 3-min intel: `data/ops/tf-intel-latest.json`

## How to Ack
When you start: `git log --author="INTERNAL_AFFAIRS"` should show your first commit within 24h.
When done: update `data/empire/strategy-scorecard.json` point-6 status → DONE.
