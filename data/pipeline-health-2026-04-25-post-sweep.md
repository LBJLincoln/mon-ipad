# Pipeline Health — Post-Sweep 2026-04-25

**Owner:** THE PLUMBER
**Timestamp:** 2026-04-25T17:37:15Z
**Rollup:** HEALTHY (3/3 TFs parity, all SLAs met, zero alerts)

## TL;DR

- **NBA TF**: PASS — content sha matches local. Caveat below.
- **POL TF**: PASS — exact sha match.
- **ITF**: PASS — exact sha match. Tick age 33s.
- **Audit sync**: PASS — last sync 9 min old.
- **Data sources**: PASS — odds 11h (SLA 12h), political 18h (SLA 24h).

## Per-TF parity

| TF | Local sha256 | Remote sha256 | Match | Latest HF commit |
|---|---|---|---|---|
| NBA `app.py` | `02551868be...4fd240c` | `02551868be...4fd240c` | YES | `dde81aa654cb` "engine-only mode + fallback singleton (e60cc5707)" 17:28:58Z |
| POL `app.py` | `913508301d...0207b7f6` | `913508301d...0207b7f6` | YES | latest after Kelly tune `0dc2f7a60089` |
| ITF `executor.py` | `1af2569dcd...c558096` | `1af2569dcd...c558096` | YES | exec at `887084205bd4` (fleet_dir_cap_skip) |

### NBA chronology caveat

Expected HF sha was `57907ff2c24e...` (sorted-edges + reliability tier). Actual latest is `dde81aa654cb` (engine-only mode + fallback singleton, which DR FRANKENSTEIN shipped same-day after the dispatch). Local HEAD includes that commit (`e60cc5707`), so the local-vs-remote sha256 still matches. Newer commits on `main` (`3e12c90c...`) are runtime state-file commits (decisions/runtime json), not `app.py` changes.

### NBA cache-bust note (worth recording)

First fetch of `/resolve/main/app.py` returned a stale CDN redirect with sha `41c4a21f...` that did NOT contain the engine-only mode code — looked like a mismatch. Re-fetching with cache-bust + pinning to commit `3e12c90c...` directly returned the actual content sha `02551868be...` matching local. The HF redirect cache can lag. Future sha audits should pin to commit hash (`/resolve/<sha>/<file>`), not `main`, when freshness is critical.

## Day-loop freshness

| TF | Latest day | Date | Written at | Age | SLA |
|---|---|---|---|---|---|
| NBA | 39/111 | 2025-11-30 | 17:30:10Z | 7 min | < 15min OK |
| POL | 110/304 | 2025-06-16 | 17:34:23Z | 3 min | < 15min OK |
| ITF | tick | live | 17:34:07Z | 33 sec | < 90sec OK |

## ITF /api/llm-leaderboard distribution

8/17 agents returned (multi-worker LB sampling artifact). Distribution shows expected primary routing:

```
mistral:large           1
mistral:medium          1
cerebras:qwen-3-235b    1
github:mistral-medium   1
github:gpt-4.1-nano     1
github:llama-3.3-70b    1
github:gpt-4.1-mini     1
selfhost:phi-4-mini     1
```

Mix is correct (mistral:large/medium + cerebras:qwen-3-235b primaries present). Cannot infer concentration from 8-of-17 sample; full leaderboard would need multi-poll aggregation.

## Audit dashboard sync

- Cron `27,57 * * * *` installed and active.
- Latest dashboard sync mtime: 17:28Z (9.3 min old).
- 8 audit MD files in `nomos-dashboard/public/tf-analytics/audit/`.
- Last 3 dashboard commits all hourly tf-analytics syncs.

## Data sources

- `data/nba-agent/odds-latest.json` — 11.1h old. SLA 12h on game days. Within SLA.
- `nomos-political-alpha/data/polymarket/` — 17.6h old. SLA 24h. Within SLA.
- `data/full-odds-2025-26.json` (the 249-cat version) absent on VM. That file is bundled into the NBA TF Space repo, not mon-ipad. Not a leak.

## Alerts: none.

## Recommendations

- None for SWITCHBOARD — no redeploy needed.
- Future PLUMBER runs: pin HF sha checks to commit hash, not `main`, to avoid CDN redirect false-positives.
