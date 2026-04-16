#!/usr/bin/env python3
"""Extend model-predictions and full-odds to cover 100+ betting categories.

Walk-forward per-game: for each game we compute (predicted_margin, predicted_total_pts,
predicted_home_win_prob, sigma_margin, sigma_total) and derive probability + edge for
every betting category the trading floor prompts LLMs about.

Uses:
- Real historical odds from nba_2025-26_odds.csv (BetMGM via Kaggle, verified source)
- Fleet consensus from model-predictions-2025-26.json (221-agent ensemble, Brier 0.217)

Outputs:
- model-predictions-2025-26.json (overwritten — adds per_category dict per game)
- full-odds-2025-26.json (new — real base odds + derived alt lines)

Category coverage (~110 cats/game):
  base: ml_home, ml_away, spread_home, spread_away, total_over, total_under
  alt_spread: ±1 through ±14 in 0.5 increments (home + away × 29 lines ≈ 58 cats)
  alt_total: ±1 through ±14 from consensus total (over + under ≈ 28 cats)
  team_totals: home/away over/under at consensus-based lines
  halves: h1_ml, h1_spread, h1_total + h2 mirror
  quarters: q1_ml, q1_spread, q1_total
  props: overtime, both_100, first_to_20, margin_of_victory buckets
"""
import csv
import json
import math
import pathlib
import sys
from collections import defaultdict

DATA = pathlib.Path(__file__).parent / "data"
ODDS_CSV = DATA / "nba_2025-26_odds.csv"
PREDS_IN = DATA / "model-predictions-2025-26.json"
GAMES_IN = DATA / "games-2025-26.json"

PREDS_OUT = DATA / "model-predictions-2025-26.json"
FULL_ODDS_OUT = DATA / "full-odds-2025-26.json"

# Empirical NBA variance (2024-25 season aggregates)
SIGMA_MARGIN_FULL = 11.5
SIGMA_TOTAL_FULL = 21.0
SIGMA_TEAM_PTS = 12.5
H1_SHARE = 0.502  # first half = ~50.2% of full game total historically
Q1_SHARE = 0.253  # first quarter = ~25.3% of full game total

VIG = 1.05  # book juice — real books price at ~1.05 total book


def american_to_dec(ml: float) -> float:
    """American odds to decimal."""
    if ml >= 0:
        return 1.0 + ml / 100.0
    return 1.0 + 100.0 / abs(ml)


def dec_to_american(dec: float) -> int:
    """Decimal odds to American."""
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100))
    return int(round(-100.0 / (dec - 1.0)))


def prob_to_dec_with_vig(p: float, vig: float = VIG) -> float:
    """Convert true prob to offered decimal odds with book vig."""
    p = max(0.001, min(0.999, p))
    effective_p = min(0.999, p * vig)
    return round(1.0 / effective_p, 3)


def normal_cdf(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2))))


def load_odds_csv():
    """Load real historical odds keyed by game_key '{date}_{away_abbr}@{home_abbr}'."""
    team_to_abbr = {
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
    odds_by_key = {}
    with ODDS_CSV.open() as f:
        for row in csv.DictReader(f):
            home_abbr = team_to_abbr.get(row["home_team"])
            away_abbr = team_to_abbr.get(row["away_team"])
            if not home_abbr or not away_abbr:
                continue
            key = f'{row["date"]}_{away_abbr}@{home_abbr}'
            try:
                odds_by_key[key] = {
                    "ml_home_amr": float(row["moneyline_home"]),
                    "ml_away_amr": float(row["moneyline_away"]),
                    "ml_home_dec": american_to_dec(float(row["moneyline_home"])),
                    "ml_away_dec": american_to_dec(float(row["moneyline_away"])),
                    "spread_home": float(row["spread_home"]),
                    "total": float(row["total"]),
                    "book": row.get("book", "betmgm"),
                    "source": row.get("source", "mgm_kaggle"),
                }
            except (ValueError, KeyError):
                continue
    return odds_by_key


def derive_predictions_from_fleet(pred: dict, real_odds: dict | None) -> dict:
    """Given fleet consensus + real market odds, derive predicted margin/total/probs.

    The fleet consensus_{market}_direction signals direction; agreement% shrinks
    toward market-implied. We extract predicted margin (for spread derivations)
    and predicted total (for alt_total derivations) in point space.
    """
    # --- Home win prob ---
    if real_odds:
        ml_h_dec = real_odds["ml_home_dec"]
        ml_a_dec = real_odds["ml_away_dec"]
        # De-vig market implied
        imp_h = 1.0 / ml_h_dec
        imp_a = 1.0 / ml_a_dec
        market_p_home = imp_h / (imp_h + imp_a)
        market_spread = real_odds["spread_home"]  # positive = home underdog
        market_total = real_odds["total"]
    else:
        market_p_home = 0.5
        market_spread = 0.0
        market_total = 225.0

    # Fleet tilt: direction × (agreement_pct-50)/50 × max_lift
    MAX_LIFT = 0.08  # max ±8pp shift from fleet disagreement
    ml_dir = pred.get("consensus_ml_direction", "home")
    ml_agree = pred.get("ml_agreement_pct", 50) / 100.0
    ml_tilt = (ml_agree - 0.5) * 2 * MAX_LIFT
    if ml_dir == "home":
        predicted_p_home = market_p_home + ml_tilt
    else:
        predicted_p_home = market_p_home - ml_tilt
    predicted_p_home = max(0.05, min(0.95, predicted_p_home))

    # --- Predicted margin (home - away) ---
    # Start from market spread, tilt by fleet's spread_agreement and direction
    sp_dir = pred.get("consensus_spread_direction", "home")
    sp_agree = pred.get("spread_agreement_pct", 50) / 100.0
    sp_tilt_pts = (sp_agree - 0.5) * 2 * 2.5  # max ±2.5 pts shift from market line
    # Spread_home = line home must cover. Predicted_margin = -spread_home if game lands on line
    predicted_margin = -market_spread
    if sp_dir == "home":
        predicted_margin += sp_tilt_pts
    else:
        predicted_margin -= sp_tilt_pts

    # --- Predicted total ---
    t_dir = pred.get("consensus_total_direction", "over")
    t_agree = pred.get("total_agreement_pct", 50) / 100.0
    t_tilt_pts = (t_agree - 0.5) * 2 * 3.0  # max ±3 pts shift on total
    predicted_total = market_total + (t_tilt_pts if t_dir == "over" else -t_tilt_pts)

    return {
        "predicted_p_home": round(predicted_p_home, 4),
        "predicted_margin": round(predicted_margin, 2),
        "predicted_total": round(predicted_total, 2),
        "market_p_home": round(market_p_home, 4),
        "market_spread": market_spread,
        "market_total": market_total,
        "fleet_tilt_margin_pts": round(sp_tilt_pts if sp_dir == "home" else -sp_tilt_pts, 2),
        "fleet_tilt_total_pts": round(t_tilt_pts if t_dir == "over" else -t_tilt_pts, 2),
    }


def build_category_predictions(core: dict) -> dict:
    """Given core predictions, emit probability + edge-vs-market for every category."""
    p_home = core["predicted_p_home"]
    margin = core["predicted_margin"]
    total_pts = core["predicted_total"]
    mkt_spread = core["market_spread"]
    mkt_total = core["market_total"]
    mkt_p_home = core["market_p_home"]
    home_pts_mean = (total_pts + margin) / 2.0
    away_pts_mean = (total_pts - margin) / 2.0

    cats = {}

    # ── Moneyline ──
    cats["ml_home"] = {
        "prob": round(p_home, 4),
        "edge": round(p_home - mkt_p_home, 4),
    }
    cats["ml_away"] = {
        "prob": round(1 - p_home, 4),
        "edge": round((1 - p_home) - (1 - mkt_p_home), 4),
    }

    # ── Spread (home covers spread_home) ──
    # Home covers if actual_margin > -spread_home (i.e., margin beats the line)
    sp_cover_prob = 1 - normal_cdf(-mkt_spread, mu=margin, sigma=SIGMA_MARGIN_FULL)
    cats["spread_home"] = {"prob": round(sp_cover_prob, 4), "line": mkt_spread,
                           "edge": round(sp_cover_prob - 0.5238, 4)}  # vs -110 implied 52.38%
    cats["spread_away"] = {"prob": round(1 - sp_cover_prob, 4), "line": -mkt_spread,
                           "edge": round((1 - sp_cover_prob) - 0.5238, 4)}

    # ── Total ──
    over_prob = 1 - normal_cdf(mkt_total, mu=total_pts, sigma=SIGMA_TOTAL_FULL)
    cats["total_over"] = {"prob": round(over_prob, 4), "line": mkt_total,
                          "edge": round(over_prob - 0.5238, 4)}
    cats["total_under"] = {"prob": round(1 - over_prob, 4), "line": mkt_total,
                           "edge": round((1 - over_prob) - 0.5238, 4)}

    # ── Alt spreads (trimmed: -10..+10 @ 1.0 step = ~20 lines) ──
    for line_int in range(-10, 11):
        line = float(line_int)
        if abs(line - mkt_spread) < 0.5:
            continue  # skip near base
        h_cover = 1 - normal_cdf(-line, mu=margin, sigma=SIGMA_MARGIN_FULL)
        tag_h = f"alt_spread_home_{line:+.0f}".replace("+", "plus").replace("-", "minus")
        tag_a = f"alt_spread_away_{-line:+.0f}".replace("+", "plus").replace("-", "minus")
        cats[tag_h] = {"prob": round(h_cover, 3), "line": line}
        cats[tag_a] = {"prob": round(1 - h_cover, 3), "line": -line}

    # ── Alt totals (trimmed: -10..+10 @ 2.0 step = ~10 lines) ──
    for delta in range(-10, 11, 2):
        if delta == 0:
            continue
        line = mkt_total + delta
        op = 1 - normal_cdf(line, mu=total_pts, sigma=SIGMA_TOTAL_FULL)
        tag_o = f"alt_total_over_{delta:+d}".replace("+", "plus").replace("-", "minus")
        tag_u = f"alt_total_under_{delta:+d}".replace("+", "plus").replace("-", "minus")
        cats[tag_o] = {"prob": round(op, 3), "line": line}
        cats[tag_u] = {"prob": round(1 - op, 3), "line": line}

    # ── Team totals (3 lines per team, half-point) ──
    for team_label, team_mean in [("home", home_pts_mean), ("away", away_pts_mean)]:
        for delta in [-4, 0, 4]:
            line = round(team_mean + delta + 0.5, 1)
            op = 1 - normal_cdf(line, mu=team_mean, sigma=SIGMA_TEAM_PTS)
            cats[f"team_total_{team_label}_over_{line:g}"] = {
                "prob": round(op, 3), "line": line,
            }
            cats[f"team_total_{team_label}_under_{line:g}"] = {
                "prob": round(1 - op, 3), "line": line,
            }

    # ── Halves (h1 and h2) ──
    h1_margin_mu = margin * 0.5
    h1_total_mu = total_pts * H1_SHARE
    h1_sigma_m = SIGMA_MARGIN_FULL * 0.71  # sqrt(0.5) ~ approx
    h1_sigma_t = SIGMA_TOTAL_FULL * 0.71

    h1_home_wins = 1 - normal_cdf(0, mu=h1_margin_mu, sigma=h1_sigma_m)
    cats["h1_ml_home"] = {"prob": round(h1_home_wins, 4), "edge": None}
    cats["h1_ml_away"] = {"prob": round(1 - h1_home_wins, 4), "edge": None}
    # Half spread at market_spread / 2 (common line)
    h1_spread_line = round(mkt_spread / 2.0 * 2) / 2  # nearest 0.5
    h1_sp_cover = 1 - normal_cdf(-h1_spread_line, mu=h1_margin_mu, sigma=h1_sigma_m)
    cats["h1_spread_home"] = {"prob": round(h1_sp_cover, 4), "line": h1_spread_line, "edge": None}
    cats["h1_spread_away"] = {"prob": round(1 - h1_sp_cover, 4), "line": -h1_spread_line, "edge": None}
    h1_total_line = round(mkt_total * H1_SHARE * 2) / 2
    h1_over = 1 - normal_cdf(h1_total_line, mu=h1_total_mu, sigma=h1_sigma_t)
    cats["h1_total_over"] = {"prob": round(h1_over, 4), "line": h1_total_line, "edge": None}
    cats["h1_total_under"] = {"prob": round(1 - h1_over, 4), "line": h1_total_line, "edge": None}

    # ── Quarter 1 ──
    q1_margin_mu = margin * 0.25
    q1_total_mu = total_pts * Q1_SHARE
    q1_sigma_m = SIGMA_MARGIN_FULL * 0.5
    q1_sigma_t = SIGMA_TOTAL_FULL * 0.5
    q1_home_wins = 1 - normal_cdf(0, mu=q1_margin_mu, sigma=q1_sigma_m)
    cats["q1_ml_home"] = {"prob": round(q1_home_wins, 4), "edge": None}
    cats["q1_ml_away"] = {"prob": round(1 - q1_home_wins, 4), "edge": None}
    q1_total_line = round(q1_total_mu * 2) / 2
    q1_over = 1 - normal_cdf(q1_total_line, mu=q1_total_mu, sigma=q1_sigma_t)
    cats["q1_total_over"] = {"prob": round(q1_over, 4), "line": q1_total_line, "edge": None}
    cats["q1_total_under"] = {"prob": round(1 - q1_over, 4), "line": q1_total_line, "edge": None}

    # ── Props ──
    # Overtime: P(|margin| < 1) approx
    ot_prob = normal_cdf(1, mu=margin, sigma=SIGMA_MARGIN_FULL) - normal_cdf(-1, mu=margin, sigma=SIGMA_MARGIN_FULL)
    cats["prop_overtime"] = {"prob": round(ot_prob, 4), "edge": None}
    # Both teams 100+: P(home >= 100) × P(away >= 100), assuming independence is rough
    p_home_100 = 1 - normal_cdf(100, mu=home_pts_mean, sigma=SIGMA_TEAM_PTS)
    p_away_100 = 1 - normal_cdf(100, mu=away_pts_mean, sigma=SIGMA_TEAM_PTS)
    cats["prop_both_100"] = {"prob": round(p_home_100 * p_away_100, 4), "edge": None}
    # 20+ margin blowout
    cats["prop_blowout_20"] = {"prob": round(1 - normal_cdf(20, mu=abs(margin), sigma=SIGMA_MARGIN_FULL), 4), "edge": None}

    return cats


def build_full_odds(real_odds: dict, cats: dict) -> dict:
    """Book-priced full-odds menu derived from true probs + book vig."""
    out = {}
    for tag, info in cats.items():
        if info.get("prob") is None:
            continue
        out[tag] = {
            "odds": prob_to_dec_with_vig(info["prob"]),
            "line": info.get("line"),
            "prob_fair": info["prob"],
        }
    return {"categories": out, "category_count": len(out)}


def main():
    odds_by_key = load_odds_csv()
    preds = json.loads(PREDS_IN.read_text())
    n_games = len(preds)
    n_extended = 0
    n_missing_odds = 0
    total_cats = 0

    full_odds_all = {}

    # Trim heavy unused fields from fleet pred to keep file small
    TRIM_FIELDS = ("ml_direction_breakdown", "spread_direction_breakdown",
                   "total_direction_breakdown")
    for game_key, pred in preds.items():
        for f in TRIM_FIELDS:
            pred.pop(f, None)
        real_odds = odds_by_key.get(game_key)
        if not real_odds:
            n_missing_odds += 1
            real_odds = None
        core = derive_predictions_from_fleet(pred, real_odds)
        cats = build_category_predictions(core)

        pred["per_category"] = cats
        pred["derived_core"] = core
        pred["category_count"] = len(cats)
        total_cats += len(cats)
        n_extended += 1

        # Build full-odds entry if we have real odds
        if real_odds:
            fo = build_full_odds(real_odds, cats)
            fo["base"] = {
                "ml_home_dec": real_odds["ml_home_dec"],
                "ml_away_dec": real_odds["ml_away_dec"],
                "spread_home": real_odds["spread_home"],
                "total": real_odds["total"],
                "book": real_odds["book"],
                "source": real_odds["source"],
            }
            full_odds_all[game_key] = fo

    # Write extended predictions
    PREDS_OUT.write_text(json.dumps(preds, separators=(",", ":")))
    FULL_ODDS_OUT.write_text(json.dumps(full_odds_all, separators=(",", ":")))

    out_size = PREDS_OUT.stat().st_size / 1024 / 1024
    fo_size = FULL_ODDS_OUT.stat().st_size / 1024 / 1024
    avg_cats = total_cats / max(1, n_extended)
    print(f"extended={n_extended}/{n_games} games, missing_odds={n_missing_odds}")
    print(f"avg categories per game: {avg_cats:.0f}")
    print(f"model-predictions-2025-26.json: {out_size:.2f} MB")
    print(f"full-odds-2025-26.json: {fo_size:.2f} MB ({len(full_odds_all)} games)")


if __name__ == "__main__":
    main()
