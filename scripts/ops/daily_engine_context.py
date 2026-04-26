#!/usr/bin/env python3
"""Per-day forensic that shows EVERYTHING agents had access to + what they bet.

For a given NBA day file:
  * All games + outcomes
  * Engine predictions per game (predicted_p_home, margin, total)
  * TOP-15 engine edges per game with prob (catches prob=0 hallucination bug)
  * All allocations per game (cross-agent matrix)
  * Roster snippet for each team (player count, top names)
  * Agent → bet with rationale, edge_source, won, profit

Output: data/audit/day-context-nba-{date}.md and -latest.md
Sync to dashboard via existing sync_tf_analytics_to_dashboard.sh
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / 'data' / 'audit'
TOK = (os.environ.get('HF_TOKEN_NBA') or os.environ.get('HF_TOKEN', ''))
H = {'Authorization': f'Bearer {TOK}'} if TOK else {}

NBA_SPACE = 'LBJLincoln26/nba-llm-trading-floor'


def fetch(url: str, timeout: int = 60) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=timeout).read()


def fetch_day_file(day_idx: int):
    p = f'data/decisions/day-{day_idx:03d}.json'
    return json.loads(fetch(f'https://huggingface.co/spaces/{NBA_SPACE}/resolve/main/{urllib.parse.quote(p)}'))


def fetch_full_dataset(path: str):
    return json.loads(fetch(f'https://huggingface.co/spaces/{NBA_SPACE}/resolve/main/{urllib.parse.quote(path)}'))


def render_day(day_idx: int) -> str:
    d = fetch_day_file(day_idx)
    date = d.get('date')
    n_games = d.get('n_games')
    written = d.get('written_at')
    ag = d.get('agents') or {}

    L = [
        f'# NBA day-{day_idx:03d} ({date}) — full agent + engine context',
        f'Generated {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',
        f'Day file written: {written}',
        f'',
        f'**{n_games} games** | **{len(ag)} agents** | total bets: {sum(len(a.get("allocations",[])) for a in ag.values())}',
        '',
    ]

    # Pull engine predictions for this date
    L.append('Loading engine predictions + games + rosters (large files, may take 30s)…')
    L.append('')

    try:
        all_preds = fetch_full_dataset('data/model-predictions-2025-26.json')
    except Exception as e:
        all_preds = {}
        L.append(f'> WARN: could not fetch model_preds: {e}')
    try:
        all_games = fetch_full_dataset('data/games-2025-26.json')
    except Exception as e:
        all_games = []
        L.append(f'> WARN: could not fetch games: {e}')
    try:
        all_rosters = fetch_full_dataset('data/rosters-2025-26.json')
    except Exception as e:
        all_rosters = {}
        L.append(f'> WARN: could not fetch rosters: {e}')
    try:
        all_full_odds = fetch_full_dataset('data/full-odds-2025-26.json')
    except Exception as e:
        all_full_odds = {}
        L.append(f'> WARN: could not fetch full_odds: {e}')

    # Build day-game list from the day file's allocations (extract games)
    games_in_day = set()
    for tid, a in ag.items():
        for al in a.get('allocations') or []:
            g = al.get('game') or ''
            if g:
                games_in_day.add(g)
        for p in a.get('parlays') or []:
            for leg in p.get('legs') or []:
                g = leg.get('game') or ''
                if g:
                    games_in_day.add(g)

    # Cross-agent allocation matrix per game
    by_game = defaultdict(list)
    for tid, a in ag.items():
        for al in a.get('allocations') or []:
            g = al.get('game') or '?'
            by_game[g].append((tid, al))

    L.append('## Per-game forensic')
    L.append('')

    for game_str in sorted(games_in_day):
        L.append(f'### {game_str}')
        # Game outcome lookup
        if '@' in game_str:
            away_home = game_str.split('@')
            if len(away_home) == 2:
                away, home = away_home
                game_obj = next((g for g in (all_games or []) if isinstance(g, dict)
                                 and g.get('date') == date and g.get('home') == home and g.get('away') == away), None)
                if game_obj:
                    L.append(f'- **outcome**: {away} {game_obj.get("away_score","?")} @ {home} {game_obj.get("home_score","?")} '
                             f'| home_won={game_obj.get("home_won")}')
                # Engine predictions
                gk = f'{date}_{away}@{home}'
                pred = (all_preds or {}).get(gk) or {}
                if pred:
                    core = pred.get('derived_core', {})
                    L.append(f'- **engine consensus**: ml={pred.get("consensus_ml_direction","?")} '
                             f'(agree {pred.get("ml_agreement_pct",0):.0f}%) | '
                             f'spread={pred.get("consensus_spread_direction","?")} '
                             f'| total={pred.get("consensus_total_direction","?")}')
                    L.append(f'- **engine predicted**: margin={core.get("predicted_margin","?"):+.2f} | '
                             f'total={core.get("predicted_total","?"):.1f} | '
                             f'p(home)={core.get("predicted_p_home","?"):.3f}')
                    per_cat = pred.get('per_category', {})
                    edges = sorted([(abs(info.get('edge', 0)), tag, info)
                                    for tag, info in per_cat.items()
                                    if isinstance(info.get('edge'), (int, float))],
                                   reverse=True)
                    L.append(f'- **ALL {len(per_cat)} engine categories** (sorted by |edge| desc):')
                    L.append('<details><summary>Show all categories</summary>')
                    L.append('')
                    L.append('  | category | prob | edge | NOTE |')
                    L.append('  |---|---:|---:|---|')
                    for abs_e, tag, info in edges:
                        prob = info.get('prob', 0) or 0
                        edge = info.get('edge', 0) or 0
                        note = ''
                        if prob == 0 and abs(edge) > 0.05:
                            note = '⚠ prob=0 but edge!=0 — likely engine hallucination'
                        elif tag.startswith('pp_'):
                            note = '🚫 pp_* (banned at parser)'
                        L.append(f'  | `{tag}` | {prob:.3f} | {edge:+.3f} | {note} |')
                    L.append('')
                    L.append('</details>')
                    L.append('')
                # Roster summary for both teams
                for team in (away, home):
                    roster = (all_rosters or {}).get(team) or (all_rosters or {}).get(team.upper()) or []
                    if isinstance(roster, list) and roster:
                        names = [str(p.get('name','') if isinstance(p, dict) else p)[:25] for p in roster[:8]]
                        L.append(f'- **{team} roster** ({len(roster)} players): {", ".join(names)}…')
                    else:
                        L.append(f'- **{team} roster**: ⚠ MISSING from data/rosters-2025-26.json')
                # Standings/Rankings
                L.append(f'- **Rankings**: ⚠ NO standings/rankings dataset on Space (gap to fill)')
                # Full odds menu
                try:
                    full_odds_obj = (all_full_odds or {}).get(gk) or {}
                    full_cats = full_odds_obj.get('categories', full_odds_obj) if isinstance(full_odds_obj, dict) else {}
                    if isinstance(full_cats, dict) and full_cats:
                        L.append(f'- **Full odds menu**: {len(full_cats)} betting categories available')
                except Exception:
                    pass
        # Agent bets on this game
        bets = by_game.get(game_str, [])
        if bets:
            L.append(f'- **{len(bets)} agent bets**:')
            L.append('  | agent | category | odds | edge | edge_source | LLM_edge | engine_edge | stake | won | profit |')
            L.append('  |---|---|---:|---:|---|---:|---:|---:|:---:|---:|')
            for tid, al in sorted(bets, key=lambda x: -(x[1].get('stake') or 0)):
                won = '✓' if al.get('won') else '✗' if al.get('won') is False else '·'
                cat = (al.get('category') or '')[:35]
                odds = al.get('odds')
                odds_s = f'{odds:.2f}' if isinstance(odds, (int, float)) else '—'
                edge_s = f'{al.get("edge",0):.3f}'
                src = (al.get('edge_source') or '?')[:22]
                llm_e = al.get('edge_llm_reported')
                llm_s = f'{llm_e:.3f}' if isinstance(llm_e, (int, float)) else '—'
                eng_e = al.get('edge_engine')
                eng_s = f'{eng_e:.3f}' if isinstance(eng_e, (int, float)) else '—'
                profit = al.get('profit') or 0
                L.append(f'  | `{tid}` | {cat} | {odds_s} | {edge_s} | {src} | {llm_s} | {eng_s} | ${al.get("stake",0):.2f} | {won} | ${profit:+.2f} |')
        else:
            L.append('- _no agent bets on this game_')
        L.append('')

    # Aggregate: agents with no bets on any game today
    silent = []
    for tid, a in ag.items():
        if not (a.get('allocations') or a.get('parlays')):
            silent.append((tid, a.get('bankroll_after', 0)))
    if silent:
        L.append('## Silent agents (no bets today)')
        L.append('')
        for tid, bk in sorted(silent, key=lambda x: x[1]):
            L.append(f'- `{tid}` bk=${bk:.1f}')
        L.append('')

    return '\n'.join(L)


def list_existing_days() -> list:
    """List all day_idx values that have a day-NNN.json on the NBA TF Hub."""
    import re
    url = f'https://huggingface.co/api/spaces/{NBA_SPACE}/tree/main/data/decisions'
    try:
        files = json.loads(fetch(url))
        days = []
        for f in files:
            if isinstance(f, dict):
                m = re.search(r'day-(\d+)\.json$', f.get('path', ''))
                if m:
                    days.append(int(m.group(1)))
        return sorted(days)
    except Exception as e:
        print(f'list_existing_days err: {e}', file=sys.stderr)
        return []


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--day', type=int, help='day_idx to render')
    p.add_argument('--all', action='store_true', help='render every day on Hub')
    p.add_argument('--last', type=int, default=0, help='render last N days only')
    args = p.parse_args()

    AUDIT.mkdir(parents=True, exist_ok=True)

    if args.all or args.last:
        days = list_existing_days()
        if args.last:
            days = days[-args.last:]
        if not days:
            print('no day files on Hub yet', file=sys.stderr)
            return
        print(f'rendering {len(days)} days: {days[0]} → {days[-1]}', file=sys.stderr)
        for d in days:
            try:
                md = render_day(d)
                out = AUDIT / f'day-context-nba-{d:03d}.md'
                out.write_text(md)
            except Exception as e:
                print(f'  day-{d:03d} FAIL: {e}', file=sys.stderr)
        # latest = most recent one
        latest_md = (AUDIT / f'day-context-nba-{days[-1]:03d}.md').read_text()
        (AUDIT / 'day-context-nba-latest.md').write_text(latest_md)
        # Build index of available days (consumed by /audit page dropdown)
        idx = {'days': [{'idx': d, 'file': f'day-context-nba-{d:03d}.md'} for d in days],
               'latest_idx': days[-1],
               'updated_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        (AUDIT / 'day-context-nba-index.json').write_text(json.dumps(idx, indent=2))
        print(f'wrote {len(days)} day-context files + index', file=sys.stderr)
        return

    if args.day is None:
        p.error('--day required (or use --all / --last N)')

    md = render_day(args.day)
    out = AUDIT / f'day-context-nba-{args.day:03d}.md'
    out.write_text(md)
    (AUDIT / f'day-context-nba-latest.md').write_text(md)
    print(f'wrote {out} + day-context-nba-latest.md', file=sys.stderr)


if __name__ == '__main__':
    main()
