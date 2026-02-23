# EXECUTIVE SUMMARY — Nomos AI Multi-RAG Orchestrator

> Last updated: 2026-02-23T23:30:00+01:00
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
- **Phase 2** (1,000q par pipeline) : **EN COURS** — Graph DONE (500/500, 78%), Quant DONE (500/500, 92%), Standard partial (579/1000, ~36%), Orchestrator BROKEN (57/1000, 0%)
- **Bloqueur critique RESOLU** : Root cause identifiee (session 51) — Broken n8n expression syntax `={{.VAR}}` au lieu de `={{$env.VAR}}` dans Standard + Graph workflow JSONs causait tous les appels API (OpenRouter, Pinecone, Jina) a envoyer `Bearer null`. Fix applique (17 instances corrigees), HF Space v5.4 deploiement en cours.
- **PME** : 3 workflows importes (multi-canal-gateway, action-executor, whatsapp-telegram-bridge) mais PAS actives (404).
- **Data ingestion** : Demarree — 3/5 datasets HuggingFace telecharges (669MB).

### Chiffres cles
| Metrique | Valeur |
|----------|--------|
| Questions testees a ce jour | **1,520+** (Phase 1 + Phase 2) |
| Precision Phase 1 (baseline) | 83.9% (PASSED) |
| Precision Phase 2 (partiel) | Graph 78%, Quant 92%, Std ~36%, Orch 0% |
| Vecteurs dans Pinecone | 22,070 |
| Entites dans Neo4j | 19,788 |
| Lignes dans Supabase | ~17,600 |
| Datasets telecharges | 7,609 sectoriels + 669MB HuggingFace |
| Commits depuis le debut | 200+ |
| Sessions Claude Code | **51** |
| Sites web live | **4** (ETI + PME connectors + PME use cases + Dashboard) |

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
    HF SPACE                          BASES DE DONNEES
    n8n (16GB RAM)               Pinecone + Neo4j + Supabase
    9+3 PME workflows                    |
    ALL 404 (activation broken)          |
    Execution layer                      |
         |                                |
         +--------------------------------+
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

### HF Space (execution — 16 GB RAM, gratuit)
| Element | Detail |
|---------|--------|
| **URL** | https://lbjlincoln-nomos-rag-engine.hf.space |
| **RAM** | 16 GB (cpu-basic) |
| **n8n** | Version 2.8.4 (pinned) |
| **DB interne** | Supabase PostgreSQL + Redis (queue mode: 1 main + 2 workers) |
| **Usage** | Execution des pipelines RAG pour les tests |
| **Status** | **v5.4 deploying** — Root cause fix: broken env var syntax (={{.VAR}} → ={{$env.VAR}}) in Standard + Graph JSONs caused all API calls to fail. 17 instances corrected. |
| **Workflows** | 9 RAG + 3 PME importes. Standard/Graph were broken due to syntax issue (fixed v5.4). Quantitative works. |

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

### Phase 2 — EN COURS (22 fevrier 2026, sessions 37-40)
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | ~36% | **STOPPED** — HF Space 404 |
| Graph | **500** | 500 | **78.0%** | **COMPLETE** |
| Quantitative | **500** | 500 | **92.0%** | **COMPLETE** |
| Orchestrator | 57 | 1000 | 0% | **BROKEN** — 404/empty on every question |
| PME Gateway | 0 | — | — | NOT ACTIVATED (404 after rebuild) |

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

### Sessions 42-51 — PROGRESS (what was done)
1. **Session 42**: VM n8n REMOVED (freed ~270MB RAM). VM is pilotage-only now. Anti-VM guards added to all eval scripts.
2. **Session 43**: HF Space rebuilt with queue mode (3 workers), Supabase PostgreSQL, 7 OpenRouter keys.
3. **Sessions 44-45**: entrypoint.sh v2-v3.1 attempts. Credential stripping, versionId fixes, CLI import debugging.
4. **Sessions 46-47**: PATCH activation instead of POST, sqlite3 direct activation attempts. Session 46 prompt optimization.
5. **Session 48**: entrypoint v4.0 — direct sqlite3 activation (bypasses n8n publish system), credential leak fixes, auto-generate missing IDs.
6. **Session 49**: Deployed v5.2 with 2-pass activation, fixed httpHeaderAuth type mapping, removed duplicate quantitative workflow.
7. **Session 50**: Deployed v5.3 with per-pipeline OpenRouter keys (6 credentials across 3 accounts, 7 env vars for key rotation).
8. **Session 51**: ROOT CAUSE FOUND — broken env var syntax `={{.VAR}}` instead of `={{$env.VAR}}` in workflow JSONs. Fixed 17 instances, deploying v5.4.
9. **User ideas captured** (5 total): New chatbot repo, ingestion test workflow, sub-agents as restrictors, CLAUDE.md cleanup, visible 8-10 step plan.

### Next sessions — PRIORITIES (ordre)
1. **VERIFY HF SPACE v5.4** — Env var syntax fix deployed. Test all 4 pipelines (Standard, Graph, Quant, Orch) confirm they return valid responses, not empty/404.
2. **RELAUNCH STANDARD** — batch-size 5, on fixed HF Space. Complete remaining 421/1000 questions.
3. **FIX ORCHESTRATOR** — Returns 0% on Phase 2. Debug intent classifier + sub-pipeline routing.
4. **ACTIVATE PME WORKFLOWS** — Configure Google API key as credential, test gateway webhook.
5. **USER IDEAS** — Implement 5 user ideas captured in session-state.md (chatbot repo, ingestion test, sub-agent restrictors, CLAUDE.md cleanup, visible plan).
6. **Complete data-ingestion** — musique + finqa downloads, start actual ingestion pipeline.

### Phase 2 completion targets
- Graph : DONE (500/500)
- Quantitative : DONE (500/500)
- Standard : 421 questions remaining (need HF Space fix first)
- Orchestrator : 943 questions remaining (need workflow fix first)

### Phase 2 → Phase 3
- Phase 2 completion : ~2-3 sessions if HF Space fixed
- Phase 3 : ~10,000 questions → objectifs encore relaxes
- Phase 4 : ~100K questions (infrastructure payante requise)
- Phase 5 : 1M+ questions (production)

### Strategie multi-model
- **Opus 4.6** : Cerveau — analyse, decisions, pilotage (modele principal)
- **Sonnet 4.5** : Bras — recherches web, batch commands (delegue quand pertinent)
- **Haiku 4.5** : Sprint — exploration codebase rapide (delegue pour recherches simples)
- Opus decide QUAND deleguer. Jamais l'inverse.

### Principes de priorisation (Rules 36-37)
- **Rule 36 — Cross-pipeline bottleneck** : Quel fix debloque le PLUS de pipelines ? Toujours prioriser les fixes a impact transversal.
- **Rule 37 — Low-hanging fruit** : A impact egal, commencer par le quick-win. Ne jamais s'enliser dans un fix complexe quand des quick-wins sont disponibles.

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
