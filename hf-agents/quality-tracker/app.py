"""
Nomos42 Quality Tracker (Q1 Agent)
Tracks prediction quality metrics across the Nomos42 NBA evolution ecosystem.
Polls 6 HF islands + VM data every 15 minutes. Sends Telegram alerts on milestones.
"""

import gradio as gr
import urllib.request
import json
import os
import time
import threading
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ATR_BRIER = 0.21570          # All-Time Record (Colab TabICL, 110f, iter 15)
WALK_FORWARD_BRIER = 0.22447 # Kaggle walk-forward baseline (19 weeks, 934 games)
TARGET_BRIER = 0.20          # Project target
SOTA_BRIER = 0.199           # Montrucchio 2026
POLL_INTERVAL = 900          # 15 minutes
MAX_HISTORY = 96             # 24h at 15-min intervals
STAGNATION_HOURS = 12        # Alert if no improvement in this many hours

TELEGRAM_CHAT_ID = "6582544948"

ISLANDS = [
    {"id": "S10", "name": "nba-quant",   "url": "https://nomos42-nba-quant.hf.space",   "role": "Exploitation"},
    {"id": "S11", "name": "nba-quant-2", "url": "https://nomos42-nba-quant-2.hf.space", "role": "Exploration"},
    {"id": "S12", "name": "nba-evo-3",   "url": "https://nomos42-nba-evo-3.hf.space",   "role": "ExtraTrees"},
    {"id": "S13", "name": "nba-evo-4",   "url": "https://nomos42-nba-evo-4.hf.space",   "role": "CatBoost"},
    {"id": "S14", "name": "nba-evo-5",   "url": "https://nomos42-nba-evo-5.hf.space",   "role": "LightGBM"},
    {"id": "S15", "name": "nba-evo-6",   "url": "https://nomos42-nba-evo-6.hf.space",   "role": "Wide Search"},
]

VM_EVAL_URL = "http://nomos42.duckdns.org:7860/data/nba-agent/latest-eval.json"
VM_SUMMARY_URL = "http://nomos42.duckdns.org:7860/data/nba-agent/quant-summary.json"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

history_log = []          # list of {"ts": str, "best_brier": float, "island": str}
island_cache = []         # latest island data rows
arena_cache = {}          # latest quant-summary
eval_cache = {}           # latest-eval
last_improvement_ts = datetime.now(timezone.utc)
current_best_live = None  # best brier seen from islands this session
alert_log = []            # recent alert messages

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_json(url, timeout=15):
    """Fetch JSON from a URL using urllib only. Returns dict or None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-QualityTracker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def send_telegram(message):
    """Send a Telegram alert via bot API."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    try:
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def determine_trend():
    """Determine whether the best brier is improving, stagnant, or degrading."""
    if len(history_log) < 4:
        return "insufficient data"
    recent = [h["best_brier"] for h in history_log[-4:] if h["best_brier"] is not None]
    older = [h["best_brier"] for h in history_log[-8:-4] if h["best_brier"] is not None]
    if not recent or not older:
        return "insufficient data"
    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)
    diff = avg_older - avg_recent  # positive = improving (lower brier is better)
    if diff > 0.001:
        return "IMPROVING"
    elif diff < -0.001:
        return "DEGRADING"
    else:
        return "STAGNANT"

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

def poll_islands():
    """Poll all 6 HF islands for status data."""
    global island_cache, current_best_live, last_improvement_ts
    rows = []
    best_brier = None
    best_island = None

    for isl in ISLANDS:
        data = fetch_json(f"{isl['url']}/api/status")
        if data:
            brier = data.get("best_brier") or data.get("best_score")
            gen = data.get("generation", "?")
            model = data.get("best_model", "?")
            features = data.get("best_features") or data.get("num_features", "?")
            status = "UP"
        else:
            brier = None
            gen = "?"
            model = "?"
            features = "?"
            status = "DOWN"

        rows.append({
            "Island": f"{isl['id']} ({isl['name']})",
            "Role": isl["role"],
            "Brier": f"{brier:.5f}" if brier else "N/A",
            "Model": str(model),
            "Features": str(features),
            "Generation": str(gen),
            "Status": status,
        })

        if brier is not None:
            if best_brier is None or brier < best_brier:
                best_brier = brier
                best_island = isl["id"]

    island_cache = rows

    # Check for improvements and alerts
    now = datetime.now(timezone.utc)

    if best_brier is not None:
        # New ATR?
        if best_brier < ATR_BRIER:
            msg = (
                f"<b>NEW ATR!</b>\n"
                f"Island {best_island} achieved Brier {best_brier:.5f}\n"
                f"Previous ATR: {ATR_BRIER:.5f}\n"
                f"Improvement: {ATR_BRIER - best_brier:.5f}"
            )
            send_telegram(msg)
            alert_log.append(f"[{now.strftime('%H:%M')}] NEW ATR: {best_brier:.5f} on {best_island}")

        # Significant improvement on any island?
        if current_best_live is not None and (current_best_live - best_brier) > 0.002:
            msg = (
                f"<b>Significant improvement!</b>\n"
                f"Island {best_island}: {best_brier:.5f}\n"
                f"Previous best: {current_best_live:.5f}\n"
                f"Delta: {current_best_live - best_brier:.5f}"
            )
            send_telegram(msg)
            alert_log.append(f"[{now.strftime('%H:%M')}] DROP: {current_best_live:.5f} -> {best_brier:.5f} on {best_island}")

        # Track improvement time
        if current_best_live is None or best_brier < current_best_live:
            last_improvement_ts = now
            current_best_live = best_brier

        # Stagnation check
        hours_since = (now - last_improvement_ts).total_seconds() / 3600
        if hours_since >= STAGNATION_HOURS:
            msg = (
                f"<b>Stagnation alert</b>\n"
                f"No improvement in {hours_since:.1f}h\n"
                f"Best live: {current_best_live:.5f}"
            )
            send_telegram(msg)
            alert_log.append(f"[{now.strftime('%H:%M')}] STAGNANT: {hours_since:.0f}h without improvement")
            # Reset timer so we don't spam every 15 min
            last_improvement_ts = now

    # Record history
    history_log.append({
        "ts": now.strftime("%Y-%m-%d %H:%M"),
        "best_brier": best_brier,
        "island": best_island,
    })
    if len(history_log) > MAX_HISTORY:
        history_log[:] = history_log[-MAX_HISTORY:]


def poll_vm():
    """Poll VM data endpoints."""
    global eval_cache, arena_cache
    data = fetch_json(VM_EVAL_URL)
    if data:
        eval_cache = data
    data = fetch_json(VM_SUMMARY_URL)
    if data:
        arena_cache = data


def poll_all():
    """Run a complete polling cycle."""
    poll_islands()
    poll_vm()


def background_poller():
    """Background thread that polls every POLL_INTERVAL seconds."""
    while True:
        try:
            poll_all()
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)

# ---------------------------------------------------------------------------
# UI Builders
# ---------------------------------------------------------------------------

def build_brier_dashboard():
    """Build the main Brier dashboard display."""
    best_live = current_best_live
    best_live_str = f"{best_live:.5f}" if best_live else "polling..."
    gap_target = f"{(best_live - TARGET_BRIER):.5f}" if best_live else "?"
    gap_sota = f"{(best_live - SOTA_BRIER):.5f}" if best_live else "?"
    trend = determine_trend()

    # Color the trend
    trend_colors = {
        "IMPROVING": "#00c853",
        "STAGNANT": "#ff9800",
        "DEGRADING": "#f44336",
        "insufficient data": "#9e9e9e",
    }
    trend_color = trend_colors.get(trend, "#9e9e9e")

    # Find best island name
    best_island_name = "N/A"
    if island_cache:
        for row in island_cache:
            if row["Brier"] != "N/A":
                try:
                    if best_live and abs(float(row["Brier"]) - best_live) < 0.00001:
                        best_island_name = row["Island"]
                        break
                except ValueError:
                    pass

    # Up count
    up_count = sum(1 for r in island_cache if r.get("Status") == "UP")
    total_count = len(ISLANDS)

    # Alerts summary
    recent_alerts = alert_log[-5:] if alert_log else ["No alerts yet"]
    alerts_html = "<br>".join(recent_alerts)

    html = f"""
    <div style="font-family: monospace; padding: 20px;">
      <h1 style="text-align:center; color: #7c4dff;">Nomos42 Quality Tracker</h1>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">

        <div style="background: #1a1a2e; border-radius: 12px; padding: 24px; text-align: center;">
          <div style="color: #aaa; font-size: 14px;">ALL-TIME RECORD (Colab TabICL)</div>
          <div style="color: #00e676; font-size: 48px; font-weight: bold;">{ATR_BRIER:.5f}</div>
          <div style="color: #666; font-size: 12px;">110 features, iteration 15</div>
        </div>

        <div style="background: #1a1a2e; border-radius: 12px; padding: 24px; text-align: center;">
          <div style="color: #aaa; font-size: 14px;">BEST LIVE ISLAND</div>
          <div style="color: #40c4ff; font-size: 48px; font-weight: bold;">{best_live_str}</div>
          <div style="color: #666; font-size: 12px;">{best_island_name}</div>
        </div>

        <div style="background: #1a1a2e; border-radius: 12px; padding: 24px; text-align: center;">
          <div style="color: #aaa; font-size: 14px;">GAP TO TARGET (0.20)</div>
          <div style="color: #ffab40; font-size: 36px; font-weight: bold;">{gap_target}</div>
          <div style="color: #666; font-size: 12px;">Lower is better</div>
        </div>

        <div style="background: #1a1a2e; border-radius: 12px; padding: 24px; text-align: center;">
          <div style="color: #aaa; font-size: 14px;">GAP TO SOTA (0.199 Montrucchio)</div>
          <div style="color: #ff5252; font-size: 36px; font-weight: bold;">{gap_sota}</div>
          <div style="color: #666; font-size: 12px;">Published state of the art</div>
        </div>

      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin: 20px 0;">

        <div style="background: #1a1a2e; border-radius: 12px; padding: 20px; text-align: center;">
          <div style="color: #aaa; font-size: 14px;">WALK-FORWARD BASELINE</div>
          <div style="color: #ce93d8; font-size: 28px; font-weight: bold;">{WALK_FORWARD_BRIER:.5f}</div>
          <div style="color: #666; font-size: 12px;">Kaggle 19 weeks, 934 games</div>
        </div>

        <div style="background: #1a1a2e; border-radius: 12px; padding: 20px; text-align: center;">
          <div style="color: #aaa; font-size: 14px;">TREND</div>
          <div style="color: {trend_color}; font-size: 28px; font-weight: bold;">{trend}</div>
          <div style="color: #666; font-size: 12px;">Based on last 2h of data</div>
        </div>

        <div style="background: #1a1a2e; border-radius: 12px; padding: 20px; text-align: center;">
          <div style="color: #aaa; font-size: 14px;">ISLANDS UP</div>
          <div style="color: {'#00e676' if up_count == total_count else '#ff9800'}; font-size: 28px; font-weight: bold;">{up_count} / {total_count}</div>
          <div style="color: #666; font-size: 12px;">HF Spaces status</div>
        </div>

      </div>

      <div style="background: #1a1a2e; border-radius: 12px; padding: 16px; margin-top: 20px;">
        <div style="color: #aaa; font-size: 14px; margin-bottom: 8px;">RECENT ALERTS</div>
        <div style="color: #e0e0e0; font-size: 13px;">{alerts_html}</div>
      </div>

      <div style="text-align: center; color: #555; font-size: 11px; margin-top: 16px;">
        Last poll: {history_log[-1]['ts'] if history_log else 'not yet'} UTC | Polls every 15 min | Auto-refreshes every 60s
      </div>
    </div>
    """
    return html


def build_island_table():
    """Build the island comparison table."""
    if not island_cache:
        return "<div style='padding:20px; color:#aaa;'>No data yet. Waiting for first poll...</div>"

    header = "<tr>" + "".join(
        f"<th style='padding:10px; background:#2a2a4a; color:#b0bec5; text-align:left;'>{col}</th>"
        for col in ["Island", "Role", "Brier", "Model", "Features", "Gen", "Status"]
    ) + "</tr>"

    rows_html = ""
    for row in island_cache:
        # Color the brier
        brier_val = row["Brier"]
        if brier_val != "N/A":
            try:
                bv = float(brier_val)
                if bv < ATR_BRIER:
                    brier_color = "#00e676"  # better than ATR
                elif bv < WALK_FORWARD_BRIER:
                    brier_color = "#40c4ff"  # better than walk-forward
                else:
                    brier_color = "#ff9800"  # needs work
            except ValueError:
                brier_color = "#e0e0e0"
        else:
            brier_color = "#f44336"

        status_color = "#00e676" if row["Status"] == "UP" else "#f44336"

        cells = [
            f"<td style='padding:10px; color:#e0e0e0;'>{row['Island']}</td>",
            f"<td style='padding:10px; color:#b0bec5;'>{row['Role']}</td>",
            f"<td style='padding:10px; color:{brier_color}; font-weight:bold;'>{brier_val}</td>",
            f"<td style='padding:10px; color:#b0bec5;'>{row['Model']}</td>",
            f"<td style='padding:10px; color:#b0bec5;'>{row['Features']}</td>",
            f"<td style='padding:10px; color:#b0bec5;'>{row['Generation']}</td>",
            f"<td style='padding:10px; color:{status_color}; font-weight:bold;'>{row['Status']}</td>",
        ]
        rows_html += "<tr style='border-bottom: 1px solid #333;'>" + "".join(cells) + "</tr>"

    html = f"""
    <div style="font-family: monospace; padding: 20px;">
      <h2 style="color: #7c4dff;">Island Comparison</h2>
      <table style="width:100%; border-collapse:collapse; background:#1a1a2e; border-radius:12px;">
        {header}
        {rows_html}
      </table>
      <div style="color: #555; font-size: 11px; margin-top: 12px;">
        Color key: <span style="color:#00e676;">green</span> = better than ATR ({ATR_BRIER}) |
        <span style="color:#40c4ff;">blue</span> = better than walk-forward ({WALK_FORWARD_BRIER}) |
        <span style="color:#ff9800;">orange</span> = needs improvement
      </div>
    </div>
    """
    return html


def build_arena_results():
    """Build arena/quant-summary display."""
    if not arena_cache:
        return "<div style='padding:20px; color:#aaa;'>No arena data yet. Waiting for VM poll...</div>"

    html = '<div style="font-family: monospace; padding: 20px;">'
    html += '<h2 style="color: #7c4dff;">Arena Results (Quant Summary)</h2>'

    # Try to display top performers
    top_models = arena_cache.get("top_models") or arena_cache.get("models") or []
    if isinstance(arena_cache, dict) and not top_models:
        # Render whatever structure we got
        html += '<div style="background:#1a1a2e; border-radius:12px; padding:20px;">'
        for key, val in arena_cache.items():
            if isinstance(val, (str, int, float)):
                html += f'<div style="margin:8px 0;"><span style="color:#aaa;">{key}:</span> <span style="color:#e0e0e0; font-weight:bold;">{val}</span></div>'
            elif isinstance(val, list) and len(val) <= 20:
                html += f'<div style="margin:12px 0;"><span style="color:#aaa;">{key}:</span>'
                for item in val[:10]:
                    if isinstance(item, dict):
                        parts = " | ".join(f"{k}: {v}" for k, v in item.items())
                        html += f'<div style="color:#b0bec5; margin-left:16px; font-size:13px;">{parts}</div>'
                    else:
                        html += f'<div style="color:#b0bec5; margin-left:16px; font-size:13px;">{item}</div>'
                html += '</div>'
            elif isinstance(val, dict):
                html += f'<div style="margin:12px 0;"><span style="color:#aaa;">{key}:</span>'
                for sk, sv in val.items():
                    html += f'<div style="color:#b0bec5; margin-left:16px; font-size:13px;">{sk}: {sv}</div>'
                html += '</div>'
        html += '</div>'
    elif top_models:
        html += '<table style="width:100%; border-collapse:collapse; background:#1a1a2e; border-radius:12px;">'
        if isinstance(top_models[0], dict):
            cols = list(top_models[0].keys())
            html += "<tr>" + "".join(
                f"<th style='padding:10px; background:#2a2a4a; color:#b0bec5;'>{c}</th>" for c in cols
            ) + "</tr>"
            for m in top_models[:15]:
                html += "<tr>" + "".join(
                    f"<td style='padding:8px; color:#e0e0e0;'>{m.get(c, '')}</td>" for c in cols
                ) + "</tr>"
        html += '</table>'

    # Also show latest-eval summary
    if eval_cache:
        html += '<h3 style="color: #b39ddb; margin-top: 24px;">Latest Evaluation</h3>'
        html += '<div style="background:#1a1a2e; border-radius:12px; padding:20px;">'
        for key, val in eval_cache.items():
            if isinstance(val, (str, int, float)):
                html += f'<div style="margin:6px 0;"><span style="color:#aaa;">{key}:</span> <span style="color:#e0e0e0;">{val}</span></div>'
        html += '</div>'

    html += '</div>'
    return html


def build_history():
    """Build the Brier timeline history display."""
    if not history_log:
        return "<div style='padding:20px; color:#aaa;'>No history yet. Data populates every 15 minutes.</div>"

    html = '<div style="font-family: monospace; padding: 20px;">'
    html += '<h2 style="color: #7c4dff;">Brier History (last 24h)</h2>'
    html += f'<div style="color:#666; margin-bottom:16px;">{len(history_log)} data points ({len(history_log) * 15} minutes of data)</div>'

    # Summary stats
    valid = [h["best_brier"] for h in history_log if h["best_brier"] is not None]
    if valid:
        html += '<div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:16px; margin-bottom:20px;">'
        html += f'''
        <div style="background:#1a1a2e; border-radius:8px; padding:16px; text-align:center;">
          <div style="color:#aaa; font-size:12px;">BEST SEEN</div>
          <div style="color:#00e676; font-size:22px; font-weight:bold;">{min(valid):.5f}</div>
        </div>
        <div style="background:#1a1a2e; border-radius:8px; padding:16px; text-align:center;">
          <div style="color:#aaa; font-size:12px;">WORST SEEN</div>
          <div style="color:#ff5252; font-size:22px; font-weight:bold;">{max(valid):.5f}</div>
        </div>
        <div style="background:#1a1a2e; border-radius:8px; padding:16px; text-align:center;">
          <div style="color:#aaa; font-size:12px;">AVERAGE</div>
          <div style="color:#b0bec5; font-size:22px; font-weight:bold;">{sum(valid)/len(valid):.5f}</div>
        </div>
        <div style="background:#1a1a2e; border-radius:8px; padding:16px; text-align:center;">
          <div style="color:#aaa; font-size:12px;">SPREAD</div>
          <div style="color:#b0bec5; font-size:22px; font-weight:bold;">{max(valid)-min(valid):.5f}</div>
        </div>
        '''
        html += '</div>'

    # ASCII-style bar chart (text-based visualization)
    html += '<div style="background:#1a1a2e; border-radius:12px; padding:20px; overflow-x:auto;">'
    html += '<div style="color:#aaa; font-size:12px; margin-bottom:12px;">TIMELINE (newest at bottom)</div>'

    if valid:
        min_b = min(min(valid), TARGET_BRIER) - 0.005
        max_b = max(valid) + 0.005
        bar_range = max_b - min_b if max_b > min_b else 0.01

    for entry in history_log[-48:]:  # show last 48 entries (12h) for readability
        ts = entry["ts"]
        brier = entry["best_brier"]
        island = entry["island"] or "?"
        if brier is not None:
            bar_width = int(((brier - min_b) / bar_range) * 40)
            bar_width = max(1, min(40, bar_width))
            bar_char = "=" * bar_width
            if brier < ATR_BRIER:
                color = "#00e676"
            elif brier < WALK_FORWARD_BRIER:
                color = "#40c4ff"
            else:
                color = "#ff9800"
            html += f'<div style="margin:2px 0;"><span style="color:#666;">{ts}</span> <span style="color:{color};">{bar_char}</span> <span style="color:#e0e0e0;">{brier:.5f}</span> <span style="color:#555;">[{island}]</span></div>'
        else:
            html += f'<div style="margin:2px 0;"><span style="color:#666;">{ts}</span> <span style="color:#f44336;">-- no data --</span></div>'

    html += '</div>'

    # Reference lines
    html += f'''
    <div style="color:#555; font-size:11px; margin-top:12px;">
      Reference: ATR={ATR_BRIER} | Walk-Forward={WALK_FORWARD_BRIER} | Target={TARGET_BRIER} | SOTA={SOTA_BRIER}
    </div>
    '''
    html += '</div>'
    return html

# ---------------------------------------------------------------------------
# Gradio App
# ---------------------------------------------------------------------------

def refresh_dashboard():
    return build_brier_dashboard()

def refresh_islands():
    return build_island_table()

def refresh_arena():
    return build_arena_results()

def refresh_history():
    return build_history()


# Initial poll
poll_all()

# Start background poller
poller_thread = threading.Thread(target=background_poller, daemon=True)
poller_thread.start()

# Build UI
with gr.Blocks(
    theme=gr.themes.Default(),
    title="Nomos42 Quality Tracker",
    css="body { background-color: #0d0d1a; }"
) as app:

    gr.Markdown("# Nomos42 Quality Tracker (Q1 Agent)")
    gr.Markdown("Tracking prediction quality across 6 NBA evolution islands. Polls every 15 min. Auto-refreshes every 60s.")

    with gr.Tabs():
        with gr.TabItem("Brier Dashboard"):
            dashboard_html = gr.HTML(value=build_brier_dashboard, every=60)

        with gr.TabItem("Island Comparison"):
            island_html = gr.HTML(value=build_island_table, every=60)

        with gr.TabItem("Arena Results"):
            arena_html = gr.HTML(value=build_arena_results, every=60)

        with gr.TabItem("History"):
            history_html = gr.HTML(value=build_history, every=60)

app.launch(server_name="0.0.0.0", server_port=7860)
