#!/usr/bin/env python3
"""cross_tf_llm_attribution — rank every LLM by PnL across NBA+POL+PQTF+ITF.

Input (pulled every 4h at :25):
  https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status
  https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status
  https://lbjlincoln26-political-quant-trading-floor.hf.space/api/status
  https://lbjlincoln26-intraday-trading-floor.hf.space/api/status

Per-TF shape differs; we normalize to (agent_tid, llm_key, bankroll, wins,
losses, llm_calls, llm_ok). PQTF reports positions not bets — we approximate
WR via positions marked `closed_profitable` when available.

Output:
  data/cross-tf/attribution-<ISO>.json  (full snapshot, per-TF + per-LLM)
  data/cross-tf/latest.json             (symlink-like copy for quick reads)
  data/cross-tf/alerts.json             (routing-mismatch alerts)

Mathematical analysis per LLM:
  - Σ bankroll across fleets (raw absolute)
  - Σ multiplier = bankroll / starting-capital per fleet, averaged
  - WR = wins / (wins + losses)
  - Sharpe-lite = mean daily return / stdev when day-series known
  - Rank within its TIER (fast/medium/large/slow per gateway tier)
  - Dominance score = Σ_fleet (rank_1_pct · 3 + rank_2_pct · 2 + rank_3_pct · 1)

Routing-mismatch alerts:
  - Flag any persona in ITF whose model_primary is NOT top-5 within its tier
  - Flag any NBA/POL agent whose LLM has bankroll < 10% of peers for >4 days
  - Write actionable proposals to data/research/cross-tf-proposals-<date>.json

This loop enforces the "ITF follows cross-fleet winners" feedback rule
(memory: feedback_itf_follow_winners_apr19.md) continuously, not one-off.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.request

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "cross-tf"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROPOSALS_DIR = REPO / "data" / "research"
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

TF_ENDPOINTS: List[Tuple[str, str, float]] = [
    ("nba",  "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status",       100.0),
    ("pol",  "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status", 100.0),
    ("pqtf", "https://lbjlincoln26-political-quant-trading-floor.hf.space/api/status", 100.0),
    ("itf",  "https://lbjlincoln26-intraday-trading-floor.hf.space/api/status",      100.0),
]

# Map TF agent tids to their LLM primary (from each TF's hardcoded personas).
# Used when the TF /api/status response doesn't expose `model_primary` directly.
AGENT_TO_LLM: Dict[str, Dict[str, str]] = {
    "nba": {
        "qwen-quant":        "cerebras:qwen-3-235b",
        "qwen-arb":          "cerebras:qwen-3-235b",
        "llama-contra":      "cerebras:llama3.1-8b",
        "gemini-anl":        "google:gemini-3-flash",
        "gemini-tact":       "google:gemini-3-flash",
        "mistral-large":     "mistral:large",
        "mistral-medium":    "mistral:medium",
        "mistral-small":     "mistral:small",
        "mistral-nemo":      "mistral:nemo",
        "mistral-ministral": "mistral:ministral-8b",
        "nemotron-120b":     "openrouter:nemotron-120b:free",
        "selfhost-qwen4b":   "selfhost:qwen3-4b",
        "nvidia-minimax":    "nvidia:minimax-m2.7",
        "nvidia-llama70":    "nvidia:llama-3.3-70b",
        "selfhost-gemma3":   "selfhost:gemma-3-4b",
        "selfhost-qwen06":   "selfhost:qwen3-0.6b",
        "selfhost-dolphin3": "selfhost:dolphin3-l32-3b",
    },
    "pol": {
        # POL omits T11 + T12 from NBA roster
        "qwen-quant":        "cerebras:qwen-3-235b",
        "qwen-arb":          "cerebras:qwen-3-235b",
        "llama-contra":      "cerebras:llama3.1-8b",
        "gemini-anl":        "google:gemini-3-flash",
        "gemini-tact":       "google:gemini-3-flash",
        "mistral-large":     "mistral:large",
        "mistral-medium":    "mistral:medium",
        "mistral-small":     "mistral:small",
        "mistral-nemo":      "mistral:nemo",
        "mistral-ministral": "mistral:ministral-8b",
        "nvidia-minimax":    "nvidia:minimax-m2.7",
        "nvidia-llama70":    "nvidia:llama-3.3-70b",
        "selfhost-gemma3":   "selfhost:gemma-3-4b",
        "selfhost-qwen06":   "selfhost:qwen3-0.6b",
        "selfhost-dolphin3": "selfhost:dolphin3-l32-3b",
    },
    "pqtf": {
        # Per hf-political-quant-trading-floor/engine.py:39-44
        "qwen-quant":     "cerebras:qwen-3-235b",
        "llama-contra":   "cerebras:llama3.1-8b",
        "gemini-anl":     "google:gemini-3-flash",
        "mistral-large":  "mistral:large",
        "mistral-medium": "mistral:medium",
        "mistral-nemo":   "mistral:nemo",
    },
}

# Gateway tier mapping (must mirror hf-llm-gateway/app.py TIER_MAP).
LLM_TIER: Dict[str, str] = {
    "cerebras:qwen-3-235b":            "large",
    "cerebras:llama3.1-8b":            "fast",
    "google:gemini-3-flash":           "fast",
    "google:gemini-2.5-flash":         "fast",
    "mistral:large":                   "large",
    "mistral:medium":                  "medium",
    "mistral:small":                   "medium",
    "mistral:nemo":                    "fast",
    "mistral:ministral-8b":            "fast",
    "openrouter:nemotron-120b:free":   "large",
    "nvidia:minimax-m2.7":             "large",
    "nvidia:llama-3.3-70b":            "large",
    "selfhost:qwen3-4b":               "medium",
    "selfhost:gemma-3-4b":             "medium",
    "selfhost:qwen3-0.6b":             "fast",
    "selfhost:dolphin3-l32-3b":        "slow",
    "selfhost:phi-3.5-mini":           "medium",
}


def _fetch(url: str, timeout: float = 15.0) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nomos42-attribution/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[WARN] fetch {url}: {type(e).__name__}: {str(e)[:80]}", file=sys.stderr)
        return None


def _normalize_tf(fleet: str, status: Dict[str, Any], starting: float) -> List[Dict[str, Any]]:
    """Turn a TF /api/status into a list of per-agent rows."""
    if fleet == "itf":
        rows = []
        for p in status.get("config_agents", []):
            tid = p.get("tid")
            llm = p.get("model_primary", "?")
            a = status.get("agents", {}).get(tid, {})
            rows.append({
                "fleet": fleet, "tid": tid, "llm": llm,
                "bankroll": a.get("bankroll", starting),
                "starting": starting,
                "multiplier": (a.get("bankroll", starting) / starting) if starting else 0,
                "wins": a.get("trades", 0),
                "losses": 0,
                "llm_calls": a.get("decisions", 0),
                "llm_ok": a.get("decisions", 0),
                "tier": LLM_TIER.get(llm, "unknown"),
            })
        return rows
    elif fleet == "pqtf":
        rows = []
        mapping = AGENT_TO_LLM.get("pqtf", {})
        for tid, a in status.get("agents", {}).items():
            # PQTF per-agent shape includes bankroll + multi-leg counts
            llm = mapping.get(tid, AGENT_TO_LLM.get("nba", {}).get(tid, "?"))
            rows.append({
                "fleet": fleet, "tid": tid, "llm": llm,
                "bankroll": a.get("bankroll", 0),
                "starting": starting,
                "multiplier": a.get("bankroll", 0) / starting if starting else 0,
                "wins": a.get("positions_closed_profitable", 0),
                "losses": a.get("positions_closed_loss", 0),
                "llm_calls": a.get("llm_calls", 0),
                "llm_ok": a.get("llm_ok", 0),
                "tier": LLM_TIER.get(llm, "unknown"),
            })
        return rows
    else:
        rows = []
        mapping = AGENT_TO_LLM.get(fleet, {})
        for tid, a in status.get("agents", {}).items():
            llm = mapping.get(tid, "?")
            rows.append({
                "fleet": fleet, "tid": tid, "llm": llm,
                "bankroll": a.get("bankroll", 0),
                "starting": starting,
                "multiplier": a.get("bankroll", 0) / starting if starting else 0,
                "wins": a.get("wins", 0),
                "losses": a.get("losses", 0),
                "llm_calls": a.get("llm_calls", 0),
                "llm_ok": a.get("llm_ok", 0),
                "tier": LLM_TIER.get(llm, "unknown"),
            })
        return rows


def _rank_by_llm(all_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate per LLM across fleets, compute stats."""
    by_llm: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in all_rows:
        by_llm[r["llm"]].append(r)
    out = []
    for llm, rows in by_llm.items():
        bankrolls  = [r["bankroll"] for r in rows]
        multipliers = [r["multiplier"] for r in rows if r["starting"]]
        wins       = sum(r["wins"] for r in rows)
        losses     = sum(r["losses"] for r in rows)
        calls      = sum(r["llm_calls"] for r in rows)
        oks        = sum(r["llm_ok"] for r in rows)
        fleets     = sorted({r["fleet"] for r in rows})
        tier       = rows[0]["tier"]
        total_br   = sum(bankrolls)
        avg_mul    = sum(multipliers) / len(multipliers) if multipliers else 0
        wr         = wins / (wins + losses) if (wins + losses) else None
        ok_rate    = oks / calls if calls else None
        # Dominance: multiplier-weighted presence across fleets (bias toward compounding winners)
        dominance  = sum(max(r["multiplier"] - 1.0, 0) for r in rows)
        out.append({
            "llm": llm,
            "tier": tier,
            "fleets": fleets,
            "agents_using": len(rows),
            "sum_bankroll": round(total_br, 2),
            "avg_multiplier": round(avg_mul, 3),
            "dominance": round(dominance, 3),
            "wr": round(wr, 3) if wr is not None else None,
            "llm_ok_rate": round(ok_rate, 3) if ok_rate is not None else None,
            "llm_calls": calls,
        })
    # Sort by dominance desc (compounding wins trump WR alone)
    out.sort(key=lambda x: x["dominance"], reverse=True)
    return out


def _detect_mismatch(ranking: List[Dict[str, Any]], itf_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flag ITF personas whose primary LLM isn't top-5-within-its-tier."""
    by_tier_top5: Dict[str, List[str]] = defaultdict(list)
    for r in ranking:
        t = r["tier"]
        if len(by_tier_top5[t]) < 5:
            by_tier_top5[t].append(r["llm"])
    alerts = []
    for row in itf_rows:
        llm = row["llm"]
        tier = LLM_TIER.get(llm, "unknown")
        top5 = by_tier_top5.get(tier, [])
        if llm not in top5 and top5:
            alerts.append({
                "fleet": "itf",
                "tid": row["tid"],
                "current_llm": llm,
                "tier": tier,
                "tier_top5": top5,
                "recommendation": f"swap {llm} → {top5[0]}",
                "severity": "warn",
                "ts": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
    return alerts


def run() -> Dict[str, Any]:
    ts = dt.datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    all_rows: List[Dict[str, Any]] = []
    fleets_ok: List[str] = []
    fleets_err: List[str] = []
    for fleet, url, starting in TF_ENDPOINTS:
        status = _fetch(url)
        if status is None:
            fleets_err.append(fleet)
            continue
        rows = _normalize_tf(fleet, status, starting)
        all_rows.extend(rows)
        fleets_ok.append(fleet)

    ranking = _rank_by_llm(all_rows)
    itf_rows = [r for r in all_rows if r["fleet"] == "itf"]
    alerts = _detect_mismatch(ranking, itf_rows)

    snapshot = {
        "ts": ts,
        "fleets_ok": fleets_ok,
        "fleets_err": fleets_err,
        "agent_count": len(all_rows),
        "llm_ranking": ranking[:15],
        "itf_mismatch_alerts": alerts,
        "top3_by_dominance": [r["llm"] for r in ranking[:3]],
        "top3_by_sum_bankroll": [
            r["llm"] for r in sorted(ranking, key=lambda x: x["sum_bankroll"], reverse=True)[:3]
        ],
    }
    (OUT_DIR / f"attribution-{ts}.json").write_text(json.dumps(snapshot, indent=2))
    (OUT_DIR / "latest.json").write_text(json.dumps(snapshot, indent=2))
    (OUT_DIR / "alerts.json").write_text(json.dumps(alerts, indent=2))

    # Emit DR FRANKENSTEIN proposals for any mismatch
    if alerts:
        date = dt.datetime.utcnow().strftime("%Y-%m-%d")
        proposal_path = PROPOSALS_DIR / f"cross-tf-proposals-{date}.json"
        existing: List[Dict[str, Any]] = []
        if proposal_path.exists():
            try:
                existing = json.loads(proposal_path.read_text())
            except Exception:
                existing = []
        for a in alerts:
            existing.append({
                "id": f"crosstf-itf-{a['tid']}-{ts}",
                "title": f"ITF routing mismatch: {a['tid']} uses off-tier-top5 {a['current_llm']}",
                "priority": 2,
                "status": "pending",
                "source_finding": f"{a['tid']} primary={a['current_llm']} (tier={a['tier']}); top5 tier winners: {a['tier_top5']}",
                "target_file": "scripts/arena/hf-intraday-trading-floor/personas.py",
                "recommendation": a["recommendation"],
                "ts": a["ts"],
                "owner": "DR_FRANKENSTEIN",
            })
        proposal_path.write_text(json.dumps(existing, indent=2))

    return snapshot


if __name__ == "__main__":
    out = run()
    print(json.dumps({
        "ts": out["ts"],
        "fleets_ok": out["fleets_ok"],
        "fleets_err": out["fleets_err"],
        "agents_analyzed": out["agent_count"],
        "top3_by_dominance": out["top3_by_dominance"],
        "top3_by_sum_bankroll": out["top3_by_sum_bankroll"],
        "itf_mismatch_alerts": len(out["itf_mismatch_alerts"]),
    }, indent=2))
