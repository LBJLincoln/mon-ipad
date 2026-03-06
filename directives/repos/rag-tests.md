# rag-tests — CLAUDE.md

> Last updated: 2026-03-06T12:00:00Z
> **Ce repo s'exécute sur la VM → HF Space webhooks (PAS de Codespace local n8n).**
> Tu es un agent Claude Code specialise dans les TESTS des 4 pipelines RAG.
> **MODELE PRINCIPAL : `claude-opus-4-6`** — Analyse, decisions, evaluation des resultats.
> **DELEGATION** : Haiku 4.5 pour exploration codebase rapide via `Task(model: "haiku", subagent_type: "Explore")`.
> Tu suis le même workflow-process que mon-ipad, adapté à ton rôle de testeur.
> Processus team-agentic multi-model : voir `technicals/project/team-agentic-process.md` (dans mon-ipad).

### REGLES CRITIQUES (Session 25+31+57+72)
- **Pre-vol checklist OBLIGATOIRE** : Consulter knowledge-base.md Section 0 avant tout test webhook
- **ZERO test sur la VM directement** : Tests → HF Space (16GB) via webhook HTTP POST
- **Field name = `query`** (PAS `question`) pour les 4 pipelines
- **67+ fixes documentes** dans `technicals/debug/fixes-library.md` — consulter AVANT tout debug
- **Background testing** : Les tests qui passent tournent en `nohup` background avec auto-commit toutes les 15 min
- **Bottleneck-first** : Toujours résoudre le blocage principal avant d'optimiser ce qui fonctionne
- **Pipeline isolation** : Si un pipeline est bloqué, l'exclure et lancer les autres en parallèle
- **Multi-endpoint** : Chaque pipeline peut cibler un HF Space différent via N8N_HOST_STANDARD, N8N_HOST_GRAPH, etc.
- **Per-pipeline batch sizes** : `--batch-size 0` = auto (std=10, graph=5, quant=3, orch=2)
- **Per-pipeline API keys** : Chaque pipeline utilise sa propre clé OpenRouter (OPENROUTER_KEY_STANDARD, etc.)

---

## ÉTAT ACTUEL — 6 mars 2026 (Session 72)

| | |
|-|-|
| **Phase 1** | **PASSED** (83.9% overall, 20 fev 2026, Session 30) |
| **Phase 2** | **PARTIAL** — Graph 78.0% (500/500), Quant 92.0% (500/500), Std/Orch STOPPED |
| **Phase 3** | **EN COURS** — Standard 87.5% COMPLETE, Graph 40.9% COMPLETE, Quant INVALID, Orch ON HOLD |
| **HF Space** | https://lbjlincoln-nomos-rag-engine.hf.space — n8n 2.8.4, 16GB RAM, 8 instances round-robin |
| **Prochain objectif** | Regenerer Quant dataset, analyser Graph accuracy drop (78% → 40.9%) |

### Commandes clés pour cette session
```bash
# Tests tournent depuis la VM → HF Space webhooks
source .env.local

# Test rapide pipeline
python3 eval/quick-test.py --questions 5 --pipeline <cible>

# Test batch Phase 3
python3 eval/run-eval-parallel.py --dataset datasets/phase-3/<fichier>.json --label "Phase3-..." --pipeline <cible> --reset
```

### État des pipelines (Phase 1 → Phase 3)
| Pipeline | Phase 1 (PASSED) | Phase 2 | Phase 3 | Target P3 |
|----------|------------------|---------|---------|-----------|
| Standard | 85.5% PASS | ~36% (579/1000) | **87.5% (8,006q) COMPLETE** | >= 85% |
| Graph | 78.0% PASS | 78.0% (500/500) COMPLETE | **40.9% (1,500q) COMPLETE** | >= 55% |
| Quantitative | 92.0% PASS | 92.0% (500/500) COMPLETE | 30% (500q) **INVALID dataset** | >= 65% |
| Orchestrator | 80.0% PASS | 0% (57/1000) BROKEN | ON HOLD | >= 70% |

---

## OBJECTIF DE CE REPO

**Tester, mesurer et rapporter** la performance des 4 pipelines RAG hébergés sur HF Space.
Tu ne modifies PAS les workflows n8n (rôle de mon-ipad).
Tu ne touches PAS aux données (rôle de rag-data-ingestion).
Tu **mesures** uniquement, et tu pushes les résultats vers GitHub.

---

## POSITION DANS LE PLAN GLOBAL (phases A→D)

```
PHASE A — RAG Pipeline Iteration  ← CE REPO EST ICI
  Phase 1 (200q)  ← PASSED (Session 30, 20 fev 2026)
  Phase 2 (1,000q HuggingFace)  ← PARTIAL (Graph+Quant DONE)
  Phase 3 (~10K q)  ← EN COURS — Standard+Graph COMPLETE, Quant INVALID, Orch ON HOLD
  Phase 4 (~100K q) / Phase 5 (1M+)  ← infrastructure payante requise

PHASE B — Analyse SOTA 2026  ← MON-IPAD (pilotage)
PHASE C — Ingestion & Enrichment BDD  ← RAG-DATA-INGESTION (COMPLETE — 34K records)
PHASE D — Production & Déploiement  ← RAG-WEBSITE + RAG-DASHBOARD
```

### Ce que ce repo doit produire pour débloquer la phase suivante

| Pour débloquer | Condition à atteindre | Comment |
|---------------|----------------------|---------|
| **Phase 3 complete** | Quant dataset regenerated + re-tested | Regenerer avec valeurs Supabase reelles |
| **Phase 3 → Phase 4** | Standard >= 85%, Graph >= 55%, Quant >= 65% | Standard OK, Graph a investiguer, Quant a retester |

### Problèmes Phase 3 identifiés
- **Quant 30%** : Le dataset a des expected answers synthétiques qui ne matchent pas les valeurs réelles en Supabase. La pipeline retourne les bonnes valeurs. Solution : régénérer le dataset.
- **Graph 40.9%** : Accuracy drop significatif vs Phase 2 (78%). Les questions Phase 3 (MuSiQue, 2WikiMultiHop, HotpotQA-bridge) sont plus difficiles que Phase 2. A analyser : est-ce les questions ou le pipeline ?
- **Orchestrator 0%** : Retourne empty body / 404 depuis Phase 2. Non testé Phase 3.

---

## EXECUTION ENVIRONMENT

```
Tests tournent DEPUIS la VM (mon-ipad) → HF Space webhooks (16GB RAM)
PAS de Codespace local n8n — PAS de docker compose up -d
Scripts eval dans mon-ipad/eval/ appellent les webhooks HF Space directement
```

**IMPORTANT** : Contrairement à ce qui était documenté avant Session 42, les tests ne nécessitent PAS de Codespace avec n8n local. Tout passe par les webhooks HF Space.

---

## ETAPE 0 — Consulter la Bibliotheque de Fixes (OBLIGATOIRE)

**AVANT tout debug, TOUJOURS consulter `technicals/debug/fixes-library.md` en premier.**

```bash
cat technicals/debug/fixes-library.md
```

67 bugs documentes ont deja ete resolus (sessions 7–71). Chercher le symptome dans le tableau PIEGES RECURRENTS avant toute analyse. **Si symptome connu → appliquer directement SANS re-analyser.** Consulter les 2-3 dernieres versions reussies dans `n8n/validated/`. Si le symptome est nouveau → debugger, puis signaler a mon-ipad pour documentation dans la bibliotheque.

### Protocole Auto-Stop
3 echecs consecutifs sur le meme type d'erreur → STOP, documenter dans `logs/diagnostics/`, signaler a mon-ipad.

### Fixes Library Partagee
La bibliotheque de fixes master est dans `mon-ipad/technicals/debug/fixes-library.md`. Ce repo recoit une copie via `push-directives.sh`. Si tu decouvres un nouveau bug, documente-le dans `logs/diagnostics/` + commit + push. L'orchestrateur (mon-ipad) ajoutera le fix au master.

---

## BOUCLE D'ITÉRATION

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

### Étape 4 : Tests lourds (500q+) — Phase 3
```bash
python3 eval/run-eval-parallel.py --dataset datasets/phase-3/standard-8700.json --label "Phase3-Std" --pipeline standard --reset
python3 eval/run-eval-parallel.py --dataset datasets/phase-3/graph-1500.json --label "Phase3-Graph" --pipeline graph --reset
python3 eval/run-eval-parallel.py --dataset datasets/phase-3/quantitative-500-v2.json --label "Phase3-Quant-v2" --pipeline quantitative --reset
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

## WEBHOOKS (HF Space — tests via HTTP POST)

```
Standard     : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3
Graph        : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717
Quantitative : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
Orchestrator : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0
```
Appel : `curl -X POST "<url>" -H "Content-Type: application/json" -d '{"query": "..."}'`

---

## PRIORITÉS ACTUELLES (Phase 3)

1. **Quant dataset** : Régénérer avec valeurs Supabase réelles (script `db/populate/regenerate_quant_phase3.py`)
2. **Graph analysis** : Comprendre le drop 78% → 40.9% (questions plus dures ou pipeline faible ?)
3. **Orchestrator** : Fix empty body / 404 (ON HOLD par décision utilisateur)

---

## DATASETS & QUESTIONS — INVENTAIRE COMPLET

### Questions disponibles par phase
| Phase | Fichier(s) | Questions | Pipelines |
|-------|-----------|-----------|-----------|
| **Phase 1** | `datasets/phase-1/standard-orch-50x2.json` | 100 | Standard (50) + Orchestrator (50) |
| **Phase 1** | `datasets/phase-1/graph-quant-50x2.json` | 100 | Graph (50) + Quantitative (50) |
| **Phase 2** | `datasets/phase-2/hf-1000.json` | 1,000 | Graph (500) + Quantitative (500) |
| **Phase 2** | `datasets/phase-2/standard-orch-1000x2.json` | 2,000 | Standard (1,000) + Orchestrator (1,000) |
| **Phase 3** | `datasets/phase-3/standard-8700.json` | 8,700 | Standard |
| **Phase 3** | `datasets/phase-3/graph-1500.json` | 1,500 | Graph |
| **Phase 3** | `datasets/phase-3/quantitative-500.json` | 500 | Quantitative (INVALID — v1) |
| **Phase 3** | `datasets/phase-3/quantitative-500-v2.json` | 500 | Quantitative (regenerated — v2) |
| **Phase 3** | `datasets/phase-3/orchestrator-auto.json` | 1,000 | Orchestrator (mixed) |
| **Sectoriels** | `datasets/sectors/*.jsonl` | 7,609 | Finance (2,250) + Juridique (2,500) + BTP (1,844) + Industrie (1,015) |
| **Total** | | **~15,500** | |

### Sources des questions (14 benchmarks)
SQuAD v2, HotpotQA, MuSiQue, 2WikiMultiHopQA, NarrativeQA, QuALITY, TriviaQA, Natural Questions, FinQA, TatQA, ConvFinQA, WikiTableQuestions, IIRC, Bamboogle

### Methodes de test
| Methode | Commande | Quand l'utiliser |
|---------|----------|-----------------|
| Test rapide (1-10q) | `python3 eval/quick-test.py --questions 5 --pipeline <cible>` | Debug, validation rapide |
| Test parallele multi-pipeline | `python3 eval/parallel-pipeline-test.py --questions 10 --concurrency 3` | Validation concurrence |
| Test iteratif | `python3 eval/iterative-eval.py --label "Phase3-fix"` | Boucle d'amelioration |
| Test batch | `python3 eval/run-eval-parallel.py --reset --label "phase3-..."` | Evaluation complete |
| Phase gates | `python3 eval/phase_gates.py` | Verification seuils |

### Limites de concurrence (session 27)
| Pipeline | Max concurrent | Note |
|----------|---------------|------|
| Standard | 5 | Rock solid |
| Graph | 3 | Leger degrade au-dela |
| Orchestrator | 1 | Degrade sous charge (delegue aux sous-pipelines) |
| Quantitative | 1 | Rate limited OpenRouter |

### Pilotage live depuis la VM (codespace-control.sh)
```bash
scripts/codespace-control.sh launch <codespace> --max 50 --label "Phase3-fix"
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
git commit -m "test(phase3): Standard X% Graph X% Quant X% Orch X%"
git push origin main

# → mon-ipad lira les résultats depuis GitHub
```

---

## RÈGLES D'OR

1. **Consulter fixes-library.md EN PREMIER** — avant tout debug (`technicals/debug/fixes-library.md`)
2. **source .env.local** avant tout script Python
3. **Tests via HF Space webhooks** — PAS de n8n local, PAS de docker compose
4. **Double analyse** (node-analyzer + analyze_n8n_executions) pour chaque exécution
5. **Ne pas modifier** les workflows n8n → rôle exclusif de mon-ipad
6. **Push résultats** régulièrement
7. **Signaler les problèmes** dans logs/diagnostics/ + commit
8. **Modele principal : claude-opus-4-6** — analyse et decisions
9. **Delegation multi-model** — Opus analyse les resultats, Haiku explore le codebase rapidement

### Strategie Multi-Model (Session 26)
- **Opus 4.6** : Analyse des resultats d'evaluation, decisions de fix, communication
- **Haiku 4.5** : Exploration rapide du codebase (`Task(model: "haiku", subagent_type: "Explore")`)
- **Sonnet 4.5** : Recherches web si necessaire (`Task(model: "sonnet", subagent_type: "general-purpose")`)
- **Regle** : Opus DECIDE quand deleguer. Jamais deleguer l'analyse des resultats ou les decisions.

---

*Ce CLAUDE.md est géré depuis `mon-ipad/directives/repos/rag-tests.md` — ne pas éditer directement.*
