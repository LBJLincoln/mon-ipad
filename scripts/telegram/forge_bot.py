#!/usr/bin/env python3
"""
@Forge42Bot — SaaS customer bot for Nomos42 NBA subscribers.
Commands are gated by subscription tier (free/scout/edge/whale).

Users authenticate with a login code, get tier-adapted picks & data.

Env: BOT_TOKEN_FORGE
Users: data/forge-users/users.json
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FORGE] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("/tmp/forge-bot.log")],
    datefmt="%H:%M:%S",
)
log = logging.getLogger("forge")

TOKEN = os.environ.get("BOT_TOKEN_FORGE", "")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
USERS_FILE = DATA_DIR / "forge-users" / "users.json"
PICKS_FILE = DATA_DIR / "nba-agent" / "latest-picks.json"
BANKROLL_FILE = DATA_DIR / "nba-agent" / "bankroll-state.json"
SUMMARY_FILE = DATA_DIR / "nba-agent" / "quant-summary.json"
FORGE_SCRIPTS = REPO_ROOT / "scripts" / "forge"
FORGE_USERS = REPO_ROOT / "forge-users"

API = f"https://api.telegram.org/bot{TOKEN}"
POLL_TIMEOUT = 30
MAX_MSG = 4000
RATE_WINDOW = 60
RATE_LIMIT = 10
_rate: dict = defaultdict(list)

running = True
signal.signal(signal.SIGINT, lambda *_: globals().update(running=False))
signal.signal(signal.SIGTERM, lambda *_: globals().update(running=False))

# ── Tiers ────────────────────────────────────────────────────

TIERS = {
    "free":  {"name": "Free",           "picks": 1,  "kelly": False, "confidence": False, "props": False, "bankroll": False, "models": False},
    "scout": {"name": "Scout ($19/mo)",  "picks": 3,  "kelly": False, "confidence": True,  "props": False, "bankroll": False, "models": False},
    "edge":  {"name": "Edge ($49/mo)",   "picks": 99, "kelly": True,  "confidence": True,  "props": False, "bankroll": True,  "models": True},
    "whale": {"name": "Whale ($149/mo)", "picks": 99, "kelly": True,  "confidence": True,  "props": True,  "bankroll": True,  "models": True},
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

def find_user_by_tid(tid: str) -> tuple[str | None, dict | None]:
    for uid, u in load_users().items():
        if str(u.get("telegram_id")) == tid:
            return uid, u
    return None, None

def find_user_by_code(code: str) -> tuple[str | None, dict | None]:
    for uid, u in load_users().items():
        if u.get("login_code") == code:
            return uid, u
    return None, None

# ── Data ─────────────────────────────────────────────────────

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
        conf = g.get("confidence", "?")
        lines.append(f"   Confidence: {conf} ({pick_prob:.0%}) | Edge: {edge:.1%}")

    if tc["kelly"]:
        kelly = g.get("kelly_stake", 0)
        odds = g.get("best_odds", {})
        lines.append(f"   Kelly: {kelly:.0%} | Odds: {odds.get('odds', '?')} ({odds.get('book', '?')})")

    if tc["props"] and g.get("player_props"):
        for p in g["player_props"][:2]:
            lines.append(f"   Prop: {p.get('player','?')} {p.get('market','?')} {p.get('pick','?')}")

    return "\n".join(lines)

# ── Commands ─────────────────────────────────────────────────

def cmd_start(chat_id, mid):
    send(chat_id,
        "Welcome to Forge42\n"
        "==================================\n\n"
        "NBA Quant AI:\n"
        "  /login YOUR_CODE\n\n"
        "Forge Factory (idea -> product):\n"
        "  /idea YOUR_BUSINESS_IDEA\n"
        "  /build\n\n"
        "No code yet? Visit nomosdashboard.vercel.app",
        mid)

def cmd_login(chat_id, mid, tid, username, args):
    if not args:
        send(chat_id, "Usage: /login YOUR_CODE", mid)
        return
    code = args[0].strip()
    uid, user = find_user_by_code(code)
    if not uid:
        send(chat_id, "Invalid code. Check your email or contact @Nomos42.", mid)
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
        f"==================================\n\n"
        f"Your commands:\n"
        f"/picks - Today's NBA picks ({picks_limit}/day)\n"
        + (f"/bankroll - Bankroll tracker\n" if tc["bankroll"] else "")
        + (f"/models - AI model stats\n" if tc["models"] else "")
        + f"/plan - Your subscription\n"
        f"/help - All commands",
        mid)
    log.info(f"LOGIN: {username} (tid={tid}) -> {uid} tier={user.get('tier')}")

def cmd_picks(chat_id, mid, user):
    tier = user.get("tier", "free")
    tc = TIERS.get(tier, TIERS["free"])
    picks = load_json(PICKS_FILE)
    games = picks.get("games", [])
    date = picks.get("date", "?")

    if not games:
        send(chat_id, "No picks available today. Check back later.", mid)
        return

    games = sorted(games, key=lambda g: g.get("edge", 0), reverse=True)
    shown = games[:tc["picks"]]

    header = f"NBA Picks - {date}\n{'=' * 30}\n"
    body = "\n\n".join(format_pick(g, tc, i) for i, g in enumerate(shown, 1))
    footer = ""
    remaining = len(games) - len(shown)
    if remaining > 0:
        footer = f"\n\n+{remaining} more picks - upgrade your plan"

    send(chat_id, header + "\n" + body + footer, mid)
    log.info(f"PICKS: {user.get('name')} tier={tier} shown={len(shown)}")

def cmd_bankroll(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"])
    if not tc["bankroll"]:
        send(chat_id, "Bankroll tracking available on Edge ($49/mo) and above.\nUpgrade at nomosdashboard.vercel.app", mid)
        return
    br = load_json(BANKROLL_FILE)
    send(chat_id,
        f"Bankroll Status\n{'=' * 30}\n"
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
        send(chat_id, "Model stats available on Edge ($49/mo) and above.\nUpgrade at nomosdashboard.vercel.app", mid)
        return
    s = load_json(SUMMARY_FILE)
    models = s.get("models", {})
    lines = [f"AI Models\n{'=' * 30}"]
    for name, info in sorted(models.items(), key=lambda x: x[1].get("brier", 1)):
        lines.append(f"  {name}: Brier {info.get('brier', '?')} [{info.get('status', '?')}]")
    lines.append(f"\nBest: {s.get('best_brier', '?')} | Features: {s.get('features', '?')}")
    send(chat_id, "\n".join(lines), mid)

def cmd_plan(chat_id, mid, user):
    tier = user.get("tier", "free")
    tc = TIERS.get(tier, TIERS["free"])
    picks_str = str(tc["picks"]) if tc["picks"] < 99 else "Unlimited"
    yn = lambda v: "Yes" if v else "No"
    lines = [
        f"Your Plan: {tc['name']}", f"{'=' * 30}",
        f"Picks/day: {picks_str}",
        f"Confidence scores: {yn(tc['confidence'])}",
        f"Kelly sizing: {yn(tc['kelly'])}",
        f"Player props: {yn(tc['props'])}",
        f"Bankroll tracking: {yn(tc['bankroll'])}",
        f"Model stats: {yn(tc['models'])}",
    ]
    if tier != "whale":
        lines.append(f"\nUpgrade at nomosdashboard.vercel.app")
    send(chat_id, "\n".join(lines), mid)

def cmd_help(chat_id, mid, user):
    tc = TIERS.get(user.get("tier", "free"), TIERS["free"]) if user else TIERS["free"]
    lines = [
        "Forge42 Commands", "=" * 30,
        "",
        "-- Forge Factory --",
        "/idea TEXT - Analyze a business idea",
        "/build - Create product from latest brief",
        "",
        "-- NBA Quant AI --",
        "/picks - Today's NBA picks",
        "/plan - Your subscription",
    ]
    if tc["bankroll"]:
        lines.append("/bankroll - Bankroll tracker")
    if tc["models"]:
        lines.append("/models - AI model stats")
    lines += ["", "/login CODE - Activate account", "/help - This message", "", "Support: @Nomos42"]
    send(chat_id, "\n".join(lines), mid)

# ── Forge Factory Commands ──────────────────────────────────

def _get_forge_username(tid: str) -> str:
    """Get forge username from telegram id. Falls back to tid-based name."""
    uid, user = find_user_by_tid(tid)
    if uid:
        return uid
    return f"tg-{tid}"

def _find_latest_brief(user: str) -> Path | None:
    """Find the most recent strategy brief for a user."""
    briefs_dir = FORGE_USERS / user / "briefs"
    if not briefs_dir.exists():
        return None
    briefs = sorted(briefs_dir.glob("strategy-*.json"), reverse=True)
    return briefs[0] if briefs else None

def cmd_idea(chat_id, mid, tid, username, args):
    """Handle /idea command — runs F0 Strategy Definer."""
    idea_text = " ".join(args).strip() if args else ""
    if not idea_text:
        send(chat_id,
            "Usage: /idea YOUR_BUSINESS_IDEA\n\n"
            "Examples:\n"
            "  /idea AI tool for restaurant menu optimization\n"
            "  /idea Fitness app for busy parents\n"
            "  /idea Newsletter platform for indie hackers\n\n"
            "I'll analyze your idea and create a strategy brief.",
            mid)
        return

    forge_user = _get_forge_username(str(tid))
    typing(chat_id)

    send(chat_id,
        f"Analyzing your idea...\n"
        f"User: {forge_user}\n\n"
        f"\"{idea_text}\"\n\n"
        f"Running F0 Strategy Definer...",
        mid)

    # Run f0_strategy_definer.py
    f0_script = FORGE_SCRIPTS / "f0_strategy_definer.py"
    try:
        result = subprocess.run(
            [sys.executable, str(f0_script),
             "--user", forge_user,
             "--idea", idea_text,
             "--json"],
            capture_output=True, text=True, timeout=60,
            cwd=str(REPO_ROOT),
        )

        if result.returncode != 0:
            log.error(f"F0 error: {result.stderr}")
            send(chat_id, f"Strategy analysis failed:\n{result.stderr[:500]}", mid)
            return

        output = json.loads(result.stdout)
        brief = output.get("brief", {})

        # Format response
        lines = [
            f"STRATEGY BRIEF",
            f"{'=' * 30}",
            f"Product: {brief.get('product_name', '?')}",
            f"Type: {brief.get('product_type', '?')}",
            f"Pitch: {brief.get('one_liner', '?')}",
            f"",
            f"Pain: {brief.get('pain_statement', '?')}",
            f"Intensity: {brief.get('pain_intensity', '?')}/10",
            f"",
            f"Model: {brief.get('pricing_model', '?')}",
        ]
        pr = brief.get("pricing_range", {})
        lines.append(f"Price: ${pr.get('low', '?')}-${pr.get('high', '?')}/{pr.get('period', 'mo')}")
        lines.append(f"")
        lines.append(f"UVP: {brief.get('unique_value_prop', '?')}")
        lines.append(f"")
        mvp = brief.get("mvp_scope", {})
        lines.append(f"MVP: {mvp.get('core_feature', '?')}")
        lines.append(f"Score: {brief.get('confidence_score', '?')}/100")
        lines.append(f"")

        comps = brief.get("competitive_landscape", [])
        if comps:
            lines.append(f"Competitors ({len(comps)}):")
            for c in comps[:3]:
                lines.append(f"  - {c.get('name', '?')}")

        method = output.get("meta", {}).get("generation_method", "?")
        lines.append(f"")
        lines.append(f"[{method}]")
        lines.append(f"")
        lines.append(f"Next: /build to create implementation plan")

        send(chat_id, "\n".join(lines), mid)
        log.info(f"IDEA: {forge_user} -> {brief.get('product_name', '?')} (score={brief.get('confidence_score', '?')})")

    except subprocess.TimeoutExpired:
        send(chat_id, "Analysis timed out. Try again or simplify your idea.", mid)
    except json.JSONDecodeError:
        send(chat_id, "Analysis completed but output was malformed. Check logs.", mid)
    except Exception as e:
        log.error(f"Idea command error: {e}", exc_info=True)
        send(chat_id, f"Error: {e}", mid)


def cmd_build(chat_id, mid, tid, username, args):
    """Handle /build command — runs F1 Product Builder."""
    forge_user = _get_forge_username(str(tid))

    # Find brief: use argument or latest
    brief_path = None
    if args:
        # User specified a brief path
        candidate = " ".join(args).strip()
        bp = Path(candidate)
        if not bp.is_absolute():
            bp = FORGE_USERS / forge_user / candidate
        if bp.exists():
            brief_path = bp
        else:
            send(chat_id, f"Brief not found: {candidate}\nRun /idea first to create one.", mid)
            return
    else:
        # Find latest brief
        bp = _find_latest_brief(forge_user)
        if bp:
            brief_path = bp
        else:
            send(chat_id,
                "No strategy brief found.\n\n"
                "Run /idea first to create one:\n"
                "  /idea AI tool for restaurant menu optimization\n\n"
                "Or specify a brief path:\n"
                "  /build briefs/strategy-2026-03-31.json",
                mid)
            return

    typing(chat_id)
    send(chat_id,
        f"Building product from brief...\n"
        f"User: {forge_user}\n"
        f"Brief: {brief_path.name}\n\n"
        f"Running F1 Product Builder...",
        mid)

    # Run f1_product_builder.py
    f1_script = FORGE_SCRIPTS / "f1_product_builder.py"
    try:
        result = subprocess.run(
            [sys.executable, str(f1_script),
             "--user", forge_user,
             "--brief", str(brief_path),
             "--json"],
            capture_output=True, text=True, timeout=60,
            cwd=str(REPO_ROOT),
        )

        if result.returncode != 0:
            log.error(f"F1 error: {result.stderr}")
            send(chat_id, f"Build plan failed:\n{result.stderr[:500]}", mid)
            return

        output = json.loads(result.stdout)
        plan = output.get("plan", {})
        tech = plan.get("tech_stack", {})
        features = plan.get("mvp_features", [])
        iteration_plan = plan.get("iteration_plan", [])
        deploy = plan.get("deployment_target", "?")
        first_iter = plan.get("first_iteration", {})

        lines = [
            f"PRODUCT BUILD PLAN",
            f"{'=' * 30}",
            f"Deploy: {deploy}",
            f"Frontend: {tech.get('frontend', '?')}",
            f"Backend: {tech.get('backend', '?')}",
            f"Database: {tech.get('database', '?')}",
            f"",
            f"Features ({len(features)}):",
        ]
        for f in features[:6]:
            marker = "*" if f.get("priority") == "P0" else " "
            lines.append(f"  [{f.get('priority', '?')}]{marker} {f['name']}")

        lines.append(f"")
        lines.append(f"Plan ({plan.get('estimated_total_iterations', '?')} iterations):")
        for step in iteration_plan:
            lines.append(f"  {step['step']}. {step['name']}: {step.get('goal', '')}")

        lines.append(f"")
        lines.append(f"FIRST ITERATION:")
        lines.append(f"  {first_iter.get('what_to_build', '?')}")
        lines.append(f"  Test: {first_iter.get('how_to_test', '?')}")

        method = output.get("meta", {}).get("generation_method", "?")
        lines.append(f"")
        lines.append(f"[{method}]")
        lines.append(f"Files: README.md, CLAUDE.md, BUILD-PLAN.md")
        lines.append(f"Dir: forge-users/{forge_user}/products/")

        send(chat_id, "\n".join(lines), mid)
        log.info(f"BUILD: {forge_user} -> {deploy} ({len(features)} features)")

    except subprocess.TimeoutExpired:
        send(chat_id, "Build plan timed out. Try again.", mid)
    except json.JSONDecodeError:
        send(chat_id, "Build completed but output was malformed. Check logs.", mid)
    except Exception as e:
        log.error(f"Build command error: {e}", exc_info=True)
        send(chat_id, f"Error: {e}", mid)


# ── Router ───────────────────────────────────────────────────

def handle(chat_id, mid, tid, username, text):
    text = text.strip()

    if text.startswith("/start"):
        cmd_start(chat_id, mid)
        return
    if text.startswith("/login"):
        args = text.split()[1:]
        cmd_login(chat_id, mid, tid, username, args)
        return
    if text.startswith("/help"):
        _, user = find_user_by_tid(str(tid))
        cmd_help(chat_id, mid, user)
        return

    # Forge Factory commands (available before full auth for discovery)
    if text.startswith("/idea"):
        args = text.split()[1:]
        cmd_idea(chat_id, mid, tid, username, args)
        return
    if text.startswith("/build"):
        args = text.split()[1:]
        cmd_build(chat_id, mid, tid, username, args)
        return

    # Auth required for everything else
    _, user = find_user_by_tid(str(tid))
    if not user:
        send(chat_id, "Please /login first with your code.", mid)
        return

    if text.startswith("/picks"):
        cmd_picks(chat_id, mid, user)
    elif text.startswith("/bankroll"):
        cmd_bankroll(chat_id, mid, user)
    elif text.startswith("/models"):
        cmd_models(chat_id, mid, user)
    elif text.startswith("/plan"):
        cmd_plan(chat_id, mid, user)
    elif text.startswith("/"):
        send(chat_id, "Unknown command. Try /help", mid)
    else:
        send(chat_id, "Use /picks for today's NBA picks or /help for commands.", mid)

# ── Main ─────────────────────────────────────────────────────

def main():
    if not TOKEN:
        log.error("Set BOT_TOKEN_FORGE"); sys.exit(1)

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
                send(chat_id, "Slow down - max 10 commands/minute.", msg["message_id"])
                continue

            log.info(f"[{tid}|{username}] {text[:80]}")
            try:
                handle(chat_id, msg["message_id"], tid, username, text)
            except Exception as e:
                log.error(f"Error: {e}", exc_info=True)
                send(chat_id, f"Error: {e}")

if __name__ == "__main__":
    main()
