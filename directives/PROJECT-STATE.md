# Etat Systeme — Session 98

> Date: 2026-03-11T18:30Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM, 226MB available |
| **S1** (engine) | UP | Standard V3.9 + Graph V3.6 + Orch V13 |
| **S2** (engine-2) | UP | Standard V3.9 + Graph V3.6 (mirror) |
| **S3** (engine-3) | UP | Standard V3.9 + Graph V3.6 |
| **S4** (engine-4) | UP | Standard V3.9 + Graph V3.6 (mirror) |
| **S5** (engine-5) | UP | Standard V3.9 + Graph V3.6 |
| **S6** (Docling) | UP | converter loaded |
| **S7** (LiteLLM) | AUTH ERROR | Returns 401, needs fix or repurpose |
| **S8** (Eval Judge) | DOWN | Ready to deploy |
| **S9** (Staging) | UP | Standard V3.9 + Graph V3.6 (staging) |
| **Embeddings** | UP | Self-hosted Jina v3, 1024 dims |
| **Reranker** | UP | Self-hosted FlashRank ms-marco-MiniLM |

## 2. DATABASES

| DB | Vectors/Docs | Content |
|----|-------------|---------|
| **E5 Pinecone** (`sectors-e5-multilingual`) | **58,533** | PRIMARY — integrated E5 inference |
| **Jina Pinecone** (`website-sectors-jina-1024`) | **12,536** | SECONDARY — Jina embeddings |
| **Legacy Pinecone** (`sota-rag-jina-1024`) | **0** | ARCHIVED — EMPTY, do not query |
| **Neo4j** | Entity/Company/Org/Law/SectorDoc | UP |
| **Supabase** | **43,357** docs, 78 financials, 0 exec_scores | UP |

## 3. PIPELINES — DEPLOYED VERSIONS

| Pipeline | Deployed | All Spaces | Status |
|----------|----------|-----------|--------|
| **Standard** | **V3.9** | S1-S5 + S9 | WORKING — E5 + Jina multi-index + self-hosted reranker |
| **Graph** | **V3.6** | S1-S5 + S9 | WORKING — self-hosted embed/rerank + correct Pinecone |
| **Quant** | V3.1 | S1-S5 | WORKING — SQL executing correctly |
| **Orchestrator** | V13 (regex) | S1 | WORKING — routes to Standard/Graph/Quant |

## 4. S98 ACCOMPLISHMENTS

### Critical Fix
- [x] **Standard pipeline DOWN on S1-S5**: Was running V3.4 (not V3.7) with expired Jina API + archived Pinecone index (0 vectors). Deployed V3.9 to ALL 6 Spaces — immediately restored
- [x] **Graph V3.6 deployed**: Self-hosted embed/rerank + correct Pinecone to ALL 6 Spaces

### Deployments
- [x] Standard V3.9 → S1, S2, S3, S4, S5, S9 (via staging-deploy.py)
- [x] Graph V3.6 → S1, S2, S3, S4, S5, S9 (via staging-deploy.py)
- [x] Orchestrator V14.1 → S1 (tested, returns empty responses — REVERTED to V13)

### Findings
- **n8n login via curl BROKEN**: HF proxy rejects curl requests, Python urllib works
- **V14.1 orchestrator empty responses**: executeWorkflow + respondToWebhook conflict, needs debugging
- **Production was V3.4 not V3.7**: The V3.7 deployment from S96 didn't persist (or was overwritten)

### Agentic Loop Cycle 1 Results (from S97 background)
- Priority: BTP data gap (25/100, 0% pass)
- Root cause: Missing DTU norms, Eurocodes, CCTP, AFNOR, RE2020
- Suggested: Ingest construction standards into Pinecone

## 5. EVAL BASELINE (S98 — V3.9 + V3.6)

### Smoke Test (20Q, Standard only)
| Sector | Score | Pass% |
|--------|-------|-------|
| BTP | 27/100 | 0% |
| Finance | 39/100 | 40% |
| Industrie | 53/100 | 60% |
| Juridique | 69/100 | 100% |
| **Overall** | **47/100** | **50%** |

### Full eval (220Q+, all pipelines) — RUNNING

## 6. NEXT PRIORITIES
1. **Wait for full eval results** (running in background)
2. **BTP data ingestion** — DTU norms, Eurocodes, CCTP, AFNOR (agentic loop priority)
3. **Debug V14.1 orchestrator** — fix empty response issue
4. **Start S8** and deploy eval-judge workflow
5. **Run continuous agentic loop** — STRATEGIZE → PLAN → BUILD → TEST → IMPROVE
6. **Start Codespace** for Docling continuous PDF ingestion
7. **Fix or repurpose S7** (LiteLLM auth error)
