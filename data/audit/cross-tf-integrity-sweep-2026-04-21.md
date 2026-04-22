# Cross-TF Integrity Sweep — 2026-04-21 14:40 UTC

**Auditor**: INTERNAL AFFAIRS (D6 EVALUATION, L2 APPLICATION)
**Mandate**: Scientific validity (not bankroll performance) across NBA + POL + ITF.
**Constraint**: research-only — no fixes applied this cycle (per user).
**Sources**: HF Hub `data/decisions/day-*.json` latest 3 per fleet, fetched via `scripts/audit/run_audit.py` 14:58:56Z.

---

## Verdict — 4/5 PASSED

| Check | NBA | POL | ITF | PQTF (incl. for completeness) |
|-------|-----|-----|-----|------|
| 1. Look-ahead leakage | OK | OK | N/A (live-dated) | N/A (live-dated) |
| 2. Bet sources | OK | OK | N/A | N/A |
| 3. Win-rate outlier | OK | OK | N/A | N/A |
| 4. Lockstep / Jaccard | **CRITICAL** | OK | N/A (probe) | OK |
| 5. Walk-forward | OK (stub) | OK | N/A | OK |

One CRITICAL, three open low/medium findings (see ALERT.json).

---

## Today's commits — per-change verdict

### SWISH 870168e56 — NBA peak-gate retire
- Read diff. No data-source change. Pure gate logic: `ROGUE_DRAWDOWN_THRESHOLD` recomputed from `ABS_SURVIVAL_FLOOR=$20`, `PEAK_DRAWDOWN_GUARD=0.0` disabled. **Integrity-safe.**
- Side effect visible: day-065 lockstep dropped to 0% (first clean day post-retire) — gate relax lets more agents diverge. Positive signal, but day-062/063 still show 79-100% shared picks, so jitter alone is insufficient.

### PLUMBER 91ddf696e — YouTube sim-date filter
- Verified `_load_prompt_override(fleet, sim_date)` at NBA app.py:153/3235 and POL app.py:140/2593. Both pass `day_date` from the sim loop, NOT `datetime.today()`.
- Ran `scripts/audit/verify_youtube_narrative_leakage.py`: NBA 0/223 post-filter across 178 sim_dates (max pre-filter 222); POL 0/223 across 184 sim_dates (max pre-filter 222). **PASS.**
- ITF + PQTF: untouched by design (live-dated — sim_date == live_date → no filter needed). Confirmed in docstring at app.py:145-148 and 143-148.

### FRANKENSTEIN 58d139379 — ITF v2.7.1 crypto override
- Read full diff. 17 lines added, all prompt text under `_OFF_HOURS_STYLE_BY_TID` for tids `gap-fade-1`, `carry-1`, `breakdown-1`. No `execute_*`, no universe, no data feed touched. Signals still come from Alpaca live-quote path. **Integrity-safe.** ITF being live-dated makes this safe by construction.

---

## The one CRITICAL — NBA lockstep

- **Check 4 (DMAD bypass)**: day-062 79.3% / day-063 100% / day-065 0% shared picks. Same signature as 12:40 audit (day-042 93.8%, day-043 100%, day-044 100%).
- **Class**: groupthink, NOT leakage. All 64 bets `source='direct'`, no forbidden sources, no WR outliers, leakage correlation clean.
- **Hypothesis**: post-SWISH peak-gate retire, day-065 is the first clean day. The blake2b jitter (amp=0.30, 2a067c15e 2026-04-18) isn't enough when the edge universe from S10-S22 tree fleet produces near-identical top-5s and all agents are MIN_DEPLOY=0.75 floored.
- **Related**: audit 12:40 already flagged same class — this is not new; SWISH's retire hints at a partial remediation path.

## Three open low findings

- **NBA walk-forward stub** (run_audit.py:326 hardcoded "ok"). NBA sim dates 2025-10 to 2026-02 unaudited for chronology.
- **run_audit.py ALERT.json schema crash** — 14:40 cron run failed silently on dict-vs-list. Previous YouTube alert used object schema; runner expected list.
- **ITF has no integrity probe** — run_audit.py only audits NBA/POL/PQTF. ITF's 17-persona live-dated surface is untouched by the 4h sweep. Not a leakage risk (live-dated), but blind spot for bet-source / lockstep checks.

---

## Files

- Full audit: `/home/termius/mon-ipad/data/audit/2026-04-21T1440-integrity.json`
- Clone of 14:58 cron result: `/home/termius/mon-ipad/data/audit/2026-04-21T1458.json`
- Active alerts: `/home/termius/mon-ipad/data/audit/ALERT.json` (4 entries — 1 RESOLVED, 1 HIGH OPEN, 2 LOW OPEN)
- YouTube leakage verifier: `/home/termius/mon-ipad/scripts/audit/verify_youtube_narrative_leakage.py`

## Escalation (no action taken — research-only)

- **THE BOSS → SWISH**: NBA lockstep post-peak-gate-retire. Jitter amp may need bump (0.30 → 0.45) or DMAD role assignment per persona.
- **DR FRANKENSTEIN**: wire NBA walk-forward check (games-2025-26.json game_date vs train_cutoff).
- **LAUNCHPAD**: coerce ALERT.json always-list in run_audit.py.
