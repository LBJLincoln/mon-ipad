# Processus Standard de Session Claude Code

## Démarrage de Session

```
1. cat docs/status.json                          # État actuel
2. python3 eval/phase_gates.py                   # Gates passées ?
3. Identifier le pipeline avec le plus gros gap  # Priorité
4. Lire context/objective.md si besoin           # Rappel objectif
```

---

## Boucle d'Itération (OBLIGATOIRE)

### Étape 1 : Test 1/1
```bash
python3 eval/quick-test.py --questions 1 --pipeline <cible>
```
- Si erreur → analyser node-par-node AVANT tout fix
- Si succès → passer à 5/5

### Étape 2 : Test 5/5
```bash
python3 eval/quick-test.py --questions 5 --pipeline <cible>
```
- **OBLIGATOIRE** : Analyse granulaire de CHAQUE exécution
- Pour chaque question :
  ```bash
  python3 eval/node-analyzer.py --execution-id <ID>
  ```
- Documenter : quel nœud, quel input, quel output, pourquoi c'est faux
- Si >= 3/5 correct → passer à 10/10
- Si < 3/5 → fixer UN nœud → retester 5/5

### Étape 3 : Test 10/10
```bash
python3 eval/fast-iter.py --label "fix-description" --questions 10
```
- **OBLIGATOIRE** : Analyse granulaire node-par-node
- Si >= 7/10 → session validée pour ce pipeline
- Si < 7/10 → itérer (retour étape 2)

### Étape 4 : Gate 10/10 atteinte
```bash
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

### Préparation pour la session suivante
1. **Sync workflows** : `python3 workflows/sync.py`
2. **Mettre à jour status** : `python3 eval/generate_status.py`
3. **Commit état final** : commit + push tout ce qui a changé
4. **Note dans context/session-state.md** : ce qui a été fait, ce qui reste

### Prêt pour le test 200q (si tous les pipelines passent 10/10)
```bash
python3 eval/run-eval-parallel.py --reset --label "Phase 1 full eval"
```

---

## Analyse Granulaire Node-par-Node (OBLIGATOIRE)

### Pour CHAQUE question testée, inspecter :

1. **Intent Analyzer** : La question a-t-elle été correctement classifiée ?
2. **Query Router** : A-t-elle été envoyée au bon pipeline ?
3. **Retrieval** (Pinecone/Neo4j/Supabase) :
   - Combien de documents récupérés ?
   - Scores de pertinence ?
   - Résultats vides ?
4. **LLM Generation** :
   - Le prompt est-il correct ?
   - La réponse est-elle fidèle au contexte ?
   - Hallucination ?
5. **Response Builder** :
   - La réponse finale correspond-elle à la sous-réponse ?
   - Perte d'information ?

### Commandes d'analyse

```bash
# Dernières 5 exécutions d'un pipeline
python3 eval/node-analyzer.py --pipeline <cible> --last 5

# Exécution spécifique
python3 eval/node-analyzer.py --execution-id <ID>

# Analyse complète (tous pipelines)
python3 eval/node-analyzer.py --all --last 5
```

### Avant TOUT fix, répondre à :
- [ ] Quel nœud exact cause le problème ?
- [ ] Qu'est-ce que le nœud reçoit en input ?
- [ ] Qu'est-ce qu'il produit en output ?
- [ ] Pourquoi cet output est-il faux ?
- [ ] Quel changement de code dans ce nœud va corriger le problème ?

---

## Règles d'Or

1. **UN fix par itération** — jamais plusieurs nœuds/pipelines en même temps
2. **n8n est la source de vérité** — éditer dans n8n, sync vers GitHub
3. **Analyse granulaire AVANT chaque fix** — pas de fix aveugle
4. **Vérifier AVANT de sync** — 5/5 doit passer avant de commit
5. **Commit + push après chaque fix réussi** — garder les agents en sync
6. **Si 3+ régressions → REVERT immédiat**
