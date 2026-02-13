# Processus Standard de Session Claude Code

## Demarrage de Session

```
1. cat docs/status.json                          # Etat actuel
2. python3 eval/phase_gates.py                   # Gates passees ?
3. Identifier le pipeline avec le plus gros gap  # Priorite
4. Lire context/objective.md si besoin           # Rappel objectif
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
python3 eval/quick-test.py --questions 5 --pipeline <cible>
```
- **OBLIGATOIRE** : Analyse granulaire de CHAQUE execution avec **LES DEUX OUTILS**
- Pour chaque question, executer **LES DEUX commandes** :
  ```bash
  # Analyse 1 : node-analyzer.py (diagnostics automatiques)
  python3 eval/node-analyzer.py --execution-id <ID>
  
  # Analyse 2 : analyze_n8n_executions.py (donnees brutes completes) - OBLIGATOIRE
  python3 analyze_n8n_executions.py --execution-id <ID>
  ```
- Documenter : quel nœud, quel input, quel output, pourquoi c'est faux
- Si >= 3/5 correct → passer a 10/10
- Si < 3/5 → fixer UN nœud → retester 5/5

### Etape 3 : Test 10/10
```bash
python3 eval/fast-iter.py --label "fix-description" --questions 10
```
- **OBLIGATOIRE** : Analyse granulaire node-par-node avec **LES DEUX OUTILS**
- Pour chaque execution ID retournee :
  ```bash
  python3 eval/node-analyzer.py --execution-id <ID>
  python3 analyze_n8n_executions.py --execution-id <ID>
  ```
- Si >= 7/10 → session validee pour ce pipeline
- Si < 7/10 → iterer (retour etape 2)

### Etape 4 : Gate 10/10 atteinte
```bash
# Analyse complete des executions avec les deux outils
python3 eval/node-analyzer.py --pipeline <cible> --last 10
python3 analyze_n8n_executions.py --pipeline <cible> --limit 10

# Sync workflow depuis n8n
python3 workflows/sync.py

# Copier vers validated/
cp workflows/live/<pipeline>.json workflows/validated/<pipeline>-$(date +%Y%m%d-%H%M).json

# Commit
git add -A && git commit -m "fix: <pipeline> passes 10/10 - <description>"
git push -u origin <branch>
```

---

## Fin de Session

### Preparation pour la session suivante
1. **Sync workflows** : `python3 workflows/sync.py`
2. **Mettre a jour status** : `python3 eval/generate_status.py`
3. **Commit etat final** : commit + push tout ce qui a change
4. **Note dans context/session-state.md** : ce qui a ete fait, ce qui reste

### Pret pour le test 200q (si tous les pipelines passent 10/10)
```bash
python3 eval/run-eval-parallel.py --reset --label "Phase 1 full eval"
```

---

## Analyse Granulaire Node-par-Node (OBLIGATOIRE - DOUBLE ANALYSE)

### ⚠️ MODIFICATION ESSENTIELLE

Pour **CHAQUE question testee**, il est **OBLIGATOIRE** d'executer **LES DEUX ANALYSES** suivantes :

---

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

### ANALYSE 2 : analyze_n8n_executions.py (Donnees brutes completes) ⭐ NOUVEAU OBLIGATOIRE

```bash
# Execution specifique (OBLIGATOIRE pour chaque question)
python3 analyze_n8n_executions.py --execution-id <ID>

# Dernieres executions d'un pipeline
python3 analyze_n8n_executions.py --pipeline <cible> --limit 5

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
| **Issues detectees** | ✅ Auto (verbose, slow, errors) | ❌ Manuelle |
| **Donnees brutes** | Preview tronquee (1000-2000 chars) | ✅ Complete (JSON intégral) |
| **Recommandations** | ✅ Auto-generees | ❌ Non |
| **LLM content** | Preview 3000 chars | ✅ Complet |
| **Fichier de sortie** | logs/diagnostics/ | n8n_analysis_results/ |
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
- [ ] Quel nœud exact cause le probleme ? **(confirme par les DEUX outils)**
- [ ] Qu'est-ce que le nœud recoit en input ? **(via analyze_n8n_executions.py)**
- [ ] Qu'est-ce qu'il produit en output ? **(via analyze_n8n_executions.py)**
- [ ] Pourquoi cet output est-il faux ?
- [ ] Quel changement de code dans ce nœud va corriger le probleme ?

---

## Commandes de Reference

### Analyse rapide (les deux outils)
```bash
# Pour une execution specifique
python3 eval/node-analyzer.py --execution-id <ID> && \
python3 analyze_n8n_executions.py --execution-id <ID>

# Pour un pipeline (5 dernieres)
python3 eval/node-analyzer.py --pipeline <cible> --last 5 && \
python3 analyze_n8n_executions.py --pipeline <cible> --limit 5
```

### Workflow IDs verifies (via API n8n)
```python
WORKFLOW_IDS = {
    "standard": "IgQeo5svGlIAPkBc",
    "graph": "95x2BBAbJlLWZtWEJn6rb",
    "quantitative": "E19NZG9WfM7FNsxr",
    "orchestrator": "ALd4gOEqiKL5KR1p",
}
```

---

## Regles d'Or

1. **UN fix par iteration** — jamais plusieurs nœuds/pipelines en meme temps
2. **n8n est la source de verite** — editer dans n8n, sync vers GitHub
3. **Analyse granulaire AVANT chaque fix** — **LES DEUX OUTILS sont OBLIGATOIRES**
4. **Verifier AVANT de sync** — 5/5 doit passer avant de commit
5. **Commit + push apres chaque fix reussi** — garder les agents en sync
6. **Si 3+ regressions → REVERT immediat**
