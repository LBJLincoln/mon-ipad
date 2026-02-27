# Key Routing + Metrics Snapshot

Timestamp (UTC): 2026-02-27T13:52:00Z

## OpenRouter key pool discovered
- OPENROUTER_API_KEY
- OPENROUTER_KEY_STANDARD
- OPENROUTER_KEY_GRAPH
- OPENROUTER_KEY_QUANTITATIVE
- OPENROUTER_KEY_ORCHESTRATOR
- OPENROUTER_KEY_PME
- OPENROUTER_KEY_SPARE

Total active keys: 7
Assumed limit/key: 20 req/min
Aggregate theoretical LLM capacity: 140 req/min

## Pipeline→key bindings in workflows
- Standard: `OPENROUTER_KEY_STANDARD`
- Graph: `OPENROUTER_KEY_GRAPH`
- Quantitative: `OPENROUTER_KEY_QUANTITATIVE`
- Orchestrator: `OPENROUTER_KEY_ORCHESTRATOR`
- PME: `OPENROUTER_KEY_PME` (gateway/action depending flow)
- Ingestion/bench utils: often `OPENROUTER_API_KEY` fallback

## Throughput math
Assuming 1/1/3/2 LLM calls per question for Standard/Graph/Quantitative/Orchestrator.

If a single pipeline consumes all 140 req/min:
- Standard: 140 q/min
- Graph: 140 q/min
- Quantitative: 46.7 q/min
- Orchestrator: 70 q/min

If 4 pipelines share equally (35 req/min each):
- Standard: 35 q/min
- Graph: 35 q/min
- Quantitative: 11.7 q/min
- Orchestrator: 17.5 q/min

Target 1000 q/min for all 4 pipelines in parallel:
- Required LLM req/min ≈ 7000
- Equivalent keys @20 req/min each ≈ 350 keys

## LLMlite/LiteLLM status
- Installed in dedicated venv: `/home/termius/mon-ipad/.venv-litellm`
- Binary available: `.venv-litellm/bin/litellm`
- Next step: configure router with weighted model pool + per-pipeline budgets + request logs.
