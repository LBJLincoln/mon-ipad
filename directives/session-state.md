# Session State — 24 Fevrier 2026 (Session 58 continued)

> Last updated: 2026-02-24T17:15:00+01:00

## Current Status: INFRASTRUCTURE READY — 5000q dataset complete, awaiting HF Space fix

### What Changed This Session (Session 58 continuation)

1. **5000q dataset complete** — 5 pipelines x 1000 questions:
   - Standard: 1000 questions (from standard-orch-1000x2.json)
   - Graph: 1000 questions (500 hf-1000 + 500 expansion from musique/2wiki/hotpotqa)
   - Quantitative: 1000 questions (500 hf-1000 + 500 expansion from finqa/tatqa/convfinqa)
   - Orchestrator: 1000 questions (from standard-orch-1000x2.json)
   - PME Gateway: 1000 questions (NEW — 9 categories, FR/EN mix)

2. **Multi-endpoint architecture deployed**:
   - eval/run-eval.py: `_host_for(pipeline)` routes to N8N_HOST_STANDARD, N8N_HOST_GRAPH, etc.
   - Per-pipeline batch sizes (auto mode --batch-size 0): std=10, graph=5, quant=3, orch=2, pme=1
   - Per-pipeline timeouts: std=90s, graph=90s, quant=120s, orch=180s, pme=60s

3. **Per-pipeline API key rotation**:
   - orchestrator.json: Fixed 8 occurrences → OPENROUTER_KEY_ORCHESTRATOR
   - quantitative.json: Fixed 8 occurrences → OPENROUTER_KEY_QUANTITATIVE
   - All 4 core pipelines now use dedicated keys (0 generic OPENROUTER_API_KEY)

4. **GitHub Actions ready**:
   - eval-1000q.yml: 5 parallel jobs (standard, graph, quantitative, orchestrator, pme-gateway)
   - 15 secrets configured on LBJLincoln/mon-ipad
   - Per-pipeline endpoints + keys in workflow env

5. **Automation scripts created**:
   - scripts/session-startup-hook.sh — Auto-displays state at session start
   - scripts/check-protocol-compliance.sh — Validates all CLAUDE.md rules

6. **CLAUDE.md updated**: Rules 21-23 added, multi-endpoint architecture documented

### Dataset Files
| File | Pipelines | Questions |
|------|-----------|-----------|
| datasets/phase-2/hf-1000.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/graph-quant-expansion-500x2.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/standard-orch-1000x2.json | standard(1000), orch(1000) | 2000 |
| datasets/phase-2/pme-gateway-1000.json | pme-gateway(1000) | 1000 |
| **TOTAL** | **5 pipelines** | **5000** |

### Infrastructure State
| Component | Status | Note |
|-----------|--------|------|
| HF Space | **UP (healthz 200)** | But webhooks mixed: orch=200, quant=500, std/graph=timeout, pme=404 |
| VM | **PILOTAGE ONLY** | No eval running, MCP servers active |
| GH Secrets | **15 configured** | All API keys + endpoints set |
| GH Actions | **READY** | 5-pipeline matrix, trigger via workflow_dispatch |
| Codespaces | **AVAILABLE** | rag-tests + data-ingestion |

### Webhook Status (as of 17:06 UTC)
| Pipeline | HTTP Code | Status |
|----------|-----------|--------|
| Standard | 000 | TIMEOUT — needs HF Space activation fix |
| Graph | 000 | TIMEOUT — needs HF Space activation fix |
| Quantitative | 500 | PARTIAL — server error but responding |
| Orchestrator | 200 | WORKING |
| PME Gateway | 404 | NOT ACTIVATED — workflow needs import/activation |

### API Key Status
- 6 of 7 OpenRouter keys working (~120 req/min aggregate)
- Per-pipeline rotation: `$env.OPENROUTER_KEY_<PIPELINE>` in n8n workflows
- All 4 core workflows verified: 0 generic OPENROUTER_API_KEY references

### BLOCKER: HF Space Webhook Activation
The #1 blocker remains: HF Space entrypoint.sh doesn't properly activate workflows after rebuild.
- Standard + Graph webhooks timeout (HTTP 000)
- PME Gateway not imported/activated
- Only Orchestrator webhook responds (200)
- Fix needed in HF Space entrypoint.sh to auto-activate all workflows on boot

### Next Steps (Priority for Next Session)
1. **CRITICAL: Fix HF Space webhook activation** — entrypoint.sh must activate all 9+ workflows on boot
2. **Test Orchestrator with 1000q** — Only pipeline with working webhook (HTTP 200)
3. **Fix Quantitative webhook** — HTTP 500 suggests workflow error, not activation issue
4. **Import + activate PME Gateway** — Workflow JSON exists but not imported to HF Space
5. **Once webhooks working**: Run `python3 eval/run-eval-parallel.py --dataset phase-2 --reset --force --early-stop 15 --all-parallel`
6. **Or trigger GH Actions**: Dispatch eval-1000q.yml workflow for parallel execution
7. **Set up 2nd HF Space** — HF_TOKEN_2 for load distribution across 2 endpoints
