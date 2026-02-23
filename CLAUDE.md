# Multi-RAG Orchestrator — Tour de Contrôle Centrale

> Last updated: 2026-02-23T16:30:00+01:00

> **CE REPO (`mon-ipad`) EST LA TOUR DE CONTRÔLE.**
> VM Google Cloud permanente · Claude Code via Termius · Pilote 6 repos satellites
> **MODÈLE PRINCIPAL : `claude-opus-4-6` (abonnement Max) — Analyse, decisions, pilotage.**
> **DELEGATION : Sonnet 4.5 (execution) + Haiku 4.5 (exploration) via Task tool — UNIQUEMENT quand Opus le juge pertinent.**
> **Lire cette section EN PREMIER à chaque session.**

---

## CARTE DES INSTANCES ACTIVES

### Instance permanente — VM Google Cloud
| Composant | Adresse | État |
|-----------|---------|------|
| VM SSH | 34.136.180.66 | Permanent |
| **n8n VM** | — | **REMOVED** (2026-02-23, freed ~270MB RAM) |
| Claude Code | Termius terminal | Ce repo — **pilotage UNIQUEMENT** |

**n8n REMOVED from VM (Session 42)**: Docker containers (n8n + Redis + PostgreSQL) stopped and removed. All eval scripts now default to HF Space. Guard blocks prevent accidental use of VM localhost for evals. VM has ~400MB+ RAM available now.

### HF Space — n8n distant (16 GB RAM, execution)
| Composant | Adresse | État |
|-----------|---------|------|
| **n8n HF Space** | https://lbjlincoln-nomos-rag-engine.hf.space | **ALL WEBHOOKS 404** — entrypoint.sh activation broken after rebuild (Session 39) |
| n8n version | 2.8.3 (latest) | SQLite + Redis |
| Credentials | 12/12 importes | postgres x4, redis, neo4j, pinecone x2, openrouter x4 |
| Workflows | 9+3 PME importes | **ALL 404** — rebuild wiped activations. Needs entrypoint.sh fix with retry + verify |
| Keep-alive | Cron VM */30 min | Empêche HF sleep |
| REST API | **BROKEN** (FIX-15 : proxy HF strip POST body pour /api/) | Webhooks **ALSO BROKEN** (404) |

**CRITICAL (Session 39)** : HF Space rebuild (triggered by PME workflow push) wiped n8n database. ALL workflow activations lost. ALL webhooks return 404. No pipelines can run on HF Space until entrypoint.sh is fixed with retry logic + activation verification.

**DECISION SESSION 42** : VM = pilotage UNIQUEMENT. n8n REMOVED from VM. All n8n workloads run on HF Space (16GB RAM) or Codespaces (8GB). Eval scripts have hard guards blocking localhost/VM usage.

**Principe : VM = pilotage ONLY (zero n8n). Evals → HF Space (16GB) ou Codespaces (8GB).**
VM RAM ~400MB+ disponible maintenant (was ~100MB with n8n). Guard anti-VM dans tous les scripts eval.

**MCP Servers** : Empreinte mémoire negligeable (~6MB total). neo4j 2.5MB, pinecone 1.4MB, huggingface 0.8MB, jina 0.7MB, cohere 0.6MB. PAS un problème RAM.

### Déploiements Vercel (production live — tous HTTP 200)
| Site | URL | Repo GitHub | Région | État |
|------|-----|-------------|--------|------|
| Website ETI (4 secteurs) | nomos-ai-pied.vercel.app | rag-website | cdg1 | Live |
| Website PME Connecteurs | nomos-pme-connectors-alexis-morets-projects.vercel.app | rag-pme-connectors | cdg1 | Live |
| Website PME Use Cases | nomos-pme-usecases-alexis-morets-projects.vercel.app | rag-pme-usecases | cdg1 | Live |
| Dashboard tech | nomos-dashboard-alexis-morets-projects.vercel.app | rag-dashboard | iad1 | Live |

### Codespaces GitHub (éphémères — 60h/mois) — CALCUL PRINCIPAL
| Codespace | Repo | État | n8n local |
|-----------|------|------|-----------|
| nomos-rag-tests-5g6g5q9vjjwjf5g4 | rag-tests | Shutdown | 3 workers (docker-compose.yml) |
| nomos-rag-website-jr7q9gr69qqfqp6r | rag-website | Shutdown | Stateless (Vercel) |
| A créer | rag-data-ingestion | Non créé | 2 workers (docker-compose.yml) |

**Résultats toujours pushés vers GitHub AVANT arrêt du Codespace.**

### Pilotage Live des Codespaces (OBLIGATOIRE)

**Problème résolu** : Avant session 23, aucune visibilité en temps réel sur les runs Codespace depuis la VM. Maintenant, le système de pilotage offre :

| Capacité | Commande VM | Mécanisme |
|----------|-------------|-----------|
| **Lancer un run** | `scripts/codespace-control.sh launch <cs> [args]` | `gh codespace ssh` + nohup |
| **Voir la progression** | `scripts/codespace-control.sh status <cs>` | Lit `/tmp/eval-progress.json` via SSH |
| **Stream logs live** | `scripts/codespace-control.sh stream <cs>` | `tail -f` via SSH |
| **Arrêter un run** | `scripts/codespace-control.sh stop <cs>` | `kill PID` via SSH |
| **Récupérer résultats** | `scripts/codespace-control.sh results <cs>` | Copie JSON via SSH |
| **Monitoring continu** | `scripts/codespace-control.sh monitor 30` | Boucle auto-refresh |

#### Architecture du pilotage
```
VM (mon-ipad) ────── gh codespace ssh ──────> Codespace (rag-tests)
   │                                               │
   ├─ codespace-control.sh                         ├─ /tmp/eval-progress.json
   │   ├─ launch → nohup python3 eval/...          │    (ProgressReporter écrit ici)
   │   ├─ status → cat progress.json               ├─ /tmp/eval-run.pid
   │   ├─ stream → tail -f log                     │    (PID du process eval)
   │   ├─ stop   → kill $(cat pid)                 ├─ /tmp/eval-run.log
   │   └─ monitor → boucle auto-refresh            │    (stdout/stderr du run)
   │                                               │
   └─ Webhook optionnel ←── POST ──────────────────┘
      (n8n /webhook/codespace-progress)         (eval script POST progress)
```

#### Callback de progression (eval/progress_callback.py)
Les scripts eval écrivent leur progression dans `/tmp/eval-progress.json` après chaque question.
Ce fichier contient : status, tested/total, accuracy par pipeline, ETA, PID.
La VM lit ce fichier via `gh codespace ssh -- cat /tmp/eval-progress.json`.

#### Commandes rapides
```bash
# Lister les Codespaces actifs
scripts/codespace-control.sh list

# Lancer un test sur rag-tests (50 questions, label Phase1)
scripts/codespace-control.sh launch nomos-rag-tests-5g6g5q9vjjwjf5g4 --max 50 --label "Phase1-fix"

# Voir la progression en temps réel
scripts/codespace-control.sh stream nomos-rag-tests-5g6g5q9vjjwjf5g4

# STOP d'urgence
scripts/codespace-control.sh stop nomos-rag-tests-5g6g5q9vjjwjf5g4

# Dashboard monitoring auto-refresh toutes les 30s
scripts/codespace-control.sh monitor 30
```

### Bases de données cloud
| Service | Contenu | Utilisation |
|---------|---------|------------|
| Pinecone sota-rag-jina-1024 | 10,411 vecteurs | Standard + Graph RAG |
| Pinecone sota-rag-phase2-graph | 1,296 vecteurs | Graph enrichi |
| Neo4j Aura | 19,788 nodes / 76,717 rels | Graph RAG |
| Supabase | 40 tables / ~17K lignes | Quantitatif + benchmarks |

---

## ÉTAT ACTUEL — PHASE 2 EN COURS (1,000q par pipeline)

### Phase 1 — PASSED (20 fév 2026, session 30)
| Pipeline | Accuracy (Phase 1) | Target | Status |
|----------|-------------------|--------|--------|
| Standard | 85.5% (47/55) | >= 85% | PASS |
| Graph | 78.0% (39/50) | >= 70% | PASS |
| Quantitative | 92.0% (46/50) | >= 85% | PASS |
| Orchestrator | 80.0% (40/50) | >= 70% | PASS |
| **Overall** | **83.9%** | >= 75% | **PASS** |

### Phase 2 — EN COURS (mise à jour : 22 fév 2026, session 39-40)
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | **~36%** | STOPPED — HF Space ALL 404 after rebuild |
| Graph | **500** | 500 | **78.0%** | COMPLETE |
| Quantitative | **500** | 500 | **92.0%** | COMPLETE |
| Orchestrator | 57 | 1000 | **0%** | BROKEN — returns empty/404 on every question |
| PME Gateway | 0 | — | — | NOT ACTIVATED — HF rebuild didn't activate PME workflows |

### CRITICAL BLOCKER (Session 39-40)
**HF Space ALL WEBHOOKS 404** — entrypoint.sh activation broken after rebuild triggered by PME workflow push. NO pipelines can run until this is fixed. This is the #1 cross-pipeline bottleneck (Rule 36): fixing it unblocks Standard + Orchestrator + PME = 3+ pipelines.

### Plan des phases (A → D) — Vue d'ensemble
| Phase | Description | Repo exécutant | Statut |
|-------|-------------|---------------|--------|
| **A.Phase1** | 200q baseline — 4 pipelines | rag-tests | ✅ PASSED (20 fév) |
| **A.Phase2** | 1 000q HuggingFace | rag-tests | **EN COURS** — Graph+Quant DONE, Standard+Orch BLOCKED |
| **A.Phase3** | ~10K q | rag-tests | Prérequis : Phase2 |
| **B. SOTA** | Recherche académique 2026 | mon-ipad | FAIT (session 13) |
| **C. Ingestion** | 14 benchmarks + secteurs | rag-data-ingestion | **STARTED** — 3/5 datasets downloaded (669MB) |
| **D. Website** | Site 4 secteurs + dashboard + PME | rag-website | EN COURS (MVP live, PME sites deployed) |

### Métriques avancées (non mesurées — à implémenter Phase 2+)
- Faithfulness >= 95% | Context Recall >= 85% | Hallucination <= 2% | Latency <= 2.5s

---

## ÉTAT PAR REPO SATELLITE

### `rag-tests` — Tests des 4 pipelines
| | |
|-|-|
| **Dernier commit** | Phase 2 runs — 22 fév 2026 |
| **État** | Phase 2 partial: Graph 500/500 DONE, Quant 500/500 DONE, Std 579/1000 STOPPED, Orch 57/1000 BROKEN |
| **Codespace** | Shutdown (à redémarrer — `docker compose up -d` au démarrage) |
| **Prochain objectif** | Fix HF Space → relaunch Standard + Orchestrator Phase 2 |
| **Commandes clés** | `docker compose up -d && python3 eval/iterative-eval.py --label "Phase2-relaunch"` |
| **Données** | 1520+ questions testées (Phase 1 + Phase 2), 50+ itérations |

### `rag-website` — Site business 4 secteurs
| | |
|-|-|
| **Dernier commit** | c5a9ec70 — 17 fév 2026 (fix SSE live feed) |
| **État** | Deployed sur Vercel (nomos-ai-pied.vercel.app) |
| **Codespace** | Shutdown |
| **Prochain objectif** | Intégrer vrais docs sectoriels (BTP/Industrie/Finance/Juridique) |
| **Commandes clés** | `git push rag-website main` → Vercel auto-deploy |
| **Dashboard live** | /dashboard → 932q feed SSE OK |

### `rag-data-ingestion` — Ingestion + enrichissement BDD
| | |
|-|-|
| **Dernier commit** | 9f5a53dd — 17 fév 2026 |
| **État** | Workflows Ingestion V3.1 + Enrichissement V3.1 |
| **Codespace** | Non créé (créer pour ingestion massive) |
| **Prochain objectif** | Télécharger 14 benchmarks (~4 GB) + ingérer secteurs (~1.4 GB) |
| **Commandes clés** | `gh codespace create --repo LBJLincoln/rag-data-ingestion` |
| **Volume** | ~5.4 GB total à ingérer → Pinecone + Neo4j + Supabase |

### `rag-dashboard` — Dashboard statique
| | |
|-|-|
| **Dernier commit** | 9f5a53dd — 17 fév 2026 |
| **État** | Statique, pas de Codespace nécessaire |
| **Prochain objectif** | Vérifier déploiement GitHub Pages / Vercel |
| **Données live** | nomos-dashboard.vercel.app (nomos-status webhook VM) |

---

## PROCESS SESSION — BOUCLE STANDARD

### Démarrage de session (TOUJOURS)
```bash
cat directives/session-state.md  # Mémoire de session
cat docs/status.json             # Métriques live
cat directives/status.md         # Résumé session précédente
```

### Fix pipeline (boucle d'itération)
```
1. DIAGNOSTIQUER  → node-analyzer.py + analyze_n8n_executions.py
2. FIXER          → API REST n8n (1 noeud à la fois)
3. TESTER         → quick-test.py --questions 5 minimum
4. VALIDER        → quick-test.py --questions 10 (5/5 minimum)
5. SYNC           → n8n/sync.py
6. COMMIT+PUSH    → origin + repos concernés
```

### Lancement parallèle (3 Codespaces + VM)
```bash
# VM (pilotage)
# → surveiller MCP, commit résultats, piloter les agents

# Codespace 1 : rag-data-ingestion (n8n propre, 2 workers)
gh codespace create --repo LBJLincoln/rag-data-ingestion --machine basicLinux32gb
gh codespace ssh --codespace <name>
# → télécharger datasets HuggingFace → ingérer → Pinecone+Neo4j+Supabase

# Codespace 2 : rag-tests (n8n LOCAL — docker-compose, 3 workers)
gh codespace start --codespace nomos-rag-tests-5g6g5q9vjjwjf5g4
gh codespace ssh --codespace nomos-rag-tests-5g6g5q9vjjwjf5g4
# → docker compose up -d   (n8n-main + 3 workers + redis + postgres)
# → source .env.local && python3 eval/iterative-eval.py --label "Phase1-200q"

# Codespace 3 : rag-website (Vercel stateless)
gh codespace start --codespace nomos-rag-website-jr7q9gr69qqfqp6r
# → npm run dev → intégrer docs sectoriels
```

---

## REGLES CRITIQUES (résumé)

| # | Règle | Conséquence si violée |
|---|-------|----------------------|
| 1 | Consulter **`technicals/debug/fixes-library.md`** avant tout debug | Re-débugger un bug déjà résolu |
| 2 | Tests SEQUENTIELS (jamais parallèles) | 503 n8n |
| 3 | source .env.local avant scripts Python | Variables manquantes |
| 4 | ZERO credentials dans git | Leak API keys |
| 5 | Commit + push après chaque fix | Travail perdu |
| 6 | 5/5 minimum avant sync n8n | Régression |
| 7 | MAJ session-state.md après milestone | Agent perdu au compactage |
| 8 | MAJ **`technicals/debug/fixes-library.md`** après chaque fix réussi | Bibliothèque incomplète |
| 9 | git config user.email = alexis.moret6@outlook.fr | Vercel rejette commits |
| 10 | 1 fix par itération (pas plusieurs noeuds) | Impossible de débugger |
| **11** | **CONSULTER `technicals/debug/knowledge-base.md` Section 0 AVANT tout test webhook** | **Mauvais webhook path, mauvais field name, fausse itération** |

---

## CE QUE TU ES ET CE QUE TU FAIS PRECISEMENT

### STRATÉGIE MULTI-MODEL — Opus 4.6 + Delegation Sonnet/Haiku

**Opus 4.6 = modèle PRINCIPAL (analyse, decisions, pilotage).**
**Sonnet 4.5 = délégué pour EXECUTION (recherches web, batch commands, generation).**
**Haiku 4.5 = délégué pour TACHES RAPIDES (exploration codebase, verifications).**

```bash
# Au démarrage de chaque session / Codespace :
bash scripts/setup-claude-opus.sh
# OU lancer directement :
claude --model claude-opus-4-6
```

Le fichier `.claude/settings.json` contient `"model": "claude-opus-4-6"`.
Tous les repos satellites doivent faire de même (voir `directives/repos/*.md`).

**Quand déléguer** (Opus décide, jamais l'inverse) :
| Tache | Modele | Mecanisme |
|-------|--------|-----------|
| Recherche web / internet | Sonnet 4.5 | `Task(model: "sonnet", subagent_type: "general-purpose")` |
| Exploration codebase | Haiku 4.5 | `Task(model: "haiku", subagent_type: "Explore")` |
| Commandes batch | Sonnet 4.5 | `Task(model: "sonnet", subagent_type: "Bash")` |
| Generation repetitive | Sonnet 4.5 | `Task(model: "sonnet", subagent_type: "general-purpose")` |

**JAMAIS déléguer** : analyse workflows, decisions debug, redaction directives, evaluation résultats, communication utilisateur.

---

Tu es Claude Code (`claude-opus-4-6`) exécuté dans **Termius** connecté à la **VM Google Cloud** (`34.136.180.66`). Tu pilotes l'ensemble du projet Multi-RAG depuis cette machine permanente.

### Tes actions concrètes
| Action | Outil | Détail |
|--------|-------|--------|
| Lire/écrire les fichiers de ce repo | Outils natifs Claude Code | `/home/termius/mon-ipad/` |
| Exécuter des scripts Python | `Bash` | `source .env.local && python3 eval/...` |
| Modifier des workflows n8n | MCP `n8n` + REST API | HF Space (VM n8n removed) |
| Interroger Pinecone | MCP `pinecone` | API HTTPS serverless |
| Interroger Neo4j | MCP `neo4j` | HTTPS API graph DB |
| Interroger Supabase | MCP `supabase` | SQL via pooler |
| Générer des embeddings | MCP `jina-embeddings` | API Jina |
| Reranking | MCP `cohere` | API Cohere (limité) |
| Chercher datasets/modèles | MCP `huggingface` | Hub API |
| Gérer GitHub | `Bash` + `gh` CLI | 5 remotes configurés |
| Contrôler les Codespaces | `gh` CLI + `codespace-control.sh` | Create/stop/ssh/monitor live |
| Committer et pousser | `Bash` git | Vers les 5 remotes |

### Ce à quoi tu AS accès
- **Filesystem local complet** : `/home/termius/mon-ipad/` (et `/home/termius/`)
- **n8n HF Space** : n8n on HF Space (VM n8n removed), MCP via HF Space endpoint
- **Bases de données cloud** : Pinecone, Neo4j Aura, Supabase (via MCP + env vars)
- **APIs externes** : OpenRouter (LLM), Jina (embeddings), Cohere (reranking), HuggingFace
- **GitHub** : 5 repos via HTTPS + token (ghp_... dans remotes)
- **Docker** : `docker ps`, `docker logs` (no containers running — n8n removed from VM)
- **gh CLI** : Authentifié en LBJLincoln, scopes complets (codespace, repo, workflow)

### Ce à quoi tu N'AS PAS accès directement
- Les filesystems des Codespaces (sauf via SSH tunnel)
- L'interface web n8n (seulement API + MCP)
- Les logs en temps réel des Codespaces sans tunnel actif
- Vercel (seulement via GitHub push déclenche le déploiement)

---

## INFRASTRUCTURE RÉELLE ET PRÉCISE

### VM Google Cloud (permanent — siège de contrôle)
```
Machine    : e2-micro (Google Cloud, us-central1)
IP         : 34.136.180.66
OS         : Linux Debian 11 (Bullseye)
CPU        : 1 vCPU Intel Xeon @ 2.20GHz
RAM        : 969 MB total | ~556 MB utilisé | ~413 MB disponible (n8n removed)
Swap       : 2047 MB total | ~1084 MB utilisé (VM souvent en swap !)
Disque     : 30 GB total | 12 GB utilisé | 17 GB libres (43% plein)
Uptime     : Permanent (pas de coupure planifiée)
```

**RAM améliorée (session 42)** : n8n removed → ~413MB disponible (was ~104MB). Claude Code seul consomme ~297MB. VM ne swap plus en utilisation normale.

### Containers Docker (sur la VM) — REMOVED
```
NO CONTAINERS RUNNING — n8n removed from VM 2026-02-23 (Session 42)
All n8n workloads moved to HF Space / Codespaces / GitHub Actions CI
```
- **n8n**: REMOVED — was consuming ~270MB RAM, causing eval fallback issues
- **Redis**: REMOVED — was n8n dependency
- **PostgreSQL**: REMOVED — was n8n dependency
- Docker compose file preserved at `/home/termius/n8n/docker-compose.yml` for reference

### n8n — Workflows actifs (9 apres audit session 18, cible 16)

#### Pipelines RAG (4)
| Workflow | ID Docker | Status |
|----------|-----------|--------|
| Standard RAG V3.4 | `TmgyRP20N4JFd9CB` | ON |
| Graph RAG V3.3 | `6257AfT1l4FMC6lY` | ON |
| Quantitative V2.0 | `e465W7V9Q8uK6zJE` | ON |
| Orchestrator V10.1 | `aGsYnJY9nNCaTM82` | ON |

#### Support (5)
| Workflow | ID Docker | Status |
|----------|-----------|--------|
| Dashboard Status API | `KcfzvJD6yydxY9Uk` | ON |
| Benchmark V3.0 | `LKZO1QQY9jvBltP0` | ON |
| Ingestion V3.1 | `15sUKy5lGL4rYW0L` | OFF (prêt) |
| Enrichissement V3.1 | `9V2UTVRbf4OJXPto` | OFF (prêt) |
| Dataset Ingestion | `YaHS9rVb1osRUJpE` | OFF (prêt) |

#### Supprimes (audit session 18)
Feedback V3.1, Monitoring Dashboard, Orchestrator Tester, RAG Batch Tester — raisons dans `technicals/infra/architecture.md`.

#### Cible 16 workflows (3 categories)
| Cat. | Workflows | Activation |
|------|-----------|------------|
| **A: Test-RAG** | 4 pipelines actuels | Actifs maintenant |
| **B: Sector** | 4 pipelines sectoriels | Apres Phase 2 |
| **C: Ingestion** | 2+2 ingestion/enrichment | Partiellement actifs |
→ Details : `technicals/infra/architecture.md`

### Bases de données cloud (état au 2026-02-17)
| BDD | Plan | Contenu | Limite |
|-----|------|---------|--------|
| **Pinecone** (sota-rag-jina-1024) | Free | 10,411 vecteurs, 12 ns, dim 1024 | 100K vecteurs max |
| **Pinecone** (sota-rag-cohere-1024) | Free | 10,411 vecteurs, backup Cohere | 100K vecteurs max |
| **Pinecone** (sota-rag-phase2-graph) | Free | 1,296 vecteurs, 1 ns, e5-large | 100K vecteurs max |
| **Neo4j Aura Free** | Free | 19,788 nodes, 76,717 relations | 200K nodes / 400K rels |
| **Supabase** | Free | 40 tables, ~17,000+ lignes | 500MB storage |

### MCP Servers configurés (`.mcp.json`)
| MCP | Endpoint | Capacités | Limite |
|-----|----------|-----------|--------|
| `n8n` | HF Space | Points to HF Space MCP endpoint (VM n8n removed) | HF proxy issues possible |
| `pinecone` | API HTTPS | Upsert, query, delete vecteurs ; gestion indexes | Free tier |
| `neo4j` | HTTPS API | Cypher queries, lecture/écriture graph | Free (200K nodes) |
| `supabase` | Pooler AWS eu-west-1:6543 | SQL SELECT/INSERT/UPDATE/DELETE | Free (500MB) |
| `jina-embeddings` | API Jina | Génère embeddings 1024-dim + Pinecone CRUD | 1M tokens/mois |
| `cohere` | API Cohere | Reranking (command-r) | Trial épuisé presque |
| `huggingface` | Hub API | Recherche modèles/datasets | Free |

### Services externes (all free tier)
| Service | Usage | Quota restant (approx) |
|---------|-------|----------------------|
| **OpenRouter** | LLM (Llama 70B, Gemma 27B, Trinity) | Free credits ($0 cost) |
| **Jina** | Embeddings-v3 primary | ~1M tokens/mois |
| **Cohere** | Reranker backup | Trial quasi-épuisé |
| **HuggingFace** | Datasets + modèles | Free |
| **GitHub** | 5 repos privés + Codespaces | 60h Codespace/mois |

### Codespaces (éphémères — exécution lourde)
```
Type        : GitHub Codespaces (Free tier)
CPU         : 2 cores
RAM         : 8 GB
Disque      : 32 GB
Limite      : 60h actives/mois (Free) — ÉPHÉMÈRES
Image       : mcr.microsoft.com/devcontainers/universal:2 (Ubuntu)
Inclus      : Python 3.11, Node.js 20, Docker-in-Docker, Claude Code CLI
```
- Tests lourds (500q+) → Codespace `rag-tests`
- Ingestion massive → Codespace `rag-data-ingestion`
- Résultats **toujours pushés vers GitHub avant arrêt**

---

## ARCHITECTURE MULTI-REPO (5 repos)

### Vue d'ensemble
```
┌─────────────────────────────────────────────────────────────────┐
│                 GitHub (LBJLincoln) — TOUS PRIVÉS               │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│  mon-ipad    │  rag-tests   │ rag-website  │ rag-data-ingestion │
│  CONTROLE    │  4 WF RAG    │  site + chat │ 2 WF ingestion     │
│              │              │              │                    │
│              │  + rag-dashboard (live metrics)                  │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬──────────┘
       │              │              │                │
    VM GCloud      Codespaces    Vercel/GH        Codespaces
    (permanent)   (éphémères)    Pages            (éphémères)
    n8n+Redis+PG  SSH tunnel→VM  Statique         n8n+workers+PG+Redis
```

### Rôles précis par repo

#### `mon-ipad` — Tour de contrôle (CE REPO)
- **Qui l'exécute** : Claude Code sur la VM permanente, via Termius
- **Ce qu'il contient** : Directives, scripts eval, configs MCP, n8n sync, CLAUDE.md master
- **Ce qu'il fait** : Piloter les 4 autres repos, lancer tests, fixer workflows n8n, analyser résultats
- **n8n** : Permanent (9 workflows actifs, cible 16 — voir `technicals/infra/architecture.md`)
- **Git remotes** : 5 (origin + 4 satellites)
- **Directive locale** : `/home/termius/mon-ipad/CLAUDE.md` (ce fichier)
- **Directive pour agents satellites** : `directives/repos/*.md` → pushés vers chaque repo

#### `rag-tests` — Tests des 4 pipelines RAG
- **Qui l'exécute** : Agent Claude Code dans Codespace éphémère
- **Ce qu'il contient** : Scripts eval Python, datasets JSON, résultats sessions
- **Ce qu'il fait** : Exécuter les tests (quick-test.py, iterative-eval.py, run-eval-parallel.py)
- **n8n** : AUCUN local — se connecte à la VM via SSH tunnel (port forwarding 5678)
- **Dépendance** : VM doit être up + SSH tunnel actif
- **Volume de tests** : 1-10q sur VM directement, 50-200q sur Codespace, 500q+ sur Codespace
- **Directive** : `CLAUDE.md` dans le repo (poussé depuis `directives/repos/rag-tests.md`)

#### `rag-website` — Site business 4 secteurs
- **Qui l'exécute** : Agent Claude Code dans Codespace éphémère (dev) + Vercel (prod)
- **Ce qu'il contient** : Next.js 14, 4 secteurs (BTP, Industrie, Finance, Juridique), chatbots
- **Ce qu'il fait** : Déployer le site vitrine avec démos RAG intégrées
- **n8n** : Local dans Codespace (docker-compose.yml standalone : n8n + postgres)
- **Déploiement** : Push GitHub → Vercel auto-deploy
- **Directive** : `CLAUDE.md` dans le repo (poussé depuis `directives/repos/rag-website.md`)

#### `rag-dashboard` — Dashboard technique live
- **Qui l'exécute** : Statique — aucun Codespace nécessaire
- **Ce qu'il contient** : HTML/JS statique, lit `status.json` via API n8n (Dashboard Status API)
- **Ce qu'il fait** : Afficher les métriques live (accuracy, pipelines, phase gates) en read-only
- **n8n** : AUCUN — consomme uniquement le webhook `/webhook/nomos-status` de la VM
- **Déploiement** : GitHub Pages ou Vercel (statique)
- **Directive** : `CLAUDE.md` dans le repo (poussé depuis `directives/repos/rag-dashboard.md`)

#### `rag-pme-connectors` — Site PME Connecteurs (15 apps)
- **Qui l'exécute** : Vercel (prod), dev local optionnel
- **Ce qu'il contient** : Next.js 15, 15 connecteurs applications (WhatsApp, Telegram, Gmail, Outlook, Slack, Google Drive, OneDrive, Dropbox, Google Calendar, Notion, Trello, HubSpot, Salesforce, Stripe, QuickBooks), chatbot MacBook-style
- **Ce qu'il fait** : Vitrine PME — intégrations Nomos AI avec 15 apps business, filtrage par catégorie (Communication, Stockage, Productivité, CRM, Finance)
- **Déploiement** : Push GitHub → Vercel auto-deploy
- **Directive** : `directives/repos/rag-pme-connectors.md` (a créer si modifs nécessaires)

#### `rag-pme-usecases` — Site PME Use Cases (200 cas)
- **Qui l'exécute** : Vercel (prod), dev local optionnel
- **Ce qu'il contient** : Next.js 14, catalogue 200 use cases, filtrage par secteur
- **Ce qu'il fait** : Catalogue exhaustif de cas d'usage RAG pour PME
- **Déploiement** : Push GitHub → Vercel auto-deploy (à configurer)
- **Directive** : Aucune (site statique)

#### `rag-data-ingestion` — Ingestion + enrichissement BDD
- **Qui l'exécute** : Agent Claude Code dans Codespace éphémère
- **Ce qu'il contient** : Workflows Ingestion V3.1, Enrichissement V3.1, scripts Python
- **Ce qu'il fait** : Ingérer documents → Pinecone/Neo4j/Supabase, enrichir données
- **n8n** : Local COMPLET (docker-compose : n8n + 2 workers + postgres + redis)
- **Workflow mode** : Queue mode (2 workers pour parallélisation)
- **Directive** : `CLAUDE.md` dans le repo (poussé depuis `directives/repos/rag-data-ingestion.md`)

### Remotes configurés (depuis ce repo)
```bash
origin             → github.com/LBJLincoln/mon-ipad.git
rag-tests          → github.com/LBJLincoln/rag-tests.git
rag-website        → github.com/LBJLincoln/rag-website.git
rag-dashboard      → github.com/LBJLincoln/rag-dashboard.git
rag-data-ingestion → github.com/LBJLincoln/rag-data-ingestion.git
rag-pme-connectors → github.com/LBJLincoln/rag-pme-connectors.git
rag-pme-usecases   → github.com/LBJLincoln/rag-pme-usecases.git
```

---

## PHASE 0 — CONTEXTE PERSISTANT

### 0.1 Résilience aux compactages
1. **Lire `directives/session-state.md`** — Mémoire de travail
2. **Lire `directives/status.md`** — Résumé dernière session
3. **Lire `docs/status.json`** — Métriques live
4. **Lire `technicals/debug/knowledge-base.md`** — **CERVEAU PERSISTANT** (patterns, solutions, LLM, APIs)
5. `cat technicals/debug/fixes-library.md | head -50` — Symptôme connu ?
6. **Consulter `docs/document-index.md`** — **INDEX DE RECHERCHE** (sujet → fichier source)
7. **Lancer Agent 1: Session Log Analyzer** — Sonnet background (Rule 41)
8. **Lancer Agent 2: Repo Health Inspector** — Sonnet background (Rule 42)

**Règle** : Avant chaque action complexe, re-lire `directives/session-state.md`.
**Règle** : Après chaque découverte technique, mettre à jour `technicals/debug/knowledge-base.md` IMMÉDIATEMENT (pas en fin de session).
**Règle** : Quand tu cherches une information, consulte `docs/document-index.md` pour savoir dans quel document la trouver.

### 0.1b Agents de démarrage obligatoires (Session 38+)

**Agent 1 — Session Log Analyzer** (Sonnet 4.5, background)
```
Task(model: "sonnet", subagent_type: "general-purpose", run_in_background: true)
Prompt:
  "Read outputs/session-<N-1>-log.md (last session log).
   Analyze: rule adherence, patterns, bottlenecks, missed improvements.
   Web search for current best practices (RAG 2026, n8n optimization, eval methodology).
   Output: concrete improvements to apply to CLAUDE.md, fixes-library.md,
   knowledge-base.md, team-agentic-process.md.
   Write changes directly. Commit with message 'auto: session analyzer improvements'."
```

**Agent 2 — Repo Health Inspector** (Sonnet 4.5, background)
```
Task(model: "sonnet", subagent_type: "general-purpose", run_in_background: true)
Prompt:
  "Scan the mon-ipad repo structure: check staleness (check-staleness.sh),
   architecture cleanliness, dead files, missing docs.
   Then check all 5 satellite repos via 'gh api repos/LBJLincoln/<repo>':
   - rag-tests: test protocol quality, dataset coverage, eval methodology
   - rag-data-ingestion: ingestion pipeline efficiency, data quality checks
   - rag-pme-connectors: PME workflow coverage, test scenarios
   - rag-dashboard: data freshness, display accuracy
   - rag-website: deployment health, content accuracy
   Output: improvement suggestions per repo.
   Write changes to technicals/project/improvements-roadmap.md.
   Commit with message 'auto: repo health inspection improvements'."
```

**Both agents run in PARALLEL at session start.** They produce improvements that Opus reviews before applying.

### 0.2 Mise à jour session-state.md (OBLIGATOIRE)
```markdown
# Session State — [date]
## Objectif de session : [...]
## Tâches en cours : [...]
## Décisions prises : [...]
## Dernière action : [...]
## Prochaine action : [...]
## Commits : [hash1, hash2, ...]
## Repos impactés : [mon-ipad, rag-tests, ...]
```

### 0.3 Sources de vérité
| Source | Rôle |
|--------|------|
| **VM locale** (`/home/termius/mon-ipad/`) | État live + credentials + contrôle |
| **GitHub** (5 repos privés) | Checkpoints persistants |
| **Codespaces** (éphémères) | Exécution lourde, résultats pushés vers repos |

### 0.4 Protocole Anti-Staleness (OBLIGATOIRE)
1. Tout fichier directive DOIT inclure `Last updated: YYYY-MM-DDTHH:MM:SSZ` en header
2. Au demarrage de session : verifier si un fichier directive a >48h → WARN + mettre a jour
3. `session-state.md` mis a jour APRES chaque milestone (pas juste fin de session)
4. `status.md` mis a jour en DERNIERE action de chaque session
5. Script : `bash scripts/check-staleness.sh` — scanne tous les .md pour dates obsoletes
6. Reference : `technicals/project/team-agentic-process.md` pour le processus formel

---

## PHASE 1 — LIRE

### 1.1 État actuel (TOUJOURS en premier)
```bash
cat directives/session-state.md
cat docs/status.json
cat directives/status.md
bash scripts/check-staleness.sh  # Verifier staleness
```

### 1.2 Comprendre le projet
- `directives/objective.md` — Objectif final, situation actuelle
- `propositions` — Architecture multi-repo, n8n distribué

### 1.3 Comprendre le processus
- `directives/workflow-process.md` — Boucle d'itération
- `directives/n8n-endpoints.md` — Webhooks et API REST

### 1.4 Références techniques
- `technicals/infra/architecture.md` — 4 pipelines + 9 workflows actifs, cible 16 (categories A/B/C)
- `technicals/infra/stack.md` — Stack technique
- `technicals/infra/credentials.md` — Configuration services
- `technicals/infra/env-vars-exhaustive.md` — **33 vars documentees**, matrice workflow x var, log modifications
- `technicals/project/team-agentic-process.md` — Processus team-agentic formel (roles, auto-stop, fixes-library)
- `technicals/project/phases-overview.md` — 5 phases et gates
- `technicals/infra/infrastructure-plan.md` — Plan d'infrastructure distribuee + Docker par repo
- `technicals/data/sector-datasets.md` — 1000+ types de documents par secteur
- `technicals/debug/fixes-library.md` — Bibliotheque des 24+ fixes documentes
- **`technicals/debug/knowledge-base.md`** — **CERVEAU PERSISTANT** — patterns, solutions, LLM, APIs, commandes, schemas. S'enrichit a chaque session.
- **`technicals/project/improvements-roadmap.md`** — **ROADMAP CENTRALISEE** — 50+ ameliorations classees par categorie et priorite. Vision complete du projet.
- `directives/dataset-rationale.md` — Justification des 14 benchmarks
- `directives/repos/` — Directives personnalisées par repo satellite
- `directives/research-methodology.md` — Directive recherche internet/academique SOTA 2026

---

## PHASE 2 — UTILISER

### 2.1 MCP Servers
| MCP | Usage | Status |
|-----|-------|--------|
| `n8n` | Inspecter workflows (HF Space MCP endpoint) | HF proxy issues possible |
| `pinecone` | Vector store (22K+ vecteurs, 3 indexes) | OK |
| `neo4j` | Graph (19K+ nodes) | OK |
| `jina-embeddings` | Embeddings Jina + Pinecone CRUD | OK |
| `supabase` | SQL queries directes | OK |
| `cohere` | Reranking (trial quasi-épuisé) | Limité |
| `huggingface` | Recherche modèles/datasets | OK |

### 2.2 Commandes d'évaluation
```bash
source .env.local  # TOUJOURS avant les scripts Python
python3 eval/quick-test.py --questions 1 --pipeline <cible>
python3 eval/quick-test.py --questions 5 --pipeline <cible>
python3 eval/iterative-eval.py --label "..."
python3 eval/run-eval-parallel.py --reset --label "..."
python3 eval/node-analyzer.py --execution-id <ID>
python3 eval/generate_status.py
python3 eval/phase_gates.py
```

### 2.3 Commandes d'analyse
```bash
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
python3 scripts/analyze_n8n_executions.py --pipeline <cible> --limit 5
```

### 2.4 Commandes push
```bash
# Push mon-ipad (CE repo uniquement)
git push origin main

# Sync CLAUDE.md directives vers les satellites
bash scripts/push-directives.sh

# Sync n8n workflows
python3 n8n/sync.py
```

**IMPORTANT** : Les repos satellites sont SÉPARÉS depuis session 41. Ne JAMAIS
`git push rag-tests main` depuis mon-ipad — ça écraserait le contenu propre du satellite.
Les satellites ont leur propre code. Seuls les CLAUDE.md sont synchés via `push-directives.sh`.

### 2.5 Pousser les directives vers les repos satellites
```bash
# Script dédié — pousse les CLAUDE.md spécifiques vers chaque repo
bash scripts/push-directives.sh
```

### 2.6 Commandes Codespaces (contrôle distant)
```bash
# Lister les Codespaces actifs
gh codespace list

# Créer un Codespace pour un repo
gh codespace create --repo LBJLincoln/rag-tests --machine basicLinux32gb

# Se connecter SSH à un Codespace
gh codespace ssh --codespace <name>

# Arrêter un Codespace
gh codespace stop --codespace <name>

# Supprimer un Codespace
gh codespace delete --codespace <name>
```

### 2.6b Pilotage Live Codespaces (NOUVEAU — session 23)
```bash
# Lancer un run eval depuis la VM
scripts/codespace-control.sh launch <codespace> --max 50 --label "Phase1-fix"

# Voir la progression en temps réel
scripts/codespace-control.sh status <codespace>

# Stream live des logs (Ctrl+C pour arrêter)
scripts/codespace-control.sh stream <codespace>

# STOP d'urgence (kill le process eval)
scripts/codespace-control.sh stop <codespace>

# Récupérer les résultats
scripts/codespace-control.sh results <codespace>

# Dashboard monitoring continu (auto-refresh 30s)
scripts/codespace-control.sh monitor 30
```

### 2.7 SSH tunnel vers VM depuis Codespace
```bash
# Dans le Codespace rag-tests, pour accéder au n8n de la VM :
ssh -L 5678:localhost:5678 <user>@34.136.180.66 -N &
# Puis les scripts rag-tests utilisent localhost:5678 normalement
```

### 2.8 Modification de workflows n8n (CRITIQUE)
```
1. DIAGNOSTIQUER  → node-analyzer.py + analyze_n8n_executions.py
2. FIXER          → API REST n8n (ou MCP n8n)
3. VÉRIFIER       → quick-test.py --questions 5 minimum
4. SYNC           → n8n/sync.py
5. ARCHIVER       → snapshot/validated/
6. COMMIT+PUSH    → origin + repos concernés
```

---

## PHASE 3 — PRODUIRE

### 3.1 Après chaque test
- Logs → `logs/`
- Diagnostics → `logs/diagnostics/`
- Status → `docs/status.json` (auto-généré)

### 3.2 Après chaque fix réussi (5/5 passe)
1. Sync : `python3 n8n/sync.py`
2. Snapshot : `snapshot/current/`
3. Status : `python3 eval/generate_status.py`
4. Session-state : `directives/session-state.md`
5. Fixes library : `technicals/debug/fixes-library.md` — documenter le fix (symptôme, cause, solution)
6. **Commit + push IMMÉDIATEMENT** (origin + repos concernés)

### 3.3 Pushes réguliers (OBLIGATOIRE)
- Après chaque fix réussi
- Après chaque milestone
- **Toutes les 30 minutes** minimum
- Avant opérations risquées
- **Vers TOUS les repos concernés** (pas juste origin)

### 3.4 Pre-push security check
```bash
git diff --cached | grep -iE 'sk-or-|pcsk_|jV_zGdx|sbp_|hf_[A-Za-z]{10}|jina_[a-f0-9]{10}|ghp_'
```

### 3.5 En fin de session — Checklist
1. `technicals/` — MAJ si changements
2. `technicals/infra/env-vars-exhaustive.md` — MAJ si credentials changees
3. `snapshot/current/` — Sync workflows
4. `docs/data.json` — Regenerer
5. `directives/session-state.md` — Etat final
6. `directives/status.md` — Resume session (EN DERNIER)
7. `bash scripts/check-staleness.sh` — Verifier aucun fichier stale
8. **Commit + push vers origin ET repos satellites impactes**

---

## Processus Team-Agentique Multi-Model (OBLIGATOIRE)

> Reference complete : `technicals/project/team-agentic-process.md`

### Principes
1. **Multi-model** : Opus 4.6 analyse + Sonnet/Haiku execution (delegation via Task tool)
2. **Parallélisation** : Taches independantes en parallele (sauf tests n8n → sequentiels)
3. **Delegation intelligente** : Opus DECIDE quand deleguer → Sonnet (execution) ou Haiku (exploration)
4. **Coordination** : L'agent principal ne duplique pas le travail des sous-agents
5. **Reference-based** : Comparer avec `snapshot/good/`
6. **Auto-Stop** : 3 echecs consecutifs → STOP (voir `technicals/project/team-agentic-process.md`)
7. **Fixes Library partagee** : master dans mon-ipad, copies vers satellites via `push-directives.sh`
8. **Etat persistant** : session-state.md, knowledge-base.md, fixes-library.md — mis a jour PENDANT la session

### Delegation Multi-Model (arbre de decision)
```
TACHE → Analyse/Decision ? → OUI → OPUS fait lui-meme
                           → NON → Complexe ? → OUI → SONNET via Task tool
                                              → NON → HAIKU via Task tool
```

### Optimisations
- `run_in_background: true` pour taches longues (recherches web, downloads)
- `resume` pour reprendre un agent apres interruption
- `model: "haiku"` pour exploration codebase rapide (Glob/Grep patterns)
- `model: "sonnet"` pour recherches web, generation, batch commands
- `model: "opus"` (ou pas de model param) pour decisions et analyses complexes
- Paralleliser 3+ sous-agents independants dans un seul message

### Architecture distribuee (par volume de tests)
| Volume | Execution | Raison |
|--------|-----------|--------|
| Pilotage + analyse | VM (Opus direct) | Decisions complexes |
| 1-50 questions | HF Space (Opus + Haiku sous-agents) | 16GB RAM |
| 50-200 questions | HF Space ou Codespace | RAM suffisante |
| 500q+ | Codespace `rag-tests` | RAM 8GB, pas de contrainte |
| Ingestion massive | Codespace `rag-data-ingestion` | n8n + 2 workers dedies |
| Recherches web | VM (Opus delegue Sonnet) | Pas besoin de RAM |

---

## Gestion des Bottlenecks et Résolution de Problèmes (OBLIGATOIRE)

> **Principe fondamental** : Lancer les tests en background, se concentrer sur les problèmes.
> Les tests qui fonctionnent tournent en autonomie. Le temps de l'agent est consacré à résoudre ce qui bloque.

### Boucle de résolution par bottleneck
```
1. IDENTIFIER   → Quel pipeline/composant bloque la progression ?
2. CLASSIFIER   → Infrastructure | Rate-limit | Code | Data | Modèle LLM
3. PRIORISER    → Impact × Effort × Urgence (voir matrice ci-dessous)
4. ISOLER       → Tests fonctionnels en background, focus sur le blocage
5. RÉSOUDRE     → 1 fix à la fois, valider, documenter
6. RELANCER     → Tests du pipeline corrigé, vérifier pas de régression
```

### Matrice de priorisation des bottlenecks
| Type | Exemples | Impact | Effort | Action |
|------|----------|--------|--------|--------|
| **Infrastructure** | TCP port bloqué, VM OOM, Docker down | HAUT | MOYEN | Contourner (HF Space, Codespace) |
| **Rate-limit** | OpenRouter 429, Jina quota | MOYEN | BAS | Changer modèle ou attendre |
| **Code workflow** | [object Object], node crash, cache stale | HAUT | MOYEN | FIX + deactivate/activate cycle |
| **Data** | IDs collision, dedup cassé, dataset manquant | MOYEN | BAS | Script correctif ponctuel |
| **Modèle LLM** | Mauvaises réponses, hallucinations | BAS | HAUT | Changer prompt ou modèle |

### Règle background testing
```
TESTS QUI PASSENT → nohup en background + auto-commit toutes les 15 min
TESTS QUI ECHOUENT → investigation immédiate par l'agent
PIPELINE BLOQUÉ → documenter le blocage + contourner + lancer les autres pipelines
```

**Pattern concret** :
```bash
# Lancer les pipelines fonctionnels en background
N8N_HOST="$HF_SPACE_URL" nohup python3 eval/run-eval-parallel.py \
  --dataset phase-2 --types standard,graph,orchestrator \
  --force --early-stop 0 --workers 3 \
  > /tmp/phase2-run.log 2>&1 &

# Auto-commit périodique
nohup bash -c 'while true; do sleep 900; cd /path/to/repo && \
  python3 eval/generate_status.py && \
  git add docs/ && git commit -m "auto-commit" && git push; done' &

# Pendant ce temps : se concentrer sur le pipeline qui bloque
```

### Priorisation cross-pipeline (Rules 36-37)
```
AVANT CHAQUE FIX, RÉPONDRE À CES 2 QUESTIONS :

Q1 — IMPACT TRANSVERSAL (Rule 36) :
  "Ce fix débloque combien de pipelines ?"
  → Fix HF Space activation = débloque Standard + Graph + Orchestrator + PME = 4 pipelines → PRIORITÉ MAX
  → Fix Orchestrator intent = débloque Orchestrator seul = 1 pipeline → priorité basse

Q2 — QUICK-WIN (Rule 37) :
  "Combien de temps pour ce fix ?"
  → Changer un env var = 2 min → QUICK-WIN
  → Réécrire un prompt LLM complet = 1h → PAS un quick-win

MATRICE DE DÉCISION :
  Impact transversal HAUT + Quick-win → FAIRE EN PREMIER (gold)
  Impact transversal HAUT + Long      → FAIRE EN SECOND (silver)
  Impact transversal BAS  + Quick-win → FAIRE EN TROISIÈME (bronze)
  Impact transversal BAS  + Long      → FAIRE EN DERNIER (backlog)
```

### Escalade des bottlenecks
| Situation | Action | Escalade |
|-----------|--------|----------|
| 1 pipeline bloqué, 3 OK | Background les 3 OK, debug le bloqué | Aucune |
| 2+ pipelines bloqués | Identifier la cause commune | Vérifier infra (n8n, API keys, network) |
| Rate-limit OpenRouter | Changer `$env.LLM_*_MODEL` vers modèle alternatif | Tester Qwen 3 235B, Mistral Small 3.1 |
| HF Space TCP bloqué | Utiliser VM n8n ou Codespace pour ce pipeline | Documenter dans fixes-library |
| 3 échecs consécutifs | Auto-stop + rapport structuré | Consul fixes-library → knowledge-base |

---

## Gestion des Credentials (CRITIQUE)

**`.env.local` = seule source. GitHub = ZÉRO credentials.**

### Règles
1. JAMAIS de clés en clair dans les fichiers trackés
2. Scripts Python → `os.environ` ou `.env.local`
3. `.claude/settings.json` et `.mcp.json` dans `.gitignore`
4. Pre-push check OBLIGATOIRE (voir section 3.4)

### Services
| Service | Type | Note |
|---------|------|------|
| OpenRouter | Free tier | LLM gratuits |
| Jina | Free tier (1M tokens/mois) | Embeddings primary |
| Pinecone | Free tier | Vector store |
| Neo4j Aura | Free tier | Graph DB |
| Supabase | Free tier | SQL DB |
| Cohere | Trial (quasi-épuisé) | Reranking backup |
| HuggingFace | Free tier | Modèles/datasets |

---

## Règles d'Or

1. **UN fix par itération** — jamais plusieurs noeuds
2. **n8n = source de vérité** — éditer dans n8n, sync vers GitHub
3. **Double analyse AVANT chaque fix**
4. **5/5 minimum avant sync**
5. **Commit + push après chaque fix** (tous repos concernés)
6. **`docs/status.json` auto-généré** — ne pas éditer
7. **3+ régressions → REVERT**
8. **MAJ `technicals/` après découvertes**
9. **MAJ `directives/status.md` en fin de session**
10. **Travailler depuis `main`** (tous repos)
11. **Push réguliers** — 30 min minimum
12. **Tests séquentiels** — jamais parallèles (503)
13. **Comparer avec références** — `snapshot/good/`
14. **ZÉRO credentials dans git**
15. **MAJ session-state.md** — après chaque milestone
16. **source .env.local** — avant tout script Python
17. **Push multi-repo** — origin + satellites impactés
18. **Codespaces = éphémère** — résultats pushés avant arrêt
19. **RAM critique** — VM a seulement ~100MB dispo, éviter scripts mémoire-intensifs en parallèle
20. **Directives repos** — MAJ `directives/repos/*.md` si changements d'architecture
21. **MAJ `technicals/debug/fixes-library.md`** — après chaque fix réussi (avant commit)
22. **Pilotage live** — utiliser `codespace-control.sh` pour lancer/monitor/stopper les runs Codespace
23. **Progress callback** — les scripts eval écrivent `/tmp/eval-progress.json` pour visibilité VM
24. **MAJ `technicals/debug/knowledge-base.md`** — cerveau persistant, enrichi PENDANT la session (pas en fin), patterns + solutions + LLM + APIs + commandes
25. **NO operations VM** — aucun test (eval, quick-test) ne tourne sur la VM. Tests → HF Space ou Codespaces uniquement
26. **Session max 2h** — chaque session Claude Code limitée à 2h pour conserver l'efficacité. A 1h45 : finaliser, push, MAJ session-state.md et status.md
27. **Kill old processes** — au démarrage, vérifier `ps aux | grep claude | grep -v grep` et tuer les anciennes sessions Claude qui consomment de la RAM
28. **n8n REMOVED from VM** — Docker containers stopped and removed (Session 42). All n8n operations on HF Space or Codespaces. Eval scripts have hard guards blocking localhost/VM usage. VM = pilotage UNIQUEMENT.
29. **Pre-vol checklist** — AVANT tout test webhook, consulter `technicals/debug/knowledge-base.md` Section 0 (webhook paths, field names, auth)
30. **Agent Continuation** — Sous-agents (Sonnet/Haiku) continuent automatiquement apres succes (5q→10q→50q). Auto-stop sur 3 echecs consecutifs. Rapport structure a Opus pour analyse et decision. Details : `technicals/project/team-agentic-process.md` Section 3b.
31. **Push regulier GitHub** — commit + push toutes les 15-20 minutes minimum, pour chaque agent actif. Resultats JAMAIS perdus.
32. **Consulter document-index** — Au demarrage, consulter `docs/document-index.md` pour la carte complete des fichiers projet. `docs/executive-summary.md` pour le resume global.
33. **Background testing** — Les tests qui passent (pipelines fonctionnels) tournent en `nohup` background avec auto-commit. L'agent se concentre sur la résolution des problèmes et bottlenecks. Ne JAMAIS attendre passivement qu'un test finisse si d'autres tâches sont possibles.
34. **Bottleneck-first** — Toujours identifier et résoudre le bottleneck principal AVANT d'optimiser ce qui fonctionne. Prioriser : Infrastructure > Rate-limits > Code > Data > Modèle. Voir section "Gestion des Bottlenecks".
35. **Pipeline isolation** — Si un pipeline est bloqué (TCP, rate-limit, code), l'isoler et lancer les autres en parallèle. Ne JAMAIS bloquer tous les tests pour un seul pipeline défaillant.
36. **Cross-pipeline bottleneck** — AVANT de fixer un problème isolé, se demander : "Ce fix résout-il le problème pour TOUS les pipelines concernés ?" Prioriser les fixes à impact transversal (ex: un fix HF Space débloque 4 pipelines > un fix Standard qui ne débloque que Standard). Matrice : Impact_transversal × Nombre_pipelines_débloqués × Urgence.
37. **Low-hanging fruit** — A impact égal, toujours commencer par le quick-win (fix rapide, résultat immédiat). Un fix de 5 min qui débloque 1 pipeline passe AVANT un fix de 2h qui en débloque 2. Réévaluer après chaque quick-win : le paysage des problèmes change. Ne JAMAIS s'enliser dans un fix complexe quand 3 quick-wins sont disponibles.
38. **Executive summary always current** — `docs/executive-summary.md` DOIT refléter l'état réel du projet à tout moment. MAJ OBLIGATOIRE après chaque milestone, chaque changement de phase, chaque wipeout/incident. C'est le fichier de compréhension du projet — s'il est stale, tout le projet est opaque.
39. **Sub-agent verification** — Les sub-agents (Session Analyzer, Repo Health Inspector) DOIVENT être vérifiés : leurs recommandations ne valent rien si elles ne sont pas APPLIQUÉES. Après chaque run sub-agent, Opus vérifie que les changements sont concrets (pas juste des recommandations dans roadmap). Si un sub-agent timeout, le relancer immédiatement.
40. **Stale = broken** — Un fichier directive/technique stale de >24h est considéré BROKEN. Le staleness checker vérifie les headers mais PAS le contenu. Vérifier manuellement que le contenu reflète la réalité actuelle, pas juste que le timestamp est récent.

---

## Infrastructure

### VM Google Cloud (permanent — pilotage only, NO n8n)
```
IP externe    : 34.136.180.66
N8N_HOST      : https://lbjlincoln-nomos-rag-engine.hf.space (HF Space — VM n8n REMOVED)
Credentials   → .env.local (jamais dans git)
```

### Pipelines RAG
| Pipeline | Webhook Path | DB | Cible Phase 1 | Accuracy actuelle |
|----------|-------------|-----|----------------|-------------------|
| Standard | `/webhook/rag-multi-index-v3` | Pinecone | >= 85% | **85.5% PASS** |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | Neo4j + Supabase | >= 70% | **68.7% FAIL** |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | Supabase | >= 85% | **78.3% FAIL** |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | Meta | >= 70% | **80.0% PASS** |
| **Overall** | | | **>= 75%** | **78.1% PASS** |

### Enterprise Production Gates 2026 (requis pour Phase Gate eligibility)
| Métrique | Seuil | État |
|---------|-------|------|
| Accuracy overall | >= 75% | **78.1% PASS** |
| Faithfulness | >= 95% | **non mesuré** ← à ajouter |
| Context Recall | >= 85% | **non mesuré** ← à ajouter |
| Hallucination | <= 2% | **non mesuré** ← à ajouter |
| Latency mean | <= 2.5s | **non mesuré** ← à ajouter |

### Modeles LLM (3 familles, tous gratuits via OpenRouter)
| Famille | Modele | Roles | Cout |
|---------|--------|-------|------|
| **Llama 70B** | `meta-llama/llama-3.3-70b-instruct:free` | SQL, Intent, Planning, HyDE, Agent, QA | $0 |
| **Gemma 27B** | `google/gemma-3-27b-it:free` | Fast, Lite | $0 |
| **Trinity** | `arcee-ai/trinity-large-preview:free` | Extraction entites, Community summaries | $0 |

Details complets : `technicals/infra/env-vars-exhaustive.md` (Section 2 : LLM Model Vars)

### Recherche Feb 2026 — Papers cles
| Paper | arXiv | Action |
|-------|-------|--------|
| A-RAG (Agentic Hierarchical Retrieval) | 2602.03442 | Blueprint Orchestrator V11 |
| DeepRead (Structure-Aware Reasoning) | 2602.05014 | Juridique/Finance chunking |
| Late Chunking | 2409.04701 | Ré-ingestion Jina `late_chunking=True` |
| RAG-Studio (Domain Adaptation) | ACL EMNLP 2024 | Synthetic data par secteur |

→ Détails complets : `technicals/project/rag-research-2026.md`

### Website/Dashboard — Livrés session 13 (2026-02-17)
- **Hero** : problem-first, pain points cycliques, dual CTA + lien dashboard
- **SectorCard** : Apple-style, pain point en grand, ROI chips, bouton vidéo
- **VideoModal** : storyboard cinématique scripts Kimi (4 secteurs)
- **HowItWorks** : "Sous le capot", pipelines en sous-section
- **DashboardCTA** : section transparence avec métriques live
- **evalStore.ts** : Zustand SSE store (XP levels, streaming, pipeline stats)
- **useEvalStream.ts** : SSE hook avec reconnect exponentiel
- **dashboard/live/** : QuestionRow, VirtualizedFeedList, FeedStatusBar, MilestoneNotification
- **XPProgressionBar** : 7 niveaux gamifiés (1q → 1000q)

→ Sites : https://nomos-ai-pied.vercel.app | https://nomos-pme-connectors-alexis-morets-projects.vercel.app | https://nomos-pme-usecases-alexis-morets-projects.vercel.app | https://nomos-dashboard-alexis-morets-projects.vercel.app

### Accès
| Ressource | Accès |
|-----------|-------|
| n8n API + MCP | HF Space (VM n8n removed) |
| n8n Webhooks | HF Space webhooks |
| Pinecone | HTTPS API |
| Neo4j | https://38c949a2.databases.neo4j.io |
| Supabase | aws-1-eu-west-1.pooler.supabase.com:6543 |

### Architecture dossiers (ce repo)
| Dossier | Rôle |
|---------|------|
| `directives/` | Mission control (session-state, status, objective, process) |
| `directives/repos/` | **Directives personnalisées par repo satellite** |
| `technicals/debug/` | **Debug & troubleshooting** — diagnostic-flowchart, fixes-library, knowledge-base |
| `technicals/infra/` | **Infrastructure** — architecture, stack, n8n-topology, env-vars, credentials |
| `technicals/project/` | **Gestion projet** — phases, roadmap, team-agentic, recherche, website |
| `technicals/data/` | **Datasets** — master list, secteurs, types de documents |
| `eval/` | Scripts d'évaluation Python |
| `scripts/` | Utilitaires Python + scripts Bash + **codespace-control.sh** (pilotage live) |
| `n8n/` | Workflows (live, validated, sync) |
| `mcp/` | Serveurs MCP |
| `website/` | Code Next.js site ETI (4 secteurs) |
| `website-pme-connectors/` | Code Next.js site PME (12 connecteurs apps) |
| `website-pme-usecases/` | Code Next.js site PME (catalogue 200 cas) |
| `datasets/` | Données de test |
| `snapshot/` | Références (good, current) |
| `logs/` | Logs d'exécution |
| `outputs/` | Archives sessions |
| `docs/` | Dashboard data (status.json, data.json), **document-index.md** (INDEX), executive-summary.md |
