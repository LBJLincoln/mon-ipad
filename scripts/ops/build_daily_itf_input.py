#!/usr/bin/env python3
"""ITF day-input builder — real-time snapshot per UTC day.

ITF is live Alpaca paper trading so the "day" is today's real market
session. Writes data/day-inputs/itf-<YYYY-MM-DD>.json with:
  - Alpaca account snapshot (equity/cash/BP/positions count)
  - All 17 personas with LLM tag + current bankroll + reserved
  - Quote snapshot from quote_bus (if available)
  - POL hot-signals that feed ITF prompts (form4, congress, scotus, etc.)
  - Top positions by PnL (winners + losers)
  - Recent orders (last 20)
  - Recent agent decisions (last 30 from agent_ledger)

Run after market close (21:00 UTC) for a clean daily archive.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "day-inputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HTTP_TIMEOUT = 15


def _env(k: str) -> str:
    # tiny .env.local reader (duplicates logic from tf_baseline_check)
    p = REPO / ".env.local"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("export "): line = line[7:]
            if "=" in line:
                kk, _, vv = line.partition("=")
                if kk.strip() == k:
                    return vv.strip().strip('"').strip("'").split(" #")[0].strip()
    return os.environ.get(k, "")


def _http_json(url: str, headers: dict | None = None) -> object | None:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:
        return None


def main() -> int:
    today = dt.date.today().isoformat()

    key = _env("ALPACA_PAPER_KEY")
    secret = _env("ALPACA_PAPER_SECRET")
    a_hdr = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    # Alpaca account + positions + recent orders
    acct = _http_json("https://paper-api.alpaca.markets/v2/account", a_hdr) or {}
    positions = _http_json("https://paper-api.alpaca.markets/v2/positions", a_hdr) or []
    orders = _http_json("https://paper-api.alpaca.markets/v2/orders?status=all&limit=30", a_hdr) or []

    # ITF space bankrolls + llm map (new endpoint we shipped earlier)
    itf_url = "https://lbjlincoln26-intraday-trading-floor.hf.space"
    bankrolls = _http_json(f"{itf_url}/api/bankrolls") or {}
    llm_leaderboard = _http_json(f"{itf_url}/api/llm-leaderboard") or {}

    # POL hot-signals file (already on VM)
    pol_hot = {}
    p_hot = REPO / "data/political/hot-signals-latest.json"
    if p_hot.exists():
        try: pol_hot = json.loads(p_hot.read_text())
        except Exception: pass

    # Agent ledger tail from Hub
    hf_tok = _env("HF_TOKEN_NBA") or _env("HF_TOKEN")
    hf_hdr = {"Authorization": f"Bearer {hf_tok}"} if hf_tok else {}
    try:
        req = urllib.request.Request(
            "https://huggingface.co/spaces/LBJLincoln26/intraday-trading-floor/raw/main/data/intraday/agent_ledger.jsonl",
            headers=hf_hdr,
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            raw = r.read().decode("utf-8", errors="replace")
            lines = raw.strip().split("\n")[-50:]
        ledger_tail = []
        for l in lines:
            try: ledger_tail.append(json.loads(l))
            except Exception: pass
    except Exception:
        ledger_tail = []

    # Compute PnL top/bottom
    def _pnl(p): return float(p.get("unrealized_pl") or 0)
    sorted_pos = sorted(positions, key=_pnl)
    top_losers = sorted_pos[:5]
    top_winners = sorted_pos[-5:][::-1]

    blob = {
        "date": today,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "alpaca_account": {
            "equity": float(acct.get("equity") or 0),
            "cash": float(acct.get("cash") or 0),
            "long_market_value": float(acct.get("long_market_value") or 0),
            "short_market_value": float(acct.get("short_market_value") or 0),
            "buying_power": float(acct.get("buying_power") or 0),
            "daytrade_count": int(acct.get("daytrade_count") or 0),
            "pattern_day_trader": bool(acct.get("pattern_day_trader")),
            "trading_blocked": bool(acct.get("trading_blocked")),
        },
        "n_positions": len(positions),
        "positions_by_class": {},
        "itf_bankrolls": bankrolls,
        "itf_llm_leaderboard": llm_leaderboard,
        "pol_hot_signals": pol_hot,
        "top_losers": [
            {"symbol": p["symbol"], "qty": p["qty"],
             "mv": float(p.get("market_value") or 0),
             "pnl": float(p.get("unrealized_pl") or 0),
             "plpc": float(p.get("unrealized_plpc") or 0)}
            for p in top_losers
        ],
        "top_winners": [
            {"symbol": p["symbol"], "qty": p["qty"],
             "mv": float(p.get("market_value") or 0),
             "pnl": float(p.get("unrealized_pl") or 0),
             "plpc": float(p.get("unrealized_plpc") or 0)}
            for p in top_winners
        ],
        "recent_orders": [
            {"symbol": o.get("symbol"), "side": o.get("side"),
             "qty": o.get("qty"), "notional": o.get("notional"),
             "status": o.get("status"),
             "submitted_at": o.get("submitted_at"),
             "filled_avg_price": o.get("filled_avg_price")}
            for o in orders[:30]
        ],
        "agent_ledger_tail": ledger_tail,
    }
    # Class breakdown
    by_class = {}
    for p in positions:
        c = p.get("asset_class","?")
        slot = by_class.setdefault(c, {"n": 0, "mv": 0.0, "pnl": 0.0})
        slot["n"] += 1
        slot["mv"] += float(p.get("market_value") or 0)
        slot["pnl"] += float(p.get("unrealized_pl") or 0)
    blob["positions_by_class"] = {k: {kk: round(v, 2) for kk, v in s.items()} for k, s in by_class.items()}

    out = OUT_DIR / f"itf-{today}.json"
    out.write_text(json.dumps(blob, indent=2, default=str))
    print(f"wrote {out}")
    print(f"  equity: ${blob['alpaca_account']['equity']:,.0f}")
    print(f"  positions: {blob['n_positions']}  (by class: {list(blob['positions_by_class'].keys())})")
    print(f"  llm leaderboard entries: {len(llm_leaderboard.get('leaderboard', []))}")
    print(f"  pol hot-signal categories: {len([k for k in pol_hot.keys() if k.startswith('cat')])}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
