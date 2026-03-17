/**
 * Anticipation Engine — Predictive Bottleneck Prevention
 *
 * Tracks recurring bottleneck patterns and acts BEFORE they happen.
 * Learns from history: frequency, severity, optimal preemptive action.
 *
 * Known bottlenecks:
 *   1. GA Stagnation       — every ~25-35 generations
 *   2. HF Space Sleep      — free tier sleeps after inactivity
 *   3. LLM Provider Failure — all providers cascade-fail
 *   4. Feature Plateau      — selected features stop improving
 *   5. Brier Regression     — improvement reverts after config change
 *   6. S10 Stuck Starting   — space hangs in STARTING state
 *   7. Connectivity Loss    — SSH/API timeouts to VM or S10
 */

const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const ANTICIPATION_FILE = '/data/agentic-loop/anticipation-state.json';
const BOTTLENECK_LOG_FILE = '/data/agentic-loop/bottleneck-history.json';

// ── Known bottleneck signatures ──
const BOTTLENECK_SIGNATURES = {
  ga_stagnation: {
    name: 'GA Stagnation',
    avgIntervalMin: 120,        // ~2h between occurrences
    warningThresholdMin: 90,    // warn at 75% of avg interval
    preemptiveAction: 'diversify_early',
    severity: 'high',
    indicators: ['stagnation > 1', 'brier flat 3+ observations'],
  },
  space_sleep: {
    name: 'HF Space Sleep/Crash',
    avgIntervalMin: 240,        // ~4h
    warningThresholdMin: 200,
    preemptiveAction: 'warm_ping',
    severity: 'medium',
    indicators: ['HTTP timeout', 'status != EVOLVING'],
  },
  llm_cascade_fail: {
    name: 'LLM Provider Cascade Failure',
    avgIntervalMin: 360,        // ~6h
    warningThresholdMin: 300,
    preemptiveAction: 'cache_completions',
    severity: 'medium',
    indicators: ['ALL LLM providers failed', 'getCompletion throws'],
  },
  feature_plateau: {
    name: 'Feature Selection Plateau',
    avgIntervalMin: 180,        // ~3h
    warningThresholdMin: 150,
    preemptiveAction: 'inject_research',
    severity: 'high',
    indicators: ['features unchanged 5+ obs', 'research pool empty'],
  },
  brier_regression: {
    name: 'Brier Regression Post-Change',
    avgIntervalMin: 90,
    warningThresholdMin: 60,
    preemptiveAction: 'snapshot_before_change',
    severity: 'high',
    indicators: ['brier increased after improve cycle'],
  },
  s10_stuck_starting: {
    name: 'S10 Stuck in STARTING',
    avgIntervalMin: 480,        // ~8h
    warningThresholdMin: 420,
    preemptiveAction: 'restart_space',
    severity: 'critical',
    indicators: ['status=STARTING for 5+ min', 'generation=0'],
  },
  connectivity_loss: {
    name: 'VM/S10 Connectivity Loss',
    avgIntervalMin: 300,
    warningThresholdMin: 240,
    preemptiveAction: 'failover_check',
    severity: 'medium',
    indicators: ['ECONNREFUSED', 'timeout', 'unreachable'],
  },
};

class AnticipationEngine {
  constructor({ callS10, bot, adminId, fetchEvolution }) {
    this.callS10 = callS10;
    this.bot = bot;
    this.adminId = adminId;
    this.fetchEvolution = fetchEvolution;

    // State: tracks each bottleneck's history
    this.state = {
      bottlenecks: {},
      lastCheck: null,
      totalPrevented: 0,
      totalOccurred: 0,
      configSnapshots: [],       // rollback points
      preemptiveActions: [],     // log of preemptive actions taken
    };

    // Initialize bottleneck trackers
    for (const [key, sig] of Object.entries(BOTTLENECK_SIGNATURES)) {
      this.state.bottlenecks[key] = {
        ...sig,
        id: key,
        occurrences: [],           // timestamps of past occurrences
        lastOccurrence: null,
        lastPreemption: null,
        avgInterval: sig.avgIntervalMin * 60000,
        warningThreshold: sig.warningThresholdMin * 60000,
        prevented: 0,
        occurred: 0,
        consecutiveHits: 0,
      };
    }

    this.history = [];
    this._load();
  }

  // ══════════════════════════════════════════
  //  MAIN CHECK — Run every cycle to predict & prevent
  // ══════════════════════════════════════════

  async check(currentEvoState) {
    this.state.lastCheck = new Date().toISOString();
    const now = Date.now();
    const actions = [];

    for (const [key, bn] of Object.entries(this.state.bottlenecks)) {
      if (!bn.lastOccurrence) continue;

      const timeSince = now - new Date(bn.lastOccurrence).getTime();
      const timeToExpected = bn.avgInterval - timeSince;
      const isInWarningZone = timeSince > bn.warningThreshold;
      const alreadyPreempted = bn.lastPreemption &&
        (now - new Date(bn.lastPreemption).getTime()) < bn.avgInterval * 0.5;

      if (isInWarningZone && !alreadyPreempted) {
        logger.info(`[ANTICIPATION] ${bn.name}: WARNING ZONE (${Math.round(timeSince / 60000)}min since last, expected every ${Math.round(bn.avgInterval / 60000)}min)`);

        const action = await this._preempt(key, bn, currentEvoState);
        if (action) {
          actions.push(action);
          bn.lastPreemption = new Date().toISOString();
          bn.prevented++;
          this.state.totalPrevented++;
        }
      }
    }

    // Also check for early indicators in current state
    if (currentEvoState) {
      const earlyActions = await this._checkEarlyIndicators(currentEvoState);
      actions.push(...earlyActions);
    }

    if (actions.length > 0) {
      this._save();
    }

    return actions;
  }

  // ══════════════════════════════════════════
  //  RECORD — Log a bottleneck occurrence
  // ══════════════════════════════════════════

  record(bottleneckId, details = {}) {
    const bn = this.state.bottlenecks[bottleneckId];
    if (!bn) {
      logger.warn(`[ANTICIPATION] Unknown bottleneck: ${bottleneckId}`);
      return;
    }

    const now = new Date().toISOString();
    const entry = { timestamp: now, id: bottleneckId, ...details };

    // Update interval estimate (exponential moving average)
    if (bn.lastOccurrence) {
      const interval = Date.now() - new Date(bn.lastOccurrence).getTime();
      bn.avgInterval = bn.avgInterval * 0.7 + interval * 0.3; // EMA
      bn.warningThreshold = bn.avgInterval * 0.75;
    }

    bn.occurrences.push(now);
    if (bn.occurrences.length > 50) bn.occurrences = bn.occurrences.slice(-50);
    bn.lastOccurrence = now;
    bn.occurred++;
    bn.consecutiveHits++;
    this.state.totalOccurred++;

    this.history.push(entry);
    if (this.history.length > 200) this.history = this.history.slice(-200);

    logger.info(`[ANTICIPATION] RECORDED: ${bn.name} (total: ${bn.occurred}, consecutive: ${bn.consecutiveHits})`);
    this._save();
  }

  // Reset consecutive counter when bottleneck is resolved
  resolve(bottleneckId) {
    const bn = this.state.bottlenecks[bottleneckId];
    if (bn) {
      bn.consecutiveHits = 0;
    }
  }

  // ══════════════════════════════════════════
  //  PREEMPT — Take action before bottleneck hits
  // ══════════════════════════════════════════

  async _preempt(bottleneckId, bn, evoState) {
    const action = { id: bottleneckId, name: bn.name, timestamp: new Date().toISOString() };

    switch (bn.preemptiveAction) {
      case 'diversify_early': {
        // Pre-diversify before stagnation hits
        const params = {
          mutation_rate: Math.min(0.18, (evoState?.mutationRate || 0.10) + 0.05),
          crossover_rate: 0.88,
        };
        const result = await this.callS10('/api/config', params);
        action.applied = `Pre-diversify: mutation ${params.mutation_rate}, crossover ${params.crossover_rate}`;
        action.result = result?.status || result?.error;

        // Also inject pending research features preemptively
        action.type = 'diversify_early';
        break;
      }

      case 'warm_ping': {
        // Ping spaces to keep them awake
        const urls = [
          'https://lbjlincoln-nomos-nba-quant.hf.space/api/status',
          'https://lbjlincoln-nomos-nba-quant-2.hf.space/api/status',
        ];
        const results = [];
        for (const url of urls) {
          try {
            const resp = await fetch(url, { signal: AbortSignal.timeout(10000) });
            results.push({ url, ok: resp.ok });
          } catch (e) {
            results.push({ url, ok: false, error: e.message });
          }
        }
        action.applied = `Warm ping: ${results.filter(r => r.ok).length}/${results.length} responsive`;
        action.type = 'warm_ping';
        break;
      }

      case 'cache_completions': {
        // Nothing to preemptively do here except log awareness
        action.applied = 'LLM cascade warning noted. Monitoring provider health.';
        action.type = 'cache_completions';
        break;
      }

      case 'inject_research': {
        // Flag that research needs acceleration
        action.applied = 'Feature plateau approaching. Research acceleration flagged.';
        action.needsResearchBoost = true;
        action.type = 'inject_research';
        break;
      }

      case 'snapshot_before_change': {
        // Save current config as rollback point
        if (evoState) {
          const snapshot = {
            timestamp: new Date().toISOString(),
            brier: evoState.brier,
            roi: evoState.roi,
            features: evoState.features,
            mutationRate: evoState.mutationRate,
            population: evoState.population,
          };
          this.state.configSnapshots.push(snapshot);
          if (this.state.configSnapshots.length > 20) {
            this.state.configSnapshots = this.state.configSnapshots.slice(-20);
          }
          action.applied = `Snapshot saved: Brier ${snapshot.brier}, ${snapshot.features} features`;
        }
        action.type = 'snapshot';
        break;
      }

      case 'restart_space': {
        // Try to restart S10 preemptively
        try {
          const resp = await fetch('https://lbjlincoln-nomos-nba-quant.hf.space/api/status',
            { signal: AbortSignal.timeout(10000) });
          if (!resp.ok) {
            action.applied = 'S10 unresponsive. Flagging for restart.';
            action.needsRestart = true;
          } else {
            action.applied = 'S10 responsive. Pre-restart not needed.';
          }
        } catch {
          action.applied = 'S10 unreachable. Restart needed.';
          action.needsRestart = true;
        }
        action.type = 'restart_check';
        break;
      }

      case 'failover_check': {
        action.applied = 'Connectivity check — monitoring degradation.';
        action.type = 'failover_check';
        break;
      }

      default:
        action.applied = `Unknown preemptive action: ${bn.preemptiveAction}`;
    }

    this.state.preemptiveActions.push(action);
    if (this.state.preemptiveActions.length > 100) {
      this.state.preemptiveActions = this.state.preemptiveActions.slice(-100);
    }

    logger.info(`[ANTICIPATION] PREEMPTED: ${action.applied}`);
    return action;
  }

  // ══════════════════════════════════════════
  //  EARLY INDICATORS — Detect approaching bottlenecks from current state
  // ══════════════════════════════════════════

  async _checkEarlyIndicators(evoState) {
    const actions = [];

    // 1. Stagnation approaching: stagnation > 0 but < 2 (not yet triggering main loop)
    if (evoState.stagnation === 1) {
      const bn = this.state.bottlenecks.ga_stagnation;
      if (!bn.lastPreemption || Date.now() - new Date(bn.lastPreemption).getTime() > 10 * 60000) {
        // Slight mutation bump to prevent full stagnation
        const nudge = {
          mutation_rate: Math.min(0.15, (evoState.mutationRate || 0.10) + 0.02),
        };
        const result = await this.callS10('/api/config', nudge);
        actions.push({
          id: 'ga_stagnation',
          type: 'early_nudge',
          applied: `Early nudge: mutation ${nudge.mutation_rate} (stagnation=1)`,
          result: result?.status || result?.error,
          timestamp: new Date().toISOString(),
        });
        bn.lastPreemption = new Date().toISOString();
      }
    }

    // 2. Features dropping below healthy threshold
    if (evoState.features > 0 && evoState.features < 70) {
      actions.push({
        id: 'feature_plateau',
        type: 'early_warning',
        applied: `Feature count low: ${evoState.features}. Need injection.`,
        timestamp: new Date().toISOString(),
      });
    }

    // 3. Population too small for diversity
    if (evoState.population > 0 && evoState.population < 80) {
      const expand = { pop_size: Math.max(150, evoState.population * 2) };
      const result = await this.callS10('/api/config', expand);
      actions.push({
        id: 'ga_stagnation',
        type: 'population_expand',
        applied: `Population too small (${evoState.population}). Expanding to ${expand.pop_size}.`,
        result: result?.status || result?.error,
        timestamp: new Date().toISOString(),
      });
    }

    // 4. Mutation rate too low (will cause stagnation)
    if (evoState.mutationRate > 0 && evoState.mutationRate < 0.04) {
      const bump = { mutation_rate: 0.08 };
      const result = await this.callS10('/api/config', bump);
      actions.push({
        id: 'ga_stagnation',
        type: 'mutation_floor',
        applied: `Mutation rate dangerously low (${evoState.mutationRate}). Bumped to 0.08.`,
        result: result?.status || result?.error,
        timestamp: new Date().toISOString(),
      });
    }

    return actions;
  }

  // ══════════════════════════════════════════
  //  ROLLBACK — Revert to last known good config
  // ══════════════════════════════════════════

  async rollback() {
    const snapshots = this.state.configSnapshots;
    if (snapshots.length === 0) return { error: 'No snapshots available' };

    // Find the best snapshot (lowest Brier)
    const best = snapshots.reduce((a, b) =>
      (a.brier && b.brier && a.brier < b.brier) ? a : b
    );

    const params = {};
    if (best.mutationRate) params.mutation_rate = best.mutationRate;
    if (best.population) params.pop_size = best.population;

    const result = await this.callS10('/api/config', params);
    logger.info(`[ANTICIPATION] ROLLBACK to snapshot: Brier ${best.brier}, ${JSON.stringify(params)}`);

    return { snapshot: best, applied: params, result };
  }

  // ══════════════════════════════════════════
  //  STATUS — For dashboard/API
  // ══════════════════════════════════════════

  getStatus() {
    const summary = {};
    for (const [key, bn] of Object.entries(this.state.bottlenecks)) {
      const timeSince = bn.lastOccurrence ?
        Date.now() - new Date(bn.lastOccurrence).getTime() : null;
      const timeToWarning = timeSince !== null ?
        Math.max(0, bn.warningThreshold - timeSince) : null;

      summary[key] = {
        name: bn.name,
        severity: bn.severity,
        occurred: bn.occurred,
        prevented: bn.prevented,
        lastOccurrence: bn.lastOccurrence,
        lastPreemption: bn.lastPreemption,
        avgIntervalMin: Math.round(bn.avgInterval / 60000),
        minutesSinceLast: timeSince !== null ? Math.round(timeSince / 60000) : null,
        minutesToWarning: timeToWarning !== null ? Math.round(timeToWarning / 60000) : null,
        inWarningZone: timeSince !== null && timeSince > bn.warningThreshold,
        consecutiveHits: bn.consecutiveHits,
      };
    }

    return {
      bottlenecks: summary,
      totalPrevented: this.state.totalPrevented,
      totalOccurred: this.state.totalOccurred,
      preventionRate: this.state.totalOccurred > 0
        ? ((this.state.totalPrevented / (this.state.totalPrevented + this.state.totalOccurred)) * 100).toFixed(1) + '%'
        : 'N/A',
      snapshots: this.state.configSnapshots.length,
      recentActions: this.state.preemptiveActions.slice(-10),
      lastCheck: this.state.lastCheck,
    };
  }

  // ══════════════════════════════════════════
  //  PERSISTENCE
  // ══════════════════════════════════════════

  _load() {
    try {
      if (fs.existsSync(ANTICIPATION_FILE)) {
        const saved = JSON.parse(fs.readFileSync(ANTICIPATION_FILE, 'utf8'));
        // Merge saved state with defaults (preserves new bottleneck types)
        if (saved.bottlenecks) {
          for (const [key, bn] of Object.entries(saved.bottlenecks)) {
            if (this.state.bottlenecks[key]) {
              Object.assign(this.state.bottlenecks[key], bn);
            }
          }
        }
        this.state.totalPrevented = saved.totalPrevented || 0;
        this.state.totalOccurred = saved.totalOccurred || 0;
        this.state.configSnapshots = saved.configSnapshots || [];
        this.state.preemptiveActions = saved.preemptiveActions || [];
      }
    } catch (e) { logger.warn('Load anticipation state:', e.message); }

    try {
      if (fs.existsSync(BOTTLENECK_LOG_FILE)) {
        this.history = JSON.parse(fs.readFileSync(BOTTLENECK_LOG_FILE, 'utf8'));
      }
    } catch (e) { logger.warn('Load bottleneck history:', e.message); }
  }

  _save() {
    try {
      fs.writeFileSync(ANTICIPATION_FILE, JSON.stringify(this.state, null, 2));
      fs.writeFileSync(BOTTLENECK_LOG_FILE, JSON.stringify(this.history));
    } catch (e) { logger.warn('Save anticipation state:', e.message); }
  }
}

module.exports = AnticipationEngine;
