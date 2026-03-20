/**
 * Multi-Agent Coordinator — 6 Specialized AI Agents Working in Parallel
 *
 * TURBO MODE: 3-minute cycles, 8 experiments per agent, 6000+ feature space
 *
 * Agents:
 *   1. Feature Scout    (Gemini)   — 6000+ feature combinations, interaction terms
 *   2. Model Architect  (OpenAI)   — 1000+ model architectures & hyperparams
 *   3. Calibrator       (Kimi)     — Calibration, Platt scaling, isotonic, beta
 *   4. Evolution Tuner  (Gemini)   — GA params, population, selection, crossover
 *   5. Market Intel     (OpenAI)   — Odds, CLV, steam, market microstructure
 *   6. Research Scholar  (Gemini)  — 2026 papers, SOTA techniques, novel approaches
 *
 * Each agent runs every 3 minutes (staggered by 30s).
 * Output: EXPERIMENT blocks → Supabase queue → S11/Kaggle/Colab → auto-promoted.
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
  // GPT-5 Codex — the BEST coding model from OpenAI (for Phase 2 code generation)
  codex: {
    url: 'https://api.openai.com/v1/chat/completions',
    key: () => process.env.OPENAI_API_KEY,
    model: 'gpt-5.1-codex-mini',
  },
  // o3 — OpenAI reasoning model (for complex architecture decisions)
  o3: {
    url: 'https://api.openai.com/v1/chat/completions',
    key: () => process.env.OPENAI_API_KEY,
    model: 'o3-mini',
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
    systemPrompt: `You are the FEATURE SCOUT for an elite NBA prediction model (current Brier ~0.22, target < 0.20).
Your ONLY job: propose NEW feature combinations to test. Be CREATIVE and SPECIFIC.

## FEATURE UNIVERSE (6000+ combinations available)

### Base Stats (30 stats × 8 windows = 240)
Stats: pts, fg_pct, fg3_pct, ft_pct, reb, ast, stl, blk, tov, pf, plus_minus, pace, ortg, drtg, net_rtg, efg_pct, ts_pct, ast_ratio, tov_pct, orb_pct, drb_pct, ftr, opp_efg, opp_tov, opp_orb, opp_ftr, pitp, fbps, potov
Windows: 3, 5, 7, 10, 15, 20, 30, season

### Interaction Terms (240 × 240 = 57600 pairs, top combos)
- Offense × Defense: efg_pct_5g * opp_drtg_5g, pace_10g * opp_pace_10g
- Rest × Performance: rest_days * pts_5g, b2b_flag * margin_10g
- Travel × Fatigue: travel_miles_7d * rest_days, timezone_changes * win_pct_5g
- Momentum × Context: streak_len * playoff_implications, hot_streak * revenge_game
- Market × Stats: clv * win_pct_10g, line_movement * margin_5g

### Advanced Categories
1. **Four Factors** (32): eFG%, TOV%, ORB%, FTR × windows × home/away
2. **Pace-Adjusted** (60): per-100-possessions stats, possession counts
3. **Opponent-Adjusted** (120): each stat vs opp's league rank/percentile
4. **Schedule** (40): rest_days, b2b, b2b_away, travel_miles, timezone, altitude, games_last_7d/14d/21d
5. **Referee** (50): ref_foul_rate, ref_home_bias, ref_over_rate, ref_tech_rate per ref crew
6. **Player Impact** (80): star_minutes_pct, injury_impact_score, lineup_net_rtg, bench_production
7. **Momentum** (60): streak_len, weighted_wins, hot_cold_5g, margin_trend, consistency_std
8. **Market** (100): spread, total, moneyline, CLV, steam, reverse_line, sharp_money_pct, market_width, line_freeze, pinnacle_vs_market
9. **Clutch** (40): q4_margin_5g, close_game_win_pct, garbage_time_adj, clutch_net_rtg
10. **Matchup** (80): h2h_record, style_matchup, pace_diff, size_mismatch, defensive_scheme_vs_offense
11. **Situational** (60): revenge_game, division_rival, playoff_race, elimination, conference_rank
12. **Season Phase** (30): early_season_flag, pre_allstar, post_allstar, last_10_games, back_stretch
13. **Venue** (25): altitude, home_court_adv, arena_size, crowd_factor
14. **Derived** (100): rolling_z_scores, percentile_ranks, ema_weighted, bayesian_priors, rate_of_change
15. **Polymarket** (40): implied_prob, market_confidence, sharp_vs_public, odds_history_slope

TOTAL: 6000+ unique feature combinations available.

RULES:
- Output 5-8 EXPERIMENT blocks per cycle. BE AGGRESSIVE.
- Each experiment tests 3-8 related features
- Include HYPOTHESIS for why this improves Brier
- Be SPECIFIC: use snake_case names matching categories above
- NEVER repeat features from RECENT EXPERIMENTS
- Prioritize interaction terms and opponent-adjusted — highest signal`,
  },
  {
    id: 'model_architect',
    name: 'Model Architect',
    provider: 'openai',
    focus: 'model_test',
    staggerMs: 30000,
    systemPrompt: `You are the MODEL ARCHITECT for an elite NBA prediction system.
Current best: Brier 0.2198 with XGBoost ensemble. Target: Brier < 0.20.

## MODEL UNIVERSE (1000+ configurations)

### Gradient Boosting (400+ configs)
**XGBoost**: max_depth=[4,6,8,10,12], lr=[0.005,0.01,0.02,0.05,0.1], n_estimators=[200,500,800,1000,1500,2000], subsample=[0.6,0.7,0.8,0.9], colsample_bytree=[0.5,0.6,0.7,0.8,0.9], reg_alpha=[0,0.01,0.1,1], reg_lambda=[1,2,5,10], booster=[gbtree,dart], min_child_weight=[1,3,5,7], gamma=[0,0.1,0.5,1]
**LightGBM**: num_leaves=[31,63,127,255], lr=[0.005,0.01,0.02,0.05], n_estimators=[300,500,1000,2000], min_data_in_leaf=[10,20,50,100], feature_fraction=[0.5,0.7,0.8,0.9], bagging_fraction=[0.6,0.7,0.8,0.9], lambda_l1=[0,0.1,1], lambda_l2=[0,0.1,1], boosting=[gbdt,dart,goss]
**CatBoost**: depth=[4,6,8,10], lr=[0.01,0.03,0.05,0.1], iterations=[500,1000,2000], l2_leaf_reg=[1,3,5,9], border_count=[32,64,128,254], boosting_type=[Ordered,Plain], grow_policy=[SymmetricTree,Depthwise,Lossguide]

### Neural Networks (300+ configs)
**MLP**: layers=[[128,64],[256,128],[512,256,128],[1024,512,256,128],[256,128,64,32]], dropout=[0.1,0.2,0.3,0.4,0.5], activation=[relu,gelu,silu,mish], batch_norm=[true,false], lr=[0.0001,0.0005,0.001,0.003], weight_decay=[0,1e-5,1e-4,1e-3], batch_size=[64,128,256,512]
**ResNet-style MLP**: residual blocks, skip connections, pre-norm vs post-norm
**LSTM**: hidden=[64,128,256], layers=[1,2,3], sequence_len=[5,10,15,20], bidirectional=[true,false]
**TabNet**: n_d=[8,16,32,64], n_a=[8,16,32,64], n_steps=[3,5,7,10], relaxation=[1.0,1.5,2.0], mask_type=[sparsemax,entmax]
**FT-Transformer**: n_blocks=[2,3,4,6], d_token=[64,128,192,256], n_heads=[4,8], ffn_d_hidden=[256,512], attention_dropout=[0.1,0.2]
**NODE**: num_layers=[2,4,6,8], num_trees=[512,1024,2048], depth=[4,6,8], choice_function=[entmax,sparsemax]

### Ensemble Methods (200+ configs)
**Stacking**: meta=[lr,xgb,mlp], base_models=[xgb+lgbm, xgb+lgbm+rf, xgb+lgbm+catboost+mlp, all_5]
**Blending**: weight optimization via Nelder-Mead, Bayesian, or differential evolution
**Snapshot Ensemble**: save models at different epochs, average predictions
**Multi-seed**: train same model with 5-10 seeds, average outputs
**Cascading**: confidence-based routing (high-confidence → simple model, uncertain → complex)

### Advanced (100+ configs)
**MC Dropout**: enable dropout at inference, average N forward passes for uncertainty
**Bayesian NN**: variational inference, posterior estimation
**Knowledge Distillation**: large ensemble teacher → small fast student
**Quantile Regression**: predict confidence intervals, use width as feature
**Conformal Prediction**: calibrated prediction sets

RULES:
- Output 5-8 EXPERIMENT blocks per cycle. BE AGGRESSIVE.
- Include EXACT hyperparameters in params JSON
- model_type: xgboost, lightgbm, catboost, rf, mlp, tabnet, ft_transformer, lstm, node, stacking
- For NNs: specify hidden_layers, dropout, lr, epochs, batch_size
- NEVER repeat configs from RECENT EXPERIMENTS
- Test EXTREME configs too — sometimes they work`,
  },
  {
    id: 'calibrator',
    name: 'Calibrator',
    provider: 'kimi',
    focus: 'calibration_test',
    staggerMs: 60000,
    systemPrompt: `You are the CALIBRATION SPECIALIST for an elite NBA prediction model.
Goal: predicted probabilities MUST match actual win rates. Brier = calibration + resolution.

## CALIBRATION METHODS (100+ configs)

### Post-hoc Calibration
- **Platt Scaling**: sigmoid fit on logits. params: regularization C=[0.01,0.1,1,10]
- **Temperature Scaling**: divide logits by T. T=[0.5,0.7,0.9,1.0,1.1,1.3,1.5,2.0]
- **Isotonic Regression**: non-parametric monotonic fit. out_of_fold=[true,false]
- **Beta Calibration**: 2-param generalization of Platt. a,b params
- **Venn-Abers**: distribution-free calibration with validity guarantees
- **Histogram Binning**: n_bins=[10,15,20,30,50], strategy=[uniform,quantile]
- **BBQ (Bayesian Binning Quantiles)**: Bayesian approach to histogram binning
- **ECES Minimization**: directly minimize Expected Calibration Error
- **Spline Calibration**: cubic spline fit, knots=[5,10,15]
- **Ensemble Calibration**: average/stack multiple calibration methods

### Training-time Calibration
- **Brier Loss**: train directly on Brier score instead of log-loss
- **Focal Loss**: gamma=[0.5,1,2,3,5] — down-weight easy examples
- **Label Smoothing**: alpha=[0.01,0.05,0.1] — prevent overconfident predictions
- **Mixup**: alpha=[0.1,0.2,0.4] — interpolate training examples
- **Confidence Penalty**: add penalty for predictions far from 0.5

### Advanced
- **Recalibration on subgroups**: calibrate separately for home/away, rest, B2B
- **Time-decay calibration**: more weight to recent games
- **Conformal Prediction**: distribution-free uncertainty, coverage=[0.8,0.9,0.95]
- **SmartCal** (2026): adaptive bin selection, proven Brier 0.199 on NBA
- **Multi-output**: predict win prob + total + spread simultaneously for regularization

RULES:
- Output 5-8 EXPERIMENT blocks per cycle. BE AGGRESSIVE.
- Specify calibration_method + all hyperparameters
- cv_folds: 5 or 10
- HYPOTHESIS: which calibration failure mode does this fix?
- Try COMBINATIONS: e.g., Platt + isotonic ensemble, focal_loss + temperature`,
  },
  {
    id: 'evolution_tuner',
    name: 'Evolution Tuner',
    provider: 'gemini',
    focus: 'config_change',
    staggerMs: 90000,
    systemPrompt: `You are the EVOLUTION TUNER for the genetic algorithm optimizing NBA predictions.
Current GA: pop=50, mutation=0.03, crossover=0.7, tournament_k=7, elitism=5.

## GA PARAMETER SPACE (200+ configs)

### Population & Selection
- Population: [30,50,80,100,120,150,200]
- Tournament k: [3,5,7,9,11,15]
- Selection: tournament, roulette_wheel, rank, sus (stochastic universal), truncation, boltzmann
- Elitism: [2,3,5,7,10,15]
- Selection pressure: linear_rank_bias=[1.2,1.5,1.8,2.0]

### Crossover
- Rate: [0.5,0.6,0.7,0.8,0.9]
- Type: single_point, two_point, uniform, blend_alpha, simulated_binary
- Blend alpha: [0.3,0.5,0.7] (for BLX-alpha crossover)

### Mutation
- Base rate: [0.01,0.02,0.03,0.05,0.08,0.1]
- Adaptive: increase mutation when stagnating (1.5x, 2x, 3x per stagnant gen)
- Type: gaussian, uniform, polynomial, non_uniform
- Mutation decay: [none, linear_decay, cosine_decay]
- Hypermutation: burst of 5x mutation every N gens, then cool down

### Advanced Strategies
- **Island Model**: 3-5 sub-populations, migrate best every N gens
- **CMA-ES**: covariance matrix adaptation for continuous params
- **Differential Evolution**: mutation via difference vectors, F=[0.5,0.8,1.0], CR=[0.3,0.7,0.9]
- **NSGA-II**: Pareto-optimal multi-objective (Brier, ROI, Sharpe, ECE)
- **Age-based replacement**: remove oldest individuals, not worst
- **Speciation**: niching to maintain diversity (like NEAT)
- **Fresh injection**: inject N random individuals every [5,10,15] stagnant gens
- **Archive**: keep hall-of-fame, inject past champions when stagnating

### Fitness Function
- Brier weight: [0.3,0.4,0.5,0.6]
- ROI weight: [0.1,0.15,0.2,0.25,0.3]
- Sharpe weight: [0.1,0.15,0.2,0.25]
- Calibration weight: [0.05,0.1,0.15,0.2]
- LogLoss weight: [0,0.05,0.1,0.15]

RULES:
- Output 5-8 EXPERIMENT blocks per cycle. BE AGGRESSIVE.
- Change 1-3 parameters per experiment (isolate effects)
- HYPOTHESIS: why this escapes current local optimum
- Consider current stagnation and generation count
- Try RADICAL changes too — sometimes disruption helps`,
  },
  {
    id: 'market_intel',
    name: 'Market Intel',
    provider: 'openai',
    focus: 'feature_test',
    staggerMs: 120000,
    systemPrompt: `You are the MARKET INTELLIGENCE agent for an elite NBA prediction model.
Your focus: extract maximum predictive signal from betting market data.

## MARKET FEATURE UNIVERSE (500+ features)

### Core Market Features
- spread_home, spread_away, total_over, total_under, moneyline_home, moneyline_away
- implied_prob_home, implied_prob_away (vig-adjusted)
- market_margin (total vig), best_available_odds

### Line Movement (100+ features)
- opening_spread, closing_spread, spread_movement, movement_direction
- line_velocity (pts/hour), movement_acceleration
- movement_timing (early_sharp vs late_public)
- reverse_line_move_flag, steam_move_flag, freeze_flag
- pinnacle_line vs consensus_line (Pinnacle = sharpest book)
- line_at_T_minus_[1h,2h,4h,8h,24h,48h] (time-series of line)

### Sharp vs Public
- public_betting_pct_home, sharp_money_pct_home
- contrarian_value (when sharp≠public)
- ticket_count vs dollar_volume (dollars = sharp, tickets = public)
- wiseguy_count (number of sharp bettors on one side)

### CLV & Historical (100+ features)
- team_clv_avg_10g, team_clv_avg_season (by team)
- home_clv_avg, away_clv_avg (by venue)
- rest_clv_interaction (CLV when rested vs B2B)
- ref_clv_interaction (CLV by referee crew)
- model_edge = model_prob - market_implied_prob

### Market Efficiency (100+ features)
- team_market_bias (consistently over/undervalued?)
- situation_bias (market undervalues B2B? overvalues home?)
- total_movement vs actual_total (market accuracy on totals)
- spread_error_by_rest, spread_error_by_travel
- market_confidence = 1 / market_width (tight spread = confident)
- books_disagreement_score (how much books differ)

### Polymarket & Exchange
- polymarket_prob, polymarket_volume, polymarket_trend
- betfair_price, betfair_volume, betfair_movement
- exchange_vs_book_delta (exchange more efficient)

### Derived Market
- market_implied_pace, market_implied_margin
- total_line_derivative (how fast total moves)
- spread_total_correlation (unusual combos = signal)
- moneyline_spread_discrepancy (when they disagree)

RULES:
- Output 5-8 EXPERIMENT blocks per cycle. BE AGGRESSIVE.
- Features must be market-derived or market-interaction
- HYPOTHESIS grounded in market microstructure theory
- Combine market features with non-market features for interaction terms
- Think like a sports quant at Pinnacle or Starlizard`,
  },
  {
    id: 'research_scholar',
    name: 'Research Scholar',
    provider: 'gemini',
    focus: 'model_test',
    staggerMs: 150000,
    systemPrompt: `You are the RESEARCH SCHOLAR for an elite NBA prediction model.
Translate cutting-edge 2025-2026 ML research into concrete, testable experiments.

## RESEARCH PAPERS & TECHNIQUES TO EXPLORE

### Tabular SOTA (2025-2026)
- **FT-Transformer** (Gorishniy 2021→2025 improvements): feature tokenization + self-attention
- **TabNet** (Arik & Pfister, Google): attention-based, interpretable
- **NODE** (Popov 2019→2025): neural oblivious decision ensembles
- **SAINT** (Somepalli 2021→2025): self-attention + intersample attention
- **TabPFN** (2023-2025): prior-data fitted network, zero-shot tabular
- **Temporal Fusion Transformer** (Lim 2021→2026): for time-series tabular
- **XTab** (2023): cross-table pretraining for tabular transformers
- **GRANDE** (2024): gradient-based decision tree ensemble
- **HyperTab** (2024): hypernetwork for tabular, few-shot learning
- **ModernNCA** (2025): nearest centroid attention for tabular

### Sports Prediction SOTA (2025-2026)
- **MC Dropout RNN** (2026): Brier 0.199 on NBA with uncertainty estimation
- **Long-Sequence LSTM** (2026): 72.35% accuracy on NBA, 20-game sequences
- **SmartCal** (2026): adaptive calibration, proven on NBA data
- **Pi-ratings** (2025): dynamic team strength ratings, better than ELO
- **Bradley-Terry temporal** (2025): time-varying team ability model
- **Bayesian ELO** (2025): uncertainty-aware ELO with posterior
- **Graph Neural Networks** for player interaction modeling
- **Attention-based player embeddings**: learn player compatibility

### Training Techniques
- **Brier Score as direct loss function** (instead of log-loss)
- **Focal Loss** (Lin 2017→2025): handle class imbalance, down-weight easy
- **Mixup / CutMix for tabular**: data augmentation
- **Self-supervised pretraining**: mask features, predict them, then fine-tune
- **Contrastive learning** for tabular: SCARF, SubTab
- **Feature interaction networks**: explicit polynomial feature learning

### Ensemble & Meta-Learning
- **Snapshot Ensembles**: save model at different training epochs
- **Stochastic Weight Averaging (SWA)**: average weights for better generalization
- **Fast Geometric Ensembles (FGE)**: explore loss landscape modes
- **Knowledge Distillation**: large teacher → small student
- **Neural Architecture Search (NAS)**: automate NN design
- **AutoML**: AutoGluon, FLAML, auto-sklearn configs

### Uncertainty & Calibration
- **Conformal Prediction**: distribution-free prediction intervals
- **Evidential Deep Learning**: Dirichlet-based uncertainty
- **MC Dropout**: approximate Bayesian inference
- **Deep Ensembles**: N independently trained models
- **Heteroscedastic regression**: predict mean AND variance

RULES:
- Output 5-8 EXPERIMENT blocks per cycle. BE AGGRESSIVE.
- CITE the technique/paper for each experiment
- Translate paper ideas into EXACT model configs + hyperparameters
- model_type: xgboost, lightgbm, catboost, rf, mlp, tabnet, ft_transformer, lstm, node, stacking
- Focus on techniques with proven tabular/sports performance
- Try bold, unconventional combos — innovation wins`,
  },
];

class MultiAgentCoordinator {
  constructor({ infraBridge, a2a, bot, adminId, getCompletion, codeAgent }) {
    this.infra = infraBridge;
    this.a2a = a2a;
    this.bot = bot;
    this.adminId = adminId;
    this.getCompletion = getCompletion; // fallback
    this.codeAgent = codeAgent; // CodeAgent instance for writing code to GitHub
    this.running = false;
    this.kaggleLastTrigger = 0;
    this.codeCommits = 0;
    this.stats = {};
    for (const agent of AGENTS) {
      this.stats[agent.id] = { runs: 0, experiments: 0, errors: 0, codeWrites: 0, lastRun: null };
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
    const intervalMs = 3 * 60 * 1000; // 3 minutes per cycle — TURBO MODE

    while (this.running) {
      try {
        await this._runAgentCycle(agent);
        this.stats[agent.id].runs++;
        this.stats[agent.id].lastRun = new Date().toISOString();

        // After submitting experiments, auto-trigger Kaggle if GPU work pending
        await this.triggerKaggleGPU().catch(() => {});
      } catch (err) {
        this.stats[agent.id].errors++;
        logger.warn(`[MULTI-AGENT] ${agent.name} error: ${err.message}`);
      }
      await new Promise(r => setTimeout(r, intervalMs));
    }
  }

  async _runAgentCycle(agent) {
    logger.info(`[MULTI-AGENT] ${agent.name} starting cycle...`);

    // 1. Gather context (including current code snippets)
    const context = await this._gatherContext(agent);

    const stateBlock = `CURRENT STATE:
- Best Brier: ${context.brier || '0.2205'}
- Generation: ${context.generation || '?'}
- Stagnation: ${context.stagnation || '?'}
- Features selected: ${context.features || '?'}
- Feature candidates: ${context.featureCandidates || '2058'}

RECENT EXPERIMENTS (last 30):
${context.recentExperiments}

RECENT RESULTS:
${context.recentResults}`;

    // ── PHASE 1: Propose experiments ──
    const expPrompt = `${agent.systemPrompt}\n\n${stateBlock}\n\nNow propose your experiments. Output EXPERIMENT blocks in this EXACT format:
EXPERIMENT: {"type":"${agent.focus}","description":"...","hypothesis":"...","params":{...},"priority":${agent.focus === 'feature_test' ? 7 : 5}}`;

    const expResponse = await this._callProvider(agent.provider, expPrompt);
    if (!expResponse) {
      logger.warn(`[MULTI-AGENT] ${agent.name}: LLM returned empty`);
      return;
    }

    const experiments = this._parseExperiments(expResponse, agent);
    let submitted = 0;
    for (const exp of experiments) {
      try {
        await this._submitExperiment(exp, agent);
        submitted++;
      } catch (err) {
        logger.warn(`[MULTI-AGENT] ${agent.name} submit failed: ${err.message}`);
      }
    }
    logger.info(`[MULTI-AGENT] ${agent.name}: ${experiments.length} experiments, ${submitted} submitted`);

    // ── PHASE 2: Write actual code (SEPARATE LLM call) ──
    let codeWrites = 0;
    if (!this.codeAgent) {
      logger.warn(`[MULTI-AGENT] ${agent.name}: NO codeAgent available — skipping code generation`);
    } else if (experiments.length === 0) {
      logger.debug(`[MULTI-AGENT] ${agent.name}: no experiments, skipping code gen`);
    } else {
      logger.info(`[MULTI-AGENT] ${agent.name}: PHASE 2 — generating code for top experiment...`);
      try {
        codeWrites = await this._writeCodeForExperiments(agent, experiments, context);
        logger.info(`[MULTI-AGENT] ${agent.name}: PHASE 2 result: ${codeWrites} code writes`);
      } catch (err) {
        logger.error(`[MULTI-AGENT] ${agent.name} PHASE 2 ERROR: ${err.message}\n${err.stack?.substring(0, 300)}`);
      }
    }

    logger.info(`[MULTI-AGENT] ${agent.name} DONE: ${submitted} experiments, ${codeWrites} code writes`);
  }

  /**
   * PHASE 2: Ask LLM to write actual Python code implementing the top experiment.
   * This is a SEPARATE call from experiment proposal — dedicated to code generation.
   */
  async _writeCodeForExperiments(agent, experiments, context) {
    const CODE_TARGETS = {
      feature_scout: { repo: 'nomos-nba-agent', file: 'features/engine.py', what: 'new feature computation functions' },
      model_architect: { repo: 'nomos-nba-agent', file: 'kaggle/nba_gpu_runner.py', what: 'new model class or training function' },
      calibrator: { repo: 'nomos-nba-agent', file: 'kaggle/nba_gpu_runner.py', what: 'new calibration method or loss function' },
      evolution_tuner: { repo: 'nomos-nba-agent', file: 'hf-space/app.py', what: 'new selection/mutation operator or GA config' },
      market_intel: { repo: 'nomos-nba-agent', file: 'features/engine.py', what: 'new market-derived feature functions' },
      research_scholar: { repo: 'nomos-nba-agent', file: 'kaggle/nba_gpu_runner.py', what: 'implementation of research paper technique' },
    };

    const target = CODE_TARGETS[agent.id];
    if (!target) return 0;

    // Pick the top experiment to implement
    const topExp = experiments[0];

    const codePrompt = `You are an expert Python developer. Write PRODUCTION-READY code to implement this improvement for an NBA prediction model.

IMPROVEMENT TO IMPLEMENT:
- Type: ${topExp.type}
- Description: ${topExp.description || 'See params'}
- Hypothesis: ${topExp.hypothesis || 'N/A'}
- Params: ${JSON.stringify(topExp.params)}

TARGET FILE: ${target.repo}/${target.file}
WHAT TO WRITE: ${target.what}

${context.currentCode ? `CURRENT END OF FILE:\n\`\`\`python\n${context.currentCode}\n\`\`\`\n` : ''}

CRITICAL RULES:
1. Output ONLY the Python code to APPEND to the file — not the whole file
2. Code must be syntactically correct and runnable
3. Include all necessary imports at the top of your code block
4. Use proper indentation (4 spaces)
5. Add a comment header with what this implements

Output format — ONLY this, nothing else:
===CODE: ${target.file}===
# Your Python code here
===END===`;

    // Use Gemini for code gen (free, reliable), codex/o3 as fallback when quota available
    const codeProvider = 'gemini';
    const codeResponse = await this._callProvider(codeProvider, codePrompt);
    if (!codeResponse) {
      logger.warn(`[MULTI-AGENT] ${agent.name}: code LLM returned EMPTY — all providers failed`);
      return 0;
    }

    logger.info(`[MULTI-AGENT] ${agent.name} code LLM responded: ${codeResponse.length} chars. First 200: ${codeResponse.substring(0, 200)}`);

    // Parse code blocks
    let codeBlocks = this._parseCodeBlocks(codeResponse);

    // Fallback: if no ===CODE=== blocks, try to extract any Python code block
    if (codeBlocks.length === 0) {
      const pyMatch = codeResponse.match(/```python\n([\s\S]*?)```/);
      if (pyMatch && pyMatch[1].length > 30) {
        codeBlocks = [{ filePath: target.file, code: pyMatch[1].trim() }];
      }
    }

    // Even more fallback: if response is mostly code (no markdown), use it directly
    if (codeBlocks.length === 0) {
      const lines = codeResponse.split('\n');
      const codeLines = lines.filter(l => l.match(/^(import |from |def |class |#|    |\s*$)/));
      if (codeLines.length > lines.length * 0.6 && codeResponse.length > 50) {
        codeBlocks = [{ filePath: target.file, code: codeResponse.trim() }];
      }
    }

    logger.info(`[MULTI-AGENT] ${agent.name}: parsed ${codeBlocks.length} code blocks from response`);
    if (codeBlocks.length === 0) {
      logger.warn(`[MULTI-AGENT] ${agent.name}: NO code blocks found. Response preview: ${codeResponse.substring(0, 300)}`);
    }

    let writes = 0;
    for (const block of codeBlocks.slice(0, 1)) { // Max 1 code write per cycle per agent
      try {
        await this._applyCodeBlock(block, agent);
        writes++;
        this.stats[agent.id].codeWrites++;
        this.codeCommits++;
      } catch (err) {
        logger.warn(`[MULTI-AGENT] ${agent.name} code write failed: ${err.message}`);
      }
    }
    return writes;
  }

  /**
   * Parse ===CODE: path/to/file=== ... ===END=== blocks from LLM response
   */
  _parseCodeBlocks(text) {
    const blocks = [];
    const regex = /===CODE:\s*(.+?)===\n([\s\S]*?)===END===/g;
    let match;
    while ((match = regex.exec(text)) !== null) {
      const filePath = match[1].trim();
      const code = match[2].trim();
      if (filePath && code.length > 20) {
        blocks.push({ filePath, code });
      }
    }
    // Also try markdown code blocks with file paths
    if (blocks.length === 0) {
      const mdRegex = /```python\s*\n#\s*(?:File|Path):\s*(.+?)\n([\s\S]*?)```/g;
      while ((match = mdRegex.exec(text)) !== null) {
        const filePath = match[1].trim();
        const code = match[2].trim();
        if (filePath && code.length > 20) {
          blocks.push({ filePath, code });
        }
      }
    }
    return blocks.slice(0, 3); // Max 3 code blocks per cycle
  }

  /**
   * Apply a code block: read current file, append new code, commit via GitHub API
   */
  async _applyCodeBlock(block, agent) {
    if (!this.codeAgent) return;

    // Determine which repo this file belongs to
    let repo = 'nomos-nba-agent';
    if (block.filePath.startsWith('hf-spaces/') || block.filePath.startsWith('scripts/')) {
      repo = 'mon-ipad';
    }

    // Clean up the file path
    let filePath = block.filePath
      .replace(/^\/+/, '')
      .replace(/^nomos-nba-agent\//, '')
      .replace(/^mon-ipad\//, '');

    logger.info(`[MULTI-AGENT] ${agent.name} writing code to ${repo}/${filePath}`);

    // Read current file content
    const currentContent = await this.codeAgent.readFile(repo, filePath);

    let newContent;
    if (currentContent) {
      // Append new code before the last line (or at end)
      // Look for a safe injection point
      const marker = `\n\n### BEGIN ${agent.name} addition (${new Date().toISOString().split('T')[0]}) ###\n`;
      const endMarker = `\n### END ${agent.name} addition ###\n`;
      newContent = currentContent + marker + block.code + endMarker;
    } else {
      // New file
      newContent = block.code;
    }

    // Commit directly to main (agents are autonomous)
    const message = `feat(${agent.id}): ${block.filePath.split('/').pop()} — auto-generated improvement`;
    await this.codeAgent.writeFile(repo, filePath, newContent, message);

    logger.info(`[MULTI-AGENT] ${agent.name} committed code to ${repo}/${filePath}`);

    // Notify via Telegram
    if (this.bot && this.adminId) {
      this.bot.sendMessage(this.adminId,
        `🔧 *${agent.name}* wrote code\n\`${repo}/${filePath}\`\n${block.code.substring(0, 100)}...`,
        { parse_mode: 'Markdown' }
      ).catch(() => {});
    }

    // Auto-review: cross-LLM review of the committed code
    await this._autoReviewCode(agent, filePath, repo).catch(e =>
      logger.warn(`[MULTI-AGENT] Review failed: ${e.message}`));
  }

  async _callProvider(providerName, prompt) {
    // Try the designated provider, then fallback chain
    const chain = [providerName, 'codex', 'gemini', 'openai', 'o3', 'kimi', 'groq'];
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
            max_tokens: 2500,
            temperature: 0.7,
          }),
          signal: AbortSignal.timeout(60000),
        });
        const data = await resp.json();
        if (data.error) {
          logger.warn(`[MULTI-AGENT] ${name}/${provider.model} API error: ${data.error?.message || JSON.stringify(data.error).substring(0, 100)}`);
          continue; // try next provider
        }
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
        const result = await this.getCompletion([{ role: 'user', content: prompt }], { maxTokens: 2500 });
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

    return experiments.slice(0, 8); // Max 8 per cycle — TURBO MODE
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
    const ctx = { brier: '0.2205', recentExperiments: 'none', recentResults: 'none', currentCode: '' };

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
           FROM nba_experiments ORDER BY created_at DESC LIMIT 30`
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

    // Fetch relevant code snippet from GitHub (so agent knows what exists)
    if (this.codeAgent) {
      try {
        const codeFiles = {
          feature_scout: { repo: 'nomos-nba-agent', path: 'features/engine.py', offset: 'last_500' },
          model_architect: { repo: 'nomos-nba-agent', path: 'kaggle/nba_gpu_runner.py', offset: 'models' },
          calibrator: { repo: 'nomos-nba-agent', path: 'kaggle/nba_gpu_runner.py', offset: 'models' },
          evolution_tuner: { repo: 'nomos-nba-agent', path: 'hf-space/app.py', offset: 'ga_config' },
          market_intel: { repo: 'nomos-nba-agent', path: 'features/engine.py', offset: 'market' },
          research_scholar: { repo: 'nomos-nba-agent', path: 'kaggle/nba_gpu_runner.py', offset: 'models' },
        };
        const target = codeFiles[agent.id];
        if (target) {
          const code = await this.codeAgent.readFile(target.repo, target.path);
          if (code) {
            // Give agent the last 2000 chars of the file (most recent additions)
            ctx.currentCode = `# File: ${target.repo}/${target.path} (last 2000 chars)\n` +
              code.substring(Math.max(0, code.length - 2000));
          }
        }
      } catch {} // eslint-disable-line no-empty
    }

    return ctx;
  }

  /**
   * Trigger Kaggle GPU kernel via Kaggle REST API.
   * Pushes the kernel code directly — no browser, no VM SSH needed.
   * Rate-limited to once per 30 minutes.
   */
  async triggerKaggleGPU() {
    const KAGGLE_USERNAME = process.env.KAGGLE_USERNAME;
    const KAGGLE_KEY = process.env.KAGGLE_KEY;
    if (!KAGGLE_USERNAME || !KAGGLE_KEY) {
      logger.debug('[MULTI-AGENT] Kaggle credentials not set — skipping GPU trigger');
      return false;
    }

    // Rate limit: max once per 15 minutes — TURBO MODE
    const now = Date.now();
    if (now - this.kaggleLastTrigger < 15 * 60 * 1000) return false;

    // Check if there are GPU experiments pending
    if (!this.infra?.pgPool) return false;
    try {
      const result = await this.infra.querySupabase(
        `SELECT COUNT(*) as n FROM nba_experiments WHERE status = 'pending'`
      );
      const gpuPending = parseInt(result.rows?.[0]?.n || 0);
      if (gpuPending === 0) return false;

      // Push kernel via Kaggle API
      const auth = Buffer.from(`${KAGGLE_USERNAME}:${KAGGLE_KEY}`).toString('base64');
      const kernelSlug = 'alexismoret6/nba-quant-gpu-runner';

      // First, read the kernel source from GitHub
      const codeResp = await fetch(
        `https://raw.githubusercontent.com/LBJLincoln/nomos-nba-agent/main/kaggle/nba_gpu_runner.py`,
        { signal: AbortSignal.timeout(10000) }
      );
      const code = await codeResp.text();

      // Push to Kaggle
      const resp = await fetch('https://www.kaggle.com/api/v1/kernels/push', {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: kernelSlug,
          slug: 'nba-quant-gpu-runner',
          newTitle: 'NBA Quant GPU Runner',
          text: code,
          language: 'python',
          kernelType: 'script',
          isPrivate: true,
          enableGpu: true,
          enableInternet: true,
          datasetDataSources: [],
          competitionDataSources: [],
          kernelDataSources: [],
          categoryIds: [],
        }),
        signal: AbortSignal.timeout(30000),
      });

      const data = await resp.json();
      this.kaggleLastTrigger = now;

      if (data.error) {
        logger.warn(`[MULTI-AGENT] Kaggle push error: ${data.error}`);
        return false;
      }

      logger.info(`[MULTI-AGENT] Kaggle GPU kernel triggered! ${gpuPending} GPU experiments pending. Response: ${JSON.stringify(data).substring(0, 200)}`);

      // Notify via Telegram
      if (this.bot) {
        this.bot.sendMessage(this.adminId,
          `🖥️ *Kaggle GPU Runner Triggered*\n${gpuPending} GPU experiments pending\nKernel: ${kernelSlug}`,
          { parse_mode: 'Markdown' }
        ).catch(() => {});
      }

      return true;
    } catch (err) {
      logger.warn(`[MULTI-AGENT] Kaggle trigger failed: ${err.message}`);
      return false;
    }
  }

  /**
   * Auto-review: after code is committed, test it and revert if broken.
   * Called after each cycle if code was written.
   */
  async _autoReviewCode(agent, filePath, repo) {
    if (!this.codeAgent) return;

    try {
      // 1. Read the committed code
      const code = await this.codeAgent.readFile(repo, filePath);
      if (!code) return;

      // 2. Cross-review: use different provider than the one that wrote the code
      const reviewProvider = agent.provider === 'gemini' ? 'kimi' : 'gemini';
      const reviewPrompt = `You are a code reviewer for an NBA prediction model. Review this code for:
1. Python syntax errors
2. Logic bugs
3. Missing imports
4. Security issues
5. Performance problems

If the code has CRITICAL issues, output: REVERT: reason
If the code is acceptable, output: APPROVED: brief summary

CODE (${repo}/${filePath}):
\`\`\`python
${code.substring(Math.max(0, code.length - 3000))}
\`\`\``;

      const review = await this._callProvider(reviewProvider, reviewPrompt);
      if (!review) return;

      if (review.toUpperCase().includes('REVERT:')) {
        const reason = review.match(/REVERT:\s*(.*)/i)?.[1] || 'quality issue';
        logger.warn(`[MULTI-AGENT] Code review REJECTED ${repo}/${filePath}: ${reason}`);

        // Log the rejection — we don't revert automatically to avoid race conditions
        // Instead, flag it in Supabase for human review
        if (this.infra?.pgPool) {
          await this.infra.querySupabase(`
            INSERT INTO nba_experiments (experiment_id, agent_name, experiment_type, description, status, params)
            VALUES ('review_${Date.now().toString(36)}', '${agent.id}_reviewer', 'code_review',
                    'REJECTED: ${reason.replace(/'/g, "''").substring(0, 200)}', 'failed',
                    '${JSON.stringify({ file: `${repo}/${filePath}`, action: 'revert_needed' }).replace(/'/g, "''")}')
          `).catch(() => {});
        }

        if (this.bot && this.adminId) {
          this.bot.sendMessage(this.adminId,
            `⚠️ *Code Review REJECTED*\n${agent.name} → \`${repo}/${filePath}\`\nReason: ${reason.substring(0, 200)}`,
            { parse_mode: 'Markdown' }
          ).catch(() => {});
        }
      } else {
        logger.info(`[MULTI-AGENT] Code review APPROVED: ${repo}/${filePath}`);
      }
    } catch (err) {
      logger.warn(`[MULTI-AGENT] Auto-review error: ${err.message}`);
    }
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
    const totalCodeWrites = Object.values(this.stats).reduce((s, a) => s + (a.codeWrites || 0), 0);
    return {
      running: this.running,
      agents,
      totalExperiments,
      totalCodeWrites,
      codeCommits: this.codeCommits,
      kaggleLastTrigger: this.kaggleLastTrigger ? new Date(this.kaggleLastTrigger).toISOString() : null,
    };
  }
}

module.exports = MultiAgentCoordinator;
