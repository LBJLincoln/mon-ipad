#!/usr/bin/env python3
"""
Nomos42 Experiment Tracker
==========================
Reads experiment results from local JSON files (and optionally Supabase),
logs them to ClearML (if available), and generates a local HTML report.

Usage:
    python3 scripts/monitoring/experiment-tracker.py [--report-only] [--clearml]

VM-safe: reads local files only by default. ClearML logging is optional.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------- paths ----------------------------------------------------------
BASE = Path(__file__).resolve().parents[2]  # mon-ipad root
DATA = BASE / "data"
NBA = DATA / "nba-agent"
ARENA = DATA / "arena"
EXPERIMENTS = DATA / "experiments"
REPORT_PATH = EXPERIMENTS / "report.html"

# ---------- optional heavy imports -----------------------------------------
clearml_available = False
try:
    from clearml import Task, Logger
    clearml_available = True
except ImportError:
    pass

psycopg2_available = False
try:
    import psycopg2
    psycopg2_available = True
except ImportError:
    pass


# ---------- data collection ------------------------------------------------

def load_json(path: Path) -> dict | list | None:
    """Load a JSON file, return None on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [WARN] Could not load {path}: {e}")
        return None


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, return list of dicts."""
    results = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return results


def collect_experiments() -> dict:
    """Collect all experiment data from local files."""
    print("[1/4] Collecting experiment data from local files...")

    data = {}

    # Latest eval
    data["latest_eval"] = load_json(NBA / "latest-eval.json")

    # Quant summary (has ATR history, models, evolution stats)
    data["quant_summary"] = load_json(NBA / "quant-summary.json")

    # Bankroll state
    data["bankroll"] = load_json(NBA / "bankroll-state.json")

    # Eval history (JSONL)
    data["eval_history"] = load_jsonl(NBA / "eval-history.jsonl")

    # Trading floor iteration
    data["trading_floor"] = load_json(ARENA / "trading-floor-iteration.json")

    # Trading floor latest
    data["trading_floor_latest"] = load_json(ARENA / "trading-floor-latest.json")

    # Trading floor v4 latest
    data["tf_v4_latest"] = load_json(ARENA / "trading-floor-v4-latest.json")

    # Agent health
    data["agent_health"] = load_json(DATA / "agent-health.json")

    # Infra status
    data["infra_status"] = load_json(DATA / "infra-status.json")

    # Cross-repo health
    data["cross_repo"] = load_json(DATA / "cross-repo-health.json")

    # Department council files
    dept_files = list((DATA / "departments").glob("council-*.json")) if (DATA / "departments").exists() else []
    data["departments"] = {}
    for f in dept_files:
        dept_name = f.stem.replace("council-", "")
        data["departments"][dept_name] = load_json(f)

    # Trader state files
    trader_files = list((ARENA / "traders").glob("*-state.json")) if (ARENA / "traders").exists() else []
    data["traders"] = {}
    for f in trader_files:
        trader_name = f.stem.replace("-state", "")
        data["traders"][trader_name] = load_json(f)

    print(f"  Loaded: eval_history={len(data['eval_history'])} entries, "
          f"traders={len(data['traders'])}, departments={len(data['departments'])}")

    return data


def collect_from_supabase() -> list[dict]:
    """Optionally collect experiment data from Supabase."""
    if not psycopg2_available:
        print("  [INFO] psycopg2 not available, skipping Supabase")
        return []

    conn_str = (
        "postgresql://postgres.xivvnrgqayciqjthbfmz:"
        "nomos42-supabase-2026@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
    )

    try:
        conn = psycopg2.connect(conn_str, connect_timeout=10)
        cur = conn.cursor()

        # Try to read from experiments table if it exists
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE '%experiment%'
        """)
        tables = [r[0] for r in cur.fetchall()]

        results = []
        if tables:
            for table in tables:
                cur.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 100")
                cols = [desc[0] for desc in cur.description]
                for row in cur.fetchall():
                    results.append(dict(zip(cols, row)))

        # Also try evolution_results
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE '%evolution%'
        """)
        evo_tables = [r[0] for r in cur.fetchall()]
        for table in evo_tables:
            try:
                cur.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 50")
                cols = [desc[0] for desc in cur.description]
                for row in cur.fetchall():
                    results.append(dict(zip(cols, row)))
            except Exception:
                pass

        conn.close()
        print(f"  Supabase: loaded {len(results)} records from {len(tables) + len(evo_tables)} tables")
        return results

    except Exception as e:
        print(f"  [WARN] Supabase connection failed: {e}")
        return []


# ---------- ClearML logging ------------------------------------------------

def log_to_clearml(data: dict, supabase_data: list[dict]):
    """Log experiment data to ClearML."""
    if not clearml_available:
        print("  [INFO] ClearML not available, skipping")
        return

    print("[2/4] Logging to ClearML...")

    try:
        task = Task.init(
            project_name="Nomos42-NBA-Quant",
            task_name=f"tracker-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
            task_type=Task.TaskTypes.monitor,
            auto_connect_frameworks=False,
            auto_resource_monitoring=False,
        )
        logger = task.get_logger()

        # Log latest eval metrics
        if data.get("latest_eval"):
            ev = data["latest_eval"]
            task.connect({
                "brier_score": ev.get("brier_score", 0),
                "features": ev.get("features", 0),
                "model": ev.get("model", "unknown"),
                "feature_engine_version": ev.get("feature_engine_version", "unknown"),
                "roi_pct": ev.get("roi_pct", 0),
                "sharpe_ratio": ev.get("sharpe_ratio", 0),
            })

        # Log ATR history as series
        if data.get("quant_summary") and "atr_history" in data["quant_summary"]:
            for i, atr in enumerate(data["quant_summary"]["atr_history"]):
                logger.report_scalar(
                    title="Brier Score",
                    series="ATR",
                    value=atr.get("brier", 0),
                    iteration=i,
                )

        # Log model Brier scores
        if data.get("quant_summary") and "models" in data["quant_summary"]:
            for name, model in data["quant_summary"]["models"].items():
                logger.report_scalar(
                    title="Model Brier",
                    series=name,
                    value=model.get("brier", 0),
                    iteration=0,
                )

        # Log trader performance
        for tname, tdata in data.get("traders", {}).items():
            if isinstance(tdata, dict):
                balance = tdata.get("balance", tdata.get("bankroll", 0))
                logger.report_scalar(
                    title="Trader Balance",
                    series=tname,
                    value=balance,
                    iteration=0,
                )

        task.close()
        print("  ClearML task logged successfully")

    except Exception as e:
        print(f"  [WARN] ClearML logging failed: {e}")


# ---------- HTML report generation -----------------------------------------

def generate_html_report(data: dict, supabase_data: list[dict]):
    """Generate a comprehensive HTML report."""
    print("[3/4] Generating HTML report...")

    EXPERIMENTS.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Extract key data
    latest = data.get("latest_eval") or {}
    summary = data.get("quant_summary") or {}
    bankroll = data.get("bankroll") or {}
    atr_history = summary.get("atr_history", [])
    models = summary.get("models", {})
    evolution = summary.get("evolution", {})
    traders = data.get("traders", {})
    departments = data.get("departments", {})

    # Build text-based Brier chart (ASCII art embedded in HTML <pre>)
    brier_chart = _build_brier_chart(atr_history, models)

    # Build models table rows
    model_rows = ""
    for name, m in sorted(models.items(), key=lambda x: x[1].get("brier", 1)):
        brier = m.get("brier", "N/A")
        weight = m.get("weight", 0)
        status = m.get("status", "?")
        status_color = "#00e676" if status == "ATR_BEST" else ("#ffc107" if status == "ACTIVE" else "#ef5350")
        model_rows += f"""
        <tr>
            <td>{name}</td>
            <td><strong>{brier}</strong></td>
            <td>{weight:.0%}</td>
            <td><span style="color: {status_color};">{status}</span></td>
        </tr>"""

    # Build ATR history rows
    atr_rows = ""
    for atr in reversed(atr_history):
        atr_rows += f"""
        <tr>
            <td>{atr.get('date', 'N/A')}</td>
            <td><strong>{atr.get('brier', 'N/A')}</strong></td>
            <td>{atr.get('model', 'N/A')}</td>
            <td>{atr.get('features', 'N/A')}</td>
            <td>{atr.get('notes', '')}</td>
        </tr>"""

    # Build trader rows
    trader_rows = ""
    for tname, tdata in sorted(traders.items()):
        if isinstance(tdata, dict):
            balance = tdata.get("balance", tdata.get("bankroll", "N/A"))
            roi = tdata.get("roi_pct", tdata.get("total_roi_pct", "N/A"))
            wins = tdata.get("wins", tdata.get("total_wins", "N/A"))
            losses = tdata.get("losses", tdata.get("total_losses", "N/A"))
            trader_rows += f"""
            <tr>
                <td>{tname}</td>
                <td>${balance:,.2f}</td>
                <td>{roi}%</td>
                <td>{wins}W / {losses}L</td>
            </tr>""" if isinstance(balance, (int, float)) else f"""
            <tr>
                <td>{tname}</td>
                <td>{balance}</td>
                <td>{roi}</td>
                <td>{wins}/{losses}</td>
            </tr>"""

    # Build department rows
    dept_rows = ""
    for dname, ddata in sorted(departments.items()):
        if isinstance(ddata, dict):
            status = ddata.get("status", ddata.get("health", "?"))
            iterations = ddata.get("iterations", ddata.get("total_iterations", "?"))
            last_run = ddata.get("last_run", ddata.get("timestamp", "?"))
            if isinstance(last_run, str) and len(last_run) > 19:
                last_run = last_run[:19]
            dept_rows += f"""
            <tr>
                <td>{dname}</td>
                <td>{status}</td>
                <td>{iterations}</td>
                <td>{last_run}</td>
            </tr>"""

    # Feature importance (from latest eval islands or models)
    feature_section = ""
    if latest.get("islands"):
        island_rows = ""
        for iname, idata in sorted(latest["islands"].items()):
            if isinstance(idata, dict):
                role = idata.get("role", "?")
                best = idata.get("best_brier", "N/A")
                mut = idata.get("mut", "N/A")
                island_rows += f"""
                <tr>
                    <td>{iname}</td>
                    <td>{role}</td>
                    <td>{best}</td>
                    <td>{mut}</td>
                </tr>"""
        feature_section = f"""
        <h2>Evolution Islands</h2>
        <table>
            <tr><th>Island</th><th>Role</th><th>Best Brier</th><th>Mutation Rate</th></tr>
            {island_rows}
        </table>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nomos42 Experiment Tracker</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        background: #0d1117; color: #c9d1d9; font-family: 'Cascadia Code', 'JetBrains Mono', monospace;
        padding: 20px; max-width: 1200px; margin: 0 auto;
    }}
    h1 {{ color: #58a6ff; margin-bottom: 5px; font-size: 1.8em; }}
    h2 {{ color: #79c0ff; margin: 25px 0 10px; font-size: 1.3em; border-bottom: 1px solid #21262d; padding-bottom: 5px; }}
    .subtitle {{ color: #8b949e; margin-bottom: 20px; }}
    .kpi-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px; margin: 20px 0;
    }}
    .kpi {{
        background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 15px; text-align: center;
    }}
    .kpi .value {{ font-size: 2em; font-weight: bold; color: #58a6ff; }}
    .kpi .label {{ color: #8b949e; font-size: 0.85em; margin-top: 5px; }}
    .kpi.good .value {{ color: #3fb950; }}
    .kpi.bad .value {{ color: #f85149; }}
    .kpi.warn .value {{ color: #d29922; }}
    table {{
        width: 100%; border-collapse: collapse; margin: 10px 0;
        background: #161b22; border-radius: 8px; overflow: hidden;
    }}
    th {{ background: #21262d; color: #79c0ff; padding: 10px; text-align: left; font-weight: 600; }}
    td {{ padding: 8px 10px; border-top: 1px solid #21262d; }}
    tr:hover td {{ background: #1c2128; }}
    pre {{
        background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 15px; overflow-x: auto; font-size: 0.9em; line-height: 1.4;
    }}
    .chart-label {{ color: #8b949e; font-size: 0.8em; }}
    .footer {{ color: #484f58; margin-top: 30px; padding-top: 10px; border-top: 1px solid #21262d; font-size: 0.8em; }}
    .badge {{
        display: inline-block; padding: 2px 8px; border-radius: 12px;
        font-size: 0.75em; font-weight: 600;
    }}
    .badge-green {{ background: #238636; color: #fff; }}
    .badge-red {{ background: #da3633; color: #fff; }}
    .badge-yellow {{ background: #9e6a03; color: #fff; }}
</style>
</head>
<body>

<h1>Nomos42 Experiment Tracker</h1>
<p class="subtitle">Generated: {now} | Engine: {latest.get('feature_engine_version', 'N/A')} | Gen: {evolution.get('generations', 'N/A')}</p>

<div class="kpi-grid">
    <div class="kpi {'good' if latest.get('brier_score', 1) < 0.22 else 'warn'}">
        <div class="value">{latest.get('brier_score', 'N/A')}</div>
        <div class="label">ATR Brier Score</div>
    </div>
    <div class="kpi">
        <div class="value">{latest.get('features', 'N/A')}</div>
        <div class="label">Features Selected</div>
    </div>
    <div class="kpi {'bad' if bankroll.get('total_profit', 0) < 0 else 'good'}">
        <div class="value">${bankroll.get('balance', 'N/A')}</div>
        <div class="label">Bankroll</div>
    </div>
    <div class="kpi {'bad' if latest.get('roi_pct', 0) < 0 else 'good'}">
        <div class="value">{latest.get('roi_pct', 'N/A')}%</div>
        <div class="label">ROI</div>
    </div>
    <div class="kpi {'bad' if latest.get('sharpe_ratio', 0) < 0 else 'good'}">
        <div class="value">{latest.get('sharpe_ratio', 'N/A')}</div>
        <div class="label">Sharpe Ratio</div>
    </div>
    <div class="kpi">
        <div class="value">{evolution.get('islands', 'N/A')}</div>
        <div class="label">Evolution Islands</div>
    </div>
</div>

<h2>Brier Score Progression</h2>
<pre>
{brier_chart}
</pre>

<h2>Model Leaderboard</h2>
<table>
    <tr><th>Model</th><th>Brier</th><th>Weight</th><th>Status</th></tr>
    {model_rows}
</table>

<h2>All-Time Record (ATR) History</h2>
<table>
    <tr><th>Date</th><th>Brier</th><th>Model</th><th>Features</th><th>Notes</th></tr>
    {atr_rows}
</table>

{feature_section}

{"<h2>Trading Floor Agents</h2>" + '<table><tr><th>Trader</th><th>Balance</th><th>ROI</th><th>Record</th></tr>' + trader_rows + '</table>' if trader_rows else ""}

{"<h2>Department Status</h2>" + '<table><tr><th>Department</th><th>Status</th><th>Iterations</th><th>Last Run</th></tr>' + dept_rows + '</table>' if dept_rows else ""}

<h2>Evolution Config</h2>
<table>
    <tr><th>Parameter</th><th>Value</th></tr>
    <tr><td>Generations</td><td>{evolution.get('generations', 'N/A')}</td></tr>
    <tr><td>Population</td><td>{evolution.get('population', 'N/A')}</td></tr>
    <tr><td>Islands</td><td>{evolution.get('islands', 'N/A')}</td></tr>
    <tr><td>Raw Features</td><td>{evolution.get('raw_features', 'N/A')}</td></tr>
    <tr><td>Selected Features</td><td>{evolution.get('selected_features', 'N/A')}</td></tr>
    <tr><td>Max Features</td><td>200 (hard cap)</td></tr>
    <tr><td>Feature Engine</td><td>{evolution.get('feature_engine_version', 'N/A')}</td></tr>
    <tr><td>Categories</td><td>{evolution.get('categories', 'N/A')}</td></tr>
    <tr><td>Platform</td><td>{evolution.get('platform', 'N/A')}</td></tr>
    <tr><td>Kaggle Iterations</td><td>{evolution.get('kaggle_iterations', 'N/A')}</td></tr>
</table>

<h2>Targets vs Actual</h2>
<table>
    <tr><th>Metric</th><th>Target</th><th>Actual</th><th>Gap</th></tr>
    <tr>
        <td>Brier Score</td><td>&lt; 0.200</td>
        <td>{latest.get('brier_score', 'N/A')}</td>
        <td style="color: #f85149;">{latest.get('brier_score', 0) - 0.2:+.5f}</td>
    </tr>
    <tr>
        <td>ROI</td><td>&gt; 5%</td>
        <td>{latest.get('roi_pct', 'N/A')}%</td>
        <td style="color: {'#3fb950' if latest.get('roi_pct', 0) > 5 else '#f85149'};">{latest.get('roi_pct', 0) - 5:+.2f}%</td>
    </tr>
    <tr>
        <td>Sharpe Ratio</td><td>&gt; 1.5</td>
        <td>{latest.get('sharpe_ratio', 'N/A')}</td>
        <td style="color: {'#3fb950' if latest.get('sharpe_ratio', 0) > 1.5 else '#f85149'};">{latest.get('sharpe_ratio', 0) - 1.5:+.2f}</td>
    </tr>
</table>

<div class="footer">
    Nomos42 Experiment Tracker | Data sources: local JSON files
    {' + Supabase' if supabase_data else ''} {' + ClearML' if clearml_available else ''}
    | Auto-generated by scripts/monitoring/experiment-tracker.py
</div>

</body>
</html>"""

    REPORT_PATH.write_text(html)
    print(f"  Report written to {REPORT_PATH} ({len(html)} bytes)")


def _build_brier_chart(atr_history: list[dict], models: dict) -> str:
    """Build a text-based horizontal bar chart for Brier scores."""
    lines = []
    lines.append("  BRIER SCORE PROGRESSION (lower is better)")
    lines.append("  " + "-" * 60)

    # ATR history timeline
    if atr_history:
        lines.append("")
        lines.append("  ATR Timeline:")
        max_brier = max(a.get("brier", 0) for a in atr_history)
        min_brier = min(a.get("brier", 0) for a in atr_history)
        chart_width = 50

        for atr in atr_history:
            brier = atr.get("brier", 0)
            date = atr.get("date", "????-??-??")
            model = atr.get("model", "?")[:15]

            # Scale bar (inverted -- lower brier = longer green bar)
            # Range from 0.20 to 0.23
            lo, hi = 0.200, 0.230
            frac = 1.0 - max(0, min(1, (brier - lo) / (hi - lo)))
            bar_len = int(frac * chart_width)
            bar = "\u2588" * bar_len + "\u2591" * (chart_width - bar_len)

            lines.append(f"  {date} |{bar}| {brier:.5f} ({model})")

    # Current model comparison
    if models:
        lines.append("")
        lines.append("  Current Models:")
        chart_width = 50
        for name, m in sorted(models.items(), key=lambda x: x[1].get("brier", 1)):
            brier = m.get("brier", 0)
            lo, hi = 0.200, 0.230
            frac = 1.0 - max(0, min(1, (brier - lo) / (hi - lo)))
            bar_len = int(frac * chart_width)
            bar = "\u2588" * bar_len + "\u2591" * (chart_width - bar_len)
            lines.append(f"  {name:>15} |{bar}| {brier:.5f}")

    lines.append("")
    lines.append("  " + "-" * 60)
    lines.append(f"  Target: 0.20000 | Current ATR: {min_brier:.5f}" if atr_history else "  No ATR data")

    return "\n".join(lines)


# ---------- save experiment snapshot ---------------------------------------

def save_experiment_snapshot(data: dict):
    """Save a timestamped experiment snapshot for the wandb-style logger."""
    print("[4/4] Saving experiment snapshot...")

    runs_dir = EXPERIMENTS / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = runs_dir / run_id
    run_dir.mkdir(exist_ok=True)

    # Config
    config = {
        "feature_engine_version": (data.get("latest_eval") or {}).get("feature_engine_version", "unknown"),
        "model": (data.get("latest_eval") or {}).get("model", "unknown"),
        "features": (data.get("latest_eval") or {}).get("features", 0),
        "categories": (data.get("latest_eval") or {}).get("categories", 0),
        "platform": (data.get("latest_eval") or {}).get("platform", "unknown"),
        "evolution_generations": (data.get("quant_summary") or {}).get("evolution", {}).get("generations", 0),
        "evolution_islands": (data.get("quant_summary") or {}).get("evolution", {}).get("islands", 0),
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))

    # Metrics
    latest = data.get("latest_eval") or {}
    metrics = {
        "brier_score": latest.get("brier_score", None),
        "accuracy": latest.get("accuracy", None),
        "roi_pct": latest.get("roi_pct", None),
        "sharpe_ratio": latest.get("sharpe_ratio", None),
        "max_drawdown_pct": latest.get("max_drawdown_pct", None),
        "win_rate_pct": latest.get("win_rate_pct", None),
        "bankroll": (data.get("bankroll") or {}).get("balance", None),
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # Summary
    summary_data = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "metrics": metrics,
        "models": (data.get("quant_summary") or {}).get("models", {}),
        "atr_history": (data.get("quant_summary") or {}).get("atr_history", []),
        "traders": {k: {"balance": v.get("balance", v.get("bankroll"))} for k, v in data.get("traders", {}).items() if isinstance(v, dict)},
    }
    (run_dir / "summary.json").write_text(json.dumps(summary_data, indent=2, default=str))

    print(f"  Snapshot saved to {run_dir}")


# ---------- main -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Nomos42 Experiment Tracker")
    parser.add_argument("--report-only", action="store_true", help="Only generate HTML report, skip ClearML")
    parser.add_argument("--clearml", action="store_true", help="Enable ClearML logging")
    parser.add_argument("--supabase", action="store_true", help="Also pull data from Supabase")
    args = parser.parse_args()

    print("=" * 60)
    print("  NOMOS42 EXPERIMENT TRACKER")
    print("=" * 60)

    # Step 1: Collect data
    data = collect_experiments()

    # Optional: Supabase
    supabase_data = []
    if args.supabase:
        supabase_data = collect_from_supabase()

    # Step 2: ClearML logging
    if args.clearml and not args.report_only:
        log_to_clearml(data, supabase_data)
    else:
        print("[2/4] ClearML logging skipped (use --clearml to enable)")

    # Step 3: HTML report
    generate_html_report(data, supabase_data)

    # Step 4: Save snapshot
    save_experiment_snapshot(data)

    print()
    print(f"  Report: {REPORT_PATH}")
    print(f"  Runs:   {EXPERIMENTS / 'runs'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
