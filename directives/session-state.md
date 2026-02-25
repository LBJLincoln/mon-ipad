# Session State — 25 Fevrier 2026 (Session 63 continued)

> Last updated: 2026-02-25T15:50:00+01:00

## Current Status: GOLDEN BASELINE REVERTED — LLM RATE-LIMITED

### Session 63 (continued) Achievements

1. **Workflow Diff Engine operational** — compares all 9 spaces vs golden 22-Feb baseline:
   - Standard + Graph: 100% match on all spaces
   - Quantitative: 4 diffs (wrong API key nodes) — REVERTED to golden on 9 spaces
   - Orchestrator: 26 diffs (14 node type changes Code→Postgres/Redis) — REVERTED to golden on 9 spaces
   - Fixed: added `activate_workflow` method to N8nClient
2. **Root cause identified: OpenRouter 429 rate limit**:
   - `meta-llama/llama-3.3-70b-instruct:free` is rate-limited upstream
   - Workflows are structurally correct (golden baseline)
   - All 10 credentials present on primary space
   - All 4 core workflows ACTIVE
   - LLM calls fail with 429 → "Unable to generate answer" / "NO_ANSWER"
3. **Golden baseline confirmed** (22 Feb results):
   - Standard: 55.6% (363q), Graph: 64.0% (400q), Quant: 52.4% (500q)
   - Workflow JSONs UNCHANGED since 22 Feb — infrastructure broke, not workflows
4. **Scripts created (session 63)**:
   - workflow-diff-engine.py (26KB) — diff + revert to golden
   - continuous-monitor.py (15KB) — daemon, 5-min ping, 15-min deep test
   - live-intelligence.py (22KB) — continuous math analysis
   - launch-all.sh (18KB) — one-click restore+activate+verify
   - auto-remediate.py (28KB) — 67 known fix patterns
   - dashboard/index.html (38KB) — per-pipeline scrollable + "for dummies" mode

### BLOCKING ISSUE
- **OpenRouter free-tier rate limit** — need to swap LLM model or set up LiteLLM multi-provider
- **Next session**: Try `google/gemma-3-27b-it:free` or set up Together.ai/Groq fallback
   - Orchestrator: 0% (empty body - separate issue)
6. **Scripts created**:
   - `scripts/scale-hf-spaces.py` — HF Space management
   - `scripts/activate-all-spaces.py` — Bulk workflow activation
   - `scripts/restore-all-spaces.py` — Parallel credential restoration
   - **`scripts/launch-all.sh` — ONE-CLICK DEPLOYMENT (NEW)**
7. **One-click deployment script** — `launch-all.sh`:
   - Self-contained bash script (18 KB, 600+ lines)
   - Orchestrates full deployment: restore → activate → test
   - Tests all 5 webhooks on all 10 spaces (50 tests total)
   - Color-coded terminal output (French)
   - Comprehensive logging to `logs/launch-all-YYYY-MM-DD.log`
   - Results matrix (spaces × pipelines)
   - **Non-technical user friendly** — just run `bash scripts/launch-all.sh`
   - Duration: 15-20 minutes for full deployment
   - Documentation: `scripts/README-launch-all.md`

### Phase 2 Eval Progress (stopped — credential restore in progress)
- Eval PID stopped (previous run had credential issues)
- **180+ tested IDs saved** to tested_ids.json
- Accuracy improving after credential restore on primary space
- **Next**: Re-run eval after credential fix completes on all spaces

| Pipeline | Tested IDs | Total Available | Current Accuracy | Status |
|----------|-----------|-----------------|------------------|--------|
| Standard | 60+ | 1000 | ~85% | STOPPED - credential restore |
| Graph | 50+ | 1000 | ~20% | STOPPED - credential restore |
| Quantitative | 50+ | 1000 | ~6% | STOPPED - credential restore |
| Orchestrator | 20+ | 1000 | 0% (empty body) | STOPPED - separate issue |
| **TOTAL** | **180+** | **4000** | **Improving** | **Credential restore** |

### Infrastructure (10 HF Spaces)
| Space | Account | URL | Status |
|-------|---------|-----|--------|
| 1 (primary) | LBJLincoln | lbjlincoln-nomos-rag-engine.hf.space | RUNNING + 11/14 workflows |
| 2 | LBJLincoln26 | lbjlincoln26-nomos-rag-engine-2.hf.space | **BROKEN** — under investigation |
| 3 | LBJLincoln | lbjlincoln-nomos-rag-engine-3.hf.space | RUNNING + credential restore |
| 4 | LBJLincoln26 | lbjlincoln26-nomos-rag-engine-4.hf.space | RUNNING + credential restore |
| 5 | LBJLincoln | lbjlincoln-nomos-rag-engine-5.hf.space | RUNNING + credential restore |
| 6 | LBJLincoln26 | lbjlincoln26-nomos-rag-engine-6.hf.space | RUNNING + credential restore |
| 7 | LBJLincoln | lbjlincoln-nomos-rag-engine-7.hf.space | RUNNING + credential restore |
| 8 | LBJLincoln26 | lbjlincoln26-nomos-rag-engine-8.hf.space | RUNNING + credential restore |
| 9 | LBJLincoln | lbjlincoln-nomos-rag-engine-9.hf.space | RUNNING + credential restore |
| 10 | LBJLincoln26 | lbjlincoln26-nomos-rag-engine-10.hf.space | RUNNING + credential restore |

### Chatbot: Live on all 4 sites
- nomos-ai-pied.vercel.app — YES
- nomos-pme-connectors — YES
- nomos-pme-usecases — YES
- nomos-dashboard — YES

### Broken Endpoints (still to fix)
- Data Ingestion V4.0: 404
- PME Gateway: 404
- Status Dashboard: 404

### Known Issues
- **Orchestrator returns empty body** — separate issue from env var fix, needs investigation
- **HF Space rebuild wipes SQLite DB** — credential references lost, restore script running
- **Standard workflow uses $env.VAR_NAME** — not credential objects for OpenRouter/Pinecone
- **N8N_BLOCK_ENV_ACCESS_IN_NODE=false REQUIRED** — for $env expressions to work

### CRITICAL: Next Session Startup
1. **Verify credential restore completed** — check all 10 spaces have credentials
2. **Re-run eval** — use dedup to continue from tested_ids.json (180+ already tested)
3. **Fix Orchestrator empty body** — investigate root cause (different from env var issue)
4. **Monitor Space 2** — currently broken, may need manual intervention
5. **Run session intelligence** — `python3 scripts/session-intelligence.py` before starting

### Session Intelligence Recommendations
1. [CRITICAL] Orchestrator degradation -20% — investigate NO_ANSWER pattern
2. [HIGH] HF Space rebuild needed (N8N_BLOCK_ENV_ACCESS_IN_NODE fix)
3. [HIGH] Quantitative degradation -8% — likely caused by env var access block
4. [MEDIUM] Standard degradation -8%

### Dataset Files
| File | Pipelines | Questions |
|------|-----------|-----------|
| datasets/phase-2/hf-1000.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/graph-quant-expansion-500x2.json | graph(500), quant(500) | 1000 |
| datasets/phase-2/standard-orch-1000x2.json | standard(1000), orch(1000) | 2000 |
| datasets/phase-2/pme-gateway-1000.json | pme-gateway(1000) | 1000 |
| **TOTAL** | **5 pipelines** | **5000** |

### Git Commits (Session 62)
- `92a36a1` — 10 HF Spaces + eval improvements (incremental saves, preflight, signal handler)
- `e6b4cdd` — executive summary update + tested_ids incremental save
- `566a4a4` — N8N_BLOCK_ENV_ACCESS_IN_NODE=false fix
- Plus: Dashboard fix, Enrichissement fix, Action Executor fix (from repair agents)
