---
title: Nomos42 Qwen2.5-0.5B CPU
emoji: 🪶
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
hardware: cpu-basic
license: apache-2.0
---

# Nomos42 Qwen2.5-0.5B CPU

Pure FastAPI OpenAI-compatible inference server for **Qwen2.5-0.5B-Instruct** (GGUF Q4_K_M, ~400 MB) running on HF Spaces free CPU tier. Used by the Nomos42 trading floor and llm-gateway as a fast, zero-quota self-hosted fallback.

- `GET  /` -> `{model, ready, ...}`
- `GET  /v1/models`
- `POST /chat/completions` (OpenAI schema)
- `POST /v1/chat/completions` (OpenAI schema)
