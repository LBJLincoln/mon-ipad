"""
Nomos42 Real LLM Trading Floor — HuggingFace Spaces
====================================================
10 AI agents (real LLM API calls) compete on 1257 NBA games (2025-26 season).
Each agent receives full game context (odds, standings, form, track record)
and REASONS about what to bet. NO hash simulation. Every decision is a real LLM 

Providers: Cerebras (5 models), Google Gemini, OpenRouter (2), Cohere, HuggingFa
Runtime: ~4-6 hours for full season. Live visualization throughout.
"""