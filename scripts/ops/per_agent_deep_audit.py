#!/usr/bin/env python3
"""Deep per-agent forensic audit — answers WHY this odd was chosen vs another.

For each TF (NBA, POL, PQTF) walks every cached day file and emits, per agent:
  - day_idx, date
  - per game/event/session: every bet with category/odds/edge/stake/rationale/won/profit
  - day_strategy + cash_rationale narrative

Plus per-game cross-agent matrix: for a given (date, game), what every agent
chose AND why — so divergence is visible at a glance.

For ITF (different schema — no day files, sparse ledger): pulls
agent_ledger.jsonl + Alpaca orders + live /api/decisions snapshot.

Outputs (all under data/audit/):
  per-agent-deep-{tf}-{date}.json     — full nested data dump
  per-agent-deep-{tf}-{date}.md       — top-level summary, last N days expanded
  per-game-deep-{tf}-{date}.md        — per-(date,game) cross-agent matrix
  per-agent-deep/{tf}/{agent}.md      — full narrative trail per agent

Reuses caching from per_agent_factual_audit.py.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys, urllib.parse, urllib.request
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Reuse the existing aggregator's caching layer
sys.path.insert(0, str(Path(__file__).resolve().parent))
from per_agent_factual_audit import (  # type: ignore
    fetch_all_days, fetch_day_cached, http_get,
    NBA_SPACE, POL_SPACE, ITF_SPACE, RESET_CUTOFF_ISO,
    fetch_alpaca_orders,
)

PQTF_SPACE = 'LBJLincoln26/political-quant-trading-floor'

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / 'data' / 'audit'
AUDIT_PER_AGENT = AUDIT / 'per-agent-deep'

# Last N days expanded inline in the rollup MD (whole history is in JSON)
EXPAND_LAST_N_DAYS = 14
# Rationale truncation to keep MD readable
RATIONALE_TRUNC = 240


def _trunc(s, n=RATIONALE_TRUNC):
    if not s: return ''
    s = str(s).replace('\n', ' ').replace('|', '/').strip()
    return s if len(s) <= n else s[:n-1] + '…'


def _emoji(won):
    if won is True:  return '✓'
    if won is False: return '✗'
    return '·'


# -------------------- NBA / POL deep extract --------------------

def deep_extract_nba_pol(days, tf, event_key, cat_key, rationale_key='rationale'):
    """Returns dict[agent] -> list[day_dict] sorted by day_idx ascending.
    day_dict = {day_idx, date, bankroll_before, bankroll_after, day_strategy,
                cash_rationale, allocations: [...], parlays: [...]}.
    Also returns by_game for cross-agent matrix:
        by_game[(date, game)] -> list of (tid, alloc_dict).
    """
    by_agent = defaultdict(list)
    by_game = defaultdict(list)
    for day in days:
        d_idx = day.get('day_idx')
        d_date = day.get('date')
        ag = day.get('agents') or {}
        for tid, a in ag.items():
            if not isinstance(a, dict): continue
            allocs = a.get('allocations') or []
            parlays = a.get('parlays') or []
            day_dict = {
                'day_idx': d_idx, 'date': d_date,
                'bankroll_before': a.get('bankroll_before'),
                'bankroll_after': a.get('bankroll_after'),
                'day_strategy': _trunc(a.get('day_strategy'), 600),
                'cash_rationale': _trunc(a.get('cash_rationale'), 300),
                'cash_held_pct': a.get('cash_held_pct'),
                'fallback_used': a.get('fallback_used'),
                'provider_status': a.get('provider_status'),
                'allocations': [],
                'parlays': [],
            }
            for al in allocs:
                if not isinstance(al, dict): continue
                row = {
                    'event': str(al.get(event_key) or al.get('ticker') or '?'),
                    'category': al.get(cat_key),
                    'odds': al.get('odds'),
                    'pct': al.get('pct'),
                    'stake': al.get('stake'),
                    'edge': al.get('edge'),
                    # 2026-04-25 NBA engine-edge override telemetry — present on
                    # bets parsed AFTER the override ship (HF 873fa2a20d25).
                    # Lets audit distinguish engine-validated bets from LLM-only.
                    'edge_source': al.get('edge_source'),
                    'edge_llm_reported': al.get('edge_llm_reported'),
                    'edge_engine': al.get('edge_engine'),
                    'confidence': al.get('confidence'),
                    'rationale': _trunc(al.get(rationale_key) or al.get('thesis')),
                    'won': al.get('won'),
                    'profit': al.get('profit'),
                    'pnl_pct': al.get('pnl_pct'),
                    'excess_return': al.get('excess_return'),
                    'direction': al.get('direction'),
                    'agency': al.get('agency'),
                }
                day_dict['allocations'].append(row)
                key = (d_date, row['event'])
                by_game[key].append((tid, row))
            for pl in parlays:
                if not isinstance(pl, dict): continue
                day_dict['parlays'].append({
                    'n_legs': pl.get('n_legs'),
                    'combined_odds': pl.get('combined_odds'),
                    'pct': pl.get('pct'),
                    'stake': pl.get('stake'),
                    'edge': pl.get('edge'),
                    'confidence': pl.get('confidence'),
                    'rationale': _trunc(pl.get('rationale')),
                    'won': pl.get('won'),
                    'profit': pl.get('profit'),
                    'legs': [
                        {
                            'event': str(l.get(event_key) or l.get('ticker') or '?'),
                            'category': l.get(cat_key),
                            'odds': l.get('odds'),
                            'won': l.get('won'),
                        } for l in (pl.get('legs') or []) if isinstance(l, dict)
                    ],
                })
            by_agent[tid].append(day_dict)
    # sort each agent's days
    for tid in by_agent:
        by_agent[tid].sort(key=lambda d: (d.get('day_idx') or 0))
    return dict(by_agent), dict(by_game)


# -------------------- PQTF deep extract --------------------

def fetch_pqtf_days():
    """PQTF schema differs: top-level keys = date, sessions[], agents_start, agents_end."""
    H = {}
    tok = os.environ.get('HF_TOKEN_NBA') or os.environ.get('HF_TOKEN', '')
    if tok: H['Authorization'] = f'Bearer {tok}'
    tree = json.loads(http_get(
        f'https://huggingface.co/api/spaces/{PQTF_SPACE}/tree/main?recursive=true'))
    paths = sorted(str(f.get('path')) for f in tree if isinstance(f, dict)
                   and str(f.get('path', '')).startswith('data/decisions/day-')
                   and str(f.get('path', '')).endswith('.json'))
    print(f'  {PQTF_SPACE}: {len(paths)} day files', file=sys.stderr)
    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        # PQTF is FROZEN — use cache liberally; only refetch latest 2.
        live_set = set(paths[-2:])
        futs = {ex.submit(fetch_day_cached, PQTF_SPACE, p, p in live_set): p for p in paths}
        for f in as_completed(futs):
            d = f.result()
            if d: out.append(d)
    out.sort(key=lambda x: x.get('date', ''))
    return out


def deep_extract_pqtf(days):
    """PQTF: sessions[].positions[] with rationale + reasoning_template + pnl."""
    by_agent = defaultdict(list)
    by_game = defaultdict(list)  # (date, etf) -> list[(tid, position)]
    for day_idx, d in enumerate(days):
        d_date = d.get('date')
        sessions = d.get('sessions') or []
        agents_end = d.get('agents_end') or {}
        agents_start = d.get('agents_start') or {}
        # Roll up positions per agent across sessions
        per_agent_today = defaultdict(lambda: {
            'day_idx': day_idx, 'date': d_date,
            'bankroll_before': None, 'bankroll_after': None,
            'positions': [],
        })
        for sess in sessions:
            if not isinstance(sess, dict): continue
            for pos in (sess.get('positions') or []):
                if not isinstance(pos, dict): continue
                tid = pos.get('tid') or '?'
                row = {
                    'session': sess.get('session_id'),
                    'etf': pos.get('etf'),
                    'option_type': pos.get('option_type'),
                    'strike': pos.get('strike'),
                    'spot_open': pos.get('spot_open'),
                    'spot_close': pos.get('spot_close'),
                    'tte_days': pos.get('tte_days'),
                    'qty': pos.get('qty'),
                    'multi_leg': pos.get('multi_leg'),
                    'iv_open': pos.get('iv_open'),
                    'entry_price': pos.get('entry_price'),
                    'mark': pos.get('mark'),
                    'cost': pos.get('cost'),
                    'pnl': pos.get('pnl'),
                    'event_idx': pos.get('event_idx'),
                    'reasoning_template': pos.get('reasoning_template'),
                    'rationale': _trunc(pos.get('rationale')),
                }
                per_agent_today[tid]['positions'].append(row)
                by_game[(d_date, pos.get('etf') or '?')].append((tid, row))
        for tid, day_dict in per_agent_today.items():
            day_dict['bankroll_before'] = agents_start.get(tid)
            day_dict['bankroll_after'] = agents_end.get(tid)
            by_agent[tid].append(day_dict)
    for tid in by_agent:
        by_agent[tid].sort(key=lambda d: d.get('date', ''))
    return dict(by_agent), dict(by_game)


# -------------------- ITF deep extract --------------------

def deep_extract_itf():
    """ITF has no day files. Dump ledger events grouped by agent +
    Alpaca orders (last 500) + live /api/decisions snapshot."""
    H = {}
    tok = os.environ.get('HF_TOKEN_NBA') or os.environ.get('HF_TOKEN', '')
    if tok: H['Authorization'] = f'Bearer {tok}'
    led_url = f'https://huggingface.co/spaces/{ITF_SPACE}/resolve/main/data/intraday/agent_ledger.jsonl'
    bk_url  = f'https://huggingface.co/spaces/{ITF_SPACE}/resolve/main/data/intraday/agent_bankrolls.json'
    pos_url = f'https://huggingface.co/spaces/{ITF_SPACE}/resolve/main/data/intraday/positions.json'

    try:
        ledger_raw = http_get(led_url, timeout=60).decode('utf-8', errors='replace')
        ledger = [json.loads(l) for l in ledger_raw.splitlines() if l.strip()]
    except Exception as e:
        print(f'[ITF] ledger fetch err: {e}', file=sys.stderr); ledger = []
    try: bk = json.loads(http_get(bk_url))
    except Exception: bk = {}
    try: positions = json.loads(http_get(pos_url))
    except Exception: positions = []

    # live /api/decisions
    decisions = []
    try:
        req = urllib.request.Request(
            'https://lbjlincoln26-intraday-trading-floor.hf.space/api/decisions?limit=200')
        with urllib.request.urlopen(req, timeout=30) as r:
            decisions = json.loads(r.read()).get('decisions') or []
    except Exception as e:
        print(f'[ITF] /api/decisions err: {e}', file=sys.stderr)

    # Alpaca orders (real-time)
    orders = fetch_alpaca_orders(limit=500)

    # Group ledger by agent
    by_agent = defaultdict(lambda: {
        'events': [], 'broker_rejects': [], 'open_fills': [],
        'reserves': [], 'credits': [],
    })
    for e in ledger:
        if not isinstance(e, dict): continue
        tid = e.get('tid') or e.get('agent_tid') or '?'
        if tid == '?': continue
        ev = e.get('event', '')
        agg = by_agent[tid]
        agg['events'].append(e)
        if ev == 'broker_reject': agg['broker_rejects'].append(e)
        elif ev == 'open_fill_confirm': agg['open_fills'].append(e)
        elif ev == 'reserve': agg['reserves'].append(e)
        elif ev == 'credit': agg['credits'].append(e)

    # Reject reason histogram per agent
    by_agent_summary = {}
    for tid, agg in by_agent.items():
        reject_reasons = Counter(e.get('reason_code') or e.get('reason') or '?'
                                 for e in agg['broker_rejects'])
        by_agent_summary[tid] = {
            'n_events': len(agg['events']),
            'n_reserves': len(agg['reserves']),
            'n_credits': len(agg['credits']),
            'n_broker_rejects': len(agg['broker_rejects']),
            'n_open_fills': len(agg['open_fills']),
            'reject_reasons_top': reject_reasons.most_common(8),
            'bankroll': bk.get(tid) if isinstance(bk, dict) else None,
            'recent_rejects': [
                {'ts': e.get('ts'), 'ticker': e.get('ticker'),
                 'reason': e.get('reason_code') or e.get('reason'),
                 'side': e.get('side'), 'stake': e.get('stake')}
                for e in agg['broker_rejects'][-12:]
            ],
            'recent_fills': [
                {'ts': e.get('ts'), 'ticker': e.get('ticker'),
                 'side': e.get('fill_side') or e.get('side'),
                 'broker_order_id': e.get('broker_order_id')}
                for e in agg['open_fills'][-12:]
            ],
        }

    return {
        'meta': bk.get('_meta', {}) if isinstance(bk, dict) else {},
        'by_agent': by_agent_summary,
        'positions_snapshot': positions if isinstance(positions, list) else [],
        'live_decisions_snapshot': decisions[:50],
        'recent_alpaca_orders': [
            {'created_at': o.get('created_at'), 'symbol': o.get('symbol'),
             'side': o.get('side'), 'qty': o.get('qty'), 'notional': o.get('notional'),
             'order_class': o.get('order_class'), 'order_type': o.get('order_type'),
             'status': o.get('status'), 'filled_avg_price': o.get('filled_avg_price'),
             'failed_at': o.get('failed_at')}
            for o in (orders or [])[:120]
        ],
        'order_status_summary': dict(Counter(o.get('status', '?') for o in (orders or []))),
    }


# -------------------- Renderers --------------------

def render_per_agent_md(tf, tid, days, schema='nba'):
    """Per-agent narrative trail: every day, every bet, with rationale."""
    lines = [f'# {tf.upper()} — `{tid}` decision trail',
             f'Generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
             f'{len(days)} days with activity', '']
    if not days:
        lines.append('_No days with activity._')
        return '\n'.join(lines)
    bk_first = next((d.get('bankroll_before') for d in days
                     if isinstance(d.get('bankroll_before'), (int, float))), None)
    bk_last = next((d.get('bankroll_after') for d in reversed(days)
                    if isinstance(d.get('bankroll_after'), (int, float))), None)
    if bk_first is not None and bk_last is not None:
        lines.append(f'**Bankroll**: ${bk_first:.2f} → ${bk_last:.2f} ({bk_last-bk_first:+.2f})')
        lines.append('')
    for d in days:
        n_alloc = len(d.get('allocations') or d.get('positions') or [])
        n_par = len(d.get('parlays') or [])
        if n_alloc == 0 and n_par == 0:
            continue
        bb = d.get('bankroll_before'); ba = d.get('bankroll_after')
        bb_s = f'${bb:.2f}' if isinstance(bb, (int, float)) else '—'
        ba_s = f'${ba:.2f}' if isinstance(ba, (int, float)) else '—'
        lines.append(f'## Day {d.get("day_idx")} — {d.get("date")} '
                     f'(bankroll: {bb_s} → {ba_s})')
        if d.get('day_strategy'):
            lines.append(f'> **Strategy:** {d["day_strategy"]}')
        if d.get('cash_rationale'):
            lines.append(f'> **Cash:** {d.get("cash_held_pct") or 0}% — {d["cash_rationale"]}')
        lines.append('')
        if schema == 'pqtf':
            lines.append('| sess | ETF | type | strike | qty | entry | mark | pnl | template | rationale |')
            lines.append('|---:|---|---|---:|---:|---:|---:|---:|---|---|')
            def _fmt(v, spec):
                if isinstance(v, (int, float)):
                    return format(v, spec)
                return '—'
            for p in d.get('positions', []):
                lines.append(f'| {p.get("session","")} | {p.get("etf","")} | '
                             f'{p.get("option_type","")} | {_fmt(p.get("strike"), ".2f")} | '
                             f'{p.get("qty","")} | {_fmt(p.get("entry_price"), ".4f")} | '
                             f'{_fmt(p.get("mark"), ".4f")} | {_fmt(p.get("pnl"), "+.2f")} | '
                             f'{p.get("reasoning_template","")} | {p.get("rationale","")} |')
        else:
            lines.append('| event | category | odds | edge | stake | won | profit | rationale |')
            lines.append('|---|---|---:|---:|---:|:---:|---:|---|')
            for al in d.get('allocations', []):
                odds = al.get('odds')
                odds_s = f'{odds:.2f}' if isinstance(odds, (int, float)) else '—'
                edge = al.get('edge')
                edge_s = f'{edge:.3f}' if isinstance(edge, (int, float)) else '—'
                stake = al.get('stake')
                stake_s = f'${stake:.2f}' if isinstance(stake, (int, float)) else '—'
                profit = al.get('profit')
                profit_s = f'{profit:+.2f}' if isinstance(profit, (int, float)) else '—'
                cat = al.get('category') or al.get('event_type') or ''
                if al.get('direction'):
                    cat = f'{cat}:{al["direction"]}'
                lines.append(f'| {al.get("event","")} | {cat} | {odds_s} | {edge_s} | '
                             f'{stake_s} | {_emoji(al.get("won"))} | {profit_s} | '
                             f'{al.get("rationale","")} |')
            if d.get('parlays'):
                lines.append('')
                lines.append('**Parlays:**')
                for p in d['parlays']:
                    legs = ' + '.join(f'{l.get("event","")}:{l.get("category","")}'
                                      f'@{l.get("odds",0):.2f}{_emoji(l.get("won"))}'
                                      for l in (p.get('legs') or []))
                    lines.append(f'- {p.get("n_legs",0)}-leg @{(p.get("combined_odds") or 0):.2f} '
                                 f'stake=${(p.get("stake") or 0):.2f} '
                                 f'edge={(p.get("edge") or 0):.3f} '
                                 f'won={_emoji(p.get("won"))} profit={(p.get("profit") or 0):+.2f} '
                                 f'\n  legs: {legs}'
                                 f'\n  > {p.get("rationale","")}')
        lines.append('')
    return '\n'.join(lines)


def render_per_game_md(tf, by_game, schema='nba', last_n_days=14):
    """Cross-agent matrix per (date, game): which agents bet which odd, with rationale.
    Shows last N distinct dates."""
    # Group by date for sorting / capping
    dates = sorted({k[0] for k in by_game.keys()}, reverse=True)
    keep_dates = set(dates[:last_n_days])
    lines = [f'# {tf.upper()} — per-game cross-agent forensic',
             f'Generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
             f'Last {last_n_days} dates expanded ({len(by_game)} total game-rows in JSON)',
             '',
             '> Reads: for each (date, game/event), which agents picked WHAT and WHY.',
             '> Use to spot consensus vs divergence, and identify why agents diverged.',
             '']
    grouped = defaultdict(list)
    for (date, game), bets in by_game.items():
        if date not in keep_dates: continue
        grouped[date].append((game, bets))
    for date in sorted(grouped.keys(), reverse=True):
        lines.append(f'## {date}')
        for game, bets in sorted(grouped[date], key=lambda x: x[0]):
            lines.append(f'### {game} ({len(bets)} bet{"s" if len(bets)!=1 else ""})')
            lines.append('| agent | category | odds | edge | stake | won | rationale |')
            lines.append('|---|---|---:|---:|---:|:---:|---|')
            for tid, al in sorted(bets, key=lambda x: -(x[1].get('stake') or 0)):
                odds = al.get('odds')
                odds_s = f'{odds:.2f}' if isinstance(odds, (int, float)) else '—'
                edge = al.get('edge')
                edge_s = f'{edge:.3f}' if isinstance(edge, (int, float)) else '—'
                stake = al.get('stake')
                stake_s = f'${stake:.2f}' if isinstance(stake, (int, float)) else '—'
                cat = al.get('category') or al.get('event_type') or ''
                if al.get('direction'): cat = f'{cat}:{al["direction"]}'
                lines.append(f'| `{tid}` | {cat} | {odds_s} | {edge_s} | {stake_s} | '
                             f'{_emoji(al.get("won"))} | {al.get("rationale","")} |')
            lines.append('')
    return '\n'.join(lines)


def render_rollup_md(tf, by_agent, n_days, schema='nba'):
    """Top-level summary; expanded last N days inline."""
    lines = [f'# {tf.upper()} — per-agent deep audit (rollup)',
             f'Generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
             f'Total simmed days: {n_days}',
             f'Per-agent narrative files: `data/audit/per-agent-deep/{tf}/<agent>.md`',
             '']
    if schema != 'pqtf':
        lines.append(f'Reset cutoff: {RESET_CUTOFF_ISO}  (post-fix data only)')
        lines.append('')
    # per-agent quick stats
    lines.append('## Activity summary')
    lines.append('| agent | days_active | total_bets | bankroll_path |')
    lines.append('|---|---:|---:|---|')
    rows = []
    for tid, days in by_agent.items():
        active = sum(1 for d in days if (d.get('allocations') or d.get('positions')))
        bets = sum(len(d.get('allocations') or d.get('positions') or []) for d in days)
        bk_first = next((d.get('bankroll_before') for d in days
                         if d.get('bankroll_before') is not None), None)
        bk_last = next((d.get('bankroll_after') for d in reversed(days)
                        if d.get('bankroll_after') is not None), None)
        bk_path = (f'${bk_first:.0f}→${bk_last:.0f}'
                   if (bk_first is not None and bk_last is not None) else '—')
        rows.append((tid, active, bets, bk_path))
    rows.sort(key=lambda x: -x[2])
    for r in rows:
        lines.append(f'| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} |')
    return '\n'.join(lines)


def render_itf_deep_md(itf):
    meta = itf.get('meta', {})
    by_agent = itf.get('by_agent', {})
    orders = itf.get('recent_alpaca_orders', [])
    statuses = itf.get('order_status_summary', {})
    decs = itf.get('live_decisions_snapshot', [])
    positions = itf.get('positions_snapshot', [])
    lines = [
        '# ITF — per-agent deep audit',
        f'Generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
        f'Seed: ${meta.get("seed_share_usd","?")} per agent  '
        f'(seeded {meta.get("seeded_at","?")}, n_agents={meta.get("n_agents","?")})',
        '',
        '> NOTE: ITF does not persist LLM rationales to disk (only to in-memory '
        '/api/decisions). Each tick this resets. To get permanent decision-trail, '
        'app.py must persist `_LIVE_DECISIONS` to data/intraday/decisions.jsonl.',
        '',
        '## Live /api/decisions snapshot (current tick only)',
        f'- {len(decs)} live decisions captured at audit time',
    ]
    for d in decs[:25]:
        ag = d.get('agent_tid') or d.get('tid') or '?'
        ev = d.get('event') or d.get('action') or ''
        tk = d.get('ticker') or ''
        rs = d.get('reason') or d.get('reason_code') or ''
        lines.append(f'  - `{ag}` {ev} {tk} reason={rs}')
    lines += [
        '',
        '## Alpaca order status summary (last 500)',
        '| status | n |',
        '|---|---:|',
    ]
    for k, v in sorted(statuses.items(), key=lambda x: -x[1]):
        lines.append(f'| {k} | {v} |')
    lines += [
        '',
        '## Per-agent ledger summary',
        '| agent | events | reserves | rejects | fills | bankroll | top reject reasons |',
        '|---|---:|---:|---:|---:|---:|---|',
    ]
    items = sorted(by_agent.items(), key=lambda kv: -kv[1]['n_broker_rejects'])
    for tid, a in items:
        bk = f'${a["bankroll"]:.0f}' if isinstance(a.get('bankroll'), (int, float)) else '—'
        rsn = ', '.join(f'{r}×{n}' for r, n in (a.get('reject_reasons_top') or [])[:4])
        lines.append(f'| `{tid}` | {a["n_events"]} | {a["n_reserves"]} | '
                     f'{a["n_broker_rejects"]} | {a["n_open_fills"]} | {bk} | {rsn} |')
    lines += ['', '## Recent Alpaca orders (last 60)',
              '| created | symbol | side | qty | notional | class/type | status |',
              '|---|---|---|---:|---:|---|---|']
    for o in orders[:60]:
        qs = o.get('qty') or '—'; ns = o.get('notional') or '—'
        lines.append(f'| {(o.get("created_at") or "")[:19]} | {o.get("symbol","")} | '
                     f'{o.get("side","")} | {qs} | {ns} | '
                     f'{o.get("order_class") or ""}/{o.get("order_type") or ""} | '
                     f'{o.get("status","")} |')
    lines += ['', f'## Open positions snapshot ({len(positions)} positions)']
    for p in positions[:20]:
        if not isinstance(p, dict): continue
        lines.append(f'- `{p.get("tid","?")}` {p.get("ticker","")} '
                     f'qty={p.get("qty","?")} entry=${p.get("entry_price",0):.2f} '
                     f'mark=${p.get("mark",0):.2f} '
                     f'unreal_pnl={p.get("unrealized_pnl",0):+.2f}')
    return '\n'.join(lines)


# -------------------- Main --------------------

def write_per_agent_files(tf, by_agent, schema):
    out_dir = AUDIT_PER_AGENT / tf
    out_dir.mkdir(parents=True, exist_ok=True)
    for tid, days in by_agent.items():
        safe_tid = tid.replace('/', '_').replace(':', '_')
        (out_dir / f'{safe_tid}.md').write_text(
            render_per_agent_md(tf, tid, days, schema=schema))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tf', choices=['nba', 'pol', 'itf', 'pqtf', 'all'], default='all')
    p.add_argument('--include-prefix-bug', action='store_true')
    p.add_argument('--last-n-days', type=int, default=EXPAND_LAST_N_DAYS)
    args = p.parse_args()

    AUDIT.mkdir(parents=True, exist_ok=True)
    AUDIT_PER_AGENT.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    post = not args.include_prefix_bug

    if args.tf in ('nba', 'all'):
        print('[NBA] deep extract...', file=sys.stderr)
        days = fetch_all_days(NBA_SPACE, post_reset_only=post)
        by_agent, by_game = deep_extract_nba_pol(
            days, 'nba', event_key='game', cat_key='category')
        (AUDIT / f'per-agent-deep-nba-{today}.json').write_text(
            json.dumps({'n_days': len(days), 'agents': by_agent}, indent=1, default=str))
        (AUDIT / f'per-agent-deep-nba-{today}.md').write_text(
            render_rollup_md('nba', by_agent, len(days)))
        (AUDIT / f'per-game-deep-nba-{today}.md').write_text(
            render_per_game_md('nba', by_game, last_n_days=args.last_n_days))
        write_per_agent_files('nba', by_agent, schema='nba')
        print(f'[NBA] wrote rollup + per-game + {len(by_agent)} per-agent files',
              file=sys.stderr)

    if args.tf in ('pol', 'all'):
        print('[POL] deep extract...', file=sys.stderr)
        days = fetch_all_days(POL_SPACE, post_reset_only=post)
        by_agent, by_game = deep_extract_nba_pol(
            days, 'pol', event_key='event_idx', cat_key='event_type',
            rationale_key='thesis')
        (AUDIT / f'per-agent-deep-pol-{today}.json').write_text(
            json.dumps({'n_days': len(days), 'agents': by_agent}, indent=1, default=str))
        (AUDIT / f'per-agent-deep-pol-{today}.md').write_text(
            render_rollup_md('pol', by_agent, len(days)))
        (AUDIT / f'per-game-deep-pol-{today}.md').write_text(
            render_per_game_md('pol', by_game, last_n_days=args.last_n_days))
        write_per_agent_files('pol', by_agent, schema='pol')
        print(f'[POL] wrote rollup + per-event + {len(by_agent)} per-agent files',
              file=sys.stderr)

    if args.tf in ('pqtf', 'all'):
        print('[PQTF] deep extract (frozen, post-mortem)...', file=sys.stderr)
        days = fetch_pqtf_days()
        by_agent, by_game = deep_extract_pqtf(days)
        (AUDIT / f'per-agent-deep-pqtf-{today}.json').write_text(
            json.dumps({'n_days': len(days), 'agents': by_agent}, indent=1, default=str))
        (AUDIT / f'per-agent-deep-pqtf-{today}.md').write_text(
            render_rollup_md('pqtf', by_agent, len(days), schema='pqtf'))
        (AUDIT / f'per-game-deep-pqtf-{today}.md').write_text(
            render_per_game_md('pqtf', by_game, last_n_days=args.last_n_days))
        write_per_agent_files('pqtf', by_agent, schema='pqtf')
        print(f'[PQTF] wrote rollup + per-etf + {len(by_agent)} per-agent files',
              file=sys.stderr)

    if args.tf in ('itf', 'all'):
        print('[ITF] deep extract...', file=sys.stderr)
        itf = deep_extract_itf()
        (AUDIT / f'per-agent-deep-itf-{today}.json').write_text(
            json.dumps(itf, indent=1, default=str))
        (AUDIT / f'per-agent-deep-itf-{today}.md').write_text(render_itf_deep_md(itf))
        print(f'[ITF] wrote deep audit', file=sys.stderr)

    print(f'\nAll outputs under {AUDIT}', file=sys.stderr)


if __name__ == '__main__':
    main()
