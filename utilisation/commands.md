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
