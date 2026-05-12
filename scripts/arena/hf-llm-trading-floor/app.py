"""
Nomos42 Real LLM Trading Floor — HuggingFace Spaces
====================================================
10 AI agents (real LLM API calls) compete on 1257 NBA games (2025-26 season).
Each agent receives full game context (odds, standings, form, 250+ bet categories)
and reasons about what to bet using a real LLM. Gradio + FastAPI.

architecture: TradingAgents (arXiv 2412.20138) + Prediction Arena (2604.07355)
Axelrod-2026: Mechs A (CK broadcast) + B (sacrificial rotation) + C (post-mortem) + D (coalitions)
"""