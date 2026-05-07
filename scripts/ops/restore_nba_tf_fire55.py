#!/usr/bin/env python3
"""Restore NBA TF app.py — cloud trigger fire-55 pushed placeholder content twice.

Background:
  fire-54 (2026-05-07T00h): commit bf5980ef truncated NBA app.py to 9-line stub.
  fire-55 (2026-05-07T06h): cloud trigger tried to restore from 73b9c9f9 but
    accidentally pushed placeholder literal "PLACEHOLDER_NBA" instead of full source.
    Bad commit: 297facd4faaa25dc42153f679e907a6b506a7c4e (15-char stub)

  Last good commit: 73b9c9f93cc9676ceaa38607154c9f5d5b0e8503
    (5799L, Mechs A/B/C + KL divergence, verified py_compile PASS)

Intended patch (Axelrod verify+tune fire-12 / fire-55):
  scripts/arena/hf-llm-trading-floor/app.py build_common_knowledge_block():
  - OLD: _rat = (a.get('rationale') or '')[:60]
  + NEW: _rat = (a.get('rationale') or a.get('thesis') or '')[:60]
  Matches Political TF L2207 which already checks both keys.

Usage (run from mon-ipad repo root):
  python3 scripts/ops/restore_nba_tf_fire55.py
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
GOOD_REF = '73b9c9f93cc9676ceaa38607154c9f5d5b0e8503'

OLD_LINE = "                    _rat = (a.get('rationale') or '')[:60]"
NEW_LINE = "                    _rat = (a.get('rationale') or a.get('thesis') or '')[:60]"


def run(cmd, **kw):
    return subprocess.check_output(cmd, text=True, **kw)


def main():
    print('[restore-fire55] Fetching origin/main ...')
    subprocess.run(['git', 'fetch', 'origin', 'main'], check=True, cwd=REPO_ROOT)

    print(f'[restore-fire55] git show {GOOD_REF}:{TARGET}')
    original = run(['git', 'show', f'{GOOD_REF}:{TARGET}'], cwd=REPO_ROOT)
    n_lines = original.count('\n') + 1
    print(f'[restore-fire55] Got {len(original)} chars, {n_lines} lines')
    if n_lines < 5000:
        print('[restore-fire55] ERROR: too few lines — unexpected content, aborting')
        sys.exit(1)

    count = original.count(OLD_LINE)
    if count == 0:
        print('[restore-fire55] NOTE: thesis patch target not found — checking if already applied')
        already = "(a.get('rationale') or a.get('thesis') or '')[:60]"
        if already in original:
            print('[restore-fire55] thesis patch already present — no patch needed')
            patched = original
        else:
            print('[restore-fire55] ERROR: neither old nor new line found — unexpected content')
            sys.exit(1)
    elif count > 1:
        print(f'[restore-fire55] ERROR: target line found {count}x — ambiguous, aborting')
        sys.exit(1)
    else:
        patched = original.replace(OLD_LINE, NEW_LINE, 1)
        print('[restore-fire55] Applied thesis fallback patch (1 occurrence)')

    with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as tf:
        tf.write(patched)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print('[restore-fire55] py_compile: PASS')
    except py_compile.PyCompileError as exc:
        print(f'[restore-fire55] py_compile: FAIL — {exc}')
        sys.exit(1)
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass

    target_path = REPO_ROOT / TARGET
    target_path.write_text(patched)
    print(f'[restore-fire55] Written {target_path} ({len(patched)} chars)')

    safe_commit = str(REPO_ROOT / 'scripts/lib/safe_commit.sh')
    msg = (
        'fix(tf): restore NBA app.py from fire-54/55 stub + thesis fallback parity (Axelrod verify+tune fire-12)\n\n'
        'Two successive cloud-trigger stub accidents corrupted scripts/arena/hf-llm-trading-floor/app.py:\n'
        '  fire-54: commit bf5980ef pushed 9-line stub (499B)\n'
        '  fire-55: commit 297facd4 pushed literal PLACEHOLDER_NBA (15B)\n\n'
        'Restored from last good commit 73b9c9f9 (5799L, Mechs A/B/C + KL divergence).\n'
        'Applied Axelrod verify+tune fire-12 parity patch:\n'
        "  build_common_knowledge_block() L3548:\n"
        "  _rat = (a.get('rationale') or a.get('thesis') or '')[:60]\n"
        '  Matches Political TF L2207. Ensures edge_rationale populated when agents\n'
        "  write under 'thesis' key instead of 'rationale'.\n\n"
        'py_compile PASS (5799L). do_not_push_hf_space_yet — mon-ipad only.\n\n'
        'Co-Authored-By: Claude Cloud Trigger <noreply@anthropic.com>'
    )
    result = subprocess.run(
        [safe_commit, 'AXELROD-RESTORE-FIRE55', msg, TARGET],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f'[restore-fire55] safe_commit failed (rc={result.returncode}):\n{result.stderr}')
        sys.exit(1)
    print('[restore-fire55] DONE')


if __name__ == '__main__':
    main()
