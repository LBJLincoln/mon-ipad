---
title: Nomos42 Real LLM Trading Floor
emoji: "\U0001F4B9"
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: "5.23.0"
app_file: app.py
python_version: "3.11"
pinned: true
---

# Nomos42 Real LLM Trading Floor

10 AI agents compete on 1257 NBA games (2025-26 season).
Each agent is a **real LLM** that reasons about odds, standings, form, and track record.

## Agents (verified 2026-04-13)

| # | Agent | Model | Provider | Personality | Risk |
|---|-------|-------|----------|-------------|------|
| T1 | Gemini Flash | gemini-2.5-flash | Google | Analytical | 0.60 |
| T2 | Gemini 3 Flash | gemini-3-flash-preview | Google | Diversified | 0.50 |
| T3 | Qwen 3 235B | qwen-3-235b | Cerebras | Quantitative | 0.55 |
| T4 | Llama 3.1 8B | llama3.1-8b | Cerebras | Contrarian | 0.65 |
| T5 | GLM 4.5 Air | glm-4.5-air | OpenRouter | Conservative | 0.40 |
| T6 | GPT-OSS 20B | gpt-oss-20b | OpenRouter | Aggressive | 0.70 |
| T7 | Gemma 4 26B | gemma-4-26b | OpenRouter | Arbitrage | 0.75 |
| T8 | Nemotron 120B | nemotron-3-super-120b | OpenRouter | Tactical | 0.60 |
| T9 | MiniMax M2.5 | minimax-m2.5 | OpenRouter | Theoretical | 0.35 |
| T10 | Qwen3 80B | qwen3-next-80b | OpenRouter | Ensemble | 0.50 |

## API Endpoints

- `GET /api/status` — progress, running state, agent bankrolls
- `POST /api/run` — start/resume experiment
- `POST /api/stop` — graceful stop after current game
- `POST /api/mutate` — change agent params mid-experiment
- `POST /api/reset` — reset bankrolls to $100
- `GET /api/logs` — per-agent decision log
- `GET /api/leaderboard` — current standings JSON

## Architecture

Based on: TradingAgents (arXiv 2412.20138), Prediction Arena (2604.07355), DMAD anti-groupthink.
