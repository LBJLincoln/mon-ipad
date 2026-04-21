---
name: ITF Aggressive Mode — 14 personas + digests + bet-freedom (2026-04-20)
description: Major ITF upgrade from 7→14 agents with knowledge/peer/council injection + removed-whitelist bet-freedom. Shipped commits e2f9e5b1a (code) + 2fbb49f4a (scorecard).
type: project
---

## Shipped 2026-04-20 — ITF "most aggressive TF" redesign

**Why:** User asked for the most active TF, max agents + full knowledge + free bet authority + structured collaboration, with one agent hitting $1M fastest. ITF previously had 7 personas, 84% pass rate dominated by "market closed, vol=0" and underlying-whitelist hard-gates.

**How to apply:**
- When working on ITF, personas.py now has 14 entries. New 7 are: arbitrage-1, news-catalyst-1, crypto-whale-1, earnings-gap-1, iv-crush-1, macro-rotate-1, leveraged-momentum-1. All routed at cloud winners (no selfhost: prefix — broken per MEMORY.md selfhost_fleet_reality).
- _build_prompt injects 3 new blocks that are cached per UTC day: `_build_knowledge_digest()` (arxiv top-3 + PQTF proof + NBA/POL lessons + Axelrod canon, ~1600 chars), `_build_peer_bets_digest()` (last 3 days from data/intraday/decisions/*.jsonl), `_format_council_block()` (data/intraday/council_plans/day-XXX.json).
- Milestone council fires at day % 15 == 0 via `run_milestone_council` using cerebras:qwen-3-235b moderator. Persists plan 15 days. env override: ITF_COUNCIL_DAYS.
- DECISION_SCHEMA dropped underlying ticker whitelist — now "ANY ticker visible in the INTRADAY TAPE". Stake floor $100, no hard ceiling (LLM sizes 2-5% bankroll per $1M mission line).
- quote_bus._repair_crypto_change_pct backfills Alpaca crypto chg% from 1Day bars when /latest/quotes returns 0.0 — silent no-op on rate-limit or when chg already set. Silenced 6/7 personas was Alpaca bug, not tape flat.
- Tests: 4/4 `test_build_prompt.py` pass (14 personas × 4 classes × headings + off-hours coverage + signal gate + fallback tag). New `test_quote_bus_crypto_repair.py` — 3/3 pass.
- Deploy recipe: HfApi.upload_file to root (`app.py`, `personas.py`, `test_build_prompt.py`, `quote_bus.py` at root + `scripts/arena/shared/quote_bus.py`) then HfApi.restart_space (NOT factory_reboot). HF_TOKEN_NBA writes to LBJLincoln26.
- Live post-deploy tick 2: 13 trades / 1 pass / 14 decisions — pass rate dropped 84% → 7%. Quote source = alpaca (live).
