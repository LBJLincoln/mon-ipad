# GitHub Actions Health Report — 2026-02-25

## Executive Summary

**STATUS: CRITICAL** — 3 repos have deleted workflows triggering phantom failures. Secrets missing in 2 repos. Only rag-dashboard + rag-tests have active workflows.

| Repo | Active Workflows | Recent Failures | Secrets | Status |
|------|------------------|-----------------|---------|--------|
| **rag-pme-connectors** | 0 | 2 (Vercel deploy) | 0/7 missing | BROKEN |
| **rag-data-ingestion** | 0 | 3 (Vercel deploy) | 0/7 missing | BROKEN |
| **rag-dashboard** | 1 ✓ (pages-build) | None | 1/1 ✓ | OK |
| **rag-tests** | 0 (but runs OK) | 3 (Vercel deploy) | 9/9 ✓ | PARTIAL |

---

## Detailed Findings

### 1. rag-pme-connectors
**Problem**: Deleted workflow file still triggering failed runs
- Workflow ID: `236757137`
- Path: `.github/workflows/deploy-website.yml`
- State: **DELETED** (2026-02-23T12:13:20Z)
- Recent runs: 2 failures (push events)
- Secrets: **0 configured** — missing VERCEL_TOKEN (required for deployment)
- Last failure: 2026-02-23 01:25:16Z
- Root cause: 
  1. Workflow file deleted but GitHub still tries to execute push triggers
  2. Even if workflow existed, no VERCEL_TOKEN secret configured

**Fix**: 
1. Delete run history or ignore (GitHub will stop queuing after ~7 days)
2. If reactivating deploys: Create `.github/workflows/deploy-website.yml` with VERCEL_TOKEN secret

---

### 2. rag-data-ingestion
**Problem**: Same as rag-pme-connectors — deleted workflow triggering failures
- State: **Workflows deleted**
- Recent runs: 3 failures (push events)
- Secrets: **0 configured** — missing VERCEL_TOKEN
- Last failure: 2026-02-23 01:25:16Z
- Root cause: Same as above

**Fix**: Same as rag-pme-connectors

---

### 3. rag-dashboard
**Status: WORKING ✓**
- Active workflow: `pages-build-deployment` (GitHub Pages auto-build)
- Secrets: 1 ✓ (VERCEL_TOKEN configured)
- Recent runs: ALL SUCCESS (2026-02-24 passes)
- Note: GitHub Pages integration handles deployment, no manual Vercel workflow needed

---

### 4. rag-tests
**Status: WORKING (with caveat)**
- Active workflows: 0 (but `Phase 1 - RAG Pipeline Tests` runs successfully via `workflow_dispatch`)
- Manual runs: All success (workflow_dispatch events)
- Automated "Deploy Website to Vercel" runs: 3 failures (but workflow file deleted)
- Secrets: 9/9 configured ✓
  - JINA_API_KEY ✓
  - N8N_API_KEY ✓
  - NEO4J_URI ✓
  - OPENROUTER_API_KEY ✓
  - PINECONE_API_KEY ✓
  - PINECONE_HOST ✓
  - SUPABASE_API_KEY ✓
  - SUPABASE_PASSWORD ✓
  - SUPABASE_URL ✓
- Eval runs: Triggering correctly via workflow_dispatch, passing with latest runs

---

## Secrets Inventory

### rag-pme-connectors (0/7 configured)
Missing: VERCEL_TOKEN, GITHUB_TOKEN, NPM_TOKEN, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SLACK_WEBHOOK, DATABASE_URL

### rag-data-ingestion (0/7 configured)
Missing: VERCEL_TOKEN, DOCKER_HUB_USERNAME, DOCKER_HUB_TOKEN, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, DATABASE_URL, SLACK_WEBHOOK

### rag-dashboard (1/1 configured) ✓
- VERCEL_TOKEN ✓

### rag-tests (9/9 configured) ✓
- JINA_API_KEY ✓
- N8N_API_KEY ✓
- NEO4J_URI ✓
- OPENROUTER_API_KEY ✓
- PINECONE_API_KEY ✓
- PINECONE_HOST ✓
- SUPABASE_API_KEY ✓
- SUPABASE_PASSWORD ✓
- SUPABASE_URL ✓

---

## Codespaces Status
- Active codespaces: 1
  - Name: `rag-tests-eval-5g6g5q9vj7vjf44x`
  - Repo: LBJLincoln/mon-ipad
  - Branch: main
  - Status: Shutdown (2026-02-24T13:50:50Z)

---

## Recommendations

### Priority 1: Stop Phantom Failures
**Action**: Disable or delete orphaned workflow runs for rag-pme-connectors and rag-data-ingestion
- GitHub will eventually stop queuing runs after 7 days of workflow deletion
- Or: Manually clean up workflow files if you want to re-enable deployments

### Priority 2: Configure Missing Secrets
**For rag-pme-connectors**:
```bash
gh secret set VERCEL_TOKEN --repo LBJLincoln/rag-pme-connectors --body "<token>"
```

**For rag-data-ingestion**:
```bash
gh secret set VERCEL_TOKEN --repo LBJLincoln/rag-data-ingestion --body "<token>"
```

### Priority 3: Re-Create Workflow Files (if needed)
If you want Vercel deployments on push, create `.github/workflows/deploy-website.yml` in each repo with:
```yaml
name: Deploy Website to Vercel
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Vercel
        run: |
          npm install -g vercel
          vercel deploy --prod --token ${{ secrets.VERCEL_TOKEN }}
```

### Priority 4: Keep rag-tests Working
- Current status: ✓ All 9 secrets configured
- Keep running eval via `gh workflow run` or manual dispatch
- No action needed

---

## Summary Checklist
- [x] Identified 3 repos with deleted workflows causing phantom failures
- [x] Found 2 repos missing VERCEL_TOKEN (rag-pme-connectors, rag-data-ingestion)
- [x] Verified rag-dashboard and rag-tests have proper secrets
- [x] Documented 1 active codespace (shutdown)
- [ ] (Optional) Decide whether to re-enable Vercel deployments or let them auto-cleanup
- [ ] (Optional) Set VERCEL_TOKEN secrets if re-enabling deployments

