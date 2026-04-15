---
title: Nomos42 SmolLM3-3B CPU
emoji: 🪁
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
hardware: cpu-basic
license: apache-2.0
---

# Nomos42 SmolLM3-3B CPU

OpenAI-compatible inference for **SmolLM3-3B** (GGUF Q4_K_M, ~1.9 GB).
128K context, dual think/no-think mode, 6 languages. Released 2026.

MMLU 68.9 · beats Llama-3.2-3B (66.5) · close to Qwen3-4B (69.4)

- `GET  /` → `{model, ready, ...}`
- `POST /v1/chat/completions`
