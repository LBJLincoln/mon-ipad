---
name: PQTF post-mortem + improvement-proposal bridge
description: Extend tf_postmortem to pqtf, build tf_to_proposals bridge, wire into cron
type: dispatch
from: nomos-brain (THE BOSS)
dispatched_at: 2026-04-19T07:30:00Z
priority: 1
track: T1 SCIENCE
---

# Dispatch — INTERNAL AFFAIRS / nomos-audit

Context: PQTF completed 50/50 days (2.34×, $600K → $1.4M fleet). POL + NBA TF also finished 50-day runs. Post-mortem showed 7/10 top single-day winners were "tier-pad: 37 events" lockstep artifacts — now killed in commit `482698f34` (2026-04-19). User correctly flagged that the new departments v3 (T1 SCIENCE in particular) should have analyzed the finished run and proposed improvements automatically. That loop is MISSING.

## Your mission (4 concrete tasks)

### Task 1 — extend `scripts/arena/tf_postmortem.py` to support `--fleet pqtf`

Current state: script supports `--fleet nba|pol|both` only. PQTF day files live in the HF Space `LBJLincoln26/political-quant-trading-floor` (pull via `huggingface_hub.hf_hub_download` or the Space's `/api/logs` endpoint — read-only, use `HF_TOKEN`).

Deliverables:
- Add `pqtf` branch to the existing CLI. Output file: `data/tf-analysis/pqtf-report.md`.
- Report must include:
  - Leaderboard (all 6 derivatives day-traders, final bankroll, peak, drawdown).
  - Peak-day rationale quotes (parse `rationale` field from day-XXX.json).
  - Top gainers / top losers by day.
  - **Multi-leg strategy usage breakdown** — vertical / iron_condor / straddle / butterfly (count + PnL contribution each). Engine records these in each position record.
  - Sharpe ratio per agent (daily returns).
  - Drawdown distribution (max DD, time-to-recover).
- Keep the NBA/POL output format intact. Don't break `--fleet both`.

### Task 2 — extend the 6h cron

Current cron line (verified):
```
40 */6 * * * cd /home/termius/mon-ipad && /usr/bin/python3 scripts/arena/tf_postmortem.py --fleet both >> /home/termius/mon-ipad/logs/tf-postmortem.log 2>&1
```

Add a second line immediately after (or change `both` to a new `all` alias that covers nba+pol+pqtf):
```
40 */6 * * * cd /home/termius/mon-ipad && /usr/bin/python3 scripts/arena/tf_postmortem.py --fleet pqtf >> /home/termius/mon-ipad/logs/tf-postmortem.log 2>&1
```

Install via `crontab -e`. Do NOT wipe any existing lines.

### Task 3 — build `scripts/audit/tf_to_proposals.py`

This is the MISSING BRIDGE from analysis → DR FRANKENSTEIN implementation queue.

Inputs (all already exist):
- `data/tf-analysis/nba-report.md`
- `data/tf-analysis/pol-report.md`
- `data/tf-analysis/pqtf-report.md` (produced by Task 1)
- `data/audit/ALERT.json` (latest audit alerts)
- `data/tf-analytics/summary.json` (per-agent/category/bet stats written every 4h :45)

Output: `data/research/tf-proposals-YYYY-MM-DD.json`

Exact schema:
```json
[
  {
    "title": "Short action name",
    "rationale": "Why this helps (cite source finding)",
    "target_file": "features/engine.py | scripts/arena/hf-*/engine.py | etc.",
    "est_brier_delta": -0.001,
    "priority": 1,
    "source_finding": "Concrete quote or stat from report/audit",
    "status": "pending"
  }
]
```

Priority rules:
- 1 = lockstep/leakage/calibration fix (scientific integrity)
- 2 = Brier-reducing feature or calibration improvement (est_brier_delta ≤ -0.001)
- 3 = PnL-improving strategy (TF fleet-level)
- 4 = diversification / anti-groupthink
- 5 = cosmetic / logging

Emit at most 10 proposals per run. Dedupe against yesterday's file (don't re-emit pending items already present). Sort by priority ASC then by `abs(est_brier_delta)` DESC.

### Task 4 — wire `tf_to_proposals.py` into the audit cron

Current audit cron line:
```
40 */4 * * * cd /home/termius/mon-ipad && /usr/bin/python3 scripts/audit/run_audit.py >> data/audit/cron.log 2>&1
```

Add immediately after:
```
45 */4 * * * cd /home/termius/mon-ipad && /usr/bin/python3 scripts/audit/tf_to_proposals.py >> data/audit/cron.log 2>&1
```

The 5-minute gap ensures audit ALERT.json is fresh when the bridge reads it.

## Boundaries

- DO NOT modify engine.py files yourself. Propose only — DR FRANKENSTEIN implements.
- DO NOT call LLM providers. This is pure scripted analysis.
- DO NOT restart any HF Space. Read-only via HF_TOKEN.
- When done, commit to `main` with message prefix `feat(audit): ` and push. Update `data/health-status.json` is NOT your job — nomos-brain does that on next cycle.

## Success metric

Next 6h cron run produces:
- `data/tf-analysis/pqtf-report.md` (new file, ≥1 KB, contains the 6 PQTF agents by name)
- `data/research/tf-proposals-2026-04-19.json` (new file, 1-10 proposals, valid schema)

Report completion back to nomos-brain via a one-line entry appended to `data/tracks/orchestrator-log.jsonl`.
