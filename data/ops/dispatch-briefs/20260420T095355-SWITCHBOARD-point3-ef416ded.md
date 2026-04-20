# SWITCHBOARD — Point #3: Migrate 4 dead selfhost: routes off Nomos42 (403-saturated)

_Dispatched 2026-04-20T09:53:55Z — severity=3_

**Department:** D7 Infra
**Target file(s):** `LBJLincoln26/llm-gateway + 3 Nomos42 Spaces`

## Why This
Gateway advertises 10 selfhost: routes, only 6 resolve. Nomos42 0/3 live (403 null-quota). Dead: selfhost:phi-4-mini, selfhost:qwen2.5-1.5b, selfhost:qwen3-0.6b, selfhost:smollm3-3b.

## Spec (concrete steps)
1. HfApi.pause_space the 3 dead Nomos42 selfhost Spaces (nomos42-llm-cpu, nomos-cpu-gemma4, fin-r1-7b-cpu)
2. Check LBJLincoln / LBJLincoln26 / TESTforge42 concurrent-Space counts (max 3-4 each tier)
3. Duplicate Qwen2.5-1.5B wheel-build template to TESTforge42 (account has slack)
4. Update gateway model registry: selfhost:qwen2.5-1.5b → testforge42-qwen25-15b URL (revive 503 first)
5. Point selfhost:smollm3-3b at TESTforge42/smollm3-3b-cpu (already exists, restart if 503)
6. Retire selfhost:phi-4-mini + selfhost:qwen3-0.6b routes (no available Space; drop from gateway /api/models)
7. Re-probe: python3 scripts/empire/build_master.py → verify selfhost.live count ≥ 8/9

## Acceptance Criteria
data/ops/selfhost-fleet-probe.json shows LIVE ≥ 8 after next empire regen

## Context
- Full empire ledger: `data/empire/MASTER.md`
- Your per-agent brief: `data/empire/briefs/switchboard.md`
- Dispatch-log: `data/ops/dispatch-log.jsonl`
- Live 3-min intel: `data/ops/tf-intel-latest.json`

## How to Ack
When you start: `git log --author="SWITCHBOARD"` should show your first commit within 24h.
When done: update `data/empire/strategy-scorecard.json` point-3 status → DONE.
