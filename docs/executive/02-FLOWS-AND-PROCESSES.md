# NOMOS42 — All Flows & Processes
> Updated 2026-03-31

## Flow 1: NBA Daily Prediction Pipeline

```
TRIGGER: cron */30 (agent-cron.sh)
    │
    ├─ 1. keepalive-spaces.sh → ping all 6 NBA islands
    ├─ 2. fetch_free_odds.py → scrape live odds (game hours only)
    ├─ 3. predict_today.py → generate predictions for tonight's games
    │     └─ Uses best evolved config from S10 (/api/status)
    │     └─ Features from engine.py (6253 features)
    │     └─ Outputs: data/nba-agent/predictions-YYYY-MM-DD.json
    ├─ 4. git push predictions
    └─ 5. Telegram alert with picks

NEXT DAY:
    ├─ evaluate_predictions.py (10:00 UTC)
    │     └─ Scores vs actual results
    │     └─ Updates bankroll-state.json
    └─ arena-engine.py (11:00 UTC)
          └─ Runs 60 competitors against today's games
```

## Flow 2: Evolution (Continuous)

```
HF SPACES (always-on, each island independently):
    │
    LOOP (every ~5-15 min per generation):
    ├─ 1. Select parents (tournament selection)
    ├─ 2. Crossover (cx_rate ~0.80)
    ├─ 3. Mutate (mut_rate 0.08-0.18, capped at 0.15)
    │     └─ Mutate model type, hyperparams, feature subset
    │     └─ MAX_FEATURES=200 enforced
    ├─ 4. Evaluate (2-fold CV, 5000 game subsample, 120s timeout)
    ├─ 5. Select survivors (elitism + tournament)
    ├─ 6. Update /api/status with best_brier, generation, stagnation
    └─ 7. Back to 1.

    Cross-pollination: PLANNED (not yet implemented)
    GPU evolution: On-demand via Kaggle/Colab/Modal
```

## Flow 3: Karpathy Autoresearch Loop

```
TRIGGER: /karpathy-loop skill or Kaggle notebook
    │
    ├─ 1. Launch 5 research subagents in parallel:
    │     ├─ R1: Latest papers (ArXiv, Google Scholar)
    │     ├─ R2: Feature proposals (analyze engine gaps)
    │     ├─ R3: Repo scout (GitHub, HF models)
    │     ├─ R4: Odds analysis (market efficiency gaps)
    │     └─ E1: Quick win features (data on disk unused)
    │
    ├─ 2. Collect proposals → rank by expected Brier impact
    │
    ├─ 3. Implement top proposal:
    │     └─ Modify 1 file → run 5-min experiment → measure Brier
    │     └─ Keep if better → commit → repeat
    │
    └─ 4. Deploy to all 6 HF islands if validated

    Rate: 12 experiments/hour, ~100/session
    Expected: 0.001-0.005 Brier improvement per 100 experiments
```

## Flow 4: Political Alpha Pipeline

```
TRIGGER: cron */30 at :05/:35 (political agent-cron.sh)
    │
    ├─ 1. Fetch signals:
    │     ├─ Executive orders (Federal Register API)
    │     ├─ Insider trades (SEC EDGAR Form 4)
    │     ├─ FEC donations (FEC API)
    │     ├─ Polymarket prices (Polymarket API)
    │     ├─ Social sentiment (Reddit, Twitter, YouTube)
    │     └─ Macro data (FRED, yfinance, CoinGecko)
    │
    ├─ 2. political_engine.py → extract 743 features (22 categories)
    │     └─ Cat17-22: Senator family, committee, district, insider network,
    │        Trump family investments, foreign sovereign ties
    │
    ├─ 3. Evolution on P1-P4 HF islands
    │
    └─ 4. Generate signals → betting_agent.py (portfolio Kelly)
         └─ 4 markets: stock, sector, event, arbitrage
```

## Flow 5: Brain Decision Loop (24/7)

```
TRIGGER: Every 4 hours (HF Space background thread)
    │
    ├─ 1. Monitor all spaces:
    │     ├─ 6 NBA islands → /api/status
    │     ├─ 4 Political islands → /api/status
    │     └─ VM health, bot status
    │
    ├─ 2. Analyze:
    │     ├─ Stagnation detection (gen without improvement)
    │     ├─ Crash detection (no response)
    │     ├─ Performance regression
    │     └─ ATR detection (new best Brier)
    │
    ├─ 3. Decide (AI chain: Gemini → OpenAI → rules):
    │     ├─ tune_ga: adjust mutation/crossover rates
    │     ├─ inject_diversity: reset population diversity
    │     ├─ restart: reboot crashed space
    │     ├─ checkpoint: save best config
    │     └─ alert: notify admin via Telegram
    │
    └─ 4. Execute decision via POST /api/config
```

## Flow 6: La Forge Factory (PLANNED)

```
STATUS: ARCHITECTURE ONLY — NOT IMPLEMENTED

TRIGGER: User message to @Forge42Bot
    │
    ├─ LAYER 0: Strategy Definer (F0)
    │     └─ Parse idea → product/service definition
    │     └─ User persona, pricing, TAM
    │
    ├─ LAYER 1: Strategic Structure (swarm of 3)
    │     ├─ F1 Product Builder (MVP → Pro, Karpathy iterations)
    │     ├─ F2 Business Strategist (Big4 analysis, pricing)
    │     └─ F3 Communication Manager (social, content, growth)
    │     [Swarm mode: each agent knows what others are doing]
    │
    ├─ LAYER 2: Intendance (3 agents)
    │     ├─ F4 Infra Manager (backend, HF, monitoring)
    │     ├─ F5 Finance (revenue, commissions, tracking)
    │     └─ F6 Admin/Legal (RGPD, CGV, compliance)
    │
    └─ LAYER 3: Continuous Evaluation
          └─ Same Karpathy loop: modify → measure → keep if better
          └─ Dashboard at /forge (NOT DEPLOYED)
```

## Flow 7: Monitoring Fleet (DEPLOYING)

```
7 NEW HF SPACES (deploying now):
    │
    ├─ fleet-monitor (LBJLincoln)
    │     └─ Poll ALL services every 5 min
    │     └─ Alert if >2 spaces DOWN
    │
    ├─ island-coordinator (LBJLincoln)
    │     └─ Track evolution progress every 10 min
    │     └─ Alert on stagnation >30 or new ATR
    │
    ├─ betting-monitor (LBJLincoln)
    │     └─ Bankroll, odds, picks every 30 min
    │     └─ Alert on 20% drawdown
    │
    ├─ quality-tracker (LBJLincoln26)
    │     └─ Brier tracking every 15 min
    │     └─ Alert on new ATR
    │
    ├─ research-radar (LBJLincoln26)
    │     └─ ArXiv + GitHub scan every 6h
    │     └─ Alert on relevant papers
    │
    ├─ predictions-monitor (LBJLincoln26)
    │     └─ Pipeline status every 15 min
    │     └─ Alert if no predictions by 20:00 UTC
    │
    └─ political-monitor (LBJLincoln26)
          └─ Political islands + Polymarket every 15 min
          └─ Alert on big market moves
```

## Cross-Repo Coordination

| Repo | Role | Key Files | Sync Required |
|------|------|-----------|---------------|
| mon-ipad | Central brain, scripts, agents | CLAUDE.md, scripts/, hf-space/ | engine.py -> all HF spaces |
| nomos-nba-agent | NBA data, features, predictions | features/engine.py, predict_today.py | engine.py must match mon-ipad |
| nomos-political-alpha | Political features, evolution | features/political_engine.py | Independent engine |
| nomos-dashboard | Web UI, API routes | src/app/ | Reads data from mon-ipad |
| rgwa | AI art generation | agents/, scripts/ | Independent |
