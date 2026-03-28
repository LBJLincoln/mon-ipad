#!/usr/bin/env python3
"""
NBA Arena Confrontation System — Nomos42 v1.0
==============================================
Strategy confrontation engine: every sizing strategy vs every market.
Round-robin elimination with mutation/re-entry mechanics.

ZERO ML on VM — pure simulation/backtesting, numpy only.

Usage:
    python3 scripts/arena/arena_confrontation.py
    python3 scripts/arena/arena_confrontation.py --brier 0.2157 --games 934
    python3 scripts/arena/arena_confrontation.py --json-data path/to/games.json

Outputs:
    data/arena/arena-results.json   — full leaderboard + logs
    data/arena/arena-live.json      — current standings (dashboard)
"""

import os, sys, json, math, argparse, hashlib, time, random
from datetime import datetime, timezone
from collections import defaultdict

import numpy as np

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARENA_DIR   = os.path.join(REPO_ROOT, "data", "arena")
RESULTS_OUT = os.path.join(ARENA_DIR, "arena-results.json")
LIVE_OUT    = os.path.join(ARENA_DIR, "arena-live.json")
os.makedirs(ARENA_DIR, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
INITIAL_BANKROLL  = 100.0
ELIMINATION_PCT   = -0.20        # -20% triggers elimination
STANDARD_ODDS     = 1.909        # -110 both sides
SPREAD_SCALE      = 13.0
NBA_STD_SPREAD    = 11.0
NBA_STD_TOTAL     = 12.0
AVG_TOTAL_POINTS  = 224.0
MIN_STAKE         = 0.10
MAX_STAKE_PCT     = 0.25         # hard cap: no single bet > 25% of bankroll
MUTATION_TRIES    = 3            # how many param variants a dead strategy can re-enter as
SEASONS_SIM       = 1            # default simulation seasons
RNG_SEED          = 42

now_utc = lambda: datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — MARKET DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class Market:
    """A bet market: describes how to evaluate a bet given game data."""
    def __init__(self, name, tier, description):
        self.name        = name
        self.tier        = tier          # 1=game lines, 2=halves, 3=team totals, 4=props
        self.description = description

    def __repr__(self):
        return f"Market({self.name})"


MARKETS = [
    Market("ML_HOME",               1, "Moneyline — home team wins"),
    Market("ML_AWAY",               1, "Moneyline — away team wins"),
    Market("ATS_HOME",              1, "Against-the-spread — home covers"),
    Market("ATS_AWAY",              1, "Against-the-spread — away covers"),
    Market("OVER",                  1, "Game total — over"),
    Market("UNDER",                 1, "Game total — under"),
    Market("H1_ML_HOME",            2, "1st-half moneyline — home"),
    Market("H1_ML_AWAY",            2, "1st-half moneyline — away"),
    Market("H1_ATS_HOME",           2, "1st-half ATS — home covers"),
    Market("H1_ATS_AWAY",           2, "1st-half ATS — away covers"),
    Market("H1_OVER",               2, "1st-half total — over"),
    Market("H1_UNDER",              2, "1st-half total — under"),
    Market("H2_ML_HOME",            2, "2nd-half moneyline — home"),
    Market("H2_ML_AWAY",            2, "2nd-half moneyline — away"),
    Market("H2_ATS_HOME",           2, "2nd-half ATS — home covers"),
    Market("H2_ATS_AWAY",           2, "2nd-half ATS — away covers"),
    Market("H2_OVER",               2, "2nd-half total — over"),
    Market("H2_UNDER",              2, "2nd-half total — under"),
    Market("TEAM_TOTAL_HOME_OVER",  3, "Home team total — over"),
    Market("TEAM_TOTAL_AWAY_OVER",  3, "Away team total — over"),
    Market("VALUE_DOG",             3, "High-value underdog bet"),
    Market("PLAYER_PROP",           4, "Player prop — placeholder"),
]

MARKET_MAP = {m.name: m for m in MARKETS}

# ── Market groups used by strategies ─────────────────────────────────────────
MARKET_GROUPS = {
    "ALL":          [m.name for m in MARKETS if m.name != "PLAYER_PROP"],
    "GAME_LINES":   ["ML_HOME", "ML_AWAY", "ATS_HOME", "ATS_AWAY", "OVER", "UNDER"],
    "ML_ONLY":      ["ML_HOME", "ML_AWAY"],
    "ATS_ONLY":     ["ATS_HOME", "ATS_AWAY"],
    "TOTALS_ONLY":  ["OVER", "UNDER"],
    "HALVES":       ["H1_ML_HOME", "H1_ML_AWAY", "H1_ATS_HOME", "H1_ATS_AWAY",
                     "H1_OVER", "H1_UNDER", "H2_ML_HOME", "H2_ML_AWAY",
                     "H2_ATS_HOME", "H2_ATS_AWAY", "H2_OVER", "H2_UNDER"],
    "TEAM_TOTALS":  ["TEAM_TOTAL_HOME_OVER", "TEAM_TOTAL_AWAY_OVER"],
    "VALUE":        ["VALUE_DOG"],
    "CONSERVATIVE": ["ML_HOME", "ML_AWAY", "ATS_HOME", "ATS_AWAY"],
    "AGGRESSIVE":   ["ML_HOME", "ML_AWAY", "ATS_HOME", "ATS_AWAY", "OVER", "UNDER",
                     "VALUE_DOG", "TEAM_TOTAL_HOME_OVER", "TEAM_TOTAL_AWAY_OVER"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — SIZING STRATEGIES (the "gladiators")
# ═══════════════════════════════════════════════════════════════════════════════

class Strategy:
    """
    Base class for all sizing strategies.
    Each strategy decides how much to stake given a bet opportunity.

    Subclass and override `stake()`.
    """

    # Immutable identity set at construction
    name:        str = "Base"
    family:      str = "base"          # kelly / flat / prop / allin / martingale / conservative / aggressive
    markets:     list = None           # market names this strategy bets on (None = ALL)
    min_edge:    float = 0.02          # minimum required edge to place bet
    params:      dict = None           # strategy parameters (for mutation tracking)
    generation:  int = 0              # 0 = original, 1+ = mutant
    parent_name: str = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if self.markets is None:
            self.markets = MARKET_GROUPS["ALL"]
        if self.params is None:
            self.params = {}

    def stake(self, edge: float, odds: float, prob: float, bankroll: float) -> float:
        """Return stake amount. Must be >= 0."""
        raise NotImplementedError

    def applies_to(self, market_name: str) -> bool:
        return market_name in self.markets

    def describe(self) -> dict:
        return {
            "name":       self.name,
            "family":     self.family,
            "min_edge":   self.min_edge,
            "markets":    self.markets,
            "params":     self.params,
            "generation": self.generation,
            "parent":     self.parent_name,
        }

    def mutate(self, trial: int = 0) -> "Strategy":
        """Return a mutated clone. Override in subclasses for smarter mutation."""
        clone = self.__class__(**self.__dict__.copy())
        clone.generation  = self.generation + 1
        clone.parent_name = self.name
        clone.name        = f"{self.name}_mut{trial}"
        return clone

    def __repr__(self):
        return f"Strategy({self.name})"


# ── Kelly variants ────────────────────────────────────────────────────────────

class KellyStrategy(Strategy):
    family  = "kelly"

    def __init__(self, fraction=1.0, name="Kelly_Full", markets=None, min_edge=0.01,
                 **kwargs):
        self.fraction = fraction
        super().__init__(name=name, markets=markets, min_edge=min_edge,
                         params={"fraction": fraction}, **kwargs)

    def stake(self, edge, odds, prob, bankroll):
        b = odds - 1.0
        q = 1.0 - prob
        kelly_full = max(0.0, (b * prob - q) / b) if b > 0 else 0.0
        raw = bankroll * kelly_full * self.fraction
        return min(raw, bankroll * MAX_STAKE_PCT)

    def mutate(self, trial=0):
        deltas = [0.5, 0.75, 1.25, 1.5, 2.0]
        new_frac = max(0.05, min(2.0, self.fraction * deltas[trial % len(deltas)]))
        return KellyStrategy(
            fraction   = new_frac,
            name       = f"Kelly_{int(new_frac*100)}pct_mut{trial}",
            markets    = self.markets,
            min_edge   = self.min_edge,
            generation = self.generation + 1,
            parent_name= self.name,
        )


class KellyHalfStrategy(KellyStrategy):
    def __init__(self, **kwargs):
        super().__init__(fraction=0.5, name="Kelly_Half",
                         min_edge=0.01, **kwargs)


class KellyQuarterStrategy(KellyStrategy):
    def __init__(self, **kwargs):
        super().__init__(fraction=0.25, name="Kelly_Quarter",
                         min_edge=0.01, **kwargs)


# ── Flat bet ──────────────────────────────────────────────────────────────────

class FlatBetStrategy(Strategy):
    family = "flat"

    def __init__(self, amount=10.0, name="Flat_10", markets=None, min_edge=0.02,
                 **kwargs):
        self.amount = amount
        super().__init__(name=name, markets=markets, min_edge=min_edge,
                         params={"amount": amount}, **kwargs)

    def stake(self, edge, odds, prob, bankroll):
        return min(self.amount, bankroll * MAX_STAKE_PCT)

    def mutate(self, trial=0):
        scales = [0.5, 2.0, 5.0, 0.25, 10.0]
        new_amt = self.amount * scales[trial % len(scales)]
        return FlatBetStrategy(
            amount     = new_amt,
            name       = f"Flat_{new_amt:.0f}_mut{trial}",
            markets    = self.markets,
            min_edge   = self.min_edge,
            generation = self.generation + 1,
            parent_name= self.name,
        )


# ── Proportional ──────────────────────────────────────────────────────────────

class ProportionalStrategy(Strategy):
    family = "proportional"

    def __init__(self, pct=0.01, name="Prop_1pct", markets=None, min_edge=0.02,
                 **kwargs):
        self.pct = pct
        super().__init__(name=name, markets=markets, min_edge=min_edge,
                         params={"pct": pct}, **kwargs)

    def stake(self, edge, odds, prob, bankroll):
        return min(bankroll * self.pct, bankroll * MAX_STAKE_PCT)

    def mutate(self, trial=0):
        scales = [0.5, 2.0, 5.0, 0.25, 3.0]
        new_pct = max(0.001, min(0.20, self.pct * scales[trial % len(scales)]))
        return ProportionalStrategy(
            pct        = new_pct,
            name       = f"Prop_{new_pct*100:.1f}pct_mut{trial}",
            markets    = self.markets,
            min_edge   = self.min_edge,
            generation = self.generation + 1,
            parent_name= self.name,
        )


# ── AllIn Daily Best ──────────────────────────────────────────────────────────

class AllInDailyStrategy(Strategy):
    """Commit full bankroll to the single best bet each day."""
    family   = "allin"
    name     = "AllIn_Daily"
    min_edge = 0.03

    def __init__(self, markets=None, min_edge=0.03, **kwargs):
        super().__init__(markets=markets, min_edge=min_edge,
                         params={}, **kwargs)
        self._day_best  = None   # (edge, odds, prob, market) of today's best
        self._day_label = None   # date string

    def stake(self, edge, odds, prob, bankroll):
        # All-in: return full bankroll (caller should ensure this is the day's best)
        return min(bankroll, bankroll * MAX_STAKE_PCT)  # capped at MAX_STAKE_PCT for safety

    def mutate(self, trial=0):
        new_edge = [0.04, 0.05, 0.025, 0.06, 0.035][trial % 5]
        s = AllInDailyStrategy(
            markets    = self.markets,
            min_edge   = new_edge,
            generation = self.generation + 1,
            parent_name= self.name,
        )
        s.name = f"AllIn_Daily_minedge{new_edge:.3f}_mut{trial}"
        return s


# ── Martingale ────────────────────────────────────────────────────────────────

class MartingaleStrategy(Strategy):
    """Double stake after each loss; reset on win."""
    family       = "martingale"
    name         = "Martingale"
    min_edge     = 0.02

    def __init__(self, base_stake=5.0, markets=None, min_edge=0.02, **kwargs):
        self.base_stake  = base_stake
        self._loss_count = 0
        self._last_stake = base_stake
        super().__init__(name="Martingale", markets=markets, min_edge=min_edge,
                         params={"base_stake": base_stake}, **kwargs)

    def stake(self, edge, odds, prob, bankroll):
        raw = self.base_stake * (2 ** self._loss_count)
        return min(raw, bankroll * MAX_STAKE_PCT, bankroll)

    def record_result(self, won: bool):
        if won:
            self._loss_count = 0
        else:
            self._loss_count += 1

    def mutate(self, trial=0):
        scales = [0.5, 2.0, 0.25, 5.0, 1.5]
        new_base = max(1.0, self.base_stake * scales[trial % len(scales)])
        s = MartingaleStrategy(
            base_stake = new_base,
            markets    = self.markets,
            min_edge   = self.min_edge,
            generation = self.generation + 1,
            parent_name= self.name,
        )
        s.name = f"Martingale_base{new_base:.0f}_mut{trial}"
        return s


# ── Anti-Martingale ───────────────────────────────────────────────────────────

class AntiMartingaleStrategy(Strategy):
    """Double stake after each win; reset on loss (ride winning streaks)."""
    family      = "anti_martingale"
    name        = "AntiMartingale"
    min_edge    = 0.02

    def __init__(self, base_stake=5.0, max_doubles=4, markets=None, min_edge=0.02,
                 **kwargs):
        self.base_stake   = base_stake
        self.max_doubles  = max_doubles
        self._win_count   = 0
        super().__init__(name="AntiMartingale", markets=markets, min_edge=min_edge,
                         params={"base_stake": base_stake, "max_doubles": max_doubles},
                         **kwargs)

    def stake(self, edge, odds, prob, bankroll):
        doubles = min(self._win_count, self.max_doubles)
        raw = self.base_stake * (2 ** doubles)
        return min(raw, bankroll * MAX_STAKE_PCT, bankroll)

    def record_result(self, won: bool):
        if won:
            self._win_count += 1
        else:
            self._win_count = 0

    def mutate(self, trial=0):
        scales = [0.5, 2.0, 0.25, 5.0, 1.5]
        new_base = max(1.0, self.base_stake * scales[trial % len(scales)])
        s = AntiMartingaleStrategy(
            base_stake = new_base,
            max_doubles= self.max_doubles,
            markets    = self.markets,
            min_edge   = self.min_edge,
            generation = self.generation + 1,
            parent_name= self.name,
        )
        s.name = f"AntiMartingale_base{new_base:.0f}_mut{trial}"
        return s


# ── Conservative / Aggressive by edge filter ─────────────────────────────────

class ConservativeStrategy(KellyStrategy):
    """High-edge-only: min_edge=5%, Kelly_25pct, conservative markets."""
    def __init__(self, **kwargs):
        super().__init__(
            fraction  = 0.25,
            name      = "Conservative",
            markets   = MARKET_GROUPS["CONSERVATIVE"],
            min_edge  = 0.05,
            **kwargs
        )
    def mutate(self, trial=0):
        new_edges = [0.04, 0.06, 0.08, 0.03, 0.07]
        s = ConservativeStrategy(generation=self.generation+1, parent_name=self.name)
        s.min_edge = new_edges[trial % len(new_edges)]
        s.name = f"Conservative_minedge{s.min_edge:.2f}_mut{trial}"
        return s


class AggressiveStrategy(KellyStrategy):
    """Low-edge-threshold: min_edge=1%, Kelly_50pct, all markets."""
    def __init__(self, **kwargs):
        super().__init__(
            fraction  = 0.50,
            name      = "Aggressive",
            markets   = MARKET_GROUPS["AGGRESSIVE"],
            min_edge  = 0.01,
            **kwargs
        )
    def mutate(self, trial=0):
        new_fracs = [0.75, 1.0, 0.25, 1.25, 0.40]
        new_edges = [0.005, 0.02, 0.015, 0.008, 0.03]
        s = AggressiveStrategy(generation=self.generation+1, parent_name=self.name)
        s.fraction = new_fracs[trial % len(new_fracs)]
        s.min_edge = new_edges[trial % len(new_edges)]
        s.params   = {"fraction": s.fraction}
        s.name     = f"Aggressive_f{int(s.fraction*100)}pct_e{s.min_edge:.3f}_mut{trial}"
        return s


# ── Master strategy registry ──────────────────────────────────────────────────

def build_default_strategies() -> list:
    return [
        KellyStrategy(fraction=1.00, name="Kelly_Full",    min_edge=0.01,
                      markets=MARKET_GROUPS["ALL"]),
        KellyHalfStrategy(markets=MARKET_GROUPS["ALL"]),
        KellyQuarterStrategy(markets=MARKET_GROUPS["ALL"]),
        FlatBetStrategy(amount=10.0, name="Flat_10",
                        markets=MARKET_GROUPS["GAME_LINES"]),
        ProportionalStrategy(pct=0.01, name="Prop_1pct",
                             markets=MARKET_GROUPS["ALL"]),
        ProportionalStrategy(pct=0.02, name="Prop_2pct",
                             markets=MARKET_GROUPS["ALL"]),
        ProportionalStrategy(pct=0.05, name="Prop_5pct",
                             markets=MARKET_GROUPS["ALL"]),
        AllInDailyStrategy(markets=MARKET_GROUPS["ML_ONLY"],  name="AllIn_Daily"),
        MartingaleStrategy(base_stake=5.0,  markets=MARKET_GROUPS["ML_ONLY"]),
        AntiMartingaleStrategy(base_stake=5.0, markets=MARKET_GROUPS["ML_ONLY"]),
        ConservativeStrategy(),
        AggressiveStrategy(),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — GAME SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def prob_to_spread(p_home: float) -> float | None:
    if p_home <= 0.01 or p_home >= 0.99:
        return None
    return -SPREAD_SCALE * math.log(p_home / (1.0 - p_home))


def cover_prob(pred_spread: float, line_spread: float) -> float:
    z = -(line_spread + pred_spread) / NBA_STD_SPREAD
    return 1.0 / (1.0 + math.exp(-1.7 * z))


def over_prob(pred_total: float, line_total: float) -> float:
    z = (pred_total - line_total) / NBA_STD_TOTAL
    return 1.0 / (1.0 + math.exp(-1.7 * z))


def simulate_game(p_home: float, rng: np.random.Generator) -> dict:
    """
    Generate a synthetic game outcome consistent with p_home probability.

    Returns a dict with all fields needed by generate_bets().
    """
    # Draw actual winner
    home_win = rng.random() < p_home

    # Draw margin: ~N(spread, 11) where spread derived from p_home
    pred_spread = prob_to_spread(p_home) or 0.0
    # Actual margin = home_score - away_score  (positive = home wins)
    true_margin = float(rng.normal(-pred_spread, NBA_STD_SPREAD))
    if (true_margin > 0) != home_win:
        true_margin = -true_margin  # force consistency with winner draw
    margin = int(round(true_margin))

    # Draw total points: N(224, 12)
    total_pts = int(max(140, round(float(rng.normal(AVG_TOTAL_POINTS, NBA_STD_TOTAL)))))

    home_score = (total_pts + margin) // 2
    away_score = total_pts - home_score

    # Half splits (roughly 47% / 53%)
    h1_share = float(rng.uniform(0.44, 0.50))
    h1_total = int(round(total_pts * h1_share))
    h2_total = total_pts - h1_total

    h1_margin_frac = float(rng.normal(0.55, 0.15))  # first-half margin slightly noisier
    h1_margin = int(round(margin * h1_margin_frac))
    h2_margin = margin - h1_margin

    return {
        "home_win":  home_win,
        "margin":    margin,
        "total_pts": total_pts,
        "home_score": home_score,
        "away_score": away_score,
        "h1_margin": h1_margin,
        "h2_margin": h2_margin,
        "h1_total":  h1_total,
        "h2_total":  h2_total,
    }


def synthetic_odds(p_home: float, spread_mean: float = 0.0,
                   total_mean: float = 224.0) -> dict:
    """
    Generate book-like odds from a home-win probability.
    Adds a small vig and noise to simulate realistic lines.
    """
    # Book probability includes vig (~5%)
    vig = 0.025
    book_p_home = max(0.01, min(0.99, p_home + random.gauss(0, 0.02)))
    book_p_away = 1.0 - book_p_home

    def decimal_from_prob(p, v):
        return (1.0 - v) / p

    odds_home = decimal_from_prob(book_p_home, vig)
    odds_away = decimal_from_prob(book_p_away, vig)

    pred_spread = prob_to_spread(book_p_home) or 0.0
    spread = round(pred_spread + random.gauss(0, 0.5), 1)  # book adds noise
    total  = round(total_mean + random.gauss(0, 2.0), 1)

    # Half-time lines: mechanical formula used by books
    h2_spread = round(spread * 0.45 + random.gauss(0, 0.3), 1)
    h2_total  = round(total  * 0.48 + random.gauss(0, 1.5), 1)

    return {
        "odds_home": odds_home,
        "odds_away": odds_away,
        "ml_home":   None,
        "ml_away":   None,
        "spread":    spread,
        "total":     total,
        "h2_spread": h2_spread,
        "h2_total":  h2_total,
        "favored":   "home" if spread < 0 else "away",
    }


def generate_bets(p_home: float, real_odds: dict, outcome: dict,
                  min_edge: float = 0.02) -> list:
    """
    For a single game, generate all candidate bets with edge > min_edge.

    Returns list of dicts:
        { type, odds, model_prob, edge, won }
    """
    bets      = []
    p_away    = 1.0 - p_home
    pred_sp   = prob_to_spread(p_home)
    if pred_sp is None:
        return bets

    pred_total = AVG_TOTAL_POINTS + abs(pred_sp) * 0.15
    margin     = outcome["margin"]
    total_pts  = outcome["total_pts"]
    h1_margin  = outcome.get("h1_margin", 0)
    h2_margin  = outcome.get("h2_margin", 0)
    h1_pts     = outcome.get("h1_total",  0)
    h2_pts     = outcome.get("h2_total",  0)
    home_score = outcome.get("home_score", 0)
    away_score = outcome.get("away_score", 0)

    odds_h = real_odds.get("odds_home")
    odds_a = real_odds.get("odds_away")
    spread = real_odds.get("spread")
    total  = real_odds.get("total")
    h2_sp  = real_odds.get("h2_spread")
    h2_to  = real_odds.get("h2_total")
    fav    = real_odds.get("favored", "home")

    def signed_spread(raw):
        if raw is None:
            return None
        return abs(float(raw)) if fav == "away" else -abs(float(raw))

    def add(market_type, odds_val, model_p, won):
        if odds_val and 1.01 < odds_val <= 25.0:
            edge = model_p * odds_val - 1.0
            if edge > min_edge:
                bets.append({"type": market_type, "odds": odds_val,
                             "model_prob": model_p, "edge": edge, "won": won})

    # ── Tier 1: Game Lines ────────────────────────────────────────────────────
    add("ML_HOME", odds_h, p_home, outcome["home_win"])
    add("ML_AWAY", odds_a, p_away, not outcome["home_win"])

    if spread is not None:
        line = signed_spread(spread)
        cp_h = cover_prob(pred_sp, line)
        add("ATS_HOME", STANDARD_ODDS, cp_h, margin > -line)
        add("ATS_AWAY", STANDARD_ODDS, 1.0-cp_h, margin < -line)

    if total is not None:
        op = over_prob(pred_total, float(total))
        if total_pts != float(total):
            add("OVER",  STANDARD_ODDS, op,     total_pts > float(total))
            add("UNDER", STANDARD_ODDS, 1.0-op, total_pts < float(total))

    # ── Tier 2: Half-time markets ─────────────────────────────────────────────
    # 2H
    if h2_sp is not None:
        h2_line   = signed_spread(h2_sp)
        h2_pred_sp = pred_sp * 0.45
        cp_h2 = cover_prob(h2_pred_sp, h2_line)
        add("H2_ATS_HOME", STANDARD_ODDS, cp_h2,    h2_margin > -h2_line)
        add("H2_ATS_AWAY", STANDARD_ODDS, 1.0-cp_h2, h2_margin < -h2_line)
        # 2H ML (from cover prob → rough ML prob)
        add("H2_ML_HOME", odds_h * 0.90 if odds_h else None,
            cp_h2 * 1.05, h2_margin > 0)
        add("H2_ML_AWAY", odds_a * 0.90 if odds_a else None,
            (1.0-cp_h2) * 1.05, h2_margin < 0)

    if h2_to is not None:
        h2_pred_total = pred_total * 0.48
        h2op = over_prob(h2_pred_total, float(h2_to))
        if h2_pts != float(h2_to):
            add("H2_OVER",  STANDARD_ODDS, h2op,     h2_pts > float(h2_to))
            add("H2_UNDER", STANDARD_ODDS, 1.0-h2op, h2_pts < float(h2_to))

    # 1H (derived from full - 2H)
    if spread is not None and h2_sp is not None:
        full_line = signed_spread(spread)
        h2_line2  = signed_spread(h2_sp)
        h1_line   = full_line - h2_line2
        h1_pred_sp = pred_sp * 0.55
        cp_h1 = cover_prob(h1_pred_sp, h1_line)
        add("H1_ATS_HOME", STANDARD_ODDS, cp_h1,     h1_margin > -h1_line)
        add("H1_ATS_AWAY", STANDARD_ODDS, 1.0-cp_h1, h1_margin < -h1_line)
        add("H1_ML_HOME",  odds_h * 0.85 if odds_h else None,
            cp_h1 * 1.05, h1_margin > 0)
        add("H1_ML_AWAY",  odds_a * 0.85 if odds_a else None,
            (1.0-cp_h1) * 1.05, h1_margin < 0)

    if total is not None and h2_to is not None:
        h1_line_total = float(total) - float(h2_to)
        h1_pred_total = pred_total * 0.52
        h1op = over_prob(h1_pred_total, h1_line_total)
        if h1_pts != h1_line_total:
            add("H1_OVER",  STANDARD_ODDS, h1op,     h1_pts > h1_line_total)
            add("H1_UNDER", STANDARD_ODDS, 1.0-h1op, h1_pts < h1_line_total)

    # ── Tier 3: Team totals ───────────────────────────────────────────────────
    if total is not None:
        mkt_total = float(total)
        home_pred_pts = (pred_total / 2) + (-pred_sp / 2)
        away_pred_pts = (pred_total / 2) + (pred_sp / 2)
        sp_val = signed_spread(spread) or 0.0
        home_line_pts = mkt_total / 2 + (-sp_val / 2)
        away_line_pts = mkt_total / 2 + (sp_val / 2)
        tt_h_op = over_prob(home_pred_pts, home_line_pts)
        tt_a_op = over_prob(away_pred_pts, away_line_pts)
        if home_score != home_line_pts:
            add("TEAM_TOTAL_HOME_OVER", STANDARD_ODDS, tt_h_op, home_score > home_line_pts)
        if away_score != away_line_pts:
            add("TEAM_TOTAL_AWAY_OVER", STANDARD_ODDS, tt_a_op, away_score > away_line_pts)

    # ── Value dog ─────────────────────────────────────────────────────────────
    if odds_h and odds_h > 3.0 and p_home > 0.28:
        edge = p_home * odds_h - 1.0
        if edge > min_edge * 2:
            bets.append({"type": "VALUE_DOG", "odds": odds_h,
                         "model_prob": p_home, "edge": edge,
                         "won": outcome["home_win"]})
    if odds_a and odds_a > 3.0 and p_away > 0.28:
        edge = p_away * odds_a - 1.0
        if edge > min_edge * 2:
            bets.append({"type": "VALUE_DOG", "odds": odds_a,
                         "model_prob": p_away, "edge": edge,
                         "won": not outcome["home_win"]})

    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — GLADIATOR (per-strategy runtime state)
# ═══════════════════════════════════════════════════════════════════════════════

class Gladiator:
    """
    Wraps a Strategy with live bankroll tracking and performance metrics.
    Immutable once eliminated — spawns Mutant children via remodel().
    """

    def __init__(self, strategy: Strategy, initial_bankroll: float = INITIAL_BANKROLL):
        self.strategy         = strategy
        self.bankroll         = initial_bankroll
        self.initial_bankroll = initial_bankroll
        self.peak_bankroll    = initial_bankroll

        # Per-round snapshots  [{"round": n, "bankroll": x, "bets": k, ...}]
        self.round_history: list = []

        # Cumulative stats
        self.total_bets      = 0
        self.wins            = 0
        self.losses          = 0
        self.total_wagered   = 0.0
        self.total_profit    = 0.0
        self.bet_history: list = []   # [{market, edge, odds, stake, won, profit}]

        # Elimination
        self.eliminated      = False
        self.eliminated_round = None
        self.elimination_reason: str = ""
        self.remodeled_as: list = []   # names of mutant children

    @property
    def name(self):
        return self.strategy.name

    @property
    def roi(self):
        return self.total_profit / self.total_wagered if self.total_wagered > 0 else 0.0

    @property
    def win_rate(self):
        denom = self.wins + self.losses
        return self.wins / denom if denom > 0 else 0.0

    @property
    def drawdown_pct(self):
        return (self.peak_bankroll - self.bankroll) / self.peak_bankroll

    @property
    def roi_pct(self):
        return (self.bankroll / self.initial_bankroll - 1.0) * 100.0

    def sharpe(self) -> float:
        """Approximate Sharpe: mean(daily_ret) / std(daily_ret) * sqrt(252)."""
        if len(self.round_history) < 5:
            return 0.0
        rets = []
        for i in range(1, len(self.round_history)):
            prev = self.round_history[i-1]["bankroll"]
            curr = self.round_history[i]["bankroll"]
            if prev > 0:
                rets.append((curr - prev) / prev)
        if not rets or np.std(rets) == 0:
            return 0.0
        return float(np.mean(rets) / np.std(rets) * math.sqrt(252))

    def max_drawdown(self) -> float:
        """Maximum peak-to-trough drawdown fraction."""
        if not self.round_history:
            return 0.0
        peak = self.initial_bankroll
        max_dd = 0.0
        for snap in self.round_history:
            b = snap["bankroll"]
            if b > peak:
                peak = b
            dd = (peak - b) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def place_bet(self, bet: dict, round_num: int) -> float:
        """
        Evaluate a bet candidate against this strategy.
        Returns profit (positive or negative) or 0 if bet not placed.
        """
        if self.eliminated:
            return 0.0
        if not self.strategy.applies_to(bet["type"]):
            return 0.0
        if bet["edge"] < self.strategy.min_edge:
            return 0.0
        if self.bankroll < MIN_STAKE:
            return 0.0

        stake = self.strategy.stake(bet["edge"], bet["odds"],
                                    bet["model_prob"], self.bankroll)
        stake = max(MIN_STAKE, stake)
        stake = min(stake, self.bankroll)  # can't bet more than you have

        profit = stake * (bet["odds"] - 1.0) if bet["won"] else -stake

        self.bankroll      += profit
        self.total_wagered += stake
        self.total_profit  += profit
        self.total_bets    += 1

        if bet["won"]:
            self.wins += 1
        else:
            self.losses += 1

        if self.bankroll > self.peak_bankroll:
            self.peak_bankroll = self.bankroll

        # Notify martingale strategies of outcome
        if hasattr(self.strategy, "record_result"):
            self.strategy.record_result(bet["won"])

        self.bet_history.append({
            "round":      round_num,
            "market":     bet["type"],
            "edge":       round(bet["edge"], 5),
            "odds":       round(bet["odds"], 4),
            "stake":      round(stake, 4),
            "won":        bet["won"],
            "profit":     round(profit, 4),
            "bankroll":   round(self.bankroll, 4),
        })
        return profit

    def check_elimination(self, round_num: int) -> bool:
        """Return True if this gladiator should be eliminated this round."""
        if self.eliminated:
            return False
        drop = (self.bankroll - self.initial_bankroll) / self.initial_bankroll
        if drop <= ELIMINATION_PCT:
            self.eliminated       = True
            self.eliminated_round = round_num
            self.elimination_reason = (
                f"Bankroll dropped {drop*100:.1f}% "
                f"(${self.bankroll:.2f} / ${self.initial_bankroll:.2f})"
            )
            return True
        return False

    def snapshot_round(self, round_num: int, bets_this_round: int):
        self.round_history.append({
            "round":    round_num,
            "bankroll": round(self.bankroll, 4),
            "bets":     bets_this_round,
            "roi_pct":  round(self.roi_pct, 3),
        })

    def remodel(self, arena_round: int) -> list:
        """
        Spawn mutated children (up to MUTATION_TRIES).
        Returns list of new Gladiators.
        """
        children = []
        for trial in range(MUTATION_TRIES):
            mutant_strat = self.strategy.mutate(trial)
            mutant_strat.generation = self.strategy.generation + 1
            g = Gladiator(mutant_strat, self.bankroll * 0.5)  # start with 50% of remaining
            g.initial_bankroll = g.bankroll
            g.peak_bankroll    = g.bankroll
            children.append(g)
            self.remodeled_as.append(mutant_strat.name)
        return children

    def leaderboard_entry(self) -> dict:
        return {
            "name":           self.name,
            "family":         self.strategy.family,
            "generation":     self.strategy.generation,
            "parent":         self.strategy.parent_name,
            "bankroll":       round(self.bankroll, 4),
            "initial_bankroll": round(self.initial_bankroll, 4),
            "roi_pct":        round(self.roi_pct, 3),
            "sharpe":         round(self.sharpe(), 4),
            "max_drawdown":   round(self.max_drawdown(), 4),
            "win_rate":       round(self.win_rate, 4),
            "total_bets":     self.total_bets,
            "wins":           self.wins,
            "losses":         self.losses,
            "total_wagered":  round(self.total_wagered, 4),
            "total_profit":   round(self.total_profit, 4),
            "eliminated":     self.eliminated,
            "eliminated_round": self.eliminated_round,
            "remodeled_as":   self.remodeled_as,
            "markets":        sorted(set(b["market"] for b in self.bet_history)),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — ARENA ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class Arena:
    """
    Orchestrates the round-robin confrontation.

    Architecture:
        - Each "round" = 1 week of NBA games (~7 games on weekday, more on weekend)
        - Rounds accumulate over a simulated season (~26 rounds = 6 months)
        - Every active gladiator bets on every game in a round
        - Elimination at round end if -20% drawdown
        - Eliminated strategies spawn mutants that re-enter next round
    """

    GAMES_PER_WEEK = 11    # average NBA games per week in a full season

    def __init__(self, strategies: list, brier: float = 0.225,
                 n_rounds: int = 26, seed: int = RNG_SEED):
        self.brier    = brier
        self.n_rounds = n_rounds
        self.rng      = np.random.default_rng(seed)

        # Build gladiators
        self.gladiators: dict[str, Gladiator] = {
            s.name: Gladiator(s) for s in strategies
        }
        self.round_num    = 0
        self.elimination_log: list = []
        self.round_log:       list = []
        self.market_stats: dict    = defaultdict(lambda: {
            "bets": 0, "wins": 0, "total_profit": 0.0,
        })

        print(f"\n{'='*70}")
        print(f"  ARENA CONFRONTATION — Nomos42 NBA Quant v1.0")
        print(f"  Model Brier: {brier:.5f} | Rounds: {n_rounds} | "
              f"Strategies: {len(strategies)}")
        print(f"  Elimination threshold: {ELIMINATION_PCT*100:.0f}% drawdown")
        print(f"{'='*70}")

    def _p_home_from_brier(self) -> float:
        """
        Sample a realistic home-win probability for a game.
        We draw from a Beta distribution calibrated to match the Brier score.
        Brier score for a perfect classifier ≈ 0 as p→deterministic.
        Real p_home values are roughly Beta(3, 3) shifted to [0.35, 0.75].
        """
        # Centered around 0.60 (home-court advantage)
        raw = float(self.rng.beta(3.5, 2.5))
        return max(0.35, min(0.85, raw * 0.50 + 0.35))

    def _add_prediction_noise(self, true_p: float) -> float:
        """
        Convert true probability to model-predicted probability by adding
        noise proportional to model's Brier score.
        Lower Brier = less noise = sharper predictions.
        """
        # Noise std ≈ sqrt(brier) * calibration_factor
        noise_std = math.sqrt(self.brier) * 0.6
        noisy = true_p + float(self.rng.normal(0, noise_std))
        return max(0.03, min(0.97, noisy))

    def run_round(self) -> dict:
        """Simulate one week of games. Returns round summary."""
        self.round_num += 1
        n_games = int(self.rng.integers(
            self.GAMES_PER_WEEK - 3,
            self.GAMES_PER_WEEK + 8
        ))
        round_bets     = defaultdict(int)  # strategy → bets placed this round
        round_profits  = defaultdict(float)

        for _ in range(n_games):
            true_p   = self._p_home_from_brier()
            model_p  = self._add_prediction_noise(true_p)
            outcome  = simulate_game(true_p, self.rng)
            odds     = synthetic_odds(model_p)

            # Gather ALL candidate bets (union of all min_edge requirements)
            global_min_edge = min(g.strategy.min_edge
                                  for g in self.gladiators.values()
                                  if not g.eliminated)
            candidates = generate_bets(model_p, odds, outcome,
                                       min_edge=global_min_edge * 0.5)

            # Each gladiator evaluates every candidate independently
            for g in list(self.gladiators.values()):
                if g.eliminated:
                    continue
                for bet in candidates:
                    profit = g.place_bet(bet, self.round_num)
                    if profit != 0.0 or g.total_bets > 0:
                        round_bets[g.name] += 1 if profit != 0.0 else 0
                        round_profits[g.name] += profit

                        # Track market stats
                        if profit != 0.0:
                            ms = self.market_stats[bet["type"]]
                            ms["bets"] += 1
                            ms["wins"] += 1 if bet["won"] else 0
                            ms["total_profit"] += round(profit, 6)

        # Snapshot round for all active gladiators
        for g in self.gladiators.values():
            if not g.eliminated:
                g.snapshot_round(self.round_num, round_bets[g.name])

        # Elimination pass
        eliminated_this_round = []
        new_entries: list[Gladiator] = []

        for g in list(self.gladiators.values()):
            if g.check_elimination(self.round_num):
                event = {
                    "round":   self.round_num,
                    "gladiator": g.name,
                    "bankroll":  round(g.bankroll, 4),
                    "reason":    g.elimination_reason,
                    "roi_pct":   round(g.roi_pct, 3),
                    "total_bets": g.total_bets,
                }
                self.elimination_log.append(event)
                eliminated_this_round.append(g.name)
                print(f"  [R{self.round_num:02d}] ELIMINATED: {g.name:30s} "
                      f"${g.bankroll:.2f} ({g.roi_pct:+.1f}%) — {g.elimination_reason}")

                # Remodel: spawn mutants
                if g.bankroll > MIN_STAKE:
                    mutants = g.remodel(self.round_num)
                    for m in mutants:
                        new_entries.append(m)
                        print(f"           -> Remodeled as: {m.name}")

        # Register mutants for next round
        for m in new_entries:
            self.gladiators[m.name] = m

        active = sum(1 for g in self.gladiators.values() if not g.eliminated)
        summary = {
            "round":          self.round_num,
            "games":          n_games,
            "active":         active,
            "eliminated":     eliminated_this_round,
            "new_entries":    [m.name for m in new_entries],
            "top_bankroll":   round(max(
                (g.bankroll for g in self.gladiators.values() if not g.eliminated),
                default=0.0
            ), 4),
        }
        self.round_log.append(summary)
        return summary

    def run(self):
        """Run all rounds."""
        print(f"\nStarting {self.n_rounds} rounds ({self.n_rounds * self.GAMES_PER_WEEK}~ games)\n")
        t0 = time.time()

        for _ in range(self.n_rounds):
            rsum = self.run_round()
            active = rsum["active"]
            top_br = rsum["top_bankroll"]
            print(f"  Round {self.round_num:02d}/{self.n_rounds}  "
                  f"games={rsum['games']:3d}  active={active:3d}  "
                  f"top=${top_br:.2f}  "
                  f"elim={len(rsum['eliminated'])}  "
                  f"new={len(rsum['new_entries'])}")

        elapsed = time.time() - t0
        print(f"\nArena complete: {elapsed:.1f}s")

    def leaderboard(self) -> list:
        """Return all gladiators sorted by ROI desc (active first)."""
        entries = [g.leaderboard_entry() for g in self.gladiators.values()]
        entries.sort(key=lambda e: (not e["eliminated"], e["roi_pct"]), reverse=True)
        return entries

    def market_leaderboard(self) -> list:
        stats = []
        for market, s in self.market_stats.items():
            n = s["bets"]
            stats.append({
                "market":     market,
                "tier":       MARKET_MAP.get(market, Market(market, 0, "")).tier,
                "bets":       n,
                "wins":       s["wins"],
                "win_rate":   round(s["wins"] / n, 4) if n > 0 else 0.0,
                "total_profit": round(s["total_profit"], 4),
                "roi_pct":    round(s["total_profit"] /
                              max(1.0, n * STANDARD_ODDS * 10.0) * 100, 3),
            })
        stats.sort(key=lambda x: x["total_profit"], reverse=True)
        return stats

    def results_dict(self) -> dict:
        lb = self.leaderboard()
        active = [e for e in lb if not e["eliminated"]]
        return {
            "meta": {
                "generated_at":    now_utc(),
                "model_brier":     self.brier,
                "rounds":          self.n_rounds,
                "initial_bankroll": INITIAL_BANKROLL,
                "elimination_threshold_pct": ELIMINATION_PCT * 100,
                "seed":            RNG_SEED,
                "games_simulated": sum(r["games"] for r in self.round_log),
            },
            "leaderboard":     lb,
            "active_count":    len(active),
            "eliminated_count": len([e for e in lb if e["eliminated"]]),
            "elimination_log": self.elimination_log,
            "round_history":   self.round_log,
            "market_stats":    self.market_leaderboard(),
            "champion": active[0] if active else lb[0] if lb else None,
        }

    def live_dict(self) -> dict:
        lb = self.leaderboard()
        active = [e for e in lb if not e["eliminated"]]
        top5   = active[:5]
        return {
            "updated_at":    now_utc(),
            "model_brier":   self.brier,
            "round":         self.round_num,
            "total_rounds":  self.n_rounds,
            "active":        len(active),
            "eliminated":    len([e for e in lb if e["eliminated"]]),
            "champion":      active[0]["name"]  if active else "N/A",
            "champion_roi":  active[0]["roi_pct"] if active else 0.0,
            "top5": [
                {
                    "rank":     i + 1,
                    "name":     e["name"],
                    "roi_pct":  e["roi_pct"],
                    "bankroll": e["bankroll"],
                    "sharpe":   e["sharpe"],
                    "win_rate": e["win_rate"],
                    "bets":     e["total_bets"],
                }
                for i, e in enumerate(top5)
            ],
            "latest_eliminations": self.elimination_log[-5:],
            "market_top3": self.market_leaderboard()[:3],
        }

    def save(self):
        results = self.results_dict()
        with open(RESULTS_OUT, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved: {RESULTS_OUT}")

        live = self.live_dict()
        with open(LIVE_OUT, "w") as f:
            json.dump(live, f, indent=2)
        print(f"Saved: {LIVE_OUT}")

        return results, live

    def print_summary(self):
        lb = self.leaderboard()
        active = [e for e in lb if not e["eliminated"]]
        elim   = [e for e in lb if e["eliminated"]]

        print(f"\n{'='*70}")
        print(f"  ARENA FINAL LEADERBOARD — {len(active)} active / {len(elim)} eliminated")
        print(f"{'='*70}")
        print(f"  {'#':3}  {'Name':30s}  {'ROI%':>7}  {'Sharpe':>6}  {'MaxDD':>6}  "
              f"{'WinRt':>5}  {'Bets':>5}  {'$':>8}")
        print(f"  {'-'*67}")

        for i, e in enumerate(lb[:20], 1):
            status = "X" if e["eliminated"] else " "
            gen    = f"g{e['generation']}" if e["generation"] > 0 else "  "
            print(f"  {i:3}  {e['name'][:28]:30s}  "
                  f"{e['roi_pct']:>+7.1f}%  "
                  f"{e['sharpe']:>6.2f}  "
                  f"{e['max_drawdown']*100:>5.1f}%  "
                  f"{e['win_rate']*100:>4.1f}%  "
                  f"{e['total_bets']:>5}  "
                  f"${e['bankroll']:>7.2f}  {status}{gen}")

        print(f"\n  Champion: {active[0]['name'] if active else 'N/A'}")
        if active:
            c = active[0]
            print(f"  ROI: {c['roi_pct']:+.2f}%  Sharpe: {c['sharpe']:.3f}  "
                  f"MaxDD: {c['max_drawdown']*100:.1f}%  Bets: {c['total_bets']}")

        print(f"\n  Top markets by profit:")
        for ms in self.market_leaderboard()[:5]:
            print(f"    {ms['market']:30s}  {ms['bets']:4d} bets  "
                  f"WR={ms['win_rate']*100:.1f}%  profit={ms['total_profit']:+.2f}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — REAL DATA INTEGRATION (optional)
# ═══════════════════════════════════════════════════════════════════════════════

def load_games_from_json(path: str) -> list:
    """Load game records from a JSON file (backtest output format)."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("games", data.get("predictions", []))


def run_arena_on_real_data(arena: Arena, games: list):
    """
    Replace synthetic simulation with real game data.
    Each game must have: predicted_home_prob, home_win, margin, total_pts.
    Optional: h1_margin, h2_margin, h1_total, h2_total, odds fields.
    """
    # Group games into weekly batches
    games_sorted = sorted(games, key=lambda g: g.get("game_date", g.get("date", "")))

    batch: list = []
    batches: list = []
    current_week = None

    for g in games_sorted:
        date_str = g.get("game_date", g.get("date", ""))[:10]
        try:
            from datetime import date
            d = date.fromisoformat(date_str)
            week = d.isocalendar()[1]
        except Exception:
            week = 0

        if week != current_week and batch:
            batches.append(batch)
            batch = []
        current_week = week
        batch.append(g)
    if batch:
        batches.append(batch)

    print(f"\nReal data mode: {len(games)} games, {len(batches)} weekly batches")

    arena.n_rounds = len(batches)

    for batch in batches:
        arena.round_num += 1
        round_bets = defaultdict(int)

        for g in batch:
            p_home = float(g.get("predicted_home_prob",
                           g.get("p_home", g.get("home_prob", 0.55))))
            outcome = {
                "home_win":  bool(g.get("home_win", g.get("actual_home_win", True))),
                "margin":    int(g.get("margin", g.get("score_diff", 5))),
                "total_pts": int(g.get("total_pts", g.get("total_points", 220))),
                "home_score": int(g.get("home_score", 110)),
                "away_score": int(g.get("away_score", 105)),
                "h1_margin": int(g.get("h1_margin", 0)),
                "h2_margin": int(g.get("h2_margin", 0)),
                "h1_total":  int(g.get("h1_total", 0)),
                "h2_total":  int(g.get("h2_total", 0)),
            }
            # Build odds from game record or synthetic
            if "odds_home" in g or "ml_home" in g:
                real_odds = {
                    "odds_home": g.get("odds_home"),
                    "odds_away": g.get("odds_away"),
                    "spread":    g.get("spread"),
                    "total":     g.get("total"),
                    "h2_spread": g.get("h2_spread"),
                    "h2_total":  g.get("h2_total_line"),
                    "favored":   g.get("favored", "home"),
                }
            else:
                real_odds = synthetic_odds(p_home)

            global_min_edge = min(
                g2.strategy.min_edge
                for g2 in arena.gladiators.values()
                if not g2.eliminated
            )
            candidates = generate_bets(p_home, real_odds, outcome,
                                       min_edge=global_min_edge * 0.5)

            for glad in arena.gladiators.values():
                if glad.eliminated:
                    continue
                for bet in candidates:
                    profit = glad.place_bet(bet, arena.round_num)
                    if profit != 0.0:
                        round_bets[glad.name] += 1
                        ms = arena.market_stats[bet["type"]]
                        ms["bets"] += 1
                        ms["wins"] += 1 if bet["won"] else 0
                        ms["total_profit"] += profit

        for glad in arena.gladiators.values():
            if not glad.eliminated:
                glad.snapshot_round(arena.round_num, round_bets[glad.name])

        # Elimination
        new_entries = []
        for glad in list(arena.gladiators.values()):
            if glad.check_elimination(arena.round_num):
                arena.elimination_log.append({
                    "round":      arena.round_num,
                    "gladiator":  glad.name,
                    "bankroll":   round(glad.bankroll, 4),
                    "reason":     glad.elimination_reason,
                    "roi_pct":    round(glad.roi_pct, 3),
                    "total_bets": glad.total_bets,
                })
                if glad.bankroll > MIN_STAKE:
                    for m in glad.remodel(arena.round_num):
                        new_entries.append(m)

        for m in new_entries:
            arena.gladiators[m.name] = m

        active = sum(1 for g in arena.gladiators.values() if not g.eliminated)
        arena.round_log.append({
            "round":  arena.round_num,
            "games":  len(batch),
            "active": active,
            "eliminated": [g.name for g in arena.gladiators.values()
                           if g.eliminated_round == arena.round_num],
            "new_entries": [m.name for m in new_entries],
            "top_bankroll": round(max(
                (g.bankroll for g in arena.gladiators.values() if not g.eliminated),
                default=0.0
            ), 4),
        })

        print(f"  Round {arena.round_num:02d}/{arena.n_rounds}  "
              f"games={len(batch):3d}  active={active:3d}  "
              f"top=${arena.round_log[-1]['top_bankroll']:.2f}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Arena Confrontation System — Nomos42 NBA Quant"
    )
    parser.add_argument("--brier",    type=float, default=0.22447,
                        help="Model Brier score (default=0.22447 walk-forward avg)")
    parser.add_argument("--rounds",   type=int,   default=26,
                        help="Number of simulation rounds (default=26 = 1 season)")
    parser.add_argument("--games",    type=int,   default=None,
                        help="Override total games (for reporting only)")
    parser.add_argument("--seed",     type=int,   default=RNG_SEED,
                        help=f"RNG seed (default={RNG_SEED})")
    parser.add_argument("--json-data", type=str,  default=None,
                        help="Path to real games JSON for data-driven mode")
    parser.add_argument("--quiet",    action="store_true",
                        help="Suppress per-bet output")
    return parser.parse_args()


def main():
    args = parse_args()

    strategies = build_default_strategies()

    print(f"Strategies in arena ({len(strategies)}):")
    for s in strategies:
        print(f"  {s.name:30s}  family={s.family:15s}  min_edge={s.min_edge:.3f}  "
              f"markets={len(s.markets)}")

    arena = Arena(
        strategies = strategies,
        brier      = args.brier,
        n_rounds   = args.rounds,
        seed       = args.seed,
    )

    if args.json_data:
        if not os.path.exists(args.json_data):
            print(f"ERROR: JSON data file not found: {args.json_data}")
            sys.exit(1)
        games = load_games_from_json(args.json_data)
        print(f"Loaded {len(games)} games from {args.json_data}")
        run_arena_on_real_data(arena, games)
    else:
        arena.run()

    arena.print_summary()
    results, live = arena.save()

    print(f"\n{'='*70}")
    print(f"  Output files:")
    print(f"    {RESULTS_OUT}")
    print(f"    {LIVE_OUT}")
    print(f"\n  Champion:  {live['champion']}  ROI={live['champion_roi']:+.1f}%")
    print(f"  Active:    {live['active']}  Eliminated: {live['eliminated']}")
    print(f"{'='*70}\n")

    return results


if __name__ == "__main__":
    main()
