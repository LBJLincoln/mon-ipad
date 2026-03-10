# Nomos Sector AI Expert — Tour de Controle

> Last updated: 2026-03-10T21:00:00Z

**CE REPO (`mon-ipad`) EST LA TOUR DE CONTROLE.**
VM Google Cloud permanente . Claude Code via Termius . Pilote 5 repos actifs + 2 archives

**MISSION : Construire le meilleur assistant IA expert sectoriel au monde sur 4 secteurs.**
**Chaque pipeline doit devenir un expert imbattable dans son domaine.**

**MODELE PRINCIPAL : `claude-opus-4-6` (abonnement Max)**
**DELEGATION : Sonnet 4.6 (execution) + Haiku 4.5 (exploration) via Task tool**

---

## 1. IDENTITY & MISSION

Tu es Claude Code (`claude-opus-4-6`) executant depuis **Termius** sur la **VM Google Cloud** (`34.136.180.66`).

**Mission** : Transformer nos 4 pipelines RAG en experts sectoriels de classe mondiale capables de traiter les documents les plus complexes de chaque industrie et de repondre avec la precision d'un expert senior.

| Tache | Modele | Mecanisme |
|-------|--------|-----------|
| Analyse, decisions, pilotage | **Opus 4.6** | Direct (toi) |
| Recherches web, batch commands | Sonnet 4.6 | `Task(model: "sonnet")` |
| Exploration codebase | Haiku 4.5 | `Task(model: "haiku")` |

**JAMAIS deleguer** : analyse workflows, decisions debug, redaction directives, evaluation resultats, communication utilisateur.

---

## 2. DEUX AXES STRATEGIQUES

### AXE 1 : Expert IA Sectoriel (priorite technique)
- 4 secteurs : **Finance**, **BTP**, **Juridique**, **Industrie**
- 4 pipelines RAG specialisees tournant en continu
- Ingestion capable de traiter 100+ types de documents, les plus complexes
- Scale a 1M documents par secteur
- Evals parfaits mesurant la qualite expert
- Self-healing : pipelines cassees se reparent, bonnes pipelines testent en continu

### AXE 2 : Monetisation (priorite revenue)
- Directives separees (fournies par l'utilisateur)
- Infra deja prete : 19 Stripe + 14 Whop + RapidAPI + 20 packages ZIP
- Focus : pourquoi pas de revenue ? restructurer autour de ce qui vend

### Priorites session (STRICT)
1. Pipelines DOWN → diagnostiquer + reparer
2. Pipelines UP → lancer evals continus jusqu'aux objectifs
3. Ingestion → nouveaux documents complexes
4. Monetisation → selon directives utilisateur

---

## 3. SECTEURS & OBJECTIFS

### Accuracy Targets (AMBITIEUX)

| Secteur | Standard | Graph | Quant | Orchestrator | Current Best |
|---------|----------|-------|-------|-------------|-------------|
| **Finance** | >= 90% | >= 75% | >= 95% | >= 85% | Std 80%, Quant 95.2% |
| **BTP** | >= 85% | >= 70% | >= 80% | >= 75% | Std 20% (DATA GAP) |
| **Juridique** | >= 90% | >= 80% | N/A | >= 80% | Std 80% |
| **Industrie** | >= 85% | >= 70% | >= 80% | >= 75% | Std 80% |

### Quality Targets (Expert-level)

| Metric | Target | Current |
|--------|--------|---------|
| Source citation | >= 90% answers cite specific document | ~50% |
| Sector terminology | >= 80% use correct professional terms | ~60% |
| Response language match | 100% respond in question language | ~85% |
| Response time | <= 30s average | ~36s |
| Complex document handling | 100+ doc types per sector | ~20 types |

### Data Scale Targets

| Secteur | Pinecone Vectors | Supabase Docs | Neo4j Nodes | Target 6mo |
|---------|-----------------|---------------|-------------|-----------|
| Finance | ~10K | 2,150 | ~20K | 250K total |
| BTP | ~8K | 1,844 | ~15K | 200K total |
| Juridique | ~8K | 2,500 | ~25K | 300K total |
| Industrie | ~6K | 1,015 | ~10K | 250K total |

### Sector Config Files

| Fichier | Contenu |
|---------|---------|
| `sectors/finance/` | Eval questions, golden answers, doc type registry |
| `sectors/btp/` | Eval questions, golden answers, doc type registry |
| `sectors/juridique/` | Eval questions, golden answers, doc type registry |
| `sectors/industrie/` | Eval questions, golden answers, doc type registry |
| `sectors/eval-datasets/` | Master eval dataset (220+ questions) |

---

## 4. CORE RULES

1. **Read before act** — `DEBUG-PLAYBOOK.md` avant debug, `PROJECT-STATE.md` avant action complexe
2. **source .env.local** — TOUJOURS avant scripts Python
3. **ZERO credentials in git** — `git diff --cached | grep -iE 'sk-or-|pcsk_|jV_zGdx|sbp_|hf_|jina_|ghp_'`
4. **1 fix per iteration** — Jamais plusieurs noeuds simultanement
5. **Sector smoke before sync** — `quick-test.py --sector all` avant `n8n/sync.py`
6. **Commit + push regularly** — Toutes les 15-20 min. Git email: `alexis.moret6@outlook.fr`
7. **Update state files** — `PROJECT-STATE.md` apres milestone
8. **VM = pilotage ONLY** — No n8n, no eval compute. Tout sur HF Spaces
9. **Push before shutdown** — Codespaces ephemeres : resultats vers GitHub AVANT arret
10. **3+ regressions → REVERT**
11. **Auto-stop on 3 failures** — Rapport structure, pas de boucle infinie
12. **10% improvement per session** — Chaque session doit ameliorer le secteur le plus faible
13. **Self-healing first** — Pipeline cassee = priorite absolue avant tout autre travail
14. **Continuous eval** — Bonnes pipelines tournent leurs tests 24/7 jusqu'aux objectifs

---

## 5. INFRASTRUCTURE

### VM Google Cloud (pilotage ONLY)
```
IP: 34.136.180.66 | Debian 11 | 1 vCPU | 969 MB RAM | 30 GB disk
```

### HF Spaces (10 slots — maximiser utilisation)

| Space | Role | URL | Status |
|-------|------|-----|--------|
| engine (S1) | n8n primary — Standard + Graph | lbjlincoln-nomos-rag-engine.hf.space | UP |
| engine-3 (S3) | n8n secondary — load balancing | lbjlincoln-nomos-rag-engine-3.hf.space | UP |
| engine-5 (S5) | n8n tertiary — eval dedicated | lbjlincoln-nomos-rag-engine-5.hf.space | UP |
| engine-7 (S7) | LiteLLM proxy — 9 models, key rotation | lbjlincoln-nomos-rag-engine-7.hf.space | CHECK |
| engine-9 (S9) | n8n quaternary — overflow | lbjlincoln-nomos-rag-engine-9.hf.space | UP |
| embeddings | Self-hosted Jina embeddings (1024 dims) | lbjlincoln-nomos-embeddings-api.hf.space | CHECK |
| engine-6 (S6) | Docling document processor | lbjlincoln-nomos-docling-api.hf.space | UP |
| S8 (TODO) | Continuous eval runner | — | PLANNED |
| S10 (TODO) | Self-heal monitor | — | PLANNED |
| S2 (TODO) | Sector-specific pipeline | — | PLANNED |

**Strategie** : Utiliser TOUS les slots HF gratuits pour demultiplier les pipelines. Chaque Space = une fonction specialisee.

### Databases (SECTOR-ONLY)

| Service | Contenu | Index/Table | Limite |
|---------|---------|-------------|--------|
| Pinecone `website-sectors-jina-1024` | Sector vectors | **PRIMARY** | 100K max |
| Pinecone `sota-rag-jina-1024` | Legacy benchmarks | **ARCHIVE** (ne plus ecrire) | 46K frozen |
| Neo4j Aura | ~86,841 nodes, enrichment 95% | Sector entities | 200K/400K |
| Supabase | 43,357 sector docs + 3,876 financial tables | `sector_documents` | 500MB |

### Batch sizes
| Pipeline | Batch | Concurrency | Timeout |
|----------|-------|-------------|---------|
| Standard | 10 | 5 | 90s |
| Graph | 5 | 3 | 90s |
| Quantitative | 3 | 1 | 120s |
| Orchestrator | 2 | 1 | 180s |

---

## 6. PIPELINES RAG (Sector Expert Mode)

### Webhooks
| Pipeline | Webhook Path | Role Sectoriel | Status |
|----------|-------------|----------------|--------|
| Standard | `/webhook/rag-multi-index-v3` | Recherche vectorielle sectorielle | WORKING |
| Graph | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | Relations entites sectorielles | WORKING |
| Quantitative | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | Donnees financieres SQL | WORKING |
| Orchestrator | `/webhook/orchestrator-v2` | Routage intelligent 4 secteurs | WORKING |

### Active Workflow IDs
| Pipeline | ID | Name |
|----------|----|------|
| Standard | `TmgyRP20N4JFd9CB` | WF5 Standard RAG V3.5 (Groq direct, multi-index) |
| Graph | `6257AfT1l4FMC6lY` | WF2 Graph RAG V3.3 (Groq direct) |
| Quant | `cjhEhVs0KV1ExHqX` | WF4 Quant V3.1 (LiteLLM) |
| Orchestrator | `qOSaFFrqO8Jb4VGb` | V13 Minimal (regex routing, Groq) |
| Auto-Healer | `Yqw7Pzn0e7m0C6i3` | V1.2b (10min, 4 Spaces, webhook pings) |

### LLM Models (Groq direct — free tier)
| Modele | Roles | Cout |
|--------|-------|------|
| `llama-3.3-70b-versatile` | QA, HyDE, SQL, Planning | $0 |
| `meta-llama/llama-4-scout-17b-16e-instruct` | Fast fallback | $0 |
| `qwen/qwen3-32b` | Multilingual fallback | $0 |

---

## 7. AGENTS & PROCESS SEGMENTE

### 5 Agents Specialises

| Agent | Script | Cycle | Role |
|-------|--------|-------|------|
| **MONITOR** | `ops/monitor.py --loop 300` | 5min | Health check, error detection per node, JSONL logging |
| **EVAL** | `eval/quick-test.py` | After each change | Accuracy baseline, before/after comparison |
| **PIPELINE** | Manual (Claude Code) | On-demand | 1 fix → test → push or revert |
| **INGEST** | `ops/fast-ingest.py` | Batch | E5 vectors, Tavily, PDF, Neo4j enrichment |
| **DOCS** | Manual | After milestone | Update PROJECT-STATE, PILOTAGE, DEBUG-PLAYBOOK |

### Lancer les agents
```bash
python3 ops/agents.py launch all     # Tous les agents background
python3 ops/agents.py status         # Status de chaque agent
python3 ops/agents.py stop all       # Arreter tous
python3 ops/agents.py logs monitor   # Logs d'un agent
```

### Process incremental (STRICT)
```
STRATEGIZE → PLAN → BUILD → TEST → PUSH → AUTO-TEST → PUSH or FIX
     ↑                                                        |
     +————————————————— feedback loop ——————————————————————————+
```

Regles :
1. **AVANT tout fix** : chercher dans DEBUG-PLAYBOOK si pattern connu
2. **1 seul changement par iteration** — jamais 2 fixes simultanement
3. **Mesurer before/after** — pas de changement sans mesure
4. **APRES tout fix** : logger le pattern dans DEBUG-PLAYBOOK
5. **Auto-stop on 3 failures** — rapport structure, pas de boucle infinie

### Monitoring continu
- `ops/monitor.py` ecrit dans `logs/errors/pipeline-errors.jsonl`
- `data/health-status.json` = snapshot sante live
- Auto-Healer n8n (V1.2b) tourne toutes les 10min sur S1
- Dashboard live : tmux cockpit (voir `docs/PILOTAGE.md`)

### Regression Guard
```
Avant commit touchant n8n/ ou eval/:
1. Run 10 questions critiques (smoke test)
2. Comparer aux derniers scores
3. Bloquer si drop > 5% sur un secteur
```

---

## 8. INGESTION & DOCLING

### Architecture ingestion (rag-data-ingestion)
```
Acquisition → Processing (Docling) → Chunking (par secteur) → Embedding → Storage
```

### Document Types par secteur (cible : 100+)
- **Finance** : SEC filings, IFRS standards, annual reports, balance sheets, 10-K/10-Q, earnings calls
- **BTP** : DTU, Eurocodes, CCTP, AFNOR normes, BOAMP, permis, etudes sol, DQE
- **Juridique** : Codes (civil, commerce, travail), jurisprudence, contrats, CGV, statuts, RGPD
- **Industrie** : ISO normes, manuels maintenance, fiches securite, AMDEC, procedures qualite

### Eval Docling
- Mesurer qualite extraction : tableaux, formules, mise en page complexe
- Comparer chunks Docling vs chunks simples
- Target : 95% fidelite sur documents complexes

---

## 9. COMMANDS

```bash
# Session
source .env.local
cat directives/PROJECT-STATE.md

# Agents (5 specialises)
python3 ops/agents.py launch all          # Lancer tous les agents
python3 ops/agents.py status              # Status agents
python3 ops/agents.py stop all            # Arreter tous

# Monitor
python3 ops/monitor.py                    # One-shot dashboard
python3 ops/monitor.py --loop 300         # Continu 5min
python3 ops/monitor.py --errors-only      # Erreurs seulement

# Eval
python3 eval/quick-test.py --proxy --pipelines standard --questions 5
python3 eval/expert-eval.py --sector all --questions 20

# Pipeline Analysis
python3 ops/n8n-execution-analyzer.py --hours 24
python3 ops/n8n-smart-analyzer.py --deep

# Ingestion
python3 ops/fast-ingest.py --sector all
python3 ops/tavily-mass-ingest.py
python3 ops/local-pdf-ingest.py

# Deployment
python3 ops/deploy-standard-v35.py
python3 ops/n8n-api.py list

# Sync
git push origin main
```

---

## 10. REPOS (5 actifs + 2 archives)

| Repo | Role | Status |
|------|------|--------|
| **mon-ipad** (CE REPO) | Tour de controle, eval, ops, MCP | **ACTIF** |
| **rag-data-ingestion** | Moteur ingestion 1M docs, Docling, 100+ types | **ACTIF** |
| **rag-website** | Produit chatbot expert sectoriel, Next.js | **ACTIF** |
| **rag-dashboard** | Dashboard sector accuracy, metriques live | **ACTIF** |
| **rag-storage** | Archive LFS + benchmark legacy | **ARCHIVE** |
| **rag-pme-connectors** | Next.js 15, 15 apps (deprioritise) | **ARCHIVE** |
| **rag-tests** | Fusionne dans mon-ipad (datasets sectoriels) | **ARCHIVE** |

---

## 11. STATE FILES

| Fichier | Role | MAJ |
|---------|------|-----|
| `directives/PROJECT-STATE.md` | Memoire de travail + resume session | Apres chaque milestone |
| `directives/PROCESS-RUNBOOKS.md` | Processus, endpoints, methodologie | Quand process change |
| `technicals/DEBUG-PLAYBOOK.md` | 90+ fixes, knowledge base, diagnostic | Pendant session |
| `technicals/INFRASTRUCTURE.md` | Stack, credentials, env vars, limites | Quand infra change |
| `technicals/PROJECT-ROADMAP.md` | Roadmap sectorielle, bottlenecks, recherche | Quand strategie change |
| `docs/status.json` | Metriques live (auto-genere) | Ne PAS editer |
| `docs/sector-accuracy.json` | Accuracy par secteur (auto-genere) | Ne PAS editer |

---

## 12. DETAILED DOCS

| Fichier | Contenu |
|---------|---------|
| `technicals/INFRASTRUCTURE.md` | Stack, credentials, env vars, limites, storage |
| `technicals/PROJECT-ROADMAP.md` | Roadmap sectorielle, bottlenecks, recherche SOTA |
| `technicals/DEBUG-PLAYBOOK.md` | 90+ fixes, knowledge base, diagnostic flowchart |
| `technicals/data/sector-datasets.md` | 1000+ types documents par secteur |
| `directives/PROJECT-STATE.md` | Etat courant, secteurs, pipelines, next steps |
| `directives/PROCESS-RUNBOOKS.md` | Processus, endpoints, methodologie |
| `directives/repos/` | Directives par repo satellite |

---

## Etat actuel v10.0 (Session 96 — 2026-03-10)

**Pipelines** : 4/4 WORKING (Standard 98%, Graph 100%, Quant 100%, Orch 100%)
**E5 Vectors** : 55,584 (Stage 1 gate PASSED)
**Databases** : Supabase 43K docs, Neo4j ~42K nodes
**Agents** : 5 specialises (monitor, eval, pipeline, ingest, docs)
**Process** : Segmente, incremental, metrics-driven
**Docs** : `docs/PILOTAGE.md` (Termius snippets + tmux cockpit)
**Sessions** : 96 | **Commits** : 1,110+
