# Etat Systeme Complet — Post Session 94

> Date: 2026-03-10 | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Lieu | Status | Notes |
|-----------|------|--------|-------|
| **VM Google Cloud** | 34.136.180.66 | UP | 969MB RAM, 18/30GB disk |
| **HF S1** (engine) | n8n primary | UP 200 | Standard V3.5 + Graph + Enrichment V4.0 |
| **HF S3** (engine-3) | n8n secondary | UP 200 | Load balancing |
| **HF S5** (engine-5) | n8n eval | 503 SLEEP | A reveiller |
| **HF S7** (engine-7) | LiteLLM proxy | UP 200 | 9 models, key rotation |
| **HF S9** (engine-9) | n8n overflow | UP 200 | Disponible |
| **HF S6** (Docling) | **NOUVEAU** Document processor | UP 200 | nomos-docling-api, cpu-basic |
| **HF Embeddings** | Jina v3 self-hosted | UP 200 | ~3.4 emb/s, batch<=50 |
| **HF Reranker** | FlashRank | UP 200 | |

## 2. BASES DE DONNEES

### Compte 1

| BDD | Utilise | Libre | Contenu |
|-----|---------|-------|---------|
| **Pinecone** `website-sectors-jina-1024` | 45,916 | 54K | Secteurs Jina v3 |
| **Pinecone** `sectors-e5-multilingual` | ~17K (ingestion EN COURS) | 83K | **NOUVEAU** E5 multilingual, integrated embedding |
| **Pinecone** `sota-rag-jina-1024` | 0 | 100K | Vide (purge S93) |
| **Neo4j** #1 (38c949a2) | 22K nodes | 178K libres | SectorDoc + Entity |
| **Supabase** #1 (ayqviqmx) | 85MB | 415MB | sector_documents (43K) |

### Compte 2

| BDD | Utilise | Libre | Usage prevu |
|-----|---------|-------|-------------|
| **Pinecone** #2 | 0 | 500K | Expansion secteurs |
| **Neo4j** #2 (48d838a5) | 0 | 200K/400K | Nouveaux secteurs |
| **Supabase** #2 (xivvnrkb) | 0 | 500MB | Nouvelles donnees |

## 3. PIPELINES RAG

| Pipeline | Status | Version | Changements S94 |
|----------|--------|---------|-----------------|
| Standard | **UPGRADED** | V3.5.0 | **Multi-index: 5 sources RRF** (Jina HyDE + Jina Original + BM25 + E5 Original + E5 HyDE) |
| Graph | WORKING | V3.3 | Inchange |
| Quant | WORKING | V3.1 | Inchange |
| Orchestrator | WORKING | V10.1 | Inchange |
| Enrichment | **DEPLOYED** | V4.0 | 5 bugs fixes, synce vers n8n |
| Auto-Healer | **NOUVEAU** | V1.0 | Deploye, cron 30min, ID Yqw7Pzn0e7m0C6i3 |

## 4. DONNEES SECTORIELLES

### Ingestion en cours (PID 203705)
- **Index cible**: sectors-e5-multilingual (integrated embedding)
- **Progression**: ~17K/26K vectors
- **Script**: `ops/ingest-integrated.py`
- **Log**: `/tmp/ingest-all-sectors.log`

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

## 5. OUTILS NOUVEAUX (S94)

| Outil | Fichier | Role |
|-------|---------|------|
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

### COURT TERME (S95)
1. Finir ingestion sectors-e5-multilingual (reste ~9K records)
2. Tester Docling sur vrais PDF sectoriels (upload direct, pas URL)
3. Implementer auto-healer V2 (analytics completes, 4 pipelines)
4. Upgrader Graph pipeline avec multi-index aussi
5. Connecter comptes BDD #2 aux pipelines
6. Ingerer les 158 documents Tavily via Docling

### MOYEN TERME (S96-S98)
7. Multi-index sur les 4 pipelines
8. Pipeline Standard queries E5 index en mode natif texte (pas besoin de Jina)
9. Auto-healer persistent (Supabase history, trends)
10. Atteindre 80% accuracy sur 4 secteurs
11. Tavily cron pour mise a jour continue des tests

### LONG TERME (S99+)
12. 250K vecteurs par secteur
13. Self-healing complet autonome
14. Monetisation : chatbot expert + Stripe
