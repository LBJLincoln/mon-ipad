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
const VMBridge = require('./lib/vm-bridge');
const OrderExecutor = require('./lib/order-executor');
const ModelHealthMonitor = require('./lib/model-health-monitor');
const RuleEngine = require('./lib/rule-engine');
const DataWorker = require('./lib/data-worker');
const Watchdog = require('./lib/watchdog');
const A2AProtocol = require('./lib/a2a-protocol');

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

// VM Bridge — SSH remote execution (same power as Claude Code CLI)
const vmBridge = new VMBridge({
  host: process.env.VM_HOST || '34.136.180.66',
  username: process.env.VM_USER || 'termius',
  privateKey: process.env.SSH_PRIVATE_KEY || '',
});

// ============================================================
// AGENTIC LOOP (Karpathy-style 24/7)
// ============================================================

let agenticLoop = null; // Initialized after LLM client setup
let orderExecutor = null;
let modelMonitor = null;
let ruleEngine = null;
let dataWorker = null;
let watchdog = null;
let a2aProtocol = null;

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
  if (!modelMonitor || modelMonitor.litellm.alive !== false) {
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
          signal: AbortSignal.timeout(30000),
        });
        const data = await resp.json();
        if (data.choices && data.choices[0]?.message?.content) {
          if (ruleEngine) ruleEngine.resetLLMFailures();
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
  }

  // 2. Use Model Health Monitor's live ranked list of working free models
  // If alive list is empty (race condition at startup, or all probed dead), use static fallback
  const DEFAULT_FREE_MODELS = [
    'deepseek/deepseek-r1-0528:free',
    'deepseek/deepseek-chat-v3-0324:free',
    'qwen/qwen3-235b-a22b:free',
    'qwen/qwen3-32b:free',
    'nvidia/nemotron-3-super-120b-a12b:free',
    'meta-llama/llama-4-maverick:free',
    'meta-llama/llama-4-scout:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'microsoft/phi-4-reasoning-plus:free',
    'microsoft/phi-4-reasoning:free',
    'mistralai/mistral-small-3.1-24b-instruct:free',
    'google/gemma-3-27b-it:free',
    'google/gemma-3-12b-it:free',
    'arcee-ai/trinity-large-preview:free',
    'rekaai/reka-flash-3:free',
    'qwen/qwen-2.5-coder-32b-instruct:free',
    'nousresearch/deephermes-3-llama-3-8b-preview:free',
  ];
  const monitorModels = modelMonitor ? modelMonitor.getAliveModels() : [];
  const aliveModels = monitorModels.length > 0 ? monitorModels : DEFAULT_FREE_MODELS;

  for (const model of aliveModels) {
    try {
      const completion = await openrouter.chat.completions.create({
        model,
        messages: allMessages,
        max_tokens: maxTokens,
        temperature,
        stream: false,
      });
      const content = completion.choices?.[0]?.message?.content || '';
      if (content.length > 0) {
        if (modelMonitor) modelMonitor.markAlive(model);
        if (ruleEngine) ruleEngine.resetLLMFailures();
        return { content, model, usage: completion.usage };
      }
    } catch (err) {
      logger.warn(`OpenRouter ${model} failed: ${err.message}`);
      if (modelMonitor) modelMonitor.markFailed(model);
    }
  }

  // 3. If ALL failed, record for rule engine
  if (ruleEngine) ruleEngine.recordLLMFailure();
  logger.error(`ALL LLM providers failed. Alive models: ${aliveModels.length}. Rule engine taking over: ${ruleEngine?.shouldTakeOver()}`);
  throw new Error('ALL LLM providers failed — rule engine active for critical actions');
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
    return `⚡ *OpenClaw v4 — DATA-DRIVEN AUTONOMOUS*
Agent IA autonome NOMOS42 NBA Quant AI
A2A Protocol + Data Worker + Watchdog

*DATA & MONITORING:*
/data — Odds & scores collection status
/watchdog — S10 evolution monitoring
/a2a — Adam ↔ Eve protocol status
/loop — Agentic loop cycles

*ORDRES EN LANGAGE NATUREL:*
"boost mutation to 0.2"
"restart S10"
"status evolution"
"fetch odds"

*Infrastructure:*
/status — Sante complete
/spaces — HF Spaces actifs
/orders — Liste des ordres

*VM Remote (SSH):*
/vm <cmd> — Executer sur la VM
/vm sysinfo — Info systeme VM

*Git & Code:*
/git <repo> [action] — GitHub status
/gitpush <repo> <msg> — Commit + push
/read <path> — Lire fichier VM

*HF Space Management:*
/hfspace <id> <action> — restart/pause/resume
/deploy <space> — Deployer
/logs <space> — Logs Space

*Databases:*
/db <sql> — Supabase SQL
/neo4j <cypher> — Neo4j Cypher

*AI & Evolution:*
/evolution — Status GA S10
/heal — Self-healing scan
/eval — Smoke test`;
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
    let text = `*HF Spaces (${spacesConfig.spaces.length} actifs)*\n\n`;
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

  '/vm': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const command = msg.text.replace('/vm', '').trim();
    if (!command) return `*VM Remote Execution*\n\nUsage: /vm <command>\n\nExamples:\n\`/vm ls -la\`\n\`/vm git status\`\n\`/vm python3 scripts/nba-data-server.py\`\n\`/vm sysinfo\`\n\`/vm ping\``;

    // Special sub-commands
    if (command === 'ping') {
      const result = await vmBridge.ping();
      return result.reachable
        ? `*VM Online* — ${result.latency}ms latency`
        : `*VM Unreachable* — ${result.error}`;
    }
    if (command === 'sysinfo') {
      const info = await vmBridge.sysinfo();
      if (info.error) return `VM Error: ${info.error}`;
      return `*VM System Info*\nHost: \`${info.hostname}\`\nUptime: ${info.uptime}\nDisk: ${info.disk}\nMemory: ${info.mem}\nLoad: ${info.load}`;
    }

    await bot.sendMessage(msg.chat.id, `Executing on VM...`, { parse_mode: 'Markdown' });
    try {
      const result = await vmBridge.exec(command, { timeout: 60000 });
      let output = result.stdout || result.stderr || '(no output)';
      if (output.length > 3500) output = output.substring(0, 3500) + '\n...(truncated)';
      return `*VM Output* (code: ${result.code})\n\`\`\`\n${output}\n\`\`\``;
    } catch (err) {
      return `VM Error: ${err.message}`;
    }
  },

  '/gitpush': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const args = msg.text.replace('/gitpush', '').trim();
    if (!args) return 'Usage: /gitpush <repo> <commit message>';
    const parts = args.split(' ');
    const repo = parts[0];
    const commitMsg = parts.slice(1).join(' ') || 'Update from OpenClaw';

    await bot.sendMessage(msg.chat.id, `Git commit+push on *${repo}*...`, { parse_mode: 'Markdown' });
    try {
      const result = await vmBridge.gitCommitPush(repo, commitMsg);
      return `*Git Push — ${repo}*\n\`\`\`\n${(result.stdout + '\n' + result.stderr).substring(0, 3000)}\n\`\`\``;
    } catch (err) {
      return `Git Error: ${err.message}`;
    }
  },

  '/hfspace': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const args = msg.text.replace('/hfspace', '').trim();
    if (!args) return `*HF Space Management*\n\nUsage: /hfspace <space-id> <action>\nActions: restart, pause, resume, logs\n\nExamples:\n\`/hfspace lbjlincoln/nomos-nba-quant restart\`\n\`/hfspace Nomos42/nomos-worker-2 logs\``;

    const parts = args.split(' ');
    const spaceId = parts[0];
    const action = parts[1] || 'restart';

    await bot.sendMessage(msg.chat.id, `HF Space *${action}* on *${spaceId}*...`, { parse_mode: 'Markdown' });
    try {
      const result = await vmBridge.hfSpaceAction(spaceId, action);
      return `*HF ${action} — ${spaceId}*\n\`\`\`\n${(result.stdout || result.stderr || 'OK').substring(0, 3000)}\n\`\`\``;
    } catch (err) {
      return `HF Error: ${err.message}`;
    }
  },

  '/models_health': async (msg) => {
    if (!modelMonitor) return 'Model monitor pas initialise.';
    const s = modelMonitor.getStatus();
    let text = `*Model Health Monitor*
Alive: *${s.alive}* / ${s.total} | Dead: ${s.dead} | Untested: ${s.untested}
Best: \`${s.bestModel}\`
LiteLLM: ${s.litellm.alive ? 'UP' : 'DOWN'}
Probes: ${s.totalProbes} | Switches: ${s.switchCount}

*Top 5 alive:*\n`;
    for (const m of s.top5) {
      text += `- \`${m}\`\n`;
    }
    return text;
  },

  '/orders': async (msg) => {
    return `*Ordres disponibles (langage naturel):*

*GA Parameters:*
"set mutation to 0.15"
"set population to 200"
"set crossover to 0.85"
"set features to 250"

*Actions immédiates:*
"diversify" / "boost mutation"
"reset population"
"inject features"
"emergency diversify"

*Mode:*
"mode aggressive" (mutation 0.18, pop 200)
"mode conservative" (mutation 0.06, pop 100)

*Loop control:*
"force research" / "force heal"
"force observe" / "force improve"
"pause loop" / "resume loop"

*Rollback:*
"rollback to last good config"
"snapshot config"

*Space management:*
"restart S10" / "restart S11"
"check VM"

*Status:*
"status evolution"
"status anticipation"
"status loop"
"show research" / "show errors"

Tape directement — pas besoin de /commande !`;
  },

  '/watchdog': async (msg) => {
    if (!watchdog) return 'Watchdog not initialized.';
    const s = watchdog.getStatus();
    let text = `*Watchdog (Observation Only)*
Checks: ${s.stats.checks} | Alerts: ${s.stats.alertsSent}
Spaces Restarted: ${s.stats.spacesRestarted}\n`;

    if (s.trends) {
      const t = s.trends;
      text += `\n*Current:*
  Brier: ${t.current.brier?.toFixed(4) || '?'} | Gen: ${t.current.generation || '?'}
  Features: ${t.current.features || '?'} | Stagnation: ${t.current.stagnation ?? '?'}`;
      if (t.brierTrend !== null) {
        const emoji = t.brierTrend < 0 ? '📉' : t.brierTrend > 0 ? '📈' : '➡️';
        text += `\n  Brier trend (1h): ${emoji} ${t.brierTrend > 0 ? '+' : ''}${t.brierTrend}`;
      }
    }

    if (s.recentAlerts.length > 0) {
      text += '\n\n*Recent Alerts:*\n';
      for (const a of s.recentAlerts.slice(-5)) {
        text += `[${a.level}] ${a.message}\n`;
      }
    }
    return text;
  },

  '/data': async (msg) => {
    if (!dataWorker) return 'Data worker not initialized.';
    const s = dataWorker.getStatus();
    let text = `*Data Worker*
Odds API: ${s.oddsApiKey}
Supabase: ${s.supabase}

*Stats:*
  Odds fetches: ${s.stats.oddsFetches}
  Odds stored: ${s.stats.oddsStored}
  Scores fetches: ${s.stats.scoresFetches}
  Games tracked: ${s.stats.gamesTracked}
  Errors: ${s.stats.errors}
  API quota left: ${s.stats.apiQuotaRemaining || '?'}

Last odds: ${s.lastOddsFetch || 'never'}
Last scores: ${s.lastScoresFetch || 'never'}`;

    if (s.recentMovements.length > 0) {
      text += '\n\n*Recent Line Movements:*\n';
      for (const m of s.recentMovements.slice(-5)) {
        text += `${m.steam ? '🔥' : '📊'} ${m.game}: ${m.prev_spread} → ${m.curr_spread}\n`;
      }
    }
    return text;
  },

  '/a2a': async (msg) => {
    if (!a2aProtocol) return 'A2A protocol not initialized.';
    const s = a2aProtocol.getStatus();
    let text = `*A2A Protocol (Adam ↔ Eve)*
Commands: ${s.stats.commandsReceived} received, ${s.stats.commandsExecuted} executed
Reports: ${s.stats.reportsPosted} | Alerts: ${s.stats.alertsPosted}
Inbox: ${s.unreadInbox} unread / ${s.totalInbox} total
Last command: ${s.stats.lastCommandAt || 'never'}
Last report: ${s.stats.lastReportAt || 'never'}`;

    if (s.recentCommands.length > 0) {
      text += '\n\n*Recent Commands:*\n';
      for (const c of s.recentCommands.slice(0, 3)) {
        text += `[${c.status}] ${c.action}\n`;
      }
    }
    return text;
  },

  '/loop': async (msg) => {
    if (!agenticLoop) return 'Agentic loop not initialized.';
    const s = agenticLoop.getStatus();
    const evo = s.state?.lastEvoStatus;
    return `*Agentic Loop v4 — Data-Driven*
Running: ${s.running ? '✅' : '❌'} | Uptime: ${s.uptime}
Cycles: ${s.state?.cycles || 0}

*S10 Evolution:*
  Brier: ${evo?.brier?.toFixed(4) || '?'} | Gen: ${evo?.generation || '?'}
  Features: ${evo?.features || '?'} | Pop: ${evo?.population || '?'}
  Stagnation: ${evo?.stagnation ?? '?'}

*Last Cycles:*
  Observe: ${s.state?.lastObserve || 'never'}
  Data: ${s.state?.lastData || 'never'}
  Health: ${s.state?.lastHealth || 'never'}
  Report: ${s.state?.lastReport || 'never'}
  Heartbeat: ${s.state?.lastHeartbeat || 'never'}

*Errors (last 24h):* ${s.state?.errors?.filter(e => new Date(e.timestamp) > new Date(Date.now() - 86400000)).length || 0}`;
  },

  '/read': async (msg) => {
    if (msg.from.id !== ADMIN_TELEGRAM_ID) return 'Admin only.';
    const filePath = msg.text.replace('/read', '').trim();
    if (!filePath) return 'Usage: /read <file-path>';

    try {
      const content = await vmBridge.readFile(filePath);
      if (content.length > 3500) {
        return `*File: ${filePath}*\n\`\`\`\n${content.substring(0, 3500)}\n...(truncated)\n\`\`\``;
      }
      return `*File: ${filePath}*\n\`\`\`\n${content}\n\`\`\``;
    } catch (err) {
      return `Read Error: ${err.message}`;
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
    version: '2026.3.18-v4-data-driven',
    uptime: Math.floor(process.uptime()),
    timestamp: new Date().toISOString(),
    memory: process.memoryUsage(),
  });
});

// -- Root / landing --
app.get('/', (req, res) => {
  res.json({
    name: 'OpenClaw Nomos Agent',
    version: '2026.3.18-v4-data-driven',
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
      vm_exec: '/api/v1/vm/exec',
      vm_git: '/api/v1/vm/git',
      vm_read: '/api/v1/vm/read',
      vm_write: '/api/v1/vm/write',
      github_file: '/api/v1/github/file',
      hf_space: '/api/v1/vm/hf-space',
    },
    infra: {
      spaces: spacesConfig.spaces.length,
      models: modelsConfig.priority.length,
      telegram: !!TELEGRAM_BOT_TOKEN,
      vm_ssh: !!process.env.SSH_PRIVATE_KEY,
      github: !!GH_TOKEN,
    },
  });
});

// -- Telegram webhook --
// CRITICAL: respond 200 IMMEDIATELY, then process async.
// Telegram webhooks timeout after ~10s — our handlers (healthcheck, DB queries) can take longer.
app.post('/webhook/telegram', (req, res) => {
  res.sendStatus(200);  // ACK immediately — prevents Telegram read timeout
  if (bot) {
    handleTelegramUpdate(req.body).catch(err => {
      logger.error('Telegram handler error:', err);
    });
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

  // Check commands first
  const cmd = text.split(' ')[0].split('@')[0].toLowerCase();
  if (COMMANDS[cmd]) {
    reply = await COMMANDS[cmd](msg);
  }
  // Then check if it's a natural language order (only for admin)
  else if (orderExecutor && msg.from?.id === ADMIN_TELEGRAM_ID && orderExecutor.isOrder(text)) {
    logger.info(`[ORDER] Detected order from admin: ${text.substring(0, 80)}`);
    const result = await orderExecutor.execute(text);
    if (result && result.executed) {
      reply = `*ORDER EXECUTED* [${result.intent}]\n\n${result.result}`;
    }
  }
  // Fallback: AI completion with conversation context
  if (!reply) {
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

// ============================================================
// VM BRIDGE API — Full VM access (same power as Claude Code CLI)
// ============================================================

// Execute command on VM
app.post('/api/v1/vm/exec', async (req, res) => {
  try {
    const { command, cwd, timeout } = req.body;
    if (!command) return res.status(400).json({ error: 'command required' });
    const result = await vmBridge.exec(command, { cwd, timeout });
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// VM ping/health
app.get('/api/v1/vm/ping', async (req, res) => {
  try {
    const result = await vmBridge.ping();
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// VM system info
app.get('/api/v1/vm/sysinfo', async (req, res) => {
  try {
    const info = await vmBridge.sysinfo();
    res.json(info);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Git operations on VM repos
app.post('/api/v1/vm/git', async (req, res) => {
  try {
    const { repo, command } = req.body;
    if (!repo || !command) return res.status(400).json({ error: 'repo and command required' });
    const result = await vmBridge.git(repo, command);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Git commit + push
app.post('/api/v1/vm/git-push', async (req, res) => {
  try {
    const { repo, message, files = '.' } = req.body;
    if (!repo || !message) return res.status(400).json({ error: 'repo and message required' });
    const result = await vmBridge.gitCommitPush(repo, message, files);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Read file from VM
app.post('/api/v1/vm/read', async (req, res) => {
  try {
    const { path: filePath } = req.body;
    if (!filePath) return res.status(400).json({ error: 'path required' });
    const content = await vmBridge.readFile(filePath);
    res.json({ content, path: filePath });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Write file to VM
app.post('/api/v1/vm/write', async (req, res) => {
  try {
    const { path: filePath, content } = req.body;
    if (!filePath || content === undefined) return res.status(400).json({ error: 'path and content required' });
    const result = await vmBridge.writeFile(filePath, content);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// HF Space management via VM
app.post('/api/v1/vm/hf-space', async (req, res) => {
  try {
    const { spaceId, action, params = {} } = req.body;
    if (!spaceId || !action) return res.status(400).json({ error: 'spaceId and action required' });
    const result = await vmBridge.hfSpaceAction(spaceId, action, params);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GitHub file operations (create/update files via API)
app.post('/api/v1/github/file', async (req, res) => {
  try {
    const { repo, path: filePath, content, message, branch = 'main' } = req.body;
    if (!repo || !filePath || content === undefined) {
      return res.status(400).json({ error: 'repo, path, and content required' });
    }

    const fullRepo = repo.includes('/') ? repo : `${GH_OWNER}/${repo}`;
    const b64Content = Buffer.from(content).toString('base64');

    // Check if file exists (to get sha for updates)
    let sha;
    try {
      const existing = await githubAPI(`/repos/${fullRepo}/contents/${filePath}?ref=${branch}`);
      sha = existing.sha;
    } catch {}

    const body = {
      message: message || `Update ${filePath} via OpenClaw`,
      content: b64Content,
      branch,
    };
    if (sha) body.sha = sha;

    const result = await githubAPI(`/repos/${fullRepo}/contents/${filePath}`, 'PUT', body);
    res.json({ ok: true, sha: result.content?.sha, url: result.content?.html_url });
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
// AGENTIC LOOP API — v4 data-driven endpoints
// ============================================================

// Get loop status
app.get('/api/v1/loop/status', (req, res) => {
  if (!agenticLoop) return res.json({ status: 'not_initialized' });
  res.json(agenticLoop.getStatus());
});

// Manual trigger: force observe
app.post('/api/v1/loop/trigger-observe', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });
  agenticLoop._cycle('observe').catch(e => logger.error('Manual observe error:', e));
  res.json({ status: 'triggered', type: 'observe' });
});

// Manual trigger: force data fetch
app.post('/api/v1/loop/trigger-data', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });
  agenticLoop._cycle('data').catch(e => logger.error('Manual data error:', e));
  res.json({ status: 'triggered', type: 'data' });
});

// Manual trigger: force health check
app.post('/api/v1/loop/trigger-health', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });
  agenticLoop._cycle('health').catch(e => logger.error('Manual health error:', e));
  res.json({ status: 'triggered', type: 'health' });
});

// Manual trigger: force heartbeat
app.post('/api/v1/loop/trigger-heartbeat', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Loop not initialized' });
  agenticLoop._cycle('heartbeat').catch(e => logger.error('Manual heartbeat error:', e));
  res.json({ status: 'triggered', type: 'heartbeat' });
});

// ============================================================
// A2A PROTOCOL API — Adam ↔ Eve communication
// ============================================================

// Adam sends a command to Eve
app.post('/api/v1/a2a/command', async (req, res) => {
  if (!a2aProtocol) return res.status(503).json({ error: 'A2A not initialized' });
  const { action, params } = req.body;
  if (!action) return res.status(400).json({ error: 'action required' });
  const result = await a2aProtocol.receiveCommand({ action, params });
  res.json(result);
});

// Adam reads Eve's inbox (reports, alerts, data)
app.get('/api/v1/a2a/inbox', (req, res) => {
  if (!a2aProtocol) return res.json([]);
  const options = {
    unread: req.query.unread === 'true',
    limit: parseInt(req.query.limit) || 50,
    level: req.query.level,
    type: req.query.type,
    since: req.query.since,
  };
  res.json(a2aProtocol.getInbox(options));
});

// Adam acknowledges messages
app.post('/api/v1/a2a/ack', (req, res) => {
  if (!a2aProtocol) return res.status(503).json({ error: 'A2A not initialized' });
  const { ids, all } = req.body;
  if (all) {
    res.json(a2aProtocol.acknowledgeAll());
  } else if (ids && Array.isArray(ids)) {
    res.json(a2aProtocol.acknowledge(ids));
  } else {
    res.status(400).json({ error: 'ids array or all:true required' });
  }
});

// A2A protocol status
app.get('/api/v1/a2a/status', (req, res) => {
  if (!a2aProtocol) return res.json({ status: 'not_initialized' });
  res.json(a2aProtocol.getStatus());
});

// Command history
app.get('/api/v1/a2a/commands', (req, res) => {
  if (!a2aProtocol) return res.json([]);
  const limit = parseInt(req.query.limit) || 20;
  res.json(a2aProtocol.getCommands(limit));
});

// ============================================================
// WATCHDOG API — Statistical monitoring
// ============================================================

// Get watchdog status
app.get('/api/v1/watchdog/status', (req, res) => {
  if (!watchdog) return res.json({ status: 'not_initialized' });
  res.json(watchdog.getStatus());
});

// Get trends
app.get('/api/v1/watchdog/trends', (req, res) => {
  if (!watchdog) return res.json(null);
  res.json(watchdog.getTrends());
});

// Get metrics history
app.get('/api/v1/watchdog/metrics', (req, res) => {
  if (!watchdog) return res.json([]);
  const limit = parseInt(req.query.limit) || 100;
  res.json(watchdog.metrics.slice(-limit));
});

// ============================================================
// DATA WORKER API — Real NBA data
// ============================================================

// Get data worker status
app.get('/api/v1/data/status', (req, res) => {
  if (!dataWorker) return res.json({ status: 'not_initialized' });
  res.json(dataWorker.getStatus());
});

// Force odds fetch
app.post('/api/v1/data/fetch-odds', async (req, res) => {
  if (!dataWorker) return res.status(503).json({ error: 'Not initialized' });
  const result = await dataWorker.fetchOdds();
  res.json(result || { error: 'Fetch failed' });
});

// Force scores fetch
app.post('/api/v1/data/fetch-scores', async (req, res) => {
  if (!dataWorker) return res.status(503).json({ error: 'Not initialized' });
  const result = await dataWorker.fetchScores();
  res.json(result || { error: 'Fetch failed' });
});

// Compute CLV
app.post('/api/v1/data/clv', async (req, res) => {
  if (!dataWorker) return res.status(503).json({ error: 'Not initialized' });
  const result = await dataWorker.computeCLV();
  res.json(result || { error: 'CLV computation failed' });
});

// Get line movements
app.get('/api/v1/data/movements', (req, res) => {
  if (!dataWorker) return res.json([]);
  const limit = parseInt(req.query.limit) || 20;
  res.json(dataWorker.lineMovements.slice(-limit));
});

// ============================================================
// ORDER EXECUTOR API
// ============================================================

// Execute an order via REST (same as Telegram natural language)
app.post('/api/v1/order', async (req, res) => {
  if (!orderExecutor) return res.status(503).json({ error: 'Not initialized' });
  const { text } = req.body;
  if (!text) return res.status(400).json({ error: 'text required' });
  const result = await orderExecutor.execute(text);
  res.json(result || { executed: false, reason: 'Not recognized as an order' });
});

// Get order history
app.get('/api/v1/order/history', (req, res) => {
  if (!orderExecutor) return res.json([]);
  res.json(orderExecutor.getHistory());
});

// ============================================================
// MODEL HEALTH MONITOR API
// ============================================================

// Get model health status
app.get('/api/v1/models/health', (req, res) => {
  if (!modelMonitor) return res.json({ status: 'not_initialized' });
  res.json(modelMonitor.getStatus());
});

// Force probe all models
app.post('/api/v1/models/probe', async (req, res) => {
  if (!modelMonitor) return res.status(503).json({ error: 'Not initialized' });
  const alive = await modelMonitor._probeAll();
  res.json({ alive: alive.length, models: alive.slice(0, 10) });
});

// Discover new free models
app.post('/api/v1/models/discover', async (req, res) => {
  if (!modelMonitor) return res.status(503).json({ error: 'Not initialized' });
  await modelMonitor.discoverFreeModels();
  res.json({ total: Object.keys(modelMonitor.models).length });
});

// Rule engine status
app.get('/api/v1/rules/status', (req, res) => {
  if (!ruleEngine) return res.json({ status: 'not_initialized' });
  res.json(ruleEngine.getStatus());
});

// ============================================================
// CRON JOBS — Self-monitoring
// ============================================================

// Watchdog handles health checks now (every 10 min via agentic loop)

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

  // Initialize Model Health Monitor — NEVER let thinking stop
  modelMonitor = new ModelHealthMonitor({
    openrouterApiKey: OPENROUTER_API_KEY,
    openrouterClient: openrouter,
    litellmUrl: LITELLM_URL,
    litellmKey: LITELLM_KEY,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
  });
  modelMonitor.start();
  // Discover new free models from OpenRouter API at startup
  modelMonitor.discoverFreeModels().catch(() => {});
  // Re-discover every 30 min
  setInterval(() => modelMonitor.discoverFreeModels().catch(() => {}), 30 * 60 * 1000);
  logger.info('Model Health Monitor initialized — tracking 20+ free models');

  // Initialize Rule Engine — deterministic fallback when LLMs are all down
  ruleEngine = new RuleEngine({ callS10 });
  logger.info('Rule Engine initialized — deterministic fallback active');

  // Initialize A2A Protocol — Adam ↔ Eve communication
  a2aProtocol = new A2AProtocol({
    onCommand: async (cmd) => {
      // Delegate to agentic loop command handler
      if (agenticLoop) {
        return await agenticLoop.executeCommand(cmd);
      }
      throw new Error('Agentic loop not initialized');
    },
  });
  logger.info('A2A Protocol initialized — Adam ↔ Eve communication active');

  // Initialize Data Worker — Real NBA data collection
  dataWorker = new DataWorker({
    oddsApiKey: process.env.ODDS_API_KEY,
    infraBridge,
    spaceExecutor,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
  });
  logger.info(`Data Worker initialized — ODDS_API_KEY: ${process.env.ODDS_API_KEY ? 'SET' : 'NOT SET'}`);

  // Initialize Watchdog — Statistical evolution monitoring (OBSERVE ONLY)
  watchdog = new Watchdog({
    fetchEvolution: fetchEvo,
    spaceExecutor,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
    a2a: a2aProtocol,
  });
  logger.info('Watchdog initialized — statistical monitoring (observation only)');

  // Initialize Agentic Loop v4 — data-driven operations
  agenticLoop = new AgenticLoop({
    fetchEvolution: fetchEvo,
    callS10,
    getCompletion,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
    watchdog,
    dataWorker,
    a2a: a2aProtocol,
    spaceExecutor,
  });
  agenticLoop.start();

  // Initialize Order Executor (natural language → actions)
  orderExecutor = new OrderExecutor({
    callS10,
    agenticLoop,
    anticipationEngine: null,
    vmBridge,
    spaceExecutor,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
  });
  logger.info('Order Executor initialized — Telegram natural language orders active');

  // Start Express
  app.listen(PORT, '0.0.0.0', () => {
    logger.info('='.repeat(60));
    logger.info(`OpenClaw v4 — DATA-DRIVEN AUTONOMOUS AGENT on port ${PORT}`);
    logger.info(`Telegram: ${TELEGRAM_BOT_TOKEN ? 'ACTIVE' : 'DISABLED'}`);
    logger.info(`OpenRouter: ${OPENROUTER_API_KEY ? 'CONFIGURED' : 'NOT SET'}`);
    logger.info(`VM Bridge: ${process.env.SSH_PRIVATE_KEY ? 'ACTIVE (SSH)' : 'NOT SET'}`);
    logger.info(`GitHub: ${GH_TOKEN ? 'ACTIVE' : 'NOT SET'}`);
    logger.info(`Agentic Loop: v4 data-driven (observe/data/health/report/command/heartbeat)`);
    logger.info(`Data Worker: ${process.env.ODDS_API_KEY ? 'ACTIVE (odds + scores)' : 'NO ODDS_API_KEY'}`);
    logger.info(`Watchdog: ACTIVE (statistical monitoring, observation only)`);
    logger.info(`A2A Protocol: ACTIVE (Adam ↔ Eve bidirectional)`);
    logger.info(`Model Monitor: ACTIVE (${Object.keys(modelMonitor.models).length} free models tracked)`);
    logger.info(`Rule Engine: ACTIVE (${ruleEngine.rules.length} deterministic rules)`);
    logger.info(`Order Executor: ACTIVE (natural language → actions)`);
    logger.info(`Dashboard: /dashboard`);
    logger.info('='.repeat(60));

    // Test VM connectivity at startup
    if (process.env.SSH_PRIVATE_KEY) {
      vmBridge.ping().then(result => {
        logger.info(`VM Bridge: ${result.reachable ? `CONNECTED (${result.latency}ms)` : `UNREACHABLE: ${result.error}`}`);
      }).catch(() => {});
    }

    // Notify admin on startup
    if (bot && TELEGRAM_BOT_TOKEN) {
      const vmStatus = process.env.SSH_PRIVATE_KEY ? 'SSH ACTIVE' : 'NO SSH';
      const ghStatus = GH_TOKEN ? 'ACTIVE' : 'NO TOKEN';
      const modelCount = Object.keys(modelMonitor.models).length;
      bot.sendMessage(ADMIN_TELEGRAM_ID,
        `⚡ *OpenClaw v4 — DATA-DRIVEN AUTONOMOUS*

*NEW:*
📡 Data Worker: Real odds + scores → Supabase
🔍 Watchdog: Statistical monitoring (observe only)
🔗 A2A Protocol: Adam ↔ Eve structured commands

*Loop v4:* observe/data/health/report/heartbeat
*Models:* ${modelCount} free models tracked
*VM:* ${vmStatus} | *GitHub:* ${ghStatus}

/data — odds & scores status
/watchdog — evolution monitoring
/a2a — Adam ↔ Eve protocol
/loop — agentic loop status
/orders — natural language commands`, {
          parse_mode: 'Markdown'
        }).catch(() => {});
    }
  });
}

start().catch(err => {
  logger.error('Startup failed:', err);
  process.exit(1);
});
