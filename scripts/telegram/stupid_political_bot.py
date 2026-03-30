#!/usr/bin/env python3
"""
@StupidPoliticalBot — SaaS bot for Political Alpha subscribers.
Tier-gated: free/scout/edge/whale. Serves political signals, insider trades,
polymarket data, portfolio recommendations.

Env: STUPID_POLITICAL_BOT_TOKEN
Users: data/forge-users/political-users.json
"""

import json
import logging
import os
import signal
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [POLITICAL] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("/tmp/political-bot.log")],
    datefmt="%H:%M:%S",
)
log = logging.getLogger("political")

TOKEN = os.environ.get("STUPID_POLITICAL_BOT_TOKEN", "")
POLITICAL_DIR = Path.home() / "nomos-political-alpha" / "data"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
USERS_FILE = DATA_DIR / "forge-users" / "political-users.json"

API = f"https://api.telegram.org/bot{TOKEN}"
POLL_TIMEOUT = 30
MAX_MSG = 4000
RATE_LIMIT = 10
RATE_WINDOW = 60
_rate: dict = defaultdict(list)

running = True
signal.signal(signal.SIGINT, lambda *_: globals().update(running=False))
signal.signal(signal.SIGTERM, lambda *_: globals().update(running=False))

# ── Tiers ────────────────────────────────────────────────────

TIERS = {
    "free":  {"name": "Free",           "signals": 2, "insider": False, "polymarket": False, "portfolio": False, "donors": False},
    "scout": {"name": "Scout ($19/mo)",  "signals": 5, "insider": False, "polymarket": True,  "portfolio": False, "donors": False},
    "edge":  {"name": "Edge ($49/mo)",   "signals": 99, "insider": True,  "polymarket": True,  "portfolio": True,  "donors": True},
    "whale": {"name": "Whale ($149/mo)", "signals": 99, "insider": True,  "polymarket": True,  "portfolio": True,  "donors": True},
}

# ── Users ────────────────────────────────────────────────────

def load_users() -> dict:
    try:
        return json.loads(USERS_FILE.read_text())
    except Exception:
        return {}

def save_users(users: dict):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))

def find_user_by_tid(tid: str):
    for uid, u in load_users().items():
        if str(u.get("telegram_id")) == tid:
            return uid, u
    return None, None

def find_user_by_code(code: str):
    for uid, u in load_users().items():
        if u.get("login_code") == code:
            return uid, u
    return None, None

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def load_json_lines(path: Path, n: int = 10) -> list:
    try:
        lines = path.read_text().strip().split("\n")
        return [json.loads(l) for l in lines[-n:]]
    except Exception:
        return []

# ── Telegram ─────────────────────────────────────────────────

def tg(method: str, data: dict = None) -> dict:
    url = f"{API}/{method}"
    if data:
        req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as r:
            return json.loads(r.read())
    except Exception as e:
        log.error(f"TG error: {e}")
        return {"ok": False}

def send(chat_id, text, reply_to=None):
    for chunk in [text[i:i+MAX_MSG] for i in range(0, len(text), MAX_MSG)]:
        d = {"chat_id": chat_id, "text": chunk}
        if reply_to:
            d["reply_to_message_id"] = reply_to
        tg("sendMessage", d)

def typing(chat_id):
    tg("sendChatAction", {"chat_id": chat_id, "action": "typing"})

def rate_ok(uid: int) -> bool:
    now = time.time()
    _rate[uid] = [t for t in _rate[uid] if now - t < RATE_WINDOW]
    if len(_rate[uid]) >= RATE_LIMIT:
        return False
    _rate[uid].append(now)
    return True

# ── Commands ─────────────────────────────────────────────────

def cmd_start(chat_id, mid):
    send(chat_id,
        "Welcome to Stupid Political — Political Alpha AI\n"
        "=================================================\n\n"
        "Login with your code:\n"
        "/login YOUR_CODE\n\n"
        "No code yet? Visit stupidpolitical.vercel.app",
        mid)

def cmd_login(chat_id, mid, tid, username, args):
    if not args:
        send(chat_id, "Usage: /login YOUR_CODE", mid)
        return
    code = args[0].strip()
    uid, user = find_user_by_code(code)
    if not uid:
        send(chat_id, "Invalid code. Check your email or contact support.", mid)
        return
    users = load_users()
    users[uid]["telegram_id"] = str(tid)
    users[uid]["telegram_username"] = username
    users[uid]["activated_at"] = datetime.now(timezone.utc).isoformat()
    save_users(users)
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"])
    send(chat_id,
        f"Welcome {user.get('name', username)}!\n"
        f"Plan: {tc['name']}\n"
        f"=================================================\n\n"
        f"/signals - Latest political signals\n"
        + (f"/insider - Insider trades\n" if tc["insider"] else "")
        + (f"/polymarket - Prediction markets\n" if tc["polymarket"] else "")
        + (f"/portfolio - Portfolio recommendations\n" if tc["portfolio"] else "")
        + (f"/donors - CEO/PAC donations\n" if tc["donors"] else "")
        + f"/plan - Your subscription\n"
        f"/help - All commands",
        mid)
    log.info(f"LOGIN: {username} -> {uid} tier={user.get('tier')}")

def cmd_signals(chat_id, mid, user):
    tier = user.get("tier", "free")
    tc = TIERS.get(tier, TIERS["free"])
    signals_dir = POLITICAL_DIR / "signals"
    if not signals_dir.exists():
        send(chat_id, "No signals available. Check back later.", mid)
        return
    # Load latest signal files
    files = sorted(signals_dir.glob("*.json"), reverse=True)[:5]
    lines = ["Political Signals", "=" * 35]
    count = 0
    for f in files:
        if count >= tc["signals"]:
            break
        try:
            data = json.loads(f.read_text())
            if isinstance(data, list):
                for sig in data[:3]:
                    if count >= tc["signals"]:
                        break
                    title = sig.get("title", sig.get("name", f.stem))
                    score = sig.get("score", sig.get("impact", "?"))
                    lines.append(f"\n  {title}")
                    lines.append(f"  Impact: {score}")
                    count += 1
            elif isinstance(data, dict):
                title = data.get("title", f.stem)
                lines.append(f"\n  {title}")
                count += 1
        except Exception:
            continue
    if count == 0:
        lines.append("\nNo recent signals found.")
    remaining = max(0, len(files) * 3 - tc["signals"])
    if remaining > 0 and tier != "whale":
        lines.append(f"\n+{remaining} more signals - upgrade your plan")
    send(chat_id, "\n".join(lines), mid)

def cmd_insider(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"])
    if not tc["insider"]:
        send(chat_id, "Insider trades available on Edge ($49/mo) and above.\nUpgrade at stupidpolitical.vercel.app", mid)
        return
    insider_dir = POLITICAL_DIR / "insider"
    if not insider_dir.exists():
        send(chat_id, "No insider data available.", mid)
        return
    files = sorted(insider_dir.glob("*.json"), reverse=True)[:1]
    lines = ["Latest Insider Trades", "=" * 35]
    for f in files:
        try:
            data = json.loads(f.read_text())
            trades = data if isinstance(data, list) else data.get("trades", [])
            for t in trades[:8]:
                name = t.get("name", t.get("politician", "?"))
                ticker = t.get("ticker", t.get("asset", "?"))
                action = t.get("type", t.get("action", "?"))
                amount = t.get("amount", "?")
                lines.append(f"  {name}: {action} {ticker} ({amount})")
        except Exception:
            lines.append(f"  Error reading {f.name}")
    send(chat_id, "\n".join(lines), mid)

def cmd_polymarket(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"])
    if not tc["polymarket"]:
        send(chat_id, "Polymarket data available on Scout ($19/mo) and above.\nUpgrade at stupidpolitical.vercel.app", mid)
        return
    poly_dir = POLITICAL_DIR / "polymarket"
    if not poly_dir.exists():
        send(chat_id, "No Polymarket data available.", mid)
        return
    files = sorted(poly_dir.glob("*.json"), reverse=True)[:1]
    lines = ["Polymarket — Prediction Markets", "=" * 35]
    for f in files:
        try:
            data = json.loads(f.read_text())
            markets = data if isinstance(data, list) else data.get("markets", [])
            for m in markets[:10]:
                q = m.get("question", m.get("title", "?"))
                prob = m.get("probability", m.get("yes_price", "?"))
                if isinstance(prob, (int, float)):
                    prob = f"{prob:.0%}"
                lines.append(f"  {q}: {prob}")
        except Exception:
            lines.append(f"  Error reading {f.name}")
    send(chat_id, "\n".join(lines), mid)

def cmd_portfolio(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"])
    if not tc["portfolio"]:
        send(chat_id, "Portfolio available on Edge ($49/mo) and above.\nUpgrade at stupidpolitical.vercel.app", mid)
        return
    send(chat_id, "Portfolio recommendations coming soon.\nFollow signals and insider trades for now.", mid)

def cmd_donors(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"])
    if not tc["donors"]:
        send(chat_id, "Donor data available on Edge ($49/mo) and above.\nUpgrade at stupidpolitical.vercel.app", mid)
        return
    donors_dir = POLITICAL_DIR / "donors"
    if not donors_dir.exists():
        send(chat_id, "No donor data available.", mid)
        return
    files = sorted(donors_dir.glob("*.json"), reverse=True)[:1]
    lines = ["CEO & PAC Donations", "=" * 35]
    for f in files:
        try:
            data = json.loads(f.read_text())
            donors = data if isinstance(data, list) else data.get("donors", [])
            for d in donors[:10]:
                name = d.get("name", d.get("donor", "?"))
                amount = d.get("amount", "?")
                recipient = d.get("recipient", d.get("party", "?"))
                lines.append(f"  {name} -> {recipient}: ${amount}")
        except Exception:
            lines.append(f"  Error reading {f.name}")
    send(chat_id, "\n".join(lines), mid)

def cmd_plan(chat_id, mid, user):
    tier = user.get("tier", "free")
    tc = TIERS.get(tier, TIERS["free"])
    sig_str = str(tc["signals"]) if tc["signals"] < 99 else "Unlimited"
    yn = lambda v: "Yes" if v else "No"
    lines = [
        f"Your Plan: {tc['name']}", "=" * 35,
        f"Signals/day: {sig_str}",
        f"Insider trades: {yn(tc['insider'])}",
        f"Polymarket: {yn(tc['polymarket'])}",
        f"Portfolio: {yn(tc['portfolio'])}",
        f"Donor tracking: {yn(tc['donors'])}",
    ]
    if tier != "whale":
        lines.append("\nUpgrade at stupidpolitical.vercel.app")
    send(chat_id, "\n".join(lines), mid)

def cmd_help(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"]) if user else TIERS["free"]
    lines = [
        "Stupid Political Commands", "=" * 35,
        "/signals - Political signals",
    ]
    if tc["polymarket"]:
        lines.append("/polymarket - Prediction markets")
    if tc["insider"]:
        lines.append("/insider - Insider trades")
    if tc["portfolio"]:
        lines.append("/portfolio - Portfolio recs")
    if tc["donors"]:
        lines.append("/donors - CEO/PAC donations")
    lines += ["", "/plan - Your subscription", "/login CODE - Activate account", "/help - This message", "", "Support: @Nomos42"]
    send(chat_id, "\n".join(lines), mid)

# ── Router ───────────────────────────────────────────────────

def handle(chat_id, mid, tid, username, text):
    text = text.strip()
    if text.startswith("/start"):
        cmd_start(chat_id, mid); return
    if text.startswith("/login"):
        cmd_login(chat_id, mid, tid, username, text.split()[1:]); return
    if text.startswith("/help"):
        _, user = find_user_by_tid(str(tid))
        cmd_help(chat_id, mid, user); return

    _, user = find_user_by_tid(str(tid))
    if not user:
        send(chat_id, "Please /login first with your code.", mid); return

    if text.startswith("/signals"):
        cmd_signals(chat_id, mid, user)
    elif text.startswith("/insider"):
        cmd_insider(chat_id, mid, user)
    elif text.startswith("/polymarket"):
        cmd_polymarket(chat_id, mid, user)
    elif text.startswith("/portfolio"):
        cmd_portfolio(chat_id, mid, user)
    elif text.startswith("/donors"):
        cmd_donors(chat_id, mid, user)
    elif text.startswith("/plan"):
        cmd_plan(chat_id, mid, user)
    elif text.startswith("/"):
        send(chat_id, "Unknown command. Try /help", mid)
    else:
        send(chat_id, "Use /signals for latest political signals or /help for commands.", mid)

# ── Main ─────────────────────────────────────────────────────

def main():
    if not TOKEN:
        log.error("Set STUPID_POLITICAL_BOT_TOKEN"); sys.exit(1)
    me = tg("getMe")
    if me.get("ok"):
        log.info(f"Started @{me['result'].get('username', '?')}")
    else:
        log.error("Cannot connect to Telegram API"); sys.exit(1)
    users = load_users()
    log.info(f"Users: {len(users)} ({', '.join(users.keys()) or 'none'})")

    offset = 0
    while running:
        updates = tg("getUpdates", {"offset": offset, "timeout": POLL_TIMEOUT, "allowed_updates": ["message"]})
        if not updates.get("ok"):
            time.sleep(5); continue
        for upd in updates.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message")
            if not msg or not msg.get("text"):
                continue
            chat_id = msg["chat"]["id"]
            tid = msg["from"]["id"]
            username = msg["from"].get("username") or msg["from"].get("first_name", "?")
            text = msg["text"]
            if not text.startswith(("/start", "/help", "/login")) and not rate_ok(tid):
                send(chat_id, "Slow down - max 10 commands/minute.", msg["message_id"]); continue
            log.info(f"[{tid}|{username}] {text[:80]}")
            try:
                handle(chat_id, msg["message_id"], tid, username, text)
            except Exception as e:
                log.error(f"Error: {e}", exc_info=True)
                send(chat_id, f"Error: {e}")

if __name__ == "__main__":
    main()
