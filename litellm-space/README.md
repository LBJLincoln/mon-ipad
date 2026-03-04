---
title: Nomos LiteLLM Proxy
emoji: ⚡
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# Nomos LiteLLM Proxy

OpenAI-compatible API key pooling proxy for Multi-RAG pipelines.

## Key Pool

| Provider | Keys | Models |
|----------|------|--------|
| OpenRouter | 7 keys | Trinity, Gemma 27B, Llama 70B, Qwen 235B |
| Google | 1 key | Gemini 2.0 Flash |
| Groq | 5 keys | Llama 3.3 70B Versatile |

**Combined theoretical RPM**: ~200+ (7 OR x 20 + 5 Groq x 30 + Google 15)

## Model Aliases

| Alias | Primary Model | Fallback Chain |
|-------|--------------|----------------|
| `default` | Trinity (7 keys) | Gemini Flash > Groq |
| `fast` | Trinity (7 keys) | Gemma 27B > Gemini Flash |
| `smart` | Llama 70B (7 keys) | Qwen 235B > Gemini Flash > Groq |

## Direct Models

- `trinity` — Arcee Trinity Large Preview (7 keys)
- `gemma-27b` — Google Gemma 3 27B (7 keys)
- `llama-70b` — Meta Llama 3.3 70B (7 OR + 5 Groq keys)
- `qwen-235b` — Qwen 3 235B (7 keys)
- `gemini-flash` — Google Gemini 2.0 Flash (1 key)
- `groq-llama` — Groq Llama 3.3 70B (5 keys)

## Endpoints

- `POST /v1/chat/completions` — OpenAI-compatible chat
- `GET /health` — Health check
- `GET /health/liveliness` — Liveliness probe
- `GET /v1/models` — Available models
- `GET /v1/model/info` — Detailed model info

## Usage

```bash
curl https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions \
  -H "Authorization: Bearer sk-litellm-nomos-2026" \
  -H "Content-Type: application/json" \
  -d '{"model": "default", "messages": [{"role": "user", "content": "Hello"}]}'
```

## Routing

- **Strategy**: usage-based-routing-v2 (least-used key first)
- **Retries**: 5 per request across all keys
- **Cooldown**: 30s on failed key before retry
- **Fallbacks**: Cross-model fallback chains configured
