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

| Pipeline | Status | Version | Notes S94 |
|----------|--------|---------|-----------|
| Standard (n8n) | **PATCHED** but data flow broken | V3.5.0 | Groq direct + E5 search patched, but n8n execution returns 0 sources |
| **RAG Proxy** | **WORKING** | V1.0 | `ops/rag-proxy.py` — E5 search + Groq LLM, bypasses n8n |
| Graph | WORKING | V3.3 | Inchange |
| Quant | WORKING | V3.1 | Inchange, uses LiteLLM (BROKEN) |
| Orchestrator | WORKING | V10.1 | Inchange |
| Enrichment | **DEPLOYED** | V4.0 | 5 bugs fixes, synced via cookie auth |
| Auto-Healer | **ACTIVE** | V1.0 | Cron 30min, ID `Yqw7Pzn0e7m0C6i3` |

### RAG Proxy (RECOMMENDED — bypasses n8n)
- **Script**: `ops/rag-proxy.py`
- **How it works**: E5 integrated search → Groq LLM → response with sources
- **Tested**: Finance (3M CapEx → $1,577M correct), BTP (BOAMP marches publics, score 0.86)
- **Usage**: `source .env.local && python3 ops/rag-proxy.py "question" [sector]`

## 4. DONNEES SECTORIELLES

### E5 Index — CLEAN INGESTION COMPLETE
- **Index**: sectors-e5-multilingual
- **Vectors**: 9,158 (purged junk, reingested clean data only)
- **Script used**: `ops/clean-ingest.py`
- **Whitelisted files**: 8 clean JSONL files from 4 sectors

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

- **220 questions FR** reecrites (grounded in real sector data)
- **93 test cases Tavily** (real PME/ETI use cases)
- Multi-index pipeline teste: finance query retourne sources des DEUX indexes

## 7. TLDR — Prochaines etapes

### IMMEDIAT (S95)
1. **Fix LiteLLM S7** — rebuild Space or fix DB (Graph+Quant depend on it)
2. **Run full eval** via rag-proxy on 220 questions (wait Groq rate limit reset)
3. **Update quick-test.py** to use rag-proxy instead of broken n8n webhooks
4. **Ingest MORE data** — Jina index has ~43K but E5 only 9K, need parity
5. **Fix n8n Standard pipeline** or replace with rag-proxy as webhook

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
