"""
Nomos42 Political Monitor — HF Space
Monitors 4 Political Alpha evolution islands + Polymarket political markets.
Auto-refresh every 120s. Telegram alerts on anomalies.
"""

import gradio as gr
import json
import os
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = "6582544948"

POLITICAL_ISLANDS = [
    {
        "id": "P1",
        "name": "nomos42-political-alpha",
        "url": "https://nomos42-political-alpha.hf.space",
        "role": "exploitation",
    },
    {
        "id": "P2",
        "name": "nomos42-political-alpha-2",
        "url": "https://nomos42-political-alpha-2.hf.space",
        "role": "exploration",
    },
    # P3/P4 removed 2026-04-03 — spaces never existed on HF
]

POLYMARKET_URL = "https://clob.polymarket.com/markets?limit=10&tag=politics"

POLL_INTERVAL = 900  # 15 minutes
STAGNATION_ALERT_THRESHOLD = 25
POLYMARKET_MOVE_ALERT_THRESHOLD = 10  # percent

ENGINE_INFO = {
    "version": "v3.1-22cat",
    "total_features": 743,
    "num_categories": 22,
    "category_breakdown": "1-16 base + 17-22 insider/Trump/foreign",
    "key_categories": [
        "1. Executive orders & Federal Register",
        "2. Congressional votes & bill status",
        "3. Polling aggregates (538, RCP)",
        "4. Campaign finance (FEC)",
        "5. Economic indicators (FRED)",
        "6. Market sentiment (VIX, sector ETFs)",
        "7. Social media sentiment",
        "8. Prediction market prices",
        "9. Judicial rulings & appointments",
        "10. International relations events",
        "11. Approval ratings (multi-source)",
        "12. Media coverage volume",
        "13. State-level polling",
        "14. Demographic shifts",
        "15. Historical election patterns",
        "16. Fundraising velocity",
        "17. Enforcement actions dismissed",
        "18. CEO personal donations",
        "19. Polymarket delta 24h",
        "20. TPU index (Trump Policy Uncertainty)",
        "21. Government contract awards",
        "22. Foreign policy signals",
    ],
}

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

island_data = []
polymarket_data = []
signals_log = []
previous_polymarket_prices = {}
monitor_running = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _send_telegram(message: str) -> None:
    """Send a Telegram alert. Fail silently."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        payload = json.dumps(
            {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def _add_signal(category: str, message: str) -> None:
    """Append to the signals log (keep last 100)."""
    global signals_log
    entry = {"timestamp": _utc_now(), "category": category, "message": message}
    signals_log = [entry] + signals_log[:99]


def _fetch_json(url: str, timeout: int = 15):
    """Fetch JSON from a URL using urllib. Returns parsed dict/list or None."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Nomos42-PoliticalMonitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Polling: Political Islands
# ---------------------------------------------------------------------------


def poll_islands() -> list:
    """Poll all 4 political islands for status."""
    results = []
    for island in POLITICAL_ISLANDS:
        status_url = f"{island['url']}/api/status"
        data = _fetch_json(status_url)
        if data is None:
            row = {
                "Island": island["id"],
                "Role": island["role"],
                "Gen": "DOWN",
                "Best Brier": "N/A",
                "Best Model": "N/A",
                "Features": "N/A",
                "Stagnation": "N/A",
            }
            _add_signal(
                "ISLAND_DOWN",
                f"{island['id']} ({island['name']}) is not responding",
            )
            _send_telegram(
                f"<b>POLITICAL ALERT</b>\n{island['id']} ({island['name']}) is DOWN"
            )
        else:
            gen = data.get("generation", data.get("gen", "?"))
            best_brier = data.get("best_brier", data.get("best_score", "?"))
            best_model = data.get("best_model", data.get("model", "?"))
            features = data.get("num_features", data.get("features", "?"))
            stagnation = data.get(
                "stagnation_counter", data.get("stagnation", "?")
            )

            if isinstance(best_brier, (int, float)):
                best_brier = f"{best_brier:.5f}"

            row = {
                "Island": island["id"],
                "Role": island["role"],
                "Gen": str(gen),
                "Best Brier": str(best_brier),
                "Best Model": str(best_model),
                "Features": str(features),
                "Stagnation": str(stagnation),
            }

            # Alert on high stagnation
            try:
                stag_val = int(stagnation)
                if stag_val > STAGNATION_ALERT_THRESHOLD:
                    _add_signal(
                        "STAGNATION",
                        f"{island['id']} stagnation={stag_val} (threshold={STAGNATION_ALERT_THRESHOLD})",
                    )
                    _send_telegram(
                        f"<b>POLITICAL ALERT</b>\n{island['id']} stagnation={stag_val} > {STAGNATION_ALERT_THRESHOLD}"
                    )
            except (ValueError, TypeError):
                pass

        results.append(row)
    return results


# ---------------------------------------------------------------------------
# Polling: Polymarket
# ---------------------------------------------------------------------------


def poll_polymarket() -> list:
    """Poll Polymarket for current political markets."""
    global previous_polymarket_prices

    data = _fetch_json(POLYMARKET_URL)
    if data is None:
        _add_signal("POLYMARKET_ERROR", "Failed to fetch Polymarket data")
        return []

    # Polymarket API may return a list directly or nested under a key
    markets = data if isinstance(data, list) else data.get("data", data.get("markets", []))
    if not isinstance(markets, list):
        _add_signal("POLYMARKET_ERROR", "Unexpected Polymarket response format")
        return []

    results = []
    current_prices = {}

    for market in markets[:10]:
        try:
            question = market.get("question", market.get("title", "Unknown"))
            # Prices may be nested differently depending on API version
            yes_price = market.get("yes_price", market.get("outcomePrices", [None, None]))
            no_price = market.get("no_price", None)

            if isinstance(yes_price, list) and len(yes_price) >= 2:
                yes_val = yes_price[0]
                no_val = yes_price[1]
            elif isinstance(yes_price, (int, float, str)):
                yes_val = yes_price
                no_val = no_price
            else:
                yes_val = "N/A"
                no_val = "N/A"

            # Format prices
            try:
                yes_display = f"${float(yes_val):.2f}"
                no_display = f"${float(no_val):.2f}" if no_val else "N/A"
            except (ValueError, TypeError):
                yes_display = str(yes_val)
                no_display = str(no_val) if no_val else "N/A"

            volume = market.get("volume", market.get("volumeNum", "N/A"))
            if isinstance(volume, (int, float)):
                if volume >= 1_000_000:
                    volume_display = f"${volume / 1_000_000:.1f}M"
                elif volume >= 1_000:
                    volume_display = f"${volume / 1_000:.1f}K"
                else:
                    volume_display = f"${volume:.0f}"
            else:
                volume_display = str(volume)

            updated = market.get("updated_at", market.get("endDate", "N/A"))
            if isinstance(updated, str) and len(updated) > 19:
                updated = updated[:19].replace("T", " ")

            market_id = market.get("condition_id", market.get("id", question[:30]))

            results.append(
                {
                    "Market": question[:80],
                    "Yes Price": yes_display,
                    "No Price": no_display,
                    "Volume": volume_display,
                    "Last Updated": str(updated),
                }
            )

            # Check for large moves
            try:
                current_yes = float(yes_val)
                current_prices[str(market_id)] = current_yes
                if str(market_id) in previous_polymarket_prices:
                    prev = previous_polymarket_prices[str(market_id)]
                    delta = abs(current_yes - prev) * 100
                    if delta > 5:
                        direction = "UP" if current_yes > prev else "DOWN"
                        _add_signal(
                            "POLYMARKET_MOVE",
                            f"{question[:60]} moved {direction} {delta:.1f}% (${prev:.2f} -> ${current_yes:.2f})",
                        )
                    if delta > POLYMARKET_MOVE_ALERT_THRESHOLD:
                        _send_telegram(
                            f"<b>POLYMARKET ALERT</b>\n{question[:60]}\nMoved {direction} {delta:.1f}%\n${prev:.2f} -> ${current_yes:.2f}"
                        )
            except (ValueError, TypeError):
                pass

        except Exception:
            continue

    previous_polymarket_prices = current_prices
    return results


# ---------------------------------------------------------------------------
# Background Monitor Thread
# ---------------------------------------------------------------------------


def monitor_loop():
    """Background thread that polls every POLL_INTERVAL seconds."""
    global island_data, polymarket_data, monitor_running
    monitor_running = True
    _add_signal("SYSTEM", "Political Monitor started")

    while monitor_running:
        try:
            island_data = poll_islands()
        except Exception as e:
            _add_signal("ERROR", f"Island polling failed: {str(e)[:100]}")

        try:
            polymarket_data = poll_polymarket()
        except Exception as e:
            _add_signal("ERROR", f"Polymarket polling failed: {str(e)[:100]}")

        # Add placeholder signals for features not yet live
        # These would be replaced by real data sources
        _add_signal("PLACEHOLDER", "Executive order monitoring: awaiting Federal Register API integration")
        _add_signal("PLACEHOLDER", "Insider trade cluster detection: awaiting SEC EDGAR polling")

        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Gradio UI callbacks
# ---------------------------------------------------------------------------


def get_island_table():
    """Return island status as a list of lists for the Dataframe."""
    if not island_data:
        return [["--", "--", "--", "--", "--", "--", "--"]]
    return [
        [
            r["Island"],
            r["Role"],
            r["Gen"],
            r["Best Brier"],
            r["Best Model"],
            r["Features"],
            r["Stagnation"],
        ]
        for r in island_data
    ]


def get_engine_info():
    """Return engine info as formatted markdown."""
    cats = "\n".join(f"  - {c}" for c in ENGINE_INFO["key_categories"])
    return f"""## Political Alpha Engine

**Version:** {ENGINE_INFO['version']}
**Total Features:** {ENGINE_INFO['total_features']}
**Categories:** {ENGINE_INFO['num_categories']} ({ENGINE_INFO['category_breakdown']})

### Category List
{cats}

---
*Last refreshed: {_utc_now()}*
"""


def get_polymarket_table():
    """Return Polymarket data as a list of lists for the Dataframe."""
    if not polymarket_data:
        return [["No data", "--", "--", "--", "--"]]
    return [
        [
            r["Market"],
            r["Yes Price"],
            r["No Price"],
            r["Volume"],
            r["Last Updated"],
        ]
        for r in polymarket_data
    ]


def get_signals_log():
    """Return signals log as formatted markdown."""
    if not signals_log:
        return "*No signals yet. Monitor will begin logging after first poll cycle.*"
    lines = []
    for s in signals_log[:50]:
        icon = {
            "POLYMARKET_MOVE": "[MARKET]",
            "STAGNATION": "[STAGNATION]",
            "ISLAND_DOWN": "[DOWN]",
            "POLYMARKET_ERROR": "[ERROR]",
            "SYSTEM": "[SYSTEM]",
            "ERROR": "[ERROR]",
            "PLACEHOLDER": "[PENDING]",
        }.get(s["category"], f"[{s['category']}]")
        lines.append(f"**{s['timestamp']}** {icon} {s['message']}")
    return "\n\n".join(lines)


def refresh_all():
    """Manual refresh triggered by the auto-refresh timer or button."""
    return (
        get_island_table(),
        get_engine_info(),
        get_polymarket_table(),
        get_signals_log(),
        f"Last refresh: {_utc_now()}",
    )


# ---------------------------------------------------------------------------
# Start background monitor
# ---------------------------------------------------------------------------

monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
monitor_thread.start()

# ---------------------------------------------------------------------------
# Gradio App
# ---------------------------------------------------------------------------

ISLAND_HEADERS = ["Island", "Role", "Gen", "Best Brier", "Best Model", "Features", "Stagnation"]
MARKET_HEADERS = ["Market", "Yes Price", "No Price", "Volume", "Last Updated"]

with gr.Blocks(
    theme=gr.themes.Default(),
    title="Nomos42 Political Monitor",
) as app:
    gr.Markdown("# Nomos42 Political Monitor")
    gr.Markdown(
        "Monitoring 4 Political Alpha evolution islands + Polymarket political markets. "
        "Polls every 15 minutes. Auto-refreshes UI every 120 seconds."
    )

    status_label = gr.Markdown(value=f"Started: {_utc_now()}")

    with gr.Tabs():
        with gr.Tab("Evolution Status"):
            gr.Markdown("### Political Alpha Evolution Islands")
            island_table = gr.Dataframe(
                headers=ISLAND_HEADERS,
                value=get_island_table(),
                interactive=False,
                wrap=True,
            )

        with gr.Tab("Engine Info"):
            engine_md = gr.Markdown(value=get_engine_info())

        with gr.Tab("Political Markets"):
            gr.Markdown("### Polymarket Political Markets (Top 10)")
            market_table = gr.Dataframe(
                headers=MARKET_HEADERS,
                value=get_polymarket_table(),
                interactive=False,
                wrap=True,
            )

        with gr.Tab("Signals Log"):
            gr.Markdown("### Detected Signals & Alerts")
            signals_md = gr.Markdown(value=get_signals_log())

    refresh_btn = gr.Button("Refresh Now", variant="secondary")
    refresh_btn.click(
        fn=refresh_all,
        outputs=[island_table, engine_md, market_table, signals_md, status_label],
    )

    # Auto-refresh every 120 seconds
    timer = gr.Timer(120)
    timer.tick(
        fn=refresh_all,
        outputs=[island_table, engine_md, market_table, signals_md, status_label],
    )

app.launch()
