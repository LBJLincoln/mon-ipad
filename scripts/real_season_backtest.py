#!/usr/bin/env python3
"""
REAL NBA Strategy Confrontation Backtest
=========================================
2024-25 season (1321 games) with real closing spreads.

TWO MODES:
  - Fixed unit betting ($100/unit, $200/unit, $500/unit)
  - Bankroll percentage (Kelly variants, flat %)

TWO SCENARIOS:
  A) Current model (90% market + 10% Elo) — minimal edge
  B) Target model (75% market + 25% Elo) — meaningful edge

Calibrated: spread_scale=15 (empirical NBA), vig=4.5%, walk-forward Elo (K=20, HA=100).
Moneyline bets only. 1 bet per game. Day-level settlement.
Starting bankroll: $10,000.
"""

import csv
import json
import math
import os
from datetime import datetime
from collections import defaultdict

ODDS_CSV = "/home/termius/mon-ipad/data/historical-odds/nba_2008-2025.csv"
OUTPUT_JSON = "/home/termius/mon-ipad/data/nba-agent/real-strategy-confrontation.json"
SEASON = 2025
BANKROLL = 10000.0

ELO_K = 20
ELO_HA = 100
MAX_EDGE = 0.08
VIG = 0.045
SCALE = 15.0

# ── STRATEGIES ───────────────────────────────────────────────────────────────
# Two categories: fixed-unit and bankroll-percentage

STRATEGIES = {
    # Fixed unit strategies (bet a fixed dollar amount)
    "fixed_$100":       {"mode": "fixed", "unit": 100, "min_e": 0.02},
    "fixed_$200":       {"mode": "fixed", "unit": 200, "min_e": 0.02},
    "fixed_$500":       {"mode": "fixed", "unit": 500, "min_e": 0.02},
    "fixed_$100_high_edge": {"mode": "fixed", "unit": 100, "min_e": 0.04},
    # Kelly / proportional (percentage of bankroll)
    "full_kelly":       {"mode": "pct", "type": "kelly", "frac": 1.0,  "min_e": 0.02, "max_pct": 0.25},
    "half_kelly":       {"mode": "pct", "type": "kelly", "frac": 0.5,  "min_e": 0.02, "max_pct": 0.15},
    "quarter_kelly":    {"mode": "pct", "type": "kelly", "frac": 0.25, "min_e": 0.03, "max_pct": 0.08},
    "eighth_kelly":     {"mode": "pct", "type": "kelly", "frac": 0.125,"min_e": 0.03, "max_pct": 0.05},
    # Flat percentage
    "flat_1pct":        {"mode": "pct", "type": "flat", "pct": 0.01, "min_e": 0.01},
    "flat_2pct":        {"mode": "pct", "type": "flat", "pct": 0.02, "min_e": 0.01},
    "flat_5pct":        {"mode": "pct", "type": "flat", "pct": 0.05, "min_e": 0.02},
    # Value / special
    "value_hunter":     {"mode": "fixed", "unit": 200, "min_e": 0.05},
    "underdog_specialist": {"mode": "fixed", "unit": 150, "min_e": 0.03, "min_odds": 2.2},
    "confidence_scaled": {"mode": "pct", "type": "conf", "min_e": 0.02, "max_pct": 0.10, "scale": 3.0},
    "proportional_edge": {"mode": "pct", "type": "prop", "min_e": 0.02, "max_pct": 0.08, "mult": 2.0},
    "grok_combo":       {"mode": "fixed", "unit": 250, "min_e": 0.04},
}

def sp2p(s, wf, side="home"):
    if s == 0: return 0.5
    fp = 1/(1+10**(-abs(s)/SCALE))
    return (fp if wf == side else 1-fp) if side in ("home", "away") else 0.5

def book_odds(ph):
    ph = max(0.03, min(0.97, ph))
    return 1/(ph*(1+VIG)), 1/((1-ph)*(1+VIG))

def elo_e(a, b):
    return 1/(1+10**((b-a)/400))

def kelly(p, o):
    b = o - 1
    return max(0, (b*p-(1-p))/b) if b > 0 else 0


def load():
    games = []
    with open(ODDS_CSV) as f:
        for r in csv.DictReader(f):
            if int(r['season']) != SEASON: continue
            sh, sa = int(r['score_home']), int(r['score_away'])
            s = float(r['spread']) if r['spread'] else 0
            wf = r['whos_favored']
            th = sp2p(s, wf, "home")
            oh, oa = book_odds(th)
            games.append({
                'd': r['date'], 'h': r['home'], 'a': r['away'],
                'hw': sh > sa, 'th': th, 'oh': oh, 'oa': oa,
                's': s, 'wf': wf, 'po': r['playoffs']=='True'
            })
    return games


def model(games, mw):
    elo = defaultdict(lambda: 1500.0)
    out = []
    for g in games:
        ep = elo_e(elo[g['h']]+ELO_HA, elo[g['a']])
        bl = mw*g['th'] + (1-mw)*ep
        e = bl - g['th']
        if abs(e) > MAX_EDGE: e = MAX_EDGE if e > 0 else -MAX_EDGE; bl = g['th']+e
        bl = max(0.03, min(0.97, bl))
        gc = dict(g)
        gc['mh'] = bl; gc['eh'] = bl - g['th']
        out.append(gc)
        act = 1.0 if g['hw'] else 0.0
        elo[g['h']] += ELO_K*(act-ep)
        elo[g['a']] += ELO_K*((1-act)-(1-ep))
    return out


def run(name, strat, games):
    bank = BANKROLL
    peak = BANKROLL
    max_dd = w = l = bets = 0
    day_rets = []
    streak_w = streak_l = msw = msl = 0
    monthly = defaultdict(float)
    total_staked = 0
    total_profit = 0

    days = defaultdict(list)
    for g in games: days[g['d']].append(g)

    for date in sorted(days):
        if bank < 10:
            day_rets.append(0); continue
        db = bank; pnl = 0

        for g in days[date]:
            ih = 1/g['oh']; ia = 1/g['oa']
            eh = g['mh']-ih; ea = (1-g['mh'])-ia

            if eh >= ea and eh > 0:
                mp, edge, odds, won = g['mh'], eh, g['oh'], g['hw']
            elif ea > 0:
                mp, edge, odds, won = 1-g['mh'], ea, g['oa'], not g['hw']
            else:
                continue

            if edge < strat.get('min_e', 0.02): continue
            if 'min_odds' in strat and odds < strat['min_odds']: continue

            # Compute stake
            if strat['mode'] == 'fixed':
                stake = min(strat['unit'], bank - 1)
            else:
                t = strat['type']
                if t == 'flat': pct = strat['pct']
                elif t == 'conf': pct = min(edge*strat['scale'], strat['max_pct'])
                elif t == 'prop': pct = min(edge*strat['mult'], strat['max_pct'])
                else: pct = min(kelly(mp, odds)*strat['frac'], strat['max_pct'])
                stake = db * pct  # Use day-start bankroll

            if stake < 10 or stake > bank - 1: continue

            bets += 1
            total_staked += stake
            mo = date[:7]

            if won:
                pr = stake*(odds-1)
                pnl += pr; w += 1
                total_profit += pr
                streak_w += 1; streak_l = 0
                msw = max(msw, streak_w)
                monthly[mo] += pr
            else:
                pnl -= stake; l += 1
                total_profit -= stake
                streak_l += 1; streak_w = 0
                msl = max(msl, streak_l)
                monthly[mo] -= stake

        bank += pnl
        bank = max(0, bank)
        day_rets.append(pnl/db if db > 0 else 0)
        peak = max(peak, bank)
        dd = (peak-bank)/peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    roi = (bank-BANKROLL)/BANKROLL*100
    wr = w/(w+l)*100 if (w+l) > 0 else 0
    yield_pct = total_profit/total_staked*100 if total_staked > 0 else 0

    act = [r for r in day_rets if r != 0]
    if len(act) > 10:
        m = sum(act)/len(act)
        v = sum((r-m)**2 for r in act)/(len(act)-1)
        sharpe = (m/math.sqrt(v))*math.sqrt(250) if v > 0 else 0
    else:
        sharpe = 0

    bm = max(monthly.items(), key=lambda x: x[1]) if monthly else ("N/A", 0)
    wm = min(monthly.items(), key=lambda x: x[1]) if monthly else ("N/A", 0)

    return {
        'strategy': name,
        'final': round(bank, 2),
        'roi_pct': round(roi, 2),
        'pnl': round(bank-BANKROLL, 2),
        'bets': bets, 'wins': w, 'losses': l,
        'win_pct': round(wr, 1),
        'yield_pct': round(yield_pct, 2),
        'sharpe': round(sharpe, 3),
        'max_dd_pct': round(max_dd*100, 1),
        'max_w_streak': msw, 'max_l_streak': msl,
        'total_staked': round(total_staked, 0),
        'best_month': bm[0], 'best_month_pnl': round(bm[1], 0),
        'worst_month': wm[0], 'worst_month_pnl': round(wm[1], 0),
    }


def print_results(title, results, W, model_info):
    print(f"\n{'=' * W}")
    print(f"  {title}")
    print(f"  Model: {model_info['desc']} | Brier: {model_info['brier']:.5f} | "
          f"Acc: {model_info['acc']:.1f}% | "
          f"Edges >2%: {model_info['e2']} | >5%: {model_info['e5']}")
    print(f"{'=' * W}")
    print(f"  {'Rk':<3} {'Strategy':<25} {'Final':>11} {'P/L':>10} {'ROI':>8} "
          f"{'Yield':>7} {'Bets':>5} {'W-L':>9} {'WR%':>6} {'Shrp':>6} {'DD%':>6} {'Stk':>4}")
    print("-" * W)

    for i, r in enumerate(results, 1):
        if r['roi_pct'] > 20: t = "***"
        elif r['roi_pct'] > 5: t = "** "
        elif r['roi_pct'] > 0: t = " * "
        elif r['roi_pct'] > -5: t = "   "
        elif r['roi_pct'] > -20: t = " . "
        else: t = " x "

        pnl = f"+${r['pnl']:,.0f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):,.0f}"
        wl = f"{r['wins']}-{r['losses']}"

        print(f"  {i:<3} {r['strategy']:<25} ${r['final']:>10,.2f} {pnl:>10} "
              f"{r['roi_pct']:>+7.1f}% {r['yield_pct']:>+6.1f}% {r['bets']:>5} "
              f"{wl:>9} {r['win_pct']:>5.1f}% {r['sharpe']:>5.2f} "
              f"{r['max_dd_pct']:>5.1f}% {r['max_l_streak']:>3}L {t}")

    print("-" * W)

    prof = [r for r in results if r['roi_pct'] > 0]
    ch = results[0]
    bs = max(results, key=lambda x: x['sharpe'])
    sp = [r for r in prof if r['bets'] > 30]
    sf = min(sp, key=lambda x: x['max_dd_pct']) if sp else None

    print(f"\n  {len(prof)}/{len(results)} PROFITABLE")
    if ch['bets'] > 0:
        print(f"  Champion: {ch['strategy']} -> ${ch['final']:,.2f} ({ch['roi_pct']:+.1f}%) "
              f"yield {ch['yield_pct']:+.1f}% | {ch['bets']} bets | Sharpe {ch['sharpe']:.3f}")
        print(f"    Best month: {ch['best_month']} (${ch['best_month_pnl']:+,.0f}) | "
              f"Worst: {ch['worst_month']} (${ch['worst_month_pnl']:+,.0f})")
    print(f"  Best Sharpe: {bs['strategy']} ({bs['sharpe']:.3f})")
    if sf:
        print(f"  Safest: {sf['strategy']} (DD {sf['max_dd_pct']:.1f}%, ROI {sf['roi_pct']:+.1f}%)")

    grok = next((r for r in results if r['strategy'] == 'grok_combo'), None)
    if grok and grok['bets'] > 0:
        gr = next(i for i, r in enumerate(results, 1) if r['strategy'] == 'grok_combo')
        print(f"  Grok combo: #{gr} -> ${grok['final']:,.2f} ({grok['roi_pct']:+.1f}%)")

    return {'profitable': len(prof), 'champion': ch, 'best_sharpe': bs, 'safest': sf}


def main():
    W = 120

    print("=" * W)
    print("  REAL NBA STRATEGY CONFRONTATION BACKTEST — 2024-25 Season")
    print("  1321 real games | Walk-forward Elo | Calibrated odds | 4.5% vig | $10K bankroll")
    print("  Fixed-unit + Kelly variants | Moneyline only | 1 bet/game max")
    print("=" * W)

    raw = load()
    reg = sum(1 for g in raw if not g['po'])
    hw = sum(1 for g in raw if g['hw'])
    print(f"\n  Season: {len(raw)} games | Regular: {reg} | Playoffs: {len(raw)-reg} | "
          f"Home win: {hw/len(raw)*100:.1f}%")

    all_results = {}

    for scenario, mw, desc in [
        ("A", 0.90, "90% Market + 10% Elo (Current)"),
        ("B", 0.75, "75% Market + 25% Elo (Target)"),
    ]:
        gm = model(raw, mw)
        brier = sum((g['mh']-(1 if g['hw'] else 0))**2 for g in gm)/len(gm)
        acc = sum(1 for g in gm if (g['mh']>0.5)==g['hw'])/len(gm)*100
        edges = sorted(abs(g['eh']) for g in gm)
        e2 = sum(1 for e in edges if e > 0.02)
        e5 = sum(1 for e in edges if e > 0.05)

        mi = {'desc': desc, 'brier': brier, 'acc': acc, 'e2': e2, 'e5': e5,
              'edge_mean': sum(edges)/len(edges)}

        results = []
        for name, strat in STRATEGIES.items():
            results.append(run(name, strat, gm))
        results.sort(key=lambda x: x['roi_pct'], reverse=True)

        info = print_results(f"SCENARIO {scenario}: {desc}", results, W, mi)
        all_results[scenario] = {'model_info': mi, 'results': results, 'analysis': info}

    # ── FINAL VERDICT ─────────────────────────────────────────────────────
    print(f"\n{'=' * W}")
    print("  FINAL VERDICT & RECOMMENDATIONS")
    print(f"{'=' * W}")

    a = all_results['A']
    b = all_results['B']

    print(f"\n  SCENARIO A (Current 90/10): {a['analysis']['profitable']}/16 profitable")
    print(f"  SCENARIO B (Target 75/25):  {b['analysis']['profitable']}/16 profitable")

    print(f"\n  KEY INSIGHTS:")
    print(f"    1. Fixed-unit betting handles variance better than percentage-based")
    print(f"       (underdog-heavy strategy = long losing streaks that crush compounding)")
    print(f"    2. Model predominantly bets underdogs (edge appears on undervalued side)")
    print(f"    3. With edge, YIELD (profit/total_staked) matters more than ROI on bankroll")
    print(f"    4. Elo + market blend gives Brier ~{a['model_info']['brier']:.5f}")
    print(f"    5. Need genuine edge >2% on 300+ games/season for profitability")

    best_overall = b['results'][0] if b['analysis']['profitable'] > 0 else a['results'][0]
    print(f"\n  BEST STRATEGY: {best_overall['strategy']}")
    print(f"    ROI: {best_overall['roi_pct']:+.1f}% | Yield: {best_overall['yield_pct']:+.1f}% | "
          f"Bets: {best_overall['bets']} | Max DD: {best_overall['max_dd_pct']:.1f}%")

    print(f"\n  FOR $1M ROADMAP:")
    print(f"    - Use fixed-unit betting ($100-$250/bet)")
    print(f"    - Minimum edge threshold: 4-5%")
    print(f"    - Target: 200+ bets/season with 5%+ yield")
    print(f"    - Current model needs improvement before deploying real capital")

    # Save
    out = {
        "metadata": {
            "date": datetime.now().isoformat(),
            "season": "2024-25", "games": len(raw),
            "elo_k": ELO_K, "spread_scale": SCALE,
            "vig": VIG, "bankroll": BANKROLL,
        },
        "scenario_a": {
            "model": "90/10 Market/Elo",
            "brier": round(a['model_info']['brier'], 5),
            "profitable": a['analysis']['profitable'],
            "results": a['results'],
        },
        "scenario_b": {
            "model": "75/25 Market/Elo",
            "brier": round(b['model_info']['brier'], 5),
            "profitable": b['analysis']['profitable'],
            "results": b['results'],
        },
        "recommendation": {
            "best_strategy": best_overall['strategy'],
            "key": "Fixed-unit beats percentage-based for underdog-heavy models. "
                   "Need edge >2% on 300+ games. Current Elo insufficient alone."
        },
    }
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(out, f, indent=2)

    print(f"\n  Saved: {OUTPUT_JSON}")
    print("=" * W)


if __name__ == "__main__":
    main()
