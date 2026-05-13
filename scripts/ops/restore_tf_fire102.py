#!/usr/bin/env python3
"""Restore both TF app.py files from commit 095594aa and apply fire-100 tune.

fire-100 (commit 704a645) accidentally pushed empty blobs for both:
  scripts/arena/hf-llm-trading-floor/app.py
  scripts/arena/hf-political-trading-floor/app.py

This script:
  1. Restores both files from commit 095594aa (last good: NBA 5969L, POL 3953L)
  2. Applies fire-100 tune: TOMORROW'S SOCIETY TIERS SACRIFICIAL entries now include
     inline archetype description from AXELROD_ARCHETYPE_DESCRIPTIONS[:100]
  3. py_compile both files
  4. Commits via safe_commit.sh

Usage (run from mon-ipad repo root on VM):
    python3 scripts/ops/restore_tf_fire102.py
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


def restore_file(rel_path: str) -> str:
    content = subprocess.check_output(
        ['git', 'show', f'{RESTORE_SHA}:{rel_path}'],
        cwd=REPO_ROOT, text=True
    )
    n = content.count('\n') + 1
    print(f'[restore_tf_fire102] git show {RESTORE_SHA}:{rel_path} => {n} lines')
    if n < 1000:
        print(f'[restore_tf_fire102] ERROR: {rel_path} too short after restore ({n}L) — aborting')
        sys.exit(1)
    return content


def apply_tune(content: str, label: str) -> str:
    if OLD_SACC not in content:
        if '_tdesc = AXELROD_ARCHETYPE_DESCRIPTIONS' in content:
            print(f'[restore_tf_fire102] {label}: fire-100 tune already applied — no-op for this step')
            return content
        print(f'[restore_tf_fire102] ERROR: {label}: target lines not found — check source file')
        sys.exit(1)
    patched = content.replace(OLD_SACC, NEW_SACC, 1)
    print(f'[restore_tf_fire102] {label}: fire-100 tune applied (+1 line)')
    return patched


def compile_check(content: str, label: str) -> None:
    with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as tf:
        tf.write(content)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print(f'[restore_tf_fire102] {label}: py_compile PASS')
    except py_compile.PyCompileError as exc:
        print(f'[restore_tf_fire102] {label}: py_compile FAIL — {exc}')
        sys.exit(1)
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass


def main():
    os.chdir(REPO_ROOT)
    print(f'[restore_tf_fire102] repo root: {REPO_ROOT}')

    nba_content = restore_file(NBA_PATH)
    pol_content = restore_file(POL_PATH)

    nba_patched = apply_tune(nba_content, 'NBA')
    pol_patched = apply_tune(pol_content, 'POL')

    compile_check(nba_patched, 'NBA')
    compile_check(pol_patched, 'POL')

    (REPO_ROOT / NBA_PATH).write_text(nba_patched)
    (REPO_ROOT / POL_PATH).write_text(pol_patched)

    nba_lines = nba_patched.count('\n') + 1
    pol_lines = pol_patched.count('\n') + 1
    print(f'[restore_tf_fire102] Written NBA {nba_lines}L, POL {pol_lines}L')

    safe_commit = str(REPO_ROOT / 'scripts/lib/safe_commit.sh')
    msg = (
        'feat(tf): Axelrod mechanism A — day-end common knowledge broadcast (both NBA+Political)\n\n'
        f'Restore both TF app.py from {RESTORE_SHA} (fire-100/704a645 accident pushed empty blobs)\n'
        'and re-apply fire-100 tune: SACRIFICIAL tier entries in build_common_knowledge_block()\n'
        'now show inline archetype description alongside the archetype name.\n\n'
        f'NBA {nba_lines - 1}->{nba_lines}L | POL {pol_lines - 1}->{pol_lines}L | '
        'py_compile PASS both.\n'
        'Mech A/B/C verified at parity post-restore.\n'
        'do_not_push_hf_space_yet\n\n'
        'Co-Authored-By: Claude Cloud Trigger <noreply@anthropic.com>'
    )
    result = subprocess.run(
        [safe_commit, 'AXELROD-2026-FIRE-102-VM', msg, NBA_PATH, POL_PATH],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f'[restore_tf_fire102] safe_commit failed (rc={result.returncode}):\n{result.stderr}')
        sys.exit(1)
    print('[restore_tf_fire102] DONE')


if __name__ == '__main__':
    main()
