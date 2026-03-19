/**
 * Agentic Loop v6 — Multi-Agent Experiment System
 *
 * Builds on v5's intelligent foundation with:
 *   - EVAL cycle: compare predictions to real game outcomes (feedback loop)
 *   - ANALYZE cycle: 5 specialized agent roles rotate each cycle
 *   - RESEARCH cycle: autonomous web research for model improvement
 *   - EXPERIMENT cycle: dispatch experiments to S11, auto-promote winners to S10
 *
 * Design principles:
 *   1. DATA > LLM — Fetch real data, compute real metrics. No hallucinations.
 *   2. OBSERVE > ACT — Watch and report. Config changes are Adam's job.
 *   3. STRUCTURED OUTPUT — All observations go to A2A inbox for Adam.
 *   4. FEEDBACK LOOP — Predictions vs reality. This changes everything.
 *   5. INTELLIGENT REASONING — Eve THINKS about data, not just relays it.
 *   6. EXPERIMENT-DRIVEN — Propose, test on S11, promote if better.
 *
 * Cycles:
 *   OBSERVE    (3 min)   — Poll S10, feed metrics to Watchdog
 *   DATA       (10 min)  — Fetch odds + scores from APIs, store in Supabase
 *   HEALTH     (5 min)   — Check all 5 HF Spaces are up
 *   REPORT     (15 min)  — Generate structured report for Adam (A2A)
 *   COMMAND    (1 min)   — Check A2A command queue from Adam
 *   HEARTBEAT  (30 min)  — Telegram summary to admin (now with insights)
 *   EVAL       (10 min)  — Check & eval yesterday + 2 days ago (once per date/day)
 *   ANALYZE    (15 min)  — 5 specialized agent roles rotate (feature/model/calibration/evolution/market)
 *   RESEARCH   (2 hours) — Autonomous web research — 12x/day
 *   EXPERIMENT (3 min)   — Dispatch pending experiments to S11
 *
 * Agent Roles (rotate each ANALYZE cycle):
 *   1. feature_discovery   — Find new features, prune bad ones
 *   2. model_architecture  — Test new models, hyperparams, stacking configs
 *   3. calibration         — Improve probability calibration
 *   4. evolution_tuner     — Optimize GA parameters
 *   5. market_intelligence — Analyze odds patterns, CLV
 */

const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const LOOP_DATA_DIR = '/data/agentic-loop';
const STATE_FILE = path.join(LOOP_DATA_DIR, 'state-v6.json');

// ══════════════════════════════════════════
//  SPECIALIZED AGENT ROLES
// ══════════════════════════════════════════

const AGENT_ROLES = [
  'feature_discovery',    // Find new features, prune bad ones
  'model_architecture',   // Test new models, hyperparams, stacking configs
  'calibration',          // Improve probability calibration
  'evolution_tuner',      // Optimize GA parameters
  'market_intelligence',  // Analyze odds patterns, CLV
];

const ROLE_PROMPTS = {
  feature_discovery: (ctx) => `You are the FEATURE DISCOVERY agent for an NBA prediction model.
Current best Brier: ${ctx.brier || '?'}. Selected features: ${ctx.features || '?'}.
Model type: ${ctx.modelType || 'ensemble'}. Population: ${ctx.population || '?'}.
Recent experiments: ${ctx.recentExperiments || 'none'}

Your job: propose NEW features to test or identify features to REMOVE.
Focus on:
- Interaction terms (e.g., rest_days * opponent_pace, home_streak * travel_distance)
- Rolling windows variants (try 3/5/7/10/15/20 game windows)
- Opponent-adjusted stats (eFG% vs opponent defensive rating)
- Advanced analytics: RAPTOR, EPM, DARKO components
- Schedule density features (games in last N days)
- Referee tendencies (foul rate, home whistle bias)
- Player availability impact (minutes-weighted team strength)

Output 1-3 EXPERIMENT blocks:
EXPERIMENT: {"type":"feature_test","description":"...","hypothesis":"...","params":{"features_to_add":["feat1"],"features_to_remove":["feat2"]}}

Also output 0-1 RECOMMENDATION blocks for direct config changes if needed.
Max 300 words.`,

  model_architecture: (ctx) => `You are the MODEL ARCHITECTURE agent for an NBA prediction model.
Current best Brier: ${ctx.brier || '?'}. Current model: ${ctx.modelType || 'ensemble'}.
Generation: ${ctx.generation || '?'}. Stagnation: ${ctx.stagnation || '?'}.
Recent experiments: ${ctx.recentExperiments || 'none'}

Your job: propose model architecture changes to test.
Focus on:
- Stacking configurations (meta-learner choice: logistic, ridge, xgboost)
- Hyperparameter search (learning_rate, max_depth, n_estimators, reg_alpha/lambda)
- New base models (CatBoost, Extra Trees, Neural Net, KNN ensemble)
- Calibration methods (Platt, isotonic, beta calibration, Venn-Abers)
- Feature selection methods (mutual info, Boruta, permutation importance)
- Ensemble weighting (Brier-weighted, Bayesian model averaging)

Output 1-3 EXPERIMENT blocks:
EXPERIMENT: {"type":"model_test","description":"...","hypothesis":"...","params":{"model_type":"xgboost","hyperparams":{"max_depth":6,"learning_rate":0.05}}}

Also output 0-1 RECOMMENDATION blocks for direct config changes if needed.
Max 300 words.`,

  calibration: (ctx) => `You are the CALIBRATION agent for an NBA prediction model.
Current best Brier: ${ctx.brier || '?'}. Accuracy: ${ctx.accuracy || '?'}.
Recent eval Brier scores: ${ctx.evalBriers || 'none'}.
Recent experiments: ${ctx.recentExperiments || 'none'}

Your job: improve probability calibration (Brier decomposition: reliability + resolution).
Focus on:
- Platt scaling parameters (fit on last 500 vs 1000 games)
- Isotonic regression (min samples per bin: 50, 100, 200)
- Beta calibration (parametric, better for extreme probs)
- Venn-Abers predictors (valid probability intervals)
- Calibration by context (home/away, back-to-back, favorites/underdogs)
- Temperature scaling (single parameter, simple but effective)
- Histogram binning (10, 15, 20 bins)
- Recalibration frequency (daily, weekly, rolling 30-day)

Output 1-3 EXPERIMENT blocks:
EXPERIMENT: {"type":"calibration_test","description":"...","hypothesis":"...","params":{"method":"platt","fit_window":500}}

Also output 0-1 RECOMMENDATION blocks for direct config changes if needed.
Max 300 words.`,

  evolution_tuner: (ctx) => `You are the EVOLUTION TUNER agent for an NBA prediction genetic algorithm.
Current best Brier: ${ctx.brier || '?'}. Generation: ${ctx.generation || '?'}.
Population: ${ctx.population || '?'}. Stagnation: ${ctx.stagnation || '?'}.
Mutation rate: ${ctx.mutationRate || '?'}. Features: ${ctx.features || '?'}.
Recent experiments: ${ctx.recentExperiments || 'none'}

Your job: optimize the genetic algorithm parameters.
Focus on:
- Population size (50-200, larger = more exploration)
- Mutation rate (0.01-0.30, adaptive vs fixed)
- Crossover rate (0.5-0.9, uniform vs two-point)
- Tournament size (3-10, selection pressure)
- Elitism count (3-10, preservation of best)
- Stagnation threshold (5-20 generations before injection)
- Fresh injection ratio (10-30% of population)
- Multi-objective weights (Brier/ROI/Sharpe/Calibration balance)
- Island model (parallel sub-populations with migration)

Output 1-3 EXPERIMENT blocks:
EXPERIMENT: {"type":"evolution_test","description":"...","hypothesis":"...","params":{"mutation_rate":0.08,"population":80,"tournament_size":5}}

Also output 0-1 RECOMMENDATION blocks for direct config changes if needed.
Max 300 words.`,

  market_intelligence: (ctx) => `You are the MARKET INTELLIGENCE agent for an NBA prediction model.
Current best Brier: ${ctx.brier || '?'}. ROI: ${ctx.roi || '?'}.
Data status: odds fetches=${ctx.oddsFetches || '?'}, line movements=${ctx.lineMovements || '?'}.
Recent experiments: ${ctx.recentExperiments || 'none'}

Your job: analyze odds patterns and improve market-based features.
Focus on:
- CLV (Closing Line Value) — are we beating the closing line?
- Steam moves detection (sharp money indicators)
- Line movement features (opening vs current vs closing)
- Market consensus features (Pinnacle vs average vs offshore)
- Reverse line movement (public vs sharp divergence)
- Totals correlation with spread (over/under as side indicator)
- Market efficiency by time (early vs late value)
- Prop market signals (player props → team performance)
- Live odds integration (pre-game model + live adjustment)

Output 1-3 EXPERIMENT blocks:
EXPERIMENT: {"type":"market_test","description":"...","hypothesis":"...","params":{"features":["clv_spread","steam_indicator","rlm_flag"]}}

Also output 0-1 RECOMMENDATION blocks for direct config changes if needed.
Max 300 words.`,
};

class AgenticLoop {
  constructor({
    fetchEvolution,
    callS10,
    getCompletion,
    bot,
    adminId,
    watchdog,
    dataWorker,
    a2a,
    spaceExecutor,
    feedbackLoop,
    researchAgent,
    codeAgent,
    infraBridge,
  }) {
    this.fetchEvolution = fetchEvolution;
    this.callS10 = callS10;
    this.getCompletion = getCompletion;
    this.bot = bot;
    this.adminId = adminId;
    this.watchdog = watchdog;
    this.dataWorker = dataWorker;
    this.a2a = a2a;
    this.spaces = spaceExecutor;
    this.feedbackLoop = feedbackLoop;
    this.researchAgent = researchAgent;
    this.codeAgent = codeAgent;
    this.infra = infraBridge;

    // Agent role — determines which cycles are active
    this.agentName = process.env.AGENT_NAME || 'Eve';
    const role = process.env.AGENT_ROLE || 'nba-quant';
    this.isNBA = role === 'nba-quant' || role === 'nba-market';
    this.isMarketAgent = role === 'nba-market';

    // S10/S11 URLs
    this.S10_URL = process.env.S10_URL || 'https://lbjlincoln-nomos-nba-quant.hf.space';
    this.S11_URL = process.env.S11_URL || 'https://lbjlincoln-nomos-nba-quant-2.hf.space';

    // Timers
    this.timers = {};
    this.running = false;

    // Last analyst insight (shown in heartbeat)
    this.lastInsight = null;

    // Auto-execute: Karpathy pattern — act on insights automatically
    this.autoExecuteEnabled = true;

    // Specialized agent role rotation (0-4, cycles through AGENT_ROLES)
    this.analyzeRoleIndex = 0;

    // Conversation memory: last N insights for multi-turn reasoning
    this.analysisHistory = [];
    this.MAX_ANALYSIS_HISTORY = 10;

    // Execution feedback: track what we did and what happened
    this.executionLog = [];
    this.MAX_EXECUTION_LOG = 20;

    // Experiment tracking
    this.experimentStats = {
      submitted: 0,
      dispatched: 0,
      completed: 0,
      promoted: 0,
      failed: 0,
    };

    // State
    this.state = {
      startedAt: null,
      cycles: 0,
      lastObserve: null,
      lastData: null,
      lastHealth: null,
      lastReport: null,
      lastCommand: null,
      lastHeartbeat: null,
      lastEval: null,
      lastAnalyze: null,
      lastResearch: null,
      lastExperiment: null,
      lastEvoStatus: null,
      errors: [],
    };

    this._load();
  }

  // ══════════════════════════════════════════
  //  START / STOP
  // ══════════════════════════════════════════

  start() {
    if (this.running) return;
    this.running = true;
    this.state.startedAt = new Date().toISOString();

    logger.info('[LOOP] Agentic Loop v6 started — multi-agent experiment system');

    // OBSERVE: Every 3 min
    this.timers.observe = setInterval(() => this._cycle('observe'), 3 * 60 * 1000);

    // DATA: Every 10 min — injuries, scores, box scores, lineups, referees
    this.timers.data = setInterval(() => this._cycle('data'), 10 * 60 * 1000);

    // HEALTH: Every 5 min
    this.timers.health = setInterval(() => this._cycle('health'), 5 * 60 * 1000);

    // REPORT: Every 15 min (offset 5 min from DATA)
    setTimeout(() => {
      this.timers.report = setInterval(() => this._cycle('report'), 15 * 60 * 1000);
    }, 5 * 60 * 1000);

    // COMMAND: Every 1 min — fast poll for Adam's commands
    this.timers.command = setInterval(() => this._cycle('command'), 60 * 1000);

    // HEARTBEAT: Every 30 min
    this.timers.heartbeat = setInterval(() => this._cycle('heartbeat'), 30 * 60 * 1000);

    // EVAL: Check every 10 min, runs once per day per date
    this.timers.eval = setInterval(() => this._maybeEval(), 10 * 60 * 1000);

    // ANALYZE: Every 15 min — 5 specialized roles rotate
    this.timers.analyze = setInterval(() => this._cycle('analyze'), 15 * 60 * 1000);

    // RESEARCH: Every 2 hours — 12x/day
    this.timers.research = setInterval(() => this._cycle('research'), 2 * 60 * 60 * 1000);

    // EXPERIMENT: Every 3 min — dispatch pending experiments to S11
    this.timers.experiment = setInterval(() => this._cycle('experiment'), 3 * 60 * 1000);

    // Run initial cycles
    setTimeout(() => this._cycle('observe'), 5000);    // 5s after start
    setTimeout(() => this._cycle('health'), 15000);     // 15s
    setTimeout(() => this._cycle('data'), 30000);       // 30s
    setTimeout(() => this._cycle('heartbeat'), 60000);  // 1 min — startup notification
    setTimeout(() => this._maybeEval(), 90000);          // 1.5 min — check if eval needed
    setTimeout(() => this._cycle('analyze'), 3 * 60 * 1000);  // 3 min — first analysis
    setTimeout(() => this._cycle('experiment'), 4 * 60 * 1000);  // 4 min — first experiment dispatch
  }

  stop() {
    this.running = false;
    for (const timer of Object.values(this.timers)) {
      clearInterval(timer);
    }
    this.timers = {};
    logger.info('[LOOP] Agentic Loop v6 stopped');
  }

  // ══════════════════════════════════════════
  //  CYCLE DISPATCHER
  // ══════════════════════════════════════════

  async _cycle(type) {
    if (!this.running) return;
    this.state.cycles++;

    try {
      switch (type) {
        case 'observe':
          await this._observe();
          break;
        case 'data':
          await this._fetchData();
          break;
        case 'health':
          await this._healthCheck();
          break;
        case 'report':
          await this._generateReport();
          break;
        case 'command':
          await this._checkCommands();
          break;
        case 'heartbeat':
          await this._heartbeat();
          break;
        case 'eval':
          await this._evaluate();
          break;
        case 'analyze':
          await this._analyze();
          break;
        case 'research':
          await this._research();
          break;
        case 'experiment':
          await this._runExperiment();
          break;
      }
    } catch (err) {
      const errEntry = {
        cycle: type,
        error: err.message,
        timestamp: new Date().toISOString(),
      };
      this.state.errors.push(errEntry);
      if (this.state.errors.length > 50) this.state.errors = this.state.errors.slice(-50);
      logger.error(`[LOOP] ${type} cycle error: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  OBSERVE — Poll S10 evolution status
  // ══════════════════════════════════════════

  async _observe() {
    this.state.lastObserve = new Date().toISOString();

    // Watchdog does the actual monitoring
    if (this.watchdog) {
      await this.watchdog.check();
    }

    // NBA-only: fetch S10 evolution status
    if (this.isNBA) {
      try {
        const evo = await this.fetchEvolution();
        if (evo) {
          this.state.lastEvoStatus = {
            brier: evo.brier || evo.best_brier,
            generation: evo.generation,
            population: evo.population || evo.pop_size,
            features: evo.features || evo.selected_features,
            stagnation: evo.stagnation,
            mutationRate: evo.mutation_rate,
            roi: evo.roi,
            status: evo.status,
            fetchedAt: this.state.lastObserve,
          };
        }
      } catch (err) {
        logger.debug(`[LOOP] Observe fetch: ${err.message}`);
      }
    }

    this._save();
  }

  // ══════════════════════════════════════════
  //  DATA — Fetch data (NBA-specific for Eve, generic for others)
  // ══════════════════════════════════════════

  async _fetchData() {
    this.state.lastData = new Date().toISOString();
    this.state.cycleCount = (this.state.cycleCount || 0) + 1;
    const cycle = this.state.cycleCount;

    if (!this.dataWorker) return;

    if (this.isMarketAgent) {
      // ── NBA MARKET INTELLIGENCE — odds, line movements, CLV only ──
      // Skip scores/injuries/box scores (Eve handles those)

      // Fetch odds + line movements (primary focus)
      const oddsResult = await this.dataWorker.fetchOdds();
      if (oddsResult && this.a2a) {
        this.a2a.postDataReport('market_odds', {
          games: oddsResult.games?.length || 0,
          stored: oddsResult.stored || 0,
          movements: oddsResult.lineMovements?.length || 0,
          agent: this.agentName,
        });
      }

      // Track line movements every cycle (market microstructure)
      if (oddsResult?.lineMovements?.length > 0) {
        this.state._lastLineMovements = oddsResult.lineMovements.slice(0, 20);
        logger.info(`[LOOP] ${this.agentName} tracked ${oddsResult.lineMovements.length} line movements`);
      }

      // Fetch today's games (for game context — no box scores)
      const todayResult = await this.dataWorker.fetchTodaysGames();
      if (todayResult && this.a2a) {
        this.a2a.postDataReport('market_games', {
          total: todayResult.total, live: todayResult.live,
          agent: this.agentName,
        });
      }

      // Fetch evolved model predictions from S10 (for CLV comparison)
      await this._ingestPredictions();

    } else if (this.isNBA) {
      // ── NBA-SPECIFIC DATA COLLECTION (Eve) ──

      // Fetch odds (dormant when quota exhausted — returns null gracefully)
      const oddsResult = await this.dataWorker.fetchOdds();
      if (oddsResult && this.a2a) {
        this.a2a.postDataReport('odds', {
          games: oddsResult.games?.length || 0,
          stored: oddsResult.stored || 0,
          movements: oddsResult.lineMovements?.length || 0,
        });
      }

      // Fetch scores via ESPN (free, always works)
      const scoresResult = await this.dataWorker.fetchScores();
      if (scoresResult && this.a2a) {
        this.a2a.postDataReport('scores', {
          source: 'espn', total: scoresResult.total,
          completed: scoresResult.completed, live: scoresResult.live,
        });
      }

      // Fetch injuries (ESPN free)
      const injResult = await this.dataWorker.fetchInjuries();
      if (injResult && this.a2a) {
        this.a2a.postDataReport('injuries', { total: injResult.total, stored: injResult.stored });
      }

      // Fetch today's games + box scores for completed games (NBA.com CDN)
      const todayResult = await this.dataWorker.fetchTodaysGames();
      if (todayResult?.gameIds?.length > 0) {
        const completedGames = todayResult.games?.filter(g => g.game_status === 3) || [];
        for (const game of completedGames.slice(0, 15)) {
          await this.dataWorker.fetchBoxScores(game.game_id);
        }
        if (this.a2a) {
          this.a2a.postDataReport('todays_games', {
            total: todayResult.total, completed: todayResult.completed,
            live: todayResult.live, boxScoresFetched: completedGames.length,
          });
        }
      }

      // Browser-based scraping — every other cycle
      if (cycle % 2 === 0) {
        await this.dataWorker.fetchLineups().catch(e => logger.warn(`[LOOP] Lineups: ${e.message}`));
        await this.dataWorker.fetchReferees().catch(e => logger.warn(`[LOOP] Referees: ${e.message}`));
      }

      // Advanced stats — once per day (every 12 cycles at 10min = 2h)
      if (cycle % 12 === 0) {
        await this.dataWorker.fetchAdvancedStats().catch(e => logger.warn(`[LOOP] AdvStats: ${e.message}`));
      }

      // Fetch evolved model predictions from S10
      await this._ingestPredictions();
    } else {
      // ── GENERAL-PURPOSE AGENT ──
      // No NBA data collection — agent waits for commands or runs generic tasks
      logger.info(`[LOOP] ${this.agentName} data cycle — awaiting commands (no NBA collection)`);
    }

    this._save();
  }

  // ══════════════════════════════════════════
  //  PREDICTION INGESTION — S10 evolved model → Supabase
  // ══════════════════════════════════════════

  async _ingestPredictions() {
    if (!this.isNBA) return; // NBA-only
    if (!this.feedbackLoop || !this.callS10) return;

    const today = new Date().toISOString().slice(0, 10);

    // Only ingest once per day
    if (this.state._lastPredictionIngest === today) return;

    try {
      // Call S10's /api/predict endpoint with today's date
      const resp = await fetch(`${this.S10_URL}/api/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: today }),
        signal: AbortSignal.timeout(30000),
      });

      if (!resp.ok) {
        logger.warn(`[LOOP] S10 predict returned ${resp.status}`);
        return;
      }

      const data = await resp.json();
      const predictions = data.predictions || [];

      if (predictions.length === 0) {
        logger.info('[LOOP] No games today — no predictions to ingest');
        return;
      }

      // Store predictions via feedbackLoop (batch)
      const validPreds = predictions
        .filter(p => !p.error && p.home_win_prob != null)
        .map(p => ({
          home_team: p.home_team,
          away_team: p.away_team,
          predicted_home_prob: p.home_win_prob,
          model_version: `s10-gen${data.model?.generation || '?'}-${data.model?.type || 'unknown'}`,
        }));

      const stored = await this.feedbackLoop.storePredictions(validPreds, today);

      logger.info(`[LOOP] Ingested ${stored}/${predictions.length} predictions from S10 for ${today}`);
      this.state._lastPredictionIngest = today;

      if (this.a2a) {
        this.a2a.postDataReport('predictions', {
          date: today,
          total: predictions.length,
          stored,
          model: data.model,
        });
      }
    } catch (e) {
      logger.warn(`[LOOP] Prediction ingestion failed: ${e.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  HEALTH — Check all HF Spaces
  // ══════════════════════════════════════════

  async _healthCheck() {
    this.state.lastHealth = new Date().toISOString();

    if (this.watchdog) {
      await this.watchdog.checkAllSpaces();
    }
  }

  // ══════════════════════════════════════════
  //  REPORT — Structured report for Adam
  // ══════════════════════════════════════════

  async _generateReport() {
    this.state.lastReport = new Date().toISOString();

    if (!this.a2a) return;

    const evo = this.state.lastEvoStatus;
    const dataStatus = this.dataWorker?.getStatus();
    const watchdogTrends = this.watchdog?.getTrends();
    const evalStatus = this.feedbackLoop?.getStatus();

    const report = {
      type: 'periodic_report',
      level: 'INFO',
      message: `Eve periodic report @ ${this.state.lastReport}`,
      data: {
        evolution: evo || 'unknown',
        data_collection: {
          odds_fetches: dataStatus?.stats?.oddsFetches || 0,
          odds_stored: dataStatus?.stats?.oddsStored || 0,
          scores_source: 'espn',
          scores_fetches: dataStatus?.stats?.scoresFetches || 0,
          api_quota_remaining: dataStatus?.stats?.apiQuotaRemaining || 'dormant',
          last_odds_fetch: dataStatus?.lastOddsFetch,
          line_movements: dataStatus?.recentMovements?.length || 0,
        },
        evaluation: evalStatus || 'not_initialized',
        trends: watchdogTrends,
        insight: this.lastInsight,
        experiments: this.experimentStats,
        currentRole: AGENT_ROLES[this.analyzeRoleIndex],
        loop: {
          cycles: this.state.cycles,
          uptime: this._uptime(),
          errors_last_24h: this.state.errors.filter(e =>
            new Date(e.timestamp) > new Date(Date.now() - 24 * 60 * 60 * 1000)
          ).length,
        },
      },
    };

    this.a2a.postReport(report);
  }

  // ══════════════════════════════════════════
  //  COMMAND — Check for Adam's commands
  // ══════════════════════════════════════════

  async _checkCommands() {
    this.state.lastCommand = new Date().toISOString();
    // Commands are handled synchronously via API endpoint
    // This cycle is a no-op placeholder — commands execute immediately
    // when received via POST /api/v1/a2a/command
  }

  // ══════════════════════════════════════════
  //  HEARTBEAT — Smart Telegram status with insights
  // ══════════════════════════════════════════

  async _heartbeat() {
    this.state.lastHeartbeat = new Date().toISOString();

    if (!this.bot) return;

    const evo = this.state.lastEvoStatus;
    const dataStatus = this.dataWorker?.getStatus();
    const watchdogStatus = this.watchdog?.getStatus();
    const evalStatus = this.feedbackLoop?.getStatus();

    // Build concise Telegram message
    const lines = [
      `⚡ *${this.agentName} HEARTBEAT* — ${new Date().toLocaleTimeString('fr-FR', { timeZone: 'Europe/Paris' })}`,
      '',
    ];

    if (this.isMarketAgent) {
      // Market Intelligence agent heartbeat
      lines.push(`📊 *Role*: NBA Market Intelligence`);
      lines.push(`📡 *Odds fetches*: ${dataStatus?.stats?.oddsFetches || 0} | Line movements tracked: ${this.state._lastLineMovements?.length || 0}`);

      if (evo) {
        lines.push(`🎯 *S10*: Brier ${evo.brier?.toFixed(4) || '?'} | Gen ${evo.generation || '?'}`);
      }

      const experiments = this.state._marketExperimentsSubmitted || 0;
      lines.push(`🧪 *Experiments submitted*: ${experiments}`);
    } else if (this.isNBA) {
      // NBA-specific heartbeat (Eve)
      if (evo) {
        lines.push(`📊 *S10*: Brier ${evo.brier?.toFixed(4) || '?'} | Gen ${evo.generation || '?'} | Stag ${evo.stagnation ?? '?'}`);
      } else {
        lines.push('📊 *S10*: No data');
      }

      lines.push(`📡 *Data*: ${dataStatus?.stats?.scoresFetches || 0} ESPN | ${dataStatus?.stats?.oddsFetches || 0} odds | ${dataStatus?.stats?.injuriesFetches || 0} injuries`);

      if (evalStatus?.lastEval) {
        const e = evalStatus.lastEval;
        lines.push(`📈 *Yesterday*: ${e.correct}/${e.total} correct (${(e.accuracy * 100).toFixed(1)}%) | Brier ${e.brier?.toFixed(4)}`);
      }

      if (watchdogStatus?.trends?.brierTrend !== null && watchdogStatus?.trends?.brierTrend !== undefined) {
        const trend = watchdogStatus.trends.brierTrend;
        const emoji = trend < 0 ? '📉' : trend > 0 ? '📈' : '➡️';
        lines.push(`🔍 Brier trend (1h): ${emoji} ${trend > 0 ? '+' : ''}${trend}`);
      }

      // Experiment stats
      const es = this.experimentStats;
      if (es.submitted > 0 || es.dispatched > 0) {
        lines.push(`🧪 *Experiments*: ${es.submitted} queued, ${es.dispatched} running, ${es.completed} done, ${es.promoted} promoted`);
      }

      // Current agent role
      lines.push(`🤖 *Agent Role*: ${AGENT_ROLES[this.analyzeRoleIndex]}`);
    } else {
      // General agent heartbeat
      lines.push(`🤖 *Role*: General-purpose agent`);
      lines.push(`🌐 *Browser*: Chromium available`);
      lines.push(`🔧 *Infra*: VM SSH + GitHub + DBs`);
    }

    // Analyst insight (from _analyze cycle)
    if (this.lastInsight) {
      lines.push('');
      lines.push(`💡 *INSIGHT*: ${this.lastInsight.substring(0, 200)}`);
    }

    // Loop health
    lines.push('');
    lines.push(`🔄 *Loop*: ${this.state.cycles} cycles | Up ${this._uptime()}`);
    const recentErrors = this.state.errors.filter(e =>
      new Date(e.timestamp) > new Date(Date.now() - 60 * 60 * 1000)
    ).length;
    if (recentErrors > 0) {
      lines.push(`  ⚠️ ${recentErrors} errors in last hour`);
    }

    const msg = lines.join('\n');
    try {
      await this.bot.sendMessage(this.adminId, msg, { parse_mode: 'Markdown' });
    } catch (err) {
      logger.warn(`[LOOP] Heartbeat send failed: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  EVAL — Daily prediction evaluation (Phase 1)
  // ══════════════════════════════════════════

  /**
   * Check if eval should run. Evaluates yesterday AND 2 days ago (catch-up).
   * Runs after 08:00 UTC when most US games are final.
   * Checks every 15 min but only evals each date once.
   */
  async _maybeEval() {
    if (!this.isNBA) return; // NBA-only
    if (!this.running || !this.feedbackLoop) return;

    const now = new Date();
    const utcHour = now.getUTCHours();

    // Only eval after 08:00 UTC (most NBA games finish by ~05:00 UTC)
    if (utcHour < 8) return;

    // Dates to evaluate: yesterday and 2 days ago (catch-up for late-finishing games)
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

    // Track which dates we've evaluated today
    const today = now.toISOString().slice(0, 10);
    if (!this.state._evalDatesCompleted || !this.state._evalDatesCompleted.startsWith(today)) {
      this.state._evalDatesCompleted = today + ':';
    }

    const evaluated = this.state._evalDatesCompleted;

    // Eval yesterday if not done
    if (!evaluated.includes(yesterday)) {
      await this._evaluateDate(yesterday);
      this.state._evalDatesCompleted += yesterday + ',';
    }

    // Catch-up eval for 2 days ago (in case games finished late or we missed it)
    if (!evaluated.includes(twoDaysAgo)) {
      await this._evaluateDate(twoDaysAgo);
      this.state._evalDatesCompleted += twoDaysAgo + ',';
    }
  }

  async _evaluate() {
    // Called by _cycle('eval') for manual triggers
    const yesterday = this._yesterday();
    await this._evaluateDate(yesterday);
  }

  async _evaluateDate(dateStr) {
    this.state.lastEval = new Date().toISOString();

    if (!this.feedbackLoop) {
      logger.warn('[LOOP] FeedbackLoop not initialized — skipping eval');
      return;
    }

    logger.info(`[LOOP] Running eval for ${dateStr}`);
    const result = await this.feedbackLoop.evaluateDay(dateStr);

    if (result && !result.error) {
      logger.info(`[LOOP] Eval ${dateStr}: ${result.correct}/${result.total_games} (Brier ${result.brier_score})`);
    } else {
      logger.info(`[LOOP] Eval ${dateStr}: ${result?.error || 'no result'}`);
    }

    this._save();
  }

  // ══════════════════════════════════════════
  //  ANALYZE — 5 Specialized Agent Roles (Phase 2)
  // ══════════════════════════════════════════

  async _analyze() {
    this.state.lastAnalyze = new Date().toISOString();

    if (!this.getCompletion) return;

    // Non-NBA agents: simple status analysis, no NBA-specific actions
    if (!this.isNBA) {
      const prompt = `You are ${this.agentName}, a general-purpose autonomous AI agent.
You are NOT focused on NBA. You handle other projects and tasks.
Report your status briefly. If you have no pending tasks, say "STATUS: IDLE — awaiting commands".
Max 100 words.`;

      try {
        const result = await this.getCompletion([{ role: 'user', content: prompt }], {
          maxTokens: 200, temperature: 0.3,
        });
        if (result?.content) {
          this.lastInsight = result.content.substring(0, 300);
        }
      } catch (err) {
        logger.warn(`[LOOP] ${this.agentName} analyze failed: ${err.message}`);
      }
      return;
    }

    // ── NBA ANALYSIS — Rotating specialized agent roles ──

    // Select current role
    const currentRole = AGENT_ROLES[this.analyzeRoleIndex];
    this.analyzeRoleIndex = (this.analyzeRoleIndex + 1) % AGENT_ROLES.length;

    logger.info(`[LOOP] Analyze cycle — role: ${currentRole} (next: ${AGENT_ROLES[this.analyzeRoleIndex]})`);

    // Gather ALL available context
    const context = {
      evolution: this.state.lastEvoStatus,
      trends: this.watchdog?.getTrends(),
      recentEvals: await this.feedbackLoop?.getHistory(7).catch(() => []),
      dataStatus: this.dataWorker?.getStatus(),
      recentAlerts: this.watchdog?.alerts?.slice(-10) || [],
      loopHealth: {
        cycles: this.state.cycles,
        uptime: this._uptime(),
        errors24h: this.state.errors.filter(e =>
          new Date(e.timestamp) > new Date(Date.now() - 24 * 60 * 60 * 1000)
        ).length,
      },
    };

    // Market agent: add market-specific context
    if (this.isMarketAgent) {
      context.lineMovements = this.state._lastLineMovements || [];
      context.marketExperimentsSubmitted = this.state._marketExperimentsSubmitted || 0;
    }

    // Fetch recent experiment results from Supabase
    let recentExperimentsStr = 'none';
    if (this.infra?.pgPool) {
      try {
        const expResult = await this.infra.querySupabase(
          `SELECT experiment_type, description, status, result_brier, result_details
           FROM nba_experiments
           ORDER BY created_at DESC LIMIT 10`
        );
        if (expResult.rows?.length > 0) {
          recentExperimentsStr = expResult.rows.map(r =>
            `[${r.status}] ${r.experiment_type}: ${(r.description || '').substring(0, 80)}${r.result_brier ? ` → Brier ${r.result_brier}` : ''}`
          ).join('\n');
        }
      } catch (e) {
        logger.debug(`[LOOP] Failed to fetch recent experiments: ${e.message}`);
      }
    }

    // Build role-specific context
    const evo = this.state.lastEvoStatus;
    const evalHistory = context.recentEvals || [];
    const roleCtx = {
      brier: evo?.brier?.toFixed(4),
      features: evo?.features,
      population: evo?.population,
      generation: evo?.generation,
      stagnation: evo?.stagnation,
      mutationRate: evo?.mutationRate,
      modelType: 'ensemble',
      roi: evo?.roi,
      accuracy: evalHistory[0]?.accuracy ? (evalHistory[0].accuracy * 100).toFixed(1) + '%' : null,
      evalBriers: evalHistory.slice(0, 5).map(e => e.brier_score).filter(Boolean).join(', '),
      oddsFetches: context.dataStatus?.stats?.oddsFetches || 0,
      lineMovements: context.dataStatus?.recentMovements?.length || 0,
      recentExperiments: recentExperimentsStr,
    };

    // Build conversation memory context
    const memoryContext = this.analysisHistory.length > 0
      ? `\n\nPREVIOUS INSIGHTS (most recent first):\n${this.analysisHistory.slice(-5).reverse().map((h, i) =>
          `[${i + 1}] ${h.timestamp} (${h.role || 'general'}): ${h.insight.substring(0, 150)}${h.actions?.length ? ` → EXECUTED: ${h.actions.join(', ')}` : ''}`
        ).join('\n')}`
      : '';

    // Build execution feedback context
    const feedbackContext = this.executionLog.length > 0
      ? `\n\nRECENT EXECUTIONS & RESULTS:\n${this.executionLog.slice(-5).reverse().map((e, i) =>
          `[${i + 1}] ${e.timestamp}: ${e.action} → ${e.result} | Brier before: ${e.brierBefore?.toFixed(4) || '?'}, after: ${e.brierAfter?.toFixed(4) || 'pending'}`
        ).join('\n')}`
      : '';

    // Build the prompt based on role (market agent overrides)
    let prompt;
    if (this.isMarketAgent) {
      const oddsSummary = JSON.stringify(context.dataStatus?.stats || {});
      const movements = JSON.stringify((context.lineMovements || []).slice(0, 10));
      const clvData = context.recentEvals?.length
        ? JSON.stringify(context.recentEvals.slice(0, 5))
        : 'No CLV data yet';

      prompt = `You are the MARKET INTELLIGENCE agent for an NBA prediction model.
Your focus: analyzing betting market data to improve predictions.

Current odds data: ${oddsSummary}
Recent line movements: ${movements}
CLV tracking: ${clvData}
Evolution status: ${JSON.stringify(context.evolution || {})}
${memoryContext}
${feedbackContext}

Propose experiments that use market data to improve the model.
Output EXPERIMENT blocks:
EXPERIMENT: {"type":"market_test","description":"...","hypothesis":"...","params":{"features":["clv_spread","steam_indicator"]}}

Rules:
- Use NUMBERS from the data, not vague statements
- Focus ONLY on market-derived features
- Max 2-3 experiments per cycle. Quality over quantity.
- Do NOT repeat experiments from PREVIOUS INSIGHTS
- Max 300 words`;

    } else if (ROLE_PROMPTS[currentRole]) {
      // Use specialized role prompt
      prompt = ROLE_PROMPTS[currentRole](roleCtx);
      prompt += `\n\nCURRENT STATE:\n${JSON.stringify(context.evolution || {}, null, 2)}`;
      prompt += memoryContext;
      prompt += feedbackContext;
      prompt += `\n\nRules:
- Use NUMBERS, not vague statements
- Compare to targets: Brier < 0.20, ROI > 5%, accuracy > 65%
- IMPORTANT: Do NOT repeat experiments from RECENT EXECUTIONS above
- IMPORTANT: If Brier went UP after an action, do NOT repeat that action
- If Brier > 0.5, something is broken — only RECOMMENDATION: {"type":"evolve","action":"rollback"}
- If everything looks normal, say "STATUS: OK" and give brief summary`;
    } else {
      // Fallback generic prompt
      prompt = `You are ${this.agentName}, an NBA quant analyst AI (role: ${currentRole}). Analyze and give recommendations.
CURRENT STATE: ${JSON.stringify(context, null, 2)}
${memoryContext}${feedbackContext}
Max 200 words.`;
    }

    try {
      const result = await this.getCompletion([{ role: 'user', content: prompt }], {
        maxTokens: 600,
        temperature: 0.4,
      });

      if (result?.content) {
        this.lastInsight = result.content.substring(0, 500);

        // Post to A2A
        if (this.a2a) {
          this.a2a.postReport({
            type: 'analyst_insight',
            level: 'INFO',
            message: `[${currentRole}] ${result.content.substring(0, 200)}`,
            data: {
              role: currentRole,
              fullAnalysis: result.content,
              model: result.model,
              context: {
                brier: context.evolution?.brier,
                stagnation: context.evolution?.stagnation,
                generation: context.evolution?.generation,
              },
            },
          });
        }

        // Parse EXPERIMENT blocks from the analysis output
        const expMatches = result.content.matchAll(/EXPERIMENT:\s*(\{[\s\S]*?\})/g);
        for (const m of expMatches) {
          try {
            const exp = JSON.parse(m[1]);
            exp.agent_name = currentRole;
            await this._submitExperiment(exp);
          } catch (e) {
            logger.debug(`[LOOP] Failed to parse EXPERIMENT block: ${e.message}`);
          }
        }

        // Market agent: also track experiments via A2A
        if (this.isMarketAgent) {
          const experiments = [];
          for (const line of result.content.split('\n')) {
            const expMatch = line.match(/EXPERIMENT:\s*(\{.+\})/i);
            if (expMatch) {
              try {
                const exp = JSON.parse(expMatch[1]);
                if (exp.type || exp.name) experiments.push(exp);
              } catch (e) {}
            }
          }
          if (experiments.length > 0 && this.a2a) {
            for (const exp of experiments) {
              this.a2a.postReport({
                type: 'market_experiment',
                level: 'INFO',
                message: `EXPERIMENT: ${exp.description || exp.name || ''}`.substring(0, 200),
                data: { experiment: exp, source: this.agentName },
              });
            }
            this.state._marketExperimentsSubmitted = (this.state._marketExperimentsSubmitted || 0) + experiments.length;
          }
        }

        // Auto-execute RECOMMENDATION blocks: Karpathy pattern (not for market agent)
        let executedActions = [];
        if (this.autoExecuteEnabled && !this.isMarketAgent) {
          executedActions = await this._tryAutoExecute(result.content, context);
        }

        // Save to conversation memory (with role)
        this.analysisHistory.push({
          timestamp: new Date().toISOString(),
          role: currentRole,
          insight: result.content,
          actions: executedActions,
          brier: context.evolution?.brier,
          model: result.model,
        });
        if (this.analysisHistory.length > this.MAX_ANALYSIS_HISTORY) {
          this.analysisHistory = this.analysisHistory.slice(-this.MAX_ANALYSIS_HISTORY);
        }

        logger.info(`[LOOP] Analyst insight generated (${currentRole}, ${result.model}): ${result.content.substring(0, 100)}...`);
      }
    } catch (err) {
      logger.warn(`[LOOP] Analyze failed (${currentRole}): ${err.message}`);
    }

    this._save();
  }

  // ══════════════════════════════════════════
  //  EXPERIMENT SUBMISSION — Write to Supabase queue
  // ══════════════════════════════════════════

  /**
   * Submit an experiment to the nba_experiments queue in Supabase.
   * Max 50 pending experiments at any time.
   */
  async _submitExperiment(exp) {
    if (!this.infra?.pgPool) {
      logger.debug('[EXPERIMENT] No infra bridge — cannot submit experiment');
      return;
    }

    try {
      // Check queue size — max 50 pending
      const countResult = await this.infra.querySupabase(
        `SELECT COUNT(*) as cnt FROM nba_experiments WHERE status = 'pending'`
      );
      const pendingCount = parseInt(countResult.rows?.[0]?.cnt || '0');
      if (pendingCount >= 50) {
        logger.info(`[EXPERIMENT] Queue full (${pendingCount}/50 pending). Skipping: ${(exp.description || '').substring(0, 60)}`);
        return;
      }

      const id = `exp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const agentName = exp.agent_name || 'unknown';
      const expType = exp.type || 'general';
      const description = (exp.description || '').substring(0, 500);
      const hypothesis = (exp.hypothesis || '').substring(0, 500);
      const params = JSON.stringify(exp.params || {});
      const priority = exp.priority || 5;
      const baselineBrier = this.state.lastEvoStatus?.brier || null;

      await this.infra.querySupabase(
        `INSERT INTO nba_experiments (experiment_id, agent_name, experiment_type, description, hypothesis, params, priority, status, target_space, baseline_brier, created_at)
         VALUES ('${id}', '${agentName}', '${expType}', '${description.replace(/'/g, "''")}', '${hypothesis.replace(/'/g, "''")}', '${params.replace(/'/g, "''")}'::jsonb, ${priority}, 'pending', 'S11', ${baselineBrier || 'NULL'}, NOW())`
      );

      this.experimentStats.submitted++;
      logger.info(`[EXPERIMENT] Submitted: ${id} (${expType}) by ${agentName}: ${description.substring(0, 60)}`);

      if (this.a2a) {
        this.a2a.postReport({
          type: 'experiment_submitted',
          level: 'INFO',
          message: `Experiment queued: [${agentName}] ${expType} — ${description.substring(0, 100)}`,
          data: { id, agentName, expType, description, priority },
        });
      }
    } catch (err) {
      logger.warn(`[EXPERIMENT] Submit failed: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  EXPERIMENT DISPATCH — S11 runner
  // ══════════════════════════════════════════

  /**
   * Experiment scheduler cycle (runs every 3 min).
   * 1. Query Supabase for next pending experiment
   * 2. Check if S11 is idle
   * 3. Dispatch experiment to S11
   * 4. Wait for result (5 min timeout)
   * 5. Store results, auto-promote if improved by 0.002+
   */
  async _runExperiment() {
    this.state.lastExperiment = new Date().toISOString();

    if (!this.isNBA) return;
    if (!this.infra?.pgPool) return;

    try {
      // S11 polls its own Supabase queue — Eve just monitors and promotes results.
      // Check for completed experiments that need promotion.

      // 1. Check queue depth (for logging)
      const queueResult = await this.infra.querySupabase(
        `SELECT status, COUNT(*) as n FROM nba_experiments GROUP BY status`
      );
      const counts = {};
      for (const row of (queueResult.rows || [])) counts[row.status] = parseInt(row.n);
      logger.info(`[EXPERIMENT] Queue: ${counts.pending || 0} pending, ${counts.running || 0} running, ${counts.completed || 0} completed, ${counts.failed || 0} failed`);

      // Auto-trigger Kaggle GPU runner if there are GPU experiments pending
      if (counts.pending > 0) {
        try {
          const gpuResult = await this.infra.querySupabase(
            `SELECT COUNT(*) as n FROM nba_experiments WHERE status = 'pending' AND target_space IN ('colab', 'gpu', 'kaggle')`
          );
          const gpuPending = parseInt(gpuResult.rows?.[0]?.n || 0);
          if (gpuPending > 0) {
            const { triggerKaggle } = require('./browser');
            const vmBridge = require('./vm-bridge');
            // Only trigger if we have a VM bridge instance
            if (this.infra?.vmBridge) {
              await triggerKaggle(this.infra.vmBridge);
              logger.info(`[EXPERIMENT] Triggered Kaggle GPU runner for ${gpuPending} pending GPU experiments`);
            }
          }
        } catch (e) {
          logger.debug(`[EXPERIMENT] Kaggle trigger skipped: ${e.message}`);
        }
      }

      // 2. Check for recently completed experiments that haven't been promoted
      const completedResult = await this.infra.querySupabase(
        `SELECT * FROM nba_experiments WHERE status = 'completed' AND promoted_at IS NULL AND result_brier IS NOT NULL ORDER BY completed_at DESC LIMIT 5`
      );

      for (const experiment of (completedResult.rows || [])) {
        const resultBrier = parseFloat(experiment.result_brier);
        const baselineBrier = parseFloat(experiment.baseline_brier) || this.state._lastBrier || 0.25;

        logger.info(`[EXPERIMENT] Evaluating ${experiment.experiment_id}: result=${resultBrier?.toFixed(4)}, baseline=${baselineBrier.toFixed(4)}`);

        // Auto-promote if result beats baseline by 0.002+
        if (resultBrier && baselineBrier && (baselineBrier - resultBrier) >= 0.002) {
          logger.info(`[EXPERIMENT] PROMOTION: ${experiment.experiment_id} improved Brier by ${(baselineBrier - resultBrier).toFixed(4)}`);

          try {
            const params = typeof experiment.params === 'string' ? JSON.parse(experiment.params) : experiment.params;

            if (experiment.experiment_type === 'feature_test' && params.features_to_add) {
              await fetch(`${this.S10_URL}/api/inject-features`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ features: params.features_to_add, source: `experiment:${experiment.experiment_id}` }),
                signal: AbortSignal.timeout(10000),
              });
            } else if (experiment.experiment_type === 'config_change' && params) {
              await fetch(`${this.S10_URL}/api/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
                signal: AbortSignal.timeout(10000),
              });
            }

          await this.infra.querySupabase(
            `UPDATE nba_experiments SET status = 'promoted', promoted_at = NOW() WHERE experiment_id = '${experiment.experiment_id}'`
          );
          this.experimentStats.promoted++;

          // Telegram notification for promotions
          if (this.bot) {
            await this.bot.sendMessage(this.adminId,
              `🏆 *EXPERIMENT PROMOTED*\n\n` +
              `ID: \`${experiment.experiment_id}\`\n` +
              `Type: ${experiment.experiment_type}\n` +
              `Agent: ${experiment.agent_name}\n` +
              `Brier: ${baselineBrier.toFixed(4)} → ${resultBrier.toFixed(4)} (${(baselineBrier - resultBrier).toFixed(4)} improvement)\n\n` +
              `${experiment.description}`,
              { parse_mode: 'Markdown' }
            ).catch(() => {});
          }

          if (this.a2a) {
            this.a2a.postReport({
              type: 'experiment_promoted',
              level: 'INFO',
              message: `Experiment promoted to S10: ${experiment.experiment_id} (Brier ${baselineBrier.toFixed(4)} → ${resultBrier.toFixed(4)})`,
              data: { id: experiment.experiment_id, baselineBrier, resultBrier, improvement: baselineBrier - resultBrier },
            });
          }
        } catch (e) {
          logger.warn(`[EXPERIMENT] Promotion failed for ${experiment.experiment_id}: ${e.message}`);
        }
        } else {
          logger.debug(`[EXPERIMENT] ${experiment.experiment_id}: no improvement (need 0.002+, got ${(baselineBrier - resultBrier).toFixed(4)})`);
        }
      }
    } catch (err) {
      logger.warn(`[EXPERIMENT] Scheduler error: ${err.message}`);
    }

    this._save();
  }

  // ══════════════════════════════════════════
  //  AUTO-EXECUTE — Karpathy pattern (act on insights)
  // ══════════════════════════════════════════

  async _tryAutoExecute(insight, context) {
    if (!this.isNBA || !this.callS10) return [];

    // ── PARSE STRUCTURED RECOMMENDATIONS ──
    // New format: RECOMMENDATION: {"type":"code|config|restart|evolve", ...}
    // Legacy format: ACTION: set_config(...) / diversify / rollback / inject_features(...)
    const recommendations = [];
    for (const line of insight.split('\n')) {
      // New structured format
      const recMatch = line.match(/RECOMMENDATION:\s*(\{.+\})/i);
      if (recMatch) {
        try {
          const rec = JSON.parse(recMatch[1]);
          if (rec.type) recommendations.push(rec);
        } catch (e) {
          logger.debug(`[AUTO-EXEC] Failed to parse recommendation JSON: ${recMatch[1].substring(0, 80)}`);
        }
        continue;
      }

      // Legacy ACTION format — convert to structured recommendations
      const actionMatch = line.match(/ACTION:\s*(.+)/i);
      if (!actionMatch) continue;
      const raw = actionMatch[1].trim();

      if (/^set_config/i.test(raw)) {
        const jsonMatch = raw.match(/\{([^}]+)\}/);
        const kvMatch = raw.match(/\(([^)]+)\)/);
        const params = {};
        if (jsonMatch) {
          try { Object.assign(params, JSON.parse(`{${jsonMatch[1]}}`)); } catch {}
        } else if (kvMatch) {
          for (const pair of kvMatch[1].split(',')) {
            const [k, v] = pair.split('=').map(s => s.trim().replace(/['"]/g, ''));
            if (k && v) params[k] = isNaN(v) ? v : parseFloat(v);
          }
        }
        if (Object.keys(params).length > 0) {
          // Convert each param to a config recommendation
          for (const [key, value] of Object.entries(params)) {
            recommendations.push({ type: 'config', key, value });
          }
        }
      } else if (/^inject_features/i.test(raw)) {
        const featureMatch = raw.match(/\(([^)]+)\)/);
        if (featureMatch) {
          const features = featureMatch[1].split(',').map(f => f.trim().replace(/['"]/g, '')).filter(Boolean);
          if (features.length > 0) recommendations.push({ type: 'evolve', action: 'inject_features', features });
        }
      } else if (/^rollback/i.test(raw)) {
        recommendations.push({ type: 'evolve', action: 'rollback' });
      } else if (/^diversify/i.test(raw)) {
        recommendations.push({ type: 'evolve', action: 'diversify' });
      } else {
        logger.debug(`[AUTO-EXEC] Unrecognized action: ${raw.substring(0, 80)}`);
      }
    }

    if (recommendations.length === 0) return [];

    // ── DEDUP: Skip recommendations identical to recent executions (last 30 min) ──
    const recentCutoff = Date.now() - 30 * 60 * 1000;
    const recentActions = this.executionLog
      .filter(e => new Date(e.timestamp).getTime() > recentCutoff)
      .map(e => e.action);

    const dedupedRecs = recommendations.filter(rec => {
      const sig = this._recommendationSignature(rec);
      if (recentActions.includes(sig)) {
        logger.info(`[AUTO-EXEC] DEDUP: Skipping ${sig} (already executed in last 30min)`);
        return false;
      }
      return true;
    });

    if (dedupedRecs.length === 0) {
      logger.info('[AUTO-EXEC] All recommendations skipped (dedup). Waiting for new insights.');
      return [];
    }

    // ── COOLDOWN: Max 3 auto-executions per hour (code tasks exempt — they create PRs, not direct changes) ──
    const hourCutoff = Date.now() - 60 * 60 * 1000;
    const nonCodeExecsThisHour = this.executionLog
      .filter(e => new Date(e.timestamp).getTime() > hourCutoff && !e.action.startsWith('code_task:'))
      .length;
    const directRecs = dedupedRecs.filter(r => r.type !== 'code');
    if (nonCodeExecsThisHour >= 3 && directRecs.length > 0) {
      logger.info(`[AUTO-EXEC] COOLDOWN: ${nonCodeExecsThisHour} direct executions this hour (max 3). Skipping non-code recs.`);
      // Still allow code tasks through — they create PRs, not direct mutations
      const codeOnly = dedupedRecs.filter(r => r.type === 'code');
      if (codeOnly.length === 0) return [];
      dedupedRecs.length = 0;
      dedupedRecs.push(...codeOnly);
    }

    // ── SAFETY GATE: Monotonic ratchet (for direct execution only) ──
    const currentBrier = context.evolution?.brier;
    let bestCheckpointBrier = null;
    try {
      const cpResp = await this.callS10('/api/checkpoint/best');
      bestCheckpointBrier = cpResp?.brier;
    } catch (e) {
      logger.debug('[AUTO-EXEC] No checkpoint data available for ratchet check');
    }

    const hasRollback = dedupedRecs.some(r => r.type === 'evolve' && r.action === 'rollback');
    const hasCodeOnly = dedupedRecs.every(r => r.type === 'code');

    // Ratchet blocks direct mutations but NOT code tasks (those create PRs for review)
    if (!hasRollback && !hasCodeOnly && bestCheckpointBrier && currentBrier && currentBrier > bestCheckpointBrier + 0.005) {
      logger.info(`[AUTO-EXEC] Direct execution BLOCKED: Brier ${currentBrier?.toFixed(4)} > checkpoint ${bestCheckpointBrier?.toFixed(4)} + 0.005`);
      if (this.a2a) {
        this.a2a.postReport({
          type: 'auto_execute_blocked',
          level: 'WARNING',
          message: `Ratchet blocked direct action(s). Brier ${currentBrier?.toFixed(4)} too far from best ${bestCheckpointBrier?.toFixed(4)}. Code tasks still allowed.`,
        });
      }
      // Filter to only code tasks
      const codeOnly = dedupedRecs.filter(r => r.type === 'code');
      if (codeOnly.length === 0) return [];
      dedupedRecs.length = 0;
      dedupedRecs.push(...codeOnly);
    }

    // ── EXECUTE RECOMMENDATIONS BY TYPE ──
    const executedActions = [];

    for (const rec of dedupedRecs) {
      try {
        let result = 'unknown';

        switch (rec.type) {
          // ── CODE: Route to Code Agent (creates branch + PR) ──
          case 'code': {
            if (this.codeAgent) {
              this.codeAgent.addTask({
                repo: rec.repo || 'nomos-nba-agent',
                description: rec.description || 'LLM-recommended code improvement',
                files: rec.files || [],
                context: rec.context || '',
              });
              this.codeAgent.processQueue().catch(err =>
                logger.error(`[AUTO-EXEC] Code task failed: ${err.message}`)
              );
              result = `code_task: ${(rec.description || '').substring(0, 80)}`;
              logger.info(`[AUTO-EXEC] Code Agent task queued: ${result}`);
            } else {
              logger.warn('[AUTO-EXEC] Code recommendation received but codeAgent not available');
              result = `code_task_skipped: no codeAgent`;
            }
            break;
          }

          // ── CONFIG: Set evolution parameters via S10 API ──
          case 'config': {
            const params = { [rec.key]: rec.value };
            await this.callS10('/api/config', { method: 'POST', body: JSON.stringify(params) });
            result = `set_config(${rec.key}=${rec.value})`;
            logger.info(`[AUTO-EXEC] Config applied: ${result}`);
            break;
          }

          // ── RESTART: Restart HF Space via Space Executor ──
          case 'restart': {
            const target = (rec.target || '').toUpperCase();
            if (this.spaces && target) {
              try {
                await this.spaces.restart(target);
                result = `restart(${target})`;
                logger.info(`[AUTO-EXEC] Space restarted: ${target}`);
              } catch (err) {
                result = `restart_failed(${target}): ${err.message}`;
                logger.warn(`[AUTO-EXEC] Space restart failed: ${err.message}`);
              }
            } else {
              result = `restart_skipped: no spaceExecutor or no target`;
              logger.warn(`[AUTO-EXEC] Restart skipped — spaceExecutor: ${!!this.spaces}, target: ${target}`);
            }
            break;
          }

          // ── EVOLVE: Evolution commands (diversify, inject, rollback) via S10 API ──
          case 'evolve': {
            const action = rec.action;
            if (action === 'diversify') {
              await this.callS10('/api/command', { method: 'POST', body: JSON.stringify({ command: 'diversify' }) });
              result = 'diversify';
              logger.info('[AUTO-EXEC] Executed: diversify');
            } else if (action === 'inject_features' && rec.features?.length > 0) {
              await this.callS10('/api/features/inject', {
                method: 'POST',
                body: JSON.stringify({ features: rec.features }),
              });
              result = `inject_features(${rec.features.join(',')})`;
              logger.info(`[AUTO-EXEC] Executed: ${result}`);
            } else if (action === 'rollback') {
              await this.callS10('/api/checkpoint/restore', { method: 'POST', body: '{}' });
              result = 'rollback to best checkpoint';
              logger.info('[AUTO-EXEC] Executed: rollback to best checkpoint');
            } else {
              result = `evolve_unknown(${action})`;
              logger.debug(`[AUTO-EXEC] Unknown evolve action: ${action}`);
            }
            break;
          }

          default:
            logger.debug(`[AUTO-EXEC] Unknown recommendation type: ${rec.type}`);
            result = `unknown_type(${rec.type})`;
        }

        executedActions.push(result);

        // Track execution for recursive feedback
        this.executionLog.push({
          timestamp: new Date().toISOString(),
          action: result,
          brierBefore: currentBrier,
          brierAfter: null, // Will be filled by _checkExecutionFeedback
          result: rec.type === 'code' ? 'pr_pending' : 'pending',
        });
        if (this.executionLog.length > this.MAX_EXECUTION_LOG) {
          this.executionLog = this.executionLog.slice(-this.MAX_EXECUTION_LOG);
        }

      } catch (err) {
        const sig = this._recommendationSignature(rec);
        logger.warn(`[AUTO-EXEC] ${rec.type} failed: ${err.message}`);
        this.executionLog.push({
          timestamp: new Date().toISOString(),
          action: sig,
          brierBefore: currentBrier,
          brierAfter: null,
          result: `FAILED: ${err.message}`,
        });
      }
    }

    // Create checkpoint after successful direct executions (not code tasks)
    const directExecutions = executedActions.filter(a => !a.startsWith('code_task'));
    if (directExecutions.length > 0) {
      try {
        await this.callS10('/api/checkpoint', { method: 'POST', body: '{}' });
        logger.info('[AUTO-EXEC] Post-execute checkpoint created');
      } catch (e) {
        logger.warn(`[AUTO-EXEC] Checkpoint after auto-execute failed: ${e.message}`);
      }

      // Schedule feedback check: after 20 min, compare Brier to see if it improved
      setTimeout(() => this._checkExecutionFeedback(currentBrier), 20 * 60 * 1000);
    }

    if (executedActions.length > 0 && this.a2a) {
      this.a2a.postReport({
        type: 'auto_execute',
        level: 'INFO',
        message: `Executed ${executedActions.length} action(s): ${executedActions.join(' | ')}`,
        data: { actions: executedActions, currentBrier, bestCheckpointBrier },
      });
    }

    return executedActions;
  }

  /**
   * Generate a dedup signature for a recommendation
   */
  _recommendationSignature(rec) {
    switch (rec.type) {
      case 'code':
        return `code_task: ${(rec.description || '').substring(0, 80)}`;
      case 'config':
        return `set_config(${rec.key}=${rec.value})`;
      case 'restart':
        return `restart(${(rec.target || '').toUpperCase()})`;
      case 'evolve':
        if (rec.action === 'inject_features') return `inject_features(${(rec.features || []).sort().join(',')})`;
        return rec.action || 'evolve';
      default:
        return `${rec.type}:${JSON.stringify(rec).substring(0, 60)}`;
    }
  }

  // ══════════════════════════════════════════
  //  EXECUTION FEEDBACK — Recursive learning
  // ══════════════════════════════════════════

  async _checkExecutionFeedback(brierBefore) {
    try {
      const evo = await this.fetchEvolution();
      const brierAfter = evo?.brier || evo?.best_brier;

      if (!brierAfter) return;

      // Update pending execution logs with actual result
      for (const entry of this.executionLog) {
        if (entry.result === 'pending') {
          entry.brierAfter = brierAfter;
          entry.result = brierAfter < brierBefore
            ? `improvement (${brierBefore?.toFixed(4)} → ${brierAfter.toFixed(4)})`
            : brierAfter > brierBefore
              ? `regression (${brierBefore?.toFixed(4)} → ${brierAfter.toFixed(4)})`
              : `neutral (${brierAfter.toFixed(4)})`;
        }
      }

      const delta = brierBefore ? brierAfter - brierBefore : 0;
      const emoji = delta < 0 ? '📉' : delta > 0 ? '📈' : '➡️';

      logger.info(`[LOOP] Execution feedback: Brier ${brierBefore?.toFixed(4)} → ${brierAfter.toFixed(4)} (${emoji} ${delta > 0 ? '+' : ''}${delta.toFixed(4)})`);

      if (this.a2a) {
        this.a2a.postReport({
          type: 'execution_feedback',
          level: delta > 0.005 ? 'WARNING' : 'INFO',
          message: `${emoji} Post-execution Brier: ${brierBefore?.toFixed(4)} → ${brierAfter.toFixed(4)}`,
          data: { brierBefore, brierAfter, delta },
        });
      }
    } catch (err) {
      logger.debug(`[LOOP] Execution feedback check failed: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  AUTO-INJECT — Research findings → Feature injection
  // ══════════════════════════════════════════

  async _autoInjectFromResearch(findings) {
    if (!this.getCompletion || !this.callS10) return;

    const actionable = findings.filter(f => f.actionable && f.relevance >= 0.6);
    if (actionable.length === 0) return;

    // Ask LLM to extract concrete feature names from findings
    const prompt = `Extract concrete NBA feature names from these research findings for our genetic algorithm.

FINDINGS:
${actionable.map(f => `- ${f.topic}: ${f.finding}`).join('\n')}

CURRENT FEATURE CATEGORIES: rolling_performance, four_factors, momentum, rest_schedule, opponent_adjusted, matchup_elo, market_microstructure, context, referee, player_impact

Output ONLY a JSON array of feature names that could be added. Use snake_case.
Example: ["pace_differential_5g", "contested_rebound_rate", "clutch_ft_pct"]
If no concrete features can be extracted, output: []
Max 5 features.`;

    try {
      const result = await this.getCompletion([{ role: 'user', content: prompt }], {
        maxTokens: 200,
        temperature: 0.2,
      });

      if (!result?.content) return;

      // Parse JSON array from response
      const jsonMatch = result.content.match(/\[[\s\S]*?\]/);
      if (!jsonMatch) return;

      const features = JSON.parse(jsonMatch[0]);
      if (!Array.isArray(features) || features.length === 0) return;

      // Inject top 3 features
      const toInject = features.slice(0, 3);
      await this.callS10('/api/features/inject', {
        method: 'POST',
        body: JSON.stringify({ features: toInject, source: 'research_auto' }),
      });

      logger.info(`[LOOP] Auto-injected ${toInject.length} features from research: ${toInject.join(', ')}`);

      if (this.a2a) {
        this.a2a.postReport({
          type: 'research_auto_inject',
          level: 'INFO',
          message: `Auto-injected ${toInject.length} features from research`,
          data: { features: toInject, findings: actionable.map(f => f.topic) },
        });
      }
    } catch (err) {
      logger.debug(`[LOOP] Auto-inject from research failed: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  RESEARCH — Autonomous web research (Phase 3)
  // ══════════════════════════════════════════

  async _research() {
    this.state.lastResearch = new Date().toISOString();

    if (!this.researchAgent) {
      logger.debug('[LOOP] ResearchAgent not initialized — skipping research');
      return;
    }

    // Build context from current system state
    const evo = this.state.lastEvoStatus;
    const evalHistory = await this.feedbackLoop?.getHistory(7).catch(() => []);
    const latestEval = evalHistory?.[0];

    const context = {
      brier: evo?.brier,
      features: evo?.features,
      stagnation: evo?.stagnation,
      accuracy: latestEval?.accuracy,
      generation: evo?.generation,
    };

    logger.info('[LOOP] Starting research cycle');
    const findings = await this.researchAgent.researchCycle(context);

    if (findings && findings.length > 0) {
      logger.info(`[LOOP] Research complete: ${findings.length} findings`);

      // Auto-inject: extract feature names from actionable findings and inject
      await this._autoInjectFromResearch(findings);
    }

    this._save();
  }

  // ══════════════════════════════════════════
  //  COMMAND HANDLERS — Called by A2A Protocol
  // ══════════════════════════════════════════

  /**
   * Execute a command from Adam.
   * This is the callback passed to A2AProtocol.
   */
  async executeCommand(command) {
    const { action, params } = command;

    switch (action) {
      // GA config changes (Adam's prerogative)
      case 'set_config':
        return await this.callS10('/api/config', params);

      case 'diversify':
        return await this.callS10('/api/command', { command: 'diversify' });

      case 'reset':
        return await this.callS10('/api/reset');

      // Data operations
      case 'fetch_odds':
        return await this.dataWorker?.fetchOdds();

      case 'fetch_scores':
        return await this.dataWorker?.fetchScores();

      case 'compute_clv':
        return await this.dataWorker?.computeCLV();

      // Eval operations (Phase 1)
      case 'eval_day':
        return await this.feedbackLoop?.evaluateDay(params?.date || this._yesterday());

      case 'eval_trend':
        return await this.feedbackLoop?.getTrend();

      // Space management
      case 'restart_space':
        return await this.spaces?.deployToSpace(params.space || 'S10');

      case 'health_check':
        return await this.watchdog?.checkAllSpaces();

      // Loop control
      case 'pause_loop':
        this.stop();
        return { status: 'paused' };

      case 'resume_loop':
        this.start();
        return { status: 'resumed' };

      // Force cycles
      case 'force_analyze':
        this._cycle('analyze').catch(e => logger.error(`Force analyze: ${e.message}`));
        return { status: 'triggered', type: 'analyze' };

      case 'force_research':
        this._cycle('research').catch(e => logger.error(`Force research: ${e.message}`));
        return { status: 'triggered', type: 'research' };

      case 'force_eval':
        this._cycle('eval').catch(e => logger.error(`Force eval: ${e.message}`));
        return { status: 'triggered', type: 'eval' };

      case 'force_experiment':
        this._cycle('experiment').catch(e => logger.error(`Force experiment: ${e.message}`));
        return { status: 'triggered', type: 'experiment' };

      // Status queries
      case 'get_status':
        return this.getStatus();

      case 'get_trends':
        return this.watchdog?.getTrends();

      case 'get_data_status':
        return this.dataWorker?.getStatus();

      case 'get_experiment_stats':
        return this.experimentStats;

      default:
        throw new Error(`Unknown command: ${action}`);
    }
  }

  // ══════════════════════════════════════════
  //  STATUS
  // ══════════════════════════════════════════

  getStatus() {
    return {
      version: 'v6-multi-agent-experiments',
      running: this.running,
      state: this.state,
      uptime: this._uptime(),
      lastInsight: this.lastInsight ? this.lastInsight.substring(0, 200) : null,
      currentRole: AGENT_ROLES[this.analyzeRoleIndex],
      nextRole: AGENT_ROLES[(this.analyzeRoleIndex + 1) % AGENT_ROLES.length],
      experimentStats: this.experimentStats,
      watchdog: this.watchdog?.getStatus(),
      dataWorker: this.dataWorker?.getStatus(),
      feedbackLoop: this.feedbackLoop?.getStatus(),
      researchAgent: this.researchAgent?.getStatus(),
      a2a: this.a2a?.getStatus(),
    };
  }

  _uptime() {
    if (!this.state.startedAt) return 'not started';
    const ms = Date.now() - new Date(this.state.startedAt).getTime();
    const h = Math.floor(ms / 3600000);
    const m = Math.floor((ms % 3600000) / 60000);
    return `${h}h${m}m`;
  }

  _yesterday() {
    return new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  }

  // ══════════════════════════════════════════
  //  PERSISTENCE
  // ══════════════════════════════════════════

  _load() {
    try {
      if (!fs.existsSync(LOOP_DATA_DIR)) fs.mkdirSync(LOOP_DATA_DIR, { recursive: true });
      // Try v6 state first, fall back to v5, then v4
      const v6File = STATE_FILE;
      const v5File = path.join(LOOP_DATA_DIR, 'state-v5.json');
      const v4File = path.join(LOOP_DATA_DIR, 'state-v4.json');
      const fileToLoad = fs.existsSync(v6File) ? v6File : (fs.existsSync(v5File) ? v5File : (fs.existsSync(v4File) ? v4File : null));
      if (fileToLoad) {
        const saved = JSON.parse(fs.readFileSync(fileToLoad, 'utf8'));
        this.state = { ...this.state, ...saved };
      }
    } catch (e) {
      logger.warn(`[LOOP] Load state: ${e.message}`);
    }
  }

  _save() {
    try {
      fs.writeFileSync(STATE_FILE, JSON.stringify(this.state, null, 2));
    } catch (e) {
      logger.warn(`[LOOP] Save state: ${e.message}`);
    }
  }
}

module.exports = AgenticLoop;
