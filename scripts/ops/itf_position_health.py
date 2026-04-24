#!/usr/bin/env python3
"""ITF position-health log — snapshot Alpaca PnL every 30min to jsonl.

Cheap audit trail for the real-money paper account. Lets us see:
  - Fleet equity trajectory over time
  - Which positions are aging + still losing
  - Whether 0DTE options are concentrating risk

Writes to data/ops/itf-position-health.jsonl (append-only, one line per run).
"""
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "ops" / "itf-position-health.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)


def _env(k):
    # Lightweight .env.local reader
    env_file = REPO / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("export "): line = line[7:]
            if "=" in line:
                kk, _, vv = line.partition("=")
                if kk.strip() == k:
                    return vv.strip().strip('"').strip("'").split(" #")[0].strip()
    return os.environ.get(k)


def _http_json(url, headers):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def main() -> int:
    key = _env("ALPACA_PAPER_KEY")
    secret = _env("ALPACA_PAPER_SECRET")
    if not (key and secret):
        print("no Alpaca creds"); return 1
    h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    acct = _http_json("https://paper-api.alpaca.markets/v2/account", h)
    pos = _http_json("https://paper-api.alpaca.markets/v2/positions", h)

    summary = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "equity": float(acct.get("equity") or 0),
        "cash": float(acct.get("cash") or 0),
        "long_mv": float(acct.get("long_market_value") or 0),
        "short_mv": float(acct.get("short_market_value") or 0),
        "buying_power": float(acct.get("buying_power") or 0),
        "daytrade_count": int(acct.get("daytrade_count") or 0),
        "n_positions": len(pos),
        "by_class": {},
        "unrealized_pnl_total": 0.0,
        "top_losers": [],
        "top_winners": [],
    }
    by_cls = {}
    for p in pos:
        cls = p.get("asset_class", "?")
        slot = by_cls.setdefault(cls, {"n": 0, "mv": 0.0, "pnl": 0.0})
        slot["n"] += 1
        slot["mv"] += float(p.get("market_value") or 0)
        slot["pnl"] += float(p.get("unrealized_pl") or 0)
        summary["unrealized_pnl_total"] += float(p.get("unrealized_pl") or 0)
    summary["by_class"] = {k: {kk: round(v, 2) for kk, v in s.items()} for k, s in by_cls.items()}

    sorted_pl = sorted(pos, key=lambda x: float(x.get("unrealized_pl") or 0))
    for p in sorted_pl[:3]:
        summary["top_losers"].append({
            "symbol": p["symbol"][:30], "pnl": round(float(p.get("unrealized_pl") or 0), 2),
            "mv": round(float(p.get("market_value") or 0), 2),
            "plpc": round(float(p.get("unrealized_plpc") or 0) * 100, 2),
        })
    for p in sorted_pl[-3:][::-1]:
        summary["top_winners"].append({
            "symbol": p["symbol"][:30], "pnl": round(float(p.get("unrealized_pl") or 0), 2),
            "mv": round(float(p.get("market_value") or 0), 2),
            "plpc": round(float(p.get("unrealized_plpc") or 0) * 100, 2),
        })

    with OUT.open("a") as f: f.write(json.dumps(summary) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main())
