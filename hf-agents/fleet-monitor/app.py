"""
Nomos42 Fleet Monitor — I1 Agent
Monitors all HF Spaces, VM data server, and Telegram bots.
Sends alerts via Telegram when services go down.
"""

import json
import os
import ssl
import threading
import time
import traceback
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL_SEC = 300  # 5 minutes
MAX_HISTORY = 288  # 24 h at 5-min intervals
ALERT_CHAT_ID = "6582544948"
DOWN_ALERT_THRESHOLD_SEC = 600  # 10 minutes

# HF Spaces to monitor  (slug used for both /api/status and runtime API)
HF_SPACES = {
    # NBA evolution islands
    "Nomos42/nba-quant":   {"type": "NBA",       "url": "nomos42-nba-quant.hf.space"},
    "Nomos42/nba-quant-2": {"type": "NBA",       "url": "nomos42-nba-quant-2.hf.space"},
    "Nomos42/nba-evo-3":   {"type": "NBA",       "url": "nomos42-nba-evo-3.hf.space"},
    "Nomos42/nba-evo-4":   {"type": "NBA",       "url": "nomos42-nba-evo-4.hf.space"},
    "Nomos42/nba-evo-5":   {"type": "NBA",       "url": "nomos42-nba-evo-5.hf.space"},
    "Nomos42/nba-evo-6":   {"type": "NBA",       "url": "nomos42-nba-evo-6.hf.space"},
    "LBJLincoln26/nba-evo-s16": {"type": "NBA", "url": "lbjlincoln26-nba-evo-s16.hf.space"},
    "LBJLincoln26/nba-evo-s17": {"type": "NBA", "url": "lbjlincoln26-nba-evo-s17.hf.space"},
    # Political alpha islands
    "Nomos42/political-alpha":   {"type": "Political", "url": "nomos42-political-alpha.hf.space"},
    "Nomos42/political-alpha-2": {"type": "Political", "url": "nomos42-political-alpha-2.hf.space"},
    # P3/P4 removed 2026-04-03 — spaces never existed on HF
    # Brain
    "Nomos42/nomos42-brain":     {"type": "Brain",     "url": "nomos42-nomos42-brain.hf.space"},
}

VM_DATA_SERVER = "http://nomos42.duckdns.org:7860"

TELEGRAM_BOTS = {
    "Nomos42Bot":          "TELEGRAM_BOT_TOKEN",
    "NomosNBABot":         "NOMOS_NBA_BOT_TOKEN",
    "StupidPoliticalBot":  "STUPID_POLITICAL_BOT_TOKEN",
    "Forge42Bot":          "FORGE_BOT_TOKEN",
}

# ---------------------------------------------------------------------------
# Shared state (guarded by lock)
# ---------------------------------------------------------------------------

state_lock = threading.Lock()
check_history: list[dict] = []       # list of full snapshots (max MAX_HISTORY)
alert_log: list[dict] = []           # list of alert events
down_since: dict[str, float] = {}    # service_name -> first-seen-down epoch
alerted_services: set[str] = set()   # services we already alerted about

# ---------------------------------------------------------------------------
# SSL context that doesn't verify (some HF endpoints have cert issues)
# ---------------------------------------------------------------------------

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _fetch_json(url: str, timeout: int = 10) -> dict | None:
    """GET a URL, return parsed JSON or None on any error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-Fleet-Monitor/1.0"})
        ctx = _ssl_ctx if url.startswith("https") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _send_telegram(message: str) -> bool:
    """Send a Telegram message via TELEGRAM_BOT_TOKEN."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return False
    try:
        payload = json.dumps({"chat_id": ALERT_CHAT_ID, "text": message, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42-Fleet-Monitor/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


def probe_hf_space(slug: str, info: dict) -> dict:
    """Probe one HF Space via its public /api/status AND the HF runtime API."""
    base_url = info["url"]
    result = {
        "service": slug,
        "type": info["type"],
        "status": "UNKNOWN",
        "brier_gen": "--",
        "details": "",
    }

    # 1. Try the space's own /api/status endpoint
    api_data = _fetch_json(f"https://{base_url}/api/status", timeout=10)
    if api_data:
        result["status"] = "UP"
        # Extract Brier / generation if present
        brier = api_data.get("best_brier") or api_data.get("brier")
        gen = api_data.get("generation") or api_data.get("gen")
        parts = []
        if brier is not None:
            try:
                parts.append(f"Brier {float(brier):.5f}")
            except (ValueError, TypeError):
                parts.append(f"Brier {brier}")
        if gen is not None:
            parts.append(f"Gen {gen}")
        result["brier_gen"] = " | ".join(parts) if parts else "--"
        result["details"] = json.dumps(api_data)[:200]
    else:
        result["status"] = "DOWN"
        result["details"] = "No response from /api/status"

    # 2. Check HF runtime stage via API
    hf_token = os.environ.get("HF_TOKEN", "")
    runtime_url = f"https://huggingface.co/api/spaces/{slug}"
    headers = {"User-Agent": "Nomos42-Fleet-Monitor/1.0"}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"
    try:
        req = urllib.request.Request(runtime_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx) as resp:
            runtime_data = json.loads(resp.read().decode())
            stage = runtime_data.get("runtime", {}).get("stage", "UNKNOWN")
            result["runtime_stage"] = stage
            # Override status if runtime says something specific
            if stage in ("RUNNING", "RUNNING_BUILDING"):
                if result["status"] == "UNKNOWN":
                    result["status"] = "UP"
            elif stage in ("PAUSED", "STOPPED", "SLEEPING"):
                result["status"] = stage
            elif stage in ("BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
                result["status"] = "ERROR"
                result["details"] = f"Runtime stage: {stage}"
    except Exception:
        result["runtime_stage"] = "UNKNOWN"

    return result


def probe_vm() -> dict:
    """Probe the VM data server."""
    result = {
        "service": "VM Data Server",
        "type": "Infra",
        "status": "UNKNOWN",
        "brier_gen": "--",
        "details": "",
    }
    try:
        req = urllib.request.Request(VM_DATA_SERVER, headers={"User-Agent": "Nomos42-Fleet-Monitor/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result["status"] = "UP"
            result["details"] = f"HTTP {resp.status}"
    except Exception as e:
        result["status"] = "DOWN"
        result["details"] = str(e)[:150]
    return result


def probe_telegram_bot(name: str, token_env: str) -> dict:
    """Probe a Telegram bot via getMe."""
    result = {
        "service": f"Bot @{name}",
        "type": "Telegram",
        "status": "UNKNOWN",
        "brier_gen": "--",
        "details": "",
    }
    token = os.environ.get(token_env, "")
    if not token:
        result["status"] = "NO_TOKEN"
        result["details"] = f"Env {token_env} not set"
        return result
    data = _fetch_json(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
    if data and data.get("ok"):
        result["status"] = "UP"
        bot_info = data.get("result", {})
        result["details"] = f"@{bot_info.get('username', '?')}"
    else:
        result["status"] = "DOWN"
        result["details"] = "getMe failed"
    return result


# ---------------------------------------------------------------------------
# Full monitoring cycle
# ---------------------------------------------------------------------------


def run_one_cycle() -> dict:
    """Run a full monitoring cycle, return snapshot dict."""
    now = _utcnow()
    epoch_now = time.time()
    services: list[dict] = []

    # HF Spaces
    for slug, info in HF_SPACES.items():
        try:
            services.append(probe_hf_space(slug, info))
        except Exception as e:
            services.append({
                "service": slug, "type": info["type"],
                "status": "ERROR", "brier_gen": "--",
                "details": f"Probe exception: {e}",
            })

    # VM
    try:
        services.append(probe_vm())
    except Exception as e:
        services.append({
            "service": "VM Data Server", "type": "Infra",
            "status": "ERROR", "brier_gen": "--",
            "details": f"Probe exception: {e}",
        })

    # Telegram bots
    for name, token_env in TELEGRAM_BOTS.items():
        try:
            services.append(probe_telegram_bot(name, token_env))
        except Exception as e:
            services.append({
                "service": f"Bot @{name}", "type": "Telegram",
                "status": "ERROR", "brier_gen": "--",
                "details": f"Probe exception: {e}",
            })

    # Compute uptime %
    for svc in services:
        svc["last_check"] = now
        svc["uptime_pct"] = _compute_uptime(svc["service"])

    snapshot = {"timestamp": now, "epoch": epoch_now, "services": services}

    # Process alerts
    _process_alerts(services, epoch_now)

    # Store
    with state_lock:
        check_history.append(snapshot)
        if len(check_history) > MAX_HISTORY:
            check_history[:] = check_history[-MAX_HISTORY:]

    return snapshot


def _compute_uptime(service_name: str) -> str:
    """Compute uptime % from history for a given service."""
    with state_lock:
        history = list(check_history)
    if not history:
        return "N/A"
    up_count = 0
    total = 0
    for snap in history:
        for svc in snap["services"]:
            if svc["service"] == service_name:
                total += 1
                if svc["status"] in ("UP", "RUNNING"):
                    up_count += 1
                break
    if total == 0:
        return "N/A"
    return f"{100 * up_count / total:.1f}%"


def _process_alerts(services: list[dict], epoch_now: float):
    """Check for alert conditions and send Telegram notifications."""
    global down_since, alerted_services

    down_services = []
    for svc in services:
        name = svc["service"]
        is_down = svc["status"] in ("DOWN", "ERROR", "RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR")

        if is_down:
            if name not in down_since:
                down_since[name] = epoch_now
            down_services.append(name)

            # Alert if down > threshold and not yet alerted
            duration = epoch_now - down_since[name]
            if duration >= DOWN_ALERT_THRESHOLD_SEC and name not in alerted_services:
                minutes = int(duration / 60)
                msg = (
                    f"<b>FLEET ALERT</b>\n"
                    f"Service <b>{name}</b> has been DOWN for {minutes} min.\n"
                    f"Status: {svc['status']}\n"
                    f"Details: {svc.get('details', 'N/A')[:100]}\n"
                    f"Time: {_utcnow()}"
                )
                sent = _send_telegram(msg)
                alerted_services.add(name)
                with state_lock:
                    alert_log.append({
                        "timestamp": _utcnow(),
                        "service": name,
                        "type": "DOWN_>10MIN",
                        "message": f"Down for {minutes} min",
                        "telegram_sent": sent,
                    })
        else:
            # Service recovered
            if name in down_since:
                if name in alerted_services:
                    duration = epoch_now - down_since[name]
                    minutes = int(duration / 60)
                    msg = (
                        f"<b>FLEET RECOVERY</b>\n"
                        f"Service <b>{name}</b> is back UP after {minutes} min.\n"
                        f"Time: {_utcnow()}"
                    )
                    _send_telegram(msg)
                    with state_lock:
                        alert_log.append({
                            "timestamp": _utcnow(),
                            "service": name,
                            "type": "RECOVERED",
                            "message": f"Back up after {minutes} min",
                            "telegram_sent": True,
                        })
                del down_since[name]
                alerted_services.discard(name)

    # Multi-down alert: >2 spaces DOWN simultaneously
    down_spaces = [s for s in down_services if not s.startswith("Bot ") and s != "VM Data Server"]
    if len(down_spaces) > 2:
        alert_key = "MULTI_DOWN"
        if alert_key not in alerted_services:
            msg = (
                f"<b>FLEET CRITICAL</b>\n"
                f"{len(down_spaces)} spaces DOWN simultaneously:\n"
                + "\n".join(f"  - {s}" for s in down_spaces)
                + f"\nTime: {_utcnow()}"
            )
            sent = _send_telegram(msg)
            alerted_services.add(alert_key)
            with state_lock:
                alert_log.append({
                    "timestamp": _utcnow(),
                    "service": "FLEET",
                    "type": "MULTI_DOWN",
                    "message": f"{len(down_spaces)} spaces down",
                    "telegram_sent": sent,
                })
    else:
        alerted_services.discard("MULTI_DOWN")

    # VM down alert
    for svc in services:
        if svc["service"] == "VM Data Server" and svc["status"] in ("DOWN", "ERROR"):
            vm_key = "VM_DOWN"
            if vm_key not in alerted_services:
                msg = (
                    f"<b>FLEET ALERT</b>\n"
                    f"VM Data Server is unreachable.\n"
                    f"Details: {svc.get('details', 'N/A')[:100]}\n"
                    f"Time: {_utcnow()}"
                )
                sent = _send_telegram(msg)
                alerted_services.add(vm_key)
                with state_lock:
                    alert_log.append({
                        "timestamp": _utcnow(),
                        "service": "VM Data Server",
                        "type": "VM_UNREACHABLE",
                        "message": "VM data server down",
                        "telegram_sent": sent,
                    })
        elif svc["service"] == "VM Data Server" and svc["status"] == "UP":
            if "VM_DOWN" in alerted_services:
                msg = (
                    f"<b>FLEET RECOVERY</b>\n"
                    f"VM Data Server is back online.\n"
                    f"Time: {_utcnow()}"
                )
                _send_telegram(msg)
                alerted_services.discard("VM_DOWN")
                with state_lock:
                    alert_log.append({
                        "timestamp": _utcnow(),
                        "service": "VM Data Server",
                        "type": "VM_RECOVERED",
                        "message": "VM data server back up",
                        "telegram_sent": True,
                    })


# ---------------------------------------------------------------------------
# Background monitoring thread
# ---------------------------------------------------------------------------


def _monitor_loop():
    """Background thread that runs monitoring cycles every POLL_INTERVAL_SEC."""
    while True:
        try:
            run_one_cycle()
        except Exception:
            traceback.print_exc()
        time.sleep(POLL_INTERVAL_SEC)


monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
monitor_thread.start()

# Run first cycle immediately so we have data at startup
try:
    run_one_cycle()
except Exception:
    traceback.print_exc()

# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

import gradio as gr


def get_status_table() -> str:
    """Return a Markdown table of current fleet status."""
    with state_lock:
        if not check_history:
            return "No data yet. First check cycle in progress..."
        latest = check_history[-1]

    lines = [
        "| Service | Type | Status | Brier / Gen | Last Check | Uptime% |",
        "|---------|------|--------|-------------|------------|---------|",
    ]
    for svc in latest["services"]:
        status = svc["status"]
        # Add visual indicator
        if status == "UP":
            indicator = "UP"
        elif status in ("DOWN", "ERROR", "RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR"):
            indicator = "DOWN"
        elif status in ("PAUSED", "STOPPED", "SLEEPING"):
            indicator = status
        elif status == "NO_TOKEN":
            indicator = "NO TOKEN"
        else:
            indicator = status

        lines.append(
            f"| {svc['service']} | {svc['type']} | {indicator} "
            f"| {svc.get('brier_gen', '--')} | {svc.get('last_check', '--')} "
            f"| {svc.get('uptime_pct', 'N/A')} |"
        )

    # Summary line
    total = len(latest["services"])
    up = sum(1 for s in latest["services"] if s["status"] in ("UP", "RUNNING"))
    lines.append("")
    lines.append(f"**Fleet: {up}/{total} services UP** | Last cycle: {latest['timestamp']}")

    return "\n".join(lines)


def get_alerts_log() -> str:
    """Return alert history as Markdown."""
    with state_lock:
        alerts = list(alert_log)

    if not alerts:
        return "No alerts recorded. All systems nominal."

    lines = [
        "| Time | Service | Type | Message | TG Sent |",
        "|------|---------|------|---------|---------|",
    ]
    # Show most recent first, max 50
    for a in reversed(alerts[-50:]):
        tg = "Yes" if a.get("telegram_sent") else "No"
        lines.append(
            f"| {a['timestamp']} | {a['service']} | {a['type']} "
            f"| {a['message']} | {tg} |"
        )
    return "\n".join(lines)


def get_health_history() -> str:
    """Return last 24h of checks as JSON."""
    with state_lock:
        history = list(check_history)

    if not history:
        return json.dumps({"message": "No history yet"}, indent=2)

    # Slim down for readability: just timestamp + service statuses
    slim = []
    for snap in history[-288:]:
        entry = {"timestamp": snap["timestamp"], "services": {}}
        for svc in snap["services"]:
            entry["services"][svc["service"]] = {
                "status": svc["status"],
                "brier_gen": svc.get("brier_gen", "--"),
            }
        slim.append(entry)

    return json.dumps(slim, indent=2)


def build_status_summary() -> str:
    """One-line summary for the auto-refresh Textbox."""
    with state_lock:
        if not check_history:
            return "Loading..."
        latest = check_history[-1]
    total = len(latest["services"])
    up = sum(1 for s in latest["services"] if s["status"] in ("UP", "RUNNING"))
    return f"Fleet: {up}/{total} UP | Last check: {latest['timestamp']}"


def api_status() -> dict:
    """Return current fleet snapshot for API consumers."""
    with state_lock:
        if not check_history:
            return {"status": "loading", "services": []}
        latest = check_history[-1]
    return latest


# ---------------------------------------------------------------------------
# Gradio App
# ---------------------------------------------------------------------------

with gr.Blocks(
    theme=gr.themes.Default(),
    title="Nomos42 Fleet Monitor",
    css="""
    .status-header { text-align: center; margin-bottom: 10px; }
    .refresh-note { font-size: 0.85em; color: #666; text-align: center; }
    """,
) as app:

    gr.Markdown("# Nomos42 Fleet Monitor", elem_classes=["status-header"])
    gr.Markdown(
        "Monitoring 11 HF Spaces + VM + 4 Telegram Bots | "
        "Polls every 5 min | Alerts via Telegram",
        elem_classes=["refresh-note"],
    )

    # Auto-refresh summary line
    summary_box = gr.Textbox(
        label="Fleet Summary",
        value=build_status_summary,
        every=60,
        interactive=False,
    )

    with gr.Tabs():
        # Tab 1: Fleet Status
        with gr.Tab("Fleet Status"):
            status_md = gr.Markdown(value=get_status_table)
            refresh_btn = gr.Button("Refresh Now")
            refresh_btn.click(fn=get_status_table, inputs=None, outputs=status_md)

        # Tab 2: Alerts
        with gr.Tab("Alerts"):
            alerts_md = gr.Markdown(value=get_alerts_log)
            refresh_alerts_btn = gr.Button("Refresh Alerts")
            refresh_alerts_btn.click(fn=get_alerts_log, inputs=None, outputs=alerts_md)

        # Tab 3: Health History
        with gr.Tab("Health History"):
            history_json = gr.Code(
                value=get_health_history,
                language="json",
                label="Last 24h Checks (JSON)",
            )
            refresh_history_btn = gr.Button("Refresh History")
            refresh_history_btn.click(fn=get_health_history, inputs=None, outputs=history_json)

    # API endpoint for external consumers
    gr.Markdown("---")
    gr.Markdown("**API**: Use `/api/predict` to get current fleet snapshot.")

    # Hidden components for the API endpoint
    api_trigger = gr.Textbox(visible=False)
    api_output = gr.JSON(visible=False)
    api_trigger.change(fn=api_status, inputs=None, outputs=api_output, api_name="status")


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
