/**
 * Rule Engine — Deterministic Action Engine (NO LLM NEEDED)
 *
 * When LLM providers are down, this engine takes over.
 * It encodes all known bottleneck→action mappings as hard rules.
 *
 * 80% of the agentic loop's actions are deterministic:
 *   stagnation → diversify
 *   space down → restart
 *   feature plateau → inject from pool
 *   brier regression → rollback
 *   mutation too low → bump
 *   population too small → expand
 *
 * Only RESEARCH (discovering new features) truly needs an LLM.
 * Everything else can run 24/7 with zero LLM dependency.
 */

const logger = require('./logger');

// ── Deterministic rules ──
// Each rule: { condition(state), action(state, callS10), description }
const RULES = [
  // STAGNATION: auto-diversify
  {
    id: 'stagnation_diversify',
    condition: (s) => s.stagnation >= 3,
    action: async (s, callS10) => {
      const newMutation = Math.min(0.22, (s.mutationRate || 0.10) + 0.06);
      await callS10('/api/config', { mutation_rate: newMutation, crossover_rate: 0.88 });
      if (s.stagnation >= 6) {
        await callS10('/api/command', { command: 'diversify' });
      }
      return `Stagnation ${s.stagnation}: mutation→${newMutation}${s.stagnation >= 6 ? ' + diversify command' : ''}`;
    },
    cooldownMin: 15,
    lastRun: 0,
  },

  // CRITICAL STAGNATION: full reset
  {
    id: 'critical_stagnation_reset',
    condition: (s) => s.stagnation >= 10,
    action: async (s, callS10) => {
      await callS10('/api/reset');
      await callS10('/api/config', {
        mutation_rate: 0.20,
        target_features: 250,
        crossover_rate: 0.90,
        pop_size: 200,
      });
      return 'CRITICAL STAGNATION: full reset + aggressive params';
    },
    cooldownMin: 60,
    lastRun: 0,
  },

  // MUTATION TOO LOW: auto-bump
  {
    id: 'mutation_floor',
    condition: (s) => s.mutationRate > 0 && s.mutationRate < 0.04,
    action: async (s, callS10) => {
      await callS10('/api/config', { mutation_rate: 0.08 });
      return `Mutation rate dangerously low (${s.mutationRate}). Bumped to 0.08`;
    },
    cooldownMin: 20,
    lastRun: 0,
  },

  // POPULATION TOO SMALL: expand
  {
    id: 'population_expand',
    condition: (s) => s.population > 0 && s.population < 80,
    action: async (s, callS10) => {
      const newPop = Math.max(150, s.population * 2);
      await callS10('/api/config', { pop_size: newPop });
      return `Population too small (${s.population}). Expanded to ${newPop}`;
    },
    cooldownMin: 30,
    lastRun: 0,
  },

  // FEATURES TOO FEW: expand target
  {
    id: 'features_expand',
    condition: (s) => s.features > 0 && s.features < 60,
    action: async (s, callS10) => {
      await callS10('/api/config', { target_features: 200 });
      return `Only ${s.features} features selected. Target expanded to 200`;
    },
    cooldownMin: 30,
    lastRun: 0,
  },

  // BRIER DEGRADING: bump exploration
  {
    id: 'brier_degrading',
    condition: (s) => s.brierTrend && s.brierTrend > 0.003,
    action: async (s, callS10) => {
      const newMutation = Math.min(0.20, (s.mutationRate || 0.10) + 0.04);
      await callS10('/api/config', { mutation_rate: newMutation });
      return `Brier degrading (trend +${s.brierTrend.toFixed(4)}). Mutation→${newMutation}`;
    },
    cooldownMin: 20,
    lastRun: 0,
  },

  // ELITISM TOO HIGH: reduce
  {
    id: 'elitism_reduce',
    condition: (s) => s.stagnation >= 4 && s.mutationRate < 0.10,
    action: async (s, callS10) => {
      await callS10('/api/config', {
        mutation_rate: 0.15,
        crossover_rate: 0.85,
      });
      return 'Reducing selection pressure: mutation→0.15, crossover→0.85';
    },
    cooldownMin: 25,
    lastRun: 0,
  },
];

class RuleEngine {
  constructor({ callS10 }) {
    this.callS10 = callS10;
    this.rules = RULES.map(r => ({ ...r })); // Clone to avoid shared state
    this.executionLog = [];
    this.totalExecutions = 0;
    this.llmFailCount = 0;
  }

  /**
   * Evaluate all rules against current evolution state.
   * Returns list of actions taken.
   * This is the FALLBACK when LLM is unavailable.
   */
  async evaluate(evoState) {
    if (!evoState) return [];
    const now = Date.now();
    const actions = [];

    for (const rule of this.rules) {
      // Check cooldown
      if (now - rule.lastRun < rule.cooldownMin * 60000) continue;

      // Check condition
      try {
        if (rule.condition(evoState)) {
          const result = await rule.action(evoState, this.callS10);
          rule.lastRun = now;
          this.totalExecutions++;

          const entry = {
            ruleId: rule.id,
            result,
            timestamp: new Date().toISOString(),
            llmFallback: true,
          };
          actions.push(entry);
          this.executionLog.push(entry);
          if (this.executionLog.length > 100) this.executionLog = this.executionLog.slice(-100);

          logger.info(`[RULE-ENGINE] ${rule.id}: ${result}`);
        }
      } catch (err) {
        logger.warn(`[RULE-ENGINE] ${rule.id} error: ${err.message}`);
      }
    }

    return actions;
  }

  /**
   * Record an LLM failure. After 3+ failures, rules take full control.
   */
  recordLLMFailure() {
    this.llmFailCount++;
    logger.warn(`[RULE-ENGINE] LLM failure count: ${this.llmFailCount}`);
  }

  resetLLMFailures() {
    this.llmFailCount = 0;
  }

  shouldTakeOver() {
    return this.llmFailCount >= 2;
  }

  getStatus() {
    return {
      totalExecutions: this.totalExecutions,
      rulesCount: this.rules.length,
      llmFailCount: this.llmFailCount,
      takingOver: this.shouldTakeOver(),
      recentActions: this.executionLog.slice(-10),
    };
  }
}

module.exports = RuleEngine;
