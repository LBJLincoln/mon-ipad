/**
 * Agentic Loop v3 — ALWAYS ACT 24/7 Tireless Autonomous NBA Quant Improvement
 *
 * Principles:
 *   1. NEVER IDLE — Every cycle MUST produce at least one real S10 API call
 *   2. ALWAYS ACT — If nothing to fix, research or inject features anyway
 *   3. NEVER STOP — LLM failure triggers rule engine + immediate retry with next model
 *   4. SELF-TRACK — Every action is tracked for improvement vs regression
 *   5. HEARTBEAT — Admin gets status every 30min via Telegram
 *
 * Agents:
 *   N.O.S  — Strategic Commander (Claude Code CLI persona)
 *   ADEMO  — Research & Execution (OpenClaw healer-alpha)
 *   CAIN   — Evolution Engine (genetic algorithm tracker)
 *   DALI   — Data Scientist (Polymarket, play-by-play, datasets)
 *   MONK   — Self-Healer (error detection, autonomous fixing)
 *
 * Cycles (AGGRESSIVE):
 *   OBSERVE     (5 min)  — Check evolution + FORCE at least 1 S10 call
 *   ANTICIPATE  (3 min)  — Predictive bottleneck prevention (faster)
 *   RESEARCH    (15 min) — Discover features via academic research
 *   EVALUATE    (10 min) — Deep model performance analysis
 *   IMPROVE     (auto)   — Apply improvements on stagnation
 *   HEAL        (5 min)  — Detect and fix errors autonomously
 *   HEARTBEAT   (30 min) — Telegram status to admin
 *   FORCE-ACT   (5 min)  — Guarantee action if other phases were quiet
 */

const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const LOOP_DATA_DIR = '/data/agentic-loop';
const CONVERSATIONS_FILE = path.join(LOOP_DATA_DIR, 'conversations.json');
const STATE_FILE = path.join(LOOP_DATA_DIR, 'state.json');
const RESEARCH_FILE = path.join(LOOP_DATA_DIR, 'research-log.json');
const ERRORS_FILE = path.join(LOOP_DATA_DIR, 'errors.json');
const ACTION_LOG_FILE = path.join(LOOP_DATA_DIR, 'action-log.json');
const MAX_CONVERSATIONS = 500;
const MAX_RESEARCH_ITEMS = 200;
const MAX_ACTION_LOG = 500;

// ── S10 API ENDPOINTS ──
const S10_BASE = 'https://lbjlincoln-nomos-nba-quant.hf.space';
const S10_ENDPOINTS = {
  status:     { method: 'GET',  path: '/api/status' },
  config:     { method: 'POST', path: '/api/config' },
  command:    { method: 'POST', path: '/api/command' },
  reset:      { method: 'POST', path: '/api/reset' },
  runStats:   { method: 'GET',  path: '/api/run-stats' },
  brierTrend: { method: 'GET',  path: '/api/brier-trend' },
  cuts:       { method: 'GET',  path: '/api/cuts' },
};

// ── ADMIN TELEGRAM ──
const ADMIN_CHAT_ID = 6582544948;

// ── 5 AGENT IDENTITIES ──
const AGENTS = {
  NOS:  { id: 'nos',  name: 'N.O.S',  role: 'Strategic Commander',    color: '#7c3aed' },
  ADEMO:{ id: 'ademo',name: 'ADEMO',  role: 'Research & Execution',   color: '#06b6d4' },
  CAIN: { id: 'cain', name: 'CAIN',   role: 'Evolution Engine',       color: '#f59e0b' },
  DALI: { id: 'dali', name: 'DALI',   role: 'Data Scientist',         color: '#39ff14' },
  MONK: { id: 'monk', name: 'MONK',   role: 'Self-Healer',            color: '#ff2e63' },
};

// ── FEATURE CATEGORIES (708 candidates across 17+ categories) ──
const FEATURE_CATEGORIES = [
  { name: 'team_rolling_stats', count: 105, desc: 'Win%, scoring over 7 windows' },
  { name: 'four_factors', count: 63, desc: 'eFG%, TOV%, OREB%, FTr' },
  { name: 'pace_efficiency', count: 74, desc: 'ORtg, DRtg, NetRtg, TS%' },
  { name: 'shooting_distribution', count: 70, desc: 'Shot zones, 3PT%, mid-range' },
  { name: 'player_impact_injuries', count: 44, desc: 'Star usage, injury impact' },
  { name: 'rest_schedule', count: 34, desc: 'B2B, rest days, travel fatigue' },
  { name: 'market_microstructure', count: 48, desc: 'CLV, steam moves, line movement, Polymarket' },
  { name: 'opponent_adjusted', count: 48, desc: 'Strength of schedule adjusted stats' },
  { name: 'momentum_form', count: 32, desc: 'Win streaks, last 5/10 performance' },
  { name: 'matchup_specific', count: 34, desc: 'H2H, style matchups, pace differential' },
  { name: 'power_ratings', count: 30, desc: 'Elo, RAPTOR, meta-models' },
  { name: 'advanced_box', count: 24, desc: 'PIE, GameScore, plus-minus adjusted' },
  { name: 'referee_conditions', count: 18, desc: 'Ref bias, foul rates, altitude' },
  { name: 'external_models', count: 16, desc: 'DARKO, 538, ESPN BPI integration' },
  { name: 'defensive_scheme', count: 18, desc: 'Switch rate, drop coverage, blitz %' },
  { name: 'temporal_calendar', count: 18, desc: 'Day of week, month, pre/post ASB' },
  { name: 'interaction_derived', count: 32, desc: 'Feature crosses, polynomial terms' },
  { name: 'tanking_playoff_context', count: 0, desc: 'Draft incentive, playoff probability, games behind' },
  { name: 'polymarket_evolution', count: 0, desc: 'Polymarket odds movement, implied probability shifts' },
  { name: 'play_by_play_impact', count: 0, desc: 'Clutch time stats, garbage time filtering, possession quality' },
  { name: 'season_trajectory', count: 0, desc: 'Win curve projection, remaining SOS, trade deadline impact' },
];

// ── FORCED ACTIONS — when nothing else to do, pick one randomly ──
// IMPORTANT: S10 has HARD CAPS — mutation ≤ 0.10, features ≤ 150, pop ≤ 80
// Eve should OBSERVE more and INTERFERE less. Good evolution needs stability.
const FORCED_ACTIONS = [
  { name: 'check_brier_trend', fn: 'brierTrend', desc: 'Pull Brier trend data from S10' },
  { name: 'check_run_stats', fn: 'runStats', desc: 'Pull run statistics from S10' },
  { name: 'check_cuts', fn: 'cuts', desc: 'Pull feature cut data from S10' },
  { name: 'status_deep_check', fn: 'status', desc: 'Deep status health check' },
  { name: 'analyze_population_diversity', fn: 'status', desc: 'Analyze population diversity metrics from S10 status' },
  { name: 'check_brier_trend_2', fn: 'brierTrend', desc: 'Second Brier trend pull' },
];

class AgenticLoop {
  constructor({ getCompletion, bot, adminId, fetchEvolution, callS10, anticipationEngine, ruleEngine }) {
    this.getCompletion = getCompletion;
    this.bot = bot;
    this.adminId = adminId || ADMIN_CHAT_ID;
    this.fetchEvolution = fetchEvolution;
    this.callS10 = callS10 || (async () => ({ error: 'callS10 not configured' }));
    this.anticipation = anticipationEngine || null;
    this.ruleEngine = ruleEngine || null;

    this.conversations = [];
    this.state = {
      status: 'idle',
      lastObserve: null, lastResearch: null, lastEvaluate: null,
      lastImprove: null, lastReport: null, lastHeal: null,
      lastAnticipate: null, lastHeartbeat: null, lastForceAct: null,
      cycleCount: 0, healCount: 0,
      bestBrier: 1.0, bestROI: -100,
      researchItems: [],
      stagnationCount: 0,
      evolutionHistory: [],
      errors: [],
      childThreads: [],
      featurePool: 708,
      modelsActive: ['xgboost', 'lightgbm', 'catboost', 'random_forest', 'stacking'],
      modelsTarget: ['xgboost', 'lightgbm', 'catboost', 'random_forest', 'stacking',
                     'temporal_fusion_transformer', 'bayesian_optimization', 'conformal_calibration',
                     'neural_net_tabular', 'gradient_boosted_trees_v2'],
      // v3: self-improvement tracking
      actionsThisCycle: 0,
      totalS10Calls: 0,
      totalActions: 0,
      improvementActions: 0,
      regressionActions: 0,
      neutralActions: 0,
      llmFailures: 0,
      llmRetries: 0,
      ruleEngineActivations: 0,
      heartbeatsSent: 0,
    };
    this.research = [];
    this.errors = [];
    this.actionLog = [];  // v3: tracks every action + outcome
    this.running = false;
    this.intervals = [];
    this._cycleActionCount = 0;  // reset each observe cycle

    this._init();
  }

  _init() {
    try { fs.mkdirSync(LOOP_DATA_DIR, { recursive: true }); } catch {}
    try {
      if (fs.existsSync(STATE_FILE))
        this.state = { ...this.state, ...JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) };
    } catch (e) { logger.warn('Load state:', e.message); }
    try {
      if (fs.existsSync(CONVERSATIONS_FILE))
        this.conversations = JSON.parse(fs.readFileSync(CONVERSATIONS_FILE, 'utf8'));
    } catch (e) { logger.warn('Load convos:', e.message); }
    try {
      if (fs.existsSync(RESEARCH_FILE))
        this.research = JSON.parse(fs.readFileSync(RESEARCH_FILE, 'utf8'));
    } catch (e) { logger.warn('Load research:', e.message); }
    try {
      if (fs.existsSync(ERRORS_FILE))
        this.errors = JSON.parse(fs.readFileSync(ERRORS_FILE, 'utf8'));
    } catch (e) { logger.warn('Load errors:', e.message); }
    try {
      if (fs.existsSync(ACTION_LOG_FILE))
        this.actionLog = JSON.parse(fs.readFileSync(ACTION_LOG_FILE, 'utf8'));
    } catch (e) { logger.warn('Load action log:', e.message); }
  }

  // ══════════════════════════════════════════
  //  START / STOP
  // ══════════════════════════════════════════

  start() {
    if (this.running) return;
    this.running = true;
    this.state.status = 'running';

    this._log('nos', 'ALWAYS ACT MODE — Agentic loop v3 initialized. 5 agents. 708 features. ZERO IDLE CYCLES. Every cycle = real action.');
    this._log('ademo', 'Research engine online. Academic-grade NBA analytics. 15min cycles.');
    this._log('cain', 'Evolution tracker active. Monitoring Brier, ROI, Sharpe, Calibration.');
    this._log('dali', 'Data scientist online. Polymarket, play-by-play, dataset validation.');
    this._log('monk', 'Self-healer online. Error detection + autonomous fixing + LLM failover.');

    // OBSERVE — every 5 min (each cycle MUST produce action)
    this.intervals.push(setInterval(() => this._safeRun('observe', () => this._observe()), 5 * 60 * 1000));
    // ANTICIPATE — every 3 min (faster detection)
    this.intervals.push(setInterval(() => this._safeRun('anticipate', () => this._anticipate()), 3 * 60 * 1000));
    // RESEARCH — every 15 min (more frequent)
    this.intervals.push(setInterval(() => this._safeRun('research', () => this._research()), 15 * 60 * 1000));
    // EVALUATE — every 10 min
    this.intervals.push(setInterval(() => this._safeRun('evaluate', () => this._evaluate()), 10 * 60 * 1000));
    // HEAL — every 5 min
    this.intervals.push(setInterval(() => this._safeRun('heal', () => this._heal()), 5 * 60 * 1000));
    // DATA VALIDATION — every 15 min
    this.intervals.push(setInterval(() => this._safeRun('data', () => this._dataCheck()), 15 * 60 * 1000));
    // FORCE-ACT — every 5 min (guarantee action if cycle was quiet)
    this.intervals.push(setInterval(() => this._safeRun('force-act', () => this._forceAct()), 5 * 60 * 1000));
    // HEARTBEAT — every 30 min (Telegram status to admin)
    this.intervals.push(setInterval(() => this._safeRun('heartbeat', () => this._heartbeat()), 30 * 60 * 1000));
    // STATE SAVE — every 2 min
    this.intervals.push(setInterval(() => this._save(), 2 * 60 * 1000));

    // Run first cycles immediately (staggered)
    setTimeout(() => this._safeRun('observe', () => this._observe()), 3000);
    setTimeout(() => this._safeRun('anticipate', () => this._anticipate()), 5000);
    setTimeout(() => this._safeRun('evaluate', () => this._evaluate()), 10000);
    setTimeout(() => this._safeRun('research', () => this._research()), 18000);
    setTimeout(() => this._safeRun('heal', () => this._heal()), 28000);
    setTimeout(() => this._safeRun('data', () => this._dataCheck()), 38000);
    // First heartbeat at 1 min (so admin knows we booted)
    setTimeout(() => this._safeRun('heartbeat', () => this._heartbeat()), 60000);

    logger.info('Agentic loop v3 ALWAYS ACT — started. 5min observe, 3min anticipate, 15min research, 30min heartbeat.');
    this._save();
  }

  stop() {
    this.running = false;
    this.state.status = 'stopped';
    this.intervals.forEach(i => clearInterval(i));
    this.intervals = [];
    this._log('nos', 'Agentic loop stopped.');
    this._save();
  }

  // ── Safe runner — catches errors, logs them, NEVER crashes ──
  // On LLM failure: rule engine takes over AND retries with next model immediately
  async _safeRun(phase, fn) {
    try {
      await fn();
    } catch (err) {
      const error = {
        phase,
        message: err.message,
        timestamp: new Date().toISOString(),
        fixed: false,
      };
      this.errors.push(error);
      if (this.errors.length > 100) this.errors = this.errors.slice(-100);
      this._log('monk', `ERROR in ${phase}: ${err.message}. Logging for auto-fix.`);
      this._saveErrors();

      // ── LLM FAILURE HANDLING — Rule engine + immediate retry ──
      if (/LLM providers failed|getCompletion|completion.*fail|model.*unavailable/i.test(err.message)) {
        this.state.llmFailures++;

        // STEP 1: Rule engine handles critical decisions immediately
        if (this.ruleEngine) {
          const lastEvo = this.state.evolutionHistory.length > 0
            ? this.state.evolutionHistory[this.state.evolutionHistory.length - 1] : null;
          if (lastEvo) {
            this._log('monk', 'LLM down — Rule Engine taking over for critical actions.');
            this.state.ruleEngineActivations++;
            const actions = await this.ruleEngine.evaluate(lastEvo);
            for (const action of actions) {
              this._log('monk', `[RULE] ${action.ruleId}: ${action.result}`);
              this._trackAction('rule_engine', action.ruleId, null);
            }
            if (actions.length > 0) {
              this._report(`Rule Engine: ${actions.length} actions while LLM down: ${actions.map(a => a.ruleId).join(', ')}`);
            }
          }
        }

        // STEP 2: Immediate retry — don't wait for next cycle
        this.state.llmRetries++;
        this._log('monk', `LLM retry #${this.state.llmRetries} — attempting immediately with next model...`);
        try {
          // Retry the phase function once more — getCompletion should rotate models
          await fn();
          this._log('monk', 'LLM retry SUCCEEDED on second attempt.');
        } catch (retryErr) {
          this._log('monk', `LLM retry also failed: ${retryErr.message}. Rule engine is covering. Will retry next cycle.`);

          // STEP 3: Even on total LLM failure, do a FORCED S10 action
          await this._forceS10Action('llm_failure_fallback');
        }
      }
    }
  }

  // ══════════════════════════════════════════
  //  OBSERVE — Check evolution + ALWAYS produce action
  // ══════════════════════════════════════════

  async _observe() {
    this.state.lastObserve = new Date().toISOString();
    this.state.cycleCount++;
    this._cycleActionCount = 0;  // reset for this cycle

    const evoData = await this.fetchEvolution();
    if (!evoData) {
      this._log('cain', 'Evolution Space unreachable. MONK will investigate.');
      this._recordError('observe', 'Evolution Space unreachable');
      if (this.anticipation) {
        this.anticipation.record('connectivity_loss', { target: 'S10', phase: 'observe' });
      }
      // ALWAYS ACT: even if S10 is down, pull what we can
      await this._forceS10Action('observe_fallback');
      return;
    }

    // Parse evoData
    let parsed;
    if (evoData && typeof evoData === 'object' && evoData.generation !== undefined) {
      parsed = {
        generation: evoData.generation || 0,
        brier: evoData.best_brier || 1.0,
        roi: evoData.best_roi || 0,
        sharpe: evoData.best_sharpe || 0,
        features: evoData.best_features || 0,
        model: evoData.best_model_type || 'unknown',
        population: evoData.pop_size || 0,
        mutationRate: evoData.mutation_rate || 0,
        stagnation: evoData.stagnation || 0,
        games: evoData.games || 0,
        featureCandidates: evoData.feature_candidates || 0,
        cycle: evoData.cycle || 0,
        status: evoData.status || 'unknown',
      };
    } else {
      parsed = this._parseEvolutionData(evoData);
    }
    if (!parsed) {
      await this._forceS10Action('observe_parse_fail');
      return;
    }

    // Snapshot Brier BEFORE this cycle (for self-improvement tracking)
    const brierBefore = this.state.bestBrier;

    this.state.evolutionHistory.push({ timestamp: new Date().toISOString(), ...parsed });
    if (this.state.evolutionHistory.length > 200)
      this.state.evolutionHistory = this.state.evolutionHistory.slice(-200);

    // ── Track improvements ──
    const brierImproved = parsed.brier > 0 && parsed.brier < this.state.bestBrier;
    const roiImproved = parsed.roi > this.state.bestROI;

    if (brierImproved) {
      const old = this.state.bestBrier;
      this.state.bestBrier = parsed.brier;
      this._log('cain', `NEW BEST Brier: ${parsed.brier.toFixed(4)} (was ${old.toFixed(4)}). Gen ${parsed.generation}, ${parsed.features} features.`);
      this._report(`Brier improved: ${old.toFixed(4)} -> ${parsed.brier.toFixed(4)}`);
      // Mark recent actions as "improvement"
      this._markRecentActions('improvement', old - parsed.brier);
    }

    if (roiImproved && parsed.roi > 0) {
      this.state.bestROI = parsed.roi;
      this._log('cain', `ROI improvement: ${parsed.roi.toFixed(1)}%! Model: ${parsed.model}.`);
    }

    // ── Track regressions ──
    if (parsed.brier > 0 && parsed.brier > brierBefore + 0.002) {
      this._log('cain', `Brier REGRESSION: ${parsed.brier.toFixed(4)} (was ${brierBefore.toFixed(4)}). Marking recent actions.`);
      this._markRecentActions('regression', parsed.brier - brierBefore);
    }

    // ── ALWAYS pull brier trend + run stats (real S10 calls every observe) ──
    await this._pullS10Data(parsed);

    // ── MONK intelligent analysis — observe, don't auto-act ──
    if (parsed.stagnation > 15 && parsed.mutationRate > 0.08) {
      this._log('monk', `OBSERVATION: GA is thrashing — high mutation (${parsed.mutationRate}) prevents convergence at stagnation ${parsed.stagnation}. Need to LOWER mutation.`);
    }
    if (parsed.features > 120) {
      this._log('monk', `OBSERVATION: Feature bloat detected (${parsed.features} features) — models may be overfitting.`);
    }
    // Check model monoculture from recent history
    const recentModels = this.state.evolutionHistory.slice(-5).map(h => h.model).filter(Boolean);
    if (recentModels.length >= 5 && new Set(recentModels).size === 1) {
      this._log('monk', `OBSERVATION: Model monoculture — all top 5 observations use "${recentModels[0]}". Diversity injection needed.`);
    }

    // ── Stagnation detection with AUTO-FIX (aggressive) ──
    if (parsed.stagnation > 2) {
      this.state.stagnationCount++;
      this._log('nos', `STAGNATION ALERT: ${parsed.stagnation} generations flat. Count: ${this.state.stagnationCount}.`);

      if (this.anticipation) {
        this.anticipation.record('ga_stagnation', {
          generation: parsed.generation, brier: parsed.brier,
          stagnation: parsed.stagnation, mutationRate: parsed.mutationRate,
        });
      }

      // Trigger improvement EVERY stagnation cycle
      this._log('nos', 'Triggering improvement cycle...');
      await this._improve(parsed);

      if (this.state.stagnationCount >= 4) {
        this._log('monk', 'CRITICAL stagnation. Emergency diversification: mutation boost, population restart, feature injection.');
        await this._emergencyDiversify(parsed);
      }
    } else {
      if (this.state.stagnationCount > 0) {
        this._log('nos', `Stagnation broken! Previous count: ${this.state.stagnationCount}`);
        if (this.anticipation) this.anticipation.resolve('ga_stagnation');
      }
      this.state.stagnationCount = 0;
    }

    // ── Time-based improve: force every 30 min if Brier > 0.21 ──
    const timeSinceImprove = this.state.lastImprove ? Date.now() - new Date(this.state.lastImprove).getTime() : Infinity;
    if (parsed.brier > 0.21 && timeSinceImprove > 30 * 60 * 1000) {
      this._log('nos', `Brier ${parsed.brier.toFixed(4)} > 0.21, no improve in ${Math.round(timeSinceImprove / 60000)}min. Forcing improvement.`);
      await this._improve(parsed);
    }

    // ── Feature pool check ──
    if (parsed.featureCandidates > 0 && parsed.featureCandidates < 500) {
      this._log('dali', `WARNING: Only ${parsed.featureCandidates} feature candidates. Should be 708. Flagging.`);
    }

    // ── ALWAYS ACT: if this cycle produced 0 S10 calls, force one ──
    if (this._cycleActionCount === 0) {
      this._log('nos', 'ALWAYS ACT: no S10 calls this cycle. Forcing action.');
      await this._forceS10Action('always_act_observe');
    }

    // Status log (every 4th cycle)
    if (this.state.cycleCount % 4 === 0) {
      this._log('nos', `Status: Gen ${parsed.generation} | Brier ${parsed.brier.toFixed(4)} | ROI ${parsed.roi.toFixed(1)}% | ${parsed.features} feats | Pop ${parsed.population} | Actions: ${this.state.totalActions}`);
      this._log('ademo', `Candidates: ${parsed.featureCandidates || '?'} | Mutation: ${parsed.mutationRate} | Stag: ${parsed.stagnation} | S10 calls: ${this.state.totalS10Calls}`);
    }
  }

  // ══════════════════════════════════════════
  //  PULL S10 DATA — Always call real endpoints
  // ══════════════════════════════════════════

  async _pullS10Data(parsed) {
    // Pull brier trend
    try {
      const trendData = await this._callS10Direct('GET', '/api/brier-trend');
      if (trendData && !trendData.error) {
        this._cycleActionCount++;
        this.state.totalS10Calls++;
        if (trendData.trend && Array.isArray(trendData.trend) && trendData.trend.length > 2) {
          const recent = trendData.trend.slice(-5);
          const improving = recent[recent.length - 1] < recent[0];
          this._log('cain', `Brier trend (last ${recent.length}): ${recent.map(b => b.toFixed ? b.toFixed(4) : b).join(' -> ')} [${improving ? 'IMPROVING' : 'FLAT/DEGRADING'}]`);
        }
      }
    } catch {}

    // Pull run stats
    try {
      const runStats = await this._callS10Direct('GET', '/api/run-stats');
      if (runStats && !runStats.error) {
        this._cycleActionCount++;
        this.state.totalS10Calls++;
        if (this.state.cycleCount % 3 === 0) {
          this._log('cain', `Run stats: ${JSON.stringify(runStats).substring(0, 200)}`);
        }
      }
    } catch {}

    // Pull cuts every 6th cycle
    if (this.state.cycleCount % 6 === 0) {
      try {
        const cuts = await this._callS10Direct('GET', '/api/cuts');
        if (cuts && !cuts.error) {
          this._cycleActionCount++;
          this.state.totalS10Calls++;
          this._log('dali', `Feature cuts: ${JSON.stringify(cuts).substring(0, 200)}`);
        }
      } catch {}
    }
  }

  // ══════════════════════════════════════════
  //  ANTICIPATE — Predictive bottleneck prevention (every 3 min)
  // ══════════════════════════════════════════

  async _anticipate() {
    if (!this.anticipation) {
      // Even without anticipation engine, do a quick S10 status check
      await this._forceS10Action('anticipate_no_engine');
      return;
    }
    this.state.lastAnticipate = new Date().toISOString();

    const lastEvo = this.state.evolutionHistory.length > 0
      ? this.state.evolutionHistory[this.state.evolutionHistory.length - 1] : null;

    const actions = await this.anticipation.check(lastEvo);

    if (actions.length > 0) {
      for (const action of actions) {
        this._log('nos', `ANTICIPATION [${action.id}]: ${action.applied}`);
        this._trackAction('anticipate', action.id, null);

        if (action.needsResearchBoost) {
          this._log('ademo', 'Anticipation requested research acceleration.');
          this._safeRun('research', () => this._research());
        }

        if (action.needsRestart) {
          this._log('monk', `Anticipation requests space restart for ${action.id}.`);
          this._report(`ANTICIPATION: ${action.name} — Space restart recommended`);
        }
      }
      this._log('nos', `Anticipation: ${actions.length} preemptive actions.`);
    } else {
      // ALWAYS ACT: if anticipation found nothing, pull fresh status
      const status = await this._callS10Direct('GET', '/api/status');
      if (status && !status.error) {
        this._cycleActionCount++;
        this.state.totalS10Calls++;
        // Quick health validation
        if (status.stagnation > 10 && status.mutation_rate < 0.06) {
          // Only bump if truly stuck AND mutation is very low. S10 caps at 0.10.
          this._log('nos', `Anticipation: stagnation ${status.stagnation} with low mutation ${status.mutation_rate}. Gentle bump.`);
          await this.callS10('/api/config', { mutation_rate: Math.min(0.08, status.mutation_rate * 1.3) });
          this._trackAction('anticipate', 'gentle_mutation_bump', { oldRate: status.mutation_rate });
        }
      }
    }
  }

  // ══════════════════════════════════════════
  //  RESEARCH — Academic-grade NBA feature discovery
  // ══════════════════════════════════════════

  async _research() {
    this.state.lastResearch = new Date().toISOString();

    const existingFeatures = this.research.map(r => r.name).join(', ');
    const currentBrier = this.state.bestBrier;

    // Pick a random category to deep-dive each cycle
    const categories = FEATURE_CATEGORIES.filter(c => c.count > 0 || c.desc.includes('NEW') || c.count === 0);
    const focusCategory = categories[Math.floor(Math.random() * categories.length)];

    this._log('ademo', `Research cycle: deep-diving "${focusCategory.name}" (${focusCategory.desc}).`);

    const result = await this.getCompletion([{
      role: 'user',
      content: `You are a world-class NBA quantitative analyst at a Starlizard/Tony Bloom-level betting syndicate. March 2026.

Our genetic evolution model: Brier ${currentBrier.toFixed(4)} (target: <0.20). Using ${this.state.modelsActive.length} models.

FOCUS THIS CYCLE: "${focusCategory.name}" — ${focusCategory.desc}

Already researched features: ${existingFeatures || 'none yet'}

Research 3 NEW, NOVEL features in the "${focusCategory.name}" category that could give us edge. Requirements:
1. Based on REAL 2025-2026 NBA analytics research or proven quant strategies
2. Publicly available data (NBA API, basketball-reference, Polymarket, ESPN)
3. Must capture information NOT already in standard models
4. Consider: tanking teams (draft incentive), playoff context, clutch vs garbage time
5. Consider: Polymarket odds evolution as a feature (crowd wisdom signal)

For each feature:
- Name (snake_case, specific)
- Category: ${focusCategory.name}
- Data source (specific API endpoint or website)
- Expected impact on Brier score (quantitative estimate)
- Implementation: exact formula or calculation
- Why it gives edge (what information does it capture that others miss?)

Be extremely specific. No generic suggestions. Think like a PhD sports analytics researcher.`
    }], { maxTokens: 2000 });

    if (result.content) {
      const newFeatures = this._parseResearchResults(result.content, focusCategory.name);
      let added = 0;
      for (const feat of newFeatures) {
        if (!this.research.find(r => r.name === feat.name)) {
          feat.status = 'new';
          feat.discoveredAt = new Date().toISOString();
          feat.model = result.model;
          feat.focusCategory = focusCategory.name;
          this.research.push(feat);
          added++;
          this._log('ademo', `DISCOVERED: "${feat.name}" (${focusCategory.name}) — ${feat.power} power`);
        }
      }

      if (this.research.length > MAX_RESEARCH_ITEMS)
        this.research = this.research.slice(-MAX_RESEARCH_ITEMS);

      this._log('ademo', `Research complete. +${added} new. Total: ${this.research.length}. ${this.research.filter(r => r.status === 'new').length} untested.`);
      this._trackAction('research', `discovered_${added}_features`, { category: focusCategory.name, added });

      // Features must be validated by Adam (CLI) before injection
      // Log discoveries with needs_validation status — do NOT auto-inject into S10
      if (added > 0) {
        const pending = this.research.filter(r => r.status === 'new').slice(0, 3);
        for (const feat of pending) feat.status = 'needs_validation';
        this._log('ademo', `${pending.length} new features logged as needs_validation. Awaiting Adam (CLI) review before injection.`);
        this._trackAction('research', 'features_pending_validation', { count: pending.length, names: pending.map(f => f.name) });
      }
    }

    this._saveResearch();
  }

  // ══════════════════════════════════════════
  //  EVALUATE — Deep model performance analysis
  // ══════════════════════════════════════════

  async _evaluate() {
    this.state.lastEvaluate = new Date().toISOString();

    const history = this.state.evolutionHistory.slice(-20);
    if (history.length < 3) {
      this._log('nos', 'Not enough evolution data. Need 3+ observations.');
      // ALWAYS ACT: pull status even if we can't evaluate
      await this._forceS10Action('evaluate_insufficient_data');
      return;
    }

    const briers = history.map(h => h.brier).filter(b => b > 0);
    const rois = history.map(h => h.roi).filter(r => r !== undefined);
    const features = history.map(h => h.features).filter(f => f > 0);
    const trend = briers.length >= 2 ? briers[briers.length - 1] - briers[0] : 0;
    const avgBrier = briers.reduce((a, b) => a + b, 0) / briers.length;

    // Detect problems + record for anticipation
    const problems = [];
    if (trend > 0.002) {
      problems.push('DEGRADING: Brier getting worse');
      if (this.anticipation) this.anticipation.record('brier_regression', { trend, briers });
    }
    if (briers.length > 5 && Math.max(...briers) - Math.min(...briers) < 0.001) {
      problems.push('PLATEAU: No variance in Brier');
      if (this.anticipation) this.anticipation.record('feature_plateau', { features, briers });
    }
    if (features.length > 0 && features[features.length - 1] < 80) problems.push('LOW_FEATURES: Under 80 selected');
    if (rois.length > 0 && rois[rois.length - 1] < 0) problems.push('NEGATIVE_ROI: Losing money');

    // v3: Include self-improvement stats in evaluation
    const improvementRate = this.state.totalActions > 0
      ? ((this.state.improvementActions / this.state.totalActions) * 100).toFixed(1)
      : '0.0';

    this._log('nos', `Eval: avg Brier ${avgBrier.toFixed(4)}, trend ${trend > 0 ? '+' : ''}${trend.toFixed(4)}, ${briers.length} obs. Problems: ${problems.length > 0 ? problems.join(', ') : 'none'}. Improvement rate: ${improvementRate}%`);

    const result = await this.getCompletion([{
      role: 'user',
      content: `Analyze NBA prediction model evolution (March 2026):

Brier scores (recent): ${briers.map(b => b.toFixed(4)).join(' -> ')}
ROIs: ${rois.map(r => r.toFixed(1) + '%').join(' -> ')}
Feature counts: ${features.join(' -> ')}
Trend: ${trend < 0 ? 'IMPROVING' : trend > 0 ? 'DEGRADING' : 'FLAT'}
Best ever: ${this.state.bestBrier.toFixed(4)}
Target: < 0.20
Stagnation: ${this.state.stagnationCount} consecutive
Active models: ${this.state.modelsActive.join(', ')}
Detected problems: ${problems.join('; ') || 'none'}
Self-improvement rate: ${improvementRate}% of actions led to improvement
Total S10 API calls: ${this.state.totalS10Calls}

New features not yet tested: ${this.research.filter(r => r.status === 'new').map(r => r.name).slice(0, 10).join(', ') || 'none'}

Give a TACTICAL assessment (4-5 sentences):
1. What's the #1 bottleneck right now?
2. What specific action would have highest impact?
3. Should we add more models (TFT, neural nets)?
4. Are we over/under-fitting?
Be quantitative and specific. Think like a quant fund PM reviewing their model.`
    }], { maxTokens: 600 });

    if (result.content) {
      this._log('nos', `Analysis: ${result.content.substring(0, 350)}`);

      // Auto-trigger improvement if ANY problem detected
      if (problems.length >= 1) {
        this._log('monk', `${problems.length} problem(s): ${problems.join(', ')}. Auto-triggering improvement.`);
        const lastEvo = history[history.length - 1];
        await this._improve(lastEvo);
      }

      // Report positive trends
      if (trend < -0.005 || (rois.length > 0 && rois[rois.length - 1] > 5)) {
        this._report(`Positive trend! Brier: ${briers[0]?.toFixed(4)} -> ${briers[briers.length - 1]?.toFixed(4)}, ROI: ${rois[rois.length - 1]?.toFixed(1)}%`);
      }
    }

    // ALWAYS ACT: pull run-stats after evaluation for completeness
    try {
      const runStats = await this._callS10Direct('GET', '/api/run-stats');
      if (runStats && !runStats.error) {
        this._cycleActionCount++;
        this.state.totalS10Calls++;
        this._trackAction('evaluate', 'pull_run_stats', runStats);
      }
    } catch {}
  }

  // ══════════════════════════════════════════
  //  IMPROVE — Apply improvements (with self-tracking)
  // ══════════════════════════════════════════

  async _improve(currentState) {
    // Cooldown: only apply improvements every 30 min
    const lastImprove = this.state.lastImproveApplied || 0;
    if (Date.now() - new Date(lastImprove).getTime() < 30 * 60 * 1000) {
      this._log('nos', 'Improve cooldown active (30min). Observing only.');
      return;
    }

    this.state.lastImprove = new Date().toISOString();
    this._log('nos', 'IMPROVE mode — APPLYING changes via S10 API.');

    // Features must be validated by Adam (CLI) before injection
    // 1. Log pending features but do NOT auto-inject into S10
    const newFeatures = this.research.filter(r => r.status === 'new');
    if (newFeatures.length > 0) {
      const top5 = newFeatures.slice(0, 5);
      for (const feat of top5) feat.status = 'needs_validation';
      this._saveResearch();
      this._log('ademo', `${top5.length} features marked needs_validation: ${top5.map(f => f.name).join(', ')}. Awaiting Adam review.`);
      this._trackAction('improve', 'features_pending_validation', { count: top5.length, features: top5.map(f => f.name) });
    }

    // 2. Ask LLM for parameter changes
    const result = await this.getCompletion([{
      role: 'user',
      content: `NBA prediction model at Brier ${currentState?.brier?.toFixed(4) || this.state.bestBrier.toFixed(4)}, stagnation ${this.state.stagnationCount * 2} cycles.

Setup: genetic feature selection, ${this.state.modelsActive.length} model ensemble, walk-forward validation.
Current mutation_rate: ${currentState?.mutationRate || 0.10}
Current population: ${currentState?.population || 150}

Self-improvement stats: ${this.state.improvementActions} improvements vs ${this.state.regressionActions} regressions out of ${this.state.totalActions} total actions.

IMPORTANT: S10 has HARD CAPS — mutation ≤ 0.10, pop ≤ 80, features ≤ 150.
The goal is Brier < 0.20 (best predictor), NOT high ROI.
Fitness = Brier 60% + Calibration 20% + ROI 10% + Sharpe 10%.
STABILITY beats aggression. Low mutation + tight features = convergence.

You MUST respond in this exact JSON format — nothing else:
{
  "mutation_rate": <float between 0.02 and 0.10>,
  "pop_size": <int between 40 and 80>,
  "target_features": <int between 60 and 150>,
  "crossover_rate": <float between 0.6 and 0.85>,
  "command": "none",
  "reasoning": "<1 sentence why>"
}

Be conservative. Small adjustments. Do NOT diversify or boost_mutation unless stagnation > 15.`
    }], { maxTokens: 300 });

    if (result.content) {
      this._log('nos', `LLM suggested: ${result.content.substring(0, 200)}`);

      try {
        let jsonStr = result.content;
        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (jsonMatch) jsonStr = jsonMatch[0];
        const suggestion = JSON.parse(jsonStr);

        // Apply config
        const configParams = {};
        // HARD CAPS — respect S10 limits
        if (suggestion.mutation_rate) configParams.mutation_rate = Math.max(0.02, Math.min(0.10, suggestion.mutation_rate));
        if (suggestion.pop_size) configParams.pop_size = Math.max(40, Math.min(80, suggestion.pop_size));
        if (suggestion.target_features) configParams.target_features = Math.max(60, Math.min(150, suggestion.target_features));
        if (suggestion.crossover_rate) configParams.crossover_rate = Math.max(0.6, Math.min(0.85, suggestion.crossover_rate));

        if (Object.keys(configParams).length > 0) {
          const configResult = await this.callS10('/api/config', configParams);
          this._log('cain', `CONFIG APPLIED: ${JSON.stringify(configParams)} -> ${configResult.status || configResult.error}`);
          this._trackAction('improve', 'config_change', configParams);
          this._cycleActionCount++;
          this.state.totalS10Calls++;
          this.state.lastImproveApplied = new Date().toISOString();
        }

        // Execute command
        if (suggestion.command && suggestion.command !== 'none') {
          const cmdResult = await this.callS10('/api/command', { command: suggestion.command });
          this._log('monk', `COMMAND APPLIED: ${suggestion.command} -> ${cmdResult.status || cmdResult.error}`);
          this._trackAction('improve', `command_${suggestion.command}`, null);
          this._cycleActionCount++;
          this.state.totalS10Calls++;
        }

        this._log('nos', `APPLIED: ${suggestion.reasoning || 'improvement applied'}`);
        this._report(`Improvement applied: ${suggestion.reasoning || JSON.stringify(configParams)}`);
      } catch (parseErr) {
        this._log('monk', `Parse failed: ${parseErr.message}. Pulling status instead of intervening.`);
        const fallbackResult = await this._callS10Direct('GET', '/api/status');
        this._log('cain', `FALLBACK status check: ${fallbackResult?.generation || fallbackResult?.error || 'ok'}`);
        this._trackAction('improve', 'fallback_status_check', null);
        this._cycleActionCount++;
        this.state.totalS10Calls++;
      }
    }
  }

  // ══════════════════════════════════════════
  //  HEAL — Self-healing error detection + fix
  // ══════════════════════════════════════════

  async _heal() {
    this.state.lastHeal = new Date().toISOString();
    this.state.healCount++;

    // 1. Check S10 remote status
    try {
      const remoteLog = await (async () => {
        try {
          const resp = await fetch('https://lbjlincoln-nomos-nba-quant.hf.space/api/remote-log',
            { signal: AbortSignal.timeout(10000) });
          return resp.ok ? await resp.json() : null;
        } catch { return null; }
      })();

      if (remoteLog) {
        const logTail = remoteLog.log_tail || [];
        const errorLogs = logTail.filter(l => /\[ERROR\]/.test(l));
        if (errorLogs.length > 0 && this.state.healCount % 3 === 0) {
          this._log('monk', `S10 has ${errorLogs.length} errors: ${errorLogs.slice(-2).join(' | ').substring(0, 200)}`);
        }
      }

      // Check S10 status via API
      try {
        const statusResp = await fetch('https://lbjlincoln-nomos-nba-quant.hf.space/api/status',
          { signal: AbortSignal.timeout(10000) });
        if (statusResp.ok) {
          const s10Status = await statusResp.json();
          this._cycleActionCount++;
          this.state.totalS10Calls++;
          const status = s10Status.status || '';
          if (status === 'STARTING' && s10Status.generation === 0 && s10Status.games === 0) {
            const startedAt = new Date(s10Status.started_at);
            const minutesStuck = (Date.now() - startedAt.getTime()) / 60000;
            if (minutesStuck > 5) {
              this._log('monk', `S10 stuck at STARTING for ${minutesStuck.toFixed(0)}min. Requesting reset.`);
              this._recordError('heal', `S10 stuck at STARTING for ${minutesStuck.toFixed(0)} minutes`);
              // ALWAYS ACT: try to unstick it
              await this.callS10('/api/reset');
              this._trackAction('heal', 'auto_reset_stuck', { minutesStuck });
              this._cycleActionCount++;
              this.state.totalS10Calls++;
            }
          } else if (/EVOLVING/.test(status)) {
            if (this.state.healCount % 6 === 0) {
              this._log('monk', `S10 healthy: Gen ${s10Status.generation}, Brier ${s10Status.best_brier}, Pop ${s10Status.pop_size}`);
            }
          }
        }
      } catch {}
    } catch {}

    // 2. Check for unfixed errors
    const unfixed = this.errors.filter(e => !e.fixed);
    if (unfixed.length === 0) {
      if (this.state.healCount % 6 === 0) {
        this._log('monk', `Health check OK: ${this.errors.length} total errors, 0 unfixed.`);
      }
      return;
    }

    this._log('monk', `${unfixed.length} unfixed errors. Analyzing + auto-fixing...`);

    const errorsByPhase = {};
    for (const err of unfixed) {
      errorsByPhase[err.phase] = errorsByPhase[err.phase] || [];
      errorsByPhase[err.phase].push(err);
    }

    for (const [phase, errs] of Object.entries(errorsByPhase)) {
      const errorMsgs = errs.map(e => e.message).join('; ');

      // S10 unreachable -> try ping
      if (/unreachable|timeout|ECONNREFUSED/i.test(errorMsgs)) {
        this._log('monk', `S10 connectivity issue in ${phase}. Pinging...`);
        try {
          const resp = await fetch('https://lbjlincoln-nomos-nba-quant.hf.space/api/status',
            { signal: AbortSignal.timeout(15000) });
          if (resp.ok) {
            this._log('monk', 'S10 back online. Marking errors fixed.');
            for (const err of errs) { err.fixed = true; err.fixedAt = new Date().toISOString(); }
            this._cycleActionCount++;
            this.state.totalS10Calls++;
          }
        } catch {}
        continue;
      }

      const result = await this.getCompletion([{
        role: 'user',
        content: `Self-healing diagnostic for NBA Quant AI.

Phase: ${phase} | Errors: ${errorMsgs} | Count: ${errs.length}

Available S10 API actions:
- POST /api/config {mutation_rate, pop_size, target_features, crossover_rate}
- POST /api/reset (population reset keeping elites)
- POST /api/command {command: "diversify" or "boost_mutation"}

Respond in JSON: {"action": "config|reset|command|none", "params": {...}, "diagnosis": "1 sentence"}`
      }], { maxTokens: 200 });

      if (result.content) {
        this._log('monk', `Diagnosis: ${result.content.substring(0, 200)}`);
        try {
          const jsonMatch = result.content.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            const fix = JSON.parse(jsonMatch[0]);
            if (fix.action === 'config' && fix.params) {
              await this.callS10('/api/config', fix.params);
              this._log('monk', `AUTO-FIX: config ${JSON.stringify(fix.params)}`);
              this._trackAction('heal', 'auto_fix_config', fix.params);
              this._cycleActionCount++;
              this.state.totalS10Calls++;
            } else if (fix.action === 'reset') {
              await this.callS10('/api/reset');
              this._log('monk', 'AUTO-FIX: population reset');
              this._trackAction('heal', 'auto_fix_reset', null);
              this._cycleActionCount++;
              this.state.totalS10Calls++;
            } else if (fix.action === 'command' && fix.params?.command) {
              await this.callS10('/api/command', fix.params);
              this._log('monk', `AUTO-FIX: ${fix.params.command}`);
              this._trackAction('heal', `auto_fix_${fix.params.command}`, null);
              this._cycleActionCount++;
              this.state.totalS10Calls++;
            }
          }
        } catch {}
        for (const err of errs) { err.fixed = true; err.fixedAt = new Date().toISOString(); }
      }
    }

    this._saveErrors();
  }

  // ══════════════════════════════════════════
  //  DATA CHECK — Dataset validation + Polymarket
  // ══════════════════════════════════════════

  async _dataCheck() {
    this._log('dali', 'Running data quality check...');

    const checks = [];
    const lastEvo = this.state.evolutionHistory.length > 0
      ? this.state.evolutionHistory[this.state.evolutionHistory.length - 1] : null;

    if (lastEvo) {
      if (lastEvo.featureCandidates < 500)
        checks.push(`Feature pool only ${lastEvo.featureCandidates}/708 — needs expansion`);
      if (lastEvo.features < 50)
        checks.push(`Only ${lastEvo.features} features selected — too few`);
      if (lastEvo.population < 100)
        checks.push(`Population ${lastEvo.population} — should be 200+`);
    }

    const missingModels = this.state.modelsTarget.filter(m => !this.state.modelsActive.includes(m));
    if (missingModels.length > 0)
      checks.push(`Missing models: ${missingModels.join(', ')}`);

    const recentResearch = this.research.filter(r => {
      const age = Date.now() - new Date(r.discoveredAt).getTime();
      return age < 3600000;
    });
    if (recentResearch.length === 0 && this.state.cycleCount > 3)
      checks.push('No new features discovered in last hour');

    if (checks.length > 0) {
      this._log('dali', `Data issues: ${checks.join(' | ')}`);

      const result = await this.getCompletion([{
        role: 'user',
        content: `NBA Quant AI data quality report:

Issues found:
${checks.map((c, i) => `${i + 1}. ${c}`).join('\n')}

Current state:
- Best Brier: ${this.state.bestBrier.toFixed(4)}
- Total features researched: ${this.research.length}
- Active models: ${this.state.modelsActive.join(', ')}
- Stagnation count: ${this.state.stagnationCount}

What data sources should we add next for maximum impact? Consider:
1. Polymarket NBA odds evolution (live API)
2. Play-by-play data (NBA API pbp endpoint)
3. Player tracking data (NBA.com/stats)
4. Vegas consensus lines (multiple books)
5. Social media sentiment (Twitter/X API)
6. Weather/travel data

Prioritize by expected Brier improvement. 3 recommendations, 1 sentence each.`
      }], { maxTokens: 300 });

      if (result.content) {
        this._log('dali', `Recommendations: ${result.content.substring(0, 250)}`);
      }
    } else {
      this._log('dali', 'Data quality OK. All nominal.');
    }

    // ALWAYS ACT: pull cuts data during data check
    try {
      const cuts = await this._callS10Direct('GET', '/api/cuts');
      if (cuts && !cuts.error) {
        this._cycleActionCount++;
        this.state.totalS10Calls++;
        this._trackAction('data_check', 'pull_cuts', null);
      }
    } catch {}
  }

  // ══════════════════════════════════════════
  //  FORCE-ACT — Guarantee action if cycle was quiet
  // ══════════════════════════════════════════

  async _forceAct() {
    this.state.lastForceAct = new Date().toISOString();

    // If we've already had actions this cycle, skip
    if (this._cycleActionCount > 2) return;

    this._log('nos', `FORCE-ACT: only ${this._cycleActionCount} actions this cycle. Forcing S10 interaction.`);
    await this._forceS10Action('force_act_cycle');

    // Features must be validated by Adam (CLI) before injection — do not auto-inject
    const untested = this.research.filter(r => r.status === 'new');
    if (untested.length > 0) {
      for (const f of untested.slice(0, 2)) f.status = 'needs_validation';
      this._saveResearch();
      this._log('ademo', `FORCE-ACT: ${untested.slice(0, 2).length} features marked needs_validation. No auto-injection.`);
    }
  }

  // ══════════════════════════════════════════
  //  HEARTBEAT — Telegram status every 30 min
  // ══════════════════════════════════════════

  async _heartbeat() {
    this.state.lastHeartbeat = new Date().toISOString();
    this.state.heartbeatsSent++;

    // Pull fresh S10 status for heartbeat
    let s10Status = null;
    try {
      s10Status = await this._callS10Direct('GET', '/api/status');
      this.state.totalS10Calls++;
    } catch {}

    const uptime = this.state.cycleCount * 5; // approx minutes
    const improvementRate = this.state.totalActions > 0
      ? ((this.state.improvementActions / this.state.totalActions) * 100).toFixed(1)
      : 'N/A';

    const s10Line = s10Status && !s10Status.error
      ? `Gen ${s10Status.generation || '?'} | Brier ${s10Status.best_brier || '?'} | Pop ${s10Status.pop_size || '?'} | Stag ${s10Status.stagnation || 0}`
      : 'S10 unreachable';

    const heartbeatMsg = [
      `*EVE HEARTBEAT #${this.state.heartbeatsSent}*`,
      '',
      `Status: RUNNING`,
      `Uptime: ~${uptime}min | Cycles: ${this.state.cycleCount}`,
      `S10: ${s10Line}`,
      '',
      `Best Brier: ${this.state.bestBrier.toFixed(4)}`,
      `Best ROI: ${this.state.bestROI.toFixed(1)}%`,
      '',
      `S10 API calls: ${this.state.totalS10Calls}`,
      `Actions: ${this.state.totalActions} total`,
      `  Improvements: ${this.state.improvementActions}`,
      `  Regressions: ${this.state.regressionActions}`,
      `  Neutral: ${this.state.neutralActions}`,
      `  Improvement rate: ${improvementRate}%`,
      '',
      `LLM failures: ${this.state.llmFailures} | Retries: ${this.state.llmRetries}`,
      `Rule engine activations: ${this.state.ruleEngineActivations}`,
      `Features researched: ${this.research.length}`,
      `Unfixed errors: ${this.errors.filter(e => !e.fixed).length}`,
      '',
      `_ALWAYS ACT mode — zero idle cycles_`,
    ].join('\n');

    if (this.bot) {
      try {
        await this.bot.sendMessage(this.adminId, heartbeatMsg, { parse_mode: 'Markdown' });
        this._log('nos', `Heartbeat #${this.state.heartbeatsSent} sent to Telegram.`);
      } catch (e) {
        logger.warn('Heartbeat Telegram failed:', e.message);
        this._log('monk', `Heartbeat Telegram failed: ${e.message}`);
      }
    }
  }

  // ══════════════════════════════════════════
  //  EMERGENCY DIVERSIFICATION
  // ══════════════════════════════════════════

  async _emergencyDiversify(currentState) {
    // CONTROLLED emergency — reset population but keep parameters conservative
    this._log('monk', 'CONTROLLED EMERGENCY — Resetting population (keeping elites) with stable params.');

    const resetResult = await this.callS10('/api/reset');
    this._log('monk', `Population RESET: ${resetResult.status || resetResult.error}`);
    this._trackAction('emergency', 'population_reset', null);
    this._cycleActionCount++;
    this.state.totalS10Calls++;

    // Set STABLE params — NOT aggressive. The goal is convergence, not chaos.
    const stableParams = {
      mutation_rate: 0.06,
      target_features: 80,
      crossover_rate: 0.80,
    };
    const configResult = await this.callS10('/api/config', stableParams);
    this._log('nos', `Stable config after reset: ${JSON.stringify(stableParams)} -> ${configResult.status || configResult.error}`);
    this._trackAction('emergency', 'stable_config', stableParams);
    this._cycleActionCount++;
    this.state.totalS10Calls++;

    this.state.stagnationCount = 0;

    this._report(`CONTROLLED RESET: Pop reset + stable params (mut 0.06, feat 80). Brier was ${currentState?.brier?.toFixed(4)}.`);
  }

  // ══════════════════════════════════════════
  //  FORCE S10 ACTION — Pick a random useful action
  // ══════════════════════════════════════════

  async _forceS10Action(reason) {
    const action = FORCED_ACTIONS[Math.floor(Math.random() * FORCED_ACTIONS.length)];
    this._log('nos', `FORCE S10 [${reason}]: ${action.desc}`);

    try {
      const endpoint = S10_ENDPOINTS[action.fn];
      if (!endpoint) return;

      let result;
      if (endpoint.method === 'GET') {
        result = await this._callS10Direct('GET', endpoint.path);
      } else if (action.params) {
        const params = typeof action.params === 'function' ? action.params() : action.params;
        result = await this.callS10(endpoint.path, params);
      } else {
        result = await this._callS10Direct('GET', S10_ENDPOINTS.status.path);
      }

      if (result && !result.error) {
        this._cycleActionCount++;
        this.state.totalS10Calls++;
        this._trackAction('force', action.name, result);

        // Special handling: log diversity metrics for population analysis
        if (action.name === 'analyze_population_diversity') {
          const modelTypes = result.model_types || result.best_model_type || 'unknown';
          const popSize = result.pop_size || '?';
          const features = result.best_features || '?';
          const stagnation = result.stagnation || 0;
          this._log('monk', `DIVERSITY CHECK: pop=${popSize}, features=${features}, stagnation=${stagnation}, model=${modelTypes}`);
        } else {
          this._log('nos', `FORCE S10 result: ${JSON.stringify(result).substring(0, 150)}`);
        }
      }
    } catch (e) {
      this._log('monk', `Force S10 action failed: ${e.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  DIRECT S10 CALL — GET requests without callS10 wrapper
  // ══════════════════════════════════════════

  async _callS10Direct(method, path) {
    try {
      const resp = await fetch(`${S10_BASE}${path}`, {
        method,
        signal: AbortSignal.timeout(15000),
      });
      if (resp.ok) return await resp.json();
      return { error: `HTTP ${resp.status}` };
    } catch (e) {
      return { error: e.message };
    }
  }

  // ══════════════════════════════════════════
  //  SELF-IMPROVEMENT TRACKING
  // ══════════════════════════════════════════

  _trackAction(phase, actionName, params) {
    this.state.totalActions++;
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      timestamp: new Date().toISOString(),
      phase,
      action: actionName,
      params: params ? JSON.stringify(params).substring(0, 200) : null,
      brierAtTime: this.state.bestBrier,
      outcome: 'pending',  // will be updated by _markRecentActions
    };
    this.actionLog.push(entry);
    if (this.actionLog.length > MAX_ACTION_LOG)
      this.actionLog = this.actionLog.slice(-MAX_ACTION_LOG);
    this._saveActionLog();
  }

  _markRecentActions(outcome, delta) {
    // Only mark as improvement if delta > 0.001 (meaningful change)
    // Use 60-min window to capture full GA cycle effects
    if (outcome === 'improvement' && Math.abs(delta) < 0.001) outcome = 'neutral';
    const cutoff = Date.now() - 60 * 60 * 1000;  // was 15 min
    let marked = 0;
    for (let i = this.actionLog.length - 1; i >= 0; i--) {
      const entry = this.actionLog[i];
      if (new Date(entry.timestamp).getTime() < cutoff) break;
      if (entry.outcome === 'pending') {
        entry.outcome = outcome;
        entry.delta = delta;
        marked++;
        if (outcome === 'improvement') this.state.improvementActions++;
        else if (outcome === 'regression') this.state.regressionActions++;
        else this.state.neutralActions++;
      }
    }
    if (marked > 0) {
      this._log('nos', `Self-track: marked ${marked} recent actions as "${outcome}" (delta: ${delta?.toFixed(4) || '?'})`);
      this._saveActionLog();
    }
  }

  // ══════════════════════════════════════════
  //  REPORT — Telegram (positive + emergencies)
  // ══════════════════════════════════════════

  _report(message) {
    this.state.lastReport = new Date().toISOString();
    if (this.bot && this.adminId) {
      const text = `*NOMOS42 NBA Quant AI*\n\n${message}\n\n_Brier: ${this.state.bestBrier.toFixed(4)} | ROI: ${this.state.bestROI.toFixed(1)}%_\n_Cycle: ${this.state.cycleCount} | S10 calls: ${this.state.totalS10Calls} | Features: ${this.research.length}_`;
      this.bot.sendMessage(this.adminId, text, { parse_mode: 'Markdown' }).catch(e => {
        logger.warn('Telegram report failed:', e.message);
      });
    }
  }

  // ══════════════════════════════════════════
  //  UTILITY METHODS
  // ══════════════════════════════════════════

  _parseEvolutionData(data) {
    try {
      const text = typeof data === 'string' ? data : JSON.stringify(data);
      const extract = (pattern) => {
        const match = text.match(pattern);
        return match ? match[1] : null;
      };
      return {
        generation: parseInt(extract(/Generation[^\d]*(\d+)/i)) || 0,
        brier: parseFloat(extract(/Best Brier[^\d]*([\d.]+)/i)) || 0,
        roi: parseFloat(extract(/Best ROI[^\d]*([\d.-]+)/i)) || 0,
        sharpe: parseFloat(extract(/Best Sharpe[^\d]*([\d.-]+)/i)) || 0,
        features: parseInt(extract(/Best Features[^\d]*(\d+)/i)) || 0,
        model: extract(/Model Type[^|]*\|\s*(\w+)/i) || 'unknown',
        population: parseInt(extract(/Population[^\d]*(\d+)/i)) || 0,
        mutationRate: parseFloat(extract(/Mutation Rate[^\d]*([\d.]+)/i)) || 0,
        stagnation: parseInt(extract(/Stagnation[^\d]*(\d+)/i)) || 0,
        games: parseInt(extract(/([\d,]+)\s*games/i)?.replace(/,/g, '')) || 0,
        featureCandidates: parseInt(extract(/Feature Candidates[^\d]*(\d+)/i)) || 0,
        cycle: parseInt(extract(/Cycle[^\d]*(\d+)/i)) || 0,
      };
    } catch { return null; }
  }

  _parseResearchResults(text, category) {
    const features = [];
    const nameMatches = text.match(/[a-z][a-z_]+_[a-z_]+/g) || [];
    const uniqueNames = [...new Set(nameMatches)].filter(n => n.length > 5 && n.length < 60);

    for (const name of uniqueNames.slice(0, 5)) {
      const idx = text.indexOf(name);
      const context = text.substring(idx, idx + 300).replace(/\n/g, ' ').trim();
      features.push({
        name,
        category: category || 'research',
        description: context.substring(0, 200),
        power: /high/i.test(context) ? 'high' : /medium/i.test(context) ? 'medium' : 'low',
        complexity: /easy/i.test(context) ? 'easy' : /hard/i.test(context) ? 'hard' : 'medium',
      });
    }
    return features;
  }

  _recordError(phase, message) {
    this.errors.push({
      phase, message,
      timestamp: new Date().toISOString(),
      fixed: false,
    });
    if (this.errors.length > 100) this.errors = this.errors.slice(-100);
    this._saveErrors();
  }

  _log(agentId, message) {
    const agent = Object.values(AGENTS).find(a => a.id === agentId) || AGENTS.NOS;
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      agent: agent.id,
      agentName: agent.name,
      role: agent.role,
      color: agent.color,
      message,
      timestamp: new Date().toISOString(),
    };
    this.conversations.push(entry);
    if (this.conversations.length > MAX_CONVERSATIONS)
      this.conversations = this.conversations.slice(-MAX_CONVERSATIONS);
    logger.info(`[${agent.name}] ${message.substring(0, 120)}`);
  }

  // ── Dashboard API getters ──
  getConversations(limit = 50) { return this.conversations.slice(-limit); }
  getStatus() {
    return {
      ...this.state,
      running: this.running,
      conversationCount: this.conversations.length,
      researchCount: this.research.length,
      newFeatures: this.research.filter(r => r.status === 'new').length,
      suggestedFeatures: this.research.filter(r => r.status === 'suggested').length,
      pendingValidation: this.research.filter(r => r.status === 'needs_validation').length,
      errorCount: this.errors.filter(e => !e.fixed).length,
      agents: AGENTS,
      featureCategories: FEATURE_CATEGORIES.length,
      totalCandidates: 708,
      // v3: self-improvement stats
      totalS10Calls: this.state.totalS10Calls,
      totalActions: this.state.totalActions,
      improvementActions: this.state.improvementActions,
      regressionActions: this.state.regressionActions,
      neutralActions: this.state.neutralActions,
      improvementRate: this.state.totalActions > 0
        ? ((this.state.improvementActions / this.state.totalActions) * 100).toFixed(1) + '%'
        : 'N/A',
      llmFailures: this.state.llmFailures,
      heartbeatsSent: this.state.heartbeatsSent,
    };
  }
  getResearch(limit = 30) { return this.research.slice(-limit); }
  getEvolutionHistory(limit = 50) { return this.state.evolutionHistory.slice(-limit); }
  getErrors() { return this.errors.slice(-20); }
  getActionLog(limit = 50) { return this.actionLog.slice(-limit); }

  // ── Persistence ──
  _save() {
    try {
      fs.writeFileSync(STATE_FILE, JSON.stringify(this.state, null, 2));
      fs.writeFileSync(CONVERSATIONS_FILE, JSON.stringify(this.conversations));
    } catch (e) { logger.warn('Save state:', e.message); }
  }
  _saveResearch() {
    try { fs.writeFileSync(RESEARCH_FILE, JSON.stringify(this.research, null, 2)); }
    catch (e) { logger.warn('Save research:', e.message); }
  }
  _saveErrors() {
    try { fs.writeFileSync(ERRORS_FILE, JSON.stringify(this.errors, null, 2)); }
    catch (e) { logger.warn('Save errors:', e.message); }
  }
  _saveActionLog() {
    try { fs.writeFileSync(ACTION_LOG_FILE, JSON.stringify(this.actionLog, null, 2)); }
    catch (e) { logger.warn('Save action log:', e.message); }
  }
}

module.exports = AgenticLoop;
