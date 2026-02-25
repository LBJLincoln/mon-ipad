# Session State — 25 Fevrier 2026 (Session 60)

> Last updated: 2026-02-25T04:15:00+01:00

## Current Status: 3/4 PIPELINES WORKING — Quant FIXED, Orch BLOCKED (Redis)

### Session 60 Progress

1. **CLAUDE.md overhaul** — 27 rules → 15 rules, false rules removed (Rule 8 seq tests), Codespace docs corrected
2. **Chatbot deployed on all 3 sites** — v1 (hardcoded) + v3 (RAG-enhanced) active on HF Space
3. **Quantitative pipeline FIXED** — Root causes:
   - Hardcoded API key in n8n expressions evaluated to NaN (`sk-or-v1-...` parsed as JS subtraction)
   - Supabase Postgres credential had wrong host (`aws-0` → `aws-1`) AND wrong project ref (`kfyrtsmdolgioyxsglbz` → `ayqviqmxifzmhphiqfmj`)
   - Fixed via n8n REST API: PATCH auth headers + create new credential + deactivate/reactivate with POST /activate
4. **Orchestrator diagnosed** — 68-node workflow depends on Redis (6 nodes, 0 credentials assigned). No Redis server on HF Space → hangs indefinitely. Needs architectural simplification.
5. **All workflows Postgres credential updated** — 8 workflows patched with correct Supabase connection
6. **`.bashrc` stale env vars removed** — Old `N8N_HOST=http://34.136.180.66:5678` was overriding `.env.local`
7. **entrypoint.sh fixed** — Corrected Supabase host and user defaults
8. **Folder cleanup** — Deleted obsolete files, consolidated snapshots

### Pipeline Status (verified 03:45 UTC)
| Pipeline | Smoke | Status | Fix Applied |
|----------|-------|--------|-------------|
| Standard | 5/5 PASS | WORKING | Postgres credential updated |
| Graph | 5/5 PASS | WORKING | Postgres credential updated |
| Quantitative | **5/5 PASS** | **FIXED** (was 0/5) | Auth headers + Postgres host + project ref |
| Orchestrator | TIMEOUT | **BLOCKED** | Redis dependency — no server |

### Infrastructure State
| Component | Status | Note |
|-----------|--------|------|
| HF Space #1 | RUNNING | 14 workflows (11 active, 3 inactive) |
| HF Space #2 | BLOCKED | Both HF_TOKEN and HF_TOKEN_2 invalid/expired |
| VM | PILOTAGE ONLY | MCP servers active |
| Supabase | WORKING | Direct connection fixed (aws-1, correct project ref) |

### Workflow Credentials (session 60 new IDs)
| Credential | ID | Type | Status |
|-----------|-----|------|--------|
| Supabase Postgres (Fixed) | Ut8VCPreZHrMt17M | postgres | WORKING |
| OpenRouter (Standard) | TFM3Q663LHfBcIAc | httpHeaderAuth | WORKING |
| OpenRouter (Graph) | VIFun2QQQlekGLiA | httpHeaderAuth | WORKING |
| OpenRouter (Quantitative) | ccrJrp4Z0BL54iIM | httpHeaderAuth | WORKING |
| OpenRouter (Orchestrator) | poTgoaQxqSSYbckv | httpHeaderAuth | WORKING |
| Redis | FmGCS5UwjP5x5gRx | redis | NOT ASSIGNED to Orch |

### Key Fixes Applied (Session 60)
- **FIX-QT-AUTH**: Quantitative 4 HTTP nodes had hardcoded API key in expression mode → replaced with `$env.OPENROUTER_KEY_QUANTITATIVE`
- **FIX-QT-PG**: Supabase credential wrong host (aws-0→aws-1) + wrong user (kfyr→ayqv) → new credential Ut8VCPreZHrMt17M
- **FIX-ORCH-AUTH**: Orchestrator 4 HTTP nodes same hardcoded key issue → replaced with `$env.OPENROUTER_KEY_ORCHESTRATOR`
- **FIX-ALL-PG**: All 8 workflows updated to use correct Supabase credential
- **FIX-ENTRYPOINT**: entrypoint.sh Supabase defaults corrected

### BLOCKERS
1. **Orchestrator Redis** — 6 Redis nodes with no credentials, no Redis server on HF Space. Needs either: (a) remove Redis dependency, (b) add Redis to Docker, or (c) use external Redis
2. **HF Space #2** — Both HF tokens expired/revoked. User must regenerate
3. **3 inactive workflows** — WhatsApp Bridge, Action Executor, Multi-Canal Gateway (missing credentials/validation errors)

### Next Steps
1. Run Phase 2 eval on 3 working pipelines (Standard 1000q, Graph 500q, Quant 500q)
2. Simplify Orchestrator to remove Redis dependency
3. Generate 1000q chatbot test dataset
4. Deploy entrypoint.sh fix to HF Space (next rebuild)

### Dataset Files
| File | Pipelines | Questions |
|------|-----------|-----------|
| datasets/phase-2/hf-1000.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/graph-quant-expansion-500x2.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/standard-orch-1000x2.json | standard(1000), orch(1000) | 2000 |
| datasets/phase-2/pme-gateway-1000.json | pme-gateway(1000) | 1000 |
| **TOTAL** | **5 pipelines** | **5000** |
