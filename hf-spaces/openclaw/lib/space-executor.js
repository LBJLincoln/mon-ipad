/**
 * SpaceExecutor — Execute operations across all 14 HF Spaces
 *
 * This is the core bridge that gives OpenClaw the same capabilities
 * as Claude Code CLI running on the VM. It can:
 * - Query any RAG pipeline via webhooks
 * - Trigger evaluations
 * - Deploy workflows via n8n API
 * - Get Space logs via HF Hub API
 * - Trigger ingestion pipelines
 * - Health-check all Spaces
 */

const https = require('https');
const http = require('http');
const logger = require('./logger');

class SpaceExecutor {
  constructor(spacesConfig, credentials) {
    this.spaces = {};
    this.webhooks = spacesConfig.webhooks;
    this.evalQuestions = spacesConfig.evalQuestions;

    for (const space of spacesConfig.spaces) {
      this.spaces[space.id] = space;
    }

    this.hfToken = credentials.hfToken;
    this.hfToken2 = credentials.hfToken2;
    this.litellmUrl = credentials.litellmUrl;
    this.litellmKey = credentials.litellmKey;
  }

  /**
   * Get the URL for a space by ID or name
   */
  resolveSpace(nameOrId) {
    const key = nameOrId.toUpperCase();
    if (this.spaces[key]) return this.spaces[key];

    // Search by name
    const found = Object.values(this.spaces).find(s =>
      s.name.toLowerCase().includes(nameOrId.toLowerCase()) ||
      s.id.toLowerCase() === nameOrId.toLowerCase()
    );
    return found || null;
  }

  /**
   * Make an HTTP request to a URL
   */
  async httpRequest(url, options = {}) {
    return new Promise((resolve, reject) => {
      const parsedUrl = new URL(url);
      const isHttps = parsedUrl.protocol === 'https:';
      const lib = isHttps ? https : http;

      const reqOptions = {
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (isHttps ? 443 : 80),
        path: parsedUrl.pathname + parsedUrl.search,
        method: options.method || 'GET',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'OpenClaw/2026.3.11',
          ...(options.headers || {}),
        },
        timeout: options.timeout || 60000,
      };

      const req = lib.request(reqOptions, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            resolve({
              status: res.statusCode,
              data: data ? JSON.parse(data) : null,
              raw: data,
            });
          } catch {
            resolve({ status: res.statusCode, data: null, raw: data });
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timeout after ${reqOptions.timeout}ms`));
      });

      if (options.body) {
        req.write(typeof options.body === 'string' ? options.body : JSON.stringify(options.body));
      }

      req.end();
    });
  }

  /**
   * Ping a single Space
   */
  async pingSpace(spaceId) {
    const space = this.resolveSpace(spaceId);
    if (!space) throw new Error(`Space not found: ${spaceId}`);

    const start = Date.now();
    try {
      const res = await this.httpRequest(space.url, { timeout: 15000 });
      return {
        up: res.status < 500,
        latency: Date.now() - start,
        status: res.status,
      };
    } catch (err) {
      return { up: false, latency: Date.now() - start, error: err.message };
    }
  }

  /**
   * Health check all Spaces
   */
  async healthCheckAll() {
    const results = {};
    const checks = Object.keys(this.spaces).map(async (id) => {
      results[id] = await this.pingSpace(id);
    });
    await Promise.allSettled(checks);
    return results;
  }

  /**
   * Execute a webhook on a Space
   */
  async executeWebhook(spaceId, webhookPath, body = {}) {
    const space = this.resolveSpace(spaceId);
    if (!space) throw new Error(`Space not found: ${spaceId}`);

    const url = `${space.url}${webhookPath}`;
    logger.info(`Executing webhook: ${url}`);

    const res = await this.httpRequest(url, {
      method: 'POST',
      body: body,
      timeout: 120000, // 2min for RAG pipelines
    });

    if (res.status >= 400) {
      throw new Error(`Webhook ${res.status}: ${res.raw?.substring(0, 200)}`);
    }

    return res.data || res.raw;
  }

  /**
   * Query a RAG pipeline
   */
  async queryPipeline(pipeline, question, sector = 'finance') {
    const webhookPath = this.webhooks[pipeline];
    if (!webhookPath) throw new Error(`Unknown pipeline: ${pipeline}`);

    const body = {
      question: question,
      query: question,
      sector: sector,
      tenant_id: sector,
      top_k: 5,
    };

    // Try S1 first, then S3, S5 as fallback
    const spaceOrder = ['S1', 'S3', 'S5'];
    let lastError;

    for (const spaceId of spaceOrder) {
      try {
        const result = await this.executeWebhook(spaceId, webhookPath, body);
        return {
          answer: result.answer || result.response || result.interpretation || result.output,
          pipeline: pipeline,
          space: spaceId,
          sources: result.sources || result.context || [],
          raw: result,
        };
      } catch (err) {
        lastError = err;
        logger.warn(`Pipeline ${pipeline} failed on ${spaceId}: ${err.message}`);
      }
    }

    throw lastError || new Error('All spaces failed');
  }

  /**
   * Run an eval batch
   */
  async runEval(pipeline, count = 5) {
    const questions = this.evalQuestions?.standard || [];
    const subset = questions.slice(0, Math.min(count, questions.length));

    const results = [];
    let passed = 0;

    for (const q of subset) {
      try {
        const start = Date.now();
        const result = await this.queryPipeline(
          pipeline === 'orchestrator' ? 'orchestrator' : pipeline,
          q.question,
          q.sector
        );
        const latency = Date.now() - start;
        const hasAnswer = !!(result.answer && result.answer.length > 20);

        if (hasAnswer) passed++;
        results.push({
          question: q.question,
          sector: q.sector,
          passed: hasAnswer,
          latency,
          answerLength: result.answer?.length || 0,
        });
      } catch (err) {
        results.push({
          question: q.question,
          sector: q.sector,
          passed: false,
          error: err.message,
        });
      }
    }

    const total = results.length;
    const avgLatency = results
      .filter(r => r.latency)
      .reduce((sum, r) => sum + r.latency, 0) / (results.filter(r => r.latency).length || 1);

    return {
      pipeline,
      total,
      passed,
      accuracy: total > 0 ? Math.round((passed / total) * 100) : 0,
      avgLatency: Math.round(avgLatency),
      results,
      failures: results.filter(r => !r.passed),
    };
  }

  /**
   * Get Space logs via HF Hub API
   */
  async getSpaceLogs(spaceId) {
    const space = this.resolveSpace(spaceId);
    if (!space) throw new Error(`Space not found: ${spaceId}`);

    const token = this.getTokenForSpace(space);
    const url = `https://huggingface.co/api/spaces/${space.hfId}/logs`;

    try {
      const res = await this.httpRequest(url, {
        headers: { 'Authorization': `Bearer ${token}` },
        timeout: 15000,
      });
      return res.raw || 'No logs available';
    } catch (err) {
      return `Failed to get logs: ${err.message}`;
    }
  }

  /**
   * Deploy to a Space (restart or update)
   */
  async deployToSpace(spaceId) {
    const space = this.resolveSpace(spaceId);
    if (!space) throw new Error(`Space not found: ${spaceId}`);

    const token = this.getTokenForSpace(space);

    // Factory reset (restart) the Space
    const url = `https://huggingface.co/api/spaces/${space.hfId}/restart`;
    try {
      const res = await this.httpRequest(url, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        timeout: 30000,
      });
      return { status: 'restarted', space: spaceId, response: res.status };
    } catch (err) {
      return { status: 'failed', space: spaceId, error: err.message };
    }
  }

  /**
   * Trigger ingestion on S9
   */
  async triggerIngestion(sector) {
    try {
      const result = await this.executeWebhook('S9', '/webhook/ingest-trigger', {
        sector: sector,
        batch_size: 10,
        source: 'openclaw',
      });
      return { status: 'triggered', sector, result };
    } catch (err) {
      return { status: 'failed', sector, error: err.message };
    }
  }

  /**
   * Get the correct HF token for a space's account
   */
  getTokenForSpace(space) {
    if (space.account === 'lbjlincoln26') return this.hfToken2;
    if (space.account === 'nomos42') return this.hfToken;  // litellm-2 (legacy)
    return this.hfToken2; // Default to main account (lbjlincoln)
  }
}

module.exports = SpaceExecutor;
