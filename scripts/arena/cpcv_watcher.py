#!/usr/bin/env python3
"""
cpcv_watcher.py — Continuous CPCV gate monitor + Telegram alerts (PLAN.md W5)

Polls data/arena/cpcv-gated-strategies.json (NBA) and
data/arena/political-cpcv-gated-strategies.json (Political) on a schedule,
diffs against a locally-stored snapshot, and posts a Telegram alert on
ANY of the following transitions:

  1. Pool grew         (n_runs_analyzed increased)
  2. New passer        (strategy id moved into `passed` since last run)
  3. Regressed passer  (strategy id moved out of `passed` since last run)
  4. Top strategy changed by DSR

Deliberate non-goals:
  - No external deps (urllib only) — runs from cron on the 1vCPU VM
  - No daemon loop — called by cron every 30 min, uses a state file
  - No retries / backoff — if Telegram is down we log and continue

State file:  data/arena/cpcv-watcher-state.json
  Stores the last-seen snapshot per repo so diffs survive restarts.

Env vars:
  TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID  (both required for alerts;
  if either is missing the watcher still diffs and writes state but
  prints instead of posting)

Usage:
  python3 scripts/arena/cpcv_watcher.py              # once, both pools
  python3 scripts/arena/cpcv_watcher.py --dry-run    # diff, no state write, no alert
  python3 scripts/arena/cpcv_watcher.py --only nba   # only NBA pool
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NBA_GATE = ROOT / "data" / "arena" / "cpcv-gated-strategies.json"
POL_GATE = ROOT / "data" / "arena" / "political-cpcv-gated-strategies.json"
STATE_FILE = ROOT / "data" / "arena" / "cpcv-watcher-state.json"
LOG_FILE = ROOT / "logs" / "arena" / "cpcv-watcher.log"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}\n"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(line)
    print(line, end="")


def load_json(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:
        log(f"[cpcv_watcher] failed to load {p}: {e}")
        return None


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def snapshot(gate: dict) -> dict:
    """Reduce a gate JSON to the fields we care about for diffing."""
    if not gate:
        return {}
    passed_ids = sorted((gate.get("passed") or {}).keys())
    rejected_top = gate.get("rejected_top10_by_dsr") or {}
    # "Top strategy by DSR" — prefer passed; fall back to best-DSR rejected
    top_id = None
    top_dsr = None
    if passed_ids:
        top_id = max(
            passed_ids,
            key=lambda k: (gate["passed"][k].get("dsr") or float("-inf")),
        )
        top_dsr = round(gate["passed"][top_id].get("dsr") or 0.0, 4)
    elif rejected_top:
        top_id = max(
            rejected_top.keys(),
            key=lambda k: (rejected_top[k].get("dsr") or float("-inf")),
        )
        top_dsr = round(rejected_top[top_id].get("dsr") or 0.0, 4)
    return {
        "timestamp": gate.get("timestamp"),
        "n_runs_analyzed": gate.get("n_runs_analyzed", 0),
        "n_strategies_evaluated": gate.get("n_strategies_evaluated", 0),
        "n_passed": gate.get("n_passed", 0),
        "n_rejected": gate.get("n_rejected", 0),
        "passed_ids": passed_ids,
        "top_id": top_id,
        "top_dsr": top_dsr,
    }


def diff_snapshots(prev: dict, curr: dict, label: str) -> list[str]:
    """Return a list of human-readable change lines. Empty list = no change."""
    changes: list[str] = []
    if not prev:
        return changes  # First run: nothing to diff against
    if curr.get("n_runs_analyzed", 0) > prev.get("n_runs_analyzed", 0):
        changes.append(
            f"[{label}] pool grew: {prev.get('n_runs_analyzed', 0)} -> "
            f"{curr['n_runs_analyzed']} runs "
            f"({curr.get('n_strategies_evaluated', 0)} strategies)"
        )
    prev_passed = set(prev.get("passed_ids") or [])
    curr_passed = set(curr.get("passed_ids") or [])
    new_passers = sorted(curr_passed - prev_passed)
    regressed = sorted(prev_passed - curr_passed)
    for sid in new_passers:
        changes.append(f"[{label}] NEW passer: {sid} (CPCV gate cleared)")
    for sid in regressed:
        changes.append(f"[{label}] REGRESSED: {sid} (was passing, no longer)")
    if prev.get("top_id") != curr.get("top_id") and curr.get("top_id"):
        changes.append(
            f"[{label}] top-by-DSR changed: "
            f"{prev.get('top_id', 'none')} -> {curr['top_id']} "
            f"(DSR={curr.get('top_dsr', 'n/a')})"
        )
    return changes


def format_telegram(all_changes: list[str], snapshots: dict) -> str:
    lines = ["<b>CPCV gate update</b>", ""]
    for label, s in snapshots.items():
        lines.append(
            f"<b>{label}</b>: {s.get('n_passed', 0)}/{s.get('n_strategies_evaluated', 0)} "
            f"passing, pool={s.get('n_runs_analyzed', 0)} runs"
        )
    lines.append("")
    lines.append("<b>Changes since last check:</b>")
    lines.extend(f"- {c}" for c in all_changes)
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if not token or not chat_id:
        log("[cpcv_watcher] TELEGRAM_BOT_TOKEN or ADMIN_TELEGRAM_ID missing — printing alert instead:")
        log(text)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
            if resp.status != 200:
                log(f"[cpcv_watcher] telegram status={resp.status}")
                return False
        log(f"[cpcv_watcher] telegram alert sent ({len(text)} chars)")
        return True
    except Exception as e:
        log(f"[cpcv_watcher] telegram send failed: {e}")
        return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Diff but do not write state or send alerts")
    p.add_argument("--only", choices=["nba", "political"], default=None,
                   help="Watch only one pool")
    args = p.parse_args()

    prev_state = load_state()
    curr_state: dict = {}
    snapshots: dict = {}
    all_changes: list[str] = []

    pools = []
    if args.only != "political":
        pools.append(("NBA", NBA_GATE))
    if args.only != "nba":
        pools.append(("Political", POL_GATE))

    for label, gate_path in pools:
        gate = load_json(gate_path)
        if gate is None:
            log(f"[cpcv_watcher] {label}: gate file missing ({gate_path.name}) — skip")
            continue
        curr = snapshot(gate)
        snapshots[label] = curr
        prev = prev_state.get(label, {})
        changes = diff_snapshots(prev, curr, label)
        curr_state[label] = curr
        if changes:
            all_changes.extend(changes)
            log(f"[cpcv_watcher] {label}: {len(changes)} change(s)")
            for c in changes:
                log(f"  - {c}")
        else:
            log(f"[cpcv_watcher] {label}: no changes "
                f"(pool={curr['n_runs_analyzed']}, passing={curr['n_passed']})")

    if all_changes:
        msg = format_telegram(all_changes, snapshots)
        if not args.dry_run:
            send_telegram(msg)
        else:
            log("[cpcv_watcher] DRY-RUN — would send telegram:")
            log(msg)

    if not args.dry_run:
        # Preserve state for pools we didn't watch this run
        merged = dict(prev_state)
        merged.update(curr_state)
        merged["_last_run"] = datetime.now(timezone.utc).isoformat()
        save_state(merged)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
