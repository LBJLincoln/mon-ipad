"""
Nomos42 Real LLM Trading Floor — HuggingFace Spaces
====================================================
10 AI agents (real LLM API calls) compete on 1257 NBA games (2025-26 season).
Each agent receives full game context (odds, standings, form, track record)
and reasons about what to bet. Full 2025-26 season.

Architecture: TradingAgents (arXiv 2412.20138) + DMAD anti-groupthink
Axelrod mechanisms A/B/C for day-end common knowledge broadcast.
"""