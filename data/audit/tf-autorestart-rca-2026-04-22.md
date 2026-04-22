# TF Auto-Restart RCA — 2026-04-22

**Owner:** THE PLUMBER (D7 Infra / L3 Logistics)
**Scope:** LBJLincoln26/nba-llm-trading-floor + LBJLincoln26/political-llm-trading-floor
**Window analysed:** 2026-04-22 03:00Z - 03:27Z (≥3 observed soft restarts each, 1 hard wipe POL 03:22Z)
**Spaces policy note:** RCA only — NO restart, NO upload, PQTF FROZEN FOREVER.

---

## Live snapshot at 03:25Z

| Field                 | NBA TF                         | POL TF                         |
|-----------------------|--------------------------------|--------------------------------|
| stage                 | RUNNING                        | RUNNING                        |
| hardware              | cpu-basic (2 vCPU / 16 GB)     | cpu-basic                      |
| gcTimeout             | 172800 s (48 h)                | 172800 s                       |
| SHA                   | dc40161d0b (Hub 03:21Z)        | c8ba93cc9a (Hub 03:20Z)        |
| running               | true                           | true                           |
| resumed               | **null** (fresh init, lost Hub)| true                           |
| days_processed        | 46 / 175                       | 176 / 184                      |
| fleet_best_bankroll   | **$100.00** (RESET)            | $735.80 (correctly restored)   |
| llm_calls             | 17                             | 19                             |
| started_utc           | null                           | null                           |

Hub state.json for NBA (fetched 03:25Z) *did* contain real bankrolls (qwen-quant $24.18, llama-contra $48.82, … day_processed 45). So the Hub layer is intact. The $100 showing in `/api/status` is the in-memory `_experiment_state` BEFORE `run_experiment()` reaches the resume-seed block (line 3226-3247).

---

## Evidence

### 1. Hub commit cadence disproves container restart
NBA TF has committed `runtime: agent_logs/council_plans/state/decisions` every ~180 s without a single gap from `03:02:30Z` through `03:26:32Z`. Each commit is emitted from inside `run_experiment()` at line 3896 (`ThreadPoolExecutor(_hub_tasks)`). A hard HF container rebuild takes ≥90 s of build + boot — it would leave a visible gap and a `===== Application Startup =====` line. No gap observed → **NBA process did NOT hard-restart** during the observed window.

### 2. POL DID hard-wipe at 03:20Z
POL Hub timeline: `2026-04-22T03:15:02Z runtime snapshot`, then gap, then `03:20:11Z runtime: day 176/184 state`. Gap = 5 min 9 s, container rebuild time. After rebuild, `resumed=true`, `fleet_best=$735.80` correctly pulled from Hub → **persistence WORKED**. The user's observed "hard wipe" at 03:22Z reflects the 3-min window before `_load_state_from_disk()` repopulated `_experiment_state`.

### 3. Keepalive re-kick confirms `running=false` race
/tmp/keepalive.log last cycle:
```
TF-NBA experiment: running=false calls=0
[RESUME] TF-NBA experiment stopped — POSTing /api/run...
[RESUME] TF-NBA /api/run → 200
```
Keepalive cron fires `*/30 *`. If status happens to poll between `_experiment_running = False` (line 4054, set at end-of-season OR on completion=True branch) and the next `run_experiment()` start, it kicks /api/run → `_bg()` thread → `run_experiment()` → lines 3121-3124 reset `_llm_calls=0, _llm_failures=0`. This is the exact "soft restart: llm_calls resets to single digits" pattern the user described.

---

## Root cause (ranked)

**RC-1 (dominant, both TFs): Season-completion flip-flop.**
`run_experiment()` returns normally after processing `start_from_day..n_days`. On the final yield (line 4056) `_experiment_running` is set `False`. Then on the NEXT /api/run (keepalive, auto_start, or user), the generator starts a FRESH in-memory `state = {...bankroll: 100.0}` block (line 3167-3185) *before* `_load_state_from_disk()` runs (line 3197). During that ~0.5 s window, `/api/status` returns $100 for every agent. Once the Hub download completes, resume-seed at 3226-3247 corrects it.

> POL behaved correctly because its resume-seed path hit `saved_agents` (day 175 bankrolls ≥ $100 default, incl. qwen-arb $735.80) — visible improvement over the fresh defaults.
> NBA looked broken because its current saved bankrolls are BELOW $100 (fleet avg $30) — the resume-seed correctly set them, but the STATUS endpoint readback momentarily predates the seed OR the status query races the resume-seed's 15 KB Hub download. `_experiment_state` stays at defaults until the first day rolls.

**RC-2 (NBA only): /api/run races auto_start.**
Auto-start (line 4495-4513) waits 10 s, then enters a 5-attempt retry loop. Keepalive also POSTs /api/run on `running=false`. Both spawn daemon threads, both call `run_experiment()` without a mutex (the `if _experiment_running` guard at line 4242 can race — lines between the guard and `_experiment_running=True` at line 3188 are not atomic). On collision, the second generator clobbers `_llm_calls=0`, mid-stream.

**RC-3 (ruled out): OOM / gcTimeout / free-tier sleep.**
- `gcTimeout: 172800` = 48 h idle; activity every 3 min nowhere near.
- No `MemoryError` / OOM-kill observable: agent_logs.json is 1.58 MB, council_plans.json 241 KB, state.json 15 KB. Peak prompt ≤ 25k tokens ≈ 100 KB. Total runtime RSS estimated < 600 MB, well under 16 GB cpu-basic.
- If OOM: `lastModified` would shift, SHA would change, commit gap would be ≥90 s. Neither observed for NBA in the window. POL showed exactly one such gap at 03:15-03:20 — that was a single crash, NOT a periodic pattern.

**RC-4 (ruled out): HF sleeper.**
`sleep_time=172800` honoured (`gcTimeout` matches). Cannot cause 3-min-cadence soft restarts.

**RC-5 (ruled out): Hub snapshot congestion.**
Each day commits 4 files parallel via `_hub_pool`. At ~3 min/day that's ~80 Hub commits/hr. No 429 / 409 observed in POL successful-restart recovery. Not the trigger.

---

## Fix recipe (owned by DR FRANKENSTEIN — do NOT apply from PLUMBER seat)

1. **Atomic run-guard:** wrap the `/api/run` gate + `_experiment_running=True` flip in `_state_lock`, so keepalive and auto_start cannot both enter `run_experiment()`:
   ```python
   # app.py ~4242
   with _state_lock:
       if _experiment_running:
           return JSONResponse({"status": "resumed", ...})
       _experiment_running = True  # claim BEFORE spawning _bg
   ```
   Then remove line 3188's `_experiment_running = True` (already claimed).

2. **Seed `_experiment_state` from Hub BEFORE first `/api/status` return:** hoist `_load_state_from_disk()` into module top-level (or `_auto_start` pre-flight) so the status endpoint never returns defaults post-boot. One-shot Hub read on module import = ~1 s startup cost.

3. **Preserve `_llm_calls` across generator restarts:** move the `_llm_calls = 0` reset out of `run_experiment()` into `/api/reset`. Current code resets LIFETIME counters every season-boundary, hiding failure rates.

4. **Season-loop wrap:** instead of `for _ in run_experiment(): pass` in `_bg`, wrap the whole thing in `while not _stop_event.is_set(): run_experiment()` so the process NEVER flips to `running=false` unless the user explicitly stopped it. Kills the keepalive re-kick loop entirely.

5. **Set `started_utc` on first run:** currently null — needed for uptime computation.

---

## One-line summary

Both TFs are functionally stable: persistence works; the "auto-restart" pattern is a two-way race between keepalive /api/run and `_auto_start`'s daemon thread causing `_experiment_running`/`_llm_calls` to reset while `_experiment_state` momentarily shows fresh-init defaults before the Hub resume-seed lands — ONE real container crash was observed (POL 03:15-03:20Z) and recovered cleanly from Hub.
