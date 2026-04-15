---
title: Nomos42 Qwen3-4B Instruct CPU
emoji: 🐋
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
hardware: cpu-basic
license: apache-2.0
---

# Nomos42 Qwen3-4B-Instruct CPU

OpenAI-compatible inference for **Qwen3-4B-Instruct-2507** (GGUF Q4_K_M, ~2.5 GB).
Released 2026-04-09, ranked #1 quality/size on free 16 GB CPU tier.

Benchmarks: MMLU-Redux 83.1 · MMLU-Pro 61.4 · IFEval 69.5

- `GET  /` → `{model, ready, ...}`
- `POST /v1/chat/completions` (OpenAI schema)
- `POST /chat/completions`
