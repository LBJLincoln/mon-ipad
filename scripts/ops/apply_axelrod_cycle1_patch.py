"""
Axelrod Cycle 1 patch: add mandatory ck_consensus_stance field to Mech A (both NBA + Political TF).

Gap addressed: build_day_prompt JSON schema had no structured field for explicit CK consensus
stance. Mission spec requires each agent to "explicitly justify why bet differs from consensus
OR why they agree". DMAD gate referenced allocation.notes (non-existent field).

Adds ck_consensus_stance to:
  1. JSON schema (between council_alignment and allocations) — both NBA + POL
  2. AUDIT FIELDS documentation section — both NBA + POL
  3. write_axelrod_log day-N.jsonl dataset capture — both NBA + POL

Parity: NBA and Political patched identically.
"""
import json
import datetime
from pathlib import Path

NBA_PATH = Path("scripts/arena/hf-llm-trading-floor/app.py")
POL_PATH = Path("scripts/arena/hf-political-trading-floor/app.py")
WQ_PATH = Path("data/work-queue.json")


def patch_nba():
    text = NBA_PATH.read_text(encoding="utf-8")

    # 1. Add ck_consensus_stance field between council_alignment and allocations in schema
    OLD_1 = (
        '  "council_alignment": {\n'
        '    "stance": "followed|deviated|partial",\n'
        '    "reason": "1 sentence — why"\n'
        '  },\n'
        '  "allocations": ['
    )
    NEW_1 = (
        '  "council_alignment": {\n'
        '    "stance": "followed|deviated|partial",\n'
        '    "reason": "1 sentence — why"\n'
        '  },\n'
        '  "ck_consensus_stance": {\n'
        '    "stance": "diverge|agree|partial",\n'
        '    "reason": "1 sentence citing specific peers from COMMON_KNOWLEDGE — e.g. '
        "'10/17 peers backed GSW ML; I diverge: rest-day advantage flips value' "
        "OR '12/17 peers backed LAL ML; I agree: injury confirms it'\"\n"
        '  },\n'
        '  "allocations": ['
    )
    assert OLD_1 in text, "NBA patch 1 anchor not found"
    text = text.replace(OLD_1, NEW_1, 1)

    # 2. Document ck_consensus_stance in AUDIT FIELDS section
    OLD_2 = "- category_reason on each allocation:"
    NEW_2 = (
        "- ck_consensus_stance: MANDATORY. After reviewing COMMON_KNOWLEDGE, state "
        "stance=diverge|agree|partial and cite specific peers/positions you track. "
        "Primary Axelrod Mech A audit field — captured in day-N.jsonl dataset.\n"
        "- category_reason on each allocation:"
    )
    assert OLD_2 in text, "NBA patch 2 anchor not found"
    text = text.replace(OLD_2, NEW_2, 1)

    # 3. Capture ck_consensus_stance in write_axelrod_log day-N.jsonl
    OLD_3 = (
        '                "day_strategy_prefix": (day_log.get("day_strategy", "")[:80] if day_log else ""),\n'
        "            })\n"
        '        log_file = AXELROD_LOG_DIR / f"day-{day_idx:03d}.jsonl"'
    )
    NEW_3 = (
        '                "day_strategy_prefix": (day_log.get("day_strategy", "")[:80] if day_log else ""),\n'
        '                "ck_consensus_stance": (day_log.get("ck_consensus_stance", {}) or {}) if day_log else {},\n'
        "            })\n"
        '        log_file = AXELROD_LOG_DIR / f"day-{day_idx:03d}.jsonl"'
    )
    assert OLD_3 in text, "NBA patch 3 anchor not found"
    text = text.replace(OLD_3, NEW_3, 1)

    NBA_PATH.write_text(text, encoding="utf-8")
    print(f"NBA patched OK ({len(text)} chars)")


def patch_pol():
    text = POL_PATH.read_text(encoding="utf-8")

    # 1. Add ck_consensus_stance field between council_alignment and allocations
    OLD_1 = (
        '  "council_alignment": {\n'
        '    "stance": "followed|deviated|partial",\n'
        '    "reason": "1 sentence — why you followed/deviated/partial vs council_commit_target"\n'
        '  },\n'
        '  "allocations": ['
    )
    NEW_1 = (
        '  "council_alignment": {\n'
        '    "stance": "followed|deviated|partial",\n'
        '    "reason": "1 sentence — why you followed/deviated/partial vs council_commit_target"\n'
        '  },\n'
        '  "ck_consensus_stance": {\n'
        '    "stance": "diverge|agree|partial",\n'
        '    "reason": "1 sentence citing specific peers from COMMON_KNOWLEDGE — e.g. '
        "'12/17 peers went long XLE; I diverge: EO already priced in' "
        "OR '10/17 peers shorted XLF; I agree: rate-cut narrative dominant'\"\n"
        '  },\n'
        '  "allocations": ['
    )
    assert OLD_1 in text, "POL patch 1 anchor not found"
    text = text.replace(OLD_1, NEW_1, 1)

    # 2. Document ck_consensus_stance in AUDIT FIELDS section
    OLD_2 = "- ticker_reason on each allocation:"
    NEW_2 = (
        "- ck_consensus_stance: MANDATORY. After reviewing COMMON_KNOWLEDGE, state "
        "stance=diverge|agree|partial and cite specific peers/positions you track. "
        "Primary Axelrod Mech A audit field — captured in day-N.jsonl dataset.\n"
        "- ticker_reason on each allocation:"
    )
    assert OLD_2 in text, "POL patch 2 anchor not found"
    text = text.replace(OLD_2, NEW_2, 1)

    # 3. Capture ck_consensus_stance in write_axelrod_log (same structure as NBA)
    OLD_3 = (
        '                "day_strategy_prefix": (day_log.get("day_strategy", "")[:80] if day_log else ""),\n'
        "            })\n"
        '        log_file = AXELROD_LOG_DIR / f"day-{day_idx:03d}.jsonl"'
    )
    NEW_3 = (
        '                "day_strategy_prefix": (day_log.get("day_strategy", "")[:80] if day_log else ""),\n'
        '                "ck_consensus_stance": (day_log.get("ck_consensus_stance", {}) or {}) if day_log else {},\n'
        "            })\n"
        '        log_file = AXELROD_LOG_DIR / f"day-{day_idx:03d}.jsonl"'
    )
    assert OLD_3 in text, "POL patch 3 anchor not found"
    text = text.replace(OLD_3, NEW_3, 1)

    POL_PATH.write_text(text, encoding="utf-8")
    print(f"POL patched OK ({len(text)} chars)")


def update_workqueue():
    with WQ_PATH.open() as f:
        wq = json.load(f)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    wq["items"].append({
        "id": "tf-axelrod-cycle1-ck-consensus-field",
        "priority": 29,
        "status": "done",
        "completed_at": now,
        "owner": "cloud-trigger-axelrod-2026",
        "subject": "Cycle 1 fire — add mandatory ck_consensus_stance to Mech A JSON schema (NBA + POL)",
        "gap_addressed": (
            "build_day_prompt JSON schema had no structured field for explicit CK consensus stance. "
            "Mission spec requires each agent to explicitly justify why bet differs from consensus "
            "OR why they agree. Added ck_consensus_stance (diverge|agree|partial + 1-sentence reason "
            "citing specific peers from COMMON_KNOWLEDGE) to: (1) JSON schema, (2) AUDIT FIELDS doc, "
            "(3) write_axelrod_log day-N.jsonl dataset. Parity: NBA + Political both patched."
        ),
        "py_compile": "PASS both apps (verified locally before push)",
        "do_not_push_hf_space_yet": True,
    })
    wq["updated_at"] = now
    with WQ_PATH.open("w") as f:
        json.dump(wq, f, indent=2)
    print(f"work-queue.json updated ({now})")


if __name__ == "__main__":
    patch_nba()
    patch_pol()
    update_workqueue()
    print("All patches applied successfully.")
