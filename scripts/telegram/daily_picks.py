#!/usr/bin/env python3
"""
@Nomos42Picks — Daily Value Bets for Paid Subscribers
======================================================
Reads predictions from nomos-nba-agent/data/nba-agent/ and
posts formatted picks to the private @Nomos42Picks channel.

Usage:
  python3 scripts/telegram/daily_picks.py              # post to channel
  python3 scripts/telegram/daily_picks.py --dry-run     # print only
  python3 scripts/telegram/daily_picks.py --preview     # send to admin only

Cron (09:00 ET = 13:00 UTC, daily during NBA season):
  0 13 * * * cd /home/termius/mon-ipad && /usr/bin/env \
    $(grep -v '^#' .env.local | xargs) python3 scripts/telegram/daily_picks.py \
    >> /tmp/daily_picks.log 2>&1
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = Path("/home/termius/nomos-nba-agent")
DATA_AGENT = AGENT_DIR / "data" / "nba-agent"
DATA_PRED = AGENT_DIR / "data" / "predictions"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_TELEGRAM_ID", "6582544948")
PICKS_CHANNEL = os.environ.get("PICKS_CHANNEL_ID", "@Nomos42Picks")

DRY_RUN = "--dry-run" in sys.argv
PREVIEW = "--preview" in sys.argv
MAX_MSG = 4000

ATR_BRIER = 0.21570
DASHBOARD_URL = "nomosdashboard.vercel.app"


def send(chat_id: str, text: str) -> bool:
    if DRY_RUN:
        print(f"\n--- DRY RUN → {chat_id} ---\n{text}\n")
        return True
    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return False
    chunks = [text[i:i + MAX_MSG] for i in range(0, len(text), MAX_MSG)]
    ok = True
    for chunk in chunks:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as resp:
                result = json.loads(resp.read())
                if not result.get("ok"):
                    print(f"[TG] failed: {result}", file=sys.stderr)
                    ok = False
        except Exception as e:
            print(f"[TG] error: {e}", file=sys.stderr)
            ok = False
    return ok


def esc(t: str) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_predictions() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for path in [
        DATA_AGENT / "predictions-today.json",
        DATA_PRED / f"predictions-{today}.json",
        DATA_AGENT / f"predictions-{today}.json",
    ]:
        if path.exists():
            d = json.loads(path.read_text())
            if d.get("games") or d.get("value_bets"):
                return d
    for path in sorted(DATA_PRED.glob("predictions-*.json"), reverse=True)[:3]:
        d = json.loads(path.read_text())
        if d.get("games"):
            return d
    return {}


def load_odds() -> list:
    path = ROOT / "data" / "nba-agent" / "live-odds.json"
    if path.exists():
        d = json.loads(path.read_text())
        return d.get("games", []) if isinstance(d, dict) else d
    return []


def confidence_emoji(conf: str) -> str:
    c = str(conf).upper()
    if c == "HIGH":
        return "🔥"
    if c == "MEDIUM":
        return "⚡"
    return "💤"


def american_display(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


def format_picks_message(preds: dict) -> str:
    date_str = preds.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    games = preds.get("games", [])
    value_bets = preds.get("value_bets", [])
    bankroll = preds.get("bankroll", 100.0)

    et_now = datetime.now(timezone(timedelta(hours=-4)))
    time_str = et_now.strftime("%I:%M %p ET")

    lines = [
        f"<b>🏀 NOMOS42 DAILY PICKS — {date_str}</b>",
        f"<i>Generated {time_str} | Model: ensemble-v1+isotonic</i>",
        f"<i>ATR Brier: {ATR_BRIER:.5f} | Bankroll: ${bankroll:.0f}</i>",
        "",
    ]

    if not games:
        lines.append("No NBA games scheduled today. Rest day. 🛌")
        lines.append("")
        lines.append(f'<i>Dashboard: {esc(DASHBOARD_URL)}</i>')
        return "\n".join(lines)

    top_bets = sorted(value_bets, key=lambda b: abs(b.get("edge", 0)), reverse=True)[:5]

    if top_bets:
        lines.append("<b>💎 VALUE BETS (highest edge first)</b>")
        lines.append("")

        for i, bet in enumerate(top_bets, 1):
            game = bet.get("game", "?")
            bet_type = bet.get("type", "moneyline").upper()
            pick = bet.get("pick", "?")
            edge = bet.get("edge", 0)
            kelly_pct = bet.get("kelly", 0)
            kelly_bet = bet.get("kelly_bet", 0)
            conf = bet.get("confidence", "MEDIUM")

            lines.append(
                f"{confidence_emoji(conf)} <b>#{i} {esc(game)}</b>"
            )
            lines.append(
                f"  📊 {bet_type} — <b>{esc(pick)}</b>"
            )
            lines.append(
                f"  📈 Edge: {edge:+.1f}% | Kelly: {kelly_pct:.1%} (${kelly_bet:.2f})"
            )

            if bet_type == "SPREAD":
                ms = bet.get("model_spread")
                mk = bet.get("market_spread")
                if ms is not None and mk is not None:
                    lines.append(f"  📐 Model spread: {ms:+.1f} vs market {mk:+.1f}")

            lines.append("")
    else:
        lines.append("⚠️ No value bets found today — model sees no edge vs market.")
        lines.append("")

    lines.append(f"<b>📋 ALL GAMES ({len(games)})</b>")
    lines.append("")

    for g in games:
        home = g.get("home", g.get("home_name", "?"))
        away = g.get("away", g.get("away_name", "?"))
        hp = g.get("home_win_prob", 0.5)
        ap = g.get("away_win_prob", 0.5)
        conf = g.get("confidence", "LOW")
        edge = g.get("edge", 0)
        market = g.get("market_implied", 0)

        fav = home if hp > ap else away
        fav_prob = max(hp, ap)

        icon = "🏠" if hp > ap else "✈️"
        lines.append(
            f"{icon} {esc(away)} @ {esc(home)}"
        )
        lines.append(
            f"  Model: {esc(fav)} {fav_prob:.0%} | Market: {market:.0%} | Edge: {edge:+.1%}"
        )

        total = g.get("total", {})
        if total and total.get("line"):
            lines.append(
                f"  O/U: {total['line']} → {total.get('pick', '?')} (model: {total.get('model_total', '?'):.1f})"
            )

        lines.append("")

    lines.append("—")
    lines.append("<b>⚠️ DISCLAIMER</b>: These are model-generated predictions,")
    lines.append("not financial advice. Bet responsibly. 18+ only.")
    lines.append("")
    lines.append(f'📊 Full stats: {esc(DASHBOARD_URL)}/nba')
    lines.append("🔔 @Nomos42Picks — $19/mo premium NBA picks")

    return "\n".join(lines)


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Loading predictions...")
    preds = load_predictions()

    if not preds:
        print("[WARN] No prediction data found. Sending no-games message.")
        preds = {"games": [], "value_bets": [], "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}

    msg = format_picks_message(preds)

    if PREVIEW:
        ok = send(ADMIN_ID, f"[PREVIEW]\n{msg}")
        print(f"Preview sent to admin: {'OK' if ok else 'FAILED'}")
    else:
        ok = send(PICKS_CHANNEL, msg)
        print(f"Posted to {PICKS_CHANNEL}: {'OK' if ok else 'FAILED'}")
        if ok:
            send(ADMIN_ID, f"✅ Daily picks posted to {PICKS_CHANNEL}")
        else:
            send(ADMIN_ID, f"❌ Failed to post picks to {PICKS_CHANNEL}")


if __name__ == "__main__":
    main()
