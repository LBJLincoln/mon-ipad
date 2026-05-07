#!/usr/bin/env python3
"""Apply AXELROD-2026 Mechanism A GF improvement to Political TF app.py.

Adds explicit 'GF=X.XXXx' (bankroll growth factor) label to the COMMON_KNOWLEDGE
leaderboard in build_common_knowledge_block(), matching the AXELROD-2026 Mech A spec:
  "Include each agent's cumulative rank (by bankroll growth factor)
   so every LLM sees the leaderboard."

NBA TF gets the same patch via scripts/ops/restore_nba_tf_fire55.py.
Run BOTH scripts for full NBA+Political parity.

Usage (run from mon-ipad repo root):
    python3 scripts/ops/apply_axelrod2026_mech_a_gf.py
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
TARGET = 'scripts/arena/hf-political-trading-floor/app.py'

OLD_GF = '            f"  #{rank} {cfg.get(\'name\', tid):<20} ${ts[\'bankroll\']:.2f} ({roi:+.1f}%)"'
NEW_GF = '            f"  #{rank} {cfg.get(\'name\', tid):<20} ${ts[\'bankroll\']:.2f} GF={gf:.3f}× ({roi:+.1f}%)"'


def main():
    target_path = REPO_ROOT / TARGET
    if not target_path.exists():
        print(f'[axelrod-gf-pol] ERROR: {target_path} not found')
        sys.exit(1)

    original = target_path.read_text()
    n_lines = original.count('\n') + 1
    print(f'[axelrod-gf-pol] Read {len(original)} chars, {n_lines} lines')
    if n_lines < 1000:
        print('[axelrod-gf-pol] ERROR: too few lines — placeholder content, aborting')
        sys.exit(1)

    count = original.count(OLD_GF)
    if count == 0:
        if 'GF={gf:.3f}' in original:
            print('[axelrod-gf-pol] GF patch already applied — no-op')
            sys.exit(0)
        print('[axelrod-gf-pol] ERROR: target line not found — unexpected content')
        sys.exit(1)
    if count > 1:
        print(f'[axelrod-gf-pol] ERROR: target line found {count}x — ambiguous, aborting')
        sys.exit(1)

    patched = original.replace(OLD_GF, NEW_GF, 1)
    print('[axelrod-gf-pol] Applied GF growth factor label (1 occurrence)')

    with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as tf:
        tf.write(patched)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print('[axelrod-gf-pol] py_compile: PASS')
    except py_compile.PyCompileError as exc:
        print(f'[axelrod-gf-pol] py_compile: FAIL — {exc}')
        sys.exit(1)
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass

    target_path.write_text(patched)
    print(f'[axelrod-gf-pol] Written {target_path} ({len(patched)} chars)')

    safe_commit = str(REPO_ROOT / 'scripts/lib/safe_commit.sh')
    msg = (
        'feat(tf): Axelrod mechanism A — day-end common knowledge broadcast (both NBA+Political)\n\n'
        'AXELROD-2026 Mech A GF parity patch: Political TF build_common_knowledge_block()\n'
        'leaderboard now shows explicit bankroll growth factor per agent.\n\n'
        'Political TF L~2180:\n'
        "  OLD: ${ts['bankroll']:.2f} ({roi:+.1f}%)\n"
        "  NEW: ${ts['bankroll']:.2f} GF={gf:.3f}× ({roi:+.1f}%)\n\n"
        'Spec: "Include each agent\'s cumulative rank (by bankroll growth factor)\n'
        'so every LLM sees the leaderboard." — AXELROD-2026 Mechanism A.\n\n'
        'NBA TF gets same patch via scripts/ops/restore_nba_tf_fire55.py (run separately).\n'
        'py_compile PASS. do_not_push_hf_space_yet — mon-ipad only.\n\n'
        'Co-Authored-By: Claude Cloud Trigger <noreply@anthropic.com>'
    )
    result = subprocess.run(
        [safe_commit, 'AXELROD-2026-MECH-A-GF-POL', msg, TARGET],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f'[axelrod-gf-pol] safe_commit failed (rc={result.returncode}):\n{result.stderr}')
        sys.exit(1)
    print('[axelrod-gf-pol] DONE')


if __name__ == '__main__':
    main()
