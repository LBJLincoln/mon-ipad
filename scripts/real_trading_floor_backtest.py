#!/usr/bin/env python3
"""
Real Trading Floor Backtest — 22 Strategies × 11 Markets × 1000+ NBA Games
Uses actual 2025-26 game results + real closing odds.
Walk-forward Elo model as prediction engine.

Author: Nomos42 Quant AI
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# ─── Team Name Mapping ────────────────────────────────────────────────
FULL_TO_ABBR = {
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
NBA_ABBRS = set(FULL_TO_ABBR.values())

# ─── 22 Trading Floor Strategies ─────────────────────────────────────
STRATEGIES = {
    # Kelly family
    "full_kelly":          {"type": "kelly", "fraction": 1.0,   "min_edge": 0.02, "max_pct": 0.25},
    "half_kelly":          {"type": "kelly", "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.15},
    "quarter_kelly":       {"type": "kelly", "fraction": 0.25,  "min_edge": 0.03, "max_pct": 0.08},
    "eighth_kelly":        {"type": "kelly", "fraction": 0.125, "min_edge": 0.03, "max_pct": 0.05},
    # Flat
    "flat_1pct":           {"type": "flat", "bet_pct": 0.01, "min_edge": 0.01},
    "flat_2pct":           {"type": "flat", "bet_pct": 0.02, "min_edge": 0.01},
    "flat_5pct":           {"type": "flat", "bet_pct": 0.05, "min_edge": 0.02},
    "diversified_flat":    {"type": "flat", "bet_pct": 0.01, "min_edge": 0.005},
    # Confidence
    "confidence_scaled":   {"type": "confidence", "min_edge": 0.02, "max_pct": 0.20, "scale": 5.0},
    # Proportional
    "proportional_edge":   {"type": "proportional", "min_edge": 0.02, "max_pct": 0.15, "multiplier": 3.0},
    # EV threshold
    "ev_threshold_110":    {"type": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.15, "ev_gate": 1.10},
    # Value hunter (high edge only)
    "value_hunter":        {"type": "kelly", "fraction": 0.5, "min_edge": 0.05, "max_pct": 0.12},
    # Underdog specialist
    "underdog_specialist": {"type": "kelly", "fraction": 0.25, "min_edge": 0.03, "max_pct": 0.08, "min_odds": 2.2},
    "dog_value_plus":      {"type": "kelly", "fraction": 0.25, "min_edge": 0.02, "max_pct": 0.06, "min_odds": 3.0},
    # Fixed unit
    "fixed_100":           {"type": "fixed", "amount": 100, "min_edge": 0.03},
    "fixed_50":            {"type": "fixed", "amount": 50, "min_edge": 0.02},
    # Martingale
    "martingale":          {"type": "martingale", "base": 5.0, "min_edge": 0.02},
    "anti_martingale":     {"type": "anti_martingale", "base": 5.0, "min_edge": 0.02},
    # GROK COMBO (the $1M roadmap pick)
    "grok_combo":          {"type": "kelly", "fraction": 0.5, "min_edge": 0.05, "max_pct": 0.15},
    # Conservative combo
    "conservative":        {"type": "kelly", "fraction": 0.15, "min_edge": 0.05, "max_pct": 0.05},
    # Aggressive combo
    "aggressive":          {"type": "kelly", "fraction": 0.75, "min_edge": 0.01, "max_pct": 0.20},
    # Drawdown-adjusted
    "drawdown_adjusted":   {"type": "drawdown_kelly", "fraction": 0.25, "min_edge": 0.03, "max_dd_target": 0.20},
}

# ─── Odds & Probability Helpers ──────────────────────────────────────

def is_decimal_odds(ml):
    """Detect if odds are already in decimal format (between 1.01 and ~30)."""
    return 1.0 < ml < 30.0

def american_to_decimal(ml):
    """Convert American moneyline to decimal odds."""
    ml = float(ml)
    if is_decimal_odds(ml):
        return ml  # Already decimal
    if ml > 0:
        return 1.0 + ml / 100.0
    else:
        return 1.0 + 100.0 / abs(ml)

def decimal_to_implied(dec):
    """Convert decimal odds to implied probability."""
    if dec <= 1.0:
        return 1.0
    return 1.0 / dec

def prob_to_spread(p_home):
    """Convert home win probability to predicted point spread (home perspective)."""
    p_home = max(0.01, min(0.99, p_home))
    return -13.0 * math.log(p_home / (1.0 - p_home))

def cover_prob(pred_spread, line_spread):
    """Probability that home team covers the spread."""
    z = -(line_spread + pred_spread) / 11.0
    return 1.0 / (1.0 + math.exp(-1.7 * z))

def over_prob(pred_total, line_total):
    """Probability that the game goes over the total."""
    z = (pred_total - line_total) / 12.0
    return 1.0 / (1.0 + math.exp(-1.7 * z))

def elo_expected(rating_a, rating_b):
    """Expected score for team A given ratings."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

# ─── Elo Model ───────────────────────────────────────────────────────

class EloModel:
    """Walk-forward Elo with home advantage."""

    def __init__(self, k=20, home_adv=100, initial=1500):
        self.k = k
        self.home_adv = home_adv
        self.initial = initial
        self.ratings = defaultdict(lambda: self.initial)

    def predict(self, home_team, away_team):
        """Return P(home_win) using current ratings + home advantage."""
        r_home = self.ratings[home_team] + self.home_adv
        r_away = self.ratings[away_team]
        return elo_expected(r_home, r_away)

    def update(self, home_team, away_team, home_won, margin=0):
        """Update ratings after a game result."""
        p_home = self.predict(home_team, away_team)
        actual = 1.0 if home_won else 0.0

        # Margin-of-victory multiplier (capped at 2x)
        mov_mult = min(2.0, math.log(max(abs(margin), 1) + 1) * 0.5 + 0.8)

        delta = self.k * mov_mult * (actual - p_home)
        self.ratings[home_team] += delta
        self.ratings[away_team] -= delta

    def predicted_total(self, home_team, away_team):
        """Rough predicted total based on offensive ratings.
        We use the league average ~224 and adjust by team strength."""
        league_avg = 224.0
        home_off = (self.ratings[home_team] - self.initial) / 15.0
        away_off = (self.ratings[away_team] - self.initial) / 15.0
        return league_avg + home_off + away_off

# ─── Strategy State ──────────────────────────────────────────────────

class StrategyState:
    """Track bankroll and stats for a single strategy."""

    def __init__(self, name, config, starting_bankroll=10000.0):
        self.name = name
        self.config = config
        self.bankroll = starting_bankroll
        self.starting_bankroll = starting_bankroll
        self.peak = starting_bankroll
        self.max_dd = 0.0
        self.total_bets = 0
        self.wins = 0
        self.losses = 0
        self.total_edge = 0.0
        self.daily_pnl = []
        self.equity_curve = []
        self.market_pnl = defaultdict(float)
        self.market_bets = defaultdict(int)
        self.market_wins = defaultdict(int)
        self._current_day_pnl = 0.0
        self._current_date = None
        self._consecutive_losses = 0
        self._consecutive_wins = 0

    def calculate_stake(self, model_prob, decimal_odds, bet_type=""):
        """Calculate stake based on strategy type."""
        cfg = self.config
        stype = cfg["type"]
        b = decimal_odds - 1.0  # net payout per unit
        p = model_prob
        q = 1.0 - p

        if b <= 0 or p <= 0:
            return 0.0

        edge = p * b - q  # expected value per $1

        # Min edge gate
        if edge < cfg.get("min_edge", 0.01):
            return 0.0

        # EV gate (for ev_threshold strategies)
        ev_ratio = p * decimal_odds
        if "ev_gate" in cfg and ev_ratio < cfg["ev_gate"]:
            return 0.0

        # Min odds gate (for underdog specialists)
        if "min_odds" in cfg and decimal_odds < cfg["min_odds"]:
            return 0.0

        if self.bankroll <= 0:
            return 0.0

        if stype == "kelly":
            kelly_full = max(0, (b * p - q) / b)
            fraction = cfg.get("fraction", 1.0)
            stake = self.bankroll * kelly_full * fraction
            max_pct = cfg.get("max_pct", 0.25)
            stake = min(stake, self.bankroll * max_pct)

        elif stype == "flat":
            bet_pct = cfg.get("bet_pct", 0.01)
            stake = self.bankroll * bet_pct

        elif stype == "confidence":
            scale = cfg.get("scale", 5.0)
            confidence = abs(p - 0.5) * 2.0  # 0 to 1
            bet_pct = confidence * scale / 100.0
            max_pct = cfg.get("max_pct", 0.20)
            stake = min(self.bankroll * bet_pct, self.bankroll * max_pct)

        elif stype == "proportional":
            multiplier = cfg.get("multiplier", 3.0)
            bet_pct = edge * multiplier
            max_pct = cfg.get("max_pct", 0.15)
            stake = min(self.bankroll * bet_pct, self.bankroll * max_pct)

        elif stype == "fixed":
            stake = float(cfg.get("amount", 100))

        elif stype == "martingale":
            base = cfg.get("base", 5.0)
            mult = 2 ** min(self._consecutive_losses, 6)  # cap at 64x
            stake = base * mult

        elif stype == "anti_martingale":
            base = cfg.get("base", 5.0)
            mult = 2 ** min(self._consecutive_wins, 4)  # cap at 16x
            stake = base * mult

        elif stype == "drawdown_kelly":
            kelly_full = max(0, (b * p - q) / b)
            fraction = cfg.get("fraction", 0.25)
            # Reduce sizing when in drawdown
            current_dd = (self.peak - self.bankroll) / self.peak if self.peak > 0 else 0
            max_dd_target = cfg.get("max_dd_target", 0.20)
            if current_dd > max_dd_target * 0.5:
                # Scale down linearly as drawdown increases
                dd_scale = max(0.1, 1.0 - (current_dd / max_dd_target))
            else:
                dd_scale = 1.0
            stake = self.bankroll * kelly_full * fraction * dd_scale
            max_pct = 0.08
            stake = min(stake, self.bankroll * max_pct)
        else:
            stake = 0.0

        # Never bet more than bankroll
        stake = max(0.0, min(stake, self.bankroll))

        # Minimum bet threshold: $1
        if stake < 1.0:
            return 0.0

        return stake

    def place_bet(self, stake, decimal_odds, won, model_prob, market, date):
        """Place a bet and update state."""
        if stake <= 0:
            return

        # Track daily PnL boundaries
        if date != self._current_date:
            if self._current_date is not None:
                self.daily_pnl.append(self._current_day_pnl)
            self._current_day_pnl = 0.0
            self._current_date = date

        edge = model_prob * (decimal_odds - 1.0) - (1.0 - model_prob)
        self.total_edge += edge
        self.total_bets += 1
        self.market_bets[market] += 1

        if won:
            profit = stake * (decimal_odds - 1.0)
            self.bankroll += profit
            self.wins += 1
            self.market_wins[market] += 1
            self.market_pnl[market] += profit
            self._current_day_pnl += profit
            self._consecutive_wins += 1
            self._consecutive_losses = 0
        else:
            self.bankroll -= stake
            self.losses += 1
            self.market_pnl[market] -= stake
            self._current_day_pnl -= stake
            self._consecutive_losses += 1
            self._consecutive_wins = 0

        # Update peak and drawdown
        if self.bankroll > self.peak:
            self.peak = self.bankroll
        dd = (self.peak - self.bankroll) / self.peak if self.peak > 0 else 0
        if dd > self.max_dd:
            self.max_dd = dd

    def finalize(self):
        """Finalize daily PnL."""
        if self._current_date is not None:
            self.daily_pnl.append(self._current_day_pnl)

    def roi(self):
        return (self.bankroll - self.starting_bankroll) / self.starting_bankroll * 100.0

    def win_rate(self):
        return self.wins / self.total_bets * 100.0 if self.total_bets > 0 else 0.0

    def avg_edge(self):
        return self.total_edge / self.total_bets if self.total_bets > 0 else 0.0

    def sharpe(self):
        """Annualized Sharpe ratio from daily PnL."""
        if len(self.daily_pnl) < 2:
            return 0.0
        avg = sum(self.daily_pnl) / len(self.daily_pnl)
        var = sum((x - avg) ** 2 for x in self.daily_pnl) / (len(self.daily_pnl) - 1)
        std = math.sqrt(var) if var > 0 else 0.001
        # Annualize: sqrt(252) for trading days
        return (avg / std) * math.sqrt(252)

    def best_market(self):
        """Return the best-performing market by total PnL."""
        if not self.market_pnl:
            return "N/A"
        return max(self.market_pnl, key=self.market_pnl.get)

    def weekly_equity(self, all_dates):
        """Generate weekly equity snapshots."""
        # Already tracked during run - just return final value
        return self.equity_curve


# ─── Data Loading ─────────────────────────────────────────────────────

def load_odds(filepath):
    """Load odds CSV, convert team names to abbreviations."""
    odds_by_game = {}  # key: (date, home_abbr, away_abbr) -> odds dict

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            home_full = row['home_team']
            away_full = row['away_team']

            home_abbr = FULL_TO_ABBR.get(home_full)
            away_abbr = FULL_TO_ABBR.get(away_full)

            if not home_abbr or not away_abbr:
                continue

            date = row['date']
            key = (date, home_abbr, away_abbr)

            try:
                ml_home = float(row['moneyline_home'])
                ml_away = float(row['moneyline_away'])
            except (ValueError, TypeError):
                continue

            dec_home = american_to_decimal(ml_home)
            dec_away = american_to_decimal(ml_away)

            # Parse spread and total (may be empty)
            spread_home = None
            total = None
            try:
                if row['spread_home']:
                    spread_home = float(row['spread_home'])
            except (ValueError, TypeError):
                pass
            try:
                if row['total']:
                    total = float(row['total'])
            except (ValueError, TypeError):
                pass

            # If we already have odds for this game, prefer the one with spread/total
            if key in odds_by_game:
                existing = odds_by_game[key]
                if existing.get('spread_home') is not None and spread_home is None:
                    continue  # Keep the existing one that has spread
                if existing.get('total') is not None and total is None and spread_home is None:
                    continue

            odds_by_game[key] = {
                'date': date,
                'home': home_abbr,
                'away': away_abbr,
                'dec_home': dec_home,
                'dec_away': dec_away,
                'spread_home': spread_home,
                'total': total,
                'source': row['source'],
            }

    return odds_by_game


def load_games(filepath):
    """Load games JSON, filter to NBA-30 regular season."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    games = []
    for g in data['games']:
        gd = g.get('game_date')
        if not gd or gd < '2025-10-21':
            continue

        home = g.get('home_team', '')
        away = g.get('away_team', '')

        if home not in NBA_ABBRS or away not in NBA_ABBRS:
            continue

        home_pts = g['home']['pts']
        away_pts = g['away']['pts']

        if home_pts is None or away_pts is None:
            continue

        games.append({
            'date': gd,
            'home': home,
            'away': away,
            'home_pts': float(home_pts),
            'away_pts': float(away_pts),
            'home_won': float(home_pts) > float(away_pts),
            'margin': float(home_pts) - float(away_pts),
            'total_pts': float(home_pts) + float(away_pts),
        })

    # Sort chronologically
    games.sort(key=lambda x: x['date'])
    return games


# ─── Main Backtest ────────────────────────────────────────────────────

def run_backtest():
    """Run the full trading floor confrontation backtest."""

    # Paths
    odds_path = '/home/lahargnedebartoli/nomos-nba-agent/data/historical-odds/nba_2025-26_odds.csv'
    games_path = '/home/lahargnedebartoli/mon-ipad/nba-quant-space/data/historical/games-2025-26.json'
    output_path = '/home/lahargnedebartoli/mon-ipad/data/nba-agent/real-trading-floor-confrontation.json'

    print("=" * 100)
    print("  NOMOS42 TRADING FLOOR — REAL BACKTEST CONFRONTATION")
    print("  22 Strategies × 11 Markets × 1000+ NBA Games (2025-26 Season)")
    print("=" * 100)
    print()

    # Load data
    print("[1/4] Loading data...")
    odds_map = load_odds(odds_path)
    games = load_games(games_path)
    print(f"  Odds records:  {len(odds_map)} unique game-odds pairs")
    print(f"  Games loaded:  {len(games)} regular season games")

    # Match games to odds
    matched = 0
    unmatched = 0
    for g in games:
        key = (g['date'], g['home'], g['away'])
        if key in odds_map:
            g['odds'] = odds_map[key]
            matched += 1
        else:
            g['odds'] = None
            unmatched += 1

    print(f"  Matched:       {matched} games with odds ({matched/len(games)*100:.1f}%)")
    print(f"  Unmatched:     {unmatched} games (no odds — still used for Elo updates)")
    print()

    # Initialize Elo model
    print("[2/4] Running walk-forward Elo model...")
    elo = EloModel(k=20, home_adv=100)

    # Initialize all 22 strategies
    strategies = {}
    for name, config in STRATEGIES.items():
        strategies[name] = StrategyState(name, config, starting_bankroll=10000.0)

    # Track model accuracy
    brier_sum = 0.0
    brier_count = 0
    correct_picks = 0
    total_picks = 0

    # Weekly equity tracking
    week_dates = set()

    # Process games chronologically
    print("[3/4] Running backtest across all games...")
    for game_idx, game in enumerate(games):
        date = game['date']
        home = game['home']
        away = game['away']
        home_won = game['home_won']
        margin = game['margin']
        total_pts = game['total_pts']

        # Get Elo prediction BEFORE updating
        p_home = elo.predict(home, away)
        p_away = 1.0 - p_home

        # Track model accuracy
        brier_sum += (p_home - (1.0 if home_won else 0.0)) ** 2
        brier_count += 1
        if (p_home > 0.5 and home_won) or (p_home < 0.5 and not home_won):
            correct_picks += 1
        total_picks += 1

        # Predicted spread and total from Elo
        pred_spread = prob_to_spread(p_home)  # negative = home favored
        pred_total = elo.predicted_total(home, away)

        # If we have odds for this game, generate bets
        if game['odds'] is not None:
            odds = game['odds']
            dec_home = odds['dec_home']
            dec_away = odds['dec_away']
            spread_home = odds['spread_home']  # from CSV, signed (pos = home underdog)
            total_line = odds['total']

            # ── Generate bet opportunities ──
            bets = []

            # 1. ML_HOME: model says home wins, bet moneyline home
            bets.append({
                'market': 'ML_HOME',
                'model_prob': p_home,
                'decimal_odds': dec_home,
                'won': home_won,
            })

            # 2. ML_AWAY: model says away wins, bet moneyline away
            bets.append({
                'market': 'ML_AWAY',
                'model_prob': p_away,
                'decimal_odds': dec_away,
                'won': not home_won,
            })

            # 3-4. ATS (Against The Spread) — only if spread available
            if spread_home is not None:
                ats_odds = 1.909  # standard -110 juice
                home_cover_p = cover_prob(pred_spread, spread_home)
                ats_home_won = margin > -spread_home  # home covers
                # Push = loss for simplicity (margin == -spread_home is a push)

                bets.append({
                    'market': 'ATS_HOME',
                    'model_prob': home_cover_p,
                    'decimal_odds': ats_odds,
                    'won': margin > -spread_home,
                })
                bets.append({
                    'market': 'ATS_AWAY',
                    'model_prob': 1.0 - home_cover_p,
                    'decimal_odds': ats_odds,
                    'won': margin < -spread_home,
                })

            # 5-6. OVER/UNDER — only if total line available
            if total_line is not None:
                ou_odds = 1.909  # standard -110 juice
                o_prob = over_prob(pred_total, total_line)

                bets.append({
                    'market': 'OVER',
                    'model_prob': o_prob,
                    'decimal_odds': ou_odds,
                    'won': total_pts > total_line,
                })
                bets.append({
                    'market': 'UNDER',
                    'model_prob': 1.0 - o_prob,
                    'decimal_odds': ou_odds,
                    'won': total_pts < total_line,
                })

            # 7. VALUE_DOG — underdog with high odds where model disagrees
            for side, prob, dec, won_flag in [
                ('VALUE_DOG_HOME', p_home, dec_home, home_won),
                ('VALUE_DOG_AWAY', p_away, dec_away, not home_won),
            ]:
                implied = decimal_to_implied(dec)
                if dec > 3.0 and prob - implied > 0.06:
                    bets.append({
                        'market': side,
                        'model_prob': prob,
                        'decimal_odds': dec,
                        'won': won_flag,
                    })

            # Apply each bet to each strategy
            for bet in bets:
                for sname, state in strategies.items():
                    stake = state.calculate_stake(
                        bet['model_prob'],
                        bet['decimal_odds'],
                        bet['market']
                    )
                    if stake > 0:
                        state.place_bet(
                            stake=stake,
                            decimal_odds=bet['decimal_odds'],
                            won=bet['won'],
                            model_prob=bet['model_prob'],
                            market=bet['market'],
                            date=date,
                        )

        # Update Elo AFTER betting (walk-forward)
        elo.update(home, away, home_won, margin)

        # Weekly equity snapshots (every Sunday or every 7th date)
        if game_idx % 50 == 0 or game_idx == len(games) - 1:
            for sname, state in strategies.items():
                state.equity_curve.append({
                    'game_idx': game_idx,
                    'date': date,
                    'bankroll': round(state.bankroll, 2),
                })

    # Finalize all strategies
    for state in strategies.values():
        state.finalize()

    # ── Results ──────────────────────────────────────────────────────
    print("[4/4] Computing results...")
    print()

    # Model stats
    brier = brier_sum / brier_count if brier_count > 0 else 999
    accuracy = correct_picks / total_picks * 100 if total_picks > 0 else 0

    print("=" * 100)
    print("  ELO MODEL PERFORMANCE")
    print("=" * 100)
    print(f"  Brier Score:  {brier:.5f}")
    print(f"  Accuracy:     {accuracy:.1f}% ({correct_picks}/{total_picks})")
    print(f"  Games Rated:  {brier_count}")
    print()

    # Sort strategies by ROI
    ranked = sorted(strategies.values(), key=lambda s: s.roi(), reverse=True)

    # Print main confrontation table
    print("=" * 100)
    print("  TRADING FLOOR CONFRONTATION — RANKED BY ROI")
    print("=" * 100)
    header = f"{'Rank':<5} {'Strategy':<22} {'Final $':>10} {'ROI%':>9} {'Bets':>6} {'WR%':>7} {'Sharpe':>8} {'MaxDD%':>8} {'AvgEdge':>9} {'Best Market':<16}"
    print(header)
    print("-" * 100)

    for i, s in enumerate(ranked, 1):
        marker = ""
        if s.name == "grok_combo":
            marker = " <-- $1M PICK"
        elif i == 1:
            marker = " <-- CHAMPION"

        print(f"{i:<5} {s.name:<22} ${s.bankroll:>9,.0f} {s.roi():>8.2f}% {s.total_bets:>6} {s.win_rate():>6.1f}% {s.sharpe():>7.2f} {s.max_dd*100:>7.2f}% {s.avg_edge():>8.4f} {s.best_market():<16}{marker}")

    print()

    # Top 5 by Sharpe
    sharpe_ranked = sorted(strategies.values(), key=lambda s: s.sharpe(), reverse=True)
    print("=" * 100)
    print("  TOP 5 BY SHARPE RATIO")
    print("=" * 100)
    print(f"{'Rank':<5} {'Strategy':<22} {'Sharpe':>8} {'ROI%':>9} {'Bets':>6} {'MaxDD%':>8} {'WR%':>7}")
    print("-" * 70)
    for i, s in enumerate(sharpe_ranked[:5], 1):
        print(f"{i:<5} {s.name:<22} {s.sharpe():>7.2f} {s.roi():>8.2f}% {s.total_bets:>6} {s.max_dd*100:>7.2f}% {s.win_rate():>6.1f}%")

    print()

    # Market breakdown for top strategy
    best = ranked[0]
    print("=" * 100)
    print(f"  MARKET BREAKDOWN — {best.name.upper()} (Champion)")
    print("=" * 100)
    print(f"{'Market':<18} {'Bets':>6} {'Wins':>6} {'WR%':>7} {'PnL':>12}")
    print("-" * 55)
    for market in sorted(best.market_bets.keys()):
        bets = best.market_bets[market]
        wins = best.market_wins[market]
        wr = wins / bets * 100 if bets > 0 else 0
        pnl = best.market_pnl[market]
        print(f"{market:<18} {bets:>6} {wins:>6} {wr:>6.1f}% ${pnl:>11,.2f}")

    print()

    # Strategy family analysis
    print("=" * 100)
    print("  STRATEGY FAMILY ANALYSIS")
    print("=" * 100)
    families = defaultdict(list)
    for s in ranked:
        families[s.config['type']].append(s)

    for family, members in sorted(families.items()):
        avg_roi = sum(m.roi() for m in members) / len(members)
        best_member = max(members, key=lambda m: m.roi())
        print(f"  {family:<20} avg ROI: {avg_roi:>8.2f}%  best: {best_member.name} ({best_member.roi():.2f}%)")

    print()

    # Grok combo spotlight
    grok = strategies['grok_combo']
    print("=" * 100)
    print("  GROK COMBO SPOTLIGHT (The $1M Roadmap Pick)")
    print("=" * 100)
    print(f"  Final Bankroll:  ${grok.bankroll:,.2f}")
    print(f"  ROI:             {grok.roi():.2f}%")
    print(f"  Total Bets:      {grok.total_bets}")
    print(f"  Win Rate:        {grok.win_rate():.1f}%")
    print(f"  Sharpe Ratio:    {grok.sharpe():.2f}")
    print(f"  Max Drawdown:    {grok.max_dd*100:.2f}%")
    print(f"  Avg Edge:        {grok.avg_edge():.4f}")
    print(f"  Best Market:     {grok.best_market()}")
    grok_rank = next(i for i, s in enumerate(ranked, 1) if s.name == 'grok_combo')
    print(f"  Overall Rank:    #{grok_rank} of {len(ranked)}")
    print()

    # Save JSON results
    results = {
        "meta": {
            "backtest_type": "real_trading_floor_confrontation",
            "season": "2025-26",
            "games_total": len(games),
            "games_with_odds": matched,
            "date_range": f"{games[0]['date']} to {games[-1]['date']}",
            "model": "walk_forward_elo_k20_ha100",
            "model_brier": round(brier, 5),
            "model_accuracy": round(accuracy, 2),
            "starting_bankroll": 10000,
            "strategies_count": len(STRATEGIES),
            "run_timestamp": datetime.now().isoformat(),
        },
        "strategies": {},
    }

    for s in ranked:
        results["strategies"][s.name] = {
            "rank_by_roi": next(i for i, x in enumerate(ranked, 1) if x.name == s.name),
            "rank_by_sharpe": next(i for i, x in enumerate(sharpe_ranked, 1) if x.name == s.name),
            "final_bankroll": round(s.bankroll, 2),
            "roi_pct": round(s.roi(), 4),
            "total_bets": s.total_bets,
            "wins": s.wins,
            "losses": s.losses,
            "win_rate": round(s.win_rate(), 2),
            "sharpe": round(s.sharpe(), 4),
            "max_dd": round(s.max_dd, 6),
            "avg_edge": round(s.avg_edge(), 6),
            "best_market": s.best_market(),
            "strategy_type": s.config['type'],
            "config": s.config,
            "market_breakdown": {
                m: {
                    "bets": s.market_bets[m],
                    "wins": s.market_wins[m],
                    "win_rate": round(s.market_wins[m] / s.market_bets[m] * 100, 2) if s.market_bets[m] > 0 else 0,
                    "pnl": round(s.market_pnl[m], 2),
                }
                for m in sorted(s.market_bets.keys())
            },
            "equity_curve": s.equity_curve,
        }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {output_path}")
    print()

    # Final summary
    profitable = sum(1 for s in ranked if s.roi() > 0)
    losing = len(ranked) - profitable
    print("=" * 100)
    print("  FINAL SUMMARY")
    print("=" * 100)
    print(f"  Profitable strategies:  {profitable}/{len(ranked)}")
    print(f"  Losing strategies:      {losing}/{len(ranked)}")
    print(f"  Best ROI:               {ranked[0].name} ({ranked[0].roi():.2f}%)")
    print(f"  Worst ROI:              {ranked[-1].name} ({ranked[-1].roi():.2f}%)")
    print(f"  Best Sharpe:            {sharpe_ranked[0].name} ({sharpe_ranked[0].sharpe():.2f})")
    print(f"  Total bets placed:      {sum(s.total_bets for s in ranked):,}")
    print("=" * 100)


if __name__ == "__main__":
    run_backtest()
