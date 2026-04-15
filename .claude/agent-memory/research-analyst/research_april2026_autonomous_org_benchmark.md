---
name: Autonomous Org Benchmark April 2026
description: April 14 2026 benchmark of nomos42 vs CORAL/Runway/OASIS/CrewAI — brutal audit of council freshness and feedback loop gaps
type: project
---

nomos42 autonomous org benchmark completed 2026-04-14.

**Why:** User asked if 9 councils + 10-agent TF + 20 islands is better than Paperclip/Runway/Mirofish/SOTA papers.

**Key findings:**

1. CORAL (arXiv:2604.01658, Apr 3 2026, MIT+NUS) is the closest real SOTA analogue to what paperclip-runner.sh tries to do. CORAL has: persistent shared memory, heartbeat-based agent health, isolated evaluator process.

2. Runway AI = video generation company. No published agent org architecture. Not a relevant benchmark.

3. Mirofish (OASIS) = fully vendored at vendor/oasis/ but ZERO integration. Dead dependency.

4. Council freshness Apr 14: only 2/9 councils fresh (D3+D6), both from analyze-trading-floor.py lightweight script, NOT hermes-runner. D1+D2 have stall_streak=13 (likely DNS/Tailscale issue).

5. THE CORE GAP: brier_proxy.py returns CONSTANT output (same file between refreshes). Paperclip keep/revert is therefore always verdict=no_op. The entire Paperclip loop is disabled.

6. Observation → actuation gap: D6 knows mistral-ministral has calibration_gap=0.299 but nothing posts to /api/mutate. D3 produces keyword correlations but nothing triggers HF island config change.

**How to apply:** When user asks about council health or autonomous loop status, the honest answer is: instrumentation works, actuation is broken. Two fixes unblock everything: (a) fix brier_proxy to use rolling holdout, (b) wire analyze-trading-floor.py → HF /api/mutate.

Key papers from Apr 2026:
- CORAL 2604.01658 — autonomous multi-agent evolution with heartbeat health monitoring
- Self-Optimizing MAS 2604.02988 — self-play prompt optimization
- Deep Researcher Agent 2604.05854 — zero-cost monitoring (log reads), Leader-Worker
- AgentRxiv 2503.18102 — shared preprint server for agent labs, 11.4% improvement
- AVO — replace fixed mutation with agent-decided variation operators
- Prediction Arena 2604.07355 — DMAD anti-groupthink for trading agents
