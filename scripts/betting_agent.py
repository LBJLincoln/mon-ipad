#!/usr/bin/env python3
"""
Nomos42 NBA Betting Agent — Portfolio-Level Kelly Optimization

Hedge fund-grade bet sizing: allocates FULL bankroll across diversified
portfolio of bets each night using optimal strategies.

Strategies:
  1. fractional_kelly  — current baseline (f=0.35 per bet, independent)
  2. portfolio_kelly   — simultaneous Kelly (maximize log-growth across all bets)
  3. mean_variance     — Markowitz-style (maximize return per unit variance)
  4. drawdown_kelly    — Kelly with max-drawdown constraint
  5. risk_parity       — equal risk contribution from each bet

Usage:
  python3 betting_agent.py --strategy portfolio_kelly --compare-all
  python3 betting_agent.py --dry-run

Input:  predictions-today.json + live-odds.json + bankroll-state.json
Output: bet-slip-YYYY-MM-DD.json + updated bankroll-state.json
"""

import json, os, sys, argparse, math
from datetime import datetime, date
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm as _norm

# ═══════════════════════════════════════
# SECTION 1: CONFIG
# ═══════════════════════════════════════

STRATEGIES = ["fractional_kelly", "portfolio_kelly", "mean_variance", "drawdown_kelly", "risk_parity"]
DEFAULT_STRATEGY = "portfolio_kelly"

# Portfolio-level caps (validated by arXiv:2107.08827 — 16,000 NBA games)
MAX_PORTFOLIO_EXPOSURE = 0.25   # 25% max nightly exposure (research-validated)
MAX_SINGLE_BET_FRACTION = 0.025 # 2.5% max per position (quarter-Kelly cap)
MIN_EV_THRESHOLD = 0.10         # 10% minimum EV — CRITICAL (MDPI Info 2026: #1 ROI filter)
MIN_EDGE_THRESHOLD = 0.05       # 5% minimum edge (Grok value_hunter uses 0.05)
MIN_ODDS = 1.80                 # Raised from 1.30 → 1.80 (Grok: underdog_specialist, min 2.2)
MAX_ODDS = 8.0                  # cap at 8.0 (reduce variance on longshots)
# Strategy alignment note (Apr 4 audit):
# Grok's winning combo = value_hunter + underdog_specialist (NOT half_kelly)
# 93% of Grok's profit comes from alt_spread at ~2.50 odds
# spread_home is NEGATIVE for all 5 TF traders — avoid
MIN_STAKE_DOLLARS = 0.50

# Drawdown constraint
MAX_DRAWDOWN_TARGET = 0.20      # max 20% single-night worst-case loss

# Kelly fraction by model quality (arXiv:2107.08827)
# Brier > 0.22: eighth-Kelly (0.125)
# Brier 0.21-0.22: quarter-Kelly (0.25)
# Brier < 0.21: third-Kelly (0.33)
CURRENT_BRIER = 0.21570
KELLY_FRACTION = 0.25 if CURRENT_BRIER < 0.22 else 0.125

# Correlation assumptions
SAME_GAME_MARKET_CORR = 0.30
CROSS_GAME_CORR = 0.05

# Paths
MON_DIR = Path("/home/termius/mon-ipad")
NBA_AGENT_DIR = Path("/home/termius/nomos-nba-agent")
DATA_DIR = MON_DIR / "data" / "nba-agent"
PREDICTIONS_PATH = NBA_AGENT_DIR / "data" / "nba-agent" / "predictions-today.json"
ODDS_PATH = DATA_DIR / "live-odds.json"
BANKROLL_PATH = DATA_DIR / "bankroll-state.json"

# ═══════════════════════════════════════
# SECTION 2: INPUT PARSING
# ═══════════════════════════════════════

TEAM_MAP = {
    "GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS",
    "WSH": "WAS", "UTAH": "UTA", "PHL": "PHI", "PHO": "PHX",
    "Golden State Warriors": "GSW", "Los Angeles Lakers": "LAL",
    "Los Angeles Clippers": "LAC", "New York Knicks": "NYK",
    "New Orleans Pelicans": "NOP", "San Antonio Spurs": "SAS",
    "Oklahoma City Thunder": "OKC", "Portland Trail Blazers": "POR",
    "Brooklyn Nets": "BKN", "Boston Celtics": "BOS",
    "Philadelphia 76ers": "PHI", "Washington Wizards": "WAS",
    "Toronto Raptors": "TOR", "Milwaukee Bucks": "MIL",
    "Indiana Pacers": "IND", "Cleveland Cavaliers": "CLE",
    "Detroit Pistons": "DET", "Chicago Bulls": "CHI",
    "Miami Heat": "MIA", "Atlanta Hawks": "ATL",
    "Charlotte Hornets": "CHA", "Orlando Magic": "ORL",
    "Minnesota Timberwolves": "MIN", "Denver Nuggets": "DEN",
    "Utah Jazz": "UTA", "Phoenix Suns": "PHX",
    "Sacramento Kings": "SAC", "Dallas Mavericks": "DAL",
    "Houston Rockets": "HOU", "Memphis Grizzlies": "MEM",
}

# Reverse map: nickname / city / partial → abbreviation.
# Replaces the broken name.upper()[:3] fallback (e.g. "San Antonio"→"SAN", "LA Clippers"→"LA ").
REVERSE_TEAM_MAP = {abbr: abbr for abbr in TEAM_MAP.values()}
REVERSE_TEAM_MAP.update({
    # Team nicknames
    "Hawks": "ATL", "Celtics": "BOS", "Nets": "BKN", "Hornets": "CHA",
    "Bulls": "CHI", "Cavaliers": "CLE", "Mavericks": "DAL", "Nuggets": "DEN",
    "Pistons": "DET", "Warriors": "GSW", "Rockets": "HOU", "Pacers": "IND",
    "Clippers": "LAC", "Lakers": "LAL", "Grizzlies": "MEM", "Heat": "MIA",
    "Bucks": "MIL", "Timberwolves": "MIN", "Pelicans": "NOP", "Knicks": "NYK",
    "Thunder": "OKC", "Magic": "ORL", "76ers": "PHI", "Sixers": "PHI",
    "Suns": "PHX", "Blazers": "POR", "Kings": "SAC", "Spurs": "SAS",
    "Raptors": "TOR", "Jazz": "UTA", "Wizards": "WAS",
    # City-only variants
    "Atlanta": "ATL", "Boston": "BOS", "Brooklyn": "BKN", "Charlotte": "CHA",
    "Chicago": "CHI", "Cleveland": "CLE", "Dallas": "DAL", "Denver": "DEN",
    "Detroit": "DET", "Houston": "HOU", "Indiana": "IND", "Memphis": "MEM",
    "Miami": "MIA", "Milwaukee": "MIL", "Minnesota": "MIN", "Orlando": "ORL",
    "Philadelphia": "PHI", "Phoenix": "PHX", "Portland": "POR",
    "Sacramento": "SAC", "Toronto": "TOR", "Washington": "WAS",
    # Multi-word city / name variants that [:3] truncation gets wrong
    "Golden State": "GSW", "LA Clippers": "LAC", "LA Lakers": "LAL",
    "New Orleans": "NOP", "New York": "NYK", "Oklahoma City": "OKC",
    "San Antonio": "SAS", "Utah": "UTA",
})

def normalize_team(name):
    if not name:
        return ""
    name = name.strip()
    # Direct match (full name or short alias in TEAM_MAP)
    if name in TEAM_MAP:
        return TEAM_MAP[name]
    # Already a valid abbreviation
    for full, abbr in TEAM_MAP.items():
        if abbr == name or name.upper() == abbr:
            return abbr
    # Nickname / city / partial — case-insensitive REVERSE_TEAM_MAP lookup
    if name in REVERSE_TEAM_MAP:
        return REVERSE_TEAM_MAP[name]
    name_upper = name.upper()
    for key, abbr in REVERSE_TEAM_MAP.items():
        if key.upper() == name_upper:
            return abbr
    # Last resort: return uppercased as-is (do NOT truncate to [:3])
    return name_upper


# ═══════════════════════════════════════
# SECTION 1b: DERIVED MARKET CALCULATORS
# ═══════════════════════════════════════

def calc_overtime_candidates(home, away, prob_home, game_idx,
                             offered_ot_yes_odds=None, offered_ot_no_odds=None):
    """
    Overtime probability derived from win-probability curve.
    Formula: p_ot = 0.063 * (1 - 4*(prob_home - 0.5)^2)
    Peaks at 6.3% for 50/50 games; drops as matchup becomes lopsided.
    Books use a flat ~6% base rate — we condition on the matchup.
    Default market lines if no live odds: OT Yes ~15.0, OT No ~1.04
    """
    p_ot = 0.063 * (1.0 - 4.0 * (prob_home - 0.5) ** 2)
    p_ot = max(0.01, min(0.20, p_ot))   # clamp to [1%, 20%]
    p_no_ot = 1.0 - p_ot

    yes_odds = float(offered_ot_yes_odds) if offered_ot_yes_odds else 15.0
    no_odds  = float(offered_ot_no_odds)  if offered_ot_no_odds  else 1.04

    candidates = []
    for side, prob, odds in [("ot_yes", p_ot, yes_odds), ("ot_no", p_no_ot, no_odds)]:
        if odds <= 0 or prob <= 0:
            continue
        implied = 1.0 / odds
        edge = prob - implied
        ev   = prob * odds - 1.0
        b    = odds - 1.0
        kelly = max(0.0, (b * prob - (1.0 - prob)) / b) if b > 0 else 0.0
        is_eligible = (ev >= MIN_EV_THRESHOLD and edge >= MIN_EDGE_THRESHOLD
                       and kelly > 0
                       and MIN_ODDS <= odds <= MAX_ODDS
                       and 0.10 <= implied <= 0.90
                       and abs(prob - implied) <= 0.50)
        # Sanity: OT Yes at 15.0 has implied=6.7% — allow implied down to 4% for OT
        # (override the 10% floor for this market only)
        if side == "ot_yes":
            is_eligible = (ev >= MIN_EV_THRESHOLD and edge >= MIN_EDGE_THRESHOLD
                           and kelly > 0
                           and 5.0 <= odds <= MAX_ODDS
                           and abs(prob - implied) <= 0.50)
        candidates.append({
            "id": f"{home}_{away}_ot_{side}",
            "game": f"{away} @ {home}",
            "market": "overtime",
            "side": side,
            "team": f"{home}/{away}",
            "model_prob": round(prob, 4),
            "decimal_odds": round(odds, 3),
            "implied_prob": round(implied, 4),
            "edge": round(edge, 4),
            "ev": round(ev, 4),
            "full_kelly": round(kelly, 4),
            "game_idx": game_idx,
            "is_eligible": is_eligible,
        })
    return candidates


# Margin band endpoints (inclusive low, exclusive high) and display labels
_MARGIN_BANDS = [
    (1,  6,  "1-5pts"),
    (6,  11, "6-10pts"),
    (11, 16, "11-15pts"),
    (16, 21, "16-20pts"),
    (21, 999, "21+pts"),
]

# Typical market odds for each margin band (home win / away win)
# These are approximate — real books post them; we use fallbacks if no live line.
_MARGIN_BAND_DEFAULT_ODDS = [4.5, 3.2, 3.8, 5.0, 4.0]


def calc_margin_band_candidates(home, away, prob_home, game_idx, offered_odds=None):
    """
    Margin-of-victory band probabilities derived from win probability.
    expected_margin = (prob_home - 0.5) * 24   (12 pt swing over full range)
    std_margin = 11.5 pts  (NBA historical σ)
    For away team: mirror the expected margin (negate).
    offered_odds: optional dict keyed by f"{team}_{band_label}" → decimal odds
    """
    exp_margin_home = (prob_home - 0.5) * 24.0
    sigma = 11.5

    candidates = []
    for team_label, sign in [(home, 1), (away, -1)]:
        mu = exp_margin_home * sign   # positive = team wins
        for idx, (lo, hi, label) in enumerate(_MARGIN_BANDS):
            # P(team wins by lo..hi-1 pts) = P(lo <= margin < hi | margin > 0)
            # We compute unconditional P(lo <= margin < hi) directly:
            p_band = _norm.cdf(hi, loc=mu, scale=sigma) - _norm.cdf(lo, loc=mu, scale=sigma)
            p_band = max(1e-4, min(0.999, p_band))

            bet_key = f"{team_label}_{label}"
            odds = float(offered_odds.get(bet_key, _MARGIN_BAND_DEFAULT_ODDS[idx])) \
                   if offered_odds else _MARGIN_BAND_DEFAULT_ODDS[idx]
            if odds <= 0:
                continue

            implied = 1.0 / odds
            edge = p_band - implied
            ev   = p_band * odds - 1.0
            b    = odds - 1.0
            kelly = max(0.0, (b * p_band - (1.0 - p_band)) / b) if b > 0 else 0.0
            is_eligible = (ev >= MIN_EV_THRESHOLD and edge >= MIN_EDGE_THRESHOLD
                           and kelly > 0
                           and MIN_ODDS <= odds <= MAX_ODDS
                           and 0.05 <= implied <= 0.95
                           and abs(p_band - implied) <= 0.50)
            candidates.append({
                "id": f"{home}_{away}_margin_{team_label}_{label}",
                "game": f"{away} @ {home}",
                "market": "margin_band",
                "side": f"{team_label} {label}",
                "team": team_label,
                "model_prob": round(p_band, 4),
                "decimal_odds": round(odds, 3),
                "implied_prob": round(implied, 4),
                "edge": round(edge, 4),
                "ev": round(ev, 4),
                "full_kelly": round(kelly, 4),
                "game_idx": game_idx,
                "is_eligible": is_eligible,
            })
    return candidates


def calc_team_total_candidates(home, away, prob_home, game_idx,
                               offered_total=None, offered_spread=None,
                               odds_home_over=None, odds_home_under=None,
                               odds_away_over=None, odds_away_under=None):
    """
    Team totals derived from game total + spread.
    team_total_home ≈ total * (1 + spread/total) / 2
    team_total_away ≈ total - team_total_home
    If no odds data, we skip (can't price without a line).
    Line is always the midpoint; model probability is derived from the
    win-probability-implied spread vs the book line.
    """
    # Need a total and a spread to derive team totals
    if offered_total is None or offered_total <= 0:
        return []
    total = float(offered_total)

    # Spread derived from win probability if not provided
    # prob_home → implied spread (home perspective): spread ≈ (0.5 - prob_home)*24
    spread = float(offered_spread) if offered_spread is not None else (0.5 - prob_home) * 24.0

    team_total_home = total * (1.0 + spread / total) / 2.0
    team_total_away = total - team_total_home

    # Typical σ for team total is ~7 pts (NBA)
    sigma_team = 7.0

    candidates = []
    for team_label, tt_line in [(home, team_total_home), (away, team_total_away)]:
        # Model: actual scoring ~ N(tt_line, sigma_team²)
        # Under = P(score < tt_line) ≈ 0.5 by construction; we need an edge
        # over the book's line. If book line equals our estimate → no edge.
        # We compute P(over) and P(under) vs book's stated line.
        # Without a distinct book line we can't find an edge, so skip.
        book_line = tt_line  # book agrees with our estimate by construction
        p_over  = 1.0 - _norm.cdf(book_line, loc=tt_line, scale=sigma_team)
        p_under = _norm.cdf(book_line, loc=tt_line, scale=sigma_team)

        if team_label == home:
            ov_odds = float(odds_home_over)  if odds_home_over  else 1.91
            un_odds = float(odds_home_under) if odds_home_under else 1.91
        else:
            ov_odds = float(odds_away_over)  if odds_away_over  else 1.91
            un_odds = float(odds_away_under) if odds_away_under else 1.91

        for side_label, prob, odds in [
            (f"{team_label} TT Over",  p_over,  ov_odds),
            (f"{team_label} TT Under", p_under, un_odds),
        ]:
            if odds <= 0 or prob <= 0:
                continue
            implied = 1.0 / odds
            edge = prob - implied
            ev   = prob * odds - 1.0
            b    = odds - 1.0
            kelly = max(0.0, (b * prob - (1.0 - prob)) / b) if b > 0 else 0.0
            is_eligible = (ev >= MIN_EV_THRESHOLD and edge >= MIN_EDGE_THRESHOLD
                           and kelly > 0
                           and MIN_ODDS <= odds <= MAX_ODDS
                           and 0.10 <= implied <= 0.90
                           and abs(prob - implied) <= 0.50)
            side_key = "over" if "Over" in side_label else "under"
            candidates.append({
                "id": f"{home}_{away}_tt_{team_label}_{side_key}",
                "game": f"{away} @ {home}",
                "market": "team_total",
                "side": side_label,
                "team": team_label,
                "model_prob": round(prob, 4),
                "decimal_odds": round(odds, 3),
                "implied_prob": round(implied, 4),
                "edge": round(edge, 4),
                "ev": round(ev, 4),
                "full_kelly": round(kelly, 4),
                "game_idx": game_idx,
                "is_eligible": is_eligible,
            })
    return candidates


def load_inputs(bankroll_override=None):
    """Load predictions, odds, and bankroll. Return (candidates, bankroll)."""

    # Load bankroll
    bankroll = 305.64  # default
    if BANKROLL_PATH.exists():
        try:
            bs = json.loads(BANKROLL_PATH.read_text())
            bankroll = float(bs.get("balance", bs.get("bankroll", 305.64)))
        except:
            pass
    if bankroll_override:
        bankroll = bankroll_override

    # Load predictions
    predictions = []
    for path in [PREDICTIONS_PATH, DATA_DIR / "predictions-today.json"]:
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if isinstance(data, dict):
                    predictions = data.get("predictions", data.get("games", []))
                elif isinstance(data, list):
                    predictions = data
                if predictions:
                    break
            except:
                pass

    # Load live odds
    odds_by_game = {}
    if ODDS_PATH.exists():
        try:
            odds_data = json.loads(ODDS_PATH.read_text())
            if isinstance(odds_data, dict):
                odds_list = odds_data.get("games", odds_data.get("odds", []))
            else:
                odds_list = odds_data if isinstance(odds_data, list) else []

            for game in odds_list:
                home = normalize_team(game.get("home_team", ""))
                away = normalize_team(game.get("away_team", ""))
                if home and away:
                    key = f"{home}_{away}"
                    # Extract best odds from bookmakers
                    best_home_odds = 0
                    best_away_odds = 0
                    for bm in game.get("bookmakers", []):
                        for market in bm.get("markets", []):
                            if market.get("key") == "h2h":
                                for outcome in market.get("outcomes", []):
                                    price = outcome.get("price", 0)
                                    name = normalize_team(outcome.get("name", ""))
                                    if name == home and price > best_home_odds:
                                        best_home_odds = price
                                    elif name == away and price > best_away_odds:
                                        best_away_odds = price
                    # Also extract totals and spreads if present
                    best_total = 0.0
                    best_over_odds = 0.0
                    best_under_odds = 0.0
                    best_spread_home = None
                    for bm in game.get("bookmakers", []):
                        for market in bm.get("markets", []):
                            mkey = market.get("key", "")
                            if mkey == "totals":
                                for outcome in market.get("outcomes", []):
                                    pt = float(outcome.get("point", 0) or 0)
                                    price = float(outcome.get("price", 0) or 0)
                                    nm = outcome.get("name", "").lower()
                                    if pt > 0 and best_total == 0:
                                        best_total = pt
                                    if "over" in nm and price > best_over_odds:
                                        best_over_odds = price
                                    elif "under" in nm and price > best_under_odds:
                                        best_under_odds = price
                            elif mkey == "spreads":
                                for outcome in market.get("outcomes", []):
                                    nm_team = normalize_team(outcome.get("name", ""))
                                    pt = float(outcome.get("point", 0) or 0)
                                    if nm_team == home and best_spread_home is None:
                                        # home spread: negative = home fav, positive = underdog
                                        best_spread_home = pt
                    odds_by_game[key] = {
                        "home_odds": best_home_odds,
                        "away_odds": best_away_odds,
                        "home": home,
                        "away": away,
                        "total": best_total,
                        "total_over_odds": best_over_odds,
                        "total_under_odds": best_under_odds,
                        "spread_home": best_spread_home,
                    }
        except Exception as e:
            print(f"[ODDS] Failed to load: {e}")

    # Build candidates
    candidates = []
    for i, pred in enumerate(predictions):
        home = normalize_team(pred.get("home_team", pred.get("home", "")))
        away = normalize_team(pred.get("away_team", pred.get("away", "")))
        model_prob = float(pred.get("predicted_home_prob", pred.get("home_win_prob", pred.get("prob", 0))))

        if not home or not away or model_prob <= 0:
            continue

        # Apply post-hoc calibration before Kelly sizing (D5: raw ECE=0.2758)
        # Only calibrate if not already calibrated upstream by predict_today.py
        if not pred.get("calibrated"):
            try:
                import sys as _sys
                _sys.path.insert(0, '/home/termius/mon-ipad/scripts')
                from calibration import IsotonicCalibration as _IsoCal
                _cal = _IsoCal()
                model_prob = _cal.calibrate(model_prob)
            except Exception:
                pass  # Use raw prob if calibration unavailable

        # Guard: skip phantom games where both teams resolve to the same abbreviation
        if home == away:
            print(f"[PHANTOM] Skipping phantom game: {away} @ {home} (same team)")
            continue

        # Get odds
        key = f"{home}_{away}"
        odds_info = odds_by_game.get(key, {})
        home_odds = float(pred.get("market_odds_home", odds_info.get("home_odds", 0)) or 0)
        away_odds = float(pred.get("market_odds_away", odds_info.get("away_odds", 0)) or 0)

        # Generate candidates for both sides
        for side, prob, odds in [("home", model_prob, home_odds), ("away", 1 - model_prob, away_odds)]:
            if odds < MIN_ODDS or odds > MAX_ODDS or prob <= 0:
                continue

            implied = 1.0 / odds
            edge = prob - implied
            ev = prob * odds - 1.0
            b = odds - 1.0

            # Sanity gate: skip if model and market diverge by >50pp (team mismatch or
            # corrupted odds) or if market implied probability is out of [10%, 90%].
            if not (0.10 <= implied <= 0.90) or abs(prob - implied) > 0.50:
                print(f"[SANITY] {away} @ {home} ({side}): skipping — "
                      f"model={prob:.2%} market={implied:.2%} "
                      f"(gap={abs(prob-implied):.2%}, implied={'OUT-OF-RANGE' if not (0.10 <= implied <= 0.90) else 'ok'})")
                continue

            # Full Kelly
            if b > 0:
                kelly = max(0, (b * prob - (1 - prob)) / b)
            else:
                kelly = 0

            is_eligible = ev >= MIN_EV_THRESHOLD and edge >= MIN_EDGE_THRESHOLD and kelly > 0

            candidates.append({
                "id": f"{home}_{away}_h2h_{side}",
                "game": f"{away} @ {home}",
                "market": "h2h",
                "side": side,
                "team": home if side == "home" else away,
                "model_prob": round(prob, 4),
                "decimal_odds": round(odds, 3),
                "implied_prob": round(implied, 4),
                "edge": round(edge, 4),
                "ev": round(ev, 4),
                "full_kelly": round(kelly, 4),
                "game_idx": i,
                "is_eligible": is_eligible,
            })

        # ── Market 1: Overtime probability ──────────────────────────────────
        candidates.extend(calc_overtime_candidates(
            home=home, away=away, prob_home=model_prob, game_idx=i,
        ))

        # ── Market 2: Margin-of-victory bands ───────────────────────────────
        candidates.extend(calc_margin_band_candidates(
            home=home, away=away, prob_home=model_prob, game_idx=i,
        ))

        # ── Market 3: Team totals (requires game total from odds) ────────────
        game_total   = float(odds_info.get("total", 0) or 0)
        spread_home  = odds_info.get("spread_home", None)
        if game_total > 0:
            candidates.extend(calc_team_total_candidates(
                home=home, away=away, prob_home=model_prob, game_idx=i,
                offered_total=game_total,
                offered_spread=float(spread_home) if spread_home is not None else None,
                odds_home_over=odds_info.get("total_over_odds") or None,
                odds_home_under=odds_info.get("total_under_odds") or None,
                odds_away_over=odds_info.get("total_over_odds") or None,
                odds_away_under=odds_info.get("total_under_odds") or None,
            ))

    print(f"[AGENT] Loaded {len(predictions)} predictions, {len(odds_by_game)} odds, {len(candidates)} candidates")
    print(f"[AGENT] Bankroll: ${bankroll:.2f}")
    print(f"[AGENT] Eligible: {sum(1 for c in candidates if c['is_eligible'])}")

    return candidates, bankroll

# ═══════════════════════════════════════
# SECTION 3: MATH PRIMITIVES
# ═══════════════════════════════════════

def build_correlation_matrix(candidates):
    """Build N x N correlation matrix for candidate bets."""
    n = len(candidates)
    C = np.full((n, n), CROSS_GAME_CORR)
    np.fill_diagonal(C, 1.0)
    for i in range(n):
        for j in range(i + 1, n):
            if candidates[i]["game_idx"] == candidates[j]["game_idx"]:
                C[i, j] = C[j, i] = SAME_GAME_MARKET_CORR
    return C


def build_covariance_matrix(candidates, corr):
    """Build covariance matrix from per-bet variance and correlation."""
    n = len(candidates)
    p = np.array([c["model_prob"] for c in candidates])
    b = np.array([c["decimal_odds"] - 1.0 for c in candidates])
    var = p * (1 - p) * (b + 1) ** 2
    std = np.sqrt(var)
    return np.outer(std, std) * corr[:n, :n]

# ═══════════════════════════════════════
# SECTION 4: STRATEGY IMPLEMENTATIONS
# ═══════════════════════════════════════

def strategy_fractional_kelly(candidates, bankroll, corr, kelly_frac=KELLY_FRACTION):
    """Baseline: independent fractional Kelly per bet."""
    stakes = {}
    for c in candidates:
        if not c["is_eligible"]:
            continue
        frac = min(c["full_kelly"] * kelly_frac, MAX_SINGLE_BET_FRACTION)
        stakes[c["id"]] = max(frac, 0.0)

    total = sum(stakes.values())
    if total > MAX_PORTFOLIO_EXPOSURE:
        scale = MAX_PORTFOLIO_EXPOSURE / total
        stakes = {k: v * scale for k, v in stakes.items()}
    return stakes


def strategy_portfolio_kelly(candidates, bankroll, corr):
    """Simultaneous Kelly: maximize expected log-growth across all bets."""
    eligible = [c for c in candidates if c["is_eligible"]]
    if not eligible:
        return {}

    n = len(eligible)
    p = np.array([c["model_prob"] for c in eligible])
    b = np.array([c["decimal_odds"] - 1.0 for c in eligible])
    q = 1.0 - p

    def neg_log_growth(f):
        wins = np.log(np.maximum(1.0 + b * f, 1e-10))
        loses = np.log(np.maximum(1.0 - f, 1e-10))
        return -(np.dot(p, wins) + np.dot(q, loses))

    def grad(f):
        dw = p * b / np.maximum(1.0 + b * f, 1e-10)
        dl = -q / np.maximum(1.0 - f, 1e-10)
        return -(dw + dl)

    bounds = [(0.0, MAX_SINGLE_BET_FRACTION)] * n
    constraints = [{"type": "ineq", "fun": lambda f: MAX_PORTFOLIO_EXPOSURE - f.sum()}]
    f0 = np.array([min(c["full_kelly"] * 0.25, MAX_SINGLE_BET_FRACTION * 0.5) for c in eligible])

    result = minimize(neg_log_growth, f0, jac=grad, method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"ftol": 1e-9, "maxiter": 1000})

    return {eligible[i]["id"]: max(result.x[i], 0.0) for i in range(n)}


def strategy_mean_variance(candidates, bankroll, corr, lambda_risk=1.0):
    """Mean-variance: maximize return per unit portfolio variance."""
    eligible = [c for c in candidates if c["is_eligible"]]
    if not eligible:
        return {}

    n = len(eligible)
    ev = np.array([c["ev"] for c in eligible])
    cov = build_covariance_matrix(eligible, corr)

    def neg_utility(f):
        port_ret = np.dot(ev, f)
        port_var = f @ cov @ f
        return -(port_ret - lambda_risk * port_var)

    bounds = [(0.0, MAX_SINGLE_BET_FRACTION)] * n
    constraints = [{"type": "ineq", "fun": lambda f: MAX_PORTFOLIO_EXPOSURE - f.sum()}]
    f0 = np.ones(n) * (MAX_PORTFOLIO_EXPOSURE / n / 2)

    result = minimize(neg_utility, f0, method="SLSQP",
                      bounds=bounds, constraints=constraints)
    return {eligible[i]["id"]: max(result.x[i], 0.0) for i in range(n)}


def strategy_drawdown_kelly(candidates, bankroll, corr, max_dd=None):
    """Kelly with drawdown constraint: worst-case loss capped."""
    if max_dd is None:
        max_dd = MAX_DRAWDOWN_TARGET

    eligible = [c for c in candidates if c["is_eligible"]]
    if not eligible:
        return {}

    n = len(eligible)
    p = np.array([c["model_prob"] for c in eligible])
    b = np.array([c["decimal_odds"] - 1.0 for c in eligible])
    q = 1.0 - p

    def neg_log_growth(f):
        wins = np.log(np.maximum(1.0 + b * f, 1e-10))
        loses = np.log(np.maximum(1.0 - f, 1e-10))
        return -(np.dot(p, wins) + np.dot(q, loses))

    bounds = [(0.0, MAX_SINGLE_BET_FRACTION)] * n
    constraints = [
        {"type": "ineq", "fun": lambda f: MAX_PORTFOLIO_EXPOSURE - f.sum()},
        {"type": "ineq", "fun": lambda f: max_dd - f.sum()},  # worst-case: all lose
        {"type": "ineq", "fun": lambda f: max_dd * 0.7 - np.dot(q, f)},  # expected loss cap
    ]
    f0 = np.array([min(c["full_kelly"] * 0.2, max_dd / max(n, 1)) for c in eligible])

    result = minimize(neg_log_growth, f0, method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"ftol": 1e-9, "maxiter": 1000})
    return {eligible[i]["id"]: max(result.x[i], 0.0) for i in range(n)}


def strategy_risk_parity(candidates, bankroll, corr):
    """Equal risk contribution from each bet."""
    eligible = [c for c in candidates if c["is_eligible"]]
    if not eligible:
        return {}

    n = len(eligible)
    cov = build_covariance_matrix(eligible, corr)
    target_rc = 1.0 / n

    def risk_parity_obj(f):
        port_var = f @ cov @ f
        if port_var < 1e-12:
            return 0.0
        marginal_rc = (cov @ f) * f / port_var
        return np.sum((marginal_rc - target_rc) ** 2)

    f0 = np.ones(n) / n
    bounds = [(1e-6, 1.0)] * n
    result = minimize(risk_parity_obj, f0, method="SLSQP", bounds=bounds)
    f_rp = np.maximum(result.x, 0.0)

    total = f_rp.sum()
    if total > 0:
        f_rp = f_rp / total * MAX_PORTFOLIO_EXPOSURE
    f_rp = np.minimum(f_rp, MAX_SINGLE_BET_FRACTION)

    return {eligible[i]["id"]: f_rp[i] for i in range(n)}


STRATEGY_FUNCS = {
    "fractional_kelly": strategy_fractional_kelly,
    "portfolio_kelly": strategy_portfolio_kelly,
    "mean_variance": strategy_mean_variance,
    "drawdown_kelly": strategy_drawdown_kelly,
    "risk_parity": strategy_risk_parity,
}

# ═══════════════════════════════════════
# SECTION 5: BET SLIP GENERATION
# ═══════════════════════════════════════

def generate_bet_slip(candidates, all_results, primary_strategy, bankroll):
    """Generate the final bet slip with all strategy comparisons."""
    today = date.today().isoformat()
    primary_stakes = all_results.get(primary_strategy, {})

    # Build bets from primary strategy
    bets = []
    for c in candidates:
        frac = primary_stakes.get(c["id"], 0)
        if frac < 0.001:
            continue
        stake = round(frac * bankroll, 2)
        if stake < MIN_STAKE_DOLLARS:
            continue

        american = int((c["decimal_odds"] - 1) * 100) if c["decimal_odds"] >= 2.0 else int(-100 / (c["decimal_odds"] - 1))

        bets.append({
            "rank": 0,
            "game": c["game"],
            "side": f"{c['team']} ML",
            "market": c["market"],
            "decimal_odds": c["decimal_odds"],
            "american_odds": american,
            "model_prob": c["model_prob"],
            "implied_prob": c["implied_prob"],
            "edge_pct": round(c["edge"] * 100, 1),
            "ev_pct": round(c["ev"] * 100, 1),
            "full_kelly_pct": round(c["full_kelly"] * 100, 1),
            "fraction": round(frac, 4),
            "stake_dollars": stake,
            "expected_profit": round(stake * c["ev"], 2),
            "status": "PENDING",
        })

    bets.sort(key=lambda b: b["ev_pct"], reverse=True)
    for i, b in enumerate(bets):
        b["rank"] = i + 1

    total_exposure = sum(b["fraction"] for b in bets)
    total_stake = sum(b["stake_dollars"] for b in bets)
    total_ev = sum(b["expected_profit"] for b in bets)
    worst_case = -total_stake

    # Strategy comparison
    strat_summary = {}
    for name, stakes in all_results.items():
        n_bets = sum(1 for v in stakes.values() if v > 0.001)
        exposure = sum(stakes.values())
        exp_ev = sum(
            stakes.get(c["id"], 0) * bankroll * c["ev"]
            for c in candidates if c["is_eligible"]
        )
        strat_summary[name] = {
            "n_bets": n_bets,
            "total_exposure_pct": round(exposure * 100, 1),
            "expected_ev_dollars": round(exp_ev, 2),
        }

    # Filtered out
    filtered = []
    for c in candidates:
        if not c["is_eligible"] and c["edge"] > 0:
            filtered.append({
                "game": c["game"],
                "side": c["side"],
                "reason": f"edge {c['edge']*100:.1f}% < {MIN_EDGE_THRESHOLD*100}% threshold"
                          if c["edge"] < MIN_EDGE_THRESHOLD
                          else f"EV {c['ev']*100:.1f}% <= 0",
            })

    return {
        "date": today,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "strategy_used": primary_strategy,
        "bankroll_before": round(bankroll, 2),
        "total_exposure_pct": round(total_exposure * 100, 1),
        "total_stake_dollars": round(total_stake, 2),
        "expected_portfolio_ev": round(total_ev, 2),
        "worst_case_loss": round(worst_case, 2),
        "n_bets": len(bets),
        "all_strategies": strat_summary,
        "bets": bets,
        "filtered_out": filtered[:10],
        "risk_metrics": {
            "worst_case_loss_dollars": round(-total_stake, 2),
            "worst_case_loss_pct": round(total_stake / bankroll * 100, 1) if bankroll > 0 else 0,
            "expected_profit_dollars": round(total_ev, 2),
            "n_eligible_candidates": sum(1 for c in candidates if c["is_eligible"]),
            "portfolio_exposure_pct": round(total_exposure * 100, 1),
        },
    }


def save_bet_slip(bet_slip, dry_run=False):
    """Save bet slip to JSON and append to history."""
    today = bet_slip["date"]
    slip_path = DATA_DIR / f"bet-slip-{today}.json"
    history_path = DATA_DIR / "portfolio-history.jsonl"

    if not dry_run:
        slip_path.write_text(json.dumps(bet_slip, indent=2))
        print(f"[AGENT] Bet slip saved: {slip_path}")

        # Append summary to history
        summary = {
            "date": today,
            "strategy": bet_slip["strategy_used"],
            "bankroll": bet_slip["bankroll_before"],
            "n_bets": bet_slip["n_bets"],
            "exposure_pct": bet_slip["total_exposure_pct"],
            "expected_ev": bet_slip["expected_portfolio_ev"],
        }
        with open(history_path, "a") as f:
            f.write(json.dumps(summary) + "\n")
    else:
        print(f"[DRY RUN] Would save to {slip_path}")


def print_bet_slip(bet_slip):
    """Print formatted bet slip to console."""
    print(f"\n{'='*70}")
    print(f"  NOMOS42 BETTING AGENT — {bet_slip['date']}")
    print(f"  Strategy: {bet_slip['strategy_used'].upper()}")
    print(f"  Bankroll: ${bet_slip['bankroll_before']:.2f}")
    print(f"{'='*70}")

    if not bet_slip["bets"]:
        print("  No bets tonight (no eligible edges)")
        return

    print(f"\n  {'#':>2} {'Game':<16} {'Side':<10} {'Odds':>6} {'Prob':>6} {'Edge':>6} {'EV':>6} {'Stake':>8} {'E[P&L]':>8}")
    print(f"  {'-'*2} {'-'*16} {'-'*10} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*8} {'-'*8}")

    for b in bet_slip["bets"]:
        print(f"  {b['rank']:>2} {b['game']:<16} {b['side']:<10} {b['decimal_odds']:>6.2f} "
              f"{b['model_prob']*100:>5.1f}% {b['edge_pct']:>5.1f}% {b['ev_pct']:>5.1f}% "
              f"${b['stake_dollars']:>7.2f} ${b['expected_profit']:>7.2f}")

    print(f"\n  {'TOTAL':<30} {'':>18} "
          f"${bet_slip['total_stake_dollars']:>7.2f} ${bet_slip['expected_portfolio_ev']:>7.2f}")
    print(f"  Exposure: {bet_slip['total_exposure_pct']:.1f}% | "
          f"Worst case: ${bet_slip['worst_case_loss']:.2f} | "
          f"Bets: {bet_slip['n_bets']}")

    # Strategy comparison
    print(f"\n  {'Strategy':<22} {'Bets':>5} {'Exposure':>9} {'E[PnL]':>9}")
    print(f"  {'-'*22} {'-'*5} {'-'*9} {'-'*9}")
    for name, s in bet_slip["all_strategies"].items():
        marker = " <--" if name == bet_slip["strategy_used"] else ""
        print(f"  {name:<22} {s['n_bets']:>5} {s['total_exposure_pct']:>8.1f}% ${s['expected_ev_dollars']:>7.2f}{marker}")

    print(f"\n{'='*70}")

# ═══════════════════════════════════════
# SECTION 6: MAIN
# ═══════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Nomos42 NBA Betting Agent")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=STRATEGIES)
    parser.add_argument("--bankroll", type=float, default=None)
    parser.add_argument("--compare-all", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-edge", type=float, default=MIN_EDGE_THRESHOLD)
    parser.add_argument("--max-exposure", type=float, default=MAX_PORTFOLIO_EXPOSURE)
    args = parser.parse_args()

    # 1. Load inputs
    candidates, bankroll = load_inputs(bankroll_override=args.bankroll)

    if not candidates:
        print("[AGENT] No candidates found. Exiting.")
        return

    eligible = [c for c in candidates if c["is_eligible"]]
    if not eligible:
        print("[AGENT] No eligible bets (no sufficient edges). Exiting.")
        # Still save empty slip
        empty_slip = generate_bet_slip(candidates, {args.strategy: {}}, args.strategy, bankroll)
        save_bet_slip(empty_slip, dry_run=args.dry_run)
        print_bet_slip(empty_slip)
        return

    # 2. Build correlation matrix
    corr = build_correlation_matrix(eligible)

    # 3. Run strategies
    all_results = {}
    for strat_name in STRATEGIES:
        try:
            fn = STRATEGY_FUNCS[strat_name]
            all_results[strat_name] = fn(candidates, bankroll, corr)
        except Exception as e:
            print(f"[AGENT] Strategy {strat_name} failed: {e}")
            all_results[strat_name] = {}

    # 4. Generate and save bet slip
    bet_slip = generate_bet_slip(candidates, all_results, args.strategy, bankroll)
    save_bet_slip(bet_slip, dry_run=args.dry_run)
    print_bet_slip(bet_slip)


if __name__ == "__main__":
    main()
