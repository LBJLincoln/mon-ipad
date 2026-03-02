# Workflow Process — Single Source of Truth

> Last updated: 2026-03-01T20:30:00Z (Session 67)

## 1. Pipeline Webhooks (VERIFIED)

| Pipeline | Path | Workflow ID | Field | Body |
|----------|------|-------------|-------|------|
| Standard | `/webhook/rag-multi-index-v3` | TmgyRP20N4JFd9CB | `query` | `{"query":"...","tenant_id":"benchmark"}` |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | 6257AfT1l4FMC6lY | `query` | `{"query":"..."}` |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | e465W7V9Q8uK6zJE | `query` | `{"query":"..."}` |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | aGsYnJY9nNCaTM82 | `query` | `{"query":"..."}` |
| PME Gateway | `/webhook/pme-gateway-v1` | — | `query` | `{"query":"...","source":"pme"}` |

**CRITICAL**: Field is `query`, NOT `question`. Using `question` returns empty/error (AP-2).

---

## 2. Iteration Loop (MANDATORY)

```
PRE-FLIGHT ─→ DIAGNOSE ─→ FIX (1 node) ─→ TEST (5q) ─→ VALIDATE (10q) ─→ SYNC ─→ COMMIT
```

### Pre-Flight (before any work)
```bash
source .env.local                              # ALWAYS first
cat technicals/debug/fixes-library.md | head -100  # Check known fixes
cat technicals/debug/knowledge-base.md | head -50  # Iron rules + quick ref
```

### Diagnose
```bash
python3 eval/quick-test.py --questions 3       # Smoke test all 4 pipelines
python3 eval/node-analyzer.py --pipeline <X> --last 5 --verbose  # Node-level analysis
python3 scripts/analyze_n8n_executions.py --pipeline <X> --limit 5  # Raw execution data
```

### Fix (1 node at a time — Rule 4)
```bash
# Via n8n REST API (preferred — hot-patch without rebuild)
curl -s -b /tmp/n8n_cookies.txt \
  "${N8N_HOST}/rest/workflows/${WORKFLOW_ID}" \
  -X PATCH -H "Content-Type: application/json" \
  -d '{"nodes":[...]}'

# After PATCH, re-activate webhook:
curl -s -b /tmp/n8n_cookies.txt \
  "${N8N_HOST}/rest/workflows/${WORKFLOW_ID}/activate" \
  -X POST -H "Content-Type: application/json" \
  -d '{"versionId":"<from GET response>"}'
```

### Test & Validate
```bash
python3 eval/quick-test.py --questions 5 --pipelines <X>  # 5/5 minimum
python3 eval/quick-test.py --questions 10 --pipelines <X>  # Gate: 10/10
```

### Sync & Commit
```bash
python3 n8n/sync.py                            # Download live workflows to n8n/live/
git add -A && git commit -m "fix: <description>" && git push origin main
```

---

## 3. n8n REST API Patterns

### Login (session cookie)
```bash
curl -s -c /tmp/n8n_cookies.txt \
  "${N8N_HOST}/rest/login" \
  -X POST -H "Content-Type: application/json" \
  -d '{"emailOrLdapLoginId":"ci@nomos.ai","password":"CI-Nomos-2026!"}'
```
**CRITICAL**: Field is `emailOrLdapLoginId`, NOT `email`.

### Get workflow (with nodes)
```bash
curl -s -b /tmp/n8n_cookies.txt "${N8N_HOST}/rest/workflows/${ID}"
```

### Update workflow (PATCH, not PUT)
```bash
curl -s -b /tmp/n8n_cookies.txt \
  "${N8N_HOST}/rest/workflows/${ID}" \
  -X PATCH -H "Content-Type: application/json" \
  -d @- <<'JSONEOF'
{"nodes": [...updated nodes...]}
JSONEOF
```

### Activate webhook (n8n 2.8+ requires versionId)
```bash
VERSION_ID=$(curl -s -b /tmp/n8n_cookies.txt "${N8N_HOST}/rest/workflows/${ID}" | python3 -c "import sys,json; print(json.load(sys.stdin)['versionId'])")
curl -s -b /tmp/n8n_cookies.txt \
  "${N8N_HOST}/rest/workflows/${ID}/activate" \
  -X POST -H "Content-Type: application/json" \
  -d "{\"versionId\":\"${VERSION_ID}\"}"
```

### Clean stuck executions (RECURRENT — do this every session)
```bash
# Via n8n REST API
curl -s -b /tmp/n8n_cookies.txt "${N8N_HOST}/rest/executions?status=running&limit=50" | python3 -c "
import sys, json
execs = json.load(sys.stdin).get('data', [])
print(f'{len(execs)} stuck executions found')
for e in execs: print(f'  ID={e[\"id\"]} workflow={e.get(\"workflowId\",\"?\")} started={e.get(\"startedAt\",\"?\")}')"
```

### List active workflows
```bash
curl -s -b /tmp/n8n_cookies.txt "${N8N_HOST}/rest/workflows?active=true" | python3 -c "
import sys, json
wfs = json.load(sys.stdin).get('data', [])
for w in wfs: print(f'{w[\"id\"]} | {w[\"name\"]} | active={w[\"active\"]}')"
```

---

## 4. Golden Snapshots

| Pipeline | Snapshot Path | Version | Accuracy |
|----------|--------------|---------|----------|
| Standard | `snapshot/current/Standard-RAG-V3.4.json` | V3.4 | 90% (Phase 2) |
| Graph | `snapshot/current/Graph-RAG-V3.3.json` | V3.3 | 78% (Phase 1) |
| Quantitative | `snapshot/current/Quantitative-V2.0-patched.json` | V2.0 | 92-100% |
| Orchestrator | `snapshot/current/Orchestrator-V10.1.json` | V10.1 | 80% (Phase 1, currently broken) |

**Restore from snapshot**:
```bash
WF_JSON=$(cat snapshot/current/Standard-RAG-V3.4.json)
curl -s -b /tmp/n8n_cookies.txt \
  "${N8N_HOST}/rest/workflows/TmgyRP20N4JFd9CB" \
  -X PATCH -H "Content-Type: application/json" \
  -d "${WF_JSON}"
# Then re-activate (see Section 3)
```

**CRITICAL**: HF Space credential IDs differ from snapshot IDs. Must remap:
- Postgres: snapshot `USU8ngVzsUbED3mn` → HF Space `Vrvh0ukcROAk9dyX` (or check live)
- Redis: snapshot `CWih07lwPxfwFeY6` → HF Space `IDrWmZSQb5ziEQeC` (or check live)

---

## 5. Key Fixes Reference (Top 12)

| # | Problem | Fix | Session |
|---|---------|-----|---------|
| FIX-01 | Task Runner code cache stale | `N8N_RUNNERS_ENABLED=false` | 7 |
| FIX-07 | Neo4j bolt protocol blocked | Switch to HTTPS API (`/db/neo4j/tx/commit`) | 12 |
| FIX-13 | HF Space $env vars empty | `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` | 19 |
| FIX-22 | OpenRouter 429 rate limit | Per-pipeline API keys (6 keys, 3 accounts) | 27 |
| FIX-28 | Jina embedding key expired | Replace in n8n HTTP Request node headers | 50 |
| FIX-33 | $env parsed as subtraction | Use `{{ $env.VAR }}` with curly braces, not raw | 35 |
| FIX-39 | Quant pipeline NO_ANSWER | Filter NO_ANSWER/N/A/ERROR in extract_answer() | 66 |
| FIX-40 | VM OOM zombie processes | Removed n8n Docker from VM (Session 42) | 42 |
| FIX-58 | HF rebuild wipes credentials | Restore via REST API POST /api/v1/credentials | 58 |
| FIX-63 | Block env access in node | Set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` in HF Space | 60 |
| FIX-66a | Stale HF Spaces in round-robin | Single host in N8N_ALL_HOSTS (not 9 dead spaces) | 66 |
| FIX-66b | Pinecone JSON stray comma | Inline conditional for namespace field | 66 |

**Full library**: `technicals/debug/fixes-library.md` (67 fixes documented)

---

## 6. Anti-Patterns (NEVER DO)

| # | Anti-Pattern | Correct Approach |
|---|-------------|-----------------|
| AP-1 | Webhook path from memory | Always check `knowledge-base.md` Section 0 |
| AP-2 | Send `"question"` field | Send `"query"` field |
| AP-3 | Edit workflow via file upload | Use REST API PATCH |
| AP-6 | PATCH nodes[] only | Also update activeVersion.nodes[] if present |
| AP-7 | Use $env without guard | Set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` |
| AP-9 | Multiple node changes at once | 1 fix per iteration (Rule 4) |
| AP-10 | Skip pre-flight checks | Always read fixes-library + knowledge-base first |
| AP-12 | Send context-rich questions to SQL pipeline | SQL expects data queries, not prose |

---

## 7. 6 Golden Rules

1. **fixes-library.md FIRST** — Read before any debug attempt
2. **1 fix per iteration** — Never change multiple nodes simultaneously
3. **n8n is source of truth** — Always GET current state before PATCH
4. **Granular analysis BEFORE fix** — Use node-analyzer.py + analyze_n8n_executions.py
5. **5/5 before sync** — Never sync workflow unless quick-test passes 5/5
6. **Commit + push after success** — Origin + satellites, every 15-20 min
