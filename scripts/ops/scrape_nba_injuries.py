#!/usr/bin/env python3
"""NBA injury report scraper — feeds the TF agents real OUT/D/Q status.

User audit 2026-04-26 found agents bet roster-dependent markets BLIND because
injuries-current.json never existed. This fixes that.

Sources (in priority order, fallback chain):
  1. nba_api.stats.endpoints.PlayerInjuries (official NBA API, free)
  2. ESPN injuries JSON (https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/news/?type=injuries)
  3. RotoWire team-by-team scrape (last resort)

Output: data/injuries-current.json
  {
    "<team_abbr>": [
      {"name": "...", "status": "OUT|D|Q|DTD|GTD", "reason": "...", "updated": "ISO-ts"},
      ...
    ],
    "_updated_at": "ISO-ts",
    "_source": "nba_api"
  }

Then push to NBA TF Space at data/injuries-current.json so the live container
picks it up at next restart (or hot-reload if implemented).

Cron: 50 14-23,0-3 * * *  (every hour during US daytime + early UTC night)
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_LOCAL = REPO / 'data' / 'injuries-current.json'
TF_SPACE = 'LBJLincoln26/nba-llm-trading-floor'

# NBA team abbr ↔ team_id (used by official nba_api)
TEAM_ABBR = {
    1610612737:'ATL',1610612738:'BOS',1610612751:'BKN',1610612766:'CHA',1610612741:'CHI',
    1610612739:'CLE',1610612742:'DAL',1610612743:'DEN',1610612765:'DET',1610612744:'GSW',
    1610612745:'HOU',1610612754:'IND',1610612746:'LAC',1610612747:'LAL',1610612763:'MEM',
    1610612748:'MIA',1610612749:'MIL',1610612750:'MIN',1610612740:'NOP',1610612752:'NYK',
    1610612760:'OKC',1610612753:'ORL',1610612755:'PHI',1610612756:'PHX',1610612757:'POR',
    1610612758:'SAC',1610612759:'SAS',1610612761:'TOR',1610612762:'UTA',1610612764:'WAS',
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _from_espn() -> dict:
    """Pull ESPN injuries JSON. Returns {team_abbr: [...injuries...]}.
    Fallback when nba_api isn't available or rate-limits."""
    out = {}
    url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 Nomos42-Injury-Scraper'})
        raw = urllib.request.urlopen(req, timeout=20).read()
        d = json.loads(raw)
        for team_obj in d.get('injuries', []):
            abbr = (team_obj.get('team', {}).get('abbreviation') or '').upper()
            if not abbr:
                continue
            inj_list = []
            for it in team_obj.get('injuries', []):
                ath = it.get('athlete') or {}
                status = (it.get('status') or '').upper()
                # ESPN uses: Out, Day-To-Day, Doubtful, Questionable, Suspended
                short = {
                    'OUT': 'OUT', 'OUT FOR SEASON': 'OUT', 'SUSPENDED': 'SUS',
                    'DOUBTFUL': 'D', 'QUESTIONABLE': 'Q',
                    'DAY-TO-DAY': 'DTD', 'GAME TIME DECISION': 'GTD',
                }.get(status, status[:4])
                inj_list.append({
                    'name': ath.get('displayName') or ath.get('shortName') or '?',
                    'status': short,
                    'reason': (it.get('details', {}).get('detail') or it.get('shortComment') or '')[:120],
                    'updated': it.get('date', ''),
                })
            if inj_list:
                out[abbr] = inj_list
    except Exception as e:
        print(f'[injury-scrape] ESPN err: {e}', file=sys.stderr)
    return out


def _from_nba_api() -> dict:
    """Try official NBA API via nba_api package (preferred — most accurate)."""
    out = {}
    try:
        # Defer import to keep optional
        from nba_api.stats.endpoints import playerinjuries
        df = playerinjuries.PlayerInjuries().get_data_frames()[0]
        for _, row in df.iterrows():
            team_id = row.get('TEAM_ID')
            abbr = TEAM_ABBR.get(team_id)
            if not abbr:
                continue
            status_full = (row.get('STATUS', '') or '').upper()
            short = {
                'OUT': 'OUT', 'DAY-TO-DAY': 'DTD',
                'DOUBTFUL': 'D', 'QUESTIONABLE': 'Q', 'SUSPENDED': 'SUS',
            }.get(status_full, status_full[:4])
            entry = {
                'name': row.get('PLAYER_NAME', '?'),
                'status': short,
                'reason': (row.get('DESCRIPTION') or '')[:120],
                'updated': str(row.get('DATE', '')),
            }
            out.setdefault(abbr, []).append(entry)
    except Exception as e:
        print(f'[injury-scrape] nba_api err: {e}', file=sys.stderr)
    return out


def main() -> int:
    # Try nba_api first, fall back to ESPN
    src = 'nba_api'
    data = _from_nba_api()
    if not data:
        src = 'espn'
        data = _from_espn()
    if not data:
        print('[injury-scrape] BOTH SOURCES FAILED — keeping previous file if any', file=sys.stderr)
        return 1
    data['_updated_at'] = _utc_now()
    data['_source'] = src
    OUT_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOCAL.write_text(json.dumps(data, indent=2, default=str))
    teams_with_inj = [k for k in data.keys() if not k.startswith('_')]
    total_inj = sum(len(data[k]) for k in teams_with_inj)
    print(f'[injury-scrape] OK — {len(teams_with_inj)} teams, {total_inj} injuries, source={src}', file=sys.stderr)

    # Push to NBA TF Space
    tok = os.environ.get('HF_TOKEN_NBA') or os.environ.get('HF_TOKEN', '')
    if not tok:
        print('[injury-scrape] no HF_TOKEN, skipping push', file=sys.stderr)
        return 0
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=tok)
        api.upload_file(
            path_or_fileobj=str(OUT_LOCAL),
            path_in_repo='data/injuries-current.json',
            repo_id=TF_SPACE, repo_type='space',
            commit_message=f'[injury-scrape] {src} — {total_inj} injuries across {len(teams_with_inj)} teams',
        )
        print(f'[injury-scrape] pushed to {TF_SPACE}', file=sys.stderr)
    except Exception as e:
        print(f'[injury-scrape] push err: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
