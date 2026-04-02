#!/usr/bin/env python3
"""
Forge Orchestrator — HuggingFace Space Edition
===============================================
Runs ALL 11 department Karpathy loops + Guardian cross-pollination on HF Spaces.

Architecture:
  1. On startup: clones mon-ipad repo (needs GH_TOKEN secret)
  2. Every 15 minutes: runs all 11 department loops in sequence
  3. Guardian cross-pollination after each cycle
  4. Gradio dashboard with tabs: Overview, Detail, Guardian, Wins, Logs
  5. Git sync after each cycle

Departments (11):
  D1  RESEARCH       — arxiv scan, technique extraction
  D2  ENGINEERING     — code quality, test pass rate, Brier delta
  D3  EVOLUTION       — 6 HF island health, generation count, cross-pollination
  D4  BETTING         — strategy performance, Kelly sizing, ROI
  D5  EVALUATION      — prediction accuracy, calibration, false positives
  D6  INFRA           — space uptime, restart count, service health
  D7  POLITICAL       — political signal freshness, ETF performance
  D8  CREATIVE (RGWA) — art generation pipeline status
  D9  COMMUNICATION   — content pipeline, channel readiness
  D10 BUSINESS        — users, pricing, MRR tracking
  D11 FINANCE         — costs, revenue, P&L generation

Each department measures ONE primary metric (Karpathy style), proposes improvements,
and the Guardian decides what to cross-pollinate.
"""

import json
import os
import sys
import time
import threading
import subprocess
import traceback
import requests
import gradio as gr
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

# ============================================================================
# CONFIGURATION
# ============================================================================

GH_TOKEN = os.environ.get("GH_TOKEN", "")
REPO_URL = (
    f"https://{GH_TOKEN}@github.com/LBJLincoln/mon-ipad.git"
    if GH_TOKEN
    else "https://github.com/LBJLincoln/mon-ipad.git"
)

WORKSPACE = Path("/tmp/forge-workspace")
ROOT = WORKSPACE / "mon-ipad"
DATA_DIR = ROOT / "data" / "departments"
GUARDIAN_REPORT = DATA_DIR / "guardian-report.json"
WINS_FILE = DATA_DIR / "wins-latest.json"

LOOP_DELAY_SECONDS = 900  # 15 minutes
MAX_ITERATIONS = 100000

# HF Space island URLs
ISLANDS = {
    "S10": {
        "url": "nomos42-nba-quant",
        "role": "exploitation",
        "specialist_model": None,
        "mut": 0.09,
        "feat": 63,
    },
    "S11": {
        "url": "nomos42-nba-quant-2",
        "role": "exploration",
        "specialist_model": None,
        "mut": 0.15,
        "feat": 80,
    },
    "S12": {
        "url": "nomos42-nba-evo-3",
        "role": "extra_trees_specialist",
        "specialist_model": "extra_trees",
        "mut": 0.08,
        "feat": 60,
    },
    "S13": {
        "url": "nomos42-nba-evo-4",
        "role": "catboost_specialist",
        "specialist_model": "catboost",
        "mut": 0.10,
        "feat": 66,
    },
    "S14": {
        "url": "nomos42-nba-evo-5",
        "role": "lightgbm_specialist",
        "specialist_model": "lightgbm",
        "mut": 0.08,
        "feat": 55,
    },
    "S15": {
        "url": "nomos42-nba-evo-6",
        "role": "wide_search",
        "specialist_model": None,
        "mut": 0.18,
        "feat": 80,
    },
}

# Known service endpoints to check
SERVICES = {
    "dashboard": "https://nomosdashboard.vercel.app",
    "data_server": "https://nomos42-nba-quant.hf.space",
}

# Department definitions
DEPARTMENTS = {
    "D1": {"name": "RESEARCH", "key": "research", "metric": "techniques_extracted", "target": 30, "direction": "higher"},
    "D2": {"name": "ENGINEERING", "key": "engineering", "metric": "brier_delta", "target": -0.01, "direction": "lower"},
    "D3": {"name": "EVOLUTION", "key": "evolution", "metric": "best_brier", "target": 0.21000, "direction": "lower"},
    "D4": {"name": "BETTING", "key": "betting", "metric": "roi_pct", "target": 5.0, "direction": "higher"},
    "D5": {"name": "EVALUATION", "key": "evaluation", "metric": "ece", "target": 0.05, "direction": "lower"},
    "D6": {"name": "INFRA", "key": "infra", "metric": "uptime_pct", "target": 99.9, "direction": "higher"},
    "D7": {"name": "POLITICAL", "key": "political", "metric": "political_brier", "target": 0.25, "direction": "lower"},
    "D8": {"name": "CREATIVE", "key": "creative", "metric": "quality_score", "target": 8.0, "direction": "higher"},
    "D9": {"name": "COMMUNICATION", "key": "communication", "metric": "posts_prepared", "target": 14, "direction": "higher"},
    "D10": {"name": "BUSINESS", "key": "business", "metric": "mrr", "target": 5000, "direction": "higher"},
    "D11": {"name": "FINANCE", "key": "finance", "metric": "financial_accuracy", "target": 100, "direction": "higher"},
}


# ============================================================================
# GLOBAL STATE (thread-safe)
# ============================================================================

_state_lock = threading.Lock()
_state = {
    "status": "initializing",
    "iteration": 0,
    "health_score": 0,
    "total_completed": 0,
    "total_failures": 0,
    "last_run_time": "never",
    "last_duration_s": 0,
    "department_results": {},
    "guardian_report": {},
    "wins": [],
    "log_lines": [],
    "loop_running": False,
    "dept_history": {},  # {dept_key: [{iteration, metric_value, ts}, ...]}
}


def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _state_lock:
        _state["log_lines"].append(line)
        if len(_state["log_lines"]) > 500:
            _state["log_lines"] = _state["log_lines"][-500:]
    print(line, flush=True)


def _update_state(**kwargs):
    with _state_lock:
        _state.update(kwargs)


def _get_state() -> dict:
    with _state_lock:
        return dict(_state)


# ============================================================================
# GIT OPERATIONS
# ============================================================================

def clone_repo():
    """Clone or pull mon-ipad repo."""
    _log("Cloning/updating mon-ipad...")
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    if ROOT.exists():
        _log("  Pulling latest...")
        try:
            subprocess.run(
                ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                cwd=str(ROOT), capture_output=True, timeout=60,
            )
            _log("  Pulled successfully")
        except Exception as e:
            _log(f"  Pull failed ({e}), re-cloning...")
            subprocess.run(["rm", "-rf", str(ROOT)], capture_output=True)
            subprocess.run(
                ["git", "clone", "--depth", "1", REPO_URL, str(ROOT)],
                capture_output=True, timeout=120,
            )
            _log("  Re-cloned")
    else:
        _log("  Cloning fresh...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(ROOT)],
            capture_output=True, timeout=120, text=True,
        )
        if result.returncode != 0:
            _log(f"  Clone FAILED: {result.stderr[:200]}")
            raise RuntimeError("Failed to clone mon-ipad")
        _log("  Cloned successfully")

    # Configure git identity
    for cmd in [
        ["git", "config", "user.email", "forge-bot@nomos42.ai"],
        ["git", "config", "user.name", "Forge Orchestrator"],
    ]:
        subprocess.run(cmd, cwd=str(ROOT), capture_output=True)


def git_sync(iteration: int):
    """Commit and push guardian report + department outputs after each cycle."""
    if not GH_TOKEN:
        _log("[git] No GH_TOKEN, skipping sync")
        return

    try:
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"],
                        cwd=str(ROOT), capture_output=True, timeout=60)

        # Stage department data files
        files_to_add = [
            "data/departments/guardian-report.json",
            "data/departments/wins-latest.json",
        ]
        for dept_info in DEPARTMENTS.values():
            key = dept_info["key"]
            kpath = f"data/departments/{key}/karpathy-output.json"
            if (ROOT / kpath).exists():
                files_to_add.append(kpath)

        for f in files_to_add:
            if (ROOT / f).exists():
                subprocess.run(["git", "add", f], cwd=str(ROOT), capture_output=True)

        # Check if there are changes to commit
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(ROOT), capture_output=True,
        )
        if status.returncode == 0:
            _log("[git] No changes to commit")
            return

        msg = f"forge: cycle {iteration} — 11 dept Karpathy + guardian"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(ROOT), capture_output=True, timeout=30,
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(ROOT), capture_output=True, timeout=60, text=True,
        )
        if result.returncode == 0:
            _log(f"[git] Pushed cycle {iteration}")
        else:
            _log(f"[git] Push failed: {result.stderr[:150]}")
    except Exception as e:
        _log(f"[git] Sync error: {e}")


# ============================================================================
# HTTP HELPERS
# ============================================================================

def safe_get(url: str, timeout: int = 15) -> Tuple[bool, dict]:
    """GET request returning (success, data_or_error)."""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Nomos42Forge/1.0"})
        if resp.status_code == 200:
            try:
                return True, resp.json()
            except Exception:
                return True, {"status": "ok", "text": resp.text[:200]}
        return False, {"status_code": resp.status_code, "text": resp.text[:200]}
    except Exception as e:
        return False, {"error": str(e)[:200]}


def safe_post(url: str, payload: dict, timeout: int = 15) -> Tuple[bool, dict]:
    """POST JSON returning (success, data_or_error)."""
    try:
        resp = requests.post(
            url, json=payload, timeout=timeout,
            headers={"User-Agent": "Nomos42Forge/1.0", "Content-Type": "application/json"},
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, {"status_code": resp.status_code}
    except Exception as e:
        return False, {"error": str(e)[:200]}


def ping_url(url: str, timeout: int = 10) -> Tuple[bool, float]:
    """Ping a URL, return (is_up, response_time_ms)."""
    try:
        start = time.time()
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Nomos42Forge/1.0"})
        elapsed = (time.time() - start) * 1000
        return resp.status_code == 200, round(elapsed, 1)
    except Exception:
        return False, -1


# ============================================================================
# DEPARTMENT LOOPS (Karpathy style: measure -> propose -> record)
# ============================================================================

def run_d1_research() -> dict:
    """D1 RESEARCH: Scan arxiv for NBA prediction papers, count techniques."""
    _log("[D1] RESEARCH: Scanning arxiv...")
    result = {
        "department": "research",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    papers_found = 0
    techniques = 0

    # Scan arxiv API for recent sports prediction / NBA papers
    queries = [
        "NBA+prediction+machine+learning",
        "sports+betting+neural+network",
        "basketball+probability+calibration",
    ]

    for query in queries:
        try:
            url = f"http://export.arxiv.org/api/query?search_query=all:{query}&max_results=10&sortBy=submittedDate"
            ok, data = safe_get(url, timeout=20)
            if ok:
                text = data.get("text", "") if isinstance(data, dict) else str(data)
                # Count <entry> tags as papers
                count = text.count("<entry>") if isinstance(text, str) else 0
                papers_found += count
                # Rough technique extraction: count method-related keywords
                for kw in ["gradient boosting", "random forest", "neural", "ensemble",
                           "calibration", "feature selection", "cross-validation",
                           "Brier", "logistic", "XGBoost", "LightGBM", "CatBoost"]:
                    if kw.lower() in text.lower():
                        techniques += 1
        except Exception as e:
            _log(f"[D1]   Query '{query}' failed: {e}")

    # Also check existing research data
    research_output = DATA_DIR / "research" / "karpathy-output.json"
    existing_papers = 0
    existing_techniques = 0
    if research_output.exists():
        try:
            existing = json.loads(research_output.read_text())
            existing_papers = existing.get("papers_scanned", 0)
            existing_techniques = existing.get("techniques_extracted", 0)
        except Exception:
            pass

    papers_found = max(papers_found, existing_papers)
    techniques = max(techniques, existing_techniques)

    result["metrics"] = {
        "papers_scanned": papers_found,
        "techniques_extracted": techniques,
        "proposals_generated": 0,
        "sota_reference": "Montrucchio 2026 (MDPI Information 17/1/56): 0.199",
        "gap_to_close": round(0.21570 - 0.199, 5),
        "improved": papers_found > existing_papers,
    }

    _save_dept_output("research", result["metrics"])
    _log(f"[D1]   Papers={papers_found}, Techniques={techniques}")
    return result


def run_d2_engineering() -> dict:
    """D2 ENGINEERING: Check code quality, feature engine version, test readiness."""
    _log("[D2] ENGINEERING: Checking code quality...")
    result = {
        "department": "engineering",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics = {
        "brier_delta": 0,
        "features_added": 0,
        "test_pass_rate": None,
        "feature_engine_version": "v3.1-46cat",
        "features_raw_count": 6253,
        "parity_check": "unknown",
    }

    # Check feature engine parity
    fe_canonical = ROOT / "features" / "engine.py"
    fe_deployed = ROOT / "hf-space" / "features" / "engine.py"
    if fe_canonical.exists() and fe_deployed.exists():
        try:
            canonical_hash = _file_hash(fe_canonical)
            deployed_hash = _file_hash(fe_deployed)
            metrics["parity_check"] = "MATCH" if canonical_hash == deployed_hash else "DRIFT"
            if metrics["parity_check"] == "DRIFT":
                _log("[D2]   WARNING: Feature engine parity DRIFT detected!")
        except Exception:
            metrics["parity_check"] = "error"

    # Check if tests exist and count them
    test_dir = ROOT / "tests"
    if test_dir.exists():
        test_files = list(test_dir.glob("test_*.py"))
        metrics["test_count"] = len(test_files)

    # Read latest eval for Brier
    eval_file = ROOT / "data" / "nba-agent" / "latest-eval.json"
    if eval_file.exists():
        try:
            eval_data = json.loads(eval_file.read_text())
            metrics["latest_brier"] = eval_data.get("brier_score", eval_data.get("brier"))
        except Exception:
            pass

    result["metrics"] = metrics
    _save_dept_output("engineering", metrics)
    _log(f"[D2]   Parity={metrics['parity_check']}, Engine={metrics['feature_engine_version']}")
    return result


def run_d3_evolution() -> dict:
    """D3 EVOLUTION: Ping all 6 HF islands, collect generation/brier, detect stagnation."""
    _log("[D3] EVOLUTION: Pinging 6 HF islands...")
    result = {
        "department": "evolution",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    island_data = {}
    spaces_up = 0
    best_brier = 1.0
    best_island = None
    total_generations = 0
    briers = []
    models = []
    stagnation_detected = []
    cross_pollination_candidates = []

    for sid, cfg in ISLANDS.items():
        space_url = f"https://{cfg['url']}.hf.space"
        _log(f"[D3]   Pinging {sid} ({cfg['url']})...")

        # Try /api/status first, fall back to root
        status_ok, status_data = safe_get(f"{space_url}/api/status", timeout=20)
        if not status_ok:
            status_ok, status_data = safe_get(space_url, timeout=20)

        island_info = {
            "url": cfg["url"],
            "role": cfg["role"],
            "specialist_model": cfg["specialist_model"],
            "up": status_ok,
            "response": {},
        }

        if status_ok and isinstance(status_data, dict):
            island_info["response"] = status_data
            spaces_up += 1

            # Extract metrics from status response
            brier = (
                status_data.get("best_brier")
                or status_data.get("brier")
                or (status_data.get("metrics", {}) or {}).get("best_brier")
            )
            gen = (
                status_data.get("generation")
                or status_data.get("total_generations")
                or (status_data.get("metrics", {}) or {}).get("generation", 0)
            )
            model = (
                status_data.get("model_type")
                or status_data.get("best_model")
                or (status_data.get("metrics", {}) or {}).get("model_type", "unknown")
            )
            stag = (
                status_data.get("stagnation_cycles")
                or (status_data.get("metrics", {}) or {}).get("stagnation_cycles", 0)
            )

            island_info["brier"] = brier
            island_info["generation"] = gen
            island_info["model"] = model
            island_info["stagnation_cycles"] = stag

            if brier is not None:
                briers.append(brier)
                if brier < best_brier:
                    best_brier = brier
                    best_island = sid
            if gen:
                total_generations += gen
            if model:
                models.append(model)
            if stag and stag > 8:
                stagnation_detected.append({
                    "island": sid,
                    "stagnation_cycles": stag,
                    "brier": brier,
                })

            # Specialist drift detection
            if cfg["specialist_model"] and model and model != cfg["specialist_model"]:
                island_info["model_drift"] = True

        island_data[sid] = island_info

    # Also load from agent-health.json as fallback
    health_file = ROOT / "data" / "agent-health.json"
    if health_file.exists() and best_brier >= 1.0:
        try:
            health = json.loads(health_file.read_text())
            spaces = health.get("projects", {}).get("nba", {}).get("spaces", {})
            for sid, sdata in spaces.items():
                b = sdata.get("brier")
                g = sdata.get("generation", 0)
                m = sdata.get("model", "unknown")
                if b is not None:
                    briers.append(b)
                    if b < best_brier:
                        best_brier = b
                        best_island = sid
                total_generations += g
                models.append(m)
                if sid in island_data and not island_data[sid].get("up"):
                    island_data[sid]["brier"] = b
                    island_data[sid]["generation"] = g
                    island_data[sid]["model"] = m
        except Exception:
            pass

    # Fleet diversity score
    diversity_score = _calc_diversity(models, briers)

    # Cross-pollination candidates: find best islands that could seed weaker ones
    sorted_islands = sorted(
        [(sid, d.get("brier", 1.0)) for sid, d in island_data.items() if d.get("brier")],
        key=lambda x: x[1],
    )
    if len(sorted_islands) >= 2:
        best_sid, best_b = sorted_islands[0]
        for sid, b in sorted_islands[-2:]:
            if b > best_b + 0.002:
                cross_pollination_candidates.append({
                    "source": best_sid,
                    "source_brier": best_b,
                    "target": sid,
                    "target_brier": b,
                    "potential_gain": round(b - best_b, 5),
                })

    # Recommendations
    recommendations = []
    for sid, info in island_data.items():
        cfg = ISLANDS.get(sid, {})
        if info.get("model_drift"):
            recommendations.append({
                "type": "model_drift",
                "island": sid,
                "expected_model": cfg.get("specialist_model"),
                "actual_model": info.get("model"),
                "action": "inject_specialist_config",
                "reason": f"{sid} specialist role drift: expected {cfg.get('specialist_model')}, got {info.get('model')}",
                "priority": 2,
            })

    fleet_avg = round(sum(briers) / len(briers), 5) if briers else None

    metrics = {
        "best_brier": best_brier if best_brier < 1.0 else None,
        "fleet_avg": fleet_avg,
        "best_island": best_island,
        "total_generations": total_generations,
        "spaces_up": spaces_up,
        "spaces_total": 6,
        "stagnation_detected": stagnation_detected,
        "stagnant_count": len(stagnation_detected),
        "diversity_score": diversity_score,
        "cross_pollination_candidates": cross_pollination_candidates,
        "recommendations": recommendations,
        "model_drift": [r for r in recommendations if r.get("type") == "model_drift"],
        "island_details": island_data,
    }

    result["metrics"] = metrics
    _save_dept_output("evolution", metrics)
    _log(f"[D3]   {spaces_up}/6 UP | Best={best_brier} ({best_island}) | Gen={total_generations} | Diversity={diversity_score}")
    return result


def run_d4_betting() -> dict:
    """D4 BETTING: Analyze strategy performance, ROI, Kelly sizing."""
    _log("[D4] BETTING: Analyzing strategy performance...")
    result = {
        "department": "betting",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics = {
        "bankroll": None,
        "roi_pct": None,
        "sharpe": None,
        "win_rate_pct": None,
        "health": "UNKNOWN",
        "strategy_rankings": [],
        "eliminated_strategies": [],
    }

    # Read bankroll state
    bankroll_file = ROOT / "data" / "nba-agent" / "bankroll-state.json"
    if bankroll_file.exists():
        try:
            br = json.loads(bankroll_file.read_text())
            metrics["bankroll"] = br.get("bankroll", br.get("current_bankroll"))
            metrics["roi_pct"] = br.get("roi_pct")
            metrics["sharpe"] = br.get("sharpe")
            metrics["win_rate_pct"] = br.get("win_rate_pct", br.get("win_rate"))
            # Determine health
            roi = metrics["roi_pct"]
            if roi is not None:
                if roi > 5:
                    metrics["health"] = "STRONG"
                elif roi > 0:
                    metrics["health"] = "POSITIVE"
                elif roi > -5:
                    metrics["health"] = "UNDERPERFORMING"
                else:
                    metrics["health"] = "CRITICAL"
        except Exception as e:
            _log(f"[D4]   Bankroll read error: {e}")

    # Read trading floor results for strategy rankings
    tf_file = ROOT / "data" / "arena" / "trading-floor-v4-latest.json"
    if tf_file.exists():
        try:
            tf = json.loads(tf_file.read_text())
            strategies = tf.get("strategies", tf.get("strategy_results", {}))
            if isinstance(strategies, dict):
                rankings = []
                rank = 0
                for name, data in sorted(
                    strategies.items(),
                    key=lambda x: x[1].get("roi_pct", x[1].get("avg_roi_pct", 0)) if isinstance(x[1], dict) else 0,
                    reverse=True,
                ):
                    rank += 1
                    roi = data.get("roi_pct", data.get("avg_roi_pct", 0)) if isinstance(data, dict) else 0
                    verdict = "ELITE" if roi > 50000 else ("STRONG" if roi > 10000 else ("SOLID" if roi > 0 else "LOSING"))
                    rankings.append({
                        "rank": rank,
                        "strategy": name,
                        "avg_roi_pct": roi,
                        "verdict": verdict,
                    })
                metrics["strategy_rankings"] = rankings[:22]
        except Exception as e:
            _log(f"[D4]   TF read error: {e}")

    # Read existing betting output for continuity
    existing_output = DATA_DIR / "betting" / "karpathy-output.json"
    if existing_output.exists() and metrics["bankroll"] is None:
        try:
            ex = json.loads(existing_output.read_text())
            ls = ex.get("live_status", {})
            metrics["bankroll"] = ls.get("bankroll", metrics["bankroll"])
            metrics["roi_pct"] = ls.get("roi_pct", metrics["roi_pct"])
            metrics["sharpe"] = ls.get("sharpe", metrics["sharpe"])
            metrics["win_rate_pct"] = ls.get("win_rate_pct", metrics["win_rate_pct"])
            metrics["health"] = ls.get("health", metrics["health"])
            metrics["strategy_rankings"] = ex.get("strategy_rankings", metrics["strategy_rankings"])
        except Exception:
            pass

    result["metrics"] = metrics
    _save_dept_output("betting", {
        "live_status": {
            "bankroll": metrics["bankroll"],
            "roi_pct": metrics["roi_pct"],
            "sharpe": metrics["sharpe"],
            "win_rate_pct": metrics["win_rate_pct"],
            "health": metrics["health"],
        },
        "strategy_rankings": metrics["strategy_rankings"],
        "eliminated_strategies": metrics["eliminated_strategies"],
    })
    _log(f"[D4]   Bankroll=${metrics['bankroll']} | ROI={metrics['roi_pct']}% | Health={metrics['health']}")
    return result


def run_d5_evaluation() -> dict:
    """D5 EVALUATION: Check prediction accuracy, calibration, false positive rate."""
    _log("[D5] EVALUATION: Checking prediction accuracy...")
    result = {
        "department": "evaluation",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics = {
        "brier_score": None,
        "ece": None,
        "false_positive_rate": None,
        "phantom_games": 0,
        "bias_detected": [],
        "critical_alerts": [],
        "improvements_proposed": [],
        "status": "UNKNOWN",
    }

    # Read latest eval
    eval_file = ROOT / "data" / "nba-agent" / "latest-eval.json"
    if eval_file.exists():
        try:
            ev = json.loads(eval_file.read_text())
            metrics["brier_score"] = ev.get("brier_score", ev.get("brier"))
            metrics["ece"] = ev.get("ece", ev.get("calibration_error"))
            metrics["false_positive_rate"] = ev.get("false_positive_rate", ev.get("fp_rate"))
        except Exception:
            pass

    # Read existing evaluation output for richer data
    eval_output = DATA_DIR / "evaluation" / "karpathy-output.json"
    if eval_output.exists():
        try:
            existing = json.loads(eval_output.read_text())
            if metrics["brier_score"] is None:
                metrics["brier_score"] = existing.get("brier_score")
            if metrics["ece"] is None:
                cal = existing.get("calibration_analysis", {})
                metrics["ece"] = cal.get("ece", existing.get("ece"))
            metrics["phantom_games"] = (existing.get("prediction_distribution") or {}).get("today_phantom_games", 0)
            metrics["bias_detected"] = existing.get("bias_detected", [])
            metrics["critical_alerts"] = existing.get("critical_alerts", [])
            metrics["improvements_proposed"] = existing.get("improvements_proposed", [])
            metrics["status"] = (existing.get("metrics_summary") or {}).get("status_overall", "UNKNOWN")

            # Extract performance trends
            perf = existing.get("performance_trends", {})
            if perf:
                metrics["roi_pct"] = perf.get("roi_pct")
                metrics["sharpe"] = perf.get("sharpe")
        except Exception:
            pass

    # Generate calibration alerts
    if metrics["ece"] is not None and metrics["ece"] > 0.15:
        metrics["critical_alerts"].append(
            f"ECE={metrics['ece']:.4f} -- calibration target <0.05, currently {metrics['ece']/0.05:.1f}x over"
        )
        metrics["status"] = "NEEDS_CALIBRATION"

    if metrics["phantom_games"] > 0:
        metrics["critical_alerts"].append(
            f"PHANTOM: {metrics['phantom_games']} phantom game(s) detected in today picks"
        )

    result["metrics"] = metrics
    _save_dept_output("evaluation", metrics)
    _log(f"[D5]   Brier={metrics['brier_score']} | ECE={metrics['ece']} | Status={metrics['status']}")
    return result


def run_d6_infra() -> dict:
    """D6 INFRA: Ping all spaces and services, check uptime."""
    _log("[D6] INFRA: Checking infrastructure health...")
    result = {
        "department": "infra",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    spaces_up = 0
    spaces_total = 6
    spaces_down = []
    space_latencies = {}
    restart_count = 0

    # Ping all 6 evolution islands
    for sid, cfg in ISLANDS.items():
        url = f"https://{cfg['url']}.hf.space"
        is_up, latency = ping_url(url, timeout=15)
        space_latencies[sid] = {"up": is_up, "latency_ms": latency, "url": cfg["url"]}
        if is_up:
            spaces_up += 1
        else:
            spaces_down.append(sid)
            _log(f"[D6]   {sid} DOWN ({cfg['url']})")

    # Ping services
    service_status = {}
    for name, url in SERVICES.items():
        is_up, latency = ping_url(url, timeout=10)
        service_status[name] = {"up": is_up, "latency_ms": latency}

    uptime_pct = round((spaces_up / spaces_total) * 100, 1) if spaces_total > 0 else 0

    # Load existing infra data for restart count continuity
    infra_output = DATA_DIR / "infra" / "karpathy-output.json"
    if infra_output.exists():
        try:
            existing = json.loads(infra_output.read_text())
            restart_count = existing.get("restart_count", 0)
        except Exception:
            pass

    metrics = {
        "spaces_up": spaces_up,
        "spaces_total": spaces_total,
        "spaces_down": spaces_down,
        "space_latencies": space_latencies,
        "uptime_pct": uptime_pct,
        "restart_count": restart_count,
        "service_status": service_status,
    }

    result["metrics"] = metrics
    _save_dept_output("infra", metrics)
    _log(f"[D6]   Spaces {spaces_up}/{spaces_total} UP | Uptime={uptime_pct}%")
    return result


def run_d7_political() -> dict:
    """D7 POLITICAL: Check political signal freshness, ETF performance."""
    _log("[D7] POLITICAL: Checking political signals...")
    result = {
        "department": "political",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics = {
        "political_brier": None,
        "etf_roi": None,
        "signal_accuracy": None,
        "categories_active": 0,
        "signals_fresh": False,
    }

    # Read existing political data
    pol_output = DATA_DIR / "political" / "karpathy-output.json"
    if pol_output.exists():
        try:
            existing = json.loads(pol_output.read_text())
            metrics["political_brier"] = existing.get("political_brier", existing.get("brier"))
            metrics["etf_roi"] = existing.get("etf_roi")
            metrics["signal_accuracy"] = existing.get("signal_accuracy")
            metrics["categories_active"] = existing.get("categories_active", 0)
        except Exception:
            pass

    # Check political alpha data freshness
    pol_data_dir = ROOT / "data" / "political"
    if pol_data_dir.exists():
        latest_files = sorted(pol_data_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if latest_files:
            age_hours = (time.time() - latest_files[0].stat().st_mtime) / 3600
            metrics["signals_fresh"] = age_hours < 24
            metrics["latest_signal_age_hours"] = round(age_hours, 1)

    # Check political HF spaces
    political_spaces = [
        "nomos42-political-alpha",
        "nomos42-political-alpha-2",
    ]
    pol_spaces_up = 0
    for space in political_spaces:
        is_up, _ = ping_url(f"https://{space}.hf.space", timeout=10)
        if is_up:
            pol_spaces_up += 1
    metrics["political_spaces_up"] = pol_spaces_up

    result["metrics"] = metrics
    _save_dept_output("political", metrics)
    _log(f"[D7]   Brier={metrics['political_brier']} | Fresh={metrics['signals_fresh']}")
    return result


def run_d8_creative() -> dict:
    """D8 CREATIVE (RGWA): Check art generation pipeline status."""
    _log("[D8] CREATIVE: Checking RGWA pipeline...")
    result = {
        "department": "creative",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics = {
        "quality_score": None,
        "pieces_today": 0,
        "pipeline_status": "UNKNOWN",
    }

    # Read existing creative data
    creative_output = DATA_DIR / "creative" / "karpathy-output.json"
    if creative_output.exists():
        try:
            existing = json.loads(creative_output.read_text())
            metrics["quality_score"] = existing.get("quality_score")
            metrics["pieces_today"] = existing.get("pieces_today", 0)
            metrics["pipeline_status"] = existing.get("pipeline_status", "UNKNOWN")
        except Exception:
            pass

    # Check RGWA space
    is_up, latency = ping_url("https://lbjlincoln-rgwa.hf.space", timeout=10)
    metrics["rgwa_space_up"] = is_up
    metrics["rgwa_latency_ms"] = latency

    result["metrics"] = metrics
    _save_dept_output("creative", metrics)
    _log(f"[D8]   Quality={metrics['quality_score']} | Pieces={metrics['pieces_today']} | RGWA Up={is_up}")
    return result


def run_d9_communication() -> dict:
    """D9 COMMUNICATION: Count prepared posts, check channel status."""
    _log("[D9] COMMUNICATION: Checking content pipeline...")
    result = {
        "department": "communication",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics = {
        "posts_prepared": 0,
        "channels_active": 0,
        "engagement_rate": 0,
        "channels": {},
    }

    # Check Telegram bot status
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if tg_token:
        try:
            resp = requests.get(f"https://api.telegram.org/bot{tg_token}/getMe", timeout=10)
            if resp.status_code == 200:
                metrics["channels"]["telegram"] = "ACTIVE"
                metrics["channels_active"] += 1
        except Exception:
            metrics["channels"]["telegram"] = "ERROR"
    else:
        metrics["channels"]["telegram"] = "NO_TOKEN"

    # Check for prepared content
    social_posts = ROOT / "docs" / "social-media-posts.md"
    if social_posts.exists():
        try:
            content = social_posts.read_text()
            # Count posts (rough: count "##" headers)
            metrics["posts_prepared"] = content.count("## ")
        except Exception:
            pass

    # GitHub is always active
    metrics["channels"]["github"] = "ACTIVE"
    metrics["channels_active"] += 1

    # Read existing comm data
    comm_output = DATA_DIR / "communication" / "karpathy-output.json"
    if comm_output.exists():
        try:
            existing = json.loads(comm_output.read_text())
            metrics["posts_prepared"] = max(metrics["posts_prepared"], existing.get("posts_prepared", 0))
            metrics["engagement_rate"] = existing.get("engagement_rate", 0)
        except Exception:
            pass

    result["metrics"] = metrics
    _save_dept_output("communication", metrics)
    _log(f"[D9]   Posts={metrics['posts_prepared']} | Channels={metrics['channels_active']}")
    return result


def run_d10_business() -> dict:
    """D10 BUSINESS: Track users, pricing, MRR."""
    _log("[D10] BUSINESS: Checking business metrics...")
    result = {
        "department": "business",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics = {
        "mrr": 0,
        "active_users": 1,  # Pierre is user #1
        "paid_users": 0,
        "conversion_rate": 0,
        "pricing_tiers": {
            "starter": 19,
            "builder": 49,
            "factory": 149,
        },
        "dashboard_status": "UNKNOWN",
    }

    # Check dashboard
    is_up, latency = ping_url("https://nomosdashboard.vercel.app", timeout=10)
    metrics["dashboard_status"] = "UP" if is_up else "DOWN"
    metrics["dashboard_latency_ms"] = latency

    # Read existing business data
    biz_output = DATA_DIR / "business" / "karpathy-output.json"
    if biz_output.exists():
        try:
            existing = json.loads(biz_output.read_text())
            metrics["mrr"] = existing.get("mrr", 0)
            metrics["active_users"] = max(1, existing.get("active_users", 1))
            metrics["paid_users"] = existing.get("paid_users", 0)
            metrics["conversion_rate"] = existing.get("conversion_rate", 0)
        except Exception:
            pass

    # Check forge users directory for user count
    forge_users = ROOT / "forge-users"
    if forge_users.exists():
        user_dirs = [d for d in forge_users.iterdir() if d.is_dir()]
        metrics["active_users"] = max(metrics["active_users"], len(user_dirs))

    result["metrics"] = metrics
    _save_dept_output("business", metrics)
    _log(f"[D10]  MRR=${metrics['mrr']} | Users={metrics['active_users']} | Dashboard={metrics['dashboard_status']}")
    return result


def run_d11_finance() -> dict:
    """D11 FINANCE: Track costs, revenue, generate P&L."""
    _log("[D11] FINANCE: Generating P&L...")
    result = {
        "department": "finance",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics = {
        "financial_accuracy": 0,
        "monthly_burn_rate": 6.0,  # ~$6/mo as documented
        "monthly_revenue": 0,
        "net_pnl": -6.0,
        "betting_pnl": 0,
        "cost_breakdown": {
            "gcp_vm": 0,
            "hf_spaces": 0,
            "kaggle_gpu": 0,
            "colab_gpu": 0,
            "vercel": 0,
            "domain": 1.0,
            "modal": 5.0,
            "supabase": 0,
        },
        "runway_months": "infinite (nearly free infra)",
    }

    # Read bankroll for betting P&L
    bankroll_file = ROOT / "data" / "nba-agent" / "bankroll-state.json"
    if bankroll_file.exists():
        try:
            br = json.loads(bankroll_file.read_text())
            initial = br.get("initial_bankroll", 100)
            current = br.get("bankroll", br.get("current_bankroll", initial))
            metrics["betting_pnl"] = round(current - initial, 2)
        except Exception:
            pass

    metrics["net_pnl"] = round(metrics["monthly_revenue"] + metrics["betting_pnl"] - metrics["monthly_burn_rate"], 2)

    # Financial accuracy: percentage of costs tracked
    total_items = len(metrics["cost_breakdown"])
    tracked = sum(1 for v in metrics["cost_breakdown"].values() if v is not None)
    metrics["financial_accuracy"] = round((tracked / total_items) * 100, 1) if total_items > 0 else 0

    # Read existing finance data
    fin_output = DATA_DIR / "finance" / "karpathy-output.json"
    if fin_output.exists():
        try:
            existing = json.loads(fin_output.read_text())
            metrics["monthly_revenue"] = existing.get("monthly_revenue", metrics["monthly_revenue"])
            metrics["financial_accuracy"] = max(metrics["financial_accuracy"], existing.get("financial_accuracy", 0))
        except Exception:
            pass

    result["metrics"] = metrics
    _save_dept_output("finance", metrics)
    _log(f"[D11]  Burn=${metrics['monthly_burn_rate']}/mo | Betting P&L=${metrics['betting_pnl']} | Net=${metrics['net_pnl']}")
    return result


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _file_hash(path: Path) -> str:
    """Quick hash of a file for comparison."""
    import hashlib
    return hashlib.md5(path.read_bytes()).hexdigest()


def _calc_diversity(models: list, briers: list) -> float:
    """Composite diversity: 60% model variety + 40% Brier spread."""
    if not models:
        return 0.0
    model_diversity = len(set(models)) / max(len(models), 1)
    brier_diversity = 0.0
    if len(briers) > 1:
        avg = sum(briers) / len(briers)
        std = (sum((b - avg) ** 2 for b in briers) / len(briers)) ** 0.5
        brier_cv = std / avg if avg > 0 else 0
        brier_diversity = min(brier_cv / 0.02, 1.0)
    return round(0.6 * model_diversity + 0.4 * brier_diversity, 3)


def _save_dept_output(dept_key: str, metrics: dict):
    """Save department karpathy-output.json."""
    dept_dir = DATA_DIR / dept_key
    dept_dir.mkdir(parents=True, exist_ok=True)
    output_file = dept_dir / "karpathy-output.json"
    output_file.write_text(json.dumps(metrics, indent=2, default=str))


# ============================================================================
# GUARDIAN ORCHESTRATOR
# ============================================================================

def run_guardian(dept_results: dict, iteration: int) -> dict:
    """
    Guardian v3: Cross-department intelligence, priority queue, elimination tracking.
    Runs AFTER all 11 departments complete.
    """
    _log("[GUARDIAN] Running cross-department analysis...")

    # 1. Extract key metrics from all departments
    metrics = _extract_guardian_metrics(dept_results)

    # 2. Detect cross-department issues
    issues = _detect_cross_dept_issues(metrics)

    # 3. Build priority queue
    priority_queue = _build_priority_queue(metrics, issues)

    # 4. Track eliminations
    eliminations = _update_eliminations(metrics, iteration)

    # 5. Cross-pollinate wins
    cross_poll = _cross_pollinate(metrics)

    # 6. Compute health score
    health_score = _compute_health_score(metrics, issues)

    # 7. Build department summaries
    dept_summaries = _build_summaries(metrics)

    # 8. Determine critical alerts (top 5)
    critical_alerts = [i for i in issues if i.get("severity") in ("CRITICAL", "HIGH")][:5]

    # 9. Build run summary
    completed = sum(1 for r in dept_results.values() if r.get("status") == "completed")
    failed = sum(1 for r in dept_results.values() if r.get("status") == "failed")
    timeout = sum(1 for r in dept_results.values() if r.get("status") == "timeout")
    total_duration = sum(r.get("duration_s", 0) for r in dept_results.values() if isinstance(r.get("duration_s"), (int, float)))

    evo_metrics = metrics.get("evolution", {})

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "cycle_start": dept_results.get("_cycle_start", datetime.now(timezone.utc).isoformat()),
        "cycle_end": datetime.now(timezone.utc).isoformat(),
        "health_score": health_score,
        "run_summary": {
            "total": 11,
            "completed": completed,
            "failed": failed,
            "timeout": timeout,
            "skipped": 11 - completed - failed - timeout,
            "total_duration_s": round(total_duration, 1),
            "fleet_interventions": 0,
            "fleet_diversity_score": evo_metrics.get("diversity_score", 0),
        },
        "dept_summaries": dept_summaries,
        "critical_alerts": critical_alerts,
        "all_issues": issues,
        "priority_queue": priority_queue,
        "cross_pollination": cross_poll,
        "eliminations": eliminations,
        "fleet_interventions": [],
        "raw_metrics": metrics,
    }

    # Save guardian report
    GUARDIAN_REPORT.parent.mkdir(parents=True, exist_ok=True)
    GUARDIAN_REPORT.write_text(json.dumps(report, indent=2, default=str))
    _log(f"[GUARDIAN] Health={health_score}/100 | {completed}/11 completed | {len(critical_alerts)} critical alerts")

    return report


def _extract_guardian_metrics(dept_results: dict) -> dict:
    """Pull key metrics from each department result."""
    metrics = {}
    for dept_info in DEPARTMENTS.values():
        key = dept_info["key"]
        result = dept_results.get(key, {})
        m = result.get("metrics", {})
        metrics[key] = m

    # Also load trading floor data
    tf_output = DATA_DIR / "trading_floor" / "karpathy-output.json"
    if tf_output.exists():
        try:
            metrics["trading_floor"] = json.loads(tf_output.read_text())
        except Exception:
            metrics["trading_floor"] = {}
    else:
        metrics["trading_floor"] = {}

    return metrics


def _detect_cross_dept_issues(metrics: dict) -> list:
    """Detect issues spanning department boundaries."""
    issues = []
    ts = datetime.now(timezone.utc).isoformat()
    ev = metrics.get("evaluation", {})
    evo = metrics.get("evolution", {})
    bet = metrics.get("betting", {})
    inf = metrics.get("infra", {})

    # Evaluation -> Engineering: phantom games
    phantom = ev.get("phantom_games", 0)
    if phantom > 0:
        issues.append({
            "severity": "CRITICAL",
            "source_dept": "evaluation",
            "target_dept": "engineering",
            "issue_type": "PHANTOM_GAME",
            "description": f"{phantom} phantom game(s) detected (home==away)",
            "recommended_action": 'Add assert game["home"] != game["away"] in predict_today.py',
            "detected_at": ts,
        })

    # Evaluation -> Engineering: calibration crisis
    ece = ev.get("ece")
    if ece is not None and ece > 0.15:
        issues.append({
            "severity": "CRITICAL",
            "source_dept": "evaluation",
            "target_dept": "engineering",
            "issue_type": "CALIBRATION_CRISIS",
            "description": f"ECE={ece:.4f} -- target <0.05, currently {ece/0.05:.1f}x over",
            "recommended_action": "Deploy Platt scaling / isotonic regression post-hoc calibration",
            "detected_at": ts,
        })

    # Evaluation biases
    for bias in ev.get("bias_detected", []):
        btype = bias.get("type", "UNKNOWN")
        bsev = bias.get("severity", "MEDIUM")
        if bsev in ("CRITICAL", "HIGH"):
            issues.append({
                "severity": bsev,
                "source_dept": "evaluation",
                "target_dept": "engineering",
                "issue_type": f"BIAS_{btype}",
                "description": bias.get("description", f"{btype} bias detected"),
                "recommended_action": bias.get("fix", "Investigate in engineering"),
                "detected_at": ts,
            })

    # Evolution: stagnation
    for stag in evo.get("stagnation_detected", []):
        cycles = stag.get("stagnation_cycles", 0)
        island = stag.get("island", "?")
        sev = "CRITICAL" if cycles >= 15 else "HIGH"
        issues.append({
            "severity": sev,
            "source_dept": "evolution",
            "target_dept": "infra",
            "issue_type": "SPACE_STAGNATION",
            "description": f"{island} stagnant for {cycles} cycles",
            "recommended_action": f"POST diversify command to {island}",
            "detected_at": ts,
        })

    # Evolution: model drift
    for drift in evo.get("model_drift", []):
        issues.append({
            "severity": "MEDIUM",
            "source_dept": "evolution",
            "target_dept": "evolution",
            "issue_type": "MODEL_DRIFT",
            "description": f"{drift.get('island')} drift: expected {drift.get('expected_model')}, got {drift.get('actual_model')}",
            "recommended_action": f"Restore {drift.get('island')} specialist config",
            "detected_at": ts,
        })

    # Evolution: low diversity
    diversity = evo.get("diversity_score")
    if diversity is not None and diversity < 0.5:
        issues.append({
            "severity": "MEDIUM",
            "source_dept": "evolution",
            "target_dept": "evolution",
            "issue_type": "LOW_DIVERSITY",
            "description": f"Fleet diversity={diversity:.3f} < 0.50",
            "recommended_action": "Force specialist configs to restore model variety",
            "detected_at": ts,
        })

    # Betting -> Evaluation: negative ROI
    roi = bet.get("roi_pct")
    if roi is not None and roi < 0:
        issues.append({
            "severity": "HIGH",
            "source_dept": "betting",
            "target_dept": "evaluation",
            "issue_type": "NEGATIVE_ROI",
            "description": f"ROI={roi:.1f}% (target >5%)",
            "recommended_action": "Prioritize ECE fix; pause full_kelly until ECE < 0.10",
            "detected_at": ts,
        })

    # Infra: spaces down
    for sid in inf.get("spaces_down", []):
        issues.append({
            "severity": "HIGH",
            "source_dept": "infra",
            "target_dept": "infra",
            "issue_type": "SPACE_DOWN",
            "description": f"{sid} is DOWN",
            "recommended_action": f"Restart {sid} via HF Spaces API or manual",
            "detected_at": ts,
        })

    # Trading Floor recommendations
    tf = metrics.get("trading_floor", {})
    for rec in tf.get("recommendations", []):
        issues.append({
            "severity": "MEDIUM",
            "source_dept": "trading_floor",
            "target_dept": rec.get("target_dept", "betting"),
            "issue_type": rec.get("type", "TRADING_FLOOR_REC"),
            "description": rec.get("reason", ""),
            "recommended_action": rec.get("reason", ""),
            "detected_at": ts,
        })

    return issues


def _build_priority_queue(metrics: dict, issues: list) -> list:
    """Build priority-ordered action queue."""
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    queue = []

    for issue in issues:
        queue.append({
            "priority": issue["severity"],
            "action": issue["recommended_action"],
            "dept": issue["target_dept"],
            "source": issue["source_dept"],
            "issue_type": issue["issue_type"],
            "description": issue["description"],
        })

    # From evaluation improvements
    for prop in metrics.get("evaluation", {}).get("improvements_proposed", []):
        pnum = prop.get("priority", 99)
        prio = "CRITICAL" if pnum <= 1 else ("HIGH" if pnum <= 3 else "MEDIUM")
        queue.append({
            "priority": prio,
            "action": prop.get("action", prop.get("title", "")),
            "dept": prop.get("department", "engineering").lower().replace("d5/", "").replace("d2/", ""),
            "source": "evaluation",
            "issue_type": prop.get("type", "improvement"),
            "description": prop.get("title", ""),
        })

    # From evolution recommendations
    for rec in metrics.get("evolution", {}).get("recommendations", []):
        rp = rec.get("priority", 3)
        prio = "CRITICAL" if rp == 1 else ("HIGH" if rp == 2 else "MEDIUM")
        queue.append({
            "priority": prio,
            "action": rec.get("action", ""),
            "dept": "evolution",
            "source": "evolution",
            "issue_type": rec.get("type", "evolution"),
            "description": rec.get("reason", ""),
        })

    # Deduplicate
    seen, deduped = set(), []
    for item in queue:
        key = (item["dept"], item["issue_type"], item["action"][:60])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    deduped.sort(key=lambda x: priority_order.get(x["priority"], 3))
    return deduped


def _update_eliminations(metrics: dict, iteration: int) -> dict:
    """Track eliminated strategies."""
    bet = metrics.get("betting", {})
    rankings = bet.get("strategy_rankings", [])

    elim_strategies = {}
    coffins = []

    # Load existing eliminations
    elim_file = DATA_DIR / "eliminations.json"
    if elim_file.exists():
        try:
            existing = json.loads(elim_file.read_text())
            elim_strategies = existing.get("strategies", {})
            coffins = existing.get("coffins", [])
        except Exception:
            pass

    for entry in rankings:
        strat = entry.get("strategy", "")
        verdict = entry.get("verdict", "")
        if verdict in ("ELIMINATED", "WEAK", "FAILING") and strat and strat not in elim_strategies:
            elim_strategies[strat] = {
                "eliminated_at_iteration": iteration,
                "reason": f"verdict={verdict}",
                "avg_roi_pct": entry.get("avg_roi_pct"),
                "eliminated_at": datetime.now(timezone.utc).isoformat(),
            }
            coffins.append({
                "type": "strategy",
                "name": strat,
                "iteration": iteration,
                "cause_of_death": verdict,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    result = {
        "strategies": elim_strategies,
        "total_eliminated": len(elim_strategies),
        "coffins": coffins[-50:],
    }

    elim_file.parent.mkdir(parents=True, exist_ok=True)
    elim_file.write_text(json.dumps(result, indent=2))
    return result


def _cross_pollinate(metrics: dict) -> dict:
    """Enhanced cross-pollination: detect wins and generate recommendations."""
    wins = {}
    recs = []

    # Evolution cross-pollination
    for cand in metrics.get("evolution", {}).get("cross_pollination_candidates", []):
        recs.append({
            "from": f"evolution/{cand.get('source')}",
            "to": f"evolution/{cand.get('target')}",
            "action": f"Seed {cand.get('target')} with {cand.get('source')} config (potential gain: {cand.get('potential_gain', 0):.5f})",
        })

    # Research -> Engineering
    res = metrics.get("research", {})
    if res.get("techniques_extracted", 0) > 0:
        wins["research"] = {"techniques": res["techniques_extracted"]}
        recs.append({
            "from": "research",
            "to": "engineering",
            "action": f"Apply {res['techniques_extracted']} extracted techniques from {res.get('papers_scanned', 0)} papers",
        })

    # Trading Floor -> Betting
    tf = metrics.get("trading_floor", {})
    tf_best = tf.get("best_strategy", {})
    if tf_best.get("roi_pct", 0) > 5:
        wins["trading_floor"] = {"strategy": tf_best.get("name"), "roi_pct": tf_best.get("roi_pct")}
        recs.append({
            "from": "trading_floor",
            "to": "betting",
            "action": f"Promote '{tf_best.get('name')}' to live ({tf_best.get('roi_pct', 0):+.1f}% ROI)",
        })

    # Evaluation win if Brier < 0.222
    ev = metrics.get("evaluation", {})
    brier = ev.get("brier_score")
    if brier and brier < 0.222:
        wins["evaluation"] = {"brier": brier}

    # Save wins
    wins_data = {
        "wins": wins,
        "recommendations": recs,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    WINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WINS_FILE.write_text(json.dumps(wins_data, indent=2))

    return {
        "wins_detected": list(wins.keys()),
        "total_wins": len(wins),
        "cross_pollination_recommendations": recs,
    }


def _compute_health_score(metrics: dict, issues: list) -> int:
    """Compute overall system health 0-100."""
    score = 100
    score -= sum(15 for i in issues if i.get("severity") == "CRITICAL")
    score -= sum(7 for i in issues if i.get("severity") == "HIGH")
    score -= sum(2 for i in issues if i.get("severity") == "MEDIUM")

    ev = metrics.get("evaluation", {})
    brier = ev.get("brier_score")
    if brier:
        score -= int(max(0, brier - 0.20) * 300)

    roi = ev.get("roi_pct")
    if roi is not None and roi < 0:
        score -= min(20, int(abs(roi) * 2))

    evo = metrics.get("evolution", {})
    diversity = evo.get("diversity_score")
    if diversity is not None and diversity >= 0.6:
        score += 5

    inf = metrics.get("infra", {})
    spaces_up = inf.get("spaces_up")
    if spaces_up is not None:
        score -= max(0, 6 - spaces_up) * 5

    return max(0, min(100, score))


def _build_summaries(metrics: dict) -> dict:
    """Build one-line summaries for each department."""
    ev = metrics.get("evaluation", {})
    evo = metrics.get("evolution", {})
    bet = metrics.get("betting", {})
    res = metrics.get("research", {})
    inf = metrics.get("infra", {})
    pol = metrics.get("political", {})
    cre = metrics.get("creative", {})
    eng = metrics.get("engineering", {})
    comm = metrics.get("communication", {})
    biz = metrics.get("business", {})
    fin = metrics.get("finance", {})
    tf = metrics.get("trading_floor", {})

    return {
        "evaluation": (
            f"Brier={ev.get('brier_score')} | ECE={ev.get('ece')} | "
            f"Phantom={ev.get('phantom_games', 0)} | Status={ev.get('status', '?')}"
        ),
        "evolution": (
            f"Best={evo.get('best_brier')} ({evo.get('best_island')}) | "
            f"Avg={evo.get('fleet_avg')} | Gen={evo.get('total_generations')} | "
            f"{evo.get('spaces_up', '?')}/6 UP | Diversity={evo.get('diversity_score')}"
        ),
        "betting": (
            f"${bet.get('bankroll')} | ROI={bet.get('roi_pct')}% | "
            f"Sharpe={bet.get('sharpe')} | WR={bet.get('win_rate_pct')}% | {bet.get('health', '?')}"
        ),
        "research": (
            f"{res.get('papers_scanned', 0)} papers | {res.get('techniques_extracted', 0)} techniques | "
            f"gap={res.get('gap_to_close')}"
        ),
        "infra": (
            f"Spaces {inf.get('spaces_up', '?')}/{inf.get('spaces_total', 6)} UP | "
            f"Uptime={inf.get('uptime_pct')}% | Restarts={inf.get('restart_count', 0)}"
        ),
        "political": (
            f"Brier={pol.get('political_brier')} | ETF={pol.get('etf_roi')} | "
            f"Fresh={pol.get('signals_fresh')}"
        ),
        "creative": (
            f"Quality={cre.get('quality_score')} | Pieces={cre.get('pieces_today', 0)} | "
            f"RGWA={cre.get('rgwa_space_up')}"
        ),
        "engineering": (
            f"Parity={eng.get('parity_check', '?')} | Engine={eng.get('feature_engine_version')} | "
            f"Brier delta={eng.get('brier_delta', 0)}"
        ),
        "communication": (
            f"Posts={comm.get('posts_prepared', 0)} | Channels={comm.get('channels_active', 0)} | "
            f"Engagement={comm.get('engagement_rate', 0)}%"
        ),
        "business": (
            f"MRR=${biz.get('mrr', 0)} | Users={biz.get('active_users', 0)} | "
            f"Dashboard={biz.get('dashboard_status', '?')}"
        ),
        "finance": (
            f"Burn=${fin.get('monthly_burn_rate', '?')}/mo | Net P&L=${fin.get('net_pnl', '?')} | "
            f"Accuracy={fin.get('financial_accuracy', 0)}%"
        ),
        "trading_floor": (
            f"iter={tf.get('iteration', '?')} | "
            f"best_strat={tf.get('best_strategy', {}).get('name', '?')} | "
            f"best_model={tf.get('best_model', {}).get('name', '?')}"
        ),
    }


# ============================================================================
# MAIN LOOP
# ============================================================================

DEPT_RUNNERS = {
    "research": run_d1_research,
    "engineering": run_d2_engineering,
    "evolution": run_d3_evolution,
    "betting": run_d4_betting,
    "evaluation": run_d5_evaluation,
    "infra": run_d6_infra,
    "political": run_d7_political,
    "creative": run_d8_creative,
    "communication": run_d9_communication,
    "business": run_d10_business,
    "finance": run_d11_finance,
}


def run_forge_cycle(iteration: int) -> dict:
    """Run one complete Forge cycle: all 11 departments + Guardian."""
    cycle_start = datetime.now(timezone.utc).isoformat()
    _log(f"=== FORGE CYCLE {iteration} START ===")
    _update_state(status="running", iteration=iteration)

    dept_results = {"_cycle_start": cycle_start}
    completed = 0
    failed = 0

    # Run all 11 departments sequentially
    for dept_key, runner_fn in DEPT_RUNNERS.items():
        dept_id = [k for k, v in DEPARTMENTS.items() if v["key"] == dept_key][0]
        try:
            start_t = time.time()
            result = runner_fn()
            result["duration_s"] = round(time.time() - start_t, 1)
            dept_results[dept_key] = result
            completed += 1

            # Track metric history
            metric_key = DEPARTMENTS[dept_id]["metric"]
            metric_val = (result.get("metrics") or {}).get(metric_key)
            if metric_val is not None:
                _track_metric(dept_key, iteration, metric_val)

        except Exception as e:
            _log(f"[{dept_id}] FAILED: {e}")
            traceback.print_exc()
            dept_results[dept_key] = {
                "department": dept_key,
                "status": "failed",
                "error": str(e)[:300],
            }
            failed += 1

    # Run Guardian cross-department analysis
    try:
        guardian_report = run_guardian(dept_results, iteration)
    except Exception as e:
        _log(f"[GUARDIAN] FAILED: {e}")
        traceback.print_exc()
        guardian_report = {"error": str(e), "health_score": 0}

    # Update global state
    _update_state(
        status="idle",
        iteration=iteration,
        health_score=guardian_report.get("health_score", 0),
        total_completed=_get_state()["total_completed"] + completed,
        total_failures=_get_state()["total_failures"] + failed,
        last_run_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        last_duration_s=round(time.time() - time.time(), 1),
        department_results=dept_results,
        guardian_report=guardian_report,
        wins=guardian_report.get("cross_pollination", {}).get("wins_detected", []),
    )

    _log(f"=== FORGE CYCLE {iteration} END === Health={guardian_report.get('health_score', 0)}/100, {completed}/11 OK")

    # Git sync
    try:
        git_sync(iteration)
    except Exception as e:
        _log(f"[git] Sync failed: {e}")

    return guardian_report


def _track_metric(dept_key: str, iteration: int, value):
    """Track metric history for trend analysis."""
    with _state_lock:
        history = _state["dept_history"].setdefault(dept_key, [])
        history.append({
            "iteration": iteration,
            "value": value,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        # Keep last 100 entries
        if len(history) > 100:
            _state["dept_history"][dept_key] = history[-100:]


def background_loop():
    """Background loop running every 15 minutes."""
    _update_state(loop_running=True, status="initializing")

    try:
        clone_repo()
        _update_state(status="ready")
    except Exception as e:
        _log(f"FATAL: Could not clone repo: {e}")
        _update_state(status=f"error: {e}", loop_running=False)
        return

    iteration = 0

    # Load existing iteration count from guardian report
    if GUARDIAN_REPORT.exists():
        try:
            existing = json.loads(GUARDIAN_REPORT.read_text())
            iteration = existing.get("iteration", 0)
        except Exception:
            pass

    while iteration < MAX_ITERATIONS:
        iteration += 1
        cycle_start = time.time()

        try:
            # Pull latest before each cycle
            subprocess.run(
                ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                cwd=str(ROOT), capture_output=True, timeout=60,
            )
        except Exception:
            pass

        try:
            run_forge_cycle(iteration)
        except Exception as e:
            _log(f"CYCLE {iteration} FAILED: {e}")
            traceback.print_exc()

        # Wait for next cycle
        elapsed = time.time() - cycle_start
        wait_time = max(10, LOOP_DELAY_SECONDS - elapsed)
        _log(f"Next cycle in {int(wait_time)}s...")
        _update_state(status=f"waiting (next in {int(wait_time)}s)")
        time.sleep(wait_time)

    _update_state(loop_running=False, status="stopped")


# ============================================================================
# GRADIO DASHBOARD
# ============================================================================

def render_overview() -> str:
    """Render the Overview tab: table of all 11 departments."""
    state = _get_state()
    report = state.get("guardian_report", {})
    summaries = report.get("dept_summaries", {})
    health = report.get("health_score", 0)
    iteration = state.get("iteration", 0)

    health_icon = "🟢" if health >= 80 else ("🟡" if health >= 60 else "🔴")

    lines = [
        f"# Forge Orchestrator {health_icon} Health: {health}/100",
        f"**Iteration:** {iteration} | **Status:** {state.get('status', '?')} | **Last Run:** {state.get('last_run_time', 'never')}",
        "",
        "| # | Department | Key Metric | Summary |",
        "|---|-----------|------------|---------|",
    ]

    dept_order = [
        ("D1", "RESEARCH", "research"),
        ("D2", "ENGINEERING", "engineering"),
        ("D3", "EVOLUTION", "evolution"),
        ("D4", "BETTING", "betting"),
        ("D5", "EVALUATION", "evaluation"),
        ("D6", "INFRA", "infra"),
        ("D7", "POLITICAL", "political"),
        ("D8", "CREATIVE", "creative"),
        ("D9", "COMMUNICATION", "communication"),
        ("D10", "BUSINESS", "business"),
        ("D11", "FINANCE", "finance"),
        ("TF", "TRADING FLOOR", "trading_floor"),
    ]

    for dept_id, dept_name, key in dept_order:
        summary = summaries.get(key, "No data yet")
        metric_name = DEPARTMENTS.get(dept_id, {}).get("metric", "")
        lines.append(f"| **{dept_id}** | {dept_name} | `{metric_name}` | {summary} |")

    # Run summary
    run_sum = report.get("run_summary", {})
    if run_sum:
        lines.extend([
            "",
            f"**Cycle Stats:** {run_sum.get('completed', 0)}/11 completed, "
            f"{run_sum.get('failed', 0)} failed, {run_sum.get('timeout', 0)} timeout | "
            f"Duration: {run_sum.get('total_duration_s', 0)}s | "
            f"Diversity: {run_sum.get('fleet_diversity_score', 0):.3f}",
        ])

    return "\n".join(lines)


def render_department_detail(dept_selection: str) -> str:
    """Render detailed view for a selected department."""
    state = _get_state()
    report = state.get("guardian_report", {})
    raw = report.get("raw_metrics", {})

    # Parse department key from selection
    dept_map = {
        "D1 - RESEARCH": "research",
        "D2 - ENGINEERING": "engineering",
        "D3 - EVOLUTION": "evolution",
        "D4 - BETTING": "betting",
        "D5 - EVALUATION": "evaluation",
        "D6 - INFRA": "infra",
        "D7 - POLITICAL": "political",
        "D8 - CREATIVE": "creative",
        "D9 - COMMUNICATION": "communication",
        "D10 - BUSINESS": "business",
        "D11 - FINANCE": "finance",
        "TRADING FLOOR": "trading_floor",
    }

    key = dept_map.get(dept_selection, "research")
    metrics = raw.get(key, {})

    if not metrics:
        return f"# {dept_selection}\n\nNo data available yet. Waiting for first cycle to complete."

    lines = [
        f"# {dept_selection}",
        "",
        "## Current Metrics",
        "```json",
        json.dumps(metrics, indent=2, default=str)[:3000],
        "```",
    ]

    # Show metric history
    history = state.get("dept_history", {}).get(key, [])
    if history:
        lines.extend([
            "",
            "## Metric History (last 20)",
            "| Iteration | Value | Timestamp |",
            "|-----------|-------|-----------|",
        ])
        for entry in history[-20:]:
            lines.append(
                f"| {entry.get('iteration')} | {entry.get('value')} | {entry.get('ts', '')[:19]} |"
            )

    # Show relevant issues
    issues = [i for i in report.get("all_issues", []) if i.get("source_dept") == key or i.get("target_dept") == key]
    if issues:
        lines.extend([
            "",
            "## Related Issues",
            "| Severity | Type | Description | Action |",
            "|----------|------|-------------|--------|",
        ])
        for issue in issues[:10]:
            lines.append(
                f"| {issue.get('severity')} | {issue.get('issue_type')} | "
                f"{issue.get('description', '')[:60]} | {issue.get('recommended_action', '')[:60]} |"
            )

    return "\n".join(lines)


def render_guardian_report() -> str:
    """Render the Guardian Report tab."""
    state = _get_state()
    report = state.get("guardian_report", {})

    if not report:
        return "# Guardian Report\n\nWaiting for first cycle to complete..."

    health = report.get("health_score", 0)
    health_icon = "🟢" if health >= 80 else ("🟡" if health >= 60 else "🔴")

    lines = [
        f"# Guardian Report {health_icon} {health}/100",
        f"**Iteration:** {report.get('iteration', 0)} | **Time:** {report.get('timestamp', '')[:19]}",
        "",
    ]

    # Critical alerts
    alerts = report.get("critical_alerts", [])
    if alerts:
        lines.extend(["## Critical Alerts", ""])
        for alert in alerts:
            lines.append(f"- **[{alert.get('severity', '?')}]** {alert.get('issue_type', '?')}: {alert.get('description', '')}")
        lines.append("")

    # Priority queue
    pq = report.get("priority_queue", [])
    if pq:
        lines.extend([
            "## Priority Action Queue",
            "| Priority | Dept | Source | Type | Action |",
            "|----------|------|--------|------|--------|",
        ])
        for item in pq[:15]:
            lines.append(
                f"| {item.get('priority')} | {item.get('dept')} | {item.get('source')} | "
                f"{item.get('issue_type', '')} | {item.get('action', '')[:70]} |"
            )
        lines.append("")

    # Cross-pollination
    cp = report.get("cross_pollination", {})
    if cp.get("cross_pollination_recommendations"):
        lines.extend(["## Cross-Pollination Recommendations", ""])
        for rec in cp["cross_pollination_recommendations"]:
            lines.append(f"- **{rec.get('from')}** -> **{rec.get('to')}**: {rec.get('action', '')}")
        lines.append("")

    # Eliminations
    elim = report.get("eliminations", {})
    if elim.get("total_eliminated", 0) > 0:
        lines.extend([
            f"## Eliminations ({elim['total_eliminated']} total)",
            "",
        ])
        for coffin in (elim.get("coffins") or [])[-5:]:
            lines.append(f"- **{coffin.get('name')}** ({coffin.get('type')}) -- {coffin.get('cause_of_death')}")
        lines.append("")

    return "\n".join(lines)


def render_wins() -> str:
    """Render the Wins tab."""
    state = _get_state()
    report = state.get("guardian_report", {})
    cp = report.get("cross_pollination", {})

    lines = [
        "# Wins & Improvements",
        "",
    ]

    wins = cp.get("wins_detected", [])
    if wins:
        lines.append(f"## Departments with Wins ({len(wins)})")
        for w in wins:
            lines.append(f"- {w}")
        lines.append("")
    else:
        lines.append("*No wins detected this cycle.*\n")

    recs = cp.get("cross_pollination_recommendations", [])
    if recs:
        lines.extend(["## Cross-Pollination Actions", ""])
        for rec in recs:
            lines.append(f"- **{rec.get('from')}** -> **{rec.get('to')}**: {rec.get('action', '')}")
        lines.append("")

    # Show full wins history from file
    try:
        if WINS_FILE.exists():
            wins_data = json.loads(WINS_FILE.read_text())
            lines.extend([
                "## Latest Wins Data",
                "```json",
                json.dumps(wins_data, indent=2, default=str)[:2000],
                "```",
            ])
    except Exception:
        pass

    return "\n".join(lines)


def render_logs() -> str:
    """Render the Logs tab."""
    state = _get_state()
    log_lines = state.get("log_lines", [])
    if not log_lines:
        return "Waiting for first cycle..."
    return "\n".join(log_lines[-200:])


def trigger_manual_cycle():
    """Manually trigger a forge cycle (for debugging)."""
    state = _get_state()
    if state.get("status") == "running":
        return "Cycle already running, please wait..."

    iteration = state.get("iteration", 0) + 1
    _log(f"MANUAL TRIGGER: Starting cycle {iteration}")

    def _run():
        try:
            run_forge_cycle(iteration)
        except Exception as e:
            _log(f"Manual cycle failed: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return f"Cycle {iteration} triggered! Check logs for progress."


# ============================================================================
# BUILD GRADIO APP
# ============================================================================

def build_app() -> gr.Blocks:
    """Build the Gradio dashboard."""
    with gr.Blocks(
        title="Nomos42 Forge Orchestrator",
        theme=gr.themes.Monochrome(),
    ) as app:
        gr.Markdown("# 🏭 Nomos42 Forge Orchestrator\n*11 Department Karpathy Loops + Guardian Cross-Pollination*")

        with gr.Tabs():
            # Tab 1: Overview
            with gr.TabItem("Overview"):
                overview_md = gr.Markdown("Loading...")
                overview_btn = gr.Button("Refresh", variant="secondary")
                overview_btn.click(fn=render_overview, outputs=overview_md)

            # Tab 2: Department Detail
            with gr.TabItem("Department Detail"):
                dept_dropdown = gr.Dropdown(
                    choices=[
                        "D1 - RESEARCH", "D2 - ENGINEERING", "D3 - EVOLUTION",
                        "D4 - BETTING", "D5 - EVALUATION", "D6 - INFRA",
                        "D7 - POLITICAL", "D8 - CREATIVE", "D9 - COMMUNICATION",
                        "D10 - BUSINESS", "D11 - FINANCE", "TRADING FLOOR",
                    ],
                    value="D3 - EVOLUTION",
                    label="Select Department",
                )
                detail_md = gr.Markdown("Select a department and click Refresh")
                detail_btn = gr.Button("Refresh", variant="secondary")
                detail_btn.click(fn=render_department_detail, inputs=dept_dropdown, outputs=detail_md)
                dept_dropdown.change(fn=render_department_detail, inputs=dept_dropdown, outputs=detail_md)

            # Tab 3: Guardian Report
            with gr.TabItem("Guardian Report"):
                guardian_md = gr.Markdown("Loading...")
                guardian_btn = gr.Button("Refresh", variant="secondary")
                guardian_btn.click(fn=render_guardian_report, outputs=guardian_md)

            # Tab 4: Wins
            with gr.TabItem("Wins"):
                wins_md = gr.Markdown("Loading...")
                wins_btn = gr.Button("Refresh", variant="secondary")
                wins_btn.click(fn=render_wins, outputs=wins_md)

            # Tab 5: Logs
            with gr.TabItem("Logs"):
                logs_md = gr.Textbox(
                    label="Live Logs",
                    lines=30,
                    max_lines=50,
                    interactive=False,
                )
                logs_btn = gr.Button("Refresh Logs", variant="secondary")
                logs_btn.click(fn=render_logs, outputs=logs_md)

            # Tab 6: Manual Controls
            with gr.TabItem("Controls"):
                gr.Markdown("## Manual Controls")
                trigger_btn = gr.Button("Trigger Manual Cycle", variant="primary")
                trigger_output = gr.Textbox(label="Result", interactive=False)
                trigger_btn.click(fn=trigger_manual_cycle, outputs=trigger_output)

                gr.Markdown("""
### Configuration
- **Loop interval:** 15 minutes
- **Departments:** 11 + Trading Floor
- **Guardian:** Runs after all departments
- **Git sync:** After each cycle (requires GH_TOKEN secret)

### Secrets Required
- `GH_TOKEN` - GitHub personal access token for repo clone/push
- `TELEGRAM_BOT_TOKEN` - (optional) for Telegram notifications

### Architecture
Each department runs a simplified Karpathy loop:
1. **Measure** the primary metric
2. **Analyze** for issues and improvements
3. **Record** to karpathy-output.json

The Guardian then:
1. Reads all 11 department outputs
2. Detects cross-department issues
3. Builds priority action queue
4. Tracks strategy eliminations
5. Cross-pollinates wins between departments
6. Computes overall health score (0-100)
                """)

        # Auto-refresh overview on load
        app.load(fn=render_overview, outputs=overview_md)

    return app


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Start background loop in a daemon thread
    loop_thread = threading.Thread(target=background_loop, daemon=True)
    loop_thread.start()

    # Launch Gradio
    app = build_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )
