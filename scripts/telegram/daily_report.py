#!/usr/bin/env python3
"""
Nomos42 Daily Report — Beautiful Telegram status update
========================================================
Sends automated status to admin + @Nomos42 channel.
Covers: fleet health + best Brier, bankroll P&L,
        Trading Floor standings (NBA + Political),
        Department health from Guardian.

Usage:
  python3 scripts/telegram/daily_report.py           # full report
  python3 scripts/telegram/daily_report.py --dry-run  # print only, no send

Cron (09:00 UTC morning brief, 21:00 UTC evening recap):
  0 9,21 * * * cd /home/lahargnedebartoli/mon-ipad && /usr/bin/env \
    $(grep -v '^#' .env.local | xargs) python3 scripts/telegram/daily_report.py \
    >> /tmp/daily_report.log 2>&1

Requirements: stdlib only (urllib, json, pathlib, datetime)
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path("/home/lahargnedebartoli/mon-ipad")
DATA = ROOT / "data"

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN",   "8672296360:AAHZ5_3-fDE7BBb3b-RJBSRWlXA1qO31UVo")
ADMIN_ID   = os.environ.get("ADMIN_TELEGRAM_ID",    "6582544948")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID",  "@Nomos42")

MAX_MSG    = 4000          # Telegram limit ~4096, leave margin
DRY_RUN    = "--dry-run" in sys.argv

# ---------------------------------------------------------------------------
# ATR / targets
# ---------------------------------------------------------------------------
ATR_BRIER  = 0.21570       # all-time record (Colab TabICL)
TARGET_BRIER   = 0.20
TARGET_ROI     = 5.0
TARGET_SHARPE  = 1.5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _esc(text: str) -> str:
    """Escape HTML special chars for Telegram HTML mode."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _send(chat_id: str, text: str) -> bool:
    """Send one message (splits if too long). Returns True on success."""
    if DRY_RUN:
        print(f"\n--- DRY RUN → {chat_id} ---\n{text}\n")
        return True

    chunks = [text[i : i + MAX_MSG] for i in range(0, len(text), MAX_MSG)]
    ok_all = True
    for chunk in chunks:
        url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id":                  chat_id,
            "text":                     chunk,
            "parse_mode":               "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(url, data=data)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                if not result.get("ok"):
                    print(f"[TG] send failed: {result}", file=sys.stderr)
                    ok_all = False
        except Exception as e:
            print(f"[TG] exception sending to {chat_id}: {e}", file=sys.stderr)
            # Retry without HTML parse_mode (in case of malformed tags)
            try:
                plain_data = urllib.parse.urlencode({
                    "chat_id": chat_id,
                    "text":    chunk,
                }).encode()
                urllib.request.urlopen(
                    urllib.request.Request(url, data=plain_data), timeout=15
                )
            except Exception:
                ok_all = False
    return ok_all


def _pct_bar(value: float, target: float, invert: bool = False, width: int = 10) -> str:
    """Return a simple ASCII progress bar towards a target."""
    try:
        ratio = value / target if not invert else target / value
        ratio = max(0.0, min(ratio, 1.0))
        filled = round(ratio * width)
        return "█" * filled + "░" * (width - filled)
    except Exception:
        return "░" * width


def _medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")


def _status_icon(status: str) -> str:
    s = str(status).lower()
    if s in ("up", "alive", "running", "completed", "active"):
        return "🟢"
    if s in ("warning", "idle", "unknown"):
        return "🟡"
    return "🔴"

# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def section_fleet() -> str:
    """HF Spaces fleet status + best Brier."""
    health = read_json(DATA / "agent-health.json")
    spaces = health.get("projects", {}).get("nba", {}).get("spaces", {})
    summary = health.get("summary", {})

    lines = ["<b>🏟️ FLEET — 6 HF ISLANDS</b>"]

    if spaces:
        best_brier = min(s.get("brier", 9) for s in spaces.values() if s.get("brier"))
        worst_brier = max(s.get("brier", 0) for s in spaces.values() if s.get("brier"))
        total_gen = sum(s.get("generation", 0) for s in spaces.values())
        up_count  = sum(1 for s in spaces.values() if str(s.get("status","")).upper() == "UP")

        lines.append(f"  Status : {up_count}/6 UP  |  Gens: {total_gen:,}")
        lines.append(f"  Best   : {best_brier:.5f}  |  Worst: {worst_brier:.5f}")
        lines.append(f"  ATR    : {ATR_BRIER:.5f}  |  Target: {TARGET_BRIER:.5f}")
        gap_to_target = best_brier - TARGET_BRIER
        gap_to_atr    = best_brier - ATR_BRIER
        lines.append(f"  Gap→ATR: {gap_to_atr:+.5f}  |  Gap→Target: {gap_to_target:+.5f}")
        lines.append("")

        # Per-island table
        island_order = ["S10","S11","S12","S13","S14","S15"]
        for sid in island_order:
            s = spaces.get(sid, {})
            if not s:
                continue
            icon  = "🟢" if str(s.get("status","")).upper() == "UP" else "🔴"
            brier = s.get("brier", "?")
            gen   = s.get("generation", "?")
            model = s.get("model", "?")[:16]
            star  = " ⭐" if isinstance(brier, float) and brier == best_brier else ""
            lines.append(f"  {icon} {sid}  {brier:.5f}  gen={gen:<4}  {model:<16}{star}")
    else:
        lines.append("  ⚠️  No space data available")

    # Kaggle status
    kaggle = health.get("projects", {}).get("nba", {}).get("kaggle", {})
    if kaggle:
        k_statuses = [v.get("status","?") for v in kaggle.values()]
        k_summary  = "OK" if all(s == "OK" for s in k_statuses) else "ERROR"
        lines.append(f"\n  Kaggle : {k_summary}  ({len(kaggle)} kernels)")

    # Global issues
    issues = health.get("issues", [])
    if issues:
        lines.append(f"\n  ⚠️  Issues: {len(issues)}")
        for iss in issues[:3]:
            lines.append(f"    · {_esc(iss[:60])}")

    return "\n".join(lines)


def section_bankroll() -> str:
    """NBA bankroll P&L."""
    br = read_json(DATA / "nba-agent" / "bankroll-state.json")
    qs = read_json(DATA / "nba-agent" / "quant-summary.json")

    if not br:
        return "<b>💰 BANKROLL</b>\n  ⚠️  Data unavailable"

    balance  = br.get("balance",      0.0)
    initial  = br.get("initial_balance", 100.0)
    profit   = br.get("total_profit",  0.0)
    roi      = br.get("roi_pct",       0.0)
    wins     = br.get("wins",          0)
    losses   = br.get("losses",        0)
    peak     = br.get("peak_balance",  0.0)
    drawdown = br.get("max_drawdown_pct", 0.0)
    sharpe   = br.get("sharpe_ratio",  0.0)
    win_rate = br.get("win_rate_pct",  0.0)
    wagered  = br.get("total_wagered", 0.0)
    total_b  = br.get("total_bets",    0)

    roi_icon = "🟢" if roi >= TARGET_ROI else ("🟡" if roi >= 0 else "🔴")
    sh_icon  = "🟢" if sharpe >= TARGET_SHARPE else ("🟡" if sharpe >= 0 else "🔴")

    # Best model brier from quant summary
    best_brier_qs = qs.get("best_brier", "?")
    best_model_qs = qs.get("best_model", "?")

    lines = [
        "<b>💰 BANKROLL — NBA REAL MONEY SIM</b>",
        f"  Balance : ${balance:.2f}  (start ${initial:.2f})",
        f"  P&L     : ${profit:+.2f}  {roi_icon} ROI: {roi:+.1f}%  (target {TARGET_ROI:+.0f}%)",
        f"  Peak    : ${peak:.2f}  |  Drawdown: {drawdown:.1f}%",
        f"  Record  : {wins}W-{losses}L  ({win_rate:.1f}% WR)  |  Bets: {total_b}  Wagered: ${wagered:.2f}",
        f"  Sharpe  : {sh_icon} {sharpe:+.2f}  (target {TARGET_SHARPE:+.1f})",
        f"  Best ATR: {best_brier_qs}  ({best_model_qs})",
    ]
    return "\n".join(lines)


def _read_trader_head(path: Path) -> dict:
    """Read only the top-level scalar fields from a (potentially large) trader JSON.

    These files can be 1–2 MB because they store full day-by-day history.
    The top-level scalar fields we need are always within the first ~600 bytes
    (the first ~20 lines), before the first array field ("nba_day_results" /
    "trade_history").  We read 8 KB, slice off everything from the first array
    opener "[", close the object, then parse.  Falls back to full-file read.
    """
    try:
        head = path.read_bytes()[:8192].decode("utf-8", errors="replace")
        # Find first list value start — cut there so JSON is valid
        bracket_pos = head.find(": [")
        if bracket_pos != -1:
            truncated = head[:bracket_pos].rstrip().rstrip(",") + "\n}"
        else:
            # No list found in first 8 KB — just try as-is
            truncated = head
        return json.loads(truncated)
    except Exception:
        # Final fallback: parse full file (slow but correct)
        return read_json(path)


def section_trading_floor() -> str:
    """Trading Floor standings — NBA + Political."""
    traders_dir = DATA / "arena" / "traders"
    if not traders_dir.exists():
        return "<b>🏦 TRADING FLOOR</b>\n  ⚠️  Trader data unavailable"

    # Load NBA traders
    nba_ids = ["grok", "claude", "openrouter", "codex", "gemini"]
    nba_traders = []
    for tid in nba_ids:
        path = traders_dir / f"{tid}-state.json"
        if not path.exists():
            continue
        d = _read_trader_head(path)
        if not d:
            continue
        nba_traders.append({
            "id":       tid,
            "name":     d.get("name", tid.title()),
            "bankroll": d.get("nba_bankroll", 0.0),
            "roi":      d.get("nba_roi_pct", 0.0),
            "sharpe":   d.get("nba_sharpe",  0.0),
            "bets":     d.get("nba_bets",    0),
            "wins":     d.get("nba_wins",    0),
            "elim":     d.get("nba_eliminated_day"),
        })

    nba_traders.sort(key=lambda x: x["bankroll"], reverse=True)

    # Load Political traders
    pol_ids = ["grok", "claude", "openrouter", "codex", "gemini"]
    pol_traders = []
    for tid in pol_ids:
        path = traders_dir / f"political-{tid}-state.json"
        if not path.exists():
            continue
        d = _read_trader_head(path)
        if not d:
            continue
        pol_traders.append({
            "id":    tid,
            "name":  d.get("name", tid.title()),
            "capital": d.get("capital", 0.0),
            "roi":   d.get("roi_pct", 0.0),
            "sharpe":d.get("sharpe", 0.0),
            "trades":d.get("total_trades", 0),
        })

    pol_traders.sort(key=lambda x: x["capital"], reverse=True)

    lines = ["<b>🏦 TRADING FLOOR v4</b>"]

    # NBA standings
    lines.append("")
    lines.append("  <u>NBA Tournament</u> (start $100):")
    for rank, t in enumerate(nba_traders, 1):
        elim = " 💀 ELIM" if t["elim"] is not None else ""
        wr = round(t["wins"] / t["bets"] * 100) if t["bets"] > 0 else 0
        lines.append(
            f"  {_medal(rank)} {t['name']:<12} "
            f"${t['bankroll']:>9,.2f}  "
            f"ROI {t['roi']:>+8.1f}%  "
            f"Sh:{t['sharpe']:>+5.2f}{elim}"
        )

    # Political standings
    if pol_traders:
        lines.append("")
        lines.append("  <u>Political Tournament</u> (start $100K):")
        for rank, t in enumerate(pol_traders, 1):
            lines.append(
                f"  {_medal(rank)} {t['name']:<12} "
                f"${t['capital']:>10,.2f}  "
                f"ROI {t['roi']:>+7.2f}%  "
                f"Sh:{t['sharpe']:>+5.2f}"
            )

    return "\n".join(lines)


def section_departments() -> str:
    """Guardian report — department health overview."""
    guardian = read_json(DATA / "departments" / "guardian-report.json")
    wins_data = read_json(DATA / "departments" / "wins-latest.json")

    if not guardian:
        return "<b>🏛️ DEPARTMENTS</b>\n  ⚠️  Guardian data unavailable"

    dept_summaries = guardian.get("dept_summaries", {})
    actions_count  = guardian.get("actions_count", 0)
    actions_hi     = guardian.get("actions_by_priority", {}).get("HIGH", 0)
    cross_routes   = guardian.get("cross_pollination", {}).get("routes_active", 0)
    guardian_status = guardian.get("status", "?")

    # Status icons per dept
    DEPT_LABELS = {
        "research":         "🔬 Research",
        "engineering":      "⚙️ Engineering",
        "evolution":        "🧬 Evolution",
        "betting":          "🎯 Betting",
        "evaluation":       "📊 Evaluation",
        "infra":            "🖥️ Infra",
        "political":        "🗳️ Political",
        "creative":         "🎨 Creative",
        "trading_floor":    "🏦 Trading Floor",
        "nba_prediction":   "🏀 NBA Pred",
        "political_signals":"📡 Pol Signals",
        "rgwa_creative":    "🎭 RGWA",
    }

    lines = [
        "<b>🏛️ DEPARTMENTS (Forge v19)</b>",
        f"  Guardian: {_status_icon(guardian_status)}  "
        f"Actions: {actions_count}  "
        f"HIGH: {actions_hi}  "
        f"Cross-pollinate: {cross_routes}",
        "",
    ]

    # Current metrics from wins-latest
    current = wins_data.get("current_metrics", {})

    shown_depts = ["research", "engineering", "evolution", "betting",
                   "evaluation", "infra", "political", "creative", "trading_floor"]

    for dept in shown_depts:
        label   = DEPT_LABELS.get(dept, dept.title())
        summary = dept_summaries.get(dept, "")
        metrics = current.get(dept, {})
        status  = metrics.get("status") or (summary.split("status=")[-1] if "status=" in summary else "?")
        icon    = _status_icon(status)

        extra = ""
        if dept == "evolution":
            bb = metrics.get("best_brier")
            if bb:
                extra = f"  Brier={bb:.5f}"
        elif dept == "research":
            papers = metrics.get("papers_scanned")
            techs  = metrics.get("techniques_extracted")
            if papers:
                extra = f"  {papers}papers / {techs}techs"
        elif dept == "betting":
            rankings = metrics.get("strategy_rankings", [])
            if rankings:
                top = rankings[0]
                extra = f"  #{1} {top.get('strategy','?')} ({top.get('verdict','?')})"
        elif dept == "infra":
            uptime = metrics.get("uptime_pct")
            if uptime:
                extra = f"  uptime={uptime}%"

        lines.append(f"  {icon} {label:<18} {_esc(status)}{_esc(extra)}")

    # Guardian pending actions
    pending = guardian.get("priority_queue", [])
    if pending:
        lines.append("")
        lines.append(f"  📋 Pending actions ({len(pending)}):")
        for act in pending[:3]:
            pri   = act.get("priority", "?")
            route = act.get("route", "?")
            action_text = act.get("action", "")[:50]
            lines.append(f"    [{pri}] {_esc(action_text)}")

    return "\n".join(lines)


def section_vm_health() -> str:
    """Quick VM health snapshot."""
    import subprocess

    lines = ["<b>🖥️ VM HEALTH</b>"]

    # Disk
    try:
        import shutil
        disk = shutil.disk_usage("/")
        disk_pct = round(disk.used / disk.total * 100)
        disk_icon = "🟢" if disk_pct < 80 else ("🟡" if disk_pct < 90 else "🔴")
        lines.append(f"  Disk   : {disk_icon} {disk_pct}%  ({disk.free // 1_073_741_824:.1f}GB free)")
    except Exception:
        lines.append("  Disk   : ❓")

    # Memory
    try:
        with open("/proc/meminfo") as f:
            mem_lines = f.readlines()
        total_kb = int(next(l for l in mem_lines if "MemTotal" in l).split()[1])
        avail_kb = int(next(l for l in mem_lines if "MemAvailable" in l).split()[1])
        used_pct = round((total_kb - avail_kb) / total_kb * 100)
        mem_icon = "🟢" if used_pct < 80 else ("🟡" if used_pct < 90 else "🔴")
        lines.append(f"  Memory : {mem_icon} {used_pct}%  ({avail_kb // 1024}MB free)")
    except Exception:
        lines.append("  Memory : ❓")

    # Load
    try:
        with open("/proc/loadavg") as f:
            load1, load5 = f.read().split()[:2]
        load_icon = "🟢" if float(load1) < 0.8 else ("🟡" if float(load1) < 1.5 else "🔴")
        lines.append(f"  Load   : {load_icon} {load1} / {load5}  (1m/5m)")
    except Exception:
        lines.append("  Load   : ❓")

    # Running bots
    try:
        ps = subprocess.check_output(
            ["pgrep", "-fc", "python3"],
            text=True, timeout=5
        ).strip()
        lines.append(f"  Procs  : 🟢 {ps} python3 processes")
    except Exception:
        lines.append("  Procs  : ❓")

    # Last git commit
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "-1", "--pretty=format:%h %s"],
            text=True, timeout=5
        ).strip()
        lines.append(f"  Git    : {_esc(commit[:60])}")
    except Exception:
        pass

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def collect_alerts(health: dict, bankroll: dict) -> list[str]:
    """Collect critical alerts that need attention."""
    alerts = []

    # Space issues
    issues = health.get("issues", [])
    for iss in issues:
        alerts.append(f"⚠️ {iss[:80]}")

    # Space DOWN
    spaces = health.get("projects", {}).get("nba", {}).get("spaces", {})
    for sid, s in spaces.items():
        if str(s.get("status","")).upper() != "UP":
            alerts.append(f"🔴 {sid} is DOWN")

    # Bankroll drawdown alert
    dd = bankroll.get("max_drawdown_pct", 0)
    if isinstance(dd, (int, float)) and dd > 20:
        alerts.append(f"📉 Bankroll drawdown {dd:.1f}% exceeds 20% threshold")

    # Sharpe below target
    sharpe = bankroll.get("sharpe_ratio", 0)
    if isinstance(sharpe, (int, float)) and sharpe < 0:
        alerts.append(f"📉 Sharpe ratio {sharpe:+.2f} is negative")

    return alerts


# ---------------------------------------------------------------------------
# Main report builder
# ---------------------------------------------------------------------------

def build_report(session: str = "AM") -> str:
    now     = datetime.now(timezone.utc)
    date_s  = now.strftime("%Y-%m-%d")
    time_s  = now.strftime("%H:%M UTC")

    health   = read_json(DATA / "agent-health.json")
    bankroll = read_json(DATA / "nba-agent" / "bankroll-state.json")
    alerts   = collect_alerts(health, bankroll)

    alert_header = ""
    if alerts:
        alert_header = (
            "\n🚨 <b>ALERTS</b>\n"
            + "\n".join(f"  {a}" for a in alerts[:5])
            + "\n"
        )

    session_icon = "🌅" if session == "AM" else "🌙"

    header = (
        f"<b>{session_icon} NOMOS42 DAILY REPORT — {date_s} {time_s}</b>\n"
        f"<i>NBA Quant AI · Forge v19 · 6 Islands · 5 Traders</i>\n"
        f"{'═' * 38}"
    )

    sections = [
        header,
        alert_header,
        section_fleet(),
        "",
        section_bankroll(),
        "",
        section_trading_floor(),
        "",
        section_departments(),
        "",
        section_vm_health(),
    ]

    footer = (
        f"\n{'─' * 38}\n"
        f"<i>ATR: {ATR_BRIER} · Target: {TARGET_BRIER} · nomos42-nba-quant.hf.space</i>"
    )
    sections.append(footer)

    return "\n".join(s for s in sections if s is not None)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    now     = datetime.now(timezone.utc)
    session = "AM" if now.hour < 14 else "PM"

    print(f"[daily_report] Building {session} report at {now.isoformat()}")

    report = build_report(session)

    if DRY_RUN:
        print(report)
        return

    if not BOT_TOKEN:
        print("[daily_report] ERROR: TELEGRAM_BOT_TOKEN not set — printing to stdout")
        print(report)
        sys.exit(1)

    # Send to admin (private, always gets full report)
    admin_ok = _send(ADMIN_ID, report)
    print(f"[daily_report] Admin ({ADMIN_ID}): {'OK' if admin_ok else 'FAIL'}")

    # Send to channel
    chan_ok = _send(CHANNEL_ID, report)
    print(f"[daily_report] Channel ({CHANNEL_ID}): {'OK' if chan_ok else 'FAIL'}")

    sys.exit(0 if (admin_ok and chan_ok) else 1)


if __name__ == "__main__":
    main()
