# Reference des Commandes — Agentic Loop

> Guide d'utilisation du systeme Multi-RAG Orchestrator.
> Tous les chemins sont relatifs a la racine du repo.

---

## Boucle Agentic (workflow standard)

### 1. Demarrage de session
```bash
cat docs/status.json                                    # Metriques live
cat directives/status.md                                # Resume derniere session
```

### 2. Test rapide (smoke test)
```bash
python3 eval/quick-test.py --questions 1 --pipeline <cible>
python3 eval/quick-test.py --questions 5 --pipeline <cible>
```

### 3. Analyse double (OBLIGATOIRE apres chaque test)
```bash
python3 eval/node-analyzer.py --execution-id <ID>
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
```

### 4. Analyse par pipeline
```bash
python3 eval/node-analyzer.py --pipeline <cible> --last 5
python3 scripts/analyze_n8n_executions.py --pipeline <cible> --limit 5
```

### 5. Eval progressive
```bash
python3 eval/iterative-eval.py --label "description du fix"
```

### 6. Full eval (200q)
```bash
python3 eval/run-eval-parallel.py --reset --label "Phase 1 full eval"
python3 eval/run-eval-parallel.py --dataset phase-2 --reset --label "Phase 2"
```

### 7. Sync & status
```bash
python3 n8n/sync.py                                     # Sync n8n -> GitHub
python3 eval/generate_status.py                          # Regenerer status.json
python3 eval/phase_gates.py                              # Verifier gates
```

---

## Modification de workflows n8n

```bash
# Diagnostiquer
python3 eval/node-analyzer.py --pipeline <cible> --last 5

# Fixer (via API REST — voir directives/n8n-endpoints.md)
# 1. GET workflow -> 2. Modifier noeud -> 3. Deactivate -> 4. PUT -> 5. Activate

# Verifier (minimum 5 questions)
python3 eval/quick-test.py --questions 5 --pipeline <cible>

# Sync
python3 n8n/sync.py
```

---

## Pipelines disponibles

| Pipeline | Argument CLI |
|----------|-------------|
| Standard RAG | `standard` |
| Graph RAG | `graph` |
| Quantitative RAG | `quantitative` |
| Orchestrator | `orchestrator` |

---

## Scripts utilitaires

| Script | Chemin | Usage |
|--------|--------|-------|
| Session start | `scripts/session-start.py` | Setup automatique |
| Session end | `scripts/session-end.py` | Sauvegarde fin |
| N8n analyzer | `scripts/analyze_n8n_executions.py` | Analyse brute complete |
| DB analyzer | `db/analyze_db.py` | Analyse BDD |
| Pinecone dims | `scripts/verify_pinecone_dims.py` | Verifier dimensions |
| Single question | `scripts/test_single_question.py` | Test unitaire |

---

## Commandes echouees — NE PAS reproduire

| Commande | Erreur | Solution |
|----------|--------|----------|
| `python3 eval/quick-test.py --pipelines standard,graph,quantitative,orchestrator --questions 5` | 503 Service Unavailable apres 2-3 questions | Tester UN pipeline a la fois, sequentiellement |
| `$env.OPENROUTER_API_KEY` dans n8n Code nodes | Access denied en Docker self-hosted | Hardcoder les valeurs directement |
| `require('crypto')` dans n8n Code nodes | Module bloque par securite | Utiliser fonction hash custom |
| `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter | 429 — plus dans le free tier | Utiliser `arcee-ai/trinity-large-preview:free` |
| `google/gemma-3-27b-it:free` via OpenRouter | 429 — plus dans le free tier | Utiliser `nvidia/nemotron-3-nano-30b-a3b:free` |
| Pinecone avec credential `httpHeaderAuth` ID `3DEiHDwB09D65919` | Credential inexistante en Docker | `authentication: "none"` + header `Api-Key` manuel |
| `https://api.cohere.ai/v2/rerank` | Erreur 404/400 | Utiliser `/v1/rerank` |

---

## Modeles LLM gratuits disponibles (fevrier 2026)

| Modele | Usage recommande |
|--------|-----------------|
| `arcee-ai/trinity-large-preview:free` | HyDE, decomposition, general |
| `nvidia/nemotron-3-nano-30b-a3b:free` | Generation LLM, synthese |
| `stepfun/step-3.5-flash:free` | Backup rapide |
| `upstage/solar-pro-3:free` | Backup |
| `arcee-ai/trinity-mini:free` | Leger, classification |

---

## Repertoires de test

| Repertoire | Usage |
|------------|-------|
| `logs/tests/1q/` | Resultats tests 1 question |
| `logs/tests/5q/` | Resultats tests 5 questions |
| `logs/tests/10q/` | Resultats tests 10 questions |
| `logs/tests/20q/` | Resultats tests 20 questions |
| `snapshot/good/` | Workflows et executions de reference (confirmes OK) |
| `snapshot/current/` | Workflows de la session actuelle |
