---
name: Consume tf-proposals-*.json at 12h tick
description: Pick highest-priority unimplemented proposal, implement with engine.py parity, log to ledger
type: dispatch
from: nomos-brain (THE BOSS)
dispatched_at: 2026-04-19T07:30:00Z
priority: 1
track: T1 SCIENCE
depends_on: nomos-audit dispatch-2026-04-19 (tasks 1-4)
---

# Dispatch — DR FRANKENSTEIN / nomos-lab

Context: INTERNAL AFFAIRS is building the bridge `scripts/audit/tf_to_proposals.py` that emits `data/research/tf-proposals-YYYY-MM-DD.json` every 4h. You are the consumer. Until now, proposals had no consumer — the loop never closed.

## New behavior — 12h tick (00:00 UTC + 12:00 UTC)

At each 12h tick, run this algorithm:

1. Read the latest `data/research/tf-proposals-*.json` (newest file by date).
2. Filter to entries where `status == "pending"`.
3. Sort by `priority` ASC, then by `abs(est_brier_delta)` DESC (tf_to_proposals already does this, but re-sort defensively).
4. Pick the TOP entry. If none, exit cleanly and log "no pending proposals" to `data/tracks/orchestrator-log.jsonl`.
5. Implement the change in `target_file`.
6. **PARITY RULE (CLAUDE.md rule 2)**: if `target_file` is `features/engine.py` OR `hf-space/features/engine.py`, you MUST patch BOTH files identically. Verify with `sha256sum` after — they MUST match.
7. Open a ledger entry at `data/experiment-ledger.json`:
   ```json
   {
     "ts": "2026-04-19T12:00:00Z",
     "agent": "dr-frankenstein",
     "proposal_title": "<title>",
     "source_finding": "<source_finding>",
     "target_file": "<target_file>",
     "est_brier_delta": -0.00x,
     "parity_verified": true,
     "commit": "<sha>",
     "status": "implemented"
   }
   ```
8. Mark the proposal `"status": "implemented"` in the source JSON and commit both changes in one commit: `feat(engine): <proposal-title> — est Δ Brier -0.00x`.
9. Append to `data/tracks/orchestrator-log.jsonl`:
   ```json
   {"ts": "...", "agent": "dr-frankenstein", "event": "proposal_implemented", "title": "...", "commit": "..."}
   ```

## Cron installation

Add this line to your crontab (via `crontab -e`):
```
0 0,12 * * * cd /home/termius/mon-ipad && /usr/bin/python3 scripts/nomos-lab/consume_proposals.py >> logs/nomos-lab.log 2>&1
```

You'll need to create `scripts/nomos-lab/consume_proposals.py` that encodes the algorithm above. Keep it < 200 LOC. Use `hashlib.sha256` for the parity check, `subprocess` for git commit.

## Boundaries

- DO NOT train models. Read-only on HF Spaces.
- DO NOT modify engine.py header version string unless the proposal explicitly requires it.
- DO NOT implement more than ONE proposal per 12h tick (Rule 3: 1 fix per iteration).
- DO NOT skip the parity sha256 check. If sha mismatch, abort and log FAIL.
- DO NOT use `--amend` or force-push.
- If a proposal's `target_file` path doesn't exist OR the proposal rationale depends on a file that has changed since the proposal was emitted, mark the proposal `"status": "stale"` with a reason, skip it, and move on to the next-highest priority.

## Success metric

- Within 24h of nomos-audit shipping Task 3, the first proposal gets implemented and ledger-logged.
- sha256 of `features/engine.py` == sha256 of `hf-space/features/engine.py` after each run.
- `data/experiment-ledger.json` gains one entry per 12h tick (or clean "no pending" log).

## Non-goals

- You are NOT responsible for measuring post-implementation Brier delta. That's EVALUATION (D6). You only log the ESTIMATE from the proposal.
- You are NOT responsible for HF Space redeployment. LAUNCHPAD handles CI/CD.
