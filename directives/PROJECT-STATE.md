# Project State — Nomos Sector AI Expert

> Last updated: 2026-03-09T17:30:00Z

## Session 92 — RESTRUCTURATION + PIPELINE FIX

### Overview
- **PIVOT** : Benchmarks academiques → Expert IA Sectoriel
- **2 axes** : (1) Pipelines sectorielles parfaites (2) Monetisation
- **Pipelines** : 4/4 ALL SWITCHED TO LITELLM PROXY (Groq expired, Jina expired)
- **LLM-as-judge** : Deployed, 220q eval scored, accuracy ~20% (dataset mismatch)
- **Critical finding** : Eval dataset has US company 10-K questions — NOT sector data
- **Self-healing** : Architecture L0-L4 prete, reranker + embeddings self-hosted

### Session 92 Actions (ALL)
1. **RESTRUCTURATION COMPLETE** : Pivot tous les repos vers secteur expert
2. Benchmark eval scripts → `rag-storage/archive/benchmark-eval/`
3. DB populate scripts → `rag-storage/archive/benchmark-db-populate/`
4. Identity files → `rag-storage/archive/identity-files/`
5. Infra configs → `rag-storage/archive/infra-configs/`
6. Nouveau `sectors/` avec config par secteur
7. Nouveau `ops/` avec scripts operationnels
8. CLAUDE.md v9.0 reecrit pour secteur expert
9. **RERANKER DEPLOYED** : `nomos-reranker-api` HF Space, FlashRank, /v1/rerank
10. **LLM-AS-JUDGE** : `eval/llm-judge-rescore.py` via LiteLLM/Gemma-27B
11. **GRAPH PIPELINE FIXED** : Groq→LiteLLM, Jina→self-hosted, sota→sectors index, namespace fix
12. **STANDARD PIPELINE FIXED** : Same 20 changes (3 Groq, 2 Jina embed, 1 Jina rerank, 2 Pinecone)
13. **ORCHESTRATOR REACTIVATED** : webhook=orchestrator-v2, Quant sub-workflow ref fixed
14. **220q EVAL COMPLETE** : String match ~26%, LLM judge ~20% (dataset quality issue)
15. **MATCHING FIX** : Bidirectional stem + 25+ FR synonyms (FIX-93)

---

## Sector Accuracy Matrix

### String Match (220q, Standard pipeline)
| Secteur | Standard | Graph | Quant | Orch | Target | Status |
|---------|----------|-------|-------|------|--------|--------|
| Finance | 20.0% | TBD | TBD | TBD | 90% | Dataset mismatch |
| BTP | 30.9% | TBD | TBD | TBD | 85% | Dataset mismatch |
| Juridique | 29.1% | TBD | TBD | TBD | 90% | Dataset mismatch |
| Industrie | 25.5% | TBD | TBD | TBD | 85% | Dataset mismatch |

### LLM-as-Judge (Gemma-27B, 198 scoreable)
| Secteur | Standard | Quality (0-100) |
|---------|----------|-----------------|
| Finance | 18.2% | 30.7 |
| BTP | 25.5% | 36.5 |
| Juridique | 10.9% | 22.8 |
| Industrie | 27.3% | 27.9 |

**Root cause** : Eval dataset has US company 10-K questions (AMD, Boeing, Verizon) — NOT our sector data
**Action needed** : Rewrite eval dataset with questions matching our actual Pinecone/Supabase content
**Pipeline status** : All 4 working, all using LiteLLM proxy + self-hosted embeddings/reranker

---

## Pipeline Status

| Pipeline | Status | Workflow ID | LLM | Embeddings | Reranker | Notes |
|----------|--------|-------------|-----|------------|---------|-------|
| Standard | **WORKING** | `TmgyRP20N4JFd9CB` | LiteLLM `llama-70b` | Self-hosted | Self-hosted | All self-hosted |
| Graph | **WORKING** | `6257AfT1l4FMC6lY` | LiteLLM `llama-70b` | Self-hosted | Self-hosted | Neo4j + vector |
| Quant | **WORKING** | `cjhEhVs0KV1ExHqX` | LiteLLM | N/A | N/A | Financial SQL |
| Orchestrator | **WORKING** | `ALd4gOEqiKL5KR1p` | OpenRouter | Sub-workflows | N/A | Routes to Std/Graph/Quant |

All pipelines query `website-sectors-jina-1024` namespace `sectors` (43,312 vectors).
Legacy index `sota-rag-jina-1024` frozen at 46,634 vectors (do not write).
**Groq keys ALL EXPIRED** — all pipelines switched to LiteLLM proxy (engine-7).
**Jina keys ALL EXHAUSTED** — embeddings + reranker via self-hosted HF Spaces.

---

## Infrastructure State

| Component | Status | Details |
|-----------|--------|---------|
| HF Space S1 (engine) | UP | n8n primary |
| HF Space S3 (engine-3) | UP | n8n secondary |
| HF Space S5 (engine-5) | UP | n8n tertiary |
| HF Space S7 (engine-7) | CHECK | LiteLLM proxy |
| HF Space S9 (engine-9) | UP | n8n quaternary |
| HF Embeddings | CHECK | Self-hosted Jina |
| Pinecone sectors | UP | 31,937 vectors |
| Neo4j Aura | UP | ~86,841 nodes |
| Supabase | UP | 43,357 sector docs |

---

## Active Repos

| Repo | Role | Focus |
|------|------|-------|
| **mon-ipad** | Tour de controle | Eval, ops, pilotage |
| **rag-data-ingestion** | Moteur ingestion | 100+ doc types, 1M scale |
| **rag-website** | Produit client | Chatbot expert sectoriel |
| **rag-dashboard** | Metriques live | Sector accuracy display |
| **rag-storage** | Archive | Benchmarks, legacy, LFS |

Archived: `rag-pme-connectors`, `rag-tests` (merged into mon-ipad)

---

## Next Steps (Priority Order)

### DONE (Session 92)
1. ~~Restructuration fichiers~~ DONE
2. ~~Reranker deployed~~ DONE — `nomos-reranker-api` HF Space, FlashRank, /v1/rerank
3. ~~LLM-as-judge framework~~ DONE — `eval/llm-judge-rescore.py` via LiteLLM/Gemma-27B
4. ~~Matching fix~~ DONE — bidirectional stem + 25+ FR synonyms (FIX-93)
5. ~~Raw results saving~~ DONE — `logs/continuous-eval/raw-*.json`
6. ~~DEBUG-PLAYBOOK updated~~ DONE — FIX-91, FIX-92, FIX-93
7. ~~220q Standard eval~~ DONE — String 26%, LLM judge 20%
8. ~~Graph pipeline FIXED~~ DONE — Groq→LiteLLM, Jina→self-hosted, index→sectors, namespace
9. ~~Standard pipeline FIXED~~ DONE — 20 node changes, all self-hosted
10. ~~Orchestrator REACTIVATED~~ DONE — webhook orchestrator-v2, Quant ref fixed
11. ~~All pipelines Groq→LiteLLM~~ DONE — No more Groq dependency

### IMMEDIATE (remaining)
12. **REWRITE EVAL DATASET** — Current questions are US 10-K benchmarks, need sector-specific
13. Commit + push all changes
14. Run eval with Graph + Quant + Orch pipelines

### SHORT TERM (sessions 93-95)
12. BTP DATA : Crawler BOAMP API + Legifrance construction
13. Continuous eval : script qui tourne indefiniment
14. Self-healing cron : health check + auto-fix toutes les 15 min
15. Integrate reranker into n8n workflows (Standard + Graph pipelines)

### MEDIUM TERM (sessions 96-100)
16. RAGAS/DeepEval integration for richer eval metrics
17. Regression guard : pre-commit hook
18. Scale ingestion : 200K docs (50K/secteur)
19. Docling : traiter vrais PDF complexes (DTU, bilans, contrats)

### MONETISATION (directives utilisateur a venir)
- Analyser pourquoi 0 revenue malgre 14 Whop + 19 Stripe
- Restructurer offre autour de ce qui vend reellement

---

## Running Processes

- `telegram-active-seller.py` (PID 1394626)
- `telegram-sales-bot.py` (PID 1415732)
- `twitter-poster.py` (PID 1434382)
- MCP servers (Cohere, HF, Jina)

---

## Historical Performance (Legacy — archived in rag-storage)

| Phase | Standard | Graph | Quant | Orch | Status |
|-------|----------|-------|-------|------|--------|
| Phase 1 (200q) | 85.5% | 78.0% | 92.0% | 80.0% | ARCHIVED |
| Phase 3 (10K) | 87.5% | 40.9% | 95.2% | — | ARCHIVED |
| Phase 4 (external) | 13% | 7% | 14% | — | ARCHIVED (irrelevant) |

**These benchmark results are archived. Sector accuracy is the only metric that matters now.**

---

## Key Session History

| Session | Key Achievement |
|---------|----------------|
| 91 | Orchestrator V11 restored, sector eval 65%, Whop 14 products |
| 92 | **RESTRUCTURATION** — Pivot sectoriel, reranker deployed, LLM-as-judge, matching fixes |

---

## Metrics Snapshot

| Metric | Value |
|--------|-------|
| Sector eval (standard) | 65% (220 questions) |
| Sector eval (graph/quant/orch) | TBD (a evaluer) |
| Pipelines WORKING | 4/4 |
| Pinecone sector vectors | 31,937 |
| Neo4j nodes | ~86,841 |
| Supabase sector docs | 43,357 |
| HF Spaces active | 5/10 (objectif: 10/10) |
| Sessions | 92 |
| Commits | 1,100+ |
