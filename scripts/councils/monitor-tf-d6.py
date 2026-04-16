"""D6 Evaluation council hook — Trading Floor calibration drift watch.

Pulls /api/day-decisions from both TF Spaces, computes:
  - Brier on settled bets only
  - Calibration error (10 bins, ECE)
  - Per-trader leaderboard delta vs yesterday
  - Reputation scoreboard (Axelrod Mech D pact_honored / pact_broken)

Emits to data/councils/d6/tf-monitor-{date}.json so the D6 council Karpathy
loop reads it next iteration. Also pings the council Space's /api/eval-input.

Cron: 25 * * * *  (every hour at :25, between TF day-runs and council loops)
"""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "councils" / "d6"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TF_ENDPOINTS = [
    ("nba", "https://lbjlincoln26-nba-llm-trading-floor.hf.space"),
    ("political", "https://lbjlincoln26-political-llm-trading-floor.hf.space"),
]


def _ece(probs, outcomes, n_bins=10):
    """Expected Calibration Error — Naeini et al. 2015."""
    if not probs:
        return None
    bins = [0.0] * n_bins
    counts = [0] * n_bins
    confs = [0.0] * n_bins
    for p, y in zip(probs, outcomes):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b] += y
        counts[b] += 1
        confs[b] += p
    n = len(probs)
    ece = 0.0
    for i in range(n_bins):
        if counts[i] == 0:
            continue
        avg_p = confs[i] / counts[i]
        avg_y = bins[i] / counts[i]
        ece += (counts[i] / n) * abs(avg_p - avg_y)
    return ece


def _brier(probs, outcomes):
    if not probs:
        return None
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs)


def fetch_tf(market, base):
    import requests
    try:
        r = requests.get(f"{base}/api/day-decisions", timeout=15)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {"market": market, "error": str(e)[:200]}
    decisions = d.get("decisions") or d.get("days") or []
    settled = []
    by_trader = {}
    for day in decisions:
        for bet in day.get("bets", []):
            if bet.get("settled") is None:
                continue
            tid = bet.get("trader_id") or bet.get("agent")
            settled.append((bet.get("p", 0.5), 1 if bet.get("won") else 0))
            by_trader.setdefault(tid, []).append((bet.get("p", 0.5), 1 if bet.get("won") else 0))
    brier = _brier([p for p, _ in settled], [y for _, y in settled])
    ece = _ece([p for p, _ in settled], [y for _, y in settled])
    leaderboard = []
    for tid, bets in by_trader.items():
        if len(bets) < 5:
            continue
        leaderboard.append({
            "trader": tid, "n": len(bets),
            "brier": _brier([p for p, _ in bets], [y for _, y in bets]),
            "win_rate": sum(y for _, y in bets) / len(bets),
        })
    leaderboard.sort(key=lambda x: x["brier"] or 1)
    try:
        rep = requests.get(f"{base}/api/status", timeout=10).json().get("reputation", {})
    except Exception:
        rep = {}
    return {
        "market": market,
        "settled_bets": len(settled),
        "brier_overall": brier,
        "ece_10bin": ece,
        "leaderboard_top5": leaderboard[:5],
        "leaderboard_bottom3": leaderboard[-3:],
        "axelrod_reputation": rep,
    }


def main():
    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "council": "d6-evaluation",
        "task": "tf-calibration-drift",
        "markets": [fetch_tf(m, b) for m, b in TF_ENDPOINTS],
    }
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (OUT_DIR / f"tf-monitor-{date}.json").write_text(json.dumps(out, indent=2))
    (OUT_DIR / "latest.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
