# Etat Systeme Complet — Post Session 93

> Date: 2026-03-09 | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Lieu | Status | RAM/Disk |
|-----------|------|--------|----------|
| **VM Google Cloud** | 34.136.180.66 | UP | 969MB RAM, 18/30GB disk |
| **HF S1** (engine) | n8n primary | UP 200 | 16GB (cpu-basic) |
| **HF S3** (engine-3) | n8n secondary | UP 200 | 16GB |
| **HF S5** (engine-5) | n8n eval | UP 200 | 16GB |
| **HF S7** (engine-7) | LiteLLM proxy | UP 200 | 16GB |
| **HF S9** (engine-9) | n8n overflow | UP 200 | 16GB |
| **HF Embeddings** | Jina self-hosted | UP 200 | cpu-basic |
| **HF Reranker** | FlashRank | UP 200 | cpu-basic |
| **HF S6** (Docling) | NON DEPLOYE | — | — |
| **HF S8** (Eval runner) | NON DEPLOYE | — | — |

## 2. BASES DE DONNEES

### Compte 1 (existant)

| BDD | Utilise | Libre | Max | Contenu |
|-----|---------|-------|-----|---------|
| **Pinecone** `website-sectors-jina-1024` | 43K vecteurs | 57K | 100K | Donnees sectorielles FR |
| **Pinecone** `sota-rag-jina-1024` | 0 | 100K | 100K | Vide (purge S93) |
| **Pinecone** slots | 2/5 | 3 libres | 5 | — |
| **Neo4j** #1 (38c949a2) | 22K nodes, 22K rels | 178K/378K | 200K/400K | SectorDoc + Entity |
| **Supabase** #1 (ayqviqmx) | 85MB | 415MB | 500MB | sector_documents (43K) |

### Compte 2 (NOUVEAU — S93)

| BDD | Utilise | Libre | Max | Usage prevu |
|-----|---------|-------|-----|-------------|
| **Pinecone** #2 | 0 | 500K | 5 indexes x 100K | Expansion secteurs |
| **Neo4j** #2 (48d838a5) | 0 | 200K/400K | 200K/400K | Nouveaux secteurs / overflow |
| **Supabase** #2 (xivvnrkb) | 0 | 500MB | 500MB | Nouvelles donnees sectorielles |

### Capacite totale combinee

| BDD | Total disponible |
|-----|-----------------|
| Pinecone | 8 index slots, ~757K vecteurs libres |
| Neo4j | ~378K nodes, ~778K relations libres |
| Supabase | ~915MB libres |

## 3. PIPELINES RAG

| Pipeline | Workflow ID | Status | LLM | Notes |
|----------|------------|--------|-----|-------|
| Standard | TmgyRP20N4JFd9CB | WORKING | LiteLLM llama-70b | Repond avec data US (pas FR) |
| Graph | 6257AfT1l4FMC6lY | WORKING | LiteLLM llama-70b | Self-hosted embed/rerank |
| Quant | cjhEhVs0KV1ExHqX | WORKING | LiteLLM | SQL financier |
| Orchestrator | ALd4gOEqiKL5KR1p | WORKING | OpenRouter | Route vers Std/Graph/Quant |
| Ingestion V4 | (n8n/live) | HTTP 200 | LiteLLM | Pas teste avec vrais docs |
| Enrichment V4 | ORa01sX4xI0iRCJ8 | FIXE (5 bugs) | LiteLLM | JSON corrige, PAS SYNCE |
| Auto-Healer | (n8n/live) | NOUVEAU | LiteLLM | PAS DEPLOYE |

## 4. DONNEES SECTORIELLES

| Secteur | Supabase docs | Pinecone vects | Neo4j nodes | Qualite | Gap |
|---------|--------------|----------------|-------------|---------|-----|
| Finance | 25,858 | ~15K est. | 15,220 | Datasets US/EN | Besoin FR |
| Juridique | 10,123 | ~10K est. | 2,500 | CAIL, cold-law, case-law | Besoin Legifrance |
| BTP | 4,443 | ~8K est. | 1,844 | BOAMP, techqa | **DATA GAP** — besoin DTU/NF |
| Industrie | 2,933 | ~5K est. | 1,015 | Manufacturing QA | Besoin normes ISO FR |

### Accuracy actuelle (220q eval)
- Finance: 20% | BTP: 31% | Juridique: 29% | Industrie: 26%
- **Root cause** : Eval = questions US, data = mix US/FR. Pas de vraies donnees sectorielles FR.

## 5. REPOS GITHUB

| Repo | Status | Derniere action S93 |
|------|--------|---------------------|
| **mon-ipad** | ACTIF, clean | Auto-healer + enrichment fix + purge script |
| **rag-data-ingestion** | ACTIF | Fix trust_remote_code, scripts ingestion |
| **rag-website** | ACTIF | Inchange S93 |
| **rag-dashboard** | ACTIF | Inchange S93 |
| **rag-storage** | ARCHIVE | Archives benchmark exportees (35MB) |

## 6. EN COURS (BACKGROUND)

- `download-massive-datasets.py` (PID 72279) — telecharge 10 HF datasets
  - Verifier: `tail -50 /tmp/download-massive.log`
  - Resultat: `ls -lh ~/rag-data-ingestion/datasets/sectors/*.jsonl`

## 7. PISTE D'AMELIORATION — LDR (Long/Moyen/Court terme)

### COURT TERME (S94 — prochaine session)
1. Sync enrichment fix vers n8n (`n8n/sync.py`)
2. Deploy auto-healer sur S5 ou S9
3. Verifier + ingerer datasets telecharges dans Pinecone
4. Reecrire eval dataset (questions FR sur vrais contenus)

### MOYEN TERME (S95-S97)
5. Deployer Docling sur HF Space S6 (traitement PDF complexes)
6. Crawler BOAMP (4,927+ marches BTP) + Legifrance XML
7. Utiliser comptes BDD #2 pour scale (Pinecone #2 pour nouveaux sectors)
8. Activer auto-healer en continu (cron 30min)
9. Atteindre 80% accuracy sur 4 secteurs

### LONG TERME (S98+)
10. 250K vecteurs par secteur (1M total)
11. Docling autonome en continu sur Codespace
12. Self-healing complet (analyze → patch → test → apply → commit)
13. Monetisation : connecter chatbot expert au Stripe/Whop
14. API publique RapidAPI avec auth
