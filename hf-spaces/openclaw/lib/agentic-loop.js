/**
 * Agentic Loop v2 — FULL BLAST 24/7 Karpathy-style autonomous NBA Quant improvement
 *
 * Self-healing, self-improving, autonomous error detection and correction.
 * Spawns child research threads for specialized feature categories.
 *
 * Agents:
 *   N.O.S  — Strategic Commander (Claude Code CLI persona)
 *   ADEMO  — Research & Execution (OpenClaw healer-alpha)
 *   CAIN   — Evolution Engine (genetic algorithm tracker)
 *   DALI   — Data Scientist (Polymarket, play-by-play, datasets)
 *   MONK   — Self-Healer (error detection, autonomous fixing)
 *
 * Cycles:
 *   OBSERVE   (5 min)  — Check evolution, detect anomalies
 *   RESEARCH  (20 min) — Discover features via academic research
 *   EVALUATE  (10 min) — Deep model performance analysis
 *   IMPROVE   (auto)   — Apply improvements on stagnation
 *   HEAL      (5 min)  — Detect and fix errors autonomously
 *   REPORT    (auto)   — Telegram only on positive news
 */

const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const LOOP_DATA_DIR = '/data/agentic-loop';
const CONVERSATIONS_FILE = path.join(LOOP_DATA_DIR, 'conversations.json');
const STATE_FILE = path.join(LOOP_DATA_DIR, 'state.json');
const RESEARCH_FILE = path.join(LOOP_DATA_DIR, 'research-log.json');
const ERRORS_FILE = path.join(LOOP_DATA_DIR, 'errors.json');
const MAX_CONVERSATIONS = 500;
const MAX_RESEARCH_ITEMS = 200;

// ── 5 AGENT IDENTITIES ──
const AGENTS = {
  NOS:  { id: 'nos',  name: 'N.O.S',  role: 'Strategic Commander',    color: '#7c3aed' },
  ADEMO:{ id: 'ademo',name: 'ADEMO',  role: 'Research & Execution',   color: '#06b6d4' },
  CAIN: { id: 'cain', name: 'CAIN',   role: 'Evolution Engine',       color: '#f59e0b' },
  DALI: { id: 'dali', name: 'DALI',   role: 'Data Scientist',         color: '#39ff14' },
  MONK: { id: 'monk', name: 'MONK',   role: 'Self-Healer',            color: '#ff2e63' },
};

// ── FEATURE CATEGORIES (708 candidates across 17 categories) ──
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
  // NEW categories (added by FULL BLAST directive)
  { name: 'tanking_playoff_context', count: 0, desc: 'Draft incentive, playoff probability, games behind' },
  { name: 'polymarket_evolution', count: 0, desc: 'Polymarket odds movement, implied probability shifts' },
  { name: 'play_by_play_impact', count: 0, desc: 'Clutch time stats, garbage time filtering, possession quality' },
  { name: 'season_trajectory', count: 0, desc: 'Win curve projection, remaining SOS, trade deadline impact' },
];

class AgenticLoop {
  constructor({ getCompletion, bot, adminId, fetchEvolution, callS10, anticipationEngine, ruleEngine }) {
    this.getCompletion = getCompletion;
    this.bot = bot;
    this.adminId = adminId;
    this.fetchEvolution = fetchEvolution;
    this.callS10 = callS10 || (async () => ({ error: 'callS10 not configured' }));
    this.anticipation = anticipationEngine || null;
    this.ruleEngine = ruleEngine || null;

    this.conversations = [];
    this.state = {
      status: 'idle',
      lastObserve: null, lastResearch: null, lastEvaluate: null,
      lastImprove: null, lastReport: null, lastHeal: null,
      lastAnticipate: null,
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
    };
    this.research = [];
    this.errors = [];
    this.running = false;
    this.intervals = [];

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
  }

  // ══════════════════════════════════════════
  //  START / STOP
  // ══════════════════════════════════════════

  start() {
    if (this.running) return;
    this.running = true;
    this.state.status = 'running';

    this._log('nos', 'FULL BLAST MODE — Agentic loop v2 initialized. 5 agents online. 708 feature candidates. 24/7 autonomous improvement.');
    this._log('ademo', 'Research engine online. Academic-grade NBA analytics research active.');
    this._log('cain', 'Evolution tracker active. Monitoring Brier, ROI, Sharpe, Calibration.');
    this._log('dali', 'Data scientist online. Polymarket tracking, play-by-play analysis, dataset validation.');
    this._log('monk', 'Self-healer online. Error detection, autonomous fixing, health monitoring.');

    // OBSERVE — every 5 min
    this.intervals.push(setInterval(() => this._safeRun('observe', () => this._observe()), 5 * 60 * 1000));
    // ANTICIPATE — every 7 min (predictive bottleneck prevention)
    this.intervals.push(setInterval(() => this._safeRun('anticipate', () => this._anticipate()), 7 * 60 * 1000));
    // RESEARCH — every 20 min (increased frequency for FULL BLAST)
    this.intervals.push(setInterval(() => this._safeRun('research', () => this._research()), 20 * 60 * 1000));
    // EVALUATE — every 10 min
    this.intervals.push(setInterval(() => this._safeRun('evaluate', () => this._evaluate()), 10 * 60 * 1000));
    // HEAL — every 5 min (self-healing cycle)
    this.intervals.push(setInterval(() => this._safeRun('heal', () => this._heal()), 5 * 60 * 1000));
    // DATA VALIDATION — every 15 min
    this.intervals.push(setInterval(() => this._safeRun('data', () => this._dataCheck()), 15 * 60 * 1000));
    // STATE SAVE — every 2 min
    this.intervals.push(setInterval(() => this._save(), 2 * 60 * 1000));

    // Run first cycles immediately (staggered) — observe first, then evaluate quickly
    setTimeout(() => this._safeRun('observe', () => this._observe()), 3000);
    setTimeout(() => this._safeRun('anticipate', () => this._anticipate()), 6000);
    setTimeout(() => this._safeRun('evaluate', () => this._evaluate()), 10000);
    setTimeout(() => this._safeRun('research', () => this._research()), 18000);
    setTimeout(() => this._safeRun('heal', () => this._heal()), 28000);
    setTimeout(() => this._safeRun('data', () => this._dataCheck()), 38000);

    logger.info('Agentic loop v3 started — FULL BLAST 24/7 + ANTICIPATION ENGINE');
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

  // ── Safe runner — catches errors, logs them, never crashes ──
  // If LLM-dependent phase fails, rule engine takes over
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

      // If LLM failed, use rule engine for critical actions
      if (/LLM providers failed/i.test(err.message) && this.ruleEngine) {
        const lastEvo = this.state.evolutionHistory.length > 0
          ? this.state.evolutionHistory[this.state.evolutionHistory.length - 1] : null;
        if (lastEvo) {
          this._log('monk', 'LLM down — Rule Engine taking over for critical actions.');
          const actions = await this.ruleEngine.evaluate(lastEvo);
          for (const action of actions) {
            this._log('monk', `[RULE] ${action.ruleId}: ${action.result}`);
          }
          if (actions.length > 0) {
            this._report(`Rule Engine: ${actions.length} actions while LLM down: ${actions.map(a => a.ruleId).join(', ')}`);
          }
        }
      }
    }
  }

  // ══════════════════════════════════════════
  //  OBSERVE — Check evolution status + anomalies
  // ══════════════════════════════════════════

  async _observe() {
    this.state.lastObserve = new Date().toISOString();
    this.state.cycleCount++;

    const evoData = await this.fetchEvolution();
    if (!evoData) {
      this._log('cain', 'Evolution Space unreachable. MONK will investigate.');
      this._recordError('observe', 'Evolution Space unreachable');
      if (this.anticipation) {
        this.anticipation.record('connectivity_loss', { target: 'S10', phase: 'observe' });
      }
      return;
    }

    // If evoData is already a JSON object from /api/status, use directly
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
    if (!parsed) return;

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
      this._report(`Brier improved: ${old.toFixed(4)} → ${parsed.brier.toFixed(4)}`);
    }

    if (roiImproved && parsed.roi > 0) {
      this.state.bestROI = parsed.roi;
      this._log('cain', `ROI improvement: ${parsed.roi.toFixed(1)}%! Model: ${parsed.model}.`);
    }

    // ── Stagnation detection with AUTO-FIX (aggressive) + ANTICIPATION RECORDING ──
    if (parsed.stagnation > 2) {
      this.state.stagnationCount++;
      this._log('nos', `STAGNATION ALERT: ${parsed.stagnation} generations flat. Count: ${this.state.stagnationCount}.`);

      // Record for anticipation engine
      if (this.anticipation) {
        this.anticipation.record('ga_stagnation', {
          generation: parsed.generation, brier: parsed.brier,
          stagnation: parsed.stagnation, mutationRate: parsed.mutationRate,
        });
      }

      // Trigger improvement every stagnation cycle (not every 2nd)
      this._log('nos', 'Triggering improvement cycle...');
      await this._improve(parsed);

      if (this.state.stagnationCount >= 4) {
        this._log('monk', 'CRITICAL stagnation. Initiating emergency diversification: mutation boost, population restart, new feature injection.');
        await this._emergencyDiversify(parsed);
      }
    } else {
      if (this.state.stagnationCount > 0) {
        this._log('nos', `Stagnation broken! Back to improving. Previous stag count: ${this.state.stagnationCount}`);
        if (this.anticipation) this.anticipation.resolve('ga_stagnation');
      }
      this.state.stagnationCount = 0;
    }

    // ── Time-based improve: force every 30 min if Brier > 0.21 ──
    const timeSinceImprove = this.state.lastImprove ? Date.now() - new Date(this.state.lastImprove).getTime() : Infinity;
    if (parsed.brier > 0.21 && timeSinceImprove > 30 * 60 * 1000) {
      this._log('nos', `Brier ${parsed.brier.toFixed(4)} > 0.21 and no improve in ${Math.round(timeSinceImprove / 60000)}min. Forcing improvement.`);
      await this._improve(parsed);
    }

    // ── Feature pool check ──
    if (parsed.featureCandidates > 0 && parsed.featureCandidates < 500) {
      this._log('dali', `WARNING: Only ${parsed.featureCandidates} feature candidates active. Should be 708. Flagging for expansion.`);
    }

    // Regular status (every 4th cycle = ~20 min)
    if (this.state.cycleCount % 4 === 0) {
      this._log('nos', `Status: Gen ${parsed.generation} | Brier ${parsed.brier.toFixed(4)} | ROI ${parsed.roi.toFixed(1)}% | ${parsed.features} feats | Pop ${parsed.population}`);
      this._log('ademo', `Candidates: ${parsed.featureCandidates || '?'} | Mutation: ${parsed.mutationRate} | Stag: ${parsed.stagnation} | Models: ${this.state.modelsActive.length}/${this.state.modelsTarget.length}`);
    }
  }

  // ══════════════════════════════════════════
  //  ANTICIPATE — Predictive bottleneck prevention
  // ══════════════════════════════════════════

  async _anticipate() {
    if (!this.anticipation) return;
    this.state.lastAnticipate = new Date().toISOString();

    const lastEvo = this.state.evolutionHistory.length > 0
      ? this.state.evolutionHistory[this.state.evolutionHistory.length - 1] : null;

    const actions = await this.anticipation.check(lastEvo);

    if (actions.length > 0) {
      for (const action of actions) {
        this._log('nos', `ANTICIPATION [${action.id}]: ${action.applied}`);

        // If anticipation says we need research boost, trigger extra research
        if (action.needsResearchBoost) {
          this._log('ademo', 'Anticipation requested research acceleration. Triggering extra cycle.');
          this._safeRun('research', () => this._research());
        }

        // If anticipation says we need a restart
        if (action.needsRestart) {
          this._log('monk', `Anticipation requests space restart for ${action.id}. Alerting admin.`);
          this._report(`ANTICIPATION: ${action.name} — Space restart recommended`);
        }
      }
      this._log('nos', `Anticipation: ${actions.length} preemptive actions taken this cycle.`);
    } else if (this.state.cycleCount % 6 === 0) {
      this._log('nos', 'Anticipation: all clear, no preemptive actions needed.');
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
    const categories = FEATURE_CATEGORIES.filter(c => c.count > 0 || c.desc.includes('NEW'));
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
          this._log('ademo', `DISCOVERED: "${feat.name}" (${focusCategory.name}) — ${feat.power} power, impact: ${feat.description?.substring(0, 80) || 'analyzing...'}`);
        }
      }

      if (this.research.length > MAX_RESEARCH_ITEMS)
        this.research = this.research.slice(-MAX_RESEARCH_ITEMS);

      this._log('ademo', `Research complete. +${added} new. Total: ${this.research.length} features catalogued. ${this.research.filter(r => r.status === 'new').length} untested.`);
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
      this._log('nos', 'Not enough evolution data for evaluation. Need 3+ observations.');
      return;
    }

    const briers = history.map(h => h.brier).filter(b => b > 0);
    const rois = history.map(h => h.roi).filter(r => r !== undefined);
    const features = history.map(h => h.features).filter(f => f > 0);
    const trend = briers.length >= 2 ? briers[briers.length - 1] - briers[0] : 0;
    const avgBrier = briers.reduce((a, b) => a + b, 0) / briers.length;

    // Detect specific problems + record for anticipation
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

    this._log('nos', `Eval: avg Brier ${avgBrier.toFixed(4)}, trend ${trend > 0 ? '+' : ''}${trend.toFixed(4)}, ${briers.length} obs. Problems: ${problems.length > 0 ? problems.join(', ') : 'none detected'}`);

    const result = await this.getCompletion([{
      role: 'user',
      content: `Analyze NBA prediction model evolution (March 2026):

Brier scores (recent): ${briers.map(b => b.toFixed(4)).join(' → ')}
ROIs: ${rois.map(r => r.toFixed(1) + '%').join(' → ')}
Feature counts: ${features.join(' → ')}
Trend: ${trend < 0 ? 'IMPROVING' : trend > 0 ? 'DEGRADING' : 'FLAT'}
Best ever: ${this.state.bestBrier.toFixed(4)}
Target: < 0.20
Stagnation: ${this.state.stagnationCount} consecutive
Active models: ${this.state.modelsActive.join(', ')}
Detected problems: ${problems.join('; ') || 'none'}

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

      // Auto-trigger improvement if ANY problem detected (was >= 2, now >= 1)
      if (problems.length >= 1) {
        this._log('monk', `${problems.length} problem(s) detected: ${problems.join(', ')}. Auto-triggering improvement.`);
        const lastEvo = history[history.length - 1];
        await this._improve(lastEvo);
      }

      // Report positive trends
      if (trend < -0.005 || (rois.length > 0 && rois[rois.length - 1] > 5)) {
        this._report(`Positive trend! Brier: ${briers[0]?.toFixed(4)} → ${briers[briers.length - 1]?.toFixed(4)}, ROI: ${rois[rois.length - 1]?.toFixed(1)}%`);
      }
    }
  }

  // ══════════════════════════════════════════
  //  IMPROVE — Apply improvements on stagnation
  // ══════════════════════════════════════════

  async _improve(currentState) {
    this.state.lastImprove = new Date().toISOString();
    this._log('nos', 'IMPROVE mode activated — will APPLY changes via S10 remote API.');

    // 1. Inject researched features into S10
    const newFeatures = this.research.filter(r => r.status === 'new');
    if (newFeatures.length > 0) {
      const top5 = newFeatures.slice(0, 5);
      const injectResult = await this.callS10('/api/inject-features', {
        features: top5.map(f => ({ name: f.name, category: f.category, description: f.description })),
      });
      for (const feat of top5) feat.status = 'injected';
      this._saveResearch();
      this._log('ademo', `INJECTED ${top5.length} features into S10: ${injectResult.status || injectResult.error}`);
    }

    // 2. Ask LLM for specific parameter changes
    const result = await this.getCompletion([{
      role: 'user',
      content: `NBA prediction model at Brier ${currentState?.brier?.toFixed(4) || this.state.bestBrier.toFixed(4)}, stagnation ${this.state.stagnationCount * 2} cycles.

Setup: genetic feature selection, ${this.state.modelsActive.length} model ensemble, walk-forward validation.
Current mutation_rate: ${currentState?.mutationRate || 0.10}
Current population: ${currentState?.population || 150}

You MUST respond in this exact JSON format — nothing else:
{
  "mutation_rate": <float between 0.02 and 0.25>,
  "pop_size": <int between 60 and 300>,
  "target_features": <int between 80 and 400>,
  "crossover_rate": <float between 0.5 and 0.95>,
  "command": "<one of: diversify, boost_mutation, or none>",
  "reasoning": "<1 sentence why>"
}

Be a quantitative PhD. Consider the stagnation level and current params. If stagnation > 10, be aggressive.`
    }], { maxTokens: 300 });

    if (result.content) {
      this._log('nos', `LLM suggested: ${result.content.substring(0, 200)}`);

      // 3. Parse and APPLY the suggestion via S10 API
      try {
        // Extract JSON from response (handle markdown code blocks)
        let jsonStr = result.content;
        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (jsonMatch) jsonStr = jsonMatch[0];
        const suggestion = JSON.parse(jsonStr);

        // Apply config changes
        const configParams = {};
        if (suggestion.mutation_rate) configParams.mutation_rate = Math.max(0.02, Math.min(0.25, suggestion.mutation_rate));
        if (suggestion.pop_size) configParams.pop_size = Math.max(60, Math.min(300, suggestion.pop_size));
        if (suggestion.target_features) configParams.target_features = Math.max(80, Math.min(400, suggestion.target_features));
        if (suggestion.crossover_rate) configParams.crossover_rate = Math.max(0.5, Math.min(0.95, suggestion.crossover_rate));

        if (Object.keys(configParams).length > 0) {
          const configResult = await this.callS10('/api/config', configParams);
          this._log('cain', `CONFIG APPLIED to S10: ${JSON.stringify(configParams)} → ${configResult.status || configResult.error}`);
        }

        // Execute command if needed
        if (suggestion.command && suggestion.command !== 'none') {
          const cmdResult = await this.callS10('/api/command', { command: suggestion.command });
          this._log('monk', `COMMAND APPLIED to S10: ${suggestion.command} → ${cmdResult.status || cmdResult.error}`);
        }

        this._log('nos', `APPLIED: ${suggestion.reasoning || 'improvement applied'}`);
        this._report(`Improvement applied: ${suggestion.reasoning || JSON.stringify(configParams)}`);
      } catch (parseErr) {
        this._log('monk', `Could not parse LLM suggestion as JSON: ${parseErr.message}. Applying default diversify.`);
        // Fallback: diversify on parse failure
        const fallbackResult = await this.callS10('/api/command', { command: 'diversify' });
        this._log('cain', `FALLBACK diversify applied: ${fallbackResult.status || fallbackResult.error}`);
      }
    }
  }

  // ══════════════════════════════════════════
  //  HEAL — Self-healing error detection + fix
  // ══════════════════════════════════════════

  async _heal() {
    this.state.lastHeal = new Date().toISOString();
    this.state.healCount++;

    // 1. Check S10 remote status for issues
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

      // Check actual S10 status via API (not log text which always contains "STARTING")
      try {
        const statusResp = await fetch('https://lbjlincoln-nomos-nba-quant.hf.space/api/status',
          { signal: AbortSignal.timeout(10000) });
        if (statusResp.ok) {
          const s10Status = await statusResp.json();
          const status = s10Status.status || '';
          // Only flag as stuck if status is literally "STARTING" for 5+ minutes
          if (status === 'STARTING' && s10Status.generation === 0 && s10Status.games === 0) {
            const startedAt = new Date(s10Status.started_at);
            const minutesStuck = (Date.now() - startedAt.getTime()) / 60000;
            if (minutesStuck > 5) {
              this._log('monk', `S10 stuck at STARTING for ${minutesStuck.toFixed(0)}min. Requesting reset.`);
              this._recordError('heal', `S10 stuck at STARTING for ${minutesStuck.toFixed(0)} minutes`);
            }
          } else if (/EVOLVING/.test(status)) {
            // S10 is healthy and evolving — log progress periodically
            if (this.state.healCount % 6 === 0) {
              this._log('monk', `S10 healthy: Gen ${s10Status.generation}, Brier ${s10Status.best_brier}, Pop ${s10Status.pop_size}`);
            }
          }
        }
      } catch {}
    } catch {}

    // 2. Check for unfixed local errors
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

      // If the error is S10 unreachable → try diversify as a wake-up
      if (/unreachable|timeout|ECONNREFUSED/i.test(errorMsgs)) {
        this._log('monk', `S10 connectivity issue in ${phase}. Attempting ping...`);
        try {
          const resp = await fetch('https://lbjlincoln-nomos-nba-quant.hf.space/api/status',
            { signal: AbortSignal.timeout(15000) });
          if (resp.ok) {
            this._log('monk', 'S10 is back online. Marking connectivity errors as fixed.');
            for (const err of errs) { err.fixed = true; err.fixedAt = new Date().toISOString(); }
          }
        } catch {}
        continue;
      }

      const result = await this.getCompletion([{
        role: 'user',
        content: `Self-healing diagnostic for NBA Quant AI.

Phase: ${phase} | Errors: ${errorMsgs} | Count: ${errs.length}

You can fix things by calling S10's API. Available actions:
- POST /api/config {mutation_rate, pop_size, target_features, crossover_rate}
- POST /api/reset (population reset keeping elites)
- POST /api/command {command: "diversify" or "boost_mutation"}

Respond in JSON: {"action": "config|reset|command|none", "params": {...}, "diagnosis": "1 sentence"}`
      }], { maxTokens: 200 });

      if (result.content) {
        this._log('monk', `Diagnosis: ${result.content.substring(0, 200)}`);
        // Try to parse and apply fix
        try {
          const jsonMatch = result.content.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            const fix = JSON.parse(jsonMatch[0]);
            if (fix.action === 'config' && fix.params) {
              await this.callS10('/api/config', fix.params);
              this._log('monk', `AUTO-FIX applied: config ${JSON.stringify(fix.params)}`);
            } else if (fix.action === 'reset') {
              await this.callS10('/api/reset');
              this._log('monk', 'AUTO-FIX applied: population reset');
            } else if (fix.action === 'command' && fix.params?.command) {
              await this.callS10('/api/command', fix.params);
              this._log('monk', `AUTO-FIX applied: ${fix.params.command}`);
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

    // Check feature pool size
    const lastEvo = this.state.evolutionHistory.length > 0
      ? this.state.evolutionHistory[this.state.evolutionHistory.length - 1] : null;

    if (lastEvo) {
      if (lastEvo.featureCandidates < 500) {
        checks.push(`Feature pool only ${lastEvo.featureCandidates}/708 — needs expansion`);
      }
      if (lastEvo.features < 50) {
        checks.push(`Only ${lastEvo.features} features selected — too few for ensemble`);
      }
      if (lastEvo.population < 100) {
        checks.push(`Population ${lastEvo.population} — should be 200+ for diversity`);
      }
    }

    // Check model coverage
    const missingModels = this.state.modelsTarget.filter(m => !this.state.modelsActive.includes(m));
    if (missingModels.length > 0) {
      checks.push(`Missing models: ${missingModels.join(', ')}`);
    }

    // Check research velocity
    const recentResearch = this.research.filter(r => {
      const age = Date.now() - new Date(r.discoveredAt).getTime();
      return age < 3600000; // last hour
    });
    if (recentResearch.length === 0 && this.state.cycleCount > 3) {
      checks.push('No new features discovered in last hour');
    }

    if (checks.length > 0) {
      this._log('dali', `Data issues: ${checks.join(' | ')}`);

      // Ask LLM for strategic recommendations based on data issues
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
      this._log('dali', 'Data quality OK. All systems nominal.');
    }
  }

  // ══════════════════════════════════════════
  //  EMERGENCY DIVERSIFICATION (critical stagnation)
  // ══════════════════════════════════════════

  async _emergencyDiversify(currentState) {
    this._log('monk', 'EMERGENCY DIVERSIFICATION — Critical stagnation. APPLYING reset + mutation boost NOW.');

    // 1. Immediately apply emergency commands to S10
    const resetResult = await this.callS10('/api/reset');
    this._log('monk', `Population RESET: ${resetResult.status || resetResult.error}`);

    const boostResult = await this.callS10('/api/command', { command: 'boost_mutation' });
    this._log('cain', `Mutation BOOSTED: ${boostResult.status || boostResult.error}`);

    // 2. Set aggressive parameters
    const aggressiveParams = {
      mutation_rate: 0.20,
      target_features: 250,
      crossover_rate: 0.90,
    };
    const configResult = await this.callS10('/api/config', aggressiveParams);
    this._log('nos', `Emergency config APPLIED: ${JSON.stringify(aggressiveParams)} → ${configResult.status || configResult.error}`);

    // 3. Inject all pending research features
    const allNew = this.research.filter(r => r.status === 'new' || r.status === 'suggested');
    if (allNew.length > 0) {
      await this.callS10('/api/inject-features', {
        features: allNew.map(f => ({ name: f.name, category: f.category, description: f.description })),
      });
      for (const f of allNew) f.status = 'injected';
      this._saveResearch();
      this._log('ademo', `Injected ${allNew.length} features during emergency.`);
    }

    // Reset stagnation counter locally
    this.state.stagnationCount = 0;

    this._report(`EMERGENCY APPLIED: Population reset + mutation 0.20 + ${allNew.length} features injected. Brier was ${currentState?.brier?.toFixed(4)}.`);
  }

  // ══════════════════════════════════════════
  //  REPORT — Telegram (positive news only, except emergencies)
  // ══════════════════════════════════════════

  _report(message) {
    this.state.lastReport = new Date().toISOString();
    if (this.bot && this.adminId) {
      const text = `*NOMOS42 NBA Quant AI*\n\n${message}\n\n_Brier: ${this.state.bestBrier.toFixed(4)} | ROI: ${this.state.bestROI.toFixed(1)}%_\n_Cycle: ${this.state.cycleCount} | Features: ${this.research.length}_`;
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
      errorCount: this.errors.filter(e => !e.fixed).length,
      agents: AGENTS,
      featureCategories: FEATURE_CATEGORIES.length,
      totalCandidates: 708,
    };
  }
  getResearch(limit = 30) { return this.research.slice(-limit); }
  getEvolutionHistory(limit = 50) { return this.state.evolutionHistory.slice(-limit); }
  getErrors() { return this.errors.slice(-20); }

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
}

module.exports = AgenticLoop;
