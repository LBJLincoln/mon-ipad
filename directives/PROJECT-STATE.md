# Project State — Nomos Sector AI Expert

> Last updated: 2026-03-09T12:00:00Z

## Session 92 — RESTRUCTURATION

### Overview
- **PIVOT** : Benchmarks academiques → Expert IA Sectoriel
- **2 axes** : (1) Pipelines sectorielles parfaites (2) Monetisation
- **Pipelines** : 4/4 WORKING (Std 36s, Graph 39s, Quant 43s, Orch 30s)
- **Sectors** : Finance 80%, Juridique 80%, Industrie 80%, **BTP 20% (DATA GAP)**
- **Restructuration** : Benchmark files → rag-storage, new sectors/ + ops/ dirs
- **Self-healing** : Architecture L0-L4 prete, evals continus planifies

### Session 92 Actions
1. **RESTRUCTURATION COMPLETE** : Pivot tous les repos vers secteur expert
2. Benchmark eval scripts → `rag-storage/archive/benchmark-eval/`
3. DB populate scripts → `rag-storage/archive/benchmark-db-populate/`
4. Identity files → `rag-storage/archive/identity-files/`
5. Infra configs → `rag-storage/archive/infra-configs/`
6. Nouveau `sectors/` avec config par secteur
7. Nouveau `ops/` avec scripts operationnels
8. CLAUDE.md v9.0 reecrit pour secteur expert

---

## Sector Accuracy Matrix

| Secteur | Standard | Graph | Quant | Orch | Target Std | Data Gap |
|---------|----------|-------|-------|------|-----------|----------|
| **Finance** | **80%** | TBD | **95.2%** | TBD | 90% | Non |
| **BTP** | **20%** | TBD | TBD | TBD | 85% | **OUI — DTU/NF manquants** |
| **Juridique** | **80%** | TBD | N/A | TBD | 90% | Non |
| **Industrie** | **80%** | TBD | TBD | TBD | 85% | Non |

**Overall sector accuracy** : 65% (Standard only, 220 questions)
**Critical blocker** : BTP a 20% — besoin massif de donnees construction francaises

---

## Pipeline Status

| Pipeline | Status | Response Time | Workflow ID | Notes |
|----------|--------|--------------|-------------|-------|
| Standard | WORKING | ~36s | `TmgyRP20N4JFd9CB` | Groq direct, sector index OK |
| Graph | WORKING | ~39s | `6257AfT1l4FMC6lY` | Groq direct, sector entities |
| Quant | WORKING | ~43s | `cjhEhVs0KV1ExHqX` | LiteLLM, financial SQL |
| Orchestrator | WORKING | ~30s | `ALd4gOEqiKL5KR1p` | V11 Minimal, Groq routing |

All pipelines query `website-sectors-jina-1024` (sector data).
Legacy index `sota-rag-jina-1024` frozen at 46,634 vectors (do not write).

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
2. ~~Reranker deployed~~ DONE — `nomos-reranker-api` HF Space, FlashRank, /v1/rerank WORKING
3. ~~LLM-as-judge framework~~ DONE — `eval/llm-judge-rescore.py` via LiteLLM/Gemma-27B
4. ~~Matching fix~~ DONE — bidirectional stem + 25+ FR synonyms (FIX-93)
5. ~~Raw results saving~~ DONE — `logs/continuous-eval/raw-*.json` for post-processing
6. ~~DEBUG-PLAYBOOK updated~~ DONE — FIX-91, FIX-92, FIX-93

### IMMEDIATE (remaining)
7. Run full 220q Standard eval + LLM judge rescore (IN PROGRESS)
8. Fix Graph pipeline timeout (webhook responds but >90s)
9. Fix Orchestrator (ALd4gOEqiKL5KR1p deactivated)
10. Renew Groq API keys (all 5 expired/403)
11. Commit + push all changes

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
