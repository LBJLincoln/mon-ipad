# Multi-RAG Orchestrator — Tour de Contrôle Centrale

> Last updated: 2026-03-07T14:30:00Z

**CE REPO (`mon-ipad`) EST LA TOUR DE CONTRÔLE.**
VM Google Cloud permanente · Claude Code via Termius · Pilote 7 repos satellites

**MODÈLE PRINCIPAL : `claude-opus-4-6` (abonnement Max) — Analyse, décisions, pilotage.**
**DELEGATION : Sonnet 4.5 (execution) + Haiku 4.5 (exploration) via Task tool — UNIQUEMENT quand Opus le juge pertinent.**

---

## 1. IDENTITY

Tu es Claude Code (`claude-opus-4-6`) exécuté dans **Termius** connecté à la **VM Google Cloud** (`34.136.180.66`). Tu pilotes l'ensemble du projet Multi-RAG depuis cette machine permanente.

| Tâche | Modèle | Mécanisme |
|-------|--------|-----------|
| Analyse, décisions, pilotage | **Opus 4.6** | Direct (toi) |
| Recherches web, batch commands, génération | Sonnet 4.5 | `Task(model: "sonnet")` |
| Exploration codebase, vérifications | Haiku 4.5 | `Task(model: "haiku")` |

**JAMAIS déléguer** : analyse workflows, décisions debug, rédaction directives, évaluation résultats, communication utilisateur.

---

## 2. QUICK START

### Démarrage session (OBLIGATOIRE)
```bash
cat directives/PROJECT-STATE.md
cat technicals/DEBUG-PLAYBOOK.md | head -100
source .env.local
```

### Priorités (STRICT)
1. Pipelines critiques down
2. RAG tests + dashboard live
3. Sites/chatbot UX
4. Démos/contenu marketing

### Boucle d'exécution
1. Diagnostiquer → 2. Un seul fix → 3. Tester incrémental → 4. Comparer golden evals → 5. Commit+push → 6. MAJ `directives/PROJECT-STATE.md`

---

## 3. STATE FILES

| Fichier | Rôle | MAJ |
|---------|------|-----|
| `directives/PROJECT-STATE.md` | Mémoire de travail + résumé session | Après chaque milestone |
| `directives/PROCESS-RUNBOOKS.md` | Processus, endpoints, méthodologie | Quand process change |
| `technicals/DEBUG-PLAYBOOK.md` | Fixes library + knowledge base + diagnostic | Pendant session |
| `technicals/INFRASTRUCTURE.md` | Stack, credentials, env vars, limites | Quand infra change |
| `technicals/PROJECT-ROADMAP.md` | Phases, roadmap, bottlenecks, recherche | Quand stratégie change |
| `docs/status.json` | Métriques live (auto-généré) | Ne PAS éditer |
| `docs/data.json` | Dashboard data (auto-généré) | Ne PAS éditer |

---

## 4. CORE RULES

1. **Read before act** — `DEBUG-PLAYBOOK.md` avant debug, `PROJECT-STATE.md` avant action complexe
2. **source .env.local** — TOUJOURS avant scripts Python
3. **ZERO credentials in git** — `git diff --cached | grep -iE 'sk-or-|pcsk_|jV_zGdx|sbp_|hf_|jina_|ghp_'`
4. **1 fix per iteration** — Jamais plusieurs noeuds simultanément
5. **5/5 before sync** — `quick-test.py --questions 5` avant `n8n/sync.py`
6. **Commit + push regularly** — Toutes les 15-20 min. Git email: `alexis.moret6@outlook.fr`
7. **Update state files** — `PROJECT-STATE.md` après milestone
8. **VM = pilotage ONLY** — No n8n, no eval compute. Tout → HF Space
9. **Push before shutdown** — Codespaces éphémères : résultats vers GitHub AVANT arrêt
10. **3+ regressions → REVERT**
11. **Auto-stop on 3 failures** — Rapport structuré, pas de boucle infinie

---

## 5. INFRASTRUCTURE

### VM Google Cloud (pilotage ONLY)
```
IP: 34.136.180.66 | Debian 11 | 1 vCPU | 969 MB RAM | 30 GB disk
N8N_HOST: https://lbjlincoln-nomos-rag-engine.hf.space
```

### HF Spaces — 4 n8n + 1 LiteLLM + 1 Embeddings
5 n8n Spaces (1,3,5,7,9). Space #7 = LiteLLM proxy. `nomos-embeddings-api` = self-hosted Jina.

### Databases
| Service | Contenu | Limite |
|---------|---------|--------|
| Pinecone sota-rag-jina-1024 | 46,634 vecteurs (benchmarks) | 100K max |
| Pinecone website-sectors-jina-1024 | 31,937 vecteurs (secteurs) | 100K max |
| Neo4j Aura | ~86,841 nodes, enrichment 95% | 200K/400K |
| Supabase | 11,387 sector docs + 3,876 financial tables | 500MB |

### Batch sizes (auto mode)
| Pipeline | Batch | Concurrency | Timeout |
|----------|-------|-------------|---------|
| Standard | 10 | 5 | 90s |
| Graph | 5 | 3 | 90s |
| Quantitative | 3 | 1 | 120s |
| Orchestrator | 2 | 1 | 180s |

**Détails complets** : `technicals/INFRASTRUCTURE.md`

---

## 6. PIPELINES RAG

### Webhooks
| Pipeline | Webhook Path | Status |
|----------|-------------|--------|
| Standard | `/webhook/rag-multi-index-v3` | WORKING |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | WORKING |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | WORKING |
| Orchestrator | `/webhook/orchestrator-v2` | **WORKING (V11 S91)** |

### Active Workflow IDs
| Pipeline | ID | Name |
|----------|----|------|
| Standard | `TmgyRP20N4JFd9CB` | WF5 Standard RAG V3.4 (Groq direct) |
| Graph | `6257AfT1l4FMC6lY` | WF2 Graph RAG V3.3 (Groq direct) |
| Quant | `cjhEhVs0KV1ExHqX` | WF4 Quant V3.1 (LiteLLM) |
| Orchestrator | `ALd4gOEqiKL5KR1p` | **V11 Minimal (Groq routing) — RESTORED S91** |

### Phase Results
| Phase | Standard | Graph | Quant | Orch |
|-------|----------|-------|-------|------|
| Phase 1 (200q) | 85.5% | 78.0% | 92.0% | 80.0% |
| Phase 3 (10K) | **87.5%** | 40.9% | **95.2%** | ON HOLD |
| **Phase 5 Sector (220q)** | **25% baseline** | **25%** | **25%** | **TODO** |

**BLOCAGE** : Pipelines query `sota-rag-jina-1024` (benchmarks). Fix : router vers `website-sectors-jina-1024`.

### LLM Models (free tier)
| Modèle | Rôles | Coût |
|--------|-------|------|
| `meta-llama/llama-3.3-70b-instruct:free` | SQL, Intent, Planning, HyDE, QA | $0 |
| `google/gemma-3-27b-it:free` | Fast, Lite | $0 |
| `arcee-ai/trinity-large-preview:free` | Extraction, Summaries | $0 |

---

## 7. COMMANDS

```bash
# Eval
source .env.local
python3 eval/quick-test.py --questions 5 --pipeline <cible>
python3 eval/sector-eval.py --all-pipelines --questions 220   # Sector eval (Phase 5)
python3 eval/run-eval-parallel.py --dataset phase-3 --types standard,graph --reset --label "..."
python3 eval/node-analyzer.py --execution-id <ID>
python3 eval/generate_status.py

# Git
git push origin main
bash scripts/push-directives.sh           # Sync CLAUDE.md → satellites
python3 n8n/sync.py                       # Sync workflows

# n8n analysis
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
python3 scripts/n8n-api.py list           # List workflows (cookie auth)

# Codespaces
scripts/codespace-control.sh list|launch|status|stop|results
```

---

## 8. REPOS (7)

| Repo | Rôle | Directive |
|------|------|-----------|
| **mon-ipad** (CE REPO) | Pilotage, eval, MCP | Ce fichier |
| **rag-tests** | Datasets, résultats eval | `directives/repos/rag-tests.md` |
| **rag-website** | Next.js, 4 secteurs, chatbots | `directives/repos/rag-website.md` |
| **rag-dashboard** | HTML/JS métriques | `directives/repos/rag-dashboard.md` |
| **rag-data-ingestion** | Ingestion V4, 34K records | `directives/repos/rag-data-ingestion.md` |
| **rag-pme-connectors** | Next.js 15, 15 apps | — |
| **rag-storage** | GitHub LFS archive | — |

---

## 9. DETAILED DOCS

| Fichier | Contenu |
|---------|---------|
| `technicals/INFRASTRUCTURE.md` | Stack, credentials, env vars, limites, storage |
| `technicals/PROJECT-ROADMAP.md` | Phases, roadmap, bottlenecks, recherche SOTA |
| `technicals/DEBUG-PLAYBOOK.md` | 75+ fixes, knowledge base, diagnostic flowchart |
| `technicals/data/sector-datasets.md` | 1000+ types documents par secteur |
| `directives/PROJECT-STATE.md` | État courant, pipelines, infra, next steps |
| `directives/PROCESS-RUNBOOKS.md` | Processus, endpoints, méthodologie |
| `directives/repos/` | Directives par repo satellite |
| `docs/executive-summary.md` | Résumé global projet |

---

## État actuel v8.0 (Session 91 — 2026-03-09)

**Déploiement** : 7 HF Spaces UP, **4/4 pipelines WORKING** (Orch V11 restored)
**Phase 5 Sector** : Baseline **25%** — pipelines query wrong index (fix en cours)
**Monetisation** : Whop + RapidAPI + Gumroad scripts prêts, 17 produits Stripe
**Sessions** : 91 | **Commits** : 1,100+
