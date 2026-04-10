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
OUTPUT = Path("/home/lahargnedebartoli/mon-ipad/data/nba-agent/backtest-results.json")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    # Try loading from .env.local
    env_file = Path("/home/lahargnedebartoli/mon-ipad/.env.local")
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

from collections import defaultdict
import statistics

def evaluate_new_predictions(conn, cur):
    """Phase 1: Match unevaluated predictions against ESPN scores."""
    cur.execute("""
        SELECT id, game_date, home_team, away_team, predicted_home_prob,
               market_odds_home, market_odds_away, edge, confidence
        FROM nba_predictions
        WHERE actual_home_win IS NULL AND game_date < CURRENT_DATE
          AND evaluated_at IS NULL
        ORDER BY game_date
    """)
    predictions = cur.fetchall()
    print(f"Found {len(predictions)} unevaluated predictions")

    if not predictions:
        print("No new predictions to evaluate")
        return 0

    dates = sorted(set(str(p[1]) for p in predictions))
    print(f"Dates to evaluate: {dates}")

    # Fetch ESPN results
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

    matched = 0
    for pred in predictions:
        pid, game_date, home, away, model_prob, odds_home, odds_away, edge, conf = pred
        date_str = str(game_date)

        key = f"{date_str}_{home}_{away}"
        result = all_results.get(key)

        if not result:
            for rkey, r in all_results.items():
                if rkey.startswith(date_str) and (
                    (r["home"] == home and r["away"] == away) or
                    (r["home"][:3] == home[:3] and r["away"][:3] == away[:3])
                ):
                    result = r
                    break

        if not result:
            unmatched_days = (datetime.now().date() - datetime.strptime(date_str, "%Y-%m-%d").date()).days
            if unmatched_days >= 3:
                cur.execute(
                    "UPDATE nba_predictions SET evaluated_at = NOW() WHERE id = %s AND evaluated_at IS NULL",
                    (pid,)
                )
                print(f"  PHANTOM: {away} @ {home} on {date_str} — no real game found")
            continue

        home_won = result["home_win"]
        cur.execute(
            "UPDATE nba_predictions SET actual_home_win = %s, evaluated_at = NOW() WHERE id = %s",
            (home_won, pid)
        )
        matched += 1

    conn.commit()
    print(f"\nNewly matched: {matched}/{len(predictions)}")
    return matched


def build_full_backtest(cur):
    """Phase 2: Rebuild full P&L from ALL evaluated predictions."""
    cur.execute("""
        SELECT id, game_date, home_team, away_team, predicted_home_prob,
               market_odds_home, market_odds_away, edge, confidence, actual_home_win
        FROM nba_predictions
        WHERE actual_home_win IS NOT NULL
        ORDER BY game_date, id
    """)
    all_preds = cur.fetchall()
    print(f"\nRebuilding backtest from {len(all_preds)} evaluated predictions")

    initial_bankroll = 100.0
    bankroll = initial_bankroll
    peak = initial_bankroll
    max_dd = 0
    total_bets = 0
    wins = 0
    losses = 0
    evaluated = []
    daily_results = []

    by_date = defaultdict(list)
    for p in all_preds:
        by_date[str(p[1])].append(p)

    for date_str in sorted(by_date.keys()):
        day_preds = by_date[date_str]
        day_bets = 0
        day_wins = 0
        day_pnl = 0

        for pred in day_preds:
            pid, game_date, home, away, model_prob, odds_home, odds_away, edge, conf, actual_home_win = pred

            if float(model_prob) > 0:
                model_p = float(model_prob)
                home_won = bool(actual_home_win)

                # Determine best bet side and correct odds
                bet_odds = None
                bet_on_home = None

                if model_p > 0.5 and odds_home:
                    odds = float(odds_home)
                    if 1.01 < odds <= 15.0:
                        bet_odds = odds
                        bet_on_home = True
                elif model_p < 0.5 and odds_away:
                    odds = float(odds_away)
                    if 1.01 < odds <= 15.0:
                        bet_odds = odds
                        bet_on_home = False

                if bet_odds is not None:
                    bet_prob = model_p if bet_on_home else (1 - model_p)
                    real_edge = bet_prob * bet_odds - 1

                    if real_edge > 0.03:
                        b = bet_odds - 1
                        q = 1 - bet_prob
                        kelly_full = max(0, (b * bet_prob - q) / b)
                        kelly_frac = kelly_full * 0.25  # quarter-Kelly (research-validated)
                        stake = min(bankroll * kelly_frac, bankroll * 0.025)  # 2.5% max

                        if stake < 0.50:
                            continue

                        won = home_won if bet_on_home else (not home_won)
                        pnl = stake * (bet_odds - 1) if won else -stake

                        bankroll += pnl
                        day_pnl += pnl
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

                        bet_side_label = "home" if bet_on_home else "away"
                        bet_team = home if bet_on_home else away
                        evaluated.append({
                            "date": date_str,
                            "game": f"{away} @ {home}",
                            "bet_side": bet_side_label,
                            "bet_team": bet_team,
                            "model_prob": round(bet_prob, 4),
                            "odds": bet_odds,
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

    # Equity curve
    all_dates = sorted(by_date.keys())
    first_date = all_dates[0] if all_dates else "2026-03-19"
    equity_curve = [{"date": first_date, "bankroll": initial_bankroll, "drawdown": 0}]
    for d in daily_results:
        running_peak = max(ec["bankroll"] for ec in equity_curve)
        dd = (running_peak - d["bankroll"]) / running_peak * 100 if running_peak > 0 else 0
        equity_curve.append({"date": d["date"], "bankroll": d["bankroll"], "drawdown": round(dd, 2)})

    # Sharpe
    daily_returns = []
    for i, d in enumerate(daily_results):
        prev_br = daily_results[i-1]["bankroll"] if i > 0 else initial_bankroll
        if prev_br > 0:
            daily_returns.append(d["pnl"] / prev_br)

    avg_ret = statistics.mean(daily_returns) if daily_returns else 0
    std_ret = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.01
    sharpe = (avg_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0

    roi = ((bankroll - initial_bankroll) / initial_bankroll) * 100
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0

    result = {
        "strategy": "Quarter-Kelly (f=0.25) + Compounding — CORRECTED ODDS",
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
        "season_start": first_date,
        "last_updated": datetime.now().isoformat(),
        "model_version": "v3.0-37cat / TabICL+Trees / Brier 0.21570",
        "brier_score": 0.21570,
        "predictions_evaluated": len(evaluated),
        "predictions_total": len(all_preds),
        "games_matched": len(all_preds),
    }

    OUTPUT.write_text(json.dumps(result, indent=2))

    # Also update bankroll-state.json for dashboard
    bankroll_state = {
        "balance": round(bankroll, 2),
        "initial_balance": initial_bankroll,
        "currency": "USD",
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "pushes": 0,
        "pending": 0,
        "total_wagered": round(sum(e["stake"] for e in evaluated), 2),
        "total_profit": round(bankroll - initial_bankroll, 2),
        "peak_balance": round(peak, 2),
        "trough_balance": initial_bankroll,
        "max_drawdown_pct": round(max_dd, 2),
        "streak_current": 0,
        "streak_best": 0,
        "streak_worst": 0,
        "daily_bets_today": 0,
        "daily_profit_today": 0.0,
        "last_bet_ts": evaluated[-1]["date"] + "T00:00:00.000000+00:00" if evaluated else "",
        "last_updated": datetime.now().isoformat() + "+00:00",
        "created": "2026-03-15T11:16:28.623775+00:00",
        "roi_pct": round(roi, 2),
        "win_rate_pct": round(win_rate, 2),
        "sharpe_ratio": round(sharpe, 2),
        "avg_edge_pct": round(statistics.mean([e["edge"] * 100 for e in evaluated]) if evaluated else 0, 2),
        "season_start": result.get("season_start", ""),
        "data_source": "backtest-results.json (synced by evaluate_predictions.py)",
    }
    BANKROLL_OUTPUT = OUTPUT.parent / "bankroll-state.json"
    BANKROLL_OUTPUT.write_text(json.dumps(bankroll_state, indent=2))
    print(f"  Bankroll state synced to {BANKROLL_OUTPUT}")

    print(f"\n{'='*60}")
    print(f"  REAL BACKTEST RESULTS (ALL TIME)")
    print(f"{'='*60}")
    print(f"  Bankroll: ${initial_bankroll} → ${bankroll:.2f} ({roi:+.2f}%)")
    print(f"  Bets: {total_bets} | W: {wins} L: {losses} | Win rate: {win_rate:.1f}%")
    print(f"  Sharpe: {sharpe:.2f} | Max DD: {max_dd:.1f}%")
    print(f"  Evaluated predictions: {len(all_preds)}")
    print(f"  Bettable trades: {len(evaluated)}")
    print(f"  Saved to {OUTPUT}")
    print(f"{'='*60}")

    return result


def run_evaluation():
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=30, options="-c search_path=public")
    cur = conn.cursor()

    # Phase 1: Evaluate new predictions
    evaluate_new_predictions(conn, cur)

    # Phase 2: Rebuild full backtest from ALL evaluated predictions
    build_full_backtest(cur)

    cur.close()
    conn.close()


if __name__ == "__main__":
    run_evaluation()
