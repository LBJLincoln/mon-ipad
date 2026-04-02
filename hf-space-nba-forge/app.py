#!/usr/bin/env python3
"""
Nomos42 NBA Forge -- Department Karpathy Loops
================================================
Autonomous monitoring space for the NBA Quant AI prediction system.
Runs 5 department loops every 10 minutes on CPU (no ML training).

Departments:
  D1 Prediction Pipeline -- validate outputs, check freshness
  D2 Feature Engine      -- monitor version, feature count, categories
  D3 Model Evaluation    -- track Brier scores, walk-forward performance
  D4 Data Quality        -- data freshness, missing games, odds quality
  D5 Evolution Sync      -- poll 6 HF islands, track best configs
"""

import os
import json
import time
import threading
import subprocess
import traceback
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

import gradio as gr

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_URL = "https://github.com/LBJLincoln/nomos-nba-agent.git"
REPO_DIR = Path("/tmp/nomos-nba-agent")
DATA_DIR = REPO_DIR / "data"

CYCLE_INTERVAL_SEC = 600  # 10 minutes
VERSION = "1.0.0"

# HF Evolution Islands -- public status endpoints
HF_ISLANDS = {
    "S10": {
        "url": "https://nomos42-nba-quant.hf.space",
        "role": "exploitation",
        "owner": "Nomos42",
        "space": "nba-quant",
    },
    "S11": {
        "url": "https://nomos42-nba-quant-2.hf.space",
        "role": "exploration",
        "owner": "Nomos42",
        "space": "nba-quant-2",
    },
    "S12": {
        "url": "https://nomos42-nba-evo-3.hf.space",
        "role": "extra_trees_specialist",
        "owner": "Nomos42",
        "space": "nba-evo-3",
    },
    "S13": {
        "url": "https://nomos42-nba-evo-4.hf.space",
        "role": "catboost_specialist",
        "owner": "Nomos42",
        "space": "nba-evo-4",
    },
    "S14": {
        "url": "https://nomos42-nba-evo-5.hf.space",
        "role": "lightgbm_specialist",
        "owner": "Nomos42",
        "space": "nba-evo-5",
    },
    "S15": {
        "url": "https://nomos42-nba-evo-6.hf.space",
        "role": "wide_search",
        "owner": "Nomos42",
        "space": "nba-evo-6",
    },
}

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
forge_state: Dict[str, Any] = {
    "cycle": 0,
    "last_cycle_ts": None,
    "last_cycle_duration_sec": 0,
    "status": "INITIALIZING",
    "departments": {},
    "islands": {},
    "errors": [],
}

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def clone_or_pull_repo() -> bool:
    """Clone the repo if missing, otherwise git pull."""
    try:
        if not REPO_DIR.exists():
            print(f"[GIT] Cloning {REPO_URL} -> {REPO_DIR}")
            subprocess.run(
                ["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)],
                capture_output=True, text=True, timeout=120,
            )
        else:
            print("[GIT] Pulling latest...")
            subprocess.run(
                ["git", "-C", str(REPO_DIR), "pull", "--ff-only"],
                capture_output=True, text=True, timeout=60,
            )
        return True
    except Exception as e:
        print(f"[GIT] Error: {e}")
        forge_state["errors"].append(f"git: {e}")
        return False


def safe_read_json(path: Path) -> Optional[Dict]:
    """Read a JSON file, return None on failure."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        print(f"[READ] {path}: {e}")
    return None


# ---------------------------------------------------------------------------
# Department D1: Prediction Pipeline
# ---------------------------------------------------------------------------

def run_d1_prediction_pipeline() -> Dict[str, Any]:
    """Check prediction outputs for freshness and validity."""
    result = {
        "name": "Prediction Pipeline",
        "status": "OK",
        "issues": [],
        "metrics": {},
    }

    # Check predictions-today.json
    today_file = DATA_DIR / "nba-agent" / "predictions-today.json"
    predictions = safe_read_json(today_file)
    if predictions is None:
        result["status"] = "ERROR"
        result["issues"].append("predictions-today.json missing or unreadable")
        return result

    pred_date = predictions.get("date", "")
    generated_at = predictions.get("generated_at", "")
    games_count = predictions.get("games_count", 0)
    games = predictions.get("games", [])

    result["metrics"]["prediction_date"] = pred_date
    result["metrics"]["generated_at"] = generated_at
    result["metrics"]["games_count"] = games_count
    result["metrics"]["model_version"] = predictions.get("model_version", "unknown")
    result["metrics"]["bankroll"] = predictions.get("bankroll", 0)

    # Freshness check: generated_at should be within last 24 hours
    try:
        gen_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - gen_dt).total_seconds() / 3600
        result["metrics"]["age_hours"] = round(age_hours, 1)
        if age_hours > 24:
            result["issues"].append(f"Predictions are {age_hours:.0f}h old (>24h stale)")
            result["status"] = "WARNING"
    except Exception:
        result["issues"].append("Cannot parse generated_at timestamp")

    # Validate game entries
    valid_games = 0
    for g in games:
        home = g.get("home", "")
        away = g.get("away", "")
        hwp = g.get("home_win_prob", -1)
        if home and away and 0 <= hwp <= 1:
            valid_games += 1
        else:
            result["issues"].append(f"Invalid game entry: {home} vs {away}")

    result["metrics"]["valid_games"] = valid_games
    if games_count > 0 and valid_games < games_count:
        result["status"] = "WARNING"
        result["issues"].append(
            f"Only {valid_games}/{games_count} games have valid probabilities"
        )

    # Check value bets
    vb_file = DATA_DIR / "nba-agent" / "value-bets.json"
    vb = safe_read_json(vb_file)
    if vb:
        bets = vb.get("value_bets", [])
        result["metrics"]["value_bets_count"] = len(bets)
        total_kelly = sum(b.get("kelly_bet", 0) for b in bets)
        result["metrics"]["total_kelly_exposure"] = round(total_kelly, 2)
    else:
        result["metrics"]["value_bets_count"] = 0

    # Check historical prediction files
    pred_dir = DATA_DIR / "predictions"
    if pred_dir.exists():
        pred_files = sorted(pred_dir.glob("predictions-*.json"))
        result["metrics"]["historical_prediction_files"] = len(pred_files)
        if pred_files:
            latest = pred_files[-1].name
            result["metrics"]["latest_prediction_file"] = latest
    else:
        result["metrics"]["historical_prediction_files"] = 0

    if not result["issues"]:
        result["status"] = "OK"

    return result


# ---------------------------------------------------------------------------
# Department D2: Feature Engine
# ---------------------------------------------------------------------------

def run_d2_feature_engine() -> Dict[str, Any]:
    """Monitor feature engine version, feature count, category coverage."""
    result = {
        "name": "Feature Engine",
        "status": "OK",
        "issues": [],
        "metrics": {},
    }

    engine_path = REPO_DIR / "features" / "engine.py"
    hf_engine_path = REPO_DIR / "hf-space" / "features" / "engine.py"

    # Check engine.py exists
    if not engine_path.exists():
        result["status"] = "ERROR"
        result["issues"].append("features/engine.py not found")
        return result

    # Read engine stats from file size and grep for version markers
    engine_text = engine_path.read_text()
    engine_size = len(engine_text)
    result["metrics"]["engine_size_bytes"] = engine_size
    result["metrics"]["engine_size_kb"] = round(engine_size / 1024, 1)

    # Count category functions (def cat_XX or Cat XX patterns)
    cat_count = 0
    cat_names = []
    for line in engine_text.split("\n"):
        stripped = line.strip()
        # Look for category markers like "# Cat01", "# Cat 1", "# --- Cat01"
        if "# Cat" in stripped or "# --- Cat" in stripped:
            cat_count += 1
            cat_names.append(stripped[:80])
        # Also look for "def _cat" function definitions
        if stripped.startswith("def _cat") or stripped.startswith("def cat"):
            cat_count += 1

    # Deduplicate (some cats may appear in both comment and def)
    result["metrics"]["category_markers_found"] = cat_count
    result["metrics"]["engine_lines"] = engine_text.count("\n")

    # Look for ENGINE_VERSION or version string
    for line in engine_text.split("\n"):
        if "ENGINE_VERSION" in line or "engine_version" in line:
            result["metrics"]["version_line"] = line.strip()[:120]
            break

    # Feature count: look for known feature list patterns
    feature_keywords = [
        "features", "FEATURE", "feature_names", "all_features",
        "MAX_FEATURES", "selected_features",
    ]
    feature_refs = sum(
        1 for line in engine_text.split("\n")
        if any(kw in line for kw in feature_keywords)
    )
    result["metrics"]["feature_reference_lines"] = feature_refs

    # Parity check: compare root engine with hf-space engine
    if hf_engine_path.exists():
        hf_text = hf_engine_path.read_text()
        if engine_text == hf_text:
            result["metrics"]["parity_check"] = "MATCH"
        else:
            result["metrics"]["parity_check"] = "MISMATCH"
            root_lines = len(engine_text.split("\n"))
            hf_lines = len(hf_text.split("\n"))
            result["issues"].append(
                f"Engine parity MISMATCH: root={root_lines}L vs hf-space={hf_lines}L"
            )
            result["status"] = "WARNING"
    else:
        result["metrics"]["parity_check"] = "HF_ENGINE_MISSING"
        result["issues"].append("hf-space/features/engine.py not found")

    # Check expansion.py for extra features
    expansion_path = REPO_DIR / "features" / "expansion.py"
    if expansion_path.exists():
        expansion_text = expansion_path.read_text()
        result["metrics"]["expansion_size_kb"] = round(len(expansion_text) / 1024, 1)
        result["metrics"]["expansion_lines"] = expansion_text.count("\n")

    if not result["issues"]:
        result["status"] = "OK"

    return result


# ---------------------------------------------------------------------------
# Department D3: Model Evaluation
# ---------------------------------------------------------------------------

def run_d3_model_evaluation() -> Dict[str, Any]:
    """Track Brier scores across models and walk-forward performance."""
    result = {
        "name": "Model Evaluation",
        "status": "OK",
        "issues": [],
        "metrics": {},
    }

    # Read quant-summary.json (canonical model summary)
    summary_path = DATA_DIR / "quant-summary.json"
    summary = safe_read_json(summary_path)

    # Also check nba-agent subdir for the richer summary
    # (predict_today.py writes there)
    nba_summary_path = DATA_DIR / "nba-agent" / "predictions-today.json"
    nba_summary = safe_read_json(nba_summary_path)

    # Try to find evaluation results
    eval_dir = DATA_DIR / "eval"
    results_dir = DATA_DIR / "results"

    # Pull data from the latest predictions
    if nba_summary:
        result["metrics"]["model_version"] = nba_summary.get("model_version", "unknown")
        result["metrics"]["bankroll"] = nba_summary.get("bankroll", 0)
        result["metrics"]["games_today"] = nba_summary.get("games_count", 0)

    # Look for Brier / evaluation scores in results
    if results_dir.exists():
        result_files = sorted(results_dir.glob("*.json"))
        result["metrics"]["result_files_count"] = len(result_files)

        # Collect model performance from crew-evolution.json
        crew_evo = safe_read_json(results_dir / "crew-evolution.json")
        if crew_evo:
            result["metrics"]["crew_evolution"] = {
                k: v for k, v in crew_evo.items()
                if k in ["best_brier", "generation", "model_type", "timestamp"]
            }

        # Collect from crew-features.json
        crew_feat = safe_read_json(results_dir / "crew-features.json")
        if crew_feat:
            result["metrics"]["crew_features_snapshot"] = {
                k: v for k, v in crew_feat.items()
                if k in ["feature_count", "engine_version", "categories"]
            }

    # Read bankroll state if exists in the repo
    bankroll_path = DATA_DIR / "bankroll"
    if bankroll_path.exists():
        bankroll_files = sorted(bankroll_path.glob("*.json"))
        if bankroll_files:
            latest_br = safe_read_json(bankroll_files[-1])
            if latest_br:
                result["metrics"]["bankroll_state"] = {
                    "balance": latest_br.get("balance", latest_br.get("bankroll")),
                    "roi_pct": latest_br.get("roi_pct"),
                    "win_rate": latest_br.get("win_rate_pct"),
                }

    # Read performance dir
    perf_dir = DATA_DIR / "performance"
    if perf_dir.exists():
        perf_files = sorted(perf_dir.glob("*.json"))
        result["metrics"]["performance_files"] = len(perf_files)
        if perf_files:
            latest_perf = safe_read_json(perf_files[-1])
            if latest_perf:
                result["metrics"]["latest_performance"] = {
                    k: v for k, v in latest_perf.items()
                    if isinstance(v, (int, float, str))
                }

    # Summary scoring
    if summary:
        result["metrics"]["quant_summary"] = summary
    else:
        result["issues"].append("quant-summary.json not found")

    # Evaluate overall health
    if eval_dir.exists():
        eval_files = sorted(eval_dir.glob("*.json"))
        result["metrics"]["eval_files_count"] = len(eval_files)

    if not result["issues"]:
        result["status"] = "OK"

    return result


# ---------------------------------------------------------------------------
# Department D4: Data Quality
# ---------------------------------------------------------------------------

def run_d4_data_quality() -> Dict[str, Any]:
    """Check data freshness, missing games, odds quality."""
    result = {
        "name": "Data Quality",
        "status": "OK",
        "issues": [],
        "metrics": {},
    }

    # Check odds files
    odds_dir = DATA_DIR / "odds"
    if odds_dir.exists():
        odds_files = sorted(odds_dir.glob("*.json"))
        result["metrics"]["total_odds_files"] = len(odds_files)

        if odds_files:
            latest_odds_file = odds_files[-1]
            result["metrics"]["latest_odds_file"] = latest_odds_file.name

            # Check age of latest odds
            mtime = datetime.fromtimestamp(
                latest_odds_file.stat().st_mtime, tz=timezone.utc
            )
            age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
            result["metrics"]["latest_odds_age_hours"] = round(age_hours, 1)

            if age_hours > 6:
                result["issues"].append(
                    f"Latest odds file is {age_hours:.1f}h old (>6h stale)"
                )
                result["status"] = "WARNING"

            # Read latest odds to check structure
            latest_odds = safe_read_json(latest_odds_file)
            if latest_odds:
                if isinstance(latest_odds, list):
                    result["metrics"]["games_with_odds"] = len(latest_odds)
                elif isinstance(latest_odds, dict):
                    result["metrics"]["odds_keys"] = list(latest_odds.keys())[:10]
        else:
            result["issues"].append("No odds files found in data/odds/")
            result["status"] = "WARNING"
    else:
        # Check root-level odds files
        root_odds = sorted(DATA_DIR.glob("odds-*.json"))
        result["metrics"]["root_odds_files"] = len(root_odds)
        if root_odds:
            latest = root_odds[-1]
            result["metrics"]["latest_root_odds"] = latest.name
            mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
            result["metrics"]["latest_odds_age_hours"] = round(age_hours, 1)
        else:
            result["issues"].append("No odds directory or root odds files found")

    # Check prediction file coverage
    pred_dir = DATA_DIR / "predictions"
    if pred_dir.exists():
        pred_files = sorted(pred_dir.glob("predictions-*.json"))
        result["metrics"]["prediction_dates_covered"] = len(pred_files)

        if pred_files:
            # Parse date range
            dates = []
            for pf in pred_files:
                try:
                    date_str = pf.stem.replace("predictions-", "")
                    dates.append(date_str)
                except Exception:
                    pass
            if dates:
                result["metrics"]["first_prediction_date"] = dates[0]
                result["metrics"]["last_prediction_date"] = dates[-1]

    # Check historical-odds directory
    hist_odds = DATA_DIR / "historical-odds"
    if hist_odds.exists():
        hist_files = sorted(hist_odds.glob("*.json"))
        result["metrics"]["historical_odds_files"] = len(hist_files)

    # Check player props
    props_dir = DATA_DIR / "player-props"
    if props_dir.exists():
        props_files = sorted(props_dir.glob("*.json"))
        result["metrics"]["player_props_files"] = len(props_files)
        if props_files:
            latest_props = props_files[-1]
            mtime = datetime.fromtimestamp(
                latest_props.stat().st_mtime, tz=timezone.utc
            )
            age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
            result["metrics"]["latest_props_age_hours"] = round(age_hours, 1)

    # Check player-tracking data
    tracking_dir = DATA_DIR / "player-tracking"
    if tracking_dir.exists():
        tracking_files = sorted(tracking_dir.glob("*.json"))
        result["metrics"]["player_tracking_files"] = len(tracking_files)

    if not result["issues"]:
        result["status"] = "OK"

    return result


# ---------------------------------------------------------------------------
# Department D5: Evolution Sync
# ---------------------------------------------------------------------------

def poll_island_status(island_id: str, info: Dict) -> Dict[str, Any]:
    """Poll a single HF island for its status via /api/status."""
    status = {
        "id": island_id,
        "role": info["role"],
        "url": info["url"],
        "status": "UNKNOWN",
        "brier": None,
        "generation": None,
        "model": None,
        "stagnation": None,
    }
    try:
        resp = requests.get(
            f"{info['url']}/api/status",
            timeout=15,
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            data = resp.json()
            status["status"] = "UP"
            status["brier"] = data.get("best_brier")
            status["generation"] = data.get("generation")
            status["model"] = data.get("best_model") or data.get("model_type")
            status["stagnation"] = data.get("stagnation_cycles", 0)
            status["pop_size"] = data.get("pop_size")
            status["features"] = data.get("n_features") or data.get("features")
        else:
            status["status"] = f"HTTP_{resp.status_code}"
    except requests.exceptions.Timeout:
        status["status"] = "TIMEOUT"
    except requests.exceptions.ConnectionError:
        status["status"] = "DOWN"
    except Exception as e:
        status["status"] = f"ERROR: {str(e)[:60]}"

    return status


def run_d5_evolution_sync() -> Dict[str, Any]:
    """Poll all 6 HF islands and track evolution progress."""
    result = {
        "name": "Evolution Sync",
        "status": "OK",
        "issues": [],
        "metrics": {},
    }

    island_statuses = {}
    best_brier = 1.0
    best_island = None
    islands_up = 0
    islands_down = 0
    total_generations = 0

    for island_id, info in HF_ISLANDS.items():
        s = poll_island_status(island_id, info)
        island_statuses[island_id] = s

        if s["status"] == "UP":
            islands_up += 1
            if s["brier"] is not None:
                brier_val = float(s["brier"])
                if brier_val < best_brier:
                    best_brier = brier_val
                    best_island = island_id
            if s["generation"] is not None:
                total_generations += int(s["generation"])
        else:
            islands_down += 1

    result["metrics"]["islands"] = island_statuses
    result["metrics"]["islands_up"] = islands_up
    result["metrics"]["islands_down"] = islands_down
    result["metrics"]["total_generations"] = total_generations

    if best_island:
        result["metrics"]["best_island"] = best_island
        result["metrics"]["best_brier"] = best_brier

    if islands_down > 0:
        down_list = [
            sid for sid, s in island_statuses.items() if s["status"] != "UP"
        ]
        result["issues"].append(f"Islands DOWN: {', '.join(down_list)}")
        if islands_down >= 3:
            result["status"] = "ERROR"
        else:
            result["status"] = "WARNING"

    # Check for stagnation (>50 cycles without improvement)
    for sid, s in island_statuses.items():
        stag = s.get("stagnation")
        if stag is not None and int(stag) > 50:
            result["issues"].append(f"{sid} stagnant ({stag} cycles)")
            if result["status"] == "OK":
                result["status"] = "WARNING"

    # Check evolution-state directory for local sync data
    evo_state_dir = DATA_DIR / "evolution-state"
    if evo_state_dir.exists():
        evo_files = sorted(evo_state_dir.glob("*.json"))
        result["metrics"]["local_evolution_states"] = len(evo_files)

    if not result["issues"]:
        result["status"] = "OK"

    return result


# ---------------------------------------------------------------------------
# Full cycle runner
# ---------------------------------------------------------------------------

def run_forge_cycle() -> Dict[str, Any]:
    """Run all 5 department loops once."""
    cycle_start = time.time()
    cycle_num = forge_state["cycle"] + 1
    ts = datetime.now(timezone.utc).isoformat()
    print(f"\n{'='*60}")
    print(f"[FORGE] Cycle {cycle_num} starting at {ts}")
    print(f"{'='*60}")

    # Step 1: Git sync
    clone_or_pull_repo()

    # Step 2: Run departments
    departments = {}

    dept_runners = [
        ("D1", run_d1_prediction_pipeline),
        ("D2", run_d2_feature_engine),
        ("D3", run_d3_model_evaluation),
        ("D4", run_d4_data_quality),
        ("D5", run_d5_evolution_sync),
    ]

    for dept_id, runner in dept_runners:
        try:
            print(f"  [{dept_id}] Running {runner.__name__}...")
            dept_result = runner()
            departments[dept_id] = dept_result
            status_icon = (
                "OK" if dept_result["status"] == "OK"
                else "WARN" if dept_result["status"] == "WARNING"
                else "ERR"
            )
            print(f"  [{dept_id}] -> {status_icon} "
                  f"({len(dept_result.get('issues', []))} issues)")
        except Exception as e:
            print(f"  [{dept_id}] EXCEPTION: {e}")
            traceback.print_exc()
            departments[dept_id] = {
                "name": runner.__name__,
                "status": "ERROR",
                "issues": [f"Exception: {str(e)[:200]}"],
                "metrics": {},
            }

    # Step 3: Update global state
    duration = time.time() - cycle_start
    forge_state["cycle"] = cycle_num
    forge_state["last_cycle_ts"] = ts
    forge_state["last_cycle_duration_sec"] = round(duration, 1)
    forge_state["status"] = "RUNNING"
    forge_state["departments"] = departments

    # Aggregate island data
    d5 = departments.get("D5", {})
    d5_metrics = d5.get("metrics", {})
    forge_state["islands"] = d5_metrics.get("islands", {})

    # Trim error log
    forge_state["errors"] = forge_state["errors"][-50:]

    # Count issues
    total_issues = sum(
        len(d.get("issues", [])) for d in departments.values()
    )
    statuses = [d.get("status", "UNKNOWN") for d in departments.values()]
    if "ERROR" in statuses:
        forge_state["status"] = "DEGRADED"
    elif "WARNING" in statuses:
        forge_state["status"] = "WARNING"
    else:
        forge_state["status"] = "HEALTHY"

    print(f"[FORGE] Cycle {cycle_num} complete in {duration:.1f}s "
          f"-- {forge_state['status']} ({total_issues} issues)")

    return forge_state


# ---------------------------------------------------------------------------
# Background daemon
# ---------------------------------------------------------------------------

def daemon_loop():
    """Background thread running the forge cycle every CYCLE_INTERVAL_SEC."""
    # Initial delay to let Gradio start
    time.sleep(5)
    while True:
        try:
            run_forge_cycle()
        except Exception as e:
            print(f"[DAEMON] Cycle error: {e}")
            traceback.print_exc()
            forge_state["errors"].append(f"cycle: {str(e)[:200]}")
        time.sleep(CYCLE_INTERVAL_SEC)


# ---------------------------------------------------------------------------
# Gradio UI helpers
# ---------------------------------------------------------------------------

def format_status_badge(status: str) -> str:
    """Return a colored status string."""
    if status in ("OK", "HEALTHY", "UP", "RUNNING"):
        return f"[OK] {status}"
    elif status in ("WARNING", "WARN", "DEGRADED"):
        return f"[!!] {status}"
    else:
        return f"[XX] {status}"


def build_overview_text() -> str:
    """Build the Overview tab content."""
    lines = []
    lines.append("# Nomos42 NBA Forge")
    lines.append("")

    status = forge_state.get("status", "INITIALIZING")
    cycle = forge_state.get("cycle", 0)
    last_ts = forge_state.get("last_cycle_ts", "never")
    duration = forge_state.get("last_cycle_duration_sec", 0)

    lines.append(f"**Status:** {format_status_badge(status)}")
    lines.append(f"**Cycle:** {cycle} | **Last run:** {last_ts}")
    lines.append(f"**Duration:** {duration}s | **Interval:** {CYCLE_INTERVAL_SEC}s")
    lines.append(f"**Version:** {VERSION}")
    lines.append("")

    # Department summary table
    lines.append("## Department Status")
    lines.append("")
    lines.append("| Dept | Name | Status | Issues |")
    lines.append("|------|------|--------|--------|")

    depts = forge_state.get("departments", {})
    for dept_id in ["D1", "D2", "D3", "D4", "D5"]:
        d = depts.get(dept_id, {})
        name = d.get("name", dept_id)
        st = d.get("status", "PENDING")
        issues = d.get("issues", [])
        issue_str = f"{len(issues)} issue(s)" if issues else "None"
        lines.append(f"| {dept_id} | {name} | {format_status_badge(st)} | {issue_str} |")

    lines.append("")

    # Island summary
    islands = forge_state.get("islands", {})
    if islands:
        lines.append("## Evolution Islands")
        lines.append("")
        lines.append("| Island | Role | Status | Brier | Gen | Model |")
        lines.append("|--------|------|--------|-------|-----|-------|")
        for sid in ["S10", "S11", "S12", "S13", "S14", "S15"]:
            s = islands.get(sid, {})
            role = s.get("role", "?")
            st = s.get("status", "?")
            brier = s.get("brier", "?")
            if brier and brier != "?":
                brier = f"{float(brier):.5f}"
            gen = s.get("generation", "?")
            model = s.get("model", "?")
            lines.append(
                f"| {sid} | {role} | {format_status_badge(st)} | {brier} | {gen} | {model} |"
            )

    # Errors
    errors = forge_state.get("errors", [])
    if errors:
        lines.append("")
        lines.append("## Recent Errors")
        lines.append("")
        for err in errors[-5:]:
            lines.append(f"- {err}")

    return "\n".join(lines)


def build_predictions_text() -> str:
    """Build the Predictions tab content."""
    lines = []
    lines.append("# D1: Prediction Pipeline")
    lines.append("")

    d1 = forge_state.get("departments", {}).get("D1", {})
    if not d1:
        lines.append("*Waiting for first cycle...*")
        return "\n".join(lines)

    st = d1.get("status", "PENDING")
    lines.append(f"**Status:** {format_status_badge(st)}")
    lines.append("")

    metrics = d1.get("metrics", {})
    if metrics:
        lines.append("## Metrics")
        lines.append("")
        lines.append(f"- **Prediction Date:** {metrics.get('prediction_date', '?')}")
        lines.append(f"- **Generated At:** {metrics.get('generated_at', '?')}")
        lines.append(f"- **Age:** {metrics.get('age_hours', '?')}h")
        lines.append(f"- **Games Count:** {metrics.get('games_count', '?')}")
        lines.append(f"- **Valid Games:** {metrics.get('valid_games', '?')}")
        lines.append(f"- **Model Version:** {metrics.get('model_version', '?')}")
        lines.append(f"- **Bankroll:** ${metrics.get('bankroll', '?')}")
        lines.append(f"- **Value Bets:** {metrics.get('value_bets_count', '?')}")
        lines.append(f"- **Kelly Exposure:** ${metrics.get('total_kelly_exposure', '?')}")
        lines.append(f"- **Historical Files:** {metrics.get('historical_prediction_files', '?')}")
        latest_file = metrics.get("latest_prediction_file", "?")
        lines.append(f"- **Latest File:** {latest_file}")

    issues = d1.get("issues", [])
    if issues:
        lines.append("")
        lines.append("## Issues")
        lines.append("")
        for issue in issues:
            lines.append(f"- {issue}")

    return "\n".join(lines)


def build_features_text() -> str:
    """Build the Features tab content."""
    lines = []
    lines.append("# D2: Feature Engine")
    lines.append("")

    d2 = forge_state.get("departments", {}).get("D2", {})
    if not d2:
        lines.append("*Waiting for first cycle...*")
        return "\n".join(lines)

    st = d2.get("status", "PENDING")
    lines.append(f"**Status:** {format_status_badge(st)}")
    lines.append("")

    metrics = d2.get("metrics", {})
    if metrics:
        lines.append("## Engine Stats")
        lines.append("")
        lines.append(f"- **Size:** {metrics.get('engine_size_kb', '?')} KB")
        lines.append(f"- **Lines:** {metrics.get('engine_lines', '?')}")
        lines.append(f"- **Category Markers:** {metrics.get('category_markers_found', '?')}")
        lines.append(f"- **Feature Reference Lines:** {metrics.get('feature_reference_lines', '?')}")
        vl = metrics.get("version_line", "not found")
        lines.append(f"- **Version Line:** `{vl}`")
        lines.append("")

        lines.append("## Parity Check")
        lines.append("")
        parity = metrics.get("parity_check", "NOT_CHECKED")
        lines.append(f"- **root engine vs hf-space engine:** {parity}")
        lines.append("")

        if metrics.get("expansion_lines"):
            lines.append("## Expansion Module")
            lines.append("")
            lines.append(f"- **expansion.py size:** {metrics.get('expansion_size_kb', '?')} KB")
            lines.append(f"- **expansion.py lines:** {metrics.get('expansion_lines', '?')}")

    issues = d2.get("issues", [])
    if issues:
        lines.append("")
        lines.append("## Issues")
        lines.append("")
        for issue in issues:
            lines.append(f"- {issue}")

    return "\n".join(lines)


def build_models_text() -> str:
    """Build the Models tab content."""
    lines = []
    lines.append("# D3: Model Evaluation")
    lines.append("")

    d3 = forge_state.get("departments", {}).get("D3", {})
    if not d3:
        lines.append("*Waiting for first cycle...*")
        return "\n".join(lines)

    st = d3.get("status", "PENDING")
    lines.append(f"**Status:** {format_status_badge(st)}")
    lines.append("")

    metrics = d3.get("metrics", {})

    # Quant summary
    qs = metrics.get("quant_summary")
    if qs:
        lines.append("## Quant Summary")
        lines.append("")
        lines.append(f"```json\n{json.dumps(qs, indent=2)[:2000]}\n```")
        lines.append("")

    # Model version and bankroll
    if metrics.get("model_version"):
        lines.append(f"- **Model Version:** {metrics.get('model_version')}")
    if metrics.get("bankroll"):
        lines.append(f"- **Bankroll:** ${metrics.get('bankroll')}")
    if metrics.get("games_today"):
        lines.append(f"- **Games Today:** {metrics.get('games_today')}")

    # Result files
    if metrics.get("result_files_count"):
        lines.append(f"- **Result Files:** {metrics.get('result_files_count')}")
    if metrics.get("eval_files_count"):
        lines.append(f"- **Eval Files:** {metrics.get('eval_files_count')}")
    if metrics.get("performance_files"):
        lines.append(f"- **Performance Files:** {metrics.get('performance_files')}")

    # Crew evolution snapshot
    crew_evo = metrics.get("crew_evolution")
    if crew_evo:
        lines.append("")
        lines.append("## Crew Evolution Snapshot")
        lines.append("")
        for k, v in crew_evo.items():
            lines.append(f"- **{k}:** {v}")

    # Bankroll state
    br = metrics.get("bankroll_state")
    if br:
        lines.append("")
        lines.append("## Bankroll State")
        lines.append("")
        for k, v in br.items():
            lines.append(f"- **{k}:** {v}")

    # Latest performance
    lp = metrics.get("latest_performance")
    if lp:
        lines.append("")
        lines.append("## Latest Performance")
        lines.append("")
        for k, v in list(lp.items())[:15]:
            lines.append(f"- **{k}:** {v}")

    issues = d3.get("issues", [])
    if issues:
        lines.append("")
        lines.append("## Issues")
        lines.append("")
        for issue in issues:
            lines.append(f"- {issue}")

    return "\n".join(lines)


def build_data_quality_text() -> str:
    """Build the Data Quality tab content."""
    lines = []
    lines.append("# D4: Data Quality")
    lines.append("")

    d4 = forge_state.get("departments", {}).get("D4", {})
    if not d4:
        lines.append("*Waiting for first cycle...*")
        return "\n".join(lines)

    st = d4.get("status", "PENDING")
    lines.append(f"**Status:** {format_status_badge(st)}")
    lines.append("")

    metrics = d4.get("metrics", {})
    if metrics:
        lines.append("## Odds Data")
        lines.append("")
        lines.append(f"- **Total Odds Files:** {metrics.get('total_odds_files', metrics.get('root_odds_files', '?'))}")
        lines.append(f"- **Latest Odds File:** {metrics.get('latest_odds_file', metrics.get('latest_root_odds', '?'))}")
        lines.append(f"- **Latest Odds Age:** {metrics.get('latest_odds_age_hours', '?')}h")
        games_with_odds = metrics.get("games_with_odds")
        if games_with_odds is not None:
            lines.append(f"- **Games With Odds:** {games_with_odds}")
        lines.append("")

        lines.append("## Predictions Coverage")
        lines.append("")
        lines.append(f"- **Prediction Dates:** {metrics.get('prediction_dates_covered', '?')}")
        lines.append(f"- **First Date:** {metrics.get('first_prediction_date', '?')}")
        lines.append(f"- **Last Date:** {metrics.get('last_prediction_date', '?')}")
        lines.append("")

        lines.append("## Supplementary Data")
        lines.append("")
        hist = metrics.get("historical_odds_files")
        if hist is not None:
            lines.append(f"- **Historical Odds Files:** {hist}")
        pp = metrics.get("player_props_files")
        if pp is not None:
            lines.append(f"- **Player Props Files:** {pp}")
            lines.append(f"- **Latest Props Age:** {metrics.get('latest_props_age_hours', '?')}h")
        pt = metrics.get("player_tracking_files")
        if pt is not None:
            lines.append(f"- **Player Tracking Files:** {pt}")

    issues = d4.get("issues", [])
    if issues:
        lines.append("")
        lines.append("## Issues")
        lines.append("")
        for issue in issues:
            lines.append(f"- {issue}")

    return "\n".join(lines)


def build_evolution_text() -> str:
    """Build the Evolution Sync tab content (island details)."""
    lines = []
    lines.append("# D5: Evolution Sync")
    lines.append("")

    d5 = forge_state.get("departments", {}).get("D5", {})
    if not d5:
        lines.append("*Waiting for first cycle...*")
        return "\n".join(lines)

    st = d5.get("status", "PENDING")
    lines.append(f"**Status:** {format_status_badge(st)}")
    lines.append("")

    metrics = d5.get("metrics", {})
    lines.append(f"- **Islands UP:** {metrics.get('islands_up', '?')}")
    lines.append(f"- **Islands DOWN:** {metrics.get('islands_down', '?')}")
    lines.append(f"- **Total Generations:** {metrics.get('total_generations', '?')}")
    best_island = metrics.get("best_island")
    best_brier = metrics.get("best_brier")
    if best_island:
        lines.append(f"- **Best Island:** {best_island} (Brier {best_brier:.5f})")
    lines.append(f"- **Local Evolution States:** {metrics.get('local_evolution_states', '?')}")
    lines.append("")

    # Detailed island table
    islands = metrics.get("islands", {})
    if islands:
        lines.append("## Island Details")
        lines.append("")
        lines.append("| Island | Role | Status | Brier | Gen | Model | Features | Pop | Stagnation |")
        lines.append("|--------|------|--------|-------|-----|-------|----------|-----|------------|")
        for sid in ["S10", "S11", "S12", "S13", "S14", "S15"]:
            s = islands.get(sid, {})
            role = s.get("role", "?")
            st_i = s.get("status", "?")
            brier = s.get("brier", "?")
            if brier and brier != "?":
                try:
                    brier = f"{float(brier):.5f}"
                except (ValueError, TypeError):
                    pass
            gen = s.get("generation", "?")
            model = s.get("model", "?")
            features = s.get("features", "?")
            pop = s.get("pop_size", "?")
            stag = s.get("stagnation", "?")
            lines.append(
                f"| {sid} | {role} | {st_i} | {brier} | {gen} | {model} | {features} | {pop} | {stag} |"
            )

    issues = d5.get("issues", [])
    if issues:
        lines.append("")
        lines.append("## Issues")
        lines.append("")
        for issue in issues:
            lines.append(f"- {issue}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gradio refresh callbacks
# ---------------------------------------------------------------------------

def refresh_overview():
    return build_overview_text()

def refresh_predictions():
    return build_predictions_text()

def refresh_features():
    return build_features_text()

def refresh_models():
    return build_models_text()

def refresh_data_quality():
    return build_data_quality_text()

def refresh_evolution():
    return build_evolution_text()

def force_cycle():
    """Manual trigger for a forge cycle."""
    run_forge_cycle()
    return build_overview_text()

def get_raw_state():
    """Return raw JSON state for debugging."""
    return json.dumps(forge_state, indent=2, default=str)


# ---------------------------------------------------------------------------
# Build Gradio app
# ---------------------------------------------------------------------------

def create_app() -> gr.Blocks:
    with gr.Blocks(
        title="Nomos42 NBA Forge",
        theme=gr.themes.Base(),
    ) as app:
        gr.Markdown("# Nomos42 NBA Forge -- Department Karpathy Loops")
        gr.Markdown(
            "Autonomous monitoring of the NBA Quant AI prediction system. "
            "5 departments run every 10 minutes."
        )

        with gr.Tabs():
            # -- Tab 1: Overview --
            with gr.Tab("Overview"):
                overview_md = gr.Markdown(
                    value="*Starting up... first cycle will run in ~5 seconds.*"
                )
                with gr.Row():
                    refresh_btn = gr.Button("Refresh", variant="secondary")
                    force_btn = gr.Button("Force Cycle Now", variant="primary")
                refresh_btn.click(fn=refresh_overview, outputs=overview_md)
                force_btn.click(fn=force_cycle, outputs=overview_md)

            # -- Tab 2: Predictions --
            with gr.Tab("Predictions"):
                pred_md = gr.Markdown(
                    value="*Waiting for first cycle...*"
                )
                pred_refresh = gr.Button("Refresh", variant="secondary")
                pred_refresh.click(fn=refresh_predictions, outputs=pred_md)

            # -- Tab 3: Features --
            with gr.Tab("Features"):
                feat_md = gr.Markdown(
                    value="*Waiting for first cycle...*"
                )
                feat_refresh = gr.Button("Refresh", variant="secondary")
                feat_refresh.click(fn=refresh_features, outputs=feat_md)

            # -- Tab 4: Models --
            with gr.Tab("Models"):
                models_md = gr.Markdown(
                    value="*Waiting for first cycle...*"
                )
                models_refresh = gr.Button("Refresh", variant="secondary")
                models_refresh.click(fn=refresh_models, outputs=models_md)

            # -- Tab 5: Data Quality --
            with gr.Tab("Data Quality"):
                dq_md = gr.Markdown(
                    value="*Waiting for first cycle...*"
                )
                dq_refresh = gr.Button("Refresh", variant="secondary")
                dq_refresh.click(fn=refresh_data_quality, outputs=dq_md)

            # -- Tab 6: Evolution Sync --
            with gr.Tab("Evolution"):
                evo_md = gr.Markdown(
                    value="*Waiting for first cycle...*"
                )
                evo_refresh = gr.Button("Refresh", variant="secondary")
                evo_refresh.click(fn=refresh_evolution, outputs=evo_md)

            # -- Tab 7: Raw State (debug) --
            with gr.Tab("Raw JSON"):
                raw_tb = gr.Textbox(
                    value="{}",
                    label="Forge State (JSON)",
                    lines=30,
                    max_lines=60,
                    interactive=False,
                )
                raw_refresh = gr.Button("Refresh", variant="secondary")
                raw_refresh.click(fn=get_raw_state, outputs=raw_tb)

    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Start background daemon
    daemon_thread = threading.Thread(target=daemon_loop, daemon=True)
    daemon_thread.start()
    print(f"[FORGE] Daemon started (interval={CYCLE_INTERVAL_SEC}s)")

    # Launch Gradio
    app = create_app()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
else:
    # When imported by Gradio SDK (HF Spaces auto-detect)
    daemon_thread = threading.Thread(target=daemon_loop, daemon=True)
    daemon_thread.start()
    print(f"[FORGE] Daemon started (interval={CYCLE_INTERVAL_SEC}s)")

    app = create_app()
    demo = app  # HF Spaces looks for `demo` or `app`
