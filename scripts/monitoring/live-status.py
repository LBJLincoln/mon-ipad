#!/usr/bin/env python3
"""
Nomos42 Live Status Dashboard — Rich Terminal UI
=================================================
Real-time monitoring of the entire Nomos42 ecosystem.
Auto-refreshes every 10 seconds. Lightweight: file reads + curls only.

Panels:
  [1] System     — CPU, RAM, disk usage
  [2] HF Spaces  — Evolution island status (from infra-status.json + live curl)
  [3] Trading    — Trading Floor v4 leaderboard
  [4] Councils   — Department council states
  [5] Cron       — Active cron jobs
  [6] Git        — Uncommitted files, last commit

Color coding:
  GREEN  = healthy / active
  YELLOW = warning / stale (>4h)
  RED    = error / dead (>12h)

Usage: python3 live-status.py [--refresh N] [--no-curl]
  --refresh N   Refresh interval in seconds (default: 10)
  --no-curl     Skip live HF Space curls (use cached infra-status.json only)

Dependencies: rich (pip install rich)
Safe for 1vCPU / 969MB — no ML, no heavy computation.
"""

import json
import os
import sys
import time
import glob
import subprocess
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.columns import Columns
    from rich import box
except ImportError:
    print("ERROR: 'rich' is required. Install with: pip install rich")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path("/home/termius/mon-ipad")
DATA_DIR = BASE_DIR / "data"
NBA_DIR = DATA_DIR / "nba-agent"
ARENA_DIR = DATA_DIR / "arena"
DEPTS_DIR = DATA_DIR / "departments"

# ── Config ────────────────────────────────────────────────────────────────────
HF_SPACES = {
    "S10": {"url": "https://nomos42-nba-quant.hf.space", "role": "Exploitation", "key": "S10_nba"},
    "S11": {"url": "https://nomos42-nba-quant-2.hf.space", "role": "Exploration", "key": "S11_nba"},
    "S12": {"url": "https://nomos42-nba-evo-3.hf.space", "role": "ExtraTrees", "key": "S12_nba"},
    "S13": {"url": "https://nomos42-nba-evo-4.hf.space", "role": "CatBoost", "key": "S13_nba"},
    "S14": {"url": "https://nomos42-nba-evo-5.hf.space", "role": "LightGBM", "key": "S14_nba"},
    "S15": {"url": "https://nomos42-nba-evo-6.hf.space", "role": "Wide Search", "key": "S15_nba"},
    "S16": {"url": "https://lbjlincoln26-nba-evo-s16.hf.space", "role": "Gradient", "key": "S16_nba"},
    "S17": {"url": "https://lbjlincoln26-nba-evo-s17.hf.space", "role": "Ensemble", "key": "S17_nba"},
}

console = Console()

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> Optional[dict]:
    """Safely load JSON file. Handles malformed JSON with control chars."""
    try:
        with open(path, "r") as f:
            raw = f.read()
        # Try strict first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Retry with control characters stripped (some files have raw newlines in strings)
            import re
            cleaned = re.sub(r'[\x00-\x1f]+', ' ', raw)
            return json.loads(cleaned)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError, Exception):
        return None


def run_cmd(cmd: str, timeout: int = 5) -> str:
    """Run a shell command safely."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""


def age_color(iso_ts: str) -> str:
    """Return color based on age of timestamp."""
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age_h < 4:
            return "green"
        elif age_h < 12:
            return "yellow"
        else:
            return "red"
    except (ValueError, TypeError):
        return "dim"


def status_color(status: str) -> str:
    """Return color for a status string."""
    s = status.lower()
    if s in ("running", "active", "healthy", "keep"):
        return "green"
    elif s in ("stale", "warning", "restarted", "paused"):
        return "yellow"
    elif s in ("error", "failed", "dead", "eliminated", "stopped"):
        return "red"
    return "white"


def fmt_money(val) -> str:
    """Format a monetary value."""
    try:
        v = float(val)
        if v >= 1000:
            return f"${v:,.0f}"
        return f"${v:,.2f}"
    except (ValueError, TypeError):
        return str(val)


# ── Panel Builders ────────────────────────────────────────────────────────────

def build_system_panel() -> Panel:
    """Panel 1: System health — CPU, RAM, disk."""
    lines = []

    # Memory
    mem_output = run_cmd("free -m")
    if mem_output:
        for line in mem_output.split("\n"):
            if line.startswith("Mem:"):
                parts = line.split()
                if len(parts) >= 3:
                    total = int(parts[1])
                    used = int(parts[2])
                    pct = (used / total * 100) if total > 0 else 0
                    color = "green" if pct < 70 else "yellow" if pct < 90 else "red"
                    lines.append(f"  RAM: [{color}]{used}MB / {total}MB ({pct:.0f}%)[/{color}]")

    # Disk
    disk_output = run_cmd("df -h / | tail -1")
    if disk_output:
        parts = disk_output.split()
        if len(parts) >= 5:
            used_pct = parts[4].rstrip("%")
            try:
                pct = int(used_pct)
                color = "green" if pct < 70 else "yellow" if pct < 90 else "red"
                lines.append(f"  Disk: [{color}]{parts[2]} / {parts[1]} ({pct}%)[/{color}]")
            except ValueError:
                lines.append(f"  Disk: {parts[2]} / {parts[1]} ({parts[4]})")

    # Load average
    load_output = run_cmd("cat /proc/loadavg")
    if load_output:
        parts = load_output.split()
        load1 = float(parts[0]) if parts else 0
        color = "green" if load1 < 0.7 else "yellow" if load1 < 1.5 else "red"
        lines.append(f"  Load: [{color}]{parts[0]} {parts[1]} {parts[2]}[/{color}]")

    # Uptime
    uptime_output = run_cmd("uptime -p")
    if uptime_output:
        lines.append(f"  Uptime: {uptime_output}")

    # Processes
    proc_count = run_cmd("ps aux | wc -l")
    py_count = run_cmd("ps aux | grep -c '[p]ython3'")
    lines.append(f"  Processes: {proc_count} total, {py_count} python3")

    content = "\n".join(lines) if lines else "  [dim]No data[/dim]"
    return Panel(content, title="[bold cyan]SYSTEM[/bold cyan]", border_style="cyan", box=box.ROUNDED)


def build_hf_panel(do_curl: bool = False) -> Panel:
    """Panel 2: HF Spaces evolution status."""
    # Primary source: infra-status.json (always available, updated by cron)
    infra = load_json(DATA_DIR / "infra-status.json")
    hf_data = infra.get("hf_spaces", {}) if infra else {}

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("Space", style="bold", width=5)
    table.add_column("Role", width=12)
    table.add_column("Status", width=9)
    table.add_column("Brier", width=9, justify="right")
    table.add_column("Gen", width=7, justify="right")

    # Best Brier tracking
    best_brier = 1.0
    best_space = ""

    for sid, info in HF_SPACES.items():
        cached = hf_data.get(info["key"], {})
        status = cached.get("status", "?") if isinstance(cached, dict) else "?"
        brier = cached.get("brier", "?") if isinstance(cached, dict) else "?"
        gen = cached.get("gen", "?") if isinstance(cached, dict) else "?"

        # Track best
        try:
            b = float(brier)
            if b < best_brier:
                best_brier = b
                best_space = sid
        except (ValueError, TypeError):
            pass

        s_color = status_color(status)
        # Color Brier: green if < 0.223, yellow if < 0.226, red otherwise
        try:
            b_val = float(brier)
            b_color = "green" if b_val < 0.223 else "yellow" if b_val < 0.226 else "red"
            brier_str = f"[{b_color}]{b_val:.5f}[/{b_color}]"
        except (ValueError, TypeError):
            brier_str = str(brier)

        table.add_row(
            sid,
            info["role"],
            f"[{s_color}]{status}[/{s_color}]",
            brier_str,
            str(gen),
        )

    # Summary line
    ts = infra.get("timestamp", "?") if infra else "?"
    summary = infra.get("summary", {}) if infra else {}
    healthy = summary.get("healthy", "?")
    total = summary.get("total", "?")
    footer = f"  Fleet: {healthy}/{total} healthy | Best: [green]{best_space} {best_brier:.5f}[/green] | Updated: {ts}"

    from rich.console import Group
    content = Group(table, Text(footer))
    return Panel(content, title="[bold green]HF EVOLUTION FLEET[/bold green]", border_style="green", box=box.ROUNDED)


def build_trading_panel() -> Panel:
    """Panel 3: Trading Floor leaderboard."""
    tf = load_json(ARENA_DIR / "trading-floor-v4-latest.json")
    if not tf:
        return Panel("[dim]No trading floor data[/dim]", title="[bold yellow]TRADING FLOOR[/bold yellow]", border_style="yellow")

    meta = tf.get("meta", {})
    lb = tf.get("leaderboard", [])

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("#", width=3, justify="right")
    table.add_column("Trader", width=12)
    table.add_column("NBA $", width=12, justify="right")
    table.add_column("ROI%", width=9, justify="right")
    table.add_column("Sharpe", width=7, justify="right")
    table.add_column("W/L", width=9)
    table.add_column("St", width=5)

    for t in lb:
        rank = t.get("rank", "?")
        name = t.get("name", "?")
        bankroll = t.get("nba_bankroll", 0)
        roi = t.get("nba_roi_pct", 0)
        sharpe = t.get("nba_sharpe", 0)
        wins = t.get("nba_wins", 0)
        losses = t.get("nba_losses", 0)
        elim = t.get("eliminated", False)

        # Color by rank
        if rank == 1:
            name_str = f"[bold green]{name}[/bold green]"
        elif rank == 2:
            name_str = f"[green]{name}[/green]"
        elif elim:
            name_str = f"[dim strikethrough]{name}[/dim strikethrough]"
        else:
            name_str = name

        roi_color = "green" if roi > 100 else "yellow" if roi > 0 else "red"
        sharpe_color = "green" if sharpe > 1.5 else "yellow" if sharpe > 0.5 else "red"
        status = "[red]ELIM[/red]" if elim else "[green]OK[/green]"

        table.add_row(
            str(rank),
            name_str,
            fmt_money(bankroll),
            f"[{roi_color}]{roi:.1f}%[/{roi_color}]",
            f"[{sharpe_color}]{sharpe:.3f}[/{sharpe_color}]",
            f"{wins}/{losses}",
            status,
        )

    # Iteration info
    tf_iter = load_json(ARENA_DIR / "trading-floor-iteration.json")
    iter_str = ""
    if tf_iter:
        iter_str = f"Iter {tf_iter.get('iteration', '?')} | Gen {tf_iter.get('generation', '?')} | "

    footer = f"  {iter_str}Games: {meta.get('matched_games', '?')} | Models: {meta.get('nba_models', '?')} | Generated: {meta.get('generated', '?')}"

    from rich.console import Group
    content = Group(table, Text(footer))
    return Panel(content, title="[bold yellow]TRADING FLOOR v4[/bold yellow]", border_style="yellow", box=box.ROUNDED)


def build_councils_panel() -> Panel:
    """Panel 4: Department council states."""
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("Department", width=18)
    table.add_column("Iter", width=5, justify="right")
    table.add_column("Best", width=12, justify="right")
    table.add_column("Last Run", width=18)
    table.add_column("Health", width=8)

    council_files = sorted(glob.glob(str(DEPTS_DIR / "council-*.json")))
    active_count = 0
    stale_count = 0

    for f in council_files:
        d = load_json(Path(f))
        if not d:
            continue

        dept = d.get("dept", os.path.basename(f).replace("council-", "").replace(".json", ""))
        iteration = d.get("iteration", 0)
        best = d.get("best_metric", None)
        last_run = d.get("last_run", "?")

        # Format best metric
        if isinstance(best, (int, float)):
            best_str = f"{best:.5f}"
        elif best is None:
            best_str = "--"
        else:
            best_str = str(best)[:12]

        # Determine health from age
        health = "ACTIVE"
        h_color = "green"
        if last_run and last_run != "?":
            try:
                lr = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                age_h = (datetime.now(timezone.utc) - lr).total_seconds() / 3600
                if age_h > 12:
                    health = "DEAD"
                    h_color = "red"
                elif age_h > 6:
                    health = "STALE"
                    h_color = "yellow"
                    stale_count += 1
                else:
                    active_count += 1
                # Truncate timestamp for display
                last_run = last_run[:16].replace("T", " ")
            except (ValueError, TypeError):
                pass
        else:
            health = "UNKNOWN"
            h_color = "dim"

        table.add_row(
            dept,
            str(iteration),
            best_str,
            last_run,
            f"[{h_color}]{health}[/{h_color}]",
        )

    footer = f"  Departments: {len(council_files)} | Active: [green]{active_count}[/green] | Stale: [yellow]{stale_count}[/yellow]"

    from rich.console import Group
    content = Group(table, Text(footer))
    return Panel(content, title="[bold magenta]DEPARTMENT COUNCILS[/bold magenta]", border_style="magenta", box=box.ROUNDED)


def build_cron_panel() -> Panel:
    """Panel 5: Active cron jobs."""
    cron_output = run_cmd("crontab -l 2>/dev/null", timeout=3)
    if not cron_output:
        return Panel("[dim]No crontab entries[/dim]", title="[bold blue]CRON JOBS[/bold blue]", border_style="blue")

    lines = []
    total = 0
    for line in cron_output.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        total += 1
        # Abbreviate long paths
        display = line
        if len(display) > 90:
            display = display[:87] + "..."
        lines.append(f"  {display}")

    # Only show first 15 entries to save space
    if len(lines) > 15:
        shown = lines[:15]
        shown.append(f"  [dim]... and {len(lines) - 15} more entries[/dim]")
    else:
        shown = lines

    footer = f"\n  Total active entries: [cyan]{total}[/cyan]"
    content = "\n".join(shown) + footer
    return Panel(content, title="[bold blue]CRON JOBS[/bold blue]", border_style="blue", box=box.ROUNDED)


def build_git_panel() -> Panel:
    """Panel 6: Git status."""
    lines = []

    # Last 5 commits
    git_log = run_cmd(f"cd {BASE_DIR} && git log --oneline --decorate -5", timeout=5)
    if git_log:
        lines.append("[bold]Last commits:[/bold]")
        for commit in git_log.split("\n")[:5]:
            lines.append(f"  {commit}")

    # Branch
    branch = run_cmd(f"cd {BASE_DIR} && git branch --show-current", timeout=3)
    if branch:
        lines.append(f"\n[bold]Branch:[/bold] [cyan]{branch}[/cyan]")

    # Uncommitted changes
    git_status = run_cmd(f"cd {BASE_DIR} && git status -s", timeout=5)
    if git_status:
        changes = git_status.split("\n")
        modified = sum(1 for c in changes if c.strip().startswith("M"))
        added = sum(1 for c in changes if c.strip().startswith("A") or c.strip().startswith("??"))
        deleted = sum(1 for c in changes if c.strip().startswith("D"))

        color = "yellow" if len(changes) < 20 else "red"
        lines.append(f"\n[bold]Uncommitted:[/bold] [{color}]{len(changes)} files[/{color}]")
        lines.append(f"  Modified: {modified} | Added: {added} | Deleted: {deleted}")

        # Show first few
        for c in changes[:8]:
            lines.append(f"  [dim]{c.strip()}[/dim]")
        if len(changes) > 8:
            lines.append(f"  [dim]... +{len(changes) - 8} more[/dim]")
    else:
        lines.append("\n[bold]Uncommitted:[/bold] [green]Clean[/green]")

    content = "\n".join(lines) if lines else "[dim]No git info[/dim]"
    return Panel(content, title="[bold white]GIT STATUS[/bold white]", border_style="white", box=box.ROUNDED)


# ── Layout Builder ────────────────────────────────────────────────────────────

def build_header() -> Panel:
    """Build the header bar."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_text = Text()
    header_text.append("  NOMOS42 ", style="bold white on dark_green")
    header_text.append("  Live Status Dashboard  ", style="bold green")
    header_text.append(f"  {now}  ", style="dim")
    header_text.append("  1vCPU/969MB  ", style="dim yellow")
    header_text.append("  Ctrl+C to exit  ", style="dim")
    return Panel(header_text, box=box.HEAVY, style="green")


def build_layout(do_curl: bool = False) -> Layout:
    """Build the full dashboard layout."""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="top", ratio=2),
        Layout(name="bottom", ratio=3),
    )

    layout["top"].split_row(
        Layout(name="system", ratio=1),
        Layout(name="hf", ratio=2),
        Layout(name="git", ratio=1),
    )

    layout["bottom"].split_row(
        Layout(name="trading", ratio=2),
        Layout(name="right", ratio=2),
    )

    layout["right"].split_column(
        Layout(name="councils", ratio=2),
        Layout(name="cron", ratio=1),
    )

    # Populate
    layout["header"].update(build_header())
    layout["system"].update(build_system_panel())
    layout["hf"].update(build_hf_panel(do_curl=do_curl))
    layout["git"].update(build_git_panel())
    layout["trading"].update(build_trading_panel())
    layout["councils"].update(build_councils_panel())
    layout["cron"].update(build_cron_panel())

    return layout


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Nomos42 Live Status Dashboard")
    parser.add_argument("--refresh", type=int, default=10, help="Refresh interval in seconds (default: 10)")
    parser.add_argument("--no-curl", action="store_true", help="Skip live HF Space curls (use cached data only)")
    parser.add_argument("--once", action="store_true", help="Print once and exit (no live mode)")
    args = parser.parse_args()

    do_curl = not args.no_curl

    if args.once:
        # Static single render
        console.print(build_layout(do_curl=do_curl))
        return

    # Live auto-refreshing dashboard
    console.clear()
    try:
        with Live(
            build_layout(do_curl=do_curl),
            console=console,
            refresh_per_second=0.5,
            screen=True,
        ) as live:
            cycle = 0
            while True:
                time.sleep(args.refresh)
                cycle += 1
                # Only curl HF spaces every 6th cycle (60s at default refresh)
                # to avoid hammering the endpoints
                curl_this_cycle = do_curl and (cycle % 6 == 0)
                live.update(build_layout(do_curl=curl_this_cycle))
    except KeyboardInterrupt:
        console.clear()
        console.print("[bold green]Nomos42 dashboard stopped.[/bold green]")


if __name__ == "__main__":
    main()
