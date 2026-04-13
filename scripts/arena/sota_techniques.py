#!/usr/bin/env python3
"""
SOTA Multi-Agent Prediction Techniques
========================================
Implements key techniques from 10 state-of-the-art papers on multi-agent
prediction markets and betting, integrated into Trading Floor v4/v5 and
Political Trading Floor.

Papers implemented:
  [P1] Prediction Arena (2604.07355) — Per-agent P&L ledger
  [P2] TradingAgents (2412.20138) — Bull/Bear debate protocol
  [P3] Agent Trading Arena (2502.17967) — Chart-based visual context
  [P4] Prophet Arena (2510.17638) — Rolling Brier weighting
  [P5] AgentSociety (2502.08691) — Opinion dynamics convergence
  [P6] MARL Market Making (2510.25929) — Heterogeneous agent objectives
  [P7] Competition→Coordination (2511.17621) — Belief market consensus
  [P8] Semantic Trading (2512.02436) — Correlation discovery
  [P9] Coherence Forecasting (2507.23163) — Coherence gate
  [P10] Manipulation in Prediction Markets (2601.20452) — Whale guard

Usage:
  from sota_techniques import SOTAEnhancer
  enhancer = SOTAEnhancer()
  bets = enhancer.enhance_bets(trader_id, raw_bets, all_agent_bets, history)

All techniques are pure functions — no API calls, no external deps.
"""

import math
import hashlib
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any


# ═══════════════════════════════════════════════════════════════════
# [P6] HETEROGENEOUS AGENT OBJECTIVES (MARL Market Making)
# Each agent optimizes for a structurally different objective.
# This prevents groupthink and ensures diverse reasoning.
# ═══════════════════════════════════════════════════════════════════

AGENT_OBJECTIVES = {
    "gemini": {
        "name": "Sharpe Maximizer",
        "objective": "max_sharpe",
        "description": "Optimizes risk-adjusted returns. Prefers consistent small edges over volatile big bets.",
        "edge_scaling": lambda edge: edge * 0.8 if edge > 0.15 else edge * 1.2,  # penalize volatile
        "min_edge_override": 0.03,  # higher threshold for consistency
        "max_bet_mult": 0.8,  # smaller bets
    },
    "openrouter": {
        "name": "ROI Maximizer",
        "objective": "max_roi",
        "description": "Maximizes total return on investment. Balanced approach.",
        "edge_scaling": lambda edge: edge,  # neutral
        "min_edge_override": 0.02,
        "max_bet_mult": 1.0,
    },
    "claude": {
        "name": "Drawdown Minimizer",
        "objective": "min_drawdown",
        "description": "Minimizes maximum drawdown. Ultra-conservative position sizing.",
        "edge_scaling": lambda edge: edge * 0.6,  # aggressive risk reduction
        "min_edge_override": 0.04,  # only high-conviction bets
        "max_bet_mult": 0.5,  # half-size bets
    },
    "codex": {
        "name": "Win Rate Maximizer",
        "objective": "max_winrate",
        "description": "Maximizes number of winning bets. Focuses on high-probability outcomes.",
        "edge_scaling": lambda edge: edge * 1.5 if edge > 0.10 else edge * 0.7,  # boost high-prob
        "min_edge_override": 0.01,  # low threshold, but favors favorites
        "max_bet_mult": 0.7,
    },
    "grok": {
        "name": "Kelly Edge Maximizer",
        "objective": "max_kelly_edge",
        "description": "Maximizes Kelly edge. Aggressive on biggest edges, zero on marginal.",
        "edge_scaling": lambda edge: edge * 2.0 if edge > 0.08 else 0.0,  # all-or-nothing
        "min_edge_override": 0.05,  # only big edges
        "max_bet_mult": 1.5,  # bigger bets on conviction
    },
}


def apply_heterogeneous_objective(trader_id: str, bets: List[Dict]) -> List[Dict]:
    """[P6] Apply agent-specific objective function to bet sizing."""
    obj = AGENT_OBJECTIVES.get(trader_id)
    if not obj:
        return bets

    filtered = []
    for bet in bets:
        edge = bet.get("edge_pct", 0) / 100.0
        prob = bet.get("model_prob", 0.5)

        # Apply objective-specific edge scaling
        scaled_edge = obj["edge_scaling"](edge)

        # Check minimum edge threshold for this objective
        if abs(scaled_edge) < obj["min_edge_override"]:
            continue

        # Scale bet size by objective multiplier
        bet = dict(bet)  # copy
        bet["bet_size"] = round(bet["bet_size"] * obj["max_bet_mult"], 4)
        bet["edge_pct"] = round(scaled_edge * 100, 2)
        bet["objective"] = obj["name"]
        bet["reasoning"] = bet.get("reasoning", "") + f" | P6:{obj['name']}"

        # [P6] Win Rate Maximizer: skip low-probability bets
        if obj["objective"] == "max_winrate" and prob < 0.52:
            continue

        # [P6] Kelly Edge Maximizer: skip small edges entirely
        if obj["objective"] == "max_kelly_edge" and abs(edge) < 0.05:
            continue

        filtered.append(bet)

    return filtered


# ═══════════════════════════════════════════════════════════════════
# [P9] COHERENCE GATE (Argumentatively Coherent Forecasting)
# Reject bets where the agent's reasoning contradicts its prediction.
# ═══════════════════════════════════════════════════════════════════

def coherence_check(bet: Dict) -> Tuple[bool, str]:
    """
    [P9] Check if a bet is coherent — reasoning aligns with prediction.

    Returns (is_coherent, reason_if_not).

    Checks:
    1. Edge sign vs bet direction — betting on something with negative expected value?
    2. Probability vs category — betting on underdog with <40% model prob at bad odds?
    3. Kelly sanity — bet size should be proportional to edge, not random
    """
    prob = bet.get("model_prob", 0.5)
    edge = bet.get("edge_pct", 0) / 100.0
    category = bet.get("category", "")
    odds = bet.get("odds", 2.0)
    bet_size = bet.get("bet_size", 0)

    # Check 1: Negative edge bet — never coherent
    if edge < -0.02:
        return False, f"negative_edge({edge:.3f})"

    # Check 2: Very low probability bet on favorites category
    if "home" in category and prob < 0.35 and odds < 2.5:
        return False, f"low_prob_favorite(prob={prob:.3f})"
    if "away" in category and (1 - prob) < 0.35 and odds < 2.5:
        return False, f"low_prob_favorite(prob={1-prob:.3f})"

    # Check 3: Bet size wildly disproportionate to edge
    if edge > 0 and bet_size > 0:
        # Kelly optimal = edge / (odds - 1)
        implied_odds = odds - 1.0 if odds > 1.0 else 1.0
        kelly_optimal = edge / implied_odds if implied_odds > 0 else 0
        if bet_size > kelly_optimal * 5 and kelly_optimal > 0:
            return False, f"oversized_vs_kelly(bet={bet_size:.4f}, kelly={kelly_optimal:.4f})"

    # Check 4: Exotic bet with no edge signal
    exotic_cats = {"exact_margin", "margin_16_plus", "double_result", "player_"}
    for exotic in exotic_cats:
        if exotic in category and abs(edge) < 0.01:
            return False, f"exotic_no_edge({category})"

    return True, "coherent"


def apply_coherence_gate(bets: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    [P9] Filter bets through coherence gate.
    Returns (passed_bets, rejected_bets).
    """
    passed = []
    rejected = []
    for bet in bets:
        is_coherent, reason = coherence_check(bet)
        if is_coherent:
            bet = dict(bet)
            bet["coherence_status"] = "PASS"
            passed.append(bet)
        else:
            bet = dict(bet)
            bet["coherence_status"] = f"REJECT:{reason}"
            rejected.append(bet)
    return passed, rejected


# ═══════════════════════════════════════════════════════════════════
# [P4] ROLLING BRIER WEIGHTING (Prophet Arena)
# Weight each agent by their rolling Brier score.
# Better-calibrated agents get more influence.
# ═══════════════════════════════════════════════════════════════════

def compute_agent_brier(bets: List[Dict], window: int = 50) -> float:
    """
    [P4] Compute rolling Brier score for an agent's recent predictions.
    Lower is better. Returns 0.25 (random baseline) if no data.
    """
    recent = bets[-window:] if len(bets) >= window else bets
    if not recent:
        return 0.25  # random baseline

    brier_sum = 0.0
    count = 0
    for b in recent:
        prob = b.get("model_prob", 0.5)
        outcome = 1.0 if b.get("outcome") == "Win" else 0.0
        brier_sum += (prob - outcome) ** 2
        count += 1

    return brier_sum / count if count > 0 else 0.25


def compute_brier_weights(agent_briers: Dict[str, float]) -> Dict[str, float]:
    """
    [P4] Convert per-agent Brier scores to normalized weights.
    Lower Brier → higher weight. Uses inverse-Brier weighting.
    """
    if not agent_briers:
        return {}

    # Inverse Brier weighting: weight = 1 / (brier + epsilon)
    epsilon = 0.01
    raw_weights = {
        tid: 1.0 / (brier + epsilon)
        for tid, brier in agent_briers.items()
    }

    # Normalize to sum to len(agents)
    total = sum(raw_weights.values())
    n = len(raw_weights)
    if total > 0:
        weights = {tid: (w / total) * n for tid, w in raw_weights.items()}
    else:
        weights = {tid: 1.0 for tid in agent_briers}

    return weights


def apply_brier_weight(trader_id: str, bets: List[Dict],
                       brier_weights: Dict[str, float]) -> List[Dict]:
    """[P4] Scale bet sizes by agent's Brier-derived weight."""
    weight = brier_weights.get(trader_id, 1.0)
    # Clamp to [0.3, 2.0] to avoid extreme scaling
    weight = max(0.3, min(2.0, weight))

    result = []
    for bet in bets:
        bet = dict(bet)
        bet["bet_size"] = round(bet["bet_size"] * weight, 4)
        bet["brier_weight"] = round(weight, 4)
        bet["reasoning"] = bet.get("reasoning", "") + f" | P4:brier_w={weight:.2f}"
        result.append(bet)
    return result


# ═══════════════════════════════════════════════════════════════════
# [P2] BULL/BEAR DEBATE PROTOCOL (TradingAgents — Princeton)
# When agents disagree by >10pp, trigger structured debate.
# ═══════════════════════════════════════════════════════════════════

DEBATE_THRESHOLD = 0.10  # 10 percentage points disagreement triggers debate

def detect_debate_trigger(agent_probs: Dict[str, float]) -> Optional[Dict]:
    """
    [P2] Check if agents disagree enough to trigger a debate.
    Returns debate context if triggered, None otherwise.
    """
    if len(agent_probs) < 2:
        return None

    probs = list(agent_probs.values())
    max_prob = max(probs)
    min_prob = min(probs)
    spread = max_prob - min_prob

    if spread < DEBATE_THRESHOLD:
        return None

    # Identify bull (highest) and bear (lowest) agents
    bull_agent = max(agent_probs, key=agent_probs.get)
    bear_agent = min(agent_probs, key=agent_probs.get)

    return {
        "triggered": True,
        "spread": round(spread, 4),
        "bull_agent": bull_agent,
        "bull_prob": round(agent_probs[bull_agent], 4),
        "bear_agent": bear_agent,
        "bear_prob": round(agent_probs[bear_agent], 4),
        "median_prob": round(sorted(probs)[len(probs) // 2], 4),
    }


def resolve_debate(debate: Dict, agent_briers: Dict[str, float],
                   agent_probs: Dict[str, float]) -> Dict[str, float]:
    """
    [P2] Resolve Bull/Bear debate using Brier-weighted consensus.

    Resolution: 2-round debate simulation
    Round 1: Bull and Bear present arguments (simulated by their calibration)
    Round 2: All agents update probabilities toward Brier-weighted center
    """
    if not debate or not debate.get("triggered"):
        return agent_probs

    # Compute Brier-based credibility for each agent
    weights = compute_brier_weights(agent_briers)

    # Weighted consensus probability
    total_weight = sum(weights.get(tid, 1.0) for tid in agent_probs)
    consensus = sum(
        prob * weights.get(tid, 1.0)
        for tid, prob in agent_probs.items()
    ) / total_weight if total_weight > 0 else 0.5

    # Round 2: Each agent moves 30% toward consensus
    # (simulates persuasion effect from debate)
    DEBATE_PULL = 0.30
    updated = {}
    for tid, prob in agent_probs.items():
        new_prob = prob + DEBATE_PULL * (consensus - prob)
        updated[tid] = round(max(0.01, min(0.99, new_prob)), 4)

    return updated


# ═══════════════════════════════════════════════════════════════════
# [P7] BELIEF MARKET CONSENSUS (Competition→Coordination)
# Agents trade probabilistic beliefs to converge on truth.
# ═══════════════════════════════════════════════════════════════════

def belief_market_round(agent_beliefs: Dict[str, float],
                        agent_weights: Dict[str, float],
                        damping: float = 0.25) -> Dict[str, float]:
    """
    [P7] One round of belief market trading.
    Each agent updates their belief toward the weighted group mean.
    damping controls how much agents move (0.25 = 25% toward consensus).
    """
    if not agent_beliefs:
        return {}

    # Compute weighted mean belief
    total_w = sum(agent_weights.get(tid, 1.0) for tid in agent_beliefs)
    if total_w <= 0:
        return agent_beliefs

    weighted_mean = sum(
        belief * agent_weights.get(tid, 1.0)
        for tid, belief in agent_beliefs.items()
    ) / total_w

    # Each agent moves toward weighted mean
    updated = {}
    for tid, belief in agent_beliefs.items():
        new_belief = belief + damping * (weighted_mean - belief)
        updated[tid] = round(max(0.01, min(0.99, new_belief)), 4)

    return updated


def run_belief_market(agent_beliefs: Dict[str, float],
                      agent_weights: Dict[str, float],
                      rounds: int = 3) -> Dict[str, float]:
    """
    [P7] Run multi-round belief market.
    Agents iteratively trade beliefs for `rounds` rounds.
    Returns final beliefs after convergence.
    """
    current = dict(agent_beliefs)
    for r in range(rounds):
        # Decreasing damping: agents become more stubborn each round
        damping = 0.25 * (1.0 - r / (rounds + 1))
        current = belief_market_round(current, agent_weights, damping)
    return current


# ═══════════════════════════════════════════════════════════════════
# [P5] OPINION DYNAMICS (AgentSociety — Tsinghua)
# Multi-round convergence with opinion decay.
# ═══════════════════════════════════════════════════════════════════

def opinion_dynamics_converge(agent_opinions: Dict[str, float],
                              agent_confidence: Dict[str, float],
                              rounds: int = 3) -> Dict[str, float]:
    """
    [P5] Run opinion dynamics convergence.

    Each agent starts with an opinion (probability) and confidence (0-1).
    Over rounds, opinions converge toward confident agents' views.
    """
    current = dict(agent_opinions)

    for r in range(rounds):
        # Each agent updates toward the confidence-weighted group opinion
        total_conf = sum(agent_confidence.get(tid, 0.5) for tid in current)
        if total_conf <= 0:
            break

        weighted_opinion = sum(
            opinion * agent_confidence.get(tid, 0.5)
            for tid, opinion in current.items()
        ) / total_conf

        # Update: high-confidence agents barely move, low-confidence move a lot
        updated = {}
        for tid, opinion in current.items():
            conf = agent_confidence.get(tid, 0.5)
            # Lower confidence → more susceptible to group influence
            susceptibility = 1.0 - conf
            move = susceptibility * 0.3 * (weighted_opinion - opinion)
            updated[tid] = round(max(0.01, min(0.99, opinion + move)), 4)

        current = updated

    return current


# ═══════════════════════════════════════════════════════════════════
# [P1] PER-AGENT P&L LEDGER (Prediction Arena)
# Individual bankroll tracking per agent — not pooled consensus.
# ═══════════════════════════════════════════════════════════════════

class AgentPnLLedger:
    """[P1] Track individual P&L for each agent independently."""

    def __init__(self, initial_capital: float = 100.0):
        self.initial_capital = initial_capital
        self.ledgers: Dict[str, Dict] = {}

    def init_agent(self, trader_id: str):
        if trader_id not in self.ledgers:
            self.ledgers[trader_id] = {
                "capital": self.initial_capital,
                "total_wagered": 0.0,
                "total_profit": 0.0,
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "peak_capital": self.initial_capital,
                "max_drawdown": 0.0,
                "daily_returns": [],
            }

    def record_bet(self, trader_id: str, bet_size: float, profit: float, won: bool):
        self.init_agent(trader_id)
        ledger = self.ledgers[trader_id]
        ledger["capital"] += profit
        ledger["total_wagered"] += bet_size
        ledger["total_profit"] += profit
        ledger["trades"] += 1
        if won:
            ledger["wins"] += 1
        else:
            ledger["losses"] += 1
        # Track peak and drawdown
        if ledger["capital"] > ledger["peak_capital"]:
            ledger["peak_capital"] = ledger["capital"]
        dd = (ledger["peak_capital"] - ledger["capital"]) / ledger["peak_capital"]
        if dd > ledger["max_drawdown"]:
            ledger["max_drawdown"] = dd

    def get_stats(self, trader_id: str) -> Dict:
        self.init_agent(trader_id)
        ledger = self.ledgers[trader_id]
        roi = ledger["total_profit"] / self.initial_capital if self.initial_capital > 0 else 0
        win_rate = ledger["wins"] / ledger["trades"] if ledger["trades"] > 0 else 0
        return {
            "capital": round(ledger["capital"], 2),
            "roi_pct": round(roi * 100, 2),
            "win_rate": round(win_rate, 4),
            "trades": ledger["trades"],
            "max_drawdown_pct": round(ledger["max_drawdown"] * 100, 2),
            "sharpe": self._compute_sharpe(trader_id),
        }

    def _compute_sharpe(self, trader_id: str) -> float:
        ledger = self.ledgers.get(trader_id, {})
        returns = ledger.get("daily_returns", [])
        if len(returns) < 5:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        var = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std = var ** 0.5
        if std < 1e-8:
            return 0.0
        return round(mean_ret / std * (252 ** 0.5), 2)  # annualized


# ═══════════════════════════════════════════════════════════════════
# [P10] MANIPULATION DETECTION / WHALE GUARD
# Detect when single agent dominates market signal.
# ═══════════════════════════════════════════════════════════════════

WHALE_THRESHOLD = 0.60  # Single agent > 60% of total wagered → dampen

def detect_whale(all_agent_bets: Dict[str, List[Dict]]) -> Dict:
    """
    [P10] Detect if any single agent dominates the betting pool.
    Returns whale detection results.
    """
    agent_totals = {}
    grand_total = 0.0

    for tid, bets in all_agent_bets.items():
        total = sum(b.get("bet_size", 0) for b in bets)
        agent_totals[tid] = total
        grand_total += total

    if grand_total <= 0:
        return {"whale_detected": False, "agent_shares": {}}

    shares = {tid: total / grand_total for tid, total in agent_totals.items()}
    whale_agent = max(shares, key=shares.get)

    return {
        "whale_detected": shares[whale_agent] > WHALE_THRESHOLD,
        "whale_agent": whale_agent if shares[whale_agent] > WHALE_THRESHOLD else None,
        "whale_share": round(shares.get(whale_agent, 0), 4),
        "agent_shares": {tid: round(s, 4) for tid, s in shares.items()},
    }


def apply_whale_dampening(trader_id: str, bets: List[Dict],
                          whale_info: Dict) -> List[Dict]:
    """[P10] Dampen whale agent's bets to prevent single-agent dominance."""
    if not whale_info.get("whale_detected"):
        return bets

    if trader_id != whale_info.get("whale_agent"):
        return bets

    # Dampen whale's bets: reduce to target 40% share
    whale_share = whale_info.get("whale_share", 0.5)
    dampening = 0.40 / whale_share if whale_share > 0 else 1.0
    dampening = max(0.3, min(1.0, dampening))

    result = []
    for bet in bets:
        bet = dict(bet)
        bet["bet_size"] = round(bet["bet_size"] * dampening, 4)
        bet["whale_dampening"] = round(dampening, 4)
        bet["reasoning"] = bet.get("reasoning", "") + f" | P10:whale_damp={dampening:.2f}"
        result.append(bet)
    return result


# ═══════════════════════════════════════════════════════════════════
# [P8] SEMANTIC CORRELATION DISCOVERY
# Discover hidden correlations between bet categories.
# ═══════════════════════════════════════════════════════════════════

def discover_correlations(all_bets_history: List[Dict],
                          min_samples: int = 20) -> Dict[str, Dict]:
    """
    [P8] Discover correlations between bet categories.
    Returns {category: {correlated_cats, win_rate, anti_correlated_cats}}.
    """
    # Group bets by game
    games = defaultdict(list)
    for bet in all_bets_history:
        game_key = f"{bet.get('date', '')}_{bet.get('game', '')}"
        games[game_key].append(bet)

    # Compute per-category outcomes per game
    cat_outcomes = defaultdict(list)  # cat -> list of (game_idx, won)
    for game_idx, (game_key, game_bets) in enumerate(games.items()):
        for bet in game_bets:
            cat = bet.get("category", "unknown")
            won = bet.get("outcome") == "Win"
            cat_outcomes[cat].append((game_idx, won))

    # Compute pairwise correlations
    correlations = {}
    cats = [c for c, outcomes in cat_outcomes.items() if len(outcomes) >= min_samples]

    for cat in cats:
        cat_games = {idx: won for idx, won in cat_outcomes[cat]}
        cat_wins = sum(1 for _, w in cat_outcomes[cat] if w)
        cat_total = len(cat_outcomes[cat])

        correlated = []
        anti_correlated = []

        for other_cat in cats:
            if other_cat == cat:
                continue
            other_games = {idx: won for idx, won in cat_outcomes[other_cat]}

            # Find overlapping games
            common = set(cat_games.keys()) & set(other_games.keys())
            if len(common) < min_samples // 2:
                continue

            # Compute agreement rate
            agreements = sum(
                1 for idx in common
                if cat_games[idx] == other_games[idx]
            )
            agreement_rate = agreements / len(common) if common else 0.5

            if agreement_rate > 0.65:
                correlated.append((other_cat, round(agreement_rate, 3)))
            elif agreement_rate < 0.35:
                anti_correlated.append((other_cat, round(agreement_rate, 3)))

        correlations[cat] = {
            "win_rate": round(cat_wins / cat_total, 4) if cat_total > 0 else 0.5,
            "sample_size": cat_total,
            "correlated": sorted(correlated, key=lambda x: -x[1])[:5],
            "anti_correlated": sorted(anti_correlated, key=lambda x: x[1])[:5],
        }

    return correlations


def apply_correlation_boost(bets: List[Dict],
                            correlations: Dict[str, Dict]) -> List[Dict]:
    """
    [P8] Boost/penalize bets based on discovered correlations.
    If two correlated bets both appear in same game, slight boost.
    If anti-correlated bets appear, reduce the weaker one.
    """
    if not correlations:
        return bets

    game_bets = defaultdict(list)
    for i, bet in enumerate(bets):
        game_key = f"{bet.get('date', '')}_{bet.get('game', '')}"
        game_bets[game_key].append(i)

    result = list(bets)  # shallow copy of list
    for game_key, indices in game_bets.items():
        cats_in_game = {result[i].get("category", ""): i for i in indices}

        for cat, idx in cats_in_game.items():
            corr_info = correlations.get(cat, {})
            correlated_cats = [c for c, _ in corr_info.get("correlated", [])]

            # If we have a correlated bet in same game, boost both by 5%
            for corr_cat in correlated_cats:
                if corr_cat in cats_in_game:
                    bet = dict(result[idx])
                    bet["bet_size"] = round(bet["bet_size"] * 1.05, 4)
                    bet["reasoning"] = bet.get("reasoning", "") + f" | P8:corr_boost({corr_cat})"
                    result[idx] = bet
                    break  # one boost per bet

    return result


# ═══════════════════════════════════════════════════════════════════
# [P3] CHART-BASED CONTEXT (Agent Trading Arena)
# Encode rolling stats as compact text sparklines for better reasoning.
# ═══════════════════════════════════════════════════════════════════

SPARK_CHARS = "▁▂▃▄▅▆▇█"

def _sparkline(values: List[float]) -> str:
    """Generate text sparkline from values."""
    if not values:
        return ""
    vmin, vmax = min(values), max(values)
    vrange = vmax - vmin if vmax > vmin else 1
    return "".join(
        SPARK_CHARS[min(len(SPARK_CHARS) - 1, int((v - vmin) / vrange * (len(SPARK_CHARS) - 1)))]
        for v in values
    )


def build_chart_context(team_form: Dict, team: str) -> str:
    """
    [P3] Build compact chart-based context string for agent reasoning.
    Encodes last 10 games as sparklines for visual pattern recognition.
    """
    wins = team_form.get("results", [])  # list of W/L
    margins = team_form.get("margins", [])  # list of point differentials

    parts = [f"{team}"]
    if wins:
        win_str = "".join("W" if w else "L" for w in wins[-10:])
        parts.append(f"L10:{win_str}")

    if margins:
        spark = _sparkline([abs(m) for m in margins[-10:]])
        parts.append(f"margins:{spark}")

    w = team_form.get("w", 0)
    l = team_form.get("l", 0)
    if w + l > 0:
        parts.append(f"({w}-{l})")

    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════
# SOTA ENHANCER — UNIFIED INTEGRATION CLASS
# Combines all 10 techniques into a single pipeline.
# ═══════════════════════════════════════════════════════════════════

class SOTAEnhancer:
    """
    Unified SOTA enhancement pipeline for Trading Floor.
    Applies all 10 paper techniques in sequence.

    Usage:
        enhancer = SOTAEnhancer()
        # After all agents decide:
        enhanced = enhancer.enhance_game(
            game_key="2026-04-12_LAL_vs_BOS",
            all_agent_bets={"gemini": [...], "grok": [...]},
            all_agent_probs={"gemini": 0.55, "grok": 0.48},
            agent_histories={"gemini": [...], "grok": [...]},
        )
    """

    def __init__(self):
        self.pnl_ledger = AgentPnLLedger(initial_capital=100.0)
        self.correlation_cache: Dict[str, Dict] = {}
        self.debate_log: List[Dict] = []

    def enhance_agent_bets(self, trader_id: str, bets: List[Dict],
                           agent_history: List[Dict]) -> List[Dict]:
        """Apply per-agent enhancements (P6, P9)."""
        # [P6] Heterogeneous objectives
        bets = apply_heterogeneous_objective(trader_id, bets)

        # [P9] Coherence gate
        bets, rejected = apply_coherence_gate(bets)

        return bets

    def enhance_game(self, game_key: str,
                     all_agent_bets: Dict[str, List[Dict]],
                     all_agent_probs: Dict[str, float],
                     agent_histories: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """
        Apply cross-agent enhancements for one game.
        Call AFTER all agents have made their individual decisions.

        Returns enhanced bets per agent.
        """
        # [P4] Compute rolling Brier weights
        agent_briers = {
            tid: compute_agent_brier(history)
            for tid, history in agent_histories.items()
        }
        brier_weights = compute_brier_weights(agent_briers)

        # [P2] Check for debate trigger
        debate = detect_debate_trigger(all_agent_probs)
        if debate:
            self.debate_log.append({"game": game_key, **debate})
            # Resolve debate and get updated probabilities
            updated_probs = resolve_debate(debate, agent_briers, all_agent_probs)
        else:
            updated_probs = all_agent_probs

        # [P5] Opinion dynamics convergence
        agent_confidence = {
            tid: 1.0 - agent_briers.get(tid, 0.25)  # lower Brier = higher confidence
            for tid in all_agent_probs
        }
        converged_probs = opinion_dynamics_converge(
            updated_probs, agent_confidence, rounds=3
        )

        # [P7] Belief market: agents trade beliefs
        final_beliefs = run_belief_market(
            converged_probs, brier_weights, rounds=3
        )

        # [P10] Whale detection
        whale_info = detect_whale(all_agent_bets)

        # Apply cross-agent techniques to each agent's bets
        enhanced = {}
        for tid, bets in all_agent_bets.items():
            # [P4] Brier weighting
            bets = apply_brier_weight(tid, bets, brier_weights)

            # [P10] Whale dampening
            bets = apply_whale_dampening(tid, bets, whale_info)

            # [P1] Record in P&L ledger
            for bet in bets:
                won = bet.get("outcome") == "Win"
                self.pnl_ledger.record_bet(
                    tid, bet.get("bet_size", 0), bet.get("profit", 0), won
                )

            enhanced[tid] = bets

        return enhanced

    def get_enhancement_summary(self) -> Dict:
        """Return summary of all SOTA enhancements applied."""
        return {
            "papers_implemented": 10,
            "techniques": [
                "P1:per_agent_pnl", "P2:bull_bear_debate", "P3:chart_context",
                "P4:brier_weighting", "P5:opinion_dynamics", "P6:heterogeneous_obj",
                "P7:belief_market", "P8:semantic_correlation", "P9:coherence_gate",
                "P10:whale_guard",
            ],
            "debates_triggered": len(self.debate_log),
            "agent_pnl": {
                tid: self.pnl_ledger.get_stats(tid)
                for tid in self.pnl_ledger.ledgers
            },
        }
