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

## Agents

| Agent | LLM Backend | Provider | Personality |
|-------|------------|----------|-------------|
| Gemma Analyst | Gemini 2.5 Flash | Google | Analytical |
| Qwen Strategist | Qwen 3 235B | Cerebras | Diversified |
| Claude Sentinel | Llama 3.3 70B | Cerebras | Conservative |
| Llama Vanguard | Llama 3.3 70B | OpenRouter | Aggressive |
| Mistral Maverick | Llama 3.1 8B | Cerebras | Contrarian |
| DeepSeek Quant | DeepSeek R1 70B | Cerebras | Quantitative |
| Phi Theorist | Phi-4 | OpenRouter | Theoretical |
| Command Tactician | Command R+ | Cohere | Tactical |
| Gemma Arbitrageur | Gemma 3 27B | HuggingFace | Arbitrage |
| Mixtral Ensemble | Llama 4 Scout | Cerebras | Ensemble |

## What This Proves

After running through the full season (~4-6 hours), the experiment reveals:
- Which LLM backbone makes the best betting decisions
- Whether personality/strategy affects profitability
- Which bet categories (ML, spread, totals) are most profitable
- How different risk tolerances perform across a full season

## Architecture

Based on: TradingAgents (arXiv 2412.20138), Prediction Arena (2604.07355), DMAD
