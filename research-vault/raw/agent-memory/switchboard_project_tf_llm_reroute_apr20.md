---
name: TF LLM Reroute 2026-04-20
description: Six NBA+POL personas rerouted off dead gateway keys (gpt-oss-120b, gpt-4o-mini 429, nvidia-minimax timeout, llama-3.1-8b, nemotron:free slow) to verified-live github: + cerebras: targets
type: project
---

**Live gateway (LBJLincoln26/llm-gateway /api/chat) probe 2026-04-20 14:34 UTC:**

ALIVE fast:
- `cerebras:qwen-3-235b` (144ms), `cerebras:llama3.1-8b` (194ms)
- `mistral:large/medium/small` (280–710ms)
- `google:gemini-3-flash` (2.6s), `google:gemini-2.5-flash` (falls back to 3)
- `nvidia:llama-3.3-70b` (469ms)
- `github:gpt-4.1-mini/nano/llama-3.3-70b/phi-4-mini/mistral-medium` (820–1300ms)

DEAD/TIMEOUT/NOT-IN-REGISTRY (do NOT route primaries here):
- `openrouter:gpt-oss-120b` — `Model not in registry` (silent kill)
- `github:gpt-4o-mini` — `Rate limited (429)` always
- `github:llama-3.1-8b` — not in registry
- `nvidia:minimax-m2.7`, `nvidia:minimax-m2.7-alt` — >20s timeout
- `selfhost:*` (qwen3-4b/gemma-3-4b/qwen3-0.6b/dolphin3/phi-3.5-mini/phi-4-mini) — >20s timeout from gateway
- `openrouter:nemotron-120b:free` — >12s latency, observed 55/99 llm_ok on POL TF

**Reroutes applied** (NBA+POL app.py, deployed via HfApi with `HF_TOKEN_2` = LBJLincoln26 creds; HF_TOKEN_LLM = Nomos42, 403 on LBJLincoln26 spaces):

| persona | was primary | new primary | new fallback |
|---|---|---|---|
| mistral-ministral | openrouter:gpt-oss-120b (not in registry) | github:gpt-4.1-mini | cerebras:llama3.1-8b |
| mistral-nemo (fb) | openrouter:gpt-oss-120b | cerebras:llama3.1-8b (kept) | mistral:medium |
| selfhost-qwen4b | github:gpt-4o-mini (429) | github:phi-4-mini | mistral:small |
| nvidia-minimax | nvidia:minimax-m2.7 (>20s) | github:llama-3.3-70b | nvidia:llama-3.3-70b |
| nvidia-llama70 (fb) | nvidia:nemotron-70b | nvidia:llama-3.3-70b (kept) | github:llama-3.3-70b |
| selfhost-gemma3 | github:llama-3.1-8b | github:mistral-medium | github:gpt-4.1-nano |
| selfhost-qwen06 | github:gpt-4o-mini | github:gpt-4.1-nano | mistral:small (NBA) / mistral:small (POL) |
| selfhost-dolphin3 | github:llama-3.1-8b | github:gpt-4.1-mini | mistral:large |
| nemotron-120b (POL) | openrouter:nemotron-120b:free (slow) | cerebras:qwen-3-235b | mistral:large |

**Why:** 14/17 NBA agents returning FALLBACK_UNIFORM (4 llm_failures, direct_fallback=22). Root cause: primary AND fallback both resolve to keys the gateway registry rejects or times out on.

**How to apply:** Before seeding a new persona, curl `POST /api/chat` with `{"model":"X"}` — if response has `"model_used":null` or timeout, that model is dead. Only route primaries to `github:gpt-4.1-*`, `github:llama-3.3-70b`, `github:phi-4-mini`, `github:mistral-medium`, `cerebras:*`, `mistral:large/medium/small`, `nvidia:llama-3.3-70b`, `google:gemini-3-flash`. AVOID: any `selfhost:*` primary (gateway routing broken per project_selfhost_fleet_reality_apr20), `openrouter:gpt-oss-120b`, `github:gpt-4o-mini`, `github:llama-3.1-8b`, `nvidia:minimax-m2.7*`.

**Deploy path:** `HfApi(token=HF_TOKEN_2).upload_file(..., repo_id="LBJLincoln26/...", repo_type="space")` then `restart_space(factory_reboot=True)`. Verified post-deploy: both Spaces responsive, POL advanced 99→105 days within 90s, NBA reset games_processed to 0 (reboot replayed day 9).
