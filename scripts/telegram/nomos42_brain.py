#!/usr/bin/env python3
"""
Nomos42 Brain Bot — Claude Code CLI via Telegram
=================================================
Identity: The Brain. Research, analysis, codebase questions.
Invokes `claude` CLI for every message, posts results to channel.

Env vars:
  TELEGRAM_BOT_TOKEN        — Nomos42 bot token
  ADMIN_TELEGRAM_ID         — only responds to this user
  TELEGRAM_CHANNEL_ID       — channel to broadcast results (e.g. @Nomos42)
  CLAUDE_WORKDIR            — working directory for claude CLI (default: ~/mon-ipad)
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BRAIN] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("brain")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "6582544948"))
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@Nomos42")
WORKDIR = os.environ.get("CLAUDE_WORKDIR", os.path.expanduser("~/mon-ipad"))
MAX_CLAUDE_TIMEOUT = 120  # seconds
MAX_MSG_LEN = 4000  # Telegram limit ~4096, leave margin
POLL_TIMEOUT = 30

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

running = True


def _signal_handler(sig, frame):
    global running
    log.info("Shutting down...")
    running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

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
    """Send message, splitting if too long."""
    chunks = [text[i:i + MAX_MSG_LEN] for i in range(0, len(text), MAX_MSG_LEN)]
    for chunk in chunks:
        data = {"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode}
        if reply_to:
            data["reply_to_message_id"] = reply_to
        result = tg_request("sendMessage", data)
        if not result.get("ok"):
            # Retry without parse_mode (in case of HTML errors)
            data["parse_mode"] = ""
            data["text"] = chunk
            tg_request("sendMessage", data)


def send_typing(chat_id):
    tg_request("sendChatAction", {"chat_id": chat_id, "action": "typing"})


# ---------------------------------------------------------------------------
# Claude Code CLI
# ---------------------------------------------------------------------------

def run_claude(prompt: str) -> str:
    """Run claude CLI with prompt, return text output."""
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "text",
        "--max-turns", "3",
    ]
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
# Command handlers
# ---------------------------------------------------------------------------

HELP_TEXT = """<b>Nomos42 Brain</b> — Claude Code CLI

<b>Commands:</b>
/status — System health snapshot
/brier — Current best Brier scores
/ask &lt;question&gt; — Ask Claude about the codebase
/run &lt;command&gt; — Run a shell command
/broadcast &lt;msg&gt; — Post to @Nomos42 channel

<b>Or just send any message</b> — it goes straight to Claude Code."""


def handle_command(chat_id: int, msg_id: int, text: str):
    text = text.strip()

    if text.startswith("/start") or text.startswith("/help"):
        send_msg(chat_id, HELP_TEXT, reply_to=msg_id)
        return

    if text.startswith("/status"):
        send_typing(chat_id)
        out = run_claude(
            "Give a brief status: git log -3, are HF spaces running (check scripts/keepalive-spaces.sh last run), "
            "current best Brier from memory. Keep it under 10 lines."
        )
        send_msg(chat_id, f"<pre>{_escape(out)}</pre>", reply_to=msg_id)
        return

    if text.startswith("/brier"):
        send_typing(chat_id)
        out = run_claude(
            "What are the current best Brier scores across all 6 HF Spaces? "
            "Check memory and data/health-status.json. Format as a table."
        )
        send_msg(chat_id, f"<pre>{_escape(out)}</pre>", reply_to=msg_id)
        return

    if text.startswith("/ask "):
        question = text[5:].strip()
        if not question:
            send_msg(chat_id, "Usage: /ask <question>", reply_to=msg_id)
            return
        send_typing(chat_id)
        out = run_claude(question)
        send_msg(chat_id, f"<pre>{_escape(out)}</pre>", reply_to=msg_id)
        return

    if text.startswith("/run "):
        cmd = text[5:].strip()
        if not cmd:
            send_msg(chat_id, "Usage: /run <command>", reply_to=msg_id)
            return
        send_typing(chat_id)
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=WORKDIR,
            )
            out = (result.stdout + result.stderr).strip()[:3000] or "[no output]"
        except subprocess.TimeoutExpired:
            out = "[timeout]"
        send_msg(chat_id, f"<pre>{_escape(out)}</pre>", reply_to=msg_id)
        return

    if text.startswith("/broadcast "):
        msg = text[11:].strip()
        if not msg:
            send_msg(chat_id, "Usage: /broadcast <message>", reply_to=msg_id)
            return
        send_msg(CHANNEL_ID, f"<b>[Brain]</b> {msg}")
        send_msg(chat_id, "Sent to channel.", reply_to=msg_id)
        return

    # Default: send everything to Claude Code
    if text.startswith("/"):
        send_msg(chat_id, f"Unknown command. {HELP_TEXT}", reply_to=msg_id)
        return

    send_typing(chat_id)
    out = run_claude(text)
    send_msg(chat_id, f"<pre>{_escape(out)}</pre>", reply_to=msg_id)

    # Also post significant results to channel (if output is substantial)
    if len(out) > 100 and not out.startswith("["):
        summary = out[:300] + ("..." if len(out) > 300 else "")
        send_msg(CHANNEL_ID, f"<b>[Brain]</b> Q: {_escape(text[:100])}\n\n<pre>{_escape(summary)}</pre>")


def _escape(text: str) -> str:
    """Escape HTML entities for Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    me = tg_request("getMe")
    if me.get("ok"):
        bot_name = me["result"].get("username", "?")
        log.info(f"Started as @{bot_name} — admin={ADMIN_ID}")
    else:
        log.error("Failed to connect to Telegram API")
        sys.exit(1)

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
            text = msg.get("text", "")

            # Admin only
            if user_id != ADMIN_ID:
                log.info(f"Ignored message from {user_id}")
                continue

            if not text:
                continue

            log.info(f"[{user_id}] {text[:80]}")
            try:
                handle_command(chat_id, msg["message_id"], text)
            except Exception as e:
                log.error(f"Handler error: {e}")
                send_msg(chat_id, f"[error] {e}")


if __name__ == "__main__":
    main()
