# Etat Systeme — Session 103

> Date: 2026-03-12T02:30Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM |
| **S1** (engine) | UP | RAG-ONLY: Standard V3.5 + Graph V3.7 + Quant V3.1 + Orch V13 |
| **S2** (engine-2) | UP | Same DB as S1 (lbjlincoln26 — can't set secrets) |
| **S3** (engine-3) | UP | RAG-ONLY: Same as S1 (shared DB) |
| **S4** (engine-4) | UP | Same DB as S3 (lbjlincoln26 — can't set secrets) |
| **S5** (engine-5) | UP | RAG-ONLY: Same as S1 (shared DB) |
| **S6** (Docling) | UP | CPU-basic, 10MB/20page limits |
| **S7** (LiteLLM) | UP | `Bearer sk-litellm-nomos-2026` — ALL pipelines use it |
| **S9** (INGEST) | UP | INGEST-ONLY — n8n webhooks BROKEN (all return "could not be started") |
| **Embeddings** | UP | Self-hosted Jina v3, 1024 dims |
| **Reranker** | UP | Self-hosted FlashRank ms-marco-MiniLM |

## 2. DATABASES

| DB | Vectors/Docs | Content |
|----|-------------|---------|
| **E5 Pinecone** (`sectors-e5-multilingual`) | **63,500+** (growing) | PRIMARY — integrated E5 inference |
| **Jina Pinecone** (`website-sectors-jina-1024`) | **12,536** | SECONDARY — Jina embeddings |
| **Neo4j** | **71,890** nodes (34.9K Entity, 30.1K SectorDoc, 5.2K Law, 1.6K Org) | UP |
| **Supabase** | **43,412** docs, **225** financials (111 companies, 4 sectors), 3,876 sector_financial_tables | UP |

## 3. PIPELINES — CANONICAL VERSIONS

| Pipeline | Workflow ID | Version | Spaces | Status |
|----------|-----------|---------|--------|--------|
| **Standard** | `9FQdtx38JLPiT3Hx` | V3.5 | S1, S3, S5 | WORKING — 4/5 eval |
| **Graph** | `6257AfT1l4FMC6lY` | V3.7 | S1, S3, S5 | WORKING — 5/5 eval |
| **Quant** | `cjhEhVs0KV1ExHqX` | V3.1 | S1, S3, S5 | WORKING — 4/5 eval (4 sectors!) |
| **Orchestrator** | `qOSaFFrqO8Jb4VGb` | V13 | S1, S3, S5 | WORKING — 3/3 eval |

**S1-S5: RAG-ONLY.** S9: INGEST-ONLY. 64+ conflicting workflows cleaned in S101-S102.

## 4. S103 ACCOMPLISHMENTS

### Quant Production-Ready
- [x] **225 financial rows** (was 110): 42 finance, 34 industrie, 20 btp, 15 juridique companies
- [x] **Juridique sector added**: Wolters Kluwer, Thomson Reuters, LexisNexis, Linklaters, Clifford Chance, French law firms
- [x] **All 4 sectors pass**: 10/10 direct test, 4/5 eval

### Ingestion System
- [x] **Tavily all 4 sectors**: Added finance + juridique queries (was BTP + industrie only)
- [x] **E5 vectors**: 59,827 → 63,500+ (+3,700 new from Tavily)
- [x] **continuous-ingest.py**: Daemon for 24/7 ingestion (Tavily + fast-ingest + HF datasets)

### Eval System Fixed
- [x] **N8N_ALL_HOSTS fixed**: Removed S9 (INGEST-ONLY), added S5 to rotation
- [x] **Quant eval questions**: Updated for French data, correct sectors
- [x] **Payload fixed**: Added `question` key + `sector` + `tenant_id: default`

## 5. EVAL RESULTS (S103)

### 4-Pipeline Eval (5Q each)
| Pipeline | Pass | Total | Score |
|----------|------|-------|-------|
| Standard | 4 | 5 | 80% |
| Graph | 5 | 5 | **100%** |
| Quant | 4 | 5 | 80% |
| Orchestrator | 3 | 3 | **100%** |
| **TOTAL** | **16** | **18** | **89%** |

### Quant Detailed (10Q, all sectors)
| Sector | Pass | Total |
|--------|------|-------|
| Finance | 4 | 4 |
| BTP | 3 | 3 |
| Juridique | 1 | 1 |
| Industrie | 2 | 2 |
| **TOTAL** | **10** | **10** = **100%** |

## 6. RUNNING PROCESSES
- Tavily finance ingestion (background)
- Tavily juridique ingestion (background)
- Tavily industrie ingestion (background)
- Monitor agent (5min cycle)
- 5 agents (monitor, eval, ingest, pipeline, docs)

## 7. NEXT PRIORITIES
1. **Start continuous-ingest daemon** — 24/7 ingestion loop
2. **Reach 70K vectors** — Tavily still running
3. **BTP data gap** — DTU norms, Eurocodes (Tavily ingesting)
4. **Codespace Docling** — always-on PDF processing (1+ month request)
5. **8 pipelines (4×2)** — prod+test identical (user demand)
6. **S9 n8n fix or rebuild** — webhooks completely broken
7. **S2/S4 secrets** — need lbjlincoln26 HF token
