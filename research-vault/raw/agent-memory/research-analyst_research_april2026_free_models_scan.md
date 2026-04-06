---
name: Free Models Landscape April 2026
description: Verified model IDs, providers, free tiers for Gemma 4, Qwen3/3.5/3.6, Llama 4, Mistral Small 4 — council advisor stack
type: project
---

# Free Models for Council Advisors — April 4 2026

## Key Findings

### Gemma 4 (Google, released Apr 2 2026)
- 4 sizes: E2B (2.3B), E4B (4.5B), 26B-A4B (MoE, 4B active), 31B (dense)
- Apache 2.0, 256K context (31B) / 128K context (E2B/E4B)
- HF model IDs: `google/gemma-4-E2B-it`, `google/gemma-4-E4B-it`, `google/gemma-4-26B-A4B-it`, `google/gemma-4-31B-it`
- **NOT available via HF Inference Providers** — weights only as of Apr 4 2026
- Paid on OpenRouter: `google/gemma-4-31b-it` at $0.14/$0.40 per 1M tokens
- **Free via Ollama**: `ollama pull gemma4` (e4b default), `gemma4:26b`, `gemma4:31b`

### Qwen3.6-Plus (Alibaba, released Apr 2 2026)
- IMPORTANT CORRECTION: This is a PROPRIETARY CLOUD MODEL — no open weights
- Previous model ID `Qwen/Qwen3.6-Plus` on HuggingFace does NOT exist
- Free access: OpenRouter `qwen/qwen3.6-plus:free` — 1M ctx, 600 RPM, confirmed active Apr 4 2026
- Capabilities: 1M token context, image/video input, tool use, 78.8 SWE-bench score

### Qwen3.5 (Alibaba, released Feb 16 2026)
- OPEN WEIGHTS on HuggingFace: `Qwen/Qwen3.5-4B`, `Qwen/Qwen3.5-9B`, `Qwen/Qwen3.5-27B`, `Qwen/Qwen3.5-397B-A17B`
- Sizes: 0.8B, 2B, 4B, 9B, 27B, 122B-A10B, 397B-A17B
- Ollama: `ollama pull qwen3.5` (9B default), `qwen3.5:4b`
- Available on HF Inference Providers (together/nebius) for paid use

### Llama 4 (Meta, released Mar/Apr 2025)
- Scout: 17B active / 109B total (16E MoE), Maverick: 17B active / ~400B total (128E)
- HF (gated): `meta-llama/Llama-4-Scout-17B-16E-Instruct`
- **FREE on Groq**: `meta-llama/llama-4-scout-17b-16e-instruct` — 750 tps, 131K ctx, 30 RPM, 1K RPD
- Ollama: `ollama pull llama4:scout` (109B total — needs 64GB+ RAM, NOT for laptop)

### Mistral Small 4 (119B MoE, released Mar 2026)
- HF: `mistralai/Mistral-Small-4-119B-2603`, Apache 2.0
- 256K context, hybrid instruct+reasoning+agentic
- NOT on free HF Inference Provider yet
- Previous Mistral-Small-3.1 still works on HF Inference API

## Best FREE Providers for Council Use

### 1. Cerebras — PRIMARY ADVISOR
- API: `https://api.cerebras.ai/v1/chat/completions` (OpenAI-compatible)
- Token env: `CEREBRAS_API_KEY`
- **Free: 1M tokens/day, 30 RPM, 60K TPM**
- Best model: `qwen-3-235b-a22b-instruct-2507` (235B MoE, 22B active, 1400 tps)
- Also: `qwen-3-32b` (2600 tps — fastest free model in existence), `llama3.3-70b`, `gpt-oss-120b`

### 2. Groq — FAST FALLBACK
- API: `https://api.groq.com/openai/v1/chat/completions` (OpenAI-compatible)
- Token env: `GROQ_API_KEY`
- Best bulk model: `llama-3.1-8b-instant` — **14,400 RPD**, 20K TPM (for council bulk queries)
- Best quality: `meta-llama/llama-4-scout-17b-16e-instruct` — 1K RPD, 30K TPM, multimodal
- Also free: `llama-3.3-70b-versatile` (1K RPD), `qwen-qwq-32b` (60 RPM, 1K RPD)

### 3. OpenRouter :free models — LONG CONTEXT
- API: `https://openrouter.ai/api/v1/chat/completions` (OpenAI-compatible)
- Token env: `OPENROUTER_API_KEY`
- Rate limits: 20 RPM, 200 RPD (free)
- Key models:
  - `qwen/qwen3.6-plus:free` — 1M ctx, 600 RPM (much higher than standard free)
  - `qwen/qwen3-coder-480b:free` — 262K ctx, best free coding
  - `google/gemma-3-27b-it:free` — 131K ctx
  - `mistralai/mistral-small-3.1-24b-instruct:free` — fast tool use
  - `deepseek/deepseek-r1:free` — reasoning
  - `meta-llama/llama-3.3-70b-instruct:free`

### 4. HF Inference API — FALLBACK ONLY
- Free credits: **$0.10/month** — barely enough for testing
- Only ~10K tokens free without PRO ($9/mo = $2.00/month credits)
- Still useful: `microsoft/phi-4` (16K ctx, fast), `mistralai/Mistral-Small-3.1-24B-Instruct-2503`

## Council Advisor Stack Configuration

Updated `scripts/forge/free_models_config.json` and `scripts/forge/free-models-integration.py`:

### Python aliases → (provider, model_id):
```
qwen       → (cerebras, qwen-3-235b-a22b-instruct-2507)   # PRIMARY
qwen_fast  → (cerebras, qwen-3-32b)                        # 2600 tps
llama4     → (groq,     llama-4-scout-17b-16e-instruct)    # multimodal
llama8b    → (groq,     llama-3.1-8b-instant)              # 14400 RPD bulk
llama70b   → (groq,     llama-3.3-70b-versatile)
qwen36     → (openrouter, qwen/qwen3.6-plus:free)          # 1M ctx
gemma3     → (openrouter, google/gemma-3-27b-it:free)
mistral    → (openrouter, mistral-small-3.1-24b-instruct:free)
deepseek   → (openrouter, deepseek/deepseek-r1:free)
phi        → (hf,       microsoft/phi-4)                    # fallback
```

## Errors in Previous Config (corrected)
1. `Qwen/Qwen3.6-Plus` on HF — DOES NOT EXIST (cloud-only model)
2. `google/gemma-4-27b-it` — DOES NOT EXIST (no 27B variant; correct: E2B/E4B/26B-A4B/31B)
3. HF free credits: $0.10/month = ~10K tokens, not "$100K credits/month" as previously noted

**Why**: These corrections prevent silent API failures in council loops. The MODELS dict in free-models-integration.py now maps to verified, working endpoints.

**How to apply**: Always use the Python aliases (qwen, llama4, etc.) — auto-fallback chain handles provider failures transparently.
