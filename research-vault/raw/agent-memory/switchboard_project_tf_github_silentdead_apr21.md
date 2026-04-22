---
name: TF github:* silent-dead RCA + v3 reroute (2026-04-21)
description: Why github:* primaries on NBA+POL TRADERS returned llm_ok=0 — gateway fallback_chains empty for github:*, so a single 429 = None content. Reroute to 7 chain-having lanes.
type: project
---

**SWITCHBOARD v3 reroute 2026-04-21** — Root cause of NBA TF 70% bleed (SWISH RCA):

5 NBA agents (mistral-ministral, nvidia-minimax, nvidia-llama70, selfhost-gemma3, selfhost-dolphin3) showed `llm_ok=0, llm_calls=17` → hit UNIFORM_FALLBACK (fabricated-edge echo → lockstep at $44.66/47% WR).

**Why:** Gateway `/api/models` `fallback_chains` dict has **zero entries for github:\***. When NBA called `github:gpt-4.1-mini` with no key or 429, gateway returned `content=None` and agent got 0/17. Lifetime `/api/stats` confirms: every github:* model shows `calls_ok=0 AND calls_fail=0 = NEVER CALLED`. The 2026-04-20 reroute to github:* was wrong — probes had received fallback-content from cerebras but my check `model_used == prov` missed the silent-fallback.

**Gateway ground truth (from `/api/stats` lifetime counters):**
- mistral:medium 95.1% ok (2727 ok) — most reliable
- mistral:small 95.4% ok (272 ok)
- google:gemini-3-flash 69.3% ok
- mistral:large 53.7% ok
- nvidia:llama-3.3-70b 41.4% ok (has chain)
- cerebras:{qwen-3-235b,llama3.1-8b} — heavily 429'd under 17-agent load but fallback-chained
- openrouter:nemotron-120b:free — has chain

**Providers with NO gateway fallback_chain (silent-dead when 429):**
- All github:{gpt-4.1-mini,gpt-4.1-nano,phi-4-mini,llama-3.3-70b,mistral-medium,gpt-4o-mini}
- Any call here returns `content=None` on first 429.

**Fix:** Dropped all 6 github:* primaries + 2 github:* fallbacks across NBA+POL. Concentrated 17 agents onto 7 chain-having lanes. Commit `c243e1643`. SHAs: NBA=78f4748dd32c, POL=77fc4595fcc5.

**When rerouting in the future:** NEVER point at a provider whose fallback_chain is empty in `/api/models`. Always check both `fallback_chains` dict AND `/api/stats` calls_ok count — `model_used` in `/api/chat` response lies about native-vs-fallback routing.

**Don't fix the gateway secrets (GITHUB_TOKEN / MISTRAL_API_KEY etc.):** out of SWITCHBOARD scope — that's LAUNCHPAD. We route around dead lanes, we don't add keys.
