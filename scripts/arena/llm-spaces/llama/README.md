---
title: Nomos42 Llama-3.2-1B CPU
emoji: 🦙
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
hardware: cpu-basic
license: apache-2.0
---

# Nomos42 Llama-3.2-1B CPU

Pure FastAPI OpenAI-compatible inference server for **Llama-3.2-1B-Instruct** (GGUF Q4_K_M, ~800 MB) on HF Spaces free CPU tier. Used by the Nomos42 trading floor and llm-gateway as a zero-quota self-hosted fallback.

- `GET  /` -> `{model, ready, ...}`
- `GET  /v1/models`
- `POST /chat/completions` (OpenAI schema)
- `POST /v1/chat/completions` (OpenAI schema)
