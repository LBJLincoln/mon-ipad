#!/usr/bin/env python3
"""DAY-0 RESET — NBA + POL + ITF, 2026-04-25.

Why: Parser bug shipped 2026-04-25 (allocations[:10] cap + dedup-per-game
silently dropped 90%+ of agent-chosen categories). Fix patched in
scripts/arena/hf-llm-trading-floor/app.py + hf-political-trading-floor/app.py.
Accumulated state was generated under the broken regime; clean A/B requires
fresh seeds for all 3 active TFs. PQTF stays frozen forever.

Order per TF:
  1. Upload fixed app.py (NBA + POL only — ITF parser unchanged)
  2. Delete state files (state.json, council_plans.json, decisions/*)
  3. factory_reboot=True (wipes ephemeral container state too)
  4. Verify /api/status alive
"""
from __future__ import annotations
import os, sys, time, json
from huggingface_hub import HfApi
import urllib.request

TOK = os.environ.get('HF_TOKEN_USERS') or os.environ.get('HF_TOKEN_NBA') or os.environ.get('HF_TOKEN','')
if not TOK:
    print('FATAL: no HF token', file=sys.stderr); sys.exit(2)

api = HfApi(token=TOK)

NBA = 'LBJLincoln26/nba-llm-trading-floor'
POL = 'LBJLincoln26/political-llm-trading-floor'
ITF = 'LBJLincoln26/intraday-trading-floor'

def upload_app(space: str, local_path: str):
    print(f'[{space}] upload {local_path}')
    api.upload_file(
        path_or_fileobj=local_path,
        path_in_repo='app.py',
        repo_id=space,
        repo_type='space',
        commit_message='[ORACLE_BRIDGE] alloc parser bugfix: cap 10->25 + dedup per (game,cat)',
    )

def delete_files(space: str, paths: list[str]):
    for p in paths:
        try:
            api.delete_file(path_in_repo=p, repo_id=space, repo_type='space',
                            commit_message=f'[ORACLE_BRIDGE] DAY-0 RESET wipe {p}')
            print(f'[{space}] deleted {p}')
        except Exception as e:
            # Tolerate already-absent files
            print(f'[{space}] {p} delete err: {type(e).__name__} {str(e)[:120]}')

def list_decisions(space: str) -> list[str]:
    url = f'https://huggingface.co/api/spaces/{space}/tree/main?recursive=true'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {TOK}'})
    with urllib.request.urlopen(req, timeout=30) as r:
        tree = json.load(r)
    return sorted(str(f.get('path')) for f in tree if isinstance(f,dict)
                  and str(f.get('path','')).startswith('data/decisions/day-')
                  and str(f.get('path','')).endswith('.json'))

def factory_reboot(space: str):
    print(f'[{space}] factory_reboot')
    api.restart_space(repo_id=space, factory_reboot=True)

def verify_alive(space: str, timeout_sec: int = 240) -> bool:
    base = 'https://' + space.lower().replace('/', '-') + '.hf.space'
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f'{base}/api/status', headers={'Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status == 200:
                    body = json.loads(r.read())
                    print(f'[{space}] ALIVE  {json.dumps({k:body.get(k) for k in ("running","day_idx","tick","equity","fleet_total")}, default=str)}')
                    return True
        except Exception:
            pass
        time.sleep(8)
    print(f'[{space}] TIMEOUT after {timeout_sec}s')
    return False


def reset_nba_pol(space: str, app_py: str):
    print(f'\n=== {space} ===')
    upload_app(space, app_py)
    decisions = list_decisions(space)
    print(f'[{space}] {len(decisions)} decisions to wipe')
    delete_files(space, ['data/runtime/state.json', 'data/runtime/council_plans.json',
                         'data/runtime/agent_logs.json', 'data/runtime/rep_history.json',
                         'data/runtime/rogue_state.json', 'data/runtime/pact_log.jsonl'])
    # Decisions wiped in chunks to avoid HF rate-limit / huge commit
    for d in decisions:
        try:
            api.delete_file(path_in_repo=d, repo_id=space, repo_type='space',
                            commit_message='[ORACLE_BRIDGE] DAY-0 RESET wipe decisions')
        except Exception as e:
            print(f'[{space}] {d} err {type(e).__name__}')
    factory_reboot(space)


def reset_itf():
    print(f'\n=== {ITF} ===')
    delete_files(ITF, ['data/intraday/agent_bankrolls.json',
                       'data/intraday/agent_ledger.jsonl',
                       'data/intraday/positions.json',
                       'data/intraday/fill_reconciliation_cursor.json'])
    factory_reboot(ITF)


def main():
    reset_nba_pol(NBA, 'scripts/arena/hf-llm-trading-floor/app.py')
    reset_nba_pol(POL, 'scripts/arena/hf-political-trading-floor/app.py')
    reset_itf()
    print('\n=== verify ===')
    for sp in (NBA, POL, ITF):
        verify_alive(sp, timeout_sec=300)


if __name__ == '__main__':
    main()
