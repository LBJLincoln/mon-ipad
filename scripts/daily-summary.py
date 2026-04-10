#!/usr/bin/env python3
"""
Nomos42 Daily Summary — 1 Telegram message per day
====================================================
Sends a consolidated daily brief to @Nomos42 channel at 23:30 UTC.
Covers: NBA Brier, Political Brier, RGWA quality, infra health.

Cron: 30 23 * * *
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/lahargnedebartoli/mon-ipad")
NBA_AGENT = Path("/home/lahargnedebartoli/nomos-nba-agent")
POLITICAL = Path("/home/lahargnedebartoli/nomos-political-alpha")
RGWA = Path("/home/lahargnedebartoli/rgwa")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@Nomos42")
ADMIN_ID = os.environ.get("ADMIN_TELEGRAM_ID", "")


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def send_telegram(text: str) -> bool:
    if not BOT_TOKEN:
        print("No TELEGRAM_BOT_TOKEN — printing to stdout instead")
        print(text)
        return False

    target = ADMIN_ID or CHANNEL_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": target,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()

    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Telegram send failed: {e}")
        print(text)
        return False


def get_nba_status() -> dict:
    """NBA Quant AI status from various data files."""
    bankroll = read_json(ROOT / "data" / "nba-agent" / "bankroll-state.json")
    karpathy = read_json(ROOT / "data" / "karpathy" / "schedule-log.json")
    infra = read_json(ROOT / "data" / "infra-status.json")

    # Best Brier from karpathy or bankroll
    best_brier = karpathy.get("nba", {}).get("best_brier", "?")
    if best_brier == "?" or best_brier == "":
        best_brier = bankroll.get("brier_score", "?")

    # Island health from infra
    nba_islands = infra.get("nba_islands", {})
    healthy = sum(1 for v in nba_islands.values() if isinstance(v, dict) and v.get("status") == "running")
    total = max(len(nba_islands), 6)
    stagnant = sum(1 for v in nba_islands.values() if isinstance(v, dict) and v.get("stagnant_gens", 0) > 10)

    return {
        "brier": best_brier,
        "bankroll": bankroll.get("balance", "?"),
        "roi": bankroll.get("roi_pct", "?"),
        "islands_healthy": healthy,
        "islands_total": total,
        "islands_stagnant": stagnant,
        "karpathy_result": karpathy.get("nba", {}).get("result", "not_run"),
        "karpathy_iters": karpathy.get("nba", {}).get("iterations", 0),
    }


def get_political_status() -> dict:
    """Political Alpha status."""
    infra = read_json(ROOT / "data" / "infra-status.json")
    pol_islands = infra.get("political_islands", {})
    healthy = sum(1 for v in pol_islands.values() if isinstance(v, dict) and v.get("status") == "running")
    total = max(len(pol_islands), 4)

    karpathy = read_json(ROOT / "data" / "karpathy" / "schedule-log.json")

    return {
        "brier": karpathy.get("political", {}).get("best_brier", "?"),
        "islands_healthy": healthy,
        "islands_total": total,
        "karpathy_result": karpathy.get("political", {}).get("result", "not_run"),
    }


def get_rgwa_status() -> dict:
    """RGWA AI Art status."""
    karpathy = read_json(RGWA / "data" / "karpathy" / "rgwa-best-config.json")
    return {
        "quality": karpathy.get("best_score", "?"),
        "iterations": karpathy.get("total_iterations", 0),
    }


def get_infra_status() -> dict:
    """VM + spaces health."""
    try:
        import shutil
        disk = shutil.disk_usage("/")
        disk_pct = round(disk.used / disk.total * 100)
    except Exception:
        disk_pct = "?"

    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem_total = int([l for l in lines if "MemTotal" in l][0].split()[1]) // 1024
        mem_avail = int([l for l in lines if "MemAvailable" in l][0].split()[1]) // 1024
        mem_pct = round((mem_total - mem_avail) / mem_total * 100)
    except Exception:
        mem_pct = "?"

    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()[0]
    except Exception:
        load = "?"

    # Count running bots
    import subprocess
    try:
        ps = subprocess.check_output(["pgrep", "-f", "python3.*bot"], text=True)
        bots_running = len(ps.strip().split("\n"))
    except Exception:
        bots_running = "?"

    return {
        "disk_pct": disk_pct,
        "mem_pct": mem_pct,
        "load": load,
        "bots": bots_running,
    }


def build_message() -> str:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nba = get_nba_status()
    pol = get_political_status()
    rgwa = get_rgwa_status()
    infra = get_infra_status()

    # Build alerts
    alerts = []
    if isinstance(nba["islands_stagnant"], int) and nba["islands_stagnant"] > 0:
        alerts.append(f"- {nba['islands_stagnant']} NBA islands stagnant >10 gens")
    if isinstance(pol["islands_healthy"], int) and pol["islands_healthy"] < pol["islands_total"]:
        down = pol["islands_total"] - pol["islands_healthy"]
        alerts.append(f"- {down} Political spaces down")
    if isinstance(infra["disk_pct"], int) and infra["disk_pct"] > 85:
        alerts.append(f"- VM disk at {infra['disk_pct']}% — cleanup needed")
    if isinstance(infra["mem_pct"], int) and infra["mem_pct"] > 85:
        alerts.append(f"- VM memory at {infra['mem_pct']}% — under pressure")

    msg = f"""<b>NOMOS42 DAILY BRIEF — {date}</b>

<b>NBA QUANT</b>
  Brier: {nba['brier']} (target &lt;0.20)
  Karpathy: {nba['karpathy_iters']} iterations, {nba['karpathy_result']}
  Bankroll: ${nba['bankroll']} ({nba['roi']}% ROI)
  Islands: {nba['islands_healthy']}/{nba['islands_total']} running

<b>POLITICAL ALPHA</b>
  Brier: {pol['brier']}
  Karpathy: {pol['karpathy_result']}
  Islands: {pol['islands_healthy']}/{pol['islands_total']} running

<b>RGWA</b>
  Quality: {rgwa['quality']}
  Iterations: {rgwa['iterations']}

<b>INFRA</b>
  VM: CPU {infra['load']}, RAM {infra['mem_pct']}%, Disk {infra['disk_pct']}%
  Bots: {infra['bots']} running"""

    if alerts:
        msg += "\n\n<b>NEEDS ATTENTION:</b>\n" + "\n".join(alerts)

    return msg


if __name__ == "__main__":
    msg = build_message()
    sent = send_telegram(msg)
    status = "sent" if sent else "printed"
    print(f"Daily summary {status} at {datetime.now(timezone.utc).isoformat()}")
