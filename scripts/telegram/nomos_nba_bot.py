#!/usr/bin/env python3
"""
@NomosNBABot — SaaS bot for NBA Quant subscribers.
Tier-gated: free/scout/edge/whale. Serves NBA picks, bankroll, models, props.

Env: BOT_TOKEN_NBA
Users: data/forge-users/nba-users.json
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
    format="%(asctime)s [NBA] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("/tmp/nba-bot.log")],
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nba")

TOKEN = os.environ.get("BOT_TOKEN_NBA", "")
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "nba-agent"
USERS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "forge-users" / "nba-users.json"

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
    "free":  {"name": "Free",           "picks": 1,  "kelly": False, "confidence": False, "props": False, "bankroll": False, "models": False, "totals": False},
    "scout": {"name": "Scout ($19/mo)",  "picks": 3,  "kelly": False, "confidence": True,  "props": False, "bankroll": False, "models": False, "totals": False},
    "edge":  {"name": "Edge ($49/mo)",   "picks": 99, "kelly": True,  "confidence": True,  "props": False, "bankroll": True,  "models": True,  "totals": True},
    "whale": {"name": "Whale ($149/mo)", "picks": 99, "kelly": True,  "confidence": True,  "props": True,  "bankroll": True,  "models": True,  "totals": True},
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

# ── Pick formatting ──────────────────────────────────────────

def format_pick(g: dict, tc: dict, num: int) -> str:
    home = g.get("home_name", g.get("home", "?"))
    away = g.get("away_name", g.get("away", "?"))
    side = g.get("bet_side", "?")
    prob = g.get("home_win_prob", 0)
    edge = g.get("edge", 0)
    pick_team = home if side == "HOME" else away
    pick_prob = prob if side == "HOME" else 1 - prob

    lines = [f"{num}. {away} @ {home}", f"   PICK: {pick_team}"]
    if tc["confidence"]:
        lines.append(f"   Confidence: {g.get('confidence', '?')} ({pick_prob:.0%}) | Edge: {edge:.1%}")
    if tc["kelly"]:
        kelly = g.get("kelly_stake", 0)
        odds = g.get("best_odds", {})
        lines.append(f"   Kelly: {kelly:.0%} | Odds: {odds.get('odds', '?')} ({odds.get('book', '?')})")
    if tc["props"] and g.get("player_props"):
        for p in g["player_props"][:2]:
            lines.append(f"   Prop: {p.get('player','?')} {p.get('market','?')} {p.get('pick','?')}")
    total = g.get("total", {})
    if tc["totals"] and total:
        lines.append(f"   Total: {total.get('pick', '?')} {total.get('line', '?')} (model: {total.get('model_total', '?')})")
    return "\n".join(lines)

# ── Commands ─────────────────────────────────────────────────

def cmd_start(chat_id, mid):
    send(chat_id,
        "Welcome to NomosQuant42 - NBA AI Predictions\n"
        "=============================================\n\n"
        "Login with your code:\n"
        "/login YOUR_CODE\n\n"
        "No code yet? Visit nomosquant42.vercel.app",
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
    picks_limit = tc["picks"] if tc["picks"] < 99 else "All"
    send(chat_id,
        f"Welcome {user.get('name', username)}!\n"
        f"Plan: {tc['name']}\n"
        f"=============================================\n\n"
        f"/picks - Today's NBA picks ({picks_limit}/day)\n"
        + (f"/bankroll - Bankroll tracker\n" if tc["bankroll"] else "")
        + (f"/models - AI model stats\n" if tc["models"] else "")
        + f"/record - Season record\n"
        f"/plan - Your subscription\n"
        f"/help - All commands",
        mid)
    log.info(f"LOGIN: {username} -> {uid} tier={user.get('tier')}")

def cmd_picks(chat_id, mid, user):
    tier = user.get("tier", "free")
    tc = TIERS.get(tier, TIERS["free"])
    picks = load_json(DATA_DIR / "latest-picks.json")
    games = picks.get("games", [])
    date = picks.get("date", "?")
    if not games:
        send(chat_id, "No picks available today. Check back later.", mid)
        return
    games = sorted(games, key=lambda g: g.get("edge", 0), reverse=True)
    shown = games[:tc["picks"]]
    header = f"NBA Picks - {date}\n{'=' * 35}\n"
    body = "\n\n".join(format_pick(g, tc, i) for i, g in enumerate(shown, 1))
    footer = ""
    remaining = len(games) - len(shown)
    if remaining > 0:
        footer = f"\n\n+{remaining} more picks - upgrade at nomosquant42.vercel.app"
    send(chat_id, header + "\n" + body + footer, mid)
    log.info(f"PICKS: {user.get('name')} tier={tier} shown={len(shown)}")

def cmd_bankroll(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"])
    if not tc["bankroll"]:
        send(chat_id, "Bankroll tracking on Edge ($49/mo)+.\nUpgrade at nomosquant42.vercel.app", mid)
        return
    br = load_json(DATA_DIR / "bankroll-state.json")
    send(chat_id,
        f"Bankroll Status\n{'=' * 35}\n"
        f"Balance: ${br.get('balance', 0):.2f}\n"
        f"ROI: {br.get('roi_pct', 0):.2f}%\n"
        f"Record: {br.get('wins', 0)}W-{br.get('losses', 0)}L\n"
        f"Win rate: {br.get('win_rate_pct', 0):.1f}%\n"
        f"Sharpe: {br.get('sharpe_ratio', 0):.2f}\n"
        f"Peak: ${br.get('peak_balance', 0):.2f}\n"
        f"Wagered: ${br.get('total_wagered', 0):.2f}", mid)

def cmd_models(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"])
    if not tc["models"]:
        send(chat_id, "Model stats on Edge ($49/mo)+.\nUpgrade at nomosquant42.vercel.app", mid)
        return
    s = load_json(DATA_DIR / "quant-summary.json")
    models = s.get("models", {})
    lines = [f"AI Models\n{'=' * 35}"]
    for name, info in sorted(models.items(), key=lambda x: x[1].get("brier", 1)):
        lines.append(f"  {name}: Brier {info.get('brier', '?')} [{info.get('status', '?')}]")
    lines.append(f"\nBest: {s.get('best_brier', '?')} | Features: {s.get('features', '?')}")
    lines.append(f"Generations: {s.get('evolution', {}).get('generations', '?')}")
    send(chat_id, "\n".join(lines), mid)

def cmd_record(chat_id, mid, user):
    br = load_json(DATA_DIR / "bankroll-state.json")
    s = load_json(DATA_DIR / "quant-summary.json")
    send(chat_id,
        f"Season Record\n{'=' * 35}\n"
        f"Record: {br.get('wins', 0)}W-{br.get('losses', 0)}L\n"
        f"ROI: {br.get('roi_pct', 0):.2f}%\n"
        f"Brier Score: {s.get('best_brier', '?')}\n"
        f"Since: {br.get('season_start', '?')}\n"
        f"Total bets: {br.get('total_bets', 0)}", mid)

def cmd_plan(chat_id, mid, user):
    tier = user.get("tier", "free")
    tc = TIERS.get(tier, TIERS["free"])
    picks_str = str(tc["picks"]) if tc["picks"] < 99 else "Unlimited"
    yn = lambda v: "Yes" if v else "No"
    lines = [
        f"Your Plan: {tc['name']}", "=" * 35,
        f"Picks/day: {picks_str}",
        f"Confidence: {yn(tc['confidence'])}",
        f"Kelly sizing: {yn(tc['kelly'])}",
        f"Player props: {yn(tc['props'])}",
        f"Totals: {yn(tc['totals'])}",
        f"Bankroll: {yn(tc['bankroll'])}",
        f"Models: {yn(tc['models'])}",
    ]
    if tier != "whale":
        lines.append("\nUpgrade at nomosquant42.vercel.app")
    send(chat_id, "\n".join(lines), mid)

def cmd_help(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"]) if user else TIERS["free"]
    lines = ["NomosQuant42 Commands", "=" * 35, "/picks - Today's NBA picks", "/record - Season record"]
    if tc["bankroll"]:
        lines.append("/bankroll - Bankroll tracker")
    if tc["models"]:
        lines.append("/models - AI model stats")
    lines += ["", "/plan - Your subscription", "/login CODE - Activate", "/help - This message", "", "Support: @Nomos42"]
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

    if text.startswith("/picks"):
        cmd_picks(chat_id, mid, user)
    elif text.startswith("/bankroll"):
        cmd_bankroll(chat_id, mid, user)
    elif text.startswith("/models"):
        cmd_models(chat_id, mid, user)
    elif text.startswith("/record"):
        cmd_record(chat_id, mid, user)
    elif text.startswith("/plan"):
        cmd_plan(chat_id, mid, user)
    elif text.startswith("/"):
        send(chat_id, "Unknown command. Try /help", mid)
    else:
        send(chat_id, "Use /picks for today's NBA picks or /help for commands.", mid)

# ── Main ─────────────────────────────────────────────────────

def main():
    if not TOKEN:
        log.error("Set BOT_TOKEN_NBA"); sys.exit(1)
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
