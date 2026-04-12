---
title: Nomos42 LLM
emoji: 🏀
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
hardware: cpu-basic
license: mit
---

# Nomos42 LLM — Self-Hosted Trading Floor Agent

OpenAI-compatible inference server running on HF Spaces free CPU tier.
Provides fallback LLM inference for Nomos42 NBA/Political trading floor agents.

## Model

Default: **Qwen3-1.7B Q4_K_M** (~1.2 GB GGUF)

Options (set via Space env vars):
- `Qwen/Qwen3-0.6B-GGUF` / `qwen3-0.6b-q4_k_m.gguf` — 0.5 GB, ultra-small
- `Qwen/Qwen3-1.7B-GGUF` / `qwen3-1.7b-q4_k_m.gguf` — **1.2 GB, recommended**
- `HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF` / `smollm2-1.7b-instruct-q4_k_m.gguf` — 1.1 GB
- `bartowski/Llama-3.2-1B-Instruct-GGUF` / `Llama-3.2-1B-Instruct-Q4_K_M.gguf` — 0.8 GB
- `microsoft/Phi-4-mini-instruct-GGUF` / `Phi-4-mini-instruct-q4.gguf` — 2.5 GB

## API

```bash
# Health check
curl https://YOUR-SPACE.hf.space/health

# Chat completion (OpenAI-compatible)
curl -X POST https://YOUR-SPACE.hf.space/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-1.7B",
    "messages": [
      {"role": "system", "content": "You are an NBA betting analyst. Respond only with valid JSON."},
      {"role": "user", "content": "Should we bet on Lakers vs Celtics tonight? Return {\"bet\": bool, \"confidence\": float}"}
    ],
    "max_tokens": 256,
    "temperature": 0.3
  }'
```

## Wire into api_pool.py

```python
# In PROVIDERS dict:
"self_hosted_cpu": ProviderConfig(
    name="self_hosted_cpu",
    base_url="https://YOUR-SPACE.hf.space",
    models=["Qwen/Qwen3-1.7B"],
    rpm=5,           # CPU is slow — 1 req per 10s is realistic
    rpd=500,
    is_free=True,
    timeout=120.0,   # CPU inference can take 30-60s for 512 tokens
    max_tokens=512,
),
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_REPO` | `Qwen/Qwen3-1.7B-GGUF` | HF repo containing the GGUF file |
| `MODEL_FILE` | `qwen3-1.7b-q4_k_m.gguf` | GGUF filename within the repo |
| `MODEL_DISPLAY` | `Qwen/Qwen3-1.7B` | Display name returned in API responses |
| `N_CTX` | `2048` | Context window size |
| `N_THREADS` | `2` | CPU threads (HF free = 2 vCPU) |
| `MAX_TOKENS` | `512` | Default max tokens per response |

## Hardware Requirements

| Tier | RAM | Model max size | Recommended |
|------|-----|----------------|-------------|
| CPU Basic (free) | 16 GB | ~10 GB GGUF | Qwen3-1.7B Q4 or SmolLM2-1.7B |
| CPU Upgrade ($9/mo) | 32 GB | ~24 GB GGUF | Gemma-3-12B Q4 or Llama-3.2-8B Q4 |

## Performance (CPU Basic, 2 vCPU)

| Model | Size | Load time | Speed | Quality |
|-------|------|-----------|-------|---------|
| Qwen3-0.6B Q4 | 0.5 GB | ~5s | ~20 tok/s | Low |
| SmolLM2-1.7B Q4 | 1.1 GB | ~8s | ~12 tok/s | Medium |
| Qwen3-1.7B Q4 | 1.2 GB | ~10s | ~12 tok/s | Medium-High |
| Llama-3.2-1B Q4 | 0.8 GB | ~6s | ~15 tok/s | Medium |
| Phi-4-mini Q4 | 2.5 GB | ~20s | ~8 tok/s | High |
