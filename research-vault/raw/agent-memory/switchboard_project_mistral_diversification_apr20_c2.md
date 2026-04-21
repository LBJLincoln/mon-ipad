---
name: TF Mistral Diversification Cycle 2 (2026-04-20)
description: Gateway fallback-chain rebalance to reduce mistral:medium substitution dominance. Added cerebras:qwen-3-235b and github:mistral-medium to front of mistral:large chain; swapped mistral:medium's pos-1 from mistral:small to cerebras:llama3.1-8b.
type: project
---

Problem: cycle-1 monitoring flagged mistral:medium at ~30% of recent fallback substitutions. Root cause: `mistral:large` fallback chain had `mistral:medium` at position 1, so every Mistral-direct 429 auto-hopped to medium (same provider, frequently same-minute rate-limited). `mistral:medium` itself fell first to `mistral:small` (same-provider again), compounding the effect.

Action 2026-04-20 ~17:20 UTC (commit SHA on Space: 3e35a3142f):
```
"mistral:large": ["cerebras:qwen-3-235b", "github:mistral-medium", "google:gemini-3-flash", "mistral:medium", "mistral:small", "selfhost:qwen3-4b"]
"mistral:medium": ["cerebras:llama3.1-8b", "github:mistral-medium", "google:gemini-2.5-flash", "mistral:small", "mistral:large", "selfhost:qwen3-4b"]
```

File: `/home/termius/mon-ipad/scripts/arena/hf-llm-gateway/app.py` lines ~538-546.
Deploy: `HfApi.upload_file` with `HF_TOKEN_NBA` (LBJLincoln26 account), then `restart_space(factory_reboot=False)`.

**Why:** github:mistral-medium is a *separate* quota (GitHub Models Marketplace, not Mistral direct). Cerebras qwen-235b/llama-8b are highest-RPM free providers. Putting cross-provider alts at pos-1 breaks the same-provider cascade.

**How to apply:** next cycle, re-measure mistral:medium share of successful fallbacks via gateway `/api/metrics` or audit logs. Target: <20% over 4h. If still >20%, next lever is reducing personas that use `mistral:medium` as *primary* (T7 mistral-medium in NBA roster) rather than more chain surgery.

DO NOT touch Nomos42 account (403 saturated).
