#!/usr/bin/env python3
"""Nomos42 TF perfect-monitor v2 — all surfaces + JSON snapshot + history.

Surfaces covered:
  - 4 TFs (NBA / POL / PQTF / ITF) with per-agent bankroll summary
  - 3 new browser/hermes Spaces (browser-nba / browser-qa / hermes-agent)
  - 7 evolution islands (S13-S22 NBA + P1-P7 POL)
  - LLM gateway + langfuse
  - Vercel dashboard routes
  - Pixel world
  - Alpaca account

Usage:
  python3 scripts/ops/tf_perfect_monitor.py                  # human-readable
  python3 scripts/ops/tf_perfect_monitor.py --json           # one-line JSON
  python3 scripts/ops/tf_perfect_monitor.py --snapshot       # human + writes
                                                             #  data/monitoring/tf-perfect-latest.json
                                                             #  data/monitoring/tf-perfect-history.jsonl
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONITOR_DIR = REPO / "data" / "monitoring"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO / ".env.local")


def _probe(url: str, timeout: int = 12) -> tuple[int | str, bytes]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nomos-mon"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except Exception as exc:
        return "ERR", str(exc).encode()


def _probe_json(url: str, timeout: int = 12) -> tuple[int | str, dict | None]:
    code, body = _probe(url, timeout)
    if code != 200:
        return code, None
    try:
        return code, json.loads(body)
    except Exception:
        return code, None


def _apca_headers() -> dict[str, str] | None:
    k = os.environ.get("ALPACA_PAPER_KEY")
    s = os.environ.get("ALPACA_PAPER_SECRET")
    if not (k and s):
        return None
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}


def _alpaca() -> dict:
    h = _apca_headers()
    if not h:
        return {"ok": False, "error": "no_key"}
    try:
        req = urllib.request.Request("https://paper-api.alpaca.markets/v2/account", headers=h)
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        return {
            "ok": True,
            "equity": float(d["portfolio_value"]),
            "cash": float(d["cash"]),
            "buying_power": float(d["buying_power"]),
            "status": d["status"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


def _alpaca_positions_count() -> int:
    h = _apca_headers()
    if not h:
        return -1
    try:
        req = urllib.request.Request("https://paper-api.alpaca.markets/v2/positions", headers=h)
        with urllib.request.urlopen(req, timeout=10) as r:
            return len(json.loads(r.read()))
    except Exception:
        return -1


TFS = [
    ("NBA",  "LBJLincoln26/nba-llm-trading-floor",
     "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status"),
    ("POL",  "LBJLincoln26/political-llm-trading-floor",
     "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status"),
    ("PQTF", "LBJLincoln26/political-quant-trading-floor",
     "https://lbjlincoln26-political-quant-trading-floor.hf.space/api/status"),
    ("ITF",  "LBJLincoln26/intraday-trading-floor",
     "https://lbjlincoln26-intraday-trading-floor.hf.space/api/status"),
]

BROWSER_HERMES = [
    ("BRW-NBA", "https://lbjlincoln-nomos-browser-nba.hf.space/api/status"),
    ("BRW-QA",  "https://testforge42-nomos-browser-qa.hf.space/api/status"),
    ("HERMES",  "https://lbjlincoln26-nomos-hermes-agent.hf.space/api/status"),
]

ISLANDS = [
    ("S13", "https://nomos42-nba-evo-4.hf.space/api/status"),
    ("S14", "https://nomos42-nba-evo-5.hf.space/api/status"),
    ("S15", "https://nomos42-nba-evo-6.hf.space/api/status"),
    ("S17", "https://lbjlincoln26-nba-evo-s17.hf.space/api/status"),
    ("S18", "https://testforge42-nba-evo-s18.hf.space/api/status"),
    ("S22", "https://testforge42-nba-evo-s22.hf.space/api/status"),
    ("P1",  "https://nomos42-political-alpha.hf.space/api/status"),
    ("P2",  "https://nomos42-political-alpha-2.hf.space/api/status"),
    ("P4",  "https://lbjlincoln-political-alpha-4.hf.space/api/status"),
    ("P5",  "https://lbjlincoln-political-alpha-5.hf.space/api/status"),
    ("P7",  "https://lbjlincoln-political-alpha-7.hf.space/api/status"),
]

EXTERNAL = [
    ("dash.health",       "https://nomosdashboard.vercel.app/api/health"),
    ("fleet.status",      "https://nomosdashboard.vercel.app/api/fleet/status"),
    ("pixel.world",       "https://nomos42-pixel-world.static.hf.space/"),
    ("llm-gateway",       "https://lbjlincoln26-llm-gateway.hf.space/api/models"),
    ("langfuse",          "https://nomos42-langfuse.hf.space/api/public/health"),
]


def _collect(api) -> dict:
    snap = {
        "ts": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tfs": {},
        "browser_hermes": {},
        "islands": {},
        "external": {},
        "alpaca": _alpaca(),
        "alpaca_positions": _alpaca_positions_count(),
    }

    for label, space, url in TFS:
        entry = {"space": space}
        try:
            rt = api.get_space_runtime(space)
            entry["stage"] = rt.stage
            entry["hardware"] = rt.hardware or "free-cpu"
        except Exception as exc:
            entry["error"] = str(exc)[:120]
            snap["tfs"][label] = entry
            continue

        if rt.stage != "RUNNING":
            snap["tfs"][label] = entry
            continue

        code, s = _probe_json(url)
        if not s:
            entry["status_code"] = code
            snap["tfs"][label] = entry
            continue

        if label == "ITF":
            ag = s.get("agents", {})
            entry.update({
                "tick": s.get("tick_count"),
                "mode": s.get("mode"),
                "last_tick": s.get("last_tick_at"),
                "agents": len(ag),
                "trades": sum(a.get("trades", 0) for a in ag.values()),
                "passes": sum(a.get("passes", 0) for a in ag.values()),
            })
        else:
            agents = s.get("agents", {})
            banks = [(t, a.get("bankroll", 0), a.get("llm_ok", 0),
                      a.get("llm_calls", 0), a.get("total_bets", 0),
                      a.get("wins", 0)) for t, a in agents.items()]
            banks.sort(key=lambda x: -x[1])
            llm_ok = sum(b[2] for b in banks)
            llm_calls = sum(b[3] for b in banks)
            bets = sum(b[4] for b in banks)
            wins = sum(b[5] for b in banks)
            entry.update({
                "day": s.get("days_processed", 0),
                "days_total": s.get("days_total", 0),
                "agents": len(agents),
                "fleet_sum": round(sum(b[1] for b in banks), 2),
                "best_agent": banks[0][0] if banks else None,
                "best_bankroll": round(banks[0][1], 2) if banks else 0,
                "worst_bankroll": round(banks[-1][1], 2) if banks else 0,
                "llm_ok_rate": round((100 * llm_ok / llm_calls) if llm_calls else 0, 1),
                "wr_pct": round((100 * wins / bets) if bets else 0, 1),
                "bets_total": bets,
                "agents_below_20": sum(1 for b in banks if b[1] < 20),
                "agents_above_150": sum(1 for b in banks if b[1] >= 150),
            })
        snap["tfs"][label] = entry

    for label, url in BROWSER_HERMES:
        code, s = _probe_json(url, 8)
        snap["browser_hermes"][label] = {
            "code": code,
            "service": (s or {}).get("service"),
            "providers": (s or {}).get("providers"),
        }

    for label, url in ISLANDS:
        code, s = _probe_json(url, 8)
        snap["islands"][label] = {
            "code": code,
            "generation": (s or {}).get("generation"),
            "best_brier": (s or {}).get("best_brier"),
        }

    for label, url in EXTERNAL:
        code, _ = _probe(url, 8)
        snap["external"][label] = code

    return snap


def _pretty(snap: dict) -> None:
    bar = "=" * 92
    print(bar)
    print(f"NOMOS42 PERFECT MONITOR v2 @ {snap['ts']}")
    print(bar)

    for label in ["NBA", "POL", "PQTF", "ITF"]:
        e = snap["tfs"].get(label, {})
        stage = e.get("stage", "?")
        hw = e.get("hardware", "?")
        print(f"\n── {label:4} stage={stage:22} hw={hw}")
        if label == "ITF" and stage == "RUNNING":
            print(f"      tick={e.get('tick')} mode={e.get('mode')} "
                  f"last={e.get('last_tick')}")
            print(f"      agents={e.get('agents')} trades={e.get('trades')} "
                  f"passes={e.get('passes')}")
        elif stage == "RUNNING":
            print(f"      day={e.get('day')}/{e.get('days_total')} "
                  f"llm_ok={e.get('llm_ok_rate')}% WR={e.get('wr_pct')}%")
            print(f"      fleet=${e.get('fleet_sum'):,.2f}  "
                  f"best={e.get('best_agent')}@${e.get('best_bankroll'):.2f}  "
                  f"worst=${e.get('worst_bankroll'):.2f}  "
                  f"<$20:{e.get('agents_below_20')}/{e.get('agents')}  "
                  f">$150:{e.get('agents_above_150')}/{e.get('agents')}")

    print("\n── BROWSER + HERMES ──")
    for label, e in snap["browser_hermes"].items():
        print(f"   {label:10} [{e['code']}] service={e.get('service')} "
              f"providers={e.get('providers')}")

    print("\n── EVOLUTION ISLANDS ──")
    for label, e in snap["islands"].items():
        print(f"   {label:4} [{e['code']}] gen={e.get('generation')} "
              f"brier={e.get('best_brier')}")

    print("\n── EXTERNAL SURFACES ──")
    for label, code in snap["external"].items():
        print(f"   {label:16} [{code}]")

    alpaca = snap["alpaca"]
    pos = snap["alpaca_positions"]
    if alpaca.get("ok"):
        print(f"   alpaca           [OK] equity=${alpaca['equity']:,.2f} "
              f"cash=${alpaca['cash']:,.2f} positions={pos} status={alpaca['status']}")
    else:
        print(f"   alpaca           [ERR] {alpaca.get('error')}")


def _write_snapshot(snap: dict) -> None:
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    (MONITOR_DIR / "tf-perfect-latest.json").write_text(json.dumps(snap, indent=1))
    with (MONITOR_DIR / "tf-perfect-history.jsonl").open("a") as f:
        f.write(json.dumps(snap) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit single-line JSON")
    ap.add_argument("--snapshot", action="store_true",
                    help="print human + write data/monitoring/tf-perfect-{latest.json,history.jsonl}")
    args = ap.parse_args()

    _load_env()
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub missing", file=sys.stderr)
        return 1
    token = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN_2")
    if not token:
        print("no HF_TOKEN", file=sys.stderr)
        return 1
    api = HfApi(token=token)

    snap = _collect(api)

    if args.json:
        print(json.dumps(snap))
    else:
        _pretty(snap)

    if args.snapshot:
        _write_snapshot(snap)

    return 0


if __name__ == "__main__":
    sys.exit(main())
