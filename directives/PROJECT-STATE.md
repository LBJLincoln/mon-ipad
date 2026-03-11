# Etat Systeme — Session 101

> Date: 2026-03-11T22:40Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM |
| **S1** (engine) | UP | Standard V3.5 + Graph V3.7 + Quant V3.1 + Orch V13 |
| **S2** (engine-2) | UP | Same workflows (lbjlincoln26 — can't set secrets) |
| **S3** (engine-3) | UP | Standard V3.5 + Graph V3.7 + Quant V3.1 + Orch V13 |
| **S4** (engine-4) | UP | Same workflows (lbjlincoln26 — can't set secrets) |
| **S5** (engine-5) | UP | Standard V3.5 + Graph V3.7 + Quant V3.1 + Orch V13 |
| **S6** (Docling) | UP | CPU-basic, 10MB/20page limits |
| **S7** (LiteLLM) | UP | `Bearer sk-litellm-nomos-2026` — ALL pipelines use it |
| **S9** (Staging) | UP | Graph V3.7 + Standard V3.5 (different ID: LVzddlzfif7DC059) |
| **Embeddings** | UP | Self-hosted Jina v3, 1024 dims |
| **Reranker** | UP | Self-hosted FlashRank ms-marco-MiniLM |

## 2. DATABASES

| DB | Vectors/Docs | Content |
|----|-------------|---------|
| **E5 Pinecone** (`sectors-e5-multilingual`) | **59,827** | PRIMARY — integrated E5 inference |
| **Jina Pinecone** (`website-sectors-jina-1024`) | **12,536** | SECONDARY — Jina embeddings |
| **Legacy Pinecone** (`sota-rag-jina-1024`) | **0** | ARCHIVED — EMPTY |
| **Neo4j** | **71,890** nodes (34.9K Entity, 30.1K SectorDoc, 5.2K Law, 1.6K Org) | UP |
| **Supabase** | **43,412** docs, 78 financials, 3,876 sector_financial_tables | UP |

## 3. PIPELINES — CANONICAL VERSIONS

| Pipeline | Workflow ID | Version | All Spaces | Status |
|----------|-----------|---------|-----------|--------|
| **Standard** | `9FQdtx38JLPiT3Hx` | V3.5 | S1-S5, S9 | WORKING — E5+Jina dual-index, LiteLLM |
| **Graph** | `6257AfT1l4FMC6lY` | V3.7 | S1-S5, S9 | WORKING — V3 keyword Cypher + Neo4j |
| **Quant** | `cjhEhVs0KV1ExHqX` | V3.1 | S1, S3, S5 | WORKING — SQL, data gap (78 US rows only) |
| **Orchestrator** | `qOSaFFrqO8Jb4VGb` | V13 | S1, S3, S5 | WORKING — regex routing |

**CRITICAL**: 17 conflicting old workflows were deactivated in S101. staging-deploy.py now uses correct Standard ID.

## 4. S101 ACCOMPLISHMENTS

### Critical Fixes
- [x] **Standard S1 broken → FIXED**: Two active workflows on same webhook. Old V3.4 (2Pk87ulicqq1CmMw) intercepted requests. 17 conflicting workflows deactivated across S1/S3/S5/S9
- [x] **Graph "Information not available" → Real answers**: Neo4j Query Builder V3 searches Entity.name + SectorDocument.question keywords. French keyword extraction. 629-699 chars real content
- [x] **Pipeline comparison dashboard**: data/pipeline-comparison.json — all nodes verified SAME across Spaces
- [x] **Workflow ID fix**: CLAUDE.md, staging-deploy.py, monitor.py, sync.py updated to `9FQdtx38JLPiT3Hx`

### Root Causes Found
- **Conflicting workflows**: n8n routes randomly when 2+ workflows share a webhook path
- **Graph empty results**: Neo4j entities have garbage names; SectorDocuments have no `name` field. Fixed with keyword search on `question` field
- **S2/S4 secrets**: Both HF tokens are LBJLincoln account — need lbjlincoln26 token

## 5. EVAL RESULTS

### S100 Baseline (before S101 fixes)
| Pipeline | Avg | Pass% |
|----------|-----|-------|
| Standard | 38.2 | 32.9% |
| Graph | 11.2 | 0% |
| Quant | 32.8 | 30% |
| Orchestrator | 47.8 | 60% |

### S101 Post-Fix (Standard only smoke)
| Sector | Score | Pass% |
|--------|-------|-------|
| BTP | 47.0 | 40% |
| Finance | 53.0 | 60% |
| Industrie | 61.0 | 60% |
| Juridique | 76.0 | 100% |
| **Overall** | **59.2** | **65.0%** |

**Standard: +21 points, +32% pass rate improvement**

### Full 4-pipeline eval — RUNNING

## 6. RUNNING PROCESSES
- Agentic loop daemon (PID 906004, working on Quant BTP fix)
- Monitor (PID 906738/906744, 5min cycle)
- 5 agents (monitor, eval, ingest, pipeline, docs)

## 7. NEXT PRIORITIES
1. **Full 4-pipeline eval** — verify Graph improvement
2. **Quant data ingestion** — French financial data into `financials` table
3. **BTP data gap** — DTU norms, Eurocodes (agentic loop working on it)
4. **Codespace Docling** — always-on PDF processing
5. **8 pipelines (4×2)** — prod+test identical (user demand)
6. **S2/S4 SSL fix** — need lbjlincoln26 HF token
