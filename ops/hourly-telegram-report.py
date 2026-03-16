#!/usr/bin/env python3
"""Hourly Telegram status report — sends progress update to admin every hour.

Usage:
    source .env.local
    python3 ops/hourly-telegram-report.py --daemon
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk")
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "6582544948"))
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
INTERVAL = 3600  # 1 hour

SPACES = [
    ("S1", "https://lbjlincoln-nomos-rag-engine.hf.space"),
    ("S3", "https://lbjlincoln-nomos-rag-engine-3.hf.space"),
    ("S5", "https://lbjlincoln-nomos-rag-engine-5.hf.space"),
    ("S7", "https://lbjlincoln-nomos-rag-engine-7.hf.space"),
    ("S9", "https://lbjlincoln-nomos-rag-engine-9.hf.space"),
    ("OpenClaw", "https://nomos42-nomos-worker-2.hf.space"),
    ("Lightning", "https://8000-01kkj0hqg9fq7twz8065b3e94m.cloudspaces.litng.ai"),
]

SITES = [
    ("Expert", "https://nomos42.vercel.app"),
    ("Satellite", "https://nomos42.vercel.app/satellite"),
    ("Marketplace", "https://nomos42.vercel.app/marketplace"),
    ("Factory", "https://nomos42.vercel.app/factory"),
    ("Vault", "https://nomos42.vercel.app/vault"),
    ("Dashboard", "https://nomos42.vercel.app/dashboard"),
    ("NBA", "https://nomos42.vercel.app/nba"),
]


def send_telegram(text):
    """Send message to admin via Telegram."""
    data = json.dumps({"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(
        f"{API_URL}/sendMessage", data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception:
        # Retry without markdown
        data2 = json.dumps({"chat_id": ADMIN_ID, "text": text}).encode()
        req2 = urllib.request.Request(
            f"{API_URL}/sendMessage", data2,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req2, timeout=30)
        except Exception as e:
            print(f"  Telegram send failed: {e}")


def check_url(url, timeout=15):
    """Check if a URL is reachable. Returns (status_code, latency_ms)."""
    try:
        start = time.time()
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.time() - start) * 1000)
            return resp.status, latency
    except Exception:
        return 0, -1


def get_daemons():
    """Get list of running daemons."""
    try:
        r = subprocess.run(
            "ps aux --no-headers | grep -E 'python3.*(ops/|eval/)' | grep -v grep | awk '{print $NF}'",
            shell=True, capture_output=True, text=True, timeout=10,
        )
        return [line.strip().split("/")[-1] for line in r.stdout.strip().split("\n") if line.strip()]
    except Exception:
        return []


def get_health():
    """Read health-status.json."""
    try:
        with open("/home/termius/mon-ipad/data/health-status.json") as f:
            return json.load(f)
    except Exception:
        return {}


def get_eval_latest():
    """Get latest eval results."""
    try:
        with open("/home/termius/mon-ipad/data/eval/parallel-eval-latest.json") as f:
            data = json.load(f)
            return data
    except Exception:
        return {}


def build_report():
    """Build the hourly status report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"*NOMOS HOURLY REPORT*", f"_{now}_\n"]

    # Infrastructure
    lines.append("*Infrastructure:*")
    for name, url in SPACES:
        code, latency = check_url(url)
        if code >= 200 and code < 400:
            lines.append(f"  + {name}: UP ({latency}ms)")
        else:
            lines.append(f"  x {name}: DOWN ({code})")

    # Sites
    lines.append("\n*Sites:*")
    for name, url in SITES:
        code, latency = check_url(url)
        if code >= 200 and code < 400:
            lines.append(f"  + {name}: LIVE ({latency}ms)")
        else:
            lines.append(f"  x {name}: DOWN ({code})")

    # Pipelines
    health = get_health()
    if health.get("pipelines"):
        lines.append("\n*Pipelines:*")
        for name, info in health["pipelines"].items():
            rate = info.get("success_rate", 0)
            total = info.get("total", 0)
            if name in ("Unknown", "Auto-Healer"):
                continue
            target = {"Standard": 90, "Graph": 75, "Quant": 95, "Orchestrator": 85}.get(name, 80)
            gap = "OK" if rate >= target else f"-{target - rate:.0f}%"
            lines.append(f"  {name}: {rate:.0f}% ({total} runs) [{gap}]")

    # Daemons
    daemons = get_daemons()
    lines.append(f"\n*Daemons:* {len(daemons)} running")
    for d in daemons[:8]:
        lines.append(f"  - {d}")

    # Eval latest
    eval_data = get_eval_latest()
    if eval_data.get("accuracy"):
        lines.append(f"\n*Latest Eval:* {eval_data['accuracy']}%")

    # Objectives status
    lines.append("\n*Objectives:*")
    lines.append("  Standard: 70.7% -> 90% target")
    lines.append("  Graph: 45.9% -> 75% target")
    lines.append("  Vectors: ~82K -> 100K target")
    lines.append("  Sites: 6/6 live on nomos42.vercel.app")

    return "\n".join(lines)


def main():
    daemon = "--daemon" in sys.argv
    print(f"=== HOURLY TELEGRAM REPORTER ===")
    print(f"Admin: {ADMIN_ID}")
    print(f"Interval: {INTERVAL}s")
    print(f"Daemon: {daemon}")

    while True:
        try:
            report = build_report()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending report...")
            send_telegram(report)
            print(f"  Report sent ({len(report)} chars)")
        except Exception as e:
            print(f"  Error: {e}")

        if not daemon:
            break

        print(f"  Next report in {INTERVAL}s")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
