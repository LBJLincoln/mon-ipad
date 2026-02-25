# EXECUTIVE SUMMARY — Nomos AI Multi-RAG Orchestrator

> Last updated: 2026-02-25T12:30:00+00:00
> **Ce fichier DOIT etre consulte et mis a jour a CHAQUE session.**
> Il est la reference unique pour comprendre tout le projet en langage clair.

---

## TABLE DES MATIERES

1. [Vue d'ensemble du projet](#1-vue-densemble-du-projet)
2. [Architecture complete](#2-architecture-complete)
3. [Les 7 repos GitHub — Roles et contenus](#3-les-7-repos-github)
4. [Infrastructure et machines](#4-infrastructure-et-machines)
5. [Les 4 pipelines RAG — Comment ca marche](#5-les-4-pipelines-rag)
6. [Bases de donnees — Etat et contenu](#6-bases-de-donnees)
7. [Credentials et acces](#7-credentials-et-acces)
8. [Boucle de travail — Etape par etape](#8-boucle-de-travail)
9. [Commandes executees dans chaque session](#9-commandes-executees)
10. [Fichiers modifies — Inventaire complet](#10-fichiers-modifies)
11. [Etat actuel et metriques](#11-etat-actuel)
12. [Prochaines etapes](#12-prochaines-etapes)
13. [Glossaire](#13-glossaire)

---

## 1. VUE D'ENSEMBLE DU PROJET

### Qu'est-ce que Nomos AI ?
Nomos AI est un **systeme d'intelligence artificielle qui repond a des questions complexes** en cherchant dans plusieurs bases de donnees simultanement. Il utilise 4 methodes de recherche differentes (appelees "pipelines") et un orchestrateur qui choisit la meilleure methode pour chaque question.

### Objectif final
Construire un moteur de reponse capable de traiter **1 million+ de questions** dans 4 secteurs d'activite (BTP, Industrie, Finance, Juridique) avec une precision de **85%+** et un temps de reponse de **moins de 2.5 secondes**.

### Ou en est-on ?
- **Phase 1** (200 questions) : **PASSED** (83.9% overall, 20 fev 2026, session 30). Tous les 4 pipelines au-dessus de leurs cibles.
- **Phase 2** (1,000q par pipeline) : **EN COURS** — Session 62 mega eval: 4 pipelines × ~1000q, 50 workers, 10 HF Spaces, 74/3950 tested. Early results: Standard 75%, Graph 20%, Quant 22%, Orch 81%.
- **Session 60 fixes** : Quantitative (API key NaN + Supabase wrong host) + Orchestrator (Redis removed, 9 nodes) + all Postgres credentials.
- **Session 61** : HF Space #2 deployed, GH Actions on 3 repos (all passing), chatbot active (75% tests), data ingestion audited.
- **Session 62** : **10 HF Spaces deployed** (LBJLincoln: 1,3,5,7,9 / LBJLincoln26: 2,4,6,8,10), round-robin load balancing, 6 repair agents fixing broken workflows (3 fixed: Status Dashboard, Enrichissement V4.0, Action Executor).
- **PME** : 3 workflows imported, Action Executor FIXED (simplified 2-node workflow), WhatsApp Bridge active (Telegram disabled).
- **Data ingestion** : Dataset Ingestion WORKING, Enrichissement V4.0 **FIXED** (Redis removed), Ingestion V4.0 repair in progress.

### Chiffres cles
| Metrique | Valeur |
|----------|--------|
| Questions testees a ce jour | **1,600+** (Phase 1 + Phase 2 + Session 62 mega eval running) |
| Precision Phase 1 (baseline) | 83.9% (PASSED) |
| Precision Phase 2 (Session 62, early) | Std 75%, Graph 20%, Quant 22%, Orch 81% (74/3950 tested) |
| Vecteurs dans Pinecone | 22,070 |
| Entites dans Neo4j | 19,788 |
| Lignes dans Supabase | ~17,600 |
| Datasets telecharges | 7,609 sectoriels + 669MB HuggingFace |
| Commits depuis le debut | 200+ |
| Sessions Claude Code | **62** |
| Sites web live | **4** (ETI + PME connectors + PME use cases + Dashboard) |
| **HF Spaces n8n** | **10** (2 comptes, round-robin load balancing) |

---

## 2. ARCHITECTURE COMPLETE

### Schema global
```
                    UTILISATEUR (iPad / Termius)
                           |
                    Terminal SSH connecte a
                           |
              VM GOOGLE CLOUD (34.136.180.66)
              Machine permanente e2-micro
              970 MB RAM (~400 MB disponibles)
              30 GB disque | PILOTAGE ONLY
                           |
                    CLAUDE CODE CLI
                    Modele: Opus 4.6
                    Tour de controle
                    Repo: mon-ipad
                    (n8n REMOVED — VM cleaned)
                           |
         +-----------------+-----------------+
         |                                   |
    10 HF SPACES                     BASES DE DONNEES
    n8n (16GB RAM each)         Pinecone + Neo4j + Supabase
    Round-robin load balancing           |
    14 workflows per space                |
    Execution layer                       |
         |                                 |
         +---------------------------------+
                           |
                     OPENROUTER
                     7 keys (multi-rotation)
                     Llama 70B + Gemma 27B
```

### Flux d'une question (de A a Z)
```
1. L'utilisateur pose une question (ex: "Quel est le chiffre d'affaires de TechVision en 2023 ?")
2. La question arrive via webhook HTTP POST sur n8n
3. n8n analyse l'intention (quel type de question ?)
4. n8n route vers le bon pipeline :
   - Standard → recherche dans Pinecone (texte)
   - Graph → recherche dans Neo4j (entites et relations)
   - Quantitative → genere du SQL et interroge Supabase (chiffres)
   - Orchestrator → combine les 3 ci-dessus
5. Le pipeline recupere les informations pertinentes
6. Un LLM (Llama 70B via OpenRouter) formule la reponse
7. La reponse est renvoyee a l'utilisateur avec les sources
```

---

## 3. LES 7 REPOS GITHUB

Tous les repos sont **prives** sous le compte `LBJLincoln`.

### Tableau recapitulatif
| # | Repo | Role | Ou ca tourne | Contenu principal |
|---|------|------|-------------|-------------------|
| 1 | **mon-ipad** | Tour de controle | VM Google Cloud | Directives, scripts eval, configs MCP, CLAUDE.md master |
| 2 | **rag-tests** | Tests des 4 pipelines | Codespace / HF Space | Scripts Python de test, resultats JSON |
| 3 | **rag-website** | Site vitrine ETI | Vercel (prod) | Next.js 14, 4 secteurs, chatbots |
| 4 | **rag-dashboard** | Dashboard metriques | GitHub Pages / Vercel | HTML/JS statique, graphiques live |
| 5 | **rag-data-ingestion** | Ingestion donnees | Codespace | Scripts download, workflows ingestion |
| 6 | **rag-pme-connectors** | Site PME connecteurs | Vercel | Next.js 15, 15 connecteurs apps (WhatsApp, Telegram, Gmail, etc.) |
| 7 | **rag-pme-usecases** | Site PME use cases | Vercel | Next.js 14, 200 cas d'usage |

### Relations entre repos
```
mon-ipad (PILOTE)
   |
   |-- distribue les CLAUDE.md personnalises a chaque repo
   |-- fixe les workflows n8n
   |-- analyse les resultats des autres repos
   |
   +-- rag-tests : MESURE la performance → rapporte via git push
   +-- rag-website : CONSTRUIT le site → deploie via Vercel
   +-- rag-data-ingestion : INGERE les donnees → Pinecone/Neo4j/Supabase
   +-- rag-dashboard : AFFICHE les metriques (lecture seule)
   +-- rag-pme-connectors : Site PME (statique)
   +-- rag-pme-usecases : Site PME (statique)
```

### Fichiers cles dans mon-ipad (tour de controle)
| Dossier | Contenu | Fichiers importants |
|---------|---------|---------------------|
| `directives/` | Memoire de session, status | `session-state.md`, `status.md`, `workflow-process.md` |
| `directives/repos/` | CLAUDE.md pour chaque satellite | `rag-tests.md`, `rag-website.md`, `rag-data-ingestion.md`, `rag-dashboard.md` |
| `technicals/` | Documentation technique (4 sous-dossiers: debug/, infra/, project/, data/) | `debug/knowledge-base.md`, `debug/fixes-library.md`, `project/team-agentic-process.md`, `infra/architecture.md` |
| `eval/` | Scripts Python d'evaluation | `quick-test.py`, `iterative-eval.py`, `run-eval-parallel.py` |
| `scripts/` | Utilitaires | `push-directives.sh`, `codespace-control.sh`, `download-sectors.py` |
| `n8n/live/` | Workflows n8n (JSON) | `standard.json`, `graph.json`, `quantitative.json`, `orchestrator.json` |
| `datasets/` | Questions de test | `phase-1/*.json`, `phase-2/*.json`, `sectors/**/*.jsonl` |
| `docs/` | Dashboard + readiness | `status.json`, `data.json`, `phase2-readiness.md`, **ce fichier** |
| `snapshot/` | References de workflows valides | `current/`, `good/` |
| `logs/` | Logs d'execution | `diagnostics/` |

---

## 4. INFRASTRUCTURE ET MACHINES

### VM Google Cloud (permanente — siege de controle)
| Element | Detail |
|---------|--------|
| **IP** | 34.136.180.66 |
| **OS** | Debian 11 (Bullseye) |
| **CPU** | 1 vCPU Intel Xeon @ 2.20GHz |
| **RAM** | 970 MB total (~400 MB disponibles) |
| **Disque** | 30 GB (12 GB utilises) |
| **Acces** | SSH via Termius (iPad) |
| **Docker** | NO containers running — n8n REMOVED (Session 42, freed ~270MB RAM). All n8n operations on HF Space. |
| **Usage** | PILOTAGE UNIQUEMENT — tour de controle, git, MCP servers. NO eval scripts, NO n8n. |

### HF Spaces (execution — 16 GB RAM each, gratuit)
| Element | Detail |
|---------|--------|
| **Count** | **10 HF Spaces** (session 62) |
| **Accounts** | LBJLincoln (Spaces 1,3,5,7,9) + LBJLincoln26 (Spaces 2,4,6,8,10) |
| **URLs** | lbjlincoln-nomos-rag-engine.hf.space, lbjlincoln-nomos-rag-engine-2 through 10 |
| **RAM** | 16 GB per Space (cpu-basic) |
| **n8n** | Version 2.8.4 (pinned) |
| **DB interne** | Supabase PostgreSQL + Redis (queue mode: 1 main + 2 workers per Space) |
| **Usage** | Round-robin load balancing for Phase 2 eval (50 concurrent workers across 10 Spaces) |
| **Status** | **ALL 10 RUNNING** — verified HTTP 200 on Standard pipeline, incremental saves every 5 min |
| **Workflows** | 14 workflows per Space (11 active: 4 pipelines + 7 support, 3 PME in repair) |

### Codespaces GitHub (ephemeres — 60h/mois)
| Element | Detail |
|---------|--------|
| **CPU** | 2 cores |
| **RAM** | 8 GB |
| **Disque** | 32 GB |
| **Usage** | Tests lourds (500q+), ingestion massive, dev website |
| **IMPORTANT** | Toujours push vers GitHub AVANT arret (travail perdu sinon) |

### Vercel (production — sites web)
| Site | URL | Status |
|------|-----|--------|
| ETI (4 secteurs) | nomos-ai-pied.vercel.app | Live |
| PME Connecteurs | nomos-pme-connectors-alexis-morets-projects.vercel.app | Live |
| PME Use Cases | nomos-pme-usecases-alexis-morets-projects.vercel.app | Live |
| Dashboard | nomos-dashboard-alexis-morets-projects.vercel.app | Live |

---

## 5. LES 4 PIPELINES RAG

### Comment chaque pipeline fonctionne

#### Pipeline Standard (recherche textuelle)
```
Question → Genere une question hypothetique (HyDE)
         → Cherche dans Pinecone (10K+ vecteurs)
         → Reranking Jina (trie par pertinence)
         → LLM genere la reponse avec les sources
```
- **Base de donnees** : Pinecone `sota-rag-jina-1024` (10,411 vecteurs)
- **Precision** : Phase 1: 85.5%, Phase 2: ~36% (degradation sous investigation)
- **Webhook** : `/webhook/rag-multi-index-v3`

#### Pipeline Graph (entites et relations)
```
Question → Extrait les entites (personnes, lieux, organisations)
         → Cherche dans Neo4j (19K entites, 76K relations)
         → Recupere les sous-graphes pertinents
         → LLM synthetise les relations trouvees
```
- **Base de donnees** : Neo4j Aura (19,788 nodes, 76,717 relations)
- **Precision** : Phase 1: 78.0%, Phase 2: 78.0% (500/500 COMPLETE)
- **Webhook** : `/webhook/ff622742-6d71-4e91-af71-b5c666088717`

#### Pipeline Quantitative (chiffres et tableaux)
```
Question → Analyse l'intention financiere
         → Genere du SQL via LLM (ou template matching)
         → Execute le SQL dans Supabase
         → LLM interprete les resultats
```
- **Base de donnees** : Supabase (financials, balance_sheet, sales_data, etc.)
- **Precision** : Phase 1: 92.0%, Phase 2: 92.0% (500/500 COMPLETE)
- **Webhook** : `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9`

#### Pipeline Orchestrator (combine les 3)
```
Question → Classifie l'intention (standard/graph/quantitative/multi)
         → Planifie les sous-taches
         → Execute chaque sous-tache via le pipeline appropriate
         → Aggrege les resultats
```
- **Base de donnees** : Toutes (Pinecone + Neo4j + Supabase)
- **Precision** : Phase 1: 80.0%, Phase 2: 0% (BROKEN — 404/empty on all questions)
- **Webhook** : `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0`

### Parametres d'appel (identiques pour les 4)
```bash
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/<path>" \
  -H "Content-Type: application/json" \
  -d '{"query": "Votre question ici", "sessionId": "optionnel"}'
```
**ATTENTION** : Le champ est `query` (PAS `question`).

---

## 6. BASES DE DONNEES

### Pinecone (recherche vectorielle)
Pinecone stocke les textes transformes en vecteurs numeriques (1024 dimensions).
Quand une question est posee, elle est aussi transformee en vecteur, et Pinecone
trouve les textes les plus proches mathematiquement.

| Index | Vecteurs | Usage |
|-------|----------|-------|
| `sota-rag-jina-1024` | 10,411 | Pipeline Standard + Graph |
| `sota-rag-phase2-graph` | 1,248 | Graph enrichi (musique dataset) |
| `sota-rag-cohere-1024` | 10,411 | Backup (ancien systeme) |

### Neo4j (graphe de connaissances)
Neo4j stocke les entites (personnes, lieux, organisations) et leurs relations.
Exemple : "Alexander Fleming" → DECOUVRIT → "Penicilline" → TRAITE → "Infections"

| Element | Nombre |
|---------|--------|
| Personnes | 8,531 |
| Entites generiques | 8,331 |
| Organisations | 1,775 |
| Villes | 840 |
| Relations totales | 76,717 |

### Supabase (base SQL)
Supabase stocke les donnees structurees (tableaux, chiffres, listes).

| Table | Lignes | Contenu |
|-------|--------|---------|
| financials | 24 | Chiffres d'affaires TechVision, GreenEnergy, HealthPlus |
| balance_sheet | 12 | Bilans comptables |
| sales_data | 1,152 | Ventes detaillees |
| employees | 150 | Effectifs |
| finqa_tables | 200 | Questions financieres HuggingFace (Phase 2) |
| tatqa_tables | 150 | Questions tableaux HuggingFace (Phase 2) |
| convfinqa_tables | 100 | Questions conversationnelles financieres (Phase 2) |
| benchmark_datasets | 10,772 | Donnees de benchmark |
| + 32 autres tables | ~5,000+ | Infrastructure, logs, feedback |

---

## 7. CREDENTIALS ET ACCES

### Ou sont stockees les credentials
| Emplacement | Contenu | Securite |
|-------------|---------|----------|
| `.env.local` (VM) | Toutes les cles API | Gitignore (JAMAIS dans GitHub) |
| `.claude/settings.json` (VM) | Config MCP servers | Gitignore |
| Docker env vars | Variables n8n | Container local |
| HF Space secrets | Variables HF | Interface HuggingFace |
| Fichiers source : `infra/credentials.md`, `technicals/credentials.md` | Documentation (pas les vraies cles) | Repo prive |

### Services connectes
| Service | Usage | Plan | Limite |
|---------|-------|------|--------|
| OpenRouter | LLM (Llama 70B, Gemma 27B) | Free | 7 keys configured (pipeline-specific rotation) |
| Jina AI | Embeddings + Reranking | Free | 2 keys configured, 1M tokens/mois each |
| Pinecone | Vector DB | Free | 100K vecteurs |
| Neo4j Aura | Graph DB | Free | 200K nodes |
| Supabase | SQL DB | Free | 500 MB |
| Cohere | Reranking (backup) | Trial | Quasi-epuise |
| HuggingFace | Datasets + HF Space | Free | 2 accounts, 2 tokens configured |
| GitHub | 7 repos prives | Free | Illimite |
| Vercel | 4 sites deployes | Free | Illimite |

### MCP Servers (outils connectes a Claude Code)
Claude Code utilise 7 "MCP Servers" pour interagir directement avec les services :

| MCP | Capacites | Empreinte RAM |
|-----|-----------|---------------|
| n8n | Executer/inspecter les workflows | ~2 MB |
| pinecone | Chercher/ajouter des vecteurs | ~1.4 MB |
| neo4j | Requetes Cypher sur le graphe | ~2.5 MB |
| supabase | Requetes SQL directes | ~1 MB |
| jina-embeddings | Generer des embeddings | ~0.7 MB |
| cohere | Reranking de resultats | ~0.6 MB |
| huggingface | Chercher des modeles/datasets | ~0.8 MB |

---

## 8. BOUCLE DE TRAVAIL — ETAPE PAR ETAPE

### Demarrage de chaque session (5 minutes)
```
ETAPE 1 : Lire l'etat precedent
  → cat directives/session-state.md     (memoire de travail)
  → cat docs/status.json                (metriques)
  → cat directives/status.md            (resume session precedente)
  → cat technicals/debug/knowledge-base.md    (cerveau persistant)

ETAPE 2 : Verifier les fixes connus
  → cat technicals/debug/fixes-library.md     (35 bugs deja resolus)

ETAPE 3 : Identifier l'objectif de session
  → Quel pipeline a le plus gros ecart par rapport a sa cible ?
  → Quelles taches sont en cours depuis la session precedente ?
```

### Boucle d'iteration (quand on fixe un pipeline)
```
     +--> DIAGNOSTIQUER (double analyse obligatoire)
     |        |
     |        v
     |    FIXER (1 seul changement a la fois)
     |        |
     |        v
     |    TESTER (minimum 5 questions)
     |        |
     |        v
     |    PASSE ?
     |    /       \
     |  OUI       NON
     |   |         |
     |   v         +---> retour a DIAGNOSTIQUER
     |  SYNC + COMMIT + PUSH
     |   |
     +---+  (iteration suivante si necessaire)
```

### Fin de chaque session (10 minutes)
```
ETAPE 1 : Sync les workflows modifies
  → python3 n8n/sync.py

ETAPE 2 : Generer les metriques
  → python3 eval/generate_status.py

ETAPE 3 : Mettre a jour les fichiers d'etat
  → directives/session-state.md
  → directives/status.md
  → technicals/knowledge-base.md (si decouvertes)
  → technicals/fixes-library.md (si fixes)
  → docs/executive-summary.md (CE FICHIER)

ETAPE 4 : Commit + Push (TOUS les repos impactes)
  → git add <fichiers>
  → git commit -m "description"
  → git push origin main
  → bash scripts/push-directives.sh (si CLAUDE.md modifies)
```

---

## 9. COMMANDES EXECUTEES DANS CHAQUE SESSION

### Commandes de pilotage (VM — tour de controle)
```bash
# --- Demarrage ---
cat directives/session-state.md          # Lire l'etat
cat docs/status.json                      # Lire les metriques
source .env.local                         # Charger les variables d'environnement

# --- Tests rapides (sur HF Space) ---
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" -d '{"query":"...","sessionId":"..."}'

# --- Diagnostics ---
python3 eval/quick-test.py --questions 5 --pipeline standard
python3 eval/node-analyzer.py --execution-id <ID>
python3 scripts/analyze_n8n_executions.py --execution-id <ID>

# --- Sync et generation ---
python3 n8n/sync.py                       # Sync les workflows
python3 eval/generate_status.py           # Generer status.json

# --- Git (push multi-repo) ---
git add <fichiers>
git commit -m "description"
git push origin main
bash scripts/push-directives.sh           # Push CLAUDE.md vers satellites

# --- Pilotage Codespaces ---
gh codespace list                         # Lister les Codespaces
gh codespace start --codespace <name>     # Demarrer un Codespace
scripts/codespace-control.sh launch <cs>  # Lancer un test distant
scripts/codespace-control.sh status <cs>  # Voir la progression
scripts/codespace-control.sh stream <cs>  # Stream live des logs

# --- Docker VM ---
docker ps                                 # Voir les containers
docker logs n8n-n8n-1 --tail 50           # Logs n8n
docker compose restart n8n                # Redemarrer n8n (rare)
```

### Commandes dans rag-tests (Codespace)
```bash
bash scripts/setup-claude-opus.sh         # Configurer Opus 4.6
docker compose up -d                      # Demarrer n8n local (3 workers)
source .env.local                         # Charger variables
python3 eval/quick-test.py --questions 5 --pipeline quantitative
python3 eval/iterative-eval.py --label "Phase1-fix"
python3 eval/run-eval-parallel.py --reset --label "phase1-200q"
git add docs/ logs/ && git push origin main
```

### Commandes dans rag-website (Codespace)
```bash
npm install && npm run dev                # Dev local (port 3000)
npm run build                             # Build pour prod
git push origin main                      # Deploy Vercel auto
```

### Commandes dans rag-data-ingestion (Codespace)
```bash
docker compose up -d                      # n8n + 2 workers
source .env.local
python3 scripts/download-sector-datasets.py --sector finance
python3 scripts/trigger-ingestion.py --dataset financebench --workers 2
git push origin main
```

---

## 10. FICHIERS MODIFIES — INVENTAIRE COMPLET

### Fichiers critiques (modifies regulierement)
| Fichier | Role | Modifie a chaque session ? |
|---------|------|---------------------------|
| `CLAUDE.md` | Directives globales (40 regles, architecture) | Souvent |
| `directives/session-state.md` | Memoire de travail active | **TOUJOURS** |
| `directives/status.md` | Resume de la derniere session | **TOUJOURS** (en dernier) |
| `technicals/debug/knowledge-base.md` | Cerveau persistant (patterns, solutions) | Souvent |
| `technicals/debug/fixes-library.md` | 35+ bugs documentes | Apres chaque fix |
| `docs/status.json` | Metriques machine-readable (auto-genere) | Apres chaque eval |
| `docs/data.json` | Donnees de toutes les iterations | Apres chaque eval |
| `docs/executive-summary.md` | **CE FICHIER** | **TOUJOURS** |
| `docs/phase2-readiness.md` | Checklist pre-lancement Phase 2 | Avant Phase 2 |

### Fichiers de configuration (modifies rarement)
| Fichier | Role |
|---------|------|
| `technicals/infra/architecture.md` | Architecture des 4 pipelines + 9 workflows |
| `technicals/project/team-agentic-process.md` | Strategie multi-model (Opus+Sonnet+Haiku) |
| `technicals/project/phases-overview.md` | Plan des 5 phases (200q → 1M+) |
| `technicals/infra/env-vars-exhaustive.md` | 33 variables d'environnement documentees |
| `technicals/data/sector-datasets.md` | 1000+ types de documents par secteur |

**Note** : `technicals/` est organise en 4 sous-dossiers: `debug/`, `infra/`, `project/`, `data/`
| `directives/workflow-process.md` | Boucle d'iteration detaillee |
| `directives/n8n-endpoints.md` | Webhooks et API REST |
| `directives/objective.md` | Objectif final du projet |

### Fichiers par repo satellite
| Repo | Fichier principal | Pousse depuis |
|------|-------------------|---------------|
| rag-tests | `CLAUDE.md` | `directives/repos/rag-tests.md` |
| rag-website | `CLAUDE.md` | `directives/repos/rag-website.md` |
| rag-data-ingestion | `CLAUDE.md` | `directives/repos/rag-data-ingestion.md` |
| rag-dashboard | `CLAUDE.md` | `directives/repos/rag-dashboard.md` |

### Fichiers de workflows n8n (JSON)
| Fichier | Pipeline |
|---------|----------|
| `n8n/live/standard.json` | Standard RAG V3.4 |
| `n8n/live/graph.json` | Graph RAG V3.3 |
| `n8n/live/quantitative.json` | Quantitative V2.0 |
| `n8n/live/quantitative-v2-template-fix.json` | Quantitative avec template SQL |
| `n8n/live/orchestrator.json` | Orchestrator V10.1 |
| `n8n/live/ingestion.json` | Ingestion V3.1 |
| `n8n/live/enrichment.json` | Enrichissement V3.1 |

---

## 11. ETAT ACTUEL ET METRIQUES

### Phase 1 — PASSED (20 fevrier 2026, session 30)
| Pipeline | Precision | Objectif | Status | Ecart |
|----------|-----------|----------|--------|-------|
| Standard | **85.5%** (47/55) | >= 85% | PASSE | +0.5pp |
| Graph | **78.0%** (39/50) | >= 70% | PASSE | +8.0pp |
| Quantitative | **92.0%** (46/50) | >= 85% | PASSE | +7.0pp |
| Orchestrator | **80.0%** (40/50) | >= 70% | PASSE | +10.0pp |
| **Global** | **83.9%** | >= 75% | **PASSE** | +8.9pp |

### Phase 2 — EN COURS (25 fevrier 2026, session 62 mega eval)
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 20 | 1000 | **75.0%** | **RUNNING** — 10-space cluster, 50 workers |
| Graph | 20 | 980 | **20.0%** | **RUNNING** — early results, sample size small |
| Quantitative | 18 | 970 | **22.2%** | **RUNNING** — early results, sample size small |
| Orchestrator | 16 | 1000 | **81.2%** | **RUNNING** — highest accuracy so far |
| **TOTAL** | **74** | **3950** | **48.6%** | **RUNNING** — incremental saves, dedup enabled |

**Note**: Early results (74/3950 = 1.9% complete). Accuracy will stabilize as sample size grows. Estimated completion: 35-40h.

### Bloqueur critique RESOLU : Broken n8n env var syntax (sessions 39-51)
- **Root cause found (Session 51)** : Standard + Graph workflow JSONs used broken syntax `={{.OPENROUTER_KEY_STANDARD}}` instead of correct `={{$env.OPENROUTER_KEY_STANDARD}}`. The `={{.VAR}}` syntax is NOT valid in n8n — evaluates to `null`, causing all HTTP headers to send `Bearer null` for OpenRouter, Jina, and Pinecone API calls.
- **Why Quantitative worked** : quantitative.json already used correct `={{$env.VAR}}` syntax. Also uses `credentials.httpHeaderAuth` approach in some nodes.
- **Previous fix attempts (v1-v4.0)** : Addressed wrong problem (activation issues, entrypoint retry logic, credential stripping). The real issue was expression syntax in workflow JSONs.
- **Fix applied (v5.4)** : `sed -i 's/={{\\./={{$env./g'` across all affected JSONs (n8n/live/ + hf-space/n8n-workflows/). Total: 17 instances fixed (8 standard, 5 graph, 1 benchmark, 3 quantitative-template).
- **Verification** : `grep -r '={{\\.' n8n/live/ hf-space/n8n-workflows/` returns zero matches.
- **Deployment status** : v5.4 deploying to HF Space

### Fixes documentes (55+ au total)
Les 55+ bugs documentes sont dans `technicals/debug/fixes-library.md`.
Highlights recents :
- FIX-54 : Broken n8n expression syntax `={{.VAR}}` → `={{$env.VAR}}` (Session 51, CRITICAL)
- FIX-55 : rag-storage migration (datasets/snapshots/logs/outputs) (Session 51)
- FIX-36 : Phase 1 gate calculation (excluded Phase 2 questions)
- FIX-29 to FIX-35 : Quantitative + Orchestrator fixes (sessions 27-28)
- Sessions 39-50 : HF Space activation issues — root cause was env var syntax, not activation

### Tests de concurrence (session 27)
| Config | Pipelines | Concurrency | Standard | Graph | Orchestrator |
|--------|-----------|-------------|----------|-------|--------------|
| Baseline | 3 | 1 | 100% (9s) | 100% (18s) | 100% (14s) |
| Moderate | 3 | 3 | 100% (23s) | 90% (26s) | 70% (35s) |
| Stress | 3 | 5 | 100% (29s) | 90% (44s) | 0% AUTO-STOP |

**Limites recommandees** : Standard 5, Graph 3, Orchestrator 1, Quantitative 1

---

## 12. PROCHAINES ETAPES

### Sessions 42-62 — PROGRESS (what was done)
1. **Session 42**: VM n8n REMOVED (freed ~270MB RAM). VM is pilotage-only now. Anti-VM guards added to all eval scripts.
2. **Session 43**: HF Space rebuilt with queue mode (3 workers), Supabase PostgreSQL, 7 OpenRouter keys.
3. **Sessions 44-45**: entrypoint.sh v2-v3.1 attempts. Credential stripping, versionId fixes, CLI import debugging.
4. **Sessions 46-47**: PATCH activation instead of POST, sqlite3 direct activation attempts. Session 46 prompt optimization.
5. **Session 48**: entrypoint v4.0 — direct sqlite3 activation (bypasses n8n publish system), credential leak fixes, auto-generate missing IDs.
6. **Session 49**: Deployed v5.2 with 2-pass activation, fixed httpHeaderAuth type mapping, removed duplicate quantitative workflow.
7. **Session 50**: Deployed v5.3 with per-pipeline OpenRouter keys (6 credentials across 3 accounts, 7 env vars for key rotation).
8. **Session 51**: ROOT CAUSE FOUND — broken env var syntax `={{.VAR}}` instead of `={{$env.VAR}}` in workflow JSONs. Fixed 17 instances, deploying v5.4.
9. **Session 58**: Multi-endpoint architecture, per-pipeline routing, GitHub Actions matrix, 5000 questions ready.
10. **Session 59**: Project chatbot MVP deployed on 3 Vercel sites, 1000q test dataset created.
11. **Session 60**: Quantitative + Orchestrator FIXED (all 4 pipelines working), Redis dependency removed from Orchestrator.
12. **Session 61**: HF Space #2 deployed, chatbot active (75% tests), GH Actions on 3 repos (all passing).
13. **Session 62**: **10 HF Spaces deployed** across 2 accounts, round-robin load balancing, mega eval (50 workers), 6 repair agents (3 fixed), incremental saves + dedup + preflight checks.

### Session 58 — INFRASTRUCTURE COMPLETE

**5000 questions prets** : 5 pipelines x 1000 questions (Standard, Graph, Quantitative, Orchestrator, PME Gateway)
**Multi-endpoint architecture** : Per-pipeline routing (N8N_HOST_STANDARD, etc.), per-pipeline API keys, per-pipeline batch sizes
**GitHub Actions** : 5-pipeline matrix configuree (eval-1000q.yml), 15 secrets
**Dashboard live** : Pushed to rag-dashboard (Vercel auto-deploy)
**Scaling doc** : `technicals/project/scaling-bottlenecks.md` — plan x2 a x100

**BLOCKERS** : 0% accuracy Phase 2 sur les 5 pipelines (questions ≠ donnees indexees + bugs workflow specifiques)

### Scaling — Comment accelerer (resume)

| Niveau | Questions/heure | Cout | Action requise |
|--------|----------------|------|----------------|
| Actuel | ~30 | $0 | - |
| **x2** | ~120 | **$0** | 2eme HF Space (Alexis: 10 min) |
| **x5** | ~600 | **$0** | Codespace Docker + GH Actions matrix |
| **x10** | ~6,000 | ~$50/mois | OpenRouter Pro + n8n multi-worker |
| **x20** | ~12,000 | ~$100/mois | VPS Hetzner (3 workers) + GPU HF Space |
| **x100** | ~120,000 | ~$500/mois | K8s cluster + self-hosted LLM |

**Doc complet** : `technicals/project/scaling-bottlenecks.md`

### Session 62 Achievements

#### 1. Infrastructure Scale-Up (10 HF Spaces deployed)
- **Script created**: `scripts/scale-hf-spaces.py` — automated deployment of multiple HF Spaces
- **Script created**: `scripts/activate-all-spaces.py` — bulk activation across all Spaces
- **Round-robin load balancing** — 50 concurrent workers across 10 Spaces
- **Account distribution** — LBJLincoln (5 Spaces), LBJLincoln26 (5 Spaces)
- **All verified** — HTTP 200 on Standard pipeline for all 10 Spaces

#### 2. Eval System Improvements
- **Incremental saves** — auto-save every 5 minutes, no data loss on crashes
- **Signal handler** — graceful shutdown on Ctrl+C, final save before exit
- **Preflight checks** — verify all HF Spaces reachable before starting
- **Deduplication** — skip already-tested questions from previous runs
- **Multi-host support** — N8N_ALL_HOSTS env var for round-robin

#### 3. Workflow Repair Agents (6 launched, 3 completed)
| Workflow | Status | Fix Applied |
|----------|--------|-------------|
| **Status Dashboard API** | ✅ FIXED | Corrected webhook path, committed to repo |
| **Enrichissement V4.0** | ✅ FIXED | Redis nodes removed (9 total), 29 nodes active |
| **Action Executor** | ✅ FIXED | Simplified to 2-node workflow, deployed |
| WhatsApp Bridge | 🔄 Active | Telegram disabled (no credentials), WhatsApp only |
| Ingestion V4.0 | 🔄 In Progress | Removing Redis lock nodes |
| Multi-Canal Gateway | 🔄 In Progress | Fixing node configuration |

#### 4. Project Chatbot LIVE
- **Deployed on all 4 Vercel sites** — ETI, PME connectors, PME use cases, Dashboard
- **Test results** — 9/12 pass (75%), 2.3s avg response time
- **Dataset created** — 1000 questions (984q generic, split ETI/PME/Individual categories)
- **Webhook** — /webhook/project-chatbot on HF Space #1
- **Remaining issue** — CORS not configured for Vercel sites (pending)

### Next Steps (priority order)

#### PRIORITY #1 — Monitor Phase 2 Mega Eval (est. 35-40h)
- **Current**: 74/3950 tested (1.9% complete), PID 54740 running
- **Expected completion**: ~2026-02-27 00:00 UTC
- **Auto-save**: Every 5 minutes to `logs/phase2-results-session62-10space.json`
- **Actions**: Monitor logs, restart if crashed, analyze results when complete

#### PRIORITY #2 — Fix Remaining Workflows (3 in progress)
1. **Ingestion V4.0** — Remove Redis lock nodes (same as Enrichissement fix)
2. **Multi-Canal Gateway** — Fix node configuration errors
3. **Chatbot CORS** — Add CORS headers for Vercel sites

#### PRIORITY #3 — HF Space #2 Full Deployment
- Fix Quantitative credentials (HTTP 500)
- Replace Orchestrator sub-workflow nodes with HTTP calls to Space #1
- Verify all 14 workflows active on Space #2

#### PRIORITY #4 — Data Ingestion Complete
- Build 500-filetype ingestion scripts (currently 11 types)
- Test Ingestion V4.0 after Redis removal
- Document real capabilities vs. documentation claims

### Infrastructure Summary (Session 62)

**10 HF Spaces deployed** — all RUNNING, verified HTTP 200
```
Account LBJLincoln:    Spaces 1, 3, 5, 7, 9
Account LBJLincoln26:  Spaces 2, 4, 6, 8, 10
Each: 16GB RAM, n8n 2.8.4, 14 workflows (11 active, 3 in repair)
```

**7 OpenRouter API keys** — per-pipeline rotation across 3 accounts
- OPENROUTER_KEY_STANDARD, GRAPH, QUANTITATIVE, ORCHESTRATOR (primary 4)
- OPENROUTER_API_KEY, KEY_2, KEY_3 (fallback rotation)

**4 Vercel sites** — all live, chatbot deployed on all
- nomos-ai-pied.vercel.app (ETI)
- nomos-pme-connectors-alexis-morets-projects.vercel.app
- nomos-pme-usecases-alexis-morets-projects.vercel.app
- nomos-dashboard-alexis-morets-projects.vercel.app

**3 GitHub Actions** — all passing
- rag-pme-connectors: Deploy Website to Vercel
- rag-data-ingestion: CI - Data Ingestion
- rag-tests: CI - RAG Tests

### Audit honnete des repos (Session 59b)

**rag-pme-connectors** : SHOWCASE SITE ONLY — 15 connecteurs = landing page (zero code integration, zero OAuth, zero SDK). 1 seul chatbot fonctionnel (proxy Orchestrator). A CONSTRUIRE ou RECLASSIFIER.

**rag-data-ingestion** : 40% REEL / 60% FICTION — ingestion.json = vrai code (30 noeuds) mais jamais teste. enrichment.json = casse (URLs placeholder — FIXED Session 59b). "500 file types" = inexistant (11 types reels). 4 scripts download FONCTIONNELS. Docker FONCTIONNEL.

---

## SESSION 62 SUMMARY — 10-SPACE MEGA DEPLOYMENT

### Infrastructure Deployed
- **10 HF Spaces** — all RUNNING across 2 accounts (LBJLincoln: 1,3,5,7,9 / LBJLincoln26: 2,4,6,8,10)
- **Round-robin load balancing** — N8N_ALL_HOSTS env var, 50 concurrent workers
- **Scripts created** — scale-hf-spaces.py, activate-all-spaces.py
- **All verified** — HTTP 200 on Standard pipeline for all 10 Spaces

### Eval System Improvements
- **Incremental saves** — auto-save every 5 minutes (no data loss)
- **Signal handler** — graceful shutdown on Ctrl+C
- **Preflight checks** — verify all HF Spaces reachable before eval
- **Deduplication** — skip already-tested questions
- **Progress**: 74/3950 tested (1.9%), early accuracy: Std 75%, Graph 20%, Quant 22%, Orch 81%

### Workflow Repairs
- ✅ **Status Dashboard API** — webhook path corrected
- ✅ **Enrichissement V4.0** — Redis removed (9 nodes), 29 active nodes
- ✅ **Action Executor** — simplified to 2-node workflow
- 🔄 **WhatsApp Bridge** — active (Telegram disabled, no creds)
- 🔄 **Ingestion V4.0** — Redis removal in progress
- 🔄 **Multi-Canal Gateway** — node config fixes in progress

### Chatbot Deployed
- **Live on all 4 Vercel sites** — ETI, PME Connectors, PME Use Cases, Dashboard
- **Test results** — 9/12 pass (75%), 2.3s avg response
- **Dataset** — 984q generic test set created
- **Remaining** — CORS config for Vercel sites

---

## 13. GLOSSAIRE

| Terme | Signification |
|-------|---------------|
| **RAG** | Retrieval-Augmented Generation — generer des reponses en cherchant d'abord dans une base de donnees |
| **Pipeline** | Enchainement d'etapes pour traiter une question (intent → search → LLM → response) |
| **Webhook** | URL HTTP qui recoit les questions (POST) et renvoie les reponses |
| **n8n** | Outil no-code pour construire des workflows (les pipelines RAG sont des workflows n8n) |
| **Pinecone** | Base de donnees vectorielle (cherche par similarite mathematique) |
| **Neo4j** | Base de donnees graphe (cherche par entites et relations) |
| **Supabase** | Base de donnees SQL (cherche par requetes structurees) |
| **OpenRouter** | Passerelle vers des LLM gratuits (Llama 70B, Gemma 27B) |
| **LLM** | Large Language Model — intelligence artificielle qui genere du texte |
| **Embedding** | Representation numerique d'un texte (vecteur de 1024 nombres) |
| **Jina** | Service qui transforme du texte en embeddings (gratuit, 1M tokens/mois) |
| **HyDE** | Hypothetical Document Embedding — technique pour ameliorer la recherche |
| **Reranking** | Trier les resultats par pertinence apres la recherche initiale |
| **MCP** | Model Context Protocol — permet a Claude Code de parler directement aux services |
| **HF Space** | Machine gratuite sur HuggingFace (16 GB RAM) qui fait tourner n8n |
| **Codespace** | Machine virtuelle ephemere GitHub (8 GB RAM, 60h/mois gratuit) |
| **Vercel** | Service de deploiement automatique pour les sites web (gratuit) |
| **Task Runner** | Composant n8n qui execute les noeuds Code dans un processus separe |
| **Template SQL** | SQL pre-calcule pour des questions connues (bypass le LLM) |

---

*Ce document est maintenu dans `mon-ipad/docs/executive-summary.md`.*
*Mis a jour obligatoirement a chaque session par l'agent Claude Code.*
