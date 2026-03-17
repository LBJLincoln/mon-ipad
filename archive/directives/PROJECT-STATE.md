# Etat Systeme — Session 106

> Date: 2026-03-12T16:40Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

### LBJLincoln Spaces (7)
| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM |
| **S1** (engine) | UP | RAG: Standard V3.5 + Graph V3.3 + Quant V3.1 + Orch V13 |
| **S3** (engine-3) | UP | RAG: Same as S1 (shared DB) |
| **S5** (engine-5) | UP | RAG: Same as S1 (shared DB) |
| **S6** (Docling) | UP | CPU-basic, 10MB/20page limits |
| **S7** (LiteLLM) | UP | `Bearer sk-litellm-nomos-2026` — ALL pipelines use it |
| **S9** (INGEST) | UP | Ingestion V4.0 + Enrichment V4.0 workflows |
| **Embeddings** | UP | Self-hosted Jina v3, 1024 dims |

### Nomos42 Spaces (5) — NEW in S106
| Composant | Status | Notes |
|-----------|--------|-------|
| **S11** (engine-11) | RUNNING | Standard + Orchestrator working, Graph/Quant TBD |
| **Embeddings-2** | RUNNING | Jina v3 duplicate |
| **Docling-2** | RUNNING | Gradio Docling duplicate |
| **LiteLLM-2** | RUNNING | LiteLLM proxy duplicate |
| **Worker-2** | RUNNING | n8n instance (no workflows loaded yet) |

## 2. DATABASES

| DB | Vectors/Docs | Content |
|----|-------------|---------|
| **E5 Pinecone** (`sectors-e5-multilingual`) | **~78,000** (78% of 100K target — daemon active) | PRIMARY — integrated E5 inference |
| **Jina Pinecone** (`website-sectors-jina-1024`) | **12,536** | SECONDARY — Jina embeddings |
| **Neo4j** | **71,890** nodes (33K Entity, 30K SectorDoc, 5.2K Law, 1.6K Org), 143K rels | UP |
| **Supabase** | **43K** docs, **225** financials (111 companies, 4 sectors), 3,876 sector_financial_tables, **29,693** eval questions in `eval_question_bank` | UP |

## 3. PIPELINES — CANONICAL VERSIONS

| Pipeline | Workflow ID | Version | Spaces | Status |
|----------|-----------|---------|--------|--------|
| **Standard** | `9FQdtx38JLPiT3Hx` | V3.5 | S1, S3, S5, S11 | WORKING |
| **Graph** | `6257AfT1l4FMC6lY` | V3.3 | S1, S3, S5 | WORKING (reactivated S106) |
| **Quant** | `cjhEhVs0KV1ExHqX` | V3.1 | S1, S3, S5 | WORKING |
| **Orchestrator** | `qOSaFFrqO8Jb4VGb` | V13 | S1, S3, S5, S11 | WORKING |
| **Ingestion** | `nh1D4Up0wBZhuQbp` | V4.0 | S9 | ACTIVE |
| **Enrichment** | `ORa01sX4xI0iRCJ8` | V4.0 | S9 | ACTIVE |
| Dashboard | — | — | S1 | ACTIVE |
| Debug | — | — | S1 | ACTIVE |
| Auto-Healer | `Yqw7Pzn0e7m0C6i3` | V1.2 | S1 | ACTIVE |
| Error Trigger | `AH3eXOmgxt5cOd93` | V1.0 | S1 | ACTIVE |

**10 n8n workflows active on S1.** S9: Ingest+Enrichment. S11: Standard+Orchestrator.

## 4. S106 ACCOMPLISHMENTS

### Graph Pipeline Recovery
- [x] **Graph pipeline was DOWN** — credential unlinked (`Community Summaries Fetch` missing postgres)
- [x] **Fixed & reactivated** — credential reassigned, workflow activated via API

### Nomos42 Account (5 spaces deployed)
- [x] **S11 (n8n engine)** — RUNNING, Standard + Orchestrator functional
- [x] **Embeddings-2** — RUNNING, Jina v3 1024d duplicate
- [x] **Docling-2** — RUNNING, Gradio Docling duplicate (fixed SDK from docker→gradio)
- [x] **LiteLLM-2** — RUNNING, proxy duplicate
- [x] **Worker-2** — RUNNING (fixed BUILD_ERROR: missing n8n-workflows dir)

### Expert Question Generation (Exa.AI+LLM)
- [x] **129 expert questions** generated across all 4 sectors (up from 69)
- [x] Finance: 42 expert questions with golden answers + source URLs
- [x] BTP: 45 expert questions
- [x] Juridique: 21+ expert questions
- [x] Industrie: 21+ expert questions
- [x] Supabase schema extended: `golden_answer`, `source_url`, `category` columns added

### Dashboard & Documentation
- [x] **Dashboard HTML regenerated** with live Supabase data
- [x] **Unified System Reference** (600+ lines, 16 sections)
- [x] **Two-system agent architecture** defined (ops/agents-separated.py)

## 5. EVAL RESULTS (S106 — 208 results in 24h)

### Accuracy by Pipeline (24h window)
| Pipeline | Pass/Total | Accuracy | Target | Gap |
|----------|-----------|----------|--------|-----|
| **Quantitative** | 107/108 | **99.1%** | 95% | +4.1% |
| **Standard** | 41/58 | **70.7%** | 90% | -19.3% |
| **Orchestrator** | 3/5 | **60.0%** | 85% | -25% (small sample) |
| **Graph** | 17/37 | **45.9%** | 75% | -29.1% |

### Accuracy by Sector (24h window)
| Sector | Pass/Total | Accuracy | Target |
|--------|-----------|----------|--------|
| **Finance** | 69/81 | **85.2%** | 90% |
| **Industrie** | 45/56 | **80.4%** | 85% |
| **Juridique** | 26/33 | **78.8%** | 90% |
| **BTP** | 28/38 | **73.7%** | 85% |

## 6. RUNNING PROCESSES
- **Agentic loop daemon** — eval blast 50q/run, 30min intervals
- **Continuous-ingest daemon** — Exa.AI (4 sectors) + fast-ingest + Docling S6
- **Expert question generator** — juridique + industrie batches in progress
- **Eval blast** — 40q multi-pipeline in progress
- Monitor agent (5min cycle)

## 7. NEXT PRIORITIES
1. **Standard pipeline accuracy** — 70.7% vs 90% target. Biggest gap
2. **Graph pipeline accuracy** — 45.9% vs 75% target. Data quality issue
3. **Reach 100K vectors** — at ~78K (78%), daemon growing
4. **S11 Graph+Quant** — need workflow import on Nomos42
5. **Redis queue workers** — Upstash creds exist, workers not built
6. **BTP data gap** — weakest sector (73.7%), needs targeted ingestion
7. **Worker-2 workflows** — n8n running but no workflows imported
