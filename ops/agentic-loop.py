#!/usr/bin/env python3
"""
Agentic Loop — Autonomous NBA Quant AI Improvement Engine
==========================================================
Orchestrates 4 AI agents (Claude Code, Codex, Gemini, Kimi) in parallel
to generate experiments, write code, push to GitHub, and trigger training.

Architecture (2026 A2A/MCP protocol):
  - Claude Code (Opus 4.6) = orchestrator (runs this script)
  - Codex CLI = code generation + implementation
  - Gemini CLI = research + analysis + review
  - Kimi Code CLI = feature engineering + model design
  - OpenClaw (Eve) = 24/7 monitoring + experiment queue
  - HF Spaces S10/S11 = training + evaluation

Usage:
  source .env.local && python3 ops/agentic-loop.py
  source .env.local && python3 ops/agentic-loop.py --cycles 1  # test single cycle
  source .env.local && python3 ops/agentic-loop.py --duration 3600  # 1 hour
"""

import json, os, sys, time, re, ast, subprocess, urllib.request, ssl
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──
LOOP_DURATION = int(sys.argv[sys.argv.index('--duration') + 1]) if '--duration' in sys.argv else 3600
MAX_CYCLES = int(sys.argv[sys.argv.index('--cycles') + 1]) if '--cycles' in sys.argv else 999
CYCLE_INTERVAL = 300  # 5 min between cycles
NBA_DIR = Path("/home/termius/nomos-nba-agent")
MON_IPAD = Path("/home/termius/mon-ipad")
MAX_COMMITS_PER_HOUR = 5
MAX_CONSECUTIVE_FAILURES = 3

# Binaries
CODEX_BIN = "/home/termius/.npm-global/bin/codex"
GEMINI_BIN = "/home/termius/.npm-global/bin/gemini"
KIMI_BIN = "/home/termius/.local/bin/kimi"

# URLs
S10_URL = "https://lbjlincoln-nomos-nba-quant.hf.space"
OPENCLAW_URL = "https://nomos42-nomos-worker-2.hf.space"

# Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("ADMIN_TELEGRAM_ID", "")

# GitHub
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = "LBJLincoln/nomos-nba-agent"

# SSL contexts
ssl_noverify = ssl.create_default_context()  # For HF Spaces (self-signed)
ssl_noverify.check_hostname = False
ssl_noverify.verify_mode = ssl.CERT_NONE
ssl_default = ssl.create_default_context()   # For public APIs (Groq, Gemini, etc.)

# State
commits_this_hour = 0
consecutive_failures = 0
cycle_results = []


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log(f"[TG] (no credentials) {msg[:80]}")
        return
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=payload, headers={"Content-Type": "application/json", "User-Agent": "NomoS42/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_default) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"[TG] send failed: {e}")


def http_get(url, timeout=15, verify=True):
    ctx = ssl_default if verify else ssl_noverify
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read())
    except Exception:
        return None


def http_post(url, data, timeout=15, verify=True):
    ctx = ssl_default if verify else ssl_noverify
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ── Agent Runners ──
# Strategy: Kimi CLI for code tasks (has codebase context), REST APIs for fast experiment gen

def call_llm_api(provider, prompt, max_tokens=2500, timeout=60):
    """Call an LLM via REST API. Returns text response or None."""
    configs = {
        'gemini': {
            'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
            'headers': {'Authorization': f'Bearer {os.environ.get("GOOGLE_API_KEY", "")}', 'Content-Type': 'application/json'},
            'body': {'model': 'gemini-2.5-flash', 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': max_tokens, 'temperature': 0.7},
            'extract': lambda d: d.get('choices', [{}])[0].get('message', {}).get('content'),
        },
        'groq': {
            'url': 'https://api.groq.com/openai/v1/chat/completions',
            'headers': {'Authorization': f'Bearer {os.environ.get("GROQ_API_KEY", "")}', 'Content-Type': 'application/json'},
            'body': {'model': 'llama-3.3-70b-versatile', 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': max_tokens, 'temperature': 0.7},
            'extract': lambda d: d.get('choices', [{}])[0].get('message', {}).get('content'),
        },
        'kimi_api': {
            'url': 'https://api.kimi.com/coding/v1/messages',
            'headers': {'x-api-key': os.environ.get("KIMI_API_KEY", ""), 'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'},
            'body': {'model': 'kimi-for-coding', 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': prompt}]},
            'extract': lambda d: d.get('content', [{}])[0].get('text'),
        },
    }
    cfg = configs.get(provider)
    if not cfg:
        return None

    payload = json.dumps(cfg['body']).encode()
    all_headers = {**cfg['headers'], 'User-Agent': 'NomoS42-AgenticLoop/1.0'}
    req = urllib.request.Request(cfg['url'], data=payload, headers=all_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_default) as r:
            data = json.loads(r.read())
        if data.get('error'):
            log(f"[{provider}] API error: {data['error']}")
            return None
        text = cfg['extract'](data)
        return text if text and len(text) > 5 else None
    except Exception as e:
        log(f"[{provider}] API call failed: {e}")
        return None


def call_llm_with_fallback(prompt, providers=('gemini', 'groq', 'kimi_api'), max_tokens=2500):
    """Try providers in order, return first success."""
    for p in providers:
        result = call_llm_api(p, prompt, max_tokens)
        if result:
            log(f"[LLM] {p} responded ({len(result)} chars)")
            return result, p
    return None, None


def run_kimi_cli(prompt, cwd=None, timeout=120):
    """Run Kimi Code CLI in headless mode. Has codebase context."""
    cmd = [KIMI_BIN, "-p", prompt, "--print", "-w", str(cwd or NBA_DIR)]
    env = os.environ.copy()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(cwd or NBA_DIR), env=env
        )
        raw = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            raw += f"\n[stderr]: {result.stderr.strip()[:500]}"
        # Parse Kimi structured output — extract TextPart content
        parts = re.findall(r"TextPart\(\s*type='text',\s*text='(.*?)'\s*\)", raw, re.DOTALL)
        if parts:
            return '\n'.join(parts)
        parts = re.findall(r"text='((?:[^'\\]|\\.)*)'\s*\)", raw, re.DOTALL)
        if parts:
            return '\n'.join(p.replace("\\'", "'").replace("\\n", "\n") for p in parts)
        # Strip event markers
        lines = [l for l in raw.split('\n')
                 if not l.startswith(('TurnBegin', 'TurnEnd', 'StepBegin', 'StepEnd',
                                     'ThinkPart', 'ToolCall', 'ToolOutput', 'TextPart('))]
        return '\n'.join(lines).strip() or raw[:2000]
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Kimi CLI timed out after {timeout}s"
    except Exception as e:
        return f"[ERROR] {e}"


# ── Context Gathering ──

def gather_context():
    """Gather current state from all sources including Supabase experiments."""
    ctx = {
        'brier': '0.2187', 'generation': '?', 'stagnation': '?',
        'features': '94', 'recent_results': [], 'pending': 0,
        'running': 0, 'completed_new': [],
    }

    # S10 evolution status
    data = http_get(f"{S10_URL}/api/status", verify=False)
    if data:
        ctx['brier'] = str(data.get('best_brier', '0.2187'))
        ctx['generation'] = str(data.get('generation', '?'))
        ctx['stagnation'] = str(data.get('stagnation', '?'))
        ctx['features'] = str(data.get('best_features', '94'))

    # Supabase experiment status (direct SQL via urllib)
    try:
        import psycopg2
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            # Pending/running counts
            cur.execute("SELECT status, COUNT(*) FROM nba_experiments WHERE status IN ('pending','running') GROUP BY status")
            for row in cur.fetchall():
                if row[0] == 'pending': ctx['pending'] = row[1]
                elif row[0] == 'running': ctx['running'] = row[1]
            # Recent completed results
            cur.execute("SELECT experiment_type, description, result_brier, agent_name FROM nba_experiments WHERE status='completed' AND result_brier IS NOT NULL ORDER BY created_at DESC LIMIT 10")
            ctx['completed_new'] = [{'type': r[0], 'desc': r[1][:60] if r[1] else '', 'brier': r[2], 'agent': r[3]} for r in cur.fetchall()]
            conn.close()
    except Exception as e:
        log(f"[DB] Context query failed: {e}")

    # Recent code state (last 100 lines of key files)
    for key, path in [('engine_tail', 'features/engine.py'), ('runner_tail', 'kaggle/nba_gpu_runner.py')]:
        fpath = NBA_DIR / path
        if fpath.exists():
            lines = fpath.read_text().split('\n')
            ctx[key] = '\n'.join(lines[-100:])

    # Previous cycle results
    ctx['previous_results'] = cycle_results[-5:] if cycle_results else []

    return ctx


# ── Experiment Generation ──

FEATURE_PROMPT_TEMPLATE = """You are the FEATURE SCOUT for an elite NBA prediction model.
Current best Brier: {brier} | Generation: {generation} | Features: {features}

Your job: propose 3 NEW feature combinations to test for NBA game prediction.
Focus on interaction terms, opponent-adjusted stats, and market microstructure.

Feature categories available: rolling stats (3/5/7/10/15/20 windows), four factors,
momentum, rest/schedule, referee, player impact, market (CLV, steam, line movement),
clutch, matchup, situational, venue, derived (z-scores, EMA, bayesian).

{previous_context}

Output EXACTLY 3 experiments in this JSON format, one per line:
EXPERIMENT: {{"type":"feature_test","description":"...","hypothesis":"...","params":{{"features":["feat1","feat2","feat3"],"windows":[5,10]}},"priority":7}}
EXPERIMENT: {{"type":"feature_test","description":"...","hypothesis":"...","params":{{"features":["feat1","feat2"],"interaction":"multiply","windows":[7,15]}},"priority":6}}
EXPERIMENT: {{"type":"feature_test","description":"...","hypothesis":"...","params":{{"features":["feat1","feat2","feat3","feat4"]}},"priority":5}}"""

MODEL_PROMPT_TEMPLATE = """You are the MODEL ARCHITECT for an elite NBA prediction system.
Current best Brier: {brier} | Target: < 0.20

Your job: propose 3 NEW model configurations to test.
Model types: xgboost, lightgbm, catboost, mlp, tabnet, ft_transformer, stacking.

{previous_context}

Output EXACTLY 3 experiments in this JSON format, one per line:
EXPERIMENT: {{"type":"model_test","description":"...","hypothesis":"...","params":{{"model_type":"xgboost","max_depth":8,"learning_rate":0.02,"n_estimators":1000,"subsample":0.8,"colsample_bytree":0.7}},"priority":7}}
EXPERIMENT: {{"type":"model_test","description":"...","hypothesis":"...","params":{{"model_type":"lightgbm","num_leaves":127,"learning_rate":0.01,"n_estimators":1500,"feature_fraction":0.7}},"priority":6}}
EXPERIMENT: {{"type":"model_test","description":"...","hypothesis":"...","params":{{"model_type":"stacking","base_models":["xgb","lgbm","catboost"],"meta_model":"lr"}},"priority":5}}"""

CODE_PROMPT_TEMPLATE = """You are writing Python code for an NBA prediction model.
The code goes in the file: {target_file}

TASK: Implement this improvement:
- Type: {exp_type}
- Description: {exp_desc}
- Params: {exp_params}

CURRENT END OF FILE:
```python
{current_code}
```

RULES:
1. Output ONLY Python code to APPEND to the file
2. Must be syntactically correct
3. Include necessary imports at the top
4. Use 4-space indentation
5. Add a comment header

Output format:
```python
# Your code here
```"""


def parse_experiments(text):
    """Parse EXPERIMENT: {{...}} lines from LLM output."""
    experiments = []
    for line in text.split('\n'):
        match = re.search(r'EXPERIMENT:\s*(\{.+\})', line)
        if match:
            try:
                # Clean common JSON issues
                raw = match.group(1).replace("'", '"').rstrip(',')
                obj = json.loads(raw)
                if obj.get('type') and obj.get('params'):
                    experiments.append(obj)
            except json.JSONDecodeError:
                continue
    return experiments


def parse_code_block(text):
    """Extract Python code from LLM response."""
    # Try ```python blocks
    match = re.search(r'```python\n([\s\S]*?)```', text)
    if match and len(match.group(1).strip()) > 30:
        code = match.group(1).strip()
        # Remove any leading markdown or non-code lines
        lines = code.split('\n')
        clean = [l for l in lines if not l.startswith('```')]
        code = '\n'.join(clean)
        # Verify it parses
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            # Try removing first line if it's a comment about file path
            if lines[0].startswith('#') and ':' in lines[0]:
                code2 = '\n'.join(lines[1:])
                try:
                    ast.parse(code2)
                    return code2
                except SyntaxError:
                    pass
            return code  # Return anyway, caller will validate
    # Try ===CODE=== blocks
    match = re.search(r'===CODE.*?===\n([\s\S]*?)===END===', text)
    if match and len(match.group(1).strip()) > 30:
        return match.group(1).strip()
    return None


def generate_experiments(ctx):
    """Run 3 agents in parallel to generate experiments + code.

    Agent allocation:
      - Gemini (REST API) → feature experiments (fast, creative)
      - Groq (REST API) → model experiments (fast, versatile)
      - Kimi CLI (headless) → code generation (has codebase context)

    Codex is available via MCP when Claude Code calls it interactively.
    """
    prev_ctx = ""
    if ctx.get('previous_results'):
        prev_ctx = "PREVIOUS RESULTS:\n" + '\n'.join(
            f"- {r.get('type','?')}: {r.get('description','?')[:60]}" for r in ctx['previous_results']
        )

    feature_prompt = FEATURE_PROMPT_TEMPLATE.format(
        brier=ctx['brier'], generation=ctx['generation'],
        features=ctx['features'], previous_context=prev_ctx
    )
    model_prompt = MODEL_PROMPT_TEMPLATE.format(
        brier=ctx['brier'], previous_context=prev_ctx
    )

    results = {'feature_exps': [], 'model_exps': [], 'code': None, 'agents_used': []}

    # ── PHASE 1: Generate experiments (parallel REST API calls) ──
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        # Gemini → feature experiments
        future_features = pool.submit(call_llm_with_fallback, feature_prompt, ('gemini', 'kimi_api', 'groq'))
        # Groq → model experiments
        future_models = pool.submit(call_llm_with_fallback, model_prompt, ('groq', 'gemini', 'kimi_api'))

        # Collect features
        try:
            feat_text, feat_provider = future_features.result(timeout=90)
            if feat_text:
                results['feature_exps'] = parse_experiments(feat_text)
                results['agents_used'].append(f'gemini({feat_provider})')
                log(f"[FEATURES] {len(results['feature_exps'])} experiments via {feat_provider}")
            else:
                log(f"[FEATURES] All providers failed")
        except Exception as e:
            log(f"[FEATURES] Exception: {e}")

        # Collect models
        try:
            model_text, model_provider = future_models.result(timeout=90)
            if model_text:
                results['model_exps'] = parse_experiments(model_text)
                results['agents_used'].append(f'model({model_provider})')
                log(f"[MODELS] {len(results['model_exps'])} experiments via {model_provider}")
            else:
                log(f"[MODELS] All providers failed")
        except Exception as e:
            log(f"[MODELS] Exception: {e}")

    # ── PHASE 2: Kimi CLI writes code for best experiment (sequential) ──
    all_exps = results['feature_exps'] + results['model_exps']
    if all_exps and commits_this_hour < MAX_COMMITS_PER_HOUR:
        top_exp = max(all_exps, key=lambda e: e.get('priority', 0))
        target_file = 'features/engine.py' if top_exp['type'] == 'feature_test' else 'kaggle/nba_gpu_runner.py'
        current_code = ctx.get('engine_tail' if 'feature' in top_exp['type'] else 'runner_tail', '')

        code_prompt = CODE_PROMPT_TEMPLATE.format(
            target_file=target_file,
            exp_type=top_exp['type'],
            exp_desc=top_exp.get('description', ''),
            exp_params=json.dumps(top_exp.get('params', {})),
            current_code=current_code[-1500:] if current_code else '# empty'
        )

        log(f"[KIMI-CLI] Generating code for: {top_exp.get('description', '?')[:60]}")
        kimi_out = run_kimi_cli(code_prompt, cwd=NBA_DIR, timeout=120)
        if '[ERROR]' not in kimi_out and '[TIMEOUT]' not in kimi_out:
            code = parse_code_block(kimi_out)
            if not code and len(kimi_out) > 50:
                # Kimi might return raw code without markdown fences
                lines = kimi_out.split('\n')
                code_lines = [l for l in lines if l.strip() and not l.startswith('#') or l.startswith('import') or l.startswith('def ') or l.startswith('class ') or l.startswith('    ')]
                if len(code_lines) > 3:
                    code = kimi_out
            if code:
                results['code'] = {'file': target_file, 'content': code, 'experiment': top_exp}
                results['agents_used'].append('kimi-cli')
                log(f"[KIMI-CLI] Generated {len(code)} chars of code")
            else:
                log(f"[KIMI-CLI] No code block found ({len(kimi_out)} chars)")
        else:
            # Fallback: use Kimi API for code gen
            log(f"[KIMI-CLI] Failed, trying Kimi API fallback...")
            kimi_api_out = call_llm_api('kimi_api', code_prompt, max_tokens=3000)
            if kimi_api_out:
                code = parse_code_block(kimi_api_out)
                if code:
                    results['code'] = {'file': target_file, 'content': code, 'experiment': top_exp}
                    results['agents_used'].append('kimi-api')
                    log(f"[KIMI-API] Generated {len(code)} chars of code")

    return results


# ── Code Application ──

def apply_code(code_result):
    """Write code to file, syntax check, git commit + push."""
    global commits_this_hour, consecutive_failures

    fpath = NBA_DIR / code_result['file']
    code = code_result['content']

    # Syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        log(f"[CODE] Syntax error: {e}")
        consecutive_failures += 1
        return False

    # Append to file
    marker = f"\n\n# === AGENTIC LOOP ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}) ===\n"
    end_marker = "\n# === END AGENTIC LOOP ===\n"

    if fpath.exists():
        existing = fpath.read_text()
        new_content = existing + marker + code + end_marker
    else:
        new_content = code

    fpath.write_text(new_content)
    log(f"[CODE] Written to {code_result['file']}")

    # Git commit + push
    try:
        desc = code_result['experiment'].get('description', 'improvement')[:50]
        exp_type = code_result['experiment'].get('type', 'unknown')
        msg = f"feat({exp_type}): {desc} [agentic-loop]"

        subprocess.run(['git', 'add', code_result['file']], cwd=str(NBA_DIR),
                       capture_output=True, timeout=10)
        result = subprocess.run(
            ['git', 'commit', '-m', msg],
            cwd=str(NBA_DIR), capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            push = subprocess.run(
                ['git', 'push', 'origin', 'main'],
                cwd=str(NBA_DIR), capture_output=True, text=True, timeout=30
            )
            if push.returncode == 0:
                commits_this_hour += 1
                consecutive_failures = 0
                log(f"[GIT] Committed + pushed: {msg}")
                return True
            else:
                log(f"[GIT] Push failed: {push.stderr[:200]}")
        else:
            log(f"[GIT] Commit failed: {result.stderr[:200]}")
    except Exception as e:
        log(f"[GIT] Error: {e}")

    consecutive_failures += 1
    return False


# ── Experiment Submission ──

def submit_experiment_supabase(exp, agent_name):
    """Submit experiment directly via GitHub API to experiment log."""
    # Write to local experiments log
    log_file = MON_IPAD / "data" / "experiments-log.jsonl"
    entry = {
        "id": f"exp_{agent_name}_{int(time.time())}",
        "agent": agent_name,
        "type": exp.get('type', 'unknown'),
        "description": exp.get('description', ''),
        "hypothesis": exp.get('hypothesis', ''),
        "params": exp.get('params', {}),
        "priority": exp.get('priority', 5),
        "status": "pending",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    return True


# ── Main Loop ──

def run_cycle(cycle_num, ctx):
    """Run one complete cycle."""
    global consecutive_failures

    log(f"{'='*60}")
    log(f"CYCLE {cycle_num} — Brier: {ctx['brier']} | Gen: {ctx['generation']} | Pending: {ctx.get('pending',0)} | Running: {ctx.get('running',0)}")
    log(f"{'='*60}")

    # Generate experiments (parallel agents)
    results = generate_experiments(ctx)

    # Submit experiments
    all_exps = results['feature_exps'] + results['model_exps']
    submitted = 0
    for exp in all_exps:
        agent = 'kimi' if exp['type'] == 'feature_test' else 'gemini'
        if submit_experiment_supabase(exp, f"adam_loop_{agent}"):
            submitted += 1

    # Apply code if generated
    code_applied = False
    if results.get('code'):
        code_applied = apply_code(results['code'])

    # Summary
    agents = ', '.join(results['agents_used']) or 'none'
    summary = (
        f"Cycle {cycle_num}: {len(results['feature_exps'])} features + "
        f"{len(results['model_exps'])} models = {submitted} submitted | "
        f"Code: {'YES' if code_applied else 'NO'} | Agents: {agents}"
    )
    log(summary)

    # Store for next cycle context
    for exp in all_exps:
        cycle_results.append(exp)

    # Telegram report every 3 cycles
    if cycle_num % 3 == 0 or code_applied:
        send_telegram(f"<b>Agentic Loop</b> — Cycle {cycle_num}\n{summary}")

    return {
        'feature_exps': len(results['feature_exps']),
        'model_exps': len(results['model_exps']),
        'submitted': submitted,
        'code_applied': code_applied,
        'agents': agents,
    }


def main():
    global commits_this_hour, consecutive_failures

    log("=" * 60)
    log("AGENTIC LOOP — NBA Quant AI Autonomous Improvement Engine")
    log(f"Duration: {LOOP_DURATION}s | Max cycles: {MAX_CYCLES} | Interval: {CYCLE_INTERVAL}s")
    log(f"Agents: Codex {CODEX_BIN} | Gemini {GEMINI_BIN} | Kimi {KIMI_BIN}")
    log("=" * 60)

    # Verify agents exist
    for name, path in [("Codex", CODEX_BIN), ("Gemini", GEMINI_BIN), ("Kimi", KIMI_BIN)]:
        if os.path.exists(path):
            log(f"  {name}: OK ({path})")
        else:
            log(f"  {name}: MISSING ({path})")
            send_telegram(f"Agentic Loop ABORT: {name} not found at {path}")
            sys.exit(1)

    # Ensure experiments log directory exists
    (MON_IPAD / "data").mkdir(exist_ok=True)

    send_telegram(
        f"<b>Agentic Loop STARTED</b>\n"
        f"Duration: {LOOP_DURATION//60} min | Agents: Codex + Gemini + Kimi\n"
        f"Target: Brier < 0.20 | Autonomous mode"
    )

    start_time = time.time()
    cycle = 0
    total_stats = {'exps': 0, 'commits': 0, 'errors': 0}

    try:
        while time.time() - start_time < LOOP_DURATION and cycle < MAX_CYCLES:
            cycle += 1
            cycle_start = time.time()

            # Safety: too many consecutive failures
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                log(f"[SAFETY] {consecutive_failures} consecutive failures — pausing 60s")
                send_telegram(f"Agentic Loop: {consecutive_failures} failures — pausing 60s")
                time.sleep(60)
                consecutive_failures = 0

            # Gather context
            ctx = gather_context()

            # Run cycle
            try:
                result = run_cycle(cycle, ctx)
                total_stats['exps'] += result['submitted']
                if result['code_applied']:
                    total_stats['commits'] += 1
            except Exception as e:
                log(f"[ERROR] Cycle {cycle} failed: {e}")
                total_stats['errors'] += 1
                consecutive_failures += 1

            # Wait for next cycle
            elapsed = time.time() - cycle_start
            sleep_time = max(0, CYCLE_INTERVAL - elapsed)
            if sleep_time > 0 and cycle < MAX_CYCLES:
                log(f"Next cycle in {sleep_time:.0f}s...")
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        log("Interrupted by user")

    # Final report
    elapsed_min = (time.time() - start_time) / 60
    final = (
        f"<b>Agentic Loop COMPLETE</b>\n"
        f"Duration: {elapsed_min:.1f} min | Cycles: {cycle}\n"
        f"Experiments: {total_stats['exps']} | Commits: {total_stats['commits']} | Errors: {total_stats['errors']}"
    )
    log(final)
    send_telegram(final)


if __name__ == '__main__':
    main()
