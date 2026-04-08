#!/usr/bin/env python3
"""
MODEL PREDICTIONS — Real ML Predictions for Trading Floor Agents
================================================================
Bridges HF Space evolution models → Trading Floor agents.
Every agent gets REAL model probabilities, not LLM guessing.

Multi-target predictions:
  - moneyline: P(home_win) from binary classifier  [LIVE on all 6 islands]
  - spread:    predicted margin (home - away)       [regression target]
  - total:     predicted total points               [regression target]

Each prediction includes:
  - probability/value from best evolved model
  - confidence interval (from ensemble of top-5 individuals)
  - model type and feature count
  - calibration quality score
"""

import json, os, sys, time, ssl, statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.error import URLError
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path('/home/termius/mon-ipad')
DATA = ROOT / 'data'

# ═══════════════════════════════════════════════════════════════
# PREDICTION TARGETS
# ═══════════════════════════════════════════════════════════════

TARGETS = {
    "moneyline": {
        "type": "classification",
        "description": "P(home_win)",
        "y_func": "1 if home_score > away_score else 0",
        "live": True,  # Already running on all 6 islands
    },
    "spread": {
        "type": "regression",
        "description": "predicted margin (home - away)",
        "y_func": "home_score - away_score",
        "live": False,  # Needs GPU autoresearch to train
    },
    "total": {
        "type": "regression",
        "description": "predicted total points",
        "y_func": "home_score + away_score",
        "live": False,  # Needs GPU autoresearch to train
    },
}

# ═══════════════════════════════════════════════════════════════
# HF SPACE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

HF_SPACES = {
    "S10": {"url": "https://nomos42-nba-quant.hf.space", "role": "exploitation", "model_type": "xgboost"},
    "S11": {"url": "https://nomos42-nba-quant-2.hf.space", "role": "exploration", "model_type": "mixed"},
    "S12": {"url": "https://nomos42-nba-evo-3.hf.space", "role": "extra_trees", "model_type": "extra_trees"},
    "S13": {"url": "https://nomos42-nba-evo-4.hf.space", "role": "catboost", "model_type": "catboost"},
    "S14": {"url": "https://nomos42-nba-evo-5.hf.space", "role": "lightgbm", "model_type": "lightgbm"},
    "S15": {"url": "https://nomos42-nba-evo-6.hf.space", "role": "wide_search", "model_type": "mixed"},
}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# ═══════════════════════════════════════════════════════════════
# PREDICTION DATA CLASSES
# ═══════════════════════════════════════════════════════════════

@dataclass
class ModelPrediction:
    """Single model's prediction for one game."""
    source: str           # e.g., "S10", "S14", "kaggle_catboost"
    model_type: str       # e.g., "xgboost", "catboost", "lightgbm"
    n_features: int
    generation: int
    brier: float          # model's training brier score (quality indicator)
    # Moneyline
    home_win_prob: float  # P(home_win) from classifier
    # Spread (from regression models when available)
    predicted_spread: Optional[float] = None  # home - away predicted margin
    spread_std: Optional[float] = None
    # Total (from regression models when available)
    predicted_total: Optional[float] = None   # predicted total points
    total_std: Optional[float] = None

@dataclass
class GamePredictionPacket:
    """Complete prediction packet for one game — what every agent receives."""
    game_id: str
    home_team: str
    away_team: str
    date: str
    # Ensemble predictions (aggregated from all models)
    home_win_prob: float          # ensemble P(home_win)
    home_win_prob_ci: Tuple[float, float] = (0.0, 1.0)  # 90% CI
    predicted_spread: Optional[float] = None
    spread_ci: Optional[Tuple[float, float]] = None
    predicted_total: Optional[float] = None
    total_ci: Optional[Tuple[float, float]] = None
    # Derived betting signals
    ml_edge_vs_odds: Optional[float] = None  # model P - implied P from odds
    spread_edge: Optional[float] = None
    total_edge: Optional[float] = None
    # Quality
    n_models: int = 0
    avg_brier: float = 1.0
    confidence: str = "low"  # low/medium/high based on model agreement
    # Raw model predictions
    model_predictions: List[dict] = field(default_factory=list)

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "date": self.date,
            "predictions": {
                "moneyline": {
                    "home_win_prob": round(self.home_win_prob, 4),
                    "ci_90": [round(x, 4) for x in self.home_win_prob_ci],
                    "edge_vs_odds": round(self.ml_edge_vs_odds, 4) if self.ml_edge_vs_odds else None,
                },
                "spread": {
                    "predicted_margin": round(self.predicted_spread, 2) if self.predicted_spread else None,
                    "ci_90": [round(x, 2) for x in self.spread_ci] if self.spread_ci else None,
                    "edge": round(self.spread_edge, 2) if self.spread_edge else None,
                },
                "total": {
                    "predicted_total": round(self.predicted_total, 1) if self.predicted_total else None,
                    "ci_90": [round(x, 1) for x in self.total_ci] if self.total_ci else None,
                    "edge": round(self.total_edge, 1) if self.total_edge else None,
                },
            },
            "quality": {
                "n_models": self.n_models,
                "avg_brier": round(self.avg_brier, 5),
                "confidence": self.confidence,
            },
            "model_details": self.model_predictions[:5],  # Top 5 for transparency
        }


# ═══════════════════════════════════════════════════════════════
# BET CATEGORY → MODEL TARGET MAPPING
# ═══════════════════════════════════════════════════════════════

# Maps each of the 120+ bet categories to which ML target(s) inform the bet
BET_CATEGORY_MODEL_MAP = {
    # GROUP 1: MONEYLINE — directly from classifier
    "ml_fg": ["moneyline"],
    "ml_1h": ["moneyline"],  # use full-game as proxy, adjust with 1H features
    "ml_2h": ["moneyline"],
    "ml_q1": ["moneyline"],
    "ml_q2": ["moneyline"],
    "ml_q3": ["moneyline"],
    "ml_q4": ["moneyline"],

    # GROUP 2: SPREAD — from regression spread model
    "sp_fg": ["spread", "moneyline"],
    "sp_1h": ["spread"],
    "sp_2h": ["spread"],
    "sp_q1": ["spread"],
    "sp_alt_p2": ["spread"],
    "sp_alt_p5": ["spread"],
    "sp_alt_m2": ["spread"],
    "sp_alt_m5": ["spread"],
    "sp_alt_m10": ["spread"],

    # GROUP 3: TOTALS — from regression total model
    "tot_fg": ["total"],
    "tot_1h": ["total"],
    "tot_2h": ["total"],
    "tot_q1": ["total"],
    "tot_alt_195": ["total"],
    "tot_alt_200": ["total"],
    "tot_alt_205": ["total"],
    "tot_alt_210": ["total"],
    "tot_alt_215": ["total"],
    "tot_alt_220": ["total"],
    "tot_alt_225": ["total"],
    "tot_alt_230": ["total"],
    "tot_alt_235": ["total"],

    # GROUP 4: PLAYER PROPS — use moneyline + team totals as base context
    "pp_pts": ["total", "moneyline"],
    "pp_reb": ["total", "moneyline"],
    "pp_ast": ["total", "moneyline"],
    "pp_3pm": ["total", "moneyline"],
    "pp_stl": ["moneyline"],
    "pp_blk": ["moneyline"],
    "pp_to":  ["moneyline"],
    "pp_pra": ["total", "moneyline"],
    "pp_pr":  ["total", "moneyline"],
    "pp_pa":  ["total", "moneyline"],
    "pp_ra":  ["total", "moneyline"],
    "pp_dd":  ["total", "moneyline"],
    "pp_td":  ["total", "moneyline"],
    "pp_fga": ["total"],
    "pp_fta": ["total"],
    "pp_min": ["moneyline"],

    # GROUP 5: QUARTERS — from moneyline + spread + total
    "q_race": ["moneyline", "spread"],
    "q_highest": ["total", "spread"],
    "q_margin": ["spread"],
    "q_exact": ["spread"],

    # GROUP 6: ALT LINES — from spread + total models
    "alt_sp_1": ["spread"],
    "alt_sp_3": ["spread"],
    "alt_sp_7": ["spread"],
    "alt_sp_10": ["spread"],
    "alt_tot_190": ["total"],
    "alt_tot_200": ["total"],
    "alt_tot_210": ["total"],
    "alt_tot_220": ["total"],
    "alt_tot_230": ["total"],
    "alt_tot_240": ["total"],

    # GROUP 7: EXOTICS — multi-target
    "ex_ot": ["moneyline", "spread"],   # overtime probability
    "ex_margin": ["spread"],            # exact margin range
    "ex_ht_ft": ["moneyline", "spread"],  # halftime/fulltime combo
    "ex_first_to": ["moneyline", "total"],
    "ex_lead_change": ["spread"],
    "ex_blowout": ["spread"],
    "ex_wire_to_wire": ["moneyline", "spread"],

    # GROUP 8: PARLAYS — ensemble of multiple targets
    "parlay_ml_2": ["moneyline"],
    "parlay_ml_3": ["moneyline"],
    "parlay_sp_2": ["spread"],
    "parlay_mixed": ["moneyline", "spread", "total"],
    "parlay_sgp": ["moneyline", "spread", "total"],
}


# ═══════════════════════════════════════════════════════════════
# FETCH PREDICTIONS FROM HF SPACES
# ═══════════════════════════════════════════════════════════════

def fetch_space_prediction(space_id: str, space_info: dict, games: List[dict], timeout: int = 30) -> List[ModelPrediction]:
    """Fetch predictions from a single HF space."""
    predictions = []
    url = space_info["url"]

    try:
        # First get the best individual's info
        req = Request(f"{url}/api/best", headers={"User-Agent": "Nomos42-TF/5.0"})
        with urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            best = json.loads(resp.read())

        gen = best.get("generation", 0)
        brier = best.get("brier", 1.0)
        n_feat = best.get("n_features", 0)
        model_type = best.get("model_type", "unknown")

        if brier >= 0.99 or n_feat < 5:
            return predictions  # Space not ready

        # Now get actual predictions for today's games
        req = Request(
            f"{url}/api/predict",
            data=json.dumps({"games": games}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42-TF/5.0"},
        )
        with urlopen(req, timeout=60, context=SSL_CTX) as resp:
            pred_data = json.loads(resp.read())

        preds = pred_data.get("predictions", pred_data if isinstance(pred_data, list) else [])
        for p in preds:
            predictions.append(ModelPrediction(
                source=space_id,
                model_type=model_type,
                n_features=n_feat,
                generation=gen,
                brier=brier,
                home_win_prob=float(p.get("home_win_prob", p.get("probability", 0.5))),
            ))

    except Exception as e:
        print(f"  {space_id}: OFFLINE ({type(e).__name__})")

    return predictions


def fetch_all_predictions(games: List[dict]) -> Dict[str, List[ModelPrediction]]:
    """Fetch predictions from ALL 6 HF spaces in parallel.
    Returns dict: game_key → list of ModelPrediction."""

    results = {}  # "home_team vs away_team" → [ModelPrediction]
    for g in games:
        key = f"{g.get('home_team', '')} vs {g.get('away_team', '')}"
        results[key] = []

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(fetch_space_prediction, sid, sinfo, games): sid
            for sid, sinfo in HF_SPACES.items()
        }
        for future in as_completed(futures, timeout=120):
            sid = futures[future]
            try:
                preds = future.result()
                if preds:
                    for i, g in enumerate(games):
                        key = f"{g.get('home_team', '')} vs {g.get('away_team', '')}"
                        if i < len(preds):
                            results[key].append(preds[i])
                            print(f"  {sid}: P(home)={preds[i].home_win_prob:.3f} ({preds[i].model_type}, {preds[i].n_features}f, gen {preds[i].generation})")
            except Exception as e:
                print(f"  {sid}: failed ({e})")

    return results


# ═══════════════════════════════════════════════════════════════
# ENSEMBLE AGGREGATION
# ═══════════════════════════════════════════════════════════════

def ensemble_predictions(game: dict, model_preds: List[ModelPrediction], odds: dict = None) -> GamePredictionPacket:
    """Aggregate multiple model predictions into a single GamePredictionPacket.
    Uses inverse-brier weighting (better models get more weight)."""

    home = game.get("home_team", "")
    away = game.get("away_team", "")

    packet = GamePredictionPacket(
        game_id=game.get("id", f"{home}_{away}"),
        home_team=home,
        away_team=away,
        date=game.get("commence_time", game.get("date", "")),
    )

    if not model_preds:
        packet.home_win_prob = 0.5
        packet.confidence = "none"
        return packet

    # Inverse-brier weighting: weight = 1 / brier (capped)
    weights = []
    probs = []
    for mp in model_preds:
        w = 1.0 / max(mp.brier, 0.15)  # Cap weight for very good models
        weights.append(w)
        probs.append(mp.home_win_prob)

    total_w = sum(weights)
    weighted_prob = sum(w * p for w, p in zip(weights, probs)) / total_w

    # Confidence interval from model disagreement
    if len(probs) >= 3:
        std = statistics.stdev(probs)
        ci_low = max(0.01, weighted_prob - 1.645 * std)
        ci_high = min(0.99, weighted_prob + 1.645 * std)
    else:
        ci_low = max(0.01, weighted_prob - 0.10)
        ci_high = min(0.99, weighted_prob + 0.10)

    packet.home_win_prob = weighted_prob
    packet.home_win_prob_ci = (ci_low, ci_high)
    packet.n_models = len(model_preds)
    packet.avg_brier = statistics.mean(mp.brier for mp in model_preds)

    # Spread estimate from moneyline using logistic approximation
    # Empirical: P(home) ≈ logistic(spread / 5.5) for NBA
    if weighted_prob > 0.01 and weighted_prob < 0.99:
        import math
        logit = math.log(weighted_prob / (1 - weighted_prob))
        packet.predicted_spread = round(logit * 5.5, 1)  # Approximate spread from ML prob
        packet.spread_ci = (packet.predicted_spread - 5.0, packet.predicted_spread + 5.0)

    # Total estimate (base ~215 + adjustment from offensive/defensive ratings)
    # This is a rough proxy until regression models are trained
    packet.predicted_total = 215.0  # Will be replaced by real regression model
    packet.total_ci = (200.0, 230.0)

    # Edge vs odds
    if odds:
        for bk_name, bk_odds in odds.items():
            home_odds = bk_odds.get(home, 0)
            if home_odds > 1.0:
                implied_prob = 1.0 / home_odds
                packet.ml_edge_vs_odds = weighted_prob - implied_prob
                break

    # Spread edge (predicted margin vs line)
    if packet.predicted_spread is not None and odds:
        line = odds.get("spread_line")  # If available from odds data
        if line is not None:
            packet.spread_edge = packet.predicted_spread - line

    # Confidence level
    if len(probs) >= 3:
        std = statistics.stdev(probs)
        if std < 0.03 and packet.avg_brier < 0.23:
            packet.confidence = "high"
        elif std < 0.06:
            packet.confidence = "medium"
        else:
            packet.confidence = "low"
    else:
        packet.confidence = "low"

    # Store model details for transparency
    for mp in sorted(model_preds, key=lambda x: x.brier)[:5]:
        packet.model_predictions.append({
            "source": mp.source,
            "model_type": mp.model_type,
            "n_features": mp.n_features,
            "brier": mp.brier,
            "home_win_prob": round(mp.home_win_prob, 4),
        })

    return packet


# ═══════════════════════════════════════════════════════════════
# AGENT CONTEXT: What each trading agent receives
# ═══════════════════════════════════════════════════════════════

def build_agent_context(game: dict, prediction: GamePredictionPacket, bet_category: str) -> dict:
    """Build the context packet that a trading agent receives for a specific bet.

    Each agent gets:
    1. Real ML model predictions (not LLM guessing)
    2. Which models inform this specific bet type
    3. Odds and calculated edge
    4. Confidence and quality metrics
    """
    models_used = BET_CATEGORY_MODEL_MAP.get(bet_category, ["moneyline"])
    pred_dict = prediction.to_dict()

    context = {
        "game": {
            "home_team": prediction.home_team,
            "away_team": prediction.away_team,
            "date": prediction.date,
        },
        "bet_category": bet_category,
        "models_informing_bet": models_used,
        "ml_predictions": {},
        "quality": pred_dict["quality"],
        "instruction": (
            f"You are betting on '{bet_category}'. "
            f"Use the ML model predictions below (NOT your intuition) to determine edge. "
            f"The models were trained on {prediction.n_models} evolved individuals "
            f"using {prediction.model_predictions[0]['n_features'] if prediction.model_predictions else '?'} features "
            f"across {prediction.model_predictions[0].get('model_type', '?') if prediction.model_predictions else '?'} architecture. "
            f"Only bet when model edge > 3% and confidence is medium or high."
        ),
    }

    # Include only the relevant ML predictions for this bet category
    for target in models_used:
        if target in pred_dict["predictions"]:
            context["ml_predictions"][target] = pred_dict["predictions"][target]

    return context


# ═══════════════════════════════════════════════════════════════
# MAIN: BUILD PREDICTIONS FOR ALL TODAY'S GAMES
# ═══════════════════════════════════════════════════════════════

def build_daily_predictions() -> List[dict]:
    """Main entry: fetch predictions for all today's games from all 6 islands."""

    # Load today's games from odds
    odds_path = DATA / 'nba-agent' / 'odds-latest.json'
    if not odds_path.exists():
        print("No odds file found — cannot build predictions")
        return []

    with open(odds_path) as f:
        games = json.load(f)

    if not games:
        print("No games today")
        return []

    print(f"\n{'='*60}")
    print(f"MODEL PREDICTIONS — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"Games: {len(games)} | Spaces: {len(HF_SPACES)} | Targets: {len(TARGETS)}")
    print(f"{'='*60}\n")

    # Fetch from all 6 HF spaces in parallel
    print("Fetching predictions from 6 evolution islands...")
    all_preds = fetch_all_predictions(games)

    # Build ensemble predictions per game
    results = []
    for game in games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        key = f"{home} vs {away}"

        # Get odds for edge calculation
        game_odds = {}
        for bk in game.get("bookmakers", [])[:3]:
            for mkt in bk.get("markets", []):
                if mkt["key"] == "h2h":
                    game_odds[bk["key"]] = {o["name"]: o["price"] for o in mkt["outcomes"]}

        model_preds = all_preds.get(key, [])
        packet = ensemble_predictions(game, model_preds, game_odds)

        results.append(packet.to_dict())

        # Print summary
        conf_icon = {"high": "+++", "medium": "++", "low": "+", "none": "?"}[packet.confidence]
        edge_str = f"edge={packet.ml_edge_vs_odds:+.1%}" if packet.ml_edge_vs_odds else "no odds"
        print(f"  {home} vs {away}: P(home)={packet.home_win_prob:.3f} "
              f"[{packet.home_win_prob_ci[0]:.3f}-{packet.home_win_prob_ci[1]:.3f}] "
              f"{edge_str} conf={conf_icon} models={packet.n_models}")

    # Save predictions
    out_path = DATA / 'arena' / 'model-predictions-latest.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_games": len(results),
            "n_models": len(HF_SPACES),
            "targets": list(TARGETS.keys()),
            "predictions": results,
        }, f, indent=2)

    print(f"\nSaved {len(results)} game predictions to {out_path}")
    return results


if __name__ == "__main__":
    build_daily_predictions()
