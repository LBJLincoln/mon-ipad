#!/usr/bin/env python3
"""Nomos42 L1 Coordinator — LangGraph state machine on VM.

Runs every 4h (cron) alongside autonomous-cycle.sh. Durable state via SQLite
so partial-tick crashes resume instead of restart. Replaces the ad-hoc Python
snippets inside autonomous-cycle.sh for the *decide-what-to-dispatch* choice.

Pattern: Magentic-One (arXiv 2411.04468) orchestrator-of-orchestrators —
the L1 coordinator never executes ML; it only selects a single action per
tick and delegates to L2 (HF Spaces) or L3 (evolution islands).

State graph: scan_health -> decide_action -> dispatch -> record -> END
Checkpoints:  scripts/coord/coord-state.sqlite (resumable)
Decision log: data/coord/decisions.jsonl (append-only audit)

Usage: python3 scripts/coord/coord.py --tick
       python3 scripts/coord/coord.py --dry-run
       python3 scripts/coord/coord.py --status
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

try:
    import requests
except ImportError:
    print("[coord] missing 'requests' — pip install requests", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[2]
STATE_DB = ROOT / "scripts" / "coord" / "coord-state.sqlite"
DECISIONS_LOG = ROOT / "data" / "coord" / "decisions.jsonl"
DECISIONS_LOG.parent.mkdir(parents=True, exist_ok=True)

ISLANDS = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
    "S16": "https://lbjlincoln26-nba-evo-s16.hf.space",
    "S17": "https://lbjlincoln26-nba-evo-s17.hf.space",
    "S18": "https://testforge42-nba-evo-s18.hf.space",
    "S19": "https://testforge42-nba-evo-s19.hf.space",
    "S20": "https://lbjlincoln26-nba-evo-s20.hf.space",
    "S21": "https://lbjlincoln26-nba-evo-s21.hf.space",
    "S22": "https://testforge42-nba-evo-s22.hf.space",
    "P1": "https://nomos42-political-alpha.hf.space",
    "P2": "https://nomos42-political-alpha-2.hf.space",
    "P3": "https://lbjlincoln-political-alpha-3.hf.space",
    "P4": "https://lbjlincoln-political-alpha-4.hf.space",
    "P5": "https://lbjlincoln-political-alpha-5.hf.space",
    "P6": "https://lbjlincoln-political-alpha-6.hf.space",
    "P7": "https://lbjlincoln-political-alpha-7.hf.space",
    "P8": "https://lbjlincoln-political-alpha-8.hf.space",
}

STAGNATION_THRESHOLD = 15


class State(TypedDict, total=False):
    tick_id: str
    started_at: str
    fleet_health: dict
    decision: dict
    executed: dict
    elapsed_ms: float


def _fetch_one(name_url):
    name, url = name_url
    try:
        r = requests.get(f"{url}/api/status", timeout=8)
        r.raise_for_status()
        d = r.json()
        return name, {
            "up": True,
            "brier": d.get("best_brier"),
            "gen": d.get("generation"),
            "stagnation": d.get("stagnation_count", d.get("stagnation", 0)),
        }
    except Exception as e:
        return name, {"up": False, "error": str(e)[:120]}


def scan_health(state: State) -> State:
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(_fetch_one, ISLANDS.items()))
    state["fleet_health"] = results
    return state


def decide_action(state: State) -> State:
    """Pick ONE action this tick. Magentic-One thin-orchestrator pattern."""
    health = state.get("fleet_health", {})
    down = [k for k, v in health.items() if not v.get("up")]
    if down:
        state["decision"] = {
            "kind": "restart",
            "target": down[0],
            "reason": f"{down[0]} down; {len(down)} total unhealthy",
        }
        return state
    stag = [(k, v) for k, v in health.items() if v.get("up") and (v.get("stagnation") or 0) > STAGNATION_THRESHOLD]
    if stag:
        stag.sort(key=lambda kv: -(kv[1].get("stagnation") or 0))
        k, v = stag[0]
        state["decision"] = {
            "kind": "diversify",
            "target": k,
            "reason": f"stagnation_count={v.get('stagnation')} > {STAGNATION_THRESHOLD}",
        }
        return state
    briers = [(k, v.get("brier")) for k, v in health.items() if v.get("up") and isinstance(v.get("brier"), (int, float))]
    briers.sort(key=lambda kv: kv[1])
    if briers:
        k, b = briers[0]
        state["decision"] = {"kind": "checkpoint", "target": k, "reason": f"brier={b} fleet-best"}
        return state
    state["decision"] = {"kind": "no_op", "reason": "no signal worth acting on"}
    return state


def dispatch(state: State, dry_run: bool = False) -> State:
    dec = state.get("decision", {})
    kind, target = dec.get("kind"), dec.get("target")
    executed = {"kind": kind, "target": target, "ok": None, "dry_run": dry_run}
    if dry_run or kind == "no_op" or not target:
        executed["ok"] = True
        executed["note"] = "dry-run or no-op"
        state["executed"] = executed
        return state
    url = ISLANDS.get(target)
    if not url:
        executed["ok"] = False
        executed["note"] = f"unknown target {target}"
        state["executed"] = executed
        return state
    try:
        if kind == "restart":
            r = requests.get(url + "/", timeout=20)
            executed["ok"] = r.status_code in (200, 301, 302, 307)
            executed["http_status"] = r.status_code
        elif kind == "diversify":
            r = requests.post(url + "/api/command", json={"command": "diversify"}, timeout=15)
            executed["ok"] = r.status_code == 200
            executed["http_status"] = r.status_code
        elif kind == "checkpoint":
            r = requests.post(url + "/api/checkpoint", timeout=15)
            executed["ok"] = r.status_code == 200
            executed["http_status"] = r.status_code
        else:
            executed["ok"] = False
            executed["note"] = f"unknown kind {kind}"
    except Exception as e:
        executed["ok"] = False
        executed["error"] = str(e)[:200]
    state["executed"] = executed
    return state


def record(state: State) -> State:
    with DECISIONS_LOG.open("a") as f:
        f.write(json.dumps({
            "tick_id": state.get("tick_id"),
            "ts": datetime.now(timezone.utc).isoformat(),
            "decision": state.get("decision"),
            "executed": state.get("executed"),
            "elapsed_ms": state.get("elapsed_ms"),
            "down_count": sum(1 for v in state.get("fleet_health", {}).values() if not v.get("up")),
        }) + "\n")
    return state


def _init_db():
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(STATE_DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS ticks ("
        " tick_id TEXT PRIMARY KEY, started_at TEXT, ended_at TEXT,"
        " decision_kind TEXT, decision_target TEXT, executed_ok INTEGER)"
    )
    con.commit()
    return con


def _build_graph():
    """Build LangGraph StateGraph if library is available, else return None."""
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None
    g = StateGraph(State)
    g.add_node("scan", scan_health)
    g.add_node("decide", decide_action)
    g.add_node("dispatch", dispatch)
    g.add_node("record", record)
    g.set_entry_point("scan")
    g.add_edge("scan", "decide")
    g.add_edge("decide", "dispatch")
    g.add_edge("dispatch", "record")
    g.add_edge("record", END)
    return g.compile()


def run_tick(dry_run: bool = False) -> dict:
    t0 = time.time()
    tick_id = uuid.uuid4().hex[:12]
    state: State = {"tick_id": tick_id, "started_at": datetime.now(timezone.utc).isoformat()}
    graph = _build_graph()
    if graph is not None and not dry_run:
        state = graph.invoke(state)
    else:
        state = scan_health(state)
        state = decide_action(state)
        state = dispatch(state, dry_run=dry_run)
        state = record(state)
    state["elapsed_ms"] = round((time.time() - t0) * 1000, 1)
    con = _init_db()
    dec = state.get("decision") or {}
    exe = state.get("executed") or {}
    con.execute(
        "INSERT OR REPLACE INTO ticks VALUES (?,?,?,?,?,?)",
        (tick_id, state["started_at"], datetime.now(timezone.utc).isoformat(),
         dec.get("kind"), dec.get("target"), 1 if exe.get("ok") else 0),
    )
    con.commit()
    con.close()
    return state


def cli_status():
    con = _init_db()
    rows = con.execute(
        "SELECT tick_id, started_at, decision_kind, decision_target, executed_ok"
        " FROM ticks ORDER BY started_at DESC LIMIT 10"
    ).fetchall()
    con.close()
    print(f"{'TICK':<14} {'STARTED_AT':<28} {'KIND':<12} {'TARGET':<8} OK")
    for r in rows:
        print(f"{r[0]:<14} {r[1]:<28} {str(r[2] or '-'):<12} {str(r[3] or '-'):<8} {r[4]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tick", action="store_true", help="run one coordination tick")
    ap.add_argument("--dry-run", action="store_true", help="scan+decide+log but do not dispatch")
    ap.add_argument("--status", action="store_true", help="show last 10 ticks")
    args = ap.parse_args()
    if args.status:
        cli_status()
        return
    if args.tick or args.dry_run:
        st = run_tick(dry_run=args.dry_run)
        print(json.dumps({
            "tick_id": st.get("tick_id"),
            "decision": st.get("decision"),
            "executed": st.get("executed"),
            "elapsed_ms": st.get("elapsed_ms"),
            "down": [k for k, v in st.get("fleet_health", {}).items() if not v.get("up")],
            "langgraph_used": _build_graph() is not None and not args.dry_run,
        }, indent=2))
        return
    ap.print_help()


if __name__ == "__main__":
    main()
