/**
 * Code Agent — Autonomous code generation, testing, and deployment.
 *
 * Multi-LLM fallback chain:
 *   1. Google Gemini 2.5 Flash (fastest, free tier)
 *   2. Groq Llama 3.3 70B via LiteLLM proxy
 *   3. OpenRouter (paid fallback — Gemini 2.5 Flash)
 *
 * Can: generate code, create files on GitHub, run tests via VM SSH,
 * create branches, submit PRs, and iterate on feedback.
 */

const logger = require('./logger');

// LiteLLM proxy (routes to Groq, Gemini, etc.)
const LITELLM_BASE = process.env.LITELLM_PROXY_URL || 'https://lbjlincoln-nomos-rag-engine-7.hf.space/v1';
const LITELLM_KEY = process.env.LITELLM_MASTER_KEY || 'sk-litellm-nomos-2026';

class CodeAgent {
  constructor({ ghToken, ghOwner, vmBridge, bot, adminId, a2a } = {}) {
    this.litellmBase = LITELLM_BASE;
    this.litellmKey = LITELLM_KEY;
    this.ghToken = ghToken || process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
    this.ghOwner = ghOwner || 'LBJLincoln';
    this.vmBridge = vmBridge;
    this.bot = bot;
    this.adminId = adminId;
    this.a2a = a2a;
    this.agentName = process.env.AGENT_NAME || 'Eve';

    // Task queue
    this.tasks = [];
    this.currentTask = null;
    this.history = []; // completed tasks
    this.stats = {
      tasksCompleted: 0,
      tasksFailed: 0,
      linesWritten: 0,
      prsCreated: 0,
      testsRun: 0,
    };
  }

  get enabled() {
    return this._getProviders().length > 0;
  }

  // ══════════════════════════════════════════
  //  LLM — Multi-provider fallback chain
  //  Gemini (free/fast) → Groq/LiteLLM → OpenRouter (paid)
  // ══════════════════════════════════════════

  async askLLM(messages, { maxTokens = 4096, temperature = 0.3 } = {}) {
    const providers = this._getProviders();
    for (const provider of providers) {
      try {
        return await this._callProvider(provider, messages, { maxTokens, temperature });
      } catch (err) {
        logger.warn(`[CODE-AGENT] ${provider.name} failed: ${err.message}, trying next...`);
      }
    }
    throw new Error('All LLM providers failed');
  }

  _getProviders() {
    const providers = [];
    // Gemini (fastest, free tier generous)
    const googleKey = process.env.GOOGLE_API_KEY;
    if (googleKey) {
      providers.push({
        name: 'Gemini',
        url: 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        key: googleKey,
        model: 'gemini-2.5-flash',
      });
    }
    // Groq via LiteLLM
    if (this.litellmKey) {
      providers.push({
        name: 'Groq/LiteLLM',
        url: this.litellmBase + '/chat/completions',
        key: this.litellmKey,
        model: 'groq/llama-3.3-70b-versatile',
      });
    }
    // OpenRouter (paid fallback)
    const orKey = process.env.OPENROUTER_API_KEY;
    if (orKey) {
      providers.push({
        name: 'OpenRouter',
        url: 'https://openrouter.ai/api/v1/chat/completions',
        key: orKey,
        model: 'google/gemini-2.5-flash',
      });
    }
    return providers;
  }

  async _callProvider(provider, messages, { maxTokens, temperature }) {
    const resp = await fetch(provider.url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${provider.key}`,
      },
      body: JSON.stringify({
        model: provider.model,
        messages,
        max_tokens: maxTokens,
        temperature,
      }),
      signal: AbortSignal.timeout(90000),
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`${provider.name} ${resp.status}: ${text.substring(0, 200)}`);
    }
    const data = await resp.json();
    const content = data.choices?.[0]?.message?.content || '';
    if (!content) throw new Error(`${provider.name}: empty response`);
    logger.info(`[CODE-AGENT] ${provider.name} (${provider.model}) responded OK`);
    return content;
  }

  // ══════════════════════════════════════════
  //  GITHUB OPS — Read, write, branch, PR
  // ══════════════════════════════════════════

  async ghApi(endpoint, { method = 'GET', body } = {}) {
    const opts = {
      method,
      headers: {
        'Authorization': `token ${this.ghToken}`,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': `${this.agentName}-CodeAgent/1.0`,
      },
      signal: AbortSignal.timeout(15000),
    };
    if (body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }

    const resp = await fetch(`https://api.github.com${endpoint}`, opts);
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`GitHub ${resp.status}: ${text.substring(0, 200)}`);
    }
    return resp.json();
  }

  async readFile(repo, filePath, branch = 'main') {
    try {
      const data = await this.ghApi(`/repos/${this.ghOwner}/${repo}/contents/${filePath}?ref=${branch}`);
      return Buffer.from(data.content, 'base64').toString('utf8');
    } catch (err) {
      return null; // file doesn't exist
    }
  }

  async writeFile(repo, filePath, content, message, branch = 'main') {
    // Get current SHA if file exists
    let sha;
    try {
      const existing = await this.ghApi(`/repos/${this.ghOwner}/${repo}/contents/${filePath}?ref=${branch}`);
      sha = existing.sha;
    } catch {}

    const body = {
      message: `${message}\n\nCo-Authored-By: ${this.agentName} <${this.agentName.toLowerCase()}@nomos42.ai>`,
      content: Buffer.from(content).toString('base64'),
      branch,
    };
    if (sha) body.sha = sha;

    return this.ghApi(`/repos/${this.ghOwner}/${repo}/contents/${filePath}`, {
      method: 'PUT',
      body,
    });
  }

  async createBranch(repo, branchName, fromBranch = 'main') {
    const ref = await this.ghApi(`/repos/${this.ghOwner}/${repo}/git/ref/heads/${fromBranch}`);
    return this.ghApi(`/repos/${this.ghOwner}/${repo}/git/refs`, {
      method: 'POST',
      body: {
        ref: `refs/heads/${branchName}`,
        sha: ref.object.sha,
      },
    });
  }

  async createPR(repo, { title, body, head, base = 'main' }) {
    const pr = await this.ghApi(`/repos/${this.ghOwner}/${repo}/pulls`, {
      method: 'POST',
      body: { title, body, head, base },
    });
    this.stats.prsCreated++;
    return pr;
  }

  // ══════════════════════════════════════════
  //  VM EXECUTION — Run commands via SSH
  // ══════════════════════════════════════════

  async runOnVM(command) {
    if (!this.vmBridge) throw new Error('VM Bridge not available');
    const result = await this.vmBridge.exec(command);
    return result;
  }

  // ══════════════════════════════════════════
  //  CODE TASK EXECUTION — The main loop
  // ══════════════════════════════════════════

  /**
   * Execute a coding task end-to-end:
   * 1. Understand the task
   * 2. Read relevant files
   * 3. Generate code with LLM (Gemini/Groq/OpenRouter fallback)
   * 4. Write to GitHub (branch)
   * 5. Test via VM
   * 6. Create PR or commit to main
   * 7. Report results
   */
  async executeTask(task) {
    if (!this.enabled) {
      return { success: false, error: 'Code agent not enabled (no LLM providers available)' };
    }

    this.currentTask = {
      ...task,
      startedAt: new Date().toISOString(),
      status: 'running',
      steps: [],
    };

    try {
      // Step 1: Plan the implementation
      const plan = await this._planTask(task);
      this.currentTask.steps.push({ step: 'plan', result: plan.substring(0, 500) });

      // Step 2: Read existing files if needed
      const context = await this._gatherContext(task, plan);
      this.currentTask.steps.push({ step: 'context', files: context.files?.length || 0 });

      // Step 3: Generate code
      const code = await this._generateCode(task, plan, context);
      this.currentTask.steps.push({ step: 'generate', files: Object.keys(code).length });

      // Step 4: Write to GitHub
      const branch = `${this.agentName.toLowerCase()}/task-${Date.now()}`;
      await this.createBranch(task.repo, branch);

      for (const [filePath, content] of Object.entries(code)) {
        await this.writeFile(task.repo, filePath, content, task.description || 'Code update', branch);
        this.stats.linesWritten += content.split('\n').length;
      }
      this.currentTask.steps.push({ step: 'write', branch, files: Object.keys(code).length });

      // Step 5: Test (if VM available and test command specified)
      let testResult = null;
      if (task.testCommand && this.vmBridge) {
        try {
          testResult = await this.runOnVM(task.testCommand);
          this.stats.testsRun++;
          this.currentTask.steps.push({ step: 'test', passed: !testResult.error, output: testResult.stdout?.substring(0, 300) });
        } catch (err) {
          this.currentTask.steps.push({ step: 'test', passed: false, error: err.message });
        }
      }

      // Step 6: Create PR
      const pr = await this.createPR(task.repo, {
        title: task.description || `${this.agentName}: code update`,
        body: `## ${this.agentName} Auto-Generated Code\n\n**Task:** ${task.description}\n\n**Plan:**\n${plan.substring(0, 500)}\n\n**Files modified:** ${Object.keys(code).join(', ')}\n\n**Test result:** ${testResult ? (testResult.error ? 'FAILED' : 'PASSED') : 'skipped'}\n\n---\n*Generated by ${this.agentName} using multi-LLM fallback (Gemini/Groq/OpenRouter)*`,
        head: branch,
      });
      this.currentTask.steps.push({ step: 'pr', url: pr.html_url, number: pr.number });

      // Done
      this.currentTask.status = 'completed';
      this.currentTask.completedAt = new Date().toISOString();
      this.currentTask.prUrl = pr.html_url;
      this.stats.tasksCompleted++;

      // Report
      await this._reportCompletion(this.currentTask);

      this.history.push(this.currentTask);
      if (this.history.length > 20) this.history = this.history.slice(-20);

      return { success: true, pr: pr.html_url, branch, files: Object.keys(code) };

    } catch (err) {
      this.currentTask.status = 'failed';
      this.currentTask.error = err.message;
      this.stats.tasksFailed++;

      logger.error(`[CODE-AGENT] Task failed: ${err.message}`);

      this.history.push(this.currentTask);
      return { success: false, error: err.message };
    } finally {
      this.currentTask = null;
    }
  }

  // ══════════════════════════════════════════
  //  INTERNAL: Plan, Context, Generate
  // ══════════════════════════════════════════

  async _planTask(task) {
    const prompt = `You are ${this.agentName}, an autonomous coding agent. Plan the implementation for this task.

TASK: ${task.description}
REPO: ${task.repo}
${task.files ? `TARGET FILES: ${task.files.join(', ')}` : ''}
${task.context ? `CONTEXT: ${task.context}` : ''}

Output a concise implementation plan (max 300 words):
1. What files to modify/create
2. Key changes in each file
3. How to test
4. Potential risks`;

    return this.askLLM([{ role: 'user', content: prompt }], { maxTokens: 1000 });
  }

  async _gatherContext(task, plan) {
    const context = { files: [] };

    // Read existing files mentioned in task or plan
    const filesToRead = task.files || [];

    // Also extract file paths from plan
    const pathMatches = plan.matchAll(/(?:modify|edit|update|read|create)\s+[`"]?([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)[`"]?/gi);
    for (const m of pathMatches) {
      if (!filesToRead.includes(m[1])) filesToRead.push(m[1]);
    }

    for (const fp of filesToRead.slice(0, 10)) {
      const content = await this.readFile(task.repo, fp);
      if (content) {
        context.files.push({ path: fp, content: content.substring(0, 5000) });
      }
    }

    return context;
  }

  async _generateCode(task, plan, context) {
    const existingFiles = context.files.map(f =>
      `--- ${f.path} ---\n${f.content}\n--- end ---`
    ).join('\n\n');

    const prompt = `You are ${this.agentName}, an expert coding agent. Generate the code for this task.

TASK: ${task.description}
PLAN: ${plan}

${existingFiles ? `EXISTING CODE:\n${existingFiles}\n` : ''}

Output ONLY code files in this exact format (no explanation outside):

===FILE: path/to/file.py===
file content here
===END===

===FILE: path/to/another.js===
another file content
===END===

Generate clean, production-ready code. Include only files that need changes.`;

    const result = await this.askLLM([{ role: 'user', content: prompt }], {
      maxTokens: 4096,
      temperature: 0.2,
    });

    // Parse files from response
    const files = {};
    const fileMatches = result.matchAll(/===FILE:\s*(.+?)===\n([\s\S]*?)===END===/g);
    for (const m of fileMatches) {
      files[m[1].trim()] = m[2].trimEnd();
    }

    if (Object.keys(files).length === 0) {
      // Fallback: if the LLM didn't use the format, try to extract code blocks
      const codeBlocks = result.matchAll(/```(?:\w+)?\n([\s\S]*?)```/g);
      let i = 0;
      for (const cb of codeBlocks) {
        const filename = task.files?.[i] || `generated_${i}.txt`;
        files[filename] = cb[1].trimEnd();
        i++;
      }
    }

    return files;
  }

  async _reportCompletion(task) {
    const msg = `🤖 *${this.agentName} Code Agent*\n\n` +
      `*Task:* ${task.description?.substring(0, 100)}\n` +
      `*Status:* ${task.status === 'completed' ? '✅ COMPLETED' : '❌ FAILED'}\n` +
      `*PR:* ${task.prUrl || 'none'}\n` +
      `*Steps:* ${task.steps?.map(s => s.step).join(' → ')}`;

    if (this.bot && this.adminId) {
      await this.bot.sendMessage(this.adminId, msg, { parse_mode: 'Markdown' }).catch(() => {});
    }

    if (this.a2a) {
      this.a2a.postReport({
        type: 'code_task',
        level: task.status === 'completed' ? 'INFO' : 'WARNING',
        message: msg,
        data: { task: task.description, status: task.status, pr: task.prUrl },
      });
    }
  }

  // ══════════════════════════════════════════
  //  QUEUE MANAGEMENT
  // ══════════════════════════════════════════

  addTask(task) {
    this.tasks.push({ ...task, addedAt: new Date().toISOString() });
    logger.info(`[CODE-AGENT] Task queued: ${task.description?.substring(0, 80)}`);
  }

  async processQueue() {
    if (this.currentTask || this.tasks.length === 0) return;
    const next = this.tasks.shift();
    return this.executeTask(next);
  }

  getStatus() {
    const providers = this._getProviders();
    return {
      enabled: this.enabled,
      providers: providers.map(p => ({ name: p.name, model: p.model })),
      providerCount: providers.length,
      currentTask: this.currentTask ? {
        description: this.currentTask.description,
        status: this.currentTask.status,
        steps: this.currentTask.steps?.length || 0,
      } : null,
      queueLength: this.tasks.length,
      stats: this.stats,
      recentHistory: this.history.slice(-5).map(t => ({
        description: t.description?.substring(0, 80),
        status: t.status,
        pr: t.prUrl,
        completedAt: t.completedAt,
      })),
    };
  }
}

module.exports = CodeAgent;
