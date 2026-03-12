# Etat Systeme — Session 105

> Date: 2026-03-12T12:00Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM |
| **S1** (engine) | UP | RAG: Standard V3.5 + Graph V3.7 + Quant V3.1 + Orch V13 |
| **S3** (engine-3) | UP | RAG: Same as S1 (shared DB) |
| **S5** (engine-5) | UP | RAG: Same as S1 (shared DB) |
| **S6** (Docling) | UP | CPU-basic, 10MB/20page limits |
| **S7** (LiteLLM) | UP | `Bearer sk-litellm-nomos-2026` — ALL pipelines use it |
| **S9** (INGEST) | UP | Ingestion V4.0 + Enrichment V4.0 workflows |
| **Embeddings** | UP | Self-hosted Jina v3, 1024 dims |
| **Reranker** | UP | Self-hosted FlashRank ms-marco-MiniLM |

## 2. DATABASES

| DB | Vectors/Docs | Content |
|----|-------------|---------|
| **E5 Pinecone** (`sectors-e5-multilingual`) | **~78,000** (78% of 100K target — daemon active) | PRIMARY — integrated E5 inference |
| **Jina Pinecone** (`website-sectors-jina-1024`) | **12,536** | SECONDARY — Jina embeddings |
| **Neo4j** | **71,890** nodes (33K Entity, 30K SectorDoc, 5.2K Law, 1.6K Org), 143K rels | UP |
| **Supabase** | **43K** docs, **225** financials (111 companies, 4 sectors), 3,876 sector_financial_tables, **29,564** eval questions in `eval_question_bank` | UP |

## 3. PIPELINES — CANONICAL VERSIONS

| Pipeline | Workflow ID | Version | Spaces | Status |
|----------|-----------|---------|--------|--------|
| **Standard** | `9FQdtx38JLPiT3Hx` | V3.5 | S1, S3, S5 | WORKING |
| **Graph** | `6257AfT1l4FMC6lY` | V3.7 | S1, S3, S5 | WORKING |
| **Quant** | `cjhEhVs0KV1ExHqX` | V3.1 | S1, S3, S5 | WORKING |
| **Orchestrator** | `qOSaFFrqO8Jb4VGb` | V13 | S1, S3, S5 | WORKING |
| **Ingestion** | `nh1D4Up0wBZhuQbp` | V4.0 | S9 | ACTIVE |
| **Enrichment** | `ORa01sX4xI0iRCJ8` | V4.0 | S9 | ACTIVE |
| Dashboard | — | — | S1 | ACTIVE |
| Debug | — | — | S1 | ACTIVE |
| Auto-Healer | `Yqw7Pzn0e7m0C6i3` | V1.2 | S1 | ACTIVE |
| Error Trigger | `AH3eXOmgxt5cOd93` | V1.0 | S1 | ACTIVE |

**10 n8n workflows active total.** S1/S3/S5: RAG. S9: Ingest+Enrichment.

## 4. S105 ACCOMPLISHMENTS

### Post-Crash Recovery (S104 agentic loop crash)
- [x] **Recovered from S104 agentic loop crash** — daemon restarted, state files restored
- [x] **Agentic loop running**: cycle 19, 30min daemon intervals
- [x] **Tokens updated**: N8N API + MCP + HF_TOKEN_3 (new HF account)

### Infrastructure Cleanup
- [x] **Docs cleaned**: 2,582 → 2,251 files, 55M → 9.3M logs
- [x] **STATUS.md created** as single source of truth
- [x] **S9 repurposed**: Ingestion V4.0 (nh1D4Up0wBZhuQbp) + Enrichment V4.0 (ORa01sX4xI0iRCJ8) workflows active

### Eval Scale-Up
- [x] **29,564 eval questions** tracked in Supabase `eval_question_bank`
- [x] **Mass eval running**: Standard + Graph 200q each
- [x] **Eval blast**: 50q/run tracking results to Supabase
- [x] **E5 vectors**: 74,718 → **~78,000** (+3.3K, daemon still growing)

### Continuous Ingest Daemon
- [x] **Daemon RUNNING** — Tavily (4 sectors) + fast-ingest + Docling S6
- [x] **10 n8n workflows active** — 6 RAG + Ingestion V4.0 + Enrichment V4.0 + Dashboard + Debug

### Previous S104 Accomplishments (retained)
- [x] continuous-ingest.py daemon — 24/7 hourly cycles
- [x] Neo4j enrichment integrated into cycle
- [x] 18/18 = 100% PASS on 4-pipeline eval
- [x] Tavily JSONL output for Neo4j enrichment

## 5. EVAL RESULTS (S105)

### Accuracy by Pipeline (mass eval in progress)
| Pipeline | Accuracy Range | Notes |
|----------|---------------|-------|
| **Standard** | ~38-50% (finance) | Weakest — data gaps, BTP worst |
| **Graph** | ~85-90% | Strong on relationship queries |
| **Quant** | ~98% | Near-perfect on financial data |
| **Orchestrator** | Routing correct | Delegates to sub-pipelines |

### Mass Eval Status
- Standard: 200q batch running
- Graph: 200q batch running
- Eval blast: 50q/run → Supabase tracking
- 29,564 eval questions in `eval_question_bank`

## 6. RUNNING PROCESSES
- **Agentic loop daemon** — cycle 19, 30min intervals
- **Continuous-ingest daemon** — Tavily (4 sectors) + fast-ingest + Docling S6
- **Mass eval** — Standard + Graph 200q each, eval blast 50q/run
- Monitor agent (5min cycle)
- 5 agents (monitor, eval, ingest, pipeline, docs)

## 7. NEXT PRIORITIES
1. **Reach 100K vectors** — at ~78K (78%), daemon growing
2. **Standard pipeline accuracy** — 38-50% finance is too low, BTP weakest (data gap)
3. **Codespace Docling** — always-on PDF processing (1+ month request)
4. **8 pipelines (4x2)** — prod+test identical (user demand)
5. **Redis queue workers** — Upstash creds exist, workers not built
6. **Expert eval 10K questions** — 29,564 in eval_question_bank, need quality curation
7. **BTP data gap** — weakest sector, needs targeted ingestion
