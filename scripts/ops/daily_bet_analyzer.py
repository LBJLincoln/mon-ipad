#!/usr/bin/env python3
"""Daily per-agent bet analyzer — for each TF, for each agent, send the
day's bets + rationales to the LLM gateway and ask for analysis of what
went right/wrong + one concrete suggestion.

Produces data/audit/analysis-<tf>-<YYYY-MM-DD>.md for NBA + POL each day.

Uses LBJLincoln26/llm-gateway with mistral:large (validated cross-TF
winner) for the analysis call. No Anthropic API dependency.

Cron: 0 7 * * *   (daily 07:00 UTC, after 06:00 digest + 06:50 scorecard)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "data" / "audit"
GATEWAY = "https://lbjlincoln26-llm-gateway.hf.space/api/chat"
HTTP_TIMEOUT = 45

SPACES = {
    "nba": "LBJLincoln26/nba-llm-trading-floor",
    "pol": "LBJLincoln26/political-llm-trading-floor",
}


def _hf_headers() -> dict[str, str]:
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or ""
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _latest_day(tf: str) -> dict | None:
    repo = SPACES[tf]
    try:
        req = urllib.request.Request(
            f"https://huggingface.co/api/spaces/{repo}/tree/main?recursive=true",
            headers=_hf_headers(),
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            tree = json.loads(r.read())
    except Exception as e:
        print(f"[{tf}] tree err: {e}", file=sys.stderr)
        return None
    if not isinstance(tree, list): return None
    days = sorted(
        str(f.get("path")) for f in tree
        if isinstance(f, dict)
        and str(f.get("path","")).startswith("data/decisions/day-")
        and str(f.get("path","")).endswith(".json")
    )
    if not days: return None
    latest = days[-1]
    try:
        req = urllib.request.Request(
            f"https://huggingface.co/spaces/{repo}/resolve/main/{urllib.parse.quote(latest)}",
            headers=_hf_headers(),
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _compact_agent_bets(agent_data: dict) -> str:
    """Render the agent's allocations into a compact string for the LLM."""
    allocs = agent_data.get("allocations") or []
    if not allocs:
        return "no bets today"
    lines = []
    for a in allocs[:15]:
        game = a.get("game") or a.get("event_id") or "?"
        cat = a.get("category") or "?"
        stake = a.get("stake") or 0
        won = a.get("won")
        edge = a.get("edge") or 0
        odds = a.get("odds") or "?"
        prof = a.get("profit") or 0
        rat = (a.get("rationale") or a.get("thesis") or "")[:120]
        result = "W" if won is True else ("L" if won is False else "-")
        lines.append(f"  [{result}] {game} {cat} stake={stake} edge={edge:.2f} odds={odds} pnl={prof:+.1f}")
        if rat: lines.append(f"    thesis: {rat}")
    return "\n".join(lines)


def _analyze_agent(tf: str, tid: str, data: dict, date: str) -> str:
    """Call LLM for one-agent analysis. Returns markdown fragment."""
    bk_before = data.get("bankroll_before")
    bk_after = data.get("bankroll_after")
    day_pnl = (float(bk_after or 0) - float(bk_before or 0)) if (bk_before and bk_after) else None
    bets = _compact_agent_bets(data)
    prompt_user = (
        f"Agent {tid} on {tf.upper()} TF, day {date}:\n"
        f"Bankroll: ${bk_before} -> ${bk_after} (PnL ${day_pnl:+.2f})\n\n"
        f"Today's bets:\n{bets}\n\n"
        "Analyze in 4-6 bullet points:\n"
        "1. Patterns in winning vs losing picks (category? edge size? thesis quality?)\n"
        "2. One specific mistake worth correcting tomorrow\n"
        "3. One strength to keep\n"
        "Stay under 200 words. Data-driven, no filler."
    )
    body = json.dumps({
        "model": "mistral:large",  # cross-TF proven winner
        "messages": [{"role": "user", "content": prompt_user}],
        "max_tokens": 500,
        "temperature": 0.2,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(GATEWAY, data=body,
                                      headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            resp = json.loads(r.read())
        return resp.get("content") or resp.get("response") or "(no content)"
    except Exception as e:
        return f"_(gateway error: {type(e).__name__})_"


def analyze_tf(tf: str) -> str | None:
    day = _latest_day(tf)
    if not day: return None
    day_idx = day.get("day_idx", "?")
    date = day.get("date", "?")
    agents = day.get("agents") or {}
    out = [f"# {tf.upper()} day-{day_idx} ({date}) — per-agent analysis",
           f"Generated {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
           ""]
    # Sort by day_pnl absolute (biggest winners + losers first)
    scored = []
    for tid, a in agents.items():
        bk_b = float(a.get("bankroll_before") or 0)
        bk_a = float(a.get("bankroll_after") or 0)
        scored.append((tid, a, bk_a - bk_b))
    scored.sort(key=lambda x: -abs(x[2]))
    for tid, a, pnl in scored[:8]:  # top 8 by |PnL| — analysis budget
        analysis = _analyze_agent(tf, tid, a, date)
        out.append(f"## `{tid}` — day PnL ${pnl:+.2f}")
        out.append(analysis)
        out.append("")
    return "\n".join(out)


def main() -> int:
    AUDIT.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    for tf in SPACES:
        try:
            md = analyze_tf(tf)
            if md:
                out = AUDIT / f"analysis-{tf}-{today}.md"
                out.write_text(md)
                print(f"wrote {out}")
            else:
                print(f"[{tf}] no day data")
        except Exception as e:
            print(f"[{tf}] FATAL {type(e).__name__}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
