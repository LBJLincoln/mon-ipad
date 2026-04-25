#!/usr/bin/env python3
"""Combination-coverage report — answers user's verification question:
"with 100k+ possibilities and 200+ odds per match, which combinations did each
agent actually choose?"

For each TF, for each agent, computes:
  - n_total_bets, n_distinct_categories, n_distinct_(game_or_event,category) combos
  - category-class distribution: ml_* / spread_* / total_* / h1_* / q1_* /
    team_total_* / pp_* / alt_* / parlay  (NBA);  insider_trade / fed_rule /
    exec_order / sec_filing / fec_donation / etc (POL); etf+option_type (PQTF)
  - top-20 most-picked combos
  - coverage ratio: n_distinct_combos / theoretical_max
  - homogeneity flag: largest-cluster share of total bets

Output: data/audit/coverage-report-{date}.md + .json
"""
from __future__ import annotations
import datetime as dt, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / 'data' / 'audit'

NBA_CAT_CLASSES = [
    ('ml',          re.compile(r'^ml_')),
    ('spread',      re.compile(r'^spread_')),
    ('total',       re.compile(r'^total_')),
    ('alt_spread',  re.compile(r'^alt_spread_')),
    ('alt_total',   re.compile(r'^alt_total_')),
    ('team_total',  re.compile(r'^team_total_')),
    ('h1',          re.compile(r'^h1_')),
    ('q1',          re.compile(r'^q1_')),
    ('pp_points',   re.compile(r'^pp_points')),
    ('pp_assists',  re.compile(r'^pp_assists')),
    ('pp_rebounds', re.compile(r'^pp_rebounds')),
    ('pp_threes',   re.compile(r'^pp_threes')),
    ('pp_steals',   re.compile(r'^pp_steals')),
    ('pp_blocks',   re.compile(r'^pp_blocks')),
]


def classify_nba(cat: str) -> str:
    if not cat: return 'unknown'
    for label, pat in NBA_CAT_CLASSES:
        if pat.match(cat): return label
    if cat.startswith('pp_'): return 'pp_other'
    return 'other'


def build_nba_pol_coverage(days: dict, tf: str, classify=None, parlay_key='parlays'):
    """days = {agent: [day_dict, ...]}"""
    per_agent = {}
    for tid, day_list in days.items():
        cats = Counter()
        combos = Counter()  # (event, category)
        events = Counter()
        classes = Counter()
        n_bets = 0
        n_parlays = 0
        n_parlay_legs = 0
        for d in day_list:
            for al in d.get('allocations') or d.get('positions') or []:
                if not isinstance(al, dict): continue
                ev = str(al.get('event') or al.get('etf') or '?')
                cat = al.get('category') or al.get('option_type') or al.get('event_type') or '?'
                cats[cat] += 1
                combos[(ev, cat)] += 1
                events[ev] += 1
                if classify:
                    classes[classify(cat)] += 1
                n_bets += 1
            for p in d.get(parlay_key) or []:
                if not isinstance(p, dict): continue
                n_parlays += 1
                legs = p.get('legs') or []
                n_parlay_legs += len(legs) if isinstance(legs, list) else 0
        # Largest cluster share
        top_cluster = cats.most_common(1)
        homogen = (top_cluster[0][1] / n_bets) if n_bets > 0 and top_cluster else 0
        per_agent[tid] = {
            'n_bets': n_bets,
            'n_distinct_categories': len(cats),
            'n_distinct_event_category_combos': len(combos),
            'n_distinct_events': len(events),
            'n_parlays': n_parlays,
            'n_parlay_legs': n_parlay_legs,
            'cat_class_distribution': dict(classes.most_common()),
            'top_20_cats': cats.most_common(20),
            'top_20_combos': [
                {'event': c[0][0], 'category': c[0][1], 'n': c[1]}
                for c in combos.most_common(20)
            ],
            'homogeneity_top_cat_share': round(homogen, 3),
        }
    return per_agent


def render(tf: str, per_agent: dict, theoretical_universe: str) -> str:
    L = [
        f'# {tf.upper()} — combination coverage report',
        f'Generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
        '',
        f'**Theoretical universe per match-day**: {theoretical_universe}',
        '',
        'Reads: for each agent, how much of the 100k+ combination space did they actually explore?',
        'Homogeneity = share of total bets in the agent\'s most-picked single category. >50% = template-bleed.',
        '',
        '## Activity + coverage table',
        '',
        '| agent | bets | par.legs | distinct_cats | distinct_combos | distinct_events | homogeneity | top class |',
        '|---|---:|---:|---:|---:|---:|---:|---|',
    ]
    rows = sorted(per_agent.items(), key=lambda kv: -kv[1]['n_bets'])
    for tid, a in rows:
        top_class = ', '.join(f'{k}×{v}' for k, v in
                              list(a['cat_class_distribution'].items())[:3])
        L.append(f'| `{tid}` | {a["n_bets"]} | {a["n_parlay_legs"]} | '
                 f'{a["n_distinct_categories"]} | '
                 f'{a["n_distinct_event_category_combos"]} | '
                 f'{a["n_distinct_events"]} | '
                 f'{a["homogeneity_top_cat_share"]*100:.0f}% | '
                 f'{top_class} |')
    L.append('')
    L.append('## Per-agent category-class breakdown')
    L.append('')
    for tid, a in rows:
        if a['n_bets'] == 0: continue
        cls = a['cat_class_distribution']
        bar = '  '.join(f'{k}={v}' for k, v in cls.items())
        L.append(f'**`{tid}`** ({a["n_bets"]} bets): {bar}')
    L.append('')
    L.append('## Per-agent top-20 categories (with count)')
    L.append('')
    for tid, a in rows:
        if a['n_bets'] == 0: continue
        L.append(f'### `{tid}`')
        L.append(f'- distinct cats: {a["n_distinct_categories"]} — distinct combos: {a["n_distinct_event_category_combos"]} — homogeneity: {a["homogeneity_top_cat_share"]*100:.0f}%')
        for c, n in a['top_20_cats']:
            pct = n/a['n_bets']*100
            L.append(f'  - `{c}`: {n} ({pct:.1f}%)')
        L.append('')
    return '\n'.join(L)


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    output_json = {}

    for tf, classify, universe in [
        ('nba', classify_nba,
         '249 categories × ~5 games × parlay 2-6 legs ≈ 1.5M combos/day; agent picks ≤25 + 8 parlays/day'),
        ('pol', None,
         '22 event types × ~30 events/day × 8 ETFs × {long,short} ≈ 100k combos/week'),
        ('pqtf', None,
         '12 ETFs × {call,put} × multi-strike × tte 2-5d ≈ 50k positions/session'),
    ]:
        path = AUDIT / f'per-agent-deep-{tf}-{today}.json'
        if not path.exists():
            print(f'skip {tf}: {path} missing', file=sys.stderr)
            continue
        d = json.loads(path.read_text())
        agents = d.get('agents', {})
        cov = build_nba_pol_coverage(agents, tf, classify=classify)
        output_json[tf] = {
            'theoretical_universe': universe,
            'agents': cov,
        }
        md = render(tf, cov, universe)
        (AUDIT / f'coverage-report-{tf}-{today}.md').write_text(md)
        (AUDIT / f'coverage-report-{tf}-latest.md').write_text(md)
        print(f'[{tf}] wrote coverage-report-{tf}-{today}.md', file=sys.stderr)

    # Combined JSON for dashboard
    (AUDIT / f'coverage-report-{today}.json').write_text(
        json.dumps(output_json, indent=2, default=str))
    (AUDIT / f'coverage-report-latest.json').write_text(
        json.dumps(output_json, indent=2, default=str))
    print(f'wrote combined coverage-report JSON', file=sys.stderr)


if __name__ == '__main__':
    main()
