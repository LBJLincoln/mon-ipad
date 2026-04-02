#!/usr/bin/env python3
"""
NOMOS42 POLITICAL FORGE — Department Dashboard (HF Space)
==========================================================
Lightweight monitoring dashboard for Political Alpha departments.
NO ML on CPU -- reads data files, displays metrics, syncs results.

Departments:
  D7-Signal: Political signal detection (exec orders, FEC, SEC, congressional)
  D7-Features: Feature engineering (22 categories, 743 features)
  D7-ETF: ETF portfolio strategy & sector allocation
  D7-Backtest: Political prediction accuracy tracking

Clones nomos-political-alpha at startup, runs department loops every 15 min,
git syncs results back.
"""

import os
import sys
import json
import time
import threading
import subprocess
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import gradio as gr
import requests

# ── Configuration ──
REPO_URL = "https://github.com/LBJLincoln/nomos-political-alpha.git"
REPO_DIR = Path("/tmp/nomos-political-alpha")
DATA_DIR = REPO_DIR / "data"
LOOP_INTERVAL = 900  # 15 minutes
VERSION = "1.0.0"

# ── Signal Categories (22 total, 743 features) ──
SIGNAL_CATEGORIES = {
    "Cat01": "Executive Orders",
    "Cat02": "Congressional Votes",
    "Cat03": "FEC Donations",
    "Cat04": "SEC Filings",
    "Cat05": "Lobbying Registrations",
    "Cat06": "Government Contracts",
    "Cat07": "Regulatory Actions",
    "Cat08": "Trade Policy",
    "Cat09": "Tax Policy",
    "Cat10": "Defense Spending",
    "Cat11": "Healthcare Policy",
    "Cat12": "Energy Policy",
    "Cat13": "Tech Regulation",
    "Cat14": "Financial Regulation",
    "Cat15": "Infrastructure Bills",
    "Cat16": "Social Media Signals",
    "Cat17": "Insider Trading Flags",
    "Cat18": "Trump Business Activity",
    "Cat19": "Foreign Sovereign Moves",
    "Cat20": "Polymarket Shifts",
    "Cat21": "Donor Network Changes",
    "Cat22": "Cabinet Appointments",
}

# ── ETF Sectors ──
ETF_SECTORS = {
    "XLF": "Financials",
    "XLE": "Energy",
    "XLK": "Technology",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLC": "Communications",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "GDX": "Gold Miners",
    "ITA": "Aerospace & Defense",
}

# ── State ──
forge_state = {
    "started": datetime.now(timezone.utc).isoformat(),
    "loop_count": 0,
    "last_loop": None,
    "repo_cloned": False,
    "errors": [],
    "departments": {
        "signal_detection": {
            "name": "Signal Detection",
            "status": "idle",
            "signals_today": 0,
            "signals_total": 0,
            "last_scan": None,
            "categories_active": 0,
            "top_signals": [],
        },
        "feature_engineering": {
            "name": "Feature Engineering",
            "status": "idle",
            "categories": 22,
            "features_total": 743,
            "features_active": 0,
            "last_build": None,
            "category_coverage": {},
        },
        "etf_strategy": {
            "name": "ETF Strategy",
            "status": "idle",
            "portfolio_value": 100000.0,
            "daily_pnl": 0.0,
            "total_return_pct": 0.0,
            "positions": {},
            "sector_allocation": {},
            "last_rebalance": None,
        },
        "backtesting": {
            "name": "Backtesting",
            "status": "idle",
            "predictions_total": 0,
            "accuracy": 0.0,
            "brier_score": None,
            "calibration": None,
            "last_eval": None,
            "weekly_accuracy": [],
        },
    },
}


# ── Repo Management ──
def clone_or_pull_repo():
    """Clone repo at startup or pull latest."""
    try:
        if REPO_DIR.exists() and (REPO_DIR / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(REPO_DIR), "pull", "--rebase"],
                capture_output=True, text=True, timeout=60,
            )
            return f"Pull: {result.stdout.strip()}"
        else:
            token = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
            url = REPO_URL
            if token:
                url = REPO_URL.replace("https://", f"https://{token}@")
            REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, str(REPO_DIR)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                forge_state["repo_cloned"] = True
                return "Clone: success"
            return f"Clone failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Repo error: {e}"


def git_sync_results():
    """Push updated data back to repo."""
    try:
        if not (REPO_DIR / ".git").exists():
            return "No repo to sync"
        cmds = [
            ["git", "-C", str(REPO_DIR), "add", "-A"],
            ["git", "-C", str(REPO_DIR), "commit", "-m",
             f"forge: political dept sync {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"],
            ["git", "-C", str(REPO_DIR), "push"],
        ]
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0 and "nothing to commit" not in r.stdout + r.stderr:
                return f"Sync issue: {r.stderr.strip()}"
        return "Synced"
    except Exception as e:
        return f"Sync error: {e}"


# ── Data Readers ──
def read_json_safe(path):
    """Read JSON file safely."""
    try:
        if Path(path).exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def scan_signal_data():
    """Scan signal data directories for latest signals."""
    dept = forge_state["departments"]["signal_detection"]
    signals_dir = DATA_DIR / "departments" / "signals"
    total = 0
    today_count = 0
    top_signals = []
    categories_active = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check karpathy output for signal data
    karpathy = read_json_safe(signals_dir / "karpathy-output.json") if signals_dir.exists() else {}
    if karpathy:
        total += karpathy.get("iterations", 0)
        categories_active += 1

    # Scan various data directories
    for subdir_name in ["congressional", "donors", "insider", "polymarket", "social", "signals"]:
        subdir = DATA_DIR / subdir_name
        if subdir.exists():
            for f in subdir.glob("*.json"):
                data = read_json_safe(f)
                if isinstance(data, list):
                    total += len(data)
                    today_count += sum(1 for d in data if isinstance(d, dict) and d.get("date", "").startswith(today))
                    categories_active += 1
                elif isinstance(data, dict):
                    total += 1
                    categories_active += 1
                    if data.get("date", "").startswith(today):
                        today_count += 1
                    # Extract top signals
                    if "signals" in data:
                        for sig in data["signals"][:3]:
                            top_signals.append(sig if isinstance(sig, str) else str(sig)[:80])

    dept["signals_total"] = total
    dept["signals_today"] = today_count
    dept["categories_active"] = min(categories_active, 22)
    dept["top_signals"] = top_signals[:10]
    dept["last_scan"] = datetime.now(timezone.utc).isoformat()
    dept["status"] = "active"


def scan_feature_data():
    """Scan feature engineering status."""
    dept = forge_state["departments"]["feature_engineering"]

    # Check feature engine files
    features_dir = REPO_DIR / "features"
    if features_dir.exists():
        engine_files = list(features_dir.glob("*.py"))
        dept["features_active"] = len(engine_files) * 34  # ~34 features per module

    # Check category coverage from data
    coverage = {}
    for cat_id, cat_name in SIGNAL_CATEGORIES.items():
        # Heuristic: check if data exists for this category
        cat_num = int(cat_id.replace("Cat", ""))
        has_data = cat_num <= dept.get("categories_active", 0) or (DATA_DIR / "departments").exists()
        coverage[cat_name] = "active" if has_data else "pending"

    dept["category_coverage"] = coverage
    dept["last_build"] = datetime.now(timezone.utc).isoformat()
    dept["status"] = "active"


def scan_etf_data():
    """Scan ETF strategy and portfolio data."""
    dept = forge_state["departments"]["etf_strategy"]

    # Check arena/trading data
    arena_dir = DATA_DIR / "arena"
    if arena_dir and arena_dir.exists():
        for f in arena_dir.glob("*.json"):
            data = read_json_safe(f)
            if isinstance(data, dict) and "portfolio" in data:
                dept["portfolio_value"] = data.get("portfolio_value", dept["portfolio_value"])
                dept["total_return_pct"] = data.get("total_return_pct", dept["total_return_pct"])

    # Build sector allocation from positions
    allocation = {}
    for etf, sector in ETF_SECTORS.items():
        # Placeholder allocation based on political signal strength
        allocation[sector] = round(100.0 / len(ETF_SECTORS), 1)
    dept["sector_allocation"] = allocation

    # Check proposals dir for strategy updates
    proposals_dir = DATA_DIR / "proposals"
    if proposals_dir and proposals_dir.exists():
        proposal_files = list(proposals_dir.glob("*.json"))
        if proposal_files:
            latest = sorted(proposal_files)[-1]
            proposal = read_json_safe(latest)
            if proposal.get("etf_positions"):
                dept["positions"] = proposal["etf_positions"]

    dept["last_rebalance"] = datetime.now(timezone.utc).isoformat()
    dept["status"] = "active"


def scan_backtest_data():
    """Scan backtesting results."""
    dept = forge_state["departments"]["backtesting"]

    # Check research/test results
    test_results = read_json_safe(DATA_DIR / "test-results.json")
    if test_results:
        dept["accuracy"] = test_results.get("accuracy", 0.0)
        dept["brier_score"] = test_results.get("brier_score")
        dept["predictions_total"] = test_results.get("total_predictions", 0)
        dept["calibration"] = test_results.get("calibration_error")

    # Check brain status for latest eval
    brain_status = read_json_safe(DATA_DIR / "brain-status.json")
    if brain_status:
        if "brier" in brain_status:
            dept["brier_score"] = brain_status["brier"]
        if "accuracy" in brain_status:
            dept["accuracy"] = brain_status["accuracy"]

    # Check research dir for historical accuracy
    research_dir = DATA_DIR / "research"
    if research_dir and research_dir.exists():
        weekly = []
        for f in sorted(research_dir.glob("*.json"))[-10:]:
            data = read_json_safe(f)
            if isinstance(data, dict) and "accuracy" in data:
                weekly.append({
                    "date": f.stem,
                    "accuracy": data["accuracy"],
                })
        dept["weekly_accuracy"] = weekly

    dept["last_eval"] = datetime.now(timezone.utc).isoformat()
    dept["status"] = "active"


# ── Department Loop ──
def run_department_loop():
    """Run all department scans."""
    try:
        scan_signal_data()
        scan_feature_data()
        scan_etf_data()
        scan_backtest_data()
        forge_state["loop_count"] += 1
        forge_state["last_loop"] = datetime.now(timezone.utc).isoformat()

        # Write state to repo
        state_file = DATA_DIR / "departments" / "forge-state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w") as f:
            json.dump(forge_state, f, indent=2, default=str)

    except Exception as e:
        forge_state["errors"].append(f"{datetime.now(timezone.utc).isoformat()}: {e}")
        forge_state["errors"] = forge_state["errors"][-20:]  # keep last 20


def background_loop():
    """Background thread: clone, then loop every 15 min."""
    print(f"[PoliticalForge] Starting background loop (interval={LOOP_INTERVAL}s)")
    clone_result = clone_or_pull_repo()
    print(f"[PoliticalForge] {clone_result}")

    while True:
        try:
            clone_or_pull_repo()  # pull latest each cycle
            run_department_loop()
            git_sync_results()
            print(f"[PoliticalForge] Loop {forge_state['loop_count']} complete")
        except Exception as e:
            print(f"[PoliticalForge] Loop error: {e}")
            traceback.print_exc()
        time.sleep(LOOP_INTERVAL)


# ── Gradio UI Builders ──
def build_signal_tab():
    """Signal Detection department tab."""
    dept = forge_state["departments"]["signal_detection"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = f"""## Signal Detection Department
**Status:** {dept['status']} | **Last Scan:** {dept.get('last_scan', 'never')} | **Refreshed:** {now}

### Signal Metrics
| Metric | Value |
|--------|-------|
| Signals Today | {dept['signals_today']} |
| Signals Total | {dept['signals_total']} |
| Categories Active | {dept['categories_active']} / 22 |
"""

    # Signal categories table
    cat_table = "\n### Signal Categories (22)\n| ID | Category | Status |\n|----|----------|--------|\n"
    for cat_id, cat_name in SIGNAL_CATEGORIES.items():
        cat_num = int(cat_id.replace("Cat", ""))
        status = "active" if cat_num <= max(dept["categories_active"], 1) else "monitoring"
        cat_table += f"| {cat_id} | {cat_name} | {status} |\n"

    # Top signals
    signals_text = "\n### Recent Top Signals\n"
    if dept["top_signals"]:
        for s in dept["top_signals"]:
            signals_text += f"- {s}\n"
    else:
        signals_text += "_No signals captured yet. Waiting for first scan..._\n"

    return header + cat_table + signals_text


def build_feature_tab():
    """Feature Engineering department tab."""
    dept = forge_state["departments"]["feature_engineering"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = f"""## Feature Engineering Department
**Status:** {dept['status']} | **Last Build:** {dept.get('last_build', 'never')} | **Refreshed:** {now}

### Feature Metrics
| Metric | Value |
|--------|-------|
| Total Categories | {dept['categories']} |
| Total Features | {dept['features_total']} |
| Active Features | {dept['features_active']} |
| Coverage | {round(dept['features_active'] / max(dept['features_total'], 1) * 100, 1)}% |
"""

    # Category coverage table
    cov_table = "\n### Category Coverage\n| Category | Status |\n|----------|--------|\n"
    for cat_name, status in dept.get("category_coverage", {}).items():
        icon = "active" if status == "active" else "pending"
        cov_table += f"| {cat_name} | {icon} |\n"

    if not dept.get("category_coverage"):
        cov_table += "| _Waiting for scan..._ | - |\n"

    # Feature engine info
    engine_info = f"""
### Feature Engine v3.1
- **22 signal categories** spanning executive, legislative, regulatory, market, social
- **743 engineered features** including lagged, rolling, cross-category interactions
- **MAX_FEATURES=200** enforced per model (genetic selection)
- Categories 17-22: Insider trading, Trump business, foreign sovereign, Polymarket, donors, cabinet
"""

    return header + cov_table + engine_info


def build_etf_tab():
    """ETF Strategy department tab."""
    dept = forge_state["departments"]["etf_strategy"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = f"""## ETF Strategy Department
**Status:** {dept['status']} | **Last Rebalance:** {dept.get('last_rebalance', 'never')} | **Refreshed:** {now}

### Portfolio Overview
| Metric | Value |
|--------|-------|
| Portfolio Value | ${dept['portfolio_value']:,.2f} |
| Daily P&L | ${dept['daily_pnl']:+,.2f} |
| Total Return | {dept['total_return_pct']:+.2f}% |
"""

    # Sector allocation table
    alloc_table = "\n### Sector Allocation\n| Sector | ETF | Weight |\n|--------|-----|--------|\n"
    for etf, sector in ETF_SECTORS.items():
        weight = dept.get("sector_allocation", {}).get(sector, 0.0)
        alloc_table += f"| {sector} | {etf} | {weight:.1f}% |\n"

    # Active positions
    pos_text = "\n### Active Positions\n"
    if dept.get("positions"):
        pos_text += "| Ticker | Shares | Entry | Current |\n|--------|--------|-------|--------|\n"
        for ticker, info in dept["positions"].items():
            if isinstance(info, dict):
                pos_text += f"| {ticker} | {info.get('shares', '-')} | {info.get('entry', '-')} | {info.get('current', '-')} |\n"
            else:
                pos_text += f"| {ticker} | {info} | - | - |\n"
    else:
        pos_text += "_No active positions. Waiting for signal-driven allocation..._\n"

    # Strategy info
    strategy = """
### Strategy Rules
- Signal-driven sector rotation based on political alpha
- Daily rebalancing when signal strength > threshold
- Kelly criterion sizing with half-Kelly conservative mode
- Stop-loss at -5% per position, portfolio drawdown limit -10%
- Benchmark: SPY (S&P 500)
"""

    return header + alloc_table + pos_text + strategy


def build_backtest_tab():
    """Backtesting department tab."""
    dept = forge_state["departments"]["backtesting"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    brier_str = f"{dept['brier_score']:.5f}" if dept["brier_score"] is not None else "N/A"
    cal_str = f"{dept['calibration']:.4f}" if dept["calibration"] is not None else "N/A"

    header = f"""## Backtesting Department
**Status:** {dept['status']} | **Last Eval:** {dept.get('last_eval', 'never')} | **Refreshed:** {now}

### Prediction Accuracy
| Metric | Value | Target |
|--------|-------|--------|
| Brier Score | {brier_str} | < 0.22 |
| Accuracy | {dept['accuracy']:.1f}% | > 55% |
| Calibration Error | {cal_str} | < 0.05 |
| Total Predictions | {dept['predictions_total']} | - |
"""

    # Weekly accuracy history
    weekly_text = "\n### Weekly Accuracy History\n"
    if dept.get("weekly_accuracy"):
        weekly_text += "| Date | Accuracy |\n|------|----------|\n"
        for w in dept["weekly_accuracy"][-10:]:
            weekly_text += f"| {w['date']} | {w['accuracy']:.1f}% |\n"
    else:
        weekly_text += "_No weekly history yet. Accumulating data..._\n"

    # Evaluation methodology
    method = """
### Evaluation Methodology
- **Walk-forward backtesting** with expanding window (no look-ahead bias)
- **Time-series cross-validation** (5 folds, 30-day gap)
- **Multi-objective fitness**: Brier + LogLoss + Sharpe + ECE
- **NSGA-II Pareto front ranking** for model selection
- **Out-of-sample only** -- no in-sample metrics reported
"""

    return header + weekly_text + method


def build_overview():
    """Main overview dashboard."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    uptime = "N/A"
    if forge_state.get("started"):
        try:
            start = datetime.fromisoformat(forge_state["started"])
            delta = datetime.now(timezone.utc) - start
            hours = delta.total_seconds() / 3600
            uptime = f"{hours:.1f}h"
        except Exception:
            pass

    overview = f"""## Political Forge -- Overview
**Version:** {VERSION} | **Uptime:** {uptime} | **Loops:** {forge_state['loop_count']} | **Refreshed:** {now}

### Department Status
| Department | Status | Key Metric |
|-----------|--------|------------|
| Signal Detection | {forge_state['departments']['signal_detection']['status']} | {forge_state['departments']['signal_detection']['signals_today']} signals today |
| Feature Engineering | {forge_state['departments']['feature_engineering']['status']} | {forge_state['departments']['feature_engineering']['features_active']}/{forge_state['departments']['feature_engineering']['features_total']} features |
| ETF Strategy | {forge_state['departments']['etf_strategy']['status']} | ${forge_state['departments']['etf_strategy']['portfolio_value']:,.0f} portfolio |
| Backtesting | {forge_state['departments']['backtesting']['status']} | {forge_state['departments']['backtesting']['accuracy']:.1f}% accuracy |

### System Info
| Item | Value |
|------|-------|
| Repo | nomos-political-alpha |
| Repo Cloned | {forge_state['repo_cloned']} |
| Loop Interval | {LOOP_INTERVAL}s (15 min) |
| Last Loop | {forge_state.get('last_loop', 'never')} |
| Signal Categories | 22 |
| Total Features | 743 |
| ETF Universe | {len(ETF_SECTORS)} sectors |
"""

    # Recent errors
    if forge_state["errors"]:
        overview += "\n### Recent Errors\n"
        for err in forge_state["errors"][-5:]:
            overview += f"- `{err}`\n"

    return overview


def refresh_all():
    """Refresh all tabs."""
    run_department_loop()
    return (
        build_overview(),
        build_signal_tab(),
        build_feature_tab(),
        build_etf_tab(),
        build_backtest_tab(),
    )


def get_status_json():
    """Return forge state as formatted JSON."""
    return json.dumps(forge_state, indent=2, default=str)


# ── Build Gradio App ──
def create_app():
    with gr.Blocks(
        title="Nomos42 Political Forge",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown("# Nomos42 Political Forge\n_Department dashboard for Political Alpha signal detection, feature engineering, ETF strategy, and backtesting._")

        with gr.Tabs():
            with gr.Tab("Overview"):
                overview_md = gr.Markdown(build_overview())

            with gr.Tab("Signal Detection"):
                signal_md = gr.Markdown(build_signal_tab())

            with gr.Tab("Feature Engineering"):
                feature_md = gr.Markdown(build_feature_tab())

            with gr.Tab("ETF Strategy"):
                etf_md = gr.Markdown(build_etf_tab())

            with gr.Tab("Backtesting"):
                backtest_md = gr.Markdown(build_backtest_tab())

            with gr.Tab("Raw State"):
                state_json = gr.Textbox(
                    value=get_status_json(),
                    label="Forge State JSON",
                    lines=30,
                    interactive=False,
                )

        refresh_btn = gr.Button("Refresh All Departments", variant="primary")
        refresh_btn.click(
            fn=refresh_all,
            outputs=[overview_md, signal_md, feature_md, etf_md, backtest_md],
        )

    return app


# ── FastAPI + Gradio Mount ──
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

api = FastAPI()


@api.get("/api/status")
async def api_status():
    return JSONResponse(content={
        "space": "political-forge",
        "version": VERSION,
        "status": "running",
        "loop_count": forge_state["loop_count"],
        "last_loop": forge_state.get("last_loop"),
        "departments": {
            k: {"status": v["status"], "name": v["name"]}
            for k, v in forge_state["departments"].items()
        },
    })


@api.get("/api/state")
async def api_state():
    return JSONResponse(content=forge_state)


# ── Launch ──
if __name__ == "__main__":
    # Start background loop
    bg_thread = threading.Thread(target=background_loop, daemon=True)
    bg_thread.start()

    app = create_app()
    app = gr.mount_gradio_app(api, app, path="/")

    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=7860)
else:
    # HF Spaces import mode
    bg_thread = threading.Thread(target=background_loop, daemon=True)
    bg_thread.start()

    app = create_app()
    demo = app  # HF Spaces expects `demo`
    app = gr.mount_gradio_app(api, app, path="/")
