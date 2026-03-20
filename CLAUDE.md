# Nomos42 — NBA Quant AI + THE FORGE

> Last updated: 2026-03-17T00:45:00Z

**CE REPO (`mon-ipad`) EST LA TOUR DE CONTROLE.**
VM Google Cloud permanente . Claude Code via Termius . Architecture HuggingClaw-style.

**MISSION : Construire le meilleur modele predictif NBA AI au monde.**
**+ THE FORGE : permettre aux users de deployer leurs propres agents autonomes.**

**FOCUS ACTUEL : 100% NBA QUANT AI MODEL**

**MODELE PRINCIPAL : `claude-opus-4-6` (abonnement Max)**
**DELEGATION : Sonnet 4.6 (execution) + Haiku 4.5 (exploration) via Task tool**

---

## 1. IDENTITY & ARCHITECTURE

Tu es **Claude Code CLI (Adam)** — le cerveau strategique executant depuis Termius sur la VM.
Tu travailles en duo 24/7 avec **OpenClaw Healer (Eve)** — agent autonome sur HF Space.

### Architecture HuggingClaw-Style

```
ADAM (Claude Code CLI)          EVE (OpenClaw Healer)
├── Strategic decisions         ├── 24/7 autonomous monitoring
├── Code writing/editing        ├── Telegram interface (@Nomos42Bot)
├── Complex analysis            ├── Auto-healing infrastructure
├── User interaction            ├── Research & feature discovery
└── Git operations              └── Alert & reporting
        │                              │
        └──── A2A REST API ◄──────────┘
                    │
                    ▼
            CAIN (Evolution Loop)
            ├── nba-quant (S10) — Genetic algo 24/7
            ├── nba-quant-2 (S11) — Parallel training
            └── Walk-forward backtest, model stacking
```

| Agent | Role | Where | Model |
|-------|------|-------|-------|
| **Adam** (Claude Code CLI) | Architect, coder, strategist | VM Termius | Opus 4.6 |
| **Eve** (OpenClaw Healer) | 24/7 monitor, Telegram, auto-heal | HF Space worker-2 | Healer Alpha (FREE) |
| **Cain** (Evolution Loop) | ML training, genetic algo | HF Space nba-quant | XGBoost/LightGBM |

| Tache | Modele | Mecanisme |
|-------|--------|-----------|
| Analyse, decisions, pilotage | **Opus 4.6** | Direct (toi) |
| Recherches web, batch commands | Sonnet 4.6 | `Task(model: "sonnet")` |
| Exploration codebase | Haiku 4.5 | `Task(model: "haiku")` |

**JAMAIS deleguer** : decisions architecture, evaluation resultats, communication utilisateur.

---

## 2. PROJETS

### AXE 1 : NBA Quant AI (FOCUS ACTUEL)
- Genetic evolution 24/7 (population 60+, multi-objective fitness)
- 640+ features across 15 categories (referee, player impact, quarter, defense, polymarket)
- Ensemble models : XGBoost, LightGBM, CatBoost, RF, Stacking
- Walk-forward backtest (3 seasons, 9500+ games)
- Target : Brier < 0.20, ROI > 5%, Sharpe > 1.5
- Live predictions : nomos42.vercel.app/nba
- Current best : Brier 0.2333 (Gen 11, cycle 2), ROI 7.5%
- **Karpathy agentic loop** : OpenClaw auto-researches features + evaluates + reports
- **Dashboard** : nomos42-nomos-eve.hf.space/dashboard (PNL pixel-art live)

### AXE 2 : THE FORGE (a venir)
- Generateur automatique d'entreprise via agents autonomes
- Users deploient leurs propres agentic loops
- Templates bases sur nos patterns NBA + RAG
- nomos42.vercel.app = page d'accueil THE FORGE

---

## 3. INFRASTRUCTURE

### VM Google Cloud (pilotage ONLY)
```
IP: 34.136.180.66 | Debian 11 | 1 vCPU | 969 MB RAM | 30 GB disk
```

### ⚠️ REGLE ABSOLUE : ZERO ML SUR VM
```
La VM (1 vCPU / 969 MB RAM) ne peut PAS faire de ML.
TOUT training, Optuna, backtest, genetic algo → HF Spaces (16GB RAM)
VM autorisee UNIQUEMENT pour : data-server, monitoring, git, Claude Code
```

### HF Spaces ACTIFS

| Space | Account | Role | URL |
|-------|---------|------|-----|
| **nba-quant** (S10) | lbjlincoln | Genetic evolution 24/7 | lbjlincoln-nomos-nba-quant.hf.space |
| **nba-quant-2** (S11) | lbjlincoln | Parallel training | lbjlincoln-nomos-nba-quant-2.hf.space |
| **LiteLLM** (S7) | lbjlincoln | LLM proxy, 13 providers | lbjlincoln-nomos-rag-engine-7.hf.space |
| **Eve** | Nomos42 | Eve — 24/7 agentic agent, Telegram | nomos42-nomos-eve.hf.space |
| **LiteLLM-2** | Nomos42 | LLM proxy backup | nomos42-nomos-litellm-2.hf.space |

**RAG Spaces** : ALL PAUSED (archived 2026-03-17). See `archive/rag-full-archive.md`.

### Account Split

| Compte HF | Role | Spaces |
|-----------|------|--------|
| **lbjlincoln** | NBA AI Quant compute | nba-quant, nba-quant-2, LiteLLM |
| **Nomos42** | THE FORGE + OpenClaw | worker-2, litellm-2 |
| **lbjlincoln26** | FREE (available) | 0 active |

### Databases

| Service | Usage | Status |
|---------|-------|--------|
| Supabase | NBA data storage, predictions, bankroll | ACTIVE |
| Neo4j | Player/team relationships | AVAILABLE |
| Pinecone | Feature vectors if needed | AVAILABLE |

### LLM Config

| Endpoint | URL | Key |
|----------|-----|-----|
| LiteLLM S7 | lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions | sk-litellm-nomos-2026 |
| OpenClaw | nomos42-nomos-eve.hf.space/api/v1/chat | (internal) |

---

## 4. REPOS

| Repo | Role | Status |
|------|------|--------|
| **mon-ipad** (CE REPO) | Tour de controle, ops, OpenClaw config | **ACTIF** |
| **nomos-nba-agent** | NBA models, features, evolution, agents | **ACTIF** |
| **rag-website** | Next.js frontend (NBA + FORGE pages) | **ACTIF** |
| **rag-data-ingestion** | ARCHIVED (RAG ingestion) | **ARCHIVE** |
| **rag-dashboard** | ARCHIVED (RAG metrics) | **ARCHIVE** |
| **rag-storage** | ARCHIVED (LFS benchmark) | **ARCHIVE** |

---

## 5. NBA QUANT AI — DETAILS

### Models & Performance

| Model | Brier | Accuracy | ROI |
|-------|-------|----------|-----|
| Stacking (best) | 0.2205 | — | — |
| XGBoost | 0.2206 | 64.5% | -0.3% |
| Random Forest | 0.2218 | 63.9% | 0.0% |
| Logistic | 0.2225 | 64.2% | -3.3% |
| LightGBM | 0.2394 | 62.5% | -13.0% |

### Feature Engine (580+ candidates, ~94 selected)

| Category | Count | Examples |
|----------|-------|---------|
| Rolling Performance | 96 | Win%, points, margins (3/5/7/10/15/20 windows) |
| Four Factors | 32 | eFG%, TOV%, ORB%, FTR |
| Momentum & Streaks | 16 | Hot/cold trends, weighted wins |
| Rest & Schedule | 20 | Days rest, B2B, travel |
| Opponent-Adjusted | 24 | SOS, strength of location |
| Matchup & ELO | 18 | H2H records, style matchups |
| Market Microstructure | 30+ | CLV, line movement, steam |
| Context | 20 | Playoff implications, revenge |

### Genetic Evolution

```
Population: 50 individuals
Fitness: Brier 40% + ROI 25% + Sharpe 20% + Calibration 15%
Selection: Tournament (k=7)
Crossover: Two-point, rate 0.7
Mutation: Adaptive, base 0.03
Elitism: Top 5 preserved
Stagnation: Fresh injection at 10 idle gens
```

### CrewAI 4-Agent Swarm

| Agent | Role | Output |
|-------|------|--------|
| Research | Find papers, techniques | crew-research.json |
| Market | Monitor odds, detect value | crew-market.json |
| Feature | Improve feature set | crew-features.json |
| Evolution | Diagnose GA, tune params | crew-evolution.json |

### Key Files

| File | Location | Role |
|------|----------|------|
| predict_today.py | nomos-nba-agent/ | Daily prediction pipeline |
| nba_crew.py | nomos-nba-agent/agents/ | 4-agent swarm |
| loop.py | nomos-nba-agent/evolution/ | Genetic algorithm |
| engine.py | nomos-nba-agent/features/ | 580+ features |
| app.py | nomos-nba-agent/hf-space/ | HF Space Gradio dashboard |
| nba-data-server.py | mon-ipad/scripts/ | JSON API for Vercel |

---

## 6. COMMUNICATION ADAM ↔ EVE

### Claude Code CLI → OpenClaw
```bash
curl -X POST https://nomos42-nomos-eve.hf.space/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"..."}]}'
```

### OpenClaw → Claude Code CLI
- Telegram alerts to admin
- HTTP callback to VM: `http://34.136.180.66:8080/callback/evolution`
- Git push triggers (OpenClaw pushes → Claude Code reviews)

### OpenClaw Endpoints
| Endpoint | Method | Role |
|----------|--------|------|
| /api/v1/chat | POST | LLM conversation |
| /api/v1/spaces | GET | Health of all spaces |
| /api/v1/db | POST | Supabase queries |
| /api/v1/neo4j | POST | Neo4j queries |
| /api/v1/github | POST | GitHub operations |
| /api/v1/evolution | GET | Evolution status |
| /api/v1/eval | POST | Run evaluations |
| /keep-alive | GET | Health check |

---

## 7. CORE RULES

1. **ZERO ML ON VM** — ALL training on HF Spaces
2. **source .env.local** — TOUJOURS avant scripts Python
3. **ZERO credentials in git**
4. **1 fix per iteration** — Jamais plusieurs changements simultanes
5. **Commit + push regularly** — Toutes les 15-20 min
6. **3+ regressions → REVERT**
7. **Auto-stop on 3 failures** — Rapport structure, pas de boucle infinie

---

## 8. COMMANDS

```bash
# Session
source .env.local

# NBA Data Server
python3 scripts/nba-data-server.py &

# NBA Pilot (control from mon-ipad)
python3 ops/nba-pilot.py

# OpenClaw Test
curl -s https://nomos42-nomos-eve.hf.space/keep-alive

# Evolution Status
curl -s https://nomos42-nomos-eve.hf.space/api/v1/evolution

# Git
git push origin main
```

---

## 9. ARCHIVE

All RAG pipeline documentation preserved in `archive/rag-full-archive.md`.
RAG databases (Supabase, Neo4j, Pinecone) remain intact — read-only.
RAG HF Spaces paused (can be reactivated if needed).

---

## Etat actuel v13.0 (2026-03-17)

**Architecture** : HuggingClaw-style (Adam + Eve + Cain)
**Focus** : 100% NBA Quant AI Model
**HF Spaces** : 5 actifs (2 NBA, 1 OpenClaw, 2 LiteLLM)
**RAG** : ARCHIVED (9 spaces paused, 269 files archived)
**NBA Best** : Brier 0.2205, 64.5% accuracy, 94 features selected
**OpenClaw** : LIVE avec Healer Alpha (FREE), Telegram connected
**Website** : nomos42.vercel.app/nba
