#!/usr/bin/env python3
"""
repair_pol_tf_fire67.py — Fix accidental 4-line stub pushed to Political TF app.py.

fire-67 cloud-trigger accidentally pushed only 4 lines (the GitHub annotation header)
to scripts/arena/hf-political-trading-floor/app.py. This script:
  1. Uses git to restore the file from the pre-accident commit (9167a1c)
  2. Applies the 3 AXELROD-2026 Mech A DMAD parity patches
  3. Runs py_compile to verify
  4. Commits the result with safe_commit.sh

Run from the mon-ipad repo root on the VM:
  python3 scripts/ops/repair_pol_tf_fire67.py
"""
import subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_PATH  = REPO_ROOT / "scripts/arena/hf-political-trading-floor/app.py"
GOOD_SHA  = "9167a1cfa234b2d789bd91242aa98840ba39ab4d"  # pre-accident commit

def run(cmd, **kw):
    kw.setdefault("check", True)
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(cmd, **kw, cwd=REPO_ROOT)

print("Step 1: restore from pre-accident commit...")
run(["git", "checkout", GOOD_SHA, "--", str(APP_PATH)])
content = APP_PATH.read_text()
lines_before = content.count("\n") + 1
print(f"  restored: {lines_before} lines")
assert lines_before > 3800, f"Unexpected line count: {lines_before}"

# Patch 1: day_strategy schema
print("Patch 1: day_strategy schema CONSENSUS_AGREE_JUSTIFIED...")
OLD1 = (
    '  "day_strategy": "MUST start with STRUCTURAL DIVERGE [peer] or STRUCTURAL '
    'COMPLEMENT [peer] citing your REASONING TEMPLATE — then 1-2 sentences on approach",'
)
NEW1 = (
    '  "day_strategy": "MUST start with STRUCTURAL DIVERGE [peer] or STRUCTURAL '
    'COMPLEMENT [peer] citing your REASONING TEMPLATE — then 1-2 sentences on approach. '
    'Or CONSENSUS_AGREE_JUSTIFIED [peer] (reason=<structural_reason>).",'
)
assert OLD1 in content, f"Patch 1 text not found"
content = content.replace(OLD1, NEW1, 1)
print("  APPLIED")

# Patch 2: NEW AUDIT FIELDS day_strategy bullet
print("Patch 2: NEW AUDIT FIELDS day_strategy bullet...")
OLD2 = (
    "NEW AUDIT FIELDS (MANDATORY — councils use these to score decision quality):\n"
    "- council_alignment:"
)
NEW2 = (
    "NEW AUDIT FIELDS (MANDATORY — councils use these to score decision quality):\n"
    "- day_strategy: MUST start with STRUCTURAL DIVERGE/COMPLEMENT/CONSENSUS_AGREE_JUSTIFIED citing\n"
    "  your REASONING TEMPLATE. Required for ANTI-GROUPTHINK enforcement (Axelrod CK gate).\n"
    "- council_alignment:"
)
assert OLD2 in content, f"Patch 2 text not found"
content = content.replace(OLD2, NEW2, 1)
print("  APPLIED")

# Patch 3: LLM timeout env-configurable
print("Patch 3: POL_TF_LLM_TIMEOUT_SEC env var...")
OLD3 = (
    '            try:\n'
    '                raw = _call_llm(provider, system_prompt, user_prompt, timeout=12.0,\n'
    '                               trace_name=f"pol-tf-day-{day_idx}",\n'
    '                               trace_metadata={"trader_id": tid, "day": day_date, "bankroll": ts["bankroll"]})\n'
    '            except Exception:\n'
    '                raw = None\n'
    '            if not raw and cfg.get("fallback_provider"):\n'
    '                try:\n'
    '                    raw = _call_llm(cfg["fallback_provider"], system_prompt, user_prompt, timeout=12.0,\n'
    '                                   trace_name=f"pol-tf-day-{day_idx}-fallback",\n'
    '                                   trace_metadata={"trader_id": tid, "day": day_date, "fallback": True})\n'
    '                except Exception:\n'
    '                    pass'
)
NEW3 = (
    '            _pol_timeout = float(os.environ.get("POL_TF_LLM_TIMEOUT_SEC", "45.0"))\n'
    '            try:\n'
    '                raw = _call_llm(provider, system_prompt, user_prompt, timeout=_pol_timeout,\n'
    '                               trace_name=f"pol-tf-day-{day_idx}",\n'
    '                               trace_metadata={"trader_id": tid, "day": day_date, "bankroll": ts["bankroll"]})\n'
    '            except Exception:\n'
    '                raw = None\n'
    '            if not raw and cfg.get("fallback_provider"):\n'
    '                try:\n'
    '                    raw = _call_llm(cfg["fallback_provider"], system_prompt, user_prompt, timeout=_pol_timeout,\n'
    '                                   trace_name=f"pol-tf-day-{day_idx}-fallback",\n'
    '                                   trace_metadata={"trader_id": tid, "day": day_date, "fallback": True})\n'
    '                except Exception:\n'
    '                    pass'
)
assert OLD3 in content, f"Patch 3 text not found"
content = content.replace(OLD3, NEW3, 1)
print("  APPLIED")

APP_PATH.write_text(content)
lines_after = content.count("\n") + 1
print(f"Wrote: {lines_after} lines (+{lines_after - lines_before} from patches)")

assert "CONSENSUS_AGREE_JUSTIFIED [peer] (reason=<structural_reason>)." in content
assert "day_strategy: MUST start with STRUCTURAL DIVERGE/COMPLEMENT" in content
assert "POL_TF_LLM_TIMEOUT_SEC" in content
print("All 3 patches verified.")

import py_compile
py_compile.compile(str(APP_PATH), doraise=True)
print("py_compile: PASS")

safe = REPO_ROOT / "scripts/lib/safe_commit.sh"
msg = (
    "fix(tf): restore Political TF app.py + Axelrod Mech A DMAD parity (fire-67 repair)\n\n"
    "fire-67 cloud-trigger accidentally truncated app.py to 4 lines.\n"
    "Restores from SHA 9167a1c + applies 3 Mech A DMAD parity patches:\n"
    "  - day_strategy schema: CONSENSUS_AGREE_JUSTIFIED option\n"
    "  - NEW AUDIT FIELDS: day_strategy bullet (Axelrod CK gate)\n"
    "  - LLM timeout: POL_TF_LLM_TIMEOUT_SEC env-configurable (default 45s)\n"
    "do_not_push_hf_space_yet\n\n"
    "Co-Authored-By: Claude Cloud Trigger <noreply@anthropic.com>"
)
if safe.exists():
    r = run([str(safe), "AXELROD-REPAIR", msg, str(APP_PATH)], check=False)
    print("safe_commit exit:", r.returncode)
    if r.returncode != 0:
        print(r.stdout[-300:], r.stderr[-300:])
else:
    run(["git", "add", str(APP_PATH)])
    run(["git", "commit", "-m", msg])
    print("git commit: done")

print("\nRepair complete. Push: git push origin main")
