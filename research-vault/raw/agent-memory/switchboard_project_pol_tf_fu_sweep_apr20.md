---
name: POL TF FALLBACK_UNIFORM sweep 2026-04-20
description: 12/17 POL agents on fallback_uniform ≥30% of last 10 days — diversified-primary+2-hop-fallback reroute (v2) + gemma3 v3 swap to cerebras:llama3.1-8b
type: project
---

**Baseline (day 183, 2026-04-20 ~14 UTC):** 12/17 POL agents on FALLBACK_UNIFORM ≥30% of last 10 days. Root cause was NOT dead models (all primaries probed alive) — it was:

1. **Provider concentration.** `cerebras:qwen-3-235b` primary on 3 agents (qwen-quant / qwen-arb / nemotron-120b). One circuit-breaker trip killed 3 agents simultaneously. Gateway's `providers_dead` showed cerebras:qwen-3-235b skipped for 3580s.
2. **Single-hop fallback chains that hit same provider.** e.g. `mistral:large` primary → no fallback defined on 8 agents.
3. **selfhost-gemma3 `llm_ok = 0/71` for 71 days** — `github:mistral-medium` was parseable on synthetic probes but the long Handshake-Axelrod-+-3-factor-template POL prompt either bloated past github context OR routed through a broken path. 100% FU for 10 weeks.
4. **github:gpt-4.1-mini on mistral-ministral:** 41/71 llm_ok (58%) — inconsistent.

**v2 reroute (commit c6c8c132 → 7db3baf2c):** every agent gets a distinct primary + a 2-hop fallback across different provider families.

| agent | v2 primary | v2 fallback | reason |
|---|---|---|---|
| qwen-quant | cerebras:qwen-3-235b | mistral:large | keep (quant lead) |
| qwen-arb | cerebras:llama3.1-8b | mistral:medium | diversify off shared 235B |
| llama-contra | cerebras:llama3.1-8b | mistral:small | new fallback |
| gemini-anl | google:gemini-3-flash | mistral:large | add fallback |
| gemini-tact | google:gemini-3-flash | mistral:medium | add fallback |
| mistral-large | mistral:large | cerebras:qwen-3-235b | add fallback |
| mistral-medium | mistral:medium | mistral:large | add fallback |
| mistral-small | mistral:small | github:gpt-4.1-nano | add fallback |
| mistral-nemo | cerebras:llama3.1-8b | mistral:medium | keep |
| mistral-ministral | github:gpt-4.1-nano | mistral:small | nano faster than mini |
| nemotron-120b | mistral:large | cerebras:qwen-3-235b | demote shared key |
| selfhost-qwen4b | github:phi-4-mini | mistral:small | keep |
| nvidia-minimax | nvidia:llama-3.3-70b | github:llama-3.3-70b | swap order |
| nvidia-llama70 | github:llama-3.3-70b | nvidia:llama-3.3-70b | swap order |
| selfhost-gemma3 (v2) | mistral:medium | github:gpt-4.1-nano | 33% llm_ok only |
| selfhost-gemma3 (v3) | cerebras:llama3.1-8b | mistral:small | proven 9/9 on llama-contra |
| selfhost-qwen06 | github:gpt-4.1-nano | mistral:small | keep |
| selfhost-dolphin3 | mistral:large | github:gpt-4.1-mini | PQTF winner |

**v2 post-reboot result (+9 new days):** 13/17 agents at 89–100% llm_ok. 3 agents at 78% (qwen-arb, mistral-large, mistral-ministral — acceptable, 2-hop fallbacks cover). 1 agent still degraded: **selfhost-gemma3 at 3/9 (33%)** — up from 0/71 but still poor. → v3 swap to `cerebras:llama3.1-8b` primary.

**Audit tripwire:** if post-v3 deploy selfhost-gemma3 stays <85% llm_ok over next 20 days, the bug is NOT provider choice — it's in the `Handshake` Axelrod-block text itself (look at `_axelrod_advice_block("selfhost-gemma3", peers)` output). Probably malformed system_prompt concatenation.

**How to apply this pattern to future reroutes:**
1. Probe every primary at the gateway *while the Space is idle* (burst-rate-limited probes lie).
2. Compute llm_ok delta post-reboot across ≥9 days — hub-committed `day-XXX.json` files lag live state; use the `/api/status` per-agent counters.
3. No more than 2 personas share the same primary.
4. Every persona MUST have a `fallback_provider` in a DIFFERENT provider family from the primary.
5. FU count in `data/decisions/day-XXX.json` is the canonical source; `status.llm_ok / llm_calls` is a leading indicator but undercounts (llm_ok increments even if fallback provider answered, which masks primary-first failures).
