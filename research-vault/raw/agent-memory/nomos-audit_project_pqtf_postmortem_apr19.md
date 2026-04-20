---
name: PQTF post-mortem + proposal bridge (2026-04-19)
description: PQTF analytics format, proposal bridge wiring, cron slots installed
type: project
---

PQTF post-mortem extended in tf_postmortem.py with --fleet pqtf (and --fleet all alias). TF-to-proposals bridge created at scripts/audit/tf_to_proposals.py. Commit 46ad6f3f7.

**PQTF HF Space data format (LBJLincoln26/political-quant-trading-floor):**
- Day files use `agents_start`/`agents_end` dicts + `sessions` list (NOT `agents` dict like NBA/POL TF).
- Fresh restart days have all bankrolls at $600 flat — filter with `abs(total_end - total_start) > 0.01`.
- Local analytics at `data/tf-analytics/pqtf/day-*.json` is the primary source (richer: per_agent, per_bet, fleet Jaccard).

**Proposal bridge output:** `data/research/tf-proposals-YYYY-MM-DD.json` — max 10 entries, deduped against yesterday's file by 60% title-word overlap.

**Cron slots installed:**
- `40 */6` — `scripts/arena/tf_postmortem.py --fleet pqtf` → `logs/tf-postmortem-pqtf.log`
- `45 */4` — `scripts/audit/tf_to_proposals.py` → `logs/tf-to-proposals.log`

**Why:** THE BOSS dispatch required the analysis→implementation loop that was missing. DR FRANKENSTEIN reads the proposals file to pick implementation targets.

**How to apply:** When PQTF data shows no positions (all $600), it means the Space was reset — local analytics cache is the only source of finished-run data until new snapshots accumulate.
