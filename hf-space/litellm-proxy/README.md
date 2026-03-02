---
title: Nomos LiteLLM Proxy
emoji: ⚡
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# Nomos LiteLLM Proxy

API key pooling proxy for Multi-RAG pipeline.
Pools 7 OpenRouter + 2 Groq keys for ~200 RPM combined.

## Endpoints

- `POST /chat/completions` — OpenAI-compatible chat
- `GET /health` — Health check
- `GET /model/info` — Available models

## Models

- `llama-70b` — Llama 3.3 70B (OpenRouter + Groq)
- `gemma-27b` — Gemma 3 27B (OpenRouter)
- `trinity` — Trinity Large (OpenRouter)
- `llama-70b-groq` — Llama via Groq only
