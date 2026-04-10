#!/usr/bin/env python3
"""
NBA Agent Pilot — Control the NBA betting agent from mon-ipad
================================================================
Launches, monitors, and controls the autonomous NBA agent.
Reports status to Telegram.
"""

import json, os, sys, time, subprocess, urllib.request, ssl
from datetime import datetime, timezone
from pathlib import Path

NBA_DIR = Path("/home/lahargnedebartoli/nomos-nba-agents")
MON_IPAD = Path("/home/lahargnedebartoli/mon-ipad")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def send_telegram(msg):
    """Send message to Telegram."""
    if not TELEGRAM_CHAT_ID:
        print(f"[WARN] No TELEGRAM_CHAT_ID set")
        return
    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[WARN] Telegram send failed: {e}")


def get_nba_status():
    """Get current NBA agent status."""
    status = {
        "timestamp": ts(),
        "daemon_running": False,
        "bankroll": None,
        "last_backtest": None,
        "agents": {},
    }

    # Check daemon
    pid_file = NBA_DIR / "data" / "daemon.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        try:
            os.kill(int(pid), 0)
            status["daemon_running"] = True
            status["daemon_pid"] = int(pid)
        except (ProcessLookupError, ValueError):
            status["daemon_running"] = False

    # Check bankroll
    bankroll_dir = NBA_DIR / "data" / "bankroll"
    if bankroll_dir.exists():
        files = sorted(bankroll_dir.glob("daily-*.json"), reverse=True)
        if files:
            latest = json.loads(files[0].read_text())
            status["bankroll"] = {
                "current": latest.get("closing_bankroll", latest.get("bankroll")),
                "date": files[0].stem.replace("daily-", ""),
                "roi": latest.get("roi"),
            }

    # Check backtest
    results_dir = NBA_DIR / "data" / "results"
    if results_dir.exists():
        files = sorted(results_dir.glob("backtest-*.json"), reverse=True)
        if files:
            latest = json.loads(files[0].read_text())
            status["last_backtest"] = {
                "file": files[0].name,
                "total_bets": latest.get("total_bets"),
                "final_bankroll": latest.get("final_bankroll"),
                "roi": latest.get("roi"),
            }

    # Check agent PIDs
    pids_dir = NBA_DIR / "data" / "pids"
    if pids_dir.exists():
        for f in pids_dir.glob("*.pid"):
            name = f.stem
            pid = f.read_text().strip()
            try:
                os.kill(int(pid), 0)
                status["agents"][name] = "RUNNING"
            except (ProcessLookupError, ValueError):
                status["agents"][name] = "DEAD"

    return status


def launch_nba():
    """Launch the NBA daemon."""
    env = {**os.environ}
    # Source mon-ipad .env.local
    env_file = MON_IPAD / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.replace("export ", "").strip()
                val = val.strip().strip("'\"")
                env[key] = val

    # Launch daemon
    proc = subprocess.Popen(
        ["python3", "-u", str(NBA_DIR / "agents" / "nba_daemon.py"), "--daemon"],
        stdout=open(NBA_DIR / "data" / "daemon.log", "a"),
        stderr=subprocess.STDOUT,
        cwd=str(NBA_DIR),
        env=env,
    )
    (NBA_DIR / "data" / "daemon.pid").write_text(str(proc.pid))
    print(f"[{ts()}] NBA daemon launched (PID {proc.pid})")
    return proc.pid


def launch_agents():
    """Launch all 7 NBA agents."""
    result = subprocess.run(
        ["python3", str(NBA_DIR / "agents" / "launcher.py"), "launch", "all"],
        capture_output=True, text=True, timeout=30,
        cwd=str(NBA_DIR),
    )
    print(result.stdout)
    return result.returncode == 0


def run_backtest():
    """Run backtest on last 30 matches."""
    env = {**os.environ}
    env_file = MON_IPAD / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.replace("export ", "").strip()
                val = val.strip().strip("'\"")
                env[key] = val

    result = subprocess.run(
        ["python3", str(NBA_DIR / "ops" / "backtest.py"), "--games", "30"],
        capture_output=True, text=True, timeout=300,
        cwd=str(NBA_DIR),
        env=env,
    )
    print(result.stdout[-3000:])
    if result.stderr:
        print(f"STDERR: {result.stderr[-500:]}")
    return result.returncode == 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="NBA Agent Pilot")
    parser.add_argument("action", choices=["status", "launch", "launch-agents", "backtest", "report", "stop"],
                       help="Action to perform")
    args = parser.parse_args()

    if args.action == "status":
        status = get_nba_status()
        print(json.dumps(status, indent=2))

    elif args.action == "launch":
        pid = launch_nba()
        msg = f"NBA Agent launched (PID {pid})"
        print(msg)
        send_telegram(f"🏀 {msg}")

    elif args.action == "launch-agents":
        launch_agents()

    elif args.action == "backtest":
        run_backtest()

    elif args.action == "report":
        status = get_nba_status()
        lines = [
            "🏀 <b>NBA AGENT STATUS</b>",
            f"⏰ {status['timestamp']}",
            f"🤖 Daemon: {'✅ RUNNING' if status['daemon_running'] else '❌ STOPPED'}",
        ]
        if status["bankroll"]:
            b = status["bankroll"]
            lines.append(f"💰 Bankroll: ${b.get('current', '?'):.2f} (ROI: {b.get('roi', '?')}%)")
        if status["last_backtest"]:
            bt = status["last_backtest"]
            lines.append(f"📊 Backtest: {bt.get('total_bets', '?')} bets, ROI: {bt.get('roi', '?')}%")
        agents = status.get("agents", {})
        if agents:
            running = sum(1 for v in agents.values() if v == "RUNNING")
            lines.append(f"🔧 Agents: {running}/{len(agents)} running")

        msg = "\n".join(lines)
        print(msg)
        send_telegram(msg)

    elif args.action == "stop":
        pid_file = NBA_DIR / "data" / "daemon.pid"
        if pid_file.exists():
            pid = int(pid_file.read_text().strip())
            try:
                os.kill(pid, 15)  # SIGTERM
                print(f"Stopped daemon PID {pid}")
            except ProcessLookupError:
                print("Daemon not running")


if __name__ == "__main__":
    main()
