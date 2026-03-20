#!/usr/bin/env python3 -u
"""
Adam + Eve + Cain — 3 Autonomous NBA Quant AI Agents

Based on HuggingClaw's conversation-loop.py pattern.
All 3 agents run as separate threads inside the same OpenClaw instance.

Architecture:
  ADAM (Strategist)  — Reviews results, sets direction, creates experiments (15 min)
  EVE  (Monitor)     — Monitors evolution health, ESPN, detects issues (5 min)
  CAIN (Coder)       — Executes coding tasks via Claude Code CLI (on demand)

All agents share the same A2A gateway and can communicate with each other.
Claude Code CLI uses OAuth (Max subscription) — no API keys needed.
"""
import json, time, re, sys, os, subprocess, threading, datetime, uuid, traceback
from pathlib import Path
from collections import deque

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ── Endpoints ────────────────────────────────────────────────────────────────
S10_URL = "https://lbjlincoln-nomos-nba-quant.hf.space"
S11_URL = "https://lbjlincoln-nomos-nba-quant-2.hf.space"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# ── Intervals ────────────────────────────────────────────────────────────────
EVE_INTERVAL = 300     # 5 minutes — monitoring
ADAM_INTERVAL = 900    # 15 minutes — strategy
CAIN_TIMEOUT = 300     # 5 minutes max per coding task

# ── OpenClaw Gateway ─────────────────────────────────────────────────────────
SPACE_HOST = os.environ.get("SPACE_HOST", "lbjlincoln-nomos-eve-agent.hf.space")
SPACE_ID = os.environ.get("SPACE_ID", "LBJLincoln/nomos-eve-agent")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "nomos42")
A2A_INTERNAL_URL = "http://localhost:18800/a2a/jsonrpc"
OPENCLAW_URL = f"https://{SPACE_HOST}"

# ── HF API ───────────────────────────────────────────────────────────────────
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# ── Workspaces (like HuggingClaw: separate per agent) ─────────────────────
CAIN_WORK_DIR = "/tmp/cain-workspace"
ADAM_WORK_DIR = "/tmp/adam-workspace"

# ── Shared State ─────────────────────────────────────────────────────────────
state = {
    "eve_turns": 0,
    "adam_turns": 0,
    "cain_tasks": 0,
    "cain_successes": 0,
    "last_brier": None,
    "s10_status": "unknown",
    "s11_status": "unknown",
    "games_today": 0,
    "last_context": {},
    "task_queue": deque(maxlen=50),
    "action_log": deque(maxlen=100),
}
state_lock = threading.Lock()
cc_lock = threading.Lock()
cc_running = False

# ══════════════════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def log(agent, msg):
    """Thread-safe logging."""
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] [{agent}] {msg}", flush=True)
    with state_lock:
        state["action_log"].append(f"[{ts}] [{agent}] {msg}")


def fetch_json(url, timeout=15):
    """Fetch JSON from URL."""
    import urllib.request
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def send_to_a2a(message, system_prompt=None):
    """Send message to OpenClaw via internal A2A gateway."""
    import urllib.request

    parts = [{"type": "text", "text": message}]
    if system_prompt:
        parts.insert(0, {"type": "text", "text": f"[SYSTEM] {system_prompt}"})

    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": str(uuid.uuid4()),
        "params": {
            "message": {
                "role": "user",
                "parts": parts
            }
        }
    }

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(A2A_INTERNAL_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {GATEWAY_TOKEN}")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            parts = result.get("result", {}).get("artifacts", [{}])
            texts = []
            for part in parts:
                for p in part.get("parts", []):
                    if p.get("type") == "text":
                        texts.append(p["text"])
            return "\n".join(texts) if texts else str(result)
    except Exception as e:
        log("A2A", f"Send failed: {e}")
        return None


def parse_tasks(text):
    """Parse [TASK] blocks from agent responses."""
    tasks = []
    pattern = r'\[TASK\](.*?)(?:\[/TASK\]|\[TASK\]|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        task = match.strip()
        if task:
            tasks.append(task)
    return tasks


def setup_workspace(workspace, agent_name):
    """Set up workspace with CLAUDE.md and skill files."""
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)

    claude_md = ws / "CLAUDE.md"
    claude_md.write_text(f"""# {agent_name} — NBA Quant AI Agent Workspace

You are {agent_name}, an autonomous NBA Quant AI agent.
You have Claude Code Max OAuth credentials (no API key needed).

## Key Endpoints
- S10 (Evolution): {S10_URL}
- S11 (Parallel): {S11_URL}
- ESPN Scores: {ESPN_URL}
- Eve (OpenClaw): {OPENCLAW_URL}

## Rules
- NEVER run ML training locally — submit experiments to Supabase for GPU runners
- Keep changes minimal and focused
- Commit and push when done
- Use git for version control
- Current best Brier: 0.2205 — your goal is to beat it
""")

    commands_dir = ws / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    (commands_dir / "fix-evolution.md").write_text("""# Fix Evolution
Read relevant evolution files, diagnose the issue, make minimal changes, commit and push.""")

    (commands_dir / "research.md").write_text("""# Research
Analyze the model, research new techniques/features, write findings, suggest improvements.""")

    (commands_dir / "submit-experiment.md").write_text("""# Submit Experiment
Create and submit a new experiment to the Supabase nba_experiments table for GPU evaluation.""")

    acpx_dir = ws / ".acpx"
    acpx_dir.mkdir(parents=True, exist_ok=True)
    config = acpx_dir / "config.json"
    if not config.exists():
        config.write_text(json.dumps({
            "defaultAgent": "claude",
            "defaultPermissions": "approve-all",
            "format": "text"
        }))

    log(agent_name, f"Workspace ready at {workspace}")


def check_gpu_queue():
    """Check pending GPU experiments in Supabase and send Telegram alert if needed."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return 0
    try:
        import urllib.request
        # Use Supabase REST API to check pending GPU experiments
        supa_url = os.environ.get("SUPABASE_URL", "")
        supa_key = os.environ.get("SUPABASE_ANON_KEY", "")
        if supa_url and supa_key:
            url = f"{supa_url}/rest/v1/nba_experiments?status=eq.pending&target_space=in.(gpu,colab,any)&select=id&limit=1"
            req = urllib.request.Request(url)
            req.add_header("apikey", supa_key)
            req.add_header("Authorization", f"Bearer {supa_key}")
            req.add_header("Prefer", "count=exact")
            with urllib.request.urlopen(req, timeout=10) as resp:
                count = resp.headers.get("content-range", "")
                # Format: "0-0/5" or "*/0"
                if "/" in count:
                    total = int(count.split("/")[1])
                else:
                    data = json.loads(resp.read())
                    total = len(data)
                return total
    except Exception as e:
        log("GPU", f"Queue check failed: {e}")
    return 0


def send_telegram(text):
    """Send a Telegram message to admin."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    admin_id = os.environ.get("TELEGRAM_ADMIN_ID", "")
    if not bot_token or not admin_id:
        return
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({"chat_id": admin_id, "text": text, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log("TG", f"Send failed: {e}")


# Track GPU alert state to avoid spamming
_gpu_last_alert = 0
COLAB_LINK = "https://colab.research.google.com/github/LBJLincoln/nomos-nba-agent/blob/main/colab/nba_gpu_runner.ipynb"


def gather_context():
    """Gather current system state."""
    global _gpu_last_alert
    ctx = {"timestamp": datetime.datetime.utcnow().isoformat()}

    # S10 status
    try:
        s10 = fetch_json(f"{S10_URL}/api/status")
        ctx["s10"] = {
            "status": s10.get("status", "unknown"),
            "brier": s10.get("best_brier", None),
            "generation": s10.get("generation", 0),
            "pop_size": s10.get("pop_size", 0),
            "features": s10.get("feature_candidates", 0),
            "log": s10.get("log", [])[-5:],
        }
    except:
        ctx["s10"] = {"status": "unreachable"}

    # S11 status
    try:
        s11 = fetch_json(f"{S11_URL}/api/status")
        ctx["s11"] = {
            "status": s11.get("status", "unknown"),
            "brier": s11.get("best_brier", None),
            "generation": s11.get("generation", 0),
            "pop_size": s11.get("pop_size", 0),
            "features": s11.get("feature_candidates", 0),
            "log": s11.get("log", [])[-5:],
        }
    except:
        ctx["s11"] = {"status": "unreachable"}

    # ESPN scores
    try:
        espn = fetch_json(ESPN_URL)
        games = []
        for evt in (espn.get("events") or []):
            comp = evt.get("competitions", [{}])[0]
            teams = comp.get("competitors", [])
            home = next((t for t in teams if t.get("homeAway") == "home"), {})
            away = next((t for t in teams if t.get("homeAway") == "away"), {})
            games.append({
                "home": home.get("team", {}).get("abbreviation", "?"),
                "away": away.get("team", {}).get("abbreviation", "?"),
                "status": comp.get("status", {}).get("type", {}).get("shortDetail", "?"),
                "home_score": home.get("score", "?"),
                "away_score": away.get("score", "?"),
            })
        ctx["games"] = games
    except:
        ctx["games"] = []

    # Check GPU experiment queue
    gpu_pending = check_gpu_queue()
    ctx["gpu_pending"] = gpu_pending
    if gpu_pending > 0:
        now = time.time()
        # Trigger max once per hour
        if now - _gpu_last_alert > 3600:
            _gpu_last_alert = now
            # Try browser trigger first
            try:
                trigger_script = os.path.join(os.path.dirname(__file__), "colab-trigger.js")
                if os.path.exists(trigger_script):
                    log("GPU", f"{gpu_pending} pending — launching Colab via Puppeteer...")
                    result = subprocess.run(
                        ["node", trigger_script, COLAB_LINK],
                        capture_output=True, text=True, timeout=120
                    )
                    if result.returncode == 0:
                        log("GPU", "Colab triggered successfully via browser")
                        send_telegram(f"🖥️ *Colab GPU Runner auto-triggered*\n{gpu_pending} experiments pending")
                    else:
                        log("GPU", f"Browser trigger failed: {result.stderr[:200]}")
                        send_telegram(
                            f"🖥️ *{gpu_pending} GPU experiments pending*\n"
                            f"Auto-trigger failed — open manually:\n{COLAB_LINK}"
                        )
                else:
                    send_telegram(
                        f"🖥️ *{gpu_pending} GPU experiments pending*\n"
                        f"Open Colab to run them:\n{COLAB_LINK}"
                    )
            except Exception as e:
                log("GPU", f"Trigger error: {e}")
                send_telegram(
                    f"🖥️ *{gpu_pending} GPU experiments pending*\n"
                    f"Open Colab: {COLAB_LINK}"
                )

    # Update shared state
    with state_lock:
        state["last_context"] = ctx
        state["s10_status"] = ctx.get("s10", {}).get("status", "unknown")
        state["s11_status"] = ctx.get("s11", {}).get("status", "unknown")
        state["games_today"] = len(ctx.get("games", []))

        s10_brier = ctx.get("s10", {}).get("brier")
        s11_brier = ctx.get("s11", {}).get("brier")
        if s10_brier and s10_brier < 1.0:
            state["last_brier"] = s10_brier
        elif s11_brier and s11_brier < 1.0:
            state["last_brier"] = s11_brier

    return ctx


# ══════════════════════════════════════════════════════════════════════════════
#  EVE — Monitor Agent (every 5 minutes)
# ══════════════════════════════════════════════════════════════════════════════

EVE_SYSTEM = """You are Eve, the Monitor agent in the NBA Quant AI system.

Your role:
1. MONITOR evolution health on S10/S11 — detect stagnation, crashes, errors
2. TRACK NBA games and scores from ESPN
3. DETECT issues and alert via Telegram
4. PROPOSE coding tasks for Cain to execute
5. REPORT important findings to Adam

You work with:
- Adam (Strategist) — sets direction every 15 min
- Cain (Coder) — executes code changes on demand

If you find issues that need code changes, write [TASK] blocks:
[TASK]
Description of what Cain should code
[/TASK]

Be concise. Focus on actionable observations."""


def eve_worker():
    """Eve monitoring loop — runs every 5 minutes."""
    log("EVE", "Monitor agent starting...")

    while True:
        with state_lock:
            state["eve_turns"] += 1
            turn = state["eve_turns"]

        log("EVE", f"Turn #{turn}")

        try:
            ctx = gather_context()

            msg = f"""# Eve Monitor — Turn #{turn}
Time: {ctx.get('timestamp', 'unknown')} UTC

## S10 (Primary Evolution)
{json.dumps(ctx.get('s10', {}), indent=2)}

## S11 (Parallel Experiments)
{json.dumps(ctx.get('s11', {}), indent=2)}

## NBA Games Today
{json.dumps(ctx.get('games', []), indent=2)}

## System Stats
- Eve turns: {state['eve_turns']}
- Adam turns: {state['adam_turns']}
- Cain tasks: {state['cain_tasks']} ({state['cain_successes']} successful)
- Last Brier: {state['last_brier'] or 'unknown'}
- Task queue: {len(state['task_queue'])} pending

## Your Job
1. Is evolution healthy? Any stagnation?
2. Are there errors in the logs?
3. Any games today that need predictions?
4. Should Cain fix anything?

If code changes needed, write [TASK] blocks for Cain."""

            response = send_to_a2a(msg, EVE_SYSTEM)

            if response:
                log("EVE", f"Response ({len(response)} chars): {response[:200]}")

                # Parse tasks and queue for Cain
                tasks = parse_tasks(response)
                if tasks:
                    with state_lock:
                        for task in tasks:
                            state["task_queue"].append({
                                "from": "eve",
                                "task": task,
                                "created": datetime.datetime.utcnow().isoformat(),
                            })
                    log("EVE", f"Queued {len(tasks)} task(s) for Cain")
            else:
                log("EVE", "No response from A2A")

        except Exception as e:
            log("EVE", f"Error: {e}")
            traceback.print_exc()

        log("EVE", f"Turn #{turn} complete. Next in {EVE_INTERVAL}s")
        time.sleep(EVE_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
#  ADAM — Strategist Agent (every 15 minutes)
# ══════════════════════════════════════════════════════════════════════════════

ADAM_SYSTEM = """You are Adam, the Strategist agent in the NBA Quant AI system.

Your role:
1. SET DIRECTION — decide what improvements to prioritize
2. REVIEW results from Cain's coding tasks and GPU experiments
3. CREATE new experiments (feature tests, model tests, benchmarks)
4. OPTIMIZE the genetic evolution parameters
5. RESEARCH new techniques from papers and competitions

You are the architect. You think big. You set the agenda.

You work with:
- Eve (Monitor) — reports system health every 5 min
- Cain (Coder) — executes your code tasks

Current best Brier: 0.2205 (baseline)
Target: Brier < 0.20, ROI > 5%, Sharpe > 1.5

If you want code changes, write [TASK] blocks for Cain:
[TASK]
Detailed description of what to implement
[/TASK]

Think strategically. What's the highest-impact improvement right now?"""


def adam_worker():
    """Adam strategy loop — runs every 15 minutes."""
    log("ADAM", "Strategist agent starting...")
    # Adam starts 2 min after Eve (staggered)
    time.sleep(120)

    while True:
        with state_lock:
            state["adam_turns"] += 1
            turn = state["adam_turns"]

        log("ADAM", f"Strategy turn #{turn}")

        try:
            ctx = state.get("last_context", {})
            recent_actions = list(state["action_log"])[-20:]

            msg = f"""# Adam Strategy — Turn #{turn}
Time: {datetime.datetime.utcnow().isoformat()} UTC

## Current State
- S10: {state['s10_status']} | S11: {state['s11_status']}
- Best Brier: {state['last_brier'] or 'unknown'} (target: < 0.20)
- Games today: {state['games_today']}
- Cain completed: {state['cain_tasks']} tasks ({state['cain_successes']} successful)
- Eve has run: {state['eve_turns']} monitoring turns
- Pending tasks: {len(state['task_queue'])}

## S10 Detail
{json.dumps(ctx.get('s10', {}), indent=2)}

## S11 Detail
{json.dumps(ctx.get('s11', {}), indent=2)}

## Recent Agent Activity
{chr(10).join(recent_actions[-10:])}

## Your Job (Strategist)
1. What is the highest-impact improvement to make RIGHT NOW?
2. Should we change evolution parameters? (mutation, population, crossover)
3. Are there new features or techniques to research?
4. Should we submit GPU experiments? (FT-Transformer, NODE, SAINT, MC Dropout RNN)
5. What should Cain work on next?

Current model arsenal:
- Traditional: XGBoost, LightGBM, CatBoost, Random Forest, Stacking
- Neural (GPU): MLP, LSTM, FT-Transformer, TabNet, NODE, SAINT, TFT
- Uncertainty: MC Dropout RNN
- Loss functions: BCE, Focal, Brier, Label Smoothing

Write [TASK] blocks for Cain to implement your strategy."""

            response = send_to_a2a(msg, ADAM_SYSTEM)

            if response:
                log("ADAM", f"Strategy ({len(response)} chars): {response[:300]}")

                tasks = parse_tasks(response)
                if tasks:
                    with state_lock:
                        for task in tasks:
                            state["task_queue"].append({
                                "from": "adam",
                                "task": task,
                                "created": datetime.datetime.utcnow().isoformat(),
                                "priority": "high",
                            })
                    log("ADAM", f"Queued {len(tasks)} strategic task(s) for Cain")
            else:
                log("ADAM", "No response from A2A")

        except Exception as e:
            log("ADAM", f"Error: {e}")
            traceback.print_exc()

        log("ADAM", f"Strategy turn #{turn} complete. Next in {ADAM_INTERVAL}s")
        time.sleep(ADAM_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
#  CAIN — Coder Agent (on demand, from task queue)
# ══════════════════════════════════════════════════════════════════════════════

def cain_execute(task_info):
    """Execute a single coding task via Claude Code CLI (acpx claude)."""
    global cc_running
    task = task_info["task"]
    from_agent = task_info.get("from", "unknown")
    workspace = CAIN_WORK_DIR

    log("CAIN", f"Executing task from {from_agent}: {task[:100]}...")

    try:
        with cc_lock:
            cc_running = True

        env = os.environ.copy()
        env["CI"] = "true"

        # Use acpx claude (like HuggingClaw)
        cmd = ["acpx", "claude", task]
        proc = subprocess.Popen(
            cmd,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines = []
        start = time.time()
        while True:
            if time.time() - start > CAIN_TIMEOUT:
                proc.kill()
                log("CAIN", f"Task timed out after {CAIN_TIMEOUT}s")
                return "TIMEOUT"

            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                output_lines.append(line.rstrip())

        exit_code = proc.returncode
        output = "\n".join(output_lines[-50:])

        with state_lock:
            state["cain_tasks"] += 1
            if exit_code == 0:
                state["cain_successes"] += 1

        if exit_code == 0:
            log("CAIN", f"Task completed (exit 0, {len(output_lines)} lines)")
        else:
            log("CAIN", f"Task failed (exit {exit_code})")

        return output

    except Exception as e:
        log("CAIN", f"Error: {e}")
        return f"ERROR: {e}"
    finally:
        with cc_lock:
            cc_running = False


def cain_worker():
    """Cain coding loop — processes tasks from the queue."""
    log("CAIN", "Coder agent starting...")
    # Cain starts 1 min after Eve
    time.sleep(60)

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
            log("CAIN", f"Picked up task from {task_info.get('from', '?')} (queue: {len(state['task_queue'])} remaining)")
            result = cain_execute(task_info)
            log("CAIN", f"Result: {result[:200] if result else 'empty'}")
        else:
            # No tasks — sleep and check again
            time.sleep(30)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN — Start all 3 agents
# ══════════════════════════════════════════════════════════════════════════════

print("=" * 60, flush=True)
print("[LOOP] Adam + Eve + Cain — 3 Autonomous Agents Starting", flush=True)
print("=" * 60, flush=True)
print(f"[LOOP] S10: {S10_URL}", flush=True)
print(f"[LOOP] S11: {S11_URL}", flush=True)
print(f"[LOOP] A2A: {A2A_INTERNAL_URL}", flush=True)
print(f"[LOOP] OpenClaw: {OPENCLAW_URL}", flush=True)
print(f"[LOOP] Eve interval: {EVE_INTERVAL}s | Adam interval: {ADAM_INTERVAL}s", flush=True)

# Set up workspaces
log("INIT", "Setting up workspaces...")
setup_workspace(CAIN_WORK_DIR, "Cain")
setup_workspace(ADAM_WORK_DIR, "Adam")

# Wait for OpenClaw + A2A gateway
log("INIT", "Waiting 60s for OpenClaw + A2A to initialize...")
time.sleep(60)

# Verify A2A
log("INIT", "Verifying A2A gateway...")
try:
    import urllib.request
    well_known_url = "http://localhost:18800/.well-known/agent.json"
    req = urllib.request.Request(well_known_url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        agent_card = json.loads(resp.read())
        log("INIT", f"A2A agent: {agent_card.get('name', '?')} (v{agent_card.get('protocolVersion', '?')})")
except Exception as e:
    log("INIT", f"A2A verification failed: {e} — will retry on first turn")

# Launch all 3 agents as daemon threads
log("INIT", "Launching 3 autonomous agents...")

eve_thread = threading.Thread(target=eve_worker, name="Eve-Monitor", daemon=True)
adam_thread = threading.Thread(target=adam_worker, name="Adam-Strategist", daemon=True)
cain_thread = threading.Thread(target=cain_worker, name="Cain-Coder", daemon=True)

eve_thread.start()
log("INIT", "Eve (Monitor) started")

adam_thread.start()
log("INIT", "Adam (Strategist) started")

cain_thread.start()
log("INIT", "Cain (Coder) started")

print("=" * 60, flush=True)
print("[LOOP] All 3 agents running autonomously", flush=True)
print("[LOOP] Eve: monitor every 5 min", flush=True)
print("[LOOP] Adam: strategy every 15 min", flush=True)
print("[LOOP] Cain: code on demand from task queue", flush=True)
print("=" * 60, flush=True)

# Main thread: keep alive + heartbeat
while True:
    time.sleep(60)
    with state_lock:
        log("HEARTBEAT",
            f"Eve:{state['eve_turns']} Adam:{state['adam_turns']} "
            f"Cain:{state['cain_tasks']}/{state['cain_successes']} "
            f"Queue:{len(state['task_queue'])} "
            f"Brier:{state['last_brier'] or '?'}")

    # Check if threads are alive
    for name, thread in [("Eve", eve_thread), ("Adam", adam_thread), ("Cain", cain_thread)]:
        if not thread.is_alive():
            log("WATCHDOG", f"{name} thread died! Restarting...")
            if name == "Eve":
                eve_thread = threading.Thread(target=eve_worker, name="Eve-Monitor", daemon=True)
                eve_thread.start()
            elif name == "Adam":
                adam_thread = threading.Thread(target=adam_worker, name="Adam-Strategist", daemon=True)
                adam_thread.start()
            elif name == "Cain":
                cain_thread = threading.Thread(target=cain_worker, name="Cain-Coder", daemon=True)
                cain_thread.start()
