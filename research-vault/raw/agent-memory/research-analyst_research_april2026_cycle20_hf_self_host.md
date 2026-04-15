---
name: HF Self-Host LLM Expansion — April 2026 Cycle 20
description: ZeroGPU H200 vs CPU GGUF vs HF Inference Providers router for Trading Floor expansion; new model releases April 2026; quota math for 1925-call season
type: project
---

HF self-host options ranked by practicality for Trading Floor (1925 calls/season):

1. **HF Inference Providers router** (BEST, ship today): InferenceClient routes to Novita/Together/Fireworks/Groq via HF_TOKEN. No new Space. New models: Gemma-4-31B-it (Together), Kimi-K2-Instruct (Groq/Novita), MiniMax-M2.5 (Fireworks), Qwen3-32B (Groq), DeepSeek-V3.2-Exp (Novita). Cost ~$0.40/season.

2. **ZeroGPU H200 Space** (2h deploy): Half H200 70GB, 25min/day PRO quota. 3 accounts = 75min/day. Season = 96min total GPU time, ~$2.10 overage. CRITICAL: vLLM INCOMPATIBLE (issue #3510 closed not-planned). Must use transformers pipeline + @spaces.GPU decorator. Best model: google/gemma-4-26B-A4B-it (MoE, 4B activated, ~50GB BF16).

3. **CPU GGUF Space** (free): 16GB RAM, 2 vCPU. Max 13B Q4_K_M = ~8GB. ~30s/call. 1925 calls = 16h wall time. Good for async overnight agent, not real-time season replay.

Key models to add (not in current 11-agent roster):
- google/gemma-4-26B-A4B-it — MoE 26B/4B active, 256K ctx, multimodal
- moonshotai/Kimi-K2-Instruct — 32B active / 1T total MoE, SOTA agentic
- MiniMaxAI/MiniMax-M2.5 — 10B active / 230B total, SWE-bench 80.2%
- deepseek-ai/DeepSeek-V3.2-Exp — latest DeepSeek, Novita cheapest
- Qwen/Qwen3-32B — dense 32.8B, thinking mode, Groq fast

**Why:** OpenRouter free tiers hit 429 across 3 keys Apr 14. HF router is the fix.
**How to apply:** Wire HF Inference Providers as fallback in llm-gateway before OpenRouter; deploy ZeroGPU Space for dedicated Gemma4 slot.
