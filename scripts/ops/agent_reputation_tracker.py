#!/usr/bin/env python3
"""Agent reputation tracker — 7-day rolling WR/Brier/PnL per agent per TF.

Produces data/ops/agent-reputation.json that each TF can include in the
context so LOSING agents see WHO the winners are + what they bet (mirror
axelrod cooperation: follow the winners).

Writes a compact block per TF:
  NBA 7d leaders: llama-contra +$47.20 wr=60% brier=0.23 / selfhost-qwen4b ...
  POL 7d leaders: qwen-quant +$483 wr=54% brier=0.21 / qwen-arb ...
  ITF 7d leaders: options-1 +$402 / vol-1 +$231 / ...

Cron: :25 every 2h  (runs after rigorous :10 and improvement :20)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "ops" / "agent-reputation.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

SPACES = {
    "nba": "LBJLincoln26/nba-llm-trading-floor",
    "pol": "LBJLincoln26/political-llm-trading-floor",
}
WINDOW_DAYS = 7
HTTP_TIMEOUT = 15


def _hf_hdr() -> dict:
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or ""
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _http_json(url: str):
    try:
        req = urllib.request.Request(url, headers=_hf_hdr())
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _tf_reputation(tf: str) -> dict:
    repo = SPACES[tf]
    tree = _http_json(f"https://huggingface.co/api/spaces/{repo}/tree/main?recursive=true")
    if not isinstance(tree, list): return {"error": "no tree"}
    days = sorted(
        str(f.get("path")) for f in tree
        if isinstance(f, dict)
        and str(f.get("path","")).startswith("data/decisions/day-")
        and str(f.get("path","")).endswith(".json")
    )[-WINDOW_DAYS:]
    if not days: return {"error": "no days"}

    per_agent = defaultdict(lambda: {"bets": 0, "wins": 0, "losses": 0, "pnl": 0.0, "brier_sum": 0.0, "brier_n": 0})
    for p in days:
        d = _http_json(f"https://huggingface.co/spaces/{repo}/resolve/main/{urllib.parse.quote(p)}")
        if not isinstance(d, dict): continue
        for tid, a in (d.get("agents") or {}).items():
            for b in (a.get("allocations") or []):
                slot = per_agent[tid]
                slot["bets"] += 1
                won = b.get("won")
                if won: slot["wins"] += 1
                elif won is False: slot["losses"] += 1
                try: slot["pnl"] += float(b.get("profit") or b.get("pnl") or 0)
                except Exception: pass
                conf = b.get("confidence")
                if conf is not None and won is not None:
                    try:
                        cv = float(conf)
                        if 0 <= cv <= 1:
                            slot["brier_sum"] += (cv - (1 if won else 0)) ** 2
                            slot["brier_n"] += 1
                    except Exception: pass

    out = []
    for tid, s in per_agent.items():
        wr = s["wins"] / max(1, s["wins"] + s["losses"])
        br = s["brier_sum"] / s["brier_n"] if s["brier_n"] else None
        out.append({
            "tid": tid, "bets": s["bets"], "wins": s["wins"], "losses": s["losses"],
            "wr": round(wr, 3), "pnl": round(s["pnl"], 2),
            "brier": round(br, 4) if br else None,
        })
    out.sort(key=lambda r: -r["pnl"])
    return {"window_days": WINDOW_DAYS, "agents": out}


def _prompt_block(tf: str, rep: dict) -> str:
    """Compact text block for injection into agent prompts."""
    if not rep.get("agents"):
        return ""
    leaders = rep["agents"][:3]
    laggers = [a for a in rep["agents"] if a.get("pnl", 0) < -5][-3:]
    lines = [f"LIVE 7-DAY AGENT REPUTATION ({tf.upper()}):"]
    for a in leaders:
        br = f" brier={a['brier']}" if a.get("brier") is not None else ""
        lines.append(f"  LEADER {a['tid']}: PnL ${a['pnl']:+.2f}  WR {a['wr']:.0%}  bets {a['bets']}{br}")
    for a in laggers:
        br = f" brier={a['brier']}" if a.get("brier") is not None else ""
        lines.append(f"  LAGGER {a['tid']}: PnL ${a['pnl']:+.2f}  WR {a['wr']:.0%}  bets {a['bets']}{br}")
    lines.append(
        "COOPERATION RULE: if you are on this LAGGER list, your axelrod strategy defaults "
        "to IMITATING the LEADERS' bet categories next day. If you're on the LEADER list, "
        "your pacts carry MORE weight in peer decisions."
    )
    return "\n".join(lines)


def main() -> int:
    result = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "tfs": {}}
    for tf in SPACES:
        rep = _tf_reputation(tf)
        result["tfs"][tf] = rep
        result["tfs"][tf]["prompt_block"] = _prompt_block(tf, rep)
    OUT.write_text(json.dumps(result, indent=2, default=str))
    print(f"wrote {OUT}")
    for tf, r in result["tfs"].items():
        if r.get("agents"):
            top = r["agents"][0]
            print(f"  {tf.upper()} leader: {top['tid']} pnl=${top['pnl']:+.2f} wr={top['wr']:.0%}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
