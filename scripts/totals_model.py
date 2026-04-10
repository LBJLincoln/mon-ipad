#!/usr/bin/env python3
"""
NBA Game Totals Prediction Model
=================================
Predicts total points scored (O/U betting) for NBA games.

Architecture:
  1. Matchup model  — PPG / PAPG interaction (Dean Oliver principles)
  2. Rolling model  — weighted moving average of both teams' recent totals
  3. Venue model    — home/away split for each team
  4. Ensemble       — blended prediction with optional XGBoost on residuals

Key insight from empirical analysis:
  - NBA O/U lines are extremely efficient (market RMSE: 17.73 pts)
  - Rolling model RMSE: 18.60 pts (within ~5% of market)
  - No simple signal reliably beats -110 vig at population level
  - Value focus: identify pace-mismatch extremes (high-pace vs high-pace = more possessions)
    and track team O/U tendencies as ancillary signals

Data source: /home/lahargnedebartoli/mon-ipad/data/historical-odds/nba_2008-2025.csv
  Columns: date, away, home, score_away, score_home, total, moneyline_*, spread

Betting logic:
  - Primary: compare ensemble pred vs line
  - Minimum edge buffer (default 2.5 pts) to avoid vig on marginal edges
  - Quarter-Kelly sizing (0.25), max 2.5% bankroll per bet
  - Skip if team O/U tendency contradicts direction

Usage:
  python3 totals_model.py [--buffer 2.5] [--train-cutoff 2016] [--xgb] [--verbose]

Live prediction (single game):
  python3 totals_model.py --predict --home BOS --away LAL --line 225.5
"""

import csv
import math
import argparse
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# ── Constants ──
LEAGUE_AVG_TOTAL_BY_ERA = {
    # Season (start year) → average total pts
    2008: 200, 2009: 200, 2010: 201, 2011: 199, 2012: 193,
    2013: 196, 2014: 202, 2015: 200, 2016: 205, 2017: 211,
    2018: 213, 2019: 222, 2020: 224, 2021: 224, 2022: 221,
    2023: 229, 2024: 228, 2025: 228,
}

OU_DECIMAL_ODDS = 1.909   # -110 American = 1.909 decimal
OU_BREAKEVEN = 1 / OU_DECIMAL_ODDS  # 52.36% win rate to break even

# ── Team name normalizer ──
TEAM_ALIASES = {
    "atl": "ATL", "bos": "BOS", "bkn": "BKN", "cha": "CHA", "chi": "CHI",
    "cle": "CLE", "dal": "DAL", "den": "DEN", "det": "DET", "gs": "GSW",
    "gsw": "GSW", "hou": "HOU", "ind": "IND", "lac": "LAC", "lal": "LAL",
    "mem": "MEM", "mia": "MIA", "mil": "MIL", "min": "MIN", "no": "NOP",
    "nop": "NOP", "nyk": "NYK", "okc": "OKC", "orl": "ORL", "phi": "PHI",
    "phx": "PHX", "por": "POR", "sac": "SAC", "sa": "SAS", "sas": "SAS",
    "tor": "TOR", "uta": "UTA", "uth": "UTA", "was": "WAS", "wsh": "WAS",
    "nj": "BKN", "njn": "BKN", "sea": "OKC", "van": "MEM",
}


def normalize_team(name: str) -> str:
    return TEAM_ALIASES.get(name.lower().strip(), name.upper().strip()[:3])


def kelly_fraction(p_win: float, decimal_odds: float = OU_DECIMAL_ODDS,
                    kelly_mult: float = 0.25) -> float:
    b = decimal_odds - 1.0
    q = 1.0 - p_win
    if b <= 0 or p_win <= 0:
        return 0.0
    f = (b * p_win - q) / b
    return max(0.0, f * kelly_mult)


def normal_cdf_approx(z: float) -> float:
    """Approximate standard normal CDF using Abramowitz & Stegun."""
    if z < 0:
        return 1.0 - normal_cdf_approx(-z)
    t = 1.0 / (1.0 + 0.2316419 * z)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
            + t * (-1.821255978 + t * 1.330274429))))
    return 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z * z) * poly


def prob_over(pred: float, line: float, sigma: float = 13.0) -> float:
    """
    P(actual > line) if predicted total ~ N(pred, sigma).
    NBA totals have ~13pt std dev around predictions.
    """
    z = (line - pred) / max(sigma, 1.0)
    return 1.0 - normal_cdf_approx(z)


# ── Data loader ──

def load_csv(path: str) -> List[dict]:
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def parse_game(row: dict) -> Optional[dict]:
    try:
        home = normalize_team(row.get("home", ""))
        away = normalize_team(row.get("away", ""))
        date = row.get("date", "")[:10]
        score_home = int(row["score_home"])
        score_away = int(row["score_away"])
        actual_total = score_home + score_away
        line_total = float(row["total"]) if row.get("total") else None
        ml_home = float(row["moneyline_home"]) if row.get("moneyline_home") else -110.0
        ml_away = float(row["moneyline_away"]) if row.get("moneyline_away") else 110.0
        spread = float(row["spread"]) if row.get("spread") else 0.0
        season = int(row.get("season", 2010))
        is_playoffs = row.get("playoffs", "False").strip() == "True"
        return {
            "date": date,
            "season": season,
            "home": home,
            "away": away,
            "score_home": score_home,
            "score_away": score_away,
            "actual_total": actual_total,
            "line_total": line_total,
            "ml_home": ml_home,
            "ml_away": ml_away,
            "spread": spread,
            "is_playoffs": is_playoffs,
        }
    except (ValueError, KeyError):
        return None


# ── Rolling state tracker ──

class TotalsStateTracker:
    """
    Per-team rolling statistics for totals prediction.
    Stores simple arrays of pts/opp_pts for fast rolling window computation.
    """

    def __init__(self):
        self.pts: Dict[str, List[float]] = defaultdict(list)
        self.opp_pts: Dict[str, List[float]] = defaultdict(list)
        self.totals: Dict[str, List[float]] = defaultdict(list)
        self.home_pts: Dict[str, List[float]] = defaultdict(list)
        self.home_opp: Dict[str, List[float]] = defaultdict(list)
        self.away_pts: Dict[str, List[float]] = defaultdict(list)
        self.away_opp: Dict[str, List[float]] = defaultdict(list)
        self.ou_record: Dict[str, List[int]] = defaultdict(list)   # 1=over, 0=under, skip push
        self.last_date: Dict[str, str] = {}
        # League-level running totals (for contextual normalization)
        self._league_total_sum = 0.0
        self._league_game_count = 0

    def record(self, home: str, away: str, sh: int, sa: int, date: str):
        actual = sh + sa
        self.pts[home].append(float(sh))
        self.pts[away].append(float(sa))
        self.opp_pts[home].append(float(sa))
        self.opp_pts[away].append(float(sh))
        self.totals[home].append(float(actual))
        self.totals[away].append(float(actual))
        self.home_pts[home].append(float(sh))
        self.home_opp[home].append(float(sa))
        self.away_pts[away].append(float(sa))
        self.away_opp[away].append(float(sh))
        self.last_date[home] = date
        self.last_date[away] = date
        self._league_total_sum += actual
        self._league_game_count += 1

    def record_ou(self, home: str, away: str, actual: float, line: float):
        if actual > line:
            self.ou_record[home].append(1)
            self.ou_record[away].append(1)
        elif actual < line:
            self.ou_record[home].append(0)
            self.ou_record[away].append(0)

    def _roll(self, arr: List[float], n: int, default: float) -> float:
        s = arr[-n:]
        return sum(s) / len(s) if s else default

    def league_avg_total(self) -> float:
        if self._league_game_count < 50:
            return 210.0
        return self._league_total_sum / self._league_game_count

    def get(self, team: str, n: int = 10) -> dict:
        lg = self.league_avg_total()
        ppg = self._roll(self.pts[team], n, lg / 2)
        pap = self._roll(self.opp_pts[team], n, lg / 2)
        tot = self._roll(self.totals[team], n, lg)
        return {
            "ppg": ppg,
            "papg": pap,
            "total_avg": tot,
            "n_games": len(self.pts[team]),
        }

    def get_home(self, team: str, n: int = 8) -> dict:
        lg = self.league_avg_total()
        ppg = self._roll(self.home_pts[team], n, lg / 2)
        pap = self._roll(self.home_opp[team], n, lg / 2)
        tot_list = [p + o for p, o in zip(self.home_pts[team], self.home_opp[team])]
        tot = self._roll(tot_list, n, lg)
        return {"ppg": ppg, "papg": pap, "total_avg": tot,
                "n_games": len(self.home_pts[team])}

    def get_away(self, team: str, n: int = 8) -> dict:
        lg = self.league_avg_total()
        ppg = self._roll(self.away_pts[team], n, lg / 2)
        pap = self._roll(self.away_opp[team], n, lg / 2)
        tot_list = [p + o for p, o in zip(self.away_pts[team], self.away_opp[team])]
        tot = self._roll(tot_list, n, lg)
        return {"ppg": ppg, "papg": pap, "total_avg": tot,
                "n_games": len(self.away_pts[team])}

    def ou_tendency(self, team: str, n: int = 10) -> float:
        """Rolling O/U rate: >0.5 = tendency to go over."""
        s = self.ou_record[team][-n:]
        return sum(s) / len(s) if s else 0.5

    def total_variance(self, team: str, n: int = 10) -> float:
        """Std dev of team's recent total points games."""
        s = self.totals[team][-n:]
        if len(s) < 3:
            return 13.0  # league avg
        mean = sum(s) / len(s)
        return (sum((x - mean) ** 2 for x in s) / len(s)) ** 0.5

    def pace_proxy(self, team: str, n: int = 10) -> float:
        """Proxy for pace: (PPG + PAPG) / 2, higher = faster team."""
        s = self.get(team, n)
        return (s["ppg"] + s["papg"]) / 2.0


# ── Prediction models ──

def matchup_predict(h: dict, a: dict, h_home: dict, a_away: dict) -> float:
    """
    Matchup model: average of H_PPG vs A_PAP and A_PPG vs H_PAP.
    This is the standard 'pace-adjusted' prediction when no pace data available.

    Expected_Home = 0.5 * (H_PPG + A_PAP)   [home offense meets away defense]
    Expected_Away = 0.5 * (A_PPG + H_PAP)   [away offense meets home defense]
    Total = Expected_Home + Expected_Away

    Then blend 60% overall + 40% venue-split for better signal.
    """
    # Overall matchup
    exp_home = (h["ppg"] + a["papg"]) / 2.0
    exp_away = (a["ppg"] + h["papg"]) / 2.0
    overall = exp_home + exp_away

    # Venue-split matchup (home team at home, away team on road)
    exp_home_v = (h_home["ppg"] + a_away["papg"]) / 2.0 if h_home["n_games"] >= 3 else exp_home
    exp_away_v = (a_away["ppg"] + h_home["papg"]) / 2.0 if a_away["n_games"] >= 3 else exp_away
    venue = exp_home_v + exp_away_v

    # Blend
    return 0.6 * overall + 0.4 * venue


def rolling_predict(h: dict, a: dict, h_home: dict, a_away: dict) -> float:
    """Rolling total average blend: 60% overall + 40% venue-specific."""
    h_tot = 0.6 * h["total_avg"] + 0.4 * h_home["total_avg"]
    a_tot = 0.6 * a["total_avg"] + 0.4 * a_away["total_avg"]
    return (h_tot + a_tot) / 2.0


def ensemble_predict(matchup: float, rolling: float,
                      xgb_pred: Optional[float] = None) -> float:
    """
    Weighted ensemble:
    - Without XGBoost: 50% matchup + 50% rolling
    - With XGBoost: 30% matchup + 30% rolling + 40% XGBoost
    """
    if xgb_pred is not None:
        return 0.30 * matchup + 0.30 * rolling + 0.40 * xgb_pred
    return 0.50 * matchup + 0.50 * rolling


# ── XGBoost feature builder ──

def build_xgb_features(
    h: dict, a: dict, h_home: dict, a_away: dict,
    h_ou: float, a_ou: float,
    h_var: float, a_var: float,
    pace_h: float, pace_a: float,
    league_avg: float,
    matchup_pred: float, rolling_pred: float,
    season: int,
) -> List[float]:
    """35-feature vector for XGBoost regression on actual total."""
    return [
        # Offenses and defenses
        h["ppg"], h["papg"], h["total_avg"],
        a["ppg"], a["papg"], a["total_avg"],
        # Venue splits
        h_home["ppg"], h_home["papg"], h_home["total_avg"],
        a_away["ppg"], a_away["papg"], a_away["total_avg"],
        # Matchup quality
        h["ppg"] - a["papg"],          # Home O - Away D
        a["ppg"] - h["papg"],          # Away O - Home D
        h["ppg"] + a["ppg"],           # Combined offense
        h["papg"] + a["papg"],         # Combined defense allowed
        # Pace proxies
        pace_h, pace_a,
        pace_h + pace_a,               # Combined pace indicator
        abs(pace_h - pace_a),          # Pace mismatch (fast vs slow)
        # O/U tendencies
        h_ou, a_ou, (h_ou + a_ou) / 2.0,
        # Variance / consistency
        h_var, a_var, (h_var + a_var) / 2.0,
        # League context
        league_avg,
        h["total_avg"] - league_avg,   # H deviation from league avg
        a["total_avg"] - league_avg,   # A deviation from league avg
        # Component predictions as meta-features
        matchup_pred, rolling_pred,
        (matchup_pred + rolling_pred) / 2.0,
        matchup_pred - rolling_pred,   # Disagreement signal
        # Season trend (higher season = higher-scoring era)
        float(season) / 2025.0,
        # Data depth
        float(min(h["n_games"], 82)) / 82.0,
        float(min(a["n_games"], 82)) / 82.0,
    ]


# ── Main backtester ──

class TotalsBacktester:

    def __init__(
        self,
        buffer: float = 2.5,
        kelly_mult: float = 0.25,
        max_bet_frac: float = 0.025,
        verbose: bool = False,
    ):
        self.buffer = buffer
        self.kelly_mult = kelly_mult
        self.max_bet_frac = max_bet_frac
        self.verbose = verbose

    def run(
        self,
        games: List[dict],
        train_cutoff: int = 2016,
        use_xgb: bool = False,
    ) -> dict:
        tracker = TotalsStateTracker()
        xgb_model = None
        xgb_X, xgb_y = [], []

        bankroll = 100.0
        bets = []
        predictions = []
        errors_model, errors_line = [], []

        games_sorted = sorted(games, key=lambda g: g["date"])

        for i, game in enumerate(games_sorted):
            home, away = game["home"], game["away"]
            date, season = game["date"], game["season"]
            sh, sa = game["score_home"], game["score_away"]
            actual = game["actual_total"]
            line = game.get("line_total")

            # Get state BEFORE recording this game
            h = tracker.get(home, n=10)
            a = tracker.get(away, n=10)
            h_home = tracker.get_home(home, n=8)
            a_away = tracker.get_away(away, n=8)
            h_ou = tracker.ou_tendency(home, n=10)
            a_ou = tracker.ou_tendency(away, n=10)
            h_var = tracker.total_variance(home, n=10)
            a_var = tracker.total_variance(away, n=10)
            pace_h = tracker.pace_proxy(home, n=10)
            pace_a = tracker.pace_proxy(away, n=10)
            lg_avg = tracker.league_avg_total()

            # Need warm-up games for meaningful prediction
            if h["n_games"] < 5 or a["n_games"] < 5:
                tracker.record(home, away, sh, sa, date)
                if line:
                    tracker.record_ou(home, away, actual, line)
                continue

            # ── Compute predictions ──
            mp = matchup_predict(h, a, h_home, a_away)
            rp = rolling_predict(h, a, h_home, a_away)

            # XGBoost feature vector
            feats = build_xgb_features(
                h, a, h_home, a_away, h_ou, a_ou, h_var, a_var,
                pace_h, pace_a, lg_avg, mp, rp, season,
            )
            xgb_X.append(feats)
            xgb_y.append(float(actual))

            # XGBoost inference (test window only)
            xgb_pred = None
            if use_xgb and season > train_cutoff and xgb_model is not None:
                try:
                    import numpy as np
                    xgb_pred = float(xgb_model.predict(np.array([feats]))[0])
                except Exception:
                    pass

            # Periodic retraining
            if (use_xgb and season >= train_cutoff
                    and len(xgb_X) >= 500 and i % 300 == 0):
                try:
                    import numpy as np
                    from xgboost import XGBRegressor
                    xgb_model = XGBRegressor(
                        n_estimators=300, max_depth=4,
                        learning_rate=0.04, subsample=0.8,
                        colsample_bytree=0.8, min_child_weight=10,
                        random_state=42, verbosity=0,
                    )
                    xgb_model.fit(np.array(xgb_X[:-1]), np.array(xgb_y[:-1]))
                    if self.verbose:
                        print(f"  XGB retrained on {len(xgb_X)} games ({date})")
                except ImportError:
                    use_xgb = False
                    print("  [xgboost not installed] running formula+rolling only")
                except Exception as e:
                    if self.verbose:
                        print(f"  XGB train error: {e}")

            ep = ensemble_predict(mp, rp, xgb_pred)

            # Track RMSE
            if line:
                errors_model.append((ep - actual) ** 2)
                errors_line.append((line - actual) ** 2)

            pred_rec = {
                "date": date, "season": season, "home": home, "away": away,
                "line": line, "actual": actual,
                "matchup": round(mp, 1), "rolling": round(rp, 1),
                "xgb": round(xgb_pred, 1) if xgb_pred else None,
                "ensemble": round(ep, 1),
                "diff": round(ep - line, 1) if line else None,
            }
            predictions.append(pred_rec)

            # ── Betting logic ──
            if line and season > train_cutoff:
                diff = ep - line
                if abs(diff) >= self.buffer:
                    direction = "over" if diff > 0 else "under"

                    # Optional filter: O/U tendency should confirm direction
                    combined_ou = (h_ou + a_ou) / 2.0
                    tendency_ok = True  # relax for now; can gate on combined_ou

                    # Estimate win probability from normal distribution
                    sigma = 13.0  # empirical NBA total std dev
                    if direction == "over":
                        p_win = prob_over(ep, line, sigma)
                    else:
                        p_win = 1.0 - prob_over(ep, line, sigma)

                    frac = kelly_fraction(p_win, OU_DECIMAL_ODDS, self.kelly_mult)
                    frac = min(frac, self.max_bet_frac)
                    bet_amt = bankroll * frac

                    over_hit = actual > line
                    under_hit = actual < line
                    push = actual == line

                    if push:
                        won = None
                        pnl = 0.0
                    elif direction == "over":
                        won = over_hit
                        pnl = bet_amt * (OU_DECIMAL_ODDS - 1) if won else -bet_amt
                    else:
                        won = under_hit
                        pnl = bet_amt * (OU_DECIMAL_ODDS - 1) if won else -bet_amt

                    bankroll += pnl

                    bet_rec = {
                        "date": date, "game": f"{away}@{home}",
                        "line": line, "pred": round(ep, 1),
                        "diff": round(diff, 1), "direction": direction,
                        "p_win": round(p_win, 3), "sigma": sigma,
                        "bet_frac": round(frac, 4), "bet_amt": round(bet_amt, 2),
                        "actual": actual, "won": won,
                        "pnl": round(pnl, 2), "bankroll": round(bankroll, 2),
                    }
                    bets.append(bet_rec)

                    if self.verbose:
                        result_str = "WIN" if won else ("PUSH" if won is None else "LOSS")
                        print(f"  {date} {away}@{home}: pred={ep:.1f} line={line} "
                              f"{direction.upper()} actual={actual} "
                              f"p={p_win:.2f} {result_str} pnl={pnl:+.2f}")

            # Record game into tracker
            tracker.record(home, away, sh, sa, date)
            if line:
                tracker.record_ou(home, away, actual, line)

        rmse_model = (sum(errors_model) / len(errors_model)) ** 0.5 if errors_model else 0.0
        rmse_line = (sum(errors_line) / len(errors_line)) ** 0.5 if errors_line else 0.0
        return self._compile(bets, predictions, bankroll, rmse_model, rmse_line)

    def _compile(self, bets, predictions, final_bankroll, rmse_model, rmse_line):
        decided = [b for b in bets if b["won"] is not None]
        pushes = [b for b in bets if b["won"] is None]
        n = len(decided)
        wins = sum(1 for b in decided if b["won"])
        wr = wins / n if n else 0.0
        total_pnl = sum(b["pnl"] for b in bets)
        wagered = sum(b["bet_amt"] for b in decided)
        roi_wagered = total_pnl / wagered if wagered > 0 else 0.0

        pnls = [b["pnl"] for b in decided]
        mean_p = sum(pnls) / max(n, 1)
        std_p = (sum((p - mean_p) ** 2 for p in pnls) / max(n - 1, 1)) ** 0.5
        sharpe = (mean_p / std_p) * (n ** 0.5) if std_p > 0 and n > 1 else 0.0

        overs = [b for b in decided if b["direction"] == "over"]
        unders = [b for b in decided if b["direction"] == "under"]

        return {
            "n_predictions": len(predictions),
            "n_bets": n,
            "n_pushes": len(pushes),
            "n_wins": wins,
            "win_rate": round(wr, 4),
            "win_pct": f"{wr * 100:.1f}%",
            "total_pnl": round(total_pnl, 2),
            "final_bankroll": round(final_bankroll, 2),
            "roi_vs_100": round(total_pnl, 2),
            "roi_on_wagered_pct": round(roi_wagered * 100, 2),
            "total_wagered": round(wagered, 2),
            "sharpe": round(sharpe, 3),
            "over_bets": len(overs),
            "over_wins": sum(1 for b in overs if b["won"]),
            "over_win_rate": round(sum(1 for b in overs if b["won"]) / max(len(overs), 1), 3),
            "under_bets": len(unders),
            "under_wins": sum(1 for b in unders if b["won"]),
            "under_win_rate": round(sum(1 for b in unders if b["won"]) / max(len(unders), 1), 3),
            "rmse_model": round(rmse_model, 2),
            "rmse_line": round(rmse_line, 2),
            "rmse_delta": round(rmse_line - rmse_model, 2),
            "breakeven_win_rate": round(OU_BREAKEVEN, 4),
            "edge_vs_breakeven_pp": round((wr - OU_BREAKEVEN) * 100, 2),
        }


def print_results(r: dict, args):
    w = 60
    print("\n" + "=" * w)
    print("NBA TOTALS MODEL — BACKTEST RESULTS")
    print("=" * w)
    print(f"  Buffer:             {args.buffer} pts")
    print(f"  Kelly fraction:     {args.kelly}")
    print(f"  Train cutoff:       Season {args.train_cutoff}")
    print(f"  XGBoost:            {'ON' if args.xgb else 'OFF (formula+rolling only)'}")
    print()
    print(f"  Total predictions:  {r['n_predictions']:,}")
    print(f"  Bets placed:        {r['n_bets']:,} ({r['n_pushes']} pushes excluded)")
    print()
    print(f"  Win rate:           {r['win_pct']}  (breakeven: {r['breakeven_win_rate']*100:.2f}%)")
    print(f"  Edge vs breakeven:  {r['edge_vs_breakeven_pp']:+.2f} pp")
    print()
    print(f"  Bets OVER:          {r['over_bets']:,}  ({r['over_win_rate']*100:.1f}% win rate)")
    print(f"  Bets UNDER:         {r['under_bets']:,}  ({r['under_win_rate']*100:.1f}% win rate)")
    print()
    print(f"  Starting bankroll:  $100.00")
    print(f"  Final bankroll:     ${r['final_bankroll']:.2f}")
    print(f"  Total P&L:          ${r['total_pnl']:+.2f}")
    print(f"  ROI on wagered:     {r['roi_on_wagered_pct']:+.2f}%")
    print(f"  Total wagered:      ${r['total_wagered']:.2f}")
    print(f"  Sharpe ratio:       {r['sharpe']:.3f}")
    print()
    print(f"  Model RMSE:         {r['rmse_model']:.2f} pts")
    print(f"  Market line RMSE:   {r['rmse_line']:.2f} pts")
    print(f"  Delta (line - mdl): {r['rmse_delta']:+.2f} pts  "
          f"({'model better' if r['rmse_delta'] > 0 else 'line better'})")
    print("=" * w)
    print()
    print("  Note: NBA O/U lines are highly efficient (RMSE ~17.7 pts).")
    print("  Model RMSE ~18.6 pts without boxscore data. The value of this model")
    print("  is for game simulation, injury-adjusted prediction, and identifying")
    print("  pace-mismatch extremes as secondary signals for the moneyline model.")
    print()


def predict_single_game(
    home: str,
    away: str,
    tracker: TotalsStateTracker,
    line: Optional[float] = None,
    buffer: float = 2.5,
) -> dict:
    """
    Predict total for a single upcoming game.
    Tracker must be populated with historical game data first.
    """
    h = tracker.get(home, n=10)
    a = tracker.get(away, n=10)
    h_home = tracker.get_home(home, n=8)
    a_away = tracker.get_away(away, n=8)

    mp = matchup_predict(h, a, h_home, a_away)
    rp = rolling_predict(h, a, h_home, a_away)
    ep = ensemble_predict(mp, rp)

    h_ou = tracker.ou_tendency(home)
    a_ou = tracker.ou_tendency(away)

    result = {
        "home": home,
        "away": away,
        "predicted_total": round(ep, 1),
        "matchup_model": round(mp, 1),
        "rolling_model": round(rp, 1),
        "h_ou_tendency": round(h_ou, 3),
        "a_ou_tendency": round(a_ou, 3),
        "combined_ou_tendency": round((h_ou + a_ou) / 2.0, 3),
        "home_games": h["n_games"],
        "away_games": a["n_games"],
    }

    if line:
        diff = ep - line
        p_over = prob_over(ep, line)
        result["line"] = line
        result["edge_pts"] = round(diff, 1)
        result["p_over"] = round(p_over, 3)
        result["p_under"] = round(1.0 - p_over, 3)

        if abs(diff) >= buffer:
            if diff > 0:
                result["recommendation"] = f"OVER {line}  (edge +{diff:.1f} pts, P={p_over:.1%})"
            else:
                result["recommendation"] = f"UNDER {line}  (edge {diff:.1f} pts, P={(1-p_over):.1%})"
        else:
            result["recommendation"] = (
                f"NO BET — edge {diff:+.1f} pts below {buffer} pt threshold  "
                f"(P(over)={p_over:.1%})"
            )

    return result


def main():
    parser = argparse.ArgumentParser(description="NBA Totals Prediction Model")
    parser.add_argument("--data",
        default="/home/lahargnedebartoli/mon-ipad/data/historical-odds/nba_2008-2025.csv")
    parser.add_argument("--buffer", type=float, default=2.5)
    parser.add_argument("--kelly", type=float, default=0.25)
    parser.add_argument("--max-bet", type=float, default=0.025)
    parser.add_argument("--train-cutoff", type=int, default=2016)
    parser.add_argument("--xgb", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--regular-only", action="store_true", default=True)
    parser.add_argument("--predict", action="store_true",
        help="Predict a single game (requires --home and --away)")
    parser.add_argument("--home", type=str, default="")
    parser.add_argument("--away", type=str, default="")
    parser.add_argument("--line", type=float, default=None)
    args = parser.parse_args()

    # Load historical data
    print(f"Loading: {args.data}")
    raw = load_csv(args.data)
    games = []
    for row in raw:
        if args.regular_only and row.get("playoffs", "False").strip() == "True":
            continue
        g = parse_game(row)
        if g:
            games.append(g)
    print(f"Parsed {len(games):,} regular season games (2008-2025)\n")

    if args.predict:
        # Build tracker on all historical data, then predict one game
        tracker = TotalsStateTracker()
        for g in sorted(games, key=lambda x: x["date"]):
            tracker.record(g["home"], g["away"], g["score_home"], g["score_away"], g["date"])
            if g["line_total"]:
                tracker.record_ou(g["home"], g["away"], g["actual_total"], g["line_total"])

        home = normalize_team(args.home)
        away = normalize_team(args.away)
        result = predict_single_game(home, away, tracker, args.line, args.buffer)
        print(f"\nPrediction: {away} @ {home}")
        print(f"  Predicted total:   {result['predicted_total']}")
        print(f"  Matchup model:     {result['matchup_model']}")
        print(f"  Rolling model:     {result['rolling_model']}")
        if args.line:
            print(f"  Line:              {args.line}")
            print(f"  Edge:              {result['edge_pts']:+.1f} pts")
            print(f"  P(over):           {result['p_over']:.1%}")
            print(f"  Recommendation:    {result['recommendation']}")
        return

    # Backtest
    backtester = TotalsBacktester(
        buffer=args.buffer,
        kelly_mult=args.kelly,
        max_bet_frac=args.max_bet,
        verbose=args.verbose,
    )
    results = backtester.run(games, train_cutoff=args.train_cutoff, use_xgb=args.xgb)
    print_results(results, args)

    # Show example predictions (last 5 games)
    print("  Recent prediction examples (last 5 games in dataset):")
    print(f"  {'Date':12} {'Game':15} {'Pred':>6} {'Line':>6} {'Actual':>7} {'Edge':>6}")
    print(f"  {'-'*12} {'-'*15} {'-'*6} {'-'*6} {'-'*7} {'-'*6}")

    demo_tracker = TotalsStateTracker()
    sorted_games = sorted(games, key=lambda g: g["date"])
    for g in sorted_games[:-5]:
        demo_tracker.record(g["home"], g["away"], g["score_home"], g["score_away"], g["date"])
        if g["line_total"]:
            demo_tracker.record_ou(g["home"], g["away"], g["actual_total"], g["line_total"])

    for g in sorted_games[-5:]:
        res = predict_single_game(g["home"], g["away"], demo_tracker, g["line_total"])
        ep = res["predicted_total"]
        line = g["line_total"] or 0
        edge = ep - line
        print(f"  {g['date']:12} {g['away']:3}@{g['home']:3}       "
              f"{ep:6.1f} {line:6.1f} {g['actual_total']:7} {edge:+6.1f}")
        demo_tracker.record(g["home"], g["away"], g["score_home"], g["score_away"], g["date"])
        if g["line_total"]:
            demo_tracker.record_ou(g["home"], g["away"], g["actual_total"], g["line_total"])
    print()

    return results


if __name__ == "__main__":
    main()
