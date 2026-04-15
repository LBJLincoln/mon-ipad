---
title: Nomos42 CPU Gemma-4 Agent
emoji: 🧠
colorFrom: yellow
colorTo: red
sdk: docker
pinned: false
short_description: Frontier-class CPU LLM agent for Nomos42 Trading Floor
---

# Nomos42 CPU Gemma-4 Agent

Self-hosted Gemma 4 E4B (Q4_K_XL) on free HF CPU Space. Exposes `/api/decide`
for the Nomos42 NBA Trading Floor (`LBJLincoln26/nba-llm-trading-floor`) to
call as agent T12.

First of a planned 4-5 self-hosted CPU LLM agents (Gemma 4 / Qwen 3 / Phi 4 /
GLM 5) — the strategy is **diversity** for DMAD anti-groupthink, not raw alpha.

- Model: `unsloth/gemma-4-E4B-it-GGUF` (UD-Q4_K_XL, 5.10GB)
- Backend: llama-cpp-python on 2 vCPU / 16 GB RAM
- Latency: ~5-12s/call
- Endpoints: `GET /` `GET /api/health` `GET /api/stats` `POST /api/decide`
