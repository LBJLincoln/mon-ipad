#!/usr/bin/env python3 -u
"""
Adam + Eve + Cain — 3 Autonomous NBA Quant AI Agents (HuggingClaw-style)

ALL 3 agents use Claude Code CLI via acpx on REAL git repos.
Based on HuggingClaw's conversation-loop.py pattern (3,403 lines).

Architecture:
  EVE  (Monitor)     — Monitors S10/S11/ESPN, detects issues, fixes via Claude Code (5 min)
  ADAM (Strategist)   — Reviews results, creates experiments, improves code via Claude Code (15 min)
  CAIN (Coder)       — Executes queued tasks from Eve/Adam via Claude Code (on demand)

Key difference from old version: ALL agents clone real GitHub repos, run Claude Code CLI,
and push changes back. Code is never lost.
"""
import json, time, re, sys, os, subprocess, threading, datetime, uuid, traceback, shutil
from pathlib import Path
from collections import deque

# Don't reconfigure stdout (shared with parent process, causes IO deadlocks)
# Output uses os.write(1, ...) directly instead

# ── Config ────────────────────────────────────────────────────────────────────
S10_URL = "https://lbjlincoln-nomos-nba-quant.hf.space"
S11_URL = "https://lbjlincoln-nomos-nba-quant-2.hf.space"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

EVE_INTERVAL = 300     # 5 minutes
ADAM_INTERVAL = 900    # 15 minutes
CC_TIMEOUT = 600       # 10 minutes max per Claude Code task
MAX_IDLE_TURNS = 3     # Force task generation after 3 idle turns (like HuggingClaw)

SPACE_HOST = os.environ.get("SPACE_HOST", "lbjlincoln-nomos-eve-agent.hf.space")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "huggingclaw")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# GitHub repos that agents work on
REPOS = {
    "nba": {
        "url": f"https://{GITHUB_TOKEN}@github.com/LBJLincoln/nomos-nba-agent.git" if GITHUB_TOKEN
               else "https://github.com/LBJLincoln/nomos-nba-agent.git",
        "dir": "/tmp/repo-nomos-nba-agent",
        "branch": "main",
    },
    "ops": {
        "url": f"https://{GITHUB_TOKEN}@github.com/LBJLincoln/mon-ipad.git" if GITHUB_TOKEN
               else "https://github.com/LBJLincoln/mon-ipad.git",
        "dir": "/tmp/repo-mon-ipad",
        "branch": "main",
    },
}

COLAB_LINK = "https://colab.research.google.com/github/LBJLincoln/nomos-nba-agent/blob/main/colab/nba_gpu_runner.ipynb"

# ── Shared State ──────────────────────────────────────────────────────────────
state = {
    "eve_turns": 0, "adam_turns": 0, "cain_tasks": 0, "cain_successes": 0,
    "pushes": 0, "last_push_time": 0, "idle_turns": 0,
    "last_brier": None, "s10_status": "unknown", "s11_status": "unknown",
    "games_today": 0, "gpu_pending": 0, "last_context": {},
    "task_queue": deque(maxlen=50),
    "action_log": deque(maxlen=100),
    "action_history": [],  # Persist to prevent repeating same actions
}
state_lock = threading.RLock()  # RLock: reentrant — log() acquires state_lock, called from within state_lock blocks
cc_lock = threading.Lock()     # Only one Claude Code process at a time

# ══════════════════════════════════════════════════════════════════════════════
#  CORE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

_log_lock = threading.Lock()


def log(agent, msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    line = f"[{ts}] [{agent}] {msg}\n"
    # Use os.write() to bypass Python IO layer deadlocks with flush=True
    with _log_lock:
        os.write(1, line.encode())
    with state_lock:
        state["action_log"].append(line.rstrip())


def fetch_json(url, timeout=15):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def _get_telegram_ip():
    """Get resolved Telegram API IP from DNS resolver (HF blocks api.telegram.org)."""
    try:
        with open("/tmp/dns-resolved.json") as f:
            resolved = json.load(f)
        return resolved.get("api.telegram.org")
    except Exception:
        return None


def send_telegram(text):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    admin_id = os.environ.get("TELEGRAM_ADMIN_ID", "")
    if not bot_token or not admin_id:
        return
    try:
        import urllib.request, ssl

        # Strategy 1: Use resolved IP with Host header (bypasses DNS block)
        resolved_ip = _get_telegram_ip()
        if resolved_ip:
            try:
                url = f"https://{resolved_ip}/bot{bot_token}/sendMessage"
                data = json.dumps({"chat_id": admin_id, "text": text[:4000]}).encode()
                ctx = ssl.create_default_context()
                ctx.check_hostname = False  # IP doesn't match cert hostname
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Host", "api.telegram.org")
                urllib.request.urlopen(req, timeout=10, context=ctx)
                return  # Success
            except Exception as e:
                log("TG", f"IP method failed ({resolved_ip}): {e}")

        # Strategy 2: Try direct domain (works if DNS not blocked)
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = json.dumps({"chat_id": admin_id, "text": text[:4000]}).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=10)
            return
        except Exception:
            pass

        # Strategy 3: Use LiteLLM proxy as Telegram relay (POST to our own proxy)
        try:
            proxy_url = os.environ.get("LITELLM_URL", "").replace("/v1/chat/completions", "")
            if proxy_url:
                url = f"{proxy_url}/telegram/send"
                data = json.dumps({"chat_id": admin_id, "text": text[:4000], "bot_token": bot_token}).encode()
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Content-Type", "application/json")
                urllib.request.urlopen(req, timeout=10)
                return
        except Exception:
            pass

        log("TG", "All Telegram methods failed")
    except Exception as e:
        log("TG", f"Send failed: {e}")


def parse_tasks(text):
    """Parse [TASK] blocks from agent responses."""
    if not text:
        return []
    tasks = []
    pattern = r'\[TASK\](.*?)(?:\[/TASK\]|\[TASK\]|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        task = match.strip()
        if task and len(task) > 10:
            tasks.append(task)
    return tasks


# ══════════════════════════════════════════════════════════════════════════════
#  LLM API — Lightweight agent that reads code, calls LLM, writes changes
#  Uses LiteLLM proxy (already running at S7) — zero extra memory footprint
# ══════════════════════════════════════════════════════════════════════════════

LITELLM_URL = os.environ.get("LITELLM_URL", "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions")
LITELLM_KEY = os.environ.get("LITELLM_KEY", "sk-litellm-nomos-2026")
# Models to try in order (LiteLLM uses friendly names)
LLM_MODELS = ["smart", "fast", "gemini-flash", "default"]


def call_llm(messages, model=None):
    """Call LLM via LiteLLM proxy. Returns response text or None."""
    import urllib.request
    for m in ([model] if model else LLM_MODELS):
        try:
            data = json.dumps({
                "model": m,
                "messages": messages,
                "max_tokens": 8000,
                "temperature": 0.3,
            }).encode()
            req = urllib.request.Request(LITELLM_URL, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {LITELLM_KEY}")
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                log("LLM", f"Got response from {m} ({len(content)} chars)")
                return content
        except Exception as e:
            log("LLM", f"Failed with {m}: {e}")
            continue
    return None


def read_repo_files(workspace, file_patterns):
    """Read multiple files from workspace. Returns dict of {path: content}."""
    ws = Path(workspace)
    files = {}
    for pattern in file_patterns:
        for fpath in ws.glob(pattern):
            if fpath.is_file() and fpath.stat().st_size < 100_000:  # Skip huge files
                try:
                    files[str(fpath.relative_to(ws))] = fpath.read_text()
                except Exception:
                    pass
    return files


def apply_file_changes(workspace, response_text):
    """Parse LLM response for file changes and apply them.

    Handles multiple formats:
      1. ```path/to/file.py\n<content>\n```
      2. ```python:path/to/file.py\n<content>\n```
      3. ```python\n# file: path/to/file.py\n<content>\n```
      4. [FILE path/to/file.py]\n```\n<content>\n```
    """
    changes = []
    LANG_IDS = {"python", "javascript", "json", "bash", "shell", "yaml", "toml",
                "js", "py", "typescript", "ts", "sh", "css", "html", "sql", "text"}
    FILE_EXTS = r'\.(?:py|js|json|yaml|yml|toml|cfg|txt|md|ipynb|ts|css|html|sql)'

    # Format 1: ```path/to/file.py
    for m in re.finditer(r'```(\S+' + FILE_EXTS + r')\n(.*?)```', response_text, re.DOTALL):
        fp, content = m.group(1), m.group(2)
        if fp not in LANG_IDS:
            changes.append((fp, content))

    # Format 2: ```python:path/to/file.py
    for m in re.finditer(r'```\w+:(\S+' + FILE_EXTS + r')\n(.*?)```', response_text, re.DOTALL):
        changes.append((m.group(1), m.group(2)))

    # Format 3: ```python\n# file: path/to/file.py
    for m in re.finditer(r'```\w+\n#\s*file:\s*(\S+' + FILE_EXTS + r')\n(.*?)```', response_text, re.DOTALL):
        changes.append((m.group(1), m.group(2)))

    # Format 4: [FILE path/to/file.py]\n```
    for m in re.finditer(r'\[FILE\s+(\S+' + FILE_EXTS + r')\]\s*\n```(?:\w*)\n(.*?)```', response_text, re.DOTALL):
        changes.append((m.group(1), m.group(2)))

    # Deduplicate (last occurrence wins)
    seen = {}
    for fp, content in changes:
        seen[fp] = content

    applied = []
    for filepath, content in seen.items():
        target = Path(workspace) / filepath
        if target.exists() or filepath.count("/") <= 2:
            # SAFETY: reject if new content is drastically smaller than existing file
            if target.exists():
                old_size = target.stat().st_size
                new_size = len(content.encode())
                if old_size > 5000 and new_size < old_size * 0.5:
                    log("WRITE", f"REJECTED {filepath}: would shrink from {old_size} to {new_size} bytes ({new_size*100//old_size}%)")
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            applied.append(filepath)
            log("WRITE", f"Updated {filepath} ({len(content)} chars)")
    return applied


def ensure_repo(repo_key):
    """Clone or pull a repo. Returns the local directory path."""
    repo = REPOS[repo_key]
    repo_dir = Path(repo["dir"])

    if repo_dir.exists() and (repo_dir / ".git").exists():
        # Pull latest
        try:
            subprocess.run(["git", "pull", "--rebase", "origin", repo["branch"]],
                           cwd=str(repo_dir), capture_output=True, timeout=30)
            log("GIT", f"Pulled {repo_key} repo")
        except Exception as e:
            log("GIT", f"Pull failed for {repo_key}: {e}")
    else:
        # Fresh clone
        if repo_dir.exists():
            shutil.rmtree(str(repo_dir), ignore_errors=True)
        try:
            subprocess.run(["git", "clone", "--depth=20", "-b", repo["branch"],
                            repo["url"], str(repo_dir)],
                           capture_output=True, timeout=120)
            # Set git identity
            subprocess.run(["git", "config", "user.email", "eve@nomos42.ai"],
                           cwd=str(repo_dir), capture_output=True)
            subprocess.run(["git", "config", "user.name", "Eve Agent"],
                           cwd=str(repo_dir), capture_output=True)
            log("GIT", f"Cloned {repo_key} repo to {repo_dir}")
        except Exception as e:
            log("GIT", f"Clone failed for {repo_key}: {e}")
            return None

    return str(repo_dir)


def write_claude_md(workspace, agent_name):
    """Write CLAUDE.md + slash commands into a workspace (like HuggingClaw's SOUL.md)."""
    ws = Path(workspace)

    claude_md = ws / "CLAUDE.md"
    claude_md.write_text(f"""# {agent_name} — NBA Quant AI Agent

You are {agent_name}, an autonomous agent improving the NBA Quant AI prediction model.
You have Claude Code Max OAuth credentials (no API key needed).
You are working on the REAL git repository. Your changes will be committed and pushed.

## MISSION
Build the best NBA prediction AI in the world. Beat the best hedge funds.
Current best: Brier 0.2205 | Target: Brier < 0.20, ROI > 5%, Sharpe > 1.5

## KEY FILES
- features/engine.py — 580+ feature candidates, 94 selected
- evolution/loop.py — Genetic algorithm (population 50+, multi-objective fitness)
- models/ — XGBoost, LightGBM, CatBoost, Stacking
- colab/nba_gpu_runner.ipynb — GPU training (MLP, LSTM, FT-Transformer, etc.)
- predict_today.py — Daily prediction pipeline

## RULES
1. NEVER run ML training here — submit experiments to Supabase for GPU runners (Colab)
2. Keep changes minimal and focused — 1 fix per commit
3. ALWAYS commit and push when done
4. Read existing code BEFORE modifying
5. Run tests if available
6. Do NOT create README.md or documentation files

## ENDPOINTS
- S10 Evolution: {S10_URL}/api/status
- S11 Parallel: {S11_URL}/api/status
- ESPN Scores: {ESPN_URL}

## SUPABASE (for experiment submission)
Use the nba_experiments table. Insert with status='pending', target_space='gpu'.
DATABASE_URL is in the environment.
""")

    # Slash commands (like HuggingClaw's /fix-cain)
    commands_dir = ws / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    (commands_dir / "improve-features.md").write_text(
        "# Improve Features\n"
        "Read features/engine.py, analyze which features are selected vs available, "
        "identify high-impact features to add or modify. Make changes, commit and push.")

    (commands_dir / "fix-evolution.md").write_text(
        "# Fix Evolution\n"
        "Read evolution/loop.py, check for stagnation or issues. "
        "Tune mutation rates, population size, or selection. Commit and push.")

    (commands_dir / "submit-experiment.md").write_text(
        "# Submit GPU Experiment\n"
        "Create a new experiment in the Supabase nba_experiments table. "
        "Choose a model type (ft_transformer, node, saint, mc_dropout_rnn, tabnet). "
        "Set status='pending', target_space='gpu'. Use DATABASE_URL from env.")

    (commands_dir / "research.md").write_text(
        "# Research\n"
        "Search for latest NBA prediction techniques, papers, Kaggle competitions. "
        "Write actionable findings. If you find improvements, implement them.")

    # acpx config for non-interactive mode
    acpx_dir = ws / ".acpx"
    acpx_dir.mkdir(parents=True, exist_ok=True)
    (acpx_dir / "config.json").write_text(json.dumps({
        "defaultAgent": "claude",
        "defaultPermissions": "approve-all",
        "format": "text"
    }))


def _run_acpx_claude(task, workspace, agent_name, env):
    """Try running acpx claude (HuggingClaw-style). Returns (output, success) or None if unavailable."""
    try:
        which = subprocess.run(["which", "acpx"], capture_output=True, text=True)
        if which.returncode != 0:
            return None

        cmd = ["acpx", "claude", task]
        log(agent_name, f"Running: acpx claude '{task[:80]}...'")

        proc = subprocess.Popen(
            cmd, cwd=workspace, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        log(agent_name, f"acpx PID: {proc.pid}")

        # Threaded reader to prevent blocking
        output_lines = []
        stop_event = threading.Event()

        def reader():
            try:
                for line in proc.stdout:
                    if stop_event.is_set():
                        break
                    output_lines.append(line.rstrip())
            except Exception:
                pass

        t = threading.Thread(target=reader, daemon=True)
        t.start()

        start = time.time()
        last_count = 0
        last_output = start

        while True:
            time.sleep(3)
            elapsed = time.time() - start
            if elapsed > CC_TIMEOUT:
                proc.kill()
                log(agent_name, f"acpx timed out after {CC_TIMEOUT}s")
                break
            if proc.poll() is not None:
                break
            cur = len(output_lines)
            if cur > last_count:
                last_output = time.time()
                for i in range(last_count, min(cur, last_count + 3)):
                    log(agent_name, f"  CC [{i+1}]: {output_lines[i][:120]}")
                last_count = cur
            elif time.time() - last_output > 120:  # 2 min no output
                proc.kill()
                log(agent_name, "acpx: no output for 120s — killed")
                break

        stop_event.set()
        t.join(timeout=5)
        output = "\n".join(output_lines[-50:])
        log(agent_name, f"acpx finished (exit={proc.returncode}, {len(output_lines)} lines, {elapsed:.0f}s)")
        return output, proc.returncode == 0
    except Exception as e:
        log(agent_name, f"acpx failed: {e}")
        return None


def _run_llm_api(task, workspace, agent_name):
    """Run coding task via direct LLM API call (lightweight fallback)."""
    key_files = read_repo_files(workspace, [
        "features/engine.py", "evolution/loop.py",
        "models/*.py", "predict_today.py",
        "colab/*.py", "agents/*.py",
    ])
    log(agent_name, f"Read {len(key_files)} files for API task")

    file_context = ""
    for fpath, content in sorted(key_files.items()):
        lines = content.split("\n")
        truncated = "\n".join(lines[:200])
        if len(lines) > 200:
            truncated += f"\n... ({len(lines) - 200} more lines)"
        file_context += f"\n### {fpath}\n```python\n{truncated}\n```\n"

    system_prompt = (
        f"You are {agent_name}, an autonomous NBA Quant AI agent.\n"
        f"Current best: Brier 0.2205 | Target: Brier < 0.20, ROI > 5%\n\n"
        f"OUTPUT FORMAT — CRITICAL:\n"
        f"You MUST output working Python code in a NEW file. Example:\n\n"
        f"Adding a pace-adjusted feature helper:\n\n"
        f"```features/pace_helper.py\n"
        f"import numpy as np\n"
        f"def compute_pace_adjusted(pts, pace, league_pace=100.0):\n"
        f"    return (pts / pace) * league_pace if pace > 0 else pts\n"
        f"```\n\n"
        f"RULES:\n"
        f"1. NEVER rewrite engine.py or loop.py — they are large, complex files. READ ONLY.\n"
        f"2. CREATE NEW files with useful helpers, models, or analysis scripts.\n"
        f"3. Triple-backtick line = file path (e.g. ```features/my_file.py), NOT ```python.\n"
        f"4. Write REAL working code. Do NOT use placeholders like 'content here'.\n"
        f"5. Keep files focused: one concern per file, 50-300 lines.\n"
        f"6. Brief explanation (2-3 lines) then code. No long analysis.\n\n"
        f"REPOSITORY FILES (READ-ONLY REFERENCE):\n{file_context}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    log(agent_name, "Calling LLM API...")
    response = call_llm(messages)
    if not response:
        log(agent_name, "LLM API returned no response")
        return None, False

    log(agent_name, f"LLM response: {len(response)} chars")
    changes = apply_file_changes(workspace, response)
    return response, len(changes) > 0


def run_claude_code(task, repo_key="nba", agent_name="Cain"):
    """
    THE KEY FUNCTION — Like HuggingClaw's action_claude_code().

    Strategy:
    1. Try acpx claude (HuggingClaw-style, uses ANTHROPIC_BASE_URL for API routing)
    2. Fall back to direct LLM API if acpx is unavailable or fails
    3. Commit and push any changes to GitHub
    """
    with cc_lock:
        log(agent_name, f"Starting task: {task[:100]}...")

        # 1. Ensure repo is up to date
        workspace = ensure_repo(repo_key)
        if not workspace:
            log(agent_name, f"Failed to prepare repo {repo_key}")
            return None, False

        write_claude_md(workspace, agent_name)

        # 2. Use direct LLM API via LiteLLM proxy (routes to Kimi/Gemini/Claude)
        log(agent_name, "Calling LLM API...")
        response, has_file_changes = _run_llm_api(task, workspace, agent_name)
        if not response:
            return None, False

        # 5. Commit any changes
        status = subprocess.run(["git", "status", "--porcelain"],
                                cwd=workspace, capture_output=True, text=True)
        has_changes = bool(status.stdout.strip())

        if has_changes:
            log(agent_name, f"Committing changes...")
            subprocess.run(["git", "add", "-A"], cwd=workspace, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m",
                 f"feat({agent_name.lower()}): auto-improvement\n\nCo-Authored-By: {agent_name} Agent <eve@nomos42.ai>"],
                cwd=workspace, capture_output=True
            )

            # Push to GitHub
            push_result = subprocess.run(
                ["git", "push", "origin", REPOS[repo_key]["branch"]],
                cwd=workspace, capture_output=True, text=True, timeout=30
            )
            if push_result.returncode == 0:
                with state_lock:
                    state["pushes"] += 1
                    state["last_push_time"] = time.time()
                    state["idle_turns"] = 0
                log(agent_name, f"Pushed to {repo_key} (total: {state['pushes']})")
                send_telegram(f"✅ *{agent_name}* pushed to `{repo_key}`\n{task[:200]}")
            else:
                log(agent_name, f"Push failed: {push_result.stderr[:200]}")
        else:
            log(agent_name, "No code changes produced")
            with state_lock:
                state["idle_turns"] += 1

        return "ok", has_changes


# ══════════════════════════════════════════════════════════════════════════════
#  CONTEXT GATHERING
# ══════════════════════════════════════════════════════════════════════════════

_gpu_last_alert = 0

def check_gpu_queue():
    supa_url = os.environ.get("SUPABASE_URL", "")
    supa_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supa_url or not supa_key:
        return 0
    try:
        import urllib.request
        url = f"{supa_url}/rest/v1/nba_experiments?status=eq.pending&target_space=in.(gpu,colab,any)&select=id&limit=1"
        req = urllib.request.Request(url)
        req.add_header("apikey", supa_key)
        req.add_header("Authorization", f"Bearer {supa_key}")
        req.add_header("Prefer", "count=exact")
        with urllib.request.urlopen(req, timeout=10) as resp:
            count = resp.headers.get("content-range", "")
            if "/" in count:
                return int(count.split("/")[1])
            return len(json.loads(resp.read()))
    except:
        return 0


def gather_context():
    global _gpu_last_alert
    ctx = {"timestamp": datetime.datetime.utcnow().isoformat()}

    # S10/S11 status
    for name, url in [("s10", S10_URL), ("s11", S11_URL)]:
        try:
            s = fetch_json(f"{url}/api/status")
            ctx[name] = {
                "status": s.get("status", "unknown"),
                "brier": s.get("best_brier"), "generation": s.get("generation", 0),
                "pop_size": s.get("pop_size", 0), "log": s.get("log", [])[-3:],
            }
        except:
            ctx[name] = {"status": "unreachable"}

    # ESPN scores
    try:
        espn = fetch_json(ESPN_URL)
        ctx["games"] = [
            {"home": next((t for t in c.get("competitors",[]) if t.get("homeAway")=="home"),{}).get("team",{}).get("abbreviation","?"),
             "away": next((t for t in c.get("competitors",[]) if t.get("homeAway")=="away"),{}).get("team",{}).get("abbreviation","?"),
             "status": c.get("status",{}).get("type",{}).get("shortDetail","?")}
            for evt in (espn.get("events") or [])
            for c in [evt.get("competitions",[{}])[0]]
        ]
    except:
        ctx["games"] = []

    # GPU queue + Colab trigger
    gpu_pending = check_gpu_queue()
    ctx["gpu_pending"] = gpu_pending
    if gpu_pending > 0 and time.time() - _gpu_last_alert > 3600:
        _gpu_last_alert = time.time()
        # Try Puppeteer, fallback to Telegram link
        trigger = os.path.join(os.path.dirname(__file__), "colab-trigger.js")
        if os.path.exists(trigger):
            try:
                r = subprocess.run(["node", trigger, COLAB_LINK], capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    send_telegram(f"🖥️ *Colab auto-triggered*\n{gpu_pending} GPU experiments pending")
                else:
                    send_telegram(f"🖥️ *{gpu_pending} GPU experiments pending*\nOpen: {COLAB_LINK}")
            except:
                send_telegram(f"🖥️ *{gpu_pending} GPU experiments pending*\nOpen: {COLAB_LINK}")
        else:
            send_telegram(f"🖥️ *{gpu_pending} GPU experiments pending*\nOpen: {COLAB_LINK}")

    # Update shared state
    with state_lock:
        state["last_context"] = ctx
        state["s10_status"] = ctx.get("s10", {}).get("status", "unknown")
        state["s11_status"] = ctx.get("s11", {}).get("status", "unknown")
        state["games_today"] = len(ctx.get("games", []))
        state["gpu_pending"] = gpu_pending
        for key in ["s10", "s11"]:
            brier = ctx.get(key, {}).get("brier")
            if brier and brier < 1.0:
                state["last_brier"] = brier
                break

    return ctx


# ══════════════════════════════════════════════════════════════════════════════
#  EVE — Monitor Agent (every 5 min, uses Claude Code CLI)
# ══════════════════════════════════════════════════════════════════════════════

def eve_worker():
    log("EVE", "Monitor agent starting (Claude Code CLI)...")

    while True:
        with state_lock:
            state["eve_turns"] += 1
            turn = state["eve_turns"]

        log("EVE", f"Turn #{turn}")

        try:
            ctx = gather_context()

            # Decide what Eve should do this turn
            s10 = ctx.get("s10", {})
            problems = []

            if s10.get("status") == "unreachable":
                problems.append("S10 is unreachable — needs restart or investigation")
            if s10.get("brier") and s10["brier"] > 0.24:
                problems.append(f"Brier is too high ({s10['brier']}) — model needs improvement")
            if s10.get("generation", 0) > 0 and s10.get("generation", 0) % 20 == 0:
                problems.append("Evolution may be stagnating — consider boosting mutation or adding features")
            if state["gpu_pending"] > 3:
                problems.append(f"{state['gpu_pending']} GPU experiments pending — Colab may need manual trigger")
            if state["idle_turns"] >= MAX_IDLE_TURNS:
                problems.append(f"IDLE ALERT: {state['idle_turns']} turns with no code pushed. MUST produce code.")

            if problems:
                # Eve runs Claude Code to fix the most urgent problem
                task = (
                    f"You are Eve, the monitor agent. Current problems detected:\n"
                    + "\n".join(f"- {p}" for p in problems) +
                    f"\n\nSystem state: S10 brier={s10.get('brier','?')}, "
                    f"gen={s10.get('generation','?')}, "
                    f"games today={len(ctx.get('games',[]))}\n\n"
                    f"Fix the most urgent problem. Focus on features/engine.py or evolution/loop.py. "
                    f"Make minimal, targeted changes. Commit and push."
                )
                output, pushed = run_claude_code(task, "nba", "Eve")
                if pushed:
                    log("EVE", "Eve pushed a fix!")
            else:
                log("EVE", f"All clear. S10={s10.get('status','?')} Brier={s10.get('brier','?')}")

        except Exception as e:
            log("EVE", f"Error: {e}")
            traceback.print_exc()

        time.sleep(EVE_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
#  ADAM — Strategist Agent (every 15 min, uses Claude Code CLI)
# ══════════════════════════════════════════════════════════════════════════════

def adam_worker():
    log("ADAM", "Strategist agent starting...")
    log("ADAM", "Sleeping 90s before first task...")
    time.sleep(90)
    log("ADAM", "Sleep done, starting first task...")

    while True:
        with state_lock:
            state["adam_turns"] += 1
            turn = state["adam_turns"]

        log("ADAM", f"Strategy turn #{turn}")

        try:
            ctx = state.get("last_context", {})
            s10 = ctx.get("s10", {})

            # Adam's strategic task — varies by turn
            if turn % 4 == 1:
                # Feature improvement turn
                task = (
                    f"You are Adam, the strategist. Current Brier: {s10.get('brier', '?')}. Target: < 0.20.\n"
                    f"STRATEGIC TASK: Improve the feature engine.\n"
                    f"Read features/engine.py. Add 1-2 high-impact features (e.g., pace-adjusted stats, "
                    f"rest-weighted performance, opponent strength decomposition).\n"
                    f"Keep changes minimal. Commit and push."
                )
            elif turn % 4 == 2:
                # Evolution tuning turn
                task = (
                    f"You are Adam, the strategist. Current Brier: {s10.get('brier', '?')}. "
                    f"Generation: {s10.get('generation', '?')}.\n"
                    f"STRATEGIC TASK: Tune the genetic evolution.\n"
                    f"Read evolution/loop.py. Consider: mutation rate, crossover strategy, "
                    f"population diversity, fitness weights, stagnation detection.\n"
                    f"Make 1 targeted improvement. Commit and push."
                )
            elif turn % 4 == 3:
                # GPU experiment submission turn
                task = (
                    f"You are Adam, the strategist. Current Brier: {s10.get('brier', '?')}.\n"
                    f"STRATEGIC TASK: Submit a GPU experiment to test a neural model.\n"
                    f"Insert a row into the Supabase nba_experiments table:\n"
                    f"  - experiment_id: 'exp_adam_{{random_hex}}'\n"
                    f"  - agent_name: 'adam_strategist'\n"
                    f"  - experiment_type: 'model_test'\n"
                    f"  - params: choose from ft_transformer, node, saint, mc_dropout_rnn\n"
                    f"  - status: 'pending', target_space: 'gpu', priority: 8\n"
                    f"  - baseline_brier: 0.2205\n"
                    f"Use DATABASE_URL from environment. Use psycopg2 or curl Supabase REST API."
                )
            else:
                # Research and analysis turn
                task = (
                    f"You are Adam, the strategist. Current Brier: {s10.get('brier', '?')}.\n"
                    f"Pushes so far: {state['pushes']}. Cain tasks: {state['cain_tasks']}.\n"
                    f"STRATEGIC TASK: Analyze the codebase and find the highest-impact improvement.\n"
                    f"Read the key files (features/engine.py, evolution/loop.py, models/).\n"
                    f"Identify what's limiting performance and implement 1 specific fix.\n"
                    f"Commit and push."
                )

            output, pushed = run_claude_code(task, "nba", "Adam")
            if pushed:
                log("ADAM", "Adam pushed strategic improvement!")

        except Exception as e:
            log("ADAM", f"Error: {e}")
            traceback.print_exc()

        time.sleep(ADAM_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
#  CAIN — Coder Agent (on demand, processes task queue via Claude Code CLI)
# ══════════════════════════════════════════════════════════════════════════════

def cain_worker():
    log("CAIN", "Coder agent starting (Claude Code CLI)...")
    time.sleep(60)  # Start 1 min after Eve

    while True:
        task_info = None
        with state_lock:
            if state["task_queue"]:
                # Prioritize Adam's tasks
                for i, t in enumerate(state["task_queue"]):
                    if t.get("priority") == "high":
                        task_info = t
                        del state["task_queue"][i]
                        break
                if not task_info:
                    task_info = state["task_queue"].popleft()

        if task_info:
            task = task_info["task"]
            from_agent = task_info.get("from", "unknown")
            repo_key = task_info.get("repo", "nba")

            log("CAIN", f"Task from {from_agent} (queue: {len(state['task_queue'])} remaining)")

            output, pushed = run_claude_code(task, repo_key, "Cain")

            with state_lock:
                state["cain_tasks"] += 1
                if pushed:
                    state["cain_successes"] += 1

            log("CAIN", f"Task done (pushed={pushed})")
        else:
            time.sleep(30)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN — Boot all 3 agents
# ══════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("[LOOP] Adam + Eve + Cain — 3 Autonomous Agents (HuggingClaw-style)", flush=True)
print("[LOOP] ALL agents use Claude Code CLI on REAL repos", flush=True)
print("=" * 60, flush=True)
print(f"[LOOP] S10: {S10_URL}", flush=True)
print(f"[LOOP] S11: {S11_URL}", flush=True)
print(f"[LOOP] GitHub token: {'SET' if GITHUB_TOKEN else 'NOT SET'}", flush=True)
print(f"[LOOP] Eve: {EVE_INTERVAL}s | Adam: {ADAM_INTERVAL}s | CC timeout: {CC_TIMEOUT}s", flush=True)

# ── Startup checks ──
log("INIT", "Verifying Claude Code CLI...")
which_claude = subprocess.run(["which", "claude"], capture_output=True, text=True)
if which_claude.returncode == 0:
    log("INIT", f"Claude CLI found: {which_claude.stdout.strip()}")
    try:
        ver = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=15)
        log("INIT", f"Claude CLI version: {ver.stdout.strip()[:100]}")
    except subprocess.TimeoutExpired:
        log("INIT", "Claude CLI --version timed out (OK, CLI is present)")
    except Exception as e:
        log("INIT", f"Claude CLI version check failed: {e} (OK, CLI is present)")
else:
    log("INIT", "WARNING: 'claude' not found in PATH — agents will not be able to code")

creds_path = Path.home() / ".claude" / ".credentials.json"
log("INIT", f"Claude credentials: {'FOUND' if creds_path.exists() else 'MISSING'}")

tg_ip = _get_telegram_ip()
log("INIT", f"Telegram resolved IP: {tg_ip or 'NOT AVAILABLE'}")

# Pre-clone repos
log("INIT", "Cloning repos...")
for key in REPOS:
    ensure_repo(key)

# Write workspace configs
for key in REPOS:
    repo_dir = REPOS[key]["dir"]
    if Path(repo_dir).exists():
        write_claude_md(repo_dir, "Agent")

# Wait for OpenClaw to start
log("INIT", "Waiting 30s for OpenClaw gateway...")
time.sleep(30)

# Launch agents
log("INIT", "Launching 3 autonomous agents...")

eve_thread = threading.Thread(target=eve_worker, name="Eve-Monitor", daemon=True)
adam_thread = threading.Thread(target=adam_worker, name="Adam-Strategist", daemon=True)
cain_thread = threading.Thread(target=cain_worker, name="Cain-Coder", daemon=True)

eve_thread.start(); log("INIT", "Eve started (monitor + Claude Code)")
adam_thread.start(); log("INIT", "Adam started (strategist + Claude Code)")
cain_thread.start(); log("INIT", "Cain started (coder + Claude Code)")

send_telegram(
    "🚀 *3 Autonomous Agents Started*\n"
    "Eve (monitor) + Adam (strategist) + Cain (coder)\n"
    "All using Claude Code CLI on real repos\n"
    f"S10 Brier target: < 0.20"
)

print("=" * 60, flush=True)
print("[LOOP] All 3 agents running — Claude Code CLI on real repos", flush=True)
print("=" * 60, flush=True)

# Main thread: heartbeat + watchdog + hang detector
_last_heartbeat = time.time()


def _hang_detector():
    """Kill process if main loop hasn't run for 5 minutes (deadlock protection)."""
    while True:
        time.sleep(120)
        if time.time() - _last_heartbeat > 300:
            print(f"[HANG-DETECTOR] No heartbeat for 5 min! Force exit.", flush=True)
            os._exit(1)  # Force kill — sync_hf.py will restart us


hang_thread = threading.Thread(target=_hang_detector, daemon=True)
hang_thread.start()

while True:
    time.sleep(60)
    _last_heartbeat = time.time()

    with state_lock:
        log("HEARTBEAT",
            f"Eve:{state['eve_turns']} Adam:{state['adam_turns']} "
            f"Cain:{state['cain_tasks']}/{state['cain_successes']} "
            f"Pushes:{state['pushes']} Idle:{state['idle_turns']} "
            f"Queue:{len(state['task_queue'])} "
            f"GPU:{state['gpu_pending']} "
            f"Brier:{state['last_brier'] or '?'}")

    # Watchdog: restart dead threads
    for name, thread, worker in [
        ("Eve", eve_thread, eve_worker),
        ("Adam", adam_thread, adam_worker),
        ("Cain", cain_thread, cain_worker),
    ]:
        if not thread.is_alive():
            log("WATCHDOG", f"{name} thread died! Restarting...")
            new_thread = threading.Thread(target=worker, name=f"{name}-Restarted", daemon=True)
            new_thread.start()
            if name == "Eve": eve_thread = new_thread
            elif name == "Adam": adam_thread = new_thread
            elif name == "Cain": cain_thread = new_thread
