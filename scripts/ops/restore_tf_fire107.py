#!/usr/bin/env python3
"""Restore both TF app.py files — fire-107 idempotent variant.

Improvements over restore_tf_fire102.py:
  - git fetch origin main first (ensures RESTORE_SHA reachable on fresh VM checkout)
  - is_placeholder() guard: no-op if files already have >MIN_LINES (safe to re-run)
  - Updated commit tag AXELROD-2026-FIRE-107-VM

Same restore logic as restore_tf_fire102.py (validated correct fire-105):
  1. git fetch origin main
  2. Restore NBA + POL from 095594aa (fire-96 source: NBA 5969L / POL 3953L)
  3. Apply fire-100 tune: SACRIFICIAL tier inline archetype description (_tdesc)
  4. py_compile both
  5. Commit via safe_commit.sh (script is idempotent — safe to re-run)

Run from mon-ipad repo root on VM:
    python3 scripts/ops/restore_tf_fire107.py
"""
import os
import pathlib
import py_compile
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(
    subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
)
RESTORE_SHA = '095594aa'
NBA_PATH = 'scripts/arena/hf-llm-trading-floor/app.py'
POL_PATH = 'scripts/arena/hf-political-trading-floor/app.py'
MIN_LINES = 3000  # anything below is a placeholder stub

# fire-100 tune: inline archetype description in SACRIFICIAL tier of CK[D] block
OLD_SACC = (
    "            if next_day_sacrificial and _tt in next_day_sacrificial:\n"
    "                _tarch = next_day_sacrificial[_tt]\n"
    "                lines.append(f\"  SACRIFICIAL #{_tr}: {_tname} — must execute \\'{_tarch}\\' archetype only\")"
)
NEW_SACC = (
    "            if next_day_sacrificial and _tt in next_day_sacrificial:\n"
    "                _tarch = next_day_sacrificial[_tt]\n"
    "                _tdesc = AXELROD_ARCHETYPE_DESCRIPTIONS.get(_tarch, '')[:100]\n"
    "                lines.append(f\"  SACRIFICIAL #{_tr}: {_tname} — must execute \\'{_tarch}\\' archetype only | {_tdesc}\")"
)


def is_placeholder(rel_path: str) -> bool:
    p = REPO_ROOT / rel_path
    if not p.exists():
        return True
    n = p.read_text(encoding='utf-8', errors='replace').count('\n') + 1
    return n < MIN_LINES


def restore_from_git(rel_path: str) -> str:
    content = subprocess.check_output(
        ['git', 'show', f'{RESTORE_SHA}:{rel_path}'],
        cwd=REPO_ROOT, text=True
    )
    n = content.count('\n') + 1
    print(f'[restore_fire107] git show {RESTORE_SHA}:{rel_path} => {n} lines')
    if n < 1000:
        print(f'[restore_fire107] ERROR: {rel_path} too short ({n}L) — aborting')
        sys.exit(1)
    return content


def apply_fire100_tune(content: str, label: str) -> str:
    if OLD_SACC not in content:
        if '_tdesc = AXELROD_ARCHETYPE_DESCRIPTIONS' in content:
            print(f'[restore_fire107] {label}: fire-100 tune already present — skip')
            return content
        print(f'[restore_fire107] ERROR: {label}: patch target not found — unexpected content')
        sys.exit(1)
    patched = content.replace(OLD_SACC, NEW_SACC, 1)
    print(f'[restore_fire107] {label}: fire-100 tune applied (+1 line)')
    return patched


def compile_check(content: str, label: str) -> None:
    with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as tf:
        tf.write(content)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print(f'[restore_fire107] {label}: py_compile PASS')
    except py_compile.PyCompileError as exc:
        print(f'[restore_fire107] {label}: py_compile FAIL — {exc}')
        sys.exit(1)
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass


def main():
    os.chdir(REPO_ROOT)
    print(f'[restore_fire107] repo root: {REPO_ROOT}')

    nba_ph = is_placeholder(NBA_PATH)
    pol_ph = is_placeholder(POL_PATH)
    if not nba_ph and not pol_ph:
        print(f'[restore_fire107] Both files already >{MIN_LINES} lines — no-op.')
        return

    print('[restore_fire107] Fetching origin/main to ensure RESTORE_SHA is reachable ...')
    subprocess.run(['git', 'fetch', 'origin', 'main'], check=True, cwd=REPO_ROOT)

    nba_content = restore_from_git(NBA_PATH)
    pol_content = restore_from_git(POL_PATH)

    nba_patched = apply_fire100_tune(nba_content, 'NBA')
    pol_patched = apply_fire100_tune(pol_content, 'POL')

    compile_check(nba_patched, 'NBA')
    compile_check(pol_patched, 'POL')

    (REPO_ROOT / NBA_PATH).write_text(nba_patched, encoding='utf-8')
    (REPO_ROOT / POL_PATH).write_text(pol_patched, encoding='utf-8')

    nba_lines = nba_patched.count('\n') + 1
    pol_lines = pol_patched.count('\n') + 1
    print(f'[restore_fire107] Written NBA {nba_lines}L, POL {pol_lines}L')

    safe_commit = str(REPO_ROOT / 'scripts/lib/safe_commit.sh')
    msg = (
        'feat(tf): Axelrod mechanism A — day-end common knowledge broadcast (both NBA+Political)\n\n'
        f'Restore both TF app.py from {RESTORE_SHA} (placeholder accident since fire-100/704a645).\n'
        'Applies fire-100 tune: SACRIFICIAL tier entries in build_common_knowledge_block()\n'
        'now show inline archetype description (_tdesc) alongside archetype name.\n\n'
        f'NBA {nba_lines}L | POL {pol_lines}L | py_compile PASS both.\n'
        'Mechs A/B/C at parity: GF leaderboard, 3d rolling bets, consensus picks+pnl/wr,\n'
        'peer CK stances, archetype perf, D+1 tier assignments w/ inline desc — all spec met.\n'
        'do_not_push_hf_space_yet — commit to mon-ipad only, human review before HF deploy.\n\n'
        'Co-Authored-By: Claude Cloud Trigger <noreply@anthropic.com>'
    )
    result = subprocess.run(
        [safe_commit, 'AXELROD-2026-FIRE-107-VM', msg, NBA_PATH, POL_PATH],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f'[restore_fire107] safe_commit failed (rc={result.returncode}):\n{result.stderr}')
        sys.exit(1)
    print('[restore_fire107] DONE — NBA + POL restored and committed.')


if __name__ == '__main__':
    main()
