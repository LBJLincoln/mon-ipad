/**
 * Multi-Agent Coordinator — 6 Specialized AI Agents Working in Parallel
 *
 * Each agent has its own LLM brain and focus area. They all share:
 *   - Supabase experiment queue (submit experiments)
 *   - A2A protocol (communicate with each other)
 *   - GitHub (create PRs for code changes)
 *
 * Agents:
 *   1. Feature Scout    (Gemini)   — Discover new features, prune bad ones
 *   2. Model Architect  (OpenAI)   — Test new model architectures
 *   3. Calibrator       (Kimi)     — Improve probability calibration
 *   4. Evolution Tuner  (Gemini)   — Optimize GA hyperparameters
 *   5. Market Intel     (OpenAI)   — Analyze betting market patterns
 *   6. Research Scholar  (Gemini)  — Read papers, find SOTA techniques
 *
 * Each agent runs every 10 minutes (staggered by 100s to avoid collisions).
 * Output: EXPERIMENT blocks → Supabase queue → S11/Colab executes → results auto-promoted.
 */

const logger = require('./logger');
const { v4: uuidv4 } = require('uuid');

// ── LLM Provider Configs ──
const PROVIDERS = {
  gemini: {
    url: 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
    key: () => process.env.GOOGLE_API_KEY,
    model: 'gemini-2.5-flash',
  },
  openai: {
    url: 'https://api.openai.com/v1/chat/completions',
    key: () => process.env.OPENAI_API_KEY,
    model: 'gpt-4.1-mini',
  },
  kimi: {
    url: 'https://api.moonshot.cn/v1/chat/completions',
    key: () => process.env.KIMI_API_KEY,
    model: 'moonshot-v1-8k',
  },
  groq: {
    url: 'https://api.groq.com/openai/v1/chat/completions',
    key: () => process.env.GROQ_API_KEY,
    model: 'llama-3.3-70b-versatile',
  },
};

// ── Agent Definitions ──
const AGENTS = [
  {
    id: 'feature_scout',
    name: 'Feature Scout',
    provider: 'gemini',
    focus: 'feature_test',
    staggerMs: 0,
    systemPrompt: `You are the FEATURE SCOUT agent for an NBA prediction model (Brier target < 0.20).
Your ONLY job: propose NEW features to test or identify features to REMOVE.

Focus areas:
- Interaction terms (rest_days * pace, streak * travel, eFG% * opp_def_rtg)
- Rolling windows (3/5/7/10/15/20/30 games) for all base stats
- Opponent-adjusted stats (team stat vs opponent's league rank in that stat)
- Schedule density (games_last_7d, games_last_14d, travel_miles_last_7d)
- Referee tendencies (foul_rate_home_bias, over_call_rate per ref)
- Player availability (minutes-weighted team strength, injury impact)
- Momentum (weighted_win_pct_5g, point_differential_trend)
- Market-derived (CLV, line_movement_speed, steam_indicator, reverse_line_move)
- Quarter-level (q1_margin_avg_5g, q4_clutch_factor)
- Pace-adjusted (possessions-based stats instead of per-game)

RULES:
- Output 3-5 EXPERIMENT blocks per cycle
- Each experiment tests 2-5 related features together
- Include a clear HYPOTHESIS for why this should improve Brier
- Be SPECIFIC with feature names (snake_case, descriptive)
- Do NOT repeat features from RECENT EXPERIMENTS below`,
  },
  {
    id: 'model_architect',
    name: 'Model Architect',
    provider: 'openai',
    focus: 'model_test',
    staggerMs: 100000,
    systemPrompt: `You are the MODEL ARCHITECT agent for an NBA prediction model.
Current best: Brier 0.2205 with XGBoost ensemble.

Your ONLY job: propose new model architectures and hyperparameter configs.

Focus areas:
- Neural networks: MLP (vary depth/width/dropout), TabNet, FT-Transformer
- Gradient boosting: XGBoost (dart booster, different max_depth 6-12, colsample 0.5-0.9)
- LightGBM: deeper trees, lower lr (0.005-0.02), more estimators (500-2000)
- CatBoost: ordered boosting, different learning rates
- Stacking: meta-learner combining XGB+LGBM+RF+MLP
- Ensemble weights: optimize blending of individual models
- Regularization: L1/L2 on tree models, dropout on NNs

RULES:
- Output 3-5 EXPERIMENT blocks per cycle
- Include specific hyperparameters in params
- model_type must be one of: xgboost, lightgbm, catboost, rf, mlp, tabnet, stacking
- For neural nets, specify hidden_layers as array, e.g. [256, 128, 64]
- Include HYPOTHESIS for why this config should improve`,
  },
  {
    id: 'calibrator',
    name: 'Calibrator',
    provider: 'kimi',
    focus: 'calibration_test',
    staggerMs: 200000,
    systemPrompt: `You are the CALIBRATION agent for an NBA prediction model.
Goal: make predicted probabilities match actual win rates PERFECTLY.

Current issue: model predicts 60% but actual win rate for those games might be 55% or 65%.

Focus areas:
- Isotonic regression calibration
- Platt scaling (sigmoid fit)
- Temperature scaling (divide logits by T, optimize T on val set)
- Beta calibration (2-parameter generalization of Platt)
- Venn-Abers predictive calibration
- Ensemble calibration: average multiple calibration methods
- Bin-based recalibration
- Bayesian calibration with prior
- Expected Calibration Error (ECE) as direct optimization target

RULES:
- Output 2-4 EXPERIMENT blocks per cycle
- Specify calibration_method and any hyperparameters
- Always include cv_folds (recommend 5-10)
- Include HYPOTHESIS explaining why this calibration approach fits the data`,
  },
  {
    id: 'evolution_tuner',
    name: 'Evolution Tuner',
    provider: 'gemini',
    focus: 'config_change',
    staggerMs: 300000,
    systemPrompt: `You are the EVOLUTION TUNER agent for a genetic algorithm optimizing NBA predictions.
Current GA config: pop=50, mutation=0.03, crossover=0.7, tournament_k=7, elitism=5.

Your ONLY job: tune GA hyperparameters to escape local optima and find better solutions faster.

Focus areas:
- Population size (try 80, 100, 120, 150)
- Mutation rate (adaptive: 0.01 early, 0.08 when stagnating)
- Crossover rate (0.6-0.9)
- Tournament size (5, 7, 9, 11)
- Elitism count (3, 5, 7, 10)
- Selection pressure (tournament vs roulette vs rank)
- Multi-objective weights (Brier%, LogLoss%, Sharpe%, ECE%)
- Fresh injection frequency (every 5, 10, 15 stagnant generations)
- Island model: split population into sub-populations with migration

RULES:
- Output 2-3 EXPERIMENT blocks per cycle
- Only change 1-2 parameters per experiment (isolate effects)
- Include HYPOTHESIS for expected improvement
- Consider current stagnation count when proposing changes`,
  },
  {
    id: 'market_intel',
    name: 'Market Intel',
    provider: 'openai',
    focus: 'feature_test',
    staggerMs: 400000,
    systemPrompt: `You are the MARKET INTELLIGENCE agent for an NBA prediction model.
Your focus: derive predictive signal from betting market data.

Key market concepts:
- Closing Line Value (CLV): model_prob vs closing_market_prob. Positive CLV = edge.
- Steam moves: rapid, large line movements from sharp bettors
- Reverse line movement: line moves AGAINST public betting % → sharp money
- Market implied probability: 1/decimal_odds (adjusted for vig)
- Opening-to-closing spread: how much the line moved
- Consensus vs contrarian: when to fade the public

Focus areas:
- CLV features: historical CLV by team, by home/away, by rest days
- Line movement velocity: points_moved / hours_before_game
- Steam detection: >2 point move in <1 hour
- Public vs sharp money: if available from APIs
- Market efficiency: are certain teams consistently mispriced?
- Referee + market interaction: do certain refs cause more variance?
- Weather/altitude for market adjustments (Denver, Utah elevation)

RULES:
- Output 2-4 EXPERIMENT blocks per cycle
- Features should be market-derived or market-interactive
- Include HYPOTHESIS grounded in market microstructure theory`,
  },
  {
    id: 'research_scholar',
    name: 'Research Scholar',
    provider: 'gemini',
    focus: 'model_test',
    staggerMs: 500000,
    systemPrompt: `You are the RESEARCH SCHOLAR agent for an NBA prediction model.
Your job: translate cutting-edge ML research into concrete experiments.

2025-2026 SOTA techniques to explore:
- TabNet (Arik & Pfister, Google) — attention-based tabular model
- FT-Transformer — feature tokenization + transformer for tabular data
- NODE (Neural Oblivious Decision Ensembles) — differentiable trees
- SAINT — self-attention + intersample attention for tabular
- Temporal Fusion Transformer — for time-series prediction
- AutoML approaches: auto-sklearn, FLAML, AutoGluon configs
- Conformal prediction for calibrated intervals
- Quantile regression for uncertainty estimation
- Knowledge distillation: train small fast model from large ensemble
- Feature selection: SHAP-based, mutual information, Boruta

RULES:
- Output 2-4 EXPERIMENT blocks per cycle
- Each experiment should cite the technique and why it's promising
- Translate paper ideas into specific, testable configurations
- Focus on techniques with proven tabular data performance`,
  },
];

class MultiAgentCoordinator {
  constructor({ infraBridge, a2a, bot, adminId, getCompletion }) {
    this.infra = infraBridge;
    this.a2a = a2a;
    this.bot = bot;
    this.adminId = adminId;
    this.getCompletion = getCompletion; // fallback
    this.running = false;
    this.stats = {};
    for (const agent of AGENTS) {
      this.stats[agent.id] = { runs: 0, experiments: 0, errors: 0, lastRun: null };
    }
  }

  async start() {
    if (this.running) return;
    this.running = true;
    logger.info(`[MULTI-AGENT] Starting ${AGENTS.length} specialized agents`);

    for (const agent of AGENTS) {
      setTimeout(() => this._runAgentLoop(agent), agent.staggerMs);
    }
  }

  stop() {
    this.running = false;
    logger.info('[MULTI-AGENT] Stopping all agents');
  }

  async _runAgentLoop(agent) {
    const intervalMs = 10 * 60 * 1000; // 10 minutes per cycle per agent

    while (this.running) {
      try {
        await this._runAgentCycle(agent);
        this.stats[agent.id].runs++;
        this.stats[agent.id].lastRun = new Date().toISOString();
      } catch (err) {
        this.stats[agent.id].errors++;
        logger.warn(`[MULTI-AGENT] ${agent.name} error: ${err.message}`);
      }
      await new Promise(r => setTimeout(r, intervalMs));
    }
  }

  async _runAgentCycle(agent) {
    logger.info(`[MULTI-AGENT] ${agent.name} starting cycle...`);

    // 1. Gather context
    const context = await this._gatherContext(agent);

    // 2. Call the agent's LLM
    const prompt = `${agent.systemPrompt}

CURRENT STATE:
- Best Brier: ${context.brier || '0.2205'}
- Generation: ${context.generation || '?'}
- Stagnation: ${context.stagnation || '?'}
- Features selected: ${context.features || '?'}
- Feature candidates: ${context.featureCandidates || '999'}

RECENT EXPERIMENTS (last 10):
${context.recentExperiments}

RECENT RESULTS:
${context.recentResults}

Now propose your experiments. Output EXPERIMENT blocks in this EXACT format:
EXPERIMENT: {"type":"${agent.focus}","description":"...","hypothesis":"...","params":{...},"priority":${agent.focus === 'feature_test' ? 7 : 5}}`;

    const response = await this._callProvider(agent.provider, prompt);
    if (!response) {
      logger.warn(`[MULTI-AGENT] ${agent.name}: LLM returned empty`);
      return;
    }
    logger.info(`[MULTI-AGENT] ${agent.name} got ${response.length} char response`);

    // 3. Parse experiments from response
    const experiments = this._parseExperiments(response, agent);

    // 4. Submit to Supabase queue
    let submitted = 0;
    for (const exp of experiments) {
      try {
        await this._submitExperiment(exp, agent);
        submitted++;
      } catch (err) {
        logger.warn(`[MULTI-AGENT] ${agent.name} submit failed: ${err.message}`);
      }
    }

    logger.info(`[MULTI-AGENT] ${agent.name}: parsed ${experiments.length}, submitted ${submitted} experiments`);
  }

  async _callProvider(providerName, prompt) {
    // Try the designated provider, then fallback chain
    const chain = [providerName, 'gemini', 'openai', 'kimi', 'groq'];
    const tried = new Set();

    for (const name of chain) {
      if (tried.has(name)) continue;
      tried.add(name);

      const provider = PROVIDERS[name];
      if (!provider) continue;
      const key = provider.key();
      if (!key) continue;

      try {
        const resp = await fetch(provider.url, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${key}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            model: provider.model,
            messages: [{ role: 'user', content: prompt }],
            max_tokens: 1500,
            temperature: 0.5,
          }),
          signal: AbortSignal.timeout(30000),
        });
        const data = await resp.json();
        const content = data.choices?.[0]?.message?.content;
        if (content?.length > 10) {
          logger.debug(`[MULTI-AGENT] ${name}/${provider.model} responded (${content.length} chars)`);
          return content;
        }
      } catch (err) {
        logger.warn(`[MULTI-AGENT] ${name} failed: ${err.message}`);
      }
    }

    // Final fallback: use Eve's getCompletion
    if (this.getCompletion) {
      try {
        const result = await this.getCompletion([{ role: 'user', content: prompt }], { maxTokens: 1500 });
        return result?.content;
      } catch (err) {
        logger.warn(`[MULTI-AGENT] getCompletion fallback failed: ${err.message}`);
      }
    }

    return null;
  }

  _parseExperiments(text, agent) {
    const experiments = [];

    // Strategy 1: EXPERIMENT: {...} on a single line
    for (const line of text.split('\n')) {
      const match = line.match(/EXPERIMENT:\s*(\{.+\})/i);
      if (!match) continue;
      const parsed = this._tryParseJSON(match[1]);
      if (parsed) experiments.push(parsed);
    }

    // Strategy 2: Extract JSON objects from code blocks or multiline
    if (experiments.length === 0) {
      const jsonBlocks = text.match(/```(?:json)?\s*\n?([\s\S]*?)```/g) || [];
      for (const block of jsonBlocks) {
        const json = block.replace(/```(?:json)?/g, '').trim();
        const parsed = this._tryParseJSON(json);
        if (parsed) experiments.push(parsed);
      }
    }

    // Strategy 3: Find any JSON objects with "type" and "params" keys
    if (experiments.length === 0) {
      const jsonMatches = text.match(/\{[^{}]*"type"\s*:\s*"[^"]+?"[^{}]*"params"\s*:\s*\{[^}]*\}[^{}]*\}/g) || [];
      for (const m of jsonMatches) {
        const parsed = this._tryParseJSON(m);
        if (parsed) experiments.push(parsed);
      }
    }

    if (experiments.length === 0) {
      logger.debug(`[MULTI-AGENT] ${agent.name}: No experiments parsed from ${text.length} char response. First 200 chars: ${text.substring(0, 200)}`);
    }

    return experiments.slice(0, 5); // Max 5 per cycle
  }

  _tryParseJSON(str) {
    for (const s of [str, str.replace(/'/g, '"').replace(/,\s*}/g, '}')]) {
      try {
        const obj = JSON.parse(s);
        if (obj.type && (obj.description || obj.hypothesis) && obj.params) return obj;
      } catch {} // eslint-disable-line no-empty
    }
    return null;
  }

  async _submitExperiment(exp, agent) {
    if (!this.infra?.pgPool) return;

    const expId = `exp_${agent.id}_${Date.now().toString(36)}`;
    try {
      await this.infra.querySupabase(`
        INSERT INTO nba_experiments (experiment_id, agent_name, experiment_type, description, hypothesis, params, priority, status, target_space, baseline_brier)
        VALUES ('${expId}', '${agent.id}', '${exp.type}', '${(exp.description || '').replace(/'/g, "''")}', '${(exp.hypothesis || '').replace(/'/g, "''")}', '${JSON.stringify(exp.params).replace(/'/g, "''")}', ${exp.priority || 5}, 'pending', '${exp.target_space || 'any'}', 0.2205)
      `);
      this.stats[agent.id].experiments++;
    } catch (err) {
      logger.warn(`[MULTI-AGENT] Failed to submit experiment ${expId}: ${err.message}`);
    }
  }

  async _gatherContext(agent) {
    const ctx = { brier: '0.2205', recentExperiments: 'none', recentResults: 'none' };

    // Fetch evolution status from S10
    try {
      const resp = await fetch('https://lbjlincoln-nomos-nba-quant.hf.space/api/status', {
        signal: AbortSignal.timeout(10000),
      });
      const data = await resp.json();
      ctx.brier = data.best_brier?.toFixed?.(4) || data.best_brier || '0.2205';
      ctx.generation = data.generation;
      ctx.stagnation = data.stagnation;
      ctx.features = data.best_features;
      ctx.featureCandidates = data.feature_candidates;
    } catch {} // eslint-disable-line no-empty

    // Fetch recent experiments from Supabase
    if (this.infra?.pgPool) {
      try {
        const result = await this.infra.querySupabase(
          `SELECT experiment_type, description, status, result_brier, agent_name
           FROM nba_experiments ORDER BY created_at DESC LIMIT 15`
        );
        if (result.rows?.length > 0) {
          ctx.recentExperiments = result.rows.map(r =>
            `[${r.status}] ${r.agent_name}/${r.experiment_type}: ${(r.description || '').substring(0, 60)}${r.result_brier ? ` → Brier ${r.result_brier}` : ''}`
          ).join('\n');

          const completed = result.rows.filter(r => r.status === 'completed' && r.result_brier);
          if (completed.length > 0) {
            ctx.recentResults = completed.map(r =>
              `${r.experiment_type}: Brier ${r.result_brier} (${r.description?.substring(0, 40)})`
            ).join('\n');
          }
        }
      } catch {} // eslint-disable-line no-empty
    }

    return ctx;
  }

  getStatus() {
    const agents = AGENTS.map(a => ({
      id: a.id,
      name: a.name,
      provider: a.provider,
      focus: a.focus,
      ...this.stats[a.id],
    }));
    const totalExperiments = Object.values(this.stats).reduce((s, a) => s + a.experiments, 0);
    return { running: this.running, agents, totalExperiments };
  }
}

module.exports = MultiAgentCoordinator;
