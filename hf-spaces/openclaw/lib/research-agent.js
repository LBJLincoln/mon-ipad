/**
 * Research Agent — Autonomous NBA Quant Research
 *
 * Eve discovers new techniques, papers, and approaches to improve
 * the NBA prediction model. Quota-aware search strategy.
 *
 * Search strategy:
 *   - Brave Search: 2000 queries/month → ~65/day. Skip if exhausted.
 *   - When web search exhausted: use LLM's own knowledge.
 *   - Generate targeted queries based on current system weaknesses.
 *
 * Research cycle: Every 12 hours (2x/day)
 */

const logger = require('./logger');

class ResearchAgent {
  constructor({ getCompletion, infraBridge, a2a, bot, adminId }) {
    this.getCompletion = getCompletion;
    this.infra = infraBridge;
    this.a2a = a2a;
    this.bot = bot;
    this.adminId = adminId;

    this.findings = [];         // In-memory recent findings
    this.lastResearch = null;
    this.stats = {
      cyclesRun: 0,
      findingsTotal: 0,
      webSearches: 0,
      llmAnalyses: 0,
      lastError: null,
    };

    this._ensureTable().catch(e => logger.warn(`[RESEARCH] Table init: ${e.message}`));
  }

  async _ensureTable() {
    if (!this.infra?.pgPool) return;

    const client = await this.infra.pgPool.connect();
    try {
      await client.query('SET search_path TO public');
      await client.query(`
        CREATE TABLE IF NOT EXISTS nba_research_findings (
          id SERIAL PRIMARY KEY,
          topic TEXT NOT NULL,
          finding TEXT NOT NULL,
          source TEXT,
          relevance REAL,
          actionable BOOLEAN DEFAULT FALSE,
          created_at TIMESTAMPTZ DEFAULT NOW()
        )
      `);
      logger.info('[RESEARCH] Table ensured: nba_research_findings');
    } finally {
      client.release();
    }
  }

  // ══════════════════════════════════════════
  //  RESEARCH CYCLE — Main entry point
  // ══════════════════════════════════════════

  async researchCycle(context = {}) {
    this.lastResearch = new Date().toISOString();
    this.stats.cyclesRun++;

    try {
      // 1. Generate targeted research queries based on current weaknesses
      const queries = this._generateQueries(context);

      // 2. Try web search first (if available)
      let webResults = [];
      const braveKey = process.env.BRAVE_SEARCH_API_KEY;
      if (braveKey) {
        for (const q of queries.slice(0, 2)) {  // Max 2 web searches per cycle
          const results = await this.searchWeb(q, braveKey);
          if (results) {
            webResults.push({ query: q, results });
            this.stats.webSearches++;
          }
        }
      }

      // 3. Analyze findings with LLM (always works — uses free models)
      const analysis = await this._analyzeWithLLM(queries, webResults, context);
      this.stats.llmAnalyses++;

      // 4. Extract and store findings
      if (analysis) {
        await this._storeFindings(analysis);
        await this._reportFindings(analysis);
      }

      return analysis;
    } catch (err) {
      this.stats.lastError = `${err.message} @ ${this.lastResearch}`;
      logger.error(`[RESEARCH] Cycle failed: ${err.message}`);
      return null;
    }
  }

  // ══════════════════════════════════════════
  //  QUERY GENERATION — Weakness-targeted
  // ══════════════════════════════════════════

  _generateQueries(context) {
    const queries = [];
    const brier = context.brier || context.evolution?.brier;
    const features = context.features || context.evolution?.features;
    const accuracy = context.accuracy;
    const stagnation = context.stagnation || context.evolution?.stagnation;

    // Base query always included
    queries.push('NBA prediction model calibration techniques 2025 2026 Brier score improvement');

    // Weakness-specific queries
    if (brier && brier > 0.22) {
      queries.push('improve NBA game prediction calibration below 0.20 Brier score methods');
    }

    if (features && features > 150) {
      queries.push('feature selection methods sports prediction reducing overfitting XGBoost');
    } else if (features && features < 40) {
      queries.push('NBA advanced statistics features predictive power player impact metrics');
    }

    if (accuracy && accuracy < 0.62) {
      queries.push('NBA home court advantage modeling rest days schedule factors prediction');
    }

    if (stagnation && stagnation >= 5) {
      queries.push('genetic algorithm stagnation escape techniques parameter optimization');
    }

    // Always include one forward-looking query
    queries.push('state of the art sports betting prediction models machine learning 2026');

    return queries.slice(0, 4);  // Max 4 queries per cycle
  }

  // ══════════════════════════════════════════
  //  WEB SEARCH — Brave API (quota-aware)
  // ══════════════════════════════════════════

  async searchWeb(query, apiKey) {
    if (!apiKey) return null;

    try {
      const url = `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=5`;
      const resp = await fetch(url, {
        headers: { 'X-Subscription-Token': apiKey },
        signal: AbortSignal.timeout(10000),
      });

      if (resp.status === 429) {
        logger.warn('[RESEARCH] Brave Search quota exhausted');
        return null;
      }

      if (!resp.ok) {
        logger.warn(`[RESEARCH] Brave Search ${resp.status}`);
        return null;
      }

      const data = await resp.json();
      return (data.web?.results || []).slice(0, 5).map(r => ({
        title: r.title,
        description: r.description,
        url: r.url,
      }));
    } catch (err) {
      logger.warn(`[RESEARCH] Web search failed: ${err.message}`);
      return null;
    }
  }

  // ══════════════════════════════════════════
  //  LLM ANALYSIS — Extract actionable insights
  // ══════════════════════════════════════════

  async _analyzeWithLLM(queries, webResults, context) {
    const webContext = webResults.length > 0
      ? `\n\nWEB SEARCH RESULTS:\n${webResults.map(wr =>
          `Query: "${wr.query}"\n${wr.results.map(r => `- ${r.title}: ${r.description}`).join('\n')}`
        ).join('\n\n')}`
      : '\n\nNo web search results available (quota exhausted). Use your training knowledge.';

    const systemContext = context.brier
      ? `Current model: Brier ${context.brier}, accuracy ${context.accuracy || '?'}, features ${context.features || '?'}`
      : 'No current model metrics available.';

    const prompt = `You are a research analyst for an NBA prediction quant model.
${systemContext}

Research queries explored: ${queries.join('; ')}
${webContext}

Based on the above, provide exactly 3 ACTIONABLE findings that could improve our NBA prediction model.

For each finding, output this exact format:
FINDING 1:
TOPIC: [specific topic in 5 words]
INSIGHT: [what we should do, in 2-3 sentences, with specific numbers/techniques]
ACTIONABLE: [yes/no]
RELEVANCE: [0.0-1.0 how relevant to improving Brier < 0.20]

FINDING 2:
...

FINDING 3:
...

Be specific. No vague advice. Mention concrete techniques, parameters, or features.`;

    try {
      const result = await this.getCompletion([{ role: 'user', content: prompt }], {
        maxTokens: 1000,
        temperature: 0.5,
      });

      if (!result?.content) return null;

      // Parse findings from LLM output
      return this._parseFindings(result.content, result.model);
    } catch (err) {
      logger.warn(`[RESEARCH] LLM analysis failed: ${err.message}`);
      return null;
    }
  }

  _parseFindings(text, model) {
    const findings = [];
    const blocks = text.split(/FINDING \d+:/i).filter(b => b.trim());

    for (const block of blocks) {
      const topicMatch = block.match(/TOPIC:\s*(.+)/i);
      const insightMatch = block.match(/INSIGHT:\s*(.+?)(?=ACTIONABLE:|RELEVANCE:|FINDING|$)/is);
      const actionableMatch = block.match(/ACTIONABLE:\s*(yes|no)/i);
      const relevanceMatch = block.match(/RELEVANCE:\s*([\d.]+)/i);

      if (topicMatch && insightMatch) {
        findings.push({
          topic: topicMatch[1].trim(),
          finding: insightMatch[1].trim(),
          actionable: actionableMatch ? actionableMatch[1].toLowerCase() === 'yes' : false,
          relevance: relevanceMatch ? parseFloat(relevanceMatch[1]) : 0.5,
          source: model || 'llm',
          timestamp: new Date().toISOString(),
        });
      }
    }

    return findings.length > 0 ? findings : null;
  }

  // ══════════════════════════════════════════
  //  STORE FINDINGS
  // ══════════════════════════════════════════

  async _storeFindings(findings) {
    for (const f of findings) {
      this.findings.push(f);
      this.stats.findingsTotal++;
    }
    if (this.findings.length > 100) this.findings = this.findings.slice(-100);

    if (!this.infra?.pgPool) return;

    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');
        for (const f of findings) {
          await client.query(`
            INSERT INTO nba_research_findings (topic, finding, source, relevance, actionable)
            VALUES ($1, $2, $3, $4, $5)
          `, [f.topic, f.finding, f.source, f.relevance, f.actionable]);
        }
      } finally {
        client.release();
      }
    } catch (e) {
      logger.warn(`[RESEARCH] Store findings: ${e.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  REPORT FINDINGS
  // ══════════════════════════════════════════

  async _reportFindings(findings) {
    if (!findings || findings.length === 0) return;

    // A2A
    if (this.a2a) {
      this.a2a.postReport({
        type: 'research_findings',
        level: 'INFO',
        message: `Research cycle: ${findings.length} findings`,
        data: { findings },
      });
    }

    // Telegram (only actionable findings)
    const actionable = findings.filter(f => f.actionable);
    if (actionable.length > 0 && this.bot) {
      const lines = [
        `🔬 *RESEARCH FINDINGS* (${actionable.length} actionable)`,
        '',
      ];
      for (const f of actionable) {
        lines.push(`*${f.topic}* (relevance: ${f.relevance})`);
        lines.push(`${f.finding.substring(0, 200)}`);
        lines.push('');
      }

      try {
        await this.bot.sendMessage(this.adminId, lines.join('\n'), { parse_mode: 'Markdown' });
      } catch (e) {
        logger.warn(`[RESEARCH] Telegram send: ${e.message}`);
      }
    }
  }

  // ══════════════════════════════════════════
  //  QUERIES
  // ══════════════════════════════════════════

  getFindings(limit = 20) {
    return this.findings.slice(-limit);
  }

  getStatus() {
    return {
      lastResearch: this.lastResearch,
      stats: this.stats,
      recentFindings: this.findings.slice(-5),
    };
  }
}

module.exports = ResearchAgent;
