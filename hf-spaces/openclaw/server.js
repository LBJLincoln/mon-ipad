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
const FeedbackLoop = require('./lib/feedback-loop');
const ResearchAgent = require('./lib/research-agent');

// ============================================================
// CONFIG
// ============================================================

const PORT = process.env.PORT || 7860;
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const ADMIN_TELEGRAM_ID = parseInt(process.env.ADMIN_TELEGRAM_ID || '6582544948');
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
// SPACE_HOST is set by HF Spaces infrastructure, but may not be available at startup.
// Hardcode the known URL as fallback to ensure Telegram webhook works.
const HF_SPACE_URL = process.env.SPACE_HOST
  ? `https://${process.env.SPACE_HOST}`
  : 'https://nomos42-nomos-worker-2.hf.space';

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
let feedbackLoop = null;   // Phase 1: Prediction vs Reality
let researchAgent = null;  // Phase 3: Autonomous research

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
    return `⚡ *OpenClaw v5 — INTELLIGENT AUTONOMOUS*
Agent IA autonome NOMOS42 NBA Quant AI
Feedback Loop + Analyst + Research Agent

*INTELLIGENCE (NEW v5):*
/eval [date] — Prediction accuracy vs reality
/research — Latest research findings
/insight — Latest analyst recommendation

*DATA & MONITORING:*
/data — Odds & scores collection status
/watchdog — S10 evolution monitoring
/a2a — Adam ↔ Eve protocol status
/loop — Agentic loop cycles

*ORDRES EN LANGAGE NATUREL:*
"boost mutation to 0.2"
"restart S10"
"force analyze" / "force research"
"status evolution"

*Infrastructure:*
/status — Sante complete
/spaces — HF Spaces actifs
/orders — Liste des ordres

*VM Remote (SSH):*
/vm <cmd> — Executer sur la VM

*Git & Code:*
/git <repo> [action] — GitHub status
/gitpush <repo> <msg> — Commit + push
/read <path> — Lire fichier VM

*HF Space Management:*
/hfspace <id> <action> — restart/pause/resume

*Databases:*
/db <sql> — Supabase SQL
/neo4j <cypher> — Neo4j Cypher

*AI & Evolution:*
/evolution — Status GA S10
/heal — Self-healing scan`;
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
    if (!feedbackLoop) return 'FeedbackLoop not initialized.';

    const args = msg.text.split(' ').slice(1);
    const dateStr = args[0] || new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

    await bot.sendMessage(msg.chat.id,
      `Evaluating predictions for *${dateStr}*...`, { parse_mode: 'Markdown' });

    try {
      const result = await feedbackLoop.evaluateDay(dateStr);
      if (result.error) return `Eval: ${result.error}`;

      let text = `*Prediction Eval — ${dateStr}*\n\n`;
      text += `🎯 Accuracy: *${(result.accuracy * 100).toFixed(1)}%* (${result.correct}/${result.total_games})\n`;
      text += `📊 Brier Score: *${result.brier_score.toFixed(4)}* (target < 0.20)\n`;

      const trend = await feedbackLoop.getTrend();
      if (trend?.avg_brier_7d) {
        text += `\n*7-Day Average:*\n`;
        text += `  Brier: ${trend.avg_brier_7d} | Accuracy: ${trend.avg_accuracy_7d ? (trend.avg_accuracy_7d * 100).toFixed(1) + '%' : '?'}`;
        text += `\n  Trending: ${trend.improving ? '📈 Improving' : '📉 Declining'}`;
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

  '/research': async (msg) => {
    if (!researchAgent) return 'Research agent not initialized.';
    const s = researchAgent.getStatus();
    let text = `*Research Agent*
Cycles: ${s.stats.cyclesRun} | Findings: ${s.stats.findingsTotal}
Web searches: ${s.stats.webSearches} | LLM analyses: ${s.stats.llmAnalyses}
Last research: ${s.lastResearch || 'never'}\n`;

    if (s.recentFindings.length > 0) {
      text += '\n*Recent Findings:*\n';
      for (const f of s.recentFindings) {
        text += `${f.actionable ? '🎯' : '📝'} *${f.topic}* (${f.relevance})\n`;
        text += `${f.finding.substring(0, 150)}\n\n`;
      }
    } else {
      text += '\nNo findings yet. Research runs every 12h.';
    }
    return text;
  },

  '/insight': async (msg) => {
    if (!agenticLoop) return 'Agentic loop not initialized.';
    const status = agenticLoop.getStatus();
    if (status.lastInsight) {
      return `*Latest Analyst Insight*\n\n${status.lastInsight}`;
    }
    return 'No analyst insight yet. Analysis runs every 2h.';
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
    version: '2026.3.18-v5-intelligent',
    uptime: Math.floor(process.uptime()),
    timestamp: new Date().toISOString(),
    memory: process.memoryUsage(),
  });
});

// -- Root / landing --
app.get('/', (req, res) => {
  res.json({
    name: 'OpenClaw Nomos Agent',
    version: '2026.3.18-v5-intelligent',
    status: 'running',
    endpoints: {
      health: '/keep-alive',
      webhook: '/webhook/telegram',
      api: '/api/v1',
      spaces: '/api/v1/spaces',
      eval_latest: '/api/v1/eval/latest',
      eval_history: '/api/v1/eval/history',
      eval_trend: '/api/v1/eval/trend',
      analyst_insight: '/api/v1/analyst/insight',
      research_findings: '/api/v1/research/findings',
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
  // Handle both regular messages and edited messages
  const msg = update.message || update.edited_message;
  if (!msg || !msg.text) return;

  const chatId = msg.chat.id;
  const text = msg.text.trim();

  logger.info(`[TG] ${msg.from?.username || msg.from?.id}: ${text.substring(0, 80)}`);

  // Save to conversation history
  persistence.saveMessage(chatId, 'user', text);

  let reply;

  try {
    // 1. Check slash commands first
    const cmd = text.split(' ')[0].split('@')[0].toLowerCase();
    if (COMMANDS[cmd]) {
      try {
        reply = await COMMANDS[cmd](msg);
      } catch (cmdErr) {
        logger.error(`[TG] Command ${cmd} crashed: ${cmdErr.message}`);
        reply = `Command ${cmd} failed: ${cmdErr.message}`;
      }
    }
    // 2. Check natural language orders (admin only)
    // Only match if message starts with "!" prefix to avoid matching casual conversation
    else if (orderExecutor && msg.from?.id === ADMIN_TELEGRAM_ID
             && (text.startsWith('!') || text.startsWith('/order '))
             && orderExecutor.isOrder(text.replace(/^[!/](?:order\s+)?/, ''))) {
      const orderText = text.replace(/^[!/](?:order\s+)?/, '');
      logger.info(`[ORDER] Detected order from admin: ${orderText.substring(0, 80)}`);
      try {
        // Timeout order execution at 15 seconds to prevent hanging
        const orderPromise = orderExecutor.execute(orderText);
        const timeoutPromise = new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Order timed out after 15s')), 15000));
        const result = await Promise.race([orderPromise, timeoutPromise]);
        if (result && result.executed) {
          reply = `*ORDER EXECUTED* [${result.intent}]\n\n${result.result}`;
        } else {
          reply = `Order recognized but not executed: ${result?.reason || 'unknown'}. Falling through to AI...`;
        }
      } catch (orderErr) {
        logger.error(`[ORDER] Execute failed: ${orderErr.message}`);
        reply = `Order failed: ${orderErr.message}`;
      }
    }

    // 3. Fallback: AI completion with conversation context
    if (!reply) {
      const history = persistence.getHistory(chatId, 10);
      const messages = history.map(h => ({ role: h.role, content: h.content }));
      messages.push({ role: 'user', content: text });

      try {
        // Timeout LLM call at 25 seconds
        const llmPromise = getCompletion(messages);
        const llmTimeout = new Promise((_, reject) =>
          setTimeout(() => reject(new Error('LLM timed out after 25s')), 25000));
        const result = await Promise.race([llmPromise, llmTimeout]);
        reply = result.content;
        logger.info(`[LLM] Model: ${result.model}, tokens: ${result.usage?.total_tokens || '?'}`);
      } catch (err) {
        logger.error(`[TG] LLM fallback failed: ${err.message}`);
        reply = `Eve is here but LLM call failed (${err.message}). Try a /command instead.\n\nAvailable: /status /eval /data /watchdog /loop /insight /research`;
      }
    }
  } catch (topLevelErr) {
    // Absolute last resort — ALWAYS reply something
    logger.error(`[TG] Handler top-level crash: ${topLevelErr.message}`);
    reply = `Internal error: ${topLevelErr.message}\nTry /status or /eval`;
  }

  // ALWAYS send a reply — never leave the user hanging
  if (!reply) {
    reply = 'Eve received your message but could not generate a response. Try /status or /eval';
  }
  if (reply) {
    const chunks = splitMessage(reply, 4000);
    for (const chunk of chunks) {
      try {
        await bot.sendMessage(chatId, chunk, { parse_mode: 'Markdown' });
      } catch (err) {
        // Retry without markdown if parsing fails
        try {
          await bot.sendMessage(chatId, chunk);
        } catch (err2) {
          logger.error(`[TG] Send failed even without markdown: ${err2.message}`);
        }
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

// ── Eve Chat System ──
const EVE_SYSTEM_PROMPT = `You are Eve, the autonomous NBA Quant AI agent for Nomos42.
You monitor genetic evolution 24/7, track live Brier scores, manage HF Spaces.
Report on: evolution status, daily evaluations, watchdog alerts, research findings.
Speak concisely with numbers. You are a quant analyst, not a chatbot.
Current targets: Brier < 0.20, ROI > 5%, accuracy > 65%, Sharpe > 1.5.`;

const chatSessions = new Map(); // sessionId → { messages: [], created: Date }

function getOrCreateSession(sessionId) {
  if (!chatSessions.has(sessionId)) {
    chatSessions.set(sessionId, {
      messages: [],
      created: new Date().toISOString(),
    });
  }
  // Cleanup old sessions (>24h)
  const now = Date.now();
  for (const [id, sess] of chatSessions) {
    if (now - new Date(sess.created).getTime() > 24 * 60 * 60 * 1000) {
      chatSessions.delete(id);
    }
  }
  return chatSessions.get(sessionId);
}

function buildEveContext() {
  const ctx = {};
  if (agenticLoop) {
    ctx.evolution = agenticLoop.state?.lastEvoStatus || {};
    ctx.lastInsight = agenticLoop.lastInsight || 'none';
    ctx.uptime = agenticLoop._uptime?.() || 'unknown';
    ctx.cycles = agenticLoop.state?.cycles || 0;
  }
  if (watchdog) {
    ctx.trends = watchdog.getTrends?.() || {};
    ctx.recentAlerts = watchdog.getRecentAlerts?.(5) || [];
  }
  if (feedbackLoop) {
    ctx.lastEval = feedbackLoop.lastEval || {};
    ctx.evalHistory = feedbackLoop.evalHistory?.slice(-7) || [];
  }
  return ctx;
}

// LLM chat (direct OpenRouter) — now with Eve sessions
app.post('/api/v1/chat', async (req, res) => {
  try {
    const { messages, model, maxTokens = 2000, sessionId } = req.body;
    if (!messages) return res.status(400).json({ error: 'messages required' });

    let finalMessages = messages;

    // If sessionId provided, use Eve persona + session history
    if (sessionId) {
      const session = getOrCreateSession(sessionId);
      const systemCtx = buildEveContext();
      const systemMsg = {
        role: 'system',
        content: `${EVE_SYSTEM_PROMPT}\n\nCurrent system status:\n${JSON.stringify(systemCtx, null, 2)}`,
      };

      // Get the last user message from the request
      const userMsg = messages[messages.length - 1];
      session.messages.push(userMsg);

      // Build conversation: system + last 30 messages
      finalMessages = [systemMsg, ...session.messages.slice(-30)];
    }

    const result = await getCompletion(finalMessages, {
      models: model ? [model] : undefined,
      maxTokens,
    });

    // Store assistant reply in session
    if (sessionId && result?.content) {
      const session = getOrCreateSession(sessionId);
      session.messages.push({ role: 'assistant', content: result.content });
    }

    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Chat history for a session
app.get('/api/v1/chat/history', (req, res) => {
  const { sessionId, limit = 50 } = req.query;
  if (!sessionId) return res.status(400).json({ error: 'sessionId required' });
  const session = chatSessions.get(sessionId);
  if (!session) return res.json({ messages: [], sessionId });
  res.json({
    sessionId,
    messages: session.messages.slice(-parseInt(limit)),
    created: session.created,
  });
});

// List active sessions
app.get('/api/v1/chat/sessions', (req, res) => {
  const sessions = [];
  for (const [id, sess] of chatSessions) {
    sessions.push({
      sessionId: id,
      messageCount: sess.messages.length,
      created: sess.created,
    });
  }
  res.json(sessions);
});

// Create a session explicitly
app.post('/api/v1/chat/session', (req, res) => {
  const sessionId = req.body.sessionId || `eve-${Date.now()}`;
  getOrCreateSession(sessionId);
  res.json({ sessionId, created: new Date().toISOString() });
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
// FEEDBACK LOOP API — Prediction evaluation (Phase 1)
// ============================================================

// Get latest evaluation
app.get('/api/v1/eval/latest', async (req, res) => {
  if (!feedbackLoop) return res.json({ status: 'not_initialized' });
  const latest = await feedbackLoop.getLatest();
  res.json(latest || { message: 'No evaluations yet' });
});

// Get evaluation history
app.get('/api/v1/eval/history', async (req, res) => {
  if (!feedbackLoop) return res.json([]);
  const days = parseInt(req.query.days) || 30;
  const history = await feedbackLoop.getHistory(days);
  res.json(history);
});

// Get evaluation trend (7-day rolling)
app.get('/api/v1/eval/trend', async (req, res) => {
  if (!feedbackLoop) return res.json(null);
  const trend = await feedbackLoop.getTrend();
  res.json(trend);
});

// Trigger evaluation for a specific date
app.post('/api/v1/eval/run', async (req, res) => {
  if (!feedbackLoop) return res.status(503).json({ error: 'Not initialized' });
  const { date } = req.body;
  const dateStr = date || new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const result = await feedbackLoop.evaluateDay(dateStr);
  res.json(result);
});

// Store predictions manually
app.post('/api/v1/eval/predictions', async (req, res) => {
  if (!feedbackLoop) return res.status(503).json({ error: 'Not initialized' });
  const { predictions, date } = req.body;
  if (!predictions || !date) return res.status(400).json({ error: 'predictions and date required' });
  const stored = await feedbackLoop.storePredictions(predictions, date);
  res.json({ stored, date });
});

// ============================================================
// RESEARCH AGENT API — Autonomous research (Phase 3)
// ============================================================

// Get research status and findings
app.get('/api/v1/research/status', (req, res) => {
  if (!researchAgent) return res.json({ status: 'not_initialized' });
  res.json(researchAgent.getStatus());
});

// Get recent findings
app.get('/api/v1/research/findings', (req, res) => {
  if (!researchAgent) return res.json([]);
  const limit = parseInt(req.query.limit) || 20;
  res.json(researchAgent.getFindings(limit));
});

// Trigger research cycle manually
app.post('/api/v1/research/run', async (req, res) => {
  if (!researchAgent) return res.status(503).json({ error: 'Not initialized' });
  agenticLoop._cycle('research').catch(e => logger.error(`Manual research: ${e.message}`));
  res.json({ status: 'triggered', type: 'research' });
});

// ============================================================
// ANALYST API — LLM-powered insights (Phase 2)
// ============================================================

// Get latest insight
app.get('/api/v1/analyst/insight', (req, res) => {
  if (!agenticLoop) return res.json({ status: 'not_initialized' });
  res.json({ insight: agenticLoop.lastInsight, lastAnalyze: agenticLoop.state.lastAnalyze });
});

// Trigger analysis manually
app.post('/api/v1/analyst/run', async (req, res) => {
  if (!agenticLoop) return res.status(503).json({ error: 'Not initialized' });
  agenticLoop._cycle('analyze').catch(e => logger.error(`Manual analyze: ${e.message}`));
  res.json({ status: 'triggered', type: 'analyze' });
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
      // Do NOT fall back to polling — it crashes on HF Spaces due to DNS/connectivity issues.
      // Webhook will be set correctly once the Space has its public URL.
      logger.warn('Telegram webhook not set — bot will use webhook mode once URL is resolved');
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

  // Initialize Data Worker — Real NBA data collection (ESPN scores + Odds API when quota allows)
  dataWorker = new DataWorker({
    oddsApiKey: process.env.ODDS_API_KEY,
    infraBridge,
    spaceExecutor,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
  });
  logger.info(`Data Worker initialized — ESPN scores (free) + Odds API: ${process.env.ODDS_API_KEY ? 'SET (dormant until quota resets)' : 'NOT SET'}`);

  // Initialize Watchdog — Statistical evolution monitoring (OBSERVE ONLY, now with recommendations)
  watchdog = new Watchdog({
    fetchEvolution: fetchEvo,
    spaceExecutor,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
    a2a: a2aProtocol,
  });
  logger.info('Watchdog initialized — statistical monitoring with recommendations');

  // Initialize Feedback Loop — Prediction vs Reality (Phase 1: THE critical addition)
  feedbackLoop = new FeedbackLoop({
    infraBridge,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
    a2a: a2aProtocol,
  });
  logger.info('FeedbackLoop initialized — prediction evaluation active');

  // Initialize Research Agent — Autonomous NBA quant research (Phase 3)
  researchAgent = new ResearchAgent({
    getCompletion,
    infraBridge,
    a2a: a2aProtocol,
    bot,
    adminId: ADMIN_TELEGRAM_ID,
  });
  logger.info(`Research Agent initialized — Brave Search: ${process.env.BRAVE_SEARCH_API_KEY ? 'CONFIGURED' : 'NOT SET (LLM-only mode)'}`);

  // Initialize Agentic Loop v5 — intelligent autonomous operations
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
    feedbackLoop,
    researchAgent,
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
    logger.info(`OpenClaw v5 — INTELLIGENT AUTONOMOUS AGENT on port ${PORT}`);
    logger.info(`Telegram: ${TELEGRAM_BOT_TOKEN ? 'ACTIVE' : 'DISABLED'}`);
    logger.info(`OpenRouter: ${OPENROUTER_API_KEY ? 'CONFIGURED' : 'NOT SET'}`);
    logger.info(`VM Bridge: ${process.env.SSH_PRIVATE_KEY ? 'ACTIVE (SSH)' : 'NOT SET'}`);
    logger.info(`GitHub: ${GH_TOKEN ? 'ACTIVE' : 'NOT SET'}`);
    logger.info(`Agentic Loop: v5 intelligent (9 cycles — analyze:30m, eval:15m, research:4h)`);
    logger.info(`Data Worker: ESPN scores (free) + Odds API (${process.env.ODDS_API_KEY ? 'dormant' : 'NOT SET'})`);
    logger.info(`FeedbackLoop: ACTIVE (prediction vs reality evaluation)`);
    logger.info(`Research Agent: ACTIVE (autonomous NBA quant research)`);
    logger.info(`Watchdog: ACTIVE (statistical monitoring with recommendations)`);
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
        `⚡ *OpenClaw v5 — INTELLIGENT AUTONOMOUS*

*NEW in v5:*
📊 FeedbackLoop: Predictions vs ESPN real scores
💡 Analyst: LLM reasoning every 2h
🔬 Research: Autonomous NBA quant research 2x/day
🎯 Smart watchdog: Recommendations with alerts

*9 Cycles:* observe/data/health/report/heartbeat/eval/analyze/research/command
*Models:* ${modelCount} free models tracked
*VM:* ${vmStatus} | *GitHub:* ${ghStatus}

/eval — prediction accuracy
/insight — analyst recommendation
/research — research findings
/data — ESPN scores + odds`, {
          parse_mode: 'Markdown'
        }).catch(() => {});
    }
  });
}

start().catch(err => {
  logger.error('Startup failed:', err);
  process.exit(1);
});
