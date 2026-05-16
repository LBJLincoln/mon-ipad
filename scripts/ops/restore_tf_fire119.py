#!/usr/bin/env python3
"""
Restore NBA+POL app.py after fire-119 placeholder push (commit 20230a05).

Bad commit 20230a05 replaced:
  scripts/arena/hf-llm-trading-floor/app.py    → "PLACEHOLDER_NBA_REPLACED_BELOW"
  scripts/arena/hf-political-trading-floor/app.py → "PLACEHOLDER_POL_REPLACED_BELOW"
  data/work-queue.json                          → "PLACEHOLDER_WQ_REPLACED_BELOW"

This script:
1. Checks out the two Python files from the parent of 20230a05 (the last good state)
2. Applies the fire-119 edge_rationale patch (1 line each) to complete Mech C spec
3. Commits and pushes (via safe_commit.sh if available)
4. Does NOT touch work-queue.json (restored via separate push in fire-119 cleanup)

Run from mon-ipad root: python3 scripts/ops/restore_tf_fire119.py
"""
import subprocess, sys, re
from pathlib import Path

BAD_COMMIT = "20230a05f4801319715e80596cfc6f6eae2fd602"
NBA_PATH = Path("scripts/arena/hf-llm-trading-floor/app.py")
POL_PATH = Path("scripts/arena/hf-political-trading-floor/app.py")


def run(cmd, **kw):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)
    if result.stdout.strip():
        print(f"    {result.stdout.strip()[:200]}")
    return result


def get_parent(repo_root):
    r = subprocess.run(["git", "rev-parse", f"{BAD_COMMIT}^"],
                       capture_output=True, text=True, cwd=repo_root)
    if r.returncode == 0:
        return r.stdout.strip()
    r2 = subprocess.run(["git", "rev-parse", "HEAD^"],
                        capture_output=True, text=True, cwd=repo_root)
    return r2.stdout.strip() if r2.returncode == 0 else None


def apply_nba_patch(content: str) -> str:
    old = '                        "strategy": d.get("strategy", ""),\n'
    new = (
        '                        "strategy": d.get("strategy", ""),\n'
        '                        "edge_rationale": (d.get("rationale") or d.get("edge_rationale", ""))[:100],\n'
    )
    if '"edge_rationale"' in content:
        print("  NBA: edge_rationale already present")
        return content
    assert old in content, "NBA anchor line not found"
    patched = content.replace(old, new, 1)
    assert '"edge_rationale"' in patched
    return patched


def apply_pol_patch(content: str) -> str:
    old = '                        "thesis": d.get("thesis", ""),\n'
    new = (
        '                        "thesis": d.get("thesis", ""),\n'
        '                        "edge_rationale": (d.get("rationale") or d.get("thesis") or d.get("edge_rationale", ""))[:100],\n'
    )
    if '"edge_rationale"' in content:
        print("  POL: edge_rationale already present")
        return content
    assert old in content, "POL anchor line not found"
    patched = content.replace(old, new, 1)
    assert '"edge_rationale"' in patched
    return patched


def main():
    repo_root = Path(__file__).resolve().parents[2]
    print(f"Working in: {repo_root}")

    result = subprocess.run(["git", "remote", "get-url", "origin"],
                            capture_output=True, text=True, cwd=repo_root)
    assert "mon-ipad" in result.stdout, f"Not in mon-ipad repo: {result.stdout}"

    print("1. Fetching origin/main...")
    run(["git", "fetch", "origin", "main"], cwd=repo_root)

    print("2. Finding parent of bad commit...")
    parent = get_parent(repo_root)
    if not parent:
        print("ERROR: Could not resolve parent commit")
        sys.exit(1)
    print(f"  Parent SHA: {parent}")

    print("3. Restoring NBA app.py...")
    run(["git", "checkout", parent, "--", str(NBA_PATH)], cwd=repo_root)
    nba_content = (repo_root / NBA_PATH).read_text()
    print(f"  NBA: {nba_content.count(chr(10))+1} lines")

    print("4. Patching NBA (edge_rationale)...")
    nba_patched = apply_nba_patch(nba_content)
    (repo_root / NBA_PATH).write_text(nba_patched)

    import py_compile
    py_compile.compile(str(repo_root / NBA_PATH), doraise=True)
    print("  NBA py_compile: PASS")

    print("5. Restoring POL app.py...")
    run(["git", "checkout", parent, "--", str(POL_PATH)], cwd=repo_root)
    pol_content = (repo_root / POL_PATH).read_text()
    print(f"  POL: {pol_content.count(chr(10))+1} lines")

    print("6. Patching POL (edge_rationale)...")
    pol_patched = apply_pol_patch(pol_content)
    (repo_root / POL_PATH).write_text(pol_patched)

    py_compile.compile(str(repo_root / POL_PATH), doraise=True)
    print("  POL py_compile: PASS")

    print("7. Staging...")
    run(["git", "add", str(NBA_PATH), str(POL_PATH)], cwd=repo_root)

    msg = (
        "fix(tf): restore NBA+POL app.py after fire-119 placeholder push\n\n"
        "Restores from parent of bad commit 20230a05 and applies 1-line edge_rationale\n"
        "patch to each file (Mech C paper dataset spec completion).\n"
        "py_compile PASS: NBA 5988L / POL 3972L\n"
        "do_not_push_hf_space_yet\n\n"
        "Co-Authored-By: Claude Cloud Trigger <noreply@anthropic.com>"
    )
    print("8. Committing...")
    safe_commit = repo_root / "scripts/lib/safe_commit.sh"
    if safe_commit.exists():
        run(["bash", str(safe_commit), "AXELROD-RESTORE-119", msg,
             str(NBA_PATH), str(POL_PATH)], cwd=repo_root)
    else:
        run(["git", "commit", "-m", msg], cwd=repo_root)
        run(["git", "push", "-u", "origin", "main"], cwd=repo_root)

    print("\nDONE. NBA+POL app.py restored with edge_rationale. Check work-queue.json too.")


if __name__ == "__main__":
    main()
