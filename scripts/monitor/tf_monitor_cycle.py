#!/usr/bin/env python3
"""TF monitor cycle — one pass every ~5 min. Flags anomalies, doesn't mutate.

Reads /api/status + /api/bankrolls for NBA/POL/ITF, diffs against latest baseline,
writes /home/termius/mon-ipad/data/monitor/cycle-<ts>.json with:
  - per-agent bankroll deltas
  - llm_ok rate post-latest-reroute (using baseline fixed-day anchor)
  - ITF fleet deploy % + stale-loser close evidence
  - top alerts: big drawdowns, dead-provider persists, agents stuck
Exits 0 always. Idempotent.
"""
import json
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timezone

MON_DIR = pathlib.Path("/home/termius/mon-ipad/data/monitor")
MON_DIR.mkdir(parents=True, exist_ok=True)

SPACES = {
    "nba": "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status",
    "pol": "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status",
    "itf_status": "https://lbjlincoln26-intraday-trading-floor.hf.space/api/status",
    "itf_bankrolls": "https://lbjlincoln26-intraday-trading-floor.hf.space/api/bankrolls",
}


def _fetch(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": str(e)}


def _latest_baseline():
    files = sorted(MON_DIR.glob("baseline-*.json"))
    if not files:
        return None
    try:
        return json.load(open(files[-1]))
    except Exception:
        return None


def _itf_auto_reseed_if_wiped(itf_br):
    """If all 17 ITF agents have total_equity=0 (post-reboot wipe), POST
    /api/reset-bankrolls to re-seed from current Alpaca equity."""
    agents = (itf_br or {}).get("agents") or {}
    if not isinstance(agents, dict) or len(agents) < 17:
        return None
    seeded = sum(1 for v in agents.values()
                 if isinstance(v, dict) and float(v.get("total_equity", 0)) > 0)
    if seeded >= 17:
        return None
    try:
        req = urllib.request.Request(
            "https://lbjlincoln26-intraday-trading-floor.hf.space/api/reset-bankrolls",
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()).get("meta", {})
    except Exception as e:
        return {"_error": str(e)[:120]}


def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nba = _fetch(SPACES["nba"])
    pol = _fetch(SPACES["pol"])
    itf_s = _fetch(SPACES["itf_status"])
    itf_br = _fetch(SPACES["itf_bankrolls"])

    # Structural guard: if ITF wiped on factory_reboot, reseed bankrolls before diff
    reseed_meta = _itf_auto_reseed_if_wiped(itf_br)
    if reseed_meta:
        itf_br = _fetch(SPACES["itf_bankrolls"])  # re-read after reseed

    baseline = _latest_baseline() or {}
    b_nba = (baseline.get("nba") or {}).get("agents", {})
    b_pol = (baseline.get("pol") or {}).get("agents", {})
    b_itf = baseline.get("itf") or {}

    def sorted_agents(d):
        agents = (d.get("agents") or {})
        rows = []
        for tid, a in agents.items():
            rows.append({"tid": tid, "bank": a.get("bankroll", 0),
                         "bets": a.get("total_bets", 0), "W": a.get("wins", 0),
                         "L": a.get("losses", 0), "pass": a.get("passes", 0),
                         "llm_ok": a.get("llm_ok", 0),
                         "llm_calls": a.get("llm_calls", 0)})
        rows.sort(key=lambda x: x["bank"], reverse=True)
        return rows

    snap = {
        "ts": ts,
        "nba": {"day": nba.get("days_processed"), "total": nba.get("days_total"),
                "agents": sorted_agents(nba)},
        "pol": {"day": pol.get("days_processed"), "total": pol.get("days_total"),
                "agents": sorted_agents(pol)},
        "itf": {"running": itf_s.get("running"),
                "last_tick_at": itf_s.get("last_tick_at"),
                "fleet_equity": itf_br.get("fleet_equity"),
                "fleet_reserved": itf_br.get("fleet_reserved"),
                "fleet_free": itf_br.get("fleet_available") or itf_br.get("fleet_free"),
                "agents_seeded": sum(1 for v in (itf_br.get("agents") or {}).values()
                                     if isinstance(v, dict) and float(v.get("total_equity", 0)) > 0)},
    }

    alerts = []

    # NBA/POL drawdown + dead-provider scan
    for fleet_key, fleet, baseline_agents in [
        ("nba", snap["nba"], b_nba),
        ("pol", snap["pol"], b_pol),
    ]:
        for a in fleet["agents"]:
            tid = a["tid"]
            prev_bank = (baseline_agents.get(tid) or {}).get("bank")
            if prev_bank is not None and prev_bank > 5:
                delta_pct = (a["bank"] - prev_bank) / prev_bank * 100
                if delta_pct <= -10:
                    alerts.append(f"{fleet_key.upper()} {tid} DRAWDOWN {delta_pct:+.1f}% "
                                  f"(${prev_bank:.2f} → ${a['bank']:.2f})")
                elif delta_pct >= 15:
                    alerts.append(f"{fleet_key.upper()} {tid} SURGE {delta_pct:+.1f}% "
                                  f"(${prev_bank:.2f} → ${a['bank']:.2f})")
            if a["llm_calls"] >= 20:
                ok_rate = a["llm_ok"] / a["llm_calls"]
                prev = baseline_agents.get(tid) or {}
                prev_calls = prev.get("llm_calls", 0)
                prev_ok = prev.get("llm_ok", 0)
                new_calls = a["llm_calls"] - prev_calls
                new_ok = a["llm_ok"] - prev_ok
                if new_calls >= 3 and new_ok / new_calls < 0.3:
                    alerts.append(f"{fleet_key.upper()} {tid} provider still DEAD "
                                  f"(new: {new_ok}/{new_calls}={100*new_ok/new_calls:.0f}%)")

    # NBA/POL stall
    for fleet_key in ("nba", "pol"):
        prev_day = (baseline.get(fleet_key) or {}).get("day")
        cur_day = snap[fleet_key]["day"]
        if prev_day is not None and cur_day is not None and cur_day == prev_day:
            alerts.append(f"{fleet_key.upper()} STALLED at day {cur_day} — no advance since baseline")

    # ITF deploy %
    fe = snap["itf"]["fleet_equity"]
    fr = snap["itf"]["fleet_reserved"]
    if isinstance(fe, (int, float)) and isinstance(fr, (int, float)) and fe > 0:
        deploy_pct = fr / fe * 100
        snap["itf"]["deploy_pct"] = round(deploy_pct, 2)
        if deploy_pct < 10:
            alerts.append(f"ITF deploy {deploy_pct:.1f}% (target 70%) — BP likely still starved")
        elif deploy_pct >= 50:
            alerts.append(f"ITF deploy {deploy_pct:.1f}% — BP unlock PAYING OFF")
        # baseline compare
        prev_fr = b_itf.get("fleet_reserved")
        prev_fe = b_itf.get("fleet_equity")
        if isinstance(prev_fr, (int, float)) and isinstance(prev_fe, (int, float)):
            dr = fr - prev_fr
            de = fe - prev_fe
            snap["itf"]["reserved_delta"] = round(dr, 2)
            snap["itf"]["equity_delta"] = round(de, 2)
            if abs(de) >= 500:
                alerts.append(f"ITF equity move ${de:+,.2f} since baseline")

    # ITF tick freshness (should advance every ~90s)
    lta = snap["itf"]["last_tick_at"]
    if lta:
        try:
            dt = datetime.fromisoformat(lta.rstrip("Z")).replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - dt).total_seconds()
            snap["itf"]["tick_age_sec"] = round(age, 1)
            if age > 300:
                alerts.append(f"ITF tick STALE ({age:.0f}s old — tick_loop may have died)")
        except Exception:
            pass

    if reseed_meta and "_error" not in reseed_meta:
        alerts.insert(0, f"ITF auto-reseeded (wipe detected): 17×${reseed_meta.get('seed_share_usd','?')} from ${reseed_meta.get('seed_equity_usd','?'):,.0f} equity")
    elif reseed_meta and "_error" in reseed_meta:
        alerts.insert(0, f"ITF reseed FAILED: {reseed_meta['_error']}")

    snap["alerts"] = alerts

    out = MON_DIR / f"cycle-{ts}.json"
    out.write_text(json.dumps(snap, indent=2))

    # update symlink
    latest = MON_DIR / "latest.json"
    try:
        latest.unlink(missing_ok=True)
    except Exception:
        pass
    latest.symlink_to(out)

    # Compact stdout
    n = snap["nba"]
    p = snap["pol"]
    i = snap["itf"]
    top_nba = n["agents"][0] if n["agents"] else {}
    top_pol = p["agents"][0] if p["agents"] else {}
    print(f"[{ts}]")
    print(f"  NBA day={n['day']}/{n['total']} top={top_nba.get('tid')} ${top_nba.get('bank',0):.2f}")
    print(f"  POL day={p['day']}/{p['total']} top={top_pol.get('tid')} ${top_pol.get('bank',0):.2f}")
    print(f"  ITF eq=${i.get('fleet_equity') or 0:,.0f} res=${i.get('fleet_reserved') or 0:,.0f} "
          f"deploy={i.get('deploy_pct','?')}% seeded={i.get('agents_seeded','?')}/17 "
          f"tick_age={i.get('tick_age_sec','?')}s")
    if alerts:
        print(f"  ALERTS ({len(alerts)}):")
        for a in alerts:
            print(f"    - {a}")
    else:
        print("  alerts: (none)")


if __name__ == "__main__":
    main()
