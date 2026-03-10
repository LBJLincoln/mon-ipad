# Etat Systeme — Session 96

> Date: 2026-03-10T21:00Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM, Debian 11 |
| **S1** (engine) | UP | Standard + Graph + Orchestrator + Auto-Healer |
| **S3** (engine-3) | UP | Standard (load balance) |
| **S5** (engine-5) | UP | Standard (load balance) |
| **S9** (engine-9) | UP | Standard + Quant |
| **S6** (Docling) | UP | cpu-basic, OOM on large PDFs |
| **S7** (LiteLLM) | BROKEN | DB corruption |

### LLM Providers
| Provider | Status | Keys | Free Tier |
|----------|--------|------|-----------|
| Groq | WORKING | 5 | 100K tok/day |
| OpenAI | WORKING (429) | 1 | Rate limited |
| Gemini | WORKING (429) | 1 | Rate limited |
| OpenRouter | WORKING (429) | 7 | Rate limited |

## 2. DATABASES

| DB | Used | Free | Content |
|----|------|------|---------|
| **E5 Pinecone** | **55,584** | 44K | Sectors (Tavily + JSONL + PDF) |
| **Jina Pinecone** | ~43K | 57K | Legacy sectors |
| **Neo4j** | ~42K nodes | 158K | Entity + SectorDocument |
| **Supabase** | 43,357 docs | 415MB | sector_documents |

## 3. PIPELINES

| Pipeline | Status | Success Rate (6h) | Execs | Avg ms |
|----------|--------|-------------------|-------|--------|
| Standard | **WORKING** | 98% | 138 | 51s |
| Orchestrator | **WORKING** | 100% | 21 | 48s |
| Graph | **WORKING** | 100% | 12 | 11s |
| Quant | **WORKING** | 100% | 9 | 10s |
| Auto-Healer | **WORKING** | 83% | 24 | 198s |

### Workflow IDs
- Standard: `TmgyRP20N4JFd9CB` (V3.5 multi-index, S1/S3/S5)
- Graph: `6257AfT1l4FMC6lY` (V3.3)
- Quant: `cjhEhVs0KV1ExHqX` (V3.1)
- Orchestrator: `qOSaFFrqO8Jb4VGb` (V13)
- Auto-Healer: `Yqw7Pzn0e7m0C6i3` (V1.2b)

## 4. MONITORING

| Component | File | Auto-update |
|-----------|------|-------------|
| Live dashboard | `ops/monitor.py` | `--loop 300` |
| Error log | `logs/errors/pipeline-errors.jsonl` | Per execution |
| Health snapshot | `data/health-status.json` | Per monitor run |
| Full report | `logs/monitor-report.json` | Per monitor run |

## 5. SCRIPTS (canonical in ops/)

| Script | Lines | Purpose |
|--------|-------|---------|
| `ops/monitor.py` | 350 | **Unified monitor + error tracker** |
| `ops/fast-ingest.py` | 616 | Multi-threaded E5 ingestion |
| `ops/tavily-mass-ingest.py` | 450 | Web research + ingest |
| `ops/local-pdf-ingest.py` | 400 | PDF extraction + ingest |
| `ops/deploy-standard-v35.py` | 250 | Deploy to HF Spaces |
| `ops/n8n-api.py` | 250 | n8n workflow management |
| `ops/rag-proxy.py` | 120 | Direct E5+Groq proxy |
| `eval/quick-test.py` | 350 | Smoke tests |
| `eval/expert-eval.py` | 1159 | LLM-as-Judge evaluation |

## 6. PROGRESSION

### Stage 1 (CURRENT) — Retrieval Quality
- Gate: 50K E5 vectors (**PASSED**: 55,584)
- Gate: Standard 50% accuracy (NEEDS EVAL)
- Gate: Graph 20% accuracy (NEEDS EVAL)
- Next: Run 220q eval to establish baseline

### S96 Accomplishments
- [x] All 4 pipelines WORKING (Standard 98%, others 100%)
- [x] E5 vectors: 15,760 → 55,584 (Tavily BTP/Industrie + PDF ingest)
- [x] Orchestrator V13 rebuilt and working
- [x] Unified monitor with per-node error tracking
- [x] Repo cleanup: 6 duplicate scripts removed, 8 obsolete JSONs archived
- [x] PILOTAGE.md: Termius snippets + tmux cockpit
- [x] Stage 1 vector gate passed

## 7. NEXT PRIORITIES
1. Run full 220q eval → establish accuracy baseline
2. Fix weak sectors (BTP data gap)
3. Start continuous eval loop
4. Dashboard (rag-dashboard) → connect to health-status.json
5. Process improvement: segmented sub-agents
