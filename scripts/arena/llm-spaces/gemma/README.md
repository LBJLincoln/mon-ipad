---
title: Nomos42 Gemma-2-2B CPU
emoji: 💎
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
hardware: cpu-basic
license: apache-2.0
---

# Nomos42 Gemma-2-2B CPU

Pure FastAPI OpenAI-compatible inference server for **gemma-2-2b-it** (GGUF Q4_K_M, ~1.6 GB) on HF Spaces free CPU tier. Used by the Nomos42 trading floor and llm-gateway as a zero-quota self-hosted fallback.

- `GET  /` -> `{model, ready, ...}`
- `GET  /v1/models`
- `POST /chat/completions` (OpenAI schema)
- `POST /v1/chat/completions` (OpenAI schema)
