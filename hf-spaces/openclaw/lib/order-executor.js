/**
 * Order Executor — Natural Language → Real Actions
 *
 * Parses free-form Telegram messages into executable actions.
 * The user can type things like:
 *   "boost mutation to 0.2"
 *   "restart S10"
 *   "inject polymarket features"
 *   "show me the evolution status"
 *   "rollback to last good config"
 *   "pause the agentic loop"
 *   "force a research cycle"
 *
 * Each intent maps to a concrete API call or system action.
 */

const logger = require('./logger');

// ── Intent patterns ──
// Each pattern: { regex, intent, extract(match) }
const INTENT_PATTERNS = [
  // GA parameter changes
  { regex: /(?:set|boost|change|increase|bump)\s+mutation\s+(?:rate\s+)?(?:to\s+)?([\d.]+)/i,
    intent: 'set_mutation', extract: (m) => ({ mutation_rate: parseFloat(m[1]) }) },
  { regex: /(?:set|change)\s+population\s+(?:size\s+)?(?:to\s+)?(\d+)/i,
    intent: 'set_population', extract: (m) => ({ pop_size: parseInt(m[1]) }) },
  { regex: /(?:set|change)\s+crossover\s+(?:rate\s+)?(?:to\s+)?([\d.]+)/i,
    intent: 'set_crossover', extract: (m) => ({ crossover_rate: parseFloat(m[1]) }) },
  { regex: /(?:set|change)\s+(?:target\s+)?features?\s+(?:to\s+)?(\d+)/i,
    intent: 'set_features', extract: (m) => ({ target_features: parseInt(m[1]) }) },

  // Diversify / boost
  { regex: /(?:diversif|diversify|diversifie)/i,
    intent: 'diversify', extract: () => ({}) },
  { regex: /(?:boost|augment|increase)\s+mutation/i,
    intent: 'boost_mutation', extract: () => ({}) },
  { regex: /(?:reset|restart)\s+(?:the\s+)?(?:ga|genetic|population|evolution)/i,
    intent: 'reset_population', extract: () => ({}) },

  // Space management
  { regex: /(?:restart|reboot|relance)\s+(?:space\s+)?(?:S10|nba[- ]?quant(?:\s*1)?|s10)/i,
    intent: 'restart_s10', extract: () => ({}) },
  { regex: /(?:restart|reboot|relance)\s+(?:space\s+)?(?:S11|nba[- ]?quant[- ]?2|s11)/i,
    intent: 'restart_s11', extract: () => ({}) },
  { regex: /(?:restart|reboot|relance)\s+(?:space\s+)?(?:openclaw|worker|eve)/i,
    intent: 'restart_openclaw', extract: () => ({}) },

  // Agentic loop control
  { regex: /(?:force|trigger|lance|run)\s+(?:a\s+)?research/i,
    intent: 'trigger_research', extract: () => ({}) },
  { regex: /(?:force|trigger|lance|run)\s+(?:a\s+)?(?:heal|healing)/i,
    intent: 'trigger_heal', extract: () => ({}) },
  { regex: /(?:force|trigger|lance|run)\s+(?:a\s+)?(?:observe|observation)/i,
    intent: 'trigger_observe', extract: () => ({}) },
  { regex: /(?:force|trigger|lance|run)\s+(?:a\s+)?(?:data|data check)/i,
    intent: 'trigger_data', extract: () => ({}) },
  { regex: /(?:force|trigger|lance|run)\s+(?:a\s+)?(?:improve|improvement|amelioration)/i,
    intent: 'trigger_improve', extract: () => ({}) },
  { regex: /(?:pause|stop|arrete)\s+(?:the\s+|la\s+)?(?:loop|boucle|agentic)/i,
    intent: 'pause_loop', extract: () => ({}) },
  { regex: /(?:resume|start|demarre|relance)\s+(?:the\s+|la\s+)?(?:loop|boucle|agentic)/i,
    intent: 'resume_loop', extract: () => ({}) },

  // Rollback / snapshot
  { regex: /(?:rollback|revert|retour)\s+(?:to\s+)?(?:last|previous|good|best)/i,
    intent: 'rollback', extract: () => ({}) },
  { regex: /(?:snapshot|save|sauvegarde)\s+(?:the\s+|la\s+)?(?:config|state|etat)/i,
    intent: 'snapshot', extract: () => ({}) },

  // Feature injection
  { regex: /(?:inject|add|ajoute)\s+(?:.*?)?(?:feature|polymarket|referee)/i,
    intent: 'inject_features', extract: () => ({}) },

  // Status queries
  { regex: /(?:status|state|etat)\s+(?:of\s+)?(?:evolution|ga|s10|evo)/i,
    intent: 'status_evolution', extract: () => ({}) },
  { regex: /(?:status|state|etat)\s+(?:of\s+)?(?:anticipation|bottleneck|prevention)/i,
    intent: 'status_anticipation', extract: () => ({}) },
  { regex: /(?:status|state|etat)\s+(?:of\s+)?(?:loop|boucle|agentic)/i,
    intent: 'status_loop', extract: () => ({}) },
  { regex: /(?:show|display|montre|affiche)\s+(?:me\s+)?(?:the\s+)?(?:research|features?\s+discover)/i,
    intent: 'show_research', extract: () => ({}) },
  { regex: /(?:show|display|montre|affiche)\s+(?:me\s+)?(?:the\s+)?(?:errors?|erreurs?)/i,
    intent: 'show_errors', extract: () => ({}) },
  { regex: /(?:show|display|montre|affiche)\s+(?:me\s+)?(?:the\s+)?(?:bottleneck|anticipation)/i,
    intent: 'status_anticipation', extract: () => ({}) },

  // VM commands
  { regex: /(?:check|verify|verifie)\s+(?:the\s+)?(?:vm|server|serveur)/i,
    intent: 'check_vm', extract: () => ({}) },

  // Emergency
  { regex: /(?:emergency|urgence|urgent)\s+(?:diversif|reset|fix)/i,
    intent: 'emergency_diversify', extract: () => ({}) },

  // Aggressive mode toggle
  { regex: /(?:mode|go|passe)\s+(?:en\s+)?(?:agress|full\s*blast|turbo|beast)/i,
    intent: 'aggressive_mode', extract: () => ({}) },
  { regex: /(?:mode|go|passe)\s+(?:en\s+)?(?:conserv|safe|prudent|calm)/i,
    intent: 'conservative_mode', extract: () => ({}) },
];

class OrderExecutor {
  constructor({ callS10, agenticLoop, anticipationEngine, vmBridge, spaceExecutor, bot, adminId }) {
    this.callS10 = callS10;
    this.loop = agenticLoop;
    this.anticipation = anticipationEngine;
    this.vmBridge = vmBridge;
    this.spaceExecutor = spaceExecutor;
    this.bot = bot;
    this.adminId = adminId;
    this.orderHistory = [];
  }

  /**
   * Parse and execute a natural language order.
   * Returns { executed: bool, intent: string, result: string }
   */
  async execute(text) {
    const parsed = this._parse(text);
    if (!parsed) return null; // Not an order, pass to LLM chat

    const { intent, params } = parsed;
    logger.info(`[ORDER] Intent: ${intent}, params: ${JSON.stringify(params)}`);

    let result;
    try {
      result = await this._dispatch(intent, params);
    } catch (err) {
      result = { error: err.message };
    }

    const entry = {
      timestamp: new Date().toISOString(),
      text,
      intent,
      params,
      result,
    };
    this.orderHistory.push(entry);
    if (this.orderHistory.length > 100) this.orderHistory = this.orderHistory.slice(-100);

    return {
      executed: true,
      intent,
      result: this._formatResult(intent, result),
    };
  }

  // ── Parse intent from text ──
  _parse(text) {
    for (const pattern of INTENT_PATTERNS) {
      const match = text.match(pattern.regex);
      if (match) {
        return {
          intent: pattern.intent,
          params: pattern.extract(match),
        };
      }
    }
    return null;
  }

  // ── Dispatch to handler ──
  async _dispatch(intent, params) {
    switch (intent) {
      // GA config changes
      case 'set_mutation':
      case 'set_population':
      case 'set_crossover':
      case 'set_features': {
        return await this.callS10('/api/config', params);
      }

      case 'diversify': {
        return await this.callS10('/api/command', { command: 'diversify' });
      }

      case 'boost_mutation': {
        return await this.callS10('/api/command', { command: 'boost_mutation' });
      }

      case 'reset_population': {
        return await this.callS10('/api/reset');
      }

      // Space management
      case 'restart_s10': {
        if (this.vmBridge) {
          return await this.vmBridge.hfSpaceAction('lbjlincoln/nomos-nba-quant', 'restart');
        }
        return { error: 'VM Bridge not available' };
      }

      case 'restart_s11': {
        if (this.vmBridge) {
          return await this.vmBridge.hfSpaceAction('lbjlincoln/nomos-nba-quant-2', 'restart');
        }
        return { error: 'VM Bridge not available' };
      }

      case 'restart_openclaw': {
        return { info: 'Cannot restart self. Use HF dashboard or /hfspace command.' };
      }

      // Loop control
      case 'trigger_research': {
        if (this.loop) {
          this.loop._research().catch(e => logger.error('Order research error:', e));
          return { status: 'Research cycle triggered' };
        }
        return { error: 'Loop not available' };
      }

      case 'trigger_heal': {
        if (this.loop) {
          this.loop._heal().catch(e => logger.error('Order heal error:', e));
          return { status: 'Heal cycle triggered' };
        }
        return { error: 'Loop not available' };
      }

      case 'trigger_observe': {
        if (this.loop) {
          this.loop._observe().catch(e => logger.error('Order observe error:', e));
          return { status: 'Observe cycle triggered' };
        }
        return { error: 'Loop not available' };
      }

      case 'trigger_data': {
        if (this.loop) {
          this.loop._dataCheck().catch(e => logger.error('Order data error:', e));
          return { status: 'Data check triggered' };
        }
        return { error: 'Loop not available' };
      }

      case 'trigger_improve': {
        if (this.loop) {
          const lastEvo = this.loop.state.evolutionHistory.length > 0
            ? this.loop.state.evolutionHistory[this.loop.state.evolutionHistory.length - 1]
            : null;
          this.loop._improve(lastEvo).catch(e => logger.error('Order improve error:', e));
          return { status: 'Improve cycle triggered' };
        }
        return { error: 'Loop not available' };
      }

      case 'pause_loop': {
        if (this.loop) {
          this.loop.stop();
          return { status: 'Agentic loop PAUSED' };
        }
        return { error: 'Loop not available' };
      }

      case 'resume_loop': {
        if (this.loop) {
          this.loop.start();
          return { status: 'Agentic loop RESUMED' };
        }
        return { error: 'Loop not available' };
      }

      // Rollback
      case 'rollback': {
        if (this.anticipation) {
          return await this.anticipation.rollback();
        }
        return { error: 'Anticipation engine not available' };
      }

      case 'snapshot': {
        if (this.anticipation && this.loop) {
          const lastEvo = this.loop.state.evolutionHistory.length > 0
            ? this.loop.state.evolutionHistory[this.loop.state.evolutionHistory.length - 1]
            : null;
          if (lastEvo) {
            this.anticipation.state.configSnapshots.push({
              timestamp: new Date().toISOString(),
              brier: lastEvo.brier,
              roi: lastEvo.roi,
              features: lastEvo.features,
              mutationRate: lastEvo.mutationRate,
              population: lastEvo.population,
            });
            this.anticipation._save();
            return { status: `Snapshot saved: Brier ${lastEvo.brier}, ${lastEvo.features} features` };
          }
        }
        return { error: 'No evolution data to snapshot' };
      }

      // Feature injection
      case 'inject_features': {
        if (this.loop) {
          const newFeatures = this.loop.research.filter(r => r.status === 'new');
          if (newFeatures.length > 0) {
            const top = newFeatures.slice(0, 5);
            const result = await this.callS10('/api/inject-features', {
              features: top.map(f => ({ name: f.name, category: f.category, description: f.description })),
            });
            for (const f of top) f.status = 'injected';
            this.loop._saveResearch();
            return { status: `Injected ${top.length} features`, features: top.map(f => f.name), result };
          }
          return { info: 'No new features to inject. Run research first.' };
        }
        return { error: 'Loop not available' };
      }

      // Status queries
      case 'status_evolution': {
        if (this.loop) {
          const evo = this.loop.state.evolutionHistory;
          const last = evo.length > 0 ? evo[evo.length - 1] : null;
          return {
            bestBrier: this.loop.state.bestBrier,
            bestROI: this.loop.state.bestROI,
            current: last,
            stagnation: this.loop.state.stagnationCount,
            cycleCount: this.loop.state.cycleCount,
          };
        }
        return { error: 'Loop not available' };
      }

      case 'status_anticipation': {
        if (this.anticipation) {
          return this.anticipation.getStatus();
        }
        return { error: 'Anticipation engine not available' };
      }

      case 'status_loop': {
        if (this.loop) {
          return this.loop.getStatus();
        }
        return { error: 'Loop not available' };
      }

      case 'show_research': {
        if (this.loop) {
          return {
            total: this.loop.research.length,
            newCount: this.loop.research.filter(r => r.status === 'new').length,
            recent: this.loop.research.slice(-5).map(r => ({
              name: r.name,
              category: r.category,
              status: r.status,
              power: r.power,
            })),
          };
        }
        return { error: 'Loop not available' };
      }

      case 'show_errors': {
        if (this.loop) {
          return this.loop.getErrors();
        }
        return { error: 'Loop not available' };
      }

      // VM check
      case 'check_vm': {
        if (this.vmBridge) {
          return await this.vmBridge.ping();
        }
        return { error: 'VM Bridge not available' };
      }

      // Emergency
      case 'emergency_diversify': {
        const resetResult = await this.callS10('/api/reset');
        const boostResult = await this.callS10('/api/command', { command: 'boost_mutation' });
        const configResult = await this.callS10('/api/config', {
          mutation_rate: 0.20,
          target_features: 250,
          crossover_rate: 0.90,
        });
        return {
          status: 'EMERGENCY DIVERSIFICATION APPLIED',
          reset: resetResult,
          boost: boostResult,
          config: configResult,
        };
      }

      // Mode changes
      case 'aggressive_mode': {
        const aggressiveConfig = {
          mutation_rate: 0.18,
          pop_size: 200,
          crossover_rate: 0.90,
          target_features: 300,
        };
        const result = await this.callS10('/api/config', aggressiveConfig);
        return { status: 'AGGRESSIVE MODE', config: aggressiveConfig, result };
      }

      case 'conservative_mode': {
        const conservativeConfig = {
          mutation_rate: 0.06,
          pop_size: 100,
          crossover_rate: 0.70,
          target_features: 120,
        };
        const result = await this.callS10('/api/config', conservativeConfig);
        return { status: 'CONSERVATIVE MODE', config: conservativeConfig, result };
      }

      default:
        return { error: `Unknown intent: ${intent}` };
    }
  }

  // ── Format result for Telegram ──
  _formatResult(intent, result) {
    if (result.error) return `Action failed: ${result.error}`;

    switch (intent) {
      case 'set_mutation':
      case 'set_population':
      case 'set_crossover':
      case 'set_features':
        return `*Config applied* ${result.status || JSON.stringify(result)}`;

      case 'diversify':
        return `*Diversification* lancee ${result.status || ''}`;

      case 'boost_mutation':
        return `*Mutation boost* applique ${result.status || ''}`;

      case 'reset_population':
        return `*Population reset* ${result.status || 'OK'}`;

      case 'restart_s10':
      case 'restart_s11':
        return `*Space restart* ${result.stdout || result.status || 'OK'}`;

      case 'trigger_research':
      case 'trigger_heal':
      case 'trigger_observe':
      case 'trigger_data':
      case 'trigger_improve':
        return `*${intent.replace('trigger_', '').toUpperCase()}* cycle declenche`;

      case 'pause_loop':
        return '*Loop PAUSED* — plus de cycles automatiques';

      case 'resume_loop':
        return '*Loop RESUMED* — cycles automatiques reactives';

      case 'rollback':
        if (result.snapshot) {
          return `*ROLLBACK* vers Brier ${result.snapshot.brier?.toFixed(4)}, ${result.snapshot.features} features`;
        }
        return `*ROLLBACK* ${result.error || 'applied'}`;

      case 'snapshot':
        return `*Snapshot* sauvegarde: ${result.status}`;

      case 'inject_features':
        if (result.features) {
          return `*Features injectees* (${result.features.length}):\n${result.features.map(f => `- \`${f}\``).join('\n')}`;
        }
        return result.info || 'No features to inject';

      case 'status_evolution': {
        const r = result;
        return `*Evolution Status*
Best Brier: ${r.bestBrier?.toFixed(4) || '?'}
Best ROI: ${r.bestROI?.toFixed(1) || '?'}%
Stagnation: ${r.stagnation}
Cycles: ${r.cycleCount}
${r.current ? `Current: Gen ${r.current.generation}, Brier ${r.current.brier?.toFixed(4)}, ${r.current.features} feats` : ''}`;
      }

      case 'status_anticipation': {
        const r = result;
        let text = `*Anticipation Engine*
Prevented: ${r.totalPrevented} | Occurred: ${r.totalOccurred}
Prevention rate: ${r.preventionRate}
Snapshots: ${r.snapshots}\n`;
        if (r.bottlenecks) {
          text += '\n*Bottlenecks:*\n';
          for (const [key, bn] of Object.entries(r.bottlenecks)) {
            const icon = bn.inWarningZone ? 'WARNING' : 'OK';
            text += `${icon} *${bn.name}*: ${bn.minutesSinceLast !== null ? bn.minutesSinceLast + 'min ago' : 'never'} (avg ${bn.avgIntervalMin}min)\n`;
          }
        }
        return text;
      }

      case 'status_loop': {
        const r = result;
        return `*Agentic Loop*
Status: ${r.status} | Running: ${r.running}
Cycles: ${r.cycleCount}
Best Brier: ${r.bestBrier?.toFixed(4)}
Research: ${r.researchCount} (${r.newFeatures} new)
Errors: ${r.errorCount} unfixed`;
      }

      case 'show_research': {
        const r = result;
        let text = `*Research* — ${r.total} total, ${r.newCount} new\n`;
        if (r.recent) {
          text += '\nRecent:\n';
          for (const f of r.recent) {
            text += `- \`${f.name}\` (${f.category}) [${f.status}] ${f.power}\n`;
          }
        }
        return text;
      }

      case 'show_errors':
        if (Array.isArray(result) && result.length > 0) {
          return `*Errors* (${result.length}):\n${result.slice(-5).map(e =>
            `- [${e.phase}] ${e.message?.substring(0, 60)} ${e.fixed ? 'FIXED' : 'OPEN'}`
          ).join('\n')}`;
        }
        return 'No errors.';

      case 'check_vm':
        return result.reachable
          ? `*VM Online* — ${result.latency}ms`
          : `*VM Offline* — ${result.error}`;

      case 'emergency_diversify':
        return '*EMERGENCY DIVERSIFICATION COMPLETE*\nPopulation reset + Mutation 0.20 + Features 250 + Crossover 0.90';

      case 'aggressive_mode':
        return `*AGGRESSIVE MODE ACTIVE*\nMutation: 0.18 | Pop: 200 | Crossover: 0.90 | Features: 300`;

      case 'conservative_mode':
        return `*CONSERVATIVE MODE ACTIVE*\nMutation: 0.06 | Pop: 100 | Crossover: 0.70 | Features: 120`;

      default:
        return JSON.stringify(result).substring(0, 500);
    }
  }

  // Check if text looks like an order (quick check before full parse)
  isOrder(text) {
    return this._parse(text) !== null;
  }

  getHistory(limit = 20) {
    return this.orderHistory.slice(-limit);
  }
}

module.exports = OrderExecutor;
