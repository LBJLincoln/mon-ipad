# rag-tests — CLAUDE.md

> Last updated: 2026-02-24T21:30:00+01:00
> **Ce repo s'exécute dans un Codespace GitHub éphémère OU sur HF Space (16GB RAM).**
> Tu es un agent Claude Code specialise dans les TESTS des 4 pipelines RAG.
> **MODELE PRINCIPAL : `claude-opus-4-6`** — Analyse, decisions, evaluation des resultats.
> **DELEGATION** : Haiku 4.5 pour exploration codebase rapide via `Task(model: "haiku", subagent_type: "Explore")`.
> **n8n LOCAL dans ce Codespace** (docker-compose : n8n-main + 3 workers) — PAS de SSH tunnel vers la VM.
> Tu suis le même workflow-process que mon-ipad, adapté à ton rôle de testeur.
> Processus team-agentic multi-model : voir `technicals/project/team-agentic-process.md` (dans mon-ipad).

### REGLES CRITIQUES (Session 25+31+57)
- **Pre-vol checklist OBLIGATOIRE** : Consulter knowledge-base.md Section 0 avant tout test webhook
- **ZERO test sur la VM** : Tests → HF Space (16GB) ou Codespace (8GB)
- **Field name = `query`** (PAS `question`) pour les 4 pipelines
- **55+ fixes documentes** dans `technicals/debug/fixes-library.md` — consulter AVANT tout debug
- **Background testing** : Les tests qui passent tournent en `nohup` background avec auto-commit toutes les 15 min
- **Bottleneck-first** : Toujours résoudre le blocage principal avant d'optimiser ce qui fonctionne
- **Pipeline isolation** : Si un pipeline est bloqué, l'exclure et lancer les autres en parallèle
- **Multi-endpoint** : Chaque pipeline peut cibler un HF Space différent via N8N_HOST_STANDARD, N8N_HOST_GRAPH, etc.
- **Per-pipeline batch sizes** : `--batch-size 0` = auto (std=10, graph=5, quant=3, orch=2)
- **Per-pipeline API keys** : Chaque pipeline utilise sa propre clé OpenRouter (OPENROUTER_KEY_STANDARD, etc.)

---

## ÉTAT ACTUEL — 22 fév 2026 (Session 37)

| | |
|-|-|
| **Dernier commit** | 1f2a1e4 — session 37: v10 done (57%), v11 running |
| **Phase 1** | PASSED (83.9% overall, 20 fev 2026) |
| **Phase 2** | EN COURS — v11 running (Standard 335/537 tested, 45.7%) |
| **v10 résultats** | 1263q, 57% overall (Standard 60.4%, Graph 55.7%, Quant 53.3%, Orch 58.2%) |
| **HF Space** | https://lbjlincoln-nomos-rag-engine.hf.space — n8n 2.8.3, 16GB RAM, RUNNING |
| **Prochain objectif** | Finaliser v11, analyser limites Phase 2, documenter |

### Commandes clés pour cette session
```bash
# Démarrer le Codespace si nécessaire
gh codespace start --codespace nomos-rag-tests-5g6g5q9vjjwjf5g4

# Dans le Codespace — configurer Opus 4.6
bash scripts/setup-claude-opus.sh

# Démarrer n8n LOCAL (3 workers — PAS de SSH tunnel vers VM !)
docker compose up -d
curl -s http://localhost:5678/healthz | head -1  # doit répondre

# Charger variables
source .env.local

# Test rapide pipeline Quantitative (priorité)
python3 eval/quick-test.py --questions 5 --pipeline quantitative

# Test itératif pour fix en cours
python3 eval/iterative-eval.py --label "Phase1-fix-quant"
```

### État des pipelines (Phase 1 PASSED, Phase 2 EN COURS)
| Pipeline | Phase 1 (PASSED) | Phase 2 v11 (en cours) | Target P2 |
|----------|------------------|------------------------|-----------|
| Standard | 85.5% PASS | 335/537 tested (45.7%) | >= 75% |
| Graph | 78.0% PASS | En attente | >= 55% |
| Quantitative | 92.0% PASS | En attente | >= 65% |
| Orchestrator | 80.0% PASS | En attente | >= 70% |

---

## OBJECTIF DE CE REPO

**Tester, mesurer et rapporter** la performance des 4 pipelines RAG hébergés sur la VM.
Tu ne modifies PAS les workflows n8n (rôle de mon-ipad).
Tu ne touches PAS aux données (rôle de rag-data-ingestion).
Tu **mesures** uniquement, et tu pushes les résultats vers GitHub.

### Cibles Phase 1 (actuel)
| Pipeline | Cible | Accuracy actuelle |
|----------|-------|-------------------|
| Standard | >= 85% | 85.5% PASS |
| Graph | >= 70% | 68.7% FAIL |
| Quantitative | >= 85% | 78.3% FAIL |
| Orchestrator | >= 70% | 80.0% PASS |
| **Overall** | **>= 75%** | **78.1% PASS** |

---

## POSITION DANS LE PLAN GLOBAL (phases A→D)

```
PHASE A — RAG Pipeline Iteration  ← CE REPO EST ICI
  Phase 1 (200q)  ← EN COURS — BLOQUÉE (Graph + Quant FAIL)
  Phase 2 (1 000q HuggingFace)  ← prérequis : Phase 1 gates toutes passées
  Phase 3 (~10K q)  ← prérequis : Phase 2
  Phase 4 (~100K q) / Phase 5 (1M+)  ← infrastructure payante requise

PHASE B — Analyse SOTA 2026  ← MON-IPAD (pilotage)
PHASE C — Ingestion & Enrichment BDD  ← RAG-DATA-INGESTION
PHASE D — Production & Déploiement  ← RAG-WEBSITE + RAG-DASHBOARD
```

### Ce que ce repo doit produire pour débloquer la phase suivante

| Pour débloquer | Condition à atteindre | Comment |
|---------------|----------------------|---------|
| **Phase 1 → Phase 2** | Graph ≥ 70% ET Quant ≥ 85% (3 iter. stables) | Fix n8n workflows + tester ici |
| **Phase 2 (1000q)** | Datasets HuggingFace ingérés par rag-data-ingestion | Attendre ingestion, puis lancer `--questions 1000` |
| **Phase 3 (10K q)** | Phase 2 gates : Graph ≥ 60%, Quant ≥ 70% | Idem |

### Pourquoi Phase 1 est encore bloquée (ne pas confondre avec Phase 2)
Les itérations 35-42 labelisées **"Phase2-quant-..."** dans `docs/data.json` sont des **tests de niveau Phase 2** sur le pipeline quantitatif, pas une entrée officielle en Phase 2. Elles ont été lancées pour identifier les lacunes. La Phase 1 reste bloquée car :
- Graph : 68.7% < 70% cible (−1.3pp)
- Quantitative : 78.3% < 85% cible (−6.7pp)
- 0 itération stable consécutive sur les 2 pipelines simultanément

---

## INFRASTRUCTURE DE CE CODESPACE

```
Type        : GitHub Codespace (éphémère — 60h/mois Free)
CPU         : 2 cores
RAM         : 8 GB (vs ~100MB disponibles sur VM → tests lourds ICI)
Disque      : 32 GB
n8n local   : OUI — docker-compose.yml (n8n-main + 3 workers + Redis + PostgreSQL)
              PAS de SSH tunnel vers VM — n8n tourne ICI dans le Codespace
              docker compose up -d  (port 5678 local)
```

**ÉPHÉMÈRE** : toujours committer + pusher résultats avant arrêt.

---

## DÉMARRAGE DE SESSION (TOUJOURS EN PREMIER)

```bash
# 0. Configurer Opus 4.6 (une fois par Codespace)
bash scripts/setup-claude-opus.sh

# 1. Préparer docker-compose.yml (le fichier source est rag-tests-docker-compose.yml)
cp rag-tests-docker-compose.yml docker-compose.yml  # si docker-compose.yml absent

# 2. Démarrer n8n LOCAL (PAS de SSH tunnel — n8n tourne dans ce Codespace)
docker compose up -d
sleep 10  # attendre que n8n démarre
curl -s http://localhost:5678/healthz | head -1  # doit répondre "OK"

# 2. Charger les variables d'environnement
source .env.local

# 3. État actuel
cat docs/status.json
python3 eval/phase_gates.py

# 4. Identifier le pipeline avec le plus gros gap
# → Quantitative (-6.7pp, PRIORITÉ 1) et Graph (-1.3pp, PRIORITÉ 2)
```

---

## ETAPE 0 — Consulter la Bibliotheque de Fixes (OBLIGATOIRE)

**AVANT tout debug, TOUJOURS consulter `technicals/debug/fixes-library.md` en premier.**

```bash
cat technicals/debug/fixes-library.md
```

35 bugs documentes ont deja ete resolus (sessions 7–27). Chercher le symptome dans le tableau PIEGES RECURRENTS avant toute analyse. **Si symptome connu → appliquer directement SANS re-analyser.** Consulter les 2-3 dernieres versions reussies dans `n8n/validated/`. Si le symptome est nouveau → debugger, puis signaler a mon-ipad pour documentation dans la bibliotheque.

### Protocole Auto-Stop
3 echecs consecutifs sur le meme type d'erreur → STOP, documenter dans `logs/diagnostics/`, signaler a mon-ipad.

### Fixes Library Partagee
La bibliotheque de fixes master est dans `mon-ipad/technicals/debug/fixes-library.md`. Ce repo recoit une copie via `push-directives.sh`. Si tu decouvres un nouveau bug, documente-le dans `logs/diagnostics/` + commit + push. L'orchestrateur (mon-ipad) ajoutera le fix au master.

---

## BOUCLE D'ITÉRATION (identique à workflow-process.md de mon-ipad)

### Étape 1 : Test 1/1
```bash
python3 eval/quick-test.py --questions 1 --pipeline <cible>
```
- Si erreur → **double analyse** node-par-node AVANT tout fix
- Si succès → passer à 5/5

### Étape 2 : Test 5/5 (double analyse OBLIGATOIRE)
```bash
python3 eval/quick-test.py --questions 5 --pipelines <cible>
# POUR CHAQUE execution-id retourné :
python3 eval/node-analyzer.py --execution-id <ID>
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
```
- Si >= 3/5 → passer à 10/10
- Si < 3/5 → **signaler à mon-ipad** (le fix est fait là-bas, pas ici)

### Étape 3 : Test 10/10
```bash
python3 eval/run-eval-parallel.py --max 10 --reset --label "label-descriptif"
```
- Si >= 7/10 → pipeline validé pour cette session
- Si < 7/10 → signaler et itérer

### Étape 4 : Tests lourds (500q+) — UNIQUEMENT ICI (RAM 8GB)
```bash
python3 eval/run-eval-parallel.py --reset --label "phase1-200q"
python3 eval/run-eval-parallel.py --questions 1000 --label "phase2-1000q"
```

### Règle d'or : JAMAIS de tests parallèles
```bash
# NE PAS FAIRE
python3 quick-test.py --pipeline standard &
python3 quick-test.py --pipeline graph &  # → 503

# FAIRE
python3 quick-test.py --questions 5 --pipelines standard,graph,quantitative,orchestrator
```

---

## ANALYSE DOUBLE (OBLIGATOIRE pour chaque execution)

```bash
# Analyse 1 : diagnostics automatiques
python3 eval/node-analyzer.py --execution-id <ID>

# Analyse 2 : données brutes complètes
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
```

Checklist pour chaque question :
- [ ] Intent Analyzer : bonne classification ?
- [ ] Query Router : bon pipeline ciblé ?
- [ ] Retrieval : documents pertinents ? Scores ?
- [ ] LLM Generation : prompt correct, pas d'hallucination ?
- [ ] Response Builder : perte d'information ?

---

## WEBHOOKS (n8n LOCAL — docker compose up -d requis)

```
Standard     : http://localhost:5678/webhook/rag-multi-index-v3
Graph        : http://localhost:5678/webhook/ff622742-6d71-4e91-af71-b5c666088717
Quantitative : http://localhost:5678/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
Orchestrator : http://localhost:5678/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0
```
Note : ces webhooks fonctionnent sur le n8n LOCAL du Codespace (même port 5678).
Les workflows n8n doivent être importés depuis `n8n/` (sync depuis mon-ipad).

---

## PRIORITÉS ACTUELLES (Phase 1 → Phase 2)

1. **Quantitative** : 78.3% → 85% (gap -6.7pp — SQL edge cases, multi-table JOINs)
2. **Graph** : 68.7% → 70% (gap -1.3pp — entity extraction)
3. **Phase 2** : 1000q (hf-1000.json) quand les gates Phase 1 passent

---

## DATASETS & QUESTIONS — INVENTAIRE COMPLET

### Questions disponibles par phase
| Phase | Fichier(s) | Questions | Pipelines |
|-------|-----------|-----------|-----------|
| **Phase 1** | `datasets/phase-1/standard-orch-50x2.json` | 100 | Standard (50) + Orchestrator (50) |
| **Phase 1** | `datasets/phase-1/graph-quant-50x2.json` | 100 | Graph (50) + Quantitative (50) |
| **Phase 2** | `datasets/phase-2/hf-1000.json` | 1,000 | Graph (500) + Quantitative (500) |
| **Phase 2** | `datasets/phase-2/standard-orch-1000x2.json` | 2,000 | Standard (1,000) + Orchestrator (1,000) |
| **Sectoriels** | `datasets/sectors/*.jsonl` | 7,609 | Finance (2,250) + Juridique (2,500) + BTP (1,844) + Industrie (1,015) |
| **Total** | | **10,809** | |

### Sources des questions (14 benchmarks)
SQuAD v2, HotpotQA, MuSiQue, 2WikiMultiHopQA, NarrativeQA, QuALITY, TriviaQA, Natural Questions, FinQA, TatQA, ConvFinQA, WikiTableQuestions, IIRC, Bamboogle

### Methodes de test
| Methode | Commande | Quand l'utiliser |
|---------|----------|-----------------|
| Test rapide (1-10q) | `python3 eval/quick-test.py --questions 5 --pipeline <cible>` | Debug, validation rapide |
| Test parallele multi-pipeline | `python3 eval/parallel-pipeline-test.py --questions 10 --concurrency 3` | Validation concurrence |
| Test iteratif | `python3 eval/iterative-eval.py --label "Phase1-fix"` | Boucle d'amelioration |
| Test batch | `python3 eval/run-eval-parallel.py --reset --label "phase1-200q"` | Evaluation complete |
| Phase gates | `python3 eval/phase_gates.py` | Verification seuils |

### HF Space — Endpoints de test (alternative au Codespace)
Les pipelines sont aussi accessibles directement sur HF Space (16 GB RAM) :
```
Standard     : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3
Graph        : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717
Quantitative : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
Orchestrator : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0
```
Appel : `curl -X POST "<url>" -H "Content-Type: application/json" -d '{"query": "..."}'`

### Limites de concurrence (session 27)
| Pipeline | Max concurrent | Note |
|----------|---------------|------|
| Standard | 5 | Rock solid |
| Graph | 3 | Leger degrade au-dela |
| Orchestrator | 1 | Degrade sous charge (delegue aux sous-pipelines) |
| Quantitative | non teste | Rate limited OpenRouter |

### Pilotage live depuis la VM (codespace-control.sh)
```bash
scripts/codespace-control.sh launch <codespace> --max 50 --label "Phase1-fix"
scripts/codespace-control.sh status <codespace>    # progression en temps reel
scripts/codespace-control.sh stream <codespace>    # stream live des logs
scripts/codespace-control.sh stop <codespace>      # arret d'urgence
scripts/codespace-control.sh results <codespace>   # recuperer resultats JSON
```
Progress callback : les scripts eval ecrivent `/tmp/eval-progress.json` apres chaque question.

---

## FIN DE SESSION (OBLIGATOIRE)

```bash
# Générer status
python3 eval/generate_status.py

# Commit résultats
git add logs/ outputs/ docs/status.json docs/data.json
git commit -m "test(phase1): Standard X% Graph X% Quant X% Orch X%"
git push origin main

# → mon-ipad lira les résultats depuis GitHub
```

---

## RÈGLES D'OR

1. **Consulter fixes-library.md EN PREMIER** — avant tout debug (`technicals/debug/fixes-library.md`)
2. **source .env.local** avant tout script Python
3. **docker compose up -d** avant tout test (n8n LOCAL — PAS de SSH tunnel)
4. **Tests séquentiels** — un pipeline à la fois (jamais de parallèles → 503)
5. **Double analyse** (node-analyzer + analyze_n8n_executions) pour chaque exécution
6. **Ne pas modifier** les workflows n8n → rôle exclusif de mon-ipad
7. **Push résultats** avant arrêt du Codespace (éphémère !)
8. **Signaler les problèmes** dans logs/diagnostics/ + commit
9. **Modele principal : claude-opus-4-6** — lancer `bash scripts/setup-claude-opus.sh` au demarrage
10. **Delegation multi-model** — Opus analyse les resultats, Haiku explore le codebase rapidement

### Strategie Multi-Model (Session 26)
- **Opus 4.6** : Analyse des resultats d'evaluation, decisions de fix, communication
- **Haiku 4.5** : Exploration rapide du codebase (`Task(model: "haiku", subagent_type: "Explore")`)
- **Sonnet 4.5** : Recherches web si necessaire (`Task(model: "sonnet", subagent_type: "general-purpose")`)
- **Regle** : Opus DECIDE quand deleguer. Jamais deleguer l'analyse des resultats ou les decisions.

---

*Ce CLAUDE.md est géré depuis `mon-ipad/directives/repos/rag-tests.md` — ne pas éditer directement.*
