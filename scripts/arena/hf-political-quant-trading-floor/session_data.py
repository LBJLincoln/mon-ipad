"""Intraday session splitter for political events.

Takes `political_events.json` (834 events, keyed by date + ticker + event_type)
and assigns each event to one of 4 intraday sessions based on event-type heuristics.

Sessions (ET):
  s1: 09:30 – 12:00  pre-lunch
  s2: 12:00 – 14:30  midday
  s3: 14:30 – 16:00  close
  s4: 16:00 – 20:00  after-hours / political window

Heuristics (events don't carry a timestamp, so we route by type):
  - insider_trade       → s2 (midday — congressional disclosures typically filed in batches)
  - fed_rule            → s3 (14:00-15:00 ET is classic Fed statement window)
  - exec_order          → s4 (WH afternoon pressers / evening signings)
  - polymarket          → s4 (political prediction markets move overnight)
  - FOMC / CPI / NFP    → s1 or s3 depending on release schedule
  - election_result     → s4 (after-hours)

Sector→ETF mapping for derivatives pricing (user trades options on these tickers):
  finance           → XLF
  consumer_staples  → XLP
  tech              → XLK
  energy            → XLE
  healthcare        → XLV
  consumer_disc     → XLY
  communications    → XLC
  private_prisons   → XLI  (industrials proxy — no direct ETF)
  other             → SPY

API:
  load_events(path) -> list of events
  split_day(events_for_date) -> {s1: [...], s2: [...], s3: [...], s4: [...]}
  all_days(events) -> {date: {s1:[...], s2:[...], s3:[...], s4:[...]}}
  sector_to_etf(sector) -> ticker
  event_iv_category(event_type) -> 'FOMC' | 'ELECTION' | 'DEFAULT' | ...
"""
import json
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any


# ── Event-type → session routing ────────────────────────────────────────────

EVENT_TYPE_SESSION = {
    "insider_trade": 2,
    "fed_rule": 3,
    "exec_order": 4,
    "polymarket": 4,
    "fomc": 3,
    "cpi": 1,
    "nfp": 1,
    "gdp": 1,
    "election_result": 4,
    "debate": 4,
    "scotus": 3,
    "geopolitical": 4,
}


# Event-type → IV scaling category (maps to intraday_paths.EVENT_IV_SCALE)
EVENT_IV_CATEGORY = {
    "insider_trade": "DEFAULT",
    "fed_rule": "FOMC",
    "exec_order": "GEOPOLITICAL",
    "polymarket": "ELECTION",
    "fomc": "FOMC",
    "cpi": "CPI",
    "nfp": "NFP",
    "gdp": "GDP",
    "election_result": "ELECTION",
    "debate": "DEBATE",
    "scotus": "SCOTUS",
    "geopolitical": "GEOPOLITICAL",
}


# Sector → ETF ticker for derivatives pricing
SECTOR_ETF = {
    "finance": "XLF",
    "consumer_staples": "XLP",
    "consumer_staple": "XLP",
    "tech": "XLK",
    "technology": "XLK",
    "energy": "XLE",
    "healthcare": "XLV",
    "health_care": "XLV",
    "consumer_disc": "XLY",
    "consumer_discretionary": "XLY",
    "communications": "XLC",
    "communication_services": "XLC",
    "private_prisons": "XLI",
    "industrials": "XLI",
    "materials": "XLB",
    "real_estate": "XLRE",
    "utilities": "XLU",
    "other": "SPY",
}


def load_events(path: str) -> List[Dict[str, Any]]:
    """Load political_events.json."""
    with open(path) as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    raise ValueError(f"unexpected root type: {type(data).__name__}")


def event_session(event: Dict[str, Any]) -> int:
    """Assign session 1-4 to an event. Default s2 for unknown types."""
    et = (event.get("event_type") or "").lower()
    return EVENT_TYPE_SESSION.get(et, 2)


def event_iv_category(event: Dict[str, Any]) -> str:
    """Return IV-scaling category key for the event (feeds scale_iv_for_event)."""
    et = (event.get("event_type") or "").lower()
    return EVENT_IV_CATEGORY.get(et, "DEFAULT")


def sector_to_etf(sector: str) -> str:
    """Map a signal_sector to a tradeable ETF ticker."""
    if not sector:
        return "SPY"
    return SECTOR_ETF.get(sector.lower(), "SPY")


def split_day(events_for_date: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Split one day's events into 4 sessions."""
    out = {"s1": [], "s2": [], "s3": [], "s4": []}
    for ev in events_for_date:
        s = event_session(ev)
        out[f"s{s}"].append(ev)
    return out


def all_days(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Group all events by date, then split each date into 4 sessions."""
    by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ev in events:
        d = ev.get("date")
        if not d:
            continue
        by_date[d].append(ev)
    return {d: split_day(evs) for d, evs in sorted(by_date.items())}


def enrich_event_for_quant(event: Dict[str, Any]) -> Dict[str, Any]:
    """Add quant-relevant fields to an event for the LLM prompt context.

    Adds:
      - etf_ticker: tradeable ETF
      - session: 1-4
      - iv_category: event-type IV bucket
      - direction_bias: +1/-1 from signal + excess_return sign (if known post-hoc)
    """
    out = dict(event)
    out["etf_ticker"] = sector_to_etf(event.get("signal_sector", ""))
    out["session"] = event_session(event)
    out["iv_category"] = event_iv_category(event)
    # Direction bias: signal_strength is magnitude only; use transaction_type or outcome hint
    tt = (event.get("transaction_type") or "").lower()
    if "purchase" in tt or "buy" in tt:
        bias = 1
    elif "sale" in tt or "sell" in tt:
        bias = -1
    else:
        bias = 0
    out["direction_bias"] = bias
    return out


# ── Self-test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    path = "/home/termius/mon-ipad/scripts/arena/hf-political-trading-floor/data/political_events.json"
    events = load_events(path)
    assert len(events) > 500, f"expected 500+ events, got {len(events)}"

    # Session routing checks
    for et, expected in [("insider_trade", 2), ("fed_rule", 3), ("polymarket", 4), ("exec_order", 4)]:
        assert event_session({"event_type": et}) == expected, f"{et} should route to s{expected}"
    assert event_session({"event_type": "unknown"}) == 2, "unknown types default to s2"

    # Sector→ETF
    assert sector_to_etf("finance") == "XLF"
    assert sector_to_etf("tech") == "XLK"
    assert sector_to_etf("unknown_sector") == "SPY"
    assert sector_to_etf("") == "SPY"

    # Event IV category
    assert event_iv_category({"event_type": "fed_rule"}) == "FOMC"
    assert event_iv_category({"event_type": "insider_trade"}) == "DEFAULT"

    # Day split — pick a known date with many events
    days = all_days(events)
    assert len(days) >= 40, f"expected 40+ days, got {len(days)}"
    sample_date = next(iter(days))
    sample = days[sample_date]
    assert set(sample.keys()) == {"s1", "s2", "s3", "s4"}
    total_in_sessions = sum(len(sample[k]) for k in sample)
    assert total_in_sessions > 0

    # Enrichment
    enriched = enrich_event_for_quant(events[0])
    assert "etf_ticker" in enriched
    assert "session" in enriched
    assert "iv_category" in enriched
    assert enriched["session"] in (1, 2, 3, 4)

    # Stats
    from collections import Counter
    session_dist = Counter(event_session(e) for e in events)
    etf_dist = Counter(sector_to_etf(e.get("signal_sector", "")) for e in events)

    print("[session_data.py] all self-tests pass")
    print(f"  Loaded {len(events)} events across {len(days)} days")
    print(f"  Session distribution: s1={session_dist[1]} s2={session_dist[2]} "
          f"s3={session_dist[3]} s4={session_dist[4]}")
    print(f"  ETF distribution: {dict(etf_dist.most_common())}")
    print(f"  Sample date {sample_date}: s1={len(sample['s1'])} s2={len(sample['s2'])} "
          f"s3={len(sample['s3'])} s4={len(sample['s4'])}")
    print(f"  Enriched event[0]: ticker={enriched.get('ticker')} etf={enriched['etf_ticker']} "
          f"session={enriched['session']} iv_cat={enriched['iv_category']} "
          f"bias={enriched['direction_bias']}")
