/**
 * Agent Executor — ReAct (Reason + Act) Tool-Calling Loop
 *
 * Transforms OpenClaw from a dumb chat proxy into a REAL agentic system.
 * The LLM can call tools (search, browse, DB, SSH, GitHub, NBA data)
 * and iterate until it has a final answer.
 *
 * Uses OpenAI-compatible function-calling format.
 * Compatible with OpenRouter models, Kimi, Gemini, GPT-4.
 *
 * Architecture:
 *   1. Define tools as OpenAI function definitions
 *   2. Send messages + tools to LLM via getCompletion
 *   3. If LLM returns tool_calls, execute them and feed results back
 *   4. Repeat until LLM returns a final text answer (no tool_calls)
 *   5. Safety: max iterations, SSH logging, error wrapping
 */

const logger = require('./logger');

// ══════════════════════════════════════════
//  TOOL DEFINITIONS — OpenAI function-calling format
// ══════════════════════════════════════════

const TOOL_DEFINITIONS = [
  {
    type: 'function',
    function: {
      name: 'web_search',
      description: 'Search the web using Brave Search API. Returns titles, URLs, and descriptions of top results.',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'The search query' },
          count: { type: 'number', description: 'Number of results (default 5, max 20)' },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'web_browse',
      description: 'Browse a URL with headless Chromium. Returns the text content of the page (JS-rendered).',
      parameters: {
        type: 'object',
        properties: {
          url: { type: 'string', description: 'The URL to browse' },
          wait_for: { type: 'string', description: 'Optional CSS selector to wait for before extracting content' },
        },
        required: ['url'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'web_screenshot',
      description: 'Take a screenshot of a web page. Returns a base64-encoded JPEG image.',
      parameters: {
        type: 'object',
        properties: {
          url: { type: 'string', description: 'The URL to screenshot' },
          full_page: { type: 'boolean', description: 'Capture full page (default true)' },
        },
        required: ['url'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'web_fill_form',
      description: 'Fill a web form using headless Chromium. Navigates to URL, fills fields by CSS selector, and clicks submit.',
      parameters: {
        type: 'object',
        properties: {
          url: { type: 'string', description: 'The URL with the form' },
          fields: {
            type: 'object',
            description: 'Map of CSS selector to value to type. Example: {"#email": "test@test.com", "#password": "secret"}',
            additionalProperties: { type: 'string' },
          },
          submit_selector: { type: 'string', description: 'CSS selector for the submit button (default: button[type="submit"])' },
        },
        required: ['url', 'fields'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'db_query',
      description: 'Execute a read-only SQL query on Supabase PostgreSQL. Returns rows and field names. Use for NBA data, predictions, odds, scores, etc.',
      parameters: {
        type: 'object',
        properties: {
          sql: { type: 'string', description: 'SQL query to execute (SELECT only recommended)' },
        },
        required: ['sql'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'db_insert',
      description: 'Insert data into a Supabase PostgreSQL table. Constructs an INSERT query from table name and data object.',
      parameters: {
        type: 'object',
        properties: {
          table: { type: 'string', description: 'Table name to insert into' },
          data: {
            type: 'object',
            description: 'Key-value pairs to insert. Example: {"player_name": "LeBron", "team": "Lakers"}',
            additionalProperties: {},
          },
        },
        required: ['table', 'data'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'neo4j_query',
      description: 'Execute a Cypher query on Neo4j graph database. Use for entity relationships, player/team networks.',
      parameters: {
        type: 'object',
        properties: {
          cypher: { type: 'string', description: 'Cypher query to execute (read-only recommended)' },
        },
        required: ['cypher'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'fetch_nba_odds',
      description: 'Fetch latest NBA odds from The Odds API. Returns games with bookmaker odds, spreads, totals, and consensus lines.',
      parameters: {
        type: 'object',
        properties: {},
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'fetch_nba_scores',
      description: 'Fetch latest NBA scores from ESPN. Optionally specify a date.',
      parameters: {
        type: 'object',
        properties: {
          date: { type: 'string', description: 'Date in YYYY-MM-DD format (default: today)' },
        },
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'fetch_nba_injuries',
      description: 'Fetch current NBA injury report from ESPN. Returns player names, teams, status, and injury type.',
      parameters: {
        type: 'object',
        properties: {},
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'fetch_nba_games_today',
      description: 'Fetch today\'s NBA games from NBA.com CDN scoreboard. Returns game IDs, teams, scores, and statuses.',
      parameters: {
        type: 'object',
        properties: {},
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'evolution_status',
      description: 'Get the current status of the S10 genetic algorithm evolution. Returns Brier score, generation, features, population, stagnation.',
      parameters: {
        type: 'object',
        properties: {},
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'execute_ssh',
      description: 'Execute a shell command on the Nomos42 VM (34.136.180.66) via SSH. Use for system administration, script execution, file operations. Dangerous commands require the confirm flag.',
      parameters: {
        type: 'object',
        properties: {
          command: { type: 'string', description: 'Shell command to execute' },
          cwd: { type: 'string', description: 'Working directory (default: /home/termius)' },
          timeout: { type: 'number', description: 'Timeout in ms (default: 30000)' },
          confirm: { type: 'boolean', description: 'Set to true for dangerous commands (rm -rf, reboot, etc.)' },
        },
        required: ['command'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'github_read',
      description: 'Read a file from a GitHub repository. Returns the file content decoded from base64.',
      parameters: {
        type: 'object',
        properties: {
          owner: { type: 'string', description: 'Repository owner (default: LBJLincoln)' },
          repo: { type: 'string', description: 'Repository name' },
          path: { type: 'string', description: 'File path within the repository' },
          branch: { type: 'string', description: 'Branch name (default: main)' },
        },
        required: ['repo', 'path'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'github_write',
      description: 'Create or update a file in a GitHub repository. Commits directly to the specified branch.',
      parameters: {
        type: 'object',
        properties: {
          owner: { type: 'string', description: 'Repository owner (default: LBJLincoln)' },
          repo: { type: 'string', description: 'Repository name' },
          path: { type: 'string', description: 'File path within the repository' },
          content: { type: 'string', description: 'File content to write' },
          message: { type: 'string', description: 'Commit message' },
          branch: { type: 'string', description: 'Branch name (default: main)' },
        },
        required: ['repo', 'path', 'content', 'message'],
      },
    },
  },
];

// ══════════════════════════════════════════
//  DANGEROUS COMMAND PATTERNS — require confirm flag
// ══════════════════════════════════════════

const DANGEROUS_PATTERNS = [
  /\brm\s+(-rf?|--recursive)\b/i,
  /\breboot\b/i,
  /\bshutdown\b/i,
  /\bmkfs\b/i,
  /\bdd\s+if=/i,
  /\b>\s*\/dev\//i,
  /\bchmod\s+-R\s+777\b/i,
  /\bgit\s+push\s+--force\b/i,
  /\bgit\s+reset\s+--hard\b/i,
  /\bdrop\s+(?:table|database)\b/i,
  /\btruncate\s+table\b/i,
  /\bdelete\s+from\b.*(?:without|no)\s*where/i,
];

function isDangerous(command) {
  return DANGEROUS_PATTERNS.some(p => p.test(command));
}

// ══════════════════════════════════════════
//  AGENT EXECUTOR CLASS
// ══════════════════════════════════════════

class AgentExecutor {
  /**
   * @param {object} deps - Dependencies injected from server.js
   * @param {Function} deps.getCompletion - LLM completion function (must support tools param)
   * @param {object} deps.infraBridge - InfraBridge instance (Supabase, Neo4j)
   * @param {object} deps.vmBridge - VMBridge instance (SSH)
   * @param {object} deps.dataWorker - DataWorker instance (NBA data)
   * @param {Function} deps.fetchEvolution - Function to fetch S10 evolution status
   * @param {string} deps.ghToken - GitHub API token
   * @param {string} deps.ghOwner - Default GitHub owner
   * @param {string} deps.braveApiKey - Brave Search API key
   * @param {string} deps.systemPrompt - System prompt for the agent
   */
  constructor(deps = {}) {
    this.getCompletionFn = deps.getCompletion;
    this.infra = deps.infraBridge;
    this.vm = deps.vmBridge;
    this.dataWorker = deps.dataWorker;
    this.fetchEvolution = deps.fetchEvolution;
    this.ghToken = deps.ghToken || process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
    this.ghOwner = deps.ghOwner || 'LBJLincoln';
    this.braveApiKey = deps.braveApiKey || process.env.BRAVE_API_KEY || process.env.BRAVE_SEARCH_API_KEY;
    this.systemPrompt = deps.systemPrompt || '';

    // Lazy-loaded browser module
    this._browser = null;

    // Stats
    this.stats = {
      executions: 0,
      toolCalls: 0,
      errors: 0,
      avgIterations: 0,
      lastExecution: null,
    };

    // Execution log (ring buffer)
    this.executionLog = [];

    logger.info('[AGENT-EXECUTOR] Initialized with tools: ' +
      TOOL_DEFINITIONS.map(t => t.function.name).join(', '));
  }

  /**
   * Get the browser module (lazy-loaded to avoid startup crash if Chromium missing).
   */
  _getBrowser() {
    if (!this._browser) {
      try {
        this._browser = require('./browser');
      } catch (err) {
        logger.warn(`[AGENT-EXECUTOR] Browser not available: ${err.message}`);
        this._browser = null;
      }
    }
    return this._browser;
  }

  /**
   * Get tool definitions, filtered to only tools whose backends are available.
   */
  getToolDefinitions() {
    const available = [];

    for (const tool of TOOL_DEFINITIONS) {
      const name = tool.function.name;

      // Filter out tools whose backends are not configured
      if (name === 'web_search' && !this.braveApiKey) continue;
      if ((name === 'web_browse' || name === 'web_screenshot' || name === 'web_fill_form') && !this._getBrowser()) continue;
      if ((name === 'db_query' || name === 'db_insert') && !this.infra?.pgPool) continue;
      if (name === 'neo4j_query' && !this.infra?.neo4jDriver) continue;
      if (name === 'fetch_nba_odds' && !this.dataWorker) continue;
      if ((name === 'fetch_nba_scores' || name === 'fetch_nba_injuries' || name === 'fetch_nba_games_today') && !this.dataWorker) continue;
      if (name === 'evolution_status' && !this.fetchEvolution) continue;
      if (name === 'execute_ssh' && !this.vm) continue;
      if ((name === 'github_read' || name === 'github_write') && !this.ghToken) continue;

      available.push(tool);
    }

    return available;
  }

  // ══════════════════════════════════════════
  //  MAIN REACT LOOP
  // ══════════════════════════════════════════

  /**
   * Execute the ReAct agent loop.
   *
   * @param {Array} messages - OpenAI-format messages [{role, content}, ...]
   * @param {object} options
   * @param {number} options.maxIterations - Max tool-calling rounds (default 10)
   * @param {number} options.maxTokens - Max tokens per LLM call (default 2000)
   * @param {number} options.temperature - LLM temperature (default 0.3)
   * @param {string} options.sessionId - Optional session ID for context
   * @returns {object} { content, model, toolsUsed, iterations, usage }
   */
  async execute(messages, options = {}) {
    const maxIterations = options.maxIterations || 10;
    const maxTokens = options.maxTokens || 2000;
    const temperature = options.temperature ?? 0.3;

    const tools = this.getToolDefinitions();
    const toolsUsed = [];
    let totalUsage = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };
    let lastModel = null;

    // Prepend system prompt if set and not already present
    const workingMessages = [...messages];
    if (this.systemPrompt && (!workingMessages[0] || workingMessages[0].role !== 'system')) {
      workingMessages.unshift({ role: 'system', content: this.systemPrompt });
    }

    const startTime = Date.now();
    this.stats.executions++;

    logger.info(`[AGENT-EXECUTOR] Starting execution (${tools.length} tools available, max ${maxIterations} iterations)`);

    for (let i = 0; i < maxIterations; i++) {
      // Call LLM with tools
      let response;
      try {
        response = await this._callLLMWithTools(workingMessages, tools, { maxTokens, temperature });
      } catch (err) {
        logger.error(`[AGENT-EXECUTOR] LLM call failed at iteration ${i}: ${err.message}`);
        this.stats.errors++;

        // If LLM fails on first iteration, return error directly
        if (i === 0) {
          return {
            content: `Agent execution failed: ${err.message}`,
            model: null,
            toolsUsed,
            iterations: i + 1,
            error: true,
          };
        }

        // If we already have partial results, return what we have
        return {
          content: `Agent stopped after ${i} iterations due to LLM error: ${err.message}. Partial results from tools used: ${toolsUsed.join(', ')}`,
          model: lastModel,
          toolsUsed,
          iterations: i + 1,
          error: true,
        };
      }

      lastModel = response.model;
      if (response.usage) {
        totalUsage.prompt_tokens += response.usage.prompt_tokens || 0;
        totalUsage.completion_tokens += response.usage.completion_tokens || 0;
        totalUsage.total_tokens += response.usage.total_tokens || 0;
      }

      // Check if LLM returned tool calls
      const toolCalls = response.tool_calls;

      if (!toolCalls || toolCalls.length === 0) {
        // No tool calls — LLM is done, return final answer
        const duration = Date.now() - startTime;
        this._recordExecution(messages, toolsUsed, i + 1, duration);

        logger.info(`[AGENT-EXECUTOR] Completed in ${i + 1} iteration(s), ${toolsUsed.length} tool call(s), ${duration}ms`);

        return {
          content: response.content || '',
          model: lastModel,
          toolsUsed,
          iterations: i + 1,
          usage: totalUsage,
        };
      }

      // Add assistant message with tool calls to conversation
      workingMessages.push({
        role: 'assistant',
        content: response.content || null,
        tool_calls: toolCalls,
      });

      // Execute each tool call
      for (const toolCall of toolCalls) {
        const fnName = toolCall.function?.name;
        let fnArgs;

        try {
          fnArgs = JSON.parse(toolCall.function?.arguments || '{}');
        } catch (parseErr) {
          logger.warn(`[AGENT-EXECUTOR] Failed to parse args for ${fnName}: ${parseErr.message}`);
          fnArgs = {};
        }

        logger.info(`[AGENT-EXECUTOR] Tool call [${i + 1}/${maxIterations}]: ${fnName}(${JSON.stringify(fnArgs).substring(0, 200)})`);
        this.stats.toolCalls++;
        toolsUsed.push(fnName);

        let result;
        try {
          result = await this._executeTool(fnName, fnArgs);
        } catch (err) {
          logger.warn(`[AGENT-EXECUTOR] Tool ${fnName} error: ${err.message}`);
          this.stats.errors++;
          result = { error: err.message };
        }

        // Stringify result and truncate if too large (to prevent context overflow)
        let resultStr = typeof result === 'string' ? result : JSON.stringify(result);
        if (resultStr.length > 15000) {
          resultStr = resultStr.substring(0, 15000) + '\n...[TRUNCATED — result was ' + resultStr.length + ' chars]';
        }

        // Add tool result to conversation
        workingMessages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          content: resultStr,
        });
      }
    }

    // Max iterations reached
    const duration = Date.now() - startTime;
    this._recordExecution(messages, toolsUsed, maxIterations, duration);
    logger.warn(`[AGENT-EXECUTOR] Max iterations (${maxIterations}) reached after ${duration}ms`);

    return {
      content: `Agent reached maximum iterations (${maxIterations}). Tools used: ${toolsUsed.join(', ')}. The task may require more steps — try increasing maxIterations or breaking it into smaller tasks.`,
      model: lastModel,
      toolsUsed,
      iterations: maxIterations,
      usage: totalUsage,
      maxIterationsReached: true,
    };
  }

  // ══════════════════════════════════════════
  //  LLM CALL WITH TOOLS
  // ══════════════════════════════════════════

  /**
   * Call the LLM with OpenAI-compatible function-calling.
   * This wraps getCompletion to pass tools and parse tool_calls from the response.
   */
  async _callLLMWithTools(messages, tools, options = {}) {
    const { maxTokens = 2000, temperature = 0.3 } = options;

    // The existing getCompletion function uses multiple providers.
    // We need to pass tools through. Most providers (OpenRouter, Gemini, OpenAI)
    // support the OpenAI function-calling format.
    //
    // Strategy: Call providers directly with tools support, falling back gracefully.

    const allMessages = messages;

    // Provider chain: LiteLLM -> Direct providers -> OpenRouter free models
    // Each must receive tools in the request body.

    const litellmBase = process.env.LITELLM_PROXY_URL || 'https://lbjlincoln-nomos-rag-engine-7.hf.space';
    const LITELLM_URL = litellmBase.endsWith('/v1/chat/completions') ? litellmBase : `${litellmBase.replace(/\/$/, '')}/v1/chat/completions`;
    const LITELLM_KEY = process.env.LITELLM_MASTER_KEY || 'sk-litellm-nomos-2026';
    const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;

    // 1. LiteLLM proxy (supports tool calling if backend model does)
    for (const litellmModel of ['smart', 'fast']) {
      try {
        const body = {
          model: litellmModel,
          messages: allMessages,
          max_tokens: maxTokens,
          temperature,
        };
        if (tools.length > 0) {
          body.tools = tools;
          body.tool_choice = 'auto';
        }

        const resp = await fetch(LITELLM_URL, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${LITELLM_KEY}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(45000),
        });
        const data = await resp.json();
        const msg = data.choices?.[0]?.message;

        if (msg) {
          return {
            content: msg.content || '',
            tool_calls: msg.tool_calls || null,
            model: `litellm/${litellmModel}`,
            usage: data.usage,
          };
        }
      } catch (err) {
        logger.warn(`[AGENT-EXECUTOR] LiteLLM ${litellmModel} failed: ${err.message}`);
      }
    }

    // 2. Direct providers — OpenAI and Gemini support function calling natively
    const DIRECT_PROVIDERS = [
      {
        name: 'openai',
        url: 'https://api.openai.com/v1/chat/completions',
        key: process.env.OPENAI_API_KEY,
        model: 'gpt-4.1-mini',
      },
      {
        name: 'gemini',
        url: 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        key: process.env.GOOGLE_API_KEY,
        model: 'gemini-2.5-flash',
      },
    ];

    for (const provider of DIRECT_PROVIDERS) {
      if (!provider.key) continue;
      try {
        const body = {
          model: provider.model,
          messages: allMessages,
          max_tokens: maxTokens,
          temperature,
        };
        if (tools.length > 0) {
          body.tools = tools;
          body.tool_choice = 'auto';
        }

        const resp = await fetch(provider.url, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${provider.key}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(30000),
        });
        const data = await resp.json();
        const msg = data.choices?.[0]?.message;

        if (msg) {
          return {
            content: msg.content || '',
            tool_calls: msg.tool_calls || null,
            model: `${provider.name}/${provider.model}`,
            usage: data.usage,
          };
        }
      } catch (err) {
        logger.warn(`[AGENT-EXECUTOR] ${provider.name} failed: ${err.message}`);
      }
    }

    // 3. OpenRouter (many models support function calling)
    if (OPENROUTER_API_KEY) {
      // Models known to support function calling on OpenRouter
      const TOOL_CAPABLE_MODELS = [
        'deepseek/deepseek-chat-v3-0324:free',
        'meta-llama/llama-4-maverick:free',
        'meta-llama/llama-4-scout:free',
        'meta-llama/llama-3.3-70b-instruct:free',
        'qwen/qwen3-235b-a22b:free',
        'qwen/qwen3-32b:free',
        'mistralai/mistral-small-3.1-24b-instruct:free',
      ];

      for (const model of TOOL_CAPABLE_MODELS) {
        try {
          const body = {
            model,
            messages: allMessages,
            max_tokens: maxTokens,
            temperature,
          };
          if (tools.length > 0) {
            body.tools = tools;
            body.tool_choice = 'auto';
          }

          const HF_SPACE_URL = process.env.SPACE_HOST
            ? `https://${process.env.SPACE_HOST}`
            : 'https://nomos42-nomos-worker-2.hf.space';

          const resp = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
              'Content-Type': 'application/json',
              'HTTP-Referer': HF_SPACE_URL,
              'X-Title': 'OpenClaw Agent Executor',
            },
            body: JSON.stringify(body),
            signal: AbortSignal.timeout(45000),
          });
          const data = await resp.json();
          const msg = data.choices?.[0]?.message;

          if (msg) {
            return {
              content: msg.content || '',
              tool_calls: msg.tool_calls || null,
              model,
              usage: data.usage,
            };
          }
        } catch (err) {
          logger.warn(`[AGENT-EXECUTOR] OpenRouter ${model} failed: ${err.message}`);
        }
      }
    }

    throw new Error('ALL LLM providers failed for agent tool-calling');
  }

  // ══════════════════════════════════════════
  //  TOOL EXECUTION — Dispatch to real implementations
  // ══════════════════════════════════════════

  /**
   * Execute a single tool by name with the given arguments.
   * Each tool is wrapped in try/catch; errors are returned as results, not thrown.
   */
  async _executeTool(name, args) {
    switch (name) {
      case 'web_search':
        return await this._toolWebSearch(args);
      case 'web_browse':
        return await this._toolWebBrowse(args);
      case 'web_screenshot':
        return await this._toolWebScreenshot(args);
      case 'web_fill_form':
        return await this._toolWebFillForm(args);
      case 'db_query':
        return await this._toolDbQuery(args);
      case 'db_insert':
        return await this._toolDbInsert(args);
      case 'neo4j_query':
        return await this._toolNeo4jQuery(args);
      case 'fetch_nba_odds':
        return await this._toolFetchNbaOdds(args);
      case 'fetch_nba_scores':
        return await this._toolFetchNbaScores(args);
      case 'fetch_nba_injuries':
        return await this._toolFetchNbaInjuries(args);
      case 'fetch_nba_games_today':
        return await this._toolFetchNbaGamesToday(args);
      case 'evolution_status':
        return await this._toolEvolutionStatus(args);
      case 'execute_ssh':
        return await this._toolExecuteSSH(args);
      case 'github_read':
        return await this._toolGithubRead(args);
      case 'github_write':
        return await this._toolGithubWrite(args);
      default:
        return { error: `Unknown tool: ${name}` };
    }
  }

  // ── Web Search (Brave API) ──

  async _toolWebSearch(args) {
    const { query, count = 5 } = args;
    if (!query) return { error: 'query is required' };
    if (!this.braveApiKey) return { error: 'BRAVE_API_KEY not configured' };

    const url = `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=${Math.min(count, 20)}`;
    const resp = await fetch(url, {
      headers: {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': this.braveApiKey,
      },
      signal: AbortSignal.timeout(10000),
    });

    if (resp.status === 429) return { error: 'Brave Search quota exhausted' };
    if (!resp.ok) return { error: `Brave Search HTTP ${resp.status}` };

    const data = await resp.json();
    const results = (data.web?.results || []).slice(0, count).map(r => ({
      title: r.title,
      url: r.url,
      description: r.description,
    }));

    return { query, resultCount: results.length, results };
  }

  // ── Web Browse (Puppeteer) ──

  async _toolWebBrowse(args) {
    const { url, wait_for } = args;
    if (!url) return { error: 'url is required' };

    const browser = this._getBrowser();
    if (!browser) return { error: 'Browser (Chromium) not available' };

    const html = await browser.scrape(url, {
      waitFor: wait_for,
      timeout: 20000,
    });

    if (!html) return { error: 'Page returned no content' };

    // Strip HTML tags, extract text content
    const text = html.replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<style[\s\S]*?<\/style>/gi, '')
      .replace(/<[^>]*>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    return {
      url,
      contentLength: text.length,
      content: text.substring(0, 10000),
    };
  }

  // ── Web Screenshot (Puppeteer) ──

  async _toolWebScreenshot(args) {
    const { url, full_page = true } = args;
    if (!url) return { error: 'url is required' };

    const browser = this._getBrowser();
    if (!browser) return { error: 'Browser (Chromium) not available' };

    const img = await browser.screenshot(url, { fullPage: full_page, timeout: 20000 });
    return { url, screenshot: img };
  }

  // ── Web Fill Form (Puppeteer) ──

  async _toolWebFillForm(args) {
    const { url, fields, submit_selector = 'button[type="submit"]' } = args;
    if (!url || !fields) return { error: 'url and fields are required' };

    const browser = this._getBrowser();
    if (!browser) return { error: 'Browser (Chromium) not available' };

    const result = await browser.fillForm(url, fields, submit_selector, { timeout: 30000 });
    return result;
  }

  // ── Database Query (Supabase PostgreSQL) ──

  async _toolDbQuery(args) {
    const { sql } = args;
    if (!sql) return { error: 'sql is required' };
    if (!this.infra?.pgPool) return { error: 'Supabase not configured' };

    const result = await this.infra.querySupabase(sql);
    return {
      rowCount: result.rowCount,
      fields: result.fields,
      rows: result.rows?.slice(0, 100), // Cap at 100 rows to prevent context overflow
    };
  }

  // ── Database Insert (Supabase PostgreSQL) ──

  async _toolDbInsert(args) {
    const { table, data } = args;
    if (!table || !data) return { error: 'table and data are required' };
    if (!this.infra?.pgPool) return { error: 'Supabase not configured' };

    const columns = Object.keys(data);
    const values = Object.values(data);
    const placeholders = columns.map((_, i) => `$${i + 1}`).join(', ');
    const sql = `INSERT INTO ${table} (${columns.join(', ')}) VALUES (${placeholders}) RETURNING *`;

    const client = await this.infra.pgPool.connect();
    try {
      await client.query('SET search_path TO public');
      const result = await client.query(sql, values);
      return {
        inserted: true,
        rowCount: result.rowCount,
        rows: result.rows,
      };
    } finally {
      client.release();
    }
  }

  // ── Neo4j Query ──

  async _toolNeo4jQuery(args) {
    const { cypher } = args;
    if (!cypher) return { error: 'cypher is required' };
    if (!this.infra?.neo4jDriver) return { error: 'Neo4j not configured' };

    const result = await this.infra.queryNeo4j(cypher);
    return {
      recordCount: result.length,
      records: result.slice(0, 50), // Cap at 50 records
    };
  }

  // ── NBA Odds ──

  async _toolFetchNbaOdds() {
    if (!this.dataWorker) return { error: 'DataWorker not initialized' };
    const result = await this.dataWorker.fetchOdds();
    if (!result) return { error: 'Odds fetch failed (quota may be exhausted)' };

    // Slim down for LLM context
    return {
      gameCount: result.games?.length || 0,
      stored: result.stored,
      games: (result.games || []).map(g => ({
        home: g.home_team,
        away: g.away_team,
        commence: g.commence_time,
        moneyline_home: g.consensus?.moneyline_home,
        moneyline_away: g.consensus?.moneyline_away,
        spread_home: g.consensus?.spread_home,
        total: g.consensus?.total_line,
        implied_home_prob: g.consensus?.implied_home_prob,
        bookmakers: g.consensus?.bookmaker_count,
      })),
    };
  }

  // ── NBA Scores ──

  async _toolFetchNbaScores(args) {
    if (!this.dataWorker) return { error: 'DataWorker not initialized' };
    const result = await this.dataWorker.fetchScores(args?.date);
    if (!result) return { error: 'Scores fetch failed' };
    return result;
  }

  // ── NBA Injuries ──

  async _toolFetchNbaInjuries() {
    if (!this.dataWorker) return { error: 'DataWorker not initialized' };
    const result = await this.dataWorker.fetchInjuries();
    if (!result) return { error: 'Injuries fetch failed' };

    // Slim down — group by team for readability
    const byTeam = {};
    for (const inj of (result.injuries || [])) {
      if (!byTeam[inj.team]) byTeam[inj.team] = [];
      byTeam[inj.team].push({
        player: inj.player_name,
        status: inj.status,
        injury: inj.injury_type,
      });
    }

    return {
      total: result.total,
      stored: result.stored,
      byTeam,
    };
  }

  // ── NBA Games Today ──

  async _toolFetchNbaGamesToday() {
    if (!this.dataWorker) return { error: 'DataWorker not initialized' };
    const result = await this.dataWorker.fetchTodaysGames();
    if (!result) return { error: 'Today\'s games fetch failed' };
    return result;
  }

  // ── Evolution Status ──

  async _toolEvolutionStatus() {
    if (!this.fetchEvolution) return { error: 'Evolution fetcher not configured' };
    const result = await this.fetchEvolution();
    if (!result) return { error: 'Could not reach S10 evolution space' };
    return result;
  }

  // ── SSH Command Execution ──

  async _toolExecuteSSH(args) {
    const { command, cwd, timeout = 30000, confirm = false } = args;
    if (!command) return { error: 'command is required' };
    if (!this.vm) return { error: 'VM Bridge (SSH) not configured' };

    // Safety: check for dangerous commands
    if (isDangerous(command) && !confirm) {
      logger.warn(`[AGENT-EXECUTOR] BLOCKED dangerous SSH command (no confirm): ${command}`);
      return {
        error: `Dangerous command blocked. Set confirm=true to execute: ${command}`,
        blocked: true,
        command,
      };
    }

    // Log all SSH commands for audit trail
    logger.info(`[AGENT-EXECUTOR] SSH exec: ${command}${cwd ? ` (cwd: ${cwd})` : ''}`);

    const result = await this.vm.exec(command, { cwd, timeout });
    return {
      stdout: (result.stdout || '').substring(0, 8000),
      stderr: (result.stderr || '').substring(0, 2000),
      exitCode: result.code,
    };
  }

  // ── GitHub Read ──

  async _toolGithubRead(args) {
    const { owner = this.ghOwner, repo, path: filePath, branch = 'main' } = args;
    if (!repo || !filePath) return { error: 'repo and path are required' };
    if (!this.ghToken) return { error: 'GitHub token not configured' };

    const url = `https://api.github.com/repos/${owner}/${repo}/contents/${filePath}?ref=${branch}`;
    const resp = await fetch(url, {
      headers: {
        'Authorization': `token ${this.ghToken}`,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'OpenClaw-Agent/1.0',
      },
      signal: AbortSignal.timeout(15000),
    });

    if (!resp.ok) {
      return { error: `GitHub API ${resp.status}: ${await resp.text().catch(() => 'unknown')}` };
    }

    const data = await resp.json();
    const content = Buffer.from(data.content || '', 'base64').toString('utf-8');

    return {
      repo: `${owner}/${repo}`,
      path: filePath,
      branch,
      sha: data.sha,
      size: data.size,
      content: content.substring(0, 15000),
      truncated: content.length > 15000,
    };
  }

  // ── GitHub Write ──

  async _toolGithubWrite(args) {
    const { owner = this.ghOwner, repo, path: filePath, content, message, branch = 'main' } = args;
    if (!repo || !filePath || content === undefined || !message) {
      return { error: 'repo, path, content, and message are required' };
    }
    if (!this.ghToken) return { error: 'GitHub token not configured' };

    const fullRepo = `${owner}/${repo}`;
    const b64Content = Buffer.from(content).toString('base64');

    // Check if file exists (to get sha for updates)
    let sha;
    try {
      const existingResp = await fetch(
        `https://api.github.com/repos/${fullRepo}/contents/${filePath}?ref=${branch}`,
        {
          headers: {
            'Authorization': `token ${this.ghToken}`,
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'OpenClaw-Agent/1.0',
          },
          signal: AbortSignal.timeout(10000),
        }
      );
      if (existingResp.ok) {
        const existing = await existingResp.json();
        sha = existing.sha;
      }
    } catch {
      // File doesn't exist — that's fine, we'll create it
    }

    const body = { message, content: b64Content, branch };
    if (sha) body.sha = sha;

    const resp = await fetch(`https://api.github.com/repos/${fullRepo}/contents/${filePath}`, {
      method: 'PUT',
      headers: {
        'Authorization': `token ${this.ghToken}`,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'OpenClaw-Agent/1.0',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });

    if (!resp.ok) {
      return { error: `GitHub API ${resp.status}: ${await resp.text().catch(() => 'unknown')}` };
    }

    const result = await resp.json();
    return {
      success: true,
      repo: fullRepo,
      path: filePath,
      sha: result.content?.sha,
      url: result.content?.html_url,
      action: sha ? 'updated' : 'created',
    };
  }

  // ══════════════════════════════════════════
  //  EXECUTION LOG
  // ══════════════════════════════════════════

  _recordExecution(messages, toolsUsed, iterations, duration) {
    const entry = {
      timestamp: new Date().toISOString(),
      userMessage: messages.filter(m => m.role === 'user').pop()?.content?.substring(0, 200) || '',
      toolsUsed,
      iterations,
      duration,
    };

    this.executionLog.push(entry);
    if (this.executionLog.length > 100) {
      this.executionLog = this.executionLog.slice(-100);
    }

    // Update rolling average
    const total = this.stats.executions;
    this.stats.avgIterations = (this.stats.avgIterations * (total - 1) + iterations) / total;
    this.stats.lastExecution = entry.timestamp;
  }

  // ══════════════════════════════════════════
  //  STATUS
  // ══════════════════════════════════════════

  getStatus() {
    return {
      tools: this.getToolDefinitions().map(t => t.function.name),
      toolCount: this.getToolDefinitions().length,
      stats: this.stats,
      recentExecutions: this.executionLog.slice(-10),
    };
  }
}

module.exports = AgentExecutor;
