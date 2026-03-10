# Etat Systeme — Session 96 (continued)

> Date: 2026-03-10T23:25Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM, 264MB free |
| **S1** (engine) | UP | Standard+Graph+Orch+AutoHealer+ErrorTrigger |
| **S3** (engine-3) | UP | Standard+ErrorTrigger (load balance) |
| **S5** (engine-5) | UP | Standard+ErrorTrigger (load balance) |
| **S9** (engine-9) | UP | Standard+Quant+ErrorTrigger |
| **S6** (Docling) | UP | converter loaded, health OK |
| **S7** (LiteLLM) | BROKEN | DB corruption |

## 2. DATABASES

| DB | Used | Content |
|----|------|---------|
| **E5 Pinecone** | **58,533** vectors | Sectors (target 100K) |
| **Jina Pinecone** | ~43K vectors | Legacy (still queried in multi-index) |
| **Neo4j** | **71,890** nodes | Entity + SectorDocument |
| **Supabase** | **43,357** docs | finance 25.8K, juridique 10.1K, btp 4.4K, industrie 2.9K |
| **Supabase pipeline_errors** | NEW | Auto-captures n8n errors via Error Trigger |

## 3. PIPELINES — ALL WORKING

### Smart Smoke Test Results (V3.7)
| Pipeline | Pass | Score | Latency | Status |
|----------|------|-------|---------|--------|
| **Standard** | 3/3 | **100/100** | 46s | OK |
| **Orchestrator** | 3/3 | **95/100** | 39s | OK |
| **Graph** | 2/3 | **70/100** | 12s | PARTIAL |
| **Quant** | 0/3 | **40/100** | 0.6s | NEEDS FIX |
| Docling | - | OK | - | converter loaded |

### Workflow IDs
| Pipeline | ID | Version | Spaces |
|----------|----|---------|--------|
| Standard | `TmgyRP20N4JFd9CB` | V3.7 | S1/S3/S5/S9 |
| Graph | `6257AfT1l4FMC6lY` | V3.4 | S1/S3/S5/S9 |
| Quant | `cjhEhVs0KV1ExHqX` | V3.1 | S1/S3/S5 |
| Orchestrator | `qOSaFFrqO8Jb4VGb` | V13 | S1/S3/S5 |
| Auto-Healer | `Yqw7Pzn0e7m0C6i3` | V1.2 | S1/S3/S5 |
| Error Trigger | `AH3eXOmgxt5cOd93` / `JyrwJ6UOQeSH9WXX` | V1.0 | ALL |
| Ingestion | `nh1D4Up0wBZhuQbp` | V4.0 | ALL |
| Enrichissement | `ORa01sX4xI0iRCJ8` | V4.0 | ALL |

## 4. MONITORING & TOOLS

| Component | File | Purpose |
|-----------|------|---------|
| Smart Smoke Test | `eval/smart-smoke.py` | 12 golden Q&A, node-by-node regression |
| Error Trigger | `n8n/live/error-trigger-handler.json` | Auto-log errors to Supabase |
| Error Analyzer | `ops/error-analyzer.py` | Success+error analysis, node metrics |
| Workflow Cleanup | `ops/cleanup-workflows.py` | Export/delete 100+ inactive workflows |
| Unified Monitor | `ops/monitor.py` | Live CLI dashboard, JSONL logging |
| Deploy Tool | `ops/deploy-error-trigger.py` | Deploy Error Trigger to all Spaces |
| Deploy Standard | `ops/deploy-standard-v35.py` | Deploy Standard to all Spaces |

## 5. S96 CONTINUED ACCOMPLISHMENTS
- [x] **ERROR TRIGGER n8n DEPLOYED** — All 4 Spaces, linked to all pipelines
- [x] **Standard V3.7** — tenant_id fallback to sector, BM25 GIN index
- [x] **Juridique FIXED** — Was 91s timeout → 31s with 10 sources
- [x] **Smart Smoke Test** — 12 golden Q&A, parallel, node-by-node comparison
- [x] **Supabase pipeline_errors** — Auto-captures all n8n failures
- [x] **Supabase FTS GIN index** — French text search on sector_documents.context
- [x] **Full workflow inventory** — 134 per Space, ~20 active
- [x] All 4 sectors Standard: 100/100 score, 10 sources each

## 6. V3.7 FIXES (CRITICAL)
1. `tenant_id` now falls back to `input.sector` (was 'default' → 0 sources)
2. BM25 GIN index: `to_tsvector('french', context)` on sector_documents
3. Both fixes = juridique works (was impossible before)

## 7. NEXT PRIORITIES
1. Fix Quant pipeline (NO_ANSWER — financial data mapping issue)
2. Run full 220q eval with V3.7
3. Clean 100+ inactive workflows from Spaces
4. E5 sector filter (integrated embedding API needs different format)
5. Continuous error analysis via error-analyzer.py
6. Reranking (FlashRank Space exists, not integrated)
