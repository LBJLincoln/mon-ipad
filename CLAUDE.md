# Multi-RAG Orchestrator — Tour de Contrôle Centrale

> Last updated: 2026-02-27T15:33:00Z

**CE REPO (`mon-ipad`) EST LA TOUR DE CONTRÔLE.**
VM Google Cloud permanente · Claude Code via Termius · Pilote 7 repos satellites

**MODÈLE PRINCIPAL : `claude-opus-4-6` (abonnement Max) — Analyse, décisions, pilotage.**
**DELEGATION : Sonnet 4.5 (execution) + Haiku 4.5 (exploration) via Task tool — UNIQUEMENT quand Opus le juge pertinent.**

---

## 1. IDENTITY — QUI TU ES

Tu es Claude Code (`claude-opus-4-6`) exécuté dans **Termius** connecté à la **VM Google Cloud** (`34.136.180.66`). Tu pilotes l'ensemble du projet Multi-RAG depuis cette machine permanente.

### Stratégie Multi-Model
| Tâche | Modèle | Mécanisme |
|-------|--------|-----------|
| Analyse, décisions, pilotage | **Opus 4.6** | Direct (toi) |
| Recherches web, batch commands, génération | Sonnet 4.5 | `Task(model: "sonnet")` |
| Exploration codebase, vérifications | Haiku 4.5 | `Task(model: "haiku")` |

**JAMAIS déléguer** : analyse workflows, décisions debug, rédaction directives, évaluation résultats, communication utilisateur.

### Capacités
- Lire/écrire `/home/termius/mon-ipad/` (filesystem VM complet)
- MCP servers : n8n (HF Space), pinecone, neo4j, supabase, jina-embeddings, cohere, huggingface
- GitHub : 7 repos via `gh` CLI (origin + 6 satellites)
- Codespaces : create/ssh/stop/monitor via `codespace-control.sh`

---

## 2. QUICK START — SESSION CHECKLIST (PROTOCOL V2)

### Démarrage session (OBLIGATOIRE, 2-3 min)
```bash
cat directives/session-state.md
cat directives/status.md
cat technicals/debug/knowledge-base.md
cat technicals/debug/fixes-library.md
source .env.local
```

### Ordre de priorité opérationnelle (STRICT)
1. **Pipelines critiques down** (Standard/Graph/Quant/Orchestrator/Ingestion/PME gateway)
2. **RAG tests + dashboard live**
3. **Sites/chatbot UX**
4. **Démos/contenu marketing**

### Boucle d'exécution obligatoire (DIFF-FIRST)
1. **Diagnostiquer** (état actuel + diff vs état fonctionnel)
2. **Un seul fix à la fois**
3. **Tester incrémental** (ne pas retraiter les questions déjà testées)
4. **Comparer aux golden evals** (bloquer si régression critique)
5. **Commit + push immédiat**
6. **Mettre à jour docs état** (`executive-summary.md`, `status.md`, `session-state.md`)

### Règles de cadence
- Push utile toutes les **10-15 minutes** en phase active
- Toujours inclure un update horodaté dans `docs/executive-summary.md` après milestone
- Si 3 tentatives échouées sur le même point: rollback snapshot + nouvelle stratégie

### Règles dépréciées (supprimées car peu efficaces)
- Démarrage systématique de multiples agents background avant stabilisation des pipelines
- Multiplication de chantiers non critiques tant qu'un pipeline prioritaire est rouge
- Changements multi-noeuds simultanés sans validation intermédiaire

## 3. STATE FILES — SOURCES DE VÉRITÉ

| Fichier | Rôle | MAJ |
|---------|------|-----|
| `directives/session-state.md` | Mémoire de travail | Après chaque milestone |
| `directives/status.md` | Résumé dernière session | EN DERNIER de session |
| `docs/status.json` | Métriques live (auto-généré) | Ne PAS éditer |
| `technicals/debug/fixes-library.md` | Bibliothèque 24+ fixes | Après chaque fix réussi |
| `technicals/debug/knowledge-base.md` | **CERVEAU PERSISTANT** | PENDANT session (pas en fin) |
| `docs/document-index.md` | INDEX fichiers projet | Quand structure change |
| `docs/executive-summary.md` | Résumé global projet | Après chaque milestone |
| `logs/session-intelligence-report.json` | **INTELLIGENCE SESSION** — analyse mathématique | Auto (script startup) |
| `logs/node-tracker-report.json` | **HISTORIQUE NOEUDS** — succès/échec timestampé | Auto (script startup) |
| `snapshot/working-session58/` | **SNAPSHOTS FONCTIONNELS** — rollback rapide | Après chaque pipeline fix |

---

## 4. 15 CORE RULES

1. **Read before act** — `fixes-library.md` avant debug, `knowledge-base.md` Section 0 avant webhook, `session-state.md` avant action complexe
2. **source .env.local** — TOUJOURS avant scripts Python
3. **ZERO credentials in git** — Pre-push check : `git diff --cached | grep -iE 'sk-or-|pcsk_|jV_zGdx|sbp_|hf_|jina_|ghp_'`
4. **1 fix per iteration** — Jamais plusieurs noeuds simultanément (debug impossible sinon)
5. **5/5 before sync** — Valider quick-test.py --questions 5 avant `n8n/sync.py`
6. **Commit + push regularly** — Origin + satellites, toutes les 15-20 min. Git email: `alexis.moret6@outlook.fr`
7. **Update state files** — `session-state.md` après milestone, `fixes-library.md` + `knowledge-base.md` pendant session, `executive-summary.md` après incident
8. **VM = pilotage ONLY** — No n8n, no eval, no tests. Tout → HF Space ou Codespaces/GH Actions
9. **Push before shutdown** — Codespaces éphémères : résultats vers GitHub AVANT arrêt
10. **3+ regressions → REVERT** — Comparer avec `snapshot/working-session{N}/`
11. **Prioritize cross-pipeline impact** — Bottleneck × pipelines × urgence. Quick-win AVANT fix long à impact égal
12. **Background testing** — Tests OK → nohup + auto-commit. Focus sur bottlenecks
13. **Auto-stop on 3 failures** — Rapport structuré, pas de boucle infinie
14. **User Scale Override** — Scale demandé 2+ fois = PRIORITÉ BLOQUANTE. "80% à l'échelle" > "100% petit"
15. **Workflow Definition-of-Done** — importé → activé → testé (5q) → documenté → notifié avec URL

### Process guidelines (non-numérotées, contextuelles)
- **Tests parallèles OK** — Batch par pipeline avec rate-limit adapté. Pas de restriction séquentielle artificielle
- **Session Intelligence** — Exécuter scripts startup au démarrage, lire recommandations
- **Snapshot after fix** — Sauver workflow validé dans `snapshot/working-session{N}/`
- **Hot-patch via REST API** — PUT/PATCH `/rest/workflows/{id}`. Rebuild HF Space = dernier recours
- **Browser credential creator** — `POST /api/v1/credentials` ou Playwright headless. Ne jamais attendre accès navigateur manuel

### Token budget
- Auto-sauver `session-state.md` toutes les 30 minutes
- Réserver tokens pour cleanup fin de session (commits, docs, handoff)

---

## 5. INFRASTRUCTURE

### VM Google Cloud (permanent — pilotage ONLY)
```
IP         : 34.136.180.66
OS         : Linux Debian 11 (Bullseye)
CPU        : 1 vCPU Intel Xeon @ 2.20GHz
RAM        : 969 MB total | ~413 MB disponible (n8n removed Session 42)
Disque     : 30 GB total | 12 GB utilisé | 17 GB libres
N8N_HOST   : https://lbjlincoln-nomos-rag-engine.hf.space (HF Space)
```

**n8n REMOVED from VM (Session 42)** : Docker containers stopped + removed. All n8n → HF Space (16GB) ou Codespaces (8GB). VM RAM ~400MB+ disponible maintenant.

### HF Spaces — n8n distributed (2 instances, 16 GB each)

**Architecture multi-endpoint** (Session 57) : Pipelines répartis sur 2 HF Spaces pour doubler le throughput.

| Space | Account | Pipelines | URL | Status |
|-------|---------|-----------|-----|--------|
| **Primary (#1)** | LBJLincoln | Standard, Graph | lbjlincoln-nomos-rag-engine.hf.space | v5.5 deploying |
| **Secondary (#2)** | À vérifier | Quantitative, Orchestrator | À configurer | PENDING — user must provide valid HF_TOKEN_2 |

**Env vars multi-endpoint** :
```bash
N8N_HOST=https://lbjlincoln-nomos-rag-engine.hf.space              # Default (Space #1)
N8N_HOST_STANDARD=https://lbjlincoln-nomos-rag-engine.hf.space      # Space #1
N8N_HOST_GRAPH=https://lbjlincoln-nomos-rag-engine.hf.space         # Space #1
N8N_HOST_QUANTITATIVE=<SPACE_2_URL>                                  # Space #2 (when ready)
N8N_HOST_ORCHESTRATOR=<SPACE_2_URL>                                  # Space #2 (when ready)
```

**Per-pipeline API keys** (6 keys, 3 accounts — Session 50+57) :
- Core pipelines: `OPENROUTER_KEY_STANDARD`, `OPENROUTER_KEY_GRAPH`, `OPENROUTER_KEY_QUANTITATIVE`, `OPENROUTER_KEY_ORCHESTRATOR`
- Generic `OPENROUTER_API_KEY` **removed from core workflow JSONs** (Session 57). Only non-core (benchmark, chatbot) use fallback.

**Per-pipeline batch sizes** (auto mode, from Session 27 benchmarks) :
| Pipeline | Batch size | Concurrency max | Timeout |
|----------|-----------|----------------|---------|
| Standard | 10 | 5 concurrent | 90s |
| Graph | 5 | 3 concurrent | 90s |
| Quantitative | 3 | 1 concurrent | 120s |
| Orchestrator | 2 | 1 concurrent | 180s |

### Codespaces GitHub (éphémères — 60h/mois)
```
Type   : GitHub Codespaces Free tier
CPU    : 2 cores | RAM : 8 GB | Disque : 32 GB
Image  : mcr.microsoft.com/devcontainers/universal:2 (Ubuntu)
Inclus : Python 3.11, Node.js 20, Docker-in-Docker, Claude Code CLI
```

**NOTE** : rag-tests tourne sur la VM via scripts eval → HF Space webhooks. PAS besoin de Codespace pour rag-tests.

| Codespace / GH Actions | Repo | Usage |
|------------------------|------|-------|
| **GH Actions** ou Codespace | rag-pme-connectors | Tests + CI/CD PME connectors |
| **GH Actions** ou Codespace | rag-data-ingestion | Ingestion massive, 2 workers docker-compose |
| Codespace (optionnel) | rag-website | Dev site (Vercel deploy auto) |

### Bases de données cloud
| Service | Contenu | Limite |
|---------|---------|--------|
| Pinecone sota-rag-jina-1024 | 10,411 vecteurs, dim 1024 | 100K max |
| Pinecone sota-rag-phase2-graph | 1,296 vecteurs, e5-large | 100K max |
| Pinecone website-sectors-jina-1024 | 31,916 vecteurs, dim 1024 (sectors) | 100K max |
| Neo4j Aura | 19,788 nodes / 76,717 rels | 200K nodes / 400K rels |
| Supabase | 40 tables / ~17K lignes | 500MB storage |

### Déploiements Vercel (production live)
| Site | URL | Région |
|------|-----|--------|
| ETI 4 secteurs | nomos-ai-pied.vercel.app | cdg1 |
| PME Connecteurs | nomos-pme-connectors-alexis-morets-projects.vercel.app | cdg1 |
| PME Use Cases | nomos-pme-usecases-alexis-morets-projects.vercel.app | cdg1 |
| Dashboard tech | nomos-dashboard-alexis-morets-projects.vercel.app | iad1 |

### MCP Servers
| MCP | Capacités | Note |
|-----|-----------|------|
| n8n | Inspecter workflows (HF Space endpoint) | HF proxy issues possible |
| pinecone | 3 indexes, 22K+ vecteurs | OK |
| neo4j | Graph 19K+ nodes, Cypher queries | OK |
| supabase | SQL queries directes | OK |
| jina-embeddings | Embeddings 1024-dim + Pinecone CRUD | 1M tokens/mois |
| cohere | Reranking command-r | Trial quasi-épuisé |
| huggingface | Recherche modèles/datasets | OK |

---

## 6. PIPELINES RAG

### État Phase 1 — PASSED (20 fév 2026)
| Pipeline | Webhook Path | DB | Accuracy P1 | Target |
|----------|-------------|-----|-------------|--------|
| Standard | `/webhook/rag-multi-index-v3` | Pinecone | 85.5% | >= 85% ✓ |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | Neo4j + Supabase | 78.0% | >= 70% ✓ |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | Supabase | 92.0% | >= 85% ✓ |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | Meta | 80.0% | >= 70% ✓ |
| **Overall** | | | **83.9%** | **>= 75% ✓** |

### État Phase 2 — EN COURS (22 fév 2026)
| Pipeline | Tested | Total | Accuracy | Status |
|----------|--------|-------|----------|--------|
| Standard | 579 | 1000 | ~36% | **STOPPED** — HF Space ALL 404 |
| Graph | **500** | 500 | 78.0% | **COMPLETE** |
| Quantitative | **500** | 500 | 92.0% | **COMPLETE** |
| Orchestrator | 57 | 1000 | 0% | **BROKEN** — empty/404 every question |
| PME Gateway | 0 | — | — | NOT ACTIVATED — HF rebuild |

### Workflows n8n actifs (9 core + 3 PME)
**Pipelines RAG (4)** : Standard V3.4, Graph V3.3, Quantitative V2.0, Orchestrator V10.1
**Support (5)** : Dashboard Status API, Benchmark V3.0, Ingestion V3.1, Enrichissement V3.1, Dataset Ingestion
**PME (3)** : PME Gateway, PME Slack Connector, PME Gmail Connector
**Cible 16 workflows** : A (Test-RAG 4), B (Sector 4), C (Ingestion 4+4). Détails : `technicals/infra/architecture.md`

### Modèles LLM (per-pipeline OpenRouter keys)
| Famille | Modèle | Rôles | Coût |
|---------|--------|-------|------|
| Llama 70B | `meta-llama/llama-3.3-70b-instruct:free` | SQL, Intent, Planning, HyDE, Agent, QA | $0 |
| Gemma 27B | `google/gemma-3-27b-it:free` | Fast, Lite | $0 |
| Trinity | `arcee-ai/trinity-large-preview:free` | Extraction entités, Community summaries | $0 |

**6 credentials OpenRouter** across 3 accounts. Détails : `technicals/infra/env-vars-exhaustive.md`

### Plan des phases (A → D)
| Phase | Description | Repo | Statut |
|-------|-------------|------|--------|
| A.Phase1 | 200q baseline | rag-tests | ✅ PASSED (20 fév) |
| A.Phase2 | 1000q HF | rag-tests | **EN COURS** — Graph+Quant DONE, Std+Orch BLOCKED |
| A.Phase3 | ~10K q | rag-tests | Prérequis : Phase2 |
| B. SOTA | Recherche 2026 | mon-ipad | FAIT (session 13) — voir `technicals/project/rag-research-2026.md` |
| C. Ingestion | 14 benchmarks | rag-data-ingestion | STARTED — 3/5 datasets (669MB) |
| D. Website | 4 secteurs + PME | rag-website | MVP live — Vercel deployed |

---

## 7. COMMANDS

### Eval
```bash
source .env.local  # TOUJOURS avant Python
python3 eval/quick-test.py --questions 5 --pipeline <cible>
python3 eval/iterative-eval.py --label "Phase2-relaunch"
python3 eval/run-eval-parallel.py --reset --label "..."
python3 eval/node-analyzer.py --execution-id <ID>
python3 eval/generate_status.py
python3 eval/phase_gates.py
```

### Git
```bash
git push origin main                         # Push mon-ipad
bash scripts/push-directives.sh              # Sync CLAUDE.md → satellites
python3 n8n/sync.py                          # Sync workflows n8n
```

**IMPORTANT** : Repos satellites SÉPARÉS (session 41). NE JAMAIS `git push rag-tests main` depuis mon-ipad. Seuls CLAUDE.md synchés via `push-directives.sh`.

### Codespaces control (pilotage live)
```bash
scripts/codespace-control.sh list                                    # Lister actifs
scripts/codespace-control.sh launch <cs> --max 50 --label "Phase1"  # Lancer run
scripts/codespace-control.sh status <cs>                             # Progression
scripts/codespace-control.sh stream <cs>                             # Stream logs live
scripts/codespace-control.sh stop <cs>                               # STOP urgence
scripts/codespace-control.sh results <cs>                            # Récupérer résultats
scripts/codespace-control.sh monitor 30                              # Dashboard auto-refresh

# Commandes gh standard
gh codespace create --repo LBJLincoln/rag-tests --machine basicLinux32gb
gh codespace ssh --codespace <name>
gh codespace stop --codespace <name>
```

### n8n analysis
```bash
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
python3 scripts/analyze_n8n_executions.py --pipeline <cible> --limit 5
```

---

## 8. REPOS — ARCHITECTURE MULTI-REPO (7 REPOS)

### Remotes configurés (depuis ce repo)
```bash
origin             → github.com/LBJLincoln/mon-ipad.git
rag-tests          → github.com/LBJLincoln/rag-tests.git
rag-website        → github.com/LBJLincoln/rag-website.git
rag-dashboard      → github.com/LBJLincoln/rag-dashboard.git
rag-data-ingestion → github.com/LBJLincoln/rag-data-ingestion.git
rag-pme-connectors → github.com/LBJLincoln/rag-pme-connectors.git
rag-pme-usecases   → github.com/LBJLincoln/rag-pme-usecases.git
rag-storage        → github.com/LBJLincoln/rag-storage.git
```

### Rôles par repo
| Repo | Exécutant | Contenu | n8n | Directive |
|------|-----------|---------|-----|-----------|
| **mon-ipad** (CE REPO) | VM (Opus) | Directives, eval scripts, MCP configs | HF Space | `/home/termius/mon-ipad/CLAUDE.md` |
| **rag-tests** | VM → HF Space | Scripts eval, datasets, résultats | HF Space webhooks | `directives/repos/rag-tests.md` |
| **rag-website** | Codespace + Vercel | Next.js 14, 4 secteurs, chatbots | Local standalone | `directives/repos/rag-website.md` |
| **rag-dashboard** | Vercel (statique) | HTML/JS, métriques live read-only | AUCUN | `directives/repos/rag-dashboard.md` |
| **rag-data-ingestion** | Codespace | Ingestion V3.1, Enrichissement V3.1 | Local complet 2 workers | `directives/repos/rag-data-ingestion.md` |
| **rag-pme-connectors** | Codespace / GH Actions + Vercel | Next.js 15, 15 apps, MacBook chat | AUCUN | À créer si modifs |
| **rag-pme-usecases** | Vercel | Next.js 14, 200 use cases | AUCUN | Aucune (statique) |
| **rag-storage** | GitHub LFS | Datasets, snapshots, logs, outputs | AUCUN | Aucune (storage) |

---

## 9. PROCESS

### Fix pipeline (boucle itération)
```
1. DIAGNOSTIQUER → node-analyzer.py + analyze_n8n_executions.py
2. FIXER        → API REST n8n (1 noeud à la fois)
3. TESTER       → quick-test.py --questions 5 minimum
4. VALIDER      → quick-test.py --questions 10 (5/5 minimum)
5. SYNC         → n8n/sync.py
6. COMMIT+PUSH  → origin + repos concernés
```

### Bottleneck management
**Principe** : Lancer tests fonctionnels en background (nohup + auto-commit), se concentrer sur résolution bottlenecks.

**Boucle** :
1. IDENTIFIER → Quel pipeline/composant bloque ?
2. CLASSIFIER → Infrastructure | Rate-limit | Code | Data | Modèle LLM
3. PRIORISER → Impact × Effort × Urgence
4. ISOLER → Tests OK en background, focus sur blocage
5. RÉSOUDRE → 1 fix, valider, documenter
6. RELANCER → Tests pipeline corrigé

**Matrice priorisation** :
- Impact transversal HAUT + Quick-win → GOLD (faire EN PREMIER)
- Impact transversal HAUT + Long → SILVER
- Impact transversal BAS + Quick-win → BRONZE
- Impact transversal BAS + Long → BACKLOG

**Escalade** :
- 1 pipeline bloqué → Background les 3 OK, debug le bloqué
- 2+ pipelines bloqués → Identifier cause commune (infra, API keys, network)
- Rate-limit → Changer `$env.LLM_*_MODEL` vers alternatif
- 3 échecs consécutifs → Auto-stop + rapport structuré

**Détails complets** : `technicals/project/team-agentic-process.md`

### Modification workflow n8n (CRITIQUE)
```
1. DIAGNOSTIQUER → node-analyzer.py + analyze_n8n_executions.py
2. FIXER        → API REST n8n (ou MCP n8n)
3. VÉRIFIER     → quick-test.py --questions 5 minimum
4. SYNC         → n8n/sync.py
5. ARCHIVER     → snapshot/validated/
6. COMMIT+PUSH  → origin + repos concernés
```

### En fin de session — Checklist
1. `technicals/` — MAJ si changements
2. `technicals/infra/env-vars-exhaustive.md` — MAJ si credentials changées
3. `snapshot/current/` — Sync workflows
4. `docs/data.json` — Régénérer
5. `directives/session-state.md` — État final
6. `directives/status.md` — Résumé session (EN DERNIER)
7. `bash scripts/check-staleness.sh` — Vérifier aucun fichier stale
8. **Commit + push** → origin ET repos satellites impactés

### Anti-Staleness protocol
- Tout fichier directive DOIT inclure `Last updated: YYYY-MM-DDTHH:MM:SSZ`
- Au démarrage : vérifier >48h → WARN + MAJ
- `session-state.md` MAJ après chaque milestone (pas juste fin)
- `status.md` MAJ en DERNIÈRE action de session
- Script : `bash scripts/check-staleness.sh`
- Référence : `technicals/project/team-agentic-process.md`

---

## 10. REFERENCES — DETAILED DOCS

### Directives
- `directives/objective.md` — Objectif final, situation actuelle
- `directives/workflow-process.md` — Boucle itération
- `directives/n8n-endpoints.md` — Webhooks et API REST
- `directives/dataset-rationale.md` — Justification 14 benchmarks
- `directives/research-methodology.md` — SOTA 2026
- `directives/repos/` — Directives personnalisées par repo satellite

### Technicals
- `technicals/infra/architecture.md` — 4 pipelines + 9 workflows actifs, cible 16
- `technicals/infra/stack.md` — Stack technique
- `technicals/infra/credentials.md` — Configuration services
- `technicals/infra/env-vars-exhaustive.md` — 33 vars documentées, matrice workflow × var
- `technicals/infra/infrastructure-plan.md` — Infrastructure distribuée + Docker par repo
- `technicals/project/team-agentic-process.md` — Processus formel (rôles, auto-stop, fixes-library)
- `technicals/project/phases-overview.md` — 5 phases et gates
- `technicals/project/improvements-roadmap.md` — 50+ améliorations classées
- `technicals/project/rag-research-2026.md` — Papers clés (A-RAG, DeepRead, Late Chunking, RAG-Studio)
- `technicals/data/sector-datasets.md` — 1000+ types documents par secteur
- `technicals/debug/fixes-library.md` — Bibliothèque 24+ fixes documentés
- `technicals/debug/knowledge-base.md` — **CERVEAU PERSISTANT** — patterns, solutions, LLM, APIs
- `technicals/debug/diagnostic-flowchart.md` — Flowchart diagnostic

### Docs
- `docs/document-index.md` — **INDEX** — sujet → fichier source
- `docs/executive-summary.md` — Résumé global projet
- `docs/status.json` — Métriques live (auto-généré, NE PAS ÉDITER)
- `docs/data.json` — Dashboard data

---

## État actuel v5.5 (2026-02-25)

**Déploiement** : HF Space UP (HTTP 200) — Standard + Graph webhooks fonctionnels
**Infrastructure** : VM pilotage only. HF Space #1 active, #2 à déployer. GH Actions pour pme-connectors
**Credentials** : 6 OpenRouter keys (3 accounts), per-pipeline rotation
**Phase** : Phase 1 PASSED, Phase 2 partial (Graph+Quant DONE, Standard 78%, Orch+Quant BROKEN)
**Pipelines working** : Standard (78%), Graph (26% on hard Phase2 questions)
**Pipelines broken** : Quantitative (NO_ANSWER), Orchestrator (empty body), PME (validation error)

**Objectifs session 60** :
1. Deploy HF Space #2 (double throughput) + activate ALL 14 workflows
2. Build project chatbot (n8n + TermiusModal on all 4 sites) + 1000q dataset
3. Fix broken pipelines (Quant, Orch, PME) using bottleneck + low-hanging fruit
4. Non-stop eval on working pipelines in background
