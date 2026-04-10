#!/usr/bin/env python3
"""
Nomos42 Bloomberg Terminal — NBA Betting Intelligence
=====================================================
Rich-based CLI terminal inspired by OpenBB / Bloomberg Terminal.

Panels:
  [O] Odds        — Real-time NBA odds from data/nba-agent/odds-latest.json
  [P] Predictions — Model predictions from data/nba-agent/predictions-today.json
  [T] Trading     — Trading Floor leaderboard (version from live meta)
  [E] Evolution   — 6 HF island fleet status
  [B] Bankroll    — P&L, bankroll, and performance metrics
  [H] Health      — System health overview

Keyboard:
  q = quit   r = refresh   o = odds   t = trading   e = evolution
  b = bankroll   p = predictions   h = health   a = all (dashboard)

Dependencies: rich (pip install rich)
Usage: python3 nomos42-terminal.py
"""

import json
import os
import sys
import time
import datetime
import threading
from pathlib import Path

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

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
NBA_DIR = DATA_DIR / "nba-agent"
ARENA_DIR = DATA_DIR / "arena"

# Data file paths
ODDS_FILE = NBA_DIR / "odds-latest.json"
PREDICTIONS_FILE = NBA_DIR / "predictions-today.json"
VALUE_BETS_FILE = NBA_DIR / "value-bets.json"
TRADING_FLOOR_FILE = ARENA_DIR / "trading-floor-v4-latest.json"
BANKROLL_FILE = NBA_DIR / "bankroll-state.json"
QUANT_FILE = NBA_DIR / "quant-summary.json"
EVAL_FILE = NBA_DIR / "latest-eval.json"
HEALTH_FILE = DATA_DIR / "agent-health.json"
INFRA_FILE = DATA_DIR / "infra-status.json"
FLEET_FILE = DATA_DIR / "fleet-status.json"

# HF Space endpoints for live status
HF_SPACES = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
}

HF_ROLES = {
    "S10": "Exploitation",
    "S11": "Exploration",
    "S12": "ExtraTrees",
    "S13": "CatBoost",
    "S14": "LightGBM",
    "S15": "Wide Search",
}

console = Console()


# ── Data Loading ───────────────────────────────────────────────────────────

def load_json(path: Path) -> dict | list | None:
    """Safely load a JSON file, return None on failure."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return None


def fetch_hf_status(space_id: str, url: str) -> dict:
    """Attempt to fetch live status from an HF Space API. Returns dict."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{url}/api/status", method="GET")
        req.add_header("User-Agent", "Nomos42-Bloomberg/1.0")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return {"id": space_id, "status": "LIVE", "data": data}
    except Exception:
        return {"id": space_id, "status": "OFFLINE", "data": {}}


# ── Panel Builders ─────────────────────────────────────────────────────────

def build_header() -> Panel:
    """Build the terminal header bar."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_text = Text()
    header_text.append("  NOMOS42 BLOOMBERG  ", style="bold white on dark_green")
    header_text.append("  NBA Betting Intelligence Terminal  ", style="bold green")
    header_text.append(f"  {now}  ", style="dim")
    header_text.append("  [q]uit [r]efresh [a]ll [o]dds [t]rading [e]vo [b]ank [p]reds [h]ealth", style="dim cyan")
    return Panel(header_text, style="green", box=box.HEAVY)


def build_odds_panel() -> Panel:
    """Build the odds display panel."""
    odds = load_json(ODDS_FILE)
    if not odds:
        return Panel("[dim]No odds data available[/dim]", title="[bold yellow]ODDS[/bold yellow]", border_style="yellow")

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold yellow", expand=True)
    table.add_column("Game", style="white", ratio=3)
    table.add_column("Time", style="dim", ratio=1)
    table.add_column("Home ML", justify="right", style="green", ratio=1)
    table.add_column("Away ML", justify="right", style="red", ratio=1)
    table.add_column("Spread", justify="right", ratio=1)
    table.add_column("Total", justify="right", ratio=1)

    games = odds if isinstance(odds, list) else [odds]
    for game in games[:12]:  # Max 12 games
        home = game.get("home_team", "?")
        away = game.get("away_team", "?")
        ct = game.get("commence_time", "")
        time_str = ct[11:16] if len(ct) > 16 else "TBD"

        # Extract best odds from bookmakers
        home_ml = "-"
        away_ml = "-"
        spread_str = "-"
        total_str = "-"

        bookmakers = game.get("bookmakers", [])
        if bookmakers:
            bk = bookmakers[0]
            for market in bk.get("markets", []):
                if market["key"] == "h2h":
                    outcomes = market.get("outcomes", [])
                    for o in outcomes:
                        if o["name"] == home:
                            home_ml = f"{o['price']:.2f}"
                        elif o["name"] == away:
                            away_ml = f"{o['price']:.2f}"
                elif market["key"] == "spreads":
                    outcomes = market.get("outcomes", [])
                    if outcomes:
                        pt = outcomes[0].get("point", "")
                        spread_str = f"{pt:+.1f}" if isinstance(pt, (int, float)) else str(pt)
                elif market["key"] == "totals":
                    outcomes = market.get("outcomes", [])
                    if outcomes:
                        pt = outcomes[0].get("point", "")
                        total_str = f"{pt}" if pt else "-"

        # Shorten team names
        home_short = home.split()[-1] if home else "?"
        away_short = away.split()[-1] if away else "?"
        table.add_row(
            f"{away_short} @ {home_short}",
            time_str,
            home_ml,
            away_ml,
            spread_str,
            total_str,
        )

    return Panel(table, title="[bold yellow]LIVE ODDS[/bold yellow]", border_style="yellow")


def build_predictions_panel() -> Panel:
    """Build model predictions panel."""
    preds = load_json(PREDICTIONS_FILE)
    if not preds:
        return Panel("[dim]No predictions available[/dim]", title="[bold cyan]PREDICTIONS[/bold cyan]", border_style="cyan")

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Game", style="white", ratio=2)
    table.add_column("Model P(Home)", justify="right", style="green", ratio=1)
    table.add_column("Confidence", justify="center", ratio=1)
    table.add_column("Edge", justify="right", ratio=1)
    table.add_column("Kelly $", justify="right", style="yellow", ratio=1)
    table.add_column("Pick", justify="center", style="bold", ratio=1)

    date_str = preds.get("date", "?")
    games = preds.get("games", [])
    for g in games[:10]:
        home = g.get("home", "?")
        away = g.get("away", "?")
        prob = g.get("home_win_prob", 0)
        conf = g.get("confidence", "?")
        edge = g.get("edge") or 0
        kelly = g.get("kelly_stake") or 0
        side = g.get("bet_side", "?")
        prob = prob or 0.5

        prob_style = "green" if prob > 0.6 else ("red" if prob < 0.4 else "yellow")
        edge_style = "green" if edge > 0.05 else "dim"
        conf_style = "bold green" if conf == "HIGH" else ("yellow" if conf == "MEDIUM" else "dim")

        table.add_row(
            f"{away} @ {home}",
            f"[{prob_style}]{prob:.1%}[/{prob_style}]",
            f"[{conf_style}]{conf}[/{conf_style}]",
            f"[{edge_style}]{edge:+.1%}[/{edge_style}]",
            f"${kelly * 100:.0f}" if kelly else "-",
            f"[bold white on blue] {side} [/bold white on blue]" if side != "?" else "-",
        )

    subtitle = f"Date: {date_str} | Games: {len(games)}"
    return Panel(table, title="[bold cyan]MODEL PREDICTIONS[/bold cyan]", subtitle=subtitle, border_style="cyan")


def build_value_bets_panel() -> Panel:
    """Build value bets panel."""
    vb = load_json(VALUE_BETS_FILE)
    if not vb:
        return Panel("[dim]No value bets[/dim]", title="[bold magenta]VALUE BETS[/bold magenta]", border_style="magenta")

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Game", style="white", ratio=2)
    table.add_column("Type", ratio=1)
    table.add_column("Pick", style="bold", ratio=1)
    table.add_column("Edge", justify="right", style="green", ratio=1)
    table.add_column("Kelly $", justify="right", style="yellow", ratio=1)
    table.add_column("Conf", justify="center", ratio=1)

    bets = vb.get("value_bets", []) if isinstance(vb, dict) else vb
    for b in bets[:8]:
        game = b.get("game", "?")
        btype = b.get("type", "?")
        pick = b.get("pick", "?")
        edge = b.get("edge", 0)
        kelly_bet = b.get("kelly_bet", 0)
        conf = b.get("confidence", "?")

        conf_style = "bold green" if conf == "HIGH" else ("yellow" if conf == "MEDIUM" else "dim")
        table.add_row(
            game,
            btype.upper(),
            pick,
            f"{edge:.2%}" if isinstance(edge, float) and edge < 1 else f"{edge:.1f}%",
            f"${kelly_bet:.2f}",
            f"[{conf_style}]{conf}[/{conf_style}]",
        )

    return Panel(table, title="[bold magenta]VALUE BETS[/bold magenta]", border_style="magenta")


def build_trading_floor_panel() -> Panel:
    """Build the Trading Floor leaderboard."""
    tf = load_json(TRADING_FLOOR_FILE)
    if not tf:
        return Panel("[dim]No trading floor data[/dim]", title="[bold red]TRADING FLOOR[/bold red]", border_style="red")

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold red", expand=True)
    table.add_column("#", justify="center", style="bold", width=3)
    table.add_column("Trader", style="bold white", ratio=1)
    table.add_column("Provider", style="dim", ratio=1)
    table.add_column("NBA $", justify="right", style="green", ratio=1)
    table.add_column("NBA ROI", justify="right", ratio=1)
    table.add_column("Sharpe", justify="right", ratio=1)
    table.add_column("W/L", justify="center", ratio=1)
    table.add_column("Pol $", justify="right", style="blue", ratio=1)
    table.add_column("Status", justify="center", ratio=1)

    leaderboard = tf.get("leaderboard", [])
    for trader in leaderboard:
        rank = trader.get("rank", "?")
        name = trader.get("name", "?")
        provider = trader.get("provider", "?")
        nba_bank = trader.get("nba_bankroll", 0)
        nba_roi = trader.get("nba_roi_pct", 0)
        sharpe = trader.get("nba_sharpe", 0)
        wins = trader.get("nba_wins", 0)
        losses = trader.get("nba_losses", 0)
        pol_bank = trader.get("political_bankroll", 0)
        eliminated = trader.get("eliminated", False)

        # Color coding
        roi_style = "green" if nba_roi > 0 else "red"
        sharpe_style = "green" if sharpe > 1 else ("yellow" if sharpe > 0 else "red")
        status = "[red]DEAD[/red]" if eliminated else "[green]LIVE[/green]"

        # Format bankroll
        if nba_bank >= 1000:
            bank_str = f"${nba_bank/1000:.1f}K"
        else:
            bank_str = f"${nba_bank:.2f}"

        pol_str = f"${pol_bank/1000:.0f}K" if pol_bank >= 1000 else f"${pol_bank:.0f}"

        # Medal for top 3
        rank_str = {1: "[gold1]1[/gold1]", 2: "[grey70]2[/grey70]", 3: "[orange3]3[/orange3]"}.get(rank, str(rank))

        table.add_row(
            rank_str,
            name,
            provider,
            bank_str,
            f"[{roi_style}]{nba_roi:+.1f}%[/{roi_style}]",
            f"[{sharpe_style}]{sharpe:.2f}[/{sharpe_style}]",
            f"{wins}/{losses}",
            pol_str,
            status,
        )

    meta = tf.get("meta", {})
    iteration = tf.get("iteration", "?")
    gen = tf.get("generation", "?")
    tf_version = meta.get("version", "trading-floor-v4").upper().replace("-", " ")
    tf_date = meta.get("date", "?")
    subtitle = f"Iter {iteration} | Gen {gen} | Date: {tf_date} | Strategies: {meta.get('nba_strategies', '?')} active, {meta.get('nba_strategies_eliminated', '?')} elim"
    return Panel(table, title=f"[bold red]{tf_version}[/bold red]", subtitle=subtitle, border_style="red")


def build_evolution_panel() -> Panel:
    """Build the 6-island evolution fleet panel."""
    # Try infra-status first (has latest gen data), fall back to agent-health
    infra = load_json(INFRA_FILE)
    health = load_json(HEALTH_FILE)

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold green", expand=True)
    table.add_column("Island", style="bold", ratio=1)
    table.add_column("Role", ratio=1)
    table.add_column("Status", justify="center", ratio=1)
    table.add_column("Brier", justify="right", style="cyan", ratio=1)
    table.add_column("Gen", justify="right", ratio=1)
    table.add_column("Model", ratio=1)

    # Parse from infra-status (has hf_spaces dict)
    hf_data = {}
    if infra and "hf_spaces" in infra:
        hf_raw = infra["hf_spaces"]
        for key, val in hf_raw.items():
            if key.startswith("S1"):
                hf_data[key.split("_")[0]] = val
    elif health and "projects" in health:
        nba = health["projects"].get("nba", {})
        spaces = nba.get("spaces", {})
        for sid, sdata in spaces.items():
            hf_data[sid] = {
                "status": sdata.get("status", "?").lower(),
                "brier": str(sdata.get("brier", "?")),
                "gen": str(sdata.get("generation", "?")),
                "model": sdata.get("model", "?"),
            }

    best_brier = 999.0
    best_island = ""

    for sid in ["S10", "S11", "S12", "S13", "S14", "S15"]:
        role = HF_ROLES.get(sid, "?")
        sdata = hf_data.get(sid, {})
        status = sdata.get("status", "unknown")
        brier_str = sdata.get("brier", "?")
        gen_str = sdata.get("gen", sdata.get("generation", "?"))
        model = sdata.get("model", "-")

        # Status styling
        if status in ("running", "UP"):
            status_fmt = "[green]RUNNING[/green]"
        elif status == "OFFLINE":
            status_fmt = "[red]OFFLINE[/red]"
        else:
            status_fmt = f"[yellow]{status}[/yellow]"

        # Track best
        try:
            brier_val = float(brier_str)
            if brier_val < best_brier:
                best_brier = brier_val
                best_island = sid
            brier_fmt = f"{brier_val:.5f}"
        except (ValueError, TypeError):
            brier_fmt = str(brier_str)

        table.add_row(sid, role, status_fmt, brier_fmt, str(gen_str), str(model))

    subtitle = f"Best: {best_island} ({best_brier:.5f})" if best_brier < 999 else ""
    return Panel(table, title="[bold green]EVOLUTION FLEET (6 Islands)[/bold green]", subtitle=subtitle, border_style="green")


def build_bankroll_panel() -> Panel:
    """Build the bankroll and P&L panel."""
    bank = load_json(BANKROLL_FILE)
    quant = load_json(QUANT_FILE)

    if not bank:
        return Panel("[dim]No bankroll data[/dim]", title="[bold yellow]BANKROLL[/bold yellow]", border_style="yellow")

    balance = bank.get("balance", 0)
    initial = bank.get("initial_balance", 100)
    roi = bank.get("roi_pct", 0)
    wins = bank.get("wins", 0)
    losses = bank.get("losses", 0)
    total_bets = bank.get("total_bets", 0)
    peak = bank.get("peak_balance", 0)
    trough = bank.get("trough_balance", 0)
    drawdown = bank.get("max_drawdown_pct", 0)
    sharpe = bank.get("sharpe_ratio", 0)
    wagered = bank.get("total_wagered", 0)
    win_rate = bank.get("win_rate_pct", 0)

    # Color based on P&L
    pnl = balance - initial
    pnl_style = "green" if pnl >= 0 else "red"
    roi_style = "green" if roi >= 0 else "red"

    # Build metrics grid
    lines = []
    lines.append(f"[bold white]Balance:[/bold white]    [{pnl_style}]${balance:.2f}[/{pnl_style}]  (initial: ${initial:.2f})")
    lines.append(f"[bold white]P&L:[/bold white]        [{pnl_style}]{pnl:+.2f}[/{pnl_style}]  ([{roi_style}]{roi:+.2f}% ROI[/{roi_style}])")
    lines.append(f"[bold white]Record:[/bold white]     {wins}W - {losses}L ({total_bets} total, {win_rate:.1f}% win rate)")
    lines.append(f"[bold white]Wagered:[/bold white]    ${wagered:.2f}")
    lines.append(f"[bold white]Peak:[/bold white]       ${peak:.2f}  |  Trough: ${trough:.2f}")
    lines.append(f"[bold white]Drawdown:[/bold white]   [red]{drawdown:.1f}%[/red]")
    lines.append(f"[bold white]Sharpe:[/bold white]     [{'green' if sharpe > 0 else 'red'}]{sharpe:.2f}[/{'green' if sharpe > 0 else 'red'}]")

    # Add quant model info
    if quant:
        lines.append("")
        lines.append("[bold white]--- Model Status ---[/bold white]")
        best_brier = quant.get("best_brier", "?")
        best_model = quant.get("best_model", "?")
        features = quant.get("features", "?")
        lines.append(f"[bold white]Best Brier:[/bold white] [cyan]{best_brier}[/cyan] ({best_model})")
        lines.append(f"[bold white]Features:[/bold white]   {features}")

        models = quant.get("models", {})
        for name, mdata in models.items():
            brier = mdata.get("brier", "?")
            status = mdata.get("status", "?")
            s_style = "green" if status == "ATR_BEST" else "dim"
            lines.append(f"  [{s_style}]{name:15s} Brier: {brier}  ({status})[/{s_style}]")

        targets = quant.get("targets", {})
        if targets:
            lines.append("")
            lines.append(f"[bold white]Targets:[/bold white] Brier < {targets.get('brier', '?')} | ROI > {targets.get('roi_pct', '?')}% | Sharpe > {targets.get('sharpe', '?')}")

    content = "\n".join(lines)
    return Panel(content, title="[bold yellow]BANKROLL & P&L[/bold yellow]", border_style="yellow")


def build_health_panel() -> Panel:
    """Build system health overview panel."""
    health = load_json(HEALTH_FILE)
    infra = load_json(INFRA_FILE)

    lines = []

    if infra:
        ts = infra.get("timestamp", "?")
        summary = infra.get("summary", {})
        total = summary.get("total", 0)
        healthy = summary.get("healthy", 0)
        restarted = summary.get("restarted", 0)
        failed = summary.get("failed", 0)

        health_style = "green" if failed == 0 else "red"
        lines.append(f"[bold white]Last Check:[/bold white] {ts}")
        lines.append(f"[bold white]Status:[/bold white]     [{health_style}]{healthy}/{total} healthy[/{health_style}], {restarted} restarted, {failed} failed")

        # Kaggle
        kaggle = infra.get("kaggle", {})
        for name, status in kaggle.items():
            status_str = str(status).split("\n")[0] if status else "?"
            if "RUNNING" in str(status).upper():
                lines.append(f"[bold white]Kaggle {name}:[/bold white] [green]RUNNING[/green]")
            elif "ERROR" in str(status).upper():
                lines.append(f"[bold white]Kaggle {name}:[/bold white] [red]ERROR[/red]")
            else:
                lines.append(f"[bold white]Kaggle {name}:[/bold white] [yellow]{status_str[:40]}[/yellow]")

        # Modal
        modal = infra.get("modal", {})
        for name, status in modal.items():
            lines.append(f"[bold white]Modal {name}:[/bold white] {status}")

    else:
        lines.append("[dim]No infra status data available[/dim]")

    # Agent health details
    if health:
        ts = health.get("timestamp", "?")
        lines.append("")
        lines.append(f"[bold white]Agent Health:[/bold white] {ts}")

        projects = health.get("projects", {})
        for proj_name, proj_data in projects.items():
            spaces = proj_data.get("spaces", {}) if isinstance(proj_data, dict) else {}
            up_count = sum(1 for s in spaces.values() if isinstance(s, dict) and s.get("status") == "UP")
            lines.append(f"  {proj_name}: {up_count}/{len(spaces)} spaces UP")

    content = "\n".join(lines)
    return Panel(content, title="[bold blue]SYSTEM HEALTH[/bold blue]", border_style="blue")


# ── View Modes ─────────────────────────────────────────────────────────────

def render_dashboard(console: Console):
    """Render the full dashboard (all panels)."""
    console.clear()
    console.print(build_header())
    console.print()

    # Row 1: Odds + Predictions
    cols_row1 = Columns([build_odds_panel(), build_predictions_panel()], equal=True, expand=True)
    console.print(cols_row1)
    console.print()

    # Row 2: Trading Floor + Evolution
    cols_row2 = Columns([build_trading_floor_panel(), build_evolution_panel()], equal=True, expand=True)
    console.print(cols_row2)
    console.print()

    # Row 3: Bankroll + Health
    cols_row3 = Columns([build_bankroll_panel(), build_health_panel()], equal=True, expand=True)
    console.print(cols_row3)


def render_single(console: Console, panel_name: str):
    """Render a single panel in full width."""
    console.clear()
    console.print(build_header())
    console.print()

    panels = {
        "o": ("ODDS", build_odds_panel),
        "p": ("PREDICTIONS", build_predictions_panel),
        "v": ("VALUE BETS", build_value_bets_panel),
        "t": ("TRADING FLOOR", build_trading_floor_panel),
        "e": ("EVOLUTION", build_evolution_panel),
        "b": ("BANKROLL", build_bankroll_panel),
        "h": ("HEALTH", build_health_panel),
    }

    if panel_name in panels:
        _, builder = panels[panel_name]
        console.print(builder())
        # For odds view, also show value bets
        if panel_name == "o":
            console.print()
            console.print(build_value_bets_panel())
        # For predictions view, also show value bets
        if panel_name == "p":
            console.print()
            console.print(build_value_bets_panel())


# ── Main Loop ──────────────────────────────────────────────────────────────

def print_splash(console: Console):
    """Print the splash screen."""
    splash = """
[bold green]
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   ███╗   ██╗ ██████╗ ███╗   ███╗ ██████╗ ███████╗██╗  ██╗   ║
    ║   ████╗  ██║██╔═══██╗████╗ ████║██╔═══██╗██╔════╝██║  ██║   ║
    ║   ██╔██╗ ██║██║   ██║██╔████╔██║██║   ██║███████╗███████║   ║
    ║   ██║╚██╗██║██║   ██║██║╚██╔╝██║██║   ██║╚════██║╚════██║   ║
    ║   ██║ ╚████║╚██████╔╝██║ ╚═╝ ██║╚██████╔╝███████║     ██║   ║
    ║   ╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚══════╝     ╚═╝   ║
    ║                                                               ║
    ║           B L O O M B E R G   T E R M I N A L                ║
    ║           NBA Betting Intelligence System v1.0                ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
[/bold green]

[dim]Loading data from {data_dir}...[/dim]
""".format(data_dir=DATA_DIR)
    console.print(splash)
    time.sleep(1)


def main():
    """Main entry point."""
    import select as sel
    import tty
    import termios

    print_splash(console)

    # Initial render
    current_view = "a"  # a = all/dashboard
    render_dashboard(console)

    # Input loop
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())

        while True:
            # Wait for input with timeout (auto-refresh every 60s)
            if sel.select([sys.stdin], [], [], 60)[0]:
                key = sys.stdin.read(1).lower()

                if key == "q":
                    console.print("\n[bold green]Nomos42 Bloomberg Terminal closed.[/bold green]")
                    break
                elif key == "r":
                    # Refresh current view
                    if current_view == "a":
                        render_dashboard(console)
                    else:
                        render_single(console, current_view)
                    console.print("[dim]Refreshed.[/dim]")
                elif key == "a":
                    current_view = "a"
                    render_dashboard(console)
                elif key in ("o", "p", "t", "e", "b", "h", "v"):
                    current_view = key
                    render_single(console, key)
                # Ignore unknown keys
            else:
                # Auto-refresh on timeout
                if current_view == "a":
                    render_dashboard(console)
                else:
                    render_single(console, current_view)

    except KeyboardInterrupt:
        console.print("\n[bold green]Nomos42 Bloomberg Terminal closed.[/bold green]")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()
