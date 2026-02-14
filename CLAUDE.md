# Multi-RAG Orchestrator — Tour de Controle

> Ce fichier est le point d'entree unique. Il existe en symlink dans `directives/claude.md`.
> Il structure la session en 3 phases : LIRE, UTILISER, PRODUIRE.

---

## PHASE 1 — LIRE (dans cet ordre exact)

### 1.1 Etat actuel (TOUJOURS en premier)
```bash
cat docs/status.json                    # Metriques live : accuracy, gaps, blockers, next_action
cat directives/status.md                # Resume de la derniere session : fichiers modifies, analyse
```

### 1.2 Comprendre le projet
Lire `directives/objective.md` :
- Objectif final (Multi-RAG SOTA, 4 pipelines, 1M+ questions)
- Situation actuelle (quel pipeline bloque, etat des BDD)
- Workflow IDs Docker verifies

### 1.3 Comprendre le processus
Lire `directives/workflow-process.md` :
- Boucle d'iteration : 1/1 → 5/5 → 10/10 → 200q
- Double analyse OBLIGATOIRE (node-analyzer + analyze_n8n_executions)
- Checklist d'analyse par noeud
- Regles avant tout fix

### 1.4 Reference technique des endpoints
Lire `directives/n8n-endpoints.md` UNIQUEMENT quand tu dois :
- Appeler un webhook (formats verifies, timestamps Paris a la seconde)
- Modifier un workflow via API REST
- Verifier un Workflow ID ou Webhook Path

### 1.5 References techniques supplementaires (AU BESOIN seulement)
- `technicals/architecture.md` — Architecture detaillee des 4 pipelines + 9 workflows
- `technicals/stack.md` — Stack technique complete
- `technicals/credentials.md` — Configuration des services (cles dans .env.local)
- `technicals/phases-overview.md` — Strategie 5 phases et gates
- `technicals/knowledge-base.json` — Patterns d'erreurs connus
- `mcp/README.md` — Status des 7 MCP servers

---

## PHASE 2 — UTILISER (outils et commandes)

### 2.1 MCP Servers (configures dans `.claude/settings.json`)
| MCP | Usage |
|-----|-------|
| `n8n` | Executer et inspecter des workflows n8n (Docker natif) |
| `pinecone` | Interroger le vector store (10K+ vecteurs) |
| `neo4j` | Interroger le graph (110 entites) |
| `jina-embeddings` | Embeddings + Pinecone CRUD |
| `supabase` | SQL queries directes |
| `cohere` | Embeddings + Reranking |
| `huggingface` | Recherche modeles/datasets |

### 2.2 Commandes d'evaluation (dossier `eval/`)
| Commande | Usage |
|----------|-------|
| `python3 eval/quick-test.py --questions 1 --pipeline <cible>` | Smoke test 1 question |
| `python3 eval/quick-test.py --questions 5 --pipeline <cible>` | Test 5 questions |
| `python3 eval/iterative-eval.py --label "..."` | Eval progressive 5→10→50 |
| `python3 eval/run-eval-parallel.py --reset --label "..."` | Full eval 200q |
| `python3 eval/node-analyzer.py --execution-id <ID>` | Analyse node-par-node (diagnostics auto) |
| `python3 eval/node-analyzer.py --pipeline <cible> --last 5` | Dernieres 5 executions |
| `python3 eval/generate_status.py` | Regenerer docs/status.json |
| `python3 eval/phase_gates.py` | Verifier les gates de phase |

### 2.3 Commandes d'analyse (dossier `scripts/`)
| Commande | Usage |
|----------|-------|
| `python3 scripts/analyze_n8n_executions.py --execution-id <ID>` | Analyse brute complete (JSON integral) |
| `python3 scripts/analyze_n8n_executions.py --pipeline <cible> --limit 5` | Analyse par pipeline |

### 2.4 Commandes n8n (dossier `n8n/`)
| Commande | Usage |
|----------|-------|
| `python3 n8n/sync.py` | Sync n8n → GitHub |

### 2.5 Reference complete des commandes
Voir `utilisation/commands.md` pour la liste exhaustive avec tous les arguments.

### 2.6 Modification de workflows n8n (CRITIQUE)

**n8n = source de verite. GitHub = copie.**

```
1. DIAGNOSTIQUER  → eval/node-analyzer.py + scripts/analyze_n8n_executions.py
2. FIXER          → API REST n8n (voir directives/n8n-endpoints.md)
3. VERIFIER       → eval/quick-test.py --questions 5 minimum
4. SYNC           → n8n/sync.py
5. ARCHIVER       → copier vers n8n/validated/ si 5/5 passe
6. COMMIT         → git push
```

**JAMAIS** : editer les JSON workflow dans le repo, fixer plusieurs noeuds a la fois, deployer sans 5q de verification.

---

## PHASE 3 — PRODUIRE (outputs obligatoires)

### 3.1 Apres chaque test
- Logs d'execution → `logs/` (auto-genere par les scripts)
- Diagnostics → `logs/diagnostics/`
- Copier les resultats dans `logs/tests/<Nq>/` selon le nombre de questions

### 3.2 Apres chaque fix reussi (5/5 passe)
- Sync workflow : `python3 n8n/sync.py`
- Copier workflow actuel → `snapshot/current/`
- Regenerer status : `python3 eval/generate_status.py`
- **Commit + push** (IMMEDIATEMENT, ne pas attendre la fin de session)

### 3.3 Pushes reguliers (OBLIGATOIRE)
- **Push apres chaque fix reussi** (5/5 passe)
- **Push apres chaque milestone** (pipeline passe 10/10)
- **Push toutes les 30 minutes** minimum si des modifications existent
- **Push avant toute operation risquee** (modification workflow, changement de modele)

### 3.4 Comparaison avec les references (OBLIGATOIRE)
Toujours comparer les tests actuels avec les **dernieres executions confirmees comme reussies** :
- Les references sont dans `snapshot/good/` (workflows + executions JSON)
- Utiliser `scripts/analyze_n8n_executions.py --execution-id <ID>` pour comparer les donnees brutes
- Utiliser `eval/node-analyzer.py --execution-id <ID>` pour comparer les diagnostics
- NE remplacer les references dans `snapshot/good/` QUE si les nouveaux tests sont confirmes superieurs

### 3.5 En fin de session — Checklist OBLIGATOIRE (dans cet ordre)

#### Etape 1 — Outputs obligatoires (toujours)
1. **`technicals/`** — Mettre a jour architecture.md, stack.md si changements decouverts
2. **`utilisation/commands.md`** — Ajouter commandes echouees, mettre a jour commandes
3. **`snapshot/current/`** — Sync des workflows actuels depuis n8n
4. **`docs/data.json`** — Regenerer avec les resultats de la session
5. **`directives/status.md`** — EN DERNIER : resume session, fichiers modifies, prochaine action

#### Etape 2 — Outputs conditionnels (si necessaire)
6. **`directives/n8n-endpoints.md`** — Si workflow IDs ou endpoints ont change
7. **`n8n/live/`** — Sync via `python3 n8n/sync.py`
8. **`snapshot/good/`** — Remplacer les references UNIQUEMENT si nouveaux tests superieurs
9. **`eval/`** — Si scripts de test ont ete modifies

#### Etape 3 — Commit final
```bash
git add -A && git commit -m "session: <date> - <resume>"
git push
```

### 3.6 Reinitialisation data.json (chaque session)
```bash
python3 scripts/analyze_n8n_executions.py --pipeline standard --limit 1
python3 scripts/analyze_n8n_executions.py --pipeline graph --limit 1
python3 scripts/analyze_n8n_executions.py --pipeline quantitative --limit 1
python3 scripts/analyze_n8n_executions.py --pipeline orchestrator --limit 1
```
Puis integrer dans `docs/data.json`.

### 3.7 Outputs dates (archives)
Tout output de session non-structurel → `outputs/` avec prefixe `JJ-mmm-description.ext`
Exemple : `14-fev-docker-fixes-analysis.md`

---

## Processus Team-Agentic (OBLIGATOIRE)

Toutes les taches complexes doivent etre executees en mode **team-agentic** :

1. **Parallelisation** : Lancer les taches independantes en parallele via le Task tool
   - Exemple : tests de 4 pipelines → 4 agents paralleles (sauf si n8n overload → sequentiel)
   - Exemple : restructuration repo + tests → agents paralleles
2. **Delegation specialisee** : Chaque sous-tache a un agent dedie
   - Agent d'analyse : lit les executions, identifie les patterns
   - Agent de fix : modifie le workflow via API REST
   - Agent de test : execute les tests et reporte
3. **Coordination** : L'agent principal coordonne, ne duplique pas le travail des sous-agents
4. **Reference-based testing** : Toujours comparer avec `snapshot/good/` avant de conclure

## Regles d'Or

1. **UN fix par iteration** — jamais plusieurs noeuds simultanement
2. **n8n = source de verite** — editer dans n8n, sync vers GitHub
3. **Double analyse AVANT chaque fix** — node-analyzer.py + analyze_n8n_executions.py
4. **Verifier AVANT de sync** — 5/5 minimum
5. **Commit + push apres chaque fix reussi** (ne pas attendre la fin de session)
6. **`docs/status.json` est auto-genere** — ne pas editer manuellement
7. **Si 3+ regressions → REVERT immediat**
8. **Mettre a jour `technicals/` apres chaque decouverte technique**
9. **Mettre a jour `directives/status.md` en fin de session** (EN DERNIER)
10. **Toujours travailler depuis `main`**
11. **Push reguliers** — toutes les 30 minutes minimum
12. **Tests sequentiels** — ne JAMAIS tester plusieurs pipelines en parallele (503 overload)
13. **Comparer avec les references** — toujours partir des `snapshot/good/` pour evaluer

---

## Credentials — Docker era (post-migration 2026-02-12)

> **Les cles API sont dans `.env.local` (gitignore) et dans les env vars Docker.**
> Ne PAS mettre de cles en clair dans le repo GitHub.

```bash
# n8n Docker self-hosted sur Google Cloud VM
N8N_HOST="http://34.136.180.66:5678"
# N8N_API_KEY → voir .env.local

# Services : OpenRouter, Jina, Cohere, Pinecone, Neo4j, Supabase, HuggingFace
# Toutes les cles → voir .env.local
```

---

## Architecture — 14 dossiers

| # | Dossier | Role |
|---|---------|------|
| 1 | `directives/` | Mission control (objective, workflow-process, n8n-endpoints, status) |
| 2 | `technicals/` | Documentation technique (architecture, stack, credentials, phases, knowledge-base) |
| 3 | `eval/` | Scripts d'evaluation (quick-test, iterative-eval, node-analyzer) |
| 4 | `scripts/` | Scripts utilitaires Python |
| 5 | `n8n/` | Workflows n8n (live, validated, analysis, sync) |
| 6 | `mcp/` | Serveurs MCP et documentation (7 servers) |
| 7 | `website/` | Code source Next.js |
| 8 | `site/` | Reference website (copies pour vision complete) |
| 9 | `datasets/` | Donnees de test (phase-1, phase-2) |
| 10 | `db/` | Database (migrations, populate, readiness) |
| 11 | `snapshot/` | Snapshots : `good/` (references OK), `current/` (session), `workflows/`, `db/` |
| 12 | `logs/` | Logs d'execution + `tests/1q/`, `tests/5q/`, `tests/10q/`, `tests/20q/` |
| 13 | `outputs/` | Archives de sessions datees |
| 14 | `docs/` | Dashboard (data.json, status.json, index.html) |

---

## Pipelines

| Pipeline | Webhook Path | DB | Target Phase 1 |
|----------|-------------|-----|----------------|
| Standard | `/webhook/rag-multi-index-v3` | Pinecone | >= 85% |
| Graph | `/webhook/ff622742-...` | Neo4j + Supabase | >= 70% |
| Quantitative | `/webhook/3e0f8010-...` | Supabase | >= 85% |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | Meta | >= 70% |
| **Overall** | | | **>= 75%** |

LLM : Modeles gratuits via OpenRouter ($0).

## Acces

| Ressource | Acces | Note |
|-----------|-------|------|
| n8n Webhooks + REST API + MCP | DIRECT | `34.136.180.66:5678` (Docker self-hosted) |
| GitHub, Pinecone | DIRECT | git + HTTPS API |
| Supabase | VIA n8n | `ayqviqmxifzmhphiqfmj.supabase.co` |
| Neo4j | VIA n8n | `bolt://localhost:7687` (Docker VM) |
