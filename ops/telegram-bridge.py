#!/usr/bin/env python3
"""Telegram CLI Bridge v4.0 — Talk to Claude Code from your phone.

Three modes:
1. Claude mode (default): Messages go to Claude Code CLI — full AI assistant
2. Shell mode (/shell): Direct bash commands (like Termius)
3. AI mode (/ai): Natural language → bash via LLM

Usage:
    source .env.local
    python3 ops/telegram-bridge.py
"""

import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request
import urllib.error
import ssl
import re
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk")
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "6582544948"))
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_INTERVAL = 1
BASE_DIR = "/home/termius/mon-ipad"

LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "sk-litellm-nomos-2026"

# SSL context for HF spaces
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Working directory state per chat
chat_cwd = {}
# Mode per chat: "claude", "shell" or "ai"
chat_mode = {}
# Running background tasks
bg_tasks = {}
# Claude conversation history per chat (for multi-turn)
claude_history = {}

REPOS = {
    "mon-ipad": "/home/termius/mon-ipad",
    "rag-website": "/home/termius/rag-website",
    "rag-data-ingestion": "/home/termius/rag-data-ingestion",
    "rag-dashboard": "/home/termius/rag-dashboard",
}

# ─── Shell executor ──────────────────────────────────────────
def run_cmd(cmd, cwd=None, timeout=120):
    """Execute shell command like Termius would."""
    env = os.environ.copy()
    # Source .env.local vars
    env_file = Path(BASE_DIR) / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, v = line.split("=", 1)
                v = v.strip("'\"")
                env[k.strip()] = v
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=cwd or BASE_DIR,
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        out = (r.stdout + r.stderr).strip()
        if len(out) > 3800:
            out = out[:1800] + "\n...(truncated)...\n" + out[-1800:]
        return {"ok": r.returncode == 0, "output": out or "(no output)", "code": r.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"TIMEOUT after {timeout}s", "code": -1}
    except Exception as e:
        return {"ok": False, "output": str(e), "code": -1}


# ─── Claude Code CLI ─────────────────────────────────────────
def ask_claude(message, cwd=None):
    """Send a message to Claude Code CLI and return the response."""
    env = os.environ.copy()
    env_file = Path(BASE_DIR) / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, v = line.split("=", 1)
                v = v.strip("'\"")
                env[k.strip()] = v

    start = time.time()
    try:
        r = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", message],
            capture_output=True, text=True, timeout=120,
            cwd=cwd or BASE_DIR, env=env,
        )
        duration = time.time() - start
        output = (r.stdout or "").strip()
        if r.returncode != 0 and r.stderr:
            output = output + "\n" + r.stderr.strip() if output else r.stderr.strip()
        if len(output) > 3800:
            output = output[:1800] + "\n...(tronque)...\n" + output[-1800:]
        return {"ok": True, "output": output or "(no output)", "duration": round(duration, 1)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "Timeout (120s). Requete trop complexe.", "duration": 120}
    except FileNotFoundError:
        return {"ok": False, "output": "Claude CLI not found. Install: npm i -g @anthropic-ai/claude-code", "duration": 0}
    except Exception as e:
        return {"ok": False, "output": f"Erreur: {e}", "duration": time.time() - start}


# ─── Telegram helpers ────────────────────────────────────────
def tg(method, data=None):
    """Telegram Bot API call."""
    url = f"{API_URL}/{method}"
    if data:
        req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return None


def send(chat_id, text, parse_mode=None):
    """Send message, auto-split if too long."""
    if not text:
        text = "(empty)"
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        if parse_mode:
            result = tg("sendMessage", {"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode})
            if not result or not result.get("ok"):
                tg("sendMessage", {"chat_id": chat_id, "text": chunk})
        else:
            tg("sendMessage", {"chat_id": chat_id, "text": chunk})


def send_typing(chat_id):
    tg("sendChatAction", {"chat_id": chat_id, "action": "typing"})


# ─── LLM for AI mode ─────────────────────────────────────────
def llm_interpret(user_msg, context=""):
    """Use LLM to interpret natural language into shell commands."""
    prompt = f"""You are a CLI assistant on a Linux VM (Debian, /home/termius/mon-ipad).
The user sends natural language commands via Telegram. Convert to exact bash commands.

Available infrastructure:
- 4 RAG pipelines on HF Spaces (Standard, Graph, Quant, Orchestrator)
- Python scripts in ops/ (monitor.py, fast-ingest.py, etc.) and eval/ (quick-test.py, eval-blast.py)
- Repos: mon-ipad, rag-website, rag-data-ingestion, rag-dashboard
- Databases: Supabase, Neo4j, Pinecone
- source .env.local must precede python scripts

{context}

RULES:
- Output ONLY the bash command(s) to run. Nothing else.
- Multiple commands: separate with &&
- If truly a question (not a command), prefix with ANSWER: and give a short answer
- If ambiguous, pick the most likely command

User says: {user_msg}"""

    data = json.dumps({
        "model": "smart",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.1,
    }).encode()
    headers = {"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"}
    req = urllib.request.Request(LITELLM_URL, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"ANSWER: LLM error: {e}"


# ─── Quick status builders ───────────────────────────────────
def get_status_text():
    """Build quick infra status."""
    lines = ["NOMOS VM STATUS", ""]

    # Processes
    r = run_cmd("ps aux --no-headers | grep -E 'python3.*(ops/|eval/)' | grep -v grep | wc -l")
    lines.append(f"Agents: {r['output'].strip()} running")

    # Memory
    r = run_cmd("free -m | awk '/Mem:/{printf \"%d/%dMB (%.0f%%)\", $3, $2, $3/$2*100}'")
    lines.append(f"RAM: {r['output']}")

    # Disk
    r = run_cmd("df -h / | awk 'NR==2{printf \"%s/%s (%s)\", $3, $2, $5}'")
    lines.append(f"Disk: {r['output']}")

    # Vectors
    r = run_cmd("python3 -c \"import json; h=json.load(open('data/health-status.json')); print(h.get('e5_vectors','?'))\" 2>/dev/null")
    lines.append(f"E5 vectors: {r['output'].strip()}")

    # Spaces
    lines.append("")
    spaces = [
        ("S1", "https://lbjlincoln-nomos-rag-engine.hf.space"),
        ("S7-LLM", "https://lbjlincoln-nomos-rag-engine-7.hf.space"),
        ("S9-Ingest", "https://lbjlincoln-nomos-rag-engine-9.hf.space"),
    ]
    for name, url in spaces:
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                lines.append(f"  [OK] {name}")
        except Exception:
            lines.append(f"  [DOWN] {name}")

    return "\n".join(lines)


def get_daemons_text():
    """List active daemons."""
    r = run_cmd(
        "ps aux --no-headers | grep -E 'python3.*(ops/|eval/)' | grep -v grep "
        "| awk '{split($0,a,\" \"); for(i=11;i<=NF;i++) printf \"%s \",a[i]; print \"\"}' | sort"
    )
    return f"Active daemons:\n{r['output']}"


def get_eval_text():
    """Get latest eval results."""
    r = run_cmd(
        "python3 -c \""
        "import json; "
        "d=json.load(open('data/eval/parallel-eval-latest.json')); "
        "print(f'Last eval: {d.get(\\\"timestamp\\\",\\\"?\\\")[:16]}'); "
        "[print(f'  {p}: {s.get(\\\"accuracy\\\",0):.0%} ({s.get(\\\"total\\\",0)}Q)') "
        "for p,s in d.get('by_pipeline',{}).items()]"
        "\" 2>/dev/null"
    )
    if r["ok"] and r["output"].strip():
        return r["output"]
    return "No recent eval data. Run: source .env.local && python3 eval/quick-test.py --proxy --pipelines standard --questions 5"


# ─── Command router ──────────────────────────────────────────
def handle_message(chat_id, text, username):
    """Route incoming message to the right handler."""
    text = text.strip()

    # Security: admin only for execution
    if chat_id != ADMIN_ID:
        send(chat_id, "Admin only. Your ID: " + str(chat_id))
        return

    # ─── Slash commands ───────────────────────────────────
    cmd_lower = text.lower().split()[0] if text.startswith("/") else ""

    if cmd_lower in ("/start", "/help"):
        send(chat_id, """NOMOS TELEGRAM BRIDGE v4.0
Claude Code depuis ton telephone.

MODES:
  Default = Claude Code (IA complete, comme Termius)
  /shell = commandes bash directes
  /ai = NLP → bash via LLM
  /claude = retour mode Claude (defaut)

QUICK COMMANDS:
  /s = status complet
  /d = daemons actifs
  /e = derniers resultats eval
  /ps = processus en cours
  /free = memoire dispo
  /pull = git pull tous les repos
  /eval [n] = lancer eval rapide
  /kill <pid> = tuer un processus
  /cd <path> = changer repertoire
  /bg <cmd> = commande en arriere-plan
  /sites = checker tous les sites
  /query <question> = interroger pipeline RAG
  /yt <url> = transcript YouTube
  /web <recherche> = recherche web via LLM
  /reset = reset conversation Claude

Ecris en langage naturel — Claude Code comprend tout.""")
        return

    if cmd_lower == "/claude":
        chat_mode[chat_id] = "claude"
        send(chat_id, "Mode Claude Code actif. Parle naturellement.")
        return

    if cmd_lower == "/ai":
        chat_mode[chat_id] = "ai"
        send(chat_id, "Mode AI ON. Je traduis tes mots en commandes.\n/claude pour revenir.")
        return

    if cmd_lower == "/shell":
        chat_mode[chat_id] = "shell"
        send(chat_id, "Mode shell. Commandes bash directes.\n/claude pour revenir.")
        return

    if cmd_lower == "/reset":
        claude_history.pop(chat_id, None)
        send(chat_id, "Conversation Claude reinitialised.")
        return

    if cmd_lower == "/s":
        send_typing(chat_id)
        send(chat_id, get_status_text())
        return

    if cmd_lower == "/d":
        send_typing(chat_id)
        send(chat_id, get_daemons_text())
        return

    if cmd_lower == "/e":
        send_typing(chat_id)
        send(chat_id, get_eval_text())
        return

    if cmd_lower == "/ps":
        send_typing(chat_id)
        r = run_cmd("ps aux --sort=-%mem --no-headers | head -15 | awk '{printf \"%-6s %5s%% %5s%% %s\\n\", $2, $3, $4, $11}'")
        send(chat_id, f"Top processes (PID CPU% MEM% CMD):\n{r['output']}")
        return

    if cmd_lower == "/free":
        r = run_cmd("free -m")
        send(chat_id, r["output"])
        return

    if cmd_lower == "/pull":
        send_typing(chat_id)
        results = []
        for name, path in REPOS.items():
            if Path(path).exists():
                r = run_cmd("git pull --quiet 2>&1", cwd=path, timeout=30)
                icon = "OK" if r["ok"] else "FAIL"
                results.append(f"  [{icon}] {name}")
        send(chat_id, "Git pull:\n" + "\n".join(results))
        return

    if cmd_lower == "/eval":
        parts = text.split()
        n = parts[1] if len(parts) > 1 else "5"
        send(chat_id, f"Running eval ({n} questions)...")
        send_typing(chat_id)
        r = run_cmd(f"cd {BASE_DIR} && python3 eval/quick-test.py --proxy --pipelines standard --questions {n} 2>&1 | tail -20", timeout=180)
        send(chat_id, r["output"])
        return

    if cmd_lower == "/kill":
        parts = text.split()
        if len(parts) < 2:
            send(chat_id, "Usage: /kill <pid>")
            return
        pid = parts[1]
        r = run_cmd(f"kill {pid} 2>&1")
        send(chat_id, f"kill {pid}: {'OK' if r['ok'] else r['output']}")
        return

    if cmd_lower == "/cd":
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            cwd = chat_cwd.get(chat_id, BASE_DIR)
            send(chat_id, f"CWD: {cwd}")
            return
        new_dir = parts[1].strip()
        if not new_dir.startswith("/"):
            new_dir = os.path.join(chat_cwd.get(chat_id, BASE_DIR), new_dir)
        new_dir = os.path.realpath(new_dir)
        if os.path.isdir(new_dir):
            chat_cwd[chat_id] = new_dir
            send(chat_id, f"CWD: {new_dir}")
        else:
            send(chat_id, f"Not a directory: {new_dir}")
        return

    if cmd_lower == "/claw":
        parts = text.split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else "--help"
        send_typing(chat_id)
        r = run_cmd(f"npx clawhub {args}", timeout=60)
        send(chat_id, r["output"])
        return

    if cmd_lower == "/bg":
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send(chat_id, "Usage: /bg <command>")
            return
        bg_cmd = parts[1]
        cwd = chat_cwd.get(chat_id, BASE_DIR)
        try:
            proc = subprocess.Popen(
                bg_cmd, shell=True, cwd=cwd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=os.environ.copy(),
            )
            bg_tasks[proc.pid] = {"cmd": bg_cmd, "proc": proc, "started": datetime.now().isoformat()}
            send(chat_id, f"Background PID {proc.pid}: {bg_cmd[:80]}")
        except Exception as e:
            send(chat_id, f"Failed: {e}")
        return

    if cmd_lower == "/sites":
        send_typing(chat_id)
        send(chat_id, check_all_sites())
        return

    if cmd_lower == "/improve":
        send_typing(chat_id)
        send(chat_id, "Running Karpathy improvement cycle...")
        r = run_cmd(
            f"cd {BASE_DIR} && python3 ops/karpathy-improver.py --once 2>&1 | tail -30",
            timeout=300
        )
        send(chat_id, r["output"] if r["output"].strip() else "Improver script not found. Building it...")
        return

    if cmd_lower == "/yt":
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send(chat_id, "Usage: /yt <youtube_url_or_video_id>\nExtrait le transcript d'une video YouTube.")
            return
        url_or_id = parts[1].strip()
        send_typing(chat_id)
        send(chat_id, "Extraction du transcript...")
        # Extract video ID from URL
        r = run_cmd(f"""python3 -c "
import sys, re, json
url = '{url_or_id}'
# Extract video ID
vid = url
for pattern in [r'v=([a-zA-Z0-9_-]{{11}})', r'youtu\\.be/([a-zA-Z0-9_-]{{11}})', r'^([a-zA-Z0-9_-]{{11}})$']:
    m = re.search(pattern, url)
    if m:
        vid = m.group(1)
        break

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    ytt = YouTubeTranscriptApi()
    transcript = ytt.fetch(vid, languages=['fr', 'en'])
    lines = [s.text for s in transcript.snippets]
    full_text = ' '.join(lines)
    # Truncate for Telegram
    if len(full_text) > 3500:
        full_text = full_text[:3500] + '...(tronque)'
    print(f'VIDEO: {{vid}}')
    print(f'Longueur: {{len(lines)}} segments')
    print('---')
    print(full_text)
except ImportError:
    # Fallback: yt-dlp subtitle extraction
    import subprocess
    r = subprocess.run(['yt-dlp', '--skip-download', '--write-auto-sub', '--sub-lang', 'fr,en', '--sub-format', 'json3', '-o', '/tmp/yt_sub', f'https://www.youtube.com/watch?v={{vid}}'], capture_output=True, text=True, timeout=30)
    import glob, os
    subs = glob.glob('/tmp/yt_sub*.json3')
    if subs:
        with open(subs[0]) as f:
            data = json.load(f)
        segments = [e.get('segs', [{{}}])[0].get('utf8', '') for e in data.get('events', []) if e.get('segs')]
        full_text = ' '.join(s.strip() for s in segments if s.strip())
        if len(full_text) > 3500:
            full_text = full_text[:3500] + '...(tronque)'
        print(f'VIDEO: {{vid}} (via yt-dlp)')
        print(f'Longueur: {{len(segments)}} segments')
        print('---')
        print(full_text)
        for s in subs:
            os.remove(s)
    else:
        print('Pas de sous-titres disponibles pour cette video.')
        print(r.stderr[:500] if r.stderr else 'Installez: pip install youtube-transcript-api')
" 2>&1""", timeout=30)
        send(chat_id, r["output"])
        return

    if cmd_lower == "/web":
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send(chat_id, "Usage: /web <recherche>\nRecherche Google via LLM.")
            return
        query = parts[1].strip()
        send_typing(chat_id)
        # Use LiteLLM to search & synthesize (since no direct search API)
        try:
            payload = json.dumps({
                "model": "smart",
                "messages": [
                    {"role": "system", "content": "Tu es un assistant de recherche. L'utilisateur te donne une requete. Reponds avec les informations les plus recentes et pertinentes que tu connais. Sois concis, factuel, cite des sources quand possible. Max 3000 caracteres."},
                    {"role": "user", "content": f"Recherche: {query}"}
                ],
                "temperature": 0.3,
                "max_tokens": 1500,
            }).encode()
            req = urllib.request.Request(
                LITELLM_URL, payload,
                {"Content-Type": "application/json", "Authorization": f"Bearer {LITELLM_KEY}"}
            )
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                result = json.loads(resp.read())
                answer = result.get("choices", [{}])[0].get("message", {}).get("content", "Pas de resultat")
                model = result.get("model", "?")
                send(chat_id, f"[{model}]\n{answer[:3800]}")
        except Exception as e:
            send(chat_id, f"Erreur recherche: {e}")
        return

    if cmd_lower == "/query":
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send(chat_id, "Usage: /query <question>")
            return
        question = parts[1]
        send_typing(chat_id)
        try:
            payload = json.dumps({"question": question, "tenant_id": "finance"}).encode()
            req = urllib.request.Request(
                "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/orchestrator-v2",
                payload, {"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                result = json.loads(resp.read())
                answer = result.get("response") or result.get("answer") or result.get("output", "No answer")
                pipeline = result.get("selected_pipeline", "?")
                send(chat_id, f"[{pipeline}] {answer[:3500]}")
        except Exception as e:
            send(chat_id, f"Pipeline error: {e}")
        return

    # ─── Non-slash: claude, shell or AI mode ──────────────
    mode = chat_mode.get(chat_id, "claude")
    cwd = chat_cwd.get(chat_id, BASE_DIR)

    if mode == "claude":
        # Claude Code CLI mode — full AI assistant
        send_typing(chat_id)
        result = ask_claude(text, cwd=cwd)
        duration_tag = f" ({result['duration']}s)" if result.get('duration') else ""
        send(chat_id, result["output"] + duration_tag)
    elif mode == "ai":
        send_typing(chat_id)
        interpreted = llm_interpret(text, f"Current directory: {cwd}")
        if interpreted.startswith("ANSWER:"):
            send(chat_id, interpreted[7:].strip())
            return
        # Show what we're about to run
        cmd = interpreted.strip().strip("`").strip()
        # Remove markdown code fences if LLM wrapped it
        cmd = re.sub(r'^```\w*\n?', '', cmd)
        cmd = re.sub(r'\n?```$', '', cmd)
        cmd = cmd.strip()
        send(chat_id, f"$ {cmd}")
        send_typing(chat_id)
        r = run_cmd(cmd, cwd=cwd, timeout=120)
        icon = "+" if r["ok"] else "x"
        send(chat_id, f"[{icon}] exit {r['code']}\n{r['output']}")
    else:
        # Direct shell mode — just run it
        send_typing(chat_id)
        r = run_cmd(text, cwd=cwd, timeout=120)
        icon = "+" if r["ok"] else "x"
        send(chat_id, f"[{icon}] exit {r['code']}\n{r['output']}")


# ─── Site checker ─────────────────────────────────────────────
def check_all_sites():
    """Check all Nomos websites."""
    sites = [
        ("Expert (main)", "https://nomos42.vercel.app"),
        ("Satellite", "https://nomos42.vercel.app/satellite"),
        ("Marketplace", "https://nomos42.vercel.app/marketplace"),
        ("Factory", "https://nomos42.vercel.app/factory"),
        ("Vault", "https://nomos42.vercel.app/vault"),
        ("Dashboard", "https://nomos42.vercel.app/dashboard"),
        ("Valorisation", "https://nomos42.vercel.app/valorisation"),
        ("Graph", "https://nomos42.vercel.app/graph"),
    ]
    lines = ["WEBSITE STATUS", ""]
    for name, url in sites:
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Nomos-Monitor/1.0")
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                lines.append(f"  [OK] {name} ({resp.status})")
        except urllib.error.HTTPError as e:
            lines.append(f"  [{e.code}] {name}")
        except Exception as e:
            lines.append(f"  [DOWN] {name}: {str(e)[:40]}")
    return "\n".join(lines)


# ─── Main loop ────────────────────────────────────────────────
def main():
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] === NOMOS TELEGRAM BRIDGE v4.0 ===")
    print(f"[{ts}] Bot: @Nomos42Bot | Admin: {ADMIN_ID}")
    print(f"[{ts}] Mode: Claude Code CLI (default)")
    print(f"[{ts}] Polling...")

    tg("deleteWebhook")

    # Notify admin that bridge is up
    send(ADMIN_ID, "BRIDGE v4.0 ONLINE\nMode Claude Code actif. Parle naturellement.\n/help pour toutes les options.")

    offset = 0
    errors = 0
    while True:
        try:
            result = tg("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message"]})
            if not result or not result.get("ok"):
                errors += 1
                if errors > 10:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 10+ consecutive TG errors, sleeping 30s")
                    time.sleep(30)
                    errors = 0
                time.sleep(POLL_INTERVAL)
                continue

            errors = 0
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                username = msg.get("from", {}).get("username", "?")

                if not text or not chat_id:
                    continue

                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] @{username}: {text[:100]}")

                try:
                    handle_message(chat_id, text, username)
                except Exception as e:
                    print(f"[{ts}] Handler error: {e}")
                    traceback.print_exc()
                    send(chat_id, f"Error: {e}")

        except KeyboardInterrupt:
            print("\nBridge stopped.")
            break
        except Exception as e:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] Loop error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
