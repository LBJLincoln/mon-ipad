#!/usr/bin/env python3
"""
AXELROD-2026 Mech B log patch — fire-63
Adds tier/was_challenged/challenge_rank/trailing_7d_delta to write_axelrod_log()
in BOTH NBA + Political TF app.py files.

Run from mon-ipad repo root:
    python3 scripts/ops/apply_mechb_log_patch.py
"""
import pathlib, sys

REPO = pathlib.Path(__file__).resolve().parents[2]

FILES = {
    "NBA": REPO / "scripts/arena/hf-llm-trading-floor/app.py",
    "POL": REPO / "scripts/arena/hf-political-trading-floor/app.py",
}

# Patch specs: (old_snippet, new_snippet, description)
NBA_PATCHES = [
    (
        # 1. Signature
        "def write_axelrod_log(day_idx: int, day_date: str, state: Dict,\n"
        "                       agent_logs: Dict, sacrificial_map: Dict[str, str]) -> None:\n"
        "    \"\"\"Axelrod Mech C: append per-day post-mortem to /tmp/axelrod-log/day-N.jsonl.\n"
        "\n"
        "    This is the primary dataset for the Nature paper on LLM agent society game theory.\n"
        "    \"\"\"",
        "def write_axelrod_log(day_idx: int, day_date: str, state: Dict,\n"
        "                       agent_logs: Dict, sacrificial_map: Dict[str, str],\n"
        "                       challenge_map: Optional[Dict[str, int]] = None) -> None:\n"
        "    \"\"\"Axelrod Mech C: append per-day post-mortem to /tmp/axelrod-log/day-N.jsonl.\n"
        "\n"
        "    This is the primary dataset for the Nature paper on LLM agent society game theory.\n"
        "    \"\"\"",
        "write_axelrod_log signature (NBA)",
    ),
    (
        # 2. Row fields
        '                "was_sacrificed": tid in sacrificial_map,\n'
        '                "num_decisions": len(decisions),',
        '                "was_sacrificed": tid in sacrificial_map,\n'
        '                "trailing_7d_delta": round(compute_trailing_delta(tid, state, agent_logs), 2),\n'
        '                "tier": ("top-3" if rank_map[tid] <= 3 else ("sacrificial" if tid in sacrificial_map else "mid-tier")),\n'
        '                "was_challenged": bool(challenge_map and tid in challenge_map),\n'
        '                "challenge_rank": (challenge_map.get(tid) if challenge_map else None),\n'
        '                "num_decisions": len(decisions),',
        "write_axelrod_log row fields (NBA)",
    ),
    (
        # 3. Call site
        "write_axelrod_log(day_idx, day_date, state, dict(_agent_logs), dict(_sacrificial_assignments))",
        "write_axelrod_log(day_idx, day_date, state, dict(_agent_logs), dict(_sacrificial_assignments), dict(_challenge_assignments))",
        "write_axelrod_log call site (NBA)",
    ),
]

POL_PATCHES = [
    (
        # 1. Signature
        "def write_axelrod_log(day_idx: int, day_date: str, state: Dict,\n"
        "                       agent_logs: Dict, sacrificial_map: Dict[str, str]) -> None:\n"
        "    \"\"\"Axelrod Mech C: per-day post-mortem for Nature paper dataset.\"\"\"",
        "def write_axelrod_log(day_idx: int, day_date: str, state: Dict,\n"
        "                       agent_logs: Dict, sacrificial_map: Dict[str, str],\n"
        "                       challenge_map: Optional[Dict[str, int]] = None) -> None:\n"
        "    \"\"\"Axelrod Mech C: per-day post-mortem for Nature paper dataset.\"\"\"",
        "write_axelrod_log signature (POL)",
    ),
    (
        # 2. Row fields (same as NBA)
        '                "was_sacrificed": tid in sacrificial_map,\n'
        '                "num_decisions": len(decisions),',
        '                "was_sacrificed": tid in sacrificial_map,\n'
        '                "trailing_7d_delta": round(compute_trailing_delta(tid, state, agent_logs), 2),\n'
        '                "tier": ("top-3" if rank_map[tid] <= 3 else ("sacrificial" if tid in sacrificial_map else "mid-tier")),\n'
        '                "was_challenged": bool(challenge_map and tid in challenge_map),\n'
        '                "challenge_rank": (challenge_map.get(tid) if challenge_map else None),\n'
        '                "num_decisions": len(decisions),',
        "write_axelrod_log row fields (POL)",
    ),
    (
        # 3. Call site (same as NBA)
        "write_axelrod_log(day_idx, day_date, state, dict(_agent_logs), dict(_sacrificial_assignments))",
        "write_axelrod_log(day_idx, day_date, state, dict(_agent_logs), dict(_sacrificial_assignments), dict(_challenge_assignments))",
        "write_axelrod_log call site (POL)",
    ),
]

PATCH_MAP = {"NBA": NBA_PATCHES, "POL": POL_PATCHES}

errors = []
for label, path in FILES.items():
    if not path.exists():
        errors.append(f"{label}: file not found at {path}")
        continue
    content = path.read_text(encoding="utf-8")
    patches = PATCH_MAP[label]
    for old, new, desc in patches:
        if old not in content:
            errors.append(f"{label}: patch target not found — {desc}")
            continue
        content = content.replace(old, new, 1)
        print(f"  PATCHED: {desc}")
    path.write_text(content, encoding="utf-8")
    print(f"{label}: wrote {path}")

if errors:
    print("\nERRORS:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

# py_compile both files
import py_compile
for label, path in FILES.items():
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"{label}: py_compile PASS")
    except py_compile.PyCompileError as e:
        print(f"{label}: py_compile FAIL — {e}")
        sys.exit(1)

print("\nAll patches applied. Run:")
print("  bash scripts/lib/safe_commit.sh AXELROD-FIRE63 'feat(tf): Axelrod Mech B log patch — tier/was_challenged/trailing_7d_delta in write_axelrod_log (NBA+Political)' scripts/arena/hf-llm-trading-floor/app.py scripts/arena/hf-political-trading-floor/app.py data/work-queue.json")
