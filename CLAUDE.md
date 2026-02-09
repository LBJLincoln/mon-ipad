# Multi-RAG Orchestrator — SOTA 2026

## Session Start — READ FIRST

```bash
cat docs/status.json    # Live metrics, phase gates, blockers, next action (<3KB)
```

Then: analyze the ONE pipeline with the worst gap → diagnose via n8n execution data → fix directly in n8n → verify with 5q eval → sync to GitHub.

**Phase roadmap**: Phase 1 (200q) → Phase 2 (1,000q) → Phase 3 (~10Kq) → Phase 4 (~100Kq) → Phase 5 (1M+q)

---

## Key Commands

| Action | Command |
|---|---|
| **Live status** | `cat docs/status.json` |
| **Phase gates** | `python3 eval/phase_gates.py` |
| **Regenerate status** | `python3 eval/generate_status.py` |
| **Smoke test (5q)** | `python3 eval/quick-test.py --questions 5` |
| **Fast iter (10q)** | `python3 eval/fast-iter.py --label "..."` |
| **Iterative eval (5→10→50)** | `python3 eval/iterative-eval.py --label "..."` |
| **Full eval (200q)** | `python3 eval/run-eval-parallel.py --reset --label "..."` |
| **Phase 2 eval** | `python3 eval/run-eval-parallel.py --dataset phase-2 --reset --label "..."` |
| **Sync workflows from n8n** | `python3 workflows/sync.py` |
| **Fetch n8n logs** | `python3 eval/n8n-proxy.py --fetch` |
| **Node diagnostics** | `python3 eval/node-analyzer.py --pipeline graph --last 5` |
| **All diagnostics** | `python3 eval/node-analyzer.py --all --last 5` |
| **Single execution** | `python3 eval/node-analyzer.py --execution-id <ID>` |
| **Setup embeddings** | `python3 db/populate/setup_embeddings.py --provider jina` |

---

## Access

| Resource | Access | Note |
|---|---|---|
| n8n Webhooks + REST API | DIRECT | `amoret.app.n8n.cloud` |
| GitHub, Pinecone | DIRECT | git + HTTPS API |
| Supabase, Neo4j | BLOCKED | Proxy 403 — access via n8n workflows only |

DB population scripts (`db/populate/`) require user action on GCloud VM.

---

## Credentials

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export SUPABASE_API_KEY="sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
export N8N_HOST="https://amoret.app.n8n.cloud"
```

---

## Architecture (brief)

4 n8n RAG workflows on `amoret.app.n8n.cloud`:

| Pipeline | Workflow ID | Webhook Path |
|---|---|---|
| **Standard** (Pinecone vector) | `8LAvwLOtX1DVpFjX` | `/webhook/rag-multi-index-v3` |
| **Graph** (Neo4j entity graph) | `1mpapjPd3O7C5Dzx` | `/webhook/ff622742-...` |
| **Quantitative** (Supabase SQL) | `E19NZG9WfM7FNsxr` | `/webhook/3e0f8010-...` |
| **Orchestrator** (routes to all 3) | `ALd4gOEqiKL5KR1p` | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` |

All LLMs: `arcee-ai/trinity-large-preview:free` via OpenRouter ($0 cost).
Embeddings: configurable via n8n `$vars.EMBEDDING_MODEL` (see `db/populate/setup_embeddings.py`).

**Full architecture details**: `docs/architecture.md`

---

## Workflow Modification Protocol (CRITICAL)

**n8n is the source of truth. GitHub is the sync target.**

### Why: apply.py patches are DEPRECATED for modifications
The old approach (`workflows/improved/apply.py --deploy`) used string-matching patches that:
- Break when upstream code changes
- Can introduce regressions (e.g., referencing variables before they're defined)
- Use stale workflow IDs that 404
- Cannot be validated without deploying

### Correct workflow for making changes:

1. **DIAGNOSE** — Fetch real execution data, analyze node-by-node I/O (see Diagnostics section)
2. **FIX IN n8n** — Use the n8n REST API to download the workflow, modify the specific node's code, then upload and activate:
   ```python
   # Download
   wf = n8n_api("GET", f"/api/v1/workflows/{WF_ID}")
   # Find and modify the target node
   for node in wf["nodes"]:
       if node["name"] == "Target Node Name":
           node["parameters"]["jsCode"] = NEW_CODE
   # Upload (deactivate → PUT → activate)
   n8n_api("POST", f"/api/v1/workflows/{WF_ID}/deactivate")
   n8n_api("PUT", f"/api/v1/workflows/{WF_ID}", clean_payload)
   n8n_api("POST", f"/api/v1/workflows/{WF_ID}/activate")
   ```
3. **VERIFY** — Run 5-question smoke test with granular analysis
4. **SYNC TO GITHUB** — Download the working workflow and save to `workflows/live/`:
   ```bash
   python3 workflows/sync.py   # Downloads all active workflows to workflows/live/
   ```
5. **COMMIT** — Commit the synced JSON to GitHub as a record of what's live

### NEVER:
- Edit workflow JSONs directly in the repo and push to n8n
- Use apply.py for new changes (it's a historical reference only)
- Deploy changes without verifying with at least 5 test questions first

---

## Granular Node Analysis Protocol (MANDATORY)

**Every eval batch (even 5 questions) MUST include full node-by-node I/O inspection.**

### After every eval run:

1. **Fetch execution data** for each question that failed or had unexpected behavior:
   ```python
   # Get execution with full node data
   exec_data = requests.get(
       f"{N8N_HOST}/api/v1/executions/{EXEC_ID}?includeData=true",
       headers={"X-N8N-API-KEY": API_KEY}
   ).json()
   result_data = exec_data["data"]["resultData"]["runData"]
   ```

2. **For EACH node in the execution**, inspect:
   - **Input**: What data entered the node?
   - **Output**: What data left the node?
   - **Duration**: How long did it take?
   - **Error**: Did it fail? What error?
   - **Data transformation**: Was information lost, corrupted, or misinterpreted between nodes?

3. **Specific checks per node type**:
   - **LLM nodes** (Intent Analyzer, Answer Synthesis): Check prompt length, output verbosity, hallucination indicators
   - **Routing nodes** (Query Router, Dynamic Switch): Check if routing decision was correct for the question
   - **Retrieval nodes** (Pinecone, Neo4j, Supabase): Check document count, relevance scores, empty results
   - **Handler nodes** (Task Result Handler, Fallback Monitor): Check if success/failure determination was correct
   - **Builder nodes** (Response Builder): Check if final response accurately reflects sub-pipeline answers

4. **Compare expected vs actual** at each step:
   - Did the Intent Analyzer correctly identify the query type?
   - Did it route to the right pipeline?
   - Did the pipeline retrieve relevant documents?
   - Did the LLM synthesize a correct answer from the context?
   - Did the handler correctly accept/reject the response?
   - Did the response builder faithfully pass the answer through?

5. **Log findings** in `logs/diagnostics/` with specific node names and data samples.

### Automated analysis tool:
```bash
python3 eval/node-analyzer.py --pipeline <target> --last 10
```

### Before making ANY fix, you MUST be able to answer:
- Which exact node is causing the problem?
- What is the node receiving as input?
- What is it producing as output?
- Why is that output wrong?
- What specific code change in that node will fix it?

---

## Iteration Protocol (MANDATORY)

### Per-pipeline 5-question eval cycle:

1. **Run 5 questions**: `python3 eval/quick-test.py --questions 5 --pipeline <target>`
2. **Analyze EVERY execution** node-by-node (see Granular Node Analysis above)
3. **Identify the root cause** — not just "accuracy is low" but "Node X receives Y and outputs Z when it should output W"
4. **Fix ONE node** via n8n API
5. **Re-run 5 questions** to verify the fix
6. **If improved**: sync to GitHub, commit, proceed to next issue
7. **If regressed**: revert immediately via n8n API (re-upload backup)

### Scaling up:
- 5q passes → run 10q
- 10q passes → run 50q
- 50q passes → run full 200q eval

### Gate thresholds:
| Stage | Accuracy | Error Rate |
|---|---|---|
| 5 questions | ≥60% | ≤40% |
| 10 questions | ≥65% | ≤20% |
| 50 questions | pipeline target | ≤10% |

---

## Rules

1. **ONE fix per iteration** — never change multiple nodes or pipelines simultaneously
2. **n8n is source of truth** — always edit in n8n, then sync to GitHub
3. **Granular analysis before every fix** — inspect node-by-node I/O, not just final accuracy
4. **Verify before syncing** — 5-question eval must pass before committing to GitHub
5. **Commit + push after every successful fix** to keep agents in sync
6. **`docs/status.json` is auto-generated** — regenerated after every eval by `live-writer.py`
7. If accuracy < target → fetch execution data, analyze node I/O, find the specific broken node
8. If error rate > 10% → prioritize error fixes over accuracy
9. If 3+ regressions → REVERT last change immediately (re-upload backup to n8n)
10. **NEVER apply blind patches** — always understand the root cause before changing code

---

## Key Files

| File | Purpose |
|---|---|
| `docs/status.json` | Compact live status (auto-generated, <3KB) |
| `docs/data.json` | Full eval data (source of truth for metrics) |
| `docs/index.html` | **Control Tower dashboard** (Tab 0 = central hub) |
| `docs/knowledge-base.json` | Error patterns, fixes, functional choices |
| `docs/architecture.md` | Detailed architecture reference |
| `eval/quick-test.py` | **5-question smoke test** (use after every fix) |
| `eval/iterative-eval.py` | **Progressive 5→10→50 per pipeline** |
| `eval/node-analyzer.py` | **Node-by-node execution analyzer** |
| `eval/n8n-proxy.py` | Fetch n8n execution logs + rich data capture |
| `eval/generate_status.py` | Generates status.json from data.json |
| `eval/live-writer.py` | Writes eval results + auto-regenerates status.json |
| `eval/phase_gates.py` | Phase gate validator |
| `workflows/sync.py` | **Sync active workflows from n8n to GitHub** |
| `workflows/live/` | **Synced workflow JSONs** (record of what's deployed) |
| `workflows/improved/apply.py` | Historical patches (DEPRECATED for new changes) |
| `db/populate/setup_embeddings.py` | **Free embeddings setup** (Jina/HF/OpenRouter → Pinecone + n8n) |
| `db/populate/phase2_neo4j.py` | Phase 2 Neo4j entity extraction |
| `db/populate/phase2_supabase.py` | Phase 2 Supabase table population |
| `db/readiness/` | Per-phase database readiness checks |
| `logs/diagnostics/` | Node-level diagnostic reports |
| `phases/overview.md` | Full 5-phase strategy |
