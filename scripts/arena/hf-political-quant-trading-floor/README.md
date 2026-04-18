---
title: Political Quant Trading Floor
emoji: 🏛️
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 5.0.0
app_file: app.py
pinned: false
license: mit
---

# Nomos42 Political Quant Trading Floor

Fork of `political-llm-trading-floor` adding:

- **4 intraday sessions per day** (09:30/12:00/14:30/16:00 ET boundaries)
- **Options derivatives** (calls + puts) priced by Black-Scholes with Greeks
- **Sector ETF routing** — events route to XLF/XLK/XLE/… based on `signal_sector`
- **Event-type IV scaling** — FOMC × 1.60, election × 1.80, insider_trade × 1.00
- **GBM intraday paths** with event-timed jumps (signal_strength × direction_bias)
- **Axelrod coalition pacts preserved** — structural DMAD requires different `reasoning_template`

## Agents (6)

`qwen-quant` · `llama-contra` · `gemini-anl` · `mistral-large` · `mistral-medium` · `mistral-nemo`

Starting bankroll: **$100,000 per agent · $600,000 fleet** · Target: 10× by Nov 3 2026.

## Endpoints

- `GET  /api/status`       — experiment + agents state
- `POST /api/run`          — start (body: `{"max_days": 50}`)
- `POST /api/stop`         — stop signal
- `GET  /api/leaderboard`  — ranked bankrolls + W/L

## Modules

- `engine.py`          — pure engine (no gradio/fastapi). Run `python3 engine.py` for self-test.
- `options.py`         — Black-Scholes pricer + Greeks + implied vol estimator.
- `intraday_paths.py`  — GBM path simulator with event jumps, 4-session sequencer.
- `session_data.py`    — event→session router + sector→ETF mapping.
- `app.py`             — FastAPI + Gradio entry point.

A/B control: `political-llm-trading-floor` (daily event-driven) remains unchanged.
