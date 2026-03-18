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

    // Agent role — determines which cycles are active
    this.agentName = process.env.AGENT_NAME || 'Eve';
    this.isNBA = (process.env.AGENT_ROLE || 'nba-quant') === 'nba-quant';

    // Timers
    this.timers = {};
    this.running = false;

    // Last analyst insight (shown in heartbeat)
    this.lastInsight = null;

    // Auto-execute: Karpathy pattern — act on insights automatically
    this.autoExecuteEnabled = true;

    // Conversation memory: last N insights for multi-turn reasoning
    this.analysisHistory = [];
    this.MAX_ANALYSIS_HISTORY = 10;

    // Execution feedback: track what we did and what happened
    this.executionLog = [];
    this.MAX_EXECUTION_LOG = 20;

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

    // OBSERVE: Every 3 min (was 5)
    this.timers.observe = setInterval(() => this._cycle('observe'), 3 * 60 * 1000);

    // DATA: Every 10 min (was 30) — injuries, scores, box scores, lineups, referees
    this.timers.data = setInterval(() => this._cycle('data'), 10 * 60 * 1000);

    // HEALTH: Every 5 min (was 10)
    this.timers.health = setInterval(() => this._cycle('health'), 5 * 60 * 1000);

    // REPORT: Every 15 min (was 30, offset 5 min from DATA)
    setTimeout(() => {
      this.timers.report = setInterval(() => this._cycle('report'), 15 * 60 * 1000);
    }, 5 * 60 * 1000);

    // COMMAND: Every 1 min (was 2) — fast poll for Adam's commands
    this.timers.command = setInterval(() => this._cycle('command'), 60 * 1000);

    // HEARTBEAT: Every 30 min (was 60)
    this.timers.heartbeat = setInterval(() => this._cycle('heartbeat'), 30 * 60 * 1000);

    // EVAL: Check every 10 min (was 15), runs once per day per date
    this.timers.eval = setInterval(() => this._maybeEval(), 10 * 60 * 1000);

    // ANALYZE: Every 15 min (was 30) — agent stays aware in near real-time
    this.timers.analyze = setInterval(() => this._cycle('analyze'), 15 * 60 * 1000);

    // RESEARCH: Every 2 hours (was 4) — 12x/day
    this.timers.research = setInterval(() => this._cycle('research'), 2 * 60 * 60 * 1000);

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

    if (this.isNBA) {
      // ── NBA-SPECIFIC DATA COLLECTION ──

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
      // ── GENERAL-PURPOSE AGENT (RGWA etc.) ──
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
      `⚡ *${this.agentName} HEARTBEAT* — ${new Date().toLocaleTimeString('fr-FR', { timeZone: 'Europe/Paris' })}`,
      '',
    ];

    if (this.isNBA) {
      // NBA-specific heartbeat
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
  //  ANALYZE — LLM-powered insight generation (Phase 2)
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

    // ── NBA-SPECIFIC ANALYSIS ──

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

    // Build conversation memory context
    const memoryContext = this.analysisHistory.length > 0
      ? `\n\nPREVIOUS INSIGHTS (most recent first):\n${this.analysisHistory.slice(-5).reverse().map((h, i) =>
          `[${i + 1}] ${h.timestamp}: ${h.insight.substring(0, 150)}${h.actions?.length ? ` → EXECUTED: ${h.actions.join(', ')}` : ''}`
        ).join('\n')}`
      : '';

    // Build execution feedback context
    const feedbackContext = this.executionLog.length > 0
      ? `\n\nRECENT EXECUTIONS & RESULTS:\n${this.executionLog.slice(-5).reverse().map((e, i) =>
          `[${i + 1}] ${e.timestamp}: ${e.action} → ${e.result} | Brier before: ${e.brierBefore?.toFixed(4) || '?'}, after: ${e.brierAfter?.toFixed(4) || 'pending'}`
        ).join('\n')}`
      : '';

    const prompt = `You are ${this.agentName}, an NBA quant analyst AI. Analyze this data and give concrete recommendations.

CURRENT STATE:
${JSON.stringify(context, null, 2)}
${memoryContext}
${feedbackContext}

Rules:
- Use NUMBERS, not vague statements
- Compare to targets: Brier < 0.20, ROI > 5%, accuracy > 65%
- You can output MULTIPLE actions, one per line:
  ACTION: set_config(param=value)
  ACTION: set_config(param2=value2)
  ACTION: diversify
  ACTION: inject_features(feature1, feature2, feature3)
  ACTION: rollback
  Valid set_config params: mutation_rate, target_features, crossover_rate, tournament_size
- Do NOT repeat the same actions from previous insights unless you have new evidence
- If an execution's result was negative, do NOT retry the same action
- If everything looks good, say "STATUS: OK" and give brief summary
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

        // Auto-execute: Karpathy pattern — act on ALL insights
        let executedActions = [];
        if (this.autoExecuteEnabled) {
          executedActions = await this._tryAutoExecute(result.content, context);
        }

        // Save to conversation memory
        this.analysisHistory.push({
          timestamp: new Date().toISOString(),
          insight: result.content,
          actions: executedActions,
          brier: context.evolution?.brier,
          model: result.model,
        });
        if (this.analysisHistory.length > this.MAX_ANALYSIS_HISTORY) {
          this.analysisHistory = this.analysisHistory.slice(-this.MAX_ANALYSIS_HISTORY);
        }

        logger.info(`[LOOP] Analyst insight generated (${result.model}): ${result.content.substring(0, 100)}...`);
      }
    } catch (err) {
      logger.warn(`[LOOP] Analyze failed: ${err.message}`);
    }

    this._save();
  }

  // ══════════════════════════════════════════
  //  AUTO-EXECUTE — Karpathy pattern (act on insights)
  // ══════════════════════════════════════════

  async _tryAutoExecute(insight, context) {
    // Parse ALL ACTION lines from insight (not just first)
    const actionMatches = [...insight.matchAll(/ACTION:\s*(\w+)(?:\(([^)]*)\))?/g)];
    if (actionMatches.length === 0) return [];

    // Safety gate: monotonic ratchet — only execute if Brier is near checkpoint best
    const currentBrier = context.evolution?.brier;
    let bestCheckpointBrier = null;
    try {
      const cpResp = await this.callS10('/api/checkpoint/best');
      bestCheckpointBrier = cpResp?.brier;
    } catch (e) {
      logger.debug('[LOOP] No checkpoint data available for ratchet check');
    }

    // Ratchet applies to config changes, NOT to rollback (rollback is emergency)
    const hasRollback = actionMatches.some(m => m[1] === 'rollback');

    if (!hasRollback && bestCheckpointBrier && currentBrier && currentBrier > bestCheckpointBrier + 0.005) {
      logger.info(`[LOOP] Auto-execute BLOCKED: Brier ${currentBrier?.toFixed(4)} > checkpoint ${bestCheckpointBrier?.toFixed(4)} + 0.005`);
      if (this.a2a) {
        this.a2a.postReport({
          type: 'auto_execute_blocked',
          level: 'WARNING',
          message: `Ratchet blocked ${actionMatches.length} action(s). Brier ${currentBrier?.toFixed(4)} too far from best ${bestCheckpointBrier?.toFixed(4)}`,
        });
      }
      return [];
    }

    const executedActions = [];

    for (const match of actionMatches) {
      const actionType = match[1];
      const actionArgs = match[2] || '';

      try {
        let result = 'unknown';

        if (actionType === 'set_config') {
          const params = {};
          for (const pair of actionArgs.split(',')) {
            const [key, val] = pair.trim().split('=');
            if (key && val) params[key.trim()] = parseFloat(val.trim()) || val.trim();
          }
          if (Object.keys(params).length > 0) {
            await this.callS10('/api/config', { method: 'POST', body: JSON.stringify(params) });
            result = `set_config(${JSON.stringify(params)})`;
            logger.info(`[LOOP] Auto-executed: ${result}`);
          }

        } else if (actionType === 'diversify') {
          await this.callS10('/api/command', { method: 'POST', body: JSON.stringify({ command: 'diversify' }) });
          result = 'diversify';
          logger.info('[LOOP] Auto-executed: diversify');

        } else if (actionType === 'inject_features') {
          // Parse feature names from args
          const features = actionArgs.split(',').map(f => f.trim()).filter(Boolean);
          if (features.length > 0) {
            await this.callS10('/api/features/inject', {
              method: 'POST',
              body: JSON.stringify({ features }),
            });
            result = `inject_features(${features.join(', ')})`;
            logger.info(`[LOOP] Auto-executed: ${result}`);
          }

        } else if (actionType === 'rollback') {
          await this.callS10('/api/checkpoint/restore', { method: 'POST', body: '{}' });
          result = 'rollback to best checkpoint';
          logger.info('[LOOP] Auto-executed: rollback to best checkpoint');

        } else {
          logger.debug(`[LOOP] Unknown action type: ${actionType}`);
          continue;
        }

        executedActions.push(result);

        // Track execution for recursive feedback
        this.executionLog.push({
          timestamp: new Date().toISOString(),
          action: result,
          brierBefore: currentBrier,
          brierAfter: null, // Will be filled by _checkExecutionFeedback
          result: 'pending',
        });
        if (this.executionLog.length > this.MAX_EXECUTION_LOG) {
          this.executionLog = this.executionLog.slice(-this.MAX_EXECUTION_LOG);
        }

      } catch (err) {
        logger.warn(`[LOOP] Auto-execute ${actionType} failed: ${err.message}`);
        this.executionLog.push({
          timestamp: new Date().toISOString(),
          action: `${actionType}(${actionArgs})`,
          brierBefore: currentBrier,
          brierAfter: null,
          result: `FAILED: ${err.message}`,
        });
      }
    }

    // Create checkpoint after successful executions
    if (executedActions.length > 0) {
      try {
        await this.callS10('/api/checkpoint', { method: 'POST', body: '{}' });
        logger.info('[LOOP] Post-execute checkpoint created');
      } catch (e) {
        logger.warn(`[LOOP] Checkpoint after auto-execute failed: ${e.message}`);
      }

      if (this.a2a) {
        this.a2a.postReport({
          type: 'auto_execute',
          level: 'INFO',
          message: `Executed ${executedActions.length} action(s): ${executedActions.join(' | ')}`,
          data: { actions: executedActions, currentBrier, bestCheckpointBrier },
        });
      }

      // Schedule feedback check: after 20 min, compare Brier to see if it improved
      setTimeout(() => this._checkExecutionFeedback(currentBrier), 20 * 60 * 1000);
    }

    return executedActions;
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
