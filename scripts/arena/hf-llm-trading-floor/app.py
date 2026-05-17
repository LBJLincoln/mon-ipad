"""Nomos42 Real LLM Trading Floor — HuggingFace Spaces
=============================================
10 AI agents (real LLM API calls) compete on 1257 NBA games (2025-26 season).
Each agent receives full game context (odds, standings, form, track record)
and REASONS about what to bet. Architecture: TradingAgents (arXiv 2412.20138)
+ DMAD anti-groupthink (2023) + Axelrod-2026 Mechanics A/B/C/D.

Mechanism A: Day-end common-knowledge broadcast (COMMON_KNOWLEDGE[D])
Mechanism B: Sacrificial role reallocation (bottom-3 get forced archetype)
Mechanism C: Per-day post-mortem log (data/arena/axelrod-log/day-N.jsonl)
Mechanism D: Axelrod-python canon strategy advice (axelrod library optional)
"""
This file is managed by cloud-trigger-axelrod-2026. Do not edit on HF Space directly.
See mon-ipad/scripts/arena/hf-llm-trading-floor/app.py for source of truth.
"""