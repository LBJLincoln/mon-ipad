# Processus Standard de Session Claude Code

## Demarrage de Session

```
1. cat docs/status.json                          # Etat actuel
2. python3 eval/phase_gates.py                   # Gates passees ?
3. Identifier le pipeline avec le plus gros gap  # Priorite
4. Lire directives/objective.md si besoin        # Rappel objectif
```

---

## Boucle d'Iteration (OBLIGATOIRE)

### Etape 1 : Test 1/1
```bash
python3 eval/quick-test.py --questions 1 --pipeline <cible>
```
- Si erreur → analyser node-par-node AVANT tout fix
- Si succes → passer a 5/5

### Etape 2 : Test 5/5
```bash
# Pipeline specifique :
python3 eval/quick-test.py --questions 5 --pipelines <cible>

# Tous les pipelines (sequentiel dans le meme process, evite les 503) :
python3 eval/quick-test.py --questions 5 --pipelines standard,graph,quantitative,orchestrator
```
**IMPORTANT** : Ne JAMAIS lancer plusieurs instances de quick-test.py en parallele → 503 n8n overload.
Utiliser `--pipelines p1,p2,p3` dans un seul appel (execution sequentielle interne).
- **OBLIGATOIRE** : Analyse granulaire de CHAQUE execution avec **LES DEUX OUTILS**
- Pour chaque question, executer **LES DEUX commandes** :
  ```bash
  # Analyse 1 : node-analyzer.py (diagnostics automatiques)
  python3 eval/node-analyzer.py --execution-id <ID>

  # Analyse 2 : analyze_n8n_executions.py (donnees brutes completes) - OBLIGATOIRE
  python3 scripts/analyze_n8n_executions.py --execution-id <ID>
  ```
- Documenter : quel noeud, quel input, quel output, pourquoi c'est faux
- Si >= 3/5 correct → passer a 10/10
- Si < 3/5 → fixer UN noeud → retester 5/5

### Etape 3 : Test 10/10
```bash
# Eval progressive avec tous les pipelines :
python3 eval/run-eval-parallel.py --max 10 --reset --label "fix-description"
# ↑ Lance standard/graph/quantitative en parallele, orchestrator apres.
#   Questions sequentielles au sein de chaque pipeline → pas de 503.

# OU eval iterative (plus lent mais plus detaille) :
python3 eval/iterative-eval.py --label "fix-description" --questions 10
```
- **OBLIGATOIRE** : Analyse granulaire node-par-node avec **LES DEUX OUTILS**
- Pour chaque execution ID retournee :
  ```bash
  python3 eval/node-analyzer.py --execution-id <ID>
  python3 scripts/analyze_n8n_executions.py --execution-id <ID>
  ```
- Si >= 7/10 → session validee pour ce pipeline
- Si < 7/10 → iterer (retour etape 2)

### Etape 4 : Gate 10/10 atteinte
```bash
# Analyse complete des executions avec les deux outils
python3 eval/node-analyzer.py --pipeline <cible> --last 10
python3 scripts/analyze_n8n_executions.py --pipeline <cible> --limit 10

# Sync workflow depuis n8n
python3 n8n/sync.py

# Copier vers validated/
cp n8n/live/<pipeline>.json n8n/validated/<pipeline>-$(date +%Y%m%d-%H%M).json

# Commit
git add -A && git commit -m "fix: <pipeline> passes 10/10 - <description>"
git push
```

---

## Fin de Session

### Preparation pour la session suivante
1. **Sync workflows** : `python3 n8n/sync.py`
2. **Mettre a jour status** : `python3 eval/generate_status.py`
3. **Commit etat final** : commit + push tout ce qui a change
4. **Note dans directives/status.md** : ce qui a ete fait, ce qui reste

### Pret pour le test 200q (si tous les pipelines passent 10/10)
```bash
python3 eval/run-eval-parallel.py --reset --label "Phase 1 full eval"
```

---

## Analyse Granulaire Node-par-Node (OBLIGATOIRE — DOUBLE ANALYSE)

### ANALYSE 1 : node-analyzer.py (Diagnostics automatiques)

```bash
# Dernieres 5 executions d'un pipeline
python3 eval/node-analyzer.py --pipeline <cible> --last 5

# Execution specifique
python3 eval/node-analyzer.py --execution-id <ID>

# Analyse complete (tous pipelines)
python3 eval/node-analyzer.py --all --last 5
```

**Fournit :**
- Detection automatique d'issues (verbose LLM, slow nodes, erreurs)
- Recommandations priorisees
- Health scores par node
- Rapport de latence (avg, p95)

---

### ANALYSE 2 : analyze_n8n_executions.py (Donnees brutes completes) — OBLIGATOIRE

```bash
# Execution specifique (OBLIGATOIRE pour chaque question)
python3 scripts/analyze_n8n_executions.py --execution-id <ID>

# Dernieres executions d'un pipeline
python3 scripts/analyze_n8n_executions.py --pipeline <cible> --limit 5

# Pipelines disponibles : standard, graph, quantitative, orchestrator
```

**Fournit :**
- **Donnees brutes completes** (full_input_data, full_output_data)
- **Extraction LLM detaillee** : content complet, tokens, modele, provider
- **Flags de routage** : skip_neo4j, skip_graph, fallback, etc.
- **Metadata de retrieval** : nombre de documents, scores, warnings

---

### Comparaison des deux outils

| Aspect | node-analyzer.py | analyze_n8n_executions.py |
|--------|------------------|---------------------------|
| **Type** | Diagnostic automatique | Extraction brute complete |
| **Issues detectees** | Auto (verbose, slow, errors) | Manuelle |
| **Donnees brutes** | Preview tronquee | Complete (JSON integral) |
| **Recommandations** | Auto-generees | Non |
| **LLM content** | Preview 3000 chars | Complet |
| **Fichier de sortie** | logs/diagnostics/ | n8n/analysis/ |
| **Usage principal** | Vue d'ensemble rapide | Debugging profond |

---

### Checklist d'analyse pour CHAQUE question

#### 1. Intent Analyzer
- [ ] La question a-t-elle ete correctement classee ?
- [ ] Quel est le output de l'Intent Analyzer ? (via **analyze_n8n_executions.py**)

#### 2. Query Router
- [ ] A-t-elle ete envoyee au bon pipeline ?
- [ ] Quelle est la decision de routage ? (via **analyze_n8n_executions.py**)

#### 3. Retrieval (Pinecone/Neo4j/Supabase)
- [ ] Combien de documents recuperes ?
- [ ] Scores de pertinence ?
- [ ] Resultats vides ?
- [ ] **Verification via les deux outils**

#### 4. LLM Generation
- [ ] Le prompt est-il correct ? (via **analyze_n8n_executions.py** - full_input_data)
- [ ] La reponse est-elle fidele au contexte ?
- [ ] Hallucination ?
- [ ] Tokens utilises ?

#### 5. Response Builder
- [ ] La reponse finale correspond-elle a la sous-reponse ?
- [ ] Perte d'information ?
- [ ] **Verification via les deux outils**

---

### Avant TOUT fix, repondre a :
- [ ] Quel noeud exact cause le probleme ? **(confirme par les DEUX outils)**
- [ ] Qu'est-ce que le noeud recoit en input ? **(via analyze_n8n_executions.py)**
- [ ] Qu'est-ce qu'il produit en output ? **(via analyze_n8n_executions.py)**
- [ ] Pourquoi cet output est-il faux ?
- [ ] Quel changement de code dans ce noeud va corriger le probleme ?

---

## Commandes de Reference

### Analyse rapide (les deux outils)
```bash
# Pour une execution specifique
python3 eval/node-analyzer.py --execution-id <ID> && \
python3 scripts/analyze_n8n_executions.py --execution-id <ID>

# Pour un pipeline (5 dernieres)
python3 eval/node-analyzer.py --pipeline <cible> --last 5 && \
python3 scripts/analyze_n8n_executions.py --pipeline <cible> --limit 5
```

### Workflow IDs Docker (source de verite)
```python
WORKFLOW_IDS = {
    "standard": "TmgyRP20N4JFd9CB",
    "graph": "6257AfT1l4FMC6lY",
    "quantitative": "e465W7V9Q8uK6zJE",
    "orchestrator": "aGsYnJY9nNCaTM82",
}
```

---

## Regles d'Or

1. **UN fix par iteration** — jamais plusieurs noeuds/pipelines en meme temps
2. **n8n est la source de verite** — editer dans n8n, sync vers GitHub
3. **Analyse granulaire AVANT chaque fix** — **LES DEUX OUTILS sont OBLIGATOIRES**
4. **Verifier AVANT de sync** — 5/5 doit passer avant de commit
5. **Commit + push apres chaque fix reussi** — garder les agents en sync
6. **Si 3+ regressions → REVERT immediat**

---

## Strategie de Test Parallele (Team-Agentic)

### Principe
n8n Docker supporte ~2-3 requetes simultanees. Au-dela → 503 Service Unavailable.

### Approche correcte par phase de test

| Phase | Methode | Script |
|-------|---------|--------|
| **1/1 smoke** | UN pipeline a la fois | `quick-test.py --questions 1 --pipelines <cible>` |
| **5/5 validation** | Tous pipelines, sequentiel | `quick-test.py --questions 5 --pipelines standard,graph,quantitative,orchestrator` |
| **10/10 gate** | Parallele stagger | `run-eval-parallel.py --max 10 --reset --label "..."` |
| **200q full** | Parallele stagger | `run-eval-parallel.py --reset --label "..."` |

### Parallele stagger (run-eval-parallel.py)
- Standard, Graph, Quantitative → threads paralleles (questions sequentielles par pipeline)
- Orchestrator → apres les 3 autres (il appelle les sub-workflows)
- Rate-limit backoff automatique (3s sur 429)
- `--workers 1` pour forcer sequentiel si necessaire
- `--delay 10` pour espacement entre questions si free models rate-limitent

### Ce qui NE FONCTIONNE PAS
- Lancer plusieurs instances de quick-test.py en parallele (bash background) → 503
- Lancer `--pipelines standard --questions 5 &` en meme temps que `--pipelines graph --questions 5 &` → 503
- Tester l'orchestrator en meme temps qu'un autre pipeline → contention sub-workflow
