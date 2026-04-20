#!/usr/bin/env python3
"""TF intel dispatcher — reads tf_intel_monitor alerts and convokes specialist agents.

Runs at a slower cadence than the monitor (every 15 min via cron) so the monitor
has time to accumulate evidence across multiple cycles before we wake an agent.

Dispatch policy (severity → agent → cooldown):
    S5 broker_401           → LAUNCHPAD     (fix Alpaca secrets)      cd=30min
    S5 gateway_down         → SWITCHBOARD   (LLM gateway keepalive)   cd=20min
    S4 fleet_decay          → DR_FRANKENSTEIN (engine deep-fix)       cd=60min
    S4 pol category_collapse → LOBBYIST      (POL island + prompts)   cd=45min
    S4 nba concentration    → SWISH         (NBA island health)       cd=45min
    S3 lockstep             → INTERNAL_AFFAIRS (scientific audit)     cd=60min
    S3 pqtf_no_multileg     → DR_FRANKENSTEIN                         cd=60min
    S3 itf_no_crypto        → THE_TICKER                              cd=45min
    S2 agent_silent         → THE_PLUMBER   (pipeline diagnosis)      cd=30min

For each dispatch we:
    1. write a task brief to data/ops/dispatch-briefs/<ts>-<agent>.md
    2. record to data/ops/dispatch-log.jsonl with status=queued
    3. invoke the agent via `claude` CLI in background (claude -p <brief>)
    4. on completion, cron tick appends status=done

Cooldown prevents flooding: we check dispatch-log.jsonl for that agent-code pair
within its cooldown window and skip if still hot.

The dispatcher is safe to run idempotently — it only fires when new evidence
exceeds cooldown, and every invocation has a signed ID.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "data" / "ops"
BRIEFS_DIR = OPS / "dispatch-briefs"
BRIEFS_DIR.mkdir(parents=True, exist_ok=True)

ALERTS_PATH = OPS / "tf-intel-latest.json"
LOG_PATH = OPS / "dispatch-log.jsonl"

# (severity_min, code_match, agent_id, cooldown_minutes, claude_subagent)
# claude_subagent None → invoke via `claude -p` (root agent); otherwise use Agent tool inside prompt
DISPATCH_RULES = [
    (5, "broker_401",         "LAUNCHPAD",        30,  "launchpad"),
    (5, "gateway_down",       "SWITCHBOARD",      20,  "switchboard"),
    (4, "fleet_decay",        "DR_FRANKENSTEIN",  60,  "dr-frankenstein"),
    (4, "fleet_concentration","SWISH",            45,  "swish"),
    (4, "agent_ruined",       "THE_PLUMBER",      30,  "the-plumber"),
    (3, "category_collapse",  "LOBBYIST",         45,  "lobbyist"),
    (3, "lockstep",           "INTERNAL_AFFAIRS", 60,  "internal-affairs"),
    (3, "pqtf_no_multileg",   "DR_FRANKENSTEIN",  60,  "dr-frankenstein"),
    (3, "pqtf_zombie_rows",   "DR_FRANKENSTEIN",  60,  "dr-frankenstein"),
    (3, "itf_no_crypto",      "THE_TICKER",       45,  "the-ticker"),
    (2, "agent_silent",       "SWITCHBOARD",      30,  "switchboard"),
    (2, "itf_agent_silent",   "SWITCHBOARD",      30,  "switchboard"),
]

# how many alerts of the same (agent_id, code) can be queued per dispatcher run
PER_RULE_MAX_PER_RUN = 2


def _load_alerts() -> list[dict[str, Any]]:
    if not ALERTS_PATH.exists():
        return []
    try:
        d = json.loads(ALERTS_PATH.read_text())
        return d.get("alerts", [])
    except Exception:
        return []


def _tail_log(window_min: int = 180) -> list[dict[str, Any]]:
    """Return log lines within window_min minutes."""
    if not LOG_PATH.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_min)
    out = []
    for line in LOG_PATH.read_text().splitlines()[-500:]:
        try:
            rec = json.loads(line)
            ts = datetime.fromisoformat(rec.get("ts", "").replace("Z", "+00:00"))
            if ts >= cutoff:
                out.append(rec)
        except Exception:
            continue
    return out


def _was_dispatched(agent: str, code: str, cooldown_min: int, recent: list[dict]) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_min)
    for rec in recent:
        if rec.get("agent") != agent or rec.get("code") != code:
            continue
        try:
            ts = datetime.fromisoformat(rec.get("ts", "").replace("Z", "+00:00"))
            if ts >= cutoff:
                return True
        except Exception:
            continue
    return False


def _pick_rule(alert: dict[str, Any]) -> tuple[str, int, str] | None:
    sev = int(alert.get("severity", 0))
    code = alert.get("code", "")
    for rule_sev, rule_code, agent, cd, subagent in DISPATCH_RULES:
        if sev >= rule_sev and rule_code == code:
            return (agent, cd, subagent)
    return None


def _write_brief(agent: str, subagent: str, alerts: list[dict], run_id: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = BRIEFS_DIR / f"{ts}-{agent}-{run_id[:8]}.md"
    lines = [
        f"# {agent} dispatch brief",
        f"_generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} | run_id {run_id}_",
        "",
        f"You are **{agent}** ({subagent}). The TF intel monitor detected the following",
        "issues. Investigate and, where you have authority, FIX them using your standard",
        "runbook. Commit via `bash scripts/lib/safe_commit.sh {0} \"...\"`.".format(agent),
        "",
        f"## Alerts routed to you ({len(alerts)})",
        "",
    ]
    for a in alerts:
        lines += [
            f"### S{a['severity']} {a['code']} — {a.get('agent') or 'fleet'}",
            f"**Finding:** {a['finding']}",
            f"**Proposed action:** {a['proposed_action']}",
            f"**Evidence:** `{json.dumps(a.get('evidence') or {}, separators=(',', ':'))}`",
            "",
        ]
    lines += [
        "## Context",
        f"- Monitor: `scripts/ops/tf_intel_monitor.py` (runs every 4 min)",
        f"- Alerts file: `data/ops/tf-intel-latest.json`",
        f"- LLM health: `data/ops/llm-health.json`, deadlist: `data/ops/llm-deadlist.json`",
        "- Git commits MUST use `scripts/lib/safe_commit.sh` (flock mutex)",
        "",
        "## Done-criteria",
        "- At least one of these alerts is resolved OR you have documented why it can't be",
        "- Post-action snapshot written to `data/ops/dispatch-done/{run_id}.json`".format(
            run_id=run_id
        ),
    ]
    path.write_text("\n".join(lines))
    return path


def _invoke_agent(subagent: str, brief_path: Path, run_id: str) -> subprocess.Popen | None:
    """Invoke Claude CLI in background with the subagent brief.

    Uses the Task/Agent mechanism indirectly: we spawn `claude -p` with the brief
    contents and let the main agent route to the correct subagent via the prompt.
    The dispatcher itself never blocks; we log a queued event and return.
    """
    prompt = (
        f"Use the Task tool with subagent_type={subagent} and the brief located at "
        f"{brief_path}. Read the brief, execute the fixes per its Done-criteria, "
        f"and write data/ops/dispatch-done/{run_id}.json with your result."
    )
    claude_bin = os.environ.get("CLAUDE_BIN", "claude")
    try:
        proc = subprocess.Popen(
            [claude_bin, "-p", prompt, "--no-interactive"],
            stdout=(OPS / f"dispatch-{run_id[:8]}.out").open("w"),
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            start_new_session=True,
        )
        return proc
    except FileNotFoundError:
        return None


def run_cycle(dry_run: bool = False) -> dict[str, Any]:
    alerts = _load_alerts()
    if not alerts:
        return {"dispatched": 0, "skipped_cooldown": 0, "no_rule": 0, "alerts_total": 0}

    recent = _tail_log(window_min=180)
    # Bucket alerts by (agent_id, code) to avoid flooding same agent
    buckets: dict[tuple[str, str, str], list[dict]] = {}
    no_rule = 0
    skipped_cd = 0

    for a in alerts:
        picked = _pick_rule(a)
        if not picked:
            no_rule += 1
            continue
        agent, cd, subagent = picked
        if _was_dispatched(agent, a["code"], cd, recent):
            skipped_cd += 1
            continue
        key = (agent, a["code"], subagent)
        buckets.setdefault(key, []).append(a)

    dispatched = 0
    for (agent, code, subagent), bucket in buckets.items():
        bucket = bucket[:PER_RULE_MAX_PER_RUN + 3]  # cap brief size
        run_id = uuid.uuid4().hex
        brief_path = _write_brief(agent, subagent, bucket, run_id)

        log_rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "run_id": run_id,
            "agent": agent,
            "subagent": subagent,
            "code": code,
            "alerts_in_brief": len(bucket),
            "brief": str(brief_path.relative_to(ROOT)),
            "status": "queued",
            "dry_run": dry_run,
        }

        if not dry_run:
            proc = _invoke_agent(subagent, brief_path, run_id)
            log_rec["pid"] = proc.pid if proc else None
            log_rec["status"] = "spawned" if proc else "spawn_failed"

        with LOG_PATH.open("a") as fh:
            fh.write(json.dumps(log_rec) + "\n")
        dispatched += 1

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "alerts_total": len(alerts),
        "dispatched": dispatched,
        "skipped_cooldown": skipped_cd,
        "no_rule": no_rule,
        "dry_run": dry_run,
    }
    (OPS / "dispatch-latest.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    s = run_cycle(dry_run=dry)
    print(json.dumps(s))
