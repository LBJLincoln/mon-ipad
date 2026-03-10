# Etat Systeme Complet — Post Session 94 (updated)

> Date: 2026-03-10T04:00Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Lieu | Status | Notes |
|-----------|------|--------|-------|
| **VM Google Cloud** | 34.136.180.66 | UP | 969MB RAM, 18/30GB disk |
| **HF S1** (engine) | n8n primary | UP 200 | Standard + Graph + Enrichment V4.0 + Auto-Healer |
| **HF S3** (engine-3) | n8n secondary | UP 200 | Load balancing |
| **HF S5** (engine-5) | n8n eval | 503 SLEEP | A reveiller |
| **HF S7** (engine-7) | LiteLLM proxy | **BROKEN** | DB corruption: `LiteLLM_VerificationToken` missing |
| **HF S9** (engine-9) | n8n overflow | UP 200 | Disponible |
| **HF S6** (Docling) | Document processor | UP 200 | nomos-docling-api, cpu-basic |
| **HF Embeddings** | Jina v3 self-hosted | UP 200 | ~3.4 emb/s, batch<=50. API keys EXHAUSTED |
| **HF Reranker** | FlashRank | UP 200 | |

### LLM Access
| Provider | Status | Notes |
|----------|--------|-------|
| **Groq direct** | WORKING | `llama-3.3-70b-versatile`, 100K tokens/day free |
| **LiteLLM S7** | BROKEN | DB corruption, needs rebuild |
| **Jina API** | EXHAUSTED | Both keys $0 balance. Self-hosted only |

## 2. BASES DE DONNEES

### Compte 1 — CORRECTED (hosts verified via Pinecone API)

| BDD | Utilise | Libre | Contenu | Host subdomain |
|-----|---------|-------|---------|----------------|
| **Pinecone** `website-sectors-jina-1024` | ~43K | 57K | Secteurs Jina v3 | `a4mkzmz` |
| **Pinecone** `sectors-e5-multilingual` | **9,158** | 91K | E5 multilingual, integrated embedding | `a4mkzmz` |
| **Pinecone** `sota-rag-jina-1024` | 0 | 100K | Vide (purge S93) | `a4mkzmz` |
| **Neo4j** #1 (38c949a2) | 22K nodes | 178K libres | SectorDoc + Entity |
| **Supabase** #1 (ayqviqmx) | 85MB | 415MB | sector_documents (43K) |

### Compte 2

| BDD | Utilise | Libre | Usage prevu |
|-----|---------|-------|-------------|
| **Pinecone** #2 | 0 | 500K | Expansion secteurs |
| **Neo4j** #2 (48d838a5) | 0 | 200K/400K | Nouveaux secteurs |
| **Supabase** #2 (xivvnrkb) | 0 | 500MB | Nouvelles donnees |

## 3. PIPELINES RAG

| Pipeline | Status | Score | Hosts | Notes |
|----------|--------|-------|-------|-------|
| **Standard (n8n)** | **WORKING** | **5/5 (100%)** | S1, S3 | E5 search + Groq direct, multi-index RRF |
| **RAG Proxy** | **WORKING** | **5/5 (100%)** | VM local | `ops/rag-proxy.py` — E5 + Groq, 5 key rotation |
| Graph (n8n) | DATA GAP | 0/5 | S1 | Neo4j has only 1,325 entities (0 BTP/Industrie) |
| Quant (n8n) | DATA GAP | 0/3 | S9 | Supabase tables empty/mismatched |
| Orchestrator | **MISSING** | N/A | — | Workflow 404 on all Spaces |
| Enrichment | DEPLOYED | — | S1 | V4.0, 5 bugs fixed |
| Auto-Healer | ACTIVE | — | S1 | Cron 30min, ID `Yqw7Pzn0e7m0C6i3` |

### RAG Proxy (backup — bypasses n8n)
- **Script**: `ops/rag-proxy.py` — E5 search + Groq LLM, 5 key rotation, 5 model fallback
- **Usage**: `source .env.local && python3 ops/rag-proxy.py "question" [sector]`
- **Eval**: `python3 eval/quick-test.py --proxy --pipelines standard --questions 5`

## 4. DONNEES SECTORIELLES

### E5 Index — FULLY INGESTED
- **Index**: sectors-e5-multilingual
- **Vectors**: **12,502** (19 JSONL files, all 4 sectors)
- **Scripts**: `ops/clean-ingest.py` (purge+reingest), `ops/ingest-integrated.py` (all files)

### Datasets disponibles (rag-data-ingestion)
| Secteur | Fichiers | Records | Status |
|---------|----------|---------|--------|
| Finance | 6 JSONL | 2,250 | INGESTION EN COURS |
| BTP | 5 JSONL | 6,771 | INGESTION EN COURS |
| Juridique | 5 JSONL | 2,500 | EN ATTENTE |
| Industrie | 3 JSONL | 1,015 | INGERE (done) |

### Tavily Research (NOUVEAU)
- **93 test cases** generes depuis donnees reelles PME/ETI
- **158 documents reels** identifies (21 sources officielles gov.fr)
- **Sujets cles**: Facturation electronique 2026, RE2020, RGPD, DUERP/ICPE
- Fichiers: `sectors/eval-datasets/tavily-real-world-tests.json`, `sectors/real-documents-to-ingest.json`

## 5. OUTILS (S94)

| Outil | Fichier | Role |
|-------|---------|------|
| **RAG Proxy** | `ops/rag-proxy.py` | **PRIMARY** — E5 search + Groq LLM |
| **Clean Ingest** | `ops/clean-ingest.py` | Purge + reingest, 8 threads, smart text extraction |
| Tavily Sector Research | `ops/tavily-sector-research.py` | Recherche temps reel PME/ETI |
| Deploy Workflows | `ops/deploy-workflows.py` | Deploy n8n via cookie auth |
| Ingest Integrated | `ops/ingest-integrated.py` | Pinecone with built-in embedding |
| Ingest Pinecone | `ops/ingest-to-pinecone.py` | Pinecone with external Jina |
| Docling Space | `hf-spaces/docling/` | PDF processing HF Space |

## 6. EVAL

### Quick-test results (S94 final)
| Pipeline | n8n | Proxy | Notes |
|----------|-----|-------|-------|
| Standard | **5/5 (100%)** | **5/5 (100%)** | Both working perfectly |
| Graph | 0/5 | 4/5 | n8n=Neo4j empty, proxy=E5 fallback |
| Orchestrator | 404 | 3/3 | n8n workflow missing |
| **Combined** | **5/5** | **12/13 (92%)** | |

- **220 questions FR** reecrites (grounded in real sector data)
- **93 test cases Tavily** (real PME/ETI use cases)
- **Groq models**: 5 models in fallback chain (70b→maverick→scout→qwen→8b)

## 7. TLDR — Prochaines etapes

### IMMEDIAT (S95)
1. **Populate Neo4j** — run enrichment pipeline to extract entities from 12.5K E5 docs → fix Graph 0/5
2. **Deploy Orchestrator workflow** — currently 404 on all Spaces
3. **Run full 220-question eval** via proxy (Groq rate limits permitting)
4. **Fix Quant pipeline** — Supabase financial tables need re-population
5. **Ingest Jina index** — currently only 2.4K vectors, needs parity with E5 (12.5K)

### COURT TERME (S96-S97)
6. Tester Docling sur vrais PDF sectoriels (upload direct)
7. Ingerer les 158 documents Tavily via Docling
8. Graph pipeline multi-index upgrade
9. Connecter comptes BDD #2 aux pipelines
10. Atteindre 80% accuracy sur 4 secteurs

### LONG TERME (S98+)
11. 250K vecteurs par secteur
12. Self-healing complet autonome
13. Monetisation : chatbot expert + Stripe
