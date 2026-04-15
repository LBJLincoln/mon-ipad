---
title: Nomos42 Gemma-3-4B-it CPU
emoji: 💎
colorFrom: yellow
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
hardware: cpu-basic
license: apache-2.0
---

# Nomos42 Gemma-3-4B-it CPU

OpenAI-compatible inference for **Gemma-3-4B-it** (GGUF Q4_K_M, ~2.5 GB).
Matches Gemma-2-27B-IT on chat/math/IFEval. 128K ctx. Strong tool-calls.

- `GET  /` → `{model, ready, ...}`
- `POST /v1/chat/completions`
