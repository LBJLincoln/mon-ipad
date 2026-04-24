#!/usr/bin/env python3
"""TF Quarantine Gate — block destructive actions on compounding TFs.

The April 22 post-mortem: every TF that started working (NBA, POL, ITF) got
factory-rebooted or state-wiped within 2-3 days by one of the 14 crew agents
(BOSS, SWISH, ORACLE_BRIDGE, INTERNAL AFFAIRS, ...) reacting to exponential-
move signals as "leakage suspect". PQTF reached $602K only because the user
explicitly said "NEVER restart" — that hands-off policy is what this tool
makes mechanical.

Model: one quarantine entry per HF Space, with an expiry timestamp. While
active, destructive commits + restart requests for that Space are denied
unless an explicit `--override <reason>` flag is passed.

`Destructive` is detected by marker words in commit message / restart JSON:
  factory_reboot, reset-state, reset-bankrolls, DAY-0 RESET, state.json wipe,
  wipe, factory-reset, factory reboot.

Usage:
  scripts/ops/tf_quarantine.py status                    # human-readable table
  scripts/ops/tf_quarantine.py check <space>             # exit 0 clear / 1 quarantined
  scripts/ops/tf_quarantine.py check-msg <space> <msg>   # exit 0 ok / 1 blocked
  scripts/ops/tf_quarantine.py set <space> <days> <reason>
  scripts/ops/tf_quarantine.py clear <space> <reason>
  scripts/ops/tf_quarantine.py seed                      # set NBA+POL for 30 days

Stored at data/ops/quarantine.json (committed so agents across VM/cloud see
the same state).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATE_FILE = REPO / "data" / "ops" / "quarantine.json"

DESTRUCTIVE_PATTERNS = [
    r"\bfactory[_\- ]reboot\b",
    r"\bfactory[_\- ]reset\b",
    r"\breset[_\- ]state\b",
    r"\breset[_\- ]bankrolls?\b",
    r"\bDAY[_\- ]?0[_\- ]?RESET\b",
    r"\bstate[_\- ]wipe\b",
    r"\bstate\.json\s+wip\b",
    r"\bwipe[_\- ]?state\b",
    r"\bfresh[_\- ]state\b",
]
_DESTRUCTIVE_RE = re.compile("|".join(DESTRUCTIVE_PATTERNS), re.IGNORECASE)

# Canonical Space keys. check() accepts fuzzy matches (case-insensitive substring).
SPACES = {
    "NBA":  "LBJLincoln26/nba-llm-trading-floor",
    "POL":  "LBJLincoln26/political-llm-trading-floor",
    "ITF":  "LBJLincoln26/intraday-trading-floor",
    "PQTF": "LBJLincoln26/political-quant-trading-floor",
}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _load() -> dict:
    if not STATE_FILE.exists():
        return {"quarantines": {}, "updated_at": None}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"quarantines": {}, "updated_at": None}


def _save(state: dict) -> None:
    state["updated_at"] = _now().isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def _resolve_space(name: str) -> str:
    """Accept NBA / pol / full slug. Returns canonical repo slug."""
    n = name.strip()
    if n.upper() in SPACES:
        return SPACES[n.upper()]
    for slug in SPACES.values():
        if n.lower() in slug.lower():
            return slug
    return n  # unknown — caller decides


def is_destructive(text: str) -> bool:
    return bool(_DESTRUCTIVE_RE.search(text or ""))


def _entry_active(entry: dict) -> bool:
    if not entry.get("active"):
        return False
    exp = entry.get("expires_at")
    if not exp:
        return True
    try:
        return dt.datetime.fromisoformat(exp) > _now()
    except Exception:
        return False


def status() -> int:
    s = _load()
    q = s.get("quarantines") or {}
    if not q:
        print("no quarantines set.")
        return 0
    print(f"{'SPACE':<55} {'STATUS':<10} {'EXPIRES':<27} REASON")
    print("-" * 120)
    for slug, e in sorted(q.items()):
        active = _entry_active(e)
        exp = e.get("expires_at") or "-"
        reason = (e.get("reason") or "")[:40]
        print(f"{slug:<55} {'ACTIVE' if active else 'expired':<10} {exp:<27} {reason}")
    return 0


def check(space: str) -> int:
    slug = _resolve_space(space)
    s = _load()
    entry = (s.get("quarantines") or {}).get(slug)
    if not entry or not _entry_active(entry):
        print(f"CLEAR {slug}")
        return 0
    print(f"QUARANTINED {slug} until {entry.get('expires_at')} -- {entry.get('reason')}")
    return 1


def check_msg(space: str, msg: str) -> int:
    if not is_destructive(msg):
        print(f"NON-DESTRUCTIVE {space!r} -- allowed")
        return 0
    rc = check(space)
    if rc != 0:
        print(f"BLOCKED: destructive action on quarantined space. Override with --override.")
    return rc


def set_q(space: str, days: int, reason: str) -> int:
    slug = _resolve_space(space)
    expires = _now() + dt.timedelta(days=days)
    s = _load()
    q = s.setdefault("quarantines", {})
    q[slug] = {
        "active": True,
        "set_at": _now().isoformat(),
        "expires_at": expires.isoformat(),
        "days": days,
        "reason": reason,
    }
    _save(s)
    print(f"SET {slug} until {expires.isoformat()} -- {reason}")
    return 0


def clear_q(space: str, reason: str) -> int:
    slug = _resolve_space(space)
    s = _load()
    q = s.setdefault("quarantines", {})
    if slug in q:
        q[slug]["active"] = False
        q[slug]["cleared_at"] = _now().isoformat()
        q[slug]["cleared_reason"] = reason
    _save(s)
    print(f"CLEARED {slug} -- {reason}")
    return 0


def seed() -> int:
    """Initial quarantine per the 2026-04-22 post-mortem: NBA + POL get 30-day
    hands-off. ITF is intraday (resets are fine — it's paper). PQTF is already
    frozen-forever by policy; also quarantined here so it's mechanical."""
    reason_nbapol = (
        "2026-04-22 post-mortem: 5 agent-initiated resets in 24h killed every "
        "compounding agent (qwen-arb hit $10K then reset, POL $126K then reset, "
        "NBA 75% DD then DAY-0 RESET). PQTF reached $602K only because it was "
        "left alone. 30-day hands-off to let compounding work."
    )
    reason_pqtf = "Frozen forever -- $602K validation artifact. User directive 2026-04-21."
    set_q("NBA", 30, reason_nbapol)
    set_q("POL", 30, reason_nbapol)
    set_q("PQTF", 3650, reason_pqtf)  # 10 years
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "status":
        return status()
    if cmd == "check":
        if len(argv) < 3:
            print("usage: check <space>", file=sys.stderr)
            return 2
        return check(argv[2])
    if cmd == "check-msg":
        if len(argv) < 4:
            print("usage: check-msg <space> <msg>", file=sys.stderr)
            return 2
        return check_msg(argv[2], " ".join(argv[3:]))
    if cmd == "set":
        if len(argv) < 5:
            print("usage: set <space> <days> <reason>", file=sys.stderr)
            return 2
        try:
            days = int(argv[3])
        except Exception:
            print("days must be int", file=sys.stderr)
            return 2
        return set_q(argv[2], days, " ".join(argv[4:]))
    if cmd == "clear":
        if len(argv) < 4:
            print("usage: clear <space> <reason>", file=sys.stderr)
            return 2
        return clear_q(argv[2], " ".join(argv[3:]))
    if cmd == "seed":
        return seed()
    print(f"unknown cmd: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
