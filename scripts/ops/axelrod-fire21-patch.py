#!/usr/bin/env python3
"""axelrod-fire21-patch.py — verify+tune fire 21 patch.

Mech A spec gap (point 4): agents must 'explicitly justify why their bet differs
from the consensus OR why they agree with it'. Previous code said CONSENSUS AGREE
FORBIDDEN — which blocks agents from ever agreeing, breaking spec parity.
Fix: add CONSENSUS_AGREE_JUSTIFIED as a third DMAD option requiring explicit
distinct structural reason. Preserves anti-lockstep doctrine (Lockstep without
justification still triggers Mech B rotation). Both NBA + Political at parity.
"""

from pathlib import Path
import py_compile, sys, json, datetime

NBA_PATH = Path("scripts/arena/hf-llm-trading-floor/app.py")
POL_PATH = Path("scripts/arena/hf-political-trading-floor/app.py")

NBA_OLD = (
    '        "CONSENSUS AGREE is FORBIDDEN — if your template converges with a peer, pick the\\n"\n'
    '        "second-best candidate from your template instead.\\n"\n'
)
NBA_NEW = (
    '        "CONSENSUS_AGREE_JUSTIFIED [peer_name] (reason=<specific_structural_reason>): ALLOWED\\n"\n'
    '        "    only if you cite a DIFFERENT structural basis (e.g. injury not in oracle, rest\\n"\n'
    '        "    advantage, a distinct template signal). Blind consensus → flagged lockstep\\n"\n'
    '        "    in post-mortem. Lockstep (≥10/17 same pick, no CONSENSUS_AGREE_JUSTIFIED)\\n"\n'
    '        "    → Mech B archetype rotation for bottom 3 next day.\\n"\n'
)

POL_OLD = (
    '        "CONSENSUS AGREE is FORBIDDEN — if your template converges with a peer, you must\\n"\n'
    '        "explicitly pick the second-best sector from your template instead.\\n"\n'
)
POL_NEW = (
    '        "CONSENSUS_AGREE_JUSTIFIED [peer_name] (reason=<specific_structural_reason>): ALLOWED\\n"\n'
    '        "    only if you cite a DIFFERENT structural basis (political signal, agency,\\n"\n'
    '        "    sector-beta divergence). Blind consensus → flagged lockstep in post-mortem.\\n"\n'
    '        "    Lockstep (≥10/17 same pick, no CONSENSUS_AGREE_JUSTIFIED)\\n"\n'
    '        "    → Mech B archetype rotation for bottom 3 next day.\\n"\n'
)


def apply_patch(path: Path, old: str, new: str, label: str) -> None:
    content = path.read_text(encoding="utf-8")
    if old not in content:
        raise ValueError(f"{label}: target string not found in {path}")
    patched = content.replace(old, new, 1)
    path.write_text(patched, encoding="utf-8")
    print(f"[{label}] patch applied OK")


def verify_compile(path: Path, label: str) -> None:
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"[{label}] py_compile PASS")
    except py_compile.PyCompileError as e:
        print(f"[{label}] py_compile FAIL: {e}")
        sys.exit(1)


def update_work_queue() -> None:
    wq_path = Path("data/work-queue.json")
    with open(wq_path) as f:
        wq = json.load(f)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wq["updated_at"] = now
    wq["items"].append({
        "id": "tf-axelrod-verify-tune-21",
        "priority": 30,
        "status": "done",
        "completed_at": now,
        "owner": "cloud-trigger-axelrod-2026",
        "subject": "verify+tune fire 21 — CONSENSUS_AGREE_JUSTIFIED gate (Mech A spec gap, NBA+POL)",
        "gap_found": (
            "Mech A spec point 4: 'justify why bet differs OR why they agree with consensus'. "
            "Code had CONSENSUS AGREE FORBIDDEN. Added CONSENSUS_AGREE_JUSTIFIED [peer] "
            "(reason=<structural>) as third DMAD option. Blind consensus still flags lockstep "
            "and triggers Mech B rotation. Both NBA + POL at parity."
        ),
        "py_compile": "PASS both apps",
        "do_not_push_hf_space_yet": True
    })
    with open(wq_path, "w") as f:
        json.dump(wq, f, indent=2)
    print("[work-queue] updated with fire-21 entry")


if __name__ == "__main__":
    apply_patch(NBA_PATH, NBA_OLD, NBA_NEW, "NBA")
    apply_patch(POL_PATH, POL_OLD, POL_NEW, "POL")
    verify_compile(NBA_PATH, "NBA")
    verify_compile(POL_PATH, "POL")
    update_work_queue()
    print("All done. Commit: NBA app.py + POL app.py + data/work-queue.json")
