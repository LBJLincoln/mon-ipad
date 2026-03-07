# rag-data-ingestion — CLAUDE.md

> Last updated: 2026-03-07T18:30:00Z
> **Ce repo s'exécute dans un Codespace GitHub éphémère.**
> Tu es un agent Claude Code specialise dans l'INGESTION et l'ENRICHISSEMENT des BDD.
> **MODELE PRINCIPAL : `claude-opus-4-6`** — Strategie ingestion, analyse qualite, decisions.
> **DELEGATION** : Sonnet 4.5 pour batch downloads/transformations via `Task(model: "sonnet")`.
> **DELEGATION** : Haiku 4.5 pour verification/exploration rapide via `Task(model: "haiku")`.
> Tu suis le même workflow-process que mon-ipad, adapté à l'amélioration des pipelines d'ingestion.
> Processus team-agentic multi-model : voir `technicals/project/team-agentic-process.md` (dans mon-ipad).
> **Bottleneck-first** : Ingestions fonctionnelles en background. Se concentrer sur les erreurs et les pipelines bloqués.
> **Push régulier** : Commit + push toutes les 15-20 min. Résultats JAMAIS perdus (Codespace éphémère).

---

## ÉTAT ACTUEL — 7 mars 2026 (Session 79)

| | |
|-|-|
| **Dernier commit** | Session 79 — 7 mars 2026 |
| **Déployé / en cours** | Workflows Ingestion V4.0 (patched) + Enrichissement V4.0 (BROKEN) |
| **Codespace** | `ingestion-prod-4j4j67rq5xjrfjp75` (Available) |
| **Datasets downloaded** | 16/16 HF benchmarks + 18/18 sector datasets (34,095 items) |
| **Pinecone sectors** | `website-sectors-jina-1024` — **31,916 vectors**, 1024-dim, cosine |
| **Pinecone benchmark** | `sota-rag-jina-1024` — **~47K vectors** (21K existing + 26K Phase 4 contexts ingesting) |
| **Supabase** | **11,387 sector_documents** (7,511 sectors + 3,876 Phase 4 quant) |
| **Supabase financial** | **3,876 sector_financial_tables** (3,288 with parsed table data) |
| **Neo4j** | **~82K nodes** (70,847 existing + ~11K Phase 4 graph paragraphs + entities) |
| **Ingestion status** | **SECTORS COMPLETE** — Phase 4 benchmark ingestion IN PROGRESS |

### État des composants (Session 79)
| Composant | Réalité | Status |
|-----------|---------|--------|
| **ingestion.json** | 30 noeuds — LLM nodes patched to OpenRouter | **WORKING** |
| **enrichment.json** | Webhook HTTP 500 — placeholder issues | BROKEN |
| **Direct ingestion scripts** | `ingest-direct.py`, `ingest-downloaded-datasets.py`, `ingest-phase3-bulk.py` | **WORKING** |
| **Phase 4 ingestion** | `mon-ipad/scripts/ingest-phase4-contexts.py` — Jina v3 + Pinecone direct | **RUNNING** |
| **Embedding** | Jina v3 (new key `jina_c87d...`, Cloudflare bypass via User-Agent) | **WORKING** |
| **Document types** | 100+ types registered, tests pass | OK |
| **Tests** | **110 offline tests passing** | **WORKING** |
| **CI** | pytest on push + manual E2E | **WORKING** |

### Session 78-79 accomplishments
1. **Supabase sector ingestion COMPLETE**: 7,509 docs across 4 sectors (Finance 2,150 | Juridique 2,500 | BTP 1,844 | Industrie 1,015)
2. **Neo4j sector ingestion COMPLETE**: 7,509 docs + entity extraction
3. **Scripts created**: `ingest-all-sectors.py` (universal QA + corpus handler), `ingest-sectors-supabase.py`, `ingest-sectors-neo4j.py`
4. **Supabase port fix**: port 6543 → 5432 (transaction pooler doesn't persist inserts)
5. **Phase 4 quant data**: 3,876 financial tables inserted into `sector_financial_tables`
6. **Phase 4 contexts**: 26K benchmark contexts being ingested into Pinecone `sota-rag-jina-1024`
7. **Phase 4 graph data**: 11K paragraph nodes + entity extraction into Neo4j
8. **Jina key renewed**: `jina_c87d...` (Cloudflare blocks datacenter IPs — bypass with User-Agent header)

### SOTA V4.0 Improvements Applied (Session 31)
| Technique | Impact | Status |
|-----------|--------|--------|
| Late Chunking (Jina) | +3.5% accuracy | Applied in Ingestion V4.0 |
| Jina v3 Task LoRA | +5-8% accuracy | Applied in Ingestion V4.0 |
| Domain-Specific Chunking | +8-12% accuracy | Applied (4 sector strategies) |
| BM25 French Improvements | +10-15% precision | Applied in Ingestion V4.0 |
| French NER Extraction | +10-15% entities | Applied in Ingestion V4.0 |
| CompactRAG QA Pairs | -50% LLM calls | Applied in Ingestion V4.0 |
| Entity Resolution V4 | Better dedup | Applied in Enrichment V4.0 |
| Cross-Document Linking | Graph quality | Applied in Enrichment V4.0 |
| Relationship Types V4 | Legal/Finance | Applied in Enrichment V4.0 |
| Community Summaries FR | French support | Applied in Enrichment V4.0 |

### Processing Pipeline
| Script | Purpose |
|--------|---------|
| `scripts/sector-file-types.py` | 500 file type registry (125/sector) |
| `scripts/process-sectors.py` | Process documents → n8n batches (1M capacity) |
| `scripts/trigger-sector-ingestion.py` | Send batches to n8n webhooks |
| `scripts/upgrade-ingestion-v4.py` | Upgrade workflow JSON with SOTA |
| `scripts/upgrade-enrichment-v4.py` | Upgrade workflow JSON with SOTA |

### Commandes clés pour cette session
```bash
# Créer le Codespace (si non existant)
gh codespace create --repo LBJLincoln/rag-data-ingestion --machine basicLinux32gb

# Se connecter
gh codespace ssh --codespace <name>

# Dans le Codespace — démarrer n8n + workers
source .env.local
docker compose up -d  # n8n + 2 workers + postgres + redis

# Télécharger datasets prioritaires (Finance puis Juridique)
python3 scripts/download-sector-datasets.py --sector finance --max 10000
python3 scripts/download-sector-datasets.py --sector juridique --max 10000

# Lancer ingestion
python3 scripts/trigger-ingestion.py --dataset financebench --workers 2
```

### Datasets prioritaires à ingérer (dans l'ordre)
| Priorité | Secteur | Dataset | Raison |
|----------|---------|---------|--------|
| P1 | Finance | PatronusAI/financebench + TheFinAI/convfinqa | Quantitative 78.3% → 85% |
| P2 | Juridique | rcds/french_case_law + rcds/cold-french-law | Graph 68.7% → 70% |
| P3 | BTP | GT4SD/code-accord + autres | Futur secteur |
| P4 | Industrie | thesven/manufacturing-qa-gpt4o + RAGBench | Futur secteur |

---

## OBJECTIF DE CE REPO

**Améliorer drastiquement** les 2 workflows d'ingestion via recherche académique 2026,
puis ingérer les datasets sectoriels dans les BDD du projet.

### Les 2 workflows — UPGRADED to V4.0 (SOTA 2026)
| Workflow | ID n8n | Version | Key V4.0 Features |
|----------|--------|---------|-------------------|
| **Ingestion V4.0** | `nh1D4Up0wBZhuQbp` | V4.0 | Late Chunking, Domain-Specific Chunking, French NER, CompactRAG, BM25 FR — LLM→OpenRouter |
| **Enrichissement V4.0** | `ORa01sX4xI0iRCJ8` | V4.0 | Entity Resolution V4, Cross-Doc Linking, FR Summaries — **HTTP 500** |

### Cibles de performance
| Métrique | V3.1 | V4.0 Target | Technique |
|---------|------|-------------|-----------|
| Chunks utiles / document | ~60% | >= 85% | Domain-specific chunking |
| Embedding quality (retrieval@5) | baseline | +15% | Late Chunking + Jina v3 LoRA |
| Entity extraction accuracy | ~70% | >= 90% | French NER + Entity Resolution V4 |
| Graph completeness | partial | >= 90% | Cross-document linking |
| BM25 precision (legal/finance) | baseline | +15% | French stop words + sector weighting |
| Temps ingestion / doc | ~60s | < 30s | Batch processing + optimized prompts |

### 500 File Types × 4 Sectors (1M Document Capacity)
| Sector | Types | Pipeline | Chunking Strategy |
|--------|-------|----------|-------------------|
| BTP/Construction | 125 | standard + graph | btp_spec_based (1024 tokens) |
| Finance | 125 | quantitative + standard | finance_page_level (256 + metadata) |
| Juridique | 125 | graph + standard | legal_clause_based (500-800 tokens) |
| Industrie | 125 | standard + quantitative | industry_hierarchical (512 tokens) |

---

## POSITION DANS LE PLAN GLOBAL (phases A→D)

```
PHASE A — RAG Pipeline Iteration  ← RAG-TESTS exécute, mon-ipad pilote
  Phase 1 (200q)   BLOQUÉE — ce repo débloque via ingestion Finance + Juridique
  Phase 2 (1 000q) ← prérequis : ce repo doit ingérer les 14 benchmarks HuggingFace
  Phase 3 (~10K q) ← prérequis : extension des ingestions

PHASE B — Analyse SOTA 2026  ← MON-IPAD (pilotage + résultats en technicals/)
  → Informe les V4.0 des workflows d'ingestion/enrichissement de CE REPO

PHASE C — Ingestion & Enrichment BDD  ← CE REPO EST ICI
  ✅ Ingestion V3.1 opérationnelle (sur VM)
  ❌ Datasets Phase 2 non encore téléchargés (~4 GB HuggingFace)
  ❌ Datasets sectoriels website non ingérés (~1.4 GB)

PHASE D — Production & Déploiement  ← RAG-WEBSITE + RAG-DASHBOARD
```

### Ce que ce repo doit produire pour débloquer la phase suivante

| Pour débloquer | Ce que ce repo doit faire |
|---------------|--------------------------|
| **Phase 1 → Phase 2** (rag-tests) | Ingérer FinQA/TatQA/ConvFinQA (Quant) + French Case Law (Graph) → datasets disponibles dans Supabase/Neo4j |
| **Phase 2 complète** | Télécharger + ingérer les 14 benchmarks HuggingFace (~4 GB) |
| **Website démos** (rag-website) | Ingérer docs sectoriels BTP/Industrie/Finance/Juridique (~1.4 GB) dans Pinecone |

### Volume total à ingérer
| Type | Source | Taille | Priorité |
|------|--------|--------|----------|
| Benchmarks Phase 2 (14 datasets) | HuggingFace | ~4 GB | P1 — débloque tests |
| Docs sectoriels website (4 secteurs) | HuggingFace + docs FR | ~1.4 GB | P2 — débloque démos |
| **Total** | | **~5.4 GB** | |

---

## PHASE 0 : RECHERCHE ACADÉMIQUE (OBLIGATOIRE — FAIRE EN PREMIER)

**Avant tout développement**, effectuer une revue systématique des papiers de recherche 2026.
Les techniques utilisées par Anthropic, OpenAI et la communauté académique pour améliorer le RAG.

### Sources prioritaires (dans l'ordre)
```
1. ArXiv cs.IR + cs.CL (2025-2026) :
   - Rechercher : "RAG ingestion 2026", "chunking strategies SOTA"
   - Rechercher : "contextual retrieval", "late chunking", "semantic chunking"
   - Rechercher : "document enrichment RAG", "metadata augmentation"

2. Anthropic Research Blog (2024-2026) :
   - "Contextual Retrieval" (2024) — technique clé d'enrichissement
   - Prompt caching pour réduire les coûts d'ingestion

3. OpenAI Research + Cookbook :
   - File Search improvements (2025-2026)
   - Embedding fine-tuning techniques

4. Jina AI Research (2024-2026) :
   - "Late Chunking" paper — segmentation après embedding
   - ColPali, ColBERT pour embeddings multi-vecteurs

5. Conférences : SIGIR 2025, ECIR 2026, ACL 2026
```

### Topics de recherche spécifiques
```
CHUNKING :
- Semantic chunking vs fixed-size chunking
- Late chunking (Jina 2024) — avantage pour documents longs
- Hierarchical chunking pour documents structurés (DTU, Eurocodes)
- Sliding window avec overlap adaptatif

ENRICHISSEMENT :
- Contextual retrieval (Anthropic) : ajouter contexte document au chunk
- Hypothetical Document Embeddings (HyDE) — déjà dans nos pipelines, à améliorer
- Summary-enhanced retrieval
- Metadata extraction automatique (date, auteur, section, type doc)

EMBEDDINGS :
- Jina embeddings-v3 vs nouvelles versions 2026
- Multilingual embeddings pour documents FR/EN mixtes
- Domain-specific fine-tuning (finance, juridique)
- Matryoshka embeddings pour compression

GRAPH ENRICHISSEMENT (Neo4j) :
- Entity extraction améliorée (NER fine-tuned sectoriel)
- Relation extraction automatique
- Community detection pour clustering

SQL ENRICHISSEMENT (Supabase) :
- Extraction automatique tableaux depuis PDF
- Normalisation données financières
- Schema inference automatique
```

### Documentation des découvertes
```bash
# Documenter chaque technique découverte
cat >> research/papers-2026.md << EOF
## [Titre du paper]
- Source : ArXiv/Anthropic/OpenAI — [URL]
- Date : [date]
- Technique clé : [description]
- Applicabilité : Ingestion V4 / Enrichissement V4
- Impact estimé : [faible/moyen/fort]
- Priorité : [1/2/3]
EOF
```

---

## INFRASTRUCTURE DE CE CODESPACE

```
Type        : GitHub Codespace (éphémère)
CPU         : 2 cores | RAM : 8 GB | Disque : 32 GB
n8n local   : NON — utilise HF Space
              Tous les workflows pointent vers HF Space (lbjlincoln-nomos-rag-engine.hf.space)
```

### HF Space Architecture (Session 42+)
```
n8n HF Space  : https://lbjlincoln-nomos-rag-engine.hf.space
n8n mode      : Queue (3 workers: main + 2 workers)
Database      : Supabase PostgreSQL (not SQLite) — 40 tables, 17K+ rows
Queue         : Redis (external, cloud-hosted)
OpenRouter    : 7 API keys configured (5 pipelines + 1 main + 1 spare)
Webhooks      : Currently ALL 404 (rebuild wipeout) — needs entrypoint.sh fix
```

**Queue mode** : permet l'ingestion parallèle de multiples documents.
**VM n8n REMOVED** : VM no longer runs n8n (freed ~270MB RAM). All workflows now on HF Space only.

---

## ETAPE 0 — Consulter la Bibliotheque de Fixes (OBLIGATOIRE)

**AVANT tout debug, TOUJOURS consulter `technicals/debug/fixes-library.md` en premier.**

```bash
cat technicals/debug/fixes-library.md
```

35 bugs documentes ont deja ete resolus (sessions 7–27). Chercher le symptome dans le tableau PIEGES RECURRENTS avant toute analyse. **Si symptome connu → appliquer directement SANS re-analyser.** Particulierement pertinent : FIX-06 (credentials manquantes), FIX-09 (PUT 400), FIX-12 (Pinecone dim mismatch). Si le symptome est nouveau → debugger, puis signaler a mon-ipad pour documentation.

### Protocole Auto-Stop
3 echecs consecutifs sur le meme type d'erreur → STOP, documenter dans `logs/diagnostics/`, signaler a mon-ipad.

### Fixes Library Partagee
La bibliotheque de fixes master est dans `mon-ipad/technicals/debug/fixes-library.md`. Ce repo recoit une copie via `push-directives.sh`. Si tu decouvres un nouveau bug, documente-le dans `logs/diagnostics/` + commit + push.

### BDD Separees (Ingestion)
| BDD | Index/Schema mon-ipad (benchmark) | Index/Schema website (secteurs) |
|-----|-----------------------------------|--------------------------------|
| Pinecone | `sota-rag-jina-1024` | `website-sectors-jina-1024` (CREATED Session 72, dim 1024, ready) |
| Neo4j | labels generiques | labels `WEB_*` |
| Supabase | schema `public` | schema `website_*` |

---

## BOUCLE D'ITÉRATION (même que workflow-process.md — adapté ingestion)

### Le "test" ici = mesurer la qualité d'ingestion
La qualité se mesure par la performance RAG APRÈS ingestion.

### Étape 1 : Test 1 document
```bash
source .env.local
# Ingérer 1 document de test
python3 scripts/ingest-one.py --file datasets/sample/btp-dtu-14-001.pdf --pipeline standard
# Vérifier dans Pinecone : bon chunk ? bon embedding ?
python3 scripts/verify-ingestion.py --last 1
```

### Étape 2 : Test retrieval sur document ingéré
```bash
# Question sur le document ingéré
python3 eval/quick-test.py --questions 1 --pipeline standard --filter "last-ingested"
# Double analyse si échec
python3 eval/node-analyzer.py --execution-id <ID>
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
```

### Étape 3 : Test batch (10 documents, 5 questions chacun)
```bash
python3 scripts/ingest-batch.py --sector btp --count 10
python3 eval/quick-test.py --questions 5 --pipeline standard --sector btp
```

### Étape 4 : Ingestion complète d'un dataset sectoriel
```bash
# Télécharger le dataset
python3 scripts/download-dataset.py --name PatronusAI/financebench

# Ingérer via n8n Ingestion workflow
python3 scripts/trigger-ingestion.py --dataset financebench --workers 2

# Vérifier la qualité
python3 scripts/verify-ingestion.py --dataset financebench
python3 eval/run-eval-parallel.py --sector finance --label "financebench-ingest"
```

### Cibles d'amélioration des workflows
| Métrique | V3.1 actuel | Cible V4.0 |
|---------|------------|-----------|
| Chunks utiles / document | ~60% | >= 80% |
| Temps ingestion / doc | variable | < 30s |
| Qualité embedding (retrieval@5) | baseline | +10% |
| Couverture graph entities | partielle | >= 90% |

---

## DATASETS À INGÉRER (depuis mon-ipad/technicals/data/sector-datasets.md)

### Ordre de priorité
```
1. Finance (impact immédiat sur Quantitative pipeline 78.3% FAIL)
   - PatronusAI/financebench (150 QA expert)
   - TheFinAI/convfinqa (3,800 conversations)

2. Juridique (améliore Graph pipeline 68.7% FAIL)
   - rcds/french_case_law (534,289 décisions)
   - rcds/cold-french-law (droit français)

3. BTP/Construction
   - Datasets identifiés dans sector-datasets.md section 3.1

4. Industrie/Manufacturing
   - Datasets identifiés dans sector-datasets.md section 3.2
```

### Script de téléchargement
```bash
source .env.local
python3 scripts/download-sector-datasets.py --sector finance --max 10000
python3 scripts/download-sector-datasets.py --sector juridique --max 10000
```

---

## AMÉLIORATION DES WORKFLOWS (processus)

### Pour chaque technique découverte en Phase 0
```
1. IMPLÉMENTER dans n8n (workflow local Codespace)
2. TESTER sur 5 documents de référence
3. MESURER la qualité retrieval (avant/après)
4. Si amélioration >= +2% → intégrer
5. SYNC vers GitHub (n8n/sync.py)
6. COMMIT + PUSH
7. SIGNALER à mon-ipad pour déploiement sur VM
```

### Règle : UN fix par itération
- Jamais changer le chunking ET l'enrichissement en même temps
- Baseline claire avant chaque changement
- Comparer avec `snapshot/good/` pour référence

---

## COMMUNICATION AVEC MON-IPAD

Les améliorations validées dans ce Codespace sont déployées sur la VM par mon-ipad :

```bash
# 1. Exporter le workflow amélioré
python3 n8n/sync.py  # exporte vers n8n/live/

# 2. Committer
git add n8n/ research/ docs/
git commit -m "feat(ingestion): V4.0 — late chunking +12% retrieval"
git push origin main

# 3. mon-ipad importe via API REST n8n (sur la VM)
# → Ce déploiement est fait depuis mon-ipad, pas depuis ce Codespace
```

---

## DATASETS & QUESTIONS — INVENTAIRE COMPLET A INGERER

### Vue globale des datasets
| Categorie | Datasets | Questions/items | Destination BDD | Status |
|-----------|----------|----------------|----------------|--------|
| **Benchmarks Phase 2** | 14 datasets HuggingFace | 3,000 | Pinecone + Neo4j + Supabase | INGERE (P2 namespaces) |
| **Phase 4 Standard** | RAGBench×8, SQuAD v2, MS MARCO, TriviaQA, CRAG | 39,805 (10,917 unique ctx) | Pinecone `sota-rag-jina-1024` | **INGESTION EN COURS** |
| **Phase 4 Graph** | RAGBench HotpotQA, HotpotQA, MuSiQue, MultiHop-RAG | 13,856 (11,300 unique ctx) | Pinecone + Neo4j | **INGESTION EN COURS** |
| **Phase 4 Quant** | RAGBench FinQA, TAT-QA | 8,000 (3,876 unique ctx) | Pinecone + Supabase | **SUPABASE DONE**, Pinecone EN COURS |
| **Finance sectors** | convfinqa, financebench, finqa, sec_qa, tatqa | 2,150 | Pinecone sectors + Supabase + Neo4j | **DONE** |
| **Juridique sectors** | french_case_law, cold_french_law, cail2018, hotpotqa | 2,500 | Pinecone sectors + Supabase + Neo4j | **DONE** |
| **BTP sectors** | code_accord, docie, ragbench_techqa | 1,844 | Pinecone sectors + Supabase + Neo4j | **DONE** |
| **Industrie sectors** | manufacturing_qa, ragbench | 1,015 | Pinecone sectors + Supabase + Neo4j | **DONE** |
| **Total** | **61,661+ questions** | | | |

### Dependances Phase 2 (qui attend quoi)
| Repo | Attend de rag-data-ingestion | Bloquant pour |
|------|------------------------------|---------------|
| **rag-tests** | 14 benchmarks HF ingeres dans les BDD | Lancer Phase 2 (3,000q) |
| **rag-website** | Datasets sectoriels ingeres dans BDD separees | Demos chatbot avec vrais docs sectoriels |
| **rag-dashboard** | Rien directement | Affiche les metriques post-ingestion |

### Methodes de test qualite ingestion
| Methode | Commande | Usage |
|---------|----------|-------|
| Verification chunks | `python3 scripts/verify-ingestion.py --last 1` | Apres chaque ingestion unitaire |
| Test retrieval post-ingestion | `python3 eval/quick-test.py --questions 5 --pipeline standard` | Valider que les docs ingeres sont retrouves |
| Stats Pinecone | MCP pinecone → `describe-index-stats` | Verifier nb vecteurs par namespace |
| Stats Neo4j | MCP neo4j → `get-schema` | Verifier labels et relations |
| Stats Supabase | MCP supabase → `execute_sql` (SELECT count) | Verifier nb lignes par table |

### HF Space — Test des pipelines apres ingestion
Apres ingestion, tester que les pipelines RAG retrouvent les documents ingeres :
```
Standard     : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3
Graph        : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717
Quantitative : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
Orchestrator : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0
```
Appel : `curl -X POST "<url>" -H "Content-Type: application/json" -d '{"query": "..."}'`
**IMPORTANT** : Le champ est `query` (PAS `question`).

**Session 72 STATUS** : Ingestion webhook returns HTTP 200 (/webhook/rag-v6-ingestion). Enrichment returns HTTP 500. Standard/Quantitative/Orchestrator webhooks OK. LLM nodes patched to OpenRouter (was LiteLLM Space#7 DOWN).
```

---

## RÈGLES D'OR

1. **Consulter fixes-library.md EN PREMIER** — avant tout debug (`technicals/debug/fixes-library.md`)
2. **Recherche papiers 2026 OBLIGATOIRE** avant tout développement
3. **source .env.local** avant tout script Python
4. **UN fix par itération** — jamais plusieurs changements simultanés
5. **Mesurer AVANT et APRÈS** chaque changement
6. **Double analyse** (node-analyzer + analyze_n8n_executions)
7. **Ne jamais écraser** les indexes Pinecone de mon-ipad (`sota-rag-*`)
8. **Push résultats** avant arrêt du Codespace (éphémère !)
9. **Documenter** chaque technique dans `research/papers-2026.md`
10. **Signaler à mon-ipad** les workflows validés pour déploiement VM
11. **Delegation multi-model** — Opus decide, Sonnet batch downloads, Haiku verifications

### Strategie Multi-Model (Session 26)
- **Opus 4.6** : Strategie d'ingestion, analyse qualite embeddings, decisions d'enrichissement
- **Sonnet 4.5** : Batch downloads HuggingFace, transformations data, operations Docker (`Task(model: "sonnet")`)
- **Haiku 4.5** : Verification datasets, exploration codebase (`Task(model: "haiku", subagent_type: "Explore")`)
- **Regle** : Opus DECIDE quand deleguer. Jamais deleguer la strategie d'ingestion ou l'analyse qualite.

---

## FIN DE SESSION

```bash
# Sync workflows
python3 n8n/sync.py

# Commit
git add n8n/ research/ docs/ logs/
git commit -m "feat(ingestion): [description] — +X% retrieval qualité"
git push origin main
```

---

*Ce CLAUDE.md est géré depuis `mon-ipad/directives/repos/rag-data-ingestion.md`.*
