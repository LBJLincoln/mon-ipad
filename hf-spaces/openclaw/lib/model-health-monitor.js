/**
 * Model Health Monitor — NEVER let OpenClaw stop thinking
 *
 * Probes ALL free OpenRouter models periodically.
 * Maintains a live ranked list of working models.
 * Auto-rotates when a model goes down.
 *
 * OpenRouter has 20+ free models at any time.
 * At least 3-5 are always responsive.
 * This monitor ensures getCompletion() ALWAYS has a working model.
 *
 * Cycle: every 10 min, probe all known free models with a tiny completion.
 * On failure during real use: immediately mark dead, try next in list.
 */

const logger = require('./logger');

// ── All known OpenRouter free models (updated 2026-03) ──
// This list is refreshed dynamically via OpenRouter /models API
const KNOWN_FREE_MODELS = [
  'nvidia/nemotron-3-super-120b-a12b:free',
  'arcee-ai/trinity-large-preview:free',
  'google/gemma-3-27b-it:free',
  'google/gemma-3-12b-it:free',
  'google/gemma-3-4b-it:free',
  'mistralai/mistral-small-3.1-24b-instruct:free',
  'qwen/qwen3-235b-a22b:free',
  'qwen/qwen3-32b:free',
  'qwen/qwen3-30b-a3b:free',
  'qwen/qwen3-14b:free',
  'qwen/qwen3-8b:free',
  'qwen/qwen3-4b:free',
  'qwen/qwen3-1.7b:free',
  'qwen/qwen3-0.6b:free',
  'qwen/qwen-2.5-coder-32b-instruct:free',
  'deepseek/deepseek-chat-v3-0324:free',
  'deepseek/deepseek-r1-0528:free',
  'meta-llama/llama-4-maverick:free',
  'meta-llama/llama-4-scout:free',
  'meta-llama/llama-3.3-70b-instruct:free',
  'microsoft/phi-4-reasoning-plus:free',
  'microsoft/phi-4-reasoning:free',
  'microsoft/mai-ds-r1:free',
  'moonshotai/kimi-vl-a3b-thinking:free',
  'nousresearch/deephermes-3-llama-3-8b-preview:free',
  'open-r1/olympiccoder-32b:free',
  'rekaai/reka-flash-3:free',
  'allenai/molmo-7b-d-0924:free',
];

// Minimum quality models for NBA quant analysis (need reasoning ability)
const PREFERRED_MODELS = [
  'deepseek/deepseek-r1-0528:free',
  'deepseek/deepseek-chat-v3-0324:free',
  'qwen/qwen3-235b-a22b:free',
  'qwen/qwen3-32b:free',
  'nvidia/nemotron-3-super-120b-a12b:free',
  'meta-llama/llama-4-maverick:free',
  'meta-llama/llama-4-scout:free',
  'meta-llama/llama-3.3-70b-instruct:free',
  'microsoft/phi-4-reasoning-plus:free',
  'mistralai/mistral-small-3.1-24b-instruct:free',
  'google/gemma-3-27b-it:free',
  'arcee-ai/trinity-large-preview:free',
  'rekaai/reka-flash-3:free',
];

const PROBE_MESSAGE = [
  { role: 'user', content: 'Reply with exactly: OK' }
];

class ModelHealthMonitor {
  constructor({ openrouterApiKey, openrouterClient, litellmUrl, litellmKey, bot, adminId }) {
    this.apiKey = openrouterApiKey;
    this.openrouter = openrouterClient;
    this.litellmUrl = litellmUrl;
    this.litellmKey = litellmKey;
    this.bot = bot;
    this.adminId = adminId;

    // Live model health state
    this.models = {};
    for (const model of KNOWN_FREE_MODELS) {
      this.models[model] = {
        id: model,
        alive: null,        // null = untested, true/false
        lastCheck: null,
        lastSuccess: null,
        latency: null,       // ms
        failCount: 0,
        successCount: 0,
        preferred: PREFERRED_MODELS.includes(model),
      };
    }

    // LiteLLM health
    this.litellm = {
      alive: null,
      lastCheck: null,
      failCount: 0,
    };

    // Sorted list of working models (best first)
    this.aliveModels = [];
    this.lastFullProbe = null;
    this.probeInterval = null;
    this.totalProbes = 0;
    this.switchCount = 0;
  }

  // ══════════════════════════════════════════
  //  START — Begin periodic probing
  // ══════════════════════════════════════════

  start() {
    // Probe immediately on start
    this._probeAll().catch(e => logger.warn('Initial probe error:', e.message));

    // Then every 10 min
    this.probeInterval = setInterval(() => {
      this._probeAll().catch(e => logger.warn('Probe error:', e.message));
    }, 10 * 60 * 1000);

    logger.info(`[MODEL-MONITOR] Started — tracking ${KNOWN_FREE_MODELS.length} free models`);
  }

  stop() {
    if (this.probeInterval) clearInterval(this.probeInterval);
  }

  // ══════════════════════════════════════════
  //  GET ALIVE MODELS — Sorted by quality
  // ══════════════════════════════════════════

  /**
   * Returns ordered list of working model IDs.
   * Preferred models first, then by latency.
   */
  getAliveModels() {
    return this.aliveModels;
  }

  /**
   * Returns the best available model right now.
   */
  getBestModel() {
    return this.aliveModels[0] || PREFERRED_MODELS[0];
  }

  /**
   * Mark a model as failed (called when getCompletion fails with it).
   * Immediately removes from alive list so next call uses a different model.
   */
  markFailed(modelId) {
    const model = this.models[modelId];
    if (model) {
      model.alive = false;
      model.failCount++;
      logger.warn(`[MODEL-MONITOR] ${modelId} marked FAILED (total fails: ${model.failCount})`);
    }
    this._rebuildAliveList();
  }

  /**
   * Mark a model as working (called when getCompletion succeeds).
   */
  markAlive(modelId) {
    const model = this.models[modelId];
    if (model) {
      model.alive = true;
      model.lastSuccess = new Date().toISOString();
      model.successCount++;
      if (model.failCount > 0) model.failCount = Math.max(0, model.failCount - 1);
    }
    this._rebuildAliveList();
  }

  // ══════════════════════════════════════════
  //  PROBE — Test all models
  // ══════════════════════════════════════════

  async _probeAll() {
    this.totalProbes++;
    this.lastFullProbe = new Date().toISOString();
    logger.info(`[MODEL-MONITOR] Full probe #${this.totalProbes} — testing ${KNOWN_FREE_MODELS.length} models...`);

    // First check LiteLLM
    await this._probeLiteLLM();

    // Probe preferred models first (parallel, batches of 5)
    const allModels = [...PREFERRED_MODELS, ...KNOWN_FREE_MODELS.filter(m => !PREFERRED_MODELS.includes(m))];
    const batchSize = 5;

    for (let i = 0; i < allModels.length; i += batchSize) {
      const batch = allModels.slice(i, i + batchSize);
      await Promise.all(batch.map(m => this._probeModel(m)));

      // If we have 5+ alive preferred models, skip the rest
      const alivePreferred = PREFERRED_MODELS.filter(m => this.models[m]?.alive === true);
      if (alivePreferred.length >= 5 && i >= PREFERRED_MODELS.length) break;
    }

    this._rebuildAliveList();

    const alive = this.aliveModels.length;
    const total = Object.keys(this.models).length;
    logger.info(`[MODEL-MONITOR] Probe complete: ${alive}/${total} alive. Best: ${this.aliveModels[0] || 'NONE'}`);

    // Alert if very few models available
    if (alive <= 2 && this.bot && this.adminId) {
      this.bot.sendMessage(this.adminId,
        `⚠️ *Model Alert*: Only ${alive} free models alive!\n${this.aliveModels.join('\n') || 'NONE'}`,
        { parse_mode: 'Markdown' }
      ).catch(() => {});
    }

    return this.aliveModels;
  }

  async _probeModel(modelId) {
    const model = this.models[modelId];
    if (!model) return;

    model.lastCheck = new Date().toISOString();
    const start = Date.now();

    try {
      const completion = await this.openrouter.chat.completions.create({
        model: modelId,
        messages: PROBE_MESSAGE,
        max_tokens: 5,
        temperature: 0,
        stream: false,
      });

      const latency = Date.now() - start;
      const content = completion.choices?.[0]?.message?.content || '';

      if (content.length > 0) {
        model.alive = true;
        model.latency = latency;
        model.lastSuccess = new Date().toISOString();
        model.successCount++;
        model.failCount = Math.max(0, model.failCount - 1);
      } else {
        model.alive = false;
        model.failCount++;
      }
    } catch (err) {
      model.alive = false;
      model.failCount++;
      model.latency = null;
    }
  }

  async _probeLiteLLM() {
    if (!this.litellmUrl) return;

    this.litellm.lastCheck = new Date().toISOString();

    try {
      const resp = await fetch(this.litellmUrl, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.litellmKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'fast',
          messages: PROBE_MESSAGE,
          max_tokens: 5,
        }),
        signal: AbortSignal.timeout(15000),
      });
      const data = await resp.json();
      this.litellm.alive = !!(data.choices && data.choices[0]?.message?.content);
      if (this.litellm.alive) this.litellm.failCount = 0;
      else this.litellm.failCount++;
    } catch {
      this.litellm.alive = false;
      this.litellm.failCount++;
    }
  }

  // ══════════════════════════════════════════
  //  REBUILD — Sort alive models by quality
  // ══════════════════════════════════════════

  _rebuildAliveList() {
    const alive = Object.values(this.models)
      .filter(m => m.alive === true)
      .sort((a, b) => {
        // Preferred first
        if (a.preferred && !b.preferred) return -1;
        if (!a.preferred && b.preferred) return 1;
        // Then by success rate
        const aRate = a.successCount / (a.successCount + a.failCount + 1);
        const bRate = b.successCount / (b.successCount + b.failCount + 1);
        if (bRate !== aRate) return bRate - aRate;
        // Then by latency
        return (a.latency || 99999) - (b.latency || 99999);
      });

    const oldBest = this.aliveModels[0];
    this.aliveModels = alive.map(m => m.id);
    if (oldBest && this.aliveModels[0] && oldBest !== this.aliveModels[0]) {
      this.switchCount++;
      logger.info(`[MODEL-MONITOR] Model switch #${this.switchCount}: ${oldBest} → ${this.aliveModels[0]}`);
    }
  }

  // ══════════════════════════════════════════
  //  DYNAMIC MODEL DISCOVERY — Fetch from OpenRouter API
  // ══════════════════════════════════════════

  async discoverFreeModels() {
    try {
      const resp = await fetch('https://openrouter.ai/api/v1/models', {
        headers: this.apiKey ? { 'Authorization': `Bearer ${this.apiKey}` } : {},
        signal: AbortSignal.timeout(15000),
      });
      const data = await resp.json();
      if (!data.data) return;

      let discovered = 0;
      for (const model of data.data) {
        const id = model.id;
        // Check if it's a free model
        const isFree = id.endsWith(':free') ||
          (model.pricing?.prompt === '0' && model.pricing?.completion === '0');

        if (isFree && !this.models[id]) {
          this.models[id] = {
            id,
            alive: null,
            lastCheck: null,
            lastSuccess: null,
            latency: null,
            failCount: 0,
            successCount: 0,
            preferred: false,
            discovered: true, // dynamically discovered
          };
          discovered++;
        }
      }

      if (discovered > 0) {
        logger.info(`[MODEL-MONITOR] Discovered ${discovered} new free models from OpenRouter API`);
      }
    } catch (err) {
      logger.warn(`[MODEL-MONITOR] Model discovery failed: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  STATUS — For API/dashboard
  // ══════════════════════════════════════════

  getStatus() {
    const aliveCount = Object.values(this.models).filter(m => m.alive === true).length;
    const deadCount = Object.values(this.models).filter(m => m.alive === false).length;
    const untested = Object.values(this.models).filter(m => m.alive === null).length;

    return {
      alive: aliveCount,
      dead: deadCount,
      untested,
      total: Object.keys(this.models).length,
      bestModel: this.aliveModels[0] || 'NONE',
      top5: this.aliveModels.slice(0, 5),
      litellm: this.litellm,
      lastProbe: this.lastFullProbe,
      totalProbes: this.totalProbes,
      switchCount: this.switchCount,
      models: Object.values(this.models).map(m => ({
        id: m.id,
        alive: m.alive,
        latency: m.latency,
        preferred: m.preferred,
        failCount: m.failCount,
        successCount: m.successCount,
      })).sort((a, b) => {
        if (a.alive && !b.alive) return -1;
        if (!a.alive && b.alive) return 1;
        return (a.latency || 99999) - (b.latency || 99999);
      }),
    };
  }
}

module.exports = ModelHealthMonitor;
