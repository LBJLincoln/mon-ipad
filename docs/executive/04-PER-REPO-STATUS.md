# NOMOS42 — Per-Repo Executive Status
> Updated 2026-03-31

## Repo 1: mon-ipad (Central Brain)

**Role**: Central coordination hub, scripts, agent configs, HF space code, Forge Factory

| Metric | Value |
|--------|-------|
| Size | ~2.5 GB (data included) |
| Active scripts | 45+ |
| Crons | 17 |
| Bots | 4 (brain, NBA, political, forge) |
| HF spaces managed | 10 evolution + 8 monitoring |
| Slash commands | 27 |

**Key directories**:
- `scripts/` — all automation (agents, arena, kaggle, telegram)
- `hf-space/` — NBA evolution island code (synced to all 6 islands)
- `hf-brain/` — Brain HF Space code
- `hf-agents/` — 7 monitoring agent spaces (NEW)
- `features/` — NBA feature engine (6253 features)
- `forge-users/` — Forge Factory user directories
- `docs/` — Architecture, research, executive docs
- `data/` — Predictions, odds, health status, arena results

**Pending**:
- [ ] Deploy 7 monitoring agents to HF Spaces
- [ ] Implement Forge F0-F6 as real agents
- [ ] Sync hf-agents/ deployment script

---

## Repo 2: nomos-nba-agent (NBA Data & Predictions)

**Role**: NBA data pipeline, feature engine, prediction generation

| Metric | Value |
|--------|-------|
| Engine | v3.1-46cat, 6253 features |
| ATR Brier | 0.21570 (Colab TabICL) |
| Walk-forward | 0.22447 (Kaggle, 19 weeks) |
| Tracking datasets | 10 (hustle, speed, drives, shots, etc.) |

**Key files**:
- `features/engine.py` — THE feature engine (must stay in sync with HF spaces)
- `predict_today.py` — Daily prediction generator
- `evaluate_predictions.py` — Next-day evaluator
- `scripts/scrape_season_odds.py` — SBR odds scraper
- `colab/nba_gpu_v2.ipynb` — GPU evolution notebook

**Pending**:
- [ ] Implement shot-chart CNN embeddings (Cat50)
- [ ] Add MC dropout uncertainty quantification
- [ ] Rolling window training (currently uses full history)

---

## Repo 3: nomos-political-alpha (Political Alpha)

**Role**: Political feature engine, evolution, betting signals

| Metric | Value |
|--------|-------|
| Engine | v3.1-22cat, 743 features |
| Categories | 22 (16 base + 6 insider/Trump/foreign) |
| Data sources | 10 APIs |
| HF Spaces | 4 (P1-P4) |

**Key files**:
- `features/political_engine.py` — Political feature engine
- `ops/fetch_political_data.py` — Data pipeline (10 APIs)
- `betting_agent.py` — Portfolio Kelly for 4 markets
- `hf-space/` — Political evolution island code

**Pending**:
- [ ] Deploy v3.1 engine (Cat17-22) to P1-P4 HF spaces
- [ ] Implement data fetchers for Cat17-22 (senator family trades, committee activity)
- [ ] Congress.gov API integration for committee hearings

---

## Repo 4: nomos-dashboard (Web Dashboard)

**Role**: Public-facing dashboard with all data visualizations

| Metric | Value |
|--------|-------|
| Framework | Next.js 14 + TypeScript |
| Hosting | Vercel (nomosdashboard.vercel.app) |
| Routes | /nba /political /rgwa /evolution /arena |
| API | Reads from mon-ipad data/ via raw GitHub |

**Key pages**:
- `/nba` — NBA predictions, model performance
- `/political` — Political signals, evolution
- `/evolution` — HF island progress, convergence
- `/arena` — 60 competitors, full-season backtest (sparklines, BUST badges)
- `/rgwa` — AI art gallery

**Pending**:
- [ ] Deploy NomosNBABot SaaS site (nomosquant42.vercel.app)
- [ ] Add /forge route for Forge Factory dashboard
- [ ] Add /monitoring route for fleet status

---

## Repo 5: rgwa (AI Art)

**Role**: Generative AI art — music, video, images

| Metric | Value |
|--------|-------|
| Agents | 5 (visual, music, video, quality, style) |
| Bot | @RGWAbot (running) |
| API | HF Inference (FLUX, MusicGen, AnimateDiff) |

**Status**: ACTIVE but secondary priority. Bot running, skills defined.

**Pending**:
- [ ] Gallery auto-update from generated pieces
- [ ] Studio Vercel site (rgwa-studio.vercel.app)
