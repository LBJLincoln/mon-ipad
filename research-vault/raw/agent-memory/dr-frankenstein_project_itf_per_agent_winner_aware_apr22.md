---
name: ITF per-agent winner-aware prompts (17 personas, tier-keyed)
description: 2026-04-22 — _WINNER_AWARE_ADDENDA dict (17 tids) + _compute_agent_tier + _tier_directive injected into _build_prompt AFTER DEAD_TAPE so every persona gets router-aware role doctrine + live-tier directive each tick
type: project
---

# ITF per-agent winner-aware system prompts — 2026-04-22

## What shipped
- Added `_WINNER_AWARE_ADDENDA: Dict[str, str]` with 17 persona entries (every
  tid in `personas.py`) in `scripts/arena/hf-intraday-trading-floor/app.py` just
  after `_OFF_HOURS_STYLE_BY_TID`. Each entry = static role + router name + asset-
  class specialization ("you are the ITF MOMENTUM lead, router=mistral:large — PQTF
  $244K #1 winner…"). Routers cite memory [feedback_itf_follow_winners_apr19.md].
- Added `_compute_agent_tier(tid, seed_share, total_equity, reserved) -> str`
  returning `winner|deployer|holder|idle|loser`. Thresholds: winner>1.10×seed,
  loser<0.90×seed, deployer=reserved/total≥0.25, idle=reserved==0, else holder.
- Added `_tier_directive(tier, total_equity, seed_share) -> str` producing the
  dynamic line appended under the static addendum (e.g. `TIER: ACTIVE-DEPLOYER
  (equity $5,935, -0.1%). Tighten edge bar to ≥0.03…`).
- Hooked into `_build_prompt` AFTER the DEAD_TAPE branch — so addenda always land
  regardless of regime. Uses `executor.get_bankroll(tid)` + `executor._load_positions()`
  + `_load_bankrolls()['_meta']['seed_share_usd']` to classify live each tick.
- Fail-open: if executor state lookup raises, static addendum still injected with
  `TIER: (unavailable: ...)` — prompts never crash.

## Why now
- User: "per-agent winner-aware system prompts across ITF's 17 personas"; all 17
  were seeded identically at $5,943.90 and currently ride the same generic
  `persona["style"]` — no reflection of provider reliability or per-agent state.
- Reserved-utilization is the only LIVE conviction proxy today because broker-fill
  reconciliation is still catching up (0 realized PnL across all 17; see
  [project_itf_compound_fix_apr22.md]).
- AXELROD_CANON / COLLECTIVE_MISSION / DEAD_TAPE_CLAUSE / CRYPTO_PIVOT_CLAUSE all
  untouched — only `style_final` gets appended to. No edits to personas.py.

## Routing decisions (baked in per persona)
- mistral:large (PQTF $244K #1): momentum-1, mean-rev-1, vol-1, options-1, iv-crush-1
- mistral:medium (PQTF $155K #2): scalper-1, pairs-1, crypto-whale-1, leveraged-momentum-1
- cerebras:qwen-3-235b (2000 tok/s): news-catalyst-1, earnings-gap-1, gap-fade-1
- github:gpt-4.1-mini/nano (post-reroute stable): breakout-1, arbitrage-1
- github:llama-3.3-70b: carry-1
- github:mistral-medium: breakdown-1
- selfhost:phi-4-mini: macro-rotate-1 (only selfhost — macro is weekly timeframe, latency OK)

## Deploy
- HF SHA: `614dbb19e1a3b4f7b93d140cee593dab96bc515a`
- factory_reboot=True via HfApi (Space: `LBJLincoln26/intraday-trading-floor`)
- git commit: `92364a4a2` (via `scripts/lib/safe_commit.sh FRANKENSTEIN ...`)
- Parity: same app.py bytes pushed to HF + repo

## Preserved
- 20s budget guard on `refresh_broker_statuses` (from earlier today)
- tick_count RCA diagnostic (id(STATE)/pid/thread)
- AGGRESSIVE DIVERT pool
- ITF_STAKE_FLOOR_PCT=0.33 Space var
- executor.py MIN_HOLD_SEC=900 (broker-level churn guard)
- AXELROD_CANON / COLLECTIVE_MISSION / DEAD_TAPE_CLAUSE / CRYPTO_PIVOT_CLAUSE

## Not touched (per task constraints)
- NBA + POL TF files (parallel agents)
- overrides.json
- executor.py
- personas.py (all changes are in app.py only)

## Next observable
- When broker-fill reconciliation catches up, equity will diverge from $5,943.90
  → tier will auto-re-classify from IDLE/HOLDER/DEPLOYER → WINNER/LOSER. No prompt
  redeploy needed. That's the whole point: the dict is static, the tier is live.
