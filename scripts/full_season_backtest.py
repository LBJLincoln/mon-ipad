#!/usr/bin/env python3
"""
Full Season Backtest — All 2025-26 games with real market odds.
Runs our best model predictions against real closing moneylines.
Computes true ROI, Sharpe, Brier, Kelly-optimal bankroll trajectory.

Usage:
  python3 scripts/full_season_backtest.py [--from-supabase] [--from-csv PATH]
"""
import json, os, sys, csv, math
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ── Config ──
INITIAL_BANKROLL = 100.0
KELLY_FRACTION = 0.25         # Quarter-Kelly (research-validated)
MAX_BET_FRACTION = 0.025      # 2.5% max per position
MAX_PORTFOLIO_EXPOSURE = 0.25 # 25% max nightly exposure
MIN_EDGE_THRESHOLD = 0.03     # 3% minimum expected value
MIN_STAKE = 0.50              # Minimum $0.50 bet

_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = _ROOT / "data" / "nba-agent"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── American → Decimal odds conversion ──
def american_to_decimal(ml):
    """Convert American moneyline to decimal odds."""
    if ml is None or ml == 0:
        return None
    ml = float(ml)
    if ml > 0:
        return 1.0 + ml / 100.0
    else:
        return 1.0 + 100.0 / abs(ml)

def decimal_to_implied_prob(odds):
    """Convert decimal odds to implied probability (no vig removal)."""
    if odds is None or odds <= 1.0:
        return None
    return 1.0 / odds

# ── Load historical odds from CSV ──
def load_odds_csv(path):
    """Load historical odds from Kaggle CSV format.
    Expected columns: date, home, away, moneyline_home, moneyline_away (or similar)."""
    odds = {}

    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        print(f"  CSV columns: {cols}")

        for row in reader:
            # Handle Kaggle format: season,date,away,home,score_away,score_home,...,moneyline_away,moneyline_home
            date = row.get('date', row.get('game_date', ''))
            home = row.get('home', row.get('home_team', '')).upper()
            away = row.get('away', row.get('away_team', '')).upper()

            # Normalize team abbrevs
            home = normalize_team(home)
            away = normalize_team(away)

            ml_home = row.get('moneyline_home', row.get('ml_home', ''))
            ml_away = row.get('moneyline_away', row.get('ml_away', ''))

            # Score
            score_home = row.get('score_home', row.get('home_score', ''))
            score_away = row.get('score_away', row.get('away_score', ''))

            if ml_home and ml_away and ml_home != '' and ml_away != '':
                try:
                    ml_h = float(ml_home)
                    ml_a = float(ml_away)
                    home_win = None
                    if score_home and score_away:
                        try:
                            home_win = int(float(score_home)) > int(float(score_away))
                        except:
                            pass

                    key = f"{date}_{home}_{away}"
                    odds[key] = {
                        'date': date,
                        'home': home,
                        'away': away,
                        'ml_home': ml_h,
                        'ml_away': ml_a,
                        'odds_home': american_to_decimal(ml_h),
                        'odds_away': american_to_decimal(ml_a),
                        'home_win': home_win,
                    }
                except ValueError:
                    continue

    print(f"  Loaded {len(odds)} games with moneylines")
    return odds

# Team normalization
TEAM_MAP = {
    "GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS",
    "WSH": "WAS", "UTAH": "UTA", "PHL": "PHI",
    "PHO": "PHX", "BRK": "BKN", "CHA": "CHO",
    "POR": "POR", "SA": "SAS",
    # lowercase
    "gs": "GSW", "ny": "NYK", "no": "NOP", "sa": "SAS",
    "por": "POR", "phi": "PHI", "hou": "HOU", "lal": "LAL",
    "lac": "LAC", "bkn": "BKN", "bos": "BOS", "chi": "CHI",
    "cle": "CLE", "dal": "DAL", "den": "DEN", "det": "DET",
    "gsw": "GSW", "ind": "IND", "mem": "MEM", "mia": "MIA",
    "mil": "MIL", "min": "MIN", "nop": "NOP", "nyk": "NYK",
    "okc": "OKC", "orl": "ORL", "phx": "PHX", "sac": "SAC",
    "sas": "SAS", "tor": "TOR", "uta": "UTA", "was": "WAS",
    "atl": "ATL", "cha": "CHA", "utah": "UTA",
}

def normalize_team(abbr):
    return TEAM_MAP.get(abbr, abbr.upper() if isinstance(abbr, str) else abbr)

# ── Load predictions from Supabase ──
def load_predictions_supabase():
    """Load all predictions from Supabase."""
    import psycopg2

    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    if not DATABASE_URL:
        env_file = _ROOT / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    DATABASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        return []

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, game_date, home_team, away_team, predicted_home_prob,
               market_odds_home, market_odds_away, actual_home_win
        FROM nba_predictions
        ORDER BY game_date, id
    """)
    rows = cur.fetchall()
    conn.close()

    predictions = []
    for row in rows:
        predictions.append({
            'id': row[0],
            'date': str(row[1]),
            'home': row[2],
            'away': row[3],
            'predicted_home_prob': float(row[4]) if row[4] else None,
            'odds_home': float(row[5]) if row[5] else None,
            'odds_away': float(row[6]) if row[6] else None,
            'actual_home_win': row[7],
        })

    print(f"Loaded {len(predictions)} predictions from Supabase")
    return predictions

# ── Betting simulation ──
def simulate_betting(predictions, external_odds=None):
    """
    Simulate Kelly betting on predictions.
    If external_odds provided, override prediction odds with real market odds.
    """
    bankroll = INITIAL_BANKROLL
    peak = INITIAL_BANKROLL
    max_dd = 0
    total_bets = 0
    wins = 0
    losses = 0
    trades = []
    daily_results = []
    brier_scores = []

    by_date = defaultdict(list)
    for p in predictions:
        by_date[p['date']].append(p)

    for date_str in sorted(by_date.keys()):
        day_preds = by_date[date_str]
        day_bets = 0
        day_wins = 0
        day_pnl = 0
        day_exposure = 0

        for pred in day_preds:
            model_p = pred.get('predicted_home_prob')
            if model_p is None or model_p <= 0:
                continue

            actual = pred.get('actual_home_win')

            # Get odds — prefer external real odds if available
            odds_home = pred.get('odds_home')
            odds_away = pred.get('odds_away')

            if external_odds:
                key = f"{date_str}_{pred['home']}_{pred['away']}"
                ext = external_odds.get(key)
                if ext:
                    odds_home = ext.get('odds_home', odds_home)
                    odds_away = ext.get('odds_away', odds_away)
                    if actual is None:
                        actual = ext.get('home_win')

            # Brier score (regardless of bet)
            if actual is not None:
                outcome = 1.0 if actual else 0.0
                brier_scores.append((model_p - outcome) ** 2)

            # Determine bet side
            bet_odds = None
            bet_on_home = None

            if model_p > 0.5 and odds_home and 1.01 < odds_home <= 15.0:
                bet_odds = odds_home
                bet_on_home = True
            elif model_p < 0.5 and odds_away and 1.01 < odds_away <= 15.0:
                bet_odds = odds_away
                bet_on_home = False

            if bet_odds is None:
                continue

            bet_prob = model_p if bet_on_home else (1 - model_p)
            real_edge = bet_prob * bet_odds - 1

            if real_edge < MIN_EDGE_THRESHOLD:
                continue

            # Kelly sizing
            b = bet_odds - 1
            q = 1 - bet_prob
            kelly_full = max(0, (b * bet_prob - q) / b) if b > 0 else 0
            kelly_frac = kelly_full * KELLY_FRACTION
            stake = min(bankroll * kelly_frac, bankroll * MAX_BET_FRACTION)

            # Portfolio exposure cap
            if day_exposure + stake > bankroll * MAX_PORTFOLIO_EXPOSURE:
                stake = max(0, bankroll * MAX_PORTFOLIO_EXPOSURE - day_exposure)

            if stake < MIN_STAKE:
                continue

            if actual is None:
                # Game not yet played — record as pending
                continue

            # Resolve bet
            won = actual if bet_on_home else (not actual)
            pnl = stake * (bet_odds - 1) if won else -stake

            bankroll += pnl
            day_pnl += pnl
            day_bets += 1
            day_exposure += stake
            total_bets += 1

            if won:
                wins += 1
                day_wins += 1
            else:
                losses += 1

            if bankroll > peak:
                peak = bankroll
            dd = (peak - bankroll) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

            bet_side_label = "home" if bet_on_home else "away"
            bet_team = pred['home'] if bet_on_home else pred['away']
            trades.append({
                "date": date_str,
                "game": f"{pred['away']} @ {pred['home']}",
                "bet_side": bet_side_label,
                "bet_team": bet_team,
                "model_prob": round(bet_prob, 4),
                "odds": round(bet_odds, 2),
                "edge": round(real_edge, 4),
                "stake": round(stake, 2),
                "won": won,
                "pnl": round(pnl, 2),
                "bankroll": round(bankroll, 2),
            })

        if day_bets > 0:
            daily_results.append({
                "date": date_str,
                "bets": day_bets,
                "wins": day_wins,
                "losses": day_bets - day_wins,
                "pnl": round(day_pnl, 2),
                "bankroll": round(bankroll, 2),
            })

    # Compute metrics
    roi_pct = (bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100
    win_rate = wins / total_bets * 100 if total_bets > 0 else 0
    brier = sum(brier_scores) / len(brier_scores) if brier_scores else None

    # Sharpe ratio (daily returns)
    if len(daily_results) >= 2:
        daily_returns = [d['pnl'] / max(1, d['bankroll'] - d['pnl']) for d in daily_results]
        mean_ret = sum(daily_returns) / len(daily_returns)
        var_ret = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        std_ret = var_ret ** 0.5
        sharpe = (mean_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0
    else:
        daily_returns = []
        sharpe = 0

    # Sortino ratio (penalizes downside volatility only)
    if len(daily_returns) >= 2:
        downside = [min(0, r) for r in daily_returns]
        downside_var = sum(d ** 2 for d in downside) / (len(downside) - 1)
        downside_std = downside_var ** 0.5
        sortino = (mean_ret / downside_std) * (252 ** 0.5) if downside_std > 0 else 0
    else:
        sortino = 0

    # Calmar ratio (annualized return / max drawdown)
    ann_return = roi_pct * 252 / max(1, len(daily_results))
    calmar = ann_return / max_dd if max_dd > 0 else 0

    # Profit factor (gross wins / gross losses)
    gross_wins = sum(t['pnl'] for t in trades if t['won'])
    gross_losses = abs(sum(t['pnl'] for t in trades if not t['won']))
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')

    # Streak tracking
    win_streak = 0
    lose_streak = 0
    max_win_streak = 0
    max_lose_streak = 0
    for t in trades:
        if t['won']:
            win_streak += 1
            lose_streak = 0
            max_win_streak = max(max_win_streak, win_streak)
        else:
            lose_streak += 1
            win_streak = 0
            max_lose_streak = max(max_lose_streak, lose_streak)

    # Average edge on placed bets
    avg_edge = sum(t['edge'] for t in trades) / len(trades) if trades else 0

    return {
        "initial_bankroll": INITIAL_BANKROLL,
        "final_bankroll": round(bankroll, 2),
        "roi_pct": round(roi_pct, 2),
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "calmar": round(calmar, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else None,
        "max_dd": round(max_dd, 2),
        "win_streak_max": max_win_streak,
        "lose_streak_max": max_lose_streak,
        "avg_edge": round(avg_edge, 4),
        "brier": round(brier, 5) if brier else None,
        "brier_n": len(brier_scores),
        "trades": trades,
        "daily_results": daily_results,
        "strategy": f"Quarter-Kelly (f={KELLY_FRACTION}) + Portfolio Cap ({MAX_PORTFOLIO_EXPOSURE*100}%) + Real Market Odds",
    }

# ── Main ──
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Full Season Backtest with Real Odds")
    parser.add_argument("--from-supabase", action="store_true", help="Load predictions from Supabase")
    parser.add_argument("--from-csv", type=str, help="Path to historical odds CSV")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "full-season-backtest.json"))
    args = parser.parse_args()

    print("=" * 60)
    print("  FULL SEASON BACKTEST — Real Market Odds")
    print("=" * 60)

    # Load external odds if available
    external_odds = None
    csv_paths = [
        args.from_csv,
        "data/historical-odds/nba_2025-26_odds.csv",
        "data/historical-odds/nba_2008-2025.csv",
    ]

    for path in csv_paths:
        if path and os.path.exists(path):
            print(f"\nLoading external odds from: {path}")
            external_odds = load_odds_csv(path)
            break

    # Load predictions
    predictions = []
    if args.from_supabase:
        predictions = load_predictions_supabase()

    if not predictions:
        print("\nNo predictions loaded. Use --from-supabase or check connection.")
        sys.exit(1)

    # Run simulation
    print(f"\nSimulating {len(predictions)} predictions...")
    results = simulate_betting(predictions, external_odds)

    # Display results
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print(f"  Bankroll: ${INITIAL_BANKROLL} → ${results['final_bankroll']} ({results['roi_pct']:+.2f}%)")
    print(f"  Bets: {results['total_bets']} | W: {results['wins']} L: {results['losses']} | Win rate: {results['win_rate']}%")
    print(f"  Sharpe: {results['sharpe']} | Sortino: {results['sortino']} | Calmar: {results['calmar']}")
    print(f"  Max DD: {results['max_dd']}% | Profit Factor: {results['profit_factor']}")
    print(f"  Streaks: {results['win_streak_max']}W max / {results['lose_streak_max']}L max | Avg Edge: {results['avg_edge']:.4f}")
    if results['brier']:
        print(f"  Brier: {results['brier']:.5f} ({results['brier_n']} games)")
    print(f"  Strategy: {results['strategy']}")
    print("=" * 60)

    # Print trades
    if results['trades']:
        print(f"\n  {'Date':12s} {'Game':22s} {'Side':5s} {'Team':4s} {'Odds':>6s} {'Edge':>7s} {'Stake':>7s} {'W/L':3s} {'P&L':>8s} {'Bank':>8s}")
        print("  " + "-" * 90)
        for t in results['trades']:
            wl = "W" if t['won'] else "L"
            print(f"  {t['date']:12s} {t['game']:22s} {t['bet_side']:5s} {t['bet_team']:4s} {t['odds']:6.2f} {t['edge']:7.4f} ${t['stake']:6.2f} {wl:3s} ${t['pnl']:7.2f} ${t['bankroll']:7.2f}")

    # Save
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to {args.output}")

    # Daily P&L summary
    if results['daily_results']:
        print(f"\n  Daily Summary:")
        for d in results['daily_results']:
            emoji = "+" if d['pnl'] >= 0 else ""
            print(f"    {d['date']}: {d['bets']} bets, {d['wins']}W-{d['losses']}L, {emoji}${d['pnl']:.2f} → ${d['bankroll']:.2f}")

if __name__ == "__main__":
    main()
