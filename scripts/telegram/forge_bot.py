#!/usr/bin/env python3
"""
Forge42 Bot — Telegram bot for Forge Factory users
====================================================
Identity: The Factory. Onboarding, status, task forwarding.
Multi-user support with role-based access and rate limiting.

Env vars:
  FORGE_BOT_TOKEN      — @Forge42Bot token (required)
  TERMINAL_API_URL     — terminal API base URL (default: http://localhost:8081)
  TERMINAL_TOKEN       — admin token for terminal API (for /run command)
  FORGE_USERS_FILE     — path to users.json (default: scripts/terminal/users.json)
"""

import os
import sys
import json
import time
import signal
import logging
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FORGE] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/forge-bot.log"),
    ],
    datefmt="%H:%M:%S",
)
log = logging.getLogger("forge")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("FORGE_BOT_TOKEN", "") or os.environ.get("FORGE42_BOT_TOKEN", "")
TERMINAL_API_URL = os.environ.get("TERMINAL_API_URL", "http://localhost:8081")
TERMINAL_TOKEN = os.environ.get("TERMINAL_TOKEN", "")
WORKDIR = os.environ.get("CLAUDE_WORKDIR", os.path.expanduser("~/mon-ipad"))

USERS_FILE = os.environ.get(
    "FORGE_USERS_FILE",
    os.path.join(os.path.dirname(__file__), "../terminal/users.json"),
)
USERS_FILE = os.path.normpath(USERS_FILE)

# Forge user registry file (tracks Telegram IDs → user records)
FORGE_REGISTRY_FILE = "/tmp/forge-users-registry.json"

# Rate limiting: 5 commands per minute per user
RATE_WINDOW = 60
RATE_LIMIT = 5
# user_id -> list of timestamps
_rate_buckets: dict = defaultdict(list)

MAX_MSG_LEN = 4000
POLL_TIMEOUT = 30
MAX_CLAUDE_TIMEOUT = 120

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

running = True


def _signal_handler(sig, frame):
    global running
    log.info("Shutting down...")
    running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ---------------------------------------------------------------------------
# Users registry (maps Telegram user_id -> forge user record)
# ---------------------------------------------------------------------------

def load_users_file() -> dict:
    """Load the users.json file with user definitions."""
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        log.warning(f"Users file not found: {USERS_FILE}")
        return {"users": {}}
    except Exception as e:
        log.error(f"Failed to load users file: {e}")
        return {"users": {}}


def load_registry() -> dict:
    """Load the Telegram ID → forge user mapping."""
    try:
        if os.path.exists(FORGE_REGISTRY_FILE):
            with open(FORGE_REGISTRY_FILE) as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Failed to load registry: {e}")
    return {"telegram_users": {}}


def save_registry(registry: dict):
    """Persist the Telegram registry."""
    try:
        with open(FORGE_REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save registry: {e}")


def get_forge_user(telegram_id: int) -> dict | None:
    """Return forge user record for a given Telegram ID, or None."""
    registry = load_registry()
    key = str(telegram_id)
    username = registry["telegram_users"].get(key)
    if not username:
        return None
    users_data = load_users_file()
    return users_data["users"].get(username)


def link_user(telegram_id: int, username: str) -> bool:
    """Link a Telegram ID to a forge username. Returns True on success."""
    users_data = load_users_file()
    if username not in users_data["users"]:
        return False
    registry = load_registry()
    registry["telegram_users"][str(telegram_id)] = username
    save_registry(registry)
    return True


def is_rate_limited(user_id: int) -> bool:
    """Return True if user has exceeded their rate limit."""
    now = time.time()
    bucket = _rate_buckets[user_id]
    # Evict expired entries
    _rate_buckets[user_id] = [t for t in bucket if now - t < RATE_WINDOW]
    if len(_rate_buckets[user_id]) >= RATE_LIMIT:
        return True
    _rate_buckets[user_id].append(now)
    return False


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

def tg_request(method: str, data: dict | None = None) -> dict:
    url = f"{API}/{method}"
    if data:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.error(f"TG API error ({method}): {e}")
        return {"ok": False}


def send_msg(chat_id, text: str, parse_mode: str = "HTML", reply_to: int | None = None):
    """Send message, splitting if needed."""
    chunks = [text[i:i + MAX_MSG_LEN] for i in range(0, len(text), MAX_MSG_LEN)]
    for chunk in chunks:
        data = {"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode}
        if reply_to:
            data["reply_to_message_id"] = reply_to
        result = tg_request("sendMessage", data)
        if not result.get("ok"):
            # Retry without parse_mode in case of HTML entity errors
            data["parse_mode"] = ""
            data["text"] = chunk
            tg_request("sendMessage", data)


def send_typing(chat_id):
    tg_request("sendChatAction", {"chat_id": chat_id, "action": "typing"})


def _escape(text: str) -> str:
    """Escape HTML entities for Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Terminal API relay
# ---------------------------------------------------------------------------

def call_terminal_api(command: str, token: str | None = None) -> dict:
    """POST a command to the terminal API. Returns response dict."""
    tok = token or TERMINAL_TOKEN
    if not tok:
        return {"output": "[error] No terminal token configured", "exit_code": -1}
    payload = json.dumps({"token": tok, "command": command}).encode()
    req = urllib.request.Request(
        f"{TERMINAL_API_URL}/api/exec",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except Exception:
            return {"output": f"[HTTP {e.code}] {body[:200]}", "exit_code": -1}
    except Exception as e:
        return {"output": f"[connection error] {e}", "exit_code": -1}


# ---------------------------------------------------------------------------
# Claude Code relay (for complex questions)
# ---------------------------------------------------------------------------

FORGE_CONTEXT = (
    "You are Forge42, an AI assistant for the Forge Factory platform. "
    "You help operators and users with NBA data ingestion, system status, "
    "and general Nomos42 questions. Be concise (under 15 lines). "
    "You have access to the codebase. Give REAL data, not vague summaries."
)


def run_claude(prompt: str) -> str:
    """Run Claude Code CLI with the given prompt."""
    full_prompt = f"{FORGE_CONTEXT}\n\nUser question: {prompt}"
    cmd = ["claude", "-p", full_prompt, "--output-format", "text"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=MAX_CLAUDE_TIMEOUT,
            cwd=WORKDIR,
            env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL": "1"},
        )
        output = result.stdout.strip()
        if not output and result.stderr:
            output = f"[stderr] {result.stderr.strip()[:500]}"
        return output or "[no output]"
    except subprocess.TimeoutExpired:
        return "[timeout — claude took too long]"
    except Exception as e:
        return f"[error] {e}"


# ---------------------------------------------------------------------------
# Command text blocks
# ---------------------------------------------------------------------------

WELCOME_TEXT = """<b>Welcome to Forge Factory!</b>

I'm your Forge42 assistant. I can help you:
- Check the status of all Nomos42 services
- Run NBA data ingestion commands
- Answer questions about the codebase

<b>First time here?</b> Use <code>/login &lt;username&gt;</code> to link your account.

<b>Commands:</b>
/start — Show this message
/login &lt;username&gt; — Link your forge account
/status — System health snapshot
/whoami — Show your account info
/ask &lt;question&gt; — Ask Claude about the codebase
/run &lt;command&gt; — Run a shell command (operators+)
/help — Show all commands"""

HELP_TEXT = """<b>Forge42 Bot Commands</b>

<b>Accounts:</b>
/login &lt;username&gt;   — Link your forge account
/whoami              — Show your account info

<b>Status:</b>
/status              — System health snapshot
/spaces              — HF evolution islands status
/picks               — Latest NBA picks

<b>Advanced (operator+):</b>
/ask &lt;question&gt;     — Ask Claude about the codebase
/run &lt;command&gt;      — Run a safe shell command

<b>Rate limit:</b> {rate_limit} commands per minute.
<b>Support:</b> Contact @Nomos42Bot for admin access.""".format(rate_limit=RATE_LIMIT)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

# Operator-restricted commands — these are blocked for operator-level users
OPERATOR_BLOCKLIST = [
    "kill", "pkill", "killall",
    "rm -rf", "rm -f",
    "git push",
    "git reset",
    "shutdown", "reboot", "poweroff",
    "sudo",
    "chmod",
    "passwd",
    "> /dev",
]


def is_operator_blocked(command: str) -> bool:
    """Check if a command is forbidden for operator-level users."""
    cmd_lower = command.strip().lower()
    for pattern in OPERATOR_BLOCKLIST:
        if pattern in cmd_lower:
            return True
    return False


def handle_command(chat_id: int, msg_id: int, user_id: int, text: str):
    text = text.strip()
    forge_user = get_forge_user(user_id)

    # ── /start ──────────────────────────────────────────────────────────────
    if text.startswith("/start"):
        send_msg(chat_id, WELCOME_TEXT, reply_to=msg_id)
        return

    # ── /help ───────────────────────────────────────────────────────────────
    if text.startswith("/help"):
        send_msg(chat_id, HELP_TEXT, reply_to=msg_id)
        return

    # ── /login ──────────────────────────────────────────────────────────────
    if text.startswith("/login"):
        parts = text.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            send_msg(chat_id, "Usage: /login <username>\nExample: /login pierre", reply_to=msg_id)
            return
        username = parts[1].strip().lower()
        if link_user(user_id, username):
            users_data = load_users_file()
            u = users_data["users"][username]
            send_msg(
                chat_id,
                f"Linked to <b>{u['name']}</b> ({u['role']}, {u['access_level']}). "
                f"Machine: {u['machine']}. Status: <code>{u['status']}</code>.",
                reply_to=msg_id,
            )
            log.info(f"User {user_id} linked to forge account '{username}'")
        else:
            send_msg(
                chat_id,
                f"Username <code>{_escape(username)}</code> not found in the forge registry.\n"
                "Contact the admin to get access.",
                reply_to=msg_id,
            )
        return

    # ── /whoami ─────────────────────────────────────────────────────────────
    if text.startswith("/whoami"):
        if not forge_user:
            send_msg(
                chat_id,
                "Not linked yet. Use /login <username> to link your account.",
                reply_to=msg_id,
            )
            return
        send_msg(
            chat_id,
            f"<b>Name:</b> {_escape(forge_user['name'])}\n"
            f"<b>Role:</b> {_escape(forge_user['role'])}\n"
            f"<b>Access:</b> {_escape(forge_user['access_level'])}\n"
            f"<b>Machine:</b> {_escape(forge_user['machine'])}\n"
            f"<b>Status:</b> <code>{_escape(forge_user['status'])}</code>",
            reply_to=msg_id,
        )
        return

    # ── All remaining commands require authentication ───────────────────────
    if not forge_user:
        send_msg(
            chat_id,
            "Please link your account first: /login <username>",
            reply_to=msg_id,
        )
        return

    # ── /status ─────────────────────────────────────────────────────────────
    if text.startswith("/status"):
        send_typing(chat_id)
        result = call_terminal_api(
            "git -C ~/mon-ipad log --oneline -3 && "
            "echo '---' && "
            "ps aux | grep -E '(nomos42|forge|terminal_api)' | grep -v grep | awk '{print $1,$11,$12}' && "
            "echo '---' && "
            "cat ~/mon-ipad/data/agent-health.json 2>/dev/null | python3 -c \""
            "import json,sys; d=json.load(sys.stdin); "
            "print('Brier ATR:', d.get('best_brier','?'), '| Updated:', d.get('updated','?'))"
            "\" 2>/dev/null || echo '[health file not found]'"
        )
        out = result.get("output", "[no output]").strip()
        send_msg(
            chat_id,
            f"<b>System Status</b> — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n"
            f"<pre>{_escape(out[:2500])}</pre>",
            reply_to=msg_id,
        )
        return

    # ── /spaces ─────────────────────────────────────────────────────────────
    if text.startswith("/spaces"):
        send_typing(chat_id)
        result = call_terminal_api(
            "cat ~/mon-ipad/data/agent-health.json 2>/dev/null | "
            "python3 -c \""
            "import json,sys; d=json.load(sys.stdin); "
            "[print(f's={s}: {v}') for s,v in d.get('spaces',{}).items()]"
            "\" 2>/dev/null || echo '[no spaces data]'"
        )
        out = result.get("output", "[no output]").strip()
        send_msg(
            chat_id,
            f"<b>HF Spaces Status</b>\n<pre>{_escape(out[:2500])}</pre>",
            reply_to=msg_id,
        )
        return

    # ── /picks ──────────────────────────────────────────────────────────────
    if text.startswith("/picks"):
        send_typing(chat_id)
        result = call_terminal_api(
            "python3 -c \""
            "import json; d=json.load(open('/home/termius/mon-ipad/data/nba-agent/latest-eval.json')); "
            "print('Date:', d.get('date','?')); "
            "picks = d.get('picks', []); "
            "print(f'{len(picks)} picks'); "
            "[print(f'  {p.get(\\\"home\\\",\\\"?\\\")!s} vs {p.get(\\\"away\\\",\\\"?\\\")!s}: {p.get(\\\"pick\\\",\\\"?\\\")!s} ({p.get(\\\"edge\\\",0):.1%} edge)') for p in picks[:5]]"
            "\" 2>/dev/null || echo '[no picks data]'"
        )
        out = result.get("output", "[no output]").strip()
        send_msg(
            chat_id,
            f"<b>Latest NBA Picks</b>\n<pre>{_escape(out[:2500])}</pre>",
            reply_to=msg_id,
        )
        return

    # ── /ask ────────────────────────────────────────────────────────────────
    if text.startswith("/ask "):
        question = text[5:].strip()
        if not question:
            send_msg(chat_id, "Usage: /ask <question>", reply_to=msg_id)
            return
        send_typing(chat_id)
        out = run_claude(question)
        send_msg(
            chat_id,
            f"<b>Claude:</b>\n<pre>{_escape(out[:2500])}</pre>",
            reply_to=msg_id,
        )
        return

    # ── /run ────────────────────────────────────────────────────────────────
    if text.startswith("/run "):
        cmd = text[5:].strip()
        if not cmd:
            send_msg(chat_id, "Usage: /run <command>", reply_to=msg_id)
            return

        access = forge_user.get("access_level", "operator")
        token = forge_user.get("terminal_token", "")

        # Operators get restricted command set
        if access == "operator" and is_operator_blocked(cmd):
            send_msg(
                chat_id,
                f"Command blocked for operator-level access: <code>{_escape(cmd[:100])}</code>\n"
                "Restricted: kill, rm -rf, git push, reboot, sudo.",
                reply_to=msg_id,
            )
            log.warning(f"Operator {forge_user['name']} blocked from: {cmd[:80]}")
            return

        send_typing(chat_id)
        result = call_terminal_api(cmd, token=token)
        out = result.get("output", "[no output]").strip()
        exit_code = result.get("exit_code", -1)

        icon = "OK" if exit_code == 0 else f"exit={exit_code}"
        send_msg(
            chat_id,
            f"<b>[{icon}]</b> <code>{_escape(cmd[:80])}</code>\n"
            f"<pre>{_escape(out[:2500])}</pre>",
            reply_to=msg_id,
        )
        log.info(f"[/run] user={forge_user['name']} cmd={cmd[:60]} exit={exit_code}")
        return

    # ── Unknown command ─────────────────────────────────────────────────────
    if text.startswith("/"):
        send_msg(chat_id, f"Unknown command.\n\n{HELP_TEXT}", reply_to=msg_id)
        return

    # ── Free-form text: forward to Claude ───────────────────────────────────
    send_typing(chat_id)
    out = run_claude(text)
    send_msg(
        chat_id,
        f"<pre>{_escape(out[:2500])}</pre>",
        reply_to=msg_id,
    )


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        log.error("FORGE_BOT_TOKEN not set — export FORGE_BOT_TOKEN=<token>")
        sys.exit(1)

    me = tg_request("getMe")
    if me.get("ok"):
        bot_name = me["result"].get("username", "?")
        log.info(f"Started as @{bot_name}")
        log.info(f"Users file: {USERS_FILE}")
        log.info(f"Terminal API: {TERMINAL_API_URL}")
    else:
        log.error("Failed to connect to Telegram API")
        sys.exit(1)

    # Pre-load users to validate config at startup
    users_data = load_users_file()
    user_count = len(users_data.get("users", {}))
    log.info(f"Loaded {user_count} forge user(s): {list(users_data.get('users', {}).keys())}")

    offset = 0
    while running:
        updates = tg_request("getUpdates", {
            "offset": offset,
            "timeout": POLL_TIMEOUT,
            "allowed_updates": ["message"],
        })

        if not updates.get("ok"):
            time.sleep(5)
            continue

        for update in updates.get("result", []):
            offset = update["update_id"] + 1
            msg = update.get("message")
            if not msg:
                continue

            chat_id = msg["chat"]["id"]
            user_id = msg.get("from", {}).get("id", 0)
            first_name = msg.get("from", {}).get("first_name", "?")
            text = msg.get("text", "")

            if not text:
                continue

            # Rate limiting (allow /start and /help without rate limit)
            if not text.startswith(("/start", "/help", "/login")):
                if is_rate_limited(user_id):
                    log.info(f"Rate limited: {user_id} ({first_name})")
                    send_msg(
                        chat_id,
                        f"Slow down — max {RATE_LIMIT} commands per minute.",
                        reply_to=msg["message_id"],
                    )
                    continue

            log.info(f"[{user_id}|{first_name}] {text[:80]}")
            try:
                handle_command(chat_id, msg["message_id"], user_id, text)
            except Exception as e:
                log.error(f"Handler error: {e}", exc_info=True)
                send_msg(chat_id, f"[error] {_escape(str(e))}")


if __name__ == "__main__":
    main()
