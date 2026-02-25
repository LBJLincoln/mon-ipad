# INDEX DES DOCUMENTS — Ou trouver chaque information

> Last updated: 2026-02-25T11:30:00+00:00

> **Ce fichier est un INDEX DE RECHERCHE.**
> Quand tu cherches une information, consulte ce fichier EN PREMIER pour savoir
> dans quel(s) document(s) la trouver. Chaque sujet pointe vers 1 a 3 fichiers sources.

---

## TABLE DES MATIERES

1. [Infrastructure & Machines](#1-infrastructure--machines)
2. [n8n & Workflows](#2-n8n--workflows)
3. [LLM & Modeles](#3-llm--modeles)
4. [Bases de donnees](#4-bases-de-donnees)
5. [Pipelines RAG](#5-pipelines-rag)
6. [Debug & Troubleshooting](#6-debug--troubleshooting)
7. [Tests & Evaluation](#7-tests--evaluation)
8. [Datasets & Donnees](#8-datasets--donnees)
9. [Credentials & Securite](#9-credentials--securite)
10. [Gestion de projet](#10-gestion-de-projet)
11. [Repos GitHub](#11-repos-github)
12. [Websites & Deploiement](#12-websites--deploiement)
13. [Recherche & SOTA](#13-recherche--sota)
14. [Matrice complete : Sujet → Fichier(s)](#14-matrice-complete)

---

## 1. INFRASTRUCTURE & MACHINES

| Information | Document(s) source |
|-------------|-------------------|
| **VM Google Cloud** (IP, RAM, CPU, disque) | `CLAUDE.md` Section "Infrastructure reelle" |
| **HF Spaces** (10 deployed, 2 accounts, URLs) | `technicals/infra/architecture.md` Section HF Spaces |
| **HF Space management** (duplicate, activate, test) | `scripts/scale-hf-spaces.py`, `scripts/activate-all-spaces.py` |
| **Codespaces** (specs, limites, commandes) | `CLAUDE.md` Section "Codespaces" |
| **Vercel** (4 sites, URLs, status) | `CLAUDE.md` Section "Deployments Vercel" |
| **Docker containers** (n8n, Redis, PostgreSQL) | `CLAUDE.md` Section "Containers Docker" |
| **Plan d'infrastructure distribue** | `technicals/infra/infrastructure-plan.md` |
| **Stack technique** (versions, libs) | `technicals/infra/stack.md` |
| **Alternatives cloud** (comparatif) | `infra/cloud-alternatives.md` |
| **Inventaire materiel** | `infra/inventory.md` |
| **Architecture globale** (schema) | `technicals/infra/architecture.md` |
| **Topologie n8n** (workers, queue, Redis) | `technicals/infra/n8n-topology.md` |
| **RAM disponible sur VM** | `CLAUDE.md` (rechercher "970 MB") |
| **Keep-alive HF Space** | `CLAUDE.md` Section HF Space |
| **Limites & quotas** (tous services) | `technicals/infra/limits-quotas.md` |

---

## 2. N8N & WORKFLOWS

| Information | Document(s) source |
|-------------|-------------------|
| **Webhook paths** (4 pipelines) | `CLAUDE.md` Section "Pipelines RAG" + `directives/n8n-endpoints.md` |
| **Webhook paths (verification rapide)** | `technicals/debug/knowledge-base.md` **Section 0** |
| **Workflow IDs** (Docker) | `CLAUDE.md` Section "Workflows actifs" |
| **Topologie n8n** (queue mode, workers) | `technicals/infra/n8n-topology.md` |
| **API REST n8n** (endpoints, auth) | `directives/n8n-endpoints.md` |
| **n8n version + config** | `technicals/infra/architecture.md` |
| **Workflows actifs** (9 actifs, cible 16) | `CLAUDE.md` Section "Workflows actifs" + `technicals/infra/architecture.md` |
| **Champ de requete** (`query` pas `question`) | `technicals/debug/knowledge-base.md` Section 0 |
| **Processus de modification workflow** | `directives/workflow-process.md` |
| **Task Runner** (cache, problemes) | `technicals/debug/fixes-library.md` FIX-21 |
| **$env blocage n8n 2.8** | `technicals/debug/fixes-library.md` FIX-33 |
| **executeWorkflow vs httpRequest** | `technicals/debug/fixes-library.md` FIX-34 |

---

## 3. LLM & MODELES

| Information | Document(s) source |
|-------------|-------------------|
| **Modeles deployes** (IDs, params, roles) | `technicals/infra/llm-models-and-fallbacks.md` Section 2 |
| **Rate limits OpenRouter** (RPM, RPD) | `technicals/infra/llm-models-and-fallbacks.md` Section 1 |
| **Strategie de fallback** (par pipeline) | `technicals/infra/llm-models-and-fallbacks.md` Section 4 |
| **Modeles alternatifs** (classement SQL) | `technicals/infra/llm-models-and-fallbacks.md` Section 3 |
| **Strategies de resilience** (rotation, BYOK) | `technicals/infra/llm-models-and-fallbacks.md` Section 5 |
| **URL OpenRouter** (format correct) | `technicals/infra/llm-models-and-fallbacks.md` Section 6 |
| **Detection 429** (headers, retry) | `technicals/infra/llm-models-and-fallbacks.md` Section 6 |
| **Env vars LLM** (9 variables) | `technicals/infra/env-vars-exhaustive.md` Section 2 |
| **Historique rate limit** | `technicals/debug/knowledge-base.md` Section 1 |
| **Patterns OpenRouter** | `technicals/debug/knowledge-base.md` Sections 1.1-1.6 |

---

## 4. BASES DE DONNEES

| Information | Document(s) source |
|-------------|-------------------|
| **Pinecone** (indexes, vecteurs, namespaces) | `CLAUDE.md` Section "Bases de donnees cloud" |
| **Neo4j** (nodes, relations, labels) | `CLAUDE.md` Section "Bases de donnees cloud" |
| **Supabase** (tables, lignes, schema) | `CLAUDE.md` Section "Bases de donnees cloud" |
| **Credentials BDD** (connection strings) | `technicals/infra/credentials.md` |
| **Schema Supabase** (40 tables detail) | `docs/executive-summary.md` Section 6 |
| **Schema Neo4j** (labels, types) | MCP neo4j → `get-schema` |
| **Pinecone stats** | MCP pinecone → `describe-index-stats` |
| **Readiness Phase 2 BDD** | `db/readiness/phase-2-analysis-report.md` |

---

## 5. PIPELINES RAG

| Information | Document(s) source |
|-------------|-------------------|
| **Architecture 4 pipelines** (schema complet) | `technicals/infra/architecture.md` |
| **Accuracy actuelle** (par pipeline) | `directives/session-state.md` + `docs/status.json` |
| **Webhook paths** | `CLAUDE.md` Section "Pipelines RAG" |
| **Standard** (HyDE, Pinecone, Jina reranking) | `technicals/infra/architecture.md` + `docs/executive-summary.md` Section 5 |
| **Graph** (Neo4j, entity extraction) | `technicals/infra/architecture.md` + `docs/executive-summary.md` Section 5 |
| **Quantitative** (SQL gen, Supabase, template) | `technicals/infra/architecture.md` + `docs/executive-summary.md` Section 5 |
| **Orchestrator** (intent, delegation) | `technicals/infra/architecture.md` + `docs/executive-summary.md` Section 5 |
| **Limites de concurrence** | `technicals/debug/knowledge-base.md` Section 7.4 |
| **Cibles accuracy Phase 1** | `CLAUDE.md` Section "Phase 1" + `technicals/project/phases-overview.md` |
| **Parametres d'appel** (`query`, POST) | `technicals/debug/knowledge-base.md` Section 0 |

---

## 6. DEBUG & TROUBLESHOOTING

| Information | Document(s) source |
|-------------|-------------------|
| **Bug deja resolu ?** (27+ fixes) | `technicals/debug/fixes-library.md` |
| **Arbre de decision** (6 flowcharts) | `technicals/debug/diagnostic-flowchart.md` |
| **Patterns et solutions connus** | `technicals/debug/knowledge-base.md` |
| **Symptome → Fix mapping** | `technicals/debug/diagnostic-flowchart.md` Section "Matrice" |
| **Anti-patterns n8n** | `technicals/debug/fixes-library.md` Section "Anti-patterns" |
| **Pre-debug checklist** | `technicals/debug/diagnostic-flowchart.md` Section "Pre-debug" |
| **Processus de fix** (boucle iteration) | `directives/workflow-process.md` |
| **Auto-stop** (3 echecs → STOP) | `technicals/project/team-agentic-process.md` |
| **Logs d'execution n8n** | `scripts/analyze_n8n_executions.py` |
| **Node analyzer** | `eval/node-analyzer.py` |

---

## 7. TESTS & EVALUATION

| Information | Document(s) source |
|-------------|-------------------|
| **Test rapide** (1-10 questions) | `eval/quick-test.py` |
| **Test parallele** (concurrent, multi-pipeline) | `eval/parallel-pipeline-test.py` |
| **Test iteratif** (boucles, labels) | `eval/iterative-eval.py` |
| **Test batch** | `eval/run-eval-parallel.py` |
| **Resultats historiques** | `docs/data.json` (932 questions, 42 iterations) |
| **Status machine-readable** | `docs/status.json` |
| **Phase gates** | `eval/phase_gates.py` |
| **Pilotage Codespace** (lancer, stream, stop) | `scripts/codespace-control.sh` |
| **Progress callback** | `eval/progress_callback.py` |
| **Resultats concurrence** | `technicals/debug/knowledge-base.md` Section 7.4 |
| **Commandes d'eval** | `CLAUDE.md` Section "Commandes d'evaluation" |

---

## 8. DATASETS & DONNEES

| Information | Document(s) source |
|-------------|-------------------|
| **14 benchmarks** (SQuAD, HotpotQA, etc.) | `technicals/data/datasets-master.md` |
| **Datasets par secteur** (BTP, Finance, etc.) | `technicals/data/datasets-4-secteurs.md` |
| **1000+ types de documents** | `technicals/data/sector-datasets.md` |
| **Justification des benchmarks** | `directives/dataset-rationale.md` |
| **Questions Phase 1** | `datasets/phase-1/` |
| **Questions Phase 2** | `datasets/phase-2/` |
| **Donnees sectorielles** | `datasets/sectors/` |
| **Phase 2 readiness** | `docs/phase2-readiness.md` |
| **Phase 2 BDD analysis** | `db/readiness/phase-2-analysis-report.md` |

---

## 9. CREDENTIALS & SECURITE

| Information | Document(s) source |
|-------------|-------------------|
| **Cles API** (valeurs reelles) | `.env.local` (JAMAIS dans git) |
| **Documentation credentials** (sans valeurs) | `technicals/infra/credentials.md` |
| **33 env vars documentees** | `technicals/infra/env-vars-exhaustive.md` |
| **MCP server configs** | `.mcp.json` (JAMAIS dans git) |
| **Pre-push security check** | `CLAUDE.md` Section 3.4 |
| **HF Space secrets** | Interface HuggingFace (pas dans git) |
| **Git config email** | `alexis.moret6@outlook.fr` |

---

## 10. GESTION DE PROJET

| Information | Document(s) source |
|-------------|-------------------|
| **Etat de session actuel** | `directives/session-state.md` |
| **Resume session precedente** | `directives/status.md` |
| **Objectif du projet** | `directives/objective.md` |
| **5 phases (200q → 1M+)** | `technicals/project/phases-overview.md` |
| **Roadmap ameliorations** (50+ items) | `technicals/project/improvements-roadmap.md` |
| **Processus team-agentic** | `technicals/project/team-agentic-process.md` |
| **Boucle de travail** | `directives/workflow-process.md` |
| **29 regles d'or** | `CLAUDE.md` Section "Regles d'Or" |
| **Executive summary** | `docs/executive-summary.md` |
| **CE FICHIER** (index) | `docs/document-index.md` |
| **Staleness check** | `scripts/check-staleness.sh` |
| **Dashboard spec** | `docs/eval-dashboard-spec.md` |

---

## 11. REPOS GITHUB

| Information | Document(s) source |
|-------------|-------------------|
| **Vue d'ensemble 7 repos** | `CLAUDE.md` Section "Architecture Multi-Repo" |
| **Directive rag-tests** | `directives/repos/rag-tests.md` |
| **Directive rag-website** | `directives/repos/rag-website.md` |
| **Directive rag-data-ingestion** | `directives/repos/rag-data-ingestion.md` |
| **Directive rag-dashboard** | `directives/repos/rag-dashboard.md` |
| **Push directives** | `scripts/push-directives.sh` |
| **Git remotes** | `CLAUDE.md` Section "Remotes configures" |
| **DevContainer configs** | `.devcontainer/*/CLAUDE.md` |

---

## 12. WEBSITES & DEPLOIEMENT

| Information | Document(s) source |
|-------------|-------------------|
| **4 sites Vercel** (URLs, status) | `CLAUDE.md` Section "Deployements Vercel" |
| **Site ETI 4 secteurs** | `website/docs/site-reference.md` |
| **Website redesign plan** | `technicals/project/website-redesign-plan.md` |
| **UX design brief** | `directives/ux-design-brief.md` |
| **Scripts video Kimi** | `docs/kimi-video-scripts.md` |
| **n8n artifacts integration** | `website/docs/n8n-artifacts-integration.md` |

---

## 13. RECHERCHE & SOTA

| Information | Document(s) source |
|-------------|-------------------|
| **Papers 2026** (A-RAG, DeepRead, etc.) | `technicals/project/rag-research-2026.md` |
| **Methodologie recherche** | `directives/research-methodology.md` |
| **Benchmarks SOTA** | `technicals/data/datasets-master.md` |

---

## 14. MATRICE COMPLETE : SUJET → FICHIER(S)

> Tableau condensé pour recherche rapide. Un sujet = 1 ligne.

| Sujet | Fichier principal | Fichier(s) secondaire(s) |
|-------|------------------|--------------------------|
| Accuracy pipelines | `directives/session-state.md` | `docs/status.json` |
| Anti-patterns n8n | `technicals/debug/fixes-library.md` | |
| Architecture globale | `technicals/infra/architecture.md` | `docs/executive-summary.md` |
| Bug deja resolu ? | `technicals/debug/fixes-library.md` | `technicals/debug/diagnostic-flowchart.md` |
| Cles API | `.env.local` | `technicals/infra/credentials.md` |
| Codespaces | `CLAUDE.md` | `technicals/infra/infrastructure-plan.md` |
| Commandes eval | `CLAUDE.md` Section 2.2 | |
| Concurrence (limites) | `technicals/debug/knowledge-base.md` §7.4 | |
| Credentials BDD | `technicals/infra/credentials.md` | `.env.local` |
| Datasets benchmarks | `technicals/data/datasets-master.md` | `directives/dataset-rationale.md` |
| Datasets Phase 2 (1000q+) | `datasets/phase-2/` | `docs/phase2-readiness.md` |
| Datasets sectoriels | `technicals/data/datasets-4-secteurs.md` | `technicals/data/sector-datasets.md` |
| Docker containers | `CLAUDE.md` | `technicals/infra/architecture.md` |
| Env vars (33) | `technicals/infra/env-vars-exhaustive.md` | |
| Limites & quotas | `technicals/infra/limits-quotas.md` | |
| Fallback LLM | `technicals/infra/llm-models-and-fallbacks.md` | |
| Fixes documentes | `technicals/debug/fixes-library.md` | |
| Flowchart debug | `technicals/debug/diagnostic-flowchart.md` | |
| Graph pipeline | `technicals/infra/architecture.md` | `docs/executive-summary.md` §5 |
| HF Spaces (10 deployed) | `technicals/infra/architecture.md` | `scripts/scale-hf-spaces.py` |
| Knowledge base | `technicals/debug/knowledge-base.md` | |
| LLM modeles | `technicals/infra/llm-models-and-fallbacks.md` | `technicals/infra/env-vars-exhaustive.md` |
| n8n API REST | `directives/n8n-endpoints.md` | |
| n8n topology | `technicals/infra/n8n-topology.md` | |
| Objectif projet | `directives/objective.md` | |
| OpenRouter rate limits | `technicals/infra/llm-models-and-fallbacks.md` §1 | `technicals/debug/knowledge-base.md` §1 |
| Orchestrator pipeline | `technicals/infra/architecture.md` | `docs/executive-summary.md` §5 |
| Papers 2026 | `technicals/project/rag-research-2026.md` | |
| Phases (5) | `technicals/project/phases-overview.md` | `docs/phase2-readiness.md` |
| Pilotage Codespace | `scripts/codespace-control.sh` | `CLAUDE.md` §2.6b |
| Pinecone | `CLAUDE.md` | `technicals/infra/credentials.md` |
| Quantitative pipeline | `technicals/infra/architecture.md` | `technicals/infra/llm-models-and-fallbacks.md` |
| Regles d'or (29) | `CLAUDE.md` | |
| Resultats tests | `docs/data.json` | `docs/status.json` |
| Roadmap | `technicals/project/improvements-roadmap.md` | |
| Session state | `directives/session-state.md` | `directives/status.md` |
| Stack technique | `technicals/infra/stack.md` | |
| Standard pipeline | `technicals/infra/architecture.md` | `docs/executive-summary.md` §5 |
| Supabase | `CLAUDE.md` | `technicals/infra/credentials.md` |
| Team-agentic | `technicals/project/team-agentic-process.md` | |
| Vercel sites | `CLAUDE.md` | `docs/executive-summary.md` |
| VM Google Cloud | `CLAUDE.md` | `technicals/infra/architecture.md` |
| Webhook paths | `technicals/debug/knowledge-base.md` §0 | `CLAUDE.md`, `directives/n8n-endpoints.md` |
| Website ETI | `website/docs/site-reference.md` | `technicals/project/website-redesign-plan.md` |
| Workflow IDs | `CLAUDE.md` | `technicals/infra/architecture.md` |
| Workflow process | `directives/workflow-process.md` | |

---

## ARBORESCENCE DES DOCUMENTS (CARTE VISUELLE)

```
mon-ipad/
├── CLAUDE.md                          ← DIRECTIVE MAITRE (point d'entree)
│
├── docs/
│   ├── document-index.md              ← CE FICHIER (index de recherche)
│   ├── executive-summary.md           ← Resume complet du projet
│   ├── phase2-readiness.md            ← Checklist Phase 2
│   ├── status.json                    ← Metriques (auto-genere)
│   ├── data.json                      ← Historique iterations (auto-genere)
│   ├── eval-dashboard-spec.md         ← Spec du dashboard evaluation
│   └── kimi-video-scripts.md          ← Scripts video marketing
│
├── directives/
│   ├── session-state.md               ← MEMOIRE DE TRAVAIL (etat courant)
│   ├── status.md                      ← Resume derniere session
│   ├── objective.md                   ← Objectif final du projet
│   ├── workflow-process.md            ← Boucle d'iteration
│   ├── n8n-endpoints.md               ← Webhooks + API REST
│   ├── dataset-rationale.md           ← Justification benchmarks
│   ├── research-methodology.md        ← Methodologie recherche SOTA
│   ├── ux-design-brief.md             ← Brief UX/UI
│   └── repos/
│       ├── rag-tests.md               ← CLAUDE.md pour rag-tests
│       ├── rag-website.md             ← CLAUDE.md pour rag-website
│       ├── rag-data-ingestion.md      ← CLAUDE.md pour rag-data-ingestion
│       └── rag-dashboard.md           ← CLAUDE.md pour rag-dashboard
│
├── technicals/
│   ├── debug/                         ← TROUBLESHOOTING
│   │   ├── diagnostic-flowchart.md    ← 6 arbres de decision
│   │   ├── fixes-library.md          ← 35+ bugs resolus documentes
│   │   └── knowledge-base.md         ← CERVEAU PERSISTANT (patterns, solutions)
│   │
│   ├── infra/                         ← INFRASTRUCTURE
│   │   ├── architecture.md            ← Architecture 4 pipelines + workflows
│   │   ├── stack.md                   ← Stack technique (versions)
│   │   ├── n8n-topology.md            ← Topologie n8n (workers, queue)
│   │   ├── infrastructure-plan.md     ← Plan d'infrastructure distribue
│   │   ├── env-vars-exhaustive.md     ← 33 variables d'environnement
│   │   ├── credentials.md             ← Documentation credentials (pas les valeurs)
│   │   ├── llm-models-and-fallbacks.md ← Modeles LLM + rate limits + fallbacks
│   │   └── limits-quotas.md           ← Limites & quotas (tous services)
│   │
│   ├── project/                       ← GESTION PROJET
│   │   ├── phases-overview.md         ← 5 phases (200q → 1M+)
│   │   ├── improvements-roadmap.md    ← 50+ ameliorations
│   │   ├── team-agentic-process.md    ← Processus multi-model
│   │   ├── rag-research-2026.md       ← Papers SOTA 2026
│   │   └── website-redesign-plan.md   ← Plan redesign website
│   │
│   └── data/                          ← DATASETS
│       ├── datasets-master.md         ← 14 benchmarks
│       ├── datasets-4-secteurs.md     ← Datasets par secteur
│       └── sector-datasets.md         ← 1000+ types de documents
│
├── eval/                              ← SCRIPTS D'EVALUATION
│   ├── quick-test.py                  ← Test rapide (1-10q)
│   ├── parallel-pipeline-test.py      ← Test concurrent multi-pipeline
│   ├── iterative-eval.py              ← Test iteratif avec labels
│   ├── run-eval-parallel.py           ← Test batch
│   ├── node-analyzer.py               ← Analyse execution n8n
│   ├── generate_status.py             ← Genere status.json
│   └── phase_gates.py                 ← Verification phase gates
│
├── scripts/                           ← UTILITAIRES
│   ├── codespace-control.sh           ← Pilotage live Codespaces
│   ├── push-directives.sh             ← Push CLAUDE.md vers satellites
│   ├── check-staleness.sh             ← Detecte fichiers obsoletes
│   ├── setup-claude-opus.sh           ← Configure Opus 4.6
│   ├── analyze_n8n_executions.py      ← Analyse executions n8n
│   ├── scale-hf-spaces.py             ← HF Space management (list, duplicate, test)
│   └── activate-all-spaces.py         ← Bulk workflow activation across spaces
│
├── n8n/                               ← WORKFLOWS N8N
│   ├── live/                          ← Workflows actifs (JSON)
│   └── validated/                     ← Workflows valides (backup)
│
├── datasets/                          ← QUESTIONS DE TEST
│   ├── phase-1/                       ← 200 questions Phase 1
│   ├── phase-2/
│   │   ├── hf-1000.json               ← Graph+Quant expansion (1000q)
│   │   ├── graph-quant-expansion-500x2.json ← Graph+Quant (1000q)
│   │   ├── standard-orch-1000x2.json  ← Standard+Orchestrator (2000q)
│   │   └── pme-gateway-1000.json      ← PME Gateway (1000q)
│   └── sectors/                       ← Donnees sectorielles
│
├── logs/                              ← EXECUTION LOGS
│   ├── eval-session62-final.log       ← Phase 2 eval log
│   └── (autres logs d'execution)
│
├── snapshot/                          ← REFERENCES
│   ├── current/                       ← Etat actuel des workflows
│   └── good/                          ← Dernier etat valide (fallback)
│
├── infra/                             ← ANCIENNE LOCATION (migre vers technicals/infra/)
│   └── (fichiers dupliques — a nettoyer)
│
└── db/readiness/                      ← ANALYSE BDD
    └── phase-2-analysis-report.md     ← Readiness Phase 2 BDD
```

---

## ORDRE DE LECTURE RECOMMANDE

### Pour un nouvel agent (premier demarrage)
1. `CLAUDE.md` — Comprendre le projet, les regles, l'architecture
2. `docs/document-index.md` — Ce fichier, pour naviguer
3. `directives/session-state.md` — Ou en est-on
4. `docs/executive-summary.md` — Vue d'ensemble detaillee

### Pour reprendre une session
1. `directives/session-state.md` — Etat courant
2. `directives/status.md` — Resume session precedente
3. `docs/status.json` — Metriques
4. `technicals/debug/knowledge-base.md` — Cerveau persistant

### Pour debugger un probleme
1. `technicals/debug/diagnostic-flowchart.md` — Arbre de decision
2. `technicals/debug/fixes-library.md` — Bug deja resolu ?
3. `technicals/debug/knowledge-base.md` — Patterns connus
4. `directives/workflow-process.md` — Processus de fix

### Pour comprendre un pipeline
1. `technicals/infra/architecture.md` — Architecture technique
2. `docs/executive-summary.md` Section 5 — Explication simple
3. `technicals/debug/knowledge-base.md` Section 0 — Webhooks + parametres

### Pour les LLM et rate limits
1. `technicals/infra/llm-models-and-fallbacks.md` — Reference complete
2. `technicals/debug/knowledge-base.md` Sections 1.x — Historique patterns

### Pour les credentials
1. `technicals/infra/credentials.md` — Documentation
2. `technicals/infra/env-vars-exhaustive.md` — 33 variables
3. `.env.local` — Valeurs reelles (pas dans git)

---

*Ce document est l'INDEX DE RECHERCHE du projet Nomos AI.*
*A consulter en priorite quand on cherche une information.*
*Maintenu dans `mon-ipad/docs/document-index.md`.*
