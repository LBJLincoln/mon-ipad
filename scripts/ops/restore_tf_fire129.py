#!/usr/bin/env python3
"""
Restore NBA+POL TF app.py — fire-129: Mech C schema 25->27 fields (is_rogue+rogue_reasons).

Run from mon-ipad git repo root:
    git pull && python scripts/ops/restore_tf_fire129.py

Fetches clean baselines from git history:
  NBA: 5b0c697b (5975L, fire-126 KL-divergence-fix baseline)
  POL: 4b43214d (3956L, fire-126 KL-divergence-fix baseline)

Applies 3-part patch to each:
  1. write_axelrod_log signature: add day_rogue_state Optional[dict] = None
  2. Row schema: add is_rogue + rogue_reasons after used_archetypes_7d
  3. Call site: pass day_rogue_state=day_rogue_state

py_compiles both, commits to main, pushes.
Commit 2c7a49b5 (fire-128) had accidentally pushed stubs — this restores them.
"""
import subprocess
import sys
import py_compile
import tempfile
import os

NBA_SHA = "5b0c697b5ac0958591261b29d7c58f91ddeff0f8"
POL_SHA = "4b43214d121910d5b1a128b04fcb45cab3e57b7c"
NBA_PATH = "scripts/arena/hf-llm-trading-floor/app.py"
POL_PATH = "scripts/arena/hf-political-trading-floor/app.py"


def git_show(sha, path):
    result = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        capture_output=True, text=True, check=True
    )
    return result.stdout


def patch_file(src, fleet):
    # 1. Signature: add day_rogue_state param after society_archetypes_by_day
    old_sig = ("                       society_archetypes_by_day: Optional[Dict] = None) -> None:")
    new_sig = ("                       society_archetypes_by_day: Optional[Dict] = None,\n"
               "                       day_rogue_state: Optional[dict] = None) -> None:")
    assert src.count(old_sig) == 1, f"{fleet}: expected 1 occurrence of sig, got {src.count(old_sig)}"
    src = src.replace(old_sig, new_sig)

    # 2. Schema: add is_rogue + rogue_reasons after used_archetypes_7d
    old_schema = ('                "used_archetypes_7d": used_archetypes_7d,\n'
                  '            })')
    new_schema = ('                "used_archetypes_7d": used_archetypes_7d,\n'
                  '                "is_rogue": (day_rogue_state or {}).get(tid, {}).get("is_rogue", False),\n'
                  '                "rogue_reasons": (day_rogue_state or {}).get(tid, {}).get("reasons", []),\n'
                  '            })')
    assert src.count(old_schema) == 1, f"{fleet}: expected 1 occurrence of schema tail, got {src.count(old_schema)}"
    src = src.replace(old_schema, new_schema)

    # 3. Call site: add day_rogue_state=day_rogue_state kwarg
    old_call = ("                          society_archetypes_by_day=dict(_society_archetypes_by_day))\n"
                "\n"
                "        # Axelrod Mechanism B:")
    new_call = ("                          society_archetypes_by_day=dict(_society_archetypes_by_day),\n"
                "                          day_rogue_state=day_rogue_state)\n"
                "\n"
                "        # Axelrod Mechanism B:")
    assert src.count(old_call) == 1, f"{fleet}: expected 1 occurrence of call site, got {src.count(old_call)}"
    src = src.replace(old_call, new_call)

    return src


def py_compile_check(content, label):
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(content)
        fname = f.name
    try:
        py_compile.compile(fname, doraise=True)
        nlines = content.count("\n") + 1
        print(f"  py_compile PASS {label} {nlines}L")
    except py_compile.PyCompileError as e:
        print(f"  py_compile FAIL {label}: {e}")
        sys.exit(1)
    finally:
        os.unlink(fname)


def main():
    print("restore_tf_fire129: fetching baselines from git history...")
    nba_src = git_show(NBA_SHA, NBA_PATH)
    pol_src = git_show(POL_SHA, POL_PATH)
    print(f"  NBA base: {nba_src.count(chr(10)) + 1}L from {NBA_SHA[:8]}")
    print(f"  POL base: {pol_src.count(chr(10)) + 1}L from {POL_SHA[:8]}")

    print("Applying patches...")
    nba_patched = patch_file(nba_src, "NBA")
    pol_patched = patch_file(pol_src, "POL")

    for label, patched in [("NBA", nba_patched), ("POL", pol_patched)]:
        assert "is_rogue" in patched, f"{label}: is_rogue missing after patch"
        assert "rogue_reasons" in patched, f"{label}: rogue_reasons missing after patch"
        assert "day_rogue_state: Optional[dict] = None" in patched, f"{label}: signature patch failed"
        assert "day_rogue_state=day_rogue_state)" in patched, f"{label}: call site patch failed"

    py_compile_check(nba_patched, "NBA")
    py_compile_check(pol_patched, "POL")

    print("Writing files...")
    with open(NBA_PATH, "w") as f:
        f.write(nba_patched)
    with open(POL_PATH, "w") as f:
        f.write(pol_patched)
    print(f"  Wrote {NBA_PATH} ({nba_patched.count(chr(10)) + 1}L)")
    print(f"  Wrote {POL_PATH} ({pol_patched.count(chr(10)) + 1}L)")

    print("Committing...")
    subprocess.run(["git", "add", NBA_PATH, POL_PATH], check=True)
    msg = (
        "feat(tf): restore NBA+POL TF app.py — Mech C 25→27 fields "
        "(is_rogue+rogue_reasons per-agent) / NBA 5979L / POL 3961L\n"
        "\n"
        "write_axelrod_log now records is_rogue (bool) + rogue_reasons (list) for\n"
        "each agent row. Rogue mode is a confound for Mech B sacrificial tier\n"
        "analysis. KL-divergence fix (D_KL(agent||peers), self-excluded) from\n"
        "fire-126 retained. py_compile PASS both. do_not_push_hf_space_yet.\n"
        "\n"
        "Co-Authored-By: Claude Cloud Trigger <noreply@anthropic.com>"
    )
    subprocess.run(["git", "commit", "-m", msg], check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], check=True)
    print("Done. NBA 5979L / POL 3961L committed and pushed.")


if __name__ == "__main__":
    main()
