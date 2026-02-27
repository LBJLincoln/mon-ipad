# QUICKSTART — Déployer tous les HF Spaces en 1 commande

## TL;DR

```bash
cd /home/termius/mon-ipad
bash scripts/launch-all.sh
```

Durée : **15-20 minutes** ⏱️

---

## Ce que fait le script

### Étape 1 : Restauration des credentials (2-3 min)
- Connecte à chaque HF Space via API n8n
- Crée les credentials (Supabase, OpenRouter, Pinecone, Neo4j, Redis)
- Restaure les références dans tous les workflows

### Étape 2 : Activation des workflows (3-5 min)
- Active tous les workflows sur les 10 spaces
- Enregistre les webhooks

### Étape 3 : Tests des webhooks (5-10 min)
- Teste 5 pipelines × 10 spaces = 50 tests
- Vérifie que chaque webhook répond avec du contenu réel

### Étape 4 : Rapport final
- Matrice de résultats colorée
- Taux de réussite par pipeline
- Logs complets sauvegardés

---

## Sortie attendue

```
╔═══════════════════════════════════════════════════════╗
║  NOMOS AI — LAUNCH ALL HF SPACES                      ║
╚═══════════════════════════════════════════════════════╝

Date : 2026-02-25 13:13:00
VM   : termius-vm (34.136.180.66)
User : termius

Spaces à activer : 10
Pipelines à tester : 5

▶ Vérification des dépendances système...
✓ Toutes les dépendances sont installées

▶ Chargement des variables d'environnement...
✓ Fichier .env.local chargé

▶ Vérification des variables d'environnement requises...
  ✓ OPENROUTER_API_KEY = sk-or-v1...3abc
  ✓ OPENROUTER_KEY_STANDARD = sk-or-v1...7def
  ...
✓ Toutes les variables requises sont définies (8/8)

▶ Test de connectivité avec les 10 HF Spaces...
→ Test de lbjlincoln-nomos-rag-engine...
✓   lbjlincoln-nomos-rag-engine : ACCESSIBLE
...
✓ Tous les spaces sont accessibles (10/10)

Prêt à lancer le déploiement sur 10 HF Spaces...
Appuyez sur ENTRÉE pour continuer ou CTRL+C pour annuler

================================================================================
ÉTAPE 1/3 : RESTAURATION DES CREDENTIALS
================================================================================

▶ Lancement de restore-all-spaces.py...
Ce processus va restaurer les credentials sur tous les HF Spaces.
Durée estimée : 2-3 minutes

[... logs Python ...]

✓ Restauration des credentials terminée

Résumé du rapport :
  Workflows restaurés : 45
  Workflows activés : 45

================================================================================
ÉTAPE 2/3 : ACTIVATION DES WORKFLOWS
================================================================================

▶ Lancement de activate-all-spaces.py...
Ce processus va activer tous les workflows sur tous les HF Spaces.
Durée estimée : 3-5 minutes

[... logs Python ...]

✓ Activation des workflows terminée

Résumé du rapport :
  Spaces activés : 10/10
  Workflows activés : 45

================================================================================
ÉTAPE 3/3 : TEST DES WEBHOOKS
================================================================================

▶ Test de 5 webhooks sur 10 spaces...
Durée estimée : 5-10 minutes

Testing space: lbjlincoln-nomos-rag-engine
→   Standard...
✓     Standard : OK (HTTP 200)
→   Graph...
✓     Graph : OK (HTTP 200)
→   Quantitative...
✓     Quantitative : OK (HTTP 200)
→   Orchestrator...
⚠     Orchestrator : EMPTY (HTTP 200)
→   PME...
✓     PME : OK (HTTP 200)

[... 9 autres spaces ...]

Résultats globaux :
  Tests effectués : 50
  ✓ Succès : 42
  ✗ Échecs : 8
  Taux de réussite : 84%

Matrice de résultats :

Space/Pipeline                 Standard        Graph           Quantitative    Orchestrator    PME
════════════════════════════════════════════════════════════════════════════════════════════════════════════════
lbjlincoln-nomos-rag-engine    ✓               ✓               ✓               ∅               ✓
lbjlincoln26-nomos-rag-engine-2 ✓               ✓               ✓               ∅               ✓
lbjlincoln-nomos-rag-engine-3  ✓               ✓               ✓               ✓               ✓
lbjlincoln26-nomos-rag-engine-4 ✓               ✓               ✓               ✓               ✓
lbjlincoln-nomos-rag-engine-5  ✓               ✓               ✓               ✓               ✓
lbjlincoln26-nomos-rag-engine-6 ✓               ✓               ✓               ✓               ✓
lbjlincoln-nomos-rag-engine-7  ✓               ✓               ✓               ✓               ✓
lbjlincoln26-nomos-rag-engine-8 ✓               ✓               ✓               ⏱               ✓
lbjlincoln-nomos-rag-engine-9  ✓               ✓               ✓               ✓               ✓
lbjlincoln26-nomos-rag-engine-10 ✓              ✓               ✓               ✓               ✗

Résultats par pipeline :
  ✓ Standard : 10/10 spaces OK (100%)
  ✓ Graph : 10/10 spaces OK (100%)
  ✓ Quantitative : 10/10 spaces OK (100%)
  ⚠ Orchestrator : 8/10 spaces OK (80%)
  ⚠ PME : 9/10 spaces OK (90%)

================================================================================
RAPPORT FINAL
================================================================================

▶ Génération du rapport consolidé...

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

Prochaines étapes :
  1. Vérifiez les rapports détaillés :
     - logs/space-restoration-report.json
     - logs/spaces-activation-report.json
  2. Lancez des tests avec : python3 eval/quick-test.py --questions 5
  3. Consultez le dashboard : https://nomos-dashboard-alexis-morets-projects.vercel.app

Logs complets : logs/launch-all-2026-02-25-131300.log

✓ Déploiement terminé avec succès!

✓ Script terminé avec succès!
Consultez les logs : logs/launch-all-2026-02-25-131300.log
```

---

## Légende des symboles

- ✓ = Succès (webhook retourne du contenu valide)
- ∅ = Vide (HTTP 200 mais corps vide)
- ✗ = Erreur (HTTP 4xx/5xx)
- ⏱ = Timeout (pas de réponse)

---

## Prochaines étapes après déploiement

### 1. Vérifier les rapports JSON

```bash
# Restauration
cat logs/space-restoration-report.json | jq '.results[] | {space, status, workflows_restored}'

# Activation
cat logs/spaces-activation-report.json | jq '.results[] | {space, login, workflows_activated: (.workflows_activated | length)}'
```

### 2. Tester les pipelines

```bash
# Test rapide (5 questions)
python3 eval/quick-test.py --questions 5 --pipeline standard

# Test complet (toutes les questions disponibles)
python3 eval/iterative-eval.py --label "post-deployment" --pipeline standard
```

### 3. Lancer l'évaluation Phase 2

```bash
# Évaluation parallèle sur tous les pipelines
python3 eval/run-eval-parallel.py --reset --label "Phase2-full-cluster"
```

### 4. Monitorer les performances

```bash
# Intelligence de session (analyse mathématique)
python3 scripts/session-intelligence.py

# Tracker de noeuds (historique succès/échec)
python3 scripts/node-tracker.py
```

---

## Troubleshooting rapide

### Le script s'arrête avant de commencer
→ Vérifiez que `.env.local` contient toutes les variables requises

### "Spaces inaccessibles"
→ Normal, ils sont en veille. Le script va les réveiller automatiquement.

### Tests de webhooks échouent (EMPTY)
→ Vérifiez que les credentials sont corrects dans `.env.local`
→ Consultez les logs n8n dans l'interface HF Space

### Échec de restauration sur un space
→ Vérifiez le rapport : `logs/space-restoration-report.json`
→ Relancez juste sur ce space : `python3 scripts/restore-all-spaces.py`

---

## Architecture du script

```
launch-all.sh
│
├─ 1. Pre-flight checks
│  ├─ Dependencies (python3, curl, jq)
│  ├─ Scripts exist (restore-all-spaces.py, activate-all-spaces.py)
│  ├─ Load .env.local
│  ├─ Check required env vars
│  └─ Test connectivity (curl health check)
│
├─ 2. Restore credentials (restore-all-spaces.py)
│  ├─ Parallel processing (4 workers)
│  ├─ Create credentials on each space
│  ├─ Map old IDs → new IDs
│  └─ Update workflow nodes
│
├─ 3. Activate workflows (activate-all-spaces.py)
│  ├─ Parallel processing (8 workers)
│  ├─ Login to each space
│  ├─ POST /rest/workflows/{id}/activate
│  └─ Basic webhook tests
│
├─ 4. Deep webhook testing (bash + curl)
│  ├─ 5 pipelines × 10 spaces = 50 tests
│  ├─ POST with test question
│  ├─ Check HTTP code + body content
│  └─ Build results matrix
│
└─ 5. Final report
   ├─ Consolidate all results
   ├─ Print colored matrix
   ├─ Per-pipeline success rate
   └─ Save logs
```

---

**Créé** : 2026-02-25
**Auteur** : Claude Code (Opus 4.6)
**Version** : 1.0.0
