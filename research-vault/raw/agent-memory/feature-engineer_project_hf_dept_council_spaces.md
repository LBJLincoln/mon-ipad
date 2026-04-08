---
name: HF Department Council Spaces Architecture
description: Architecture plan for 9 autonomous dept council Spaces across 4 HF accounts (2026-04-05)
type: project
---

Designed autonomous HF Space council system: 9 dept spaces, 4 HF accounts, free LLM (Cerebras primary).

**Account allocation:**
- LBJLincoln (HF_TOKEN) → D1 Research, D2 Engineering
- LBJLincoln26 (HF_TOKEN_2) → D3 Evolution, D4 Product
- Nomos42 (HF_TOKEN_3) → D5 Business, D6 Evaluation
- Forge42 (HF_TOKEN_FORGE) → D7 Infra, D8 Finance, D9 Cross-Repo

**Space naming:** `{account}/nomos-dept-{d_number}-{dept_name}`

**LLM stack (all free):** Cerebras Qwen3-235B (primary, 1M tokens/day) → Groq Llama4 (fast, 1K RPD) → OpenRouter auto:free (fallback)

**Gemma 4 status:** NOT available free as of 2026-04-05. Use `google/gemma-3-27b-it:free` on OpenRouter. Gemma 4 is weights-only on HF, paid-only on OpenRouter.

**Plan file:** `/home/termius/mon-ipad/scripts/councils/hf-dept-spaces-plan.md`

**Why:** Autonomous always-on councils that scan the 6 evolution islands and propose actions, without burning Claude Code API budget. Karpathy loop pattern in a Gradio Space.

**How to apply:** When user asks about "council spaces" or "dept councils on HF", reference this architecture. D7 Infra is the recommended pilot space. Deployment uses git subtree push with `council-spaces/shared` prefix in nomos-nba-agent repo.
