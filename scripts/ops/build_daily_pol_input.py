#!/usr/bin/env python3
"""POL day-input builder — mirror of NBA builder for POL TF.

Produces data/day-inputs/pol-<YYYY-MM-DD>.json per simulated political day
with: all events, event categories, sector ETFs, P7 model predictions,
pre-ranked edge candidates.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
POL_CACHE = REPO / "scripts/arena/hf-political-trading-floor/data"
OUT_DIR = REPO / "data" / "day-inputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EVENTS = POL_CACHE / "political_events.json"
POL_CATS = POL_CACHE / "political-full-cats.json"
POL_PREDS = POL_CACHE / "political-predictions.json"


def _load(p: Path) -> Any:
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except Exception: return {}


def build_for_date(date: str) -> dict | None:
    events_root = _load(EVENTS)
    cats = _load(POL_CATS)
    preds = _load(POL_PREDS)

    # events_root may be dict{events:[...]} or list
    events_list = events_root.get("events", []) if isinstance(events_root, dict) else events_root
    events_today = [
        e for e in events_list
        if isinstance(e, dict) and (e.get("date") == date or e.get("event_date") == date)
    ]
    if not events_today:
        # Also try date prefix match
        events_today = [
            e for e in events_list
            if isinstance(e, dict) and (e.get("date","") or e.get("event_date","")).startswith(date[:10])
        ]
    if not events_today:
        return None

    day_blob = {"date": date, "n_events": len(events_today), "events": []}
    all_edges = []

    for e in events_today:
        eid = e.get("event_id") or e.get("id")
        ticker = e.get("ticker") or e.get("underlying_ticker") or "?"
        pred = preds.get(str(eid), {}) if isinstance(preds, dict) else {}
        p_yes = pred.get("p_yes") or pred.get("prob_yes")
        # Sector ETF map (common subset)
        sector_etfs = {
            "energy": "XLE", "financial": "XLF", "tech": "XLK", "health": "XLV",
            "industrial": "XLI", "utilities": "XLU", "materials": "XLB",
            "consumer_discretionary": "XLY", "consumer_staples": "XLP",
            "communication": "XLC", "real_estate": "XLRE",
        }
        event_blob = {
            "event_id": eid,
            "event_type": e.get("event_type"),
            "agency": e.get("agency"),
            "ticker": ticker,
            "sector": e.get("sector"),
            "description": e.get("description", "")[:300],
            "date": e.get("date") or e.get("event_date"),
            "p_yes": p_yes,
            "p_no": 1 - p_yes if isinstance(p_yes, (int, float)) else None,
            "model_brier": pred.get("brier_cv") or pred.get("brier"),
        }
        if p_yes is not None:
            all_edges.append({
                "event_id": eid, "ticker": ticker,
                "direction": "long" if p_yes > 0.5 else "short",
                "p_yes": round(float(p_yes), 4),
                "edge": round(abs(float(p_yes) - 0.5), 4),
            })
        day_blob["events"].append(event_blob)

    scored = sorted(all_edges, key=lambda x: -x["edge"])
    day_blob["top_edges_ranked"] = scored[:25]
    day_blob["n_edges"] = len(scored)
    return day_blob


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: build_daily_pol_input.py YYYY-MM-DD  |  all")
        return 2
    target = sys.argv[1]
    events_root = _load(EVENTS)
    events_list = events_root.get("events", []) if isinstance(events_root, dict) else events_root
    if target == "all":
        dates = sorted({(e.get("date") or e.get("event_date") or "")[:10] for e in events_list if isinstance(e, dict)})
        dates = [d for d in dates if d]
        print(f"building {len(dates)} POL day-input files...")
        built = 0
        for date in dates:
            blob = build_for_date(date)
            if not blob: continue
            (OUT_DIR / f"pol-{date}.json").write_text(json.dumps(blob, indent=2, default=str))
            built += 1
        print(f"wrote {built} files")
        return 0
    blob = build_for_date(target)
    if not blob:
        print(f"no events on {target}"); return 1
    out = OUT_DIR / f"pol-{target}.json"
    out.write_text(json.dumps(blob, indent=2, default=str))
    print(f"wrote {out}")
    print(f"  n_events: {blob['n_events']}")
    print(f"  n_edges: {blob['n_edges']}")
    if blob["top_edges_ranked"]:
        print("  top 5 edges:")
        for e in blob["top_edges_ranked"][:5]:
            print(f"    {e['ticker']} {e['direction']} p_yes={e['p_yes']} edge={e['edge']:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
