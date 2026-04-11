"""
Nomos42 Island Coordinator — V1
Monitors evolution progress across 6 NBA + 4 Political HF Space islands.
Polls /api/status every 10 minutes, stores 24h of history, sends Telegram alerts.
"""

import json
import os
import threading
import time
import urllib.request
import urllib.error
from collections import deque
from datetime import datetime, timezone

import gradio as gr

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = "6582544948"

POLL_INTERVAL_SEC = 600  # 10 minutes
HISTORY_SIZE = 144  # 24h at 10-min intervals

ISLANDS = {
    # NBA islands
    "S10": {
        "url": "https://nomos42-nba-quant.hf.space/api/status",
        "role": "exploitation",
        "domain": "NBA",
    },
    "S11": {
        "url": "https://nomos42-nba-quant-2.hf.space/api/status",
        "role": "exploration",
        "domain": "NBA",
    },
    "S12": {
        "url": "https://nomos42-nba-evo-3.hf.space/api/status",
        "role": "extra_trees",
        "domain": "NBA",
    },
    "S13": {
        "url": "https://nomos42-nba-evo-4.hf.space/api/status",
        "role": "catboost",
        "domain": "NBA",
    },
    "S14": {
        "url": "https://nomos42-nba-evo-5.hf.space/api/status",
        "role": "lightgbm",
        "domain": "NBA",
    },
    "S15": {
        "url": "https://nomos42-nba-evo-6.hf.space/api/status",
        "role": "wide_search",
        "domain": "NBA",
    },
    "S16": {
        "url": "https://lbjlincoln26-nba-evo-s16.hf.space/api/status",
        "role": "gradient_boost",
        "domain": "NBA",
    },
    "S17": {
        "url": "https://lbjlincoln26-nba-evo-s17.hf.space/api/status",
        "role": "ensemble",
        "domain": "NBA",
    },
    # Political islands
    "P1": {
        "url": "https://nomos42-political-alpha.hf.space/api/status",
        "role": "political",
        "domain": "Political",
    },
    "P2": {
        "url": "https://nomos42-political-alpha-2.hf.space/api/status",
        "role": "political",
        "domain": "Political",
    },
    # P3/P4 removed 2026-04-03 — spaces never existed on HF
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

# Current snapshot: island_id -> dict
current_status = {}

# History: island_id -> deque of (timestamp_str, best_brier)
brier_history = {iid: deque(maxlen=HISTORY_SIZE) for iid in ISLANDS}

# All-time records per island
atr_brier = {}  # island_id -> best brier ever seen

# Logs
convergence_log = deque(maxlen=500)
pollination_log = deque(maxlen=200)
recommendation_log = deque(maxlen=200)
alert_log = deque(maxlen=100)

lock = threading.Lock()

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def send_telegram(message: str) -> None:
    """Send a Telegram message. Fails silently if token is missing."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        payload = json.dumps(
            {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            }
        ).encode("utf-8")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------


def fetch_island_status(island_id: str, cfg: dict) -> dict | None:
    """Fetch /api/status for one island. Returns parsed JSON or None."""
    try:
        req = urllib.request.Request(cfg["url"], method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except Exception:
        return None


def poll_all_islands() -> None:
    """Poll every island, update state, generate recommendations & alerts."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for island_id, cfg in ISLANDS.items():
        data = fetch_island_status(island_id, cfg)

        with lock:
            if data is None:
                # Island appears crashed
                prev = current_status.get(island_id)
                if prev and prev.get("_status") != "DOWN":
                    msg = f"[ALERT] {island_id} ({cfg['role']}) is DOWN at {now_str}"
                    alert_log.append(msg)
                    send_telegram(f"<b>Island DOWN</b>\n{island_id} ({cfg['role']})")
                current_status[island_id] = {
                    "_status": "DOWN",
                    "_role": cfg["role"],
                    "_domain": cfg["domain"],
                    "_last_check": now_str,
                }
                continue

            # Enrich with metadata
            data["_status"] = "UP"
            data["_role"] = cfg["role"]
            data["_domain"] = cfg["domain"]
            data["_last_check"] = now_str

            best_brier = data.get("best_brier")
            generation = data.get("generation", "?")
            stagnation = data.get("stagnation", 0)
            features = data.get("best_features", data.get("features", "?"))
            best_model = data.get("best_model", "?")

            # Record history
            if best_brier is not None:
                try:
                    bb = float(best_brier)
                    brier_history[island_id].append((now_str, bb))

                    # ATR check
                    prev_atr = atr_brier.get(island_id)
                    if prev_atr is None or bb < prev_atr:
                        if prev_atr is not None:
                            msg = (
                                f"[ATR] {island_id} new ATR: {bb:.5f} "
                                f"(prev {prev_atr:.5f}) at {now_str}"
                            )
                            convergence_log.append(msg)
                            alert_log.append(msg)
                            send_telegram(
                                f"<b>New ATR!</b>\n{island_id}: {bb:.5f} "
                                f"(was {prev_atr:.5f})"
                            )
                        atr_brier[island_id] = bb
                except (ValueError, TypeError):
                    pass

            # Stagnation alert
            try:
                stag = int(stagnation)
                if stag > 30:
                    msg = (
                        f"[STAGNATION] {island_id} stagnation={stag} at {now_str}"
                    )
                    alert_log.append(msg)
                    send_telegram(
                        f"<b>High Stagnation</b>\n{island_id}: {stag} generations"
                    )
            except (ValueError, TypeError):
                pass

            current_status[island_id] = data

    # Generate recommendations after polling all islands
    _generate_recommendations(now_str)


def _generate_recommendations(now_str: str) -> None:
    """Analyze current state and produce recommendations."""
    with lock:
        recs = []

        # Stagnation checks
        for iid, data in current_status.items():
            if data.get("_status") == "DOWN":
                recs.append(
                    f"[{now_str}] CRITICAL: {iid} is DOWN. Check Space logs."
                )
                continue

            stag = data.get("stagnation", 0)
            try:
                stag = int(stag)
            except (ValueError, TypeError):
                stag = 0

            if stag > 20:
                recs.append(
                    f"[{now_str}] {iid}: stagnation={stag} > 20. "
                    f"Recommend diversity injection (reset 30% of population)."
                )

            # Feature bloat
            feats = data.get("best_features", data.get("features", 0))
            try:
                feats = int(feats)
            except (ValueError, TypeError):
                feats = 0

            if feats > 150:
                recs.append(
                    f"[{now_str}] {iid}: features={feats} > 150. "
                    f"Warn: feature bloat may hurt generalization."
                )

        # Monoculture check — group by domain
        for domain in ("NBA", "Political"):
            domain_islands = {
                iid: d
                for iid, d in current_status.items()
                if d.get("_domain") == domain and d.get("_status") == "UP"
            }
            if len(domain_islands) >= 2:
                models = set()
                for d in domain_islands.values():
                    m = d.get("best_model", "?")
                    if m and m != "?":
                        models.add(m)
                if len(models) == 1:
                    recs.append(
                        f"[{now_str}] MONOCULTURE WARNING ({domain}): "
                        f"All islands converged to {models.pop()}. "
                        f"Inject alternative model types."
                    )

        # Brier improvement tracking
        for iid in ISLANDS:
            hist = brier_history[iid]
            if len(hist) >= 2:
                prev_bb = hist[-2][1]
                curr_bb = hist[-1][1]
                if curr_bb < prev_bb:
                    delta = prev_bb - curr_bb
                    recs.append(
                        f"[{now_str}] {iid}: Brier improved by {delta:.5f} "
                        f"({prev_bb:.5f} -> {curr_bb:.5f})."
                    )

        for r in recs:
            recommendation_log.append(r)


# ---------------------------------------------------------------------------
# Background thread
# ---------------------------------------------------------------------------

_monitor_running = False


def monitor_loop() -> None:
    """Background polling loop."""
    global _monitor_running
    _monitor_running = True
    while _monitor_running:
        try:
            poll_all_islands()
        except Exception as e:
            with lock:
                alert_log.append(
                    f"[ERROR] Monitor loop exception: {e}"
                )
        time.sleep(POLL_INTERVAL_SEC)


def start_monitor() -> None:
    """Start the background monitor thread (once)."""
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# UI builders
# ---------------------------------------------------------------------------


def build_dashboard_table() -> str:
    """Build HTML table for the Evolution Dashboard tab."""
    with lock:
        snapshot = dict(current_status)

    if not snapshot:
        return (
            "<div style='text-align:center; padding:40px; color:#888;'>"
            "<h3>Waiting for first poll...</h3>"
            "<p>The monitor polls every 10 minutes. Data will appear shortly.</p>"
            "</div>"
        )

    rows = []
    # Order: S10-S15, P1-P4
    ordered = ["S10", "S11", "S12", "S13", "S14", "S15", "P1", "P2", "P3", "P4"]

    for iid in ordered:
        data = snapshot.get(iid)
        if data is None:
            continue

        status = data.get("_status", "?")
        role = data.get("_role", "?")
        domain = data.get("_domain", "?")

        if status == "DOWN":
            rows.append(
                f"<tr style='background:#2d1111;'>"
                f"<td><b>{iid}</b> <span style='color:#666;'>({domain})</span></td>"
                f"<td>{role}</td>"
                f"<td>-</td><td>-</td><td>-</td><td>-</td>"
                f"<td>-</td><td>-</td>"
                f"<td style='color:#ff4444;font-weight:bold;'>DOWN</td>"
                f"</tr>"
            )
            continue

        gen = data.get("generation", "?")
        best_brier = data.get("best_brier", "?")
        best_model = data.get("best_model", "?")
        features = data.get("best_features", data.get("features", "?"))
        stagnation = data.get("stagnation", "?")
        pop = data.get("population_size", data.get("pop_size", "?"))

        # Format brier
        try:
            bb_val = float(best_brier)
            brier_str = f"{bb_val:.5f}"
        except (ValueError, TypeError):
            brier_str = str(best_brier)

        # Stagnation color
        try:
            stag_val = int(stagnation)
            if stag_val > 20:
                stag_color = "#ff4444"
            elif stag_val >= 10:
                stag_color = "#ffaa00"
            else:
                stag_color = "#44ff44"
            stag_str = f"<span style='color:{stag_color};font-weight:bold;'>{stag_val}</span>"
        except (ValueError, TypeError):
            stag_str = str(stagnation)

        # Feature warning
        try:
            feat_val = int(features)
            if feat_val > 150:
                feat_str = f"<span style='color:#ff4444;'>{feat_val}</span>"
            else:
                feat_str = str(feat_val)
        except (ValueError, TypeError):
            feat_str = str(features)

        rows.append(
            f"<tr>"
            f"<td><b>{iid}</b> <span style='color:#888;'>({domain})</span></td>"
            f"<td>{role}</td>"
            f"<td>{gen}</td>"
            f"<td><b>{brier_str}</b></td>"
            f"<td>{best_model}</td>"
            f"<td>{feat_str}</td>"
            f"<td>{stag_str}</td>"
            f"<td>{pop}</td>"
            f"<td style='color:#44ff44;'>UP</td>"
            f"</tr>"
        )

    header = (
        "<tr style='background:#222;'>"
        "<th>Island</th><th>Role</th><th>Gen</th>"
        "<th>Best Brier</th><th>Best Model</th><th>Features</th>"
        "<th>Stagnation</th><th>Pop</th><th>Status</th>"
        "</tr>"
    )

    last_poll = ""
    for iid in ordered:
        d = snapshot.get(iid, {})
        lc = d.get("_last_check")
        if lc:
            last_poll = lc
            break

    html = (
        f"<div style='margin-bottom:10px;color:#aaa;'>Last poll: {last_poll}</div>"
        f"<table style='width:100%;border-collapse:collapse;font-family:monospace;'>"
        f"<thead>{header}</thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        f"</table>"
        f"<style>"
        f"table td, table th {{ padding: 8px 12px; border-bottom: 1px solid #333; text-align: left; }}"
        f"table tr:hover {{ background: #1a1a2e; }}"
        f"</style>"
    )
    return html


def build_convergence_log() -> str:
    """Build convergence text log showing Brier history per island."""
    with lock:
        hist_copy = {iid: list(dq) for iid, dq in brier_history.items()}
        conv_copy = list(convergence_log)

    lines = []
    lines.append("=" * 70)
    lines.append("BRIER CONVERGENCE HISTORY (last 24h)")
    lines.append("=" * 70)

    ordered = ["S10", "S11", "S12", "S13", "S14", "S15", "P1", "P2", "P3", "P4"]
    for iid in ordered:
        entries = hist_copy.get(iid, [])
        if not entries:
            lines.append(f"\n{iid} ({ISLANDS[iid]['role']}): No data yet")
            continue

        lines.append(f"\n{iid} ({ISLANDS[iid]['role']}):")
        # Show last 20 data points
        recent = entries[-20:]
        for ts, bb in recent:
            lines.append(f"  {ts}  Brier={bb:.5f}")

        # Show trend
        if len(entries) >= 2:
            first_bb = entries[0][1]
            last_bb = entries[-1][1]
            delta = last_bb - first_bb
            direction = "improved" if delta < 0 else "worsened" if delta > 0 else "unchanged"
            lines.append(f"  Trend: {direction} by {abs(delta):.5f}")

    if conv_copy:
        lines.append("\n" + "=" * 70)
        lines.append("CONVERGENCE EVENTS")
        lines.append("=" * 70)
        for entry in conv_copy[-50:]:
            lines.append(entry)

    return "\n".join(lines)


def build_pollination_log() -> str:
    """Build cross-pollination log."""
    with lock:
        entries = list(pollination_log)

    if not entries:
        return (
            "No cross-pollination actions recorded yet.\n\n"
            "Cross-pollination occurs when:\n"
            "- A stagnated island receives migrants from a better-performing island\n"
            "- The coordinator triggers a diversity injection\n"
            "- Manual migration is initiated via the Brain agent\n\n"
            "This log will populate as the coordinator takes actions."
        )

    return "\n".join(entries)


def build_recommendations() -> str:
    """Build recommendations text."""
    with lock:
        recs = list(recommendation_log)
        alerts = list(alert_log)

    lines = []

    if alerts:
        lines.append("=" * 70)
        lines.append("ALERTS")
        lines.append("=" * 70)
        for a in alerts[-20:]:
            lines.append(a)
        lines.append("")

    if recs:
        lines.append("=" * 70)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 70)
        for r in recs[-30:]:
            lines.append(r)
    else:
        lines.append("No recommendations generated yet.")
        lines.append("Recommendations appear after the first polling cycle.")
        lines.append("")
        lines.append("The coordinator checks for:")
        lines.append("  - Stagnation > 20 generations -> diversity injection")
        lines.append("  - Brier improvements -> logged")
        lines.append("  - Model monoculture -> warns if all islands use same model")
        lines.append("  - Feature bloat -> warns if features > 150")
        lines.append("  - Island crashes -> critical alert")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gradio App
# ---------------------------------------------------------------------------


def refresh_dashboard():
    return build_dashboard_table()


def refresh_convergence():
    return build_convergence_log()


def refresh_pollination():
    return build_pollination_log()


def refresh_recommendations():
    return build_recommendations()


def build_app() -> gr.Blocks:
    theme = gr.themes.Default()

    with gr.Blocks(
        title="Nomos42 Island Coordinator",
        theme=theme,
        css="""
        .gradio-container { max-width: 1200px; }
        textarea { font-family: monospace !important; font-size: 13px !important; }
        """,
    ) as app:
        gr.Markdown(
            "# Nomos42 Island Coordinator\n"
            "Monitoring 6 NBA + 4 Political evolution islands. "
            "Polls every 10 minutes. Auto-refreshes every 60 seconds."
        )

        with gr.Tabs():
            with gr.Tab("Evolution Dashboard"):
                dashboard_html = gr.HTML(
                    value=build_dashboard_table,
                    every=60,
                )

            with gr.Tab("Convergence"):
                convergence_text = gr.Textbox(
                    value=build_convergence_log,
                    every=60,
                    label="Brier Convergence Log",
                    lines=30,
                    max_lines=50,
                    interactive=False,
                )

            with gr.Tab("Cross-Pollination Log"):
                pollination_text = gr.Textbox(
                    value=build_pollination_log,
                    every=60,
                    label="Migration & Cross-Pollination Actions",
                    lines=20,
                    max_lines=40,
                    interactive=False,
                )

            with gr.Tab("Recommendations"):
                recommendations_text = gr.Textbox(
                    value=build_recommendations,
                    every=60,
                    label="AI Recommendations & Alerts",
                    lines=25,
                    max_lines=40,
                    interactive=False,
                )

        gr.Markdown(
            "<div style='text-align:center;color:#666;margin-top:20px;'>"
            "Nomos42 Island Coordinator v1.0 | "
            "6 NBA islands (S10-S15) + 4 Political islands (P1-P4) | "
            "Polling interval: 10min | History: 24h"
            "</div>"
        )

    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Start background monitor on import
start_monitor()

app = build_app()

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
