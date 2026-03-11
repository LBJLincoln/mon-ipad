# Process Runbooks — Multi-RAG Orchestrator

> Last updated: 2026-03-07T14:00:00Z

---

## Table of Contents

1. [Objective & Mission](#objective--mission)
2. [Standard Iteration Process](#standard-iteration-process)
3. [n8n API Endpoints Reference](#n8n-api-endpoints-reference)
4. [Dataset Rationale](#dataset-rationale)
5. [Research Methodology](#research-methodology)

---

## Objective & Mission

### Vision Globale

Construire un **Multi-RAG Orchestrator SOTA** capable de router intelligemment des questions vers 4 pipelines RAG spécialisées (Standard, Graph, Quantitative, Orchestrator) et d'atteindre des performances state-of-the-art sur des benchmarks HuggingFace progressifs.

**Cible finale**: 1M+ questions, accuracy > 75% overall, coût $0 en LLM.

### Rôles par Repo

| Repo | Rôle | Localisation | n8n |
|------|------|--------------|-----|
| **mon-ipad** | Pilotage, stockage n8n final, sync GitHub/VM | VM Google Cloud (34.136.180.66) | HF Space #1 |
| **rag-tests** | Exécuter tests, mesurer accuracy, rapporter résultats | VM → HF Space webhooks | HF Space #1 |
| **rag-website** | Site business, chatbots sectoriels, dashboard SSE live | Codespace + Vercel | Standalone local |
| **rag-data-ingestion** | Télécharger datasets HF, ingérer dans BDD séparées | Codespace | Local complet (2 workers) |
| **rag-dashboard** | Dashboard technique affichant métriques en temps réel | Vercel (statique) | AUCUN |
| **rag-pme-connectors** | Next.js 15, 15 apps, MacBook chat | Codespace + Vercel | AUCUN |
| **rag-pme-usecases** | Next.js 14, 200 use cases | Vercel | AUCUN |

### Pipelines RAG (4)

| Pipeline | Role | Base de données | Webhook | Target Phase 1 |
|----------|------|-----------------|---------|----------------|
| **Standard** | RAG vectoriel classique | Pinecone (21,073 vecteurs) | `/webhook/rag-multi-index-v3` | >= 85% |
| **Graph** | RAG sur graphe d'entités | Neo4j (~70K nodes) | `/webhook/ff622742-...` | >= 70% |
| **Quantitative** | RAG SQL sur tables | Supabase (40 tables) | `/webhook/3e0f8010-...` | >= 85% |
| **Orchestrator** | Route vers les 3 pipelines | Meta-pipeline | `/webhook/92217bb8-...` | >= 70% |

### Plan Global en 4 Phases

```
PHASE A : RAG Pipeline Iteration (prioritaire)
  Phase 1 (200q) ← PASSED (83.9%)
  Phase 2 (1000q) ← PARTIAL (Graph 78%, Quant 92% DONE)
  Phase 3 (~10Kq) ← IN PROGRESS (Std 87.5%, Graph 40.9%, Quant INVALID)
  Phase 4 (~100Kq) → Phase 5 (1M+)

PHASE B : Analyse SOTA 2026 (recherche académique)
  Papiers récents → Techniques SOTA → Design optimisé
  FAIT (session 13) — voir technicals/project/rag-research-2026.md

PHASE C : Ingestion & Enrichment
  14 benchmarks HuggingFace + 20 datasets sectoriels
  COMPLETE — 34,095 records, 31,916 sector vectors

PHASE D : Production & Déploiement
  Site business + Dashboard live + Monitoring
  MVP LIVE — Vercel deployed
```

---

## Standard Iteration Process

### ÉTAPE 0 — Pre-vol Checklist (OBLIGATOIRE)

#### 0.A Consulter la Bibliothèque de Fixes

**AVANT tout debug, TOUJOURS consulter `technicals/debug/fixes-library.md` en premier.**

```bash
cat technicals/debug/fixes-library.md
```

**Pourquoi**: 71+ bugs critiques ont été résolus sur ce projet. La majorité des nouveaux symptômes sont des récurrences ou variantes de bugs connus. Consulter la bibliothèque évite de re-debugger des problèmes déjà résolus.

**Utilisation**:
1. Identifier le symptôme (HTTP 500, boucle infinie, credential manquante, skip_graph, PUT 400...)
2. Chercher dans le tableau **PIÈGES RÉCURRENTS** → solution immédiate
3. **Si le symptôme correspond à un fix connu → appliquer directement SANS re-analyser**
4. Si le symptôme est nouveau → debugger normalement, puis documenter le fix dans la bibliothèque
5. **Consulter les 2-3 dernières versions réussies** de ce pipeline dans `snapshot/working-session{N}/`

#### 0.B Consulter Knowledge Base Section 0

**Consulter `technicals/debug/knowledge-base.md` Section 0 QUICK REFERENCE** pour les webhook paths, field names et méthodes d'authentification.

| Pipeline | Webhook Path | Field | Méthode |
|----------|-------------|-------|---------|
| Standard | `/webhook/rag-multi-index-v3` | query | POST |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | query | POST |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | query | POST |
| Orchestrator | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | query | POST |

**IMPORTANT**: Ne JAMAIS modifier de workflow sur la VM. Utiliser HF Space via REST API ou MCP.

#### 0.C Protocole Auto-Stop (3 échecs consécutifs)

Si un pipeline enchaîne **3 échecs consécutifs** sur le même type d'erreur:
1. **STOP** — ne pas retenter le même fix
2. Documenter le pattern dans `logs/diagnostics/`
3. Analyser avec les 2 outils (node-analyzer + analyze_n8n_executions)
4. Consulter `technicals/project/team-agentic-process.md` pour la procédure complète

#### 0.D Mise à Jour Obligatoire

Après chaque fix réussi (5/5 PASS) → ajouter l'entrée dans `technicals/debug/fixes-library.md`:
- Numéro de fix suivant
- Session + date
- Pipeline concerné
- Symptôme exact
- Root cause
- Fix appliqué (code si pertinent)
- Fichier impacté

---

### Démarrage de Session

```bash
cat directives/PROJECT-STATE.md              # État actuel
cat directives/PROCESS-RUNBOOKS.md           # Process (ce fichier)
cat technicals/debug/knowledge-base.md       # Cerveau persistant
cat technicals/debug/fixes-library.md        # 71+ fixes documentés
source .env.local                            # Load env vars
python3 eval/generate_status.py              # Régénérer status.json
python3 eval/phase_gates.py                  # Gates passées ?
```

---

### Boucle d'Itération (OBLIGATOIRE)

#### Étape 1: Test 1/1 (Smoke Test)

```bash
python3 eval/quick-test.py --questions 1 --pipeline <cible>
```

- **IMPORTANT**: Use incremental saves with preflight checks (deduplication active by default)
- **--no-force policy**: Never use --force flag, always preserve existing test results
- Si erreur → analyser node-par-node AVANT tout fix
- Si succès → passer à 5/5

#### Étape 2: Test 5/5 (Validation)

```bash
# Pipeline spécifique:
python3 eval/quick-test.py --questions 5 --pipelines <cible>

# Tous les pipelines (séquentiel dans le même process, évite les 503):
python3 eval/quick-test.py --questions 5 --pipelines standard,graph,quantitative,orchestrator
```

**IMPORTANT**: Ne JAMAIS lancer plusieurs instances de quick-test.py en parallèle → 503 n8n overload.
Utiliser `--pipelines p1,p2,p3` dans un seul appel (exécution séquentielle interne).

**Analyse granulaire OBLIGATOIRE** avec **LES DEUX OUTILS**:

```bash
# Pour chaque question, exécuter LES DEUX commandes:

# Analyse 1: node-analyzer.py (diagnostics automatiques)
python3 eval/node-analyzer.py --execution-id <ID>

# Analyse 2: analyze_n8n_executions.py (données brutes complètes) — OBLIGATOIRE
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
```

- Documenter: quel nœud, quel input, quel output, pourquoi c'est faux
- Si >= 3/5 correct → passer à 10/10
- Si < 3/5 → fixer UN nœud → retester 5/5

#### Étape 3: Test 10/10 (Gate)

```bash
# Eval progressive avec tous les pipelines:
python3 eval/run-eval-parallel.py --max 10 --reset --label "fix-description"
# ↑ Lance standard/graph/quantitative en parallèle, orchestrator après.
#   Questions séquentielles au sein de chaque pipeline → pas de 503.

# OU eval itérative (plus lent mais plus détaillé):
python3 eval/iterative-eval.py --label "fix-description" --questions 10
```

**Analyse granulaire OBLIGATOIRE** avec **LES DEUX OUTILS**:

```bash
python3 eval/node-analyzer.py --execution-id <ID>
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
```

- Si >= 7/10 → session validée pour ce pipeline
- Si < 7/10 → itérer (retour étape 2)

#### Étape 4: Gate 10/10 Atteinte

```bash
# Analyse complète des exécutions avec les deux outils
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

### Analyse Granulaire Node-par-Node (DOUBLE ANALYSE OBLIGATOIRE)

#### ANALYSE 1: node-analyzer.py (Diagnostics automatiques)

```bash
# Dernières 5 exécutions d'un pipeline
python3 eval/node-analyzer.py --pipeline <cible> --last 5

# Exécution spécifique
python3 eval/node-analyzer.py --execution-id <ID>

# Analyse complète (tous pipelines)
python3 eval/node-analyzer.py --all --last 5
```

**Fournit**:
- Détection automatique d'issues (verbose LLM, slow nodes, erreurs)
- Recommandations priorisées
- Health scores par node
- Rapport de latence (avg, p95)

#### ANALYSE 2: analyze_n8n_executions.py (Données brutes complètes)

```bash
# Exécution spécifique (OBLIGATOIRE pour chaque question)
python3 scripts/analyze_n8n_executions.py --execution-id <ID>

# Dernières exécutions d'un pipeline
python3 scripts/analyze_n8n_executions.py --pipeline <cible> --limit 5

# Pipelines disponibles: standard, graph, quantitative, orchestrator
```

**Fournit**:
- **Données brutes complètes** (full_input_data, full_output_data)
- **Extraction LLM détaillée**: content complet, tokens, modèle, provider
- **Flags de routage**: skip_neo4j, skip_graph, fallback, etc.
- **Metadata de retrieval**: nombre de documents, scores, warnings

#### Comparaison des Deux Outils

| Aspect | node-analyzer.py | analyze_n8n_executions.py |
|--------|------------------|---------------------------|
| **Type** | Diagnostic automatique | Extraction brute complète |
| **Issues détectées** | Auto (verbose, slow, errors) | Manuelle |
| **Données brutes** | Preview tronquée | Complète (JSON intégral) |
| **Recommandations** | Auto-générées | Non |
| **LLM content** | Preview 3000 chars | Complet |
| **Fichier de sortie** | logs/diagnostics/ | n8n/analysis/ |
| **Usage principal** | Vue d'ensemble rapide | Debugging profond |

#### Checklist d'Analyse pour CHAQUE Question

**1. Intent Analyzer**
- [ ] La question a-t-elle été correctement classée ?
- [ ] Quel est le output de l'Intent Analyzer ? (via **analyze_n8n_executions.py**)

**2. Query Router**
- [ ] A-t-elle été envoyée au bon pipeline ?
- [ ] Quelle est la décision de routage ? (via **analyze_n8n_executions.py**)

**3. Retrieval (Pinecone/Neo4j/Supabase)**
- [ ] Combien de documents récupérés ?
- [ ] Scores de pertinence ?
- [ ] Résultats vides ?
- [ ] **Vérification via les deux outils**

**4. LLM Generation**
- [ ] Le prompt est-il correct ? (via **analyze_n8n_executions.py** - full_input_data)
- [ ] La réponse est-elle fidèle au contexte ?
- [ ] Hallucination ?
- [ ] Tokens utilisés ?

**5. Response Builder**
- [ ] La réponse finale correspond-elle à la sous-réponse ?
- [ ] Perte d'information ?
- [ ] **Vérification via les deux outils**

#### Avant TOUT Fix, Répondre à:

- [ ] **Consulté technicals/debug/fixes-library.md ?** → symptôme déjà connu ? (OBLIGATOIRE)
- [ ] Quel nœud exact cause le problème ? **(confirmé par les DEUX outils)**
- [ ] Qu'est-ce que le nœud reçoit en input ? **(via analyze_n8n_executions.py)**
- [ ] Qu'est-ce qu'il produit en output ? **(via analyze_n8n_executions.py)**
- [ ] Pourquoi cet output est-il faux ?
- [ ] Quel changement de code dans ce nœud va corriger le problème ?

---

### Stratégie de Test Parallèle

#### Principe

n8n sur HF Space supporte ~2-3 requêtes simultanées. Au-delà → 503 Service Unavailable.

#### Approche Correcte par Phase de Test

| Phase | Méthode | Script |
|-------|---------|--------|
| **1/1 smoke** | UN pipeline à la fois | `quick-test.py --questions 1 --pipelines <cible>` |
| **5/5 validation** | Tous pipelines, séquentiel | `quick-test.py --questions 5 --pipelines standard,graph,quantitative,orchestrator` |
| **10/10 gate** | Parallèle stagger | `run-eval-parallel.py --max 10 --reset --label "..."` |
| **200q full** | Parallèle stagger | `run-eval-parallel.py --reset --label "..."` |

#### Parallèle Stagger (run-eval-parallel.py)

- Standard, Graph, Quantitative → threads parallèles (questions séquentielles par pipeline)
- Orchestrator → après les 3 autres (il appelle les sub-workflows)
- Rate-limit backoff automatique (3s sur 429)
- `--workers 1` pour forcer séquentiel si nécessaire
- `--delay 10` pour espacement entre questions si free models rate-limitent
- `--early-stop 4`: arrête un pipeline après 4 échecs consécutifs (défaut actif)
- `--early-stop 0`: désactive l'arrêt prématuré

#### Timeouts par Pipeline

| Pipeline | Timeout | Justification |
|----------|---------|---------------|
| **Standard** | 120s | avg ~30s, max ~90s, marge +30s |
| **Graph** | 120s | avg ~50s, max ~90s, marge +30s |
| **Quantitative** | 120s | avg ~40s, max ~90s, marge +30s |
| **Orchestrator** | 360s | avg ~200s, max ~300s, marge +60s |

#### Background Testing (OBLIGATOIRE pour runs 50q+)

**Principe**: Les tests qui passent tournent en background. L'agent se concentre sur les problèmes.

```bash
# Pattern: lancer les pipelines fonctionnels en background
N8N_HOST="$HF_SPACE_URL" nohup python3 eval/run-eval-parallel.py \
  --dataset phase-2 --types standard,graph,orchestrator \
  --force --early-stop 0 --workers 3 \
  --label "Phase2-background" \
  > /tmp/phase2-run.log 2>&1 &

# Auto-commit périodique (toutes les 15 min)
nohup bash -c 'while true; do sleep 900; \
  python3 eval/generate_status.py > /dev/null 2>&1 && \
  git add docs/ && git commit -m "auto-commit" && git push; done' \
  > /tmp/periodic-commit.log 2>&1 &

# Monitorer: tail -f /tmp/phase2-run.log
```

**Quand un pipeline est bloqué**:
1. L'exclure du `--types`
2. Documenter le blocage dans knowledge-base.md
3. Lancer les autres pipelines en background
4. Se concentrer sur le diagnostic et la résolution du pipeline bloqué
5. Une fois fixé, relancer ce pipeline séparément avec dedup

---

### Fin de Session — Checklist

1. `technicals/` — MAJ si changements
2. `technicals/infra/env-vars-exhaustive.md` — MAJ si credentials changées
3. `snapshot/current/` — Sync workflows
4. `docs/data.json` — Régénérer via `generate_status.py`
5. `directives/PROJECT-STATE.md` — État final session
6. `bash scripts/check-staleness.sh` — Vérifier aucun fichier stale
7. **Commit + push** → origin ET repos satellites impactés

---

### Règles d'Or

1. **Consulter fixes-library.md EN PREMIER** — avant tout debug
2. **UN fix par itération** — jamais plusieurs nœuds/pipelines en même temps
3. **n8n est la source de vérité** — éditer dans n8n, sync vers GitHub via `n8n/sync.py`
4. **Analyse granulaire AVANT chaque fix** — **LES DEUX OUTILS sont OBLIGATOIRES**
5. **Vérifier AVANT de sync** — 5/5 doit passer avant de commit
6. **Commit + push après chaque fix réussi** — garder les agents en sync
7. **Si 3+ régressions → REVERT immédiat**
8. **MAJ fixes-library.md après chaque fix** — perpétuer la connaissance

---

## n8n API Endpoints Reference

### Configuration — HF Space #1 (Active)

```bash
# Single active HF Space (Space #1)
N8N_HOST=https://lbjlincoln-nomos-rag-engine.hf.space
# Auth: Cookie-based (scripts/n8n-api.py helper)
# n8n: ci@nomos.ai / CI-Nomos-2026!
```

### HF Space Endpoints

| Space | URL | Account | Role | Status |
|-------|-----|---------|------|--------|
| Space 1 | https://lbjlincoln-nomos-rag-engine.hf.space | LBJLincoln | n8n (RAG pipelines) | **ACTIVE** |
| Space 7 | https://lbjlincoln-nomos-rag-engine-7.hf.space | LBJLincoln | LiteLLM Proxy (key rotation) | **ACTIVE** |
| Spaces 2-6, 8-10 | Various | Mixed | INACTIVE | **NOT DEPLOYED** |

> **NOTE**: Only Space #1 (n8n) and Space #7 (LiteLLM) are active. SQLite is used for n8n ephemeral workflow storage.

---

### LiteLLM Proxy (Space #7) — ALL PIPELINES ROUTE THROUGH THIS

```bash
LITELLM_URL=https://lbjlincoln-nomos-rag-engine-7.hf.space
LITELLM_KEY=sk-litellm-nomos-2026

# Health check
curl -s "$LITELLM_URL/health/liveliness"

# Chat completion (auto key/model rotation: OpenRouter + Gemini + Groq)
curl -s -X POST "$LITELLM_URL/v1/chat/completions" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"smart","messages":[{"role":"user","content":"test"}]}'

# Model groups (use 'smart' for all pipelines):
#   smart (13 providers) — OpenRouter llama-70b + qwen-235b + Gemini + Groq
#   default (10) — OpenRouter trinity + Gemini + Groq
#   fast (11) — OpenRouter trinity + gemma-27b + Gemini
#   llama-70b (12) — OpenRouter + Groq (5 keys)
#   gemma-27b (7) — OpenRouter only
#   gemini-flash (1) — Google direct
#   groq-llama (5) — Groq only (AVOID: no fallback, rate-limited)

# List all models
curl -s "$LITELLM_URL/v1/models" -H "Authorization: Bearer $LITELLM_KEY"
```

---

### Format de Requête pour Scripts Python (RÉFÉRENCE)

#### Format de Body Webhook (VÉRIFIÉ FONCTIONNEL)

```python
# Format qui FONCTIONNE — vérifié le 2026-03-03
# ATTENTION: le field name est "query" (PAS "question")
payload = {"query": "Your question here"}
# Content-Type: application/json
# Method: POST
```

> **PIÈGE RÉCURRENT**: Utiliser `question` au lieu de `query` provoque une VALIDATION_ERROR.
> Toujours utiliser `query` pour les 4 pipelines.

#### Pattern Python pour Appeler un Webhook

```python
import urllib.request, json

N8N_HOST = "https://lbjlincoln-nomos-rag-engine.hf.space"

def call_webhook(path, question, timeout=120):
    """Appel webhook n8n."""
    url = f"{N8N_HOST}{path}"
    payload = json.dumps({"query": question}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())
```

---

### REST API — Cookie Auth (Session 68 Discovery)

> **IMPORTANT**: n8n on HF Space does NOT support API key auth (JWT invalidates on rebuild).
> Use cookie-based auth via `scripts/n8n-api.py` helper.

#### Helper Script (Recommended)

```bash
source .env.local
python3 scripts/n8n-api.py list                          # List workflows
python3 scripts/n8n-api.py get <WF_ID>                   # Export workflow JSON
python3 scripts/n8n-api.py deploy n8n/live/workflow.json # Import workflow
python3 scripts/n8n-api.py activate <WF_ID>              # Activate webhook
python3 scripts/n8n-api.py exec <WF_ID>                  # Trigger execution
```

#### Raw REST API (Cookie Auth)

```bash
# 1. Login (get session cookie)
curl -s -c /tmp/n8n-cookies.txt -X POST "$N8N_HOST/rest/login" \
  -H "Content-Type: application/json" \
  -d '{"emailOrLdapLoginId":"ci@nomos.ai","password":"CI-Nomos-2026!"}'

# 2. List workflows
curl -s -b /tmp/n8n-cookies.txt "$N8N_HOST/rest/workflows"

# 3. Get workflow
curl -s -b /tmp/n8n-cookies.txt "$N8N_HOST/rest/workflows/<WF_ID>"

# 4. Update workflow (PATCH, not PUT)
curl -s -b /tmp/n8n-cookies.txt -X PATCH "$N8N_HOST/rest/workflows/<WF_ID>" \
  -H "Content-Type: application/json" \
  -d '{"nodes": [...], "connections": {...}}'

# 5. Activate (REQUIRED for webhooks — needs versionId!)
curl -s -b /tmp/n8n-cookies.txt -X POST "$N8N_HOST/rest/workflows/<WF_ID>/activate" \
  -H "Content-Type: application/json" \
  -d '{"versionId": "<VERSION_ID_FROM_PATCH_RESPONSE>"}'

# 6. Get executions
curl -s -b /tmp/n8n-cookies.txt "$N8N_HOST/rest/executions?workflowId=<WF_ID>&limit=5"
```

---

### Webhooks (Endpoints de Test — Verified 2026-03-07)

```bash
N8N_HOST=https://lbjlincoln-nomos-rag-engine.hf.space

# Standard RAG V3.8 (WORKING — 6/6 PASS, all sectors, via LiteLLM)
curl -s -X POST "$N8N_HOST/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"query": "Quels sont les ratios financiers pour evaluer la solvabilite?", "sector": "finance", "disable_acl": true}'

# Graph RAG V3.5 (WORKING — self-hosted embeddings + LiteLLM)
curl -s -X POST "$N8N_HOST/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelles entites sont liees aux normes IFRS?", "sector": "finance", "disable_acl": true}'

# Quantitative V3.2 (WORKING — SQL generation via LiteLLM)
curl -s -X POST "$N8N_HOST/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelles sont les 5 entreprises avec le plus gros revenu?", "sector": "finance", "disable_acl": true}'

# Orchestrator V13 (WORKING — routes to sub-pipelines)
curl -s -X POST "$N8N_HOST/webhook/orchestrator-v2" \
  -H "Content-Type: application/json" \
  -d '{"query": "Comment fonctionne la responsabilite delictuelle?", "sector": "juridique", "disable_acl": true}'
```

---

### Pièges Connus (Updated Session 75)

| Piège | Solution |
|-------|----------|
| `"query"` not `"question"` | Webhook body MUST use `query` field |
| API key auth doesn't work on HF Space | Use cookie auth (POST /rest/login) |
| PATCH needs versionId for reactivation | Get versionId from PATCH response → POST /activate |
| Disabled Code nodes pass through raw webhook data | Re-enable or fix downstream references |
| `$items('DisabledNode')` crashes | Wrap in try/catch for disabled/optional nodes |
| Jina rate limit 100K tokens/min | Pause background ingestion before testing pipelines |
| Duplicate workflows share webhook ID | Check execution's `workflowId` to find which is running (FIX-71) |
| Supabase tenant_id | Use `benchmark` (NOT `default`) |
| Postgres credential | Use `b44avEJtnkw46GL6` (NOT `cH96tQ3I9uIHqiiq`) |

---

## Dataset Rationale

### Pourquoi Ces Datasets ?

Notre système Multi-RAG est évalué sur 14 datasets soigneusement sélectionnés parmi les benchmarks les plus reconnus en 2024-2026.

### Vue d'Ensemble

| # | Dataset | Total Questions | Notre Échantillon | Pipeline | Source |
|---|---------|----------------|------------------|----------|--------|
| 1 | SQuAD 2.0 | 142,192 | 1,125 | Standard | Stanford, ACL 2018 |
| 2 | TriviaQA | 95,000+ | 1,209 | Standard | Joshi et al., ACL 2017 |
| 3 | PopQA | 14,267 | 1,208 | Standard | Mallen et al., 2023 |
| 4 | NarrativeQA | 46,765 | 1,208 | Standard | DeepMind, 2018 |
| 5 | PubMedQA | 211,269 | 625 | Standard | Jin et al., 2019 |
| 6 | FRAMES | 824 | 949 | Standard | Google, 2024 |
| 7 | Natural Questions | 307,372 | 1,208 | Standard | Google, TACL 2019 |
| 8 | MS MARCO | 1,010,916 | 1,000 | Standard | Microsoft, 2016 |
| 9 | ASQA | 6,316 | 948 | Standard | Stelmakh et al., 2022 |
| 10 | HotpotQA | 112,779 | 1,325 | Graph | Yang et al., EMNLP 2018 |
| 11 | MuSiQue | 25,000 | 267 | Graph | Trivedi et al., TACL 2022 |
| 12 | 2WikiMultihopQA | 192,606 | 367 | Graph | Ho et al., COLING 2020 |
| 13 | FinQA | 8,281 | 400 | Quantitative | Chen et al., EMNLP 2021 |
| 14 | TAT-QA | 16,552 | 233 | Quantitative | Zhu et al., ACL 2021 |
| **Total** | **~2,190,139** | **~11,072** | | |

### L'Échantillon de 11K Questions sur 2.19M

Notre échantillon de ~11,000 questions représente 0.5% du total disponible. C'est SUFFISANT car:
1. **Statistiquement significatif**: avec 11K questions, la marge d'erreur est < 1% (intervalle de confiance 95%)
2. **Diversité maximale**: les questions sont échantillonnées de manière stratifiée (par difficulté, type, domaine)
3. **Standard industriel**: BEIR benchmark utilise 5K-15K queries par dataset pour évaluation
4. **Pragmatique**: tester 2.19M questions prendrait ~4,500 heures (188 jours) — infaisable économiquement

### Validation par la Recherche

Nos 14 datasets sont validés par les benchmarks de référence suivants:

#### 1. BEIR — Benchmarking IR (Thakur et al., NeurIPS 2021)
**Paper**: "BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models"

BEIR est le benchmark de référence pour l'évaluation zero-shot des systèmes de retrieval. Il inclut 18 datasets dont 5 que nous utilisons: SQuAD, Natural Questions, HotpotQA, MS MARCO, et PubMedQA.

#### 2. MTEB — Massive Text Embedding Benchmark (Muennighoff et al., 2023)
**Paper**: "MTEB: Massive Text Embedding Benchmark" (EACL 2023)

MTEB est le leaderboard de référence pour les modèles d'embeddings (HuggingFace). Il inclut des tâches de retrieval basées sur nos datasets (SQuAD, NQ, MS MARCO, HotpotQA).

#### 3. CRAG — Comprehensive RAG Benchmark (Meta, 2024)
**Paper**: "CRAG: Comprehensive RAG Benchmark" (KDD Cup 2024)

CRAG de Meta recommande explicitement l'évaluation multi-domain et multi-hop pour les systèmes RAG. Notre sélection de 14 datasets couvre exactement ces deux axes.

#### 4. RAGBench (Galileo, 2024)
**Paper**: "RAGBench: Explainable Benchmark for Retrieval-Augmented Generation Systems"

RAGBench est le premier benchmark conçu nativement pour les systèmes RAG. Il valide notre approche d'évaluation par pipeline et notre méthodologie de scoring (correctness + faithfulness).

#### 5. FRAMES (Google, 2024)
**Paper**: "FRAMES: Factuality, Retrieval, And Multi-hop Evaluation for Summarization"

FRAMES est le benchmark le plus récent de notre sélection. Il représente l'état de l'art de l'évaluation RAG et teste des capacités que les benchmarks plus anciens ne couvrent pas.

### Couverture des Capacités RAG

| Capacité | Datasets qui la testent |
|----------|------------------------|
| Retrieval factuel | SQuAD, NQ, TriviaQA, MS MARCO |
| Long-tail knowledge | PopQA |
| Compréhension longue | NarrativeQA |
| Domaine spécialisé | PubMedQA (biomedical), FinQA/TAT-QA (finance) |
| Multi-document | FRAMES, ASQA |
| Multi-hop reasoning | HotpotQA (2-hop), MuSiQue (2-4 hop), 2Wiki (comparison) |
| Raisonnement numérique | FinQA, TAT-QA |
| Questions ambiguës | ASQA |
| Abstention (no answer) | SQuAD 2.0 |
| Distribution naturelle | NQ, MS MARCO |

### Phases de Test Progressives

| Phase | Questions | Datasets | Target |
|-------|-----------|----------|--------|
| 1 (Baseline) | 200 | Curated (4 fichiers) | std>=85%, graph>=70%, quant>=85% |
| 2 (Expand) | 1,200 | + HF graph/quant | graph>=60%, quant>=70% |
| 3 (Scale) | ~11,000 | All 14 datasets | std>=75%, graph>=55%, quant>=65% |
| 4 (Full HF) | ~100K | 10x échantillons | No regression |
| 5 (Production) | 1M+ | Full datasets | Production-ready |

---

## Research Methodology

### Principe Fondamental

**Toute recherche internet dans ce projet DOIT suivre cette méthodologie.**
Ce fichier est la source de vérité pour la façon dont les agents Claude Code effectuent des recherches dans TOUS les repos.

---

### 1. Sources Prioritaires (Par Ordre)

#### Tier 1 — Papiers de Recherche Académiques (OBLIGATOIRE)

| Source | URL | Ce qu'on y cherche |
|--------|-----|-------------------|
| **arXiv** | arxiv.org | Papiers RAG, NLP, LLM, embeddings, retrieval — toujours la version la plus récente |
| **Semantic Scholar** | semanticscholar.org | Citations croisées, impact factor, papiers connexes |
| **ACL Anthology** | aclanthology.org | Conférences NLP (ACL, EMNLP, NAACL, EACL) |
| **NeurIPS / ICML / ICLR** | proceedings officiels | ML/AI foundations |
| **Google Scholar** | scholar.google.com | Meta-recherche, citations, trending papers |

**Règle**: Un papier cité DOIT avoir un identifiant (arXiv ID, DOI, ou lien conférence).
Pas de "j'ai lu quelque part que..." — toujours une référence vérifiable.

#### Tier 2 — Blogs de Recherche des Labs Majeurs (SUIVI CONSTANT)

| Lab | Blog/Research | Fréquence de suivi | Focus |
|-----|--------------|-------------------|-------|
| **Anthropic** | anthropic.com/research | Hebdomadaire | Constitutional AI, RLHF, retrieval, safety |
| **OpenAI** | openai.com/research | Hebdomadaire | GPT, embeddings, file search, tool use |
| **Google DeepMind** | deepmind.google/research | Hebdomadaire | Gemini, PaLM, retrieval, multimodal |
| **xAI (Grok)** | x.ai/blog | Bi-hebdomadaire | Grok models, reasoning, real-time knowledge |
| **Meta AI (FAIR)** | ai.meta.com/research | Bi-hebdomadaire | Llama, open-source LLM, embeddings |
| **Jina AI** | jina.ai/news | Mensuel | Embeddings, reranking, late chunking |
| **Cohere** | cohere.com/research | Mensuel | Reranking, embed models, RAG |
| **Pinecone** | pinecone.io/learn | Mensuel | Vector DB, hybrid search, serverless |

#### Tier 3 — Documentation Technique Officielle

| Service | Docs | Ce qu'on y cherche |
|---------|------|-------------------|
| n8n | docs.n8n.io | Workflows, queue mode, API, best practices |
| Pinecone | docs.pinecone.io | SDK, sparse vectors, namespaces, serverless |
| Neo4j | neo4j.com/docs | Cypher, graph algorithms, Aura |
| Supabase | supabase.com/docs | PostgreSQL, Edge Functions, RLS |
| Jina | docs.jina.ai | Embeddings API, reranking, late chunking |

#### Tier 4 — Benchmarks et Leaderboards

| Leaderboard | URL | Utilité |
|-------------|-----|---------|
| MTEB | huggingface.co/spaces/mteb/leaderboard | Embedding models ranking |
| Open LLM Leaderboard | huggingface.co/spaces/open-llm-leaderboard | LLM models ranking |
| RAGAS | ragas.io | RAG evaluation metrics |
| Chatbot Arena | lmarena.ai | LLM quality comparative |

---

### 2. Méthodologie de Recherche

#### Étape 1: Formuler la Question de Recherche

```
MAUVAIS: "comment améliorer le RAG"
BON    : "techniques SOTA 2025-2026 pour améliorer la précision du retrieval
          dans un système RAG multi-pipeline avec embeddings Jina 1024-dim"
```

#### Étape 2: Rechercher sur arXiv + Semantic Scholar

```
Requêtes types:
- "RAG retrieval augmented generation 2025 2026"
- "hybrid search sparse dense retrieval"
- "graph RAG entity disambiguation"
- "financial table question answering SQL generation"
- "late chunking contextual retrieval"
- "reranking cross-encoder 2026"
```

#### Étape 3: Croiser avec les Blogs des Labs

Vérifier si Anthropic, OpenAI, Google ou xAI ont publié quelque chose de pertinent dans les 3 derniers mois sur le sujet.

#### Étape 4: Documenter avec Références

```markdown
## Technique: [Nom]
- **Papier**: [Titre] (arXiv:XXXX.XXXXX, [Auteurs], [Date])
- **Lab**: [Anthropic/OpenAI/Google/Meta/...]
- **Impact estimé**: [+X% accuracy / -Xs latency / ...]
- **Coût**: $0 (gratuit) / $X/mois
- **Faisabilité**: HIGH/MEDIUM/LOW
- **Implementation**: [Description concrète dans notre stack]
```

#### Étape 5: Valider la Gratuité

**RÈGLE ABSOLUE**: Toute technique proposée DOIT être implémentable à $0.
Si un papier propose une technique nécessitant un modèle payant, chercher l'équivalent open-source/gratuit:
- GPT-4 → Llama 70B (gratuit via OpenRouter)
- Claude → Gemma 27B (gratuit via OpenRouter)
- Cohere Embed v3 → Jina Embeddings v3 (gratuit 1M tokens/mois)
- OpenAI Embeddings → Jina ou multilingual-e5-large (gratuit)

---

### 3. Suivi Continu des Labs (OBLIGATOIRE)

#### Check-list de Suivi (à Chaque Session de Recherche)

- [ ] Anthropic Research: nouveau papier ou blog post ?
- [ ] OpenAI Research: nouveau modèle, technique, ou API ?
- [ ] Google DeepMind: Gemini update, nouveau benchmark ?
- [ ] xAI (Grok): nouveau modèle Grok, technique de reasoning ?
- [ ] Meta AI: nouveau Llama, technique open-source ?
- [ ] Jina AI: nouveau embedding model, late chunking update ?

---

### 4. Ce qui est INTERDIT

1. **Pas de sources non-académiques** comme seule référence (blog random, tutorial Medium)
2. **Pas de techniques non-vérifiées** — tout doit avoir un papier ou un benchmark
3. **Pas de solutions payantes** sans alternative gratuite documentée
4. **Pas de "j'ai entendu dire"** — référence ou rien
5. **Pas de papiers avant 2024** sauf classiques fondateurs (Attention Is All You Need, etc.)

---

### 5. Application par Repo

| Repo | Quand rechercher | Quoi rechercher |
|------|-----------------|-----------------|
| **mon-ipad** | À chaque session | SOTA RAG, infrastructure, benchmarks |
| **rag-tests** | Avant chaque fix pipeline | Technique spécifique au pipeline en échec |
| **rag-website** | Avant ajout secteur | UX/RAG chatbot, sector-specific RAG |
| **rag-data-ingestion** | Avant chaque ingestion | Chunking SOTA, enrichment techniques |
| **rag-dashboard** | Rarement | Dataviz best practices |

---

### 6. Template de Recherche (à Copier)

```markdown
# Recherche: [Sujet]
Date: YYYY-MM-DD
Repo: [mon-ipad/rag-tests/...]

## Question de recherche
[Question précise]

## Sources consultées
1. arXiv: [requête] → [X résultats pertinents]
2. Semantic Scholar: [requête] → [X résultats]
3. [Lab] Blog: [URL] → [pertinent/non pertinent]

## Papiers retenus
### [Papier 1]
- arXiv: XXXX.XXXXX
- Auteurs: [...]
- Date: [...]
- Technique: [...]
- Impact estimé: [...]
- Gratuit: OUI/NON (si NON, alternative gratuite: [...])

## Recommandation
[Action concrète à implémenter]

## Références
- [1] [Citation complète]
- [2] [Citation complète]
```

---

**END OF PROCESS RUNBOOKS**
