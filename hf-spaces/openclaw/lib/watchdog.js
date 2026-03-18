/**
 * Watchdog — Statistical Evolution Monitor (OBSERVATION ONLY)
 *
 * Replaces the destructive anticipation-engine + rule-engine.
 * This module OBSERVES and ALERTS — it NEVER changes S10 config.
 *
 * Philosophy:
 *   - Config changes are Adam's job (human-in-the-loop)
 *   - Eve's job is to WATCH, MEASURE, and ALERT
 *   - Only exception: restarting a crashed HF Space
 *
 * Metrics tracked:
 *   - Brier score time series (detect plateau/regression)
 *   - Generation count (detect stall)
 *   - Population diversity (detect convergence)
 *   - Feature count (detect bloat)
 *   - Space health (detect crashes)
 *
 * Alert levels:
 *   INFO    — Logged only
 *   WARNING — Logged + stored in A2A inbox
 *   CRITICAL — Logged + Telegram + A2A inbox
 */

const fs = require('fs');
const logger = require('./logger');

const STATE_FILE = '/data/watchdog/state.json';
const METRICS_FILE = '/data/watchdog/metrics.json';

class Watchdog {
  constructor({ fetchEvolution, spaceExecutor, bot, adminId, a2a }) {
    this.fetchEvolution = fetchEvolution;
    this.spaces = spaceExecutor;
    this.bot = bot;
    this.adminId = adminId;
    this.a2a = a2a;  // A2A protocol for posting reports

    // Metrics ring buffer (max 500 observations)
    this.metrics = [];
    this.alerts = [];
    this.lastCheck = null;
    this.consecutiveFailures = 0;
    this.lastBrier = null;
    this.lastGeneration = null;
    this.stagnationStart = null;

    // Stats
    this.stats = {
      checks: 0,
      alertsSent: 0,
      spacesRestarted: 0,
      lastStatus: null,
    };

    this._load();
  }

  // ══════════════════════════════════════════
  //  MAIN CHECK — Called every 5 minutes
  // ══════════════════════════════════════════

  async check() {
    this.stats.checks++;
    this.lastCheck = new Date().toISOString();
    const alerts = [];

    // 1. Fetch S10 evolution status
    let evo = null;
    try {
      evo = await this.fetchEvolution();
      this.consecutiveFailures = 0;
    } catch (err) {
      this.consecutiveFailures++;
      logger.warn(`[WATCHDOG] S10 fetch failed (${this.consecutiveFailures}x): ${err.message}`);

      if (this.consecutiveFailures >= 3) {
        alerts.push(this._alert('CRITICAL', 's10_unreachable',
          `S10 unreachable for ${this.consecutiveFailures} consecutive checks`,
          { failures: this.consecutiveFailures }));

        // Auto-restart after 5 consecutive failures (only safe auto-action)
        if (this.consecutiveFailures === 5) {
          await this._restartS10();
        }
      }
    }

    if (!evo) {
      this._save();
      return alerts;
    }

    // Record metrics
    const observation = {
      timestamp: this.lastCheck,
      brier: evo.brier || evo.best_brier,
      generation: evo.generation,
      population: evo.population || evo.pop_size,
      features: evo.features || evo.selected_features,
      stagnation: evo.stagnation,
      mutationRate: evo.mutation_rate,
      roi: evo.roi,
      sharpe: evo.sharpe,
      status: evo.status,
    };
    this.metrics.push(observation);
    if (this.metrics.length > 500) this.metrics = this.metrics.slice(-500);
    this.stats.lastStatus = observation;

    // 2. Check for stagnation
    const stagnationAlert = this._checkStagnation(observation);
    if (stagnationAlert) alerts.push(stagnationAlert);

    // 3. Check for Brier regression
    const regressionAlert = this._checkRegression(observation);
    if (regressionAlert) alerts.push(regressionAlert);

    // 4. Check for feature bloat or collapse
    const featureAlert = this._checkFeatures(observation);
    if (featureAlert) alerts.push(featureAlert);

    // 5. Check population health
    const popAlert = this._checkPopulation(observation);
    if (popAlert) alerts.push(popAlert);

    // 6. Check space status
    if (observation.status && observation.status !== 'EVOLVING' && observation.status !== 'running') {
      alerts.push(this._alert('WARNING', 's10_not_evolving',
        `S10 status: ${observation.status} (expected EVOLVING)`,
        { status: observation.status }));
    }

    // Update tracking
    this.lastBrier = observation.brier;
    this.lastGeneration = observation.generation;

    // Save state
    this._save();

    // Send all alerts
    for (const alert of alerts) {
      await this._dispatch(alert);
    }

    return alerts;
  }

  // ══════════════════════════════════════════
  //  STATISTICAL CHECKS
  // ══════════════════════════════════════════

  _checkStagnation(obs) {
    if (!obs.generation) return null;

    // If generation hasn't changed in 30+ minutes (6+ checks at 5min interval)
    const recentObs = this.metrics.slice(-6);
    if (recentObs.length < 6) return null;

    const allSameGen = recentObs.every(o => o.generation === obs.generation);
    if (allSameGen) {
      return this._alert('WARNING', 'generation_stall',
        `Generation stuck at ${obs.generation} for 30+ min`,
        { generation: obs.generation, duration: '30+ min' });
    }

    // If Brier hasn't improved in 60+ minutes (12+ checks)
    const last12 = this.metrics.slice(-12);
    if (last12.length >= 12) {
      const oldBrier = last12[0].brier;
      const newBrier = obs.brier;
      if (oldBrier && newBrier && Math.abs(newBrier - oldBrier) < 0.0001) {
        return this._alert('WARNING', 'brier_plateau',
          `Brier unchanged at ${newBrier?.toFixed(4)} for 60+ min`,
          { brier: newBrier, duration: '60+ min' });
      }
    }

    // Explicit stagnation counter from S10
    if (obs.stagnation >= 8) {
      return this._alert('CRITICAL', 'high_stagnation',
        `S10 stagnation counter: ${obs.stagnation} (GA stuck)`,
        { stagnation: obs.stagnation, brier: obs.brier });
    }

    return null;
  }

  _checkRegression(obs) {
    if (!obs.brier || !this.lastBrier) return null;

    // Brier increased by more than 0.005 since last check
    const delta = obs.brier - this.lastBrier;
    if (delta > 0.005) {
      return this._alert('WARNING', 'brier_regression',
        `Brier regressed: ${this.lastBrier?.toFixed(4)} → ${obs.brier?.toFixed(4)} (+${delta.toFixed(4)})`,
        { prev: this.lastBrier, curr: obs.brier, delta });
    }

    // Check longer-term regression (1 hour)
    const hourAgo = this.metrics.slice(-12);
    if (hourAgo.length >= 12) {
      const hourDelta = obs.brier - hourAgo[0].brier;
      if (hourDelta > 0.01) {
        return this._alert('CRITICAL', 'brier_regression_1h',
          `Brier regressed over 1h: ${hourAgo[0].brier?.toFixed(4)} → ${obs.brier?.toFixed(4)} (+${hourDelta.toFixed(4)})`,
          { prev1h: hourAgo[0].brier, curr: obs.brier, delta: hourDelta });
      }
    }

    return null;
  }

  _checkFeatures(obs) {
    if (!obs.features) return null;

    if (obs.features > 200) {
      return this._alert('WARNING', 'feature_bloat',
        `Feature count high: ${obs.features} (risk of overfitting)`,
        { features: obs.features });
    }

    if (obs.features < 20) {
      return this._alert('WARNING', 'feature_collapse',
        `Feature count dangerously low: ${obs.features}`,
        { features: obs.features });
    }

    return null;
  }

  _checkPopulation(obs) {
    if (!obs.population) return null;

    if (obs.population < 20) {
      return this._alert('CRITICAL', 'population_collapse',
        `Population collapsed to ${obs.population} — evolution may be stuck`,
        { population: obs.population });
    }

    return null;
  }

  // ══════════════════════════════════════════
  //  ALERT SYSTEM
  // ══════════════════════════════════════════

  _alert(level, type, message, data = {}) {
    const alert = {
      level,
      type,
      message,
      data,
      timestamp: new Date().toISOString(),
    };

    this.alerts.push(alert);
    if (this.alerts.length > 200) this.alerts = this.alerts.slice(-200);

    logger.info(`[WATCHDOG] ${level}: ${message}`);
    return alert;
  }

  async _dispatch(alert) {
    this.stats.alertsSent++;

    // Post to A2A inbox (for Adam to see)
    if (this.a2a) {
      this.a2a.postReport({
        type: 'watchdog_alert',
        level: alert.level,
        alert: alert.type,
        message: alert.message,
        data: alert.data,
      });
    }

    // Telegram for CRITICAL alerts only
    if (alert.level === 'CRITICAL' && this.bot) {
      const icon = '🚨';
      const msg = `${icon} *WATCHDOG ${alert.level}*\n${alert.message}`;
      try {
        await this.bot.sendMessage(this.adminId, msg, { parse_mode: 'Markdown' });
      } catch (e) {
        logger.warn(`[WATCHDOG] Telegram send failed: ${e.message}`);
      }
    }
  }

  // ══════════════════════════════════════════
  //  AUTO-ACTIONS (minimal, safe only)
  // ══════════════════════════════════════════

  async _restartS10() {
    logger.warn('[WATCHDOG] Auto-restarting S10 after 5 consecutive failures');
    try {
      if (this.spaces) {
        await this.spaces.deployToSpace('S10');
        this.stats.spacesRestarted++;
        if (this.bot) {
          await this.bot.sendMessage(this.adminId,
            '🔄 *WATCHDOG*: Auto-restarted S10 after 5 consecutive failures',
            { parse_mode: 'Markdown' }).catch(() => {});
        }
      }
    } catch (err) {
      logger.error(`[WATCHDOG] S10 restart failed: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  SPACE HEALTH CHECK (all 5 spaces)
  // ══════════════════════════════════════════

  async checkAllSpaces() {
    if (!this.spaces) return {};

    const results = await this.spaces.healthCheckAll();
    const down = [];

    for (const [id, status] of Object.entries(results)) {
      if (!status.up && id !== 'worker-2') { // Don't check self
        down.push(id);
      }
    }

    if (down.length > 0) {
      const alert = this._alert('WARNING', 'spaces_down',
        `${down.length} space(s) down: ${down.join(', ')}`,
        { down });
      await this._dispatch(alert);
    }

    return results;
  }

  // ══════════════════════════════════════════
  //  TRENDS — Compute metrics over time
  // ══════════════════════════════════════════

  getTrends() {
    if (this.metrics.length < 2) return null;

    const recent = this.metrics.slice(-12); // Last hour
    const older = this.metrics.slice(-24, -12); // Hour before

    const avg = (arr, key) => {
      const valid = arr.filter(o => o[key] != null);
      return valid.length > 0 ? valid.reduce((s, o) => s + o[key], 0) / valid.length : null;
    };

    return {
      current: {
        brier: recent[recent.length - 1]?.brier,
        generation: recent[recent.length - 1]?.generation,
        features: recent[recent.length - 1]?.features,
        population: recent[recent.length - 1]?.population,
        stagnation: recent[recent.length - 1]?.stagnation,
      },
      avgLastHour: {
        brier: avg(recent, 'brier'),
        features: avg(recent, 'features'),
      },
      avgPrevHour: {
        brier: avg(older, 'brier'),
        features: avg(older, 'features'),
      },
      brierTrend: (avg(recent, 'brier') && avg(older, 'brier'))
        ? +(avg(recent, 'brier') - avg(older, 'brier')).toFixed(5)
        : null,
      totalObservations: this.metrics.length,
      alertsLast24h: this.alerts.filter(a =>
        new Date(a.timestamp) > new Date(Date.now() - 24 * 60 * 60 * 1000)
      ).length,
    };
  }

  // ══════════════════════════════════════════
  //  STATUS
  // ══════════════════════════════════════════

  getStatus() {
    return {
      lastCheck: this.lastCheck,
      consecutiveFailures: this.consecutiveFailures,
      stats: this.stats,
      trends: this.getTrends(),
      recentAlerts: this.alerts.slice(-10),
      metricsCount: this.metrics.length,
    };
  }

  // ══════════════════════════════════════════
  //  PERSISTENCE
  // ══════════════════════════════════════════

  _load() {
    try {
      const dir = '/data/watchdog';
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

      if (fs.existsSync(STATE_FILE)) {
        const saved = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
        this.alerts = saved.alerts || [];
        this.stats = { ...this.stats, ...saved.stats };
        this.lastBrier = saved.lastBrier;
        this.lastGeneration = saved.lastGeneration;
      }
      if (fs.existsSync(METRICS_FILE)) {
        this.metrics = JSON.parse(fs.readFileSync(METRICS_FILE, 'utf8'));
      }
    } catch (e) {
      logger.warn(`[WATCHDOG] Load state: ${e.message}`);
    }
  }

  _save() {
    try {
      fs.writeFileSync(STATE_FILE, JSON.stringify({
        alerts: this.alerts.slice(-200),
        stats: this.stats,
        lastBrier: this.lastBrier,
        lastGeneration: this.lastGeneration,
      }, null, 2));
      fs.writeFileSync(METRICS_FILE, JSON.stringify(this.metrics));
    } catch (e) {
      logger.warn(`[WATCHDOG] Save state: ${e.message}`);
    }
  }
}

module.exports = Watchdog;
