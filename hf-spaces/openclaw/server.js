/**
 * OpenClaw v2026.3.17 — Nomos NBA Quant AI Agent
 *
 * Express server deployed on HF Spaces (Docker, port 7860).
 * HuggingClaw-style architecture: Adam (Claude CLI) + Eve (OpenClaw) + Cain (Evolution)
 * 24/7 Karpathy-style autonomous improvement loop.
 *
 * Target Space: Nomos42/nomos-worker-2
 */

const express = require('express');
const TelegramBot = require('node-telegram-bot-api');
const OpenAI = require('openai');
const cron = require('node-cron');
const { v4: uuidv4 } = require('uuid');
const { Pool } = require('pg');
const neo4j = require('neo4j-driver');
const fs = require('fs');
const path = require('path');
const { execSync, exec } = require('child_process');
const https = require('https');
const http = require('http');

const logger = require('./lib/logger');
const persistence = require('./lib/persistence');
const SpaceExecutor = require('./lib/space-executor');
const InfraBridge = require('./lib/infra-bridge');
const AgenticLoop = require('./lib/agentic-loop');

// ============================================================
// CONFIG
// ============================================================

const PORT = process.env.PORT || 7860;
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const ADMIN_TELEGRAM_ID = parseInt(process.env.ADMIN_TELEGRAM_ID || '6582544948');
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const HF_SPACE_URL = process.env.SPACE_HOST
  ? `https://${process.env.SPACE_HOST}`
  : `http://localhost:${PORT}`;

// Load model + space configs
const modelsConfig = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'config', 'models.json'), 'utf8')
);
const spacesConfig = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'config', 'spaces.json'), 'utf8')
);

// ============================================================
// EXPRESS APP
// ============================================================

const app = express();
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// CORS for dashboard
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// Request logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    if (req.path !== '/keep-alive' && req.path !== '/dashboard') {
      logger.info(`${req.method} ${req.path} ${res.statusCode} ${duration}ms`);
    }
  });
  next();
});

// ============================================================
// INFRASTRUCTURE BRIDGES
// ============================================================

const spaceExecutor = new SpaceExecutor(spacesConfig, {
  hfToken: process.env.HF_TOKEN_3,
  hfToken2: process.env.HF_TOKEN,
  litellmUrl: process.env.LITELLM_PROXY_URL,
  litellmKey: process.env.LITELLM_MASTER_KEY,
});

const infraBridge = new InfraBridge({
  supabaseUrl: process.env.DATABASE_URL,
  neo4jUri: process.env.NEO4J_URI,
  neo4jPassword: process.env.NEO4J_PASSWORD,
  pineconeHost: process.env.PINECONE_HOST,
  pineconeApiKey: process.env.PINECONE_API_KEY,
});

// ============================================================
// AGENTIC LOOP (Karpathy-style 24/7)
// ============================================================

let agenticLoop = null; // Initialized after LLM client setup

// ============================================================
// OPENROUTER LLM CLIENT
// ============================================================

const openrouter = new OpenAI({
  apiKey: OPENROUTER_API_KEY,
  baseURL: 'https://openrouter.ai/api/v1',
  defaultHeaders: {
    'HTTP-Referer': HF_SPACE_URL,
    'X-Title': 'OpenClaw Nomos Agent',
  },
});

const GH_TOKEN = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
const GH_REPOS = ['mon-ipad', 'nomos-nba-agent', 'rag-data-ingestion', 'rag-website', 'rag-dashboard'];
const GH_OWNER = 'LBJLincoln';

const SYSTEM_PROMPT = `Tu es ADEMO (OpenClaw), agent IA autonome du projet NOMOS42 NBA Quant AI.
Architecture HuggingClaw: N.O.S (Claude Code CLI) = cerveau strategique, ADEMO (toi) = recherche & execution, CAIN = moteur d'evolution genetique.

MISSION: Construire le meilleur modele predictif NBA au monde.
- Brier score actuel ~0.23, target < 0.20
- Evolution genetique 24/7 avec selection de features
- 640+ features, 9 modeles ML, walk-forward backtesting
- Recherche continue de nouvelles features

INFRASTRUCTURE:
- HF Spaces: NBA Quant (S10+S11), OpenClaw (worker-2), LiteLLM (S7)
- Databases: Supabase, Neo4j, Pinecone
- GitHub: mon-ipad, nomos-nba-agent
- Telegram: reports positifs uniquement

ROLE ADEMO:
1. Rechercher de nouvelles features NBA (academic papers, analytics 2026)
2. Analyser les resultats d'evolution (Brier, ROI, Sharpe trends)
3. Suggerer des ameliorations (hyperparameters, models, calibration)
4. Monitorer la sante des Spaces
5. Reporter les resultats positifs via Telegram

MODE KARPATHY: Tu tournes en boucle autonome 24/7.
Observer → Rechercher → Evaluer → Ameliorer → Reporter.
Ne rapporter que les BONNES nouvelles sur Telegram.

Sois concis, technique, actionable. Format Telegram Markdown.`;

/**
 * Get LLM completion — LiteLLM FIRST (13-provider fallback), then OpenRouter free tier
 */
const LITELLM_URL = process.env.LITELLM_PROXY_URL || 'https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions';
const LITELLM_KEY = process.env.LITELLM_MASTER_KEY || 'sk-litellm-nomos-2026';

async function getCompletion(messages, options = {}) {
  const allMessages = [{ role: 'system', content: SYSTEM_PROMPT }, ...messages];
  const maxTokens = options.maxTokens || 2000;
  const temperature = options.temperature || 0.4;

  // 1. Try LiteLLM proxy first (has 13 providers with auto-fallback)
  for (const litellmModel of ['smart', 'fast', 'default']) {
    try {
      const resp = await fetch(LITELLM_URL, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${LITELLM_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: litellmModel,
          messages: allMessages,
          max_tokens: maxTokens,
          temperature,
        }),
        signal: AbortSignal.timeout(30000), // 30s timeout
      });
      const data = await resp.json();
      if (data.choices && data.choices[0]?.message?.content) {
        return {
          content: data.choices[0].message.content,
          model: `litellm/${litellmModel}`,
          usage: data.usage,
        };
      }
    } catch (err) {
      logger.warn(`LiteLLM ${litellmModel} failed: ${err.message}`);
    }
  }

  // 2. Fallback to OpenRouter free models
  const freeModels = [
    'nvidia/nemotron-3-super-120b-a12b:free',
    'arcee-ai/trinity-large-preview:free',
  ];

  for (const model of freeModels) {
    try {
      const completion = await openrouter.chat.completions.create({
        model,
        messages: allMessages,
        max_tokens: maxTokens,
        temperature,
        stream: false,
      });
      return {
        content: completion.choices[0]?.message?.content || '',
        model,
        usage: completion.usage,
      };
    } catch (err) {
      logger.warn(`OpenRouter ${model} failed: ${err.message}`);
    }
  }

  throw new Error('ALL LLM providers failed (LiteLLM + OpenRouter)');
}

// ============================================================
// TELEGRAM BOT (WEBHOOK MODE)
// ============================================================

let bot = null;
if (TELEGRAM_BOT_TOKEN) {
  bot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: false });
  logger.info('Telegram bot initialized (webhook mode)');
} else {
  logger.warn('TELEGRAM_BOT_TOKEN not set — bot disabled');
}

/**
 * Telegram command handlers
 */
const COMMANDS = {
  '/start': async (msg) => {
    return `*OpenClaw v2026.3.11-beta.1*
Agent IA d'operations Nomos Sector AI

Commandes disponibles :
/status — Sante de l'infrastructure
/spaces — Liste des HF Spaces
/eval — Lancer un smoke test
/query <question> — Interroger un pipeline RAG
/db <sql> — Requete Supabase directe
/neo4j <cypher> — Requete Neo4j directe
/deploy <space> — Deployer sur un Space
/logs <space> — Voir les logs d'un Space
/ingest <sector> — Lancer une ingestion
/models — Modeles LLM configures
/ping — Test de connectivite

Ou posez directement votre question !`;
  },

  '/status': async (msg) => {
    try {
      const health = await spaceExecutor.healthCheckAll();
      let text = '*Infrastructure Status*\n\n';
      for (const [name, status] of Object.entries(health)) {
        const icon = status.up ? '🟢' : '🔴';
        text += `${icon} *${name}* — ${status.latency || 'N/A'}ms\n`;
      }

      // DB status
      const dbStatus = await infraBridge.checkDatabases();
      text += '\n*Databases*\n';
      for (const [name, status] of Object.entries(dbStatus)) {
        const icon = status.connected ? '🟢' : '🔴';
        text += `${icon} *${name}* — ${status.info || 'OK'}\n`;
      }
      return text;
    } catch (err) {
      return `Error checking status: ${err.message}`;
    }
  },

  '/spaces': async (msg) => {
    let text = '*HF Spaces (14 actifs)*\n\n';
    for (const space of spacesConfig.spaces) {
      text += `*${space.name}* (${space.id})\n`;
      text += `  Role: ${space.role}\n`;
      text += `  URL: \`${space.url}\`\n\n`;
    }
    return text;
  },

  '/eval': async (msg) => {
    const args = msg.text.split(' ').slice(1);
    const pipeline = args[0] || 'standard';
    const count = parseInt(args[1]) || 5;

    await bot.sendMessage(msg.chat.id,
      `Lancement eval: *${pipeline}* x${count} questions...`, { parse_mode: 'Markdown' });

    try {
      const results = await spaceExecutor.runEval(pipeline, count);
      let text = `*Eval Results — ${pipeline}*\n\n`;
      text += `Score: *${results.accuracy}%* (${results.passed}/${results.total})\n`;
      text += `Avg latency: ${results.avgLatency}ms\n`;
      if (results.failures?.length > 0) {
        text += '\nFailures:\n';
        for (const f of results.failures.slice(0, 3)) {
          text += `- ${f.question.substring(0, 60)}...\n`;
        }
      }
      return text;
    } catch (err) {
      return `Eval failed: ${err.message}`;
    }
  },

  '/query': async (msg) => {
    const question = msg.text.replace('/query', '').trim();
    if (!question) return 'Usage: /query <votre question>';

    await bot.sendMessage(msg.chat.id, 'Interrogation pipeline...', { parse_mode: 'Markdown' });

    try {
      const result = await spaceExecutor.queryPipeline('orchestrator', question);
      let text = `*Reponse RAG*\n\n${result.answer || result.response || 'No answer'}`;
      if (result.pipeline) text += `\n\n_Pipeline: ${result.pipeline}_`;
      if (result.sources?.length > 0) {
        text += '\n\n*Sources:*\n';
        for (const s of result.sources.slice(0, 3)) {
          text += `- ${s.title || s.source || 'unknown'}\n`;
        }
      }
      return text;
    } catch (err) {
      return `Query failed: ${err.message}`;
    }
  },

  '/db': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const sql = msg.text.replace('/db', '').trim();
    if (!sql) return 'Usage: /db <SQL query>';
    try {
      const result = await infraBridge.querySupabase(sql);
      return `*Query Result*\n\`\`\`\n${JSON.stringify(result.rows?.slice(0, 10), null, 2)}\n\`\`\``;
    } catch (err) {
      return `SQL Error: ${err.message}`;
    }
  },

  '/neo4j': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const cypher = msg.text.replace('/neo4j', '').trim();
    if (!cypher) return 'Usage: /neo4j <Cypher query>';
    try {
      const result = await infraBridge.queryNeo4j(cypher);
      return `*Neo4j Result*\n\`\`\`\n${JSON.stringify(result.slice(0, 10), null, 2)}\n\`\`\``;
    } catch (err) {
      return `Cypher Error: ${err.message}`;
    }
  },

  '/git': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const args = msg.text.replace('/git', '').trim();
    if (!args) return `*GitHub Repos*\n${GH_REPOS.map(r => `- \`${GH_OWNER}/${r}\``).join('\n')}\n\nUsage: /git <repo> [commits|issues|prs|status]`;
    const parts = args.split(' ');
    const repo = parts[0];
    const action = parts[1] || 'status';
    try {
      const result = await githubAction(repo, action);
      return result;
    } catch (err) {
      return `GitHub Error: ${err.message}`;
    }
  },

  '/evolution': async (msg) => {
    try {
      const resp = await fetchJSON('https://lbjlincoln-nomos-nba-quant.hf.space/gradio_api/call/dash_status', { data: [] });
      if (resp?.event_id) {
        const result = await fetchSSE(`https://lbjlincoln-nomos-nba-quant.hf.space/gradio_api/call/dash_status/${resp.event_id}`);
        return result || 'No evolution data';
      }
      return 'Evolution Space unreachable';
    } catch (err) {
      return `Evolution check failed: ${err.message}`;
    }
  },

  '/heal': async (msg) => {
    await bot.sendMessage(msg.chat.id, 'Scanning infrastructure for issues...', { parse_mode: 'Markdown' });
    try {
      const health = await spaceExecutor.healthCheckAll();
      const down = Object.entries(health).filter(([, s]) => !s.up);
      const dbStatus = await infraBridge.checkDatabases();
      const dbDown = Object.entries(dbStatus).filter(([, s]) => !s.connected);

      let issues = [];
      if (down.length > 0) issues.push(`Spaces DOWN: ${down.map(([n]) => n).join(', ')}`);
      if (dbDown.length > 0) issues.push(`DBs DOWN: ${dbDown.map(([n]) => n).join(', ')}`);

      if (issues.length === 0) {
        return '*HEALER SCAN COMPLETE*\n\nAll systems operational. No issues found.';
      }

      let text = `*HEALER SCAN — ${issues.length} issues found*\n\n`;
      for (const issue of issues) text += `- ${issue}\n`;
      text += '\nAnalyzing root causes...';

      const analysis = await getCompletion([{
        role: 'user',
        content: `Diagnose these infrastructure issues and suggest fixes:\n${issues.join('\n')}\n\nBe specific: which Space to restart, which config to change.`
      }], { models: modelsConfig.routing.analysis });

      text += `\n\n*Diagnosis:*\n${analysis.content}`;
      return text;
    } catch (err) {
      return `Heal scan failed: ${err.message}`;
    }
  },

  '/deploy': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const args = msg.text.split(' ').slice(1);
    const target = args[0];
    if (!target) return 'Usage: /deploy <space-name>';

    await bot.sendMessage(msg.chat.id, `Deploying to *${target}*...`, { parse_mode: 'Markdown' });
    try {
      const result = await spaceExecutor.deployToSpace(target);
      return `Deploy to *${target}*: ${result.status}\n${result.message || ''}`;
    } catch (err) {
      return `Deploy failed: ${err.message}`;
    }
  },

  '/logs': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const args = msg.text.split(' ').slice(1);
    const target = args[0] || 'S1';
    try {
      const logs = await spaceExecutor.getSpaceLogs(target);
      return `*Logs — ${target}*\n\`\`\`\n${logs.substring(0, 3500)}\n\`\`\``;
    } catch (err) {
      return `Logs failed: ${err.message}`;
    }
  },

  '/ingest': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const sector = msg.text.split(' ')[1] || 'all';
    await bot.sendMessage(msg.chat.id, `Ingestion *${sector}* lancee...`, { parse_mode: 'Markdown' });
    try {
      const result = await spaceExecutor.triggerIngestion(sector);
      return `Ingestion *${sector}*: ${result.status}\nDocs: ${result.count || 'pending'}`;
    } catch (err) {
      return `Ingest failed: ${err.message}`;
    }
  },

  '/models': async (msg) => {
    let text = '*Modeles LLM configures*\n\n';
    text += '*Prioritaires:*\n';
    for (const m of modelsConfig.priority) {
      const info = modelsConfig.models[m] || {};
      text += `- \`${m}\` — ${info.context || '?'}k ctx\n`;
    }
    text += '\n*Fallback:*\n';
    for (const m of modelsConfig.fallback) {
      text += `- \`${m}\`\n`;
    }
    return text;
  },

  '/ping': async (msg) => {
    const start = Date.now();
    await spaceExecutor.pingSpace('S1');
    const latency = Date.now() - start;
    return `Pong! S1 latency: ${latency}ms\nOpenClaw uptime: ${formatUptime(process.uptime())}`;
  },

  '/exec': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const args = msg.text.replace('/exec', '').trim();
    if (!args) return 'Usage: /exec <space> <webhook-path> [json-body]';

    const parts = args.split(' ');
    const space = parts[0];
    const webhookPath = parts[1];
    const body = parts.slice(2).join(' ') || '{}';

    try {
      const result = await spaceExecutor.executeWebhook(space, webhookPath, JSON.parse(body));
      return `*Exec Result — ${space}*\n\`\`\`\n${JSON.stringify(result, null, 2).substring(0, 3500)}\n\`\`\``;
    } catch (err) {
      return `Exec failed: ${err.message}`;
    }
  },
};

// ============================================================
// GITHUB + HELPERS
// ============================================================

async function githubAPI(path, method = 'GET', body = null) {
  if (!GH_TOKEN) throw new Error('GH_TOKEN not set');
  const url = `https://api.github.com${path}`;
  const headers = {
    'Authorization': `token ${GH_TOKEN}`,
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'OpenClaw-Healer/1.0',
  };
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(url, opts);
  if (!resp.ok) throw new Error(`GitHub API ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

async function githubAction(repo, action) {
  const fullRepo = repo.includes('/') ? repo : `${GH_OWNER}/${repo}`;
  switch (action) {
    case 'commits': {
      const commits = await githubAPI(`/repos/${fullRepo}/commits?per_page=5`);
      let text = `*Recent commits — ${fullRepo}*\n\n`;
      for (const c of commits) {
        const msg = c.commit.message.split('\n')[0].substring(0, 60);
        const date = c.commit.author.date.substring(0, 10);
        text += `\`${c.sha.substring(0,7)}\` ${date} ${msg}\n`;
      }
      return text;
    }
    case 'issues': {
      const issues = await githubAPI(`/repos/${fullRepo}/issues?state=open&per_page=10`);
      if (issues.length === 0) return `*${fullRepo}* — No open issues`;
      let text = `*Open issues — ${fullRepo}*\n\n`;
      for (const i of issues) {
        text += `#${i.number} ${i.title.substring(0, 50)}\n`;
      }
      return text;
    }
    case 'prs': {
      const prs = await githubAPI(`/repos/${fullRepo}/pulls?state=open&per_page=10`);
      if (prs.length === 0) return `*${fullRepo}* — No open PRs`;
      let text = `*Open PRs — ${fullRepo}*\n\n`;
      for (const p of prs) {
        text += `#${p.number} ${p.title.substring(0, 50)}\n`;
      }
      return text;
    }
    default: {
      const repo_info = await githubAPI(`/repos/${fullRepo}`);
      return `*${fullRepo}*\nStars: ${repo_info.stargazers_count} | Forks: ${repo_info.forks_count}\nDefault branch: \`${repo_info.default_branch}\`\nLast push: ${repo_info.pushed_at?.substring(0, 10) || 'N/A'}\nOpen issues: ${repo_info.open_issues_count}`;
    }
  }
}

async function fetchJSON(url, body) {
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return resp.json();
  } catch (err) {
    return null;
  }
}

async function fetchSSE(url) {
  try {
    const resp = await fetch(url);
    const text = await resp.text();
    for (const line of text.split('\n')) {
      if (line.startsWith('data:')) {
        const data = JSON.parse(line.substring(5).trim());
        if (Array.isArray(data) && data[0]) return data[0];
      }
    }
    return null;
  } catch (err) {
    return null;
  }
}

// ============================================================
// ROUTES
// ============================================================

// -- Keep-alive (mandatory for HF Spaces) --
app.get('/keep-alive', (req, res) => {
  res.json({
    status: 'alive',
    version: '2026.3.17-fullblast',
    uptime: Math.floor(process.uptime()),
    timestamp: new Date().toISOString(),
    memory: process.memoryUsage(),
  });
});

// -- Root / landing --
app.get('/', (req, res) => {
  res.json({
    name: 'OpenClaw Nomos Agent',
    version: '2026.3.17-fullblast',
    status: 'running',
    endpoints: {
      health: '/keep-alive',
      webhook: '/webhook/telegram',
      api: '/api/v1',
      spaces: '/api/v1/spaces',
      eval: '/api/v1/eval',
      query: '/api/v1/query',
      db: '/api/v1/db',
      metrics: '/api/v1/metrics',
    },
    infra: {
      spaces: spacesConfig.spaces.length,
      models: modelsConfig.priority.length,
      telegram: !!TELEGRAM_BOT_TOKEN,
    },
  });
});

// -- Telegram webhook --
app.post('/webhook/telegram', async (req, res) => {
  try {
    if (bot) {
      await handleTelegramUpdate(req.body);
    }
    res.sendStatus(200);
  } catch (err) {
    logger.error('Telegram webhook error:', err);
    res.sendStatus(200); // Always 200 for Telegram
  }
});

async function handleTelegramUpdate(update) {
  const msg = update.message;
  if (!msg || !msg.text) return;

  const chatId = msg.chat.id;
  const text = msg.text.trim();

  logger.info(`[TG] ${msg.from?.username || msg.from?.id}: ${text.substring(0, 80)}`);

  // Save to conversation history
  persistence.saveMessage(chatId, 'user', text);

  let reply;

  // Check commands
  const cmd = text.split(' ')[0].split('@')[0].toLowerCase();
  if (COMMANDS[cmd]) {
    reply = await COMMANDS[cmd](msg);
  } else {
    // AI completion with conversation context
    const history = persistence.getHistory(chatId, 10);
    const messages = history.map(h => ({ role: h.role, content: h.content }));
    messages.push({ role: 'user', content: text });

    try {
      const result = await getCompletion(messages);
      reply = result.content;
      logger.info(`[LLM] Model: ${result.model}, tokens: ${result.usage?.total_tokens || '?'}`);
    } catch (err) {
      logger.error('LLM error:', err);
      reply = 'Erreur LLM. Tous les modeles sont indisponibles. Reessayez.';
    }
  }

  if (reply) {
    // Telegram message limit: 4096 chars
    const chunks = splitMessage(reply, 4000);
    for (const chunk of chunks) {
      try {
        await bot.sendMessage(chatId, chunk, { parse_mode: 'Markdown' });
      } catch (err) {
        // Retry without markdown if parsing fails
        await bot.sendMessage(chatId, chunk).catch(() => {});
      }
    }
    persistence.saveMessage(chatId, 'assistant', reply);
  }

  // Notify admin of external conversations
  if (chatId !== ADMIN_TELEGRAM_ID && msg.from?.id !== ADMIN_TELEGRAM_ID) {
    const who = msg.from?.username || msg.from?.first_name || chatId;
    bot.sendMessage(ADMIN_TELEGRAM_ID,
      `[OpenClaw] ${who}: ${text.substring(0, 200)}`).catch(() => {});
  }
}

// -- REST API --

// Query any pipeline
app.post('/api/v1/query', async (req, res) => {
  try {
    const { question, pipeline = 'orchestrator', sector = 'finance' } = req.body;
    if (!question) return res.status(400).json({ error: 'question required' });

    const result = await spaceExecutor.queryPipeline(pipeline, question, sector);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Execute on any Space
app.post('/api/v1/exec', async (req, res) => {
  try {
    const { space, webhook, body = {} } = req.body;
    if (!space || !webhook) return res.status(400).json({ error: 'space and webhook required' });

    const result = await spaceExecutor.executeWebhook(space, webhook, body);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// List spaces with health
app.get('/api/v1/spaces', async (req, res) => {
  try {
    const health = await spaceExecutor.healthCheckAll();
    res.json({ spaces: spacesConfig.spaces, health });
  } catch (err) {
    res.json({ spaces: spacesConfig.spaces, health: null, error: err.message });
  }
});

// Run eval
app.post('/api/v1/eval', async (req, res) => {
  try {
    const { pipeline = 'standard', count = 5 } = req.body;
    const result = await spaceExecutor.runEval(pipeline, count);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Database queries (full admin access)
app.post('/api/v1/db', async (req, res) => {
  try {
    const { sql } = req.body;
    if (!sql) return res.status(400).json({ error: 'sql required' });
    const result = await infraBridge.querySupabase(sql);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Neo4j queries (full admin access)
app.post('/api/v1/neo4j', async (req, res) => {
  try {
    const { cypher } = req.body;
    if (!cypher) return res.status(400).json({ error: 'cypher required' });
    const result = await infraBridge.queryNeo4j(cypher);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GitHub API proxy
app.post('/api/v1/github', async (req, res) => {
  try {
    const { repo, action = 'status' } = req.body;
    if (!repo) return res.status(400).json({ error: 'repo required' });
    const result = await githubAction(repo, action);
    res.json({ result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Evolution status
app.get('/api/v1/evolution', async (req, res) => {
  try {
    const resp = await fetchJSON('https://lbjlincoln-nomos-nba-quant.hf.space/gradio_api/call/dash_status', { data: [] });
    if (resp?.event_id) {
      const result = await fetchSSE(`https://lbjlincoln-nomos-nba-quant.hf.space/gradio_api/call/dash_status/${resp.event_id}`);
      res.json({ status: 'ok', data: result });
    } else {
      res.json({ status: 'unreachable' });
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Metrics endpoint
app.get('/api/v1/metrics', async (req, res) => {
  try {
    const metrics = {
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      conversations: persistence.getStats(),
      timestamp: new Date().toISOString(),
    };
    res.json(metrics);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Trigger ingestion
app.post('/api/v1/ingest', async (req, res) => {
  try {
    const { sector = 'all' } = req.body;
    const result = await spaceExecutor.triggerIngestion(sector);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// LLM chat (direct OpenRouter)
app.post('/api/v1/chat', async (req, res) => {
  try {
    const { messages, model, maxTokens = 2000 } = req.body;
    if (!messages) return res.status(400).json({ error: 'messages required' });

    const result = await getCompletion(messages, {
      models: model ? [model] : undefined,
      maxTokens,
    });
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ============================================================
// DASHBOARD — Served from /dashboard
// ============================================================

app.get('/dashboard', (req, res) => {
  const dashPath = path.join(__dirname, 'public', 'dashboard.html');
  if (fs.existsSync(dashPath)) {
    res.sendFile(dashPath);
  } else {
    res.status(404).send('Dashboard not deployed yet. Upload dashboard.html to public/');
  }
});

// ============================================================
// AGENTIC LOOP API — Live data for dashboard
// ============================================================

// Get loop status
app.get('/api/v1/loop/status', (req, res) => {
  if (!agenticLoop) return res.json({ status: 'not_initialized' });
  res.json(agenticLoop.getStatus());
});

// Get live agent conversations
app.get('/api/v1/loop/conversations', (req, res) => {
  if (!agenticLoop) return res.json([]);
  const limit = parseInt(req.query.limit) || 50;
  const since = req.query.since; // ISO timestamp
  let convos = agenticLoop.getConversations(limit);
  if (since) {
    convos = convos.filter(c => c.timestamp > since);
  }
  res.json(convos);
});

// Get research log
app.get('/api/v1/loop/research', (req, res) => {
  if (!agenticLoop) return res.json([]);
  const limit = parseInt(req.query.limit) || 30;
  res.json(agenticLoop.getResearch(limit));
});

// Get evolution history for charts
app.get('/api/v1/loop/evolution-history', (req, res) => {
  if (!agenticLoop) return res.json([]);
  const limit = parseInt(req.query.limit) || 50;
  res.json(agenticLoop.getEvolutionHistory(limit));
});

// Manual trigger: force a research cycle
app.post('/api/v1/loop/trigger-research', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });
  agenticLoop._research().catch(e => logger.error('Manual research error:', e));
  res.json({ status: 'triggered', type: 'research' });
});

// Get errors log
app.get('/api/v1/loop/errors', (req, res) => {
  if (!agenticLoop) return res.json([]);
  res.json(agenticLoop.getErrors());
});

// Manual trigger: force a heal cycle
app.post('/api/v1/loop/trigger-heal', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });
  agenticLoop._heal().catch(e => logger.error('Manual heal error:', e));
  res.json({ status: 'triggered', type: 'heal' });
});

// Manual trigger: force a data check
app.post('/api/v1/loop/trigger-data', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });
  agenticLoop._dataCheck().catch(e => logger.error('Manual data check error:', e));
  res.json({ status: 'triggered', type: 'data-check' });
});

// Manual trigger: force an observe cycle
app.post('/api/v1/loop/trigger-observe', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });
  agenticLoop._observe().catch(e => logger.error('Manual observe error:', e));
  res.json({ status: 'triggered', type: 'observe' });
});

// Send a message as N.O.S (Claude CLI → OpenClaw conversation)
app.post('/api/v1/loop/message', async (req, res) => {
  const { message, agent = 'nos' } = req.body;
  if (!message) return res.status(400).json({ error: 'message required' });
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });

  // Log the incoming message
  agenticLoop._log(agent, message);

  // If from N.O.S, generate ADEMO response
  if (agent === 'nos') {
    try {
      const result = await getCompletion([{
        role: 'user',
        content: `N.O.S (Claude Code CLI, strategic commander) says: "${message}"\n\nRespond as ADEMO (research & execution agent). Be specific and actionable. Max 3 sentences.`
      }], { maxTokens: 300 });

      if (result.content) {
        agenticLoop._log('ademo', result.content);
        res.json({ status: 'ok', response: result.content, model: result.model });
        return;
      }
    } catch (err) {
      res.json({ status: 'ok', error: err.message });
      return;
    }
  }

  res.json({ status: 'ok' });
});

// ============================================================
// CRON JOBS — Self-monitoring
// ============================================================

// Health check every 5 minutes
cron.schedule('*/5 * * * *', async () => {
  try {
    const health = await spaceExecutor.healthCheckAll();
    const down = Object.entries(health).filter(([, s]) => !s.up);

    if (down.length > 0 && bot) {
      const names = down.map(([n]) => n).join(', ');
      bot.sendMessage(ADMIN_TELEGRAM_ID,
        `[OpenClaw Alert] Spaces DOWN: ${names}`).catch(() => {});
    }

    logger.info(`Health check: ${Object.keys(health).length - down.length}/${Object.keys(health).length} UP`);
  } catch (err) {
    logger.error('Health cron error:', err);
  }
});

// Keep-alive self-ping every 4 minutes (prevent HF sleep)
cron.schedule('*/4 * * * *', () => {
  const url = `http://localhost:${PORT}/keep-alive`;
  http.get(url, (res) => {
    let data = '';
    res.on('data', c => data += c);
    res.on('end', () => logger.debug('Self-ping OK'));
  }).on('error', (err) => {
    logger.warn('Self-ping failed:', err.message);
  });
});

// Save conversation history every 10 minutes
cron.schedule('*/10 * * * *', () => {
  persistence.flush();
  logger.debug('Persistence flushed');
});

// ============================================================
// HELPERS
// ============================================================

function splitMessage(text, maxLen) {
  if (text.length <= maxLen) return [text];
  const chunks = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= maxLen) {
      chunks.push(remaining);
      break;
    }
    let splitAt = remaining.lastIndexOf('\n', maxLen);
    if (splitAt < maxLen / 2) splitAt = maxLen;
    chunks.push(remaining.substring(0, splitAt));
    remaining = remaining.substring(splitAt);
  }
  return chunks;
}

function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}h ${m}m ${s}s`;
}

// ============================================================
// STARTUP
// ============================================================

async function start() {
  // Set Telegram webhook if token provided
  if (bot && TELEGRAM_BOT_TOKEN) {
    const webhookUrl = `${HF_SPACE_URL}/webhook/telegram`;
    try {
      await bot.setWebHook(webhookUrl);
      logger.info(`Telegram webhook set: ${webhookUrl}`);
    } catch (err) {
      logger.warn(`Telegram webhook failed: ${err.message}`);
      logger.info('Falling back to polling mode...');
      bot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: true });
      bot.on('message', async (msg) => {
        await handleTelegramUpdate({ message: msg });
      });
      logger.info('Telegram polling started');
    }
  }

  // Initialize persistence
  persistence.init();

  // Ensure dashboard directory
  try { fs.mkdirSync(path.join(__dirname, 'public'), { recursive: true }); } catch {}

  // S10 base URL for evolution API
  const S10_URL = 'https://lbjlincoln-nomos-nba-quant.hf.space';

  // Fetch evolution status via new FastAPI endpoint (fallback to Gradio SSE)
  async function fetchEvo() {
    // Try new FastAPI JSON endpoint first
    try {
      const resp = await fetch(`${S10_URL}/api/status`, { signal: AbortSignal.timeout(15000) });
      if (resp.ok) return await resp.json();
    } catch {}
    // Fallback to Gradio SSE
    try {
      const resp = await fetchJSON(`${S10_URL}/gradio_api/call/dash_status`, { data: [] });
      if (resp?.event_id) {
        return await fetchSSE(`${S10_URL}/gradio_api/call/dash_status/${resp.event_id}`);
      }
    } catch {}
    return null;
  }

  // Call S10 remote control API (OpenClaw → S10 direct mutation)
  async function callS10(endpoint, body = {}) {
    try {
      const resp = await fetch(`${S10_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(15000),
      });
      if (resp.ok) return await resp.json();
      return { error: `HTTP ${resp.status}` };
    } catch (err) {
      return { error: err.message };
    }
  }

  agenticLoop = new AgenticLoop({
    getCompletion,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
    fetchEvolution: fetchEvo,
    callS10,
  });
  agenticLoop.start();

  // Start Express
  app.listen(PORT, '0.0.0.0', () => {
    logger.info('='.repeat(60));
    logger.info(`OpenClaw v2026.3.17 started on port ${PORT}`);
    logger.info(`Telegram: ${TELEGRAM_BOT_TOKEN ? 'ACTIVE' : 'DISABLED'}`);
    logger.info(`OpenRouter: ${OPENROUTER_API_KEY ? 'CONFIGURED' : 'NOT SET'}`);
    logger.info(`Agentic Loop: STARTED (Karpathy mode)`);
    logger.info(`Dashboard: /dashboard`);
    logger.info(`Models: ${modelsConfig.priority.length} priority + ${modelsConfig.fallback.length} fallback`);
    logger.info('='.repeat(60));

    // Notify admin on startup
    if (bot && TELEGRAM_BOT_TOKEN) {
      bot.sendMessage(ADMIN_TELEGRAM_ID,
        '*OpenClaw v2026.3.17 — NBA Quant Mode*\nAgentic loop started. Karpathy 24/7 active.\nDashboard: /dashboard', {
          parse_mode: 'Markdown'
        }).catch(() => {});
    }
  });
}

start().catch(err => {
  logger.error('Startup failed:', err);
  process.exit(1);
});
