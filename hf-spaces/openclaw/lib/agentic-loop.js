/**
 * Agentic Loop v4 — Data-Driven Autonomous NBA Quant Operations
 *
 * Replaces v3 (1375 lines of LLM-hallucination theater) with a lean,
 * data-driven loop that does REAL work.
 *
 * Design principles:
 *   1. DATA > LLM — Fetch real data, compute real metrics. No hallucinations.
 *   2. OBSERVE > ACT — Watch and report. Config changes are Adam's job.
 *   3. STRUCTURED OUTPUT — All observations go to A2A inbox for Adam.
 *   4. MINIMUM VIABLE — 6 simple cycles, no fake agents.
 *
 * Cycles:
 *   OBSERVE   (5 min)  — Poll S10, feed metrics to Watchdog
 *   DATA      (30 min) — Fetch odds + scores from APIs, store in Supabase
 *   HEALTH    (10 min) — Check all 5 HF Spaces are up
 *   REPORT    (30 min) — Generate structured report for Adam (A2A)
 *   COMMAND   (2 min)  — Check A2A command queue from Adam
 *   HEARTBEAT (60 min) — Telegram summary to admin
 */

const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const LOOP_DATA_DIR = '/data/agentic-loop';
const STATE_FILE = path.join(LOOP_DATA_DIR, 'state-v4.json');

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

    // Timers
    this.timers = {};
    this.running = false;

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

    logger.info('[LOOP] Agentic Loop v4 started — data-driven operations');

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

    // Run initial cycles
    setTimeout(() => this._cycle('observe'), 5000);   // 5s after start
    setTimeout(() => this._cycle('health'), 15000);    // 15s
    setTimeout(() => this._cycle('data'), 30000);      // 30s
    setTimeout(() => this._cycle('heartbeat'), 60000); // 1 min — startup notification
  }

  stop() {
    this.running = false;
    for (const timer of Object.values(this.timers)) {
      clearInterval(timer);
    }
    this.timers = {};
    logger.info('[LOOP] Agentic Loop v4 stopped');
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

    // Fetch odds
    const oddsResult = await this.dataWorker.fetchOdds();
    if (oddsResult) {
      // Post to A2A
      if (this.a2a) {
        this.a2a.postDataReport('odds', {
          games: oddsResult.games?.length || 0,
          stored: oddsResult.stored || 0,
          movements: oddsResult.lineMovements?.length || 0,
        });
      }
    }

    // Fetch scores
    const scoresResult = await this.dataWorker.fetchScores();
    if (scoresResult) {
      if (this.a2a) {
        this.a2a.postDataReport('scores', {
          total: scoresResult.total,
          completed: scoresResult.completed,
          live: scoresResult.live,
        });
      }
    }

    this._save();
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

    const report = {
      type: 'periodic_report',
      level: 'INFO',
      message: `Eve periodic report @ ${this.state.lastReport}`,
      data: {
        evolution: evo || 'unknown',
        data_collection: {
          odds_fetches: dataStatus?.stats?.oddsFetches || 0,
          odds_stored: dataStatus?.stats?.oddsStored || 0,
          api_quota_remaining: dataStatus?.stats?.apiQuotaRemaining || 'unknown',
          last_odds_fetch: dataStatus?.lastOddsFetch,
          line_movements: dataStatus?.recentMovements?.length || 0,
        },
        trends: watchdogTrends,
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
  //  HEARTBEAT — Telegram status to admin
  // ══════════════════════════════════════════

  async _heartbeat() {
    this.state.lastHeartbeat = new Date().toISOString();

    if (!this.bot) return;

    const evo = this.state.lastEvoStatus;
    const dataStatus = this.dataWorker?.getStatus();
    const watchdogStatus = this.watchdog?.getStatus();

    // Build concise Telegram message
    const lines = [
      `⚡ *EVE HEARTBEAT* — ${new Date().toLocaleTimeString('fr-FR', { timeZone: 'Europe/Paris' })}`,
      '',
    ];

    // Evolution status
    if (evo) {
      lines.push(`📊 *S10 Evolution*`);
      lines.push(`  Brier: ${evo.brier?.toFixed(4) || '?'} | Gen: ${evo.generation || '?'}`);
      lines.push(`  Features: ${evo.features || '?'} | Pop: ${evo.population || '?'}`);
      lines.push(`  Stagnation: ${evo.stagnation ?? '?'} | Mutation: ${evo.mutationRate?.toFixed(3) || '?'}`);
    } else {
      lines.push('📊 *S10*: No data');
    }

    // Data collection
    lines.push('');
    lines.push(`📡 *Data Collection*`);
    lines.push(`  Odds fetched: ${dataStatus?.stats?.oddsFetches || 0} | Stored: ${dataStatus?.stats?.oddsStored || 0}`);
    lines.push(`  API quota left: ${dataStatus?.stats?.apiQuotaRemaining || '?'}`);
    if (dataStatus?.recentMovements?.length > 0) {
      lines.push(`  Line movements: ${dataStatus.recentMovements.length}`);
    }

    // Watchdog
    if (watchdogStatus) {
      lines.push('');
      lines.push(`🔍 *Watchdog*`);
      lines.push(`  Checks: ${watchdogStatus.stats?.checks || 0} | Alerts: ${watchdogStatus.stats?.alertsSent || 0}`);
      if (watchdogStatus.trends?.brierTrend !== null) {
        const trend = watchdogStatus.trends.brierTrend;
        const emoji = trend < 0 ? '📉' : trend > 0 ? '📈' : '➡️';
        lines.push(`  Brier trend (1h): ${emoji} ${trend > 0 ? '+' : ''}${trend}`);
      }
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
      version: 'v4-data-driven',
      running: this.running,
      state: this.state,
      uptime: this._uptime(),
      watchdog: this.watchdog?.getStatus(),
      dataWorker: this.dataWorker?.getStatus(),
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

  // ══════════════════════════════════════════
  //  PERSISTENCE
  // ══════════════════════════════════════════

  _load() {
    try {
      if (!fs.existsSync(LOOP_DATA_DIR)) fs.mkdirSync(LOOP_DATA_DIR, { recursive: true });
      if (fs.existsSync(STATE_FILE)) {
        const saved = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
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
