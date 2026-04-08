#!/usr/bin/env python3
"""
SEASON-WIDE BULL vs BEAR DEBATE (stats-only, no LLM)
=======================================================
The LLM debate in debate_round.py is wired into TF v5 Stage 2 for tonight's
~14 games. This module runs the SAME conceptual debate across ALL 1081+
historical games inside backtest_engine.py, using only statistical signals
(no LLM calls) so it executes in sub-second time on a 969 MB VM.

Why two modules:
  - debate_round.py  → live games, multi-round LLM exchange, judge synthesis
  - season_debate.py → full season, features-only, produces a gold label we
                       can grade against actual ROI to validate whether the
                       debate pattern adds real signal.

Debate construction:
  Bull score: how strong is the model's case for its preferred side?
    + |edge_ml|            (market disagreement, favors bull if model > mkt)
    + confidence           (how extreme the model probability is)
    + is_favorite_model    (1.0 if model_prob > 0.55 on that side)
    + multi_edge_agreement (do spread/total edges point same direction)

  Bear score: how much variance/regret risk is in the bet?
    + |1 - 2*prob_home|    (distance from 50/50 = certainty; inverse for bear)
    + variance_proxy       (wider margin predictions = higher variance)
    + line_disagreement    (|spread_edge| large but ml_edge small → trap)
    + pushes_possible      (catgeories with exactly-median line risk)

  Verdict: bull if bull >> bear, bear if bear >> bull, tie otherwise.
  Conviction: 0-1, |bull - bear| / max(bull + bear, 1e-6).

Usage (standalone diagnostic):
  python3 scripts/arena/season_debate.py
"""

from typing import Dict, Optional


def compute_debate(pred: Dict, game=None, odds=None) -> Dict:
    """
    Run a statistical Bull vs Bear debate for a single game.

    Args:
        pred: dict from ModelPredictor.predict_game() with keys
              prob_home, confidence, edge_ml, edge_spread, edge_total, market_prob
        game: optional Game dataclass (for future: rest days, injuries)
        odds: optional OddsLine (for future: line movement)

    Returns:
        dict with {verdict, conviction, bull_score, bear_score, preferred_side,
                   signals: {...breakdown...}}
    """
    prob_home = float(pred.get("prob_home", 0.5))
    confidence = float(pred.get("confidence", 0.3))
    edge_ml = float(pred.get("edge_ml", 0.0))
    edge_spread = float(pred.get("edge_spread", 0.0))
    edge_total = float(pred.get("edge_total", 0.0))
    market_prob = float(pred.get("market_prob", 0.5))

    preferred_side = "home" if prob_home >= 0.5 else "away"
    abs_edge_ml = abs(edge_ml)
    abs_edge_spread = abs(edge_spread)
    abs_edge_total = abs(edge_total)

    # ── BULL CASE ────────────────────────────────────────────────────────
    bull_signals = {
        "edge_ml": round(abs_edge_ml * 10.0, 3),        # scale 0-1
        "confidence": round(confidence, 3),
        "extreme_prob": round(abs(prob_home - 0.5) * 2.0, 3),  # 0 at 0.5, 1 at 0/1
    }
    # Multi-edge agreement: ML edge and spread edge point same direction
    if edge_ml * edge_spread > 0 and abs_edge_ml > 0.01:
        bull_signals["multi_edge_agreement"] = 0.4
    else:
        bull_signals["multi_edge_agreement"] = 0.0

    # Model disagrees strongly with market (big edge) → bull
    if abs_edge_ml > 0.05:
        bull_signals["market_disagreement"] = 0.3
    else:
        bull_signals["market_disagreement"] = 0.0

    bull_score = sum(bull_signals.values())

    # ── BEAR CASE ────────────────────────────────────────────────────────
    bear_signals = {
        "near_coinflip": round((1.0 - abs(prob_home - 0.5) * 2.0) * 0.6, 3),
        "low_confidence": round((1.0 - confidence) * 0.4, 3),
    }
    # Trap detection: large spread edge but tiny ML edge = noise
    if abs_edge_ml < 0.02 and abs_edge_spread > 0.3:
        bear_signals["trap_signal"] = 0.4
    else:
        bear_signals["trap_signal"] = 0.0

    # Variance risk: total prediction very far from market → volatile game
    if abs_edge_total > 0.8:
        bear_signals["total_volatility"] = 0.3
    else:
        bear_signals["total_volatility"] = 0.0

    # Market strongly disagrees (market very confident the other way)
    if market_prob > 0.7 or market_prob < 0.3:
        bear_signals["market_conviction_against"] = 0.2
    else:
        bear_signals["market_conviction_against"] = 0.0

    bear_score = sum(bear_signals.values())

    # ── VERDICT ──────────────────────────────────────────────────────────
    total = bull_score + bear_score + 1e-6
    diff = bull_score - bear_score
    conviction = round(abs(diff) / total, 4)

    if bull_score >= bear_score * 1.25 and bull_score >= 0.5:
        verdict = "bull"
    elif bear_score >= bull_score * 1.25 and bear_score >= 0.5:
        verdict = "bear"
    else:
        verdict = "tie"

    return {
        "verdict": verdict,
        "conviction": conviction,
        "bull_score": round(bull_score, 3),
        "bear_score": round(bear_score, 3),
        "preferred_side": preferred_side,
        "signals": {
            "bull": bull_signals,
            "bear": bear_signals,
        },
    }


def categorize_conviction(conviction: float) -> str:
    """Bucket conviction into labels for ROI attribution."""
    if conviction >= 0.7:
        return "high"
    if conviction >= 0.4:
        return "mid"
    return "low"


if __name__ == "__main__":
    # Smoke test with 3 synthetic predictions
    test_cases = [
        # Strong bull: model vs market edge, high confidence
        {"prob_home": 0.72, "confidence": 0.85, "edge_ml": 0.08,
         "edge_spread": 0.4, "edge_total": 0.1, "market_prob": 0.64},
        # Strong bear: near coinflip, low edge
        {"prob_home": 0.51, "confidence": 0.32, "edge_ml": 0.005,
         "edge_spread": 0.5, "edge_total": 0.0, "market_prob": 0.505},
        # Tie: moderate everything
        {"prob_home": 0.58, "confidence": 0.50, "edge_ml": 0.03,
         "edge_spread": 0.1, "edge_total": 0.2, "market_prob": 0.55},
    ]
    import json
    for i, p in enumerate(test_cases):
        result = compute_debate(p)
        print(f"\n=== case {i} ===")
        print(json.dumps(result, indent=2))
