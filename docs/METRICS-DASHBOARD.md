# Nomos AI — Master Metrics Dashboard

> Auto-updated: 2026-03-12T11:00Z | Session: S105
> **Single source of truth for ALL system metrics.**

---

## 1. PIPELINES — Accuracy (29,564Q eval tracked, mass eval running)

| Pipeline | Finance | BTP | Juridique | Industrie | Status |
|----------|---------|-----|-----------|-----------|--------|
| **Standard V3.9** | ~38-50% | ~20% | ~80% | ~80% | WORKING |
| **Graph V3.6** | ~85-90% | ~60% | ~70% | ~70% | WORKING |
| **Quant V3.2** | ~98% | ~98% | N/A | N/A | WORKING |
| **Orchestrator V13** | ~85% | ~50% | ~75% | ~75% | WORKING |
| **Target** | 90% | 85% | 90% | 85% | — |

**All 4 pipelines WORKING on S1/S3/S5.** Mass eval running (Standard + Graph 200q, eval-blast 50q/30min).
**Bottleneck #1**: Standard Finance — keyword matching produces false negatives.
**Bottleneck #2**: BTP all pipelines — DATA GAP (no DTU/Eurocodes ingested yet).

## 2. DATABASES

| Database | Count | Change S105 | Target |
|----------|-------|-------------|--------|
| **E5 Pinecone** (sectors-e5-multilingual) | **~78,000 vectors** | +18,268 (Tavily 4 sectors) | 100,000 |
| **Jina Pinecone** (website-sectors-jina-1024) | 12,536 vectors | 0 | deprecated |
| **Legacy Pinecone** (sota-rag-jina-1024) | 0 | 0 | ARCHIVED |
| **Supabase** (sector_documents) | **~43,000 docs** | stable | 100,000 |
| **Supabase** (financials) | **225 rows** | 111 companies, 4 sectors | growing |
| **Neo4j** | ~71,890 nodes | 0 | 200,000 |

### Vector Breakdown (E5 Pinecone)
| Source | Count | Type |
|--------|-------|------|
| Academic benchmarks | ~59,523 | ragbench, hotpotqa, finqa, etc. |
| Expert (Tavily text) | ~18,300+ | Real sector documents (all 4 sectors) |
| Expert (Docling PDF) | ~200+ | Real PDF chunks |
| **Total** | **~78,000** | 78% of 100K target |

### Supabase Breakdown
| Dataset | Count | Type |
|---------|-------|------|
| ragbench_* | ~38,000 | Academic benchmarks |
| sector-specific | ~5,300 | Generated sector Q&A |
| expert-docling | ~200+ | Real PDF docs |
| **Total** | **~43,000** | |

## 3. INFRASTRUCTURE

### HF Spaces (10 slots)
| Space | Role | Health | Pipelines |
|-------|------|--------|-----------|
| S1 (engine) | Primary n8n | UP (200) | Std V3.9 + Graph V3.6 + Quant V3.2 + Orch V13 |
| S2 (engine-2) | Mirror n8n | UP (200*) | Shared DB with S1 |
| S3 (engine-3) | Load balance | UP (200) | All 4 pipelines |
| S4 (engine-4) | Mirror n8n | UP (200*) | Shared DB with S1 |
| S5 (engine-5) | Load balance | UP (200) | All 4 pipelines |
| S6 (docling-api) | Docling PDF processor | UP (no /healthz) | Docling converter |
| S7 (engine-7) | LiteLLM proxy | UP (no /healthz) | 9 models, 13 providers |
| S8 (eval-judge) | Eval judge | DOWN | Not deployed |
| S9 (engine-9) | Staging (separate DB) | UP (200) | Excluded from eval |
| Embeddings | Self-hosted Jina | UP (no /healthz) | v3, 1024 dims |

*S2/S4 use lbjlincoln26 account, different /healthz path. S1-S5 share same DB.

### VM GCP
| Metric | Value |
|--------|-------|
| IP | 34.136.180.66 |
| RAM | 969MB total, ~244MB free |
| Disk | 30GB |
| OS | Debian 11, Linux 6.1 |
| Role | Pilotage ONLY (no compute) |

### Codespaces
| Name | Repo | Status |
|------|------|--------|
| continuous-ingest | rag-data-ingestion | Intermittent (auto-shutdown) |
| website-redesign | rag-website | Shutdown |
| testing-daemon | rag-data-ingestion | Shutdown |
| monetisation-v2 | mon-ipad | Shutdown |

## 4. AGENTIC LOOP

| Metric | Value |
|--------|-------|
| Phases | 7 (STRATEGIZE-PLAN-BUILD-OBSERVE-COLLECT-ANALYZE-REPORT) |
| Cycle interval | 1800s (30 min) |
| Cycles completed | 17 |
| Current priority | BTP data gap + Standard Finance accuracy |
| Mass eval | Standard + Graph 200q, eval-blast 50q/30min |
| Continuous ingest | Tavily daemon active (all 4 sectors) |

### Agentic Loop Status
- All 4 pipelines now functional (Graph+Quant fixed since S103)
- eval-blast running every 30 min for regression detection
- Continuous ingest daemon feeding Tavily data to E5 Pinecone
- 29,564 eval questions tracked across all pipelines

## 5. SPECIALIZED AGENTS

| Agent | Status | Role | Notes |
|-------|--------|------|-------|
| monitor | RUNNING | Health checks, error detection | 5min loop |
| eval | RUNNING | Mass eval + eval-blast | Standard+Graph 200q, blast 50q/30min |
| ingest | RUNNING | Continuous Tavily + Docling | All 4 sectors, daemon mode |
| pipeline | ON-DEMAND | Fix workflows (Claude Code) | Manual intervention |
| docs | ON-DEMAND | Update state files | After milestones |

## 6. EVAL SYSTEM

| Metric | Value |
|--------|-------|
| Total questions tracked | **29,564** |
| Active evals | Mass eval (Standard+Graph 200q), eval-blast (50q/30min) |
| Workers | S1/S3/S5 (3 Spaces) |
| Target questions | 10,000 expert-grade |

### Eval Scores (S105, all 4 pipelines)
| Sector | Standard | Graph | Quant | Orchestrator | Target |
|--------|----------|-------|-------|-------------|--------|
| Finance | ~38-50% | ~85-90% | ~98% | ~85% | 90% |
| BTP | ~20% | ~60% | ~98% | ~50% | 85% |
| Juridique | ~80% | ~70% | N/A | ~75% | 90% |
| Industrie | ~80% | ~70% | N/A | ~75% | 85% |

## 7. SCRIPTS & TOOLS INVENTORY

### ops/ (Operations)
| Script | Role | Last Used | Status |
|--------|------|-----------|--------|
| `agentic-loop.py` | Master 7-phase loop | Running (daemon) | WORKING |
| `agents.py` | 5 agent launcher | S105 | WORKING |
| `fast-ingest.py` | E5 Pinecone upsert | S104 | WORKING |
| `staging-deploy.py` | CI/CD staging->prod | S98 | WORKING |
| `metrics-collector.py` | n8n execution metrics | Timeout | BROKEN (120s timeout) |
| `metrics-analyzer.py` | LLM metrics analysis | S97 | UNTESTED |
| `monitor.py` | Health dashboard | Running (agent) | WORKING |
| `deploy-eval-judge.py` | Deploy judge to S8 | Never | UNTESTED |
| `populate-quant-tables.py` | Quant financial data | S96 | WORKING |

### eval/ (Evaluation)
| Script | Role | Last Used | Status |
|--------|------|-----------|--------|
| `eval-blast.py` | 50q/30min continuous eval | S105 (running) | WORKING |
| `mass-eval.py` | Mass eval 200q batches | S105 (running) | WORKING |
| `parallel-eval.py` | 6-Space parallel eval | S103 | WORKING |
| `quick-test.py` | Smoke test | S103 | WORKING |
| `continuous-judge.py` | LLM-as-Judge | Running (agent) | WORKING |
| `expert-discovery.py` | Tavily doc finder | S104 | WORKING |
| `mass-question-generator.py` | 5K+ question gen | S97 | WORKING |
| `expert-eval.py` | Expert-grade eval | S97 | WORKING |
| `generate-graph-questions.py` | Graph eval questions | S105 | WORKING |
| `generate-quant-questions.py` | Quant eval questions | S105 | WORKING |
| `generate-standard-questions.py` | Standard eval questions | S105 | WORKING |

### codespace/ (Ingestion)
| Script | Role | Last Used | Status |
|--------|------|-----------|--------|
| `docling-cron.py` | Continuous PDF ingestion | S104 | WORKING |

### n8n/live/ (Workflows)
| Workflow | Version | ID | Status |
|----------|---------|-----|--------|
| Standard RAG | V3.9 | 9FQdtx38JLPiT3Hx | WORKING |
| Graph RAG | V3.6 | 6257AfT1l4FMC6lY | WORKING |
| Quantitative | V3.2 | cjhEhVs0KV1ExHqX | WORKING |
| Orchestrator | V13 | qOSaFFrqO8Jb4VGb | WORKING |
| Auto-Healer | V1.2 | Yqw7Pzn0e7m0C6i3 | RUNNING (10min) |
| Error Trigger | V1.0 | AH3eXOmgxt5cOd93 | ACTIVE |

## 8. REPOSITORIES

| Repo | Role | Status | Commits | Files |
|------|------|--------|---------|-------|
| **mon-ipad** | Tour de controle | ACTIVE | 1,500+ | 500+ |
| **rag-data-ingestion** | Ingestion engine | ACTIVE | ~200 | ~50 |
| **rag-website** | Chatbot product | ACTIVE | ~300 | ~100 |
| **rag-dashboard** | Metrics dashboard | ACTIVE | ~100 | ~30 |
| 11 others | Various | ARCHIVED | — | — |

## 9. CREDENTIALS & KEYS

| Service | Key Name | Status |
|---------|----------|--------|
| Pinecone | PINECONE_API_KEY | VALID |
| Supabase | SUPABASE_API_KEY (anon) | VALID (read-only for REST) |
| Supabase | DATABASE_URL (pooler) | VALID (write, needs `SET search_path TO public`) |
| Tavily | TAVILY_API_KEY | VALID |
| LiteLLM | sk-litellm-nomos-2026 | VALID |
| Neo4j | NEO4J_URI + AUTH | VALID |
| HuggingFace | HF_TOKEN | VALID |
| OpenRouter | sk-or-v1-... | LEAKED in workflow JSON (rotate!) |
| Jina | jina_... | EXPIRED + LEAKED in workflow JSON |
| GitHub | GH_TOKEN | VALID |

## 10. S103-S105 KEY FIXES

| # | Fix | Session | Impact |
|---|-----|---------|--------|
| 1 | All 4 pipelines 18/18 = 100% pass | S103 | Graph+Quant restored |
| 2 | 25 conflicting workflows deactivated | S103 | Eliminated random routing |
| 3 | Orchestrator Quant routing fixed | S103 | Quant calls S5 correctly |
| 4 | Quant 4-sector data: 225 rows, 111 companies | S103 | Full sector coverage |
| 5 | E5 vectors: 59K to 78K (+18K Tavily all 4 sectors) | S104 | Better retrieval coverage |
| 6 | Continuous ingest daemon (Tavily 4 sectors) | S104 | Automated data growth |
| 7 | Docling S6 integrated into continuous-ingest | S104 | PDF pipeline operational |
| 8 | Mass eval + eval-blast running | S105 | Continuous accuracy tracking |
| 9 | 29,564 eval questions tracked | S105 | Comprehensive evaluation |

## 11. GAPS & BLOCKERS

| Priority | Gap | Blocker | Impact |
|----------|-----|---------|--------|
| P0 | Standard Finance ~38-50% | Keyword matching = false negatives | Biggest accuracy gap |
| P0 | BTP all pipelines ~20-60% | DATA GAP — no DTU/Eurocodes ingested | Worst sector overall |
| P1 | Standard Juridique/Industrie ~80% | Near target but not there yet | Need 85-90% |
| P1 | Graph BTP ~60% | Sparse entity graph for BTP domain | Need sector-specific docs |
| P2 | Orchestrator BTP ~50% | Inherits weak sub-pipeline scores | Depends on Standard+Graph fixes |
| P2 | processing_queue empty | No Redis workers consuming queue | Can't scale ingestion |
| P2 | Codespace intermittent | Shutdown frequently | Interrupts PDF ingestion |
| P3 | S8 not deployed | eval-judge workflow not running | No continuous judging |
| P3 | OpenRouter key leaked | In workflow JSON files | Security risk |
