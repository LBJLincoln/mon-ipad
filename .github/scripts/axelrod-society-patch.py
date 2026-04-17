#!/usr/bin/env python3
"""Axelrod Mech B — society-wide archetype dedup patch (fire-8).

Applies 3 changes to both NBA and Political trading-floor app.py:
  1. Add _society_archetypes_by_day global
  2. assign_sacrificial_archetypes: use society-wide dedup instead of per-agent
  3. run_experiment: clear _society_archetypes_by_day on fresh run
"""
import sys

FILES = {
    'nba': 'scripts/arena/hf-llm-trading-floor/app.py',
    'pol': 'scripts/arena/hf-political-trading-floor/app.py',
}

NBA_OLD_BODY = (
    '    assignments: Dict[str, str] = {}\n'
    '    for tid in bottom:\n'
    '        unused = [a for a in AXELROD_ARCHETYPES if a not in _used_archetypes[tid]]\n'
    '        if not unused:\n'
    '            _used_archetypes[tid].clear()  # exhausted \u2192 rotate again\n'
    '            unused = list(AXELROD_ARCHETYPES)\n'
    '        # Deterministic pick by tid-hash for reproducibility\n'
    '        pick = unused[hash(tid + day_date) % len(unused)]\n'
    '        assignments[tid] = pick\n'
    '        _used_archetypes[tid].add(pick)\n'
    '    return assignments'
)

POL_OLD_BODY = (
    '    assignments: Dict[str, str] = {}\n'
    '    for tid in bottom:\n'
    '        unused = [a for a in AXELROD_ARCHETYPES if a not in _used_archetypes[tid]]\n'
    '        if not unused:\n'
    '            _used_archetypes[tid].clear()\n'
    '            unused = list(AXELROD_ARCHETYPES)\n'
    '        pick = unused[hash(tid + day_date) % len(unused)]\n'
    '        assignments[tid] = pick\n'
    '        _used_archetypes[tid].add(pick)\n'
    '    return assignments'
)

NEW_BODY = (
    '    assignments: Dict[str, str] = {}\n'
    '    for tid in bottom:\n'
    '        # Society-wide dedup: prevents two agents getting same archetype in trailing window\n'
    '        society_used = set().union(*_society_archetypes_by_day.values()) if _society_archetypes_by_day else set()\n'
    '        unused = [a for a in AXELROD_ARCHETYPES if a not in society_used]\n'
    '        if not unused:\n'
    '            unused = list(AXELROD_ARCHETYPES)  # All used society-wide \u2192 allow reuse\n'
    '        # Deterministic pick by tid-hash for reproducibility\n'
    '        pick = unused[hash(tid + day_date) % len(unused)]\n'
    '        assignments[tid] = pick\n'
    '        _society_archetypes_by_day.setdefault(day_date, set()).add(pick)\n'
    '        _used_archetypes[tid].add(pick)\n'
    '    return assignments'
)

GLOBAL_OLD = '_used_archetypes: Dict[str, set] = defaultdict(set)  # Axelrod Mech B: tid \u2192 set of archetypes tried'
GLOBAL_NEW = (GLOBAL_OLD +
              '\n_society_archetypes_by_day: Dict[str, set] = {}'
              '  # Axelrod Mech B: day \u2192 archetypes assigned society-wide')

CLEAR_OLD = '    _used_archetypes.clear()  # Axelrod Mech B: reset archetype history'
CLEAR_NEW = (CLEAR_OLD +
             '\n    _society_archetypes_by_day.clear()'
             '  # Axelrod Mech B: reset society-wide archetype history')

errors = []
for label, path in FILES.items():
    old_body = NBA_OLD_BODY if label == 'nba' else POL_OLD_BODY
    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        errors.append(f'[{label}] File not found: {path}')
        continue

    if '_society_archetypes_by_day' in content:
        count = content.count('_society_archetypes_by_day')
        print(f'[{label}] Already patched ({count} occurrences) \u2014 skipping')
        continue

    for desc, old, new in [
        ('global', GLOBAL_OLD, GLOBAL_NEW),
        ('body',   old_body,   NEW_BODY),
        ('clear',  CLEAR_OLD,  CLEAR_NEW),
    ]:
        if old not in content:
            errors.append(f'[{label}] MISS: {desc} \u2014 pattern not found')
            print(f'  MISS pattern start: {repr(old[:60])}', file=sys.stderr)
        else:
            content = content.replace(old, new, 1)
            print(f'[{label}] Applied: {desc}')

    count = content.count('_society_archetypes_by_day')
    if count != 5:
        errors.append(f'[{label}] Verification FAIL: expected 5 occurrences, got {count}')
        continue

    import py_compile, tempfile, os
    tmp = tempfile.mktemp(suffix='.py')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(content)
    try:
        py_compile.compile(tmp, doraise=True)
        print(f'[{label}] py_compile: PASS')
    except py_compile.PyCompileError as e:
        errors.append(f'[{label}] py_compile FAIL: {e}')
        os.unlink(tmp)
        continue
    os.unlink(tmp)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'[{label}] Written: {path} ({count} occurrences, {len(content)} chars)')

if errors:
    for e in errors:
        print('ERROR:', e, file=sys.stderr)
    sys.exit(1)
print('ALL PATCHES APPLIED SUCCESSFULLY')
