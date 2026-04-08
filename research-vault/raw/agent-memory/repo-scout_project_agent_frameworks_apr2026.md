---
name: Agent Frameworks April 2026 Evaluation
description: Scored 9 LLM agent frameworks for Nomos42 bash-driven Karpathy council pattern (9 depts + 5 traders, free HF router, 1vCPU/969MB VM)
type: project
---

Evaluated April 2026. Winner: PocketFlow. Smolagents stays as fallback for tool-calling.

**Why:** Our outer loop is bash (hermes-runner.sh). We need a library, not a runtime. PocketFlow is 100 lines, zero deps, MIT, 10.4k stars — the only framework that imposes zero overhead and respects our bash-owned loop.

**How to apply:** D1 Research gets migrated first as POC. hermes-runner.sh stays. council_d1.py replaces raw requests with PocketFlow Node subclass calling HF Inference Router.

## Scorecard

| Framework | Stars | License | Python | RAM | HF Router | Bash-library | MCP | Verdict |
|-----------|-------|---------|--------|-----|-----------|--------------|-----|---------|
| PocketFlow | 10.4k | MIT | agnostic | ~5MB | Yes (zero-vendor) | YES | manual | **WINNER** |
| smolagents | 14k | Apache 2.0 | 3.10+ | ~80MB spike | YES (HfApiModel) | YES | via tools | HIGH |
| strands-agents | 5.6k | Apache 2.0 | 3.10+ | unknown | via LiteLLM | YES | YES native | MEDIUM |
| Agno | 39k | Apache 2.0 | 3.7+ | 700MB+ startup | YES | YES | not native | LOW (RAM kill) |
| DSPy | 22k+ | MIT | 3.9+ | moderate | YES | YES | YES native | MEDIUM (overkill) |
| mcp-agent | 2k | MIT | 3.10+ | moderate | indirect | YES | YES native | MEDIUM |
| Atomic Agents | 5.8k | MIT | multi | low | via Instructor | YES | NO | LOW |
| PydanticAI | 8k+ | MIT | 3.9+ | low | YES | YES | YES (v1.74) | MEDIUM |
| LangGraph | heavy | MIT | 3.9+ | 200MB+ | YES | NO | via tools | REJECTED |

## Rejected outright
- Agno: 700MB baseline RAM on a 969MB VM = instant kill
- CrewAI, AutoGen, LangGraph, agency-swarm: previously rejected
- strands-agents: AWS-first, LiteLLM bridge adds latency, unclear HF router compat

## Migration plan (if HIGH confirmed)
1. D1 Research POC: `scripts/councils/council_d1_pocketflow.py`
2. Bash stays: `hermes-runner.sh d1` calls `python council_d1_pocketflow.py`
3. State: reads/writes `data/departments/council-d1-research-latest.json` (no change)
4. Nodes: ScanNode → ProposeNode → ExecuteNode → EvaluateNode → KeepRevertNode
5. Each node calls `requests.post(HF_INFERENCE_ROUTER_URL, ...)` directly (no vendor SDK)
6. If POC works, D3 Evolution + D7 Infra next (simplest state shapes)
