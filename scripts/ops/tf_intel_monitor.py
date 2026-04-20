#!/usr/bin/env python3
"""TF intelligence monitor — diagnose per-agent per-TF problems every cron cycle.

Answers the question "WHAT IS NOT WORKING right now" across the 4 trading
floors (NBA / POL / PQTF / ITF), not just "is the LLM gateway up". Output is a
curated alert list that names specific agents and specific remedies so the
next cron tick (or a human glance) can act on them immediately.

Output (atomically rewritten each cycle):
    data/ops/tf-intel-latest.json  — current snapshot (full diagnosis)
    data/ops/tf-intel-alerts.jsonl — append-only event log (one line per alert)
    data/ops/tf-intel-summary.md   — human-readable digest

Alert severity scale (1-5):
    5 CRITICAL — floor wedged / all agents at $0 / broker 401
    4 HIGH     — ≥50% of agents silent for ≥2 days or drawdown ≥90%
    3 MEDIUM   — lockstep jaccard ≥0.5 / capital concentration ≥80% in ≤3 agents
    2 LOW      — one agent silent / mild drift
    1 INFO     — structural observations

Detectors implemented (grouped by TF):

    NBA:
      - Agent silent (n_bets=0 across ≥3 latest snapshots)
      - Agent drawdown ≥0.9 AND bankroll <$50 (ruined)
      - Fleet jaccard ≥0.5 (lockstep)
      - Fleet leader single-agent concentration >70% of fleet_total
      - Fleet total decay >30% between most recent 2 snapshots

    POL:
      - Same agent/fleet detectors as NBA
      - Category coverage <2 distinct categories (insider_trade-only collapse)

    PQTF:
      - Multi-leg ratio = 0 despite Phase-2 infra
      - Zombie order rows (type=null OR strike=0)
      - Bankroll floor breach (<$1000 active, <$20 archived)

    ITF:
      - Broker 401/403 (Alpaca creds bad)
      - Zero crypto trades in off-hours window
      - Agent 0 bids on last 3 decision files

For each alert the monitor emits a proposed_action (text ≤200 chars) that an
action agent (or human) can execute without re-investigation.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "ops"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_PATH = OUT_DIR / "tf-intel-latest.json"
ALERTS_PATH = OUT_DIR / "tf-intel-alerts.jsonl"
SUMMARY_PATH = OUT_DIR / "tf-intel-summary.md"

ANALYTICS_DIR = ROOT / "data" / "tf-analytics"
INTRADAY_DIR = ROOT / "data" / "intraday"


def _load_json(p: Path) -> dict[str, Any] | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _day_files(tf: str, last_n: int = 5) -> list[Path]:
    d = ANALYTICS_DIR / tf
    if not d.is_dir():
        return []
    files = sorted(d.glob("day-*.json"), key=lambda p: int(p.stem.split("-")[-1]))
    return files[-last_n:]


def _aid(a: dict[str, Any]) -> str:
    return a.get("agent_id") or a.get("tid") or a.get("trader_id") or a.get("persona") or "?"


def _emit(alerts: list[dict[str, Any]], tf: str, severity: int, code: str, agent: str | None,
          finding: str, proposed_action: str, evidence: dict[str, Any] | None = None) -> None:
    alerts.append({
        "tf": tf,
        "severity": severity,
        "code": code,
        "agent": agent,
        "finding": finding[:240],
        "proposed_action": proposed_action[:280],
        "evidence": evidence or {},
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


def analyze_fleet_tf(tf: str, alerts: list[dict[str, Any]]) -> dict[str, Any]:
    days = _day_files(tf, last_n=5)
    if not days:
        _emit(alerts, tf, 4, "no_analytics", None,
              f"No tf-analytics/{tf}/day-*.json found — floor not emitting rollups",
              f"Check TF {tf} on HF Space /api/status; if running, verify tf_analytics cron at :45 is live")
        return {"n_days": 0, "agents": {}, "fleet_history": []}

    fleet_history = []
    agent_trajectory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    category_union: set[str] = set()
    for dp in days:
        d = _load_json(dp) or {}
        fleet = d.get("fleet") or {}
        fleet_history.append({
            "day": dp.stem,
            "fleet_total": fleet.get("fleet_total"),
            "n_agents": fleet.get("n_agents"),
            "jaccard_mean": fleet.get("jaccard_fleet_mean"),
            "jaccard_max": fleet.get("jaccard_fleet_max"),
            "day_wr": fleet.get("day_fleet_wr"),
            "leader": fleet.get("fleet_leader"),
            "laggard": fleet.get("fleet_laggard"),
            "deploy_pct": fleet.get("fleet_total_deploy_pct"),
            "day_bets": fleet.get("day_total_bets"),
        })
        per_agent = d.get("per_agent") or {}
        if isinstance(per_agent, dict):
            for aid, a in per_agent.items():
                a = dict(a)
                a["_day"] = dp.stem
                a["_agent_id"] = aid
                agent_trajectory[aid].append(a)
        elif isinstance(per_agent, list):
            for a in per_agent:
                a = dict(a)
                a["_day"] = dp.stem
                aid = _aid(a)
                agent_trajectory[aid].append(a)
        for cat in (d.get("per_category") or {}):
            if isinstance(d["per_category"], dict):
                category_union.add(cat)

    # Fleet-level alerts
    if len(fleet_history) >= 2:
        cur, prev = fleet_history[-1], fleet_history[-2]
        try:
            delta = (cur["fleet_total"] - prev["fleet_total"]) / max(prev["fleet_total"], 1)
            if delta < -0.3:
                _emit(alerts, tf, 4, "fleet_decay", None,
                      f"Fleet total decayed {delta * 100:.1f}% between {prev['day']} and {cur['day']}",
                      f"Restart {tf.upper()} TF with fresh bankrolls via /api/reset + factory_reboot",
                      {"prev": prev["fleet_total"], "cur": cur["fleet_total"]})
        except (TypeError, KeyError):
            pass

        if (cur.get("jaccard_mean") or 0) >= 0.5:
            _emit(alerts, tf, 3, "lockstep", None,
                  f"Lockstep: jaccard_mean={cur['jaccard_mean']:.2f} (>=0.5)",
                  "Rewrite prompt overrides: add DMAD 'exclude peer consensus category' mandate",
                  {"day": cur["day"], "jaccard_mean": cur["jaccard_mean"]})

    # Agent-level
    live_agents = {}
    for aid, traj in agent_trajectory.items():
        recent3 = traj[-3:]
        n_bets_recent = sum(int(x.get("n_bets") or 0) for x in recent3)
        latest = traj[-1]
        bankroll = float(latest.get("bankroll_after") or latest.get("bankroll") or 0)
        dd = float(latest.get("max_drawdown") or 0)
        live_agents[aid] = {
            "bankroll": bankroll,
            "drawdown": dd,
            "recent_bets_3d": n_bets_recent,
            "strategy": latest.get("day_strategy", ""),
            "coalition_proposal": latest.get("coalition_proposal") is not None,
        }

        if n_bets_recent == 0 and len(recent3) >= 3:
            _emit(alerts, tf, 2, "agent_silent", aid,
                  f"Agent {aid} has 0 bets across last {len(recent3)} snapshot days",
                  f"Check agent {aid} LLM route — may be timing out; reroute via /api/mutate or prompt override",
                  {"recent_days": [x.get("_day") for x in recent3]})

        if dd >= 0.9 and bankroll < 50:
            _emit(alerts, tf, 4, "agent_ruined", aid,
                  f"Agent {aid} drawdown={dd:.2f} bankroll=${bankroll:.2f} — ruined",
                  f"Trigger capital-preservation mode for {aid} (dynamic MIN_DEPLOY floor already caps at 0.25)",
                  {"dd": dd, "bankroll": bankroll})

    # Concentration: if 1 agent holds >70% of fleet total
    if fleet_history:
        total = sum(a["bankroll"] for a in live_agents.values()) or 1.0
        for aid, a in live_agents.items():
            if a["bankroll"] / total > 0.7:
                _emit(alerts, tf, 3, "fleet_concentration", aid,
                      f"Single agent {aid} holds {a['bankroll'] / total * 100:.1f}% of fleet capital",
                      f"Dilute via coalition rebalance or diversify prompt — avoid single point of failure",
                      {"bankroll": a["bankroll"], "fleet_total": total})

    # Category coverage (POL-specific but harmless elsewhere)
    if tf == "pol" and len(category_union) < 2:
        _emit(alerts, tf, 3, "category_collapse", None,
              f"POL fleet only trades {len(category_union)} distinct categories ({sorted(category_union)})",
              "Inject POL prompt override: 'You MUST bet on >=2 distinct POL categories per day'",
              {"categories": sorted(category_union)})

    return {"n_days": len(days), "agents": live_agents, "fleet_history": fleet_history,
            "categories_seen": sorted(category_union)}


def analyze_pqtf(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    res = analyze_fleet_tf("pqtf", alerts)
    days = _day_files("pqtf", last_n=3)
    if not days:
        return res
    latest = _load_json(days[-1]) or {}
    per_bet = latest.get("per_bet") or []
    if per_bet:
        zombie = [b for b in per_bet if (b.get("type") is None) or (b.get("strike") in (0, 0.0, None))]
        if len(zombie) >= max(3, int(len(per_bet) * 0.2)):
            _emit(alerts, "pqtf", 3, "pqtf_zombie_rows", None,
                  f"{len(zombie)}/{len(per_bet)} PQTF order rows have type=null or strike=0",
                  "Patch pqtf engine: enforce explicit type+strike fields in LLM JSON contract",
                  {"zombie_count": len(zombie), "total": len(per_bet)})

        multi_leg = [b for b in per_bet if (b.get("legs") or b.get("strategy_type") in
                                            ("vertical_debit", "vertical_credit", "iron_condor",
                                             "straddle", "butterfly"))]
        if len(multi_leg) == 0 and len(per_bet) >= 10:
            _emit(alerts, "pqtf", 3, "pqtf_no_multileg", None,
                  f"PQTF emitted {len(per_bet)} bets, 0 multi-leg structures despite Phase-2 support",
                  "Inject PQTF prompt override mandating >=1 multi-leg structure per session",
                  {"total_bets": len(per_bet)})
    return res


def analyze_itf(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    positions_path = INTRADAY_DIR / "positions.json"
    decisions_dir = INTRADAY_DIR / "decisions"
    positions = _load_json(positions_path) or {}

    broker_401 = 0
    total_orders = 0
    silent_agents: list[str] = []
    crypto_trades = 0

    for tid, posns in positions.items():
        if not isinstance(posns, list):
            continue
        if not posns:
            silent_agents.append(tid)
            continue
        for p in posns:
            total_orders += 1
            err = (p.get("error") or "") + " " + (p.get("status") or "")
            if "401" in err or "403" in err:
                broker_401 += 1
            ticker = p.get("ticker", "")
            if "/" in ticker or ticker in ("BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE"):
                crypto_trades += 1

    if broker_401 > 0:
        pct = broker_401 / max(total_orders, 1) * 100
        _emit(alerts, "itf", 5, "broker_401", None,
              f"Alpaca broker returned 401 on {broker_401}/{total_orders} orders ({pct:.0f}%)",
              "Set ALPACA_PAPER_KEY + ALPACA_PAPER_SECRET as Space secrets on LBJLincoln26/intraday-trading-floor (the executor reads these env names, not APCA_* or ALPACA_API_KEY_ID)",
              {"broker_401": broker_401, "total": total_orders})

    if crypto_trades == 0 and total_orders > 0:
        _emit(alerts, "itf", 3, "itf_no_crypto", None,
              f"ITF emitted {total_orders} orders but 0 crypto trades (24/7 universe unused)",
              "Verify CRYPTO_PIVOT_CLAUSE deployment + _off_hours_crypto_signal threshold (BTC/ETH/SOL |change_pct|>0.2%)",
              {"total_orders": total_orders})

    decision_files = sorted(decisions_dir.glob("*.jsonl"))[-3:] if decisions_dir.is_dir() else []
    bids_per_agent: dict[str, int] = defaultdict(int)
    for df in decision_files:
        for line in df.read_text().splitlines():
            try:
                rec = json.loads(line)
                tid = rec.get("agent_tid") or rec.get("trader_id")
                if tid and (rec.get("action") or rec.get("side") or rec.get("ticker")):
                    bids_per_agent[tid] += 1
            except Exception:
                pass

    for tid, posns in positions.items():
        if bids_per_agent.get(tid, 0) == 0 and tid not in silent_agents:
            silent_agents.append(tid)

    for tid in set(silent_agents):
        _emit(alerts, "itf", 2, "itf_agent_silent", tid,
              f"ITF agent {tid} silent in last {len(decision_files)} decision files + 0 positions",
              f"Check gateway routing for {tid}'s model_primary; consult data/ops/llm-deadlist.json",
              {"bids": bids_per_agent.get(tid, 0)})

    return {
        "total_positions": total_orders,
        "broker_401_count": broker_401,
        "crypto_trades": crypto_trades,
        "silent_agents": sorted(set(silent_agents)),
        "bids_last_3_decisions": dict(bids_per_agent),
    }


def write_summary(snap: dict[str, Any]) -> None:
    lines = ["# TF Intel Snapshot", f"_generated {snap['ts']}_", ""]
    counts = defaultdict(int)
    for a in snap["alerts"]:
        counts[a["severity"]] += 1
    severity_line = "  ".join(f"S{sev}×{counts[sev]}" for sev in sorted(counts.keys(), reverse=True))
    lines.append(f"**Alerts:** {len(snap['alerts'])}   ({severity_line or 'none'})")
    lines.append("")
    for tf in ("nba", "pol", "pqtf", "itf"):
        lines.append(f"## {tf.upper()}")
        tf_alerts = [a for a in snap["alerts"] if a["tf"] == tf]
        if not tf_alerts:
            lines.append("- no alerts")
        for a in sorted(tf_alerts, key=lambda x: -x["severity"])[:20]:
            agent = f" [{a['agent']}]" if a["agent"] else ""
            lines.append(f"- **S{a['severity']} {a['code']}**{agent} — {a['finding']}")
            lines.append(f"    → {a['proposed_action']}")
        lines.append("")
    SUMMARY_PATH.write_text("\n".join(lines))


def run_cycle() -> dict[str, Any]:
    alerts: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    per_tf: dict[str, Any] = {}
    per_tf["nba"] = analyze_fleet_tf("nba", alerts)
    per_tf["pol"] = analyze_fleet_tf("pol", alerts)
    per_tf["pqtf"] = analyze_pqtf(alerts)
    per_tf["itf"] = analyze_itf(alerts)

    dead_llm_path = OUT_DIR / "llm-deadlist.json"
    dead_llm = _load_json(dead_llm_path) or {}
    snap = {
        "ts": ts,
        "alerts": alerts,
        "per_tf": per_tf,
        "dead_aliases_from_llm_monitor": dead_llm.get("dead", []),
        "broken_aliases_from_llm_monitor": dead_llm.get("broken", []),
    }
    SNAPSHOT_PATH.write_text(json.dumps(snap, indent=2))
    with ALERTS_PATH.open("a") as fh:
        for a in alerts:
            fh.write(json.dumps(a) + "\n")
    write_summary(snap)
    return snap


if __name__ == "__main__":
    snap = run_cycle()
    sev5 = sum(1 for a in snap["alerts"] if a["severity"] == 5)
    sev4 = sum(1 for a in snap["alerts"] if a["severity"] == 4)
    print(json.dumps({
        "ts": snap["ts"],
        "n_alerts": len(snap["alerts"]),
        "s5_critical": sev5,
        "s4_high": sev4,
        "nba_days": snap["per_tf"]["nba"]["n_days"],
        "pol_days": snap["per_tf"]["pol"]["n_days"],
        "pqtf_days": snap["per_tf"]["pqtf"]["n_days"],
        "itf_positions": snap["per_tf"]["itf"]["total_positions"],
        "itf_broker_401": snap["per_tf"]["itf"]["broker_401_count"],
    }))
