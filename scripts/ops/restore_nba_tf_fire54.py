#!/usr/bin/env python3
"""Restore NBA TF app.py — accidentally truncated to 9-line stub in commit bf5980ef.

Background:
  fire-54 (2026-05-07T00h): cloud trigger called create_or_update_file with
  placeholder content instead of the full 5800-line NBA TF source.
  Bad commit:     bf5980ef45949686f7dbb222ac2c0e054f2ecc48  (9-line stub, 499B)
  Last good blob: 7eb7429ad6980648d85c41dc8c136b922e0c5bce  (292KB, 5800 lines)
  Parent commit:  bf5980ef^ (= 8488c42c810f8a2ef364d2317b62863f5e92c3fa)

Intended patch (Axelrod verify+tune fire-54):
  scripts/arena/hf-llm-trading-floor/app.py L3548:
  - OLD: _rat = (a.get('rationale') or '')[:60]
  + NEW: _rat = (a.get('rationale') or a.get('thesis') or '')[:60]
  Matches Political TF which already checks both fields.

Usage (run from mon-ipad repo root):
  python3 scripts/ops/restore_nba_tf_fire54.py
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
TARGET = 'scripts/arena/hf-llm-trading-floor/app.py'
PARENT_REF = 'bf5980ef45949686f7dbb222ac2c0e054f2ecc48^'

OLD_LINE = "                    _rat = (a.get('rationale') or '')[:60]"
NEW_LINE = "                    _rat = (a.get('rationale') or a.get('thesis') or '')[:60]"


def run(cmd, **kw):
    return subprocess.check_output(cmd, text=True, **kw)


def main():
    print('[restore-fire54] Fetching origin/main...')
    subprocess.run(['git', 'fetch', 'origin', 'main'], check=True, cwd=REPO_ROOT)

    print(f'[restore-fire54] git show {PARENT_REF}:{TARGET}')
    original = run(['git', 'show', f'{PARENT_REF}:{TARGET}'], cwd=REPO_ROOT)
    n_lines = original.count('\n') + 1
    print(f'[restore-fire54] Got {len(original)} chars, {n_lines} lines')
    if n_lines < 1000:
        print('[restore-fire54] ERROR: too few lines — unexpected content, aborting')
        sys.exit(1)

    count = original.count(OLD_LINE)
    if count == 0:
        print('[restore-fire54] NOTE: thesis line not found — may already be patched or wrong version')
        patched = original
    elif count > 1:
        print(f'[restore-fire54] ERROR: target line found {count} times — ambiguous, aborting')
        sys.exit(1)
    else:
        patched = original.replace(OLD_LINE, NEW_LINE, 1)
        print('[restore-fire54] Applied thesis fallback patch (1 occurrence)')

    with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as tf:
        tf.write(patched)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print('[restore-fire54] py_compile: PASS')
    except py_compile.PyCompileError as exc:
        print(f'[restore-fire54] py_compile: FAIL — {exc}')
        sys.exit(1)
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass

    target_path = REPO_ROOT / TARGET
    target_path.write_text(patched)
    print(f'[restore-fire54] Written {target_path} ({len(patched)} chars)')

    safe_commit = str(REPO_ROOT / 'scripts/lib/safe_commit.sh')
    msg = (
        'fix(tf): restore NBA TF app.py full source + thesis fallback (fire-54 truncation fix)\n\n'
        'Restores scripts/arena/hf-llm-trading-floor/app.py from 9-line stub (commit bf5980ef)\n'
        'back to full 5800-line source. Applies the intended fire-54 Axelrod verify+tune patch:\n'
        "  L3548: a.get('rationale') now also a.get('thesis') fallback, matching POL TF parity.\n\n"
        'py_compile PASS. do_not_push_hf_space_yet — mon-ipad only.\n\n'
        'Co-Authored-By: Claude Cloud Trigger <noreply@anthropic.com>'
    )
    result = subprocess.run(
        [safe_commit, 'AXELROD-RESTORE-FIRE54', msg, TARGET],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f'[restore-fire54] safe_commit failed (rc={result.returncode}):\n{result.stderr}')
        sys.exit(1)
    print('[restore-fire54] DONE')


if __name__ == '__main__':
    main()
