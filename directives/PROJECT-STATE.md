# Etat Systeme — Session 97

> Date: 2026-03-11T14:00Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM, 180MB free |
| **S1** (engine) | UP | 11 active workflows |
| **S2** (engine-2) | UP | 11 active workflows (mirror) |
| **S3** (engine-3) | UP | 11 active workflows |
| **S4** (engine-4) | UP | 11 active workflows (mirror) |
| **S5** (engine-5) | UP | 11 active workflows (FIXED S97 — DB corruption) |
| **S6** (Docling) | UP | converter loaded |
| **S7** (LiteLLM) | UP | 9 model groups, 13-provider fallback |
| **S8** (Eval Judge) | DOWN | Ready to deploy (eval-judge-workflow.json + deploy script) |
| **S9** (Staging) | UP | 13 active workflows, staging Space for CI/CD |
| **Embeddings** | UP | Self-hosted Jina v3, 1024 dims, no auth |
| **Reranker** | UP | Self-hosted FlashRank, Jina/Cohere-compatible API |

## 2. DATABASES

| DB | Vectors/Docs | Content |
|----|-------------|---------|
| **E5 Pinecone** (`sectors-e5-multilingual`) | **58,533** | PRIMARY — integrated E5 inference |
| **Jina Pinecone** (`website-sectors-jina-1024`) | **12,536** | SECONDARY — Jina embeddings |
| **Legacy Pinecone** (`sota-rag-jina-1024`) | **0** | ARCHIVED — EMPTY, do not query |
| **Neo4j** | Entity/Company/Org/Law/SectorDoc | UP |
| **Supabase** | **43,357** docs, 78 financials | + execution_scores table (NEW) |

## 3. PIPELINES — LATEST VERSIONS

| Pipeline | Deployed | Latest (to deploy) | Key Changes |
|----------|----------|-------------------|-------------|
| **Standard** | V3.8 (LiteLLM) | **V3.9** (multi-index) | E5 58K vectors + fix Pinecone + self-hosted reranker |
| **Graph** | V3.5 (LiteLLM) | **V3.6** (all endpoints) | Self-hosted embed + reranker + correct Pinecone |
| **Quant** | V3.2 (LiteLLM) | V3.2 (current) | Working, no changes needed |
| **Orchestrator** | V13 (regex) | **V14.1** (harness) | LLM intent + CoT planner + task engine + harness |

## 4. S97 ACCOMPLISHMENTS

### New Scripts (15 files, 16K+ lines)
- [x] `n8n/live/standard-rag-v3.9-multi-index.json` — E5 4th retrieval branch
- [x] `n8n/live/graph-rag-v3.6-fixed.json` — All endpoints fixed
- [x] `n8n/live/orchestrator-v14-llm.json` — LLM routing (lean)
- [x] `n8n/live/orchestrator-v14.1-harness.json` — Full harness (building)
- [x] `n8n/live/eval-judge-workflow.json` — LLM-as-Judge for S8
- [x] `eval/continuous-judge.py` — Daemon scoring + good/bad board
- [x] `eval/expert-discovery.py` — Tavily real doc discovery
- [x] `eval/mass-question-generator.py` — 5000+ questions from templates
- [x] `eval/queue-eval-orchestrator.py` — Redis-backed parallel eval
- [x] `ops/staging-deploy.py` — CI/CD: staging → smoke → promote
- [x] `ops/deploy-eval-judge.py` — Deploy eval judge to S8
- [x] `ops/fix-s5-activate.py` — S5 reactivation tool
- [x] `codespace/setup-docling.sh` — Docling setup on Codespace
- [x] `codespace/docling-cron.py` — Continuous PDF ingestion cron
- [x] `codespace/crontab.txt` — Cron schedule

### Fixes
- [x] S5 DB corruption → rebooted + reactivated all workflows
- [x] Graph timeout on S1 → workflow was deactivated, reactivated
- [x] Pinecone wrong index → V3.9 queries correct index + E5
- [x] Expired Jina embeddings → self-hosted embeddings Space
- [x] Expired Jina reranker → self-hosted FlashRank Space
- [x] Dataset expanded: 220 → 276 → 5,276 questions

### Findings
- **46K invisible vectors**: Pipelines queried archived index, missing 58K E5 vectors
- **V10.1 orchestrator**: Full harness existed but was abandoned due to Groq limits
- **Dual webhook paths**: Each Space has WF-WEB + our versions = 2x worker capacity

## 5. EVAL CAPACITY

| Metric | Value |
|--------|-------|
| Workers | 48 (6 Spaces × 4 pipelines × 2 webhooks) |
| Throughput | ~5,760 Q/hour |
| Dataset | 5,276 questions |
| Eval duration | ~55 min at full parallel |
| Queue | Redis-backed (Upstash) with backpressure |

## 6. NEXT PRIORITIES
1. **Deploy V3.9 Standard** via staging-deploy.py (S9 first → promote)
2. **Deploy V3.6 Graph** via staging-deploy.py
3. **Deploy V14.1 Orchestrator** (harness with disabled memory)
4. **Start S8** and deploy eval-judge workflow
5. **Run full 5276Q eval** via queue-eval-orchestrator
6. **Start Codespace** for Docling continuous ingestion
7. **Generate LLM-augmented questions** (5000 templates → 10K+ with LLM variation)
8. Re-enable V10.1 memory nodes once eval scores are solid
