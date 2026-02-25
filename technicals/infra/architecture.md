# Architecture Reference — Multi-RAG Orchestrator SOTA 2026

> Last updated: 2026-02-25T11:30:00+00:00
> Reference detaillee. Pour demarrage rapide, utiliser `docs/status.json`.

---

## Architecture globale (Session 62 — 25 fev 2026)

```
VM Google Cloud (34.136.180.66) — PERMANENT (PILOTAGE UNIQUEMENT)
  n8n Docker : REMOVED (Session 42) — All n8n moved to HF Spaces
  Redis : REMOVED (Session 60 — Orchestrator Redis removed)
  PostgreSQL : REMOVED (Session 42)
  Claude Code : Termius terminal (pilotage + eval orchestration)
  ⚠️ Eval runs from VM → HF Space webhooks (round-robin routing)
  ⚠️ RAM ~413MB available (n8n removed, lightweight only)
  MCP Servers : ~6MB total (negligeable)

HF Spaces (10 deployed — Session 62) — DISTRIBUTED EXECUTION
  Architecture : 10 spaces across 2 accounts (round-robin routing)
    - LBJLincoln account : Spaces 1, 3, 5, 7, 9 (odd)
    - LBJLincoln26 account : Spaces 2, 4, 6, 8, 10 (even)

  Each space :
    - n8n 2.8.3 : 16GB RAM, SQLite DB
    - Identical workflow imports (4 RAG pipelines + support)
    - N8N_BLOCK_ENV_ACCESS_IN_NODE=false (added to entrypoint.sh)
      ⚠️ CRITICAL FIX pending rebuild — enables $env.VAR_NAME access
    - Independent credentials (12+ per space)

  Eval strategy :
    - VM runs eval scripts (quick-test.py, iterative-eval.py)
    - Round-robin routing to 10 HF Space endpoints
    - 10x throughput vs single-space architecture

  Status (Session 62) :
    - All 4 pipelines working : Standard, Graph, Quantitative, Orchestrator
    - Orchestrator : Redis removed (9 nodes bypassed), Postgres-only mode
    - Phase 2 eval running across all spaces

GitHub — Source de verite
  n8n/live/     : Workflows Phase 1 (benchmark)
  n8n/website/  : Workflows website (copies Phase 1 + ingestion secteurs)
  n8n/validated/: Snapshots versiones

Codespace rag-tests — NOT USED (eval runs from VM)
  n8n LOCAL (3 workers, docker-compose)
  ⚠️ DEPRECATED : Eval moved to VM → HF Spaces architecture

Codespace rag-website — Site + demos secteurs
  n8n LOCAL (docker-compose)
  Import workflows depuis n8n/website/
  Ingestion secteurs → Pinecone website-sectors-jina-1024

Codespace rag-data-ingestion — Ingestion benchmarks
  n8n LOCAL (2 workers, docker-compose)
  Import workflows Ingestion V3.1 + Enrichissement V3.1
  → Pinecone sota-rag-jina-1024, Neo4j, Supabase
```

### Decision architecturale critique (Session 25)

**VM = PILOTAGE UNIQUEMENT** — Regles 25, 28, 29

| Action | Ou l'executer | Pourquoi |
|--------|---------------|----------|
| Modifier un workflow n8n | HF Space ou Codespace | Task Runner VM cache le code compile (Pattern 2.11) |
| Tester un pipeline (1/1, 5/5) | HF Space (16GB) | RAM VM insuffisante + Task Runner cache |
| Full eval (50q+) | Codespace rag-tests (8GB) | Docker-compose 3 workers |
| Piloter, committer, analyser | VM | Claude Code CLI + git + MCP |
| Stocker workflows | VM n8n | PostgreSQL permanent |

---

## n8n Docker Workflows (Phase 1 — Codespace rag-tests)

### Pipelines RAG (4)

| Workflow | Webhook Path (COMPLET) | Field | DB | Docker ID |
|---|---|---|---|---|
| Standard RAG V3.4 | `/webhook/rag-multi-index-v3` | query | Pinecone | `TmgyRP20N4JFd9CB` |
| Graph RAG V3.3 | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | query | Neo4j + Supabase | `6257AfT1l4FMC6lY` |
| Quantitative V2.0 | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | query | Supabase REST API (exec_sql RPC) | `e465W7V9Q8uK6zJE` |
| Orchestrator V10.1 | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | query | Routes to above | `aGsYnJY9nNCaTM82` |

### Support Workflows — Actifs (5 apres audit session 18)

| Workflow | Docker ID | Statut |
|---|---|---|
| Ingestion V3.1 | `15sUKy5lGL4rYW0L` | GARDER |
| Enrichissement V3.1 | `9V2UTVRbf4OJXPto` | GARDER |
| Benchmark V3.0 | `LKZO1QQY9jvBltP0` | GARDER — script benchmark automatise |
| Dataset Ingestion Pipeline | `YaHS9rVb1osRUJpE` | GARDER — pipeline HuggingFace → Pinecone |
| SQL Executor Utility | `22k9541l9mHENlLD` | GARDER — sub-workflow utilise par quantitative |

### Support Workflows — Supprimes (audit session 18)

| Workflow | Docker ID | Raison suppression |
|---|---|---|
| Feedback V3.1 | `F70g14jMxIGCZnFz` | Reference DeepSeek API non configure, SLACK_WEBHOOK_URL absent |
| Monitoring & Alerting | `tLNh3wTty7sEprLj` | OTEL_EXPORTER non configure, aucun monitoring actif |
| Orchestrator Tester | `m9jaYzWMSVbBFeSf` | Duplique `eval/quick-test.py --pipeline orchestrator` |
| RAG Batch Tester | `y2FUkI5SZfau67dN` | Duplique `eval/quick-test.py` |

---

## Architecture 16 Workflows (Cible)

### Category A : Test-RAG (4 pipelines actifs)
| Workflow | BDD | Activation |
|----------|-----|------------|
| Standard RAG V3.4 | Pinecone `sota-rag-jina-1024` | Actif maintenant |
| Graph RAG V3.3 | Neo4j general + Supabase `public` | Actif maintenant |
| Quantitative V2.0 | Supabase `public` | Actif maintenant |
| Orchestrator V10.1 | Meta (route vers A) | Actif maintenant |

### Category B : Sector (4 pipelines — apres Phase 2 validee)
| Workflow | BDD | Activation |
|----------|-----|------------|
| Sector Standard | Pinecone `website-sectors-jina-1024` | Apres Phase 2 |
| Sector Graph | Neo4j labels `WEB_*` | Apres Phase 2 |
| Sector Quantitative | Supabase schema `website_*` | Apres Phase 2 |
| Sector Orchestrator | Meta (route vers B) | Apres Phase 2 |

### Category C : Ingestion (2+2 workflows)
| Workflow | BDD | Activation |
|----------|-----|------------|
| Ingestion V3.1 | Pinecone `sota-rag-*`, Neo4j, Supabase | Actif maintenant |
| Enrichissement V3.1 | Neo4j, Pinecone | Actif maintenant |
| Sector Ingestion | Pinecone `website-sectors-*`, Neo4j `WEB_*` | Apres Phase 2 |
| Sector Enrichissement | Neo4j `WEB_*` | Apres Phase 2 |

### Support (4 workflows)
| Workflow | Role |
|----------|------|
| Benchmark V3.0 | Tests automatises |
| Dataset Ingestion Pipeline | HuggingFace → Pinecone |
| SQL Executor | Sub-workflow quantitative |
| Dashboard Status API | Webhook metriques live |

**Total : 4 (A) + 4 (B) + 4 (C) + 4 (Support) = 16 workflows**

## Workflows Website (Codespace rag-website — n8n/website/)

> Ces workflows sont des COPIES des workflows Phase 1 validés, adaptés pour les secteurs.
> Voir `n8n/website/README.md` pour l'architecture complète.

### RAG Pipelines website (fichiers JSON)
| Workflow | Source | Secteur | Pinecone namespace |
|---------|--------|---------|-------------------|
| website-standard-btp | standard.json (85.5%) | BTP/Construction | `btp` |
| website-standard-industrie | standard.json (85.5%) | Industrie | `industrie` |
| website-quantitative-finance | quantitative.json (fixé) | Finance | `finance` |
| website-graph-juridique | graph.json (fixé) | Juridique | `juridique` |
| website-orchestrator | orchestrator.json (80%) | Routeur | `website-sectors-jina-1024` |

### Fixes appliqués (Phase 1 → website)
| Fix | Pipeline | Problème | Solution |
|-----|---------|---------|---------|
| tenant_id dual | Graph | Neo4j a `default` ET `benchmark` | `n.tenant_id IN ['default','benchmark'] OR IS NULL` |
| Schema tables | Quantitative | `sales_data`, `kpis` inexistants en Supabase | Tables corrigées : `orders`, `customers`, `quarterly_revenue` |
| SQL Validator JOIN | Quantitative | Injection tenant_id casse les JOINs | Injection désactivée (LLM gère via prompt) |

### Ingestion website (nouveaux workflows — NOT rag-data-ingestion)
| Workflow | Datasets HF | Namespace |
|---------|------------|---------|
| website-ingestion-finance | financebench, ConvFinQA, tatqa | `finance` |
| website-ingestion-juridique | french_case_law, cold-french-law, legalbench | `juridique` |
| website-ingestion-btp | code-accord, ragbench | `btp` |
| website-ingestion-industrie | manufacturing-qa-gpt4o, ragbench | `industrie` |

---

### Trace Cloud (OBSOLETE — reference uniquement)

| Pipeline | Cloud ID | Execution reussie |
|---|---|---|
| Standard | `IgQeo5svGlIAPkBc` | #19404 |
| Graph | `95x2BBAbJlLWZtWEJn6rb` | #19305 |
| Quantitative | `E19NZG9WfM7FNsxr` | #19326 |
| Orchestrator | `ALd4gOEqiKL5KR1p` | #19323 |

---

## Databases

| DB | Content | Phase 1 | Phase 2 |
|---|---|---|---|
| **Pinecone** (sota-rag-jina-1024) | Vector embeddings (Jina) | 10,411 vectors, 12 namespaces | Standard RAG search (primary) |
| **Pinecone** (sota-rag-cohere-1024) | Vector embeddings (Cohere) | 10,411 vectors, 12 namespaces | Backup index |
| **Pinecone** (sota-rag-phase2-graph) | Graph passage embeddings | N/A | 1,296 musique passages (e5-large, 1024-dim) |
| **Neo4j** | Entity graph | 19,788 nodes, 76,717 relationships | +4,884 entities, +21,810 rels from Phase 2 |
| **Supabase** | Financial tables + benchmark_datasets | 38 tables, 10,772+ rows | +1,000 Phase 2 questions in benchmark_datasets |

---

## LLM Model Registry

Modeles gratuits via OpenRouter.

### Docker Env Vars (models configured in n8n)

| Variable | Model | Usage |
|---|---|---|
| `LLM_SQL_MODEL` | meta-llama/llama-3.3-70b-instruct:free | SQL generation |
| `LLM_FAST_MODEL` | google/gemma-3-27b-it:free | Fast operations |
| `LLM_INTENT_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Intent classification |
| `LLM_PLANNER_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Task planning |
| `LLM_AGENT_MODEL` | meta-llama/llama-3.3-70b-instruct:free | Agent reasoning |
| `LLM_HYDE_MODEL` | meta-llama/llama-3.3-70b-instruct:free | HyDE generation |
| `LLM_EXTRACTION_MODEL` | arcee-ai/trinity-large-preview:free | Entity extraction |
| `LLM_COMMUNITY_MODEL` | arcee-ai/trinity-large-preview:free | Community summaries |
| `LLM_LITE_MODEL` | google/gemma-3-27b-it:free | Lightweight tasks |

### Embeddings & Reranking

| Provider | Model | Dimensions |
|---|---|---|
| **Jina AI** (primary) | jina-embeddings-v3 | 1024 |
| **Jina AI** (reranker) | jina-reranker-v2-base-multilingual | N/A |
| **Cohere** (backup) | embed-english-v3.0 | 1024 |

---

## Capability Matrix (from Claude Code)

| Capability | Access | How |
|---|---|---|
| **n8n Webhooks** | DIRECT | HTTPS to `34.136.180.66:5678/webhook/*` |
| **n8n REST API** | DIRECT | HTTPS to `34.136.180.66:5678/api/v1/*` |
| **n8n MCP** | DIRECT | streamableHttp to `34.136.180.66:5678/mcp-server/http` |
| **GitHub** | DIRECT | `git push` + `gh` CLI |
| **Pinecone** | DIRECT | HTTPS REST API |
| **Neo4j** | VIA n8n | Docker bolt://localhost:7687 |
| **Supabase** | VIA n8n | Docker direct access |
| **OpenRouter** | VIA n8n | Proxied through n8n workflows |

---

## Data Flow

```
eval/quick-test.py (1-5q)   -+
eval/iterative-eval.py       -+-- 4 pipelines (n8n webhooks)
eval/run-eval-parallel.py    -+
          |
          +-- Standard Pipeline  --> Pinecone
          +-- Graph RAG Pipeline --> Neo4j + Supabase
          +-- Quantitative       --> Supabase SQL
          +-- Orchestrator       --> Routes to above
                    |
          eval/node-analyzer.py  (diagnostics)
          scripts/analyze_n8n_executions.py (raw data)
                    |
          +--------+--------------------+
          v        v                    v
    docs/data.json  logs/diagnostics/  n8n/analysis/
          v
    eval/generate_status.py
          v
    docs/status.json
          v
    docs/index.html (dashboard)
```

---

## Repository Structure

```
mon-ipad/
+-- CLAUDE.md                    # Session bootstrap
+-- directives/                  # Mission control
+-- technicals/                  # Reference docs (architecture, stack, credentials, phases, knowledge-base)
+-- eval/                        # Evaluation scripts
+-- scripts/                     # Utility scripts
+-- n8n/                         # Workflows (live, validated, sync)
+-- mcp/                         # MCP servers & docs
+-- website/                     # Next.js frontend
+-- site/                        # Website reference (copies)
+-- datasets/                    # Test questions
+-- db/                          # Database management
+-- docs/                        # Dashboard + status
+-- logs/                        # Execution logs
+-- snapshot/                    # Historical backups
+-- outputs/                     # Dated session archives
+-- utilisation/                 # Usage guides
```

---

## Phase Gates (Targets)

### Phase 1 — Baseline (200q) — BLOQUEE (Graph 68.7% < 70%, Quant 78.3% < 85%)
| Pipeline | Target |
|---|---|
| Standard | >=85% |
| Graph | >=70% |
| Quantitative | >=85% |
| Orchestrator | >=70% (P95 latency <15s, error rate <5%) |
| **Overall** | **>=75%** (3 consecutive stable iterations) |

### Phase 2-5
See `technicals/phases-overview.md` for full gate definitions.

---

## Root Cause Analysis (from previous iterations)

### Orchestrator
- Cascading timeouts: broadcasts to ALL 3 sub-pipelines
- Response Builder crash on empty `task_results`
- Query Router bug: leading space in `" direct_llm"` causes misrouting

### Graph RAG
- Entity extraction failures: HyDE extracts wrong names
- Missing entities: historical figures not matched

### Quantitative RAG
- SQL edge cases: multi-table JOINs, period filtering

### Standard RAG
- "No item to return" from Pinecone
- Verbose answers lower F1
