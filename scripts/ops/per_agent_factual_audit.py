#!/usr/bin/env python3
"""Per-agent FACTUAL audit across all simmed days.

For each TF (NBA, POL), for each agent:
  - n_days_simmed (saw a day file)
  - n_days_traded (placed >=1 bet that day)
  - n_total_bets, n_total_parlays
  - distinct_categories (set + count)  [POL: distinct event_types]
  - distinct_games / distinct_events
  - mean / median / min / max odds                  [NBA only]
  - mean stake_usd, mean stake_pct, mean edge
  - n_wins / n_losses / win_rate
  - bankroll start -> end -> peak -> trough
  - per-day breakdown (n_bets, n_parlays, distinct_cats_today, mean_odds)

For ITF (different schema — ledger-driven):
  - n_orders, n_fills, distinct_tickers, distinct_strategies
  - mean_notional, total_notional
  - bankroll start -> current

Filters by `written_at >= cutoff` so the broken-parser pre-2026-04-25 archive
is excluded by default. Pass --include-prefix-bug to keep them (useful for A/B).

Output:
  data/audit/per-agent-factual-{tf}-{date}.md
  data/audit/per-agent-factual-{tf}-{date}.json
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, statistics, sys, urllib.parse, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "data" / "audit"
CACHE = REPO / "data" / "tf-analytics-cache"

TOK = (os.environ.get('HF_TOKEN_NBA') or os.environ.get('HF_TOKEN_POL')
       or os.environ.get('HF_TOKEN') or '')
H = {'Authorization': f'Bearer {TOK}'} if TOK else {}

# 2026-04-25: aggregator was 6+ min/run because it re-fetched all 209 POL day
# files every time. Fix: cache by path on disk; only re-fetch the last N days
# (the active ones). Older days never change once written (day_idx monotonic).
LIVE_REFETCH_TAIL = 5

NBA_SPACE = 'LBJLincoln26/nba-llm-trading-floor'
POL_SPACE = 'LBJLincoln26/political-llm-trading-floor'
ITF_SPACE = 'LBJLincoln26/intraday-trading-floor'

# Reset-cutoff: any day file written before this is pre-fix garbage
RESET_CUTOFF_ISO = '2026-04-25T08:00:00Z'


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def list_day_files(space: str) -> list[str]:
    tree = json.loads(http_get(
        f'https://huggingface.co/api/spaces/{space}/tree/main?recursive=true'))
    return sorted(str(f.get('path')) for f in tree
                  if isinstance(f, dict)
                  and str(f.get('path', '')).startswith('data/decisions/day-')
                  and str(f.get('path', '')).endswith('.json'))


def fetch_day(space: str, path: str) -> dict | None:
    try:
        return json.loads(http_get(
            f'https://huggingface.co/spaces/{space}/resolve/main/'
            + urllib.parse.quote(path)))
    except Exception:
        return None


def _cache_path(space: str, path: str) -> Path:
    safe = space.replace('/', '__')
    return CACHE / safe / path.replace('/', '__')


def fetch_day_cached(space: str, path: str, force: bool = False) -> dict | None:
    cp = _cache_path(space, path)
    if not force and cp.exists():
        try:
            return json.loads(cp.read_text())
        except Exception:
            pass
    d = fetch_day(space, path)
    if d is not None:
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(d))
    return d


def fetch_all_days(space: str, post_reset_only: bool = True) -> list[dict]:
    paths = list_day_files(space)
    n_total = len(paths)
    # Force-refetch only the last LIVE_REFETCH_TAIL paths (live activity);
    # serve everything else from disk cache. Cuts per-run fetches from 200+
    # to ~5 once cache is warm.
    live_set = set(paths[-LIVE_REFETCH_TAIL:])
    n_force = sum(1 for p in paths if p in live_set)
    n_cache_hit = sum(1 for p in paths if p not in live_set and _cache_path(space, p).exists())
    n_cold = n_total - n_force - n_cache_hit
    print(f'  {space}: {n_total} day files | refetch_live={n_force} '
          f'cached={n_cache_hit} cold={n_cold}', file=sys.stderr)
    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_day_cached, space, p, p in live_set): p for p in paths}
        for f in as_completed(futs):
            d = f.result()
            if not d: continue
            if post_reset_only and d.get('written_at', '') < RESET_CUTOFF_ISO:
                continue
            out.append(d)
    out.sort(key=lambda x: int(x.get('day_idx', 0)))
    print(f'  {space}: kept {len(out)} (post-reset)' if post_reset_only
          else f'  {space}: kept {len(out)} (all)', file=sys.stderr)
    return out


def aggregate_nba_pol(days: list[dict], event_key: str, cat_key: str) -> dict:
    """event_key='game' or 'event_idx'; cat_key='category' or 'event_type'."""
    by_agent: dict[str, dict] = defaultdict(lambda: {
        'n_days_simmed': 0, 'n_days_traded': 0,
        'n_total_bets': 0, 'n_total_parlays': 0,
        'categories': Counter(), 'events_or_games': Counter(),
        'odds_list': [], 'stake_pcts': [], 'stake_usd': [],
        'edges': [], 'confidences': [],
        'wins': 0, 'losses': 0, 'unsettled': 0,
        'pnl_total': 0.0,
        'bankroll_start': None, 'bankroll_end': None,
        'bankroll_peak': None, 'bankroll_trough': None,
        'per_day': [],
    })

    for day in days:
        ag = day.get('agents') or {}
        d_idx = day.get('day_idx')
        d_date = day.get('date')
        for tid, a in ag.items():
            if not isinstance(a, dict): continue
            agg = by_agent[tid]
            agg['n_days_simmed'] += 1

            allocs = a.get('allocations') or []
            parlays = a.get('parlays') or []
            n_bets = len(allocs)
            n_par = len(parlays)
            if n_bets > 0 or n_par > 0:
                agg['n_days_traded'] += 1
            agg['n_total_bets'] += n_bets
            agg['n_total_parlays'] += n_par

            day_cats = Counter()
            day_events = Counter()
            day_odds = []
            for al in allocs:
                if not isinstance(al, dict): continue
                cat = al.get(cat_key) or '?'
                ev = al.get(event_key) or al.get('ticker') or '?'
                agg['categories'][cat] += 1
                agg['events_or_games'][str(ev)] += 1
                day_cats[cat] += 1
                day_events[str(ev)] += 1

                stake = float(al.get('stake') or 0)
                pct = float(al.get('pct') or 0)
                edge = float(al.get('edge') or 0)
                conf = float(al.get('confidence') or 0)
                odds = al.get('odds')
                if odds is not None:
                    try:
                        o = float(odds)
                        if o > 1.0:
                            agg['odds_list'].append(o); day_odds.append(o)
                    except Exception: pass
                if stake > 0: agg['stake_usd'].append(stake)
                if pct > 0: agg['stake_pcts'].append(pct)
                if edge > 0: agg['edges'].append(edge)
                if conf > 0: agg['confidences'].append(conf)

                won = al.get('won')
                if won is True: agg['wins'] += 1
                elif won is False: agg['losses'] += 1
                else: agg['unsettled'] += 1
                pnl = al.get('profit') or al.get('pnl_pct') or 0
                try: agg['pnl_total'] += float(pnl or 0)
                except Exception: pass

            bk_b = a.get('bankroll_before')
            bk_a = a.get('bankroll_after')
            if bk_b is not None and agg['bankroll_start'] is None:
                agg['bankroll_start'] = float(bk_b)
            if bk_a is not None:
                agg['bankroll_end'] = float(bk_a)
                if agg['bankroll_peak'] is None or float(bk_a) > agg['bankroll_peak']:
                    agg['bankroll_peak'] = float(bk_a)
                if agg['bankroll_trough'] is None or float(bk_a) < agg['bankroll_trough']:
                    agg['bankroll_trough'] = float(bk_a)

            agg['per_day'].append({
                'day_idx': d_idx, 'date': d_date,
                'n_bets': n_bets, 'n_parlays': n_par,
                'distinct_cats': len(day_cats),
                'distinct_events': len(day_events),
                'mean_odds': round(statistics.mean(day_odds), 3) if day_odds else None,
                'pnl': round(float(bk_a or 0) - float(bk_b or 0), 2) if (bk_b is not None and bk_a is not None) else None,
            })

    # Finalize
    out = {}
    for tid, agg in by_agent.items():
        odds = agg['odds_list']
        out[tid] = {
            'n_days_simmed': agg['n_days_simmed'],
            'n_days_traded': agg['n_days_traded'],
            'n_total_bets': agg['n_total_bets'],
            'n_total_parlays': agg['n_total_parlays'],
            'distinct_categories': len(agg['categories']),
            'distinct_events_or_games': len(agg['events_or_games']),
            'top_categories': agg['categories'].most_common(8),
            'odds_stats': {
                'n': len(odds),
                'mean': round(statistics.mean(odds), 3) if odds else None,
                'median': round(statistics.median(odds), 3) if odds else None,
                'min': round(min(odds), 3) if odds else None,
                'max': round(max(odds), 3) if odds else None,
            },
            'mean_stake_usd': round(statistics.mean(agg['stake_usd']), 2) if agg['stake_usd'] else None,
            'mean_stake_pct': round(statistics.mean(agg['stake_pcts']), 4) if agg['stake_pcts'] else None,
            'mean_edge': round(statistics.mean(agg['edges']), 4) if agg['edges'] else None,
            'mean_confidence': round(statistics.mean(agg['confidences']), 3) if agg['confidences'] else None,
            'wins': agg['wins'], 'losses': agg['losses'], 'unsettled': agg['unsettled'],
            'win_rate': round(agg['wins'] / (agg['wins'] + agg['losses']), 4)
                       if (agg['wins'] + agg['losses']) > 0 else None,
            'pnl_total': round(agg['pnl_total'], 2),
            'bankroll_start': agg['bankroll_start'],
            'bankroll_end': agg['bankroll_end'],
            'bankroll_peak': agg['bankroll_peak'],
            'bankroll_trough': agg['bankroll_trough'],
            'per_day': agg['per_day'],
        }
    return out


def render_md(tf: str, agg: dict, n_days: int) -> str:
    lines = [
        f'# {tf.upper()} — per-agent factual audit',
        f'Generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
        f'Days simmed: {n_days}  |  reset cutoff: {RESET_CUTOFF_ISO}',
        '',
        '## Aggregate (sorted by total bets)',
        '',
        '| agent | days_traded | bets | parlays | distinct_cats | mean_odds | mean_edge | mean_stake | W-L | WR | bankroll | PnL |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    items = sorted(agg.items(), key=lambda kv: -kv[1]['n_total_bets'])
    for tid, a in items:
        odds = a['odds_stats']['mean']
        odds_s = f'{odds:.2f}' if odds else '—'
        edge_s = f'{a["mean_edge"]:.3f}' if a['mean_edge'] else '—'
        stake_s = f'${a["mean_stake_usd"]:.2f}' if a['mean_stake_usd'] else '—'
        wr_s = f'{a["win_rate"]*100:.1f}%' if a['win_rate'] is not None else '—'
        bk = f'${a["bankroll_start"]:.0f}→${a["bankroll_end"]:.0f}' if (a['bankroll_start'] is not None and a['bankroll_end'] is not None) else '—'
        lines.append(f'| `{tid}` | {a["n_days_traded"]}/{a["n_days_simmed"]} | {a["n_total_bets"]} | {a["n_total_parlays"]} | {a["distinct_categories"]} | {odds_s} | {edge_s} | {stake_s} | {a["wins"]}-{a["losses"]} | {wr_s} | {bk} | {a["pnl_total"]:+.1f} |')
    lines.append('')
    lines.append('## Per-agent top categories')
    for tid, a in items:
        if a['n_total_bets'] == 0: continue
        top = ', '.join(f'`{c}`×{n}' for c, n in a['top_categories'][:6])
        lines.append(f'- **{tid}** ({a["distinct_categories"]} cats): {top}')
    lines.append('')
    lines.append('## Odds distribution per agent')
    for tid, a in items:
        if a['odds_stats']['n'] == 0: continue
        s = a['odds_stats']
        lines.append(f'- **{tid}** n={s["n"]} mean={s["mean"]} median={s["median"]} min={s["min"]} max={s["max"]}')
    return '\n'.join(lines)


def fetch_alpaca_orders(limit: int = 500) -> list[dict]:
    """Pull recent orders directly from Alpaca paper API. Real-time, bypasses
    Hub-sync lag on ledger.jsonl."""
    key = os.environ.get('ALPACA_PAPER_KEY') or os.environ.get('ALPACA_API_KEY','')
    sec = os.environ.get('ALPACA_PAPER_SECRET') or os.environ.get('ALPACA_SECRET_KEY','')
    if not (key and sec): return []
    url = f'https://paper-api.alpaca.markets/v2/orders?status=all&limit={limit}&direction=desc'
    try:
        req = urllib.request.Request(url, headers={
            'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': sec, 'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f'[alpaca] orders err: {e}', file=sys.stderr)
        return []


def aggregate_itf() -> dict:
    """Pull ITF agent_ledger.jsonl + agent_bankrolls.json from HF + Alpaca-direct order stream."""
    bk_url = f'https://huggingface.co/spaces/{ITF_SPACE}/resolve/main/data/intraday/agent_bankrolls.json'
    led_url = f'https://huggingface.co/spaces/{ITF_SPACE}/resolve/main/data/intraday/agent_ledger.jsonl'
    try:
        bk = json.loads(http_get(bk_url))
    except Exception:
        bk = {}
    try:
        ledger_raw = http_get(led_url, timeout=60).decode('utf-8', errors='replace')
        ledger = [json.loads(l) for l in ledger_raw.splitlines() if l.strip()]
    except Exception:
        ledger = []

    # Alpaca-direct order stream (real-time, no Hub-sync lag)
    alpaca_orders = fetch_alpaca_orders(limit=500)
    alpaca_status_c = Counter(o.get('status','?') for o in alpaca_orders)
    n_filled = alpaca_status_c.get('filled', 0)
    n_rejected = alpaca_status_c.get('rejected', 0)
    n_canceled = alpaca_status_c.get('canceled', 0) + alpaca_status_c.get('cancelled', 0)
    n_pending = sum(alpaca_status_c.get(s,0) for s in ('new','accepted','partially_filled','pending_new'))
    n_total_alpaca = len(alpaca_orders)
    fill_rate_alpaca = n_filled / max(n_total_alpaca, 1)
    alpaca_summary = {
        'n_orders_last_500': n_total_alpaca,
        'status_counts': dict(alpaca_status_c),
        'filled': n_filled, 'rejected': n_rejected, 'canceled': n_canceled, 'pending': n_pending,
        'fill_rate': round(fill_rate_alpaca, 3),
    }
    print(f'[ITF Alpaca-direct] orders={n_total_alpaca} filled={n_filled} '
          f'rejected={n_rejected} canceled={n_canceled} pending={n_pending} '
          f'fill_rate={fill_rate_alpaca*100:.0f}%', file=sys.stderr)
    by_agent = defaultdict(lambda: {
        'n_orders': 0, 'n_fills': 0, 'tickers': Counter(), 'strategies': Counter(),
        'sides': Counter(), 'notional_list': [], 'realized_pnl': 0.0,
    })
    for e in ledger:
        if not isinstance(e, dict): continue
        tid = e.get('tid') or e.get('agent') or '?'
        if tid == '?': continue
        ev = e.get('event') or ''
        agg = by_agent[tid]
        if 'order' in ev or ev.startswith('place'):
            agg['n_orders'] += 1
        if 'fill' in ev:
            agg['n_fills'] += 1
        tk = e.get('ticker') or ''
        if tk: agg['tickers'][tk] += 1
        st = e.get('strategy') or e.get('side') or ''
        if st: agg['strategies'][st] += 1
        side = e.get('side') or ''
        if side: agg['sides'][side] += 1
        try:
            qty = float(e.get('qty') or 0); pr = float(e.get('price') or 0)
            if qty and pr: agg['notional_list'].append(qty * pr)
        except Exception: pass
        try: agg['realized_pnl'] += float(e.get('realized_pnl') or 0)
        except Exception: pass

    out = {}
    bk_meta = bk.get('_meta', {}) if isinstance(bk, dict) else {}
    for tid, a in by_agent.items():
        ns = a['notional_list']
        out[tid] = {
            'n_orders': a['n_orders'], 'n_fills': a['n_fills'],
            'distinct_tickers': len(a['tickers']),
            'distinct_strategies': len(a['strategies']),
            'top_tickers': a['tickers'].most_common(8),
            'top_strategies': a['strategies'].most_common(8),
            'mean_notional': round(statistics.mean(ns), 2) if ns else None,
            'total_notional': round(sum(ns), 2),
            'realized_pnl': round(a['realized_pnl'], 2),
            'bankroll': bk.get(tid) if isinstance(bk, dict) else None,
        }
    return {'meta': bk_meta, 'agents': out, 'alpaca_direct': alpaca_summary}


def render_itf_md(itf: dict) -> str:
    meta = itf.get('meta', {})
    alp = itf.get('alpaca_direct', {})
    lines = [
        '# ITF — per-agent factual audit',
        f'Generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
        f'Seed: ${meta.get("seed_share_usd","?")} per agent at {meta.get("seeded_at","?")} (n_agents={meta.get("n_agents","?")})',
        '',
        '## Alpaca-direct fill rate (real-time, bypasses Hub-sync)',
        f'- last 500 orders: filled={alp.get("filled","?")} rejected={alp.get("rejected","?")} '
        f'canceled={alp.get("canceled","?")} pending={alp.get("pending","?")} | '
        f'**fill_rate={alp.get("fill_rate","?")*100 if alp.get("fill_rate") is not None else "?":.0f}%**'
            if isinstance(alp.get("fill_rate"), float) else '- alpaca creds missing',
        f'- status counts: {alp.get("status_counts", {})}',
        '',
        '## Per-agent (from Hub ledger — may lag real-time)',
        '| agent | orders | fills | distinct_tickers | distinct_strategies | mean_notional | total_notional | realized_pnl | bankroll |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    items = sorted(itf['agents'].items(), key=lambda kv: -kv[1]['n_fills'])
    for tid, a in items:
        bk = f'${a["bankroll"]:.0f}' if isinstance(a['bankroll'], (int, float)) else '—'
        mn = f'${a["mean_notional"]:.2f}' if a['mean_notional'] else '—'
        lines.append(f'| `{tid}` | {a["n_orders"]} | {a["n_fills"]} | {a["distinct_tickers"]} | {a["distinct_strategies"]} | {mn} | ${a["total_notional"]:.0f} | {a["realized_pnl"]:+.2f} | {bk} |')
    lines.append('')
    lines.append('## Per-agent top tickers')
    for tid, a in items:
        if a['n_fills'] == 0: continue
        top = ', '.join(f'{t}×{n}' for t, n in a['top_tickers'][:6])
        lines.append(f'- **{tid}** ({a["distinct_tickers"]} tickers): {top}')
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--include-prefix-bug', action='store_true',
                   help='include pre-2026-04-25 broken-parser data')
    p.add_argument('--tf', choices=['nba','pol','itf','all'], default='all')
    args = p.parse_args()
    AUDIT.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    post = not args.include_prefix_bug

    if args.tf in ('nba','all'):
        print('[NBA] fetching days...', file=sys.stderr)
        days = fetch_all_days(NBA_SPACE, post_reset_only=post)
        agg = aggregate_nba_pol(days, event_key='game', cat_key='category')
        (AUDIT / f'per-agent-factual-nba-{today}.json').write_text(
            json.dumps({'n_days': len(days), 'agents': agg}, indent=2, default=str))
        (AUDIT / f'per-agent-factual-nba-{today}.md').write_text(
            render_md('NBA', agg, len(days)))
        print(f'[NBA] wrote {AUDIT}/per-agent-factual-nba-{today}.md', file=sys.stderr)

    if args.tf in ('pol','all'):
        print('[POL] fetching days...', file=sys.stderr)
        days = fetch_all_days(POL_SPACE, post_reset_only=post)
        agg = aggregate_nba_pol(days, event_key='event_idx', cat_key='event_type')
        (AUDIT / f'per-agent-factual-pol-{today}.json').write_text(
            json.dumps({'n_days': len(days), 'agents': agg}, indent=2, default=str))
        (AUDIT / f'per-agent-factual-pol-{today}.md').write_text(
            render_md('POL', agg, len(days)))
        print(f'[POL] wrote {AUDIT}/per-agent-factual-pol-{today}.md', file=sys.stderr)

    if args.tf in ('itf','all'):
        print('[ITF] fetching ledger...', file=sys.stderr)
        itf = aggregate_itf()
        (AUDIT / f'per-agent-factual-itf-{today}.json').write_text(
            json.dumps(itf, indent=2, default=str))
        (AUDIT / f'per-agent-factual-itf-{today}.md').write_text(render_itf_md(itf))
        print(f'[ITF] wrote {AUDIT}/per-agent-factual-itf-{today}.md', file=sys.stderr)


if __name__ == '__main__':
    main()
