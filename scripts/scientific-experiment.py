#!/usr/bin/env python3
"""
SCIENTIFIC EXPERIMENT ENGINE v1.0 — NBA + Political Prediction Analysis
========================================================================
Complete scientific evaluation of all prediction and trading data.

Part 1: EVALUATION — Brier, log-loss, calibration, AUC-ROC, progression
Part 2: STRATEGY BACKTESTING — regression, optimal thresholds, Kelly, Sharpe
Part 3: OUTPUT — JSON + Markdown reports

Usage:
  python3 scripts/scientific-experiment.py --project nba
  python3 scripts/scientific-experiment.py --project political
  python3 scripts/scientific-experiment.py --project all
  python3 scripts/scientific-experiment.py --project nba --verbose
"""

import json
import math
import argparse
import os
import sys
import urllib.request
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

# ═══════════════════════════════════════════════════════════════════════════════
# NUMPY / SCIPY (graceful fallback)
# ═══════════════════════════════════════════════════════════════════════════════
try:
    import numpy as np
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("WARNING: numpy/scipy not found — using pure Python (limited stats)")

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════
ROOT = Path("/home/termius/mon-ipad")
DATA_DIR = ROOT / "data" / "arena"
PREDICTIONS_DIR = DATA_DIR / "predictions-v5"
BACKTEST_DIR = DATA_DIR / "backtest-results"
POLITICAL_DIR = DATA_DIR / "political"
ODDS_DIR = ROOT / "data" / "nba-agent"
OUTPUT_DIR = ROOT / "data" / "experiments"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Team abbreviation normalization
TEAM_MAP = {
    "GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS",
    "WSH": "WAS", "UTAH": "UTA", "PHL": "PHI",
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}


def normalize_team(abbr: str) -> str:
    return TEAM_MAP.get(abbr, abbr)


# ═══════════════════════════════════════════════════════════════════════════════
# PART 0: DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_predictions() -> Dict[str, dict]:
    """Load all prediction files from predictions-v5/."""
    all_preds = {}
    if not PREDICTIONS_DIR.exists():
        print(f"  WARNING: {PREDICTIONS_DIR} not found")
        return all_preds

    for f in sorted(PREDICTIONS_DIR.glob("predictions-*.json")):
        try:
            data = json.loads(f.read_text())
            date_str = f.stem.replace("predictions-", "")
            if data:  # skip empty
                all_preds[date_str] = data
        except Exception as e:
            print(f"  WARNING: Failed to load {f.name}: {e}")
    return all_preds


def load_trading_floors() -> Dict[str, dict]:
    """Load all trading floor v5 date files."""
    floors = {}
    for f in sorted(DATA_DIR.glob("trading-floor-v5-202*.json")):
        try:
            data = json.loads(f.read_text())
            date_str = data.get("date", f.stem.split("-")[-1])
            floors[date_str] = data
        except Exception as e:
            print(f"  WARNING: Failed to load {f.name}: {e}")
    return floors


def load_backtest_results() -> List[dict]:
    """Load all backtest result files."""
    results = []
    if not BACKTEST_DIR.exists():
        return results
    for f in sorted(BACKTEST_DIR.glob("backtest-*.json")):
        try:
            data = json.loads(f.read_text())
            data["_filename"] = f.name
            results.append(data)
        except Exception as e:
            print(f"  WARNING: Failed to load {f.name}: {e}")
    return results


def load_season_memory() -> dict:
    """Load season memory with historical trader bets."""
    smf = DATA_DIR / "season-memory.json"
    if smf.exists():
        return json.loads(smf.read_text())
    return {}


def load_odds_data() -> Dict[str, dict]:
    """Load odds data from nba-agent for game result resolution."""
    odds = {}
    odds_file = ODDS_DIR / "odds-latest.json"
    if odds_file.exists():
        try:
            data = json.loads(odds_file.read_text())
            if isinstance(data, list):
                for game in data:
                    home = normalize_team(game.get("home_team", ""))
                    away = normalize_team(game.get("away_team", ""))
                    ct = game.get("commence_time", "")
                    date_str = ct[:10] if ct else ""
                    if home and away and date_str:
                        key = f"{date_str}_{away}@{home}"
                        odds[key] = game
        except Exception as e:
            print(f"  WARNING: Failed to load odds: {e}")
    return odds


def load_political_floors() -> Dict[str, dict]:
    """Load all political trading floor files."""
    floors = {}
    if not POLITICAL_DIR.exists():
        return floors
    for f in sorted(POLITICAL_DIR.glob("political-trading-floor-202*.json")):
        try:
            data = json.loads(f.read_text())
            date_str = data.get("meta", {}).get("date", f.stem.split("-")[-1])
            floors[date_str] = data
        except Exception as e:
            print(f"  WARNING: Failed to load {f.name}: {e}")
    return floors


def fetch_espn_scores(date_str: str) -> List[dict]:
    """Fetch actual NBA scores from ESPN API."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    espn_date = dt.strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={espn_date}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            results = []
            for event in data.get("events", []):
                comps = event.get("competitions", [{}])
                if not comps:
                    continue
                comp = comps[0]
                teams_data = comp.get("competitors", [])
                if len(teams_data) != 2:
                    continue
                home_data = away_data = None
                for t in teams_data:
                    if t.get("homeAway") == "home":
                        home_data = t
                    else:
                        away_data = t
                if not home_data or not away_data:
                    continue
                home_abbr = normalize_team(home_data.get("team", {}).get("abbreviation", ""))
                away_abbr = normalize_team(away_data.get("team", {}).get("abbreviation", ""))
                home_score = int(home_data.get("score", "0") or "0")
                away_score = int(away_data.get("score", "0") or "0")
                status = comp.get("status", {}).get("type", {}).get("name", "")
                if home_score > 0 and away_score > 0 and status == "STATUS_FINAL":
                    results.append({
                        "home": home_abbr, "away": away_abbr,
                        "home_score": home_score, "away_score": away_score,
                        "home_win": home_score > away_score,
                        "total_pts": home_score + away_score,
                        "margin": home_score - away_score,
                    })
            return results
    except Exception as e:
        print(f"  ESPN fetch failed for {date_str}: {e}")
    return []


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1: EVALUATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def brier_score(prob: float, outcome: int) -> float:
    """Brier score for a single prediction. outcome=1 if event happened."""
    return (prob - outcome) ** 2


def log_loss_single(prob: float, outcome: int, eps: float = 1e-15) -> float:
    """Log loss for a single prediction."""
    p = max(eps, min(1 - eps, prob))
    if outcome == 1:
        return -math.log(p)
    else:
        return -math.log(1 - p)


def compute_calibration_buckets(predictions: List[Tuple[float, int]], n_buckets: int = 10) -> List[dict]:
    """
    Compute calibration / reliability diagram buckets.
    predictions = list of (predicted_prob, actual_outcome)
    """
    if not predictions:
        return []

    buckets = defaultdict(lambda: {"sum_pred": 0.0, "sum_actual": 0, "count": 0})
    for prob, outcome in predictions:
        bucket_idx = min(int(prob * n_buckets), n_buckets - 1)
        b = buckets[bucket_idx]
        b["sum_pred"] += prob
        b["sum_actual"] += outcome
        b["count"] += 1

    result = []
    for i in range(n_buckets):
        b = buckets[i]
        if b["count"] > 0:
            avg_pred = b["sum_pred"] / b["count"]
            avg_actual = b["sum_actual"] / b["count"]
            result.append({
                "bucket": i,
                "range": f"{i/n_buckets:.1f}-{(i+1)/n_buckets:.1f}",
                "avg_predicted": round(avg_pred, 4),
                "avg_actual": round(avg_actual, 4),
                "count": b["count"],
                "calibration_error": round(abs(avg_pred - avg_actual), 4),
            })
        else:
            result.append({
                "bucket": i,
                "range": f"{i/n_buckets:.1f}-{(i+1)/n_buckets:.1f}",
                "avg_predicted": None,
                "avg_actual": None,
                "count": 0,
                "calibration_error": None,
            })
    return result


def expected_calibration_error(predictions: List[Tuple[float, int]], n_buckets: int = 10) -> float:
    """ECE: weighted average of per-bucket calibration error."""
    buckets = compute_calibration_buckets(predictions, n_buckets)
    total = sum(b["count"] for b in buckets)
    if total == 0:
        return 0.0
    ece = 0.0
    for b in buckets:
        if b["count"] > 0 and b["calibration_error"] is not None:
            ece += (b["count"] / total) * b["calibration_error"]
    return ece


def compute_auc_roc(predictions: List[Tuple[float, int]]) -> float:
    """
    AUC-ROC via the Wilcoxon-Mann-Whitney statistic.
    predictions = list of (predicted_prob, actual_outcome)
    """
    if not predictions:
        return 0.5

    pos = [p for p, o in predictions if o == 1]
    neg = [p for p, o in predictions if o == 0]

    if not pos or not neg:
        return 0.5

    # Mann-Whitney U
    concordant = 0
    tied = 0
    for p in pos:
        for n in neg:
            if p > n:
                concordant += 1
            elif p == n:
                tied += 0.5

    auc = (concordant + tied) / (len(pos) * len(neg))
    return auc


def bootstrap_ci(values: List[float], n_bootstrap: int = 1000, ci: float = 0.95) -> Tuple[float, float, float]:
    """Bootstrap confidence interval. Returns (mean, lower, upper)."""
    if not values:
        return (0.0, 0.0, 0.0)

    if HAS_SCIPY:
        arr = np.array(values)
        n = len(arr)
        means = []
        for _ in range(n_bootstrap):
            sample = arr[np.random.randint(0, n, size=n)]
            means.append(float(np.mean(sample)))
        means.sort()
        alpha = (1 - ci) / 2
        lower = means[int(alpha * n_bootstrap)]
        upper = means[int((1 - alpha) * n_bootstrap)]
        return (float(np.mean(arr)), lower, upper)
    else:
        import random
        n = len(values)
        mean_val = sum(values) / n
        means = []
        for _ in range(n_bootstrap):
            sample = [random.choice(values) for _ in range(n)]
            means.append(sum(sample) / n)
        means.sort()
        alpha = (1 - ci) / 2
        lower = means[int(alpha * n_bootstrap)]
        upper = means[int((1 - alpha) * n_bootstrap)]
        return (mean_val, lower, upper)


def extract_agent_predictions(predictions_by_date: Dict[str, dict], actual_results: Dict[str, dict]) -> Dict[str, List[dict]]:
    """
    Extract per-agent ML predictions matched against actual results.
    Returns: {agent_id: [{date, game_key, prob_home, actual_home_win, confidence, edge}, ...]}
    """
    agent_preds = defaultdict(list)

    for date_str, pred_data in sorted(predictions_by_date.items()):
        # Get actual results for this date
        date_results = actual_results.get(date_str, {})
        if not date_results:
            continue

        for agent_id, agent_games in pred_data.items():
            if not isinstance(agent_games, dict):
                continue

            for game_key, game_pred in agent_games.items():
                if not isinstance(game_pred, dict):
                    continue

                # Parse game key: "2026-04-05_TOR@BOS"
                parts = game_key.split("_", 1)
                if len(parts) != 2:
                    continue
                game_date = parts[0]
                matchup = parts[1]  # "TOR@BOS"

                if "@" not in matchup:
                    continue
                away, home = matchup.split("@")

                # Find actual result
                actual = date_results.get(f"{away}@{home}")
                if actual is None:
                    continue

                # Extract ML prediction
                ml = game_pred.get("ml_fg", {})
                if not ml or not isinstance(ml, dict):
                    continue

                direction = ml.get("direction", "")
                confidence = ml.get("confidence", 0.5)
                edge = ml.get("edge_pct", 0.0)

                # Convert to probability of home win
                if direction == "home":
                    prob_home = confidence
                elif direction == "away":
                    prob_home = 1.0 - confidence
                else:
                    continue

                agent_preds[agent_id].append({
                    "date": game_date,
                    "game_key": game_key,
                    "prob_home": prob_home,
                    "actual_home_win": 1 if actual["home_win"] else 0,
                    "confidence": confidence,
                    "edge_pct": edge,
                    "direction": direction,
                })

    return dict(agent_preds)


def extract_consensus_predictions(trading_floors: Dict[str, dict], actual_results: Dict[str, dict]) -> List[dict]:
    """
    Extract consensus predictions from trading floor data matched against actual results.
    """
    consensus_preds = []

    for date_str, tf_data in sorted(trading_floors.items()):
        consensus = tf_data.get("consensus", {})
        date_results = actual_results.get(date_str, {})
        if not date_results or not consensus:
            continue

        for game_key, game_consensus in consensus.items():
            parts = game_key.split("_", 1)
            if len(parts) != 2:
                continue
            matchup = parts[1]
            if "@" not in matchup:
                continue
            away, home = matchup.split("@")

            actual = date_results.get(f"{away}@{home}")
            if actual is None:
                continue

            # ML consensus
            ml_con = game_consensus.get("consensus_ml", {})
            spread_con = game_consensus.get("consensus_spread", {})
            total_con = game_consensus.get("consensus_total", {})

            if ml_con:
                ml_dir = ml_con.get("direction", "")
                ml_conf = ml_con.get("confidence", 0.5)
                ml_agree = ml_con.get("agreement_pct", 0.5)
                if ml_dir == "home":
                    prob_home = ml_conf
                elif ml_dir == "away":
                    prob_home = 1.0 - ml_conf
                else:
                    prob_home = 0.5

                consensus_preds.append({
                    "date": date_str,
                    "game_key": game_key,
                    "category": "ml_fg",
                    "direction": ml_dir,
                    "prob_home": prob_home,
                    "confidence": ml_conf,
                    "agreement": ml_agree,
                    "actual_home_win": 1 if actual["home_win"] else 0,
                    "actual_total_pts": actual.get("total_pts"),
                    "actual_margin": actual.get("margin"),
                    "edge_pct": game_consensus.get("avg_edge_pct", 0.0),
                    "num_agents": game_consensus.get("num_agents", 0),
                })

            # Total consensus
            if total_con and actual.get("total_pts") is not None:
                total_dir = total_con.get("direction", "")
                total_conf = total_con.get("confidence", 0.5)
                total_agree = total_con.get("agreement_pct", 0.5)
                # We cannot fully resolve totals without the line, but we can track direction accuracy
                consensus_preds.append({
                    "date": date_str,
                    "game_key": game_key,
                    "category": "total_fg",
                    "direction": total_dir,
                    "confidence": total_conf,
                    "agreement": total_agree,
                    "actual_total_pts": actual.get("total_pts"),
                    "edge_pct": game_consensus.get("avg_edge_pct", 0.0),
                    "num_agents": game_consensus.get("num_agents", 0),
                })

    return consensus_preds


def evaluate_agent_predictions(agent_preds: Dict[str, List[dict]]) -> Dict[str, dict]:
    """Compute per-agent metrics: Brier, log-loss, calibration, AUC-ROC."""
    results = {}

    for agent_id, preds in agent_preds.items():
        if len(preds) < 2:
            continue

        brier_scores = []
        log_losses = []
        prob_outcome_pairs = []

        for p in preds:
            prob = p["prob_home"]
            outcome = p["actual_home_win"]
            brier_scores.append(brier_score(prob, outcome))
            log_losses.append(log_loss_single(prob, outcome))
            prob_outcome_pairs.append((prob, outcome))

        avg_brier = sum(brier_scores) / len(brier_scores)
        avg_logloss = sum(log_losses) / len(log_losses)
        auc = compute_auc_roc(prob_outcome_pairs)
        ece = expected_calibration_error(prob_outcome_pairs)
        calibration = compute_calibration_buckets(prob_outcome_pairs)

        # Bootstrap CI on Brier
        brier_mean, brier_lo, brier_hi = bootstrap_ci(brier_scores, n_bootstrap=500)

        # Win rate (directional accuracy)
        correct = sum(1 for p in preds if
                      (p["direction"] == "home" and p["actual_home_win"] == 1) or
                      (p["direction"] == "away" and p["actual_home_win"] == 0))
        accuracy = correct / len(preds)

        # Per-date progression
        date_briers = defaultdict(list)
        for p, bs in zip(preds, brier_scores):
            date_briers[p["date"]].append(bs)
        progression = []
        for d in sorted(date_briers.keys()):
            progression.append({
                "date": d,
                "avg_brier": round(sum(date_briers[d]) / len(date_briers[d]), 5),
                "n_games": len(date_briers[d]),
            })

        results[agent_id] = {
            "agent_id": agent_id,
            "n_predictions": len(preds),
            "brier_score": round(avg_brier, 5),
            "brier_ci_95": [round(brier_lo, 5), round(brier_hi, 5)],
            "log_loss": round(avg_logloss, 5),
            "auc_roc": round(auc, 4),
            "ece": round(ece, 4),
            "accuracy": round(accuracy, 4),
            "calibration_buckets": calibration,
            "progression": progression,
        }

    return results


def evaluate_consensus(consensus_preds: List[dict]) -> dict:
    """Evaluate consensus ML predictions."""
    ml_preds = [p for p in consensus_preds if p.get("category") == "ml_fg"]
    if not ml_preds:
        return {"error": "no ML consensus predictions found"}

    brier_scores = []
    log_losses = []
    prob_outcome_pairs = []

    for p in ml_preds:
        prob = p.get("prob_home", 0.5)
        outcome = p["actual_home_win"]
        brier_scores.append(brier_score(prob, outcome))
        log_losses.append(log_loss_single(prob, outcome))
        prob_outcome_pairs.append((prob, outcome))

    avg_brier = sum(brier_scores) / len(brier_scores)
    avg_logloss = sum(log_losses) / len(log_losses)
    auc = compute_auc_roc(prob_outcome_pairs)
    ece = expected_calibration_error(prob_outcome_pairs)
    calibration = compute_calibration_buckets(prob_outcome_pairs)
    brier_mean, brier_lo, brier_hi = bootstrap_ci(brier_scores, n_bootstrap=500)

    # Accuracy
    correct = sum(1 for p in ml_preds if
                  (p["direction"] == "home" and p["actual_home_win"] == 1) or
                  (p["direction"] == "away" and p["actual_home_win"] == 0))
    accuracy = correct / len(ml_preds)

    # Agreement analysis
    high_agree = [p for p in ml_preds if p.get("agreement", 0) >= 0.8]
    low_agree = [p for p in ml_preds if p.get("agreement", 0) < 0.6]

    high_agree_acc = 0.0
    if high_agree:
        h_correct = sum(1 for p in high_agree if
                        (p["direction"] == "home" and p["actual_home_win"] == 1) or
                        (p["direction"] == "away" and p["actual_home_win"] == 0))
        high_agree_acc = h_correct / len(high_agree)

    low_agree_acc = 0.0
    if low_agree:
        l_correct = sum(1 for p in low_agree if
                        (p["direction"] == "home" and p["actual_home_win"] == 1) or
                        (p["direction"] == "away" and p["actual_home_win"] == 0))
        low_agree_acc = l_correct / len(low_agree)

    # Progression
    date_briers = defaultdict(list)
    for p, bs in zip(ml_preds, brier_scores):
        date_briers[p["date"]].append(bs)
    progression = []
    for d in sorted(date_briers.keys()):
        vals = date_briers[d]
        progression.append({
            "date": d,
            "avg_brier": round(sum(vals) / len(vals), 5),
            "n_games": len(vals),
        })

    return {
        "n_predictions": len(ml_preds),
        "brier_score": round(avg_brier, 5),
        "brier_ci_95": [round(brier_lo, 5), round(brier_hi, 5)],
        "log_loss": round(avg_logloss, 5),
        "auc_roc": round(auc, 4),
        "ece": round(ece, 4),
        "accuracy": round(accuracy, 4),
        "calibration_buckets": calibration,
        "progression": progression,
        "agreement_analysis": {
            "high_agreement_games": len(high_agree),
            "high_agreement_accuracy": round(high_agree_acc, 4),
            "low_agreement_games": len(low_agree),
            "low_agreement_accuracy": round(low_agree_acc, 4),
        },
    }


def statistical_significance_test(agent_results: Dict[str, dict], agent_preds: Dict[str, List[dict]]) -> List[dict]:
    """
    Bootstrap paired test: is the difference between two models' Brier scores significant?
    Compare all pairs of top agents.
    """
    comparisons = []
    agents = sorted(agent_results.keys(), key=lambda a: agent_results[a]["brier_score"])

    # Only compare top 10 agents to keep it tractable
    top_agents = agents[:10]

    for i in range(len(top_agents)):
        for j in range(i + 1, len(top_agents)):
            a1, a2 = top_agents[i], top_agents[j]
            preds1 = {p["game_key"]: p for p in agent_preds[a1]}
            preds2 = {p["game_key"]: p for p in agent_preds[a2]}

            # Find common games
            common = set(preds1.keys()) & set(preds2.keys())
            if len(common) < 5:
                continue

            diffs = []
            for gk in common:
                p1 = preds1[gk]
                p2 = preds2[gk]
                bs1 = brier_score(p1["prob_home"], p1["actual_home_win"])
                bs2 = brier_score(p2["prob_home"], p2["actual_home_win"])
                diffs.append(bs1 - bs2)  # negative = agent1 is better

            if not diffs:
                continue

            mean_diff = sum(diffs) / len(diffs)

            # Bootstrap test
            if HAS_SCIPY:
                arr = np.array(diffs)
                n = len(arr)
                boot_means = []
                for _ in range(2000):
                    sample = arr[np.random.randint(0, n, size=n)]
                    boot_means.append(float(np.mean(sample)))
                boot_means.sort()
                # p-value: proportion of bootstrap samples where diff crosses 0
                n_positive = sum(1 for m in boot_means if m > 0)
                n_negative = sum(1 for m in boot_means if m < 0)
                p_value = 2 * min(n_positive, n_negative) / len(boot_means)  # two-sided
                ci_lo = boot_means[int(0.025 * len(boot_means))]
                ci_hi = boot_means[int(0.975 * len(boot_means))]
            else:
                import random
                n = len(diffs)
                boot_means = []
                for _ in range(2000):
                    sample = [random.choice(diffs) for _ in range(n)]
                    boot_means.append(sum(sample) / n)
                boot_means.sort()
                n_positive = sum(1 for m in boot_means if m > 0)
                n_negative = sum(1 for m in boot_means if m < 0)
                p_value = 2 * min(n_positive, n_negative) / len(boot_means)
                ci_lo = boot_means[int(0.025 * len(boot_means))]
                ci_hi = boot_means[int(0.975 * len(boot_means))]

            comparisons.append({
                "agent_1": a1,
                "agent_2": a2,
                "brier_1": agent_results[a1]["brier_score"],
                "brier_2": agent_results[a2]["brier_score"],
                "mean_diff": round(mean_diff, 5),
                "ci_95": [round(ci_lo, 5), round(ci_hi, 5)],
                "p_value": round(p_value, 4),
                "significant_at_005": p_value < 0.05,
                "common_games": len(common),
                "better_agent": a1 if mean_diff < 0 else a2,
            })

    return comparisons


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2: STRATEGY BACKTESTING
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_backtest_strategies(backtest_results: List[dict]) -> dict:
    """Analyze all backtest results: find optimal strategy, compute risk metrics."""
    if not backtest_results:
        return {"error": "no backtest results found"}

    # Use the latest backtest
    latest = backtest_results[-1]
    strategies = latest.get("strategies", {})
    model_brier = latest.get("model_brier", None)
    games_total = latest.get("games_total", 0)

    if not strategies:
        return {"error": "no strategies in latest backtest"}

    # Parse all strategies
    strategy_list = []
    for sid, s in strategies.items():
        strategy_list.append({
            "id": sid,
            "name": s.get("name", sid),
            "total_bets": s.get("total_bets", 0),
            "wins": s.get("wins", 0),
            "win_rate": s.get("win_rate", 0.0),
            "total_pnl": s.get("total_pnl", 0.0),
            "roi": s.get("roi", 0.0),
            "final_bankroll": s.get("final_bankroll", 100.0),
            "max_drawdown": s.get("max_drawdown", 0.0),
            "sharpe": s.get("sharpe", 0.0),
        })

    # Sort by different criteria
    by_sharpe = sorted([s for s in strategy_list if s["total_bets"] >= 5],
                       key=lambda x: x["sharpe"], reverse=True)
    by_roi = sorted([s for s in strategy_list if s["total_bets"] >= 5],
                    key=lambda x: x["roi"], reverse=True)
    by_pnl = sorted([s for s in strategy_list if s["total_bets"] >= 5],
                    key=lambda x: x["total_pnl"], reverse=True)
    by_calmar = sorted([s for s in strategy_list if s["total_bets"] >= 5 and s["max_drawdown"] > 0],
                       key=lambda x: x["roi"] / max(x["max_drawdown"], 0.001), reverse=True)

    # Compute Calmar ratio for top strategies
    for s in strategy_list:
        if s["max_drawdown"] > 0:
            s["calmar_ratio"] = round(s["roi"] / (s["max_drawdown"] * 100), 4)
        else:
            s["calmar_ratio"] = 0.0

    # Group by category
    kelly_strats = [s for s in strategy_list if s["id"].startswith("kelly_")]
    fixed_strats = [s for s in strategy_list if s["id"].startswith("fixed_")]
    value_strats = [s for s in strategy_list if s["id"].startswith("value_")]
    spec_strats = [s for s in strategy_list if s["id"].startswith("spec_")]

    # Optimal Kelly fraction analysis
    kelly_analysis = []
    for s in kelly_strats:
        parts = s["id"].replace("kelly_", "").split("_")
        if len(parts) == 2:
            try:
                fraction = float(parts[0])
                min_edge = float(parts[1])
                kelly_analysis.append({
                    "fraction": fraction,
                    "min_edge_pct": min_edge * 100,
                    "roi": s["roi"],
                    "sharpe": s["sharpe"],
                    "max_drawdown": s["max_drawdown"],
                    "total_bets": s["total_bets"],
                    "calmar": s.get("calmar_ratio", 0.0),
                })
            except ValueError:
                pass

    return {
        "model_brier": model_brier,
        "games_total": games_total,
        "total_strategies_tested": len(strategy_list),
        "best_by_sharpe": by_sharpe[:5] if by_sharpe else [],
        "best_by_roi": by_roi[:5] if by_roi else [],
        "best_by_pnl": by_pnl[:5] if by_pnl else [],
        "best_by_calmar": by_calmar[:5] if by_calmar else [],
        "kelly_fraction_analysis": sorted(kelly_analysis, key=lambda x: x["sharpe"], reverse=True),
        "category_summary": {
            "kelly_variants": len(kelly_strats),
            "fixed_bet_variants": len(fixed_strats),
            "value_hunter_variants": len(value_strats),
            "specialist_variants": len(spec_strats),
        },
        "all_strategies": sorted(strategy_list, key=lambda x: x["sharpe"], reverse=True),
    }


def run_regression_analysis(season_memory: dict) -> dict:
    """
    Run linear regression on historical bet data: PnL ~ confidence + edge + odds.
    Uses season memory trader data.
    """
    if not HAS_SCIPY:
        return {"error": "scipy required for regression analysis"}

    trader_memories = season_memory.get("trader_memories", {})
    if not trader_memories:
        return {"error": "no trader memories found in season-memory.json"}

    all_bets = []
    for trader_id, bets in trader_memories.items():
        if not isinstance(bets, list):
            continue
        for bet in bets:
            if not isinstance(bet, dict):
                continue
            profit = bet.get("profit", 0)
            edge = bet.get("edge_pct", 0)
            odds = bet.get("odds", 0)
            kelly_f = bet.get("kelly_fraction", 0)
            model_prob = bet.get("model_prob", 0)
            category = bet.get("category", "unknown")
            outcome_str = bet.get("outcome", "")
            won = 1 if outcome_str == "Win" else 0

            if odds > 0 and model_prob > 0:
                all_bets.append({
                    "trader": trader_id,
                    "category": category,
                    "profit": profit,
                    "edge_pct": edge,
                    "odds": odds,
                    "kelly_fraction": kelly_f,
                    "model_prob": model_prob,
                    "won": won,
                    "confidence": model_prob,  # proxy
                })

    if len(all_bets) < 10:
        return {"error": f"only {len(all_bets)} bets found, need >= 10 for regression"}

    # Overall regression: PnL ~ confidence + edge + odds
    y = np.array([b["profit"] for b in all_bets])
    X = np.array([[b["confidence"], b["edge_pct"], b["odds"]] for b in all_bets])

    # Add intercept
    X_with_const = np.column_stack([np.ones(len(X)), X])

    # OLS via normal equations
    try:
        beta = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
        y_pred = X_with_const @ beta
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # Standard errors and p-values
        n = len(y)
        k = X_with_const.shape[1]
        mse = ss_res / max(n - k, 1)
        try:
            var_beta = mse * np.linalg.inv(X_with_const.T @ X_with_const)
            se = np.sqrt(np.diag(var_beta))
            t_stats = beta / np.where(se > 0, se, 1e-10)
            p_values = [float(2 * (1 - scipy_stats.t.cdf(abs(t), df=max(n - k, 1)))) for t in t_stats]
        except np.linalg.LinAlgError:
            se = np.zeros(k)
            t_stats = np.zeros(k)
            p_values = [1.0] * k

        overall_regression = {
            "n_observations": n,
            "r_squared": round(float(r_squared), 4),
            "coefficients": {
                "intercept": {"beta": round(float(beta[0]), 6), "se": round(float(se[0]), 6), "p_value": round(p_values[0], 4)},
                "confidence": {"beta": round(float(beta[1]), 6), "se": round(float(se[1]), 6), "p_value": round(p_values[1], 4)},
                "edge_pct": {"beta": round(float(beta[2]), 6), "se": round(float(se[2]), 6), "p_value": round(p_values[2], 4)},
                "odds": {"beta": round(float(beta[3]), 6), "se": round(float(se[3]), 6), "p_value": round(p_values[3], 4)},
            },
            "interpretation": {},
        }

        # Interpret coefficients
        for name, idx in [("confidence", 1), ("edge_pct", 2), ("odds", 3)]:
            coef = overall_regression["coefficients"][name]
            sig = "***" if coef["p_value"] < 0.001 else "**" if coef["p_value"] < 0.01 else "*" if coef["p_value"] < 0.05 else "ns"
            direction = "positive" if coef["beta"] > 0 else "negative"
            overall_regression["interpretation"][name] = f"{direction} effect ({sig})"

    except Exception as e:
        overall_regression = {"error": f"regression failed: {e}"}

    # Per-category analysis
    category_bets = defaultdict(list)
    for b in all_bets:
        category_bets[b["category"]].append(b)

    category_results = {}
    for cat, bets in category_bets.items():
        if len(bets) < 5:
            continue

        wins = sum(b["won"] for b in bets)
        total_profit = sum(b["profit"] for b in bets)
        avg_edge = sum(b["edge_pct"] for b in bets) / len(bets)
        avg_odds = sum(b["odds"] for b in bets) / len(bets)

        category_results[cat] = {
            "n_bets": len(bets),
            "wins": wins,
            "win_rate": round(wins / len(bets), 4),
            "total_profit": round(total_profit, 4),
            "avg_profit": round(total_profit / len(bets), 4),
            "avg_edge_pct": round(avg_edge, 2),
            "avg_odds": round(avg_odds, 3),
            "profitable": total_profit > 0,
        }

    return {
        "total_bets_analyzed": len(all_bets),
        "overall_regression": overall_regression,
        "per_category": dict(sorted(category_results.items(),
                                     key=lambda x: x[1]["total_profit"], reverse=True)),
        "traders_analyzed": list(trader_memories.keys()),
    }


def optimal_threshold_search(season_memory: dict) -> dict:
    """
    Find optimal thresholds for confidence, edge, and stake sizing.
    Walk-forward: train on first 70%, validate on last 30%.
    """
    trader_memories = season_memory.get("trader_memories", {})
    all_bets = []
    for trader_id, bets in trader_memories.items():
        if not isinstance(bets, list):
            continue
        for bet in bets:
            if not isinstance(bet, dict):
                continue
            if bet.get("odds", 0) > 0:
                all_bets.append(bet)

    if len(all_bets) < 20:
        return {"error": f"only {len(all_bets)} bets, need >= 20"}

    # Sort by date for walk-forward
    all_bets.sort(key=lambda b: b.get("date", ""))
    split_idx = int(len(all_bets) * 0.7)
    train_bets = all_bets[:split_idx]
    test_bets = all_bets[split_idx:]

    # Grid search on training set
    best_config = None
    best_train_roi = -999

    confidence_thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    edge_thresholds = [0.0, 2.0, 5.0, 8.0, 10.0, 15.0]
    kelly_fractions = [0.05, 0.1, 0.25, 0.5]

    grid_results = []

    for min_conf in confidence_thresholds:
        for min_edge in edge_thresholds:
            for kelly_f in kelly_fractions:
                # Simulate on training set
                bankroll = 100.0
                peak = 100.0
                max_dd = 0.0
                total_pnl = 0.0
                n_bets = 0
                daily_returns = defaultdict(float)

                for bet in train_bets:
                    prob = bet.get("model_prob", 0.5)
                    edge = bet.get("edge_pct", 0)
                    odds = bet.get("odds", 1.0)
                    won = bet.get("outcome", "") == "Win"
                    date_str = bet.get("date", "")

                    if prob < min_conf or edge < min_edge:
                        continue

                    # Kelly sizing
                    p = prob
                    b = odds - 1  # net decimal odds
                    if b <= 0:
                        continue
                    q = 1 - p
                    kelly_stake = max(0, (p * b - q) / b) * kelly_f
                    kelly_stake = min(kelly_stake, 0.03)  # max 3% per bet (realistic constraint)
                    stake = bankroll * kelly_stake

                    if stake <= 0 or stake < 0.01:
                        continue

                    n_bets += 1
                    if won:
                        profit = stake * (odds - 1)
                    else:
                        profit = -stake

                    bankroll += profit
                    # Cap bankroll at $10K for realistic simulation
                    bankroll = min(bankroll, 10000.0)
                    total_pnl += profit
                    daily_returns[date_str] += profit

                    peak = max(peak, bankroll)
                    dd = (peak - bankroll) / peak if peak > 0 else 0
                    max_dd = max(max_dd, dd)

                if n_bets >= 5:
                    # ROI = (final - initial) / initial * 100
                    roi = ((bankroll - 100.0) / 100.0) * 100

                    # Sharpe
                    returns = list(daily_returns.values())
                    if len(returns) >= 2:
                        mean_r = sum(returns) / len(returns)
                        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
                        std_r = math.sqrt(var_r) if var_r > 0 else 0.001
                        sharpe = (mean_r / std_r) * math.sqrt(180)
                    else:
                        sharpe = 0.0

                    config = {
                        "min_confidence": min_conf,
                        "min_edge_pct": min_edge,
                        "kelly_fraction": kelly_f,
                        "train_bets": n_bets,
                        "train_roi": round(roi, 2),
                        "train_pnl": round(total_pnl, 2),
                        "train_bankroll": round(bankroll, 2),
                        "train_max_dd": round(max_dd, 4),
                        "train_sharpe": round(sharpe, 3),
                    }
                    grid_results.append(config)

                    if roi > best_train_roi:
                        best_train_roi = roi
                        best_config = config

    if not best_config:
        return {"error": "no valid configuration found in grid search"}

    # Validate best config on test set
    min_conf = best_config["min_confidence"]
    min_edge = best_config["min_edge_pct"]
    kelly_f = best_config["kelly_fraction"]

    bankroll = 100.0
    peak = 100.0
    max_dd = 0.0
    total_pnl = 0.0
    n_bets = 0
    daily_returns = defaultdict(float)

    for bet in test_bets:
        prob = bet.get("model_prob", 0.5)
        edge = bet.get("edge_pct", 0)
        odds = bet.get("odds", 1.0)
        won = bet.get("outcome", "") == "Win"
        date_str = bet.get("date", "")

        if prob < min_conf or edge < min_edge:
            continue

        p = prob
        b = odds - 1
        if b <= 0:
            continue
        q = 1 - p
        kelly_stake = max(0, (p * b - q) / b) * kelly_f
        kelly_stake = min(kelly_stake, 0.03)  # max 3% per bet
        stake = bankroll * kelly_stake

        if stake <= 0 or stake < 0.01:
            continue

        n_bets += 1
        if won:
            profit = stake * (odds - 1)
        else:
            profit = -stake

        bankroll += profit
        bankroll = min(bankroll, 10000.0)  # Liquidity cap
        total_pnl += profit
        daily_returns[date_str] += profit

        peak = max(peak, bankroll)
        dd = (peak - bankroll) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    test_result = {
        "test_bets": n_bets,
        "test_pnl": round(total_pnl, 2),
        "test_bankroll": round(bankroll, 2),
        "test_max_dd": round(max_dd, 4),
    }
    if n_bets > 0:
        # ROI = (final - initial) / initial * 100
        test_result["test_roi"] = round(((bankroll - 100.0) / 100.0) * 100, 2)
        returns = list(daily_returns.values())
        if len(returns) >= 2:
            mean_r = sum(returns) / len(returns)
            var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            std_r = math.sqrt(var_r) if var_r > 0 else 0.001
            test_result["test_sharpe"] = round((mean_r / std_r) * math.sqrt(180), 3)

    best_config.update(test_result)

    # Top 10 configs by train Sharpe
    grid_results.sort(key=lambda x: x.get("train_sharpe", 0), reverse=True)

    return {
        "train_size": split_idx,
        "test_size": len(all_bets) - split_idx,
        "total_bets": len(all_bets),
        "optimal_config": best_config,
        "top_10_configs": grid_results[:10],
        "grid_search_size": len(grid_results),
    }


def analyze_betting_categories(consensus_preds: List[dict], trading_floors: Dict[str, dict]) -> dict:
    """Analyze performance by betting category (ML, spread, total)."""
    # Extract bets with outcomes from trading floors
    category_stats = defaultdict(lambda: {
        "n_bets": 0, "stakes": [], "confidences": [], "agreements": [],
        "edges": [], "odds_list": [],
    })

    for date_str, tf in trading_floors.items():
        bets = tf.get("bets", [])
        for bet in bets:
            cat = bet.get("category", "unknown")
            conf = bet.get("confidence", 0)
            agree = bet.get("agreement", 0)
            edge = bet.get("edge_pct", 0)
            odds = bet.get("odds", 0)
            stake = bet.get("stake", 0)
            forced = bet.get("_forced", False)

            s = category_stats[cat]
            s["n_bets"] += 1
            s["stakes"].append(stake)
            s["confidences"].append(conf)
            s["agreements"].append(agree)
            s["edges"].append(edge)
            s["odds_list"].append(odds)
            if forced:
                s["forced_count"] = s.get("forced_count", 0) + 1

    result = {}
    for cat, s in category_stats.items():
        n = s["n_bets"]
        if n == 0:
            continue
        result[cat] = {
            "n_bets": n,
            "avg_stake": round(sum(s["stakes"]) / n, 2),
            "total_staked": round(sum(s["stakes"]), 2),
            "avg_confidence": round(sum(s["confidences"]) / n, 4),
            "avg_agreement": round(sum(s["agreements"]) / n, 4),
            "avg_edge_pct": round(sum(s["edges"]) / n, 2),
            "avg_odds": round(sum(s["odds_list"]) / n, 3),
            "forced_bets": s.get("forced_count", 0),
        }

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2B: POLITICAL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_political(political_floors: Dict[str, dict]) -> dict:
    """Analyze political trading floor data."""
    if not political_floors:
        return {"error": "no political trading floor data found"}

    # Get the latest
    latest_date = max(political_floors.keys())
    latest = political_floors[latest_date]

    leaderboard = latest.get("leaderboard", [])
    traders = latest.get("traders", {})
    meta = latest.get("meta", {})

    # Trader performance analysis
    trader_analysis = {}
    for trader in leaderboard:
        tid = trader.get("trader_id", "unknown")
        capital = trader.get("capital", 100000)
        roi = trader.get("roi_pct", 0)
        sharpe = trader.get("sharpe", 0)
        wins = trader.get("wins", 0)
        losses = trader.get("losses", 0)
        total = wins + losses
        wr = trader.get("win_rate", 0)
        dd = trader.get("max_drawdown", 0)

        # Risk-adjusted metrics
        calmar = roi / (dd * 100) if dd > 0 else 0
        profit_factor = wins / max(losses, 1)

        trader_analysis[tid] = {
            "rank": trader.get("rank"),
            "capital": capital,
            "roi_pct": roi,
            "sharpe": sharpe,
            "win_rate": wr,
            "total_trades": total,
            "max_drawdown": dd,
            "calmar_ratio": round(calmar, 4),
            "profit_factor": round(profit_factor, 4),
            "personality": trader.get("personality", "unknown"),
            "primary_strategy": trader.get("primary_strategy", "unknown"),
        }

    # Strategy breakdown from detailed trader data
    strategy_performance = defaultdict(lambda: {"trades": 0, "pnl": 0, "wins": 0})
    sector_performance = defaultdict(float)

    for tid, tdata in traders.items():
        strat_breakdown = tdata.get("political_strategy_breakdown", {})
        for strat_name, strat_data in strat_breakdown.items():
            sp = strategy_performance[strat_name]
            sp["trades"] += strat_data.get("trades", 0)
            sp["pnl"] += strat_data.get("pnl", 0)
            sp["wins"] += strat_data.get("wins", 0)

        sector_breakdown = tdata.get("political_sector_breakdown", {})
        for sector, pnl in sector_breakdown.items():
            sector_performance[sector] += pnl

    # Compute win rates
    for strat_name, sp in strategy_performance.items():
        if sp["trades"] > 0:
            sp["win_rate"] = round(sp["wins"] / sp["trades"], 4)
            sp["avg_pnl"] = round(sp["pnl"] / sp["trades"], 2)
        sp["pnl"] = round(sp["pnl"], 2)

    # Progression across dates
    progression = []
    for date_str in sorted(political_floors.keys()):
        pf = political_floors[date_str]
        lb = pf.get("leaderboard", [])
        if lb:
            top_capital = lb[0].get("capital", 100000)
            avg_capital = sum(t.get("capital", 100000) for t in lb) / len(lb)
            progression.append({
                "date": date_str,
                "top_capital": round(top_capital, 2),
                "avg_capital": round(avg_capital, 2),
                "n_traders": len(lb),
            })

    return {
        "latest_date": latest_date,
        "meta": meta,
        "trader_analysis": trader_analysis,
        "strategy_performance": dict(strategy_performance),
        "sector_performance": dict(sorted(sector_performance.items(),
                                          key=lambda x: x[1], reverse=True)),
        "progression": progression,
        "recommendations": generate_political_recommendations(trader_analysis, strategy_performance),
    }


def generate_political_recommendations(trader_analysis: dict, strategy_performance: dict) -> List[str]:
    """Generate actionable recommendations for political trading."""
    recs = []

    # Best trader
    best = min(trader_analysis.items(), key=lambda x: x[1]["rank"] or 999)
    recs.append(f"BEST TRADER: {best[0]} (ROI {best[1]['roi_pct']:.2f}%, Sharpe {best[1]['sharpe']:.1f})")

    # Best strategy
    if strategy_performance:
        best_strat = max(strategy_performance.items(), key=lambda x: x[1]["pnl"])
        recs.append(f"BEST STRATEGY: {best_strat[0]} (PnL ${best_strat[1]['pnl']:.2f}, "
                    f"WR {best_strat[1].get('win_rate', 0):.1%})")

    # Risk warnings
    for tid, ta in trader_analysis.items():
        if ta["roi_pct"] < -1:
            recs.append(f"WARNING: {tid} has negative ROI ({ta['roi_pct']:.2f}%)")
        if ta["max_drawdown"] > 0.005:
            recs.append(f"RISK: {tid} drawdown at {ta['max_drawdown']:.4f}")

    return recs


# ═══════════════════════════════════════════════════════════════════════════════
# PART 3: OUTPUT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_nba_report(results: dict) -> str:
    """Generate human-readable Markdown report for NBA experiment."""
    lines = []
    lines.append("# NBA Scientific Experiment Report")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Engine:** scientific-experiment.py v1.0")
    lines.append("")

    # === EVALUATION ===
    lines.append("## Part 1: Model Evaluation")
    lines.append("")

    # Consensus evaluation
    cons = results.get("consensus_evaluation", {})
    if cons and "error" not in cons:
        lines.append("### Consensus Model Performance")
        lines.append(f"- **Predictions evaluated:** {cons.get('n_predictions', 0)}")
        lines.append(f"- **Brier Score:** {cons.get('brier_score', 'N/A')} "
                      f"(95% CI: [{cons.get('brier_ci_95', [0,0])[0]}, {cons.get('brier_ci_95', [0,0])[1]}])")
        lines.append(f"- **Log Loss:** {cons.get('log_loss', 'N/A')}")
        lines.append(f"- **AUC-ROC:** {cons.get('auc_roc', 'N/A')}")
        lines.append(f"- **ECE (Calibration):** {cons.get('ece', 'N/A')}")
        lines.append(f"- **Directional Accuracy:** {cons.get('accuracy', 'N/A'):.1%}" if isinstance(cons.get('accuracy'), (int, float)) else "")
        lines.append("")

        # Agreement analysis
        aa = cons.get("agreement_analysis", {})
        if aa:
            lines.append("#### Agreement Analysis")
            lines.append(f"- High agreement (>80%): {aa.get('high_agreement_games', 0)} games, "
                          f"accuracy {aa.get('high_agreement_accuracy', 0):.1%}")
            lines.append(f"- Low agreement (<60%): {aa.get('low_agreement_games', 0)} games, "
                          f"accuracy {aa.get('low_agreement_accuracy', 0):.1%}")
            lines.append("")

        # Calibration
        cal = cons.get("calibration_buckets", [])
        if cal:
            lines.append("#### Calibration (Reliability Diagram)")
            lines.append("| Bucket | Predicted | Actual | Count | Error |")
            lines.append("|--------|-----------|--------|-------|-------|")
            for b in cal:
                if b["count"] > 0:
                    lines.append(f"| {b['range']} | {b['avg_predicted']:.3f} | "
                                  f"{b['avg_actual']:.3f} | {b['count']} | {b['calibration_error']:.3f} |")
            lines.append("")

        # Progression
        prog = cons.get("progression", [])
        if prog:
            lines.append("#### Brier Score Progression")
            lines.append("| Date | Avg Brier | Games |")
            lines.append("|------|-----------|-------|")
            for p in prog:
                lines.append(f"| {p['date']} | {p['avg_brier']:.5f} | {p['n_games']} |")
            lines.append("")

    # Per-agent results
    agent_eval = results.get("agent_evaluation", {})
    if agent_eval:
        lines.append("### Per-Agent Model Ranking")
        sorted_agents = sorted(agent_eval.items(), key=lambda x: x[1].get("brier_score", 1.0))
        lines.append("| Rank | Agent | Brier | Log-Loss | AUC | Accuracy | N |")
        lines.append("|------|-------|-------|----------|-----|----------|---|")
        for rank, (aid, metrics) in enumerate(sorted_agents[:20], 1):
            lines.append(f"| {rank} | {aid} | {metrics['brier_score']:.5f} | "
                          f"{metrics['log_loss']:.5f} | {metrics['auc_roc']:.4f} | "
                          f"{metrics['accuracy']:.3f} | {metrics['n_predictions']} |")
        lines.append("")

    # Statistical significance
    sig_tests = results.get("significance_tests", [])
    if sig_tests:
        lines.append("### Statistical Significance (Paired Bootstrap)")
        sig_only = [t for t in sig_tests if t["significant_at_005"]]
        if sig_only:
            lines.append("| Agent 1 | Agent 2 | Brier Diff | p-value | Better |")
            lines.append("|---------|---------|------------|---------|--------|")
            for t in sig_only[:10]:
                lines.append(f"| {t['agent_1']} | {t['agent_2']} | "
                              f"{t['mean_diff']:+.5f} | {t['p_value']:.4f} | {t['better_agent']} |")
        else:
            lines.append("No statistically significant differences found at p < 0.05.")
        lines.append("")

    # === STRATEGY BACKTESTING ===
    lines.append("## Part 2: Strategy Backtesting")
    lines.append("")

    strat = results.get("strategy_analysis", {})
    if strat and "error" not in strat:
        lines.append(f"- **Model Brier:** {strat.get('model_brier', 'N/A')}")
        lines.append(f"- **Games in backtest:** {strat.get('games_total', 0)}")
        lines.append(f"- **Strategies tested:** {strat.get('total_strategies_tested', 0)}")
        lines.append("")

        # Best by Sharpe
        best_sharpe = strat.get("best_by_sharpe", [])
        if best_sharpe:
            lines.append("### Best Strategies by Sharpe Ratio")
            lines.append("| Rank | Strategy | Sharpe | ROI% | PnL | Bets | MaxDD |")
            lines.append("|------|----------|--------|------|-----|------|-------|")
            for rank, s in enumerate(best_sharpe, 1):
                lines.append(f"| {rank} | {s['name']} | {s['sharpe']:.3f} | "
                              f"{s['roi']:.1f}% | ${s['total_pnl']:.2f} | "
                              f"{s['total_bets']} | {s['max_drawdown']:.3f} |")
            lines.append("")

        # Kelly analysis
        kelly = strat.get("kelly_fraction_analysis", [])
        if kelly:
            lines.append("### Kelly Fraction Optimization")
            lines.append("| Fraction | Min Edge | Sharpe | ROI% | MaxDD | Bets |")
            lines.append("|----------|----------|--------|------|-------|------|")
            for k in kelly[:10]:
                lines.append(f"| {k['fraction']:.2f} | {k['min_edge_pct']:.0f}% | "
                              f"{k['sharpe']:.3f} | {k['roi']:.1f}% | "
                              f"{k['max_drawdown']:.3f} | {k['total_bets']} |")
            lines.append("")

    # Regression
    reg = results.get("regression_analysis", {})
    if reg and "error" not in reg:
        lines.append("### Regression Analysis: PnL ~ confidence + edge + odds")
        overall = reg.get("overall_regression", {})
        if overall and "error" not in overall:
            lines.append(f"- **N observations:** {overall.get('n_observations', 0)}")
            lines.append(f"- **R-squared:** {overall.get('r_squared', 0):.4f}")
            lines.append("")
            lines.append("| Variable | Coefficient | Std Error | p-value | Sig |")
            lines.append("|----------|-------------|-----------|---------|-----|")
            for var, coef in overall.get("coefficients", {}).items():
                sig = "***" if coef["p_value"] < 0.001 else "**" if coef["p_value"] < 0.01 else "*" if coef["p_value"] < 0.05 else ""
                lines.append(f"| {var} | {coef['beta']:.6f} | {coef['se']:.6f} | "
                              f"{coef['p_value']:.4f} | {sig} |")
            lines.append("")

        # Profitable categories
        cats = reg.get("per_category", {})
        if cats:
            lines.append("### Profit by Betting Category")
            lines.append("| Category | Bets | Win Rate | Total Profit | Avg Profit | Avg Edge |")
            lines.append("|----------|------|----------|--------------|------------|----------|")
            for cat, cs in list(cats.items())[:15]:
                emoji = "+" if cs["profitable"] else "-"
                lines.append(f"| {cat} | {cs['n_bets']} | {cs['win_rate']:.3f} | "
                              f"{emoji}${abs(cs['total_profit']):.2f} | "
                              f"${cs['avg_profit']:.4f} | {cs['avg_edge_pct']:.1f}% |")
            lines.append("")

    # Optimal thresholds
    opt = results.get("optimal_thresholds", {})
    if opt and "error" not in opt:
        lines.append("### Optimal Threshold Search (Walk-Forward)")
        lines.append(f"- **Train/Test split:** {opt.get('train_size', 0)} / {opt.get('test_size', 0)} bets")
        lines.append(f"- **Grid configurations tested:** {opt.get('grid_search_size', 0)}")
        lines.append("")
        oc = opt.get("optimal_config", {})
        if oc:
            lines.append("**Optimal Configuration:**")
            lines.append(f"- Min Confidence: {oc.get('min_confidence', 0):.2f}")
            lines.append(f"- Min Edge: {oc.get('min_edge_pct', 0):.1f}%")
            lines.append(f"- Kelly Fraction: {oc.get('kelly_fraction', 0):.2f}")
            lines.append(f"- Train ROI: {oc.get('train_roi', 0):.1f}% | Test ROI: {oc.get('test_roi', 'N/A')}")
            lines.append(f"- Train Sharpe: {oc.get('train_sharpe', 0):.3f} | Test Sharpe: {oc.get('test_sharpe', 'N/A')}")
            lines.append(f"- Test Max Drawdown: {oc.get('test_max_dd', 'N/A')}")
            lines.append("")

        # Top configs
        top = opt.get("top_10_configs", [])
        if top:
            lines.append("**Top 10 Configurations by Train Sharpe:**")
            lines.append("| Conf | Edge | Kelly | Train ROI | Train Sharpe | Bets |")
            lines.append("|------|------|-------|-----------|--------------|------|")
            for c in top:
                lines.append(f"| {c['min_confidence']:.2f} | {c['min_edge_pct']:.0f}% | "
                              f"{c['kelly_fraction']:.2f} | {c['train_roi']:.1f}% | "
                              f"{c['train_sharpe']:.3f} | {c['train_bets']} |")
            lines.append("")

    # Category analysis from trading floor
    cat_analysis = results.get("category_analysis", {})
    if cat_analysis:
        lines.append("### Betting Category Profile (from Trading Floor)")
        lines.append("| Category | Bets | Avg Stake | Avg Conf | Avg Agreement | Avg Edge | Forced |")
        lines.append("|----------|------|-----------|----------|---------------|----------|--------|")
        for cat, ca in sorted(cat_analysis.items()):
            lines.append(f"| {cat} | {ca['n_bets']} | ${ca['avg_stake']:.2f} | "
                          f"{ca['avg_confidence']:.3f} | {ca['avg_agreement']:.3f} | "
                          f"{ca['avg_edge_pct']:.1f}% | {ca['forced_bets']} |")
        lines.append("")

    # === RECOMMENDATIONS ===
    lines.append("## Recommendations")
    lines.append("")
    recs = results.get("recommendations", [])
    for r in recs:
        lines.append(f"- {r}")
    lines.append("")

    return "\n".join(lines)


def generate_political_report(results: dict) -> str:
    """Generate Markdown report for political experiment."""
    lines = []
    lines.append("# Political Alpha Scientific Experiment Report")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    pol = results.get("political_analysis", {})
    if pol and "error" not in pol:
        meta = pol.get("meta", {})
        lines.append(f"- **Latest date:** {pol.get('latest_date', 'N/A')}")
        lines.append(f"- **Total events:** {meta.get('events_total', 0)}")
        lines.append(f"- **Trading days:** {meta.get('trading_days', 0)}")
        lines.append(f"- **Social tickers:** {meta.get('social_tickers', 0)}")
        lines.append(f"- **ETF universe:** {meta.get('etf_universe', 0)}")
        lines.append("")

        # Leaderboard
        ta = pol.get("trader_analysis", {})
        if ta:
            lines.append("### Trader Leaderboard")
            lines.append("| Rank | Trader | ROI% | Sharpe | Win Rate | Trades | MaxDD | Calmar | Strategy |")
            lines.append("|------|--------|------|--------|----------|--------|-------|--------|----------|")
            for tid, t in sorted(ta.items(), key=lambda x: x[1]["rank"] or 999):
                lines.append(f"| {t['rank']} | {tid} | {t['roi_pct']:.2f}% | "
                              f"{t['sharpe']:.1f} | {t['win_rate']:.1f}% | "
                              f"{t['total_trades']} | {t['max_drawdown']:.4f} | "
                              f"{t['calmar_ratio']:.2f} | {t['primary_strategy']} |")
            lines.append("")

        # Strategy performance
        sp = pol.get("strategy_performance", {})
        if sp:
            lines.append("### Strategy Performance (across all traders)")
            lines.append("| Strategy | Trades | PnL | Win Rate |")
            lines.append("|----------|--------|-----|----------|")
            for sname, sd in sorted(sp.items(), key=lambda x: x[1]["pnl"], reverse=True):
                lines.append(f"| {sname} | {sd['trades']} | ${sd['pnl']:.2f} | "
                              f"{sd.get('win_rate', 0):.3f} |")
            lines.append("")

        # Sector performance
        sec = pol.get("sector_performance", {})
        if sec:
            lines.append("### Sector Performance")
            lines.append("| Sector | Total PnL |")
            lines.append("|--------|-----------|")
            for sector, pnl in sec.items():
                lines.append(f"| {sector} | ${pnl:.2f} |")
            lines.append("")

        # Progression
        prog = pol.get("progression", [])
        if prog:
            lines.append("### Capital Progression")
            lines.append("| Date | Top Capital | Avg Capital | Traders |")
            lines.append("|------|-------------|-------------|---------|")
            for p in prog:
                lines.append(f"| {p['date']} | ${p['top_capital']:,.2f} | "
                              f"${p['avg_capital']:,.2f} | {p['n_traders']} |")
            lines.append("")

        # Recommendations
        recs = pol.get("recommendations", [])
        if recs:
            lines.append("### Recommendations")
            for r in recs:
                lines.append(f"- {r}")
            lines.append("")

    return "\n".join(lines)


def generate_recommendations(results: dict) -> List[str]:
    """Generate actionable recommendations from all analyses."""
    recs = []

    # From consensus evaluation
    cons = results.get("consensus_evaluation", {})
    if cons and "error" not in cons:
        brier = cons.get("brier_score", 1.0)
        acc = cons.get("accuracy", 0)
        if brier < 0.25:
            recs.append(f"CONSENSUS Brier {brier:.5f} is competitive. Target: < 0.21570 (ATR)")
        else:
            recs.append(f"CONSENSUS Brier {brier:.5f} needs improvement. Focus on calibration.")

        aa = cons.get("agreement_analysis", {})
        if aa:
            h_acc = aa.get("high_agreement_accuracy", 0)
            l_acc = aa.get("low_agreement_accuracy", 0)
            if h_acc > l_acc + 0.1:
                recs.append(f"HIGH-AGREEMENT bets outperform by {(h_acc-l_acc):.1%}. "
                            "Increase stake on high-agreement consensus.")
            elif l_acc > h_acc:
                recs.append("WARNING: Low-agreement bets outperform high-agreement. "
                            "Consensus mechanism may be flawed.")

    # From strategy backtesting
    strat = results.get("strategy_analysis", {})
    if strat and "error" not in strat:
        best = strat.get("best_by_sharpe", [])
        if best:
            top = best[0]
            recs.append(f"BEST STRATEGY: {top['name']} (Sharpe {top['sharpe']:.3f}, "
                        f"ROI {top['roi']:.1f}%, MaxDD {top['max_drawdown']:.3f})")

    # From optimal thresholds
    opt = results.get("optimal_thresholds", {})
    if opt and "error" not in opt:
        oc = opt.get("optimal_config", {})
        if oc:
            recs.append(f"OPTIMAL THRESHOLDS: confidence >= {oc.get('min_confidence', 0):.2f}, "
                        f"edge >= {oc.get('min_edge_pct', 0):.1f}%, "
                        f"Kelly fraction = {oc.get('kelly_fraction', 0):.2f}")
            test_roi = oc.get("test_roi")
            if test_roi is not None:
                if test_roi > 0:
                    recs.append(f"OUT-OF-SAMPLE validation positive: ROI {test_roi:.1f}%. Strategy is robust.")
                else:
                    recs.append(f"WARNING: Out-of-sample ROI is {test_roi:.1f}%. Possible overfitting.")

    # From regression
    reg = results.get("regression_analysis", {})
    if reg and "error" not in reg:
        overall = reg.get("overall_regression", {})
        if overall and "error" not in overall:
            coefs = overall.get("coefficients", {})
            for var in ["confidence", "edge_pct", "odds"]:
                c = coefs.get(var, {})
                if c.get("p_value", 1) < 0.05:
                    direction = "increases" if c["beta"] > 0 else "decreases"
                    recs.append(f"REGRESSION: {var} significantly {direction} PnL "
                                f"(beta={c['beta']:.4f}, p={c['p_value']:.4f})")

        # Profitable categories
        cats = reg.get("per_category", {})
        profitable = [c for c, d in cats.items() if d.get("profitable")]
        unprofitable = [c for c, d in cats.items() if not d.get("profitable")]
        if profitable:
            recs.append(f"PROFITABLE categories ({len(profitable)}): " +
                        ", ".join(profitable[:5]))
        if unprofitable:
            recs.append(f"AVOID categories ({len(unprofitable)}): " +
                        ", ".join(unprofitable[:5]))

    # From agent evaluation
    agent_eval = results.get("agent_evaluation", {})
    if agent_eval:
        best_agent = min(agent_eval.items(), key=lambda x: x[1].get("brier_score", 1.0))
        worst_agent = max(agent_eval.items(), key=lambda x: x[1].get("brier_score", 1.0))
        recs.append(f"BEST AGENT: {best_agent[0]} (Brier {best_agent[1]['brier_score']:.5f})")
        recs.append(f"WORST AGENT: {worst_agent[0]} (Brier {worst_agent[1]['brier_score']:.5f}) — "
                    "consider removing or retraining")

    return recs


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_nba_experiment(verbose: bool = False) -> dict:
    """Run the complete NBA scientific experiment."""
    print("=" * 70)
    print("  NBA SCIENTIFIC EXPERIMENT ENGINE v1.0")
    print("=" * 70)
    print()

    results = {
        "project": "nba",
        "timestamp": datetime.now().isoformat(),
        "engine_version": "1.0",
    }

    # ── Load data ──
    print("[1/8] Loading predictions...")
    predictions = load_predictions()
    print(f"  Loaded {len(predictions)} prediction dates: {list(predictions.keys())}")

    print("[2/8] Loading trading floors...")
    trading_floors = load_trading_floors()
    print(f"  Loaded {len(trading_floors)} trading floor dates")

    print("[3/8] Loading backtest results...")
    backtest_results = load_backtest_results()
    print(f"  Loaded {len(backtest_results)} backtest files")

    print("[4/8] Loading season memory...")
    season_memory = load_season_memory()
    n_memories = sum(len(v) for v in season_memory.get("trader_memories", {}).values()
                     if isinstance(v, list))
    print(f"  Loaded {n_memories} historical bets from season memory")

    # ── Fetch actual results ──
    print("[5/8] Fetching actual NBA results from ESPN...")
    actual_results = {}  # {date_str: {matchup_key: result_dict}}
    all_dates = set(predictions.keys()) | set(trading_floors.keys())
    for date_str in sorted(all_dates):
        # Only fetch for past dates
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            if d >= date.today():
                continue
        except ValueError:
            continue

        scores = fetch_espn_scores(date_str)
        if scores:
            date_results = {}
            for s in scores:
                key = f"{s['away']}@{s['home']}"
                date_results[key] = s
            actual_results[date_str] = date_results
            print(f"  {date_str}: {len(scores)} games resolved")
        else:
            print(f"  {date_str}: no scores found (future game or API issue)")

    if not actual_results:
        print("  WARNING: No actual results fetched. Evaluation will be limited.")
        print("  (This may happen if all prediction dates are in the future)")

    results["data_summary"] = {
        "prediction_dates": len(predictions),
        "trading_floor_dates": len(trading_floors),
        "backtest_files": len(backtest_results),
        "season_memory_bets": n_memories,
        "dates_with_results": len(actual_results),
        "total_resolved_games": sum(len(r) for r in actual_results.values()),
    }

    # ── Part 1: Evaluation ──
    print("\n[6/8] Running evaluation...")

    # Extract and evaluate agent predictions
    agent_preds = extract_agent_predictions(predictions, actual_results)
    if agent_preds:
        print(f"  Extracted predictions for {len(agent_preds)} agents")
        agent_eval = evaluate_agent_predictions(agent_preds)
        results["agent_evaluation"] = agent_eval
        print(f"  Evaluated {len(agent_eval)} agents")

        # Statistical significance
        if len(agent_eval) >= 2:
            sig_tests = statistical_significance_test(agent_eval, agent_preds)
            results["significance_tests"] = sig_tests
            print(f"  Ran {len(sig_tests)} pairwise significance tests")
    else:
        print("  No agent predictions matched with actual results")
        results["agent_evaluation"] = {}
        results["significance_tests"] = []

    # Consensus evaluation
    consensus_preds = extract_consensus_predictions(trading_floors, actual_results)
    if consensus_preds:
        cons_eval = evaluate_consensus(consensus_preds)
        results["consensus_evaluation"] = cons_eval
        print(f"  Consensus evaluation: {cons_eval.get('n_predictions', 0)} ML predictions")
    else:
        results["consensus_evaluation"] = {"error": "no consensus predictions matched results"}
        print("  No consensus predictions matched with actual results")

    # ── Part 2: Strategy backtesting ──
    print("\n[7/8] Running strategy analysis...")

    # Analyze existing backtest results
    strat_analysis = analyze_backtest_strategies(backtest_results)
    results["strategy_analysis"] = strat_analysis
    if "error" not in strat_analysis:
        print(f"  Analyzed {strat_analysis.get('total_strategies_tested', 0)} strategies")
    else:
        print(f"  Strategy analysis: {strat_analysis.get('error')}")

    # Regression analysis
    reg_analysis = run_regression_analysis(season_memory)
    results["regression_analysis"] = reg_analysis
    if "error" not in reg_analysis:
        print(f"  Regression on {reg_analysis.get('total_bets_analyzed', 0)} bets, "
              f"R2={reg_analysis.get('overall_regression', {}).get('r_squared', 'N/A')}")
    else:
        print(f"  Regression: {reg_analysis.get('error')}")

    # Optimal thresholds
    opt_thresholds = optimal_threshold_search(season_memory)
    results["optimal_thresholds"] = opt_thresholds
    if "error" not in opt_thresholds:
        oc = opt_thresholds.get("optimal_config", {})
        print(f"  Optimal: conf>={oc.get('min_confidence', 0):.2f}, "
              f"edge>={oc.get('min_edge_pct', 0):.1f}%, "
              f"kelly={oc.get('kelly_fraction', 0):.2f}")
    else:
        print(f"  Threshold search: {opt_thresholds.get('error')}")

    # Category analysis from trading floors
    cat_analysis = analyze_betting_categories(consensus_preds, trading_floors)
    results["category_analysis"] = cat_analysis
    print(f"  Analyzed {len(cat_analysis)} betting categories")

    # ── Generate recommendations ──
    print("\n[8/8] Generating recommendations...")
    recs = generate_recommendations(results)
    results["recommendations"] = recs
    for r in recs:
        print(f"  >> {r}")

    return results


def run_political_experiment(verbose: bool = False) -> dict:
    """Run the complete political experiment."""
    print("=" * 70)
    print("  POLITICAL ALPHA SCIENTIFIC EXPERIMENT ENGINE v1.0")
    print("=" * 70)
    print()

    results = {
        "project": "political",
        "timestamp": datetime.now().isoformat(),
        "engine_version": "1.0",
    }

    print("[1/2] Loading political trading floors...")
    political_floors = load_political_floors()
    print(f"  Loaded {len(political_floors)} dates")

    print("[2/2] Analyzing political data...")
    pol_analysis = analyze_political(political_floors)
    results["political_analysis"] = pol_analysis

    if "error" not in pol_analysis:
        ta = pol_analysis.get("trader_analysis", {})
        print(f"  Analyzed {len(ta)} traders")
        for tid, t in sorted(ta.items(), key=lambda x: x[1]["rank"] or 999):
            print(f"    #{t['rank']} {tid}: ROI {t['roi_pct']:.2f}%, Sharpe {t['sharpe']:.1f}")
    else:
        print(f"  Error: {pol_analysis.get('error')}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Scientific Experiment Engine for NBA + Political predictions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/scientific-experiment.py --project nba
  python3 scripts/scientific-experiment.py --project political
  python3 scripts/scientific-experiment.py --project all --verbose
        """)
    parser.add_argument("--project", choices=["nba", "political", "all"],
                        default="nba", help="Which project to analyze")
    parser.add_argument("--verbose", action="store_true",
                        help="Print extra debug info")
    args = parser.parse_args()

    today = date.today().isoformat()

    if args.project in ("nba", "all"):
        nba_results = run_nba_experiment(verbose=args.verbose)

        # Save JSON
        json_path = OUTPUT_DIR / f"nba-experiment-{today}.json"
        json_path.write_text(json.dumps(nba_results, indent=2, default=str))
        print(f"\nJSON saved: {json_path}")

        # Save Markdown
        md_path = OUTPUT_DIR / f"nba-experiment-{today}.md"
        md_content = generate_nba_report(nba_results)
        md_path.write_text(md_content)
        print(f"Report saved: {md_path}")

    if args.project in ("political", "all"):
        pol_results = run_political_experiment(verbose=args.verbose)

        # Save JSON
        json_path = OUTPUT_DIR / f"political-experiment-{today}.json"
        json_path.write_text(json.dumps(pol_results, indent=2, default=str))
        print(f"\nJSON saved: {json_path}")

        # Save Markdown
        md_path = OUTPUT_DIR / f"political-experiment-{today}.md"
        md_content = generate_political_report(pol_results)
        md_path.write_text(md_content)
        print(f"Report saved: {md_path}")

    print("\n" + "=" * 70)
    print("  EXPERIMENT COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
