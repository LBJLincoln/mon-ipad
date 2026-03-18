/**
 * Agentic Loop v5 — Intelligent Autonomous NBA Quant Operations
 *
 * Builds on v4's data-driven foundation with:
 *   - EVAL cycle: compare predictions to real game outcomes (feedback loop)
 *   - ANALYZE cycle: LLM-powered insight generation from collected data
 *   - RESEARCH cycle: autonomous web research for model improvement
 *
 * Design principles:
 *   1. DATA > LLM — Fetch real data, compute real metrics. No hallucinations.
 *   2. OBSERVE > ACT — Watch and report. Config changes are Adam's job.
 *   3. STRUCTURED OUTPUT — All observations go to A2A inbox for Adam.
 *   4. FEEDBACK LOOP — Predictions vs reality. This changes everything.
 *   5. INTELLIGENT REASONING — Eve THINKS about data, not just relays it.
 *
 * Cycles:
 *   OBSERVE   (5 min)   — Poll S10, feed metrics to Watchdog
 *   DATA      (30 min)  — Fetch odds + scores from APIs, store in Supabase
 *   HEALTH    (10 min)  — Check all 5 HF Spaces are up
 *   REPORT    (30 min)  — Generate structured report for Adam (A2A)
 *   COMMAND   (2 min)   — Check A2A command queue from Adam
 *   HEARTBEAT (60 min)  — Telegram summary to admin (now with insights)
 *   EVAL      (15 min)  — Check & eval yesterday + 2 days ago (once per date/day)
 *   ANALYZE   (30 min)  — LLM reasoning over all collected data — near real-time awareness
 *   RESEARCH  (4 hours) — Autonomous web research — 6x/day
 */

const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const LOOP_DATA_DIR = '/data/agentic-loop';
const STATE_FILE = path.join(LOOP_DATA_DIR, 'state-v5.json');

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

    // Timers
    this.timers = {};
    this.running = false;

    // Last analyst insight (shown in heartbeat)
    this.lastInsight = null;

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

    logger.info('[LOOP] Agentic Loop v5 started — intelligent autonomous operations');

    // OBSERVE: Every 5 min
    this.timers.observe = setInterval(() => this._cycle('observe'), 5 * 60 * 1000);

    // DATA: Every 30 min
    this.timers.data = setInterval(() => this._cycle('data'), 30 * 60 * 1000);

    // HEALTH: Every 10 min
    this.timers.health = setInterval(() => this._cycle('health'), 10 * 60 * 1000);

    // REPORT: Every 30 min (offset from DATA by 15 min)
    setTimeout(() => {
      this.timers.report = setInterval(() => this._cycle('report'), 30 * 60 * 1000);
    }, 15 * 60 * 1000);

    // COMMAND: Every 2 min (fast poll for Adam's commands)
    this.timers.command = setInterval(() => this._cycle('command'), 2 * 60 * 1000);

    // HEARTBEAT: Every 60 min
    this.timers.heartbeat = setInterval(() => this._cycle('heartbeat'), 60 * 60 * 1000);

    // EVAL: Check every 15 min, runs once per day per date (yesterday + 2 days ago catch-up)
    this.timers.eval = setInterval(() => this._maybeEval(), 15 * 60 * 1000);

    // ANALYZE: Every 30 min — Eve stays aware of the system in near real-time
    this.timers.analyze = setInterval(() => this._cycle('analyze'), 30 * 60 * 1000);

    // RESEARCH: Every 4 hours — 6x/day gives solid coverage with free LLM models
    this.timers.research = setInterval(() => this._cycle('research'), 4 * 60 * 60 * 1000);

    // Run initial cycles
    setTimeout(() => this._cycle('observe'), 5000);    // 5s after start
    setTimeout(() => this._cycle('health'), 15000);     // 15s
    setTimeout(() => this._cycle('data'), 30000);       // 30s
    setTimeout(() => this._cycle('heartbeat'), 60000);  // 1 min — startup notification
    setTimeout(() => this._maybeEval(), 90000);          // 1.5 min — check if eval needed
    setTimeout(() => this._cycle('analyze'), 3 * 60 * 1000);  // 3 min — first analysis
  }

  stop() {
    this.running = false;
    for (const timer of Object.values(this.timers)) {
      clearInterval(timer);
    }
    this.timers = {};
    logger.info('[LOOP] Agentic Loop v5 stopped');
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

    // Also fetch for our own state tracking
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
      // Watchdog already handles this
      logger.debug(`[LOOP] Observe fetch: ${err.message}`);
    }

    this._save();
  }

  // ══════════════════════════════════════════
  //  DATA — Fetch real NBA data
  // ══════════════════════════════════════════

  async _fetchData() {
    this.state.lastData = new Date().toISOString();

    if (!this.dataWorker) return;

    // Fetch odds (dormant when quota exhausted — returns null gracefully)
    const oddsResult = await this.dataWorker.fetchOdds();
    if (oddsResult) {
      if (this.a2a) {
        this.a2a.postDataReport('odds', {
          games: oddsResult.games?.length || 0,
          stored: oddsResult.stored || 0,
          movements: oddsResult.lineMovements?.length || 0,
        });
      }
    }

    // Fetch scores via ESPN (free, always works)
    const scoresResult = await this.dataWorker.fetchScores();
    if (scoresResult) {
      if (this.a2a) {
        this.a2a.postDataReport('scores', {
          source: 'espn',
          total: scoresResult.total,
          completed: scoresResult.completed,
          live: scoresResult.live,
        });
      }
    }

    // Fetch evolved model predictions from S10 and store for feedback loop
    await this._ingestPredictions();

    this._save();
  }

  // ══════════════════════════════════════════
  //  PREDICTION INGESTION — S10 evolved model → Supabase
  // ══════════════════════════════════════════

  async _ingestPredictions() {
    if (!this.feedbackLoop || !this.callS10) return;

    const today = new Date().toISOString().slice(0, 10);

    // Only ingest once per day
    if (this.state._lastPredictionIngest === today) return;

    try {
      // Call S10's /api/predict endpoint with today's date
      const s10Base = process.env.S10_URL || 'https://lbjlincoln-nomos-nba-quant.hf.space';
      const resp = await fetch(`${s10Base}/api/predict`, {
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
      `⚡ *EVE HEARTBEAT* — ${new Date().toLocaleTimeString('fr-FR', { timeZone: 'Europe/Paris' })}`,
      '',
    ];

    // Evolution status
    if (evo) {
      lines.push(`📊 *S10*: Brier ${evo.brier?.toFixed(4) || '?'} | Gen ${evo.generation || '?'} | Stag ${evo.stagnation ?? '?'}`);
    } else {
      lines.push('📊 *S10*: No data');
    }

    // Data collection
    lines.push(`📡 *Data*: ${dataStatus?.stats?.scoresFetches || 0} ESPN fetches | ${dataStatus?.stats?.oddsFetches || 0} odds`);

    // Evaluation (from feedback loop)
    if (evalStatus?.lastEval) {
      const e = evalStatus.lastEval;
      lines.push(`📈 *Yesterday*: ${e.correct}/${e.total} correct (${(e.accuracy * 100).toFixed(1)}%) | Brier ${e.brier?.toFixed(4)}`);
    }

    // Watchdog
    if (watchdogStatus?.trends?.brierTrend !== null && watchdogStatus?.trends?.brierTrend !== undefined) {
      const trend = watchdogStatus.trends.brierTrend;
      const emoji = trend < 0 ? '📉' : trend > 0 ? '📈' : '➡️';
      lines.push(`🔍 Brier trend (1h): ${emoji} ${trend > 0 ? '+' : ''}${trend}`);
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
  //  ANALYZE — LLM-powered insight generation (Phase 2)
  // ══════════════════════════════════════════

  async _analyze() {
    this.state.lastAnalyze = new Date().toISOString();

    if (!this.getCompletion) return;

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

    const prompt = `You are Eve, an NBA quant analyst AI. Analyze this data and give ONE concrete recommendation.

${JSON.stringify(context, null, 2)}

Rules:
- Use NUMBERS, not vague statements
- Compare to targets: Brier < 0.20, ROI > 5%, accuracy > 65%
- If recommending a GA change, specify exact parameter and value
- If everything looks good, say so briefly
- Max 200 words`;

    try {
      const result = await this.getCompletion([{ role: 'user', content: prompt }], {
        maxTokens: 500,
        temperature: 0.3,
      });

      if (result?.content) {
        this.lastInsight = result.content.substring(0, 500);

        // Post to A2A
        if (this.a2a) {
          this.a2a.postReport({
            type: 'analyst_insight',
            level: 'INFO',
            message: result.content.substring(0, 200),
            data: {
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

        logger.info(`[LOOP] Analyst insight generated (${result.model}): ${result.content.substring(0, 100)}...`);
      }
    } catch (err) {
      logger.warn(`[LOOP] Analyze failed: ${err.message}`);
    }

    this._save();
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

      // Status queries
      case 'get_status':
        return this.getStatus();

      case 'get_trends':
        return this.watchdog?.getTrends();

      case 'get_data_status':
        return this.dataWorker?.getStatus();

      default:
        throw new Error(`Unknown command: ${action}`);
    }
  }

  // ══════════════════════════════════════════
  //  STATUS
  // ══════════════════════════════════════════

  getStatus() {
    return {
      version: 'v5-intelligent',
      running: this.running,
      state: this.state,
      uptime: this._uptime(),
      lastInsight: this.lastInsight ? this.lastInsight.substring(0, 200) : null,
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
      // Try v5 state first, fall back to v4
      const v5File = STATE_FILE;
      const v4File = path.join(LOOP_DATA_DIR, 'state-v4.json');
      const fileToLoad = fs.existsSync(v5File) ? v5File : (fs.existsSync(v4File) ? v4File : null);
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
