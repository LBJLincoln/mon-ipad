# Launch All HF Spaces — Guide d'utilisation

## Vue d'ensemble

`launch-all.sh` est un script tout-en-un qui restaure et active automatiquement tous les 10 HF Spaces n8n du projet NOMOS AI.

## Prérequis

- Accès SSH à la VM Google Cloud (34.136.180.66)
- Fichier `.env.local` configuré avec toutes les credentials
- Scripts Python `restore-all-spaces.py` et `activate-all-spaces.py` présents

## Utilisation simple

```bash
# Sur la VM, dans le répertoire du projet
cd /home/termius/mon-ipad
bash scripts/launch-all.sh
```

Le script va :
1. ✅ Vérifier les dépendances système (python3, curl, jq)
2. ✅ Charger les variables d'environnement depuis `.env.local`
3. ✅ Tester la connectivité avec les 10 HF Spaces
4. ✅ Restaurer les credentials sur tous les spaces (2-3 min)
5. ✅ Activer tous les workflows (3-5 min)
6. ✅ Tester tous les webhooks (5-10 min)
7. ✅ Générer un rapport final avec matrice de résultats

## Durée totale

**15-20 minutes** pour un déploiement complet sur 10 spaces.

## Logs

Les logs sont sauvegardés dans :
```
logs/launch-all-YYYY-MM-DD-HHMMSS.log
```

Chaque exécution crée un nouveau fichier de log avec timestamp.

## Rapports générés

Le script génère 3 rapports :

1. **Restauration des credentials**
   - Fichier : `logs/space-restoration-report.json`
   - Contenu : Nombre de workflows restaurés par space

2. **Activation des workflows**
   - Fichier : `logs/spaces-activation-report.json`
   - Contenu : Workflows activés, webhooks testés

3. **Rapport final consolidé**
   - Affiché dans le terminal
   - Matrice de résultats (spaces × pipelines)
   - Taux de réussite par pipeline

## Exemple de sortie

```
╔═══════════════════════════════════════════════════════╗
║  NOMOS AI — DÉPLOIEMENT MULTI-SPACE COMPLÉTÉ          ║
╚═══════════════════════════════════════════════════════╝

Résumé :
  HF Spaces configurés : 10 / 10
  Workflows restaurés : 45
  Workflows activés : 45

Pipelines RAG disponibles :
  ✓ Standard : /webhook/rag-multi-index-v3
  ✓ Graph : /webhook/ff622742-6d71-4e91-af71-b5c666088717
  ✓ Quantitative : /webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
  ✓ Orchestrator : /webhook/92217bb8-ffc8-459a-8331-3f553812c3d0
  ✓ PME : /webhook/pme-assistant-gateway

Matrice de résultats :
Space/Pipeline                 Standard        Graph           Quantitative    Orchestrator    PME
════════════════════════════════════════════════════════════════════════════════════════════════════════════════
lbjlincoln-nomos-rag-engine    ✓               ✓               ✓               ✓               ✓
lbjlincoln26-nomos-rag-engine-2 ✓               ✓               ✓               ✓               ✓
...

Résultats par pipeline :
  ✓ Standard : 10/10 spaces OK (100%)
  ✓ Graph : 10/10 spaces OK (100%)
  ✓ Quantitative : 10/10 spaces OK (100%)
  ⚠ Orchestrator : 8/10 spaces OK (80%)
  ⚠ PME : 7/10 spaces OK (70%)
```

## Troubleshooting

### Erreur : "Dépendances manquantes"
```bash
sudo apt-get update
sudo apt-get install -y python3 curl jq
```

### Erreur : "Variables manquantes"
Éditez `.env.local` et ajoutez les variables requises :
- `OPENROUTER_API_KEY`
- `OPENROUTER_KEY_STANDARD`
- `OPENROUTER_KEY_GRAPH`
- `OPENROUTER_KEY_QUANTITATIVE`
- `OPENROUTER_KEY_ORCHESTRATOR`
- `PINECONE_API_KEY`
- `SUPABASE_PASSWORD`
- `NEO4J_AUTH`

### Erreur : "Spaces inaccessibles"
Les HF Spaces peuvent être en veille. Le script va les réveiller automatiquement lors du premier appel. Attendez 30-60 secondes et relancez.

### Webhooks qui échouent
Si certains webhooks retournent EMPTY ou ERROR :
1. Vérifiez les credentials dans `.env.local`
2. Vérifiez que les workflows sont activés dans l'interface n8n
3. Consultez les logs détaillés : `logs/spaces-activation-report.json`

## Workflow manuel (si le script échoue)

En cas d'échec du script automatique, vous pouvez lancer les étapes manuellement :

```bash
# 1. Restaurer les credentials
python3 scripts/restore-all-spaces.py

# 2. Activer les workflows
python3 scripts/activate-all-spaces.py

# 3. Tester les webhooks
python3 eval/quick-test.py --questions 5 --pipeline standard
```

## Support

Pour toute question ou problème :
1. Consultez les logs détaillés
2. Vérifiez les rapports JSON dans `logs/`
3. Lancez les scripts Python individuellement pour identifier l'étape qui échoue
4. Vérifiez l'état des HF Spaces dans l'interface Hugging Face

## Architecture

Le script coordonne 3 composants :

1. **restore-all-spaces.py** (Session 61)
   - Restaure les credentials Supabase, OpenRouter, Pinecone, Neo4j, Redis
   - Mappe les anciens IDs de credentials vers les nouveaux
   - Met à jour tous les workflows avec les bonnes références

2. **activate-all-spaces.py** (Session 61)
   - Active tous les workflows via POST `/rest/workflows/{id}/activate`
   - Teste les webhooks de base

3. **launch-all.sh** (ce script)
   - Orchestre les 2 scripts Python
   - Teste TOUS les webhooks en profondeur
   - Génère un rapport consolidé

## Prochaines étapes après le lancement

1. **Vérifier le dashboard**
   ```
   https://nomos-dashboard-alexis-morets-projects.vercel.app
   ```

2. **Lancer des tests d'évaluation**
   ```bash
   python3 eval/quick-test.py --questions 5 --pipeline standard
   python3 eval/iterative-eval.py --label "post-deployment"
   ```

3. **Monitorer les performances**
   ```bash
   python3 scripts/session-intelligence.py
   python3 scripts/node-tracker.py
   ```

4. **Lancer l'évaluation Phase 2**
   ```bash
   python3 eval/run-eval-parallel.py --reset --label "Phase2-deployment-test"
   ```

---

**Dernière mise à jour** : 2026-02-25
**Auteur** : Claude Code (Opus 4.6)
**Version** : 1.0.0
