#!/usr/bin/env python3
"""Restore NBA TF app.py — cloud trigger fire-55 pushed placeholder content twice.

Background:
  fire-54 (2026-05-07T00h): commit bf5980ef truncated NBA app.py to 9-line stub.
  fire-55 (2026-05-07T06h): cloud trigger tried to restore from 73b9c9f9 but
    accidentally pushed placeholder literal "PLACEHOLDER_NBA" instead of full source.
    Bad commit: 297facd4faaa25dc42153f679e907a6b506a7c4e (15-char stub)

  Last good commit: 73b9c9f93cc9676ceaa38607154c9f5d5b0e8503
    (5799L, Mechs A/B/C + KL divergence, verified py_compile PASS)

Patches applied on top of 73b9c9f9 (in order):
  1. Axelrod verify+tune fire-12 — thesis fallback parity:
     build_common_knowledge_block() _rat: 'rationale' or 'thesis'
     Matches Political TF L2207.
  2. AXELROD-2026 Mech A GF improvement (fire-57):
     build_common_knowledge_block() leaderboard: add explicit GF=X.XXXx label.
     Spec: "Include each agent's cumulative rank (by bankroll growth factor)".
     Parity: same change applied to Political TF via apply_axelrod2026_mech_a_gf.py.

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

# Patch 1: thesis fallback parity (fire-12 / fire-55 intended)
OLD_THESIS = "                    _rat = (a.get('rationale') or '')[:60]"
NEW_THESIS = "                    _rat = (a.get('rationale') or a.get('thesis') or '')[:60]"

# Patch 2: AXELROD-2026 Mech A — explicit bankroll growth factor in leaderboard (fire-57)
OLD_GF = '            f"  #{rank} {cfg.get(\'name\', tid):<20} ${ts[\'bankroll\']:.2f} ({roi:+.1f}%)"'
NEW_GF = '            f"  #{rank} {cfg.get(\'name\', tid):<20} ${ts[\'bankroll\']:.2f} GF={gf:.3f}× ({roi:+.1f}%)"'


def run(cmd, **kw):
    return subprocess.check_output(cmd, text=True, **kw)


def apply_patch(text, old, new, patch_name):
    count = text.count(old)
    if count == 0:
        if new in text:
            print(f'[restore-fire55] {patch_name}: already applied — skip')
            return text
        print(f'[restore-fire55] ERROR: {patch_name} target not found — unexpected content')
        sys.exit(1)
    if count > 1:
        print(f'[restore-fire55] ERROR: {patch_name} target found {count}x — ambiguous, aborting')
        sys.exit(1)
    result = text.replace(old, new, 1)
    print(f'[restore-fire55] {patch_name}: APPLIED (1 occurrence)')
    return result


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

    # Apply patches in sequence
    patched = apply_patch(original, OLD_THESIS, NEW_THESIS, 'thesis-fallback')
    patched = apply_patch(patched, OLD_GF, NEW_GF, 'axelrod-2026-gf-label')

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
        'feat(tf): Axelrod mechanism A — day-end common knowledge broadcast (both NBA+Political)\n\n'
        'Restore NBA TF app.py from fire-54/55 stub accidents + 2 sequential patches:\n\n'
        '1. Thesis fallback parity (Axelrod verify+tune fire-12):\n'
        '   build_common_knowledge_block() L~3548:\n'
        "   _rat = (a.get('rationale') or a.get('thesis') or '')[:60]\n"
        '   Matches Political TF — populates edge_rationale when agents write\n'
        "   under 'thesis' key.\n\n"
        '2. AXELROD-2026 Mech A GF improvement (fire-57):\n'
        '   build_common_knowledge_block() leaderboard line:\n'
        "   OLD: ${ts['bankroll']:.2f} ({roi:+.1f}%)\n"
        "   NEW: ${ts['bankroll']:.2f} GF={gf:.3f}× ({roi:+.1f}%)\n"
        '   Spec: "Include each agent\'s cumulative rank (by bankroll growth factor)."\n\n'
        'py_compile PASS. do_not_push_hf_space_yet — mon-ipad only.\n\n'
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
