#!/usr/bin/env python3
"""5-min snapshot of NBA + ITF (+POL) — confirms fixes working."""
import json, urllib.request, urllib.parse, os, sys
from collections import Counter
from datetime import datetime, timezone

tok = os.environ.get('HF_TOKEN_NBA') or os.environ.get('HF_TOKEN','')
H = {'Authorization': f'Bearer {tok}'} if tok else {}

def fetch(url, timeout=15):
    return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=timeout).read()

def latest_day(space):
    """Pick the 3 freshest day files by COMMIT TIME, not lex sort on day_idx.
    Day files get OVERWRITTEN as the season is re-simmed, so a day_idx=110
    file from 3h ago is older than a day_idx=54 file just written."""
    commits = json.loads(fetch(f'https://huggingface.co/api/spaces/{space}/commits/main?limit=80'))
    out = []
    seen = set()
    for c in commits:
        title = c.get('title','')
        if 'decisions: day' in title:
            try:
                day_idx = int(title.split('day')[1].strip().split()[0])
                p = f'data/decisions/day-{day_idx:03d}.json'
                if p not in seen:
                    seen.add(p)
                    out.append(p)
                    if len(out) >= 3: break
            except Exception:
                continue
    return out  # commit-time order, freshest first

def parse_day(space, p):
    return json.loads(fetch(f'https://huggingface.co/spaces/{space}/resolve/main/{urllib.parse.quote(p)}'))

now = datetime.now(timezone.utc).strftime('%H:%M:%SZ')
print(f'\n========== {now} TF MONITOR ==========')

# NBA
print(f'\n[NBA] LBJLincoln26/nba-llm-trading-floor')
days = latest_day('LBJLincoln26/nba-llm-trading-floor')
for p in days:
    d = parse_day('LBJLincoln26/nba-llm-trading-floor', p)
    ag = d.get('agents') or {}
    bets = sum(len(a.get('allocations',[])) for a in ag.values())
    edge_src = Counter()
    cat_class = Counter()
    bk_total = sum((a.get('bankroll_after',0) or 0) for a in ag.values())
    n_silent = sum(1 for a in ag.values() if not a.get('allocations'))
    for tid, a in ag.items():
        for al in a.get('allocations') or []:
            edge_src[al.get('edge_source','none')] += 1
            cat = al.get('category','')
            if cat.startswith(('ml_','spread_','total_')): cat_class['HIGH']+=1
            elif cat.startswith(('alt_','team_total_','h1_','h2_','q')): cat_class['MEDIUM']+=1
            elif cat.startswith('pp_'): cat_class['LOW']+=1
    written = (d.get('written_at','') or '')[-13:-7]
    day = p.split('-')[-1].split('.')[0]
    print(f'  day-{day} t={written} bets={bets:>3} silent={n_silent}/{len(ag)} bk_sum=${bk_total:>5.0f} src={dict(edge_src)} class={dict(cat_class)}')

# ITF
print(f'\n[ITF]')
try:
    s = json.loads(fetch('https://lbjlincoln26-intraday-trading-floor.hf.space/api/status'))
    ag = s.get('agents',{})
    tot_bk = sum(a.get('bankroll',0) for a in ag.values())
    tot_dec = sum(a.get('decisions',0) for a in ag.values())
    tot_tr = sum(a.get('trades',0) for a in ag.values())
    print(f'  tick={s.get("tick_count")} run={s.get("running")} dec={tot_dec} trades={tot_tr} fleet_bk=${tot_bk:,.0f} (seed=99569)')
    top3 = sorted(ag.items(), key=lambda x:-x[1].get('bankroll',0))[:3]
    bot3 = sorted(ag.items(), key=lambda x:x[1].get('bankroll',0))[:3]
    for tid, a in top3:
        print(f'    TOP {tid:>22} ${a.get("bankroll",0):>+8,.0f}')
    for tid, a in bot3:
        print(f'    BOT {tid:>22} ${a.get("bankroll",0):>+8,.0f}')
except Exception as e:
    print(f'  ERR: {e}')

# POL (brief)
print(f'\n[POL]')
days = latest_day('LBJLincoln26/political-llm-trading-floor')
if days:
    d = parse_day('LBJLincoln26/political-llm-trading-floor', days[-1])
    ag = d.get('agents') or {}
    bets = sum(len(a.get('allocations',[])) for a in ag.values())
    bk_total = sum((a.get('bankroll_after',0) or 0) for a in ag.values())
    print(f'  day-{days[-1].split("-")[-1].split(".")[0]} bets={bets} bk_sum=${bk_total:.0f} (seed=1700)')
    rows = sorted(ag.items(), key=lambda x:-(x[1].get('bankroll_after') or 0))[:3]
    for tid, a in rows:
        print(f'    TOP {tid:>22} ${a.get("bankroll_after",0):>+6,.0f}')
