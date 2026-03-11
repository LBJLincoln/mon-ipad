# Nomos AI — Master Metrics Dashboard

> Auto-updated: 2026-03-11T18:45Z | Session: S99
> **Single source of truth for ALL system metrics.**

---

## 1. PIPELINES — Accuracy (5,276Q eval running)

| Pipeline | Finance | BTP | Juridique | Industrie | Status |
|----------|---------|-----|-----------|-----------|--------|
| **Standard V3.9** | ~40% | ~27% | ~69% | ~53% | WORKING |
| **Graph V3.6** | 0% | 0% | 0% | 0% | BROKEN (120s timeout — S7 LLM hangs) |
| **Quant V3.2** | 0% | 0% | 0% | 0% | BROKEN ("Error in workflow") |
| **Orchestrator V13** | ~40% | ~35% | ~45% | ~40% | WORKING |
| **Target** | 90% | 85% | 90% | 85% | — |

**Root cause Graph+Quant**: Both call LiteLLM S7 which works with correct key, but n8n stored credentials may override. Investigating.

## 2. DATABASES

| Database | Count | Change S99 | Target |
|----------|-------|------------|--------|
| **E5 Pinecone** (sectors-e5-multilingual) | **59,732 vectors** | +54 (DTU expert) | 100,000 |
| **Jina Pinecone** (website-sectors-jina-1024) | 12,536 vectors | 0 | deprecated |
| **Legacy Pinecone** (sota-rag-jina-1024) | 0 | 0 | ARCHIVED |
| **Supabase** (sector_documents) | **43,410 docs** | +53 (DTU expert) | 100,000 |
| **Supabase** (processing_queue) | **0 items** | 0 | queue active |
| **Neo4j** | ~86,841 nodes | 0 | 200,000 |

### Vector Breakdown (E5 Pinecone)
| Source | Count | Type |
|--------|-------|------|
| Academic benchmarks | ~59,523 | ragbench, hotpotqa, finqa, etc. |
| Expert (Tavily text) | ~155 | Real sector documents |
| Expert (Docling PDF) | **54** | Real DTU PDF chunks (NEW S99) |
| **Total** | **59,732** | 59.7% of 100K target |

### Supabase Breakdown
| Dataset | Count | Type |
|---------|-------|------|
| ragbench_* | ~38,000 | Academic benchmarks |
| sector-specific | ~5,300 | Generated sector Q&A |
| expert-docling-dtu | **53** | Real PDF docs (NEW S99) |
| **Total** | **43,410** | |

## 3. INFRASTRUCTURE

### HF Spaces (10 slots)
| Space | Role | Health | Pipelines |
|-------|------|--------|-----------|
| S1 (engine) | Primary n8n | UP (200) | Std V3.9 + Graph V3.6 + Quant V3.2 + Orch V13 |
| S2 (engine-2) | Mirror n8n | UP (200*) | Std V3.9 + Graph V3.6 |
| S3 (engine-3) | Load balance | UP (200) | Std V3.9 + Graph V3.6 |
| S4 (engine-4) | Mirror n8n | UP (200*) | Std V3.9 + Graph V3.6 |
| S5 (engine-5) | Load balance | UP (200) | Std V3.9 + Graph V3.6 |
| S6 (docling-api) | Docling PDF processor | UP (no /healthz) | Docling converter |
| S7 (engine-7) | LiteLLM proxy | UP (no /healthz) | 9 models, 13 providers |
| S8 (eval-judge) | Eval judge | DOWN | Not deployed |
| S9 (engine-9) | Staging | UP (200) | Std V3.9 + Graph V3.6 |
| Embeddings | Self-hosted Jina | UP (no /healthz) | v3, 1024 dims |

*S2/S4 use lbjlincoln26 account, different /healthz path

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
| continuous-ingest | rag-data-ingestion | **Shutdown** (should be running!) |
| website-redesign | rag-website | Shutdown |
| testing-daemon | rag-data-ingestion | Shutdown |
| monetisation-v2 | mon-ipad | Shutdown |

## 4. AGENTIC LOOP

| Metric | Value |
|--------|-------|
| Daemon PID | 779132 |
| Phases | 7 (STRATEGIZE-PLAN-BUILD-OBSERVE-COLLECT-ANALYZE-REPORT) |
| Cycle interval | 1800s (30 min) |
| Cycles completed | 7 |
| Current priority | BTP data gap (DTU norms ingestion) |
| Last score | 39/100 (+6 pts) |
| Improvements | 2 total |

### Agentic Loop Limitations (to fix)
- Only detects "data gaps", not "broken pipelines"
- Doesn't auto-fix Graph/Quant (treats 0% as bad sector, not broken workflow)
- Expert discovery (Tavily) times out at 180s
- No Redis for queue management
- BUILD phase works but limited to data ingestion

## 5. SPECIALIZED AGENTS

| Agent | PID | Status | Role | Last Activity |
|-------|-----|--------|------|---------------|
| monitor | 776716 | RUNNING | Health checks, error detection | 2min ago |
| eval | 776717 | RUNNING | Accuracy baselines | active |
| ingest | 776718 | RUNNING | E5 vectors, Tavily, PDF | active |
| pipeline | 776719 | RUNNING | Fix workflows | active |
| docs | 776720 | RUNNING | Update state files | active |

## 6. EVAL SYSTEM

| Metric | Value |
|--------|-------|
| Total questions | 5,572 (5,276 extended + 289 full + 27 smoke) |
| Current eval | 5,276Q running, 2,620/5,276 done (50%) |
| Workers | 24 across 6 Spaces |
| Speed | 0.6 Q/s (~36 Q/min) |
| ETA | ~75 min remaining |
| Target questions | 10,000 expert-grade |

### Eval Scores (S98 baseline, 20Q smoke)
| Sector | Standard | Target |
|--------|----------|--------|
| BTP | 27/100 | 85% |
| Finance | 39/100 | 90% |
| Industrie | 53/100 | 85% |
| Juridique | 69/100 | 90% |

## 7. SCRIPTS & TOOLS INVENTORY

### ops/ (Operations)
| Script | Role | Last Used | Status |
|--------|------|-----------|--------|
| `agentic-loop.py` | Master 7-phase loop | Running (daemon) | WORKING |
| `agents.py` | 5 agent launcher | S99 | WORKING |
| `fast-ingest.py` | E5 Pinecone upsert | S98 | WORKING |
| `staging-deploy.py` | CI/CD staging->prod | S98 | WORKING |
| `metrics-collector.py` | n8n execution metrics | Timeout | BROKEN (120s timeout) |
| `metrics-analyzer.py` | LLM metrics analysis | S97 | UNTESTED |
| `monitor.py` | Health dashboard | Running (agent) | WORKING |
| `deploy-eval-judge.py` | Deploy judge to S8 | Never | UNTESTED |
| `populate-quant-tables.py` | Quant financial data | S96 | WORKING |

### eval/ (Evaluation)
| Script | Role | Last Used | Status |
|--------|------|-----------|--------|
| `parallel-eval.py` | 6-Space parallel eval | Running now | WORKING |
| `quick-test.py` | Smoke test | S98 | WORKING |
| `continuous-judge.py` | LLM-as-Judge | Running (agent) | WORKING |
| `expert-discovery.py` | Tavily doc finder | S98 | TIMEOUT (180s) |
| `mass-question-generator.py` | 5K+ question gen | S97 | WORKING |
| `expert-eval.py` | Expert-grade eval | S97 | WORKING |
| `turbo-eval.py` | Fast eval | S96 | UNTESTED |

### codespace/ (Ingestion)
| Script | Role | Last Used | Status |
|--------|------|-----------|--------|
| `docling-cron.py` | Continuous PDF ingestion | S99 (fixed) | FIXED (was broken) |

### n8n/live/ (Workflows)
| Workflow | Version | ID | Status |
|----------|---------|-----|--------|
| Standard RAG | V3.9 | TmgyRP20N4JFd9CB | WORKING |
| Graph RAG | V3.6 | 6257AfT1l4FMC6lY | BROKEN (timeout) |
| Quantitative | V3.2 | cjhEhVs0KV1ExHqX | BROKEN (error) |
| Orchestrator | V13 | qOSaFFrqO8Jb4VGb | WORKING |
| Ingestion V4.0 | V4.0 | nh1D4Up0wBZhuQbp | NOT WIRED (wrong endpoints) |
| Enrichment V4.0 | V4.0 | ORa01sX4xI0iRCJ8 | NOT WIRED (wrong endpoints) |
| Auto-Healer | V1.2 | Yqw7Pzn0e7m0C6i3 | RUNNING (10min) |

## 8. REPOSITORIES

| Repo | Role | Status | Commits | Files |
|------|------|--------|---------|-------|
| **mon-ipad** | Tour de controle | ACTIVE | 1,453 | 473 |
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

## 10. S99 FIXES APPLIED

| # | Fix | Impact |
|---|-----|--------|
| 1 | docling-cron.py: `full_text` not `markdown` | Unblocks PDF ingestion |
| 2 | docling-cron.py: Supabase schema corrected | Docs now persist |
| 3 | DATABASE_URL: `SET search_path TO public` | Fixed 159 "ghost" inserts from S98 |
| 4 | First real PDF E2E: DTU → Docling → E5 + Supabase | 53 expert chunks |
| 5 | parallel-eval.py: --extended flag | 5K eval capability |
| 6 | All 5 agents launched | Continuous monitoring |
| 7 | S7 LiteLLM: WORKS (was reported 401, key is correct) | LLM available |

## 11. GAPS & BLOCKERS

| Priority | Gap | Blocker | Impact |
|----------|-----|---------|--------|
| P0 | Graph V3.6 broken | Timeout calling S7 (LLM hangs in n8n) | 0% accuracy |
| P0 | Quant V3.2 broken | Workflow crash | 0% accuracy |
| P1 | Ingestion V4.0 wrong endpoints | unstructured.io, wrong Pinecone | Can't use n8n ingestion |
| P1 | Enrichment V4.0 wrong endpoints | Wrong Pinecone index, node name bug | Can't enrich docs |
| P1 | Codespace not running | Shutdown | No continuous PDF ingestion |
| P2 | processing_queue empty | No workers consuming queue | Can't scale ingestion |
| P2 | 0 real PDFs in pipeline DB | Only 53 DTU chunks so far | Missing expert data |
| P2 | Agentic loop limited | Only data gaps, not pipeline fixes | Misses broken pipelines |
| P3 | S8 not deployed | eval-judge workflow not running | No continuous judging |
| P3 | OpenRouter key leaked | In workflow JSON files | Security risk |
