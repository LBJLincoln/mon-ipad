#!/usr/bin/env python3
"""
Real Prediction Evaluator — Fetches actual NBA results and scores our predictions.
Computes real P&L with Kelly sizing.
Updates Supabase and writes results JSON for dashboard.
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# Output
OUTPUT = Path("/home/termius/mon-ipad/data/nba-agent/backtest-results.json")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    # Try loading from .env.local
    env_file = Path("/home/termius/mon-ipad/.env.local")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                DATABASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

import psycopg2

# ── Step 1: Fetch actual NBA scores ──

def fetch_nba_scores(date_str):
    """Fetch NBA scores for a date from balldontlie API (free, no key needed)."""
    url = f"https://api.balldontlie.io/v1/games?dates[]={date_str}"
    headers = {"Authorization": ""}  # Free tier

    # Try balldontlie first
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            games = data.get("data", [])
            results = []
            for g in games:
                home = g.get("home_team", {}).get("abbreviation", "")
                away = g.get("visitor_team", {}).get("abbreviation", "")
                home_score = g.get("home_team_score", 0)
                away_score = g.get("visitor_team_score", 0)
                status = g.get("status", "")
                if home_score > 0 and away_score > 0:
                    results.append({
                        "home": home, "away": away,
                        "home_score": home_score, "away_score": away_score,
                        "home_win": home_score > away_score
                    })
            if results:
                return results
    except Exception as e:
        print(f"  balldontlie failed for {date_str}: {e}")

    # Fallback: NBA API via nba_api
    try:
        from nba_api.stats.endpoints import ScoreboardV2
        from nba_api.stats.static import teams as nba_teams

        # Convert date format
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        sb = ScoreboardV2(game_date=dt.strftime("%m/%d/%Y"))

        team_map = {t["id"]: t["abbreviation"] for t in nba_teams.get_teams()}
        results = []

        line_score = sb.line_score.get_data_frame()
        if not line_score.empty:
            games = line_score.groupby("GAME_ID")
            for gid, group in games:
                if len(group) >= 2:
                    rows = group.sort_values("TEAM_ABBREVIATION").to_dict("records")
                    # Find home/away
                    for r in rows:
                        pts = r.get("PTS", 0) or 0
                        if pts > 0:
                            pass  # Need more parsing

        return results
    except Exception as e:
        print(f"  nba_api failed for {date_str}: {e}")

    return []

def fetch_scores_from_espn(date_str):
    """Fetch scores from ESPN API."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    espn_date = dt.strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={espn_date}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
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

                home_abbr = home_data.get("team", {}).get("abbreviation", "")
                away_abbr = away_data.get("team", {}).get("abbreviation", "")
                home_score = int(home_data.get("score", "0") or "0")
                away_score = int(away_data.get("score", "0") or "0")
                status = comp.get("status", {}).get("type", {}).get("name", "")

                if home_score > 0 and away_score > 0 and status == "STATUS_FINAL":
                    results.append({
                        "home": home_abbr, "away": away_abbr,
                        "home_score": home_score, "away_score": away_score,
                        "home_win": home_score > away_score
                    })

            return results
    except Exception as e:
        print(f"  ESPN failed for {date_str}: {e}")

    return []

# Team abbreviation mapping (ESPN ↔ our format)
TEAM_MAP = {
    "GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS",
    "LAL": "LAL", "LAC": "LAC", "PHX": "PHX", "BKN": "BKN",
    "WSH": "WAS", "UTAH": "UTA", "PHL": "PHI",
}

def normalize_team(abbr):
    return TEAM_MAP.get(abbr, abbr)

# ── Step 2: Score predictions ──

def run_evaluation():
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=30, options="-c search_path=public")
    cur = conn.cursor()

    # Get all unevaluated predictions
    cur.execute("""
        SELECT id, game_date, home_team, away_team, predicted_home_prob,
               market_odds_home, market_odds_away, edge, confidence
        FROM nba_predictions
        WHERE actual_home_win IS NULL AND game_date < CURRENT_DATE
        ORDER BY game_date
    """)
    predictions = cur.fetchall()
    print(f"Found {len(predictions)} unevaluated predictions")

    if not predictions:
        print("No predictions to evaluate")
        return

    # Get unique dates
    dates = sorted(set(str(p[1]) for p in predictions))
    print(f"Dates to evaluate: {dates}")

    # Fetch results for each date
    all_results = {}
    for date_str in dates:
        print(f"\nFetching scores for {date_str}...")
        results = fetch_scores_from_espn(date_str)
        if not results:
            results = fetch_nba_scores(date_str)

        if results:
            print(f"  Got {len(results)} games")
            for r in results:
                r["home"] = normalize_team(r["home"])
                r["away"] = normalize_team(r["away"])
                key = f"{date_str}_{r['home']}_{r['away']}"
                all_results[key] = r
                print(f"    {r['away']} @ {r['home']}: {r['away_score']}-{r['home_score']} ({'H' if r['home_win'] else 'A'})")
        else:
            print(f"  No results found")

    # Match and evaluate
    initial_bankroll = 100.0
    bankroll = initial_bankroll
    total_bets = 0
    wins = 0
    losses = 0
    total_pnl = 0
    peak = initial_bankroll
    max_dd = 0
    daily_results = []
    evaluated = []

    # Group by date for daily P&L
    from collections import defaultdict
    by_date = defaultdict(list)
    for p in predictions:
        by_date[str(p[1])].append(p)

    for date_str in sorted(by_date.keys()):
        day_preds = by_date[date_str]
        day_bets = 0
        day_wins = 0
        day_pnl = 0

        for pred in day_preds:
            pid, game_date, home, away, model_prob, odds_home, odds_away, edge, conf = pred

            # Try matching
            key = f"{date_str}_{home}_{away}"
            result = all_results.get(key)

            if not result:
                # Try reverse abbreviation matching
                for rkey, r in all_results.items():
                    if rkey.startswith(date_str) and (
                        (r["home"] == home and r["away"] == away) or
                        (r["home"][:3] == home[:3] and r["away"][:3] == away[:3])
                    ):
                        result = r
                        break

            if not result:
                continue

            home_won = result["home_win"]

            # Update Supabase
            cur.execute(
                "UPDATE nba_predictions SET actual_home_win = %s, evaluated_at = NOW() WHERE id = %s",
                (home_won, pid)
            )

            # Calculate bet P&L
            # Only bet when we have positive edge and valid odds
            if odds_home and float(model_prob) > 0 and edge is not None:
                model_p = float(model_prob)

                # Determine if we should bet home or away
                if model_p > 0.5 and odds_home:
                    # Bet home
                    odds = float(odds_home)
                    if odds <= 1.0 or odds > 20:
                        continue  # Skip broken odds

                    implied = 1 / odds
                    real_edge = model_p * odds - 1

                    if real_edge > 0.03:  # 3% min edge
                        # Kelly sizing
                        b = odds - 1
                        q = 1 - model_p
                        kelly_full = max(0, (b * model_p - q) / b)
                        kelly_frac = kelly_full * 0.35  # Aggressive 35% Kelly
                        stake = min(bankroll * kelly_frac, bankroll * 0.05)

                        if stake < 0.50:
                            continue

                        won = home_won
                        pnl = stake * (odds - 1) if won else -stake

                        bankroll += pnl
                        day_pnl += pnl
                        total_pnl += pnl
                        day_bets += 1
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

                        evaluated.append({
                            "date": date_str,
                            "game": f"{away} @ {home}",
                            "model_prob": round(model_p, 4),
                            "odds": odds,
                            "edge": round(real_edge, 4),
                            "stake": round(stake, 2),
                            "won": won,
                            "pnl": round(pnl, 2),
                            "bankroll": round(bankroll, 2),
                        })

                elif model_p < 0.5 and odds_home:
                    # Bet away (implied from home odds)
                    # We'd need away odds — skip if not available
                    pass

        if day_bets > 0:
            daily_results.append({
                "date": date_str,
                "bets": day_bets,
                "wins": day_wins,
                "losses": day_bets - day_wins,
                "pnl": round(day_pnl, 2),
                "bankroll": round(bankroll, 2),
            })

    conn.commit()

    # Build equity curve
    equity_curve = [{"date": daily_results[0]["date"] if daily_results else dates[0], "bankroll": initial_bankroll, "drawdown": 0}]
    running_bankroll = initial_bankroll
    running_peak = initial_bankroll
    for d in daily_results:
        running_bankroll = d["bankroll"]
        if running_bankroll > running_peak:
            running_peak = running_bankroll
        dd = (running_peak - running_bankroll) / running_peak * 100 if running_peak > 0 else 0
        equity_curve.append({"date": d["date"], "bankroll": d["bankroll"], "drawdown": round(dd, 2)})

    # Sharpe ratio
    daily_returns = []
    for d in daily_results:
        prev_br = equity_curve[daily_results.index(d)]["bankroll"]
        if prev_br > 0:
            daily_returns.append(d["pnl"] / prev_br)

    import statistics
    avg_ret = statistics.mean(daily_returns) if daily_returns else 0
    std_ret = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.01
    sharpe = (avg_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0

    roi = ((bankroll - initial_bankroll) / initial_bankroll) * 100
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0

    # Build result
    result = {
        "strategy": "Aggressive Kelly (f=0.35) + Compounding — REAL DATA",
        "data_source": "REAL predictions from nba_predictions table + ESPN actual results",
        "initial_bankroll": initial_bankroll,
        "current_bankroll": round(bankroll, 2),
        "total_roi_pct": round(roi, 2),
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "peak_bankroll": round(peak, 2),
        "avg_edge_pct": round(statistics.mean([e["edge"] * 100 for e in evaluated]) if evaluated else 0, 2),
        "avg_kelly_pct": 0,
        "best_month": {"month": "", "roi_pct": 0},
        "worst_month": {"month": "", "roi_pct": 0},
        "equity_curve": equity_curve,
        "monthly_pnl": [],
        "by_market": {"moneyline": {"bets": total_bets, "wins": wins, "roi_pct": round(roi, 2)}},
        "by_model": {"evolved_ensemble": {"bets": total_bets, "wins": wins, "roi_pct": round(roi, 2), "avg_edge": round(statistics.mean([e["edge"] * 100 for e in evaluated]) if evaluated else 0, 2)}},
        "daily_log": daily_results,
        "trades": evaluated,
        "season_start": str(dates[0]) if dates else "",
        "last_updated": datetime.now().isoformat(),
        "model_version": "v3.0-37cat / TabICL+Trees / Brier 0.21570",
        "brier_score": 0.21570,
        "predictions_evaluated": len([e for e in evaluated]),
        "predictions_total": len(predictions),
        "games_matched": len([1 for p in predictions for k in [f"{p[1]}_{p[2]}_{p[3]}"] if k in all_results]),
    }

    # Save
    OUTPUT.write_text(json.dumps(result, indent=2))
    print(f"\n{'='*60}")
    print(f"  REAL BACKTEST RESULTS")
    print(f"{'='*60}")
    print(f"  Bankroll: ${initial_bankroll} → ${bankroll:.2f} ({roi:+.2f}%)")
    print(f"  Bets: {total_bets} | W: {wins} L: {losses} | Win rate: {win_rate:.1f}%")
    print(f"  Sharpe: {sharpe:.2f} | Max DD: {max_dd:.1f}%")
    print(f"  Predictions matched: {result['games_matched']}/{len(predictions)}")
    print(f"  Saved to {OUTPUT}")
    print(f"{'='*60}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    run_evaluation()
