"""
Nomos42 Real LLM Trading Floor — HuggingFace Spaces
====================================================
10 AI agents (real LLM API calls) compete on 1257 NBA games (2025-26 season).
Each agent receives full game context (odds, standings, form, track record)
and REASONS about what to bet. NO hash simulation. Every decision is a real LLM call.

Providers: Cerebras (5 models), Google Gemini, OpenRouter (2), Cohere, HuggingFace
Runtime: ~4-6 hours for full season. Live visualization throughout.

Architecture follows:
  - TradingAgents (arXiv 2412.20138): structured agent reasoning
  - Prediction Arena (arXiv 2604.07355): 1-bet-per-agent validation
  - DMAD (Diverse Multi-Agent Debate): structurally different data views
"""

import gradio as gr
import json
import os
import csv
import time
import requests
import traceback
import io
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Centralised gateway router (vendored into Space; see scripts/arena/gateway_client.py)
from gateway_client import gateway_call as _gateway_call, GATEWAY_URL as _GATEWAY_URL

# Island oracle — bridges TF agents to the island-trained calibrated model (S18).
# Failure-open: if island is down, oracle returns {} and the prompt skips the block.
try:
    from island_oracle import (
        nba_oracle_predict as _island_nba_predict,
        nba_oracle_predict_many as _island_nba_predict_many,
        oracle_block_for_prompt as _island_oracle_block,
    )
    _ORACLE_OK = True
except Exception as _orc_err:
    print(f"[oracle] import failed: {_orc_err}")
    _ORACLE_OK = False
    def _island_nba_predict(*a, **kw): return {}
    def _island_nba_predict_many(games): return [{} for _ in (games or [])]
    def _island_oracle_block(nba_pred=None, pol_pred=None): return ""

# ── STARTUP DIAGNOSTICS ─────────────────────────────────────────────────────
print("=" * 60)
print("NOMOS42 REAL LLM TRADING FLOOR — STARTUP")
print("=" * 60)
for k in ["CEREBRAS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_2",
          "OPENROUTER_KEY_ORCHESTRATOR", "OPENROUTER_KEY_PME", "OPENROUTER_KEY_BARTOLI"]:
    v = os.environ.get(k, "")
    if v:
        print(f"  {k}: {v[:6]}...{v[-3:]} (len={len(v)})")
    else:
        print(f"  {k}: NOT SET")
print("=" * 60)