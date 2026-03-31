"""
Nomos42 Betting Monitor (B1 + B5 Agents)
Monitors NBA betting performance with auto-refresh and Telegram alerts.
"""

import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone

import gradio as gr

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "http://nomos42.duckdns.org:7860/data/nba-agent"
ENDPOINTS = {
    "bankroll": f"{BASE_URL}/bankroll-state.json",
    "eval": f"{BASE_URL}/latest-eval.json",
    "live_odds": f"{BASE_URL}/live-odds.json",
    "odds_latest": f"{BASE_URL}/odds-latest.json",
    "quant": f"{BASE_URL}/quant-summary.json",
}
FETCH_TIMEOUT = 10  # seconds
REFRESH_INTERVAL = 1800  # 30 minutes (background thread)
UI_REFRESH = 120  # seconds (auto-refresh UI)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = "6582544948"

DRAWDOWN_THRESHOLD = 80.0  # alert if balance < $80
BIG_WIN_ROI_THRESHOLD = 50.0  # alert if single bet ROI > 50%
STALE_HOURS = 48  # alert if no predictions for this long

# ---------------------------------------------------------------------------
# Data cache (thread-safe via GIL for simple dict reads/writes)
# ---------------------------------------------------------------------------
_cache: dict = {
    "bankroll": None,
    "eval": None,
    "live_odds": None,
    "odds_latest": None,
    "quant": None,
    "last_fetch": None,
    "errors": {},
}
_alert_state: dict = {
    "drawdown_sent": False,
    "big_win_sent": False,
    "stale_sent": False,
}


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------
def fetch_json(url: str) -> dict | list | None:
    """Fetch JSON from URL with timeout. Returns None on any failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-BettingMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def refresh_cache():
    """Fetch all endpoints and update cache."""
    errors = {}
    for key, url in ENDPOINTS.items():
        data = fetch_json(url)
        if data is not None:
            _cache[key] = data
        else:
            errors[key] = "Server unreachable"
    _cache["errors"] = errors
    _cache["last_fetch"] = datetime.now(timezone.utc).isoformat()
    check_alerts()


# ---------------------------------------------------------------------------
# Telegram alerts
# ---------------------------------------------------------------------------
def send_telegram(message: str):
    """Send a Telegram message via Bot API."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=FETCH_TIMEOUT)
    except Exception:
        pass


def check_alerts():
    """Check conditions and fire Telegram alerts."""
    bankroll = _cache.get("bankroll")
    eval_data = _cache.get("eval")

    # --- Drawdown alert ---
    if bankroll and isinstance(bankroll, dict):
        balance = bankroll.get("balance", 100)
        if balance < DRAWDOWN_THRESHOLD:
            if not _alert_state["drawdown_sent"]:
                send_telegram(
                    f"<b>DRAWDOWN ALERT</b>\n"
                    f"Bankroll: ${balance:.2f} (below ${DRAWDOWN_THRESHOLD:.0f})\n"
                    f"ROI: {bankroll.get('roi_pct', 0):.1f}%\n"
                    f"Record: {bankroll.get('wins', 0)}W-{bankroll.get('losses', 0)}L"
                )
                _alert_state["drawdown_sent"] = True
        else:
            _alert_state["drawdown_sent"] = False

        # --- Big win alert ---
        roi = bankroll.get("roi_pct", 0)
        daily_profit = bankroll.get("daily_profit_today", 0)
        if daily_profit > 0 and roi > BIG_WIN_ROI_THRESHOLD:
            if not _alert_state["big_win_sent"]:
                send_telegram(
                    f"<b>BIG WIN!</b>\n"
                    f"Daily profit: +${daily_profit:.2f}\n"
                    f"ROI: {roi:.1f}%\n"
                    f"Bankroll: ${balance:.2f}"
                )
                _alert_state["big_win_sent"] = True
        else:
            _alert_state["big_win_sent"] = False

    # --- Pipeline stall alert ---
    if bankroll and isinstance(bankroll, dict):
        last_bet = bankroll.get("last_bet_ts", "")
        if last_bet:
            try:
                last_dt = datetime.fromisoformat(last_bet)
                now = datetime.now(timezone.utc)
                hours_since = (now - last_dt).total_seconds() / 3600
                if hours_since > STALE_HOURS:
                    if not _alert_state["stale_sent"]:
                        send_telegram(
                            f"<b>PIPELINE STALL</b>\n"
                            f"No predictions for {hours_since:.0f}h (threshold: {STALE_HOURS}h)\n"
                            f"Last bet: {last_bet[:19]}"
                        )
                        _alert_state["stale_sent"] = True
                else:
                    _alert_state["stale_sent"] = False
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Background refresh thread
# ---------------------------------------------------------------------------
def background_loop():
    """Runs forever, refreshing cache every REFRESH_INTERVAL seconds."""
    while True:
        try:
            refresh_cache()
        except Exception:
            pass
        time.sleep(REFRESH_INTERVAL)


# Start background thread
_bg_thread = threading.Thread(target=background_loop, daemon=True)
_bg_thread.start()

# Also do an initial fetch at startup
refresh_cache()


# ---------------------------------------------------------------------------
# Tab renderers
# ---------------------------------------------------------------------------
def _status_line() -> str:
    ts = _cache.get("last_fetch", "never")
    errs = _cache.get("errors", {})
    parts = [f"Last refresh: {ts[:19] if ts else 'never'} UTC"]
    if errs:
        parts.append(f"Errors: {', '.join(errs.keys())}")
    return " | ".join(parts)


def render_bankroll() -> str:
    """Tab 1: Bankroll overview."""
    data = _cache.get("bankroll")
    if data is None:
        return "## Server unreachable\nCould not fetch bankroll-state.json"

    balance = data.get("balance", 0)
    initial = data.get("initial_balance", 100)
    roi = data.get("roi_pct", 0)
    wins = data.get("wins", 0)
    losses = data.get("losses", 0)
    pushes = data.get("pushes", 0)
    sharpe = data.get("sharpe_ratio", 0)
    peak = data.get("peak_balance", 0)
    trough = data.get("trough_balance", 0)
    max_dd = data.get("max_drawdown_pct", 0)
    total_bets = data.get("total_bets", 0)
    total_wagered = data.get("total_wagered", 0)
    total_profit = data.get("total_profit", 0)
    win_rate = data.get("win_rate_pct", 0)
    last_bet = data.get("last_bet_ts", "N/A")
    updated = data.get("last_updated", "N/A")
    streak = data.get("streak_current", 0)

    pnl_emoji = "+" if total_profit >= 0 else ""
    roi_color = "green" if roi >= 0 else "red"

    md = f"""## Bankroll Status

| Metric | Value |
|--------|-------|
| **Current Balance** | **${balance:.2f}** |
| Starting Balance | ${initial:.2f} |
| **ROI** | **{pnl_emoji}{roi:.1f}%** |
| Total Profit | {pnl_emoji}${total_profit:.2f} |
| **Record** | **{wins}W - {losses}L - {pushes}P** |
| Win Rate | {win_rate:.1f}% |
| Total Bets | {total_bets} |
| Total Wagered | ${total_wagered:.2f} |
| **Sharpe Ratio** | **{sharpe:.2f}** |
| Peak Balance | ${peak:.2f} |
| Trough Balance | ${trough:.2f} |
| Max Drawdown | {max_dd:.1f}% |
| Current Streak | {streak} |
| Last Bet | {str(last_bet)[:19]} |
| Last Updated | {str(updated)[:19]} |

---
*{_status_line()}*
"""
    return md


def render_picks() -> str:
    """Tab 2: Today's picks / latest evaluation."""
    data = _cache.get("eval")
    if data is None:
        return "## Server unreachable\nCould not fetch latest-eval.json"

    accuracy = data.get("accuracy", 0)
    total = data.get("total", 0)
    evaluated = data.get("evaluated", 0)
    passed = data.get("passed", 0)
    cycle = data.get("cycle", 0)
    brier = data.get("brier_score", 0)
    model = data.get("model", "unknown")
    features = data.get("features", 0)
    engine = data.get("feature_engine_version", "unknown")
    wins = data.get("wins", 0)
    losses = data.get("losses", 0)
    roi = data.get("roi_pct", 0)
    sharpe = data.get("sharpe_ratio", 0)
    bankroll = data.get("bankroll", 0)
    atr = data.get("atr_brier", 0)
    prev_atr = data.get("prev_atr_brier", 0)
    improvement = data.get("improvement_vs_prev", 0)
    platform = data.get("platform", "unknown")
    ts = data.get("timestamp", "N/A")

    # Islands summary
    islands = data.get("islands", {})
    island_lines = ""
    for sid, info in islands.items():
        role = info.get("role", "unknown")
        best = info.get("best_brier", "N/A")
        gen = info.get("gen", "N/A")
        mut = info.get("mut", "N/A")
        notes = info.get("notes", "")
        island_lines += f"| {sid} | {role} | {best} | {gen} | {mut} | {notes} |\n"

    md = f"""## Latest Evaluation (Cycle {cycle})

| Metric | Value |
|--------|-------|
| **Model** | **{model}** |
| Features | {features} |
| Engine | {engine} |
| **Brier Score** | **{brier:.5f}** |
| ATR Brier | {atr:.5f} |
| Previous ATR | {prev_atr:.5f} |
| Improvement | {improvement:.5f} |
| Platform | {platform} |
| Accuracy | {accuracy:.1f}% |
| Evaluated | {evaluated} / {total} |
| Passed (bets) | {passed} |
| **Record** | **{wins}W - {losses}L** |
| ROI | {roi:.2f}% |
| Sharpe | {sharpe:.2f} |
| Bankroll | ${bankroll:.2f} |
| Timestamp | {str(ts)[:19]} |

### Evolution Islands

| Island | Role | Best Brier | Gen | Mutation | Notes |
|--------|------|------------|-----|----------|-------|
{island_lines}

---
*{_status_line()}*
"""
    return md


def render_live_odds() -> str:
    """Tab 3: Live odds display."""
    data = _cache.get("live_odds")
    if data is None:
        return "## Server unreachable\nCould not fetch live-odds.json"

    # live-odds.json has a "games" key with a list
    games = data.get("games", data) if isinstance(data, dict) else data
    if not isinstance(games, list):
        return "## No games data available"

    if len(games) == 0:
        return "## No games currently listed"

    md = "## Live Odds\n\n"
    for game in games:
        home = game.get("home_team", "?")
        away = game.get("away_team", "?")
        commence = game.get("commence_time", "")
        commence_display = commence[:16].replace("T", " ") if commence else "TBD"

        md += f"### {away} @ {home}\n"
        md += f"*Tip-off: {commence_display} UTC*\n\n"

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            md += "*No odds available*\n\n"
            continue

        # Show first 3 bookmakers to keep it readable
        for bk in bookmakers[:3]:
            bk_name = bk.get("title", bk.get("key", "?"))
            md += f"**{bk_name}**\n\n"
            markets = bk.get("markets", [])
            for market in markets:
                mkey = market.get("key", "?")
                outcomes = market.get("outcomes", [])
                if mkey == "h2h":
                    md += "| Moneyline | Odds |\n|-----------|------|\n"
                    for o in outcomes:
                        md += f"| {o.get('name', '?')} | {o.get('price', '?')} |\n"
                    md += "\n"
                elif mkey == "spreads":
                    md += "| Spread | Line | Odds |\n|--------|------|------|\n"
                    for o in outcomes:
                        md += f"| {o.get('name', '?')} | {o.get('point', '?')} | {o.get('price', '?')} |\n"
                    md += "\n"
                elif mkey == "totals":
                    md += "| Total | Line | Odds |\n|-------|------|------|\n"
                    for o in outcomes:
                        md += f"| {o.get('name', '?')} | {o.get('point', '?')} | {o.get('price', '?')} |\n"
                    md += "\n"
            md += "\n"
        md += "---\n\n"

    md += f"\n*Showing up to 3 bookmakers per game | {_status_line()}*"
    return md


def render_history() -> str:
    """Tab 4: Performance history (ATR Brier history + model breakdown)."""
    quant = _cache.get("quant")
    if quant is None:
        return "## Server unreachable\nCould not fetch quant-summary.json"

    # ATR history
    atr_history = quant.get("atr_history", [])
    targets = quant.get("targets", {})
    evolution = quant.get("evolution", {})
    calibration = quant.get("calibration", {})

    md = "## Performance History\n\n"

    # Targets
    md += "### Targets\n\n"
    md += "| Metric | Target | Current |\n|--------|--------|---------|\n"
    md += f"| Brier | {targets.get('brier', 'N/A')} | {quant.get('best_brier', 'N/A')} |\n"
    md += f"| ROI | {targets.get('roi_pct', 'N/A')}% | {quant.get('roi_pct', 'N/A')}% |\n"
    md += f"| Sharpe | {targets.get('sharpe', 'N/A')} | N/A |\n\n"

    # ATR timeline
    md += "### All-Time Record (Brier Score)\n\n"
    md += "| Date | Brier | Model | Features | Notes |\n"
    md += "|------|-------|-------|----------|-------|\n"
    for entry in atr_history:
        md += (
            f"| {entry.get('date', '?')} "
            f"| **{entry.get('brier', '?')}** "
            f"| {entry.get('model', '?')} "
            f"| {entry.get('features', '?')} "
            f"| {entry.get('notes', '')} |\n"
        )
    md += "\n"

    # Models breakdown
    models = quant.get("models", {})
    if models:
        md += "### Model Ensemble\n\n"
        md += "| Model | Brier | Weight | Status |\n"
        md += "|-------|-------|--------|--------|\n"
        for name, info in models.items():
            md += (
                f"| {name} "
                f"| {info.get('brier', '?')} "
                f"| {info.get('weight', '?')} "
                f"| {info.get('status', '?')} |\n"
            )
        md += "\n"

    # Evolution stats
    if evolution:
        md += "### Evolution Status\n\n"
        md += "| Parameter | Value |\n|-----------|-------|\n"
        for k, v in evolution.items():
            md += f"| {k} | {v} |\n"
        md += "\n"

    md += f"\n---\n*{_status_line()}*"
    return md


def render_quant_summary() -> str:
    """Tab 5: Full quant-summary.json display."""
    data = _cache.get("quant")
    if data is None:
        return "## Server unreachable\nCould not fetch quant-summary.json"

    # Top-level summary
    md = "## Quant Summary\n\n"
    md += "| Metric | Value |\n|--------|-------|\n"

    top_keys = [
        "timestamp", "bankroll", "growth_pct", "record", "roi_pct",
        "best_brier", "best_model", "features", "games_trained",
        "research_papers", "latest_picks", "latest_exposure",
        "latest_ev", "daemon_status", "data_source",
    ]
    for k in top_keys:
        if k in data:
            v = data[k]
            if isinstance(v, float):
                md += f"| {k} | {v:.4f} |\n"
            else:
                md += f"| {k} | {v} |\n"
    md += "\n"

    # Feature categories
    fc = data.get("feature_categories", {})
    if fc:
        md += "### Feature Categories\n\n"
        md += "| Parameter | Value |\n|-----------|-------|\n"
        for k, v in fc.items():
            md += f"| {k} | {v} |\n"
        md += "\n"

    # Calibration
    cal = data.get("calibration", {})
    if cal:
        md += "### Calibration Parameters\n\n"
        md += "| Parameter | Value |\n|-----------|-------|\n"
        for k, v in cal.items():
            if k == "reasoning":
                continue  # show separately
            md += f"| {k} | {v} |\n"
        md += "\n"
        if "reasoning" in cal:
            md += f"**Reasoning:** {cal['reasoning']}\n\n"

    # Raw JSON dump for anything else
    md += "### Raw JSON\n\n"
    md += f"```json\n{json.dumps(data, indent=2, default=str)[:5000]}\n```\n"

    md += f"\n---\n*{_status_line()}*"
    return md


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------
def build_app() -> gr.Blocks:
    theme = gr.themes.Default()

    with gr.Blocks(
        title="Nomos42 Betting Monitor",
        theme=theme,
        css="""
        .markdown-text h2 { color: #2e7d32; }
        .status-bar { font-size: 0.85em; color: #666; }
        """,
    ) as app:
        gr.Markdown("# Nomos42 Betting Monitor\n*NBA Quant AI -- B1 + B5 Agents*")

        with gr.Tabs():
            # Tab 1: Bankroll
            with gr.Tab("Bankroll"):
                bankroll_md = gr.Markdown(value=render_bankroll, every=UI_REFRESH)

            # Tab 2: Today's Picks
            with gr.Tab("Today's Picks"):
                picks_md = gr.Markdown(value=render_picks, every=UI_REFRESH)

            # Tab 3: Live Odds
            with gr.Tab("Live Odds"):
                odds_md = gr.Markdown(value=render_live_odds, every=UI_REFRESH)

            # Tab 4: Performance History
            with gr.Tab("Performance History"):
                history_md = gr.Markdown(value=render_history, every=UI_REFRESH)

            # Tab 5: Quant Summary
            with gr.Tab("Quant Summary"):
                quant_md = gr.Markdown(value=render_quant_summary, every=UI_REFRESH)

        gr.Markdown(
            f"*Auto-refresh every {UI_REFRESH}s | Background fetch every {REFRESH_INTERVAL // 60}min | "
            f"Alerts: drawdown <${DRAWDOWN_THRESHOLD:.0f}, big win >{BIG_WIN_ROI_THRESHOLD:.0f}% ROI, stale >{STALE_HOURS}h*"
        )

    return app


app = build_app()

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
