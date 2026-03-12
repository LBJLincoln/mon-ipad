/**
 * OpenClaw v2026.3.11-beta.1 — Nomos AI Operations Agent
 *
 * Express server deployed on HF Spaces (Docker, port 7860).
 * Full infrastructure access: all HF Spaces, databases, LLM proxy.
 * Telegram bot webhook for remote command & control.
 *
 * Target Space: Nomos42/worker-2
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

// Request logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    if (req.path !== '/keep-alive') {
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

const SYSTEM_PROMPT = `Tu es OpenClaw, l'agent IA d'operations de Nomos Sector AI.
Tu tournes sur un HF Space Docker et tu as acces a TOUTE l'infrastructure :
- 14 HF Spaces (n8n engines, LiteLLM, embeddings, docling)
- 4 pipelines RAG (Standard, Graph, Quantitative, Orchestrator)
- Bases de donnees : Supabase (43K docs), Neo4j (72K nodes), Pinecone (58K vectors)
- LiteLLM proxy avec 13 providers et rotation automatique

Tu peux :
1. Executer des commandes sur n'importe quel Space via webhooks
2. Lancer des evaluations sur les pipelines
3. Diagnostiquer et reparer des problemes
4. Ingerer de nouveaux documents
5. Monitorer la sante de l'infrastructure
6. Deployer des workflows n8n
7. Interroger directement les bases de donnees

Reponds de maniere concise et technique. Utilise le francais sauf si on te parle en anglais.
Format tes reponses pour Telegram (Markdown).`;

/**
 * Get LLM completion with model fallback chain
 */
async function getCompletion(messages, options = {}) {
  const modelChain = options.models || modelsConfig.priority;

  for (const model of modelChain) {
    try {
      const completion = await openrouter.chat.completions.create({
        model: model,
        messages: [{ role: 'system', content: SYSTEM_PROMPT }, ...messages],
        max_tokens: options.maxTokens || 2000,
        temperature: options.temperature || 0.4,
        stream: false,
      });
      return {
        content: completion.choices[0]?.message?.content || '',
        model: model,
        usage: completion.usage,
      };
    } catch (err) {
      logger.warn(`Model ${model} failed: ${err.message}`);
      continue;
    }
  }
  throw new Error('All models in fallback chain failed');
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
    if (/\b(drop|delete|truncate|alter|update|insert)\b/i.test(sql)) {
      return 'Read-only queries only. No mutations allowed via Telegram.';
    }
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
    if (/\b(delete|detach|remove|create|merge|set)\b/i.test(cypher)) {
      return 'Read-only queries only. No mutations allowed via Telegram.';
    }
    try {
      const result = await infraBridge.queryNeo4j(cypher);
      return `*Neo4j Result*\n\`\`\`\n${JSON.stringify(result.slice(0, 10), null, 2)}\n\`\`\``;
    } catch (err) {
      return `Cypher Error: ${err.message}`;
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
// ROUTES
// ============================================================

// -- Keep-alive (mandatory for HF Spaces) --
app.get('/keep-alive', (req, res) => {
  res.json({
    status: 'alive',
    version: '2026.3.11-beta.1',
    uptime: Math.floor(process.uptime()),
    timestamp: new Date().toISOString(),
    memory: process.memoryUsage(),
  });
});

// -- Root / landing --
app.get('/', (req, res) => {
  res.json({
    name: 'OpenClaw Nomos Agent',
    version: '2026.3.11-beta.1',
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

// Database queries (read-only)
app.post('/api/v1/db', async (req, res) => {
  try {
    const { sql } = req.body;
    if (!sql) return res.status(400).json({ error: 'sql required' });
    if (/\b(drop|delete|truncate|alter|update|insert)\b/i.test(sql)) {
      return res.status(403).json({ error: 'Read-only queries only' });
    }
    const result = await infraBridge.querySupabase(sql);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Neo4j queries (read-only)
app.post('/api/v1/neo4j', async (req, res) => {
  try {
    const { cypher } = req.body;
    if (!cypher) return res.status(400).json({ error: 'cypher required' });
    if (/\b(delete|detach|remove|create|merge|set)\b/i.test(cypher)) {
      return res.status(403).json({ error: 'Read-only queries only' });
    }
    const result = await infraBridge.queryNeo4j(cypher);
    res.json(result);
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

  // Start Express
  app.listen(PORT, '0.0.0.0', () => {
    logger.info('='.repeat(60));
    logger.info(`OpenClaw v2026.3.11-beta.1 started on port ${PORT}`);
    logger.info(`Telegram: ${TELEGRAM_BOT_TOKEN ? 'ACTIVE' : 'DISABLED'}`);
    logger.info(`OpenRouter: ${OPENROUTER_API_KEY ? 'CONFIGURED' : 'NOT SET'}`);
    logger.info(`Spaces configured: ${spacesConfig.spaces.length}`);
    logger.info(`Models configured: ${modelsConfig.priority.length} priority + ${modelsConfig.fallback.length} fallback`);
    logger.info(`Admin Telegram ID: ${ADMIN_TELEGRAM_ID}`);
    logger.info('='.repeat(60));

    // Notify admin on startup
    if (bot && TELEGRAM_BOT_TOKEN) {
      bot.sendMessage(ADMIN_TELEGRAM_ID,
        '*OpenClaw v2026.3.11-beta.1 started*\nAll systems operational.', {
          parse_mode: 'Markdown'
        }).catch(() => {});
    }
  });
}

start().catch(err => {
  logger.error('Startup failed:', err);
  process.exit(1);
});
