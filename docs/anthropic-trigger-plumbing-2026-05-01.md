# Anthropic Cloud Brain — Trigger Plumbing Audit (2026-05-01)

**Question:** Le tool 15×/jour proposé par Anthropic est-il adapté au projet, et agit-il vraiment ou juste publie ?

## Architecture two-tier (per CLAUDE.md ll. 26-40 + scripts/autonomous-cycle.sh header)

```
[ANTHROPIC HOSTED]              [REPO]                         [VM cron]
trig_01BS3ix...EemcgD  --►  health-status.json  --►  scripts/autonomous-cycle.sh
(decides + recommends)       (publication of recs)        (reads + ACTS)

   "every 4h at :00"             rec text payload                "every 1h at :30"
                                                                 Reads recs, calls
                                                                 HF /api/config,
                                                                 restarts spaces,
                                                                 git push picks
```

**Conclusion design:** the cloud brain is BY DESIGN a publish-decisions step; the VM cron is the actor. Together they ACT. Neither alone does. So the user's worry "il publie pas il agit" is half right — the cloud brain alone publishes; the closed loop only acts if the VM muscle is alive AND reads the recs AND takes effect.

## Where the trigger lives

| Artifact | Location | Mutable from this repo? |
|---|---|---|
| Trigger ID `trig_01BS3ixBvt2uKHY9p5EemcgD` | Anthropic claude.ai/code Triggers UI (server-side) | No |
| Cron expression "every 4h at :00" | configured at the trigger UI on Anthropic side | No |
| Trigger prompt (what the brain is told to do per cycle) | configured at the trigger UI on Anthropic side | No |
| `health-status.json` (publication target) | repo root | Yes — but it's the OUTPUT not input |
| VM cron `scripts/autonomous-cycle.sh` | repo + crontab on VM | Yes |

**Implication:** I cannot edit the trigger configuration from this codespace. To inspect / modify cadence (e.g. push to 15/day), the user must open https://claude.ai/code → Triggers → `trig_01BS3ix...`.

## Reality check — what actually fired in the last 30 days

Source: `git log --since="30 days ago" --author="noreply@anthropic.com"` and `git log -- health-status.json`

| Source | Cadence declared | Empirical 30d count |
|---|---|---|
| Cloud Brain commits to `health-status.json` | every 4h = 6/day = ~180/30d | 1 commit (Apr 29) — **180× under-firing** |
| `noreply@anthropic.com` commits all-cause | (no formal target) | 8 commits, of which 4 are today's user-initiated session and 4 are AXELROD-CLOUD fire-23/24/25/26/27 patches | 
| VM muscle `[overnight-monitor]` and `[BRAIN]` | hourly VM cron | active and committing every hour — VM side is healthy |

**Diagnosis:** the VM muscle is alive (overnight monitor commits hourly, picks shipped daily, snapshots written on schedule). The cloud brain is silently dead — last `health-status.json` rewrite was 2026-04-29, gap of ~2 days at the time of audit, and before that an even longer gap visible from the commit log.

## When the cloud brain DOES fire, does it ACT?

Yes. Evidence from the most recent published cycles:

```
[BRAIN 20Z]  cross-project proposal: xgboost_brier NBA port + S22 audit + lightning injection gate
[BRAIN 20Z]  health-status: 6-island scan, S18 fleet-best 0.22027, S13 DOWN, S22 anomaly
[BRAIN cycle2 2026-04-29]  diversify S15+S18, research proposal, health-status update
[AXELROD-CLOUD fire-27]  fix stale '10 agents' in council prompts (NBA+POL)
[AXELROD-FIRE26]  build_day_prompt schema parity (full schema + MANDATORY CK audit block)
```

Each of these modified real files: prompts, engine version pins, config payloads. The closed loop demonstrably acts — it just doesn't fire often enough.

`health-status.json[actions_this_cycle]` historical sample (Apr 15 cycle):
- "Political: +Cat45 Market Maker Pre-Positioning (20f) as standalone module"
- "Political: hf-space +Cat37 (same features inline), ENGINE v3.14→v3.15"  
- "NBA: S10-S15 fresh API data (all EVOLVING, stagnation=0)"
- "Political: Alpha-3 RECOVERED from DOWN (gen 10622, brier 0.25223)"

These are real interventions, not telemetry.

## Is 15×/jour "adapté" to this project?

**Yes, architecturally.** NBA games ~10-12 / night; intraday window 13:00-20:00 UTC; political signals daily. The natural rhythm needs:
- 1 cycle pre-tip (16:00-18:00 UTC) — adjust based on day's news/injuries
- 1 cycle post-game (04:00-08:00 UTC) — settle, recalibrate Brier, mutate
- 4-6 cycles intraday during US market hours for ITF (90 min cadence)
- 1 cycle EOD (22:00 UTC) — ledger close, compounding decisions

Sum: ~10-13 cycles/day natural. **15/day Anthropic cap is sufficient with a small no-op guard.** No need for more.

**No, empirically — until plumbing fixed.** The cap is irrelevant if the trigger fires once every 2 days. Pushing 6/day → 15/day on a system that fires <1/day changes nothing.

## Action plan — fix BEFORE bumping cadence

| # | Action | Where | Owner |
|---|---|---|---|
| 1 | Open https://claude.ai/code → Triggers → `trig_01BS3ix...` and check: status (active/paused), last 30d run history, last error | Anthropic UI | user only — I have no access |
| 2 | Verify the trigger isn't out of credit / over rate-cap on the user's Anthropic plan | Anthropic UI | user only |
| 3 | If trigger is live but runs are no-ops, add a guard at top of the prompt: `if no anomalies on /api/status AND no new data since last cycle, write health-status.json with {actions: []} and exit fast — don't burn the slot on busywork` | Anthropic trigger prompt | user (edit the trigger prompt) |
| 4 | Add a heartbeat check: if `health-status.json` git-mtime > 6h, `scripts/autonomous-cycle.sh` should log a warning and post to Slack/Telegram | `scripts/autonomous-cycle.sh` | this repo |
| 5 | Once 6/day is reliably firing AND acting, bump cadence to "every 90 min during 13:00-22:00 UTC + 1 cycle at 04:00 UTC = 7 active windows × 2 cycles = 14/day" — fits 15-cap | Anthropic UI | user, after #1-#4 done |

## Heartbeat patch — repo-side (deliverable from this audit)

I'll add a freshness alarm in `scripts/autonomous-cycle.sh` so the next time the cloud brain stops firing, the VM logs a clear warning instead of silently using stale recommendations. See companion patch `scripts/ops/cloud_brain_heartbeat.py` (committed in same PR).

## TL;DR

- **The brain ACTS, doesn't just publish** — but it acts via the VM muscle reading the publication. Together they're a closed loop. The publication step is *real* science output (Cat45 added, engine version bumped, islands diversified, prompts patched).
- **15/day is the right ceiling for this project.** Don't bump higher.
- **The bottleneck is reliability, not cadence.** The 4h-:00 trigger fired ~1 cycle in the last 14 days where it should have fired ~84. Fix that on Anthropic's UI side, then 15/day will be more than enough.
